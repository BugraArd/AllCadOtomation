"""CILA - hakemin gercek puanini dogrudan optimize eden yerel arama.

Asama 3'te ogrenilen sey: yerlestiriciler vekil bir maliyet (HPWL + genel
cezalar) optimize ediyordu, hakem ise YAML kurallarina bakiyordu. Sentetik
tezgahta ikisi ortusuyor, gercek kartta ortusmuyor - bu yuzden dort
yerlestiricinin ucu `pic_programmer`i BOZUYORDU.

Buradaki cila katmani araya girer: bir baslangic yerlesimi alir, hakemin
kendi olcutuyle (`ctx.evaluate`) kucuk yerel hamleler dener ve YALNIZCA
olcumu iyilestiren hamleyi kabul eder. Iki sonucu var:

  1. Cikti hicbir zaman baslangictan kotu olamaz (monoton garanti).
  2. Kural sinirlarina "kil payi" takilan hatalar kapanir - hamleler
     bulgulardan uretildigi icin dogrudan hataya nisan alir.

Ana giris: `polish(start, ctx, budget_s)`.
"""

from __future__ import annotations

import math
import random
import time
from typing import Any, Iterable

from .base import Evaluation, Placement, PlacementContext

# Bulgu kaynakli hamlelerde denenen yaricap kesirleri (limitin katlari)
_RADIUS_FRACTIONS = (0.35, 0.55, 0.75)
# Bir hedefin cevresinde denenen aci sayisi
_ANGLE_STEPS = 8
# Ince ayar hamlelerinde denenen kaydirmalar (mm)
_NUDGES = (0.5, 1.0, 2.0, 4.0)


def _refs_of(finding: Any) -> list[str]:
    return list(getattr(finding, "refs", None) or [])


def _limit_of(finding: Any, fallback: float) -> float:
    limit = getattr(finding, "limit", None)
    return float(limit) if isinstance(limit, (int, float)) and limit > 0 else fallback


def _inside(outline: tuple[float, float, float, float], x: float, y: float) -> bool:
    minx, miny, maxx, maxy = outline
    return minx <= x <= maxx and miny <= y <= maxy


def _with(placement: Placement, ref: str, xyr: tuple[float, float, float]) -> Placement:
    """Tek bileseni degistirilmis YENI bir yerlestirme sozlugu."""
    out = dict(placement)
    out[ref] = xyr
    return out


def _ring(cx: float, cy: float, radius: float) -> Iterable[tuple[float, float]]:
    for i in range(_ANGLE_STEPS):
        a = 2.0 * math.pi * i / _ANGLE_STEPS
        yield cx + radius * math.cos(a), cy + radius * math.sin(a)


def _extent_of(ref: str, ctx: PlacementContext) -> float:
    """Bilesenin kaba yaricapi (courtyard kutusunun yarisi)."""
    comp = ctx.design.component(ref)
    poly = getattr(comp, "courtyard_local", None) if comp else None
    if not poly:
        return 1.0
    xs = [px for px, _ in poly]
    ys = [py for _, py in poly]
    return max(max(xs) - min(xs), max(ys) - min(ys)) / 2.0 or 1.0


def _centroid(refs: list[str], placement: Placement) -> tuple[float, float] | None:
    pts = [placement[r][:2] for r in refs if r in placement]
    if not pts:
        return None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def _finding_moves(
    finding: Any,
    placement: Placement,
    ctx: PlacementContext,
) -> list[tuple[str, tuple[float, float, float]]]:
    """Bir bulgudan somut hamleler uretir.

    Kural iki yonde de ihlal edilebilir, hamle yonu buna gore secilir:

      * olcum > limit  -> BIRBIRINE YAKLASTIR (decoupling mesafesi, net
        uzunlugu, yuk kondansatoru...)
      * olcum < limit  -> BIRBIRINDEN UZAKLASTIR (courtyard cakismasi,
        asgari aciklik...)

    Bu ayrimi kacirmak, cakisan iki bileseni ust uste bindirmeye calismak
    demektir - limit orada "en az bu kadar acik olsun" anlamina gelir.
    """
    refs = [r for r in _refs_of(finding) if r in placement]
    if len(refs) < 2:
        return []

    measured = getattr(finding, "measured", None)
    limit = getattr(finding, "limit", None)
    if not isinstance(limit, (int, float)) or limit <= 0:
        limit = 10.0
    push_apart = isinstance(measured, (int, float)) and measured < limit

    moves: list[tuple[str, tuple[float, float, float]]] = []
    outline = ctx.outline()

    for mover in refs:
        if mover in ctx.locked:
            continue
        others = [r for r in refs if r != mover]
        anchor = _centroid(others, placement)
        if anchor is None:
            continue
        ax, ay = anchor
        mx, my, rot = placement[mover]

        if push_apart:
            # Cakismayi acmak icin gereken en kucuk yaricap
            gap = _extent_of(mover, ctx) + max(_extent_of(r, ctx) for r in others) + limit
            radii = [gap * f for f in (1.0, 1.35, 1.8)]
        else:
            # Limitin guvenli ic tarafina yerlestir
            radii = [limit * f for f in _RADIUS_FRACTIONS]

        for radius in radii:
            for nx, ny in _ring(ax, ay, radius):
                if _inside(outline, nx, ny) and (abs(nx - mx) > 1e-9 or abs(ny - my) > 1e-9):
                    moves.append((mover, (nx, ny, rot)))
    return moves


def _nudge_moves(
    ref: str,
    placement: Placement,
    ctx: PlacementContext,
    rng: random.Random,
) -> list[tuple[str, tuple[float, float, float]]]:
    """Tek bilesen icin kucuk kaydirma ve 90 derece donme denemeleri."""
    x, y, rot = placement[ref]
    outline = ctx.outline()
    moves = []
    for step in _NUDGES:
        for dx, dy in ((step, 0.0), (-step, 0.0), (0.0, step), (0.0, -step)):
            if _inside(outline, x + dx, y + dy):
                moves.append((ref, (x + dx, y + dy, rot)))
    for turn in (90.0, 180.0, 270.0):
        moves.append((ref, (x, y, (rot + turn) % 360.0)))
    rng.shuffle(moves)
    return moves


def polish(
    start: Placement,
    ctx: PlacementContext,
    budget_s: float | None = None,
    *,
    verbose: bool = False,
) -> Placement:
    """Baslangic yerlesimini hakem olcutuyle iyilestirir.

    Hicbir zaman baslangictan kotu bir sonuc dondurmez. `ctx.evaluate`
    yoksa (eski cagri yolu) girdiyi oldugu gibi geri verir.
    """
    if ctx.evaluator is None:
        return dict(start)

    deadline = time.perf_counter() + (budget_s if budget_s is not None else ctx.time_budget_s)
    rng = random.Random(ctx.seed)

    best = dict(start)
    best_eval = ctx.evaluate(best)
    if best_eval is None:
        return best

    def try_moves(moves) -> bool:
        """Ilk iyilestiren hamleyi kabul eder (first-improvement)."""
        nonlocal best, best_eval
        for ref, xyr in moves:
            if time.perf_counter() > deadline:
                return False
            cand = _with(best, ref, xyr)
            ev = ctx.evaluate(cand)
            if ev is not None and ev.better_than(best_eval):
                best, best_eval = cand, ev
                return True
        return False

    # 1) Bulgu gudumlu onarim: hakemin saydigi hatalara dogrudan nisan al.
    #
    # Her tur, o anki bulgu listesinin tamamini SIRAYLA gezer. Ilk iyilesmede
    # bastan baslamak, kucuk kazanclar veren tek bir bulgunun butun butceyi
    # yemesine yol aciyordu - bu yuzden iyilesme olsa da sonraki bulguya
    # gecilir; liste ancak tur sonunda tazelenir.
    improved = True
    while improved and time.perf_counter() < deadline:
        improved = False
        findings = list(best_eval.findings)
        errors = [f for f in findings if getattr(f, "severity", "") == "error"]
        warnings = [f for f in findings if getattr(f, "severity", "") == "warning"]
        for finding in errors + warnings:
            if time.perf_counter() > deadline:
                break
            if try_moves(_finding_moves(finding, best, ctx)):
                improved = True
                if verbose:
                    print(f"    onarim: {getattr(finding, 'rule_id', '?')} -> {best_eval.score:.1f}")

    # 2) Genel ince ayar: kalan butceyi bilesenleri tek tek kaydirmaya harca.
    movable = [r for r in ctx.movable() if r in best]
    rng.shuffle(movable)
    idx = 0
    stagnant = 0
    while time.perf_counter() < deadline and movable and stagnant < len(movable):
        ref = movable[idx % len(movable)]
        idx += 1
        if try_moves(_nudge_moves(ref, best, ctx, rng)):
            stagnant = 0
            if verbose:
                print(f"    ince ayar: {ref} -> {best_eval.score:.1f}")
        else:
            stagnant += 1

    return best


def keep_best(
    candidates: dict[str, Placement],
    ctx: PlacementContext,
) -> tuple[str, Placement, Evaluation | None]:
    """Adaylar arasindan hakem olcutune gore en iyisini secer.

    `candidates` icine kartin mevcut halini de koyun ki sonuc asla
    baslangictan kotu olmasin.
    """
    best_name, best_pl, best_ev = "", {}, None
    for name, pl in candidates.items():
        ev = ctx.evaluate(pl)
        if ev is None:
            if not best_name:
                best_name, best_pl = name, pl
            continue
        if ev.better_than(best_ev):
            best_name, best_pl, best_ev = name, pl, ev
    return best_name, best_pl, best_ev
