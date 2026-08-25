"""HAKEM - bir yerlestiriciyi calistirir, oncesi/sonrasi puanlar.

    python -m pcbqa.harness --placer random
    python -m pcbqa.harness --placer identity --board samples/bench_bad.kicad_pcb
    python -m pcbqa.harness --all --json sonuc.json
    python -m pcbqa.harness --placer force --write .work/sonuc.kicad_pcb

Birden fazla agent paralel calisip ayni arayuzu farkli algoritmayla uyguluyor.
Hangisinin daha iyi oldugunu tartismaya gerek yok - bu arac olcer.

Karsilastirma adil olsun diye her yerlestirici AYNI tasarimin taze bir
kopyasiyla, ayni tohum ve ayni sure butcesiyle calisir.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from . import placement as placement_mod
from .model import Design, build_design
from .netlist import netlist_from_board
from .pcb import Board, read_board
from .placement.base import Placement, PlacementContext, validate
from .report import PENALTY, Report, enable_ansi
from .rules import load_rules, run_rules
from .sexpr import dumps, parse_with_stats

# Tezgah varsayilanlari
DEFAULT_BOARD = Path("samples/bench_bad.kicad_pcb")
DEFAULT_RULES = Path("samples/bench.rules.yaml")
DEFAULT_TARGET = Path("samples/bench_good.kicad_pcb")

# Konnektorler ve montaj delikleri mekanige bagli oldugu icin varsayilan kilitli
DEFAULT_LOCK_PREFIXES = ("J", "P", "MH", "H")


@dataclass
class Score:
    score: float
    errors: int
    warnings: int
    total_hpwl_mm: float

    @classmethod
    def of(cls, design: Design, rules) -> "Score":
        findings = run_rules(design, rules)
        report = Report(design=design, metrics=design.metrics(), findings=findings)
        return cls(
            score=report.score,
            errors=report.count("error"),
            warnings=report.count("warning"),
            total_hpwl_mm=report.metrics.total_hpwl_mm,
        )

    def as_dict(self) -> dict:
        return {
            "score": round(self.score, 1),
            "errors": self.errors,
            "warnings": self.warnings,
            "total_hpwl_mm": round(self.total_hpwl_mm, 1),
        }


@dataclass
class Result:
    placer: str
    before: Score
    after: Score
    seconds: float
    moved: int
    problems: list[str]

    @property
    def gain(self) -> float:
        return self.after.score - self.before.score

    def as_dict(self) -> dict:
        return {
            "placer": self.placer,
            "before": self.before.as_dict(),
            "after": self.after.as_dict(),
            "gain": round(self.gain, 1),
            "seconds": round(self.seconds, 2),
            "moved": self.moved,
            "problems": self.problems,
        }


def best_result(results: list[Result]) -> Result | None:
    """Sozlesme ihlali olmayan en iyi sonucu secer."""
    valid = [r for r in results if not r.problems]
    if not valid:
        return None
    return max(
        valid,
        key=lambda r: (
            r.after.score,
            -r.after.errors,
            -r.after.warnings,
            -r.after.total_hpwl_mm,
            r.gain,
            -r.seconds,
        ),
    )


def load_design(board_path: Path) -> Design:
    board = read_board(board_path)
    return build_design(board, netlist_from_board(board), project_name=board_path.stem)


def locked_refs(design: Design, prefixes=DEFAULT_LOCK_PREFIXES) -> set[str]:
    """Konum olarak sabit kabul edilen bilesenler."""
    return {
        c.ref
        for c in design.board.components
        if any(c.ref.upper().startswith(p) and c.ref[len(p) :].isdigit() for p in prefixes)
    }


def apply_placement(design: Design, placement: Placement) -> Design:
    """Yerlestirmeyi uygular ve YENI bir Design dondurur (girdi bozulmaz)."""
    board: Board = copy.deepcopy(design.board)
    for ref, (x, y, rot) in placement.items():
        comp = board.by_ref(ref)
        if comp is not None:
            comp.place(x, y, rot)
    return build_design(board, netlist_from_board(board), project_name=design.project_name)


def write_board(source: Path, placement: Placement, target: Path) -> None:
    """Yerlestirmeyi kaynak dosyaya uygulayip yeni bir .kicad_pcb yazar.

    KiCad'de gozle incelemek icin. Kaynak dosyaya dokunulmaz.
    """
    root, _ = parse_with_stats(source.read_text(encoding="utf-8"))

    for node in root:
        if not (isinstance(node, list) and node and node[0] == "footprint"):
            continue
        ref = None
        for prop in node:
            if isinstance(prop, list) and len(prop) > 2 and prop[0] == "property":
                if prop[1] == "Reference":
                    ref = prop[2]
                    break
        if ref not in placement:
            continue
        x, y, rot = placement[ref]
        for item in node:
            if isinstance(item, list) and item and item[0] == "at":
                item[1:] = [f"{x:g}", f"{y:g}"] + ([f"{rot:g}"] if rot else [])
                break

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dumps(root) + "\n", encoding="utf-8")


def run_one(name: str, design: Design, rules, seed: int, budget: float) -> Result:
    placer = placement_mod.get(name)
    ctx = PlacementContext(
        design=design, locked=locked_refs(design), seed=seed, time_budget_s=budget
    )

    before = Score.of(design, rules)
    started = time.perf_counter()
    result = placer.run(ctx)
    seconds = time.perf_counter() - started

    problems = validate(result, ctx)
    moved = sum(
        1
        for ref, (x, y, _) in result.items()
        if (c := design.component(ref)) and (abs(c.x - x) > 1e-6 or abs(c.y - y) > 1e-6)
    )
    after = Score.of(apply_placement(design, result), rules)

    return Result(
        placer=name,
        before=before,
        after=after,
        seconds=seconds,
        moved=moved,
        problems=problems,
    ), result


def render(results: list[Result], target: Score | None, color: bool) -> str:
    def c(text: str, code: str) -> str:
        return f"{code}{text}\033[0m" if color else text

    lines = ["", "=" * 78, "  HAKEM - yerlestirme karsilastirmasi", "=" * 78, ""]
    lines.append(f"  {'yerlestirici':<16}{'once':>8}{'sonra':>8}{'kazanc':>9}"
                 f"{'hata':>7}{'HPWL mm':>11}{'sure':>8}")
    lines.append("  " + "-" * 68)

    for r in sorted(results, key=lambda r: r.gain, reverse=True):
        gain = f"{r.gain:+.1f}"
        gain_color = "\033[32m" if r.gain > 0 else ("\033[31m" if r.gain < 0 else "\033[2m")
        lines.append(
            f"  {r.placer:<16}{r.before.score:>8.0f}{r.after.score:>8.0f}"
            f"{c(f'{gain:>9}', gain_color)}"
            f"{r.after.errors:>7}{r.after.total_hpwl_mm:>11,.0f}{r.seconds:>7.1f}s"
        )
        for problem in r.problems:
            lines.append(c(f"      SOZLESME IHLALI: {problem}", "\033[31m"))

    if target is not None:
        lines.append("  " + "-" * 68)
        lines.append(
            f"  {'HEDEF (bench_good)':<16}{'':>8}{target.score:>8.0f}"
            f"{'':>9}{target.errors:>7}{target.total_hpwl_mm:>11,.0f}"
        )

    lines.append("")
    lines.append(c("  identity kazanci 0 olmali (hakem dogrulamasi); "
                   "random negatif olmali (skor duyarliligi).", "\033[2m"))
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(
        prog="pcbqa.harness", description="Yerlestiricileri calistirir ve puanlar."
    )
    ap.add_argument("--placer", action="append", default=None, help="Calistirilacak yerlestirici")
    ap.add_argument("--all", action="store_true", help="Kayitli tum yerlestiricileri calistir")
    ap.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    ap.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    ap.add_argument("--target", type=Path, default=DEFAULT_TARGET, help="Hedef kart (referans skor)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--budget", type=float, default=30.0, help="Saniye cinsinden sure butcesi")
    ap.add_argument("--write", type=Path, default=None, help="Sonucu .kicad_pcb olarak yaz")
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args(argv)

    names = list(placement_mod.PLACERS) if args.all else (args.placer or ["identity"])
    unknown = [n for n in names if n not in placement_mod.PLACERS]
    if unknown:
        print(f"hata: bilinmeyen yerlestirici: {', '.join(unknown)}\n"
              f"mevcut: {', '.join(sorted(placement_mod.PLACERS))}", file=sys.stderr)
        return 2
    if not args.board.exists():
        print(f"hata: kart bulunamadi: {args.board}", file=sys.stderr)
        return 2

    rules = load_rules(args.rules)
    design = load_design(args.board)

    # Bos yol Path(".") olur ve exists() True doner; klasoru kart sanmayalim.
    target_score = None
    if args.target and str(args.target) not in ("", ".") and args.target.is_file():
        target_score = Score.of(load_design(args.target), rules)

    results: list[Result] = []
    raw_by_placer: dict[str, Placement] = {}
    for name in names:
        # Her yerlestirici taze bir kopyayla calisir - adil karsilastirma
        result, raw = run_one(name, copy.deepcopy(design), rules, args.seed, args.budget)
        results.append(result)
        raw_by_placer[name] = raw

    print(render(results, target_score, enable_ansi() and not args.no_color))

    winner = best_result(results)
    if args.write and winner:
        write_board(args.board, raw_by_placer[winner.placer], args.write)
        print(
            f"  kazanan kart yazildi: {args.write}  "
            f"({winner.placer}, KiCad'de acip inceleyebilirsiniz)\n"
        )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "board": str(args.board),
            "rules": str(args.rules),
            "seed": args.seed,
            "target": target_score.as_dict() if target_score else None,
            "winner": winner.placer if winner else None,
            "results": [r.as_dict() for r in results],
        }
        args.json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  JSON: {args.json}\n")

    return 1 if any(r.problems for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
