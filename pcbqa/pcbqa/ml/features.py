"""DONMUS OZNITELIK SEMASI - bir aday hamleyi sayilara cevirir.

Bu dosya `placement/base.py` ile ayni statude: **geri uyumsuz degistirmeyin.**
Egitilmis model dosyalari oznitelik ADLARINI ve SIRASINI icinde saklar; sema
degisirse eski modeller sessizce yanlis sayilari okur. Yeni oznitelik eklemek
icin `FEATURE_VERSION`'i artirin ve yeni adi listenin SONUNA koyun -
`ml.model.Model.predict` eksik/fazla adi yakalar ve hata verir.

## Neden bu isin ML tarafi burada baslamak zorunda

Asama 3'un ana dersi: "yerlestirici, hakemin puanladigi seyi optimize etmeli."
Asama 5 bunu bir adim ileri goturur: hakemin gercek olcumu DOGRU ama PAHALI
(buyuk kartta bir degerlendirme onlarca ms; `jetson` gibi kartlarda `auto`nun
sure butcesini asmasinin sebebi tam olarak bu). Buradaki oznitelikler ayni
soruyu **yerel** olarak cevaplamaya calisir:

    "Bu bileseni buraya tasirsam hakemin puani artar mi?"

Hepsi tek bir bilesenin kendi netleri ve yakin komsulariyla hesaplanir, yani
maliyet kartin buyuklugune degil bilesenin **derecesine** baglidir.

## Vekil maliyet uydurmak degil mi bu?

Hayir - ve fark onemli. Asama 3'te yasaklanan sey, EL YAPIMI bir vekil maliyet
uydurup hakemi hic gormemekti. Burada oznitelikler yalnizca **girdi**; hedef
degisken her zaman hakemin gercek olcumundeki degisimdir (`ml/collect.py`) ve
model ciktisi yalnizca hamlelerin DENENME SIRASINI belirler. Kabul karari hala
`ctx.evaluate` ile verilir, yani monotonluk garantisi bozulmaz. Model tamamen
yaniliyorsa sonuc yavaslamaktir, gerileme degil.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .. import geom
from ..model import Design

# Sema surumu. Oznitelik listesi her degistiginde artar.
FEATURE_VERSION = 1

# Bilesen turleri - `model.ref_kind` ile ayni kume, sabit sirali.
KINDS: tuple[str, ...] = (
    "ic",
    "capacitor",
    "resistor",
    "inductor",
    "diode",
    "transistor",
    "crystal",
    "connector",
    "switch",
    "fuse",
    "testpoint",
    "other",
)

# Komsu aramasinin yaricapi (mm) ve izgara hucre boyu.
NEIGHBOR_RADIUS_MM = 15.0
_GRID_MM = 10.0

# "Uzak" yerine kullanilan sonlu buyuk deger - komsu yoksa sonsuz yazamayiz,
# model sonsuzla calisamaz.
FAR_MM = 250.0


def _kind_index(kind: str) -> int:
    try:
        return KINDS.index(kind)
    except ValueError:
        return KINDS.index("other")


FEATURE_NAMES: tuple[str, ...] = (
    # --- kart baglami (hamleden bagimsiz, modelin kartlar arasi genellemesi icin)
    "board_components_log",
    "board_nets_log",
    "board_density",
    "board_diag_log",
    "cur_score_norm",
    "cur_errors_log",
    "cur_warnings_log",
    # --- tasinan bilesen
    "comp_pads_log",
    "comp_area_log",
    "comp_extent",
    "comp_degree_log",
    *(f"kind_{k}" for k in KINDS),
    "comp_in_finding",
    "comp_finding_error",
    "comp_finding_ratio",
    # --- hamlenin geometrisi
    "move_dist",
    "move_dist_norm",
    "move_rot_changed",
    "edge_dist_before",
    "edge_dist_after",
    "d_edge_dist",
    # --- tel uzunlugu (yerel: yalnizca bu bilesenin netleri)
    "hpwl_before_log",
    "d_hpwl",
    "d_hpwl_norm",
    "d_hpwl_worst_net",
    "nets_improved_frac",
    # --- komsuluk ve cakisma
    "overlaps_before",
    "overlaps_after",
    "d_overlaps",
    "clearance_before",
    "clearance_after",
    "d_clearance",
    "neighbors_before",
    "neighbors_after",
    # --- ayni nete bagli bilesenlere yakinlik (proximity kurallarinin vekili)
    "net_partner_min_before",
    "net_partner_min_after",
    "d_net_partner_min",
    "net_partner_mean_before",
    "net_partner_mean_after",
    "d_net_partner_mean",
)

FEATURE_COUNT = len(FEATURE_NAMES)


def _log1p(v: float) -> float:
    return math.log1p(max(0.0, v))


def _rotate(dx: float, dy: float, degrees: float) -> tuple[float, float]:
    """KiCad donme konvansiyonu (Y asagi) - `pcb._rotate` ile ayni formul.

    Burada yeniden yaziliyor cunku `ml` katmani `pcb`nin ozel yardimcilarina
    degil, yalnizca `model.Design`e bagli olmali.
    """
    if not degrees:
        return dx, dy
    rad = math.radians(degrees)
    cos, sin = math.cos(rad), math.sin(rad)
    return dx * cos + dy * sin, dy * cos - dx * sin


@dataclass
class _CompStatic:
    """Bilesenin hamleden bagimsiz, bir kez hesaplanan bilgileri."""

    ref: str
    kind_index: int
    pad_count: int
    courtyard_local: list[tuple[float, float]]
    extent: float
    area: float
    nets: tuple[str, ...] = ()


class MoveFeaturizer:
    """Bir tasarim icin oznitelik cikarici.

    Kullanim:

        fz = MoveFeaturizer(design, locked)
        fz.refresh(placement, evaluation)          # yerlesim degistiginde
        vec = fz.features(ref, (x, y, rot))        # aday hamle basina

    `refresh` cagrilmadan `features` cagrilamaz; ikisinin ayri olmasinin sebebi
    yerel aramanin binlerce aday icin AYNI yerlesim onbelleklerini kullanmasi.
    """

    def __init__(
        self,
        design: Design,
        locked: Iterable[str] = (),
        *,
        neighbor_radius_mm: float = NEIGHBOR_RADIUS_MM,
    ) -> None:
        self.design = design
        self.locked = set(locked)
        self.radius = neighbor_radius_mm

        self._static: dict[str, _CompStatic] = {}
        self._net_pins: dict[str, list[tuple[str, float, float]]] = {}

        for comp in design.board.components:
            local_pads = [(p.dx, p.dy) for p in comp.pads]
            poly = list(comp.courtyard_local)
            if poly:
                xs = [x for x, _ in poly]
                ys = [y for _, y in poly]
                extent = max(max(xs) - min(xs), max(ys) - min(ys)) / 2.0
                area = abs(geom.area(geom.convex_hull(poly)))
            elif local_pads:
                xs = [x for x, _ in local_pads]
                ys = [y for _, y in local_pads]
                extent = max(max(xs) - min(xs), max(ys) - min(ys)) / 2.0
                area = (max(xs) - min(xs)) * (max(ys) - min(ys))
            else:
                extent, area = 1.0, 0.0
            self._static[comp.ref] = _CompStatic(
                ref=comp.ref,
                kind_index=_kind_index(design.kind_of(comp.ref)),
                pad_count=len(local_pads),
                courtyard_local=poly,
                extent=max(extent, 0.1),
                area=area,
            )

        # net -> [(ref, pad_dx, pad_dy)]; pad konumlari YERLESIMDEN turetilir,
        # boylece arama sirasindaki yerlesimle (design'inkiyle degil) calisiriz.
        nets_of: dict[str, set[str]] = {ref: set() for ref in self._static}
        for net_name in design.net_names():
            entries: list[tuple[str, float, float]] = []
            for pin in design.pins_on_net(net_name):
                comp = design.component(pin.ref)
                if comp is None:
                    continue
                pad = comp.pad(pin.pin)
                if pad is None:
                    continue
                entries.append((pin.ref, pad.dx, pad.dy))
            if len(entries) >= 2:
                self._net_pins[net_name] = entries
                for ref, _, _ in entries:
                    nets_of.setdefault(ref, set()).add(net_name)
        for ref, names in nets_of.items():
            if ref in self._static:
                self._static[ref].nets = tuple(sorted(names))

        # net -> ayni nete bagli farkli bilesenler
        self._net_refs: dict[str, tuple[str, ...]] = {
            name: tuple(sorted({r for r, _, _ in entries}))
            for name, entries in self._net_pins.items()
        }

        metrics = design.metrics()
        outline = design.board.outline
        if outline is None:
            xs = [c.x for c in design.board.components] or [0.0]
            ys = [c.y for c in design.board.components] or [0.0]
            outline = (min(xs), min(ys), max(xs), max(ys))
        self.outline = outline
        diag = math.hypot(outline[2] - outline[0], outline[3] - outline[1]) or 1.0
        self._diag = diag
        density = metrics.density_pct
        self._board_block = [
            _log1p(len(design.board.components)),
            _log1p(len(self._net_pins)),
            (density / 100.0) if density is not None else -1.0,
            _log1p(diag),
        ]

        # refresh() ile dolar
        self._pos: dict[str, tuple[float, float, float]] = {}
        self._poly: dict[str, list[tuple[float, float]]] = {}
        self._bbox: dict[str, tuple[float, float, float, float]] = {}
        self._grid: dict[tuple[int, int], list[str]] = {}
        self._pin_xy: dict[str, list[tuple[str, float, float]]] = {}
        self._finding: dict[str, tuple[float, float]] = {}
        self._eval_block = [1.0, 0.0, 0.0]
        self._ready = False

    # ------------------------------------------------------------------ onbellek

    def refresh(
        self,
        placement: dict[str, tuple[float, float, float]],
        evaluation: Any = None,
    ) -> None:
        """Yerlesim onbelleklerini tazeler. Yerlesim her degistiginde cagirin."""
        self._pos = {}
        for ref in self._static:
            xyr = placement.get(ref)
            if xyr is None:
                comp = self.design.component(ref)
                xyr = (comp.x, comp.y, comp.rotation) if comp else (0.0, 0.0, 0.0)
            self._pos[ref] = (float(xyr[0]), float(xyr[1]), float(xyr[2]))

        self._poly = {ref: self._abs_poly(ref, self._pos[ref]) for ref in self._static}
        self._bbox = {
            ref: (
                min(px for px, _ in poly),
                min(py for _, py in poly),
                max(px for px, _ in poly),
                max(py for _, py in poly),
            )
            for ref, poly in self._poly.items()
            if poly
        }

        self._grid = {}
        for ref, (x, y, _) in self._pos.items():
            self._grid.setdefault((int(x // _GRID_MM), int(y // _GRID_MM)), []).append(ref)

        self._pin_xy = {}
        for name, entries in self._net_pins.items():
            resolved = []
            for ref, dx, dy in entries:
                px, py, rot = self._pos.get(ref, (0.0, 0.0, 0.0))
                rx, ry = _rotate(dx, dy, rot)
                resolved.append((ref, px + rx, py + ry))
            self._pin_xy[name] = resolved

        self._finding = {}
        if evaluation is not None:
            for finding in getattr(evaluation, "findings", ()) or ():
                severity = 1.0 if getattr(finding, "severity", "") == "error" else 0.0
                measured = getattr(finding, "measured", None)
                limit = getattr(finding, "limit", None)
                ratio = 0.0
                if isinstance(measured, (int, float)) and isinstance(limit, (int, float)) and limit:
                    ratio = max(-4.0, min(4.0, float(measured) / float(limit)))
                for ref in getattr(finding, "refs", ()) or ():
                    prev = self._finding.get(ref)
                    if prev is None or severity > prev[0]:
                        self._finding[ref] = (severity, ratio)
            score = float(getattr(evaluation, "score", 100.0))
            self._eval_block = [
                score / 100.0,
                _log1p(getattr(evaluation, "errors", 0)),
                _log1p(getattr(evaluation, "warnings", 0)),
            ]
        else:
            self._eval_block = [1.0, 0.0, 0.0]

        self._ready = True

    # ------------------------------------------------------------------ yardimci

    def _abs_poly(
        self, ref: str, xyr: tuple[float, float, float]
    ) -> list[tuple[float, float]]:
        static = self._static[ref]
        x, y, rot = xyr
        if static.courtyard_local:
            return [
                (x + rx, y + ry)
                for rx, ry in (_rotate(lx, ly, rot) for lx, ly in static.courtyard_local)
            ]
        e = static.extent
        return [(x - e, y - e), (x + e, y - e), (x + e, y + e), (x - e, y + e)]

    def _neighbors(self, ref: str, x: float, y: float) -> list[str]:
        """Yaricap icindeki bilesenler - izgara sorgusu."""
        cx, cy = int(x // _GRID_MM), int(y // _GRID_MM)
        span = int(self.radius // _GRID_MM) + 1
        out = []
        for gx in range(cx - span, cx + span + 1):
            for gy in range(cy - span, cy + span + 1):
                for other in self._grid.get((gx, gy), ()):
                    if other == ref:
                        continue
                    ox, oy, _ = self._pos[other]
                    if math.hypot(ox - x, oy - y) <= self.radius:
                        out.append(other)
        return out

    def _edge_distance(self, x: float, y: float) -> float:
        minx, miny, maxx, maxy = self.outline
        return min(x - minx, maxx - x, y - miny, maxy - y)

    def _net_state(
        self, ref: str, xyr: tuple[float, float, float] | None
    ) -> tuple[float, list[float]]:
        """Bilesenin netlerinin HPWL toplami ve net basina degerler.

        `xyr` verilirse bu bilesenin pinleri oraya tasinmis varsayilir; None
        ise mevcut onbellek kullanilir. Maliyet netin pin sayisiyla orantili,
        kartin buyuklugunden bagimsiz.
        """
        static = self._static[ref]
        per_net: list[float] = []
        total = 0.0
        nx = ny = nrot = 0.0
        if xyr is not None:
            nx, ny, nrot = xyr
        for name in static.nets:
            xs: list[float] = []
            ys: list[float] = []
            cached = self._pin_xy[name]
            if xyr is None:
                for _, px, py in cached:
                    xs.append(px)
                    ys.append(py)
            else:
                offsets = self._net_pins[name]
                for i, (pin_ref, px, py) in enumerate(cached):
                    if pin_ref == ref:
                        rx, ry = _rotate(offsets[i][1], offsets[i][2], nrot)
                        xs.append(nx + rx)
                        ys.append(ny + ry)
                    else:
                        xs.append(px)
                        ys.append(py)
            if len(xs) < 2:
                per_net.append(0.0)
                continue
            hpwl = (max(xs) - min(xs)) + (max(ys) - min(ys))
            per_net.append(hpwl)
            total += hpwl
        return total, per_net

    def _partner_distances(self, ref: str, x: float, y: float) -> tuple[float, float]:
        """Ayni nete bagli bilesenlere en kisa ve ortalama mesafe.

        `proximity` kurallarinin ucuz vekili: o kurallarin tamami "ayni nette
        su bilesen su kadar yakin mi" biciminde.
        """
        best = FAR_MM
        total = 0.0
        count = 0
        seen: set[str] = set()
        for name in self._static[ref].nets:
            for other in self._net_refs[name]:
                if other == ref or other in seen:
                    continue
                seen.add(other)
                ox, oy, _ = self._pos[other]
                d = math.hypot(ox - x, oy - y)
                best = min(best, d)
                total += min(d, FAR_MM)
                count += 1
        mean = (total / count) if count else FAR_MM
        return best, mean

    def _overlap_state(
        self, ref: str, poly: list[tuple[float, float]], x: float, y: float
    ) -> tuple[float, float, float]:
        """(cakisan komsu sayisi, en kucuk aciklik, yaricaptaki komsu sayisi).

        Cakisma testi GERCEK poligonla (SAT) yapilir - `courtyard_overlap`
        kurali da oyle calisiyor, vekilin orada yanilmasi pahaliya patlar.
        Aciklik ise sinir kutulari arasindaki bosluktur: gercek poligon
        mesafesi olcumun %77'sini yiyordu (profil) ve siralamaya kattigi sey
        kutu boslugundan farksizdi. Cakismayan iki kutu icin bu deger gercek
        mesafenin alt siniridir, yani yon olarak dogru.
        """
        neighbors = self._neighbors(ref, x, y)
        minx = min(px for px, _ in poly)
        maxx = max(px for px, _ in poly)
        miny = min(py for _, py in poly)
        maxy = max(py for _, py in poly)

        overlaps = 0
        clearance = FAR_MM
        for other in neighbors:
            box = self._bbox.get(other)
            if box is None:
                continue
            omnx, omny, omxx, omxy = box
            gx = omnx - maxx if omnx > maxx else (minx - omxx if minx > omxx else 0.0)
            gy = omny - maxy if omny > maxy else (miny - omxy if miny > omxy else 0.0)
            if gx > 0.0 or gy > 0.0:
                # Kutular ayrik: poligonlar da kesin ayrik, SAT'a gerek yok.
                if clearance > 0.0:
                    clearance = min(clearance, math.hypot(gx, gy))
                continue
            # Kutular kesisiyor: burada gercek poligon testi sart. Nadir
            # oldugu icin pahali `geom.distance` yalnizca bu dala duser.
            if geom.overlap(poly, self._poly[other]):
                overlaps += 1
                clearance = 0.0
            elif clearance > 0.0:
                clearance = min(clearance, geom.distance(poly, self._poly[other]))
        return float(overlaps), min(clearance, FAR_MM), float(len(neighbors))

    # ------------------------------------------------------------------ oznitelik

    def features(self, ref: str, xyr: tuple[float, float, float]) -> list[float]:
        """Aday hamle icin oznitelik vektoru. `FEATURE_NAMES` ile ayni sirada."""
        if not self._ready:
            raise RuntimeError("once refresh(placement) cagirin")
        if ref not in self._static:
            raise KeyError(f"kartta boyle bir bilesen yok: {ref!r}")

        static = self._static[ref]
        x0, y0, rot0 = self._pos[ref]
        x1, y1, rot1 = float(xyr[0]), float(xyr[1]), float(xyr[2])

        kind_hot = [0.0] * len(KINDS)
        kind_hot[static.kind_index] = 1.0
        severity, ratio = self._finding.get(ref, (0.0, 0.0))

        hpwl_before, per_before = self._net_state(ref, None)
        hpwl_after, per_after = self._net_state(ref, (x1, y1, rot1))
        d_hpwl = hpwl_after - hpwl_before
        deltas = [a - b for a, b in zip(per_after, per_before)]
        worst = max(deltas) if deltas else 0.0
        improved = (
            sum(1 for d in deltas if d < -1e-9) / len(deltas) if deltas else 0.0
        )

        ov_b, cl_b, nb_b = self._overlap_state(ref, self._poly[ref], x0, y0)
        poly_after = self._abs_poly(ref, (x1, y1, rot1))
        ov_a, cl_a, nb_a = self._overlap_state(ref, poly_after, x1, y1)

        pmin_b, pmean_b = self._partner_distances(ref, x0, y0)
        pmin_a, pmean_a = self._partner_distances(ref, x1, y1)

        dist = math.hypot(x1 - x0, y1 - y0)
        edge_b = self._edge_distance(x0, y0)
        edge_a = self._edge_distance(x1, y1)

        vec = [
            *self._board_block,
            *self._eval_block,
            _log1p(static.pad_count),
            _log1p(static.area),
            static.extent,
            _log1p(len(static.nets)),
            *kind_hot,
            1.0 if ref in self._finding else 0.0,
            severity,
            ratio,
            dist,
            dist / self._diag,
            1.0 if abs(rot1 - rot0) > 1e-9 else 0.0,
            edge_b,
            edge_a,
            edge_a - edge_b,
            _log1p(hpwl_before),
            d_hpwl,
            d_hpwl / self._diag,
            worst,
            improved,
            ov_b,
            ov_a,
            ov_a - ov_b,
            cl_b,
            cl_a,
            cl_a - cl_b,
            nb_b,
            nb_a,
            pmin_b,
            pmin_a,
            pmin_a - pmin_b,
            pmean_b,
            pmean_a,
            pmean_a - pmean_b,
        ]
        if len(vec) != FEATURE_COUNT:  # sema ile kod ayrisirsa hemen patla
            raise AssertionError(
                f"oznitelik sayisi uyusmuyor: {len(vec)} != {FEATURE_COUNT}"
            )
        return vec

    def features_many(
        self, moves: Sequence[tuple[str, tuple[float, float, float]]]
    ) -> list[list[float]]:
        return [self.features(ref, xyr) for ref, xyr in moves]
