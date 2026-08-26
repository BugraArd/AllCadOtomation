"""DONMUS OZNITELIK SEMASI - bir aday hamleyi sayilara cevirir.

Bu dosya `placement/base.py` ile ayni statude: **geri uyumsuz degistirmeyin.**
(v2, Asama 6: birlesik hamleler - takas/kume tasima - eklendi. Tek bilesenli
hamlelerde ilk 51 deger v1 ile birebir ayni anlami tasir; sonuna 8 oznitelik
eklendi, yani v1 modelleri yeniden egitilmeli.)
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
FEATURE_VERSION = 2

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
    # --- BIRLESIK hamle blogu (sema v2, Asama 6): hamlenin tumunu ozetler.
    # Tek bilesenli hamlelerde bu degerler yukaridaki birincil bloktan
    # turetilebilir; ayri tutulmalarinin sebebi takas/kume hamlelerinde
    # ayrismalari - orada birincil bilesenin gordugu ile hamlenin toplam
    # etkisi farkli seylerdir.
    "moved_count_log",
    "is_swap",
    "move_dist_total",
    "move_dist_max",
    "d_hpwl_all",
    "d_hpwl_all_norm",
    "d_overlaps_all",
    "clearance_after_min",
)

FEATURE_COUNT = len(FEATURE_NAMES)


def _log1p(v: float) -> float:
    return math.log1p(max(0.0, v))


def _bbox_of(poly: Sequence[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [px for px, _ in poly]
    ys = [py for _, py in poly]
    return min(xs), min(ys), max(xs), max(ys)


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

    # ------------------------------------------------- birlesik hamle hesabi
    #
    # Asama 6: bir hamle artik birden fazla bileseni AYNI ANDA oynatabilir
    # (takas, kume tasima). Bu, hesabi da degistirir: A'nin yeni tel
    # uzunlugu B hala eski yerindeymis gibi hesaplanirsa takasin tam yarisi
    # yanlis olur. Asagidaki her fonksiyon `moved` sozlugunun TAMAMINI dikkate
    # alir; tek bilesenli hamle bunun 1 elemanli ozel halidir.

    def _nets_touched(self, refs: Iterable[str]) -> list[str]:
        """Verilen bilesenlerin dokundugu netler (tekrarsiz, kararli sirada)."""
        seen: dict[str, None] = {}
        for ref in refs:
            for name in self._static[ref].nets:
                seen.setdefault(name, None)
        return list(seen)

    def _hpwl(
        self, names: Sequence[str], moved: dict[str, tuple[float, float, float]] | None
    ) -> tuple[float, list[float]]:
        """Verilen netlerin HPWL toplami ve net basina degerleri.

        `moved` verilirse o bilesenlerin pinleri yeni konumlarindan hesaplanir.
        Maliyet netlerin pin sayisiyla orantili, kartin buyuklugunden bagimsiz.
        """
        per_net: list[float] = []
        total = 0.0
        for name in names:
            cached = self._pin_xy[name]
            xs: list[float] = []
            ys: list[float] = []
            if not moved:
                for _, px, py in cached:
                    xs.append(px)
                    ys.append(py)
            else:
                offsets = self._net_pins[name]
                for i, (pin_ref, px, py) in enumerate(cached):
                    target = moved.get(pin_ref)
                    if target is None:
                        xs.append(px)
                        ys.append(py)
                    else:
                        rx, ry = _rotate(offsets[i][1], offsets[i][2], target[2])
                        xs.append(target[0] + rx)
                        ys.append(target[1] + ry)
            if len(xs) < 2:
                per_net.append(0.0)
                continue
            hpwl = (max(xs) - min(xs)) + (max(ys) - min(ys))
            per_net.append(hpwl)
            total += hpwl
        return total, per_net

    def _partner_distances(
        self,
        ref: str,
        x: float,
        y: float,
        moved: dict[str, tuple[float, float, float]] | None = None,
    ) -> tuple[float, float]:
        """Ayni nete bagli bilesenlere en kisa ve ortalama mesafe.

        `proximity` kurallarinin ucuz vekili: o kurallarin tamami "ayni nette
        su bilesen su kadar yakin mi" biciminde. Partnerin kendisi de
        tasiniyorsa YENI konumu kullanilir.
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
                target = moved.get(other) if moved else None
                ox, oy = (target[0], target[1]) if target else self._pos[other][:2]
                d = math.hypot(ox - x, oy - y)
                best = min(best, d)
                total += min(d, FAR_MM)
                count += 1
        mean = (total / count) if count else FAR_MM
        return best, mean

    def _overlap_state(
        self,
        ref: str,
        poly: list[tuple[float, float]],
        x: float,
        y: float,
        moved: dict[str, tuple[float, float, float]] | None = None,
        new_polys: dict[str, list[tuple[float, float]]] | None = None,
    ) -> tuple[float, float, float]:
        """(cakisan komsu sayisi, en kucuk aciklik, yaricaptaki komsu sayisi).

        Cakisma testi GERCEK poligonla (SAT) yapilir - `courtyard_overlap`
        kurali da oyle calisiyor, vekilin orada yanilmasi pahaliya patlar.
        Aciklik ise sinir kutulari arasindaki bosluktur: gercek poligon
        mesafesi olcumun %77'sini yiyordu (profil) ve siralamaya kattigi sey
        kutu boslugundan farksizdi. Cakismayan iki kutu icin bu deger gercek
        mesafenin alt siniridir, yani yon olarak dogru.

        **Takasta kritik nokta:** izgara ESKI konumlardan kurulu. Tasinan
        bilesenler o yuzden komsu listesinden cikarilip YENI konumlariyla geri
        eklenir - yoksa A, B'nin eski yerine tasindiginda B'yi orada bulup
        hayali bir cakisma raporlanir, ve takas asla kabul edilmez.
        """
        candidates: list[tuple[tuple[float, float, float, float], list[tuple[float, float]]]] = []
        for other in self._neighbors(ref, x, y):
            if moved and other in moved:
                continue
            box = self._bbox.get(other)
            if box is not None:
                candidates.append((box, self._poly[other]))
        if moved and new_polys:
            for other, target in moved.items():
                if other == ref:
                    continue
                if math.hypot(target[0] - x, target[1] - y) > self.radius:
                    continue
                other_poly = new_polys[other]
                if not other_poly:
                    continue
                candidates.append((_bbox_of(other_poly), other_poly))

        minx = min(px for px, _ in poly)
        maxx = max(px for px, _ in poly)
        miny = min(py for _, py in poly)
        maxy = max(py for _, py in poly)

        overlaps = 0
        clearance = FAR_MM
        for (omnx, omny, omxx, omxy), other_poly in candidates:
            gx = omnx - maxx if omnx > maxx else (minx - omxx if minx > omxx else 0.0)
            gy = omny - maxy if omny > maxy else (miny - omxy if miny > omxy else 0.0)
            if gx > 0.0 or gy > 0.0:
                # Kutular ayrik: poligonlar da kesin ayrik, SAT'a gerek yok.
                if clearance > 0.0:
                    clearance = min(clearance, math.hypot(gx, gy))
                continue
            # Kutular kesisiyor: burada gercek poligon testi sart. Nadir
            # oldugu icin pahali `geom.distance` yalnizca bu dala duser.
            if geom.overlap(poly, other_poly):
                overlaps += 1
                clearance = 0.0
            elif clearance > 0.0:
                clearance = min(clearance, geom.distance(poly, other_poly))
        return float(overlaps), min(clearance, FAR_MM), float(len(candidates))

    # ------------------------------------------------------------------ oznitelik

    def features(self, ref: str, xyr: tuple[float, float, float]) -> list[float]:
        """Tek bilesenli hamle icin oznitelik vektoru (1 elemanli birlesik)."""
        return self.features_compound(((ref, xyr),))

    def features_compound(self, atoms: Sequence[tuple[str, tuple[float, float, float]]]) -> list[float]:
        """Birlesik hamle icin oznitelik vektoru. `FEATURE_NAMES` ile ayni sirada.

        Ilk atom BIRINCIL sayilir: bilesen kimligi, tur, bulgu ve hamle
        geometrisi bloklari ondan doldurulur. Boylece tek bilesenli hamlelerde
        vektorun ilk 51 degeri sema v1 ile birebir ayni anlami tasir.
        """
        if not self._ready:
            raise RuntimeError("once refresh(placement) cagirin")
        if not atoms:
            raise ValueError("bos birlesik hamle")

        moved: dict[str, tuple[float, float, float]] = {}
        for ref, xyr in atoms:
            if ref not in self._static:
                raise KeyError(f"kartta boyle bir bilesen yok: {ref!r}")
            moved[ref] = (float(xyr[0]), float(xyr[1]), float(xyr[2]))
        new_polys = {r: self._abs_poly(r, t) for r, t in moved.items()}

        primary = atoms[0][0]
        static = self._static[primary]
        x0, y0, rot0 = self._pos[primary]
        x1, y1, rot1 = moved[primary]

        kind_hot = [0.0] * len(KINDS)
        kind_hot[static.kind_index] = 1.0
        severity, ratio = self._finding.get(primary, (0.0, 0.0))

        # Birincil bilesenin netleri: tum tasinanlar dikkate alinarak
        primary_nets = static.nets
        hpwl_before, per_before = self._hpwl(primary_nets, None)
        hpwl_after, per_after = self._hpwl(primary_nets, moved)
        d_hpwl = hpwl_after - hpwl_before
        deltas = [a - b for a, b in zip(per_after, per_before)]
        worst = max(deltas) if deltas else 0.0
        improved = sum(1 for d in deltas if d < -1e-9) / len(deltas) if deltas else 0.0

        ov_b, cl_b, nb_b = self._overlap_state(primary, self._poly[primary], x0, y0)
        ov_a, cl_a, nb_a = self._overlap_state(
            primary, new_polys[primary], x1, y1, moved, new_polys
        )

        pmin_b, pmean_b = self._partner_distances(primary, x0, y0)
        pmin_a, pmean_a = self._partner_distances(primary, x1, y1, moved)

        dist = math.hypot(x1 - x0, y1 - y0)
        edge_b = self._edge_distance(x0, y0)
        edge_a = self._edge_distance(x1, y1)

        # --- birlesik blok: hamlenin TUMUNU ozetler
        dists = []
        for ref, target in moved.items():
            ox, oy, _ = self._pos[ref]
            dists.append(math.hypot(target[0] - ox, target[1] - oy))
        all_nets = self._nets_touched(moved)
        all_before, _ = self._hpwl(all_nets, None)
        all_after, _ = self._hpwl(all_nets, moved)
        d_overlaps_all = 0.0
        clearance_min = FAR_MM
        for ref, target in moved.items():
            b_ov, _, _ = self._overlap_state(ref, self._poly[ref], *self._pos[ref][:2])
            a_ov, a_cl, _ = self._overlap_state(
                ref, new_polys[ref], target[0], target[1], moved, new_polys
            )
            d_overlaps_all += a_ov - b_ov
            clearance_min = min(clearance_min, a_cl)
        # Takas: tam iki bilesen ve ikisi de digerinin eski yerine gidiyor.
        is_swap = 0.0
        if len(atoms) == 2:
            (ra, ta), (rb, tb) = atoms[0], atoms[1]
            pa, pb = self._pos[ra], self._pos[rb]
            if (
                abs(ta[0] - pb[0]) < 1e-6
                and abs(ta[1] - pb[1]) < 1e-6
                and abs(tb[0] - pa[0]) < 1e-6
                and abs(tb[1] - pa[1]) < 1e-6
            ):
                is_swap = 1.0

        vec = [
            *self._board_block,
            *self._eval_block,
            _log1p(static.pad_count),
            _log1p(static.area),
            static.extent,
            _log1p(len(static.nets)),
            *kind_hot,
            1.0 if primary in self._finding else 0.0,
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
            # --- birlesik blok (sema v2)
            _log1p(len(moved)),
            is_swap,
            sum(dists),
            max(dists),
            all_after - all_before,
            (all_after - all_before) / self._diag,
            d_overlaps_all,
            clearance_min,
        ]
        if len(vec) != FEATURE_COUNT:  # sema ile kod ayrisirsa hemen patla
            raise AssertionError(
                f"oznitelik sayisi uyusmuyor: {len(vec)} != {FEATURE_COUNT}"
            )
        return vec

    def features_many(
        self, moves: Sequence[Sequence[tuple[str, tuple[float, float, float]]]]
    ) -> list[list[float]]:
        """Birden fazla BIRLESIK hamle icin vektorler."""
        return [self.features_compound(m) for m in moves]
