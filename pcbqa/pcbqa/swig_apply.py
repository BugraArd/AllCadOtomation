"""API'SIZ BAGLANTI - yerlesimi KiCad'in SUREC-ICI Python'undan uygular.

`ipc.py` calisan KiCad'e disaridan, IPC API sunucusu uzerinden baglanir. O
sunucu KiCad'de VARSAYILAN OLARAK KAPALI (`kicad_common.json` -> `api`:
`"enable_server": false`), yani her son kullanicidan Tercihler'e girip acmasi
beklenir. Dagitilacak bir uygulama ya da eklenti icin bu kabul edilemez bir
kurulum adimidir.

Bu modul ayni isi API'siz yapar: KiCad'in kendi icinde calisan Python'dan,
`pcbnew` (SWIG) baglamalariyla. Kurulum adimi yoktur - `pcbnew` KiCad ile
birlikte gelir.

## Nerede calisir

    KiCad 10.0 python 3.11.5 : pcbnew VAR, pyyaml YOK
    proje .venv    python 3.13 : pcbnew YOK, pyyaml VAR

Yani bu modul YALNIZCA KiCad'in yorumlayicisinda calisir. Paketin geri kalani
oraya `confload.py` sayesinde tasinabiliyor (YAML artik istege bagli).
Kurulumsuz dogrulama: GUI olmadan da kosar -

    pcbnew.LoadBoard(yol) -> 63 footprint  (olculdu, pic_programmer)

yani bu yol GUI acmadan bastan sona test edilebilir.

## Sozlesme `ipc.py` ile AYNI

Ayni `Placement` (ref -> x_mm, y_mm, aci) girer, ayni ozet cikar: varsayilan
DRY-RUN, KiCad'de kilitli footprint'e dokunulmaz, tekrar eden referansta
durulur, ve yazdiktan sonra kart GERI OKUNUP dogrulanir. Iki yol arasinda
davranis farki olsaydi hangisinin kullanildigi sonuca karisirdi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .placement.base import Placement

NM_PER_MM = 1_000_000.0


class SwigApplyError(RuntimeError):
    """Yerlesim surec-ici API ile uygulanamadi."""


@dataclass
class SwigApplySummary:
    """`ipc.IpcApplySummary` ile ayni alanlar - iki yol karsilastirilabilir olsun."""

    board_name: str
    kicad_version: str = ""
    requested: int = 0
    changed: int = 0
    unchanged: int = 0
    missing_refs: list[str] = field(default_factory=list)
    skipped_locked_refs: list[str] = field(default_factory=list)
    duplicate_refs: list[str] = field(default_factory=list)
    applied_refs: list[str] = field(default_factory=list)
    verify_errors: list[str] = field(default_factory=list)
    dry_run: bool = True
    saved: bool = False

    @property
    def ok(self) -> bool:
        return not self.duplicate_refs and not self.verify_errors

    def describe(self) -> str:
        lines = [f"kart: {self.board_name}"
                 + (f"  (KiCad {self.kicad_version})" if self.kicad_version else "")]
        lines.append(
            f"  istenen {self.requested}, degisen {self.changed}, "
            f"zaten yerinde {self.unchanged}"
        )
        if self.missing_refs:
            lines.append(f"  kartta yok: {', '.join(self.missing_refs[:8])}")
        if self.skipped_locked_refs:
            lines.append(f"  kilitli, dokunulmadi: {', '.join(self.skipped_locked_refs[:8])}")
        for problem in self.verify_errors:
            lines.append(f"  DOGRULAMA HATASI: {problem}")
        if self.dry_run:
            lines.append("  (dry-run - uygulamak icin apply=True)")
        elif self.saved:
            lines.append("  kart kaydedildi")
        return "\n".join(lines)

    def as_dict(self) -> dict[str, Any]:
        return {
            "board_name": self.board_name,
            "kicad_version": self.kicad_version,
            "requested": self.requested,
            "changed": self.changed,
            "unchanged": self.unchanged,
            "missing_refs": list(self.missing_refs),
            "skipped_locked_refs": list(self.skipped_locked_refs),
            "duplicate_refs": list(self.duplicate_refs),
            "applied_refs": list(self.applied_refs),
            "verify_errors": list(self.verify_errors),
            "dry_run": self.dry_run,
            "saved": self.saved,
            "ok": self.ok,
        }


# --------------------------------------------------------------------------
# pcbnew erisimi
# --------------------------------------------------------------------------


def load_pcbnew():
    """`pcbnew` modulu. Yanlis yorumlayicida acikca soyler."""
    try:
        import pcbnew  # type: ignore
    except ModuleNotFoundError as exc:
        raise SwigApplyError(
            "pcbnew bulunamadi - bu modul KiCad'in KENDI Python'unda calisir. "
            "Ornek: \"C:\\Program Files\\KiCad\\10.0\\bin\\python.exe\" -m ... "
            "(proje .venv'inde pcbnew yoktur)"
        ) from exc
    return pcbnew


def open_board(path: Path | str | None = None):
    """Kart nesnesi: yol verilirse dosyadan, verilmezse KiCad'de ACIK olan.

    Yol verilen bicim GUI gerektirmez; testler bunu kullanir.
    """
    pcbnew = load_pcbnew()
    if path is not None:
        board = pcbnew.LoadBoard(str(path))
        if board is None:
            raise SwigApplyError(f"kart yuklenemedi: {path}")
        return board
    board = pcbnew.GetBoard()
    if board is None:
        raise SwigApplyError(
            "KiCad'de acik bir kart yok (bu cagri PCB Editor icinden yapilmali)"
        )
    return board


def board_name_of(board) -> str:
    name = str(board.GetFileName() or "")
    return Path(name).name if name else ""


def _position_mm(footprint) -> tuple[float, float]:
    pos = footprint.GetPosition()
    return float(pos.x) / NM_PER_MM, float(pos.y) / NM_PER_MM


def _angle_delta(a: float, b: float) -> float:
    return ((a - b + 180.0) % 360.0) - 180.0


def _pose_changed(footprint, x: float, y: float, rot: float, tolerance_mm: float) -> bool:
    cx, cy = _position_mm(footprint)
    crot = float(footprint.GetOrientationDegrees())
    return (
        abs(cx - x) > tolerance_mm
        or abs(cy - y) > tolerance_mm
        or abs(_angle_delta(crot, rot)) > 1e-6
    )


def index_footprints(board) -> tuple[dict[str, Any], list[str]]:
    """Referans -> footprint. Tekrar eden referanslar ayrica bildirilir."""
    by_ref: dict[str, Any] = {}
    duplicates: set[str] = set()
    for fp in board.GetFootprints():
        ref = str(fp.GetReference())
        if ref in by_ref:
            duplicates.add(ref)
            continue
        by_ref[ref] = fp
    return by_ref, sorted(duplicates)


# --------------------------------------------------------------------------
# Uygulama
# --------------------------------------------------------------------------


def apply_placement(
    board,
    placement: Placement,
    *,
    apply: bool = False,
    save: bool = False,
    locked_refs: set[str] | None = None,
    respect_kicad_locks: bool = True,
    refresh: bool = True,
    tolerance_mm: float = 1e-6,
) -> SwigApplySummary:
    """Yerlesimi acik karta uygular. Varsayilan DRY-RUN.

    Yazdiktan sonra kart GERI OKUNUR: istenen konum gercekten oturmus mu diye
    bakilir. Yazip gormemek en kotu sonuc olurdu - `ipc.py` ile ayni karar.
    """
    pcbnew = load_pcbnew()
    summary = SwigApplySummary(
        board_name=board_name_of(board),
        kicad_version=str(pcbnew.GetBuildVersion()),
        requested=len(placement),
        dry_run=not apply,
    )

    locked_refs = locked_refs or set()
    by_ref, duplicates = index_footprints(board)
    summary.duplicate_refs = [ref for ref in duplicates if ref in placement]
    if summary.duplicate_refs:
        raise SwigApplyError(
            "kartta tekrar eden referans var; hangi footprint'in tasinacagi "
            "belirsiz: " + ", ".join(summary.duplicate_refs)
        )

    planned: list[tuple[str, Any, float, float, float]] = []
    for ref in sorted(placement):
        x, y, rot = (float(v) for v in placement[ref])
        if ref in locked_refs:
            summary.skipped_locked_refs.append(ref)
            continue
        footprint = by_ref.get(ref)
        if footprint is None:
            summary.missing_refs.append(ref)
            continue
        if respect_kicad_locks and bool(footprint.IsLocked()):
            summary.skipped_locked_refs.append(ref)
            continue
        if _pose_changed(footprint, x, y, rot, tolerance_mm):
            planned.append((ref, footprint, x, y, rot))
        else:
            summary.unchanged += 1

    summary.changed = len(planned)
    if not apply:
        return summary

    for ref, footprint, x, y, rot in planned:
        footprint.SetPosition(pcbnew.VECTOR2I(int(round(x * NM_PER_MM)),
                                              int(round(y * NM_PER_MM))))
        footprint.SetOrientationDegrees(rot)
        summary.applied_refs.append(ref)

    # Geri okuma: yazildigi gibi mi durdu?
    fresh, _ = index_footprints(board)
    for ref, _fp, x, y, rot in planned:
        footprint = fresh.get(ref)
        if footprint is None:
            summary.verify_errors.append(f"{ref}: uygulamadan sonra kartta bulunamadi")
            continue
        if _pose_changed(footprint, x, y, rot, tolerance_mm):
            cx, cy = _position_mm(footprint)
            summary.verify_errors.append(
                f"{ref}: beklenen ({x:.3f}, {y:.3f}, {rot:.1f}), "
                f"okunan ({cx:.3f}, {cy:.3f}, {footprint.GetOrientationDegrees():.1f})"
            )

    if save and not summary.verify_errors:
        board.Save(board.GetFileName())
        summary.saved = True

    if refresh:
        # GUI disinda `Refresh` yoktur; testler bu daldan gecer.
        refresher = getattr(pcbnew, "Refresh", None)
        if callable(refresher):
            refresher()
    return summary


# --------------------------------------------------------------------------
# Komut satiri
# --------------------------------------------------------------------------


def build_parser():
    import argparse

    ap = argparse.ArgumentParser(
        prog="pcbqa.swig_apply",
        description="Bir karti yerlestirip sonucu pcbnew ile uygular (API GEREKMEZ).",
    )
    ap.add_argument("board", type=Path, help="Kart dosyasi (.kicad_pcb)")
    ap.add_argument("--rules", type=Path, default=None, help="Kural dosyasi")
    ap.add_argument("--budget", type=float, default=20.0, help="Sure butcesi (saniye)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--apply", action="store_true", help="Dry-run yerine gercekten uygula")
    ap.add_argument("--keep-connectors", action="store_true",
                    help="Konnektorleri (J*, P*...) sabit tut - gercek kartlarda varsayilan")
    ap.add_argument("--allow-open-project", action="store_true",
                    help="KiCad'de acikken de yaz (onerilmez)")
    return ap


def main(argv: list[str] | None = None) -> int:
    import sys

    from .harness import (
        apply_placement as apply_to_model,
        evaluate_design,
        load_design,
        locked_refs,
        make_evaluator,
    )
    from .placement.auto import Auto
    from .placement.base import PlacementContext
    from .rules import load_rules
    from .sch_write import lock_files

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    if not args.board.is_file():
        print(f"hata: kart bulunamadi: {args.board}", file=sys.stderr)
        return 2

    # Kart KiCad'de acikken dosyaya yazmak iki tarafi da kaybettirir.
    locks = lock_files(args.board)
    if args.apply and locks and not args.allow_open_project:
        print(f"hata: proje KiCad'de acik gorunuyor ({locks[0].name}); once kapatin "
              "(bilerek devam etmek icin --allow-open-project)", file=sys.stderr)
        return 2

    default_rules = Path(__file__).parent / "presets" / "uretim.rules.yaml"
    rules = load_rules(args.rules or default_rules)
    design = load_design(args.board)
    before = evaluate_design(design, rules)

    locked = locked_refs(design) if args.keep_connectors else set()
    ctx = PlacementContext(
        design=design, locked=locked, seed=args.seed,
        time_budget_s=args.budget, evaluator=make_evaluator(design, rules),
    )
    placement = Auto().run(ctx)
    after = evaluate_design(apply_to_model(design, placement), rules)

    print(f"skor: {before.score:.1f} -> {after.score:.1f} "
          f"({after.score - before.score:+.1f})")
    if after.score + 1e-9 < before.score:
        print("yerlestirme skoru dusurdu; uygulanmadi", file=sys.stderr)
        return 1

    try:
        board = open_board(args.board)
        summary = apply_placement(
            board, placement,
            apply=args.apply, save=args.apply, locked_refs=locked,
        )
    except SwigApplyError as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 1

    print(summary.describe())
    return 0 if summary.ok else 1
