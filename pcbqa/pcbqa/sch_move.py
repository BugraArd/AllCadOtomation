"""Baglanti koruyan sembol tasima (Asama 4d).

Sematikte baglanti GEOMETRIKTIR. Bir sembolu kaydirip birakmak, pinlerine
degen tel uclarini yerinde birakir ve baglanti SESSIZCE kopar - olculdu:
`pic_programmer` uzerinde R1'i tek izgara adimi (1.27 mm) kaydirmak bile
pin 1'i `unconnected-(R1-Pad1)` yapiyor.

Bu modul sembolu tasirken ona TUTUNAN her seyi birlikte tasir:

  * pinlerine degen tel uclari (telin diger ucu yerinde kalir -> tel uzar
    veya kisalir)
  * pin konumundaki junction ve no_connect isaretleri
  * pin konumundaki etiketler
  * sembolun kendi property konumlari (referans, deger, footprint metinleri)

## Tasinamayan durum: dogrudan pin-pine temas

Iki sembolun pini araya tel girmeden birbirine degiyorsa (guc sembolleri
cogunlukla boyle baglanir), birini tasimak baglantiyi koparir ve uzatilacak
bir tel de yoktur. Bu durumda tasima REDDEDILIR; cozum ya ikisini birlikte
tasimak ya da once aralarina tel koymaktir.

## Son soz kalkanindir

Geometrik akil yurutme her seyi yakalayamaz: tasinan bir tel ucu baska bir
telin ortasindan gecebilir, ustune oturabilir, bir etiketi yakalayabilir.
Bu yuzden yazma oncesi degisiklik bir kum havuzunda uygulanir ve
`sch_verify` ile netlist karsilastirilir. Kalkan gecmezse yazma yapilmaz.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .schematic import GRID_MM, Schematic, read_schematic
from .sch_verify import ConnectivityDiff, SchVerifyError, compare, connectivity_of
from .sch_write import SchWriteError, WriteResult, lock_files, write_tree
from .sexpr import as_float, child, children, dumps, head, parse_with_stats

# Konum esitligi toleransi (mm). KiCad konumlari 4 haneye yuvarlar.
EPS = 1e-4


class SchMoveError(RuntimeError):
    """Tasima planlanamadi veya reddedildi."""


@dataclass
class MovePlan:
    """Bir tasimanin ne yapacaginin dokumu."""

    ref: str
    sheet_path: str
    file: Path
    dx: float
    dy: float
    old_pos: tuple[float, float]
    new_pos: tuple[float, float]
    wire_endpoints: int = 0
    junctions: int = 0
    no_connects: int = 0
    labels: int = 0
    properties: int = 0
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blockers

    def describe(self) -> str:
        return (
            f"{self.ref}: ({self.old_pos[0]:g}, {self.old_pos[1]:g}) -> "
            f"({self.new_pos[0]:g}, {self.new_pos[1]:g})  "
            f"[tel ucu {self.wire_endpoints}, junction {self.junctions}, "
            f"no-connect {self.no_connects}, etiket {self.labels}, "
            f"property {self.properties}]"
        )


@dataclass
class MoveResult:
    plan: MovePlan
    diff: ConnectivityDiff | None = None
    write: WriteResult | None = None
    applied: bool = False


def _same(a: float, b: float) -> bool:
    return abs(a - b) < EPS


def _snap(value: float, grid: float) -> float:
    return round(round(value / grid) * grid, 4)


def _at_of(node) -> list | None:
    return child(node, "at")


def _symbol_ref(node) -> str:
    for p in children(node, "property"):
        if len(p) > 2 and str(p[1]) == "Reference" and not isinstance(p[2], list):
            return str(p[2])
    return ""


def _shift_at(node, dx: float, dy: float) -> bool:
    """Bir `(at x y [rot])` dugumunu kaydirir."""
    at = _at_of(node)
    if at is None or len(at) < 3:
        return False
    at[1] = f"{round(as_float(at[1]) + dx, 4):g}"
    at[2] = f"{round(as_float(at[2]) + dy, 4):g}"
    return True


def plan_move(
    schematic: Schematic,
    ref: str,
    dx: float,
    dy: float,
    *,
    snap: bool = True,
    sheet_path: str | None = None,
) -> MovePlan:
    """Tasimayi planlar; dosyaya dokunmaz.

    `snap` verilirse sembol izgaraya oturtulur ve GERCEKLESEN kaydirma
    miktari ona gore yeniden hesaplanir - tel uclari da ayni miktarda
    kaydirilmali, yoksa pinden kopar.
    """
    matches = [
        s
        for s in schematic.symbols
        if s.ref == ref and (sheet_path is None or s.sheet_path == sheet_path)
    ]
    if not matches:
        raise SchMoveError(f"{ref} bulunamadi")
    if len({s.sheet_path for s in matches}) > 1:
        sheets = ", ".join(sorted({s.sheet_path for s in matches}))
        raise SchMoveError(f"{ref} birden fazla sayfada var ({sheets}); sheet_path verin")

    symbol = matches[0]
    file_path = schematic.file_of_sheet.get(symbol.sheet_path)
    if file_path is None:
        raise SchMoveError(f"{ref} icin sayfa dosyasi bulunamadi ({symbol.sheet_path})")

    target_x, target_y = symbol.x + dx, symbol.y + dy
    if snap:
        target_x, target_y = _snap(target_x, GRID_MM), _snap(target_y, GRID_MM)
    real_dx = round(target_x - symbol.x, 4)
    real_dy = round(target_y - symbol.y, 4)

    plan = MovePlan(
        ref=ref,
        sheet_path=symbol.sheet_path,
        file=file_path,
        dx=real_dx,
        dy=real_dy,
        old_pos=(symbol.x, symbol.y),
        new_pos=(target_x, target_y),
    )

    if _same(real_dx, 0.0) and _same(real_dy, 0.0):
        plan.warnings.append("kaydirma sifir (izgaraya oturtuldu); degisiklik yok")
        return plan

    if len(matches) > 1:
        plan.warnings.append(f"{ref} icin {len(matches)} birim var; hepsi ayni sayfada")

    shared = schematic.sheets_sharing_a_file()
    if file_path in shared:
        plan.blockers.append(
            f"{file_path.name} birden fazla sayfada kullaniliyor "
            f"({', '.join(shared[file_path])}); duzenlemek hepsini etkiler"
        )

    # Bu sembolun pin konumlari
    pin_points = [(round(p.x, 4), round(p.y, 4)) for s in matches for p in s.pins]

    # Ayni sayfadaki DIGER sembollerin pinleri -> dogrudan temas riski
    for other in schematic.symbols:
        if other.sheet_path != symbol.sheet_path or other.ref == ref:
            continue
        for opin in other.pins:
            for px, py in pin_points:
                if _same(opin.x, px) and _same(opin.y, py):
                    plan.blockers.append(
                        f"{ref} pini {other.ref}.{opin.number} ile dogrudan temas halinde "
                        f"({px:g}, {py:g}); arada tel yok, tasima baglantiyi koparir"
                    )

    # Tutunan ogeleri say (gercek tasima apply_move icinde)
    plan.properties = sum(len(s.properties) for s in matches)
    for wire in schematic.wires:
        if wire.sheet_path != symbol.sheet_path:
            continue
        for wx, wy in wire.endpoints:
            if any(_same(wx, px) and _same(wy, py) for px, py in pin_points):
                plan.wire_endpoints += 1
    for point in schematic.junctions:
        if point.sheet_path == symbol.sheet_path and any(
            _same(point.x, px) and _same(point.y, py) for px, py in pin_points
        ):
            plan.junctions += 1
    for point in schematic.no_connects:
        if point.sheet_path == symbol.sheet_path and any(
            _same(point.x, px) and _same(point.y, py) for px, py in pin_points
        ):
            plan.no_connects += 1
    for label in schematic.labels:
        if label.sheet_path == symbol.sheet_path and any(
            _same(label.x, px) and _same(label.y, py) for px, py in pin_points
        ):
            plan.labels += 1

    return plan


def _edit_tree(root, schematic: Schematic, plan: MovePlan, uuids: set[str]) -> MovePlan:
    """Agac uzerinde tasimayi uygular ve plani gercek sayimlarla gunceller."""
    dx, dy = plan.dx, plan.dy

    symbols = [s for s in schematic.symbols if s.ref == plan.ref and s.sheet_path == plan.sheet_path]
    pin_points = [(round(p.x, 4), round(p.y, 4)) for s in symbols for p in s.pins]

    def at_pin(node) -> bool:
        at = _at_of(node)
        if at is None or len(at) < 3:
            return False
        x, y = as_float(at[1]), as_float(at[2])
        return any(_same(x, px) and _same(y, py) for px, py in pin_points)

    moved_props = 0
    moved_symbols = 0
    for node in root:
        if not isinstance(node, list) or not node:
            continue
        tag = head(node)

        if tag == "symbol":
            # UUID ile eslestir: referans metni ayni olan baska bir sembolu
            # yanlislikla tasimamak icin en guvenilir kimlik odur. UUID yoksa
            # (elle duzenlenmis dosyalar) referansa duseriz.
            uuid_node = child(node, "uuid")
            uuid = str(uuid_node[1]) if uuid_node and len(uuid_node) > 1 else ""
            is_target = uuid in uuids if uuid else _symbol_ref(node) == plan.ref
            if not is_target:
                continue
            _shift_at(node, dx, dy)
            moved_symbols += 1
            # Metin alanlari da sembolle birlikte gitmeli
            for prop in children(node, "property"):
                if _shift_at(prop, dx, dy):
                    moved_props += 1

        elif tag == "wire":
            pts = child(node, "pts")
            for xy in children(pts, "xy") if pts else []:
                x, y = as_float(xy[1]), as_float(xy[2])
                if any(_same(x, px) and _same(y, py) for px, py in pin_points):
                    xy[1] = f"{round(x + dx, 4):g}"
                    xy[2] = f"{round(y + dy, 4):g}"

        elif tag in ("junction", "no_connect", "label", "global_label", "hierarchical_label"):
            if at_pin(node):
                _shift_at(node, dx, dy)

    plan.properties = moved_props
    if moved_symbols == 0:
        raise SchMoveError(f"{plan.ref} dosyada bulunamadi ({plan.file.name})")

    # Sifir uzunluklu tel olustu mu?
    degenerate = 0
    for node in root:
        if isinstance(node, list) and head(node) == "wire":
            pts = child(node, "pts")
            xys = list(children(pts, "xy")) if pts else []
            if len(xys) >= 2:
                if _same(as_float(xys[0][1]), as_float(xys[-1][1])) and _same(
                    as_float(xys[0][2]), as_float(xys[-1][2])
                ):
                    degenerate += 1
    if degenerate:
        plan.warnings.append(f"{degenerate} tel sifir uzunluga dustu")
    return plan


def _sandbox_copy(schematic: Schematic, tmp: Path) -> Path:
    """Projeyi gecici bir dizine kopyalar; kok sematigin yeni yolunu dondurur.

    Kalkan `kicad-cli` calistirir ve o da alt sayfalari, sembol tablolarini
    diskten okur - bu yuzden tek dosya degil, proje klasoru kopyalanir.
    """
    source_dir = schematic.root_path.parent
    target_dir = tmp / source_dir.name
    shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
    return target_dir / schematic.root_path.name


def apply_move(
    sch_path: Path | str,
    ref: str,
    dx: float,
    dy: float,
    *,
    apply: bool = False,
    snap: bool = True,
    sheet_path: str | None = None,
    verify: bool = True,
    force: bool = False,
    backup: bool = True,
    allow_open_project: bool = False,
    kicad_cli: str | None = None,
) -> MoveResult:
    """Bir sembolu, tutundugu her seyle birlikte tasir.

    Varsayilan DRY-RUN'dir. `verify` acikken degisiklik once bir kum
    havuzunda uygulanip netlist karsilastirilir; baglanti degistiyse yazma
    yapilmaz (`force=True` bu reddi devre disi birakir).
    """
    schematic = read_schematic(sch_path)
    plan = plan_move(schematic, ref, dx, dy, snap=snap, sheet_path=sheet_path)

    if not plan.ok and not force:
        return MoveResult(plan=plan, applied=False)
    if _same(plan.dx, 0.0) and _same(plan.dy, 0.0):
        return MoveResult(plan=plan, applied=False)

    uuids = {
        s.uuid
        for s in schematic.symbols
        if s.ref == ref and s.sheet_path == plan.sheet_path and s.uuid
    }

    root, stray = parse_with_stats(plan.file.read_text(encoding="utf-8"))
    if stray:
        raise SchMoveError(
            f"{plan.file.name} bozuk gorunuyor ({stray} kacak parantez); yazma yapilmadi"
        )
    _edit_tree(root, schematic, plan, uuids)
    new_text = dumps(root) + "\n"

    diff: ConnectivityDiff | None = None
    if verify:
        with tempfile.TemporaryDirectory(prefix="pcbqa-sandbox-") as tmp:
            sandbox_root = _sandbox_copy(schematic, Path(tmp))
            relative = plan.file.relative_to(schematic.root_path.parent)
            (sandbox_root.parent / relative).write_text(new_text, encoding="utf-8")
            try:
                before = connectivity_of(schematic.root_path, kicad_cli)
                after = connectivity_of(sandbox_root, kicad_cli)
                diff = compare(before, after)
            except SchVerifyError as exc:
                raise SchMoveError(f"kalkan calistirilamadi: {exc}") from exc

        if not diff.ok and not force:
            return MoveResult(plan=plan, diff=diff, applied=False)

    write = write_tree(
        plan.file,
        root,
        apply=apply,
        backup=backup,
        allow_open_project=allow_open_project,
    )
    return MoveResult(plan=plan, diff=diff, write=write, applied=write.written)


# --------------------------------------------------------------------------
# Komut satiri
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pcbqa.sch_move",
        description="Sematikte bir sembolu baglantisini koruyarak tasir.",
    )
    ap.add_argument("--sch", type=Path, required=True, help="Kok .kicad_sch dosyasi")
    ap.add_argument("--ref", required=True, help="Tasinacak sembolun referansi (or. R1)")
    ap.add_argument("--dx", type=float, default=0.0, help="X kaydirmasi (mm)")
    ap.add_argument("--dy", type=float, default=0.0, help="Y kaydirmasi (mm)")
    ap.add_argument("--sheet", default=None, help="Sembol birden fazla sayfadaysa sayfa yolu")
    ap.add_argument("--apply", action="store_true", help="Dosyaya gercekten yaz (varsayilan dry-run)")
    ap.add_argument("--no-snap", action="store_true", help="Izgaraya oturtma")
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

    try:
        result = apply_move(
            args.sch,
            args.ref,
            args.dx,
            args.dy,
            apply=args.apply,
            snap=not args.no_snap,
            sheet_path=args.sheet,
            verify=not args.no_verify,
            force=args.force,
            backup=not args.no_backup,
            allow_open_project=args.allow_open_project,
            kicad_cli=args.kicad_cli,
        )
    except (SchMoveError, SchWriteError, SchVerifyError, FileNotFoundError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2

    plan = result.plan
    print()
    print(f"  {plan.describe()}")
    print(f"  dosya: {plan.file}")

    for note in plan.warnings:
        print(f"  uyari: {note}")

    if plan.blockers:
        print()
        for blocker in plan.blockers:
            print(f"  ENGEL: {blocker}")
        if not args.force:
            print()
            print("  tasima yapilmadi (--force ile zorlanabilir)")
            return 1

    if result.diff is not None:
        print()
        if result.diff.ok:
            print("  KALKAN: baglanti degismedi")
        else:
            print(f"  KALKAN: {result.diff.describe()}")
            for line in result.diff.details(limit=8):
                print(f"  {line}")
            if not args.force:
                print()
                print("  tasima yapilmadi - baglanti bozulurdu")
                return 1

    print()
    if result.applied:
        print(f"  UYGULANDI: {result.write.bytes_written:,} bayt yazildi")
        if result.write.backup:
            print(f"  yedek: {result.write.backup.name}")
    else:
        print("  DRY-RUN: dosyaya dokunulmadi (--apply ile yazilir)")
    for note in (result.write.notes if result.write else []):
        print(f"  {note}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
