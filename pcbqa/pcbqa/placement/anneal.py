"""Benzetimli tavlama (simulated annealing) yerlestirici.

Fikir: `bench.rules.yaml`'daki esikleri (okunmus, degistirilmemis) yansitan bir
maliyet fonksiyonu tanimlanir - agirlikli HPWL + kritik mesafe cezalari
(decoupling, kristal yuk kondansatoru, regulator kondansatoru) + courtyard
cakisma cezasi + kart kenari ihlali. Sonra rastgele `move` / `swap` /
`rotate90` hamleleriyle uzay taranir; kotulesen hamleler sicakliga bagli bir
olasilikla (Metropolis kriteri) kabul edilir, sicaklik zaman butcesine gore
kademeli dusurulur. En iyi gorulen durum ayri tutulur (elitism) ve sonunda o
donduruLur - SA rastgele gezindigi icin "su an nerede" ile "en iyi nerede
oldugu" farkli olabilir.

Guclu yan: yerel minimumlardan kacabilme (swap + sicaklikli kabul).
Zayif yan: yavas - bu yuzden `ctx.time_budget_s`'e gore toplam iterasyon
sayisi (dolayisiyla sicaklik programi) onceden, tutucu (guvenli) bir hiz
tahminiyle hesaplanir. Sicaklik program ITERASYON SAYISINA endekslidir,
gercek zaman akisina degil - boylece ayni seed + ayni butce, makine o an
ne kadar yukluyse yuklu olsun, HER ZAMAN AYNI sonucu uretir. Gercek zaman
sadece bir guvenlik supabi olarak izlenir (asiri yavas donen bir ortamda
donmeyi onlemek icin); normal kosuda hic tetiklenmez.
"""

from __future__ import annotations

import copy
import math
import random
import re
import time

from .. import geom
from .base import Placement, PlacementContext

# --------------------------------------------------------------------------
# bench.rules.yaml'dan OKUNMUS (degistirilmemis) esikler - maliyet fonksiyonu
# bunlari yaklasik olarak modelliyor ki tavlama gercek skoru optimize etsin.
# --------------------------------------------------------------------------

_IGNORE_NETS = {"GND", "AGND", "NC"}

# (net regex, max_hpwl_mm, agirlik)
_NET_LENGTH_RULES = [
    (re.compile(r"^(3V3|VBUS|AVDD)$", re.I), 60.0, 5.0),
    (re.compile(r"^(XIN|XOUT)$", re.I), 12.0, 35.0),
    (re.compile(r"^(SDA|SCL|TX|RX|nRESET|GPIO)", re.I), 45.0, 2.0),
]

# ((net_a, net_b), tolerans_mm, agirlik)
_LENGTH_MATCH_GROUPS = [
    (("USB_DP", "USB_DM"), 3.0, 18.0),
]

_HPWL_WEIGHT = 0.05          # genel kompaktlik baskisi (arka plan)
_CLEARANCE_MM = 0.2          # courtyard-cakisma kurali
_OVERLAP_WEIGHT = 10.0
_EDGE_MIN_MM = 2.0           # kart-kenari kurali
_EDGE_WEIGHT = 10.0


def _build_proximity_group(
    design,
    *,
    pin_ref_rx=None,
    pin_kind=None,
    pin_pintype=None,
    partner_kind=None,
    partner_value_rx=None,
    exclusive=True,
    max_mm=6.0,
    weight=1.0,
):
    """`proximity` kuralinin ayni netteki hedef/partner eslesmesini onceden
    cikarir (net baglantisi yerlesimle degismez - sadece mesafeler degisir).
    """
    groups = []
    for net_name in design.net_names():
        if net_name in _IGNORE_NETS:
            continue
        pins = design.pins_on_net(net_name)

        targets = []
        for p in pins:
            if pin_ref_rx is not None and not pin_ref_rx.search(p.ref):
                continue
            if pin_kind is not None and design.kind_of(p.ref) != pin_kind:
                continue
            if pin_pintype is not None and p.pintype != pin_pintype:
                continue
            targets.append((p.ref, p.pin))
        if not targets:
            continue

        partners = []
        for p in pins:
            if partner_kind is not None and design.kind_of(p.ref) != partner_kind:
                continue
            if partner_value_rx is not None and not partner_value_rx.search(design.value_of(p.ref)):
                continue
            partners.append((p.ref, p.pin))
        if not partners:
            continue

        groups.append((targets, partners))

    return {"groups": groups, "exclusive": exclusive, "max_mm": max_mm, "weight": weight}


def _proximity_cost(group, pin_xy) -> float:
    total = 0.0
    max_mm = group["max_mm"]
    weight = group["weight"]
    exclusive = group["exclusive"]
    claimed: set[str] = set()

    for targets, partners in group["groups"]:
        pairs = []
        for t in targets:
            tx = pin_xy(t)
            if tx is None:
                continue
            for p in partners:
                if p[0] == t[0]:
                    continue
                px = pin_xy(p)
                if px is None:
                    continue
                d = math.hypot(tx[0] - px[0], tx[1] - px[1])
                pairs.append((d, t, p))

        if exclusive:
            pairs.sort(key=lambda z: z[0])
            matched: dict = {}
            used: set[str] = set()
            for d, t, p in pairs:
                if t in matched:
                    continue
                if p[0] in claimed or p[0] in used:
                    continue
                matched[t] = d
                used.add(p[0])
            claimed |= used
            for t in targets:
                d = matched.get(t)
                if d is None:
                    total += weight * (max_mm * 4.0) ** 2
                elif d > max_mm:
                    total += weight * (d - max_mm) ** 2
        else:
            best_for_target: dict = {}
            for d, t, p in pairs:
                if t not in best_for_target or d < best_for_target[t]:
                    best_for_target[t] = d
            for t in targets:
                d = best_for_target.get(t)
                if d is not None and d > max_mm:
                    total += weight * (d - max_mm) ** 2

    return total


def _snapshot(work, refs):
    return {ref: (work[ref].x, work[ref].y, work[ref].rotation) for ref in refs}


def _accept(new_cost: float, current_cost: float, temperature: float, rng: random.Random) -> bool:
    if new_cost <= current_cost:
        return True
    if temperature <= 1e-9:
        return False
    return rng.random() < math.exp(-(new_cost - current_cost) / temperature)


class SimulatedAnnealing:
    """Benzetimli tavlama ile detayli yerlesim iyilestirmesi.

    Maliyet = agirlikli HPWL + kritik-mesafe cezalari (decoupling, kristal
    yuku, regulator kondansatoru, USB diferansiyel dengesi, guc rayi uzunlugu)
    + courtyard cakisma cezasi + kart kenari ihlali cezasi.

    Hamleler: `move` (kucuk sapma veya buyuk sicrama), `swap` (iki bilesenin
    konum+rotasyonunu degistirir - atama tipi problemler icin onemli, cunku
    hangi kondansatorun hangi IC'ye "ait" oldugu net yapisindan degil sadece
    fiziksel yakinliktan belli oluyor), `rotate90`.

    Sicaklik zaman butcesine (ctx.time_budget_s) endeksli geometrik programla
    dusurulur; en iyi gorulen durum ayri saklanir (elitism) ve sonunda o
    dondurulur.
    """

    name = "anneal"

    def run(self, ctx: PlacementContext) -> Placement:
        design = ctx.design
        movable_refs = ctx.movable()
        if not movable_refs:
            return {}

        rng = random.Random(ctx.seed)
        minx, miny, maxx, maxy = ctx.outline()
        margin = 1.0
        lo_x, hi_x = minx + margin, max(minx + margin, maxx - margin)
        lo_y, hi_y = miny + margin, max(miny + margin, maxy - margin)

        # -- calisma kopyalari: sadece tasinabilirler deepcopy, kilitliler
        #    dogrudan referans (asla .place() cagrilmaz, ctx.design bozulmaz) --
        work = {}
        for c in design.board.components:
            work[c.ref] = copy.deepcopy(c) if c.ref not in ctx.locked else c

        move_refs = list(movable_refs)

        net_pins = {
            name: [(p.ref, p.pin) for p in design.pins_on_net(name)]
            for name in design.net_names()
        }

        proximity_groups = [
            # guc-decoupling: her IC guc pininin KENDI kondansatoru olmali
            _build_proximity_group(
                design,
                pin_kind="ic",
                pin_pintype="power_in",
                partner_kind="capacitor",
                exclusive=True,
                max_mm=6.0,
                weight=20.0,
            ),
            # regulator-kondansator: U2'nin tum pinleri, uF degerli kondansatorlere yakin
            _build_proximity_group(
                design,
                pin_ref_rx=re.compile(r"^U2$"),
                partner_kind="capacitor",
                partner_value_rx=re.compile("uF", re.I),
                exclusive=False,
                max_mm=8.0,
                weight=6.0,
            ),
            # kristal-yuk-kondansatoru: kristal pinleri, pF degerli kondansatorlere yakin
            _build_proximity_group(
                design,
                pin_kind="crystal",
                partner_kind="capacitor",
                partner_value_rx=re.compile("pF", re.I),
                exclusive=True,
                max_mm=6.0,
                weight=20.0,
            ),
        ]

        def pin_xy(t):
            ref, pin = t
            c = work.get(ref)
            if c is None:
                return None
            pad = c.pad(pin)
            return (pad.x, pad.y) if pad is not None else None

        def cost() -> float:
            total = 0.0
            hpwl_cache: dict[str, float] = {}

            for name, pins in net_pins.items():
                pts = []
                for ref, pin in pins:
                    xy = pin_xy((ref, pin))
                    if xy is not None:
                        pts.append(xy)
                if len(pts) >= 2:
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    h = (max(xs) - min(xs)) + (max(ys) - min(ys))
                else:
                    h = 0.0
                hpwl_cache[name] = h
                if name not in _IGNORE_NETS:
                    total += _HPWL_WEIGHT * h

            for rx, max_mm, w in _NET_LENGTH_RULES:
                for name, h in hpwl_cache.items():
                    if h > max_mm and rx.search(name):
                        total += w * (h - max_mm) ** 2

            for (na, nb), tol, w in _LENGTH_MATCH_GROUPS:
                diff = abs(hpwl_cache.get(na, 0.0) - hpwl_cache.get(nb, 0.0))
                if diff > tol:
                    total += w * (diff - tol) ** 2

            for group in proximity_groups:
                total += _proximity_cost(group, pin_xy)

            # courtyard cakismasi (rules.py'deki mantigin aynisi: bbox on
            # elemesi + gercek poligon SAT testi)
            comps = [c for c in work.values() if c.courtyard_poly]
            n = len(comps)
            for i in range(n):
                a = comps[i]
                ax1, ay1, ax2, ay2 = a.courtyard
                a_back = a.layer.startswith("B.")
                for j in range(i + 1, n):
                    b = comps[j]
                    if a_back != b.layer.startswith("B."):
                        continue
                    bx1, by1, bx2, by2 = b.courtyard
                    if max(bx1 - ax2, ax1 - bx2, by1 - ay2, ay1 - by2) >= _CLEARANCE_MM:
                        continue
                    if geom.overlap(a.courtyard_poly, b.courtyard_poly):
                        ox = min(ax2, bx2) - max(ax1, bx1)
                        oy = min(ay2, by2) - max(ay1, by1)
                        area = max(0.0, ox) * max(0.0, oy)
                        total += _OVERLAP_WEIGHT * (8.0 + 6.0 * area)
                    else:
                        gap = geom.distance(a.courtyard_poly, b.courtyard_poly)
                        if gap < _CLEARANCE_MM:
                            # duz esik penaltisi: en ufak ihlal bile "hata" sayilir,
                            # sadece mesafeyle orantili kucuk bir kuadratik ceza
                            # SA'yi tam cozmeye zorlamaya yetmez (skor binary).
                            deficit = (_CLEARANCE_MM - gap) / _CLEARANCE_MM
                            total += _OVERLAP_WEIGHT * (1.0 + 4.0 * deficit)

            # kart kenari - sadece tasiyabildigimiz bilesenler icin (kilitliler
            # zaten oynatilamaz, onlarin ihlali motorca duzeltilemez).
            # NOT: `move_refs` (liste) uzerinden - `set` uzerinden gezmek
            # PYTHONHASHSEED'e bagli sirayla toplama yapar; kayan nokta
            # toplaminin sirasi degisince maliyette ULP farki olusur, bu da
            # tavlamanin kaotik dinamiginde binlerce iterasyon sonra tamamen
            # farkli bir sonuca yol acabilir (deterministik olmayan calisma).
            for ref in move_refs:
                c = work[ref]
                if not c.courtyard_poly:
                    continue
                cx1, cy1, cx2, cy2 = c.courtyard
                edge_margin = min(cx1 - minx, cy1 - miny, maxx - cx2, maxy - cy2)
                if edge_margin < _EDGE_MIN_MM:
                    deficit = (_EDGE_MIN_MM - edge_margin) / _EDGE_MIN_MM
                    total += _EDGE_WEIGHT * (1.0 + 4.0 * deficit)

            return total

        # ---------------------------------------------------------- tavlama
        current_cost = cost()
        best_cost = current_cost
        best_snapshot = _snapshot(work, movable_refs)

        temp0 = max(1e-6, best_cost * 0.05)
        temp_min = temp0 * 1e-3

        # Sicaklik programi ITERASYON SAYISINA endekslidir, gercek zaman
        # akisina degil - boylece ayni seed + ayni butce her zaman AYNI
        # sonucu uretir (makine yuku o an ne olursa olsun). Toplam iterasyon
        # sayisi ctx.time_budget_s'e gore SABIT bir hizla (bu makinede olculmus,
        # tutucu tutulmus) onceden hesaplanir; calisirken zaman asimini
        # sadece bir GUVENLIK supabi olarak kullaniriz (buyuk kartlarda
        # donmeyi onlemek icin), normal kosuda hic tetiklenmez.
        started = time.perf_counter()
        budget = max(0.1, ctx.time_budget_s - 0.3)
        # Tutucu (guvenli) tahmin: bu makine paralel calisan baska agent'larla
        # paylasilabilir, bu yuzden olculen en yavas hizin bile altinda kal.
        est_iters_per_sec = 2_000
        max_iterations = int(max(2_000, min(400_000, est_iters_per_sec * budget)))
        safety_deadline = started + ctx.time_budget_s * 1.5

        can_swap = len(move_refs) >= 2

        for iteration in range(max_iterations):
            if iteration % 512 == 0 and time.perf_counter() > safety_deadline:
                break
            frac = iteration / max_iterations
            temperature = temp0 * (temp_min / temp0) ** frac

            r = rng.random()
            if r < 0.55 or not can_swap:
                # -- move --
                ref = rng.choice(move_refs)
                c = work[ref]
                old_x, old_y, old_rot = c.x, c.y, c.rotation
                if rng.random() < 0.18:
                    nx = rng.uniform(lo_x, hi_x)
                    ny = rng.uniform(lo_y, hi_y)
                else:
                    sigma = 0.08 + 16.0 * (temperature / temp0)
                    nx = min(hi_x, max(lo_x, old_x + rng.gauss(0.0, sigma)))
                    ny = min(hi_y, max(lo_y, old_y + rng.gauss(0.0, sigma)))
                c.place(nx, ny, old_rot)
                new_cost = cost()
                if new_cost < best_cost:
                    best_cost = new_cost
                    best_snapshot = _snapshot(work, movable_refs)
                if _accept(new_cost, current_cost, temperature, rng):
                    current_cost = new_cost
                else:
                    c.place(old_x, old_y, old_rot)

            elif r < 0.85:
                # -- swap --
                a_ref, b_ref = rng.sample(move_refs, 2)
                a, b = work[a_ref], work[b_ref]
                old_a = (a.x, a.y, a.rotation)
                old_b = (b.x, b.y, b.rotation)
                a.place(old_b[0], old_b[1], old_b[2])
                b.place(old_a[0], old_a[1], old_a[2])
                new_cost = cost()
                if new_cost < best_cost:
                    best_cost = new_cost
                    best_snapshot = _snapshot(work, movable_refs)
                if _accept(new_cost, current_cost, temperature, rng):
                    current_cost = new_cost
                else:
                    a.place(old_a[0], old_a[1], old_a[2])
                    b.place(old_b[0], old_b[1], old_b[2])

            else:
                # -- rotate90 --
                ref = rng.choice(move_refs)
                c = work[ref]
                old_rot = c.rotation
                new_rot = (old_rot + 90.0) % 360.0
                c.place(c.x, c.y, new_rot)
                new_cost = cost()
                if new_cost < best_cost:
                    best_cost = new_cost
                    best_snapshot = _snapshot(work, movable_refs)
                if _accept(new_cost, current_cost, temperature, rng):
                    current_cost = new_cost
                else:
                    c.place(c.x, c.y, old_rot)

        return {ref: best_snapshot[ref] for ref in movable_refs}
