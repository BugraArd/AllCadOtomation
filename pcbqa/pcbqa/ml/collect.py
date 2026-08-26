"""VERI TOPLAMA - gercek hakemle etiketlenmis aday hamle ornekleri.

    python -m pcbqa.ml.collect --board samples/bench_bad.kicad_pcb --out .work/moves.jsonl
    python -m pcbqa.ml.collect --suite "C:\\Program Files\\KiCad\\10.0\\share\\kicad\\demos" \\
        --rules pcbqa/default_rules.yaml --out .work/moves.jsonl --budget 20

## Iki kritik karar

**1. Adaylar aramanin GERCEKTEN urettigi adaylardir.** Hamleler
`refine.finding_moves` / `refine.nudge_moves` ile uretilir - yani modelin
egitimde gordugu dagilim, kullanimda gorecegi dagilimla aynidir. Buraya ikinci
bir hamle ureteci yazmak (or. "rastgele konumlar") klasik dagilim kaymasi
hatasidir: model laboratuvarda parlar, aramada ise yaramaz.

**2. Yorunge monotondur.** `polish` yalnizca iyilestiren hamleleri kabul eder,
yani arama sirasinda gorulen yerlesimler hep "baslangic + kabul edilmis
iyilesmeler" zinciridir. Toplayici da ayni zinciri yurur. Veri hacmini
artirmak icin rastgele kotulestirilmis durumlar EKLENMEZ; onun yerine kart
BOZULMUS bir baslangictan da yeniden baslatilir (`--starts`), cunku `auto`
gercekten de kaba yerlesimin ciktisini cilalar - o durumlar dagilimin icinde.

## Etiket

Hakemin siralama anahtari sozlukseldir: (skor, -hata, -uyari, -HPWL). Hata ve
uyari zaten skorun icinde; geriye skor ile HPWL kaliyor. Skor 0.1 adimlarla
yuvarlandigi icin HPWL'i 0.05 agirlikli bir ESITLIK BOZUCU olarak eklemek
sozluksel sirayi birebir korur:

    etiket = d_skor + 0.05 * clamp(-d_HPWL / HPWL_onceki, -1, +1)

Boylece `etiket > 0` ile `Evaluation.better_than` pratikte ayni seyi soyler.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

from ..harness import (
    DEFAULT_LOCK_PREFIXES,
    discover_boards,
    load_design,
    locked_refs,
    make_evaluator,
)
from ..placement import refine
from ..placement.base import Placement, PlacementContext
from ..rules import load_rules
from .dataset import Dataset, Sample
from .features import FEATURE_NAMES, FEATURE_VERSION, MoveFeaturizer

# Skorun yuvarlama adimi 0.1; esitlik bozucu bundan kucuk olmali.
LABEL_HPWL_EPS = 0.05


def label_of(before, after) -> float:
    """Iki degerlendirme arasindaki farki tek sayiya indirir (bkz. modul basi)."""
    d_score = after.score - before.score
    base = max(1.0, before.total_hpwl_mm)
    ratio = (before.total_hpwl_mm - after.total_hpwl_mm) / base
    return d_score + LABEL_HPWL_EPS * max(-1.0, min(1.0, ratio))


def perturb(placement: Placement, ctx: PlacementContext, rng: random.Random,
            fraction: float = 0.35, spread_mm: float = 8.0) -> Placement:
    """Yerlesimin bir kismini bozar - "kaba yerlesim ciktisi" benzeri durum.

    Kilitli bilesenlere dokunmaz; kart sinirinin disina tasmaz.
    """
    minx, miny, maxx, maxy = ctx.outline()
    out = dict(placement)
    movable = ctx.movable()
    rng.shuffle(movable)
    for ref in movable[: max(1, int(len(movable) * fraction))]:
        x, y, rot = out[ref]
        nx = min(maxx, max(minx, x + rng.uniform(-spread_mm, spread_mm)))
        ny = min(maxy, max(miny, y + rng.uniform(-spread_mm, spread_mm)))
        out[ref] = (nx, ny, rot)
    return out


def collect_board(
    board_path: Path,
    rules,
    *,
    seed: int = 0,
    budget_s: float = 20.0,
    starts: int = 2,
    max_batch: int = 24,
    max_findings: int = 12,
    nudge_refs: int = 6,
    verbose: bool = True,
) -> Dataset:
    """Tek karttan ornek toplar. Hakem her aday icin GERCEKTEN calisir."""
    design = load_design(board_path)
    ds = Dataset(feature_names=list(FEATURE_NAMES), feature_version=FEATURE_VERSION)
    if not design.board.components:
        return ds

    ctx = PlacementContext(
        design=design,
        locked=locked_refs(design, DEFAULT_LOCK_PREFIXES),
        seed=seed,
        time_budget_s=budget_s,
        evaluator=make_evaluator(design, rules),
    )
    if not ctx.movable():
        return ds

    fz = MoveFeaturizer(design, ctx.locked)
    rng = random.Random(seed)
    deadline = time.perf_counter() + budget_s
    group = board_path.stem
    batch_no = 0
    evals = 0

    for start_index in range(max(1, starts)):
        if time.perf_counter() > deadline:
            break
        placement = ctx.current() if start_index == 0 else perturb(ctx.current(), ctx, rng)
        current = ctx.evaluate(placement)
        if current is None:
            break

        # Monoton yorunge: her adimda tum aday listeleri denenir, en iyi
        # iyilestiren hamle kabul edilir; iyilestiren yoksa yorunge biter.
        while time.perf_counter() < deadline:
            fz.refresh(placement, current)
            step_best: tuple[float, str, tuple[float, float, float]] | None = None

            findings = list(current.findings)
            errors = [f for f in findings if getattr(f, "severity", "") == "error"]
            warnings = [f for f in findings if getattr(f, "severity", "") == "warning"]
            groups: list[tuple[str, list]] = []
            for finding in (errors + warnings)[:max_findings]:
                moves = refine.finding_moves(finding, placement, ctx)
                if moves:
                    groups.append((f"f{getattr(finding, 'rule_id', '?')}", moves))
            refs = [r for r in ctx.movable() if r in placement]
            rng.shuffle(refs)
            for ref in refs[:nudge_refs]:
                groups.append((f"n{ref}", refine.nudge_moves(ref, placement, ctx, rng)))

            if not groups:
                break

            produced = 0
            for source, moves in groups:
                if time.perf_counter() > deadline:
                    break
                if len(moves) > max_batch:
                    moves = rng.sample(moves, max_batch)
                batch_no += 1
                for ref, xyr in moves:
                    if time.perf_counter() > deadline:
                        break
                    cand = refine.with_move(placement, ref, xyr)
                    after = ctx.evaluate(cand)
                    evals += 1
                    if after is None:
                        continue
                    y = label_of(current, after)
                    ds.add(
                        Sample(
                            features=fz.features(ref, xyr),
                            label=y,
                            group=group,
                            batch=f"{start_index}-{batch_no}",
                            extra={
                                "ref": ref,
                                "src": source[0],
                                "d_score": round(after.score - current.score, 3),
                                "d_err": after.errors - current.errors,
                                "d_hpwl": round(after.total_hpwl_mm - current.total_hpwl_mm, 2),
                            },
                        )
                    )
                    produced += 1
                    if step_best is None or y > step_best[0]:
                        step_best = (y, ref, xyr)

            if not produced or step_best is None or step_best[0] <= 0.0:
                break  # iyilestiren hamle kalmadi - yorunge burada biter
            placement = refine.with_move(placement, step_best[1], step_best[2])
            nxt = ctx.evaluate(placement)
            if nxt is None:
                break
            current = nxt

    if verbose:
        s = ds.summary()
        print(
            f"  {group[:33]:<33} {s['samples']:>6} ornek  "
            f"{s['batches']:>4} parti  {s['improving']:>5} iyi  "
            f"({evals} degerlendirme)",
            flush=True,
        )
    return ds


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(
        prog="pcbqa.ml.collect",
        description="Hakemle etiketlenmis aday hamle veri kumesi uretir.",
    )
    ap.add_argument("--board", type=Path, action="append", default=None)
    ap.add_argument("--suite", type=Path, default=None, help="Klasordeki tum kartlar")
    ap.add_argument("--rules", type=Path, default=Path("pcbqa/default_rules.yaml"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--budget", type=float, default=20.0, help="Kart basina saniye")
    ap.add_argument("--starts", type=int, default=2, help="Kart basina yorunge sayisi")
    ap.add_argument("--max-batch", type=int, default=24, help="Aday listesi basina ornek")
    ap.add_argument("--limit", type=int, default=0, help="En fazla kac kart (0 = hepsi)")
    args = ap.parse_args(argv)

    boards: list[Path] = list(args.board or [])
    if args.suite:
        if not args.suite.exists():
            print(f"hata: klasor bulunamadi: {args.suite}", file=sys.stderr)
            return 2
        boards.extend(discover_boards(args.suite))
    if not boards:
        print("hata: --board veya --suite verin", file=sys.stderr)
        return 2
    if args.limit:
        boards = boards[: args.limit]
    if not args.rules.exists():
        print(f"hata: kural dosyasi bulunamadi: {args.rules}", file=sys.stderr)
        return 2

    rules = load_rules(args.rules)
    print()
    print(f"  VERI TOPLAMA - {len(boards)} kart, kart basina {args.budget:g}s")
    print()

    total = Dataset(feature_names=list(FEATURE_NAMES), feature_version=FEATURE_VERSION)
    started = time.perf_counter()
    for board in boards:
        try:
            part = collect_board(
                board,
                rules,
                seed=args.seed,
                budget_s=args.budget,
                starts=args.starts,
                max_batch=args.max_batch,
            )
        except Exception as exc:  # bozuk kart toplamayi durdurmasin
            print(f"  {board.stem[:33]:<33} ATLANDI ({str(exc)[:40]})", flush=True)
            continue
        total.extend(part)

    total.meta = {
        "rules": str(args.rules),
        "boards": len(boards),
        "seed": args.seed,
        "budget_s": args.budget,
    }
    total.save(args.out)
    summary = total.summary()
    print()
    print(f"  {json.dumps(summary, ensure_ascii=False)}")
    print(f"  sure: {time.perf_counter() - started:.1f}s   JSONL: {args.out}")
    print()
    return 0 if len(total) else 1


if __name__ == "__main__":
    raise SystemExit(main())
