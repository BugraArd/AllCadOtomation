"""Sematik okuyucu (Asama 4a) - .kicad_sch dosyalarini veri modeline cevirir.

SALT-OKUNUR. Bu modul hicbir dosyaya yazmaz.

KiCad 10'da IPC API'si yalnizca PCB editorunde var, sematikte yok. Ama
sematigi okumak icin IPC'ye gerek yok: .kicad_sch da s-expression, ve
`sexpr.py` onu zaten sorunsuz okuyor (pic_programmer uzerinde 0 bozuk
parantez, agac birebir korunuyor). Yani sematik okuma KiCad 11'i beklemez.

## Pin konumu nasil bulunur (deneysel olarak dogrulandi)

Kutuphane sembolunde pin konumu yereldir ve kutuphane uzayinda Y yukari
bakar; sayfada ise Y asagi bakar. Sembol ayrica dondurulmus ve aynalanmis
olabilir. Dogru donusum, KiCad'in 19 demo projesindeki TUM sematiklerde
(2445 ayirt edici pin) tel uclari ve junction'larla karsilastirilarak
secildi:

    ofset = (px*cos - py*sin,  -px*sin - py*cos)      %93.5 ortusme
                                                       (rakip hipotez: %37.8)

Ayna ROTASYONDAN SONRA uygulanir (892 aynali sembol, 352 ayirt edici pin):

    mirror x -> (ox, -oy)      %94.9 ortusme
    mirror y -> (-ox, oy)      (ters sira: %27.0)

Okuyucu 19 demo projesinin tamaminda (17.088 pin) dogrulandi: pinlerin
%98.7'si bir capaya oturuyor, projelerin cogunda %100. Bozuk parantez: 0.

Capa yalnizca tel ucu DEGILDIR. Bir pin sunlardan herhangi birine oturabilir:
tel ucu, junction, no_connect, etiket, veya DOGRUDAN baska bir sembolun pini.
Sonuncusu sik: guc sembolleri (GND, VCC) cogu zaman telsiz, dogrudan IC
pinine yapisir. Dar bir olcut bunlari 'kaciran pin' sanar - pic_programmer'da
oyle olmus, gercek oran %79 degil %100 cikmisti.

## Hiyerarsi

Kok dosya `sheet` dugumleri icerir; her biri `Sheetfile` ile baska bir
.kicad_sch'e isaret eder. Okuyucu bunlari ozyinelemeli takip eder ve her
ogeye ait oldugu sayfa yolunu (`/`, `/pic_sockets`, ...) isler. Dongulere
karsi ziyaret edilen dosyalar takip edilir.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from .sexpr import as_float, child, children, head, parse_with_stats

# Sematik izgarasi - KiCad baglantiyi bu adimda kurar
GRID_MM = 1.27

# Guc sembolleri (GND, VCC...) gercek bilesen degildir
POWER_PREFIX = "power:"


def _num(node, index: int, default: float = 0.0) -> float:
    if not isinstance(node, list) or len(node) <= index:
        return default
    return as_float(node[index], default)


def _atom(node, index: int = 1, default: str = "") -> str:
    if not isinstance(node, list) or len(node) <= index:
        return default
    value = node[index]
    return default if isinstance(value, list) else str(value)


def _flag(node, name: str, default: bool = False) -> bool:
    c = child(node, name)
    if c is None or len(c) < 2:
        return default
    return _atom(c) == "yes"


def _on_grid(value: float, grid: float, tol: float) -> bool:
    return abs(value / grid - round(value / grid)) < tol


@dataclass
class SchPin:
    """Sayfa koordinatina cozulmus bir sembol pini."""

    number: str
    name: str
    x: float
    y: float
    electrical: str = "unspecified"
    length: float = 0.0

    def on_grid(self, grid: float = GRID_MM, tol: float = 1e-6) -> bool:
        return _on_grid(self.x, grid, tol) and _on_grid(self.y, grid, tol)


@dataclass
class SchSymbol:
    """Sayfaya yerlestirilmis bir sembol ornegi."""

    ref: str
    lib_id: str
    x: float
    y: float
    rotation: float = 0.0
    mirror: str | None = None
    unit: int = 1
    body_style: int = 1
    uuid: str = ""
    value: str = ""
    footprint: str = ""
    dnp: bool = False
    in_bom: bool = True
    sheet_path: str = "/"
    properties: dict[str, str] = field(default_factory=dict)
    pins: list[SchPin] = field(default_factory=list)
    # Sayfa koordinatinda govde sinir kutusu (minx, miny, maxx, maxy)
    bbox: tuple[float, float, float, float] | None = None

    @property
    def is_power(self) -> bool:
        """Guc sembolu mu? (GND, VCC...)"""
        return self.lib_id.startswith(POWER_PREFIX) or self.ref.startswith("#PWR")

    @property
    def is_virtual(self) -> bool:
        """Gercek bir bilesen degil.

        KiCad sanal sembolleri `#` ile baslayan referans alir: `#PWR` (guc
        sembolleri), `#FLG` (PWR_FLAG) gibi. Bunlarin footprint'i olmaz ve
        BOM'a girmezler, dolayisiyla bilesen sayimlarindan ve footprint
        kontrollerinden dislanmalidirlar.
        """
        return self.ref.startswith("#") or self.is_power

    @property
    def key(self) -> str:
        """Hiyerarside benzersiz anahtar."""
        return self.ref if self.sheet_path == "/" else f"{self.sheet_path}:{self.ref}"

    def pin(self, number: str) -> SchPin | None:
        return next((p for p in self.pins if p.number == number), None)

    def on_grid(self, grid: float = GRID_MM, tol: float = 1e-6) -> bool:
        return _on_grid(self.x, grid, tol) and _on_grid(self.y, grid, tol)


@dataclass
class SchWire:
    x1: float
    y1: float
    x2: float
    y2: float
    uuid: str = ""
    sheet_path: str = "/"

    @property
    def endpoints(self) -> tuple[tuple[float, float], tuple[float, float]]:
        return (self.x1, self.y1), (self.x2, self.y2)

    @property
    def length(self) -> float:
        return math.hypot(self.x2 - self.x1, self.y2 - self.y1)


@dataclass
class SchPoint:
    """Junction / no_connect gibi tek noktali ogeler."""

    x: float
    y: float
    kind: str = "junction"
    sheet_path: str = "/"


@dataclass
class SchLabel:
    text: str
    x: float
    y: float
    rotation: float = 0.0
    kind: str = "local"  # local | global | hierarchical
    sheet_path: str = "/"


@dataclass
class SchSheetRef:
    """Bir dosyadaki alt sayfa kutusu."""

    name: str
    filename: str
    x: float
    y: float
    width: float
    height: float
    uuid: str = ""
    parent_path: str = "/"
    path: str = "/"
    missing: bool = False


@dataclass
class Schematic:
    """Bir sematik hiyerarsisinin tamami."""

    root_path: Path
    version: str = ""
    paper: str = ""
    uuid: str = ""
    symbols: list[SchSymbol] = field(default_factory=list)
    wires: list[SchWire] = field(default_factory=list)
    junctions: list[SchPoint] = field(default_factory=list)
    no_connects: list[SchPoint] = field(default_factory=list)
    labels: list[SchLabel] = field(default_factory=list)
    sheets: list[SchSheetRef] = field(default_factory=list)
    files: list[Path] = field(default_factory=list)
    # Toleransli okuyucunun atladigi bozuk parantez sayisi (0 olmali)
    stray_parens: int = 0

    @property
    def real_symbols(self) -> list[SchSymbol]:
        """Sanal semboller (#PWR, #FLG...) haric gercek bilesenler."""
        return [s for s in self.symbols if not s.is_virtual]

    def by_ref(self, ref: str) -> SchSymbol | None:
        return next((s for s in self.symbols if s.ref == ref), None)

    def on_sheet(self, sheet_path: str) -> list[SchSymbol]:
        return [s for s in self.symbols if s.sheet_path == sheet_path]

    def sheet_paths(self) -> list[str]:
        seen: list[str] = []
        for s in self.symbols:
            if s.sheet_path not in seen:
                seen.append(s.sheet_path)
        return seen or ["/"]

    def endpoint_counts(self) -> dict[tuple[str, float, float], int]:
        """Tel uclarinin sayfa bazinda sayim tablosu."""
        counts: dict[tuple[str, float, float], int] = {}
        for w in self.wires:
            for px, py in w.endpoints:
                key = (w.sheet_path, round(px, 3), round(py, 3))
                counts[key] = counts.get(key, 0) + 1
        return counts

    def pin_points(self) -> dict[tuple[str, float, float], list[tuple[SchSymbol, SchPin]]]:
        """Sayfa bazinda pin konumu -> (sembol, pin) listesi."""
        out: dict[tuple[str, float, float], list[tuple[SchSymbol, SchPin]]] = {}
        for sym in self.symbols:
            for pin in sym.pins:
                key = (sym.sheet_path, round(pin.x, 3), round(pin.y, 3))
                out.setdefault(key, []).append((sym, pin))
        return out

    def stats(self) -> dict:
        return {
            "dosya": len(self.files),
            "sayfa": len(self.sheet_paths()),
            "sembol": len(self.symbols),
            "gercek_bilesen": len(self.real_symbols),
            "sanal_sembol": len(self.symbols) - len(self.real_symbols),
            "tel": len(self.wires),
            "junction": len(self.junctions),
            "no_connect": len(self.no_connects),
            "etiket": len(self.labels),
            "alt_sayfa": len(self.sheets),
        }


# --------------------------------------------------------------------------
# Kutuphane sembolu geometrisi
# --------------------------------------------------------------------------


def _unit_matches(unit_name: str, unit: int, body_style: int) -> bool:
    """`R_1_1` gibi alt birim adini ornek birimiyle eslestirir.

    Bicim `<ad>_<unit>_<body_style>`; unit 0 tum birimler icin ortak
    grafiktir, body_style 0 da tum stiller icin ortaktir.
    """
    parts = unit_name.rsplit("_", 2)
    if len(parts) != 3:
        return True
    try:
        u, b = int(parts[1]), int(parts[2])
    except ValueError:
        return True
    return u in (0, unit) and b in (0, body_style)


def _lib_pins(lib_symbol, unit: int, body_style: int):
    """Kutuphane sembolunden (px, py, numara, ad, elektriksel_tip, uzunluk)."""
    out = []
    for sub in children(lib_symbol, "symbol"):
        if not _unit_matches(_atom(sub), unit, body_style):
            continue
        for p in children(sub, "pin"):
            at = child(p, "at")
            if at is None:
                continue
            out.append(
                (
                    _num(at, 1),
                    _num(at, 2),
                    _atom(child(p, "number")),
                    _atom(child(p, "name")),
                    _atom(p, 1, "unspecified"),
                    _num(child(p, "length"), 1),
                )
            )
    return out


def _lib_extent(lib_symbol, unit: int, body_style: int):
    """Kutuphane uzayinda govde sinir kutusu (minx, miny, maxx, maxy)."""
    xs: list[float] = []
    ys: list[float] = []
    for sub in children(lib_symbol, "symbol"):
        if not _unit_matches(_atom(sub), unit, body_style):
            continue
        for shape in sub:
            if not isinstance(shape, list) or not shape:
                continue
            tag = shape[0]
            if tag == "rectangle":
                for corner in ("start", "end"):
                    node = child(shape, corner)
                    if node:
                        xs.append(_num(node, 1))
                        ys.append(_num(node, 2))
            elif tag in ("polyline", "bezier"):
                pts = child(shape, "pts")
                for xy in children(pts, "xy") if pts else []:
                    xs.append(_num(xy, 1))
                    ys.append(_num(xy, 2))
            elif tag == "circle":
                center = child(shape, "center")
                radius = _num(child(shape, "radius"), 1)
                if center:
                    cx, cy = _num(center, 1), _num(center, 2)
                    xs.extend([cx - radius, cx + radius])
                    ys.extend([cy - radius, cy + radius])
            elif tag == "arc":
                for corner in ("start", "mid", "end"):
                    node = child(shape, corner)
                    if node:
                        xs.append(_num(node, 1))
                        ys.append(_num(node, 2))
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def place_point(px: float, py: float, rotation: float, mirror: str | None) -> tuple[float, float]:
    """Kutuphane noktasini sayfa ofsetine cevirir.

    Modul basligindaki deneysel olarak dogrulanmis donusum. Sira onemli:
    once rotasyon + Y cevirme, SONRA ayna.
    """
    r = math.radians(rotation)
    cos, sin = round(math.cos(r), 12), round(math.sin(r), 12)
    ox = px * cos - py * sin
    oy = -px * sin - py * cos
    if mirror == "x":
        oy = -oy
    elif mirror == "y":
        ox = -ox
    return ox, oy


# --------------------------------------------------------------------------
# Dosya okuma
# --------------------------------------------------------------------------


def _properties(node) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in children(node, "property"):
        if len(p) > 2 and not isinstance(p[1], list) and not isinstance(p[2], list):
            out[str(p[1])] = str(p[2])
    return out


def _read_symbol(node, lib_index: dict, sheet_path: str) -> SchSymbol | None:
    lib_id_node = child(node, "lib_id")
    at = child(node, "at")
    if lib_id_node is None or at is None:
        return None

    lib_id = _atom(lib_id_node)
    props = _properties(node)
    mirror = _atom(child(node, "mirror")) or None
    unit = int(_num(child(node, "unit"), 1, 1))
    body_style = int(_num(child(node, "body_style"), 1, 1))
    x, y, rotation = _num(at, 1), _num(at, 2), _num(at, 3)

    sym = SchSymbol(
        ref=props.get("Reference", ""),
        lib_id=lib_id,
        x=x,
        y=y,
        rotation=rotation,
        mirror=mirror,
        unit=unit,
        body_style=body_style,
        uuid=_atom(child(node, "uuid")),
        value=props.get("Value", ""),
        footprint=props.get("Footprint", ""),
        dnp=_flag(node, "dnp"),
        in_bom=_flag(node, "in_bom", default=True),
        sheet_path=sheet_path,
        properties=props,
    )

    lib_symbol = lib_index.get(lib_id)
    if lib_symbol is None:
        return sym

    for px, py, number, name, electrical, length in _lib_pins(lib_symbol, unit, body_style):
        ox, oy = place_point(px, py, rotation, mirror)
        sym.pins.append(
            SchPin(
                number=number,
                name=name,
                x=round(x + ox, 4),
                y=round(y + oy, 4),
                electrical=electrical,
                length=length,
            )
        )

    extent = _lib_extent(lib_symbol, unit, body_style)
    if extent:
        corners = [
            place_point(cx, cy, rotation, mirror)
            for cx, cy in (
                (extent[0], extent[1]),
                (extent[0], extent[3]),
                (extent[2], extent[1]),
                (extent[2], extent[3]),
            )
        ]
        xs = [x + c[0] for c in corners]
        ys = [y + c[1] for c in corners]
        sym.bbox = (round(min(xs), 4), round(min(ys), 4), round(max(xs), 4), round(max(ys), 4))
    return sym


_LABEL_KINDS = {
    "label": "local",
    "global_label": "global",
    "hierarchical_label": "hierarchical",
}


def _read_file(path: Path, sheet_path: str, schematic: Schematic, visited: set[Path]) -> None:
    """Tek bir .kicad_sch dosyasini okur ve alt sayfalarina iner."""
    schematic.files.append(path)

    root, stray = parse_with_stats(path.read_text(encoding="utf-8", errors="replace"))
    schematic.stray_parens += stray

    if sheet_path == "/":
        schematic.version = _atom(child(root, "version"))
        schematic.paper = _atom(child(root, "paper"))
        schematic.uuid = _atom(child(root, "uuid"))

    lib_index = {}
    lib_node = child(root, "lib_symbols")
    for ls in children(lib_node, "symbol") if lib_node else []:
        name = _atom(ls)
        if name:
            lib_index[name] = ls

    for node in root:
        if not isinstance(node, list) or not node:
            continue
        tag = head(node)

        if tag == "symbol":
            sym = _read_symbol(node, lib_index, sheet_path)
            if sym is not None:
                schematic.symbols.append(sym)

        elif tag == "wire":
            pts = child(node, "pts")
            xys = list(children(pts, "xy")) if pts else []
            if len(xys) >= 2:
                schematic.wires.append(
                    SchWire(
                        x1=_num(xys[0], 1),
                        y1=_num(xys[0], 2),
                        x2=_num(xys[-1], 1),
                        y2=_num(xys[-1], 2),
                        uuid=_atom(child(node, "uuid")),
                        sheet_path=sheet_path,
                    )
                )

        elif tag in ("junction", "no_connect"):
            at = child(node, "at")
            if at:
                point = SchPoint(x=_num(at, 1), y=_num(at, 2), kind=tag, sheet_path=sheet_path)
                target = schematic.junctions if tag == "junction" else schematic.no_connects
                target.append(point)

        elif tag in _LABEL_KINDS:
            at = child(node, "at")
            text = _atom(node)
            if at and text:
                schematic.labels.append(
                    SchLabel(
                        text=text,
                        x=_num(at, 1),
                        y=_num(at, 2),
                        rotation=_num(at, 3),
                        kind=_LABEL_KINDS[tag],
                        sheet_path=sheet_path,
                    )
                )

        elif tag == "sheet":
            props = _properties(node)
            at, size = child(node, "at"), child(node, "size")
            name = props.get("Sheetname", "")
            filename = props.get("Sheetfile", "")
            child_path = f"{sheet_path.rstrip('/')}/{name}" if name else sheet_path
            target = (path.parent / filename) if filename else None
            schematic.sheets.append(
                SchSheetRef(
                    name=name,
                    filename=filename,
                    x=_num(at, 1),
                    y=_num(at, 2),
                    width=_num(size, 1),
                    height=_num(size, 2),
                    uuid=_atom(child(node, "uuid")),
                    parent_path=sheet_path,
                    path=child_path,
                    missing=not (target and target.is_file()),
                )
            )
            if target and target.is_file() and target.resolve() not in visited:
                visited.add(target.resolve())
                _read_file(target, child_path, schematic, visited)


def read_schematic(path: Path | str) -> Schematic:
    """Bir .kicad_sch dosyasini (ve tum alt sayfalarini) okur.

    Klasor verilirse icindeki .kicad_sch secilir; birden fazlaysa klasor
    adiyla eslesen tercih edilir.
    """
    path = Path(path)
    if path.is_dir():
        candidates = sorted(path.glob("*.kicad_sch"))
        if not candidates:
            raise FileNotFoundError(f"{path} altinda .kicad_sch yok")
        named = [c for c in candidates if c.stem == path.name]
        path = named[0] if named else candidates[0]
    if not path.is_file():
        raise FileNotFoundError(f"sematik bulunamadi: {path}")

    schematic = Schematic(root_path=path)
    _read_file(path, "/", schematic, {path.resolve()})
    return schematic
