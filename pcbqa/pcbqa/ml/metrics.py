"""Metrikler: regresyon dogrulugu VE - asil onemlisi - siralama kalitesi.

Bir modelin R^2'si yuksek diye ise yaramaz. Yerel arama modeli yalnizca
"hangi adayi once deneyelim" diye kullanir; onemli olan aday listesi ICINDE
dogru siralama yapmasidir. Bu yuzden buradaki asil olcut `evals_to_first_gain`:

    Rastgele sirada ilk iyilestiren hamleyi bulmak icin ortalama kac gercek
    degerlendirme gerekiyordu, model sirasinda kac gerekiyor?

Bu sayi dogrudan hiz kazancina cevrilir; R^2 cevrilmez.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Sequence

Number = float


def mae(actual: Sequence[float], predicted: Sequence[float]) -> float:
    if not actual:
        return 0.0
    return sum(abs(a - p) for a, p in zip(actual, predicted)) / len(actual)


def rmse(actual: Sequence[float], predicted: Sequence[float]) -> float:
    if not actual:
        return 0.0
    return math.sqrt(sum((a - p) ** 2 for a, p in zip(actual, predicted)) / len(actual))


def r2(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Aciklanan varyans orani. Sabit tahmin 0, mukemmel tahmin 1."""
    if len(actual) < 2:
        return 0.0
    mean = sum(actual) / len(actual)
    ss_tot = sum((a - mean) ** 2 for a in actual)
    if ss_tot <= 1e-12:
        return 0.0
    ss_res = sum((a - p) ** 2 for a, p in zip(actual, predicted))
    return 1.0 - ss_res / ss_tot


def spearman(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Sira korelasyonu (baglar ortalama sirayla)."""
    n = len(actual)
    if n < 2:
        return 0.0
    ra, rb = _ranks(actual), _ranks(predicted)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = math.sqrt(sum((x - ma) ** 2 for x in ra))
    db = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return num / (da * db) if da > 0 and db > 0 else 0.0


def _ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        shared = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = shared
        i = j + 1
    return ranks


# --------------------------------------------------------------- siralama


def pairwise_accuracy(batches: Sequence[Sequence[tuple[float, float]]]) -> float:
    """Parti icindeki (gercek, tahmin) ciftlerinde uyumlu cift orani.

    Esit gercek degerli ciftler sayilmaz - onlarda "dogru siralama" diye bir
    sey yoktur (etiketlerin cogu tam 0'dir, hepsini sayarsak metrik sisar).
    """
    concordant = 0.0
    total = 0
    for batch in batches:
        n = len(batch)
        for i in range(n):
            ai, pi = batch[i]
            for j in range(i + 1, n):
                aj, pj = batch[j]
                if abs(ai - aj) <= 1e-9:
                    continue
                total += 1
                if abs(pi - pj) <= 1e-12:
                    concordant += 0.5  # berabere TAHMIN: yazi-tura sayilir
                elif (ai > aj) == (pi > pj):
                    concordant += 1.0
    return concordant / total if total else 0.0


def evals_to_first_gain(
    batches: Sequence[Sequence[tuple[float, float]]], threshold: float = 1e-9
) -> dict[str, float]:
    """Ilk iyilestiren hamleye kac degerlendirmede ulasiliyor.

    Yalnizca en az bir iyilestiren adayi olan partiler sayilir; digerlerinde
    siralamanin bir anlami yok (hepsi denenir ve hicbiri kabul edilmez).

    UC sira karsilastirilir ve DOGRU KIYAS ikincisidir:

      * `random` - kapali formul: n adayin k tanesi iyi ise ilk iyinin
        beklenen sirasi (n+1)/(k+1).
      * `order`  - **partinin kendi sirasi**, yani `polish`in bugun dendigi
        sira. Kazanc buna gore olculmeli: hamle ureteci zaten rastgele degil
        (bulgu hamleleri yaricap sirasina dizili), dolayisiyla rastgele
        formulunu taban almak modele haksiz avantaj verir.
      * `model`  - tahmine gore azalan sira.
    """
    model_ranks: list[float] = []
    order_ranks: list[float] = []
    random_ranks: list[float] = []
    hit_at_1 = 0
    for batch in batches:
        k = sum(1 for a, _ in batch if a > threshold)
        if not k:
            continue
        n = len(batch)
        ordering = sorted(range(n), key=lambda i: -batch[i][1])
        rank = next(
            (pos + 1 for pos, i in enumerate(ordering) if batch[i][0] > threshold), n
        )
        model_ranks.append(float(rank))
        order_ranks.append(float(next(i + 1 for i in range(n) if batch[i][0] > threshold)))
        random_ranks.append((n + 1) / (k + 1))
        hit_at_1 += 1 if rank == 1 else 0
    if not model_ranks:
        return {
            "batches": 0.0,
            "model": 0.0,
            "order": 0.0,
            "random": 0.0,
            "speedup": 1.0,
            "top1": 0.0,
        }
    model_mean = sum(model_ranks) / len(model_ranks)
    order_mean = sum(order_ranks) / len(order_ranks)
    random_mean = sum(random_ranks) / len(random_ranks)
    return {
        "batches": float(len(model_ranks)),
        "model": model_mean,
        "order": order_mean,
        "random": random_mean,
        "speedup": (order_mean / model_mean) if model_mean > 0 else 1.0,
        "top1": hit_at_1 / len(model_ranks),
    }


def recall_at_k(
    batches: Sequence[Sequence[tuple[float, float]]],
    ks: Sequence[int] = (4, 8, 12, 16, 24),
    threshold: float = 1e-9,
) -> dict[int, dict[str, float]]:
    """ELEME riskini olcer: top-K kesiminden kac iyilestiren hamle sag cikiyor.

    Siralama kayipsizdir - sirayi degistirmek hicbir adayi yok etmez, sadece
    daha erken bulur. **Eleme oyle degildir**: modelin dusuk puan verdigi bir
    iyilesme tamamen kaybolur ve arama onu bir daha goremez. Genis repertuarda
    eleme zorunlu oldugu icin (takas O(n^2) aday uretir) K'yi tahminle degil bu
    egriyle secmek gerekir.

    Iki sayi doner ve **karar verdirici olan `hit`tir**:

      * `recall` - iyilestiren hamlelerin yuzde kaci top-K icinde.
      * `hit`    - partilerin yuzde kacinda top-K icinde EN AZ BIR iyilestiren
        hamle var. Yerel arama ilk iyilesmeyi kabul edip durdugu icin
        gerceklen gereken sey budur; digerlerini kaybetmek maliyetsizdir.
    """
    out: dict[int, dict[str, float]] = {}
    usable = [b for b in batches if any(a > threshold for a, _ in b)]
    for k in ks:
        if not usable:
            out[k] = {"recall": 0.0, "hit": 0.0, "batches": 0.0}
            continue
        recalls: list[float] = []
        hits = 0
        for batch in usable:
            order = sorted(range(len(batch)), key=lambda i: -batch[i][1])[:k]
            good_total = sum(1 for a, _ in batch if a > threshold)
            kept = sum(1 for i in order if batch[i][0] > threshold)
            recalls.append(kept / good_total)
            hits += 1 if kept else 0
        out[k] = {
            "recall": sum(recalls) / len(recalls),
            "hit": hits / len(usable),
            "batches": float(len(usable)),
        }
    return out


def evaluate(
    samples: Sequence[Any],
    predict: Callable[[list[float]], float],
) -> dict[str, Any]:
    """Bir model icin tum metrikleri hesaplar.

    `samples` `dataset.Sample` listesi; `predict` tek vektor alir.
    """
    actual = [s.label for s in samples]
    predicted = [predict(s.features) for s in samples]

    by_batch: dict[str, list[tuple[float, float]]] = {}
    by_batch_score: dict[str, list[tuple[float, float]]] = {}
    for s, p in zip(samples, predicted):
        key = f"{s.group}|{s.batch}"
        by_batch.setdefault(key, []).append((s.label, p))
        by_batch_score.setdefault(key, []).append(
            (float(s.extra.get("d_score", s.label)), p)
        )
    batches = [b for b in by_batch.values() if len(b) > 1]
    score_batches = [b for b in by_batch_score.values() if len(b) > 1]

    search = evals_to_first_gain(batches)
    # Ikinci olcum yalnizca SKORU artiran hamleleri "iyi" sayar. Ayri
    # tutulmasinin sebebi: veri kumesinde etiketi pozitif olan hamlelerin
    # buyuk cogunlugu skoru hic degistirmiyor, sadece HPWL'i kisaltiyor.
    # Cila esas olarak bulgu kapatmak icin var; asil bakilacak sutun bu.
    score_search = evals_to_first_gain(score_batches)
    return {
        "n": len(samples),
        "mae": mae(actual, predicted),
        "rmse": rmse(actual, predicted),
        "r2": r2(actual, predicted),
        "spearman": spearman(actual, predicted),
        "pairwise": pairwise_accuracy(batches),
        "evals_model": search["model"],
        "evals_order": search["order"],
        "evals_random": search["random"],
        "speedup": search["speedup"],
        "top1": search["top1"],
        "ranked_batches": int(search["batches"]),
        "evals_model_score": score_search["model"],
        "evals_order_score": score_search["order"],
        "speedup_score": score_search["speedup"],
        "scored_batches": int(score_search["batches"]),
        # Eleme riski: hem "her iyilesme" hem "skor artiran" olcutuyle
        "recall": recall_at_k(batches),
        "recall_score": recall_at_k(score_batches),
    }
