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
    # Pin ADI ("VIN", "SW", "FB"). KiCad bunu pad'e yaziyor; sematik olmadan da
    # okunabilir. Kural seciciSindeki `function:` alani bunu kullanir.
    function: str = ""
    # Footprint'e gore yerel, DONDURULMEMIS ofset. Bileseni yeniden
    # konumlandirabilmek icin gerekli (yerlestirme motoru bunu kullanir).
    dx: float = 0.0
    dy: float = 0.0
    # Pad bakirinin boyutu (mm). Aciklik kurallari pad'i noktasal kabul
    # edemez: 1.6 mm'lik bir pad, 0.4 mm'lik bir acikliktan buyuktur.
    size_x: float = 0.0
    size_y: float = 0.0
    # Pad bakirinin MUTLAK acisi (bilesen donmesi + pad'in kendi donmesi).
    # Dikdortgen pad'in koselerini dogru yere koymak icin gerekir.
    angle: float = 0.0
    # circle | oval | rect | roundrect | trapezoid | custom
    shape: str = "rect"
    # Pad'in bulundugu BAKIR katmanlar. Bos demet = "tum bakir katmanlar"
    # (delikli pad, dosyada "*.Cu" yazar). SMD pad tek katmandadir.
    #
    # Neden onemli: kart kenari konnektorlerinde on ve arka yuzdeki pad'ler
    # AYNI x/y'dedir ve farkli netlere baglidir (interf_u demosunda BUS1.29 VCC,
    # BUS1.60 /PC-A2). Katman ayrimi olmadan aralarinda 0.000 mm aciklik
    # olculuyordu - gercek bir kartta kisa devre demek olurdu.
    copper_layers: tuple[str, ...] = ()

    @property
    def on_all_layers(self) -> bool:
        return not self.copper_layers

    @property
    def area_mm2(self) -> float:
        """Pad bakirinin alani (mm2). Sekle gore tam hesaplanir."""
        if self.size_x <= 0 or self.size_y <= 0:
            return 0.0
        if self.shape == "circle" or abs(self.size_x - self.size_y) < 1e-9:
            r = min(self.size_x, self.size_y) / 2.0
            return math.pi * r * r
        if self.shape == "oval":
            short = min(self.size_x, self.size_y)
            long_ = max(self.size_x, self.size_y)
            r = short / 2.0
            # stadyum = iki yarim daire + ortadaki dikdortgen
            return math.pi * r * r + (long_ - short) * short
        return self.size_x * self.size_y

    @property
    def radius_mm(self) -> float:
        """Pad'i cevreleyen dairenin yaricapi (kaba olcum icin)."""
        return math.hypot(self.size_x, self.size_y) / 2.0

    def copper_shape(self) -> tuple[list[tuple[float, float]], float]:
        """Pad bakiri: (noktalar, sisme_yaricapi).

        Sonuc, noktalarin `r` kadar sisirilmis halidir. Bu gosterim uc pad
        turunu de TAM ifade eder:

          * circle -> tek nokta + r            (kusursuz)
          * oval   -> uzun eksen boyunca parca + kisa yarim genislik
                      (stadyum sekli - kusursuz)
          * rect   -> donmus dortgen + 0

        Yuvarlak pad'i kareye yuvarlamak olcumu bozuyordu: TO-92'nin 1.27 mm
        kosegen araliktaki 1.3 mm'lik iki yuvarlak pad'i kare kabul edilince
        koseleri 0.03 mm cakisiyor ve saglam bir kart "aciklik ihlali"
        veriyordu. Gercekte aralarinda 0.50 mm var.

        roundrect/trapezoid/custom dortgen kabul edilir - kucuk bir fazla
        tahmin, yani aciklik olcumunde guvenli yon.
        """
        if self.size_x <= 0 or self.size_y <= 0:
            return [(self.x, self.y)], 0.0

        if self.shape == "circle" or abs(self.size_x - self.size_y) < 1e-9:
            return [(self.x, self.y)], min(self.size_x, self.size_y) / 2.0

        if self.shape == "oval":
            short = min(self.size_x, self.size_y)
            span = (max(self.size_x, self.size_y) - short) / 2.0
            dx, dy = (span, 0.0) if self.size_x > self.size_y else (0.0, span)
            rx, ry = _rotate(dx, dy, self.angle)
            return [(self.x - rx, self.y - ry), (self.x + rx, self.y + ry)], short / 2.0

        hx, hy = self.size_x / 2.0, self.size_y / 2.0
        corners = [
            (self.x + rx, self.y + ry)
            for rx, ry in (
                _rotate(dx, dy, self.angle)
                for dx, dy in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))
            )
        ]
        return corners, 0.0

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
class Track:
    """Bakir katmandaki bir iz parcasi (segment veya arc).

    `width` mm cinsinden iz genisligi; akim tasima kurallari bunu olcer.
    Arc'lar icin uzunluk, uc noktalar arasi duz mesafe ile YAKLASIK hesaplanir
    (kural motoru uzunlugu degil genisligi kullandigi icin yeterli).
    """

    net: str
    width: float
    layer: str
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def length_mm(self) -> float:
        return math.hypot(self.x2 - self.x1, self.y2 - self.y1)

    @property
    def is_outer(self) -> bool:
        """Dis katman mi? IPC akim tablolari ic/dis icin farklidir."""
        return self.layer in ("F.Cu", "B.Cu")


@dataclass
class Via:
    """Bir via. `size` bakir pad capi, `drill` delik capi (mm)."""

    net: str
    x: float
    y: float
    size: float
    drill: float
    layers: tuple[str, ...] = ()


@dataclass
class ZoneFill:
    """Bir zone'un TEK KATMANDAKI doldurulmus bakiri."""

    layer: str
    points: list[tuple[float, float]] = field(default_factory=list)

    @property
    def area_mm2(self) -> float:
        return geom.area(self.points)


@dataclass
class Zone:
    """Bakir dokum alani (poligon).

    Iki poligon vardir ve karistirilmamalidir:
      * `outline` - kullanicinin CIZDIGI sinir
      * `fills`   - KiCad'in gercekten doldurdugu bakir (ada basina bir poligon,
                    katman basina ayri)

    Alan olcumu `fills` varsa ondan gelir: aciklik ve termal koprulerden sonra
    kalan GERCEK bakir odur. Kart hic doldurulmamissa `outline`a duser ve bu
    FAZLA tahmindir - bu yuzden `filled` bayragi ayrica tasinir.
    """

    net: str
    layers: tuple[str, ...] = ()
    outline: list[tuple[float, float]] = field(default_factory=list)
    fills: list[ZoneFill] = field(default_factory=list)

    @property
    def filled(self) -> bool:
        return bool(self.fills)

    @property
    def area_mm2(self) -> float:
        """Bakir alani (mm2).

        Doldurulmus poligonlarda delikler, poligonun kendisine giren ince
        "kesik" yollarla temsil edilir; shoelace bu gidis-donusleri birbirini
        goturdugu icin alan yine dogru cikar (yaklasik, ~%1).
        """
        if self.fills:
            return sum(fill.area_mm2 for fill in self.fills)
        return geom.area(self.outline)

    def area_on(self, layer: str) -> float:
        """Tek bir katmandaki bakir alani."""
        if self.fills:
            return sum(f.area_mm2 for f in self.fills if f.layer == layer)
        return geom.area(self.outline) if layer in self.layers else 0.0


@dataclass
class Board:
    """Okunmus kart."""

    path: Path
    components: list[Component] = field(default_factory=list)
    outline: tuple[float, float, float, float] | None = None  # (minx, miny, maxx, maxy)
    # Yonlendirilmis bakir. Bos liste "kart henuz yonlendirilmemis" demektir;
    # iz genisligi kurallari o durumda sessizce atlanir (bkz. rules.py).
    tracks: list[Track] = field(default_factory=list)
    vias: list[Via] = field(default_factory=list)
    # Bakir dokum alanlari. Sicak dongu alani, SW bakir alani ve termal bakir
    # alani kurallarinin on kosulu (bkz. docs/tasarim-kurallari/).
    zones: list[Zone] = field(default_factory=list)
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

    def copper_area_mm2(
        self,
        net: str,
        layer: str | None = None,
        sources: tuple[str, ...] = ("zone", "track", "pad"),
    ) -> float:
        """Bir netin toplam bakir alani (mm2).

        UYARI - bu bir FAZLA TAHMINDIR: ustuste binen bakir (pad'in uzerinden
        gecen iz, dokumun altindaki pad) iki kez sayilir. Poligon birlesimi
        hesaplamak cok daha pahali ve bu olcumun kullanildigi kurallar icin
        gereksiz.

        Hatanin YONU kural tipine gore degisir, ve bu onemlidir:
          * `max_mm2` (or. SW bakir alani <= 100 mm2) -> fazla tahmin GUVENLI
            taraftadir; en fazla yanlis alarm verir.
          * `min_mm2` (or. termal bakir alani) -> fazla tahmin GUVENSIZ taraftadir;
            yetersiz bakiri yeterli gosterebilir. O kurallarda pay birakin.
        """
        total = 0.0
        if "zone" in sources:
            for zone in self.zones:
                if zone.net != net:
                    continue
                total += zone.area_on(layer) if layer else zone.area_mm2
        if "track" in sources:
            for track in self.tracks:
                if track.net != net:
                    continue
                if layer and track.layer != layer:
                    continue
                total += track.length_mm * track.width
        if "pad" in sources:
            for comp in self.components:
                for pad in comp.pads:
                    if pad.net != net:
                        continue
                    if layer and not pad.on_all_layers and layer not in pad.copper_layers:
                        continue
                    total += pad.area_mm2
        return total

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


def _pad_copper_layers(pad_node) -> tuple[str, ...]:
    """Pad'in bakir katmanlari. Bos demet = tum bakir katmanlar.

    Dosyada delikli pad "*.Cu", SMD pad "F.Cu" / "B.Cu" yazar. Maske/pasta
    katmanlari elenir; aciklik olcumunu yalnizca bakir ilgilendirir.
    """
    node = child(pad_node, "layers")
    if node is None:
        return ()
    layers = [str(x) for x in node[1:]]
    if any(layer == "*.Cu" for layer in layers):
        return ()
    return tuple(layer for layer in layers if layer.endswith(".Cu"))


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
        psize = child(pnode, "size")
        comp.pads.append(
            Pad(
                number=pnode[1] if len(pnode) > 1 else "",
                net=_pad_net(pnode),
                x=fx + rx,
                y=fy + ry,
                pintype=value(pnode, "pintype", default=""),
                function=value(pnode, "pinfunction", default="") or "",
                dx=dx,
                dy=dy,
                size_x=as_float(psize[1]) if psize and len(psize) > 1 else 0.0,
                size_y=as_float(psize[2]) if psize and len(psize) > 2 else 0.0,
                angle=frot + (as_float(pat[3]) if pat and len(pat) > 3 else 0.0),
                shape=str(pnode[3]) if len(pnode) > 3 and isinstance(pnode[3], str) else "rect",
                copper_layers=_pad_copper_layers(pnode),
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


def _node_net(node) -> str:
    """(net "VCC") ve eski (net 5 "VCC") bicimlerinin ikisi de: ad son elemandir."""
    n = child(node, "net")
    if n is None or len(n) < 2:
        return ""
    return str(n[-1])


def _read_tracks(root) -> list[Track]:
    """Ust duzey (segment ...) ve (arc ...) dugumleri.

    KiCad bakir izleri kart kokunde tutar (footprint icindekiler degil).
    Arc'ta orta nokta da vardir, ama genislik kurallari icin uc noktalar yeter.
    """
    tracks: list[Track] = []
    for name in ("segment", "arc"):
        for node in children(root, name):
            start = child(node, "start")
            end = child(node, "end")
            width = child(node, "width")
            if start is None or end is None or width is None:
                continue
            if len(start) < 3 or len(end) < 3:
                continue
            tracks.append(
                Track(
                    net=_node_net(node),
                    width=as_float(width[1]) if len(width) > 1 else 0.0,
                    layer=str(value(node, "layer", default="") or ""),
                    x1=as_float(start[1]),
                    y1=as_float(start[2]),
                    x2=as_float(end[1]),
                    y2=as_float(end[2]),
                )
            )
    return tracks


def _read_vias(root) -> list[Via]:
    vias: list[Via] = []
    for node in children(root, "via"):
        at = child(node, "at")
        if at is None or len(at) < 3:
            continue
        size = child(node, "size")
        drill = child(node, "drill")
        layers_node = child(node, "layers")
        layers = tuple(str(x) for x in layers_node[1:]) if layers_node else ()
        vias.append(
            Via(
                net=_node_net(node),
                x=as_float(at[1]),
                y=as_float(at[2]),
                size=as_float(size[1]) if size and len(size) > 1 else 0.0,
                drill=as_float(drill[1]) if drill and len(drill) > 1 else 0.0,
                layers=layers,
            )
        )
    return vias


def _points_of(node) -> list[tuple[float, float]]:
    """Bir (pts (xy ..) (xy ..)) dugumundeki noktalar."""
    pts = child(node, "pts")
    if pts is None:
        return []
    return [
        (as_float(xy[1]), as_float(xy[2])) for xy in children(pts, "xy") if len(xy) > 2
    ]


def _zone_layers(node) -> tuple[str, ...]:
    """Zone'un katmanlari. Dosyada tekil (layer "F.Cu") ya da cogul
    (layers "In1.Cu" "In2.Cu") olarak yazilabilir; ikisi de gecerli."""
    plural = child(node, "layers")
    if plural is not None:
        return tuple(str(x) for x in plural[1:])
    single = value(node, "layer", default=None)
    return (str(single),) if single else ()


def _read_zones(root) -> list[Zone]:
    zones: list[Zone] = []
    for node in children(root, "zone"):
        # Zone'da net ADI ayri bir alanda: (net 1) (net_name "GND")
        net = value(node, "net_name", default="") or ""
        zone = Zone(
            net=str(net),
            layers=_zone_layers(node),
            outline=_points_of(child(node, "polygon") or []),
        )
        for fill in children(node, "filled_polygon"):
            points = _points_of(fill)
            if len(points) >= 3:
                zone.fills.append(
                    ZoneFill(layer=str(value(fill, "layer", default="") or ""), points=points)
                )
        zones.append(zone)
    return zones


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
    board.tracks = _read_tracks(root)
    board.vias = _read_vias(root)
    board.zones = _read_zones(root)
    return board
