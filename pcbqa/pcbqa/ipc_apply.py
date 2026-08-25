"""Run the placement contest and apply the winning output to KiCad via IPC.

Usage:
    python -m pcbqa.ipc_apply --board samples\bench_bad.kicad_pcb --apply
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import placement as placement_mod
from .harness import DEFAULT_BOARD, DEFAULT_RULES, DEFAULT_TARGET, Score
from .harness import load_design, locked_refs, render, run_one
from .ipc import IpcApplyError, apply_placement_to_running_kicad
from .placement.base import Placement, PlacementContext, validate
from .rules import load_rules

BASELINE_PLACERS = {"identity", "random"}


@dataclass
class Candidate:
    placer: str
    result: Any
    placement: Placement


def _competitive_placers() -> list[str]:
    return [name for name in placement_mod.PLACERS if name not in BASELINE_PLACERS]


# Skor duseni kazanan saymamak icin tolerans (kayan nokta gurultusu)
REGRESSION_EPS = 0.05


def select_winner(candidates: list[Candidate]) -> Candidate:
    """Karta yazilacak adayi secer.

    Gerileme koruyucusu (Asama 3): karti mevcut halinden KOTU yapan bir
    yerlestirme asla uygulanmaz. Kullanicinin calisan tasarimini bozmaktansa
    hicbir sey yapmamak dogru davranistir.
    """
    valid = [c for c in candidates if not c.result.problems]
    if not valid:
        raise ValueError("gecerli yerlestirme sonucu yok")
    improving = [c for c in valid if c.result.gain >= -REGRESSION_EPS]
    if not improving:
        best = max(valid, key=lambda c: c.result.gain)
        raise ValueError(
            "hicbir yerlestirici karti iyilestiremedi "
            f"(en iyisi {best.placer}: {best.result.gain:+.1f} puan); "
            "karta dokunulmadi"
        )
    valid = improving
    return max(
        valid,
        key=lambda c: (
            c.result.after.score,
            -c.result.after.errors,
            -c.result.after.warnings,
            -c.result.after.total_hpwl_mm,
            c.result.gain,
            -c.result.seconds,
        ),
    )


def load_placement_json(path: Path) -> Placement:
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("placement") if isinstance(data, dict) and "placement" in data else data
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: placement nesnesi bekleniyordu")

    placement: Placement = {}
    for ref, value in raw.items():
        if not (isinstance(value, (list, tuple)) and len(value) == 3):
            raise ValueError(f"{path}: {ref} icin [x, y, rot] bekleniyordu")
        x, y, rot = value
        if not all(isinstance(v, (int, float)) for v in (x, y, rot)):
            raise ValueError(f"{path}: {ref} konumu sayisal olmali")
        placement[str(ref)] = (float(x), float(y), float(rot))
    return placement


def write_placement_json(path: Path, candidate: Candidate, board: Path, seed: int) -> None:
    payload = {
        "version": 1,
        "board": str(board),
        "placer": candidate.placer,
        "seed": seed,
        "before": candidate.result.before.as_dict(),
        "after": candidate.result.after.as_dict(),
        "gain": round(candidate.result.gain, 1),
        "placement": {ref: [x, y, rot] for ref, (x, y, rot) in sorted(candidate.placement.items())},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


# Varsayilan uretim yerlestiricisi: kaba yerlesim + hakem gudumlu cila +
# gerileme tabani. Tek basina yarisan motorlarin hepsini kapsar, bu yuzden
# hepsini ayri ayri kosturmaya gerek yok (`--all` hala mumkun).
DEFAULT_PLACER = "auto"


def _names_from_args(args: argparse.Namespace) -> list[str]:
    if args.placer:
        names = args.placer
    elif args.all:
        names = list(placement_mod.PLACERS)
    elif DEFAULT_PLACER in placement_mod.PLACERS:
        names = [DEFAULT_PLACER]
    else:
        names = _competitive_placers()

    if not args.include_baselines and not args.placer:
        names = [name for name in names if name not in BASELINE_PLACERS]
    return names


def _load_or_run_candidate(args: argparse.Namespace, design, rules) -> tuple[list[Any], Candidate]:
    if args.placement_json:
        placement = load_placement_json(args.placement_json)
        ctx = PlacementContext(
            design=design,
            locked=locked_refs(design),
            seed=args.seed,
            time_budget_s=args.budget,
        )
        problems = validate(placement, ctx)
        before = Score.of(copy.deepcopy(design), rules)
        after_design = load_design(args.board)
        from .harness import apply_placement

        after = Score.of(apply_placement(after_design, placement), rules)
        result = type(
            "LoadedResult",
            (),
            {
                "placer": args.placement_json.stem,
                "before": before,
                "after": after,
                "gain": after.score - before.score,
                "seconds": 0.0,
                "moved": len(placement),
                "problems": problems,
            },
        )()
        if result.gain < -REGRESSION_EPS:
            raise ValueError(
                f"{args.placement_json.name} karti kotulestiriyor "
                f"({result.gain:+.1f} puan); karta dokunulmadi"
            )
        return [result], Candidate(args.placement_json.stem, result, placement)

    names = _names_from_args(args)
    unknown = [name for name in names if name not in placement_mod.PLACERS]
    if unknown:
        raise ValueError(
            f"bilinmeyen yerlestirici: {', '.join(unknown)}; "
            f"mevcut: {', '.join(sorted(placement_mod.PLACERS))}"
        )

    candidates: list[Candidate] = []
    for name in names:
        result, placement = run_one(name, copy.deepcopy(design), rules, args.seed, args.budget)
        candidates.append(Candidate(name, result, placement))
    return [c.result for c in candidates], select_winner(candidates)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pcbqa.ipc_apply",
        description="Yerlestirme kazananini calisan KiCad PCB editorune IPC ile uygular.",
    )
    ap.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    ap.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    ap.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    ap.add_argument("--placer", action="append", default=None)
    ap.add_argument("--all", action="store_true", help="Kayitli tum yerlestiricileri calistir")
    ap.add_argument("--include-baselines", action="store_true", help="identity/random sonucunu da yarisa kat")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--budget", type=float, default=30.0, help="Yerlestirici basina saniye butcesi")
    ap.add_argument("--placement-json", type=Path, default=None, help="Yarisi kosmadan bu placement JSON'u uygula")
    ap.add_argument("--write-placement-json", type=Path, default=None, help="Kazanan ham placement sonucunu yaz")
    ap.add_argument("--apply", action="store_true", help="Dry-run yerine KiCad'e gercekten yaz")
    ap.add_argument("--save", action="store_true", help="Uygulamadan sonra KiCad kartini kaydet")
    ap.add_argument("--allow-board-mismatch", action="store_true", help="Aktif KiCad kart adi --board ile ayni olmasa da uygula")
    ap.add_argument("--ignore-kicad-locks", action="store_true", help="KiCad'de kilitli footprint'leri de tasimayi dene")
    ap.add_argument("--socket", default=None, help="KICAD_API_SOCKET yerine kullanilacak IPC socket/pipe")
    ap.add_argument("--token", default=None, help="KICAD_API_TOKEN yerine kullanilacak IPC token")
    ap.add_argument("--timeout-ms", type=int, default=5000)
    ap.add_argument("--no-color", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    if args.target is None and args.board == DEFAULT_BOARD:
        args.target = DEFAULT_TARGET
    try:
        if not args.board.exists():
            raise ValueError(f"kart bulunamadi: {args.board}")
        rules = load_rules(args.rules)
        design = load_design(args.board)

        results, winner = _load_or_run_candidate(args, design, rules)

        target_score = None
        if args.target and str(args.target) not in ("", ".") and args.target.is_file():
            target_score = Score.of(load_design(args.target), rules)
        print(render(results, target_score, color=False if args.no_color else sys.stdout.isatty()))
        print(
            f"  KAZANAN: {winner.placer}  skor {winner.result.after.score:.0f}/100  "
            f"kazanc {winner.result.gain:+.1f}\n"
        )

        if args.write_placement_json:
            write_placement_json(args.write_placement_json, winner, args.board, args.seed)
            print(f"  placement JSON: {args.write_placement_json}\n")

        summary = apply_placement_to_running_kicad(
            winner.placement,
            apply=args.apply,
            save=args.save,
            locked_refs=locked_refs(design),
            expected_board_name=args.board.name,
            allow_board_mismatch=args.allow_board_mismatch,
            respect_kicad_locks=not args.ignore_kicad_locks,
            socket_path=args.socket,
            kicad_token=args.token,
            timeout_ms=args.timeout_ms,
        )

    except (IpcApplyError, ValueError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2

    mode = "UYGULANDI" if args.apply else "DRY-RUN"
    print(f"  IPC {mode}: {summary.board_name or '(adsiz kart)'}")
    print(
        f"  degisecek/degisen: {summary.changed}  ayni: {summary.unchanged}  "
        f"kilitli atlandi: {len(summary.skipped_locked_refs)}  "
        f"eksik: {len(summary.missing_refs)}"
    )
    if summary.missing_refs:
        print(f"  aktif kartta olmayanlar: {', '.join(summary.missing_refs[:12])}")
    if summary.skipped_locked_refs:
        print(f"  kilitli atlananlar: {', '.join(summary.skipped_locked_refs[:12])}")
    if not args.apply:
        print("  KiCad'e yazilmadi. Gercek uygulama icin ayni komutu --apply ile calistirin.")
    elif args.save:
        print("  kart kaydedildi.")
    else:
        print("  KiCad undo gecmisine tek islem olarak eklendi; dosya kaydedilmedi.")
    print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
