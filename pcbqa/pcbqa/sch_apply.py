"""Toplu sematik yerlestirme uygulayici (Asama 4e).

`sch_move` tek bir sembolu tasir ve her cagrida kalkani (iki `kicad-cli`
ihracati, ~2-4 sn) calistirir. Bir sayfada 30 sembol tasimak bu yolla
dakikalar surer ve ara adimlarda gecici olarak bozuk durumlar olusur.

Bu modul tersini yapar: TUM tasimalari agac uzerinde uygular, kalkani BIR KEZ
kosturur, dosyalari BIR KEZ yazar. `sch_place.improve` ciktisi (uuid ->
(x, y)) dogrudan buraya verilir.

## Suruklenen ogeler

Bir sembol tasindiginda pinlerine degen her sey ayni delta ile gider: tel
uclari, junction ve no_connect isaretleri, etiketler. Bir nokta birden fazla
tasinan sembolun pinine denk geliyorsa ve deltalari FARKLIYSA o noktayi nereye
goturecegimiz belirsizdir - boyle bir durum catisma sayilir ve uygulama
reddedilir.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .schematic import GRID_MM, Schematic, read_schematic
from .sch_place import SchPlacement, changed_only, improve
from .sch_verify import ConnectivityDiff, SchVerifyError, compare, connectivity_of
from .sch_write import SchWriteError, WriteResult, write_tree
from .sexpr import as_float, child, children, dumps, head, parse_with_stats

EPS = 1e-4


class SchApplyError(RuntimeError):
    """Toplu uygulama planlanamadi veya reddedildi."""


def _same(a: float, b: float) -> bool:
    return abs(a - b) < EPS


def _pt(x: float, y: float) -> tuple[float, float]:
    return (round(x, 3), round(y, 3))


@dataclass
class ApplyPlan:
    sheet_path: str
    file: Path
    moves: int = 0
    wire_endpoints: int = 0
    points: int = 0
    labels: int = 0
    conflicts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.conflicts


@dataclass
class ApplyResult:
    plans: list[ApplyPlan]
    diff: ConnectivityDiff | None = None
    writes: list[WriteResult] = field(default_factory=list)
    applied: bool = False

    @property
    def ok(self) -> bool:
        return all(p.ok for p in self.plans)

    @property
    def total_moves(self) -> int:
        return sum(p.moves for p in self.plans)


def _drag_map(
    schematic: Schematic,
    placement: SchPlacement,
    sheet_path: str,
    plan: ApplyPlan,
) -> dict[tuple[float, float], tuple[float, float]]:
    """Tasinan sembollerin pin konumlarindan `nokta -> delta` tablosu kurar.

    Ayni nokta farkli deltalarla iki kez talep edilirse catisma yazilir.
    """
    drag: dict[tuple[float, float], tuple[float, float]] = {}
    for sym in schematic.symbols:
        if sym.sheet_path != sheet_path or sym.uuid not in placement:
            continue
        nx, ny = placement[sym.uuid]
        delta = (round(nx - sym.x, 4), round(ny - sym.y, 4))
        if _same(delta[0], 0.0) and _same(delta[1], 0.0):
            continue
        for pin in sym.pins:
            point = _pt(pin.x, pin.y)
            existing = drag.get(point)
            if existing is not None and not (
                _same(existing[0], delta[0]) and _same(existing[1], delta[1])
            ):
                plan.conflicts.append(
                    f"({point[0]:g}, {point[1]:g}) noktasi iki farkli yone cekiliyor "
                    f"({existing} ve {delta}); {sym.ref} dahil"
                )
            drag[point] = delta
    return drag


def _edit_sheet(root, schematic: Schematic, placement: SchPlacement, plan: ApplyPlan) -> None:
    """Bir sayfa dosyasinin agacinda tum tasimalari uygular."""
    deltas = {}
    for sym in schematic.symbols:
        if sym.sheet_path != plan.sheet_path or sym.uuid not in placement:
            continue
        nx, ny = placement[sym.uuid]
        delta = (round(nx - sym.x, 4), round(ny - sym.y, 4))
        if not (_same(delta[0], 0.0) and _same(delta[1], 0.0)):
            deltas[sym.uuid] = delta

    drag = _drag_map(schematic, placement, plan.sheet_path, plan)
    if not plan.ok:
        return

    def shift(node, dx: float, dy: float) -> bool:
        at = child(node, "at")
        if at is None or len(at) < 3:
            return False
        at[1] = f"{round(as_float(at[1]) + dx, 4):g}"
        at[2] = f"{round(as_float(at[2]) + dy, 4):g}"
        return True

    for node in root:
        if not isinstance(node, list) or not node:
            continue
        tag = head(node)

        if tag == "symbol":
            uuid_node = child(node, "uuid")
            uuid = str(uuid_node[1]) if uuid_node and len(uuid_node) > 1 else ""
            delta = deltas.get(uuid)
            if delta is None:
                continue
            shift(node, *delta)
            for prop in children(node, "property"):
                shift(prop, *delta)
            plan.moves += 1

        elif tag == "wire":
            pts = child(node, "pts")
            for xy in children(pts, "xy") if pts else []:
                delta = drag.get(_pt(as_float(xy[1]), as_float(xy[2])))
                if delta is None:
                    continue
                xy[1] = f"{round(as_float(xy[1]) + delta[0], 4):g}"
                xy[2] = f"{round(as_float(xy[2]) + delta[1], 4):g}"
                plan.wire_endpoints += 1

        elif tag in ("junction", "no_connect", "label", "global_label", "hierarchical_label"):
            at = child(node, "at")
            if at is None or len(at) < 3:
                continue
            delta = drag.get(_pt(as_float(at[1]), as_float(at[2])))
            if delta is None:
                continue
            shift(node, *delta)
            if tag in ("junction", "no_connect"):
                plan.points += 1
            else:
                plan.labels += 1


def apply_placement(
    sch_path: Path | str,
    placement: SchPlacement,
    *,
    sheet_path: str = "/",
    apply: bool = False,
    verify: bool = True,
    force: bool = False,
    backup: bool = True,
    allow_open_project: bool = False,
    kicad_cli: str | None = None,
) -> ApplyResult:
    """Bir yerlestirmenin tamamini uygular. Varsayilan DRY-RUN.

    Kalkan BIR KEZ calisir: tum tasimalar uygulandiktan sonra.
    """
    schematic = read_schematic(sch_path)
    file_path = schematic.file_of_sheet.get(sheet_path)
    if file_path is None:
        raise SchApplyError(f"sayfa bulunamadi: {sheet_path}")

    shared = schematic.sheets_sharing_a_file()
    plan = ApplyPlan(sheet_path=sheet_path, file=file_path)
    if file_path in shared:
        plan.conflicts.append(
            f"{file_path.name} birden fazla sayfada kullaniliyor "
            f"({', '.join(shared[file_path])}); duzenlemek hepsini etkiler"
        )

    root, stray = parse_with_stats(file_path.read_text(encoding="utf-8"))
    if stray:
        raise SchApplyError(f"{file_path.name} bozuk gorunuyor ({stray} kacak parantez)")

    _edit_sheet(root, schematic, placement, plan)
    result = ApplyResult(plans=[plan])

    if not plan.ok and not force:
        return result
    if plan.moves == 0:
        plan.warnings.append("tasinacak sembol yok")
        return result

    new_text = dumps(root) + "\n"

    if verify:
        with tempfile.TemporaryDirectory(prefix="pcbqa-sandbox-") as tmp:
            source_dir = schematic.root_path.parent
            sandbox_dir = Path(tmp) / source_dir.name
            shutil.copytree(source_dir, sandbox_dir, dirs_exist_ok=True)
            relative = file_path.relative_to(source_dir)
            (sandbox_dir / relative).write_text(new_text, encoding="utf-8")
            try:
                before = connectivity_of(schematic.root_path, kicad_cli)
                after = connectivity_of(sandbox_dir / schematic.root_path.name, kicad_cli)
                result.diff = compare(before, after)
            except SchVerifyError as exc:
                raise SchApplyError(f"kalkan calistirilamadi: {exc}") from exc

        if not result.diff.ok and not force:
            return result

    write = write_tree(
        file_path, root, apply=apply, backup=backup, allow_open_project=allow_open_project
    )
    result.writes.append(write)
    result.applied = write.written
    return result


def optimize_and_apply(
    sch_path: Path | str,
    *,
    sheet_path: str = "/",
    budget_s: float = 20.0,
    seed: int = 0,
    apply: bool = False,
    **kwargs,
):
    """`improve` + `apply_placement` kisayolu.

    `(placement, once, sonra, sonuc)` dondurur.
    """
    schematic = read_schematic(sch_path)
    placement, before, after = improve(schematic, sheet_path, budget_s=budget_s, seed=seed)
    moves = changed_only(schematic, placement, sheet_path)
    result = apply_placement(sch_path, moves, sheet_path=sheet_path, apply=apply, **kwargs)
    return moves, before, after, result


# --------------------------------------------------------------------------
# Komut satiri
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pcbqa.sch_apply",
        description="Sematik sayfasinin yerlesimini iyilestirir ve uygular.",
    )
    ap.add_argument("--sch", type=Path, required=True, help="Kok .kicad_sch dosyasi")
    ap.add_argument("--sheet", default="/", help="Sayfa yolu (varsayilan kok)")
    ap.add_argument("--budget", type=float, default=20.0, help="Saniye cinsinden sure butcesi")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--apply", action="store_true", help="Dosyaya gercekten yaz")
    ap.add_argument("--no-verify", action="store_true", help="Netlist kalkanini atla (onerilmez)")
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--force", action="store_true", help="Catismalari ve kalkan reddini yok say")
    ap.add_argument("--allow-open-project", action="store_true")
    ap.add_argument("--kicad-cli", default=None)
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)

    try:
        moves, before, after, result = optimize_and_apply(
            args.sch,
            sheet_path=args.sheet,
            budget_s=args.budget,
            seed=args.seed,
            apply=args.apply,
            verify=not args.no_verify,
            force=args.force,
            backup=not args.no_backup,
            allow_open_project=args.allow_open_project,
            kicad_cli=args.kicad_cli,
        )
    except (SchApplyError, SchWriteError, SchVerifyError, FileNotFoundError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2

    plan = result.plans[0]
    print()
    print(f"  sayfa {args.sheet}  ({plan.file.name})")
    print(f"  ONCE : skor {before.score:5.1f}  hata {before.errors}  uyari {before.warnings}"
          f"  tel {before.total_hpwl_mm:,.1f} mm")
    print(f"  SONRA: skor {after.score:5.1f}  hata {after.errors}  uyari {after.warnings}"
          f"  tel {after.total_hpwl_mm:,.1f} mm")
    gain = before.total_hpwl_mm - after.total_hpwl_mm
    print(f"  kazanc: skor {after.score - before.score:+.1f}  tel {gain:+,.1f} mm")
    print(f"  tasinan: {len(moves)} sembol  "
          f"[tel ucu {plan.wire_endpoints}, junction/no-connect {plan.points}, etiket {plan.labels}]")

    for note in plan.warnings:
        print(f"  uyari: {note}")

    if plan.conflicts:
        print()
        for conflict in plan.conflicts:
            print(f"  CATISMA: {conflict}")
        if not args.force:
            print("\n  uygulanmadi (--force ile zorlanabilir)")
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
                print("\n  uygulanmadi - baglanti bozulurdu")
                return 1

    print()
    if result.applied:
        write = result.writes[0]
        print(f"  UYGULANDI: {write.bytes_written:,} bayt yazildi")
        if write.backup:
            print(f"  yedek: {write.backup.name}")
    else:
        print("  DRY-RUN: dosyaya dokunulmadi (--apply ile yazilir)")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
