"""Sematikten karta yansitma - "Update PCB from Schematic" (Asama 4g).

KiCad'in kendi "Update PCB from Schematic" komutu YALNIZCA GUI'de var:
`kicad-cli pcb` alt komutlari drc/export/import/render/upgrade ile sinirli.
Yani sematige bilesen eklemek karta kendiliginden yansimiyordu. Bu modul o
adimi kapatir.

## Ne yapar

  1. Sematigi ve KiCad'in kendi netlist'ini okur (hangi bilesen hangi
     footprint'i istiyor, hangi pin hangi agda).
  2. Kartta OLMAYAN bilesenleri bulur (esleme UUID YOLU uzerinden yapilir,
     referans uzerinden degil - referans yeniden numaralanabilir, yol
     kalicidir).
  3. Eksik olanlarin `.kicad_mod` dosyasini kutuphaneden getirir, kart
     bicimine cevirir (kutuphane onekli ad, yeni UUID'ler, `path` bagi,
     `sheetname`/`sheetfile`) ve pad'lere sematikten gelen AG ADLARINI yazar.
  4. Kartin bos bir yerine, birbirine girmeyecek sekilde dizer.

## Ne yapmaz (bilincli)

Var olan bilesenlere DOKUNMAZ: silme, tasima, footprint degistirme yok.
Yalnizca ekler. Boylece "yansitma" adimi kartin mevcut yerlesimini asla
bozamaz - sematik tarafindaki `sch_move`/`sch_add` sozlesmesinin aynisi.
Bilesenleri guzel yerlestirmek `auto` yerlestiricisinin isi; bu modul
onlari yalnizca gecerli ve cakismayan bir baslangic noktasina koyar.

KiCad 10 not: kart dosyasinda artik numarali net tablosu YOK; pad'ler agi
dogrudan adiyla tasiyor (`(net "VCC")`). Bu, yansitmayi belirgin sekilde
basitlestiriyor.
"""

from __future__ import annotations

import argparse
import sys
import uuid as uuidlib
from dataclasses import dataclass, field
from pathlib import Path

from . import symlib
from .pcb import read_board
from .sch_verify import SchVerifyError, connectivity_of
from .sch_write import SchWriteError, WriteResult, write_tree
from .schematic import Schematic, read_schematic
from .sexpr import child, children, head, parse_with_stats

# Yeni bilesenler kartin bu kadar sagina dizilir
GAP_MM = 10.0
# Aralarindaki mesafe
PITCH_MM = 12.7


# NOT (olculdu, sezgiye aykiri): `unconnected-(R5-Pad1)` bicimindeki adlar
# "yer tutucu" gibi gorunse de KART DOSYASINA YAZILMALIDIR - ornek kartta
# KiCad'in kendi yazdigi 77 tane var. Bunlari eleyip pad'i agsiz birakmayi
# denedik; KiCad'in sematik paritesi "Ped, sematik tarafindan verilen agdan
# yoksun" diye alti uyari verdi. Netlist ne diyorsa o yazilir.


class PcbSyncError(RuntimeError):
    """Yansitma yapilamadi."""


@dataclass
class NewFootprint:
    ref: str
    footprint_id: str
    value: str
    path: str  # "/<sayfa-uuid>/<sembol-uuid>"
    x: float = 0.0
    y: float = 0.0
    nets: dict[str, str] = field(default_factory=dict)  # pad numarasi -> ag adi
    # Sembolden karta tasinan alanlar (Datasheet, Description...). KiCad'in
    # sematik PARITE kontrolu bunlarin ayni olmasini ister; olculdu:
    # kopyalamayinca "'Description' alani farkli" diye uyariyor.
    properties: dict[str, str] = field(default_factory=dict)
    # Birim adi -> o birimin pad numaralari. Cok birimli parcada kartta TEK
    # footprint olur; bu blok hangi kapinin hangi bacaklara dustugunu tutar.
    units: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class SyncPlan:
    sch: Path
    pcb: Path
    add: list[NewFootprint] = field(default_factory=list)
    # Sematikte olup footprint'i atanmamis bilesenler (karta gidemezler)
    without_footprint: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def describe(self) -> str:
        lines = [f"{self.sch.name} -> {self.pcb.name}"]
        if not self.add:
            lines.append("  kart guncel: eklenecek bilesen yok")
        for item in self.add:
            nets = ", ".join(f"{p}:{n}" for p, n in sorted(item.nets.items()) if n)
            lines.append(f"  + {item.ref:<6} {item.footprint_id}"
                         f" @ ({item.x:g}, {item.y:g})" + (f"  [{nets}]" if nets else ""))
        for ref in self.without_footprint:
            lines.append(f"  atlandi (footprint atanmamis): {ref}")
        for note in self.notes:
            lines.append(f"  not: {note}")
        for problem in self.problems:
            lines.append(f"  ENGEL: {problem}")
        return "\n".join(lines)


@dataclass
class SyncResult:
    plan: SyncPlan
    write: WriteResult | None = None
    applied: bool = False
    verified: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Eslestirme
# --------------------------------------------------------------------------


def symbol_path(schematic: Schematic, ref: str) -> str:
    """Sembolun KiCad yolu: `/<sayfa-uuid>/<sembol-uuid>`.

    Kart bileseni sematik sembolune BU YOLLA baglidir; referans degisse bile
    bag kopmaz. Yolu yanlis yazmak, KiCad'in bileseni "sematikte yok" sayip
    bir sonraki guncellemede silmesi demektir.
    """
    for sym in schematic.symbols:
        if sym.ref != ref:
            continue
        sheet = sym.sheet_path.rstrip("/")
        return f"{sheet}/{sym.uuid}" if sheet else f"/{sym.uuid}"
    raise KeyError(ref)


def board_paths(root) -> dict[str, str]:
    """Karttaki footprint'lerin yol -> referans esleme."""
    out: dict[str, str] = {}
    for fp in children(root, "footprint"):
        path_node = child(fp, "path")
        path = str(path_node[1]).strip('"') if path_node and len(path_node) > 1 else ""
        ref = ""
        for prop in children(fp, "property"):
            if len(prop) >= 3 and str(prop[1]).strip('"') == "Reference":
                ref = str(prop[2]).strip('"')
        if path:
            out[path] = ref
    return out


def board_refs(root) -> set[str]:
    refs = set()
    for fp in children(root, "footprint"):
        for prop in children(fp, "property"):
            if len(prop) >= 3 and str(prop[1]).strip('"') == "Reference":
                refs.add(str(prop[2]).strip('"'))
    return refs


# --------------------------------------------------------------------------
# Yerlestirme
# --------------------------------------------------------------------------


def free_positions(pcb_path: Path, count: int) -> tuple[list[tuple[float, float]], str]:
    """Yeni bilesenler icin kartin SAGINDA bos konumlar.

    Kartin uzerine koymak, mevcut yerlesimin uzerine binmek demek olurdu.
    KiCad'in kendi davranisi da yeni bilesenleri bir kenara birakmaktir;
    duzgun yerlestirme `auto`nun isi.
    """
    board = read_board(pcb_path)
    xs = [c.x for c in board.components] or [0.0]
    ys = [c.y for c in board.components] or [0.0]
    if board.outline:
        minx, miny, maxx, maxy = board.outline
    else:
        minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)

    start_x = round(maxx + GAP_MM, 3)
    positions = [(start_x + (i % 8) * PITCH_MM, round(miny + (i // 8) * PITCH_MM, 3))
                 for i in range(count)]
    return positions, f"yeni bilesenler kartin sagina dizildi (x >= {start_x:g} mm)"


# --------------------------------------------------------------------------
# Footprint donusturme
# --------------------------------------------------------------------------


def _uuid() -> str:
    return f'"{uuidlib.uuid4()}"'


def _q(text: str) -> str:
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _copy(node):
    return [_copy(n) for n in node] if isinstance(node, list) else node


def _drop(node, names: set[str]) -> list:
    return [n for n in node if not (isinstance(n, list) and head(n) in names)]


def _set_property(fp, name: str, value: str) -> None:
    for prop in children(fp, "property"):
        if len(prop) >= 3 and str(prop[1]).strip('"') == name:
            prop[2] = _q(value)
            return
    fp.append(["property", _q(name), _q(value), ["at", "0", "0", "0"],
               ["layer", '"F.Fab"'], ["uuid", _uuid()],
               ["effects", ["font", ["size", "1", "1"], ["thickness", "0.15"]]]])


def build_footprint_node(
    item: NewFootprint,
    sheet_file: str,
    sheet_name: str = "/",
    kicad_cli: str | None = None,
    project_dir: Path | None = None,
) -> list:
    """`.kicad_mod` dosyasini kart bicimine cevirir."""
    path = symlib.footprint_path(item.footprint_id, project_dir, kicad_cli)
    root, stray = parse_with_stats(path.read_text(encoding="utf-8", errors="replace"))
    if stray:
        raise PcbSyncError(f"{path.name} bozuk gorunuyor ({stray} kacak parantez)")
    if head(root) != "footprint":
        raise PcbSyncError(f"{path.name} bir footprint dosyasi degil")

    node = _copy(root)
    # Kutuphane dosyasina ait alanlar karta gitmez
    node = _drop(node, {"version", "generator", "generator_version", "embedded_fonts"})
    node[1] = _q(item.footprint_id)  # kartta ad kutuphane onekiyle durur

    # Konum, kimlik ve sematik bagi
    node.insert(2, ["at", f"{item.x:g}", f"{item.y:g}"])
    node.insert(3, ["uuid", _uuid()])
    node.append(["path", _q(item.path)])
    node.append(["sheetname", _q(sheet_name)])
    node.append(["sheetfile", _q(sheet_file)])

    _set_property(node, "Reference", item.ref)
    _set_property(node, "Value", item.value)
    for name, value in item.properties.items():
        _set_property(node, name, value)

    # Pad'lere ag adlarini yaz. KiCad 10'da numarali net tablosu yok:
    # ad dogrudan pad'in icinde durur.
    for pad in children(node, "pad"):
        number = str(pad[1]).strip('"') if len(pad) > 1 else ""
        net = item.nets.get(number, "")
        pad.append(["uuid", _uuid()])
        if net:
            pad.append(["net", _q(net)])

    if item.units:
        node.append([
            "units",
            *[["unit", ["name", _q(name)], ["pins", *[_q(p) for p in pins]]]
              for name, pins in sorted(item.units.items())],
        ])

    for prop in children(node, "property"):
        if not child(prop, "uuid"):
            prop.append(["uuid", _uuid()])
    return node


# --------------------------------------------------------------------------
# Plan + uygulama
# --------------------------------------------------------------------------


def plan_sync(
    sch_path: Path | str,
    pcb_path: Path | str,
    *,
    kicad_cli: str | None = None,
) -> tuple[SyncPlan, list]:
    """Karta neyin ekleneceğini hesaplar; DOSYAYA DOKUNMAZ."""
    sch_path, pcb_path = Path(sch_path), Path(pcb_path)
    schematic = read_schematic(sch_path)
    plan = SyncPlan(sch=sch_path, pcb=pcb_path)

    root, stray = parse_with_stats(pcb_path.read_text(encoding="utf-8", errors="replace"))
    if stray:
        raise PcbSyncError(f"{pcb_path.name} bozuk gorunuyor ({stray} kacak parantez)")

    try:
        conn = connectivity_of(sch_path, kicad_cli)
    except SchVerifyError as exc:
        raise PcbSyncError(f"netlist alinamadi: {exc}") from exc

    have_paths = set(board_paths(root))
    have_refs = board_refs(root)

    # Bilesenler REFERANSA gore gruplanir. Cok birimli bir sembol (74LS125 ->
    # U7A, U7B...) sematikte birden cok sembol dugumudur ama kartta TEK
    # fiziksel paketle karsilanir. Grupla(ma)mak, olculdu: U7 karta iki kez
    # gidiyordu ve KiCad paritesi haklı olarak sikayet ediyordu.
    by_ref: dict[str, list] = {}
    for sym in schematic.real_symbols:
        by_ref.setdefault(sym.ref, []).append(sym)

    missing: list[NewFootprint] = []
    for ref, units in by_ref.items():
        units = sorted(units, key=lambda s: s.unit)
        first = units[0]
        try:
            path = symbol_path(schematic, ref)
        except KeyError:
            continue
        if path in have_paths or ref in have_refs:
            continue
        if not first.footprint:
            plan.without_footprint.append(ref)
            continue
        nets = {pin: net for (r, pin), net in conn.net_of.items() if r == ref}
        carried = {
            name: value
            for name, value in first.properties.items()
            # `ki_*` kutuphaneye ait; Reference/Value/Footprint zaten yazildi.
            if not name.startswith("ki_")
            and name not in ("Reference", "Value", "Footprint")
        }
        unit_pins = {
            chr(64 + sym.unit): [p.number for p in sym.pins]
            for sym in units
        }
        missing.append(
            NewFootprint(ref=ref, footprint_id=first.footprint, value=first.value,
                         path=path, nets=nets, properties=carried, units=unit_pins)
        )

    if missing:
        positions, note = free_positions(pcb_path, len(missing))
        for item, (x, y) in zip(missing, positions):
            item.x, item.y = x, y
        plan.notes.append(note)

    project_dir = sch_path.parent
    for item in missing:
        if not symlib.footprint_exists(item.footprint_id, project_dir, kicad_cli):
            plan.problems.append(
                f"{item.ref}: footprint bulunamadi ({item.footprint_id})"
            )
    plan.add = missing
    return plan, root


def sync(
    sch_path: Path | str,
    pcb_path: Path | str,
    *,
    apply: bool = False,
    backup: bool = True,
    allow_open_project: bool = False,
    force: bool = False,
    kicad_cli: str | None = None,
) -> SyncResult:
    """Sematikte olup kartta olmayan bilesenleri karta ekler.

    Varsayilan DRY-RUN. Yazdiktan sonra kart geri okunur ve eklenen her
    bilesen gercekten orada mi, pad agları dogru mu diye bakilir - yazip
    gormemek en kotu sonuc olurdu.
    """
    sch_path, pcb_path = Path(sch_path), Path(pcb_path)
    plan, root = plan_sync(sch_path, pcb_path, kicad_cli=kicad_cli)
    if not plan.ok and not force:
        return SyncResult(plan=plan, applied=False)
    if not plan.add:
        return SyncResult(plan=plan, applied=False)

    schematic = read_schematic(sch_path)
    for item in plan.add:
        sheet_file = sch_path.name
        sheet_name = "/"
        for sym in sorted(schematic.symbols, key=lambda s: s.unit):
            if sym.ref == item.ref:
                file_path = schematic.file_of_sheet.get(sym.sheet_path)
                sheet_file = file_path.name if file_path else sch_path.name
                sheet_name = sym.sheet_path
                break
        root.append(
            build_footprint_node(item, sheet_file, sheet_name,
                                 kicad_cli=kicad_cli, project_dir=sch_path.parent)
        )

    write = write_tree(pcb_path, root, apply=apply, backup=backup,
                       allow_open_project=allow_open_project)
    result = SyncResult(plan=plan, write=write, applied=write.written)

    if write.written:
        board = read_board(pcb_path)
        for item in plan.add:
            comp = board.by_ref(item.ref)
            if comp is None:
                result.plan.problems.append(f"{item.ref} yazildi ama geri okunamadi")
                continue
            wrong = [
                f"{p.number}: {p.net or '(bos)'} != {item.nets.get(p.number, '')}"
                for p in comp.pads
                if item.nets.get(p.number, "") and p.net != item.nets[p.number]
            ]
            if wrong:
                result.plan.problems.append(f"{item.ref} pad agi yanlis: {', '.join(wrong)}")
            else:
                result.verified.append(item.ref)
    return result


# --------------------------------------------------------------------------
# Komut satiri
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pcbqa.pcb_sync",
        description="Sematikte olup kartta olmayan bilesenleri karta ekler.",
    )
    ap.add_argument("--sch", type=Path, required=True, help="Kok .kicad_sch dosyasi")
    ap.add_argument("--pcb", type=Path, default=None,
                    help="Kart dosyasi (varsayilan: ayni adli .kicad_pcb)")
    ap.add_argument("--apply", action="store_true", help="Dosyaya gercekten yaz")
    ap.add_argument("--no-backup", action="store_true", help="Yedek alma")
    ap.add_argument("--force", action="store_true", help="Engelleri yok say")
    ap.add_argument("--allow-open-project", action="store_true", help="KiCad acikken de yaz")
    ap.add_argument("--kicad-cli", default=None)
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    pcb = args.pcb or args.sch.with_suffix(".kicad_pcb")
    if not pcb.exists():
        print(f"hata: kart dosyasi yok: {pcb}", file=sys.stderr)
        return 2

    try:
        result = sync(args.sch, pcb, apply=args.apply, backup=not args.no_backup,
                      force=args.force, allow_open_project=args.allow_open_project,
                      kicad_cli=args.kicad_cli)
    except (PcbSyncError, SchWriteError, symlib.SymLibError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 1

    print(result.plan.describe())
    if result.applied:
        print(f"  yazildi: {result.write.path}"
              + (f" (yedek: {result.write.backup.name})" if result.write.backup else ""))
        print(f"  dogrulandi: {len(result.verified)}/{len(result.plan.add)} bilesen"
              " karttan geri okundu, pad aglari sematikle ayni")
    elif not args.apply:
        print("  (dry-run - yazmak icin --apply)")
    return 0 if (result.plan.ok and (result.applied or not args.apply)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
