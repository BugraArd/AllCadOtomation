"""Kumeleme tabanli hiyerarsik yerlestirme.

Fikir: bir kartin gercek yapisi netlist grafiginde saklidir. Bir IC, kendi
decoupling kondansatorleri, kristali ve kristalin yuk kondansatorleri
elektriksel olarak tek bir "blok"tur; bu bilesenler arasindaki mesafe
kisitlari (decoupling <= 6 mm, kristal izi <= 12 mm) yerel kisitlardir.
Onlari once blogun ICINDE cozersek, sonra bloklari kart uzerinde birbirine
gore konumlandirdigimizda bu kisitlar TASARIM GEREGI saglanmis olur - global
bir optimize edicinin sansina kalmaz.

Dort asama (klasik EDA sirasi):

  1. KUMELEME       netlist grafiginden mantiksal bloklar cikarilir.
                    Her 2-pinli pasif, "hangi pine ait?" sorusuyla bir IC/
                    kristal pinine ozel olarak eslenir (aciozlu, tekil eslesme
                    - kural motorunun `exclusive` semantigiyle ayni).
  2. IC-ICI DUZEN   her kume bir agac olarak ozyinelemeli dizilir: cocuk,
                    ait oldugu pinin bulundugu KENARA, o pinin tam karsisina,
                    baglantili pad'i ebeveyne bakacak sekilde dondurulerek
                    konur. Ayni kenardaki cocuklar 1-B legalizasyonla ayrilir.
  3. KUME YERLESIMI bloklar kart uzerinde katı cisim gibi tasinir/dondurulur;
                    aralarinda cok baglanti olanlar birbirine yaklasir.
  4. DETAY          bilesen bazinda tavlama + acgozlu inis; courtyard, kart
                    kenari ve diferansiyel cift simetrisi burada rotusiyor.

Deterministiktir: tum rastgelelik ctx.seed'den turer, yineleme sayilari
sabittir (sure butcesi yalnizca guvenlik freni olarak kullanilir).
"""

from __future__ import annotations

import math
import random
import re
import time
from dataclasses import dataclass, field

from .base import Placement, PlacementContext

ROTS = (0.0, 90.0, 180.0, 270.0)
_RIDX = {r: i for i, r in enumerate(ROTS)}

# --- hedefler (kural esiklerinden daha sikı tutulur ki guvenlik payi kalsin) --
CLEARANCE = 0.55  # courtyard'lar arasi hedef bosluk (kural: 0.2)
EDGE = 2.6  # kart kenarina hedef mesafe (kural: 2.0)
PAIR_TARGET = 4.0  # decoupling kondansatoru - guc pini hedefi (kural: 6.0)
PAIR_LIMIT = 6.0
SRC_TARGET = 4.5  # yigin kondansatoru - kaynak (regulator) pini hedefi
SRC_LIMIT = 8.0
DIFF_TOL = 0.8  # diferansiyel cift uzunluk farki hedefi (kural: 3.0)
DIFF_LIMIT = 3.0
GAP = 0.45  # kume ici komsuluk boslugu

# Net sinifina gore uzunluk butcesi: (hedef, sert sinir) mm.
# Saat netleri kisa olmak zorundadir (kararli osilasyon), guc raylari dusuk
# empedans icin toplu durmali, sinyaller makul kalmali.
BUD_CLOCK = (9.0, 12.0)
BUD_POWER = (50.0, 60.0)
BUD_SIGNAL = (36.0, 45.0)

# --- maliyet agirliklari ------------------------------------------------------
W_OVERLAP = 900.0
W_EDGE = 900.0
W_PAIR = 60.0
W_SRC = 40.0
W_BUDGET = 8.0
W_DIFF = 120.0
W_GROUND = 0.45
W_POWER = 2.6
W_CLOCK = 9.0
W_DIFFNET = 2.2
W_SIGNAL = 1.0

_GROUND_RX = re.compile(r"^(?:[AD]?GND\w*|VSS\w*|EARTH)$", re.I)
_DEAD_RX = re.compile(r"^(?:NC|DNC|NO?_?CONNECT)\d*$", re.I)


def _rotate(dx: float, dy: float, deg: float) -> tuple[float, float]:
    """KiCad donme konvansiyonu (Y ekseni asagi)."""
    if deg == 0.0:
        return dx, dy
    if deg == 90.0:
        return dy, -dx
    if deg == 180.0:
        return -dx, -dy
    if deg == 270.0:
        return -dy, dx
    th = math.radians(deg)
    c, s = math.cos(th), math.sin(th)
    return dx * c + dy * s, dy * c - dx * s


def _cap_value(text: str) -> float:
    """'100nF' -> 1e-7. Kondansator buyuklugu, hangi pine ait oldugunu ayirmaya
    yarar: pF sinifi kristal yuku, nF sinifi decoupling, uF sinifi yigin/regulator."""
    m = re.search(r"([\d.]+)\s*([pnumµ]?)F?", text or "", re.I)
    if not m:
        return math.inf
    try:
        base = float(m.group(1))
    except ValueError:
        return math.inf
    return base * {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "": 1.0}[
        m.group(2).lower()
    ]


@dataclass
class _Part:
    idx: int
    ref: str
    kind: str
    value: str
    locked: bool
    x: float
    y: float
    rot: float
    # rotasyon indeksine gore: [(net_id, dx, dy), ...]
    pads: list[list[tuple[int, float, float]]] = field(default_factory=list)
    # rotasyon indeksine gore courtyard sinir kutusu (x0, y0, x1, y1)
    cyd: list[tuple[float, float, float, float]] = field(default_factory=list)
    # pad numarasi -> (net_id, dx0, dy0, pintype)   (dondurulmemis)
    padinfo: list[tuple[str, int, float, float, str]] = field(default_factory=list)


@dataclass
class _Node:
    """Kume agacinin bir dugumu."""

    part: _Part
    children: list["_Node"] = field(default_factory=list)
    # ebeveyn uzerinde bagli oldugu pad indeksleri (hedef pinler)
    anchor_pads: list[int] = field(default_factory=list)


class ClusterPlacer:
    """Kumeleme tabanli hiyerarsik yerlestirici."""

    name = "cluster"

    def run(self, ctx: PlacementContext) -> Placement:
        return _Engine(ctx).solve()


# =============================================================================
#  Motor
# =============================================================================


class _Engine:
    def __init__(self, ctx: PlacementContext) -> None:
        self.ctx = ctx
        self.design = ctx.design
        self.deadline = time.perf_counter() + max(2.0, ctx.time_budget_s * 0.88)
        self.outline = ctx.outline()

        self._build_parts()
        self._classify_nets()
        self._build_clusters()

    # ------------------------------------------------------------ 0. veri modeli

    def _build_parts(self) -> None:
        design = self.design
        comps = sorted(design.board.components, key=lambda c: c.ref)

        self.net_id: dict[str, int] = {}
        self.net_name: list[str] = []

        def nid(name: str) -> int:
            if name not in self.net_id:
                self.net_id[name] = len(self.net_name)
                self.net_name.append(name)
            return self.net_id[name]

        self.parts: list[_Part] = []

        for i, c in enumerate(comps):
            p = _Part(
                idx=i,
                ref=c.ref,
                kind=design.kind_of(c.ref),
                value=design.value_of(c.ref) or c.value,
                locked=c.ref in self.ctx.locked,
                x=c.x,
                y=c.y,
                rot=c.rotation,
            )
            for pad in c.pads:
                if not pad.net or _DEAD_RX.match(pad.net):
                    continue
                p.padinfo.append((pad.number, nid(pad.net), pad.dx, pad.dy, pad.pintype))

            local = c.courtyard_local
            if len(local) < 3:
                pts = [(pd.dx, pd.dy) for pd in c.pads] or [(0.0, 0.0)]
                mx = max(abs(v) for v, _ in pts) + 0.5
                my = max(abs(v) for _, v in pts) + 0.5
                local = [(-mx, -my), (mx, -my), (mx, my), (-mx, my)]

            for r in ROTS:
                p.pads.append([(n, *_rotate(dx, dy, r)) for _, n, dx, dy, _ in p.padinfo])
                rp = [_rotate(lx, ly, r) for lx, ly in local]
                xs = [v for v, _ in rp]
                ys = [v for _, v in rp]
                p.cyd.append((min(xs), min(ys), max(xs), max(ys)))

            self.parts.append(p)

        self.n = len(self.parts)
        self.nn = len(self.net_name)

        # net -> [(part_idx, pad_slot)]
        self.net_pins: list[list[tuple[int, int]]] = [[] for _ in range(self.nn)]
        for p in self.parts:
            for slot, (_num, n, _dx, _dy, _pt) in enumerate(p.padinfo):
                self.net_pins[n].append((p.idx, slot))

    def _classify_nets(self) -> None:
        """Netleri turlerine ayirir: toprak / guc / saat / diferansiyel / sinyal."""
        self.is_ground = [bool(_GROUND_RX.match(nm)) for nm in self.net_name]
        self.is_power = [False] * self.nn
        self.is_clock = [False] * self.nn

        for n in range(self.nn):
            if self.is_ground[n]:
                continue
            for pi, slot in self.net_pins[n]:
                p = self.parts[pi]
                pt = p.padinfo[slot][4]
                if pt in ("power_in", "power_out"):
                    self.is_power[n] = True
                if p.kind == "crystal":
                    self.is_clock[n] = True

        # --- diferansiyel cift tespiti (isim tabanli: ..P / ..M, ..N) ---------
        keys: dict[str, dict[str, list[int]]] = {}
        for n, nm in enumerate(self.net_name):
            if self.is_ground[n]:
                continue
            toks = re.split(r"([_\-])", nm)
            for t, tok in enumerate(toks):
                if len(tok) < 2 or tok[-1].upper() not in "PMN":
                    continue
                pol = "P" if tok[-1].upper() == "P" else "N"
                key = "".join(toks[:t]) + tok[:-1] + "#" + "".join(toks[t + 1 :])
                keys.setdefault(key.upper(), {}).setdefault(pol, []).append(n)

        self.diff_pairs: list[tuple[int, int]] = []
        for key in sorted(keys):
            pols = keys[key]
            if len(pols.get("P", [])) == 1 and len(pols.get("N", [])) == 1:
                self.diff_pairs.append((pols["P"][0], pols["N"][0]))

        self.is_diff = [False] * self.nn
        for a, b in self.diff_pairs:
            self.is_diff[a] = self.is_diff[b] = True

        self.net_w: list[float] = []
        self.net_bud: list[tuple[float, float] | None] = []
        for n in range(self.nn):
            bud: tuple[float, float] | None
            if self.is_ground[n]:
                w, bud = W_GROUND, None
            elif self.is_clock[n]:
                w, bud = W_CLOCK, BUD_CLOCK
            elif self.is_power[n]:
                w, bud = W_POWER, BUD_POWER
            elif self.is_diff[n]:
                w, bud = W_DIFFNET, BUD_SIGNAL
            else:
                w, bud = W_SIGNAL, BUD_SIGNAL
            # tek pinli netlerin HPWL'i her zaman 0; hesaptan cikar
            if len(self.net_pins[n]) < 2:
                w, bud = 0.0, None
            self.net_w.append(w)
            self.net_bud.append(bud)

    # ------------------------------------------------------- 1. KUMELEME

    def _build_clusters(self) -> None:
        """Netlist grafigini mantiksal bloklara ayirir.

        Once "hangi kondansator hangi pine ait?" sorusu cozulur: her IC guc
        pini ve her kristal pini bir hedeftir, ayni nette olup diger ucu
        toprakta olan kondansatorler adaydir. Eslesme TEKILDIR - kural
        motorunun exclusive semantigi de boyle calisir, yani burada dogru
        cozersek kural da gecer.
        """
        parts = self.parts

        def two_pin_shunt(p: _Part) -> tuple[int, int] | None:
            """(sinyal_net, pad_slot) - iki uclu, bir ucu toprakta olan pasif."""
            if len(p.padinfo) != 2:
                return None
            a, b = p.padinfo
            if self.is_ground[a[1]] and not self.is_ground[b[1]]:
                return b[1], 1
            if self.is_ground[b[1]] and not self.is_ground[a[1]]:
                return a[1], 0
            return None

        # --- hedef pinler ----------------------------------------------------
        targets: list[tuple[int, int, int, int]] = []  # (oncelik, part_idx, slot, net)
        for p in parts:
            for slot, (_num, n, _dx, _dy, pt) in enumerate(p.padinfo):
                if self.is_ground[n]:
                    continue
                if p.kind == "crystal":
                    targets.append((0, p.idx, slot, n))
                elif p.kind == "ic" and pt == "power_in":
                    targets.append((1, p.idx, slot, n))

        # --- adaylar ---------------------------------------------------------
        shunts: dict[int, tuple[int, int]] = {}  # part_idx -> (net, slot)
        for p in parts:
            if p.locked or p.kind != "capacitor":
                continue
            sh = two_pin_shunt(p)
            if sh:
                shunts[p.idx] = sh

        cand: dict[int, list[int]] = {}  # target index -> aday part idx listesi
        for ti, (_pri, pi, _slot, net) in enumerate(targets):
            cand[ti] = sorted(
                (ci for ci, (cnet, _cs) in shunts.items() if cnet == net and ci != pi),
                key=lambda ci: (_cap_value(parts[ci].value), parts[ci].ref),
            )

        # Az secenegi olan hedef once secsin (kisitli hedefler ac kalmasin).
        order = sorted(range(len(targets)), key=lambda ti: (targets[ti][0], len(cand[ti]), ti))
        used: set[int] = set()
        # cap part_idx -> (parent part_idx, parent pad slot)
        self.owner: dict[int, tuple[int, int]] = {}
        for ti in order:
            for ci in cand[ti]:
                if ci in used:
                    continue
                used.add(ci)
                self.owner[ci] = (targets[ti][1], targets[ti][2])
                break

        # Artan kondansatorler (yigin/regulator kapasitesi): guc KAYNAGI pinine
        # (power_out) yapissin; yoksa ayni netteki herhangi bir IC pinine.
        for ci, (net, _slot) in sorted(shunts.items()):
            if ci in self.owner:
                continue
            best = None
            for pi, slot in self.net_pins[net]:
                p = parts[pi]
                if pi == ci or p.kind not in ("ic", "crystal"):
                    continue
                pt = p.padinfo[slot][4]
                rank = 0 if pt == "power_out" else (1 if pt == "power_in" else 2)
                key = (rank, p.ref, slot)
                if best is None or key < best[0]:
                    best = (key, pi, slot)
            if best:
                self.owner[ci] = (best[1], best[2])

        # --- kume agaclari ---------------------------------------------------
        anchors = [p for p in parts if p.kind in ("ic", "crystal") and not p.locked]
        nodes: dict[int, _Node] = {p.idx: _Node(part=p) for p in anchors}
        for ci, (pi, slot) in sorted(self.owner.items()):
            nodes.setdefault(ci, _Node(part=parts[ci]))
            nodes.setdefault(pi, _Node(part=parts[pi]))

        parent_of: dict[int, int] = {}
        for ci, (pi, slot) in sorted(self.owner.items()):
            if pi == ci:
                continue
            parent_of[ci] = pi
            nodes[pi].children.append(nodes[ci])
            nodes[ci].anchor_pads = [slot]

        # Kristal, bagli oldugu IC'nin alt blogudur: XIN/XOUT netlerini
        # paylastigi IC'ye tutturulur.
        for p in parts:
            if p.kind != "crystal" or p.locked or p.idx in parent_of:
                continue
            counts: dict[int, list[int]] = {}
            for _num, n, _dx, _dy, _pt in p.padinfo:
                if self.is_ground[n]:
                    continue
                for pi, slot in self.net_pins[n]:
                    if pi != p.idx and parts[pi].kind == "ic" and not parts[pi].locked:
                        counts.setdefault(pi, []).append(slot)
            if not counts:
                continue
            pi = max(sorted(counts), key=lambda k: len(counts[k]))
            parent_of[p.idx] = pi
            nodes.setdefault(pi, _Node(part=parts[pi]))
            nodes[pi].children.append(nodes[p.idx])
            nodes[p.idx].anchor_pads = sorted(set(counts[pi]))

        for nd in nodes.values():
            nd.children.sort(key=lambda c: c.part.ref)

        # Kok dugumler = kumeler. Gerisi (pull-up'lar, seri direncler...) tek
        # basina birer "serbest" kume olur; iki farkli bloga esit baglilar,
        # bir blogun icine hapsedilmeleri dogru olmaz.
        self.roots: list[_Node] = []
        claimed = set(parent_of)
        for p in parts:
            if p.locked or p.idx in claimed:
                continue
            self.roots.append(nodes.get(p.idx) or _Node(part=p))
        self.roots.sort(key=lambda nd: (-_subtree_size(nd), nd.part.ref))

        self.cluster_of = [-1] * self.n
        self.members: list[list[int]] = []
        for ci, root in enumerate(self.roots):
            mem = sorted(_subtree_refs(root))
            self.members.append(mem)
            for i in mem:
                self.cluster_of[i] = ci

        # --- yakinlik olcumu ------------------------------------------------
        # Bir kondansatorun "hangi pine ait oldugu" kume kurarken bizim
        # kararimizdi; ama kalite olcumu TEKIL EN-YAKIN eslemeyle yapilir
        # (bir kondansator tek bir pine sayilir). Maliyet fonksiyonu bu yuzden
        # kendi atamamizi degil, gercek tekil eslemeyi puanlar - yoksa
        # optimize edici "benim atamama gore iyi ama esleme baska turlu
        # cikiyor" tuzagina duser.
        def slot_on(part_idx: int, net: int) -> int | None:
            return next(
                (s for s, info in enumerate(parts[part_idx].padinfo) if info[1] == net), None
            )

        # her biri bagimsiz bir tekil-esleme problemi (IC guc pinleri / kristal)
        self.prox_sets: list[list[tuple[list, list]]] = []
        for pri in (0, 1):
            groups: dict[int, tuple[list, list]] = {}
            for _p, pi, slot, net in targets:
                if _p != pri:
                    continue
                g = groups.setdefault(net, ([], []))
                g[0].append((pi, slot))
            for net, g in groups.items():
                for ci, (cnet, _cs) in sorted(shunts.items()):
                    if cnet != net:
                        continue
                    cs = slot_on(ci, net)
                    if cs is not None and not any(ci == t[0] for t in g[0]):
                        g[1].append((ci, cs))
            sel = [groups[net] for net in sorted(groups) if groups[net][1]]
            if sel:
                self.prox_sets.append(sel)

        # Kume atamasinin kendisi de bir kisittir: her kondansator, kume
        # kurarken sahiplendigi pinin dibinde durmali. Tekil esleme terimi
        # "her guc pininin BIR kondansatoru olsun" der; bu terim ise "hangi
        # kondansator" sorusunu sabitler. Regulator yigin kondansatorleri
        # (tekil eslemeye hic girmeyen artiklar) yalnizca buradan tutulur -
        # yoksa optimize edici onlari kartin obur ucuna savurur.
        self.src_pairs: list[tuple[int, int, int, int]] = []
        for ci, (pi, slot) in sorted(self.owner.items()):
            net = parts[pi].padinfo[slot][1]
            cs = slot_on(ci, net)
            if cs is not None:
                self.src_pairs.append((pi, slot, ci, cs))

    # --------------------------------------------- 2. KUME ICI HIYERARSIK DUZEN

    def _layout(self, node: _Node, rot: float) -> tuple[dict[int, tuple[float, float, float]],
                                                        tuple[float, float, float, float]]:
        """Bir alt agaci, kokunu (0,0)/rot'a koyarak dizer.

        Doner: {part_idx: (dx, dy, rot)} ve alt agacin sinir kutusu.
        """
        key = (node.part.idx, rot)
        hit = self._layout_cache.get(key)
        if hit is not None:
            return hit

        p = node.part
        ri = _RIDX[rot]
        own = p.cyd[ri]
        placed: dict[int, tuple[float, float, float]] = {p.idx: (0.0, 0.0, rot)}
        box = list(own)

        # cocuklari, bagli olduklari pinin bulundugu KENARA gore grupla
        sides: dict[str, list[tuple[float, _Node, tuple[float, float]]]] = {}
        hx = max(abs(own[0]), abs(own[2])) or 1.0
        hy = max(abs(own[1]), abs(own[3])) or 1.0
        for child in node.children:
            slots = child.anchor_pads or [0]
            pts = [_rotate(p.padinfo[s][2], p.padinfo[s][3], rot) for s in slots]
            px = sum(v for v, _ in pts) / len(pts)
            py = sum(v for _, v in pts) / len(pts)
            side = ("R" if px > 0 else "L") if abs(px) / hx >= abs(py) / hy else (
                "B" if py > 0 else "T"
            )
            sides.setdefault(side, []).append((0.0, child, (px, py)))

        for side in sorted(sides):
            items = sides[side]
            horiz = side in ("L", "R")
            entries = []
            for _, child, (px, py) in items:
                best = None
                for crot in ROTS:
                    sub, sbox = self._layout(child, crot)
                    cp = self._link_pad(child, node, crot, sub)
                    if side == "L":
                        ox = own[0] - GAP - sbox[2]
                        oy = py - cp[1]
                    elif side == "R":
                        ox = own[2] + GAP - sbox[0]
                        oy = py - cp[1]
                    elif side == "T":
                        oy = own[1] - GAP - sbox[3]
                        ox = px - cp[0]
                    else:
                        oy = own[3] + GAP - sbox[1]
                        ox = px - cp[0]
                    dist = math.hypot(ox + cp[0] - px, oy + cp[1] - py)
                    span = (sbox[3] - sbox[1]) if horiz else (sbox[2] - sbox[0])
                    score = (round(dist + 0.25 * span, 4), _RIDX[crot])
                    if best is None or score < best[0]:
                        best = (score, crot, ox, oy, sub, sbox)
                entries.append((best[3] if horiz else best[2], child, best))
            entries.sort(key=lambda e: (e[0], e[1].part.ref))

            # ayni kenardaki cocuklar icin 1-B legalizasyon
            cursor = -math.inf
            for _, child, best in entries:
                _score, crot, ox, oy, sub, sbox = best
                lo = (oy + sbox[1]) if horiz else (ox + sbox[0])
                hi = (oy + sbox[3]) if horiz else (ox + sbox[2])
                if lo < cursor + GAP:
                    shift = cursor + GAP - lo
                    if horiz:
                        oy += shift
                    else:
                        ox += shift
                    hi += shift
                cursor = hi
                for idx, (sx, sy, sr) in sub.items():
                    placed[idx] = (ox + sx, oy + sy, sr)
                box[0] = min(box[0], ox + sbox[0])
                box[1] = min(box[1], oy + sbox[1])
                box[2] = max(box[2], ox + sbox[2])
                box[3] = max(box[3], oy + sbox[3])

        out = (placed, (box[0], box[1], box[2], box[3]))
        self._layout_cache[key] = out
        return out

    def _link_pad(self, child: _Node, parent: _Node, crot: float,
                  sub: dict[int, tuple[float, float, float]]) -> tuple[float, float]:
        """Cocugun ebeveyne baglandigi pad'in, alt agac kokunune gore ofseti."""
        nets = {parent.part.padinfo[s][1] for s in (child.anchor_pads or [])}
        cp = child.part
        hits = [
            _rotate(dx, dy, crot)
            for _num, n, dx, dy, _pt in cp.padinfo
            if n in nets
        ]
        if not hits:
            hits = [_rotate(dx, dy, crot) for _num, _n, dx, dy, _pt in cp.padinfo]
        if not hits:
            return (0.0, 0.0)
        return (sum(v for v, _ in hits) / len(hits), sum(v for _, v in hits) / len(hits))

    # ------------------------------------------------------------ maliyet

    def _cost(self, xs, ys, ris, detail: bool = False):
        parts = self.parts
        nn = self.nn
        INF = math.inf
        nviol = 0
        nx0 = [INF] * nn
        ny0 = [INF] * nn
        nx1 = [-INF] * nn
        ny1 = [-INF] * nn

        for i in range(self.n):
            x = xs[i]
            y = ys[i]
            for n, dx, dy in parts[i].pads[ris[i]]:
                px = x + dx
                py = y + dy
                if px < nx0[n]:
                    nx0[n] = px
                if px > nx1[n]:
                    nx1[n] = px
                if py < ny0[n]:
                    ny0[n] = py
                if py > ny1[n]:
                    ny1[n] = py

        wire = 0.0
        raw = 0.0
        over = 0.0
        w = self.net_w
        bud = self.net_bud
        for n in range(nn):
            if w[n] <= 0.0:
                continue
            h = (nx1[n] - nx0[n]) + (ny1[n] - ny0[n])
            wire += w[n] * h
            raw += h
            b = bud[n]
            if b is not None and h > b[0]:
                v = h - b[0]
                over += v * v
                if h > b[1]:
                    nviol += 1

        # diferansiyel cift simetrisi
        diff = 0.0
        for a, b in self.diff_pairs:
            ha = (nx1[a] - nx0[a]) + (ny1[a] - ny0[a])
            hb = (nx1[b] - nx0[b]) + (ny1[b] - ny0[b])
            gap = abs(ha - hb)
            v = gap - DIFF_TOL
            if v > 0:
                diff += v * v
                if gap > DIFF_LIMIT:
                    nviol += 1

        # courtyard bosluklari
        ovl = 0.0
        boxes = []
        for i in range(self.n):
            c = parts[i].cyd[ris[i]]
            boxes.append((xs[i] + c[0], ys[i] + c[1], xs[i] + c[2], ys[i] + c[3]))
        for i, j in self.pair_list:
            a = boxes[i]
            b = boxes[j]
            dx = b[0] - a[2] if b[0] > a[2] else (a[0] - b[2] if a[0] > b[2] else
                                                  max(b[0] - a[2], a[0] - b[2]))
            dy = b[1] - a[3] if b[1] > a[3] else (a[1] - b[3] if a[1] > b[3] else
                                                  max(b[1] - a[3], a[1] - b[3]))
            if dx >= 0.0 or dy >= 0.0:
                sep = math.hypot(max(dx, 0.0), max(dy, 0.0))
            else:
                sep = max(dx, dy)  # ic ice: negatif = girme derinligi
            v = CLEARANCE - sep
            if v > 0:
                ovl += v * v
                if sep < 0.2:
                    nviol += 1

        # kart kenari
        bx0, by0, bx1, by1 = self.outline
        edge = 0.0
        for i in self.free_idx:
            b = boxes[i]
            m = min(b[0] - bx0, b[1] - by0, bx1 - b[2], by1 - b[3])
            v = EDGE - m
            if v > 0:
                edge += v * v
                if m < 2.0:
                    nviol += 1

        # kondansator <-> pin yakinligi (TEKIL en-yakin esleme ile)
        prox = 0.0

        def pad_xy(pi: int, slot: int) -> tuple[float, float]:
            d = parts[pi].pads[ris[pi]][slot]
            return xs[pi] + d[1], ys[pi] + d[2]

        for sel in self.prox_sets:
            claimed: set[int] = set()
            for tgts, cands in sel:
                cand_pts = []
                for ci, cs in cands:
                    cand_pts.append((ci, pad_xy(ci, cs)))
                trip = []
                for ti, (pi, ps) in enumerate(tgts):
                    tx, ty = pad_xy(pi, ps)
                    for cj, (ci, (cxp, cyp)) in enumerate(cand_pts):
                        trip.append((math.hypot(tx - cxp, ty - cyp), ti, cj))
                trip.sort()
                matched: dict[int, float] = {}
                used: set[int] = set()
                for d, ti, cj in trip:
                    if ti in matched:
                        continue
                    ci = cand_pts[cj][0]
                    if ci in claimed or cj in used:
                        continue
                    matched[ti] = d
                    used.add(cj)
                claimed |= {cand_pts[cj][0] for cj in used}
                # Eslesemeyen hedef: kondansator sayisi yetmiyor demektir
                # (devre kusuru, yerlesimle kapatilamaz). Yine de sabit bir
                # ceza vermek gradyansiz bir plato yaratir ve o pini kartin
                # obur ucuna savurur; bunun yerine EN YAKIN adaya olan
                # mesafesini cezalandirip pini havuza yakin tutariz.
                nearest = {}
                for d, ti, _cj in trip:
                    if ti not in nearest:
                        nearest[ti] = d
                for ti in range(len(tgts)):
                    d = matched.get(ti)
                    if d is None:
                        prox += 40.0 + max(0.0, nearest.get(ti, 0.0) - PAIR_TARGET) ** 2
                        nviol += 1
                        continue
                    v = d - PAIR_TARGET
                    if v > 0:
                        prox += v * v
                        if d > PAIR_LIMIT:
                            nviol += 1

        # Yigin/regulator kondansatoru kendi kaynak pininin dibinde durmali.
        src = 0.0
        for pi, ps, ci, cs in self.src_pairs:
            ax, ay = pad_xy(pi, ps)
            bx, by = pad_xy(ci, cs)
            d = math.hypot(ax - bx, ay - by)
            v = d - SRC_TARGET
            if v > 0:
                src += v * v
                if d > SRC_LIMIT:
                    nviol += 1

        total = (wire + W_OVERLAP * ovl + W_EDGE * edge + W_PAIR * prox
                 + W_SRC * src + W_BUDGET * over + W_DIFF * diff)
        if detail:
            return total, {"wire": wire, "raw": raw, "ovl": ovl, "edge": edge,
                           "prox": prox, "src": src, "over": over, "diff": diff,
                           "viol": nviol}
        return total

    # ------------------------------------------------------------ 3+4. arama

    RESTARTS = 5

    def solve(self) -> Placement:
        """Bagimsiz yeniden baslatmalar; en iyisi secilir.

        Secim olcutu once SERT ihlal sayisi (courtyard / kart kenari /
        decoupling mesafesi), sonra maliyet - kisa bir tel uzunlugu ugruna bir
        kural ihlalini kabul etmek istemiyoruz.
        """
        self._prepare()
        best = None
        for attempt in range(self.RESTARTS):
            rng = random.Random((self.ctx.seed * 1_000_003) ^ (attempt * 2_654_435_761))
            cand = self._attempt(rng, attempt)
            if best is None or (cand[0], cand[1]) < (best[0], best[1]):
                best = cand
            if time.perf_counter() > self.deadline:
                break

        _viol, _cost, cx, cy, cr = best
        return {
            self.parts[i].ref: (round(cx[i], 4), round(cy[i], 4), ROTS[cr[i]])
            for i in self.free_idx
        }

    def _prepare(self) -> None:
        self._layout_cache: dict[tuple[int, float], tuple] = {}

        self.free_idx = [p.idx for p in self.parts if not p.locked]
        self.pair_list = [
            (i, j)
            for i in range(self.n)
            for j in range(i + 1, self.n)
            if not (self.parts[i].locked and self.parts[j].locked)
        ]

        # --- kume gecici duzenleri (her rotasyon icin onbellek) --------------
        self.cl_layout: list[dict[float, dict[int, tuple[float, float, float]]]] = []
        for root in self.roots:
            per_rot = {}
            for r in ROTS:
                sub, _box = self._layout(root, r)
                per_rot[r] = sub
            self.cl_layout.append(per_rot)

    def _attempt(self, rng: random.Random, attempt: int):
        nc = len(self.roots)
        xs = [p.x for p in self.parts]
        ys = [p.y for p in self.parts]
        ris = [_RIDX.get(p.rot % 360.0, 0) for p in self.parts]

        # --- baslangic: kume cipalarini mevcut konumlarinda birak, ama
        #     serbest tek-parcalarini bagli pinlerinin agirlik merkezine tasi
        anchor = []
        for ci, root in enumerate(self.roots):
            anchor.append([root.part.x, root.part.y, 0.0])
        for ci, root in enumerate(self.roots):
            if len(self.members[ci]) == 1:
                p = root.part
                pts = []
                for _num, n, _dx, _dy, _pt in p.padinfo:
                    if self.is_ground[n]:
                        continue
                    for pi, slot in self.net_pins[n]:
                        if pi == p.idx:
                            continue
                        q = self.parts[pi]
                        d = _rotate(q.padinfo[slot][2], q.padinfo[slot][3], q.rot)
                        pts.append((q.x + d[0], q.y + d[1]))
                if pts:
                    anchor[ci][0] = sum(v for v, _ in pts) / len(pts)
                    anchor[ci][1] = sum(v for _, v in pts) / len(pts)

        bx0, by0, bx1, by1 = self.outline
        if attempt:
            # Ilk deneme mevcut yerlesimi sicak baslangic olarak kullanir;
            # digerleri kumeleri kartin uzerine yeniden dagitir.
            for ci in range(nc):
                anchor[ci][0] = rng.uniform(bx0 + 6, bx1 - 6)
                anchor[ci][1] = rng.uniform(by0 + 6, by1 - 6)
                anchor[ci][2] = rng.choice(ROTS)

        self._apply(anchor, xs, ys, ris)
        best = (self._cost(xs, ys, ris), [a[:] for a in anchor])

        # ------------------------------------------------ 3. KUME YERLESIMI
        cur = [a[:] for a in anchor]
        cur_c = best[0]
        t0, t1 = 14.0, 0.05
        iters = 6000 if nc > 1 else 0
        for it in range(iters):
            if (it & 255) == 0 and time.perf_counter() > self.deadline:
                break
            T = t0 * (t1 / t0) ** (it / iters)
            ci = rng.randrange(nc)
            old = cur[ci][:]
            m = rng.random()
            if m < 0.72:
                s = 12.0 * T / t0 + 0.5
                cur[ci][0] += rng.uniform(-s, s)
                cur[ci][1] += rng.uniform(-s, s)
            elif m < 0.85:
                cur[ci][0] = rng.uniform(bx0 + 4, bx1 - 4)
                cur[ci][1] = rng.uniform(by0 + 4, by1 - 4)
            else:
                cur[ci][2] = rng.choice(ROTS)
            self._apply(cur, xs, ys, ris)
            c = self._cost(xs, ys, ris)
            if c <= cur_c or rng.random() < math.exp((cur_c - c) / max(T, 1e-6)):
                cur_c = c
                if c < best[0]:
                    best = (c, [a[:] for a in cur])
            else:
                cur[ci] = old

        self._apply(best[1], xs, ys, ris)

        # ------------------------------------------------ 4. DETAY IYILESTIRME
        cx = xs[:]
        cy = ys[:]
        cr = ris[:]
        cur_c = self._cost(cx, cy, cr)
        bxs, bys, brs, bc = cx[:], cy[:], cr[:], cur_c
        free = self.free_idx
        t0, t1 = 6.0, 0.02
        iters = 18000
        for it in range(iters):
            if (it & 255) == 0 and time.perf_counter() > self.deadline:
                break
            T = t0 * (t1 / t0) ** (it / iters)
            m = rng.random()
            undo = None
            if m < 0.16 and nc > 1:  # katı kume otelemesi
                ci = rng.randrange(nc)
                mem = self.members[ci]
                s = 4.0 * T / t0 + 0.3
                dx = rng.uniform(-s, s)
                dy = rng.uniform(-s, s)
                undo = ("cluster", mem, dx, dy)
                for i in mem:
                    cx[i] += dx
                    cy[i] += dy
            elif m < 0.86:  # tek bilesen otelemesi
                i = free[rng.randrange(len(free))]
                s = 5.0 * T / t0 + 0.15
                undo = ("one", i, cx[i], cy[i], cr[i])
                cx[i] += rng.uniform(-s, s)
                cy[i] += rng.uniform(-s, s)
            elif m < 0.95:  # dondurme
                i = free[rng.randrange(len(free))]
                undo = ("one", i, cx[i], cy[i], cr[i])
                cr[i] = rng.randrange(4)
            else:  # takas
                i = free[rng.randrange(len(free))]
                j = free[rng.randrange(len(free))]
                if i == j:
                    continue
                undo = ("swap", i, j, cx[i], cy[i], cr[i], cx[j], cy[j], cr[j])
                cx[i], cx[j] = cx[j], cx[i]
                cy[i], cy[j] = cy[j], cy[i]
                cr[i], cr[j] = cr[j], cr[i]

            c = self._cost(cx, cy, cr)
            if c <= cur_c or rng.random() < math.exp((cur_c - c) / max(T, 1e-6)):
                cur_c = c
                if c < bc:
                    bc = c
                    bxs, bys, brs = cx[:], cy[:], cr[:]
            else:
                self._undo(undo, cx, cy, cr)

        cx, cy, cr = bxs[:], bys[:], brs[:]
        cur_c = bc

        # ------------------------------------------------ acgozlu inis (rotus)
        for step in (1.6, 0.8, 0.4, 0.2, 0.1, 0.05):
            improved = True
            while improved:
                improved = False
                if time.perf_counter() > self.deadline:
                    break
                for i in free:
                    for dx, dy in ((step, 0), (-step, 0), (0, step), (0, -step),
                                   (step, step), (-step, -step), (step, -step), (-step, step)):
                        ox, oy = cx[i], cy[i]
                        cx[i] = ox + dx
                        cy[i] = oy + dy
                        c = self._cost(cx, cy, cr)
                        if c < cur_c - 1e-9:
                            cur_c = c
                            improved = True
                        else:
                            cx[i], cy[i] = ox, oy
                    for r in range(4):
                        if r == cr[i]:
                            continue
                        orr = cr[i]
                        cr[i] = r
                        c = self._cost(cx, cy, cr)
                        if c < cur_c - 1e-9:
                            cur_c = c
                            improved = True
                        else:
                            cr[i] = orr

        total, info = self._cost(cx, cy, cr, detail=True)
        return (info["viol"], total, cx, cy, cr)

    # ------------------------------------------------------------ yardimcilar

    def _apply(self, anchor, xs, ys, ris) -> None:
        for ci, root in enumerate(self.roots):
            ax, ay, ar = anchor[ci]
            for idx, (dx, dy, rr) in self.cl_layout[ci][ar].items():
                xs[idx] = ax + dx
                ys[idx] = ay + dy
                ris[idx] = _RIDX[rr]

    @staticmethod
    def _undo(undo, cx, cy, cr) -> None:
        if undo is None:
            return
        if undo[0] == "cluster":
            _, mem, dx, dy = undo
            for i in mem:
                cx[i] -= dx
                cy[i] -= dy
        elif undo[0] == "one":
            _, i, x, y, r = undo
            cx[i], cy[i], cr[i] = x, y, r
        else:
            _, i, j, xi, yi, ri, xj, yj, rj = undo
            cx[i], cy[i], cr[i] = xi, yi, ri
            cx[j], cy[j], cr[j] = xj, yj, rj


def _subtree_refs(node: _Node) -> list[int]:
    out = [node.part.idx]
    for c in node.children:
        out.extend(_subtree_refs(c))
    return out


def _subtree_size(node: _Node) -> int:
    return 1 + sum(_subtree_size(c) for c in node.children)
