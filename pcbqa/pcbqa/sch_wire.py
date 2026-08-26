"""Sematik baglanti parcalari: tel, etiket, junction (Asama 4f).

Sematikte baglanti GEOMETRIKTIR (bkz. `sch_verify`): iki sey ayni noktaya
degiyorsa baglidir. Bu modul o geometriyi uretir - tel yolu cikarir, etiket
dugumu kurar, gereken yerde junction koyar. Elektriksel dogrulama BURADA
YAPILMAZ; onu netlist kalkani yapar. Buradaki is yalnizca "makul ve temiz
bir yol ciz".

## Iki baglanma yolu

  1. ETIKET - pinin tam ustune bir yerel etiket konur. Ad ayni olan her sey
     ayni aga girer, sayfa icinde mesafe onemsizdir. Uzaktaki bir aga
     baglanmanin en saglam yolu budur; tel cizmek gerekmez.
  2. TEL - iki pin arasina L bicimli (en fazla iki parca) dik yol cizilir.
     Kisa mesafeler ve komsu pinler icin dogru olan budur.

## Yolun secimi

Iki aday vardir: once yatay-sonra dikey, ve tersi. Aralarindan, uzerinden
BASKA bir pin ya da baska bir telin ucu GECMEYENI secilir - cunku KiCad'de
bir telin ortasina degen uc, o telle baglanir. Kesisme (X) sorun degildir:
junction olmadan kesisen teller BAGLANMAZ.

Hicbir aday temiz degilse `None` doner ve cagiran taraf isi etikete birakir.
"""

from __future__ import annotations

import math
import uuid as uuidlib
from dataclasses import dataclass

from .schematic import GRID_MM, SchSymbol, Schematic, place_point

Point = tuple[float, float]
TOL = 1e-6


def _uuid() -> str:
    return f'"{uuidlib.uuid4()}"'


def _q(text: str) -> str:
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _same(a: float, b: float) -> bool:
    return abs(a - b) < TOL


def snap(value: float, grid: float = GRID_MM) -> float:
    return round(round(value / grid) * grid, 4)


# --------------------------------------------------------------------------
# Geometri
# --------------------------------------------------------------------------


def pin_position(x: float, y: float, rotation: float, mirror: str | None,
                 pin_x: float, pin_y: float) -> Point:
    """Yeni bir sembolun pininin SAYFA koordinati.

    Kutuphane uzayindan sayfaya donusum `schematic.place_point` ile ayni -
    tek kaynak; okuma tarafi ile ekleme tarafi ayrisirsa pin noktalari
    sessizce kayar ve baglanti kopar.
    """
    ox, oy = place_point(pin_x, pin_y, rotation, mirror)
    return (round(x + ox, 4), round(y + oy, 4))


def _on_segment(p: Point, a: Point, b: Point, *, strict: bool = True) -> bool:
    """Nokta, dik `a-b` parcasinin uzerinde mi? `strict` uclari disar birakir."""
    (px, py), (ax, ay), (bx, by) = p, a, b
    if _same(ax, bx):
        if not _same(px, ax):
            return False
        lo, hi = min(ay, by), max(ay, by)
    elif _same(ay, by):
        if not _same(py, ay):
            return False
        lo, hi = min(ax, bx), max(ax, bx)
    else:
        return False  # egik parca - bu modul dik yol cizer
    value = py if _same(ax, bx) else px
    if strict:
        return lo + TOL < value < hi - TOL
    return lo - TOL <= value <= hi + TOL


def _segments(points: list[Point]) -> list[tuple[Point, Point]]:
    return [(points[i], points[i + 1]) for i in range(len(points) - 1)
            if points[i] != points[i + 1]]


def candidates(start: Point, end: Point) -> list[list[Point]]:
    """Iki nokta arasindaki dik yol adaylari (once duz, sonra L)."""
    if _same(start[0], end[0]) or _same(start[1], end[1]):
        return [[start, end]]
    return [
        [start, (end[0], start[1]), end],  # once yatay
        [start, (start[0], end[1]), end],  # once dikey
    ]


def blocked_points(schematic: Schematic, sheet_path: str,
                   exclude: set[Point] = frozenset()) -> set[Point]:
    """Uzerinden gecilmemesi gereken noktalar.

    Bunlar mevcut pin noktalari ve tel uclaridir: bir telin ortasina degen
    uc KiCad'de BAGLANIR, yani yolumuz oradan gecerse istemedigimiz bir
    baglanti dogar.
    """
    points: set[Point] = set()
    for (sheet, x, y) in schematic.pin_points():
        if sheet == sheet_path:
            points.add((round(x, 4), round(y, 4)))
    for wire in schematic.wires + schematic.buses:
        if wire.sheet_path != sheet_path:
            continue
        points.add((round(wire.x1, 4), round(wire.y1, 4)))
        points.add((round(wire.x2, 4), round(wire.y2, 4)))
    return {p for p in points if p not in exclude}


def route(
    start: Point,
    end: Point,
    schematic: Schematic,
    sheet_path: str,
) -> list[Point] | None:
    """Iki pin arasinda temiz bir yol; yoksa None.

    "Temiz" = yolun uzerinden (uclar haric) baska bir pin ya da tel ucu
    gecmiyor. Kesisen teller junction olmadan baglanmadigi icin kesisme
    engel sayilmaz.
    """
    avoid = blocked_points(schematic, sheet_path, exclude={start, end})
    for points in candidates(start, end):
        segs = _segments(points)
        if any(_on_segment(p, a, b) for p in avoid for a, b in segs):
            continue
        # Kose noktasi da bos olmali - orada bir pin varsa ona degeriz
        if any(corner in avoid for corner in points[1:-1]):
            continue
        return points
    return None


def junctions_needed(points: list[Point], schematic: Schematic,
                     sheet_path: str) -> list[Point]:
    """Yolun uclari mevcut bir telin ORTASINA denk geliyorsa junction gerekir.

    KiCad kendi cizdiginde de boyle yapar: uc uca eklenen tellerde junction
    yoktur, ortaya degen uclarda vardir.
    """
    out: list[Point] = []
    for end in (points[0], points[-1]):
        for wire in schematic.wires:
            if wire.sheet_path != sheet_path:
                continue
            a, b = (wire.x1, wire.y1), (wire.x2, wire.y2)
            if _on_segment(end, a, b):
                out.append(end)
                break
    return out


# --------------------------------------------------------------------------
# Dugum uretimi
# --------------------------------------------------------------------------


def wire_nodes(points: list[Point]) -> list[list]:
    """Yolu KiCad tel dugumlerine cevirir (parca basina bir `wire`)."""
    nodes = []
    for (x1, y1), (x2, y2) in _segments(points):
        nodes.append([
            "wire",
            ["pts", ["xy", f"{x1:g}", f"{y1:g}"], ["xy", f"{x2:g}", f"{y2:g}"]],
            ["stroke", ["width", "0"], ["type", "default"]],
            ["uuid", _uuid()],
        ])
    return nodes


def label_node(x: float, y: float, name: str, rotation: float = 0.0,
               size: float = 1.27) -> list:
    """Yerel etiket. Pinin tam ustune konursa o pini `name` agina baglar."""
    return [
        "label", _q(name),
        ["at", f"{x:g}", f"{y:g}", f"{rotation:g}"],
        ["effects",
         ["font", ["size", f"{size:g}", f"{size:g}"]],
         ["justify", "left", "bottom"]],
        ["uuid", _uuid()],
    ]


def junction_node(x: float, y: float) -> list:
    return [
        "junction",
        ["at", f"{x:g}", f"{y:g}"],
        ["diameter", "0"],
        ["color", "0", "0", "0", "0"],
        ["uuid", _uuid()],
    ]


def label_rotation(pin_rotation: float) -> float:
    """Etiketi pinin gosterdigi yonde yazdirir (okunakli dursun diye).

    Pin acisi kutuphane uzayindadir: 0 = saga bakan pin. Etiketin dogru
    yonu pinin GOVDEDEN DISARI baktigi yondur.
    """
    return (180.0 + pin_rotation) % 360.0


@dataclass
class Connection:
    """Tek bir baglama istegi: hangi pin, neye."""

    pin: str  # eklenen sembolun pin numarasi
    target: str  # "VCC" (ag adi) veya "R1.2" (baska bir pin)

    @property
    def is_pin_target(self) -> bool:
        """Hedef bir pin mi (`R1.2`), yoksa ag adi mi (`VCC`)?"""
        ref, _, number = self.target.partition(".")
        return bool(number) and not number.startswith(" ") and bool(ref)

    @property
    def target_pin(self) -> tuple[str, str]:
        ref, _, number = self.target.partition(".")
        return ref, number

    @classmethod
    def parse(cls, text: str) -> "Connection":
        pin, sep, target = text.partition("=")
        if not sep or not pin.strip() or not target.strip():
            raise ValueError(
                f"baglanti 'PIN=HEDEF' bicimide olmali (or. 1=VCC ya da 2=R1.1): {text!r}"
            )
        return cls(pin=pin.strip(), target=target.strip())


def existing_pin_point(schematic: Schematic, ref: str, number: str,
                       sheet_path: str) -> Point:
    """Var olan bir sembol pininin sayfa koordinati."""
    for sym in schematic.symbols:
        if sym.ref != ref or sym.sheet_path != sheet_path:
            continue
        pin = sym.pin(number)
        if pin is not None:
            return (round(pin.x, 4), round(pin.y, 4))
    raise KeyError(f"{ref}.{number} bulunamadi (sayfa {sheet_path})")


def pins_on_net(net_of: dict, name: str) -> set:
    """Bir ag adina bugun bagli olan pinler.

    Ad karsilastirmasi hosgorulu: KiCad kok sayfadaki yerel etiketleri
    disariya `/AD` olarak verir, kullanici ise `AD` yazar.
    """
    wanted = name.strip().lstrip("/")
    return {
        pin
        for pin, net in net_of.items()
        if net == name or net.lstrip("/") == wanted
    }
