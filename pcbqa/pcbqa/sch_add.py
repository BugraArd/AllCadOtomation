"""Sematige kutuphaneden sembol EKLEME (Asama 4f).

"Sematige 5 direnc ekle" demek uc ayri isin birlikte yapilmasi demek:

  1. OKUMA      - `Device:R` tanimini kutuphaneden getir (`symlib.py`)
  2. BIRLESTIRME- tanimi dosyanin `lib_symbols` bolumune kopyala (yoksa).
                  KiCad dosyayi kendi kendine yeter tutar: sematik acildiginda
                  kutuphane kurulu olmasa bile sembol cizilebilmelidir.
  3. EKLEME     - sayfaya sembol ornegi koy: konum, referans (R5, R6...),
                  ozellikler, pin UUID'leri ve `instances` blogu.

## Neden `instances` blogu sart

KiCad 10'da referans (R5) sembolun icinde DEGIL, `instances` blogunda durur:
ayni sayfa dosyasi hiyerarside iki kez ornekleniyorsa iki farkli referans
gerekir. Blok eksikse Eeschema sembolu "R?" olarak gosterir. Bu yuzden blok,
ayni dosyadaki MEVCUT bir sembolden kopyalanir - boylece cok ornekli
sayfalarda her ornege dogru referans yazilir.

## Guvenlik

`sch_move` ile ayni boru hatti: varsayilan DRY-RUN, kum havuzunda netlist
kalkani, yedek, kilit kontrolu, atomik yazma. Kalkanin ekleme surumu
`sch_verify.compare_additive`: mevcut devrenin bolunusu AYNEN durmali,
yalnizca beklenen yeni bilesenler eklenmis olmali. Yeni sembol yanlislikla
var olan bir tele degerse bu kalkan yakalar.

UUID'ler yalnizca YENI dugumler icin uretilir; var olanlara dokunulmaz.

Ana giris: `add_symbols(sch, lib_id, count, ...)`, CLI: `python -m pcbqa.sch_add`.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import uuid as uuidlib
from dataclasses import dataclass, field
from pathlib import Path

from . import symlib, sch_wire
from .schematic import GRID_MM, Schematic, place_point, read_schematic
from .sch_verify import (
    ConnectivityDiff,
    SchVerifyError,
    compare_additive,
    connectivity_of,
)
from .sch_write import SchWriteError, WriteResult, write_tree
from .sexpr import child, children, dumps, head, parse_with_stats

# Yeni sembollerin oturtuldugu izgara (sematik gelenegi: 1.27 mm'nin katlari)
PLACE_STEP = 2.54 * 5  # 12.7 mm - iki bilesen arasi rahat aciklik
# Sayfa kenarindan birakilan bosluk
MARGIN_MM = 12.7
# Mevcut govdelerin cevresinde saygi gosterilen tampon
CLEARANCE_MM = 2.54

# KiCad kagit boyutlari (mm, yatay)
PAPER_SIZES = {
    "A5": (210.0, 148.0),
    "A4": (297.0, 210.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "A0": (1189.0, 841.0),
    "A": (279.4, 215.9),
    "B": (431.8, 279.4),
    "C": (558.8, 431.8),
    "D": (863.6, 558.8),
    "E": (1117.6, 863.6),
    "USLetter": (279.4, 215.9),
    "USLegal": (355.6, 215.9),
    "USLedger": (431.8, 279.4),
}


class SchAddError(RuntimeError):
    """Ekleme yapilamadi."""


@dataclass
class NewSymbol:
    """Eklenecek tek bir sembol ornegi."""

    ref: str
    x: float
    y: float
    rotation: float = 0.0
    unit: int = 1


@dataclass
class AddPlan:
    """Ne eklenecegi - yazmadan once gosterilebilir."""

    lib_id: str
    file: Path
    sheet_path: str
    symbols: list[NewSymbol] = field(default_factory=list)
    value: str = ""
    footprint: str = ""
    library_merged: bool = False
    multi_unit: bool = False
    # (ref, pin, hedef, "etiket" | "tel") - kurulacak baglantilar
    connections: list[tuple[str, str, str, str]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems and bool(self.symbols)

    def describe(self) -> str:
        lines = [f"{self.lib_id} x{len(self.symbols)} -> {self.file.name} (sayfa {self.sheet_path})"]
        if self.value:
            lines.append(f"  deger: {self.value}")
        if self.footprint:
            lines.append(f"  footprint: {self.footprint}")
        if not self.problems:
            # Engel varsa agac hic duzenlenmedi, yani bu soru daha
            # cevaplanmadi - "zaten var" demek yaniltici olurdu.
            lines.append("  kutuphane tanimi: " + ("dosyaya eklenecek" if self.library_merged
                                                   else "zaten var, dokunulmuyor"))
        for s in self.symbols:
            label = s.ref + (chr(64 + s.unit) if self.multi_unit else "")
            lines.append(f"  {label:<7} @ ({s.x:g}, {s.y:g})"
                         + (f" {s.rotation:g}deg" if s.rotation else ""))
        for ref, pin, target, how in self.connections:
            lines.append(f"  baglanti: {ref}.{pin} -> {target} ({how})")
        for note in self.notes:
            lines.append(f"  not: {note}")
        for problem in self.problems:
            lines.append(f"  ENGEL: {problem}")
        return "\n".join(lines)


@dataclass
class AddResult:
    plan: AddPlan
    diff: ConnectivityDiff | None = None
    write: WriteResult | None = None
    applied: bool = False


# --------------------------------------------------------------------------
# Referans numaralandirma
# --------------------------------------------------------------------------


def next_references(schematic: Schematic, prefix: str, count: int) -> list[str]:
    """Kullanilmayan `prefix1..N` referanslari.

    Numaralandirma TUM sematik uzerinden yapilir (yalnizca hedef sayfa
    degil): referans butun projede benzersiz olmali, yoksa KiCad'in
    ek-acma (annotation) araci karisir.
    """
    used: set[int] = set()
    for sym in schematic.symbols:
        ref = sym.ref
        if not ref.startswith(prefix):
            continue
        tail = ref[len(prefix):]
        if tail.isdigit():
            used.add(int(tail))

    out: list[str] = []
    number = 1
    while len(out) < count:
        if number not in used:
            out.append(f"{prefix}{number}")
            used.add(number)
        number += 1
    return out


# --------------------------------------------------------------------------
# Yerlestirme
# --------------------------------------------------------------------------


def _snap(value: float, grid: float = GRID_MM) -> float:
    return round(round(value / grid) * grid, 4)


def occupied_boxes(schematic: Schematic, sheet_path: str) -> list[tuple[float, float, float, float]]:
    """Sayfada dolu olan alanlar (sembol govdeleri + tel parcalari)."""
    boxes: list[tuple[float, float, float, float]] = []
    for sym in schematic.symbols:
        if sym.sheet_path != sheet_path:
            continue
        if sym.bbox:
            boxes.append(sym.bbox)
        else:
            # Govde okunamadiysa konumun cevresinde makul bir kutu varsay
            boxes.append((sym.x - 5.08, sym.y - 5.08, sym.x + 5.08, sym.y + 5.08))
    for wire in schematic.wires + schematic.buses:
        if wire.sheet_path != sheet_path:
            continue
        boxes.append((min(wire.x1, wire.x2), min(wire.y1, wire.y2),
                      max(wire.x1, wire.x2), max(wire.y1, wire.y2)))
    for sheet in schematic.sheets:
        if getattr(sheet, "sheet_path", sheet_path) == sheet_path:
            box = getattr(sheet, "bbox", None)
            if box:
                boxes.append(box)
    return boxes


def _overlaps(box, others, clearance: float = CLEARANCE_MM) -> bool:
    x0, y0, x1, y1 = box
    for ox0, oy0, ox1, oy1 in others:
        if (x0 - clearance < ox1 and x1 + clearance > ox0
                and y0 - clearance < oy1 and y1 + clearance > oy0):
            return True
    return False


def free_slots(
    schematic: Schematic,
    sheet_path: str,
    count: int,
    size: tuple[float, float],
    step: float = PLACE_STEP,
) -> tuple[list[tuple[float, float]], list[str]]:
    """Sayfada bos `count` adet konum bulur (soldan saga, yukaridan asagiya).

    Sayfa dolarsa asagi dogru TASAR ve bunu not olarak bildirir - KiCad
    kagit disina yerlestirmeye izin verir, kullanici sonra toplayabilir.
    """
    width, height = PAPER_SIZES.get(schematic.paper or "A4", PAPER_SIZES["A4"])
    taken = occupied_boxes(schematic, sheet_path)
    half_w, half_h = size[0] / 2.0, size[1] / 2.0

    slots: list[tuple[float, float]] = []
    notes: list[str] = []
    y = _snap(MARGIN_MM + half_h)
    overflow = False
    while len(slots) < count:
        x = _snap(MARGIN_MM + half_w)
        while x + half_w <= width - MARGIN_MM and len(slots) < count:
            box = (x - half_w, y - half_h, x + half_w, y + half_h)
            if not _overlaps(box, taken):
                slots.append((x, y))
                taken.append(box)
            x = _snap(x + step)
        y = _snap(y + step)
        if y + half_h > height - MARGIN_MM and len(slots) < count:
            if not overflow:
                notes.append("sayfada yer kalmadi; kalanlar kagidin altina tasti")
                overflow = True
            if y > height * 3:  # sonsuz donguye karsi emniyet
                raise SchAddError("bos yer bulunamadi")
    return slots, notes


# --------------------------------------------------------------------------
# Plan
# --------------------------------------------------------------------------


def plan_add(
    schematic: Schematic,
    lib_id: str,
    count: int,
    *,
    value: str | None = None,
    footprint: str | None = None,
    sheet_path: str | None = None,
    at: tuple[float, float] | None = None,
    step: float = PLACE_STEP,
    rotation: float = 0.0,
    reference_prefix: str | None = None,
    unit: int | None = None,
    check_footprint: bool = True,
    kicad_cli: str | None = None,
) -> tuple[AddPlan, symlib.LibSymbol]:
    """Ne yapilacagini hesaplar; DOSYAYA DOKUNMAZ."""
    if count < 1:
        raise SchAddError("count en az 1 olmali")

    sheet_path = sheet_path or "/"
    target = schematic.file_of_sheet.get(sheet_path)
    if target is None:
        known = ", ".join(sorted(schematic.file_of_sheet)[:6])
        raise SchAddError(f"sayfa bulunamadi: {sheet_path!r} (bilinenler: {known})")

    project_dir = schematic.root_path.parent
    symbol = symlib.get_symbol(lib_id, project_dir=project_dir, kicad_cli=kicad_cli)

    prefix = reference_prefix or symbol.reference_prefix
    assignments = allocate_units(symbol, count, unit)
    refs = next_references(schematic, prefix, len({i for i, _ in assignments}))
    placements = [(refs[slot], unit_no) for slot, unit_no in assignments]

    # Govde boyutu: yalnizca YERLESTIRILEN birimin pinleri sayilir
    size = symbol_size(symbol, placements[0][1])
    notes: list[str] = []
    if at is not None:
        positions = [(_snap(at[0] + i * step), _snap(at[1])) for i in range(count)]
        if abs(positions[0][0] - at[0]) > 1e-9 or abs(positions[0][1] - at[1]) > 1e-9:
            # Izgara disi sembol, pinleri tellere denk getiremez - KiCad'in
            # kendisi de yerlestirmede oturtur.
            notes.append(
                f"istenen konum ({at[0]:g}, {at[1]:g}) "
                f"{GRID_MM:g} mm izgarasina oturtuldu -> "
                f"({positions[0][0]:g}, {positions[0][1]:g})"
            )
    else:
        positions, notes = free_slots(schematic, sheet_path, count, size, step=step)

    plan = AddPlan(
        lib_id=lib_id,
        file=target,
        sheet_path=sheet_path,
        symbols=[NewSymbol(ref=r, x=p[0], y=p[1], rotation=rotation, unit=u)
                 for (r, u), p in zip(placements, positions)],
        value=value if value is not None else symbol.properties.get("Value", symbol.name),
        footprint=footprint if footprint is not None else symbol.properties.get("Footprint", ""),
        multi_unit=symbol.unit_count > 1,
        notes=notes,
    )

    if symbol.unit_count > 1:
        used = ", ".join(f"{r}{chr(64 + u)}" for r, u in placements[:6])
        plan.notes.append(
            f"{symbol.name} {symbol.unit_count} birimli; birimler: {used}"
            + (" ..." if len(placements) > 6 else "")
        )
        # Bir referansin birimleri eksik kalirsa KiCad'in ERC'si "missing_unit"
        # uyarisi verir - olculdu. Engel degil, ama sessiz kalmamali.
        eksik = {
            ref: sorted(set(range(1, symbol.unit_count + 1))
                        - {u for r, u in placements if r == ref})
            for ref in {r for r, _ in placements}
        }
        eksik = {r: u for r, u in eksik.items() if u}
        if eksik:
            detay = "; ".join(
                f"{r}: {', '.join(chr(64 + u) for u in units)}"
                for r, units in sorted(eksik.items())
            )
            plan.notes.append(
                f"yerlestirilmeyen birimler var ({detay}) - KiCad ERC'si "
                "bunu 'missing_unit' diye bildirir"
            )

    if plan.footprint and check_footprint:
        try:
            path = symlib.footprint_path(plan.footprint, project_dir, kicad_cli)
            plan.notes.append(f"footprint dogrulandi: {path.name}")
        except symlib.SymLibError as exc:
            plan.problems.append(str(exc))

    return plan, symbol


def allocate_units(
    symbol: symlib.LibSymbol,
    count: int,
    unit: int | None = None,
) -> list[tuple[int, int]]:
    """(referans yuvasi, birim) ciftleri.

    Cok birimli sembollerde (74LS125 -> 4 kapi + guc birimi) KiCad'in
    kurali su: BIR referans butun birimleri tasir - U3A, U3B, U3C, U3D.
    Bu yuzden `--count 6` demek "6 kapi" demektir ve bu iki referansa
    dagitilir: U3'un 5 birimi, sonra U4'un 1 birimi.

    `unit` acikca verilirse her ornek O birimi kullanir ve her biri kendi
    referansini alir - "yalnizca 3. kapidan 4 tane" demek budur.
    """
    if unit is not None:
        if unit < 1 or unit > max(1, symbol.unit_count):
            raise SchAddError(
                f"{symbol.name} birim araligi 1..{symbol.unit_count}; {unit} verildi"
            )
        return [(i, unit) for i in range(count)]

    per_ref = max(1, symbol.unit_count)
    return [(i // per_ref, (i % per_ref) + 1) for i in range(count)]


def symbol_size(symbol: symlib.LibSymbol, unit: int = 1) -> tuple[float, float]:
    """Sembolun kapladigi kaba alan (pinler dahil)."""
    pins = [p for p in symbol.pins if p.unit in (0, unit)] or symbol.pins
    xs = [p.x for p in pins]
    ys = [p.y for p in pins]
    if not xs or not ys:
        return (5.08, 5.08)
    return (max(max(xs) - min(xs), 5.08), max(max(ys) - min(ys), 5.08))


# --------------------------------------------------------------------------
# Agac duzenleme
# --------------------------------------------------------------------------


def _new_uuid() -> str:
    return f'"{uuidlib.uuid4()}"'


def _q(text: str) -> str:
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def merge_lib_symbol(root, symbol: symlib.LibSymbol) -> bool:
    """Tanimi `lib_symbols` bolumune ekler. Zaten varsa dokunmaz.

    Doner: gercekten eklendi mi.
    """
    lib_node = child(root, "lib_symbols")
    if lib_node is None:
        lib_node = ["lib_symbols"]
        # `lib_symbols` her zaman basliktan sonra, govdeden once durur
        insert_at = 1
        for i, node in enumerate(root):
            if isinstance(node, list) and head(node) in ("uuid", "paper", "title_block"):
                insert_at = i + 1
        root.insert(insert_at, lib_node)

    wanted = f"{symbol.library}:{symbol.name}"
    for existing in children(lib_node, "symbol"):
        if symlib.head_atom(existing) == wanted:
            return False

    lib_node.append(symlib.resolve_definition(symbol))
    return True


def _instances_template(root) -> list | None:
    """Ayni dosyadaki bir sembolun `instances` blogu (sablon olarak)."""
    for node in children(root, "symbol"):
        inst = child(node, "instances")
        if inst is not None:
            return inst
    return None


def _instances_for(root, schematic: Schematic, ref: str, unit: int) -> list:
    """Yeni sembol icin `instances` blogu.

    Sablon ayni dosyadaki bir sembolden alinir; boylece sayfa hiyerarside
    kac kez orneklenmisse o kadar yol (path) yazilir. Sablon yoksa (bos
    sayfa) kok UUID ile tek yol uretilir.
    """
    template = _instances_template(root)
    if template is not None:
        node = _copy(template)
        for project in children(node, "project"):
            for path in children(project, "path"):
                _set_field(path, "reference", _q(ref))
                _set_field(path, "unit", str(unit))
        return node

    project_name = schematic.root_path.stem
    root_uuid = schematic.uuid or ""
    return [
        "instances",
        ["project", _q(project_name),
         ["path", _q("/" + root_uuid.strip('"')),
          ["reference", _q(ref)],
          ["unit", str(unit)]]],
    ]


def _set_field(node, name: str, value: str) -> None:
    sub = child(node, name)
    if sub is None:
        node.append([name, value])
    elif len(sub) > 1:
        sub[1] = value
    else:
        sub.append(value)


def _copy(node):
    return [_copy(n) for n in node] if isinstance(node, list) else node


def _property_node(source, name: str, value: str, sx: float, sy: float,
                   rotation: float) -> list:
    """Kutuphane ozelligini sayfa koordinatina tasinmis kopyasi."""
    node = _copy(source)
    node[2] = _q(value)
    at = child(node, "at")
    if at and len(at) >= 3:
        px, py = float(at[1]), float(at[2])
        ox, oy = place_point(px, py, rotation, None)
        at[1] = f"{round(sx + ox, 4):g}"
        at[2] = f"{round(sy + oy, 4):g}"
        if len(at) >= 4:
            at[3] = f"{(float(at[3]) + rotation) % 360:g}"
    return node


def build_symbol_node(
    root,
    schematic: Schematic,
    symbol: symlib.LibSymbol,
    new: NewSymbol,
    value: str,
    footprint: str,
) -> list:
    """Sayfaya konacak `(symbol ...)` dugumu."""
    node: list = [
        "symbol",
        ["lib_id", _q(f"{symbol.library}:{symbol.name}")],
        ["at", f"{new.x:g}", f"{new.y:g}", f"{new.rotation:g}"],
        ["unit", str(new.unit)],
        ["exclude_from_sim", "no"],
        ["in_bom", "yes"],
        ["on_board", "yes"],
        ["dnp", "no"],
        ["uuid", _new_uuid()],
    ]

    overrides = {"Reference": new.ref, "Value": value, "Footprint": footprint}
    seen: set[str] = set()
    for prop in children(symbol.node, "property"):
        name = str(prop[1]).strip('"')
        if name.startswith("ki_"):
            # `ki_keywords`, `ki_fp_filters` KUTUPHANE tanimina aittir; KiCad
            # bunlari sembol ORNEGINE yazmaz. Yazarsak kartin sematik parite
            # kontrolu "ayak izinde eksik sembol alani 'ki_keywords'" diye
            # uyariyor - olculdu, uc bilesende uc uyari.
            continue
        seen.add(name)
        node.append(_property_node(prop, name, overrides.get(name, str(prop[2]).strip('"')),
                                   new.x, new.y, new.rotation))
    # Kutuphanede tanimli degilse bile Reference/Value yazilmali
    for name in ("Reference", "Value"):
        if name not in seen:
            node.append(["property", _q(name), _q(overrides[name]),
                         ["at", f"{new.x:g}", f"{new.y:g}", "0"]])

    for pin in symbol.pins:
        if pin.unit not in (0, new.unit):
            continue
        node.append(["pin", _q(pin.number), ["uuid", _new_uuid()]])

    node.append(_instances_for(root, schematic, new.ref, new.unit))
    return node


def new_pin_points(symbol: symlib.LibSymbol, new: NewSymbol) -> dict[str, tuple]:
    """Eklenecek sembolun pin numarasi -> sayfa koordinati."""
    return {
        pin.number: sch_wire.pin_position(new.x, new.y, new.rotation, None, pin.x, pin.y)
        for pin in symbol.pins
        if pin.unit in (0, new.unit)
    }


def pin_rotation(symbol: symlib.LibSymbol, new: NewSymbol, number: str) -> float:
    """Pinin SAYFA uzerindeki acisi (etiketi dogru yone yazdirmak icin)."""
    for pin in symbol.pins:
        if pin.number == number and pin.unit in (0, new.unit):
            return (pin.rotation + new.rotation) % 360.0
    return 0.0


def build_connections(
    root,
    schematic: Schematic,
    plan: AddPlan,
    symbol: symlib.LibSymbol,
    connections: list[sch_wire.Connection],
) -> list[list]:
    """Baglanti dugumleri (tel + etiket + junction) uretir.

    Iki yol var ve ikisi de KiCad'in kendi kurallariyla calisir:

      * hedef bir AG ADI ise pinin tam ustune yerel etiket konur;
      * hedef bir PIN ise (`R1.2`) araya dik bir yol cizilir. Yol
        bulunamazsa (arada baska pinler var) baglanti ETIKETE dusurulur -
        ad uydurmak yerine hedef pinin bugunku agina baglanmak dogru olmaz,
        bu yuzden bu durumda engel uretilir ve kullaniciya soylenir.
    """
    nodes: list[list] = []
    for new in plan.symbols:
        points = new_pin_points(symbol, new)
        for conn in connections:
            if conn.pin not in points:
                plan.problems.append(
                    f"{symbol.name} sembolunde {conn.pin!r} pini yok "
                    f"(birim {new.unit}: {', '.join(sorted(points))})"
                )
                continue
            start = points[conn.pin]

            if not conn.is_pin_target:
                rotation = sch_wire.label_rotation(
                    pin_rotation(symbol, new, conn.pin)
                )
                nodes.append(sch_wire.label_node(start[0], start[1], conn.target, rotation))
                plan.connections.append((new.ref, conn.pin, conn.target, "etiket"))
                continue

            ref, number = conn.target_pin
            try:
                end = sch_wire.existing_pin_point(schematic, ref, number, plan.sheet_path)
            except KeyError as exc:
                plan.problems.append(str(exc))
                continue

            path = sch_wire.route(start, end, schematic, plan.sheet_path)
            if path is None:
                plan.problems.append(
                    f"{new.ref}.{conn.pin} -> {conn.target}: arada baska pinler/tel "
                    "uclari var, temiz bir yol cizilemedi (etiketle baglayin)"
                )
                continue
            nodes.extend(sch_wire.wire_nodes(path))
            for jx, jy in sch_wire.junctions_needed(path, schematic, plan.sheet_path):
                nodes.append(sch_wire.junction_node(jx, jy))
            plan.connections.append((new.ref, conn.pin, conn.target, "tel"))
    return nodes


def edit_tree(root, schematic: Schematic, plan: AddPlan, symbol: symlib.LibSymbol,
              connections: list[sch_wire.Connection] | None = None) -> None:
    """Plani agaca uygular (dosyaya yazmaz)."""
    plan.library_merged = merge_lib_symbol(root, symbol)
    for new in plan.symbols:
        root.append(build_symbol_node(root, schematic, symbol, new,
                                      plan.value, plan.footprint))
    for node in build_connections(root, schematic, plan, symbol, connections or []):
        root.append(node)


# --------------------------------------------------------------------------
# Uygulama
# --------------------------------------------------------------------------


def _expected_joins(
    plan: AddPlan,
    connections: list[sch_wire.Connection],
    before,
) -> dict[tuple[str, str], set[tuple[str, str]]]:
    """Kalkana "bu pin SU pinle ayni aga girmeli" listesi.

    Ag adiyla baglanirken beklenen kume, o agin BUGUNKU pinleridir. Ag
    hicbir yerde yoksa (yeni ad) kume bostur; o zaman kalkan yalnizca
    "eski hicbir pine degmesin" kuralini uygular.
    """
    out: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for new in plan.symbols:
        for conn in connections:
            key = (new.ref, conn.pin)
            if conn.is_pin_target:
                out[key] = {conn.target_pin}
            else:
                pins = sch_wire.pins_on_net(before.net_of, conn.target)
                if pins:
                    out[key] = set(pins)
    return out


def _sandbox_copy(schematic: Schematic, tmp: Path) -> Path:
    """Proje klasorunu gecici dizine kopyalar; yeni kok sematik yolunu doner."""
    source_dir = schematic.root_path.parent
    target_dir = tmp / source_dir.name
    shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
    return target_dir / schematic.root_path.name


def add_symbols(
    sch_path: Path | str,
    lib_id: str,
    count: int = 1,
    *,
    value: str | None = None,
    footprint: str | None = None,
    sheet_path: str | None = None,
    at: tuple[float, float] | None = None,
    rotation: float = 0.0,
    step: float = PLACE_STEP,
    reference_prefix: str | None = None,
    unit: int | None = None,
    connect: list[str] | None = None,
    check_footprint: bool = True,
    apply: bool = False,
    verify: bool = True,
    force: bool = False,
    backup: bool = True,
    allow_open_project: bool = False,
    kicad_cli: str | None = None,
) -> AddResult:
    """Kutuphaneden sembol(ler) ekler.

    Varsayilan DRY-RUN'dir. `verify` acikken degisiklik once kum havuzunda
    uygulanip netlist karsilastirilir: mevcut devre aynen durmali, yalnizca
    beklenen bilesenler eklenmis olmali (`force=True` reddi devre disi birakir).
    """
    schematic = read_schematic(sch_path)
    plan, symbol = plan_add(
        schematic, lib_id, count,
        value=value, footprint=footprint, sheet_path=sheet_path, at=at,
        step=step, rotation=rotation, reference_prefix=reference_prefix,
        unit=unit, check_footprint=check_footprint, kicad_cli=kicad_cli,
    )
    if not plan.ok and not force:
        return AddResult(plan=plan, applied=False)

    try:
        wanted = [sch_wire.Connection.parse(text) for text in (connect or [])]
    except ValueError as exc:
        raise SchAddError(str(exc)) from exc

    root, stray = parse_with_stats(plan.file.read_text(encoding="utf-8"))
    if stray:
        raise SchAddError(
            f"{plan.file.name} bozuk gorunuyor ({stray} kacak parantez); yazma yapilmadi"
        )
    edit_tree(root, schematic, plan, symbol, wanted)
    if plan.problems and not force:
        # Baglanti kurulamadiysa yarim is yazmayiz.
        return AddResult(plan=plan, applied=False)
    new_text = dumps(root) + "\n"

    diff: ConnectivityDiff | None = None
    if verify:
        # ONCE olcumu de kum havuzunda alinir. Sebep olculdu: `kicad-cli`
        # projeyi acarken `~<proje>.kicad_pro.lck` birakiyor ve onu
        # temizlemiyor. Kullanicinin klasorunde calistirirsak kendi
        # kalkanimiz kendi yazmamizi "proje KiCad'de acik" diye reddeder.
        with tempfile.TemporaryDirectory(prefix="pcbqa-sandbox-") as tmp:
            base_root = _sandbox_copy(schematic, Path(tmp) / "once")
            after_root = _sandbox_copy(schematic, Path(tmp) / "sonra")
            relative = plan.file.relative_to(schematic.root_path.parent)
            (after_root.parent / relative).write_text(new_text, encoding="utf-8")
            try:
                before = connectivity_of(base_root, kicad_cli)
                after = connectivity_of(after_root, kicad_cli)
            except SchVerifyError as exc:
                raise SchAddError(f"kalkan calistirilamadi: {exc}") from exc
            # SANAL semboller (#PWR, #FLG) netlist'te HIC gorunmez - KiCad
            # onlari bilesen olarak yazmaz. Beklenen listeye koyarsak
            # "eklenenler beklenenlerle ayni mi" kontrolu HER ZAMAN duser ve
            # guc sembolu eklenemez. Olculdu: power:+24V eklendikten sonra
            # netlist'in bilesen kumesi HIC degismiyor (17 -> 17).
            beklenen = {s.ref for s in plan.symbols if not s.ref.startswith("#")}
            diff = compare_additive(
                before, after, beklenen,
                expected_joins=_expected_joins(plan, wanted, before),
            )

        if not diff.ok and not force:
            return AddResult(plan=plan, diff=diff, applied=False)

    write = write_tree(
        plan.file, root,
        apply=apply, backup=backup, allow_open_project=allow_open_project,
    )
    return AddResult(plan=plan, diff=diff, write=write, applied=write.written)


# --------------------------------------------------------------------------
# Komut satiri
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pcbqa.sch_add",
        description="Sematige kutuphaneden sembol ekler (varsayilan dry-run).",
    )
    ap.add_argument("--sch", type=Path, required=True, help="Kok .kicad_sch dosyasi")
    ap.add_argument("--lib-id", required=True, help="Sembol kimligi, or. Device:R")
    ap.add_argument("--count", type=int, default=1, help="Kac adet")
    ap.add_argument("--value", default=None, help="Deger (or. 10k). Yoksa kutuphanedeki")
    ap.add_argument("--footprint", default=None, help="Footprint kimligi")
    ap.add_argument("--sheet", default=None, help="Hedef sayfa yolu (varsayilan kok)")
    ap.add_argument("--at", default=None, help="Ilk sembolun konumu: X,Y (mm)")
    ap.add_argument("--rotation", type=float, default=0.0, help="Donme acisi")
    ap.add_argument("--step", type=float, default=PLACE_STEP, help="Semboller arasi aralik (mm)")
    ap.add_argument("--prefix", default=None, help="Referans on eki (varsayilan kutuphaneden)")
    ap.add_argument("--unit", type=int, default=None,
                    help="Cok birimli sembolde hangi birim (varsayilan: sirayla doldur)")
    ap.add_argument("--no-check-footprint", action="store_true",
                    help="Footprint kimligini dogrulama")
    ap.add_argument("--connect", action="append", default=None, metavar="PIN=HEDEF",
                    help="Pini bagla. HEDEF bir ag adi (1=VCC) ya da pin (2=R1.1). "
                         "Birden fazla kez verilebilir.")
    ap.add_argument("--apply", action="store_true", help="Dosyaya gercekten yaz")
    ap.add_argument("--no-verify", action="store_true", help="Netlist kalkanini atla (onerilmez)")
    ap.add_argument("--no-backup", action="store_true", help="Yedek alma")
    ap.add_argument("--force", action="store_true", help="Engelleri ve kalkan reddini yok say")
    ap.add_argument("--allow-open-project", action="store_true", help="KiCad acikken de yaz")
    ap.add_argument("--kicad-cli", default=None)
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    at = None
    if args.at:
        try:
            x, y = (float(v) for v in args.at.replace(" ", "").split(","))
            at = (x, y)
        except ValueError:
            print("hata: --at X,Y bicimide olmali", file=sys.stderr)
            return 2

    try:
        result = add_symbols(
            args.sch, args.lib_id, args.count,
            value=args.value, footprint=args.footprint, sheet_path=args.sheet,
            at=at, rotation=args.rotation, step=args.step,
            reference_prefix=args.prefix, unit=args.unit, connect=args.connect,
            check_footprint=not args.no_check_footprint,
            apply=args.apply, verify=not args.no_verify, force=args.force,
            backup=not args.no_backup, allow_open_project=args.allow_open_project,
            kicad_cli=args.kicad_cli,
        )
    except (SchAddError, SchWriteError, symlib.SymLibError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 1

    print(result.plan.describe())
    if result.diff is not None:
        if result.diff.ok:
            print("  kalkan: mevcut devre degismedi, yalnizca yeni bilesenler eklendi")
        else:
            # Ozet ONCE yazilir: asagidaki dokum bos kalabiliyor (or. yalnizca
            # "eklenenler beklenenle tutmadi" durumunda) ve o zaman kullaniciya
            # gerekcesiz bir "KALKAN REDDETTI:" gorunuyordu. Olculdu: guc
            # sembolu eklerken red mesaji tamamen bostu.
            print(f"  KALKAN REDDETTI: {result.diff.describe()}")
            for satir in result.diff.details():
                print("  " + satir)
            for pin, old, new, *_ in result.diff.regrouped[:5]:
                print(f"    {pin[0]}.{pin[1]}: {old} -> {new}")
            for pin in result.diff.lost_pins[:5]:
                print(f"    kaybolan pin: {pin[0]}.{pin[1]}")
    if result.write is not None:
        for note in result.write.notes:
            print(f"  {note}")
        if result.applied:
            print(f"  yazildi: {result.write.path}"
                  + (f" (yedek: {result.write.backup.name})" if result.write.backup else ""))
    if not result.applied and not args.apply:
        print("  (dry-run - yazmak icin --apply)")
    return 0 if (result.applied or not args.apply) else 1


if __name__ == "__main__":
    raise SystemExit(main())
