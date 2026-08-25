"""Topology-aware deterministic placer for the placement contest.

The strategy is deliberately small and rule-focused:

1. Build an analytical floorplan from the net names and component classes.
2. Put critical peripherals (regulator caps, crystal load caps, USB series
   resistors, decouplers) near the pins they serve.
3. Run a bounded coordinate descent with a local surrogate cost that heavily
   penalizes rule-relevant violations before HPWL.

Only a placement dictionary is returned; the input design is never mutated.
"""

from __future__ import annotations

import copy
import math
import time
from dataclasses import dataclass

from .. import geom
from ..pcb import Component
from .base import Placement, PlacementContext

IGNORE_NETS = {"GND", "AGND", "NC"}
EDGE_CLEARANCE_MM = 2.0
COURTYARD_CLEARANCE_MM = 0.2


@dataclass(frozen=True)
class _Pin:
    ref: str
    pin: str
    pintype: str
    net: str
    x: float
    y: float

    def distance_to(self, other: "_Pin") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


class Codex:
    name = "codex"

    def run(self, ctx: PlacementContext) -> Placement:
        started = time.perf_counter()
        movable = set(ctx.movable())
        state: Placement = {
            c.ref: (c.x, c.y, _snap_rotation(c.rotation))
            for c in ctx.design.board.components
        }

        _seed_critical_floorplan(ctx, state, movable)
        state = _improve(ctx, state, movable, started)

        return {
            ref: state[ref]
            for ref in sorted(movable)
            if ref in state
        }


def _seed_critical_floorplan(
    ctx: PlacementContext, state: Placement, movable: set[str]
) -> None:
    comps = {c.ref: c for c in ctx.design.board.components}
    minx, miny, maxx, maxy = ctx.outline()
    width = maxx - minx
    height = maxy - miny

    def put(ref: str, x: float, y: float, rot: float = 0.0) -> None:
        comp = comps.get(ref)
        if comp is None or ref not in movable:
            return
        state[ref] = (*_clamp_center(comp, x, y, rot, ctx.outline()), rot)

    ics = sorted(
        [c for c in comps.values() if c.ref in movable and ctx.design.kind_of(c.ref) == "ic"],
        key=lambda c: (-len(c.pads), c.ref),
    )
    if not ics:
        return

    main = ics[0]
    regulators = [
        c for c in ics[1:]
        if {"VBUS", "3V3"}.issubset(_nets_of(ctx, c.ref))
        or "LDO" in ctx.design.value_of(c.ref).upper()
        or "AP2112" in ctx.design.value_of(c.ref).upper()
    ]
    regulator = regulators[0] if regulators else (ics[1] if len(ics) > 1 else None)
    peripherals = [c for c in ics[1:] if c is not regulator]

    main_x = minx + 0.52 * width
    main_y = miny + 0.62 * height
    put(main.ref, main_x, main_y)

    if regulator is not None:
        put(regulator.ref, minx + 0.27 * width, miny + 0.73 * height)

    for i, periph in enumerate(peripherals):
        put(periph.ref, minx + (0.705 + 0.04 * i) * width, miny + 0.71 * height)

    _place_regulator_caps(ctx, state, movable, regulator)
    _place_decouplers(ctx, state, movable, main, peripherals)
    _place_crystal_cluster(ctx, state, movable, main)
    _place_usb_series_resistors(ctx, state, movable)
    _place_pullups(ctx, state, movable, main, peripherals)


def _place_regulator_caps(
    ctx: PlacementContext,
    state: Placement,
    movable: set[str],
    regulator: Component | None,
) -> None:
    if regulator is None:
        return
    comps = {c.ref: c for c in ctx.design.board.components}
    reg_x, reg_y, _ = state[regulator.ref]
    uf_caps = [
        c for c in comps.values()
        if c.ref in movable
        and ctx.design.kind_of(c.ref) == "capacitor"
        and "UF" in ctx.design.value_of(c.ref).upper()
    ]
    vbus_caps = sorted([c for c in uf_caps if "VBUS" in _nets_of(ctx, c.ref)], key=lambda c: c.ref)
    out_caps = sorted([c for c in uf_caps if "3V3" in _nets_of(ctx, c.ref)], key=lambda c: c.ref)

    if vbus_caps:
        _put_component(ctx, state, vbus_caps[0], reg_x - 4.6, reg_y)
    if out_caps:
        _put_component(ctx, state, out_caps[0], reg_x + 4.7, reg_y)


def _place_decouplers(
    ctx: PlacementContext,
    state: Placement,
    movable: set[str],
    main: Component,
    peripherals: list[Component],
) -> None:
    comps = {c.ref: c for c in ctx.design.board.components}
    used: set[str] = set()
    small_caps = sorted(
        [
            c for c in comps.values()
            if c.ref in movable
            and ctx.design.kind_of(c.ref) == "capacitor"
            and "PF" not in ctx.design.value_of(c.ref).upper()
            and "UF" not in ctx.design.value_of(c.ref).upper()
        ],
        key=lambda c: c.ref,
    )

    main_power = [
        p for p in ctx.design.pins_of(main.ref)
        if p.pintype == "power_in" and p.net not in IGNORE_NETS
    ]
    main_power.sort(key=lambda p: (p.net != "3V3", _pin_number(p.pin)))

    if main_power:
        cap = _first_cap_on_net(ctx, small_caps, main_power[0].net, used)
        if cap is not None:
            pin = _pin_at(ctx, state, main_power[0].ref, main_power[0].pin)
            if pin is not None:
                _place_pad_near(ctx, state, cap, main_power[0].net, pin.x, pin.y - 2.8)
                used.add(cap.ref)

    for target in main_power[1:]:
        cap = _first_cap_on_net(ctx, small_caps, target.net, used)
        if cap is None:
            continue
        pin = _pin_at(ctx, state, target.ref, target.pin)
        if pin is None:
            continue
        _place_pad_near(ctx, state, cap, target.net, pin.x + 2.6, pin.y)
        used.add(cap.ref)

    for periph in peripherals:
        targets = [
            p for p in ctx.design.pins_of(periph.ref)
            if p.pintype == "power_in" and p.net not in IGNORE_NETS
        ]
        for target in sorted(targets, key=lambda p: (_pin_number(p.pin), p.net)):
            cap = _first_cap_on_net(ctx, small_caps, target.net, used)
            if cap is None:
                continue
            pin = _pin_at(ctx, state, target.ref, target.pin)
            if pin is None:
                continue
            _place_pad_near(ctx, state, cap, target.net, pin.x, pin.y - 4.0)
            used.add(cap.ref)


def _place_crystal_cluster(
    ctx: PlacementContext, state: Placement, movable: set[str], main: Component
) -> None:
    comps = {c.ref: c for c in ctx.design.board.components}
    crystals = sorted(
        [c for c in comps.values() if c.ref in movable and ctx.design.kind_of(c.ref) == "crystal"],
        key=lambda c: c.ref,
    )
    if not crystals:
        return

    main_xpins = [
        p for p in ctx.design.pins_of(main.ref)
        if p.net.upper() in {"XIN", "XOUT"}
    ]
    if len(main_xpins) < 2:
        return
    placed = [_pin_at(ctx, state, p.ref, p.pin) for p in main_xpins]
    placed = [p for p in placed if p is not None]
    if len(placed) < 2:
        return

    avg_x = sum(p.x for p in placed) / len(placed)
    avg_y = sum(p.y for p in placed) / len(placed)
    crystal = crystals[0]
    _put_component(ctx, state, crystal, avg_x - 3.6, avg_y + 1.55)
    cx, cy, _ = state[crystal.ref]

    pf_caps = sorted(
        [
            c for c in comps.values()
            if c.ref in movable
            and ctx.design.kind_of(c.ref) == "capacitor"
            and "PF" in ctx.design.value_of(c.ref).upper()
        ],
        key=lambda c: c.ref,
    )
    by_net = {net.upper(): [] for net in ("XIN", "XOUT")}
    for cap in pf_caps:
        for net in _nets_of(ctx, cap.ref):
            if net.upper() in by_net:
                by_net[net.upper()].append(cap)

    if by_net["XIN"]:
        _put_component(ctx, state, by_net["XIN"][0], cx - 2.6, cy - 4.0)
    if by_net["XOUT"]:
        _put_component(ctx, state, by_net["XOUT"][0], cx + 0.75, cy - 4.0)


def _place_usb_series_resistors(
    ctx: PlacementContext, state: Placement, movable: set[str]
) -> None:
    comps = {c.ref: c for c in ctx.design.board.components}
    minx, _, maxx, _ = ctx.outline()
    x = minx + 0.267 * (maxx - minx)
    targets: list[tuple[str, Component, float]] = []

    for net in ("USB_DM", "USB_DP"):
        connector_pin = _locked_pin_on_net(ctx, net)
        if connector_pin is None:
            continue
        for pin in ctx.design.pins_on_net(net):
            comp = comps.get(pin.ref)
            if (
                comp is not None
                and comp.ref in movable
                and ctx.design.kind_of(comp.ref) == "resistor"
            ):
                targets.append((net, comp, connector_pin.y))

    for _, comp, y in sorted(targets, key=lambda t: t[0]):
        _put_component(ctx, state, comp, x, y)


def _place_pullups(
    ctx: PlacementContext,
    state: Placement,
    movable: set[str],
    main: Component,
    peripherals: list[Component],
) -> None:
    comps = {c.ref: c for c in ctx.design.board.components}
    pullups = []
    for comp in comps.values():
        nets = _nets_of(ctx, comp.ref)
        if (
            comp.ref in movable
            and ctx.design.kind_of(comp.ref) == "resistor"
            and "3V3" in nets
            and nets.intersection({"SDA", "SCL"})
        ):
            pullups.append(comp)
    if not pullups:
        return

    main_box = _placed_bbox(ctx, state, main.ref)
    mx, my, _ = state[main.ref]
    px = mx + 0.125 * (ctx.outline()[2] - ctx.outline()[0])
    if peripherals:
        periph_box = _placed_bbox(ctx, state, peripherals[0].ref)
        if main_box and periph_box:
            px = (main_box[2] + periph_box[0]) / 2.0

    base_y = (main_box[3] + 1.5) if main_box else my + 7.2
    for i, comp in enumerate(sorted(pullups, key=lambda c: sorted(_nets_of(ctx, c.ref)))):
        _put_component(ctx, state, comp, px, base_y + 2.3 * i)


def _improve(
    ctx: PlacementContext,
    initial: Placement,
    movable: set[str],
    started: float,
) -> Placement:
    state = dict(initial)
    best_cost = _cost(ctx, state)
    time_limit = max(0.25, min(ctx.time_budget_s * 0.65, ctx.time_budget_s - 0.1))

    refs = sorted(movable)
    for step in (2.0, 1.0, 0.5, 0.25):
        improved = True
        passes = 0
        while improved and passes < 3:
            if time.perf_counter() - started > time_limit:
                return state
            improved = False
            passes += 1
            for ref in refs:
                comp = ctx.design.component(ref)
                if comp is None or ref not in state:
                    continue
                x, y, rot = state[ref]
                candidates = [
                    (x, y),
                    (x - step, y),
                    (x + step, y),
                    (x, y - step),
                    (x, y + step),
                    (x - step, y - step),
                    (x - step, y + step),
                    (x + step, y - step),
                    (x + step, y + step),
                ]

                local_best = state[ref]
                local_cost = best_cost
                for cx, cy in candidates:
                    nx, ny = _clamp_center(comp, cx, cy, rot, ctx.outline())
                    trial = dict(state)
                    trial[ref] = (nx, ny, rot)
                    cost = _cost(ctx, trial)
                    if cost + 1e-6 < local_cost:
                        local_cost = cost
                        local_best = trial[ref]

                if local_best != state[ref]:
                    state[ref] = local_best
                    best_cost = local_cost
                    improved = True

    return state


def _cost(ctx: PlacementContext, state: Placement) -> float:
    comps = _placed_components(ctx, state)
    pins_by_net = _pins_by_net(ctx, comps)

    hpwl = 0.0
    net_hpwl: dict[str, float] = {}
    for net, pins in pins_by_net.items():
        length = _hpwl(pins)
        net_hpwl[net] = length
        weight = 1.0
        if net in {"XIN", "XOUT", "USB_DP", "USB_DM"}:
            weight = 3.0
        elif net in {"3V3", "VBUS", "AVDD"}:
            weight = 1.6
        hpwl += weight * length

    penalty = 0.0
    penalty += _edge_penalty(ctx, comps)
    penalty += _overlap_penalty(comps)
    penalty += _decoupling_penalty(ctx, comps, pins_by_net)
    penalty += _regulator_cap_penalty(ctx, comps, pins_by_net)
    penalty += _crystal_penalty(ctx, comps, pins_by_net, net_hpwl)
    penalty += _usb_pair_penalty(net_hpwl)
    penalty += _net_budget_penalty(net_hpwl)
    return penalty + hpwl


def _edge_penalty(ctx: PlacementContext, comps: dict[str, Component]) -> float:
    minx, miny, maxx, maxy = ctx.outline()
    penalty = 0.0
    for ref in ctx.movable():
        comp = comps.get(ref)
        if comp is None or not comp.courtyard:
            continue
        cx1, cy1, cx2, cy2 = comp.courtyard
        margin = min(cx1 - minx, cy1 - miny, maxx - cx2, maxy - cy2)
        if margin < EDGE_CLEARANCE_MM:
            miss = EDGE_CLEARANCE_MM - margin
            penalty += 50_000.0 + 5_000.0 * miss * miss
    return penalty


def _overlap_penalty(comps: dict[str, Component]) -> float:
    all_comps = [c for c in comps.values() if c.courtyard_poly]
    penalty = 0.0
    for i, a in enumerate(all_comps):
        ax1, ay1, ax2, ay2 = a.courtyard
        for b in all_comps[i + 1:]:
            if (a.layer.startswith("B.")) != (b.layer.startswith("B.")):
                continue
            bx1, by1, bx2, by2 = b.courtyard
            if max(max(bx1 - ax2, ax1 - bx2), max(by1 - ay2, ay1 - by2)) >= COURTYARD_CLEARANCE_MM:
                continue
            gap = 0.0 if geom.overlap(a.courtyard_poly, b.courtyard_poly) else geom.distance(a.courtyard_poly, b.courtyard_poly)
            if gap < COURTYARD_CLEARANCE_MM:
                miss = COURTYARD_CLEARANCE_MM - gap
                penalty += 60_000.0 + 8_000.0 * miss * miss
    return penalty


def _decoupling_penalty(
    ctx: PlacementContext,
    comps: dict[str, Component],
    pins_by_net: dict[str, list[_Pin]],
) -> float:
    penalty = 0.0
    claimed: set[str] = set()
    for net, pins in pins_by_net.items():
        if net in IGNORE_NETS:
            continue
        targets = [
            p for p in pins
            if ctx.design.kind_of(p.ref) == "ic" and p.pintype == "power_in"
        ]
        partners = [
            p for p in pins
            if p.ref in comps and ctx.design.kind_of(p.ref) == "capacitor"
        ]
        penalty += _exclusive_distance_penalty(targets, partners, 6.0, claimed, 45_000.0, 2_000.0)
    return penalty


def _regulator_cap_penalty(
    ctx: PlacementContext,
    comps: dict[str, Component],
    pins_by_net: dict[str, list[_Pin]],
) -> float:
    regulators = {
        c.ref for c in comps.values()
        if ctx.design.kind_of(c.ref) == "ic"
        and (
            {"VBUS", "3V3"}.issubset(_nets_of(ctx, c.ref))
            or "LDO" in ctx.design.value_of(c.ref).upper()
            or "AP2112" in ctx.design.value_of(c.ref).upper()
        )
    }
    if not regulators:
        return 0.0

    penalty = 0.0
    for net, pins in pins_by_net.items():
        if net in IGNORE_NETS:
            continue
        targets = [p for p in pins if p.ref in regulators]
        partners = [
            p for p in pins
            if p.ref in comps
            and ctx.design.kind_of(p.ref) == "capacitor"
            and "UF" in ctx.design.value_of(p.ref).upper()
        ]
        if not targets:
            continue
        if not partners:
            penalty += 30_000.0 * len(targets)
            continue
        for target in targets:
            best = min((target.distance_to(partner) for partner in partners), default=math.inf)
            if best > 8.0:
                miss = best - 8.0
                penalty += 25_000.0 + 1_000.0 * miss * miss
    return penalty


def _crystal_penalty(
    ctx: PlacementContext,
    comps: dict[str, Component],
    pins_by_net: dict[str, list[_Pin]],
    net_hpwl: dict[str, float],
) -> float:
    penalty = 0.0
    claimed: set[str] = set()
    for net, pins in pins_by_net.items():
        if net in IGNORE_NETS:
            continue
        targets = [p for p in pins if ctx.design.kind_of(p.ref) == "crystal"]
        partners = [
            p for p in pins
            if p.ref in comps
            and ctx.design.kind_of(p.ref) == "capacitor"
            and "PF" in ctx.design.value_of(p.ref).upper()
        ]
        penalty += _exclusive_distance_penalty(targets, partners, 6.0, claimed, 45_000.0, 2_000.0)

    for net in ("XIN", "XOUT"):
        length = net_hpwl.get(net, 0.0)
        if length > 12.0:
            miss = length - 12.0
            penalty += 40_000.0 + 1_500.0 * miss * miss
    return penalty


def _usb_pair_penalty(net_hpwl: dict[str, float]) -> float:
    if "USB_DP" not in net_hpwl or "USB_DM" not in net_hpwl:
        return 0.0
    spread = abs(net_hpwl["USB_DP"] - net_hpwl["USB_DM"])
    if spread <= 3.0:
        return 0.0
    miss = spread - 3.0
    return 40_000.0 + 1_500.0 * miss * miss


def _net_budget_penalty(net_hpwl: dict[str, float]) -> float:
    penalty = 0.0
    for net in ("3V3", "VBUS", "AVDD"):
        length = net_hpwl.get(net, 0.0)
        if length > 60.0:
            miss = length - 60.0
            penalty += 8_000.0 + 800.0 * miss * miss
    for net, length in net_hpwl.items():
        if net.startswith(("SDA", "SCL", "TX", "RX", "nRESET", "GPIO")) and length > 45.0:
            miss = length - 45.0
            penalty += 6_000.0 + 500.0 * miss * miss
    return penalty


def _exclusive_distance_penalty(
    targets: list[_Pin],
    partners: list[_Pin],
    limit: float,
    claimed: set[str],
    base: float,
    scale: float,
) -> float:
    if not targets:
        return 0.0
    if not partners:
        return base * len(targets)

    pairs: list[tuple[float, _Pin, _Pin]] = []
    for target in targets:
        for partner in partners:
            if partner.ref != target.ref:
                pairs.append((target.distance_to(partner), target, partner))
    pairs.sort(key=lambda item: item[0])

    matched: dict[tuple[str, str], tuple[float, _Pin]] = {}
    used: set[str] = set()
    for dist, target, partner in pairs:
        key = (target.ref, target.pin)
        if key in matched or partner.ref in claimed or partner.ref in used:
            continue
        matched[key] = (dist, partner)
        used.add(partner.ref)
    claimed.update(used)

    penalty = 0.0
    for target in targets:
        hit = matched.get((target.ref, target.pin))
        if hit is None:
            penalty += base
            continue
        dist, _ = hit
        if dist > limit:
            miss = dist - limit
            penalty += base + scale * miss * miss
    return penalty


def _placed_components(ctx: PlacementContext, state: Placement) -> dict[str, Component]:
    placed = copy.deepcopy(ctx.design.board.components)
    result: dict[str, Component] = {}
    for comp in placed:
        x, y, rot = state.get(comp.ref, (comp.x, comp.y, comp.rotation))
        comp.place(x, y, rot)
        result[comp.ref] = comp
    return result


def _pins_by_net(
    ctx: PlacementContext, comps: dict[str, Component]
) -> dict[str, list[_Pin]]:
    by_net: dict[str, list[_Pin]] = {}
    for net in ctx.design.net_names():
        pins: list[_Pin] = []
        for original in ctx.design.pins_on_net(net):
            comp = comps.get(original.ref)
            if comp is None:
                continue
            pad = comp.pad(original.pin)
            if pad is None:
                continue
            pins.append(_Pin(original.ref, original.pin, original.pintype, net, pad.x, pad.y))
        by_net[net] = pins
    return by_net


def _hpwl(pins: list[_Pin]) -> float:
    if len(pins) < 2:
        return 0.0
    xs = [p.x for p in pins]
    ys = [p.y for p in pins]
    return (max(xs) - min(xs)) + (max(ys) - min(ys))


def _put_component(
    ctx: PlacementContext, state: Placement, comp: Component, x: float, y: float, rot: float = 0.0
) -> None:
    state[comp.ref] = (*_clamp_center(comp, x, y, rot, ctx.outline()), rot)


def _place_pad_near(
    ctx: PlacementContext,
    state: Placement,
    comp: Component,
    net: str,
    target_x: float,
    target_y: float,
    rot: float = 0.0,
) -> None:
    pad = next((p for p in comp.pads if p.net == net), None)
    if pad is None:
        _put_component(ctx, state, comp, target_x, target_y, rot)
        return
    dx, dy = _rotate(pad.dx, pad.dy, rot)
    _put_component(ctx, state, comp, target_x - dx, target_y - dy, rot)


def _clamp_center(
    comp: Component,
    x: float,
    y: float,
    rot: float,
    outline: tuple[float, float, float, float],
    margin: float = EDGE_CLEARANCE_MM,
) -> tuple[float, float]:
    minx, miny, maxx, maxy = outline
    local = [_rotate(px, py, rot) for px, py in comp.courtyard_local]
    if not local:
        return (
            min(max(x, minx + margin), maxx - margin),
            min(max(y, miny + margin), maxy - margin),
        )
    lx1, ly1, lx2, ly2 = geom.bbox(local)
    low_x = minx + margin - lx1
    high_x = maxx - margin - lx2
    low_y = miny + margin - ly1
    high_y = maxy - margin - ly2
    if low_x <= high_x:
        x = min(max(x, low_x), high_x)
    if low_y <= high_y:
        y = min(max(y, low_y), high_y)
    return x, y


def _placed_bbox(ctx: PlacementContext, state: Placement, ref: str):
    comp = ctx.design.component(ref)
    if comp is None:
        return None
    clone = copy.deepcopy(comp)
    x, y, rot = state.get(ref, (comp.x, comp.y, comp.rotation))
    clone.place(x, y, rot)
    return clone.courtyard


def _pin_at(ctx: PlacementContext, state: Placement, ref: str, pin_number: str) -> _Pin | None:
    comp = ctx.design.component(ref)
    if comp is None:
        return None
    pad = comp.pad(pin_number)
    if pad is None:
        return None
    x, y, rot = state.get(ref, (comp.x, comp.y, comp.rotation))
    dx, dy = _rotate(pad.dx, pad.dy, rot)
    original = next((p for p in ctx.design.pins_of(ref) if p.pin == pin_number), None)
    return _Pin(ref, pin_number, original.pintype if original else "", pad.net, x + dx, y + dy)


def _locked_pin_on_net(ctx: PlacementContext, net: str) -> _Pin | None:
    for pin in ctx.design.pins_on_net(net):
        if pin.ref not in ctx.locked or pin.x is None or pin.y is None:
            continue
        return _Pin(pin.ref, pin.pin, pin.pintype, net, pin.x, pin.y)
    pins = [p for p in ctx.design.pins_on_net(net) if p.x is not None and p.y is not None]
    if not pins:
        return None
    pin = pins[0]
    return _Pin(pin.ref, pin.pin, pin.pintype, net, pin.x, pin.y)


def _first_cap_on_net(
    ctx: PlacementContext, caps: list[Component], net: str, used: set[str]
) -> Component | None:
    for cap in caps:
        if cap.ref not in used and net in _nets_of(ctx, cap.ref):
            return cap
    return None


def _nets_of(ctx: PlacementContext, ref: str) -> set[str]:
    return {p.net for p in ctx.design.pins_of(ref)}


def _snap_rotation(rot: float) -> float:
    options = (0.0, 90.0, 180.0, 270.0)
    return min(options, key=lambda candidate: abs(((rot - candidate + 180.0) % 360.0) - 180.0))


def _pin_number(raw: str) -> int:
    try:
        return int(raw)
    except ValueError:
        return 10_000


def _rotate(dx: float, dy: float, degrees: float) -> tuple[float, float]:
    if not degrees:
        return dx, dy
    th = math.radians(degrees)
    cos, sin = math.cos(th), math.sin(th)
    return dx * cos + dy * sin, dy * cos - dx * sin
