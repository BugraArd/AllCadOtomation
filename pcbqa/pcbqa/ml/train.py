"""EGITIM ve KARSILASTIRMA - `harness.py`nin ML tarafindaki karsiligi.

    python -m pcbqa.ml.train .work/moves.jsonl --model all
    python -m pcbqa.ml.train .work/moves.jsonl --model gbt --out pcbqa/ml/models/move-v1.json
    python -m pcbqa.ml.train .work/moves.jsonl --model all --cv 5

`harness` ile ayni felsefe: hangi modelin iyi oldugunu tartismayiz, olceriz.
Ve tipki `identity` gibi bir TABAN CIZGISI (`mean`) hep yarisir - bir model
onu gecemiyorsa ogrenilecek sinyal bulunamamis demektir.

Bolme KART BAZLIDIR (bkz. `dataset.py`): ayni kart hem egitimde hem testte
olamaz, yoksa metrikler ezberi olcer.

Bakilacak sutun **skor hizlanmasi**: SKORU ARTIRAN ilk hamleye, cilanin bugun
kullandigi sirada kac degerlendirmede ulasildigi / model sirasinda kac
degerlendirmede ulasildigi. 1.0 = modelin faydasi yok. R^2 ikincil bilgidir;
`--target score` icin hic basilmaz cunku o modelde anlamsizdir.

Hedef secimi (`--target`) model secimindeki farktan daha buyuk fark yaratiyor;
sebebi `targets()` icinde olcumuyle birlikte yaziyor - okumadan degistirmeyin.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from . import metrics as M
from .dataset import Dataset
from .model import build
from .trees import GBTModel
from .linear import RidgeModel

DEFAULT_MODELS = ("mean", "ridge", "gbt")


def targets(ds: Dataset, mode: str) -> list[float]:
    """Egitim hedefi. Hangisini sectiginiz MODEL SECIMINDEN daha onemli - olculdu.

    `value` - etiketin kendisi (skor farki + HPWL esitlik bozucu). Buyuk
              kazanci buyuk tahmin etmeye calisir.
    `sign`  - "bu hamle hakemi mutlu eder mi" (1/0). Yerel arama ILK
              IYILESTIREN hamleyi kabul ettigi icin sorulan soru aslinda budur.
    `score` - "bu hamle SKORU artirir mi" (1/0). `sign`den farki HPWL-only
              iyilesmeleri olumlu saymamasi.

    **Neden `score` var:** veri kumesinde etiketi pozitif olan hamlelerin
    %81'i skoru hic degistirmiyor, yalnizca HPWL'i birkac mm kisaltiyor.
    `sign` ile egitilen model bunlari ogrendi ve cilayi mikro HPWL kazanclarina
    yonlendirdi; hakemin sayimindaki hatalar acik kaldigi icin `complex_hierarchy`
    94 -> 81 dustu (HPWL ise 1680 -> 1594 iyilesti). Kural: modele neyi
    siralamasini istiyorsak ETIKET tam olarak o olmali.
    """
    if mode == "sign":
        return [1.0 if s.label > 1e-9 else 0.0 for s in ds.samples]
    if mode == "score":
        return [
            1.0 if float(s.extra.get("d_score", s.label)) > 1e-9 else 0.0
            for s in ds.samples
        ]
    return list(ds.y)


def fit_model(name: str, train: Dataset, seed: int = 0, target: str = "value", **kw: Any):
    """Adi verilen modeli egitir ve semasini icine yazar."""
    model = GBTModel(seed=seed, **kw) if name == "gbt" else build(name, **kw)
    model.feature_names = list(train.feature_names)
    model.feature_version = train.feature_version
    model.meta["target"] = target
    model.fit(train.X, targets(train, target))  # type: ignore[attr-defined]
    return model


def cross_validate(
    name: str, ds: Dataset, folds: int, seed: int, target: str = "value"
) -> dict[str, float]:
    """Gruplu k-kat capraz dogrulama; ortalama metrikleri dondurur."""
    runs = []
    for train, test in ds.folds_by_group(folds, seed=seed):
        model = fit_model(name, train, seed=seed, target=target)
        runs.append(M.evaluate(test.samples, model.predict))
    if not runs:
        return {}
    keys = ("mae", "rmse", "r2", "spearman", "pairwise", "speedup",
            "speedup_score", "top1")
    return {k: sum(r[k] for r in runs) / len(runs) for k in keys}


def _row(name: str, res: dict[str, Any], seconds: float, target: str) -> str:
    # MAE/R2 yalnizca hedef `value` iken anlamli; `sign` modeli baska bir
    # olcekte tahmin eder, sayiyi basmak yaniltici olur.
    fit = f"{res['mae']:>9.3f}{res['r2']:>8.3f}" if target == "value" else f"{'-':>9}{'-':>8}"
    return (
        f"  {name:<8}{target:<7}{res['n']:>8}{fit}"
        f"{res['pairwise']:>9.3f}"
        f"{res['speedup']:>10.2f}x"
        f"{res['evals_model_score']:>9.1f}{res['evals_order_score']:>9.1f}"
        f"{res['speedup_score']:>10.2f}x{seconds:>8.1f}s"
    )


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(
        prog="pcbqa.ml.train", description="Hamle siralama modeli egitir ve olcer."
    )
    ap.add_argument("dataset", type=Path)
    ap.add_argument("--model", action="append", default=None,
                    help="mean | ridge | gbt | all (birden fazla verilebilir)")
    ap.add_argument("--target", action="append", default=None,
                    help="score (skoru artirir mi, ONERILEN) | sign | value | all")
    ap.add_argument("--out", type=Path, default=None, help="Kazanani buraya kaydet")
    ap.add_argument("--test-frac", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--cv", type=int, default=0, help="Gruplu k-kat capraz dogrulama")
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)

    if not args.dataset.exists():
        print(f"hata: veri kumesi bulunamadi: {args.dataset}", file=sys.stderr)
        return 2
    ds = Dataset.load(args.dataset)
    if len(ds) < 20:
        print(f"hata: cok az ornek ({len(ds)})", file=sys.stderr)
        return 2

    names = list(args.model or ["all"])
    if "all" in names:
        names = list(DEFAULT_MODELS)

    summary = ds.summary()
    print()
    print(f"  VERI: {summary['samples']} ornek, {summary['groups']} kart, "
          f"{summary['batches']} parti, {summary['features']} oznitelik "
          f"(sema v{summary['feature_version']})")
    print(f"  ETIKET: {summary['improving']} iyi / {summary['worsening']} kotu / "
          f"{summary['neutral']} notr")

    train, test = ds.split_by_group(args.test_frac, seed=args.seed)
    print(f"  BOLME (kart bazli): egitim {len(train)} ornek / "
          f"{len(train.groups())} kart, test {len(test)} ornek / "
          f"{len(test.groups())} kart")
    modes = list(args.target or ["score"])
    if "all" in modes:
        modes = ["value", "sign", "score"]

    print()
    print(f"  {'':<15}{'':>8}{'':>9}{'':>8}{'':>9}{'her iyilesme':>11}"
          f"{'  --- SKOR ARTIRAN HAMLE ---':<28}")
    print(f"  {'model':<8}{'hedef':<7}{'test n':>8}{'MAE':>9}{'R2':>8}{'ikili':>9}"
          f"{'hizlanma':>11}{'model':>9}{'mevcut':>9}{'hizlanma':>11}{'egitim':>9}")
    print("  " + "-" * 100)

    results: dict[str, Any] = {}
    trained: dict[str, Any] = {}
    for mode in modes:
        for name in names:
            key = name if len(modes) == 1 else f"{name}:{mode}"
            started = time.perf_counter()
            try:
                model = fit_model(name, train, seed=args.seed, target=mode)
            except Exception as exc:
                print(f"  {key:<15} EGITILEMEDI: {exc}")
                continue
            seconds = time.perf_counter() - started
            res = M.evaluate(test.samples, model.predict)
            results[key] = {**res, "train_seconds": seconds, "target": mode}
            trained[key] = model
            print(_row(name, res, seconds, mode))

    if not trained:
        print("\n  hicbir model egitilemedi", file=sys.stderr)
        return 2

    # Kazanan SKOR ARTIRAN hamleyi ne kadar erken buldugu ile secilir.
    # "Her iyilesme" olcutuyle secmek, sirf HPWL'i kisaltan mikro hamleleri
    # one alan bir model uretiyor - olculdu, gercek kartta gerileme yapti.
    winner = max(
        results, key=lambda n: (results[n]["speedup_score"], results[n]["pairwise"])
    )
    print()
    print(f"  KAZANAN: {winner}  (skor hizlanmasi {results[winner]['speedup_score']:.2f}x, "
          f"ikili dogruluk {results[winner]['pairwise']:.3f})")
    if results[winner]["speedup_score"] <= 1.02 and winner != "mean":
        print("  UYARI: taban cizgisine gore kayda deger kazanc yok - "
              "daha fazla veri toplayin veya oznitelik ekleyin")

    if args.cv:
        print()
        print(f"  CAPRAZ DOGRULAMA ({args.cv} kat, kart bazli)")
        print(f"  {'model':<15}{'spearman':>10}{'ikili':>10}{'hizlanma':>10}"
              f"{'skor hizl.':>12}")
        print("  " + "-" * 57)
        for key in trained:
            name, _, mode = key.partition(":")
            cv = cross_validate(name, ds, args.cv, args.seed, mode or "value")
            results.setdefault(key, {})["cv"] = cv
            if cv:
                print(f"  {key:<15}{cv['spearman']:>10.3f}{cv['pairwise']:>10.3f}"
                      f"{cv['speedup']:>9.2f}x{cv['speedup_score']:>11.2f}x")

    # --- ELEME EGRISI (A3): genis repertuarda K'yi buradan secin, tahminle degil.
    win = results[winner]
    print()
    print("  ELEME RISKI - top-K kesiminden sag cikan SKOR ARTIRAN hamleler")
    print(f"  {'K':>5}{'hit (parti)':>14}{'recall':>10}   <- hit: en az bir iyilesme sag kaldi mi")
    print("  " + "-" * 45)
    for k, row in sorted(win["recall_score"].items()):
        print(f"  {k:>5}{row['hit']:>13.1%}{row['recall']:>10.1%}")
    safe = [k for k, row in sorted(win["recall_score"].items()) if row["hit"] >= 0.95]
    if safe:
        print(f"  hit >= %95 icin yeterli K: {safe[0]}  "
              f"(refine.WIDE_KEEP bunu karsilamali)")
    else:
        print("  UYARI: hicbir K'da hit %95'e ulasmiyor - eleme iyilesme kaybettiriyor")

    best = trained[winner]
    if isinstance(best, RidgeModel):
        print()
        print("  EN ETKILI OZNITELIKLER (standartlastirilmis katsayi)")
        for feat, w in best.top_features(ds.feature_names, 8):
            print(f"    {feat:<26}{w:>9.4f}")
    elif isinstance(best, GBTModel):
        print()
        print("  EN COK BOLUNEN OZNITELIKLER")
        for feat, c in best.feature_uses(ds.feature_names, 8):
            print(f"    {feat:<26}{c:>6}")

    if args.out:
        best.meta = {
            "dataset": str(args.dataset),
            "trained_on": summary,
            "test_metrics": {
                k: round(v, 4)
                for k, v in results[winner].items()
                if isinstance(v, (int, float))
            },
            "recall_score": {
                str(k): {m: round(v, 4) for m, v in row.items()}
                for k, row in results[winner]["recall_score"].items()
            },
        }
        best.save(args.out)
        print(f"\n  MODEL: {args.out}  ({args.out.stat().st_size / 1024:.0f} KB)")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps({"winner": winner, "results": results}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  JSON: {args.json}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
