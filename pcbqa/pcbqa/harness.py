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
from .placement.base import Evaluation, Placement, PlacementContext, validate
from .report import PENALTY, Report, enable_ansi
from .rules import load_rules, run_rules
from .sexpr import dumps, parse_with_stats

# Tezgah varsayilanlari
DEFAULT_BOARD = Path("samples/bench_bad.kicad_pcb")
DEFAULT_RULES = Path("samples/bench.rules.yaml")
DEFAULT_TARGET = Path("samples/bench_good.kicad_pcb")

# Konnektorler ve montaj delikleri mekanige bagli oldugu icin varsayilan kilitli
DEFAULT_LOCK_PREFIXES = ("J", "P", "MH", "H")


def evaluate_design(design: Design, rules) -> Evaluation:
    """Bir tasarimi kural motoruyla olcer. Hakemin tek gercek olcutu."""
    findings = run_rules(design, rules)
    report = Report(design=design, metrics=design.metrics(), findings=findings)
    return Evaluation(
        score=report.score,
        errors=report.count("error"),
        warnings=report.count("warning"),
        total_hpwl_mm=report.metrics.total_hpwl_mm,
        findings=findings,
    )


def make_evaluator(design: Design, rules):
    """`placement -> Evaluation` kapanisi uretir (yerlestiricilere verilir).

    Degerlendirme HER ZAMAN tasarimin bozulmamis bir kopyasi uzerinden
    yapilir; boylece sozlesmeyi ihlal edip ctx.design'i degistiren bir
    yerlestirici olcumu kirletemez.
    """
    pristine = copy.deepcopy(design)

    def evaluate(placement: Placement) -> Evaluation:
        return evaluate_design(apply_placement(pristine, placement), rules)

    return evaluate


@dataclass
class Score:
    score: float
    errors: int
    warnings: int
    total_hpwl_mm: float

    @classmethod
    def of(cls, design: Design, rules) -> "Score":
        ev = evaluate_design(design, rules)
        return cls(
            score=ev.score,
            errors=ev.errors,
            warnings=ev.warnings,
            total_hpwl_mm=ev.total_hpwl_mm,
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
    """Sozlesme ihlali olmayan ve karti KOTULESTIRMEYEN en iyi sonucu secer.

    Gerileme koruyucusu (Asama 3): skoru baslangictan dusuk bir yerlestirme
    asla kazanan sayilmaz. Boyle bir cikti karta yazilirsa kullanicinin
    tasarimi elle yaptigindan kotu hale gelir; hicbir sey yapmamak yeglenir.
    """
    valid = [r for r in results if not r.problems and r.gain >= -0.05]
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
        design=design,
        locked=locked_refs(design),
        seed=seed,
        time_budget_s=budget,
        evaluator=make_evaluator(design, rules),
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


def discover_boards(root: Path) -> list[Path]:
    """Bir klasordeki tum .kicad_pcb dosyalarini bulur (yedekler haric)."""
    boards = [
        p
        for p in sorted(root.rglob("*.kicad_pcb"))
        if not p.name.startswith("_") and "-backups" not in str(p)
    ]
    return boards


def run_suite(boards: list[Path], names: list[str], rules, seed: int, budget: float) -> dict:
    """Yerlestiricileri bir kart kumesinde kosturur.

    Asama 3'un asil kabul olcutu burada: hicbir kartta gerileme olmamali.
    Tek kartta iyi sonuc, sentetik tezgaha asiri uyum olabilir.
    """
    rows: list[dict] = []
    for board_path in boards:
        try:
            design = load_design(board_path)
        except Exception as exc:  # bozuk/eksik kart suiti durdurmasin
            rows.append({"board": board_path.name, "error": str(exc)[:80]})
            print(f"  {board_path.stem[:33]:<33} ATLANDI ({str(exc)[:40]})", flush=True)
            continue
        if not design.board.components:
            rows.append({"board": board_path.name, "error": "bilesen yok"})
            print(f"  {board_path.stem[:33]:<33} ATLANDI (bilesen yok)", flush=True)
            continue

        entry = {"board": board_path.name, "components": len(design.board.components), "placers": {}}
        for name in names:
            result, _ = run_one(name, copy.deepcopy(design), rules, seed, budget)
            entry["placers"][name] = result.as_dict()
            flag = "GERILEME" if result.gain < -0.05 else ""
            label = board_path.stem
            if len(label) > 32:
                label = label[:31] + "~"
            print(
                f"  {label:<33} {name:<9}"
                f"{result.before.score:>6.0f} ->{result.after.score:>6.0f}"
                f"{result.gain:>+8.1f}  {flag}",
                flush=True,
            )
        rows.append(entry)

    regressions = [
        (r["board"], n, p["gain"])
        for r in rows
        for n, p in r.get("placers", {}).items()
        if p["gain"] < -0.05
    ]
    return {"rows": rows, "regressions": regressions}


def score_corpus(boards: list[Path], rules) -> dict:
    """Bir kart kumesini YERLESTIRME YAPMADAN puanlar (Faz 1d).

    Neden ayri bir kip: kalibrasyon sorusu "yerlestiricim iyi mi" degil,
    "OLCUTUM iyi mi". Sahaya cikmis, profesyonelce uretilmis bir karta skorumuz
    dusuk veriyorsa yanlis olan kart degil SKORDUR. Yerlestirme calistirmak hem
    gereksiz hem de olculen seyi degistirir.

    Doner: kart basina satirlar + kural basina atesleme sayisi.
    """
    rows: list[dict] = []
    fired: dict[str, int] = {}
    boards_with_findings = 0

    for board_path in boards:
        try:
            design = load_design(board_path)
        except Exception as exc:
            rows.append({"board": board_path.name, "error": str(exc)[:100]})
            continue
        if not design.board.components:
            rows.append({"board": board_path.name, "error": "bilesen yok"})
            continue

        ev = evaluate_design(design, rules)
        seen = {f.rule_id for f in ev.findings if f.severity != "info"}
        for rule_id in seen:
            fired[rule_id] = fired.get(rule_id, 0) + 1
        if seen:
            boards_with_findings += 1

        rows.append(
            {
                "board": board_path.name,
                "components": len(design.board.components),
                "score": round(ev.score, 1),
                "errors": ev.errors,
                "warnings": ev.warnings,
                "rules_fired": sorted(seen),
            }
        )

    scored = [r for r in rows if "score" in r]
    scores = sorted(r["score"] for r in scored)
    return {
        "boards": len(rows),
        "scored": len(scored),
        "skipped": len(rows) - len(scored),
        "boards_with_findings": boards_with_findings,
        "median": scores[len(scores) // 2] if scores else None,
        "min": scores[0] if scores else None,
        "max": scores[-1] if scores else None,
        "quartiles": (
            [scores[len(scores) // 4], scores[len(scores) // 2], scores[3 * len(scores) // 4]]
            if len(scores) >= 4
            else None
        ),
        "rule_fire_counts": dict(sorted(fired.items(), key=lambda kv: -kv[1])),
        "rows": rows,
    }


def render_corpus(report: dict, rules, color: bool = True) -> None:
    """Kalibrasyon raporunu yazar.

    Yorum kurali: bir kural gercek kartlarin COGUNDA atesleniyorsa suphelidir -
    kartlar degil, kural ya da esigi yanlis olabilir.
    """
    ok = len([r for r in report["rows"] if "score" in r])
    print()
    skipped = report["skipped"]
    header = f"  KALIBRASYON - {ok} kart puanlandi"
    if skipped:
        header += f", {skipped} atlandi"
    print(header)
    print()
    for row in report["rows"]:
        if "error" in row:
            print(f"  {row['board'][:38]:<40} ATLANDI ({row['error'][:34]})")
            continue
        print(
            f"  {row['board'][:38]:<40}{row['components']:>5} bilesen"
            f"{row['score']:>8.1f}{row['errors']:>5}h{row['warnings']:>4}u"
        )

    print()
    q = report["quartiles"]
    print(f"  skor: medyan {report['median']}, aralik {report['min']}-{report['max']}"
          + (f", ceyrekler {q[0]}/{q[1]}/{q[2]}" if q else ""))
    print(f"  bulgu ureten kart: {report['boards_with_findings']}/{ok}")

    if report["rule_fire_counts"]:
        print()
        print("  kural basina atesleme (gercek kartlarda):")
        for rule_id, count in report["rule_fire_counts"].items():
            share = count / ok if ok else 0.0
            flag = "  <- SUPHELI: kartlarin cogunda atesliyor" if share > 0.5 else ""
            print(f"    {rule_id:<40}{count:>4}/{ok}  %{share*100:>5.1f}{flag}")
    else:
        print()
        print("  hicbir kural ateslemedi")


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
    ap.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Hedef kart (referans skor). Varsayilan: yalnizca tezgah kartinda bench_good",
    )
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--budget", type=float, default=30.0, help="Saniye cinsinden sure butcesi")
    ap.add_argument("--write", type=Path, default=None, help="Sonucu .kicad_pcb olarak yaz")
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument(
        "--suite",
        type=Path,
        default=None,
        help="Klasordeki tum .kicad_pcb dosyalarinda kostur (regresyon paketi)",
    )
    ap.add_argument(
        "--score-only",
        type=Path,
        default=None,
        metavar="KLASOR",
        help="Yerlestirme YAPMADAN klasordeki kartlari puanla (kalibrasyon)",
    )
    args = ap.parse_args(argv)

    # Referans kart yalnizca tezgahin kendisinde anlamlidir. Baska bir kart
    # verilmisken bench_good'u referans gostermek yaniltici bir satir uretiyordu.
    if args.target is None and args.board == DEFAULT_BOARD:
        args.target = DEFAULT_TARGET

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

    if args.score_only is not None:
        if not args.score_only.exists():
            print(f"hata: klasor bulunamadi: {args.score_only}", file=sys.stderr)
            return 2
        boards = discover_boards(args.score_only)
        if not boards:
            print(f"hata: {args.score_only} altinda .kicad_pcb yok", file=sys.stderr)
            return 2
        report = score_corpus(boards, rules)
        render_corpus(report, rules, color=not args.no_color)
        if args.json:
            args.json.write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"\n  JSON: {args.json}")
        return 0

    if args.suite is not None:
        if not args.suite.exists():
            print(f"hata: klasor bulunamadi: {args.suite}", file=sys.stderr)
            return 2
        boards = discover_boards(args.suite)
        if not boards:
            print(f"hata: {args.suite} altinda .kicad_pcb yok", file=sys.stderr)
            return 2
        print()
        print(f"  REGRESYON PAKETI - {len(boards)} kart x {len(names)} yerlestirici"
              f"  (kural: {args.rules.name}, butce: {args.budget:g}s)")
        print()
        summary = run_suite(boards, names, rules, args.seed, args.budget)
        print()
        if summary["regressions"]:
            print(f"  SONUC: {len(summary['regressions'])} GERILEME")
            for board, name, gain in summary["regressions"]:
                print(f"    {board} / {name}: {gain:+.1f}")
        else:
            print("  SONUC: hicbir kartta gerileme yok")
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(
                json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"  JSON: {args.json}")
        return 1 if summary["regressions"] else 0

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
