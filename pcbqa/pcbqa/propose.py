"""Sematikten baglanti ONERISI cikarir - "bunlar nasil baglanmali" sorusu.

`intent.py` bunu BEYAN EDILMIS bir plandan yapar: sablon "su pin su aga gider"
der. Bu modul ise sayfada duran, hakkinda hicbir sey beyan edilmemis sembollere
bakip oneri uretir.

## Neyi kanit sayiyoruz

Dosyada niyet yazmiyor - ama YERLESIM yaziyor. Kullanici iki pini tam ayni
hizaya koyduysa bu bir tesaduf degil; guc sembolunu iki parcanin ortasina
ustten koyduysa o da degil. Bu modul yalnizca bu tur kanitlara dayanir:

  1. HIZALAMA  - iki bos pin ayni x ya da ayni y'de ve aralarinda engel yok.
                 Ikisi de birbirinin EN YAKIN hizali komsusu olmali; boylece
                 "hangisini sectin" diye bir tercih yapmak gerekmiyor.
  2. GUC INISI - bir guc sembolunun bos pini, onerilen (ya da var olan) bir
                 tel parcasinin UZERINE dik iniyor ve inis noktasi parcanin
                 ORTASINA dusuyor.

## Neyi kanit saymiyoruz

Geri kalan her sey. Sayfada bir direnc ve bir kondansator varsa bunlarin
seri mi paralel mi olacagi DOSYADA YAZMIYOR - ikisi de gecerli okuma. Boyle
bir durumda bu modul oneri uretmez ve nedenini soyler. Kaynagi olmayan esik
yazmadigimiz gibi, kaniti olmayan devre de cizmiyoruz.

Her onerinin yaninda GEREKCESI durur; cagiran taraf (ve kullanici) oneriyi
gerekcesiyle birlikte gorur.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import sch_wire
from .schematic import Schematic

Point = tuple[float, float]
TOL = 1e-6


@dataclass
class PinRef:
    """Sayfadaki tek bir pin."""

    ref: str
    number: str
    point: Point
    is_power: bool = False

    def __str__(self) -> str:
        return f"{self.ref}.{self.number}"


@dataclass
class Proposal:
    """Bir baglanti onerisi ve NEDEN onerildigi."""

    kind: str                       # "hizalama" | "guc-inisi"
    pins: list[PinRef] = field(default_factory=list)
    path: list[Point] = field(default_factory=list)
    reason: str = ""

    def __str__(self) -> str:
        uclar = " - ".join(str(p) for p in self.pins) or "(rayin ustune)"
        return f"{self.kind:<10} {uclar}  [{self.reason}]"


# --------------------------------------------------------------------------
# Sayfanin durumu
# --------------------------------------------------------------------------


def occupied_points(schematic: Schematic, sheet_path: str) -> set[Point]:
    """Uzerinde zaten bir baglanti ogesi olan noktalar."""
    points: set[Point] = set()
    for wire in schematic.wires + schematic.buses:
        if wire.sheet_path != sheet_path:
            continue
        for px, py in wire.endpoints:
            points.add((round(px, 4), round(py, 4)))
    for group in (schematic.junctions, schematic.no_connects, schematic.bus_entries):
        for point in group:
            if getattr(point, "sheet_path", "/") == sheet_path:
                points.add((round(point.x, 4), round(point.y, 4)))
    for label in schematic.labels:
        if getattr(label, "sheet_path", "/") == sheet_path:
            points.add((round(label.x, 4), round(label.y, 4)))
    return points


def _touched_by_a_wire(point: Point, schematic: Schematic, sheet_path: str) -> bool:
    """Nokta bir telin UZERINDE mi (ucu dahil)?"""
    for wire in schematic.wires + schematic.buses:
        if wire.sheet_path != sheet_path:
            continue
        a, b = wire.endpoints
        if sch_wire._on_segment(point, a, b, strict=False):
            return True
    return False


def free_pins(schematic: Schematic, sheet_path: str = "/") -> list[PinRef]:
    """Hicbir seye baglanmamis pinler - onerinin konusu yalnizca bunlar.

    Zaten bagli bir pini yeniden baglamak var olan agi degistirir; bu modul
    MEVCUT baglantiya asla dokunmaz.
    """
    busy = occupied_points(schematic, sheet_path)
    out: list[PinRef] = []
    for sym in schematic.symbols:
        if sym.sheet_path != sheet_path:
            continue
        for pin in sym.pins:
            point = (round(pin.x, 4), round(pin.y, 4))
            if point in busy or _touched_by_a_wire(point, schematic, sheet_path):
                continue
            out.append(PinRef(sym.ref, pin.number, point, sym.is_power))
    return out


# --------------------------------------------------------------------------
# 1) Hizalama
# --------------------------------------------------------------------------


def _aligned(a: Point, b: Point) -> bool:
    return (abs(a[0] - b[0]) < TOL) != (abs(a[1] - b[1]) < TOL)


def _distance(a: Point, b: Point) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _clear_between(a: Point, b: Point, pins: list[PinRef],
                   schematic: Schematic, sheet_path: str) -> bool:
    """Iki hizali pin arasinda BASKA bir pin ya da tel ucu var mi?"""
    for other in pins:
        if other.point in (a, b):
            continue
        if sch_wire._on_segment(other.point, a, b):
            return False
    for wire in schematic.wires + schematic.buses:
        if wire.sheet_path != sheet_path:
            continue
        for end in wire.endpoints:
            if sch_wire._on_segment((round(end[0], 4), round(end[1], 4)), a, b):
                return False
    return True


def alignment_pairs(pins: list[PinRef], schematic: Schematic,
                    sheet_path: str = "/") -> list[Proposal]:
    """Karsilikli en yakin hizali pin ciftleri.

    "Karsilikli" sarti bilincli: A'nin en yakin hizali komsusu B ve ayni
    zamanda B'nin en yakin hizali komsusu A ise arada tercih yapmak
    gerekmiyor. Tek yonlu bir yakinlik, hangisinin dogru oldugunu bilmedigimiz
    bir secim demek olurdu.
    """
    nearest: dict[int, int] = {}
    for i, pin in enumerate(pins):
        best, best_d = None, None
        for j, other in enumerate(pins):
            if i == j or not _aligned(pin.point, other.point):
                continue
            # AYNI SEMBOLUN pinleri asla eslesmez. Bir sembolun kendi pinleri
            # zaten hizalidir - bu hizalama sembolun GEOMETRISINDEN gelir,
            # kullanicinin yerlesiminden degil, yani hicbir niyet tasimaz.
            # Olculdu: bu kural olmadan ilk oneri "R1.1 - R1.2" oluyordu,
            # yani direncin uzerinden kisa devre.
            if other.ref == pin.ref:
                continue
            if not _clear_between(pin.point, other.point, pins, schematic, sheet_path):
                continue
            d = _distance(pin.point, other.point)
            if best_d is None or d < best_d:
                best, best_d = j, d
        if best is not None:
            nearest[i] = best

    out: list[Proposal] = []
    for i, j in nearest.items():
        if nearest.get(j) != i or j < i:
            continue
        a, b = pins[i], pins[j]
        eksen = "dikey" if abs(a.point[0] - b.point[0]) < TOL else "yatay"
        out.append(Proposal(
            kind="hizalama",
            pins=[a, b],
            path=[a.point, b.point],
            reason=f"ayni {eksen} hizada, {_distance(a.point, b.point):.2f} mm, "
                   "aralarinda engel yok",
        ))
    return out


# --------------------------------------------------------------------------
# 2) Guc inisi
# --------------------------------------------------------------------------


def power_drops(pins: list[PinRef], segments: list[tuple[Point, Point]],
                schematic: Schematic, sheet_path: str = "/") -> list[Proposal]:
    """Guc sembolunun bos pini bir tel parcasinin ORTASINA dik iniyorsa.

    Neden yalnizca ORTASINA: uc noktasina inseydi orada zaten bir pin var
    demektir ve o pine baglanmak "hizalama" kuralinin isi olurdu. Ortaya inen
    bir uc ise KiCad'de junction ister - ve tam olarak insanin cizdigi sekil
    budur.
    """
    out: list[Proposal] = []
    for pin in pins:
        if not pin.is_power:
            continue
        for a, b in segments:
            if abs(a[0] - b[0]) < TOL:      # dikey parca -> yatay inis
                inis = (a[0], pin.point[1])
            elif abs(a[1] - b[1]) < TOL:    # yatay parca -> dikey inis
                inis = (pin.point[0], a[1])
            else:
                continue
            if not sch_wire._on_segment(inis, a, b):   # strict: uclar haric
                continue
            if not _clear_between(pin.point, inis, pins, schematic, sheet_path):
                continue
            out.append(Proposal(
                kind="guc-inisi",
                pins=[pin],
                path=[pin.point, inis],
                reason=f"{pin.ref} rayin uzerine yerlestirilmis, "
                       f"({inis[0]:g},{inis[1]:g}) noktasina dik iniyor",
            ))
            break
    return out


# --------------------------------------------------------------------------
# Butun
# --------------------------------------------------------------------------


@dataclass
class Suggestion:
    proposals: list[Proposal] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        lines = [str(p) for p in self.proposals]
        lines += [f"onerilmedi: {s}" for s in self.skipped]
        return "\n".join(lines) or "oneri yok"


def suggest(schematic: Schematic, sheet_path: str = "/") -> Suggestion:
    """Sayfaya bakip baglanti onerir; kaniti olmayanlari SOYLEYEREK atlar."""
    pins = free_pins(schematic, sheet_path)
    result = Suggestion()
    if not pins:
        result.skipped.append("bos pin yok - her sey zaten bagli")
        return result

    hizali = alignment_pairs(pins, schematic, sheet_path)
    result.proposals.extend(hizali)

    # Guc inisi, hem ONERILEN hem de VAR OLAN teller uzerine bakar.
    segments: list[tuple[Point, Point]] = []
    for p in hizali:
        segments.extend(sch_wire._segments(p.path))
    for wire in schematic.wires:
        if wire.sheet_path == sheet_path:
            segments.append(wire.endpoints)

    result.proposals.extend(power_drops(pins, segments, schematic, sheet_path))

    # Hakkinda hicbir kanit bulunmayan pinler ACIKCA soylenir - sessizce
    # atlanan bir pin, kullanicinin fark etmedigi eksik bir baglantidir.
    onerilen = {pin.point for p in result.proposals for pin in p.pins}
    for pin in pins:
        if pin.point in onerilen:
            continue
        result.skipped.append(
            f"{pin} - hizali bos komsusu yok, yerlesimden bir niyet okunamiyor"
        )
    return result
