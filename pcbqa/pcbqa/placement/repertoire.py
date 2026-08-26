"""GENIS HAMLE REPERTUARI - takas, kume tasima, bolge sicramasi (Asama 6, Faz A).

## Neden gerekliydi

Asama 5 sunu olctu: ogrenilmis siralayici, skoru artiran hamleyi 2.8 yerine
~1.4 denemede buluyor - ama yerlestirme kalitesi hic degismiyor. Sebep modelin
zayifligi degil, `polish`in **hamle repertuarinin dar olmasi**: yalnizca tek
bilesen oteleme + 90 derece donme. Hicbir tek-bilesen hamlesi skoru artirmaz
olunca arama biter, ve o nokta ulasilabilir en iyinin epey altinda kalir.
Regresyon paketinde 19 kartin 8'inde `auto` hic iyilestirme bulamiyor.

Yani darbogaz "iyilestiren hamleyi bulma hizi" degil, "iyilestiren hamlenin
repertuarda VAR OLMASI". Bu modul repertuari genisletir.

## Ucu de neden BIRLESIK hamle

Takas ve kume tasima ancak birden fazla bilesen AYNI ANDA oynarsa ise yarar.
Ara adim uzerinden gitmek (once A'yi tasi, sonra B'yi) her seferinde cakisma
uretir; hakem ara adimi reddeder ve hamle hic kabul edilmez. Bu yuzden
`base.Compound` tipi eklendi.

## Modelin buradaki gercek isi

Takas O(n^2) aday uretir; 1000 bilesenli bir kartta bunlarin tamamini gercek
hakemle denemek imkansiz (aday basina 2-6 ms). Aday uretimi ucuz, DEGERLENDIRME
pahali. Iste Asama 5'te olculen 65-85x maliyet farki tam burada paraya donusur:
model adaylari eleyip yalnizca en umut vereni hakeme gonderir.

Adalet icin `auto` da ayni sayida aday deneyecek - ama rastgele secilmis.
Ayni degerlendirme butcesi, farkli secim: karsilastirma boylece modelin
katkisini olcer, repertuarin katkisini degil.
"""

from __future__ import annotations

import math
import random
from typing import Iterable

from .base import Compound, Placement, PlacementContext

# Takasta iki bilesenin boyut orani bu carpani asarsa aday uretilmez.
# 0402 kondansatoru ile SOIC-20'yi takas etmek her zaman cakisma uretir;
# aday listesini sismekten kurtarmak eleme kalitesini de artirir.
SWAP_EXTENT_RATIO = 2.0
# Bir bilesen icin en fazla kac takas ortagi denenir
SWAP_MAX_PARTNERS = 20
# Bir kumede en fazla kac bilesen tasinir
CLUSTER_MAX_SIZE = 6
# Kume tasima adimlari (mm)
CLUSTER_STEPS = (2.0, 5.0, 10.0)
# Bolge sicramasinda denenen en bos hucre sayisi
REGION_CANDIDATES = 12
# Komsuluk grafiginde yok sayilan net buyuklugu. GND/VCC gibi raylar her
# bileseni her bilesene baglar; "ayni nete bagli" bilgisi orada anlamsizlasir.
RAIL_NET_SIZE = 12


def _extent(ref: str, ctx: PlacementContext) -> float:
    own = getattr(ctx, "extent_of", None)
    if callable(own):
        return max(float(own(ref)), 0.1)
    comp = ctx.design.component(ref)
    poly = getattr(comp, "courtyard_local", None) if comp else None
    if not poly:
        return 1.0
    xs = [px for px, _ in poly]
    ys = [py for _, py in poly]
    return max(max(xs) - min(xs), max(ys) - min(ys)) / 2.0 or 1.0


class Repertoire:
    """Bir tasarim icin genis hamle ureteci.

    Komsuluk grafigi ve boyutlar bir kez kurulur; yerlesime bagli olan tek sey
    doluluk izgarasi ve o da yalnizca yerlesim degistiginde yeniden hesaplanir.
    """

    def __init__(
        self,
        ctx: PlacementContext,
        rng: random.Random | None = None,
        *,
        include_regions: bool = False,
    ) -> None:
        self.ctx = ctx
        self.rng = rng or random.Random(ctx.seed)
        self.include_regions = include_regions
        self.movable = set(ctx.movable())
        self.extent = {c.ref: _extent(c.ref, ctx) for c in ctx.design.board.components}

        # ref -> ayni (kucuk) nete bagli bilesenler
        self.adjacent: dict[str, set[str]] = {r: set() for r in self.extent}
        design = ctx.design
        for name in design.net_names():
            refs = {p.ref for p in design.pins_on_net(name)}
            if len(refs) < 2 or len(refs) > RAIL_NET_SIZE:
                continue
            for ref in refs:
                if ref in self.adjacent:
                    self.adjacent[ref] |= refs - {ref}

        self._grid_stamp: object = None
        self._occupied: dict[tuple[int, int], int] = {}
        self._cell = max(
            4.0, 2.0 * (sum(self.extent.values()) / max(len(self.extent), 1))
        )

    # ---------------------------------------------------------------- yardimci

    def _centroid(self, ref: str, placement: Placement) -> tuple[float, float] | None:
        """Bilesenin bagli oldugu bilesenlerin agirlik merkezi."""
        pts = [placement[o][:2] for o in self.adjacent.get(ref, ()) if o in placement]
        if not pts:
            return None
        return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)

    def _refresh_grid(self, placement: Placement) -> None:
        stamp = id(placement)
        if stamp == self._grid_stamp:
            return
        self._grid_stamp = stamp
        cell = self._cell
        occupied: dict[tuple[int, int], int] = {}
        for xyr in placement.values():
            key = (int(xyr[0] // cell), int(xyr[1] // cell))
            occupied[key] = occupied.get(key, 0) + 1
        self._occupied = occupied

    def _inside(self, x: float, y: float) -> bool:
        minx, miny, maxx, maxy = self.ctx.outline()
        return minx <= x <= maxx and miny <= y <= maxy

    # ---------------------------------------------------------------- ureticiler

    def swaps(self, ref: str, placement: Placement) -> list[Compound]:
        """Iki bilesenin yer degistirmesi.

        Ortaklar, `ref`in bagli oldugu bilesenlerin agirlik merkezine
        YAKINLIGA gore siralanir - yani "beni ait oldugum yere goturecek"
        takaslar once gelir. `proximity` kurallarinin tamami bu bicimde
        oldugu icin hedefe dogrudan nisan alir. Cesitlilik icin listenin
        sonuna birkac rastgele ortak eklenir.
        """
        if ref in self.ctx.locked or ref not in placement:
            return []
        x, y, rot = placement[ref]
        mine = self.extent[ref]
        anchor = self._centroid(ref, placement) or (x, y)

        partners: list[str] = []
        for other in self.movable:
            if other == ref or other not in placement:
                continue
            theirs = self.extent.get(other, 1.0)
            if not (1.0 / SWAP_EXTENT_RATIO <= theirs / mine <= SWAP_EXTENT_RATIO):
                continue
            partners.append(other)
        if not partners:
            return []

        partners.sort(
            key=lambda o: math.hypot(placement[o][0] - anchor[0], placement[o][1] - anchor[1])
        )
        chosen = partners[: SWAP_MAX_PARTNERS - 4]
        rest = partners[SWAP_MAX_PARTNERS - 4 :]
        if rest:
            chosen += self.rng.sample(rest, min(4, len(rest)))

        out: list[Compound] = []
        for other in chosen:
            ox, oy, orot = placement[other]
            if abs(ox - x) < 1e-9 and abs(oy - y) < 1e-9:
                continue
            # Her bilesen KENDI donusunu korur; footprint'ler farkli oldugu
            # icin donusleri de takas etmek pad'leri saga sola dagitir.
            out.append(((ref, (ox, oy, rot)), (other, (x, y, orot))))
        return out

    def cluster_of(self, ref: str, placement: Placement) -> list[str]:
        """`ref` ve ona ait uydular (decoupling kondansatoru, seri direnc...).

        Uydu olma olcutu: kucuk bir neti `ref` ile paylasiyor VE en yakin
        baglantisi `ref`. Ikinci sart sart - yoksa iki IC arasindaki bir
        direnc iki kumeye birden girer ve tasima ikisini de bozar.
        """
        group = [ref]
        for other in sorted(self.adjacent.get(ref, ())):
            if other not in placement or other in self.ctx.locked or other == ref:
                continue
            if self.extent.get(other, 1.0) > self.extent[ref]:
                continue
            ox, oy, _ = placement[other]
            own = math.hypot(ox - placement[ref][0], oy - placement[ref][1])
            closer = min(
                (
                    math.hypot(placement[p][0] - ox, placement[p][1] - oy)
                    for p in self.adjacent.get(other, ())
                    if p in placement and p != other
                ),
                default=own,
            )
            if own <= closer + 1e-9:
                group.append(other)
            if len(group) >= CLUSTER_MAX_SIZE:
                break
        return group

    def clusters(self, ref: str, placement: Placement) -> list[Compound]:
        """Bir bileseni UYDULARIYLA BIRLIKTE oteler.

        Tek basina tasindiginda IC kendi kondansatorlerinden kopar ve skor
        duser; bu yuzden `polish` boyle hamleleri hic kabul edemiyordu. Grup
        halinde tasindiginda ic mesafeler korunur, yalnizca kumenin kart
        uzerindeki yeri degisir.
        """
        if ref in self.ctx.locked or ref not in placement:
            return []
        group = self.cluster_of(ref, placement)
        if len(group) < 2:
            return []

        out: list[Compound] = []
        targets: list[tuple[float, float]] = []
        for step in CLUSTER_STEPS:
            targets += [(step, 0.0), (-step, 0.0), (0.0, step), (0.0, -step)]
        anchor = self._centroid(ref, placement)
        if anchor is not None:
            ax, ay = anchor
            cx, cy = placement[ref][:2]
            length = math.hypot(ax - cx, ay - cy)
            if length > 1e-6:
                # Kumeyi bagli oldugu yere dogru cek
                for frac in (0.35, 0.7):
                    targets.append(((ax - cx) * frac, (ay - cy) * frac))

        for dx, dy in targets:
            atoms = []
            legal = True
            for member in group:
                mx, my, mrot = placement[member]
                if not self._inside(mx + dx, my + dy):
                    legal = False
                    break
                atoms.append((member, (mx + dx, my + dy, mrot)))
            if legal and atoms:
                out.append(tuple(atoms))
        return out

    def regions(self, ref: str, placement: Placement) -> list[Compound]:
        """Bileseni kartin BOS bir bolgesine sicratir.

        Yerel hamleler bir bileseni ancak komsulari izin verdigi kadar
        oynatabilir; sikisik bir bolgede takilan bilesen oradan hic
        cikamaz. Bu hamle o kilidi acar.
        """
        if ref in self.ctx.locked or ref not in placement:
            return []
        self._refresh_grid(placement)
        minx, miny, maxx, maxy = self.ctx.outline()
        cell = self._cell
        _, _, rot = placement[ref]

        cells: list[tuple[int, tuple[float, float]]] = []
        gx = int((maxx - minx) / cell) + 1
        gy = int((maxy - miny) / cell) + 1
        for i in range(gx):
            for j in range(gy):
                cx = minx + (i + 0.5) * cell
                cy = miny + (j + 0.5) * cell
                if not self._inside(cx, cy):
                    continue
                key = (int(cx // cell), int(cy // cell))
                cells.append((self._occupied.get(key, 0), (cx, cy)))
        if not cells:
            return []
        cells.sort(key=lambda kv: kv[0])
        return [
            ((ref, (cx, cy, rot)),) for _, (cx, cy) in cells[:REGION_CANDIDATES]
        ]

    def wide_batches(
        self, ref: str, placement: Placement
    ) -> list[tuple[str, list[Compound]]]:
        """Genis repertuar adaylari, ureticiye gore AYRI partiler halinde.

        Tek listede birlestirip kesmek olculebilir bir hataydi. Doymus bir
        yerlesimde (dar repertuarin bitirdigi nokta) iyilestiren aday orani:

            kume tasima   %28.3 (pic_programmer) / %20.5 (interf_u)
            takas          %1.8                  /  %3.2
            bolge sicrama  %0.0                  /  %1.7

        Uc ureticinin ciktisini havuzlayip rastgele 12 tanesini denemek, aday
        sayisi bakimindan bolge+takas agir bastigi icin (449+300 vs 318) zengin
        damari suluyordu. Ayri partiler halinde ve ZENGINDEN FAKIRE sirayla
        denenirler.

        `regions` varsayilan olarak KAPALI: iki kartta da pratikte hicbir sey
        bulmadi ama adaylarin ucte birini yiyordu. Ureticinin kendisi duruyor,
        sikisik kartlarda tekrar olculebilir (`include_regions=True`).
        """
        batches = [("kume", self.clusters(ref, placement)),
                   ("takas", self.swaps(ref, placement))]
        if self.include_regions:
            batches.append(("bolge", self.regions(ref, placement)))
        return [(name, moves) for name, moves in batches if moves]

    def wide_moves(self, ref: str, placement: Placement) -> list[Compound]:
        """Tum genis adaylar tek listede (veri toplama ve testler icin)."""
        out: list[Compound] = []
        for _, moves in self.wide_batches(ref, placement):
            out += moves
        return out


# ----------------------------------------------------------- tekil kullanim
#
# Veri toplayici ve testler tek seferlik cagirabilsin diye. Yerel arama
# icinde HER cagride yeni Repertoire kurmayin - komsuluk grafigi O(net x pin).


def swap_moves(ref: str, placement: Placement, ctx: PlacementContext,
               rng: random.Random | None = None) -> list[Compound]:
    return Repertoire(ctx, rng).swaps(ref, placement)


def cluster_moves(ref: str, placement: Placement, ctx: PlacementContext,
                  rng: random.Random | None = None) -> list[Compound]:
    return Repertoire(ctx, rng).clusters(ref, placement)


def region_moves(ref: str, placement: Placement, ctx: PlacementContext,
                 rng: random.Random | None = None) -> list[Compound]:
    return Repertoire(ctx, rng).regions(ref, placement)
