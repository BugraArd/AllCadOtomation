"""`.kicad_pcb` okuyucu: bilesenlerin ve pad'lerin FIZIKSEL konumu.

Bu katman sadece okur; karta hicbir sey yazmaz.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from . import geom, sexpr
from .sexpr import as_float, child, children, value

# Kart anahatlarinin cizildigi katman
EDGE_LAYER = "Edge.Cuts"

# Bilesenin kapladigi alanin cizildigi katmanlar (courtyard)
COURTYARD_LAYERS = ("F.CrtYd", "B.CrtYd")


@dataclass
class Pad:
    """Bir footprint pad'i. x/y kart uzerindeki MUTLAK konum (mm)."""

    number: str
    net: str
    x: float
    y: float
    pintype: str = ""
    # Footprint'e gore yerel, DONDURULMEMIS ofset. Bileseni yeniden
    # konumlandirabilmek icin gerekli (yerlestirme motoru bunu kullanir).
    dx: float = 0.0
    dy: float = 0.0

    @property
    def connected(self) -> bool:
        return bool(self.net)


@dataclass
class Component:
    """Karta yerlestirilmis bir bilesen (footprint)."""

    ref: str
    value: str
    footprint_id: str
    x: float
    y: float
    rotation: float
    layer: str
    pads: list[Pad] = field(default_factory=list)
    # Bilesenin kart uzerinde kapladigi gercek alan (donmus, mutlak mm).
    # Dondurulmus bilesenlerde sinir kutusu cok buyuk kalir, bu yuzden
    # cakisma testleri poligon uzerinden yapilir.
    courtyard_poly: list[tuple[float, float]] = field(default_factory=list)
    # Courtyard'in yerel, dondurulmemis hali (yeniden konumlandirma icin)
    courtyard_local: list[tuple[float, float]] = field(default_factory=list)

    def place(self, x: float, y: float, rotation: float | None = None) -> None:
        """Bileseni yeni konuma tasir; pad ve courtyard mutlak konumlarini
        yeniden hesaplar. Yerlestirme motorunun tek yazma noktasidir."""
        self.x = x
        self.y = y
        if rotation is not None:
            self.rotation = rotation
        for pad in self.pads:
            rx, ry = _rotate(pad.dx, pad.dy, self.rotation)
            pad.x, pad.y = x + rx, y + ry
        self.courtyard_poly = [
            (x + rx, y + ry)
            for rx, ry in (_rotate(lx, ly, self.rotation) for lx, ly in self.courtyard_local)
        ]

    @property
    def courtyard(self) -> tuple[float, float, float, float] | None:
        """Courtyard'in sinir kutusu (hizli on eleme ve yogunluk icin)."""
        if not self.courtyard_poly:
            return None
        return geom.bbox(self.courtyard_poly)

    @property
    def area_mm2(self) -> float:
        """Kapladigi alan. Courtyard yoksa pad'lerin sinir kutusuna duser."""
        if self.courtyard_poly:
            return geom.area(self.courtyard_poly)
        box = self.pad_bbox
        if box is None:
            return 0.0
        minx, miny, maxx, maxy = box
        return (maxx - minx) * (maxy - miny)

    @property
    def pad_bbox(self) -> tuple[float, float, float, float] | None:
        if not self.pads:
            return None
        xs = [p.x for p in self.pads]
        ys = [p.y for p in self.pads]
        return min(xs), min(ys), max(xs), max(ys)

    def pad(self, number: str) -> Pad | None:
        for p in self.pads:
            if p.number == number:
                return p
        return None

    def distance_to(self, other: "Component") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


@dataclass
class Board:
    """Okunmus kart."""

    path: Path
    components: list[Component] = field(default_factory=list)
    outline: tuple[float, float, float, float] | None = None  # (minx, miny, maxx, maxy)
    # Dosyada atlanan bozuk parantez sayisi (0 ise dosya saglam)
    parse_warnings: int = 0

    def area_by_side(self) -> dict[str, float]:
        """Bilesenlerin kapladigi alan, kart yuzune gore ayri ayri.

        Cift tarafli kartlarda toplam alan kart alanini asabilir; yogunlugun
        anlamli olmasi icin yuzler ayri hesaplanir.
        """
        totals: dict[str, float] = {}
        for comp in self.components:
            side = "B" if comp.layer.startswith("B.") else "F"
            totals[side] = totals.get(side, 0.0) + comp.area_mm2
        return totals

    def by_ref(self, ref: str) -> Component | None:
        for c in self.components:
            if c.ref == ref:
                return c
        return None

    @property
    def area_mm2(self) -> float | None:
        if not self.outline:
            return None
        minx, miny, maxx, maxy = self.outline
        return (maxx - minx) * (maxy - miny)


def _rotate(dx: float, dy: float, degrees: float) -> tuple[float, float]:
    """KiCad'in donme konvansiyonu (Y ekseni asagi dogru).

    KiCad kaynagindaki RotatePoint ile ayni:
        x' = x*cos + y*sin
        y' = y*cos - x*sin
    """
    if not degrees:
        return dx, dy
    th = math.radians(degrees)
    cos, sin = math.cos(th), math.sin(th)
    return dx * cos + dy * sin, dy * cos - dx * sin


def _pad_net(pad_node) -> str:
    """(net "GND") ve eski (net 5 "GND") bicimlerinin ikisini de destekler."""
    node = child(pad_node, "net")
    if node is None or len(node) < 2:
        return ""
    return node[-1]  # ad her zaman son eleman


def _local_points(node) -> list[tuple[float, float]]:
    """Bir cizim dugumundeki tum koordinatlari toplar (footprint yerel eksende)."""
    pts: list[tuple[float, float]] = []
    for key in ("start", "end", "center", "mid"):
        pt = child(node, key)
        if pt and len(pt) > 2:
            pts.append((as_float(pt[1]), as_float(pt[2])))
    poly = child(node, "pts")
    if poly:
        for xy in children(poly, "xy"):
            if len(xy) > 2:
                pts.append((as_float(xy[1]), as_float(xy[2])))
    return pts


def _read_courtyard_local(node) -> list[tuple[float, float]]:
    """Footprint icindeki courtyard cizimlerinden YEREL poligon.

    Courtyard dosyada tek bir fp_poly olarak da, dort ayri fp_line olarak da
    saklanabilir; ikinci durumda nokta sirasi belirsizdir. Bu yuzden toplanan
    noktalarin dısbukey kabugu alinir - dikdortgen courtyard'lar icin birebir
    dogru, nadir gorulen icbukey olanlarda ise guvenli tarafta kalan bir
    yaklasimdir.

    Not: fp_circle icin sadece merkez ve cevre noktasi alinir, dairesel
    courtyard'larda alan bir miktar kucuk cikabilir.
    """
    pts: list[tuple[float, float]] = []
    for item in node:
        if not isinstance(item, list) or not item:
            continue
        if not str(item[0]).startswith("fp_"):
            continue
        if value(item, "layer") not in COURTYARD_LAYERS:
            continue
        pts.extend(_local_points(item))
    if len(pts) < 3:
        return []
    return geom.convex_hull(pts)


def _read_footprint(node) -> Component | None:
    at = child(node, "at")
    if at is None:
        return None
    fx = as_float(at[1]) if len(at) > 1 else 0.0
    fy = as_float(at[2]) if len(at) > 2 else 0.0
    frot = as_float(at[3]) if len(at) > 3 else 0.0

    ref, val = "", ""
    for prop in children(node, "property"):
        if len(prop) < 3:
            continue
        if prop[1] == "Reference":
            ref = prop[2]
        elif prop[1] == "Value":
            val = prop[2]
    if not ref:
        return None

    comp = Component(
        ref=ref,
        value=val,
        footprint_id=node[1] if len(node) > 1 and isinstance(node[1], str) else "",
        x=fx,
        y=fy,
        rotation=frot,
        layer=value(node, "layer", default="F.Cu"),
    )

    for pnode in children(node, "pad"):
        pat = child(pnode, "at")
        dx = as_float(pat[1]) if pat and len(pat) > 1 else 0.0
        dy = as_float(pat[2]) if pat and len(pat) > 2 else 0.0
        rx, ry = _rotate(dx, dy, frot)
        comp.pads.append(
            Pad(
                number=pnode[1] if len(pnode) > 1 else "",
                net=_pad_net(pnode),
                x=fx + rx,
                y=fy + ry,
                pintype=value(pnode, "pintype", default=""),
                dx=dx,
                dy=dy,
            )
        )

    comp.courtyard_local = _read_courtyard_local(node)
    comp.courtyard_poly = [
        (fx + rx, fy + ry)
        for rx, ry in (_rotate(lx, ly, frot) for lx, ly in comp.courtyard_local)
    ]
    return comp


def _read_outline(root) -> tuple[float, float, float, float] | None:
    """Edge.Cuts uzerindeki cizimlerden kartin sinir kutusu."""
    xs: list[float] = []
    ys: list[float] = []

    for node in root:
        if not isinstance(node, list) or not node:
            continue
        if not str(node[0]).startswith("gr_"):
            continue
        if value(node, "layer") != EDGE_LAYER:
            continue
        for key in ("start", "end", "center", "mid", "at"):
            pt = child(node, key)
            if pt and len(pt) > 2:
                xs.append(as_float(pt[1]))
                ys.append(as_float(pt[2]))
        poly = child(node, "pts")
        if poly:
            for xy in children(poly, "xy"):
                if len(xy) > 2:
                    xs.append(as_float(xy[1]))
                    ys.append(as_float(xy[2]))

    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def read_board(path: str | Path) -> Board:
    """Bir .kicad_pcb dosyasini okur."""
    path = Path(path)
    root, stray = sexpr.parse_with_stats(path.read_text(encoding="utf-8"))

    board = Board(path=path, parse_warnings=stray)
    for node in children(root, "footprint"):
        comp = _read_footprint(node)
        if comp is not None:
            board.components.append(comp)
    board.outline = _read_outline(root)
    return board
