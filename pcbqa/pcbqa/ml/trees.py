"""Gradyan artirmali regresyon agaclari (GBT) - saf Python, histogram tabanli.

Ridge'in yakalayamadigi sey etkilesimler: "kondansator icin `d_hpwl` cok
onemli ama konnektor icin degil", "`d_overlaps` negatifse gerisi onemsiz".
Bunlar carpim terimleri; dogrusal model ancak elle yazarsaniz gorur, agac
kendiliginden bulur.

Hiz icin iki karar:

* **Histogram bolme.** Oznitelik degerleri bir kez nicem (quantile) kutularina
  cevrilir; her dugumde bolme aramasi kutu histogrami uzerinden yapilir, yani
  maliyet O(ornek x oznitelik), siralama yok.
* **Alt orneklem.** Her agac satirlarin ve sutunlarin bir kismini gorur; hem
  hizlandirir hem asiri uyumu azaltir.

Egitim maliyeti kabaca `agac x derinlik x ornek x sutun` islemdir. Saf
Python'da 5.000 ornek / 60 agac / derinlik 3 yaklasik yarim dakika surer;
tahmin ise agac basina birkac karsilastirma, yani mikrosaniye.
"""

from __future__ import annotations

import random
from bisect import bisect_left
from typing import Any, Sequence

from .model import Model, register

# Yaprak: {"v": deger}  |  Dal: {"f": sutun, "t": esik, "l": ..., "r": ...}
Node = dict[str, Any]


def _bin_edges(values: list[float], max_bins: int) -> list[float]:
    """Nicem tabanli kutu sinirlari (artan, tekrarsiz)."""
    uniq = sorted(set(values))
    if len(uniq) <= 1:
        return []
    if len(uniq) <= max_bins:
        return [(uniq[i] + uniq[i + 1]) / 2.0 for i in range(len(uniq) - 1)]
    ordered = sorted(values)
    edges: list[float] = []
    n = len(ordered)
    for b in range(1, max_bins):
        v = ordered[min(n - 1, int(n * b / max_bins))]
        if not edges or v > edges[-1]:
            edges.append(v)
    return edges


class _Builder:
    """Tek bir agaci kurar. Histogramlar dugum bazinda yeniden hesaplanir."""

    def __init__(
        self,
        binned: list[list[int]],      # sutun bazli kutu indisleri
        edges: list[list[float]],
        n_bins: list[int],
        max_depth: int,
        min_samples_leaf: int,
        l2: float,
    ) -> None:
        self.binned = binned
        self.edges = edges
        self.n_bins = n_bins
        self.max_depth = max_depth
        self.min_leaf = min_samples_leaf
        self.l2 = l2

    def build(
        self, rows: list[int], grad: list[float], columns: list[int], depth: int
    ) -> Node:
        total = 0.0
        for i in rows:
            total += grad[i]
        count = len(rows)
        leaf = {"v": total / (count + self.l2)}
        if depth >= self.max_depth or count < 2 * self.min_leaf:
            return leaf

        best_gain = 1e-12
        best: tuple[int, int] | None = None
        parent = total * total / (count + self.l2)

        for j in columns:
            nb = self.n_bins[j]
            if nb < 2:
                continue
            col = self.binned[j]
            hist_g = [0.0] * nb
            hist_n = [0] * nb
            for i in rows:
                b = col[i]
                hist_g[b] += grad[i]
                hist_n[b] += 1
            gl = 0.0
            nl = 0
            for b in range(nb - 1):
                gl += hist_g[b]
                nl += hist_n[b]
                nr = count - nl
                if nl < self.min_leaf or nr < self.min_leaf:
                    continue
                gr = total - gl
                gain = gl * gl / (nl + self.l2) + gr * gr / (nr + self.l2) - parent
                if gain > best_gain:
                    best_gain = gain
                    best = (j, b)

        if best is None:
            return leaf

        j, b = best
        col = self.binned[j]
        left = [i for i in rows if col[i] <= b]
        right = [i for i in rows if col[i] > b]
        if not left or not right:
            return leaf
        return {
            "f": j,
            "t": self.edges[j][b],
            "l": self.build(left, grad, columns, depth + 1),
            "r": self.build(right, grad, columns, depth + 1),
        }


def _predict_tree(node: Node, x: Sequence[float]) -> float:
    while "v" not in node:
        node = node["l"] if x[node["f"]] <= node["t"] else node["r"]
    return node["v"]


@register
class GBTModel(Model):
    """Gradyan artirmali regresyon agaclari (kare hata)."""

    kind = "gbt"

    def __init__(
        self,
        n_trees: int = 60,
        learning_rate: float = 0.1,
        max_depth: int = 3,
        min_samples_leaf: int = 8,
        max_bins: int = 24,
        subsample: float = 0.7,
        colsample: float = 0.7,
        l2: float = 1.0,
        seed: int = 0,
        **kw: Any,
    ) -> None:
        super().__init__(**kw)
        self.n_trees = n_trees
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.max_bins = max_bins
        self.subsample = subsample
        self.colsample = colsample
        self.l2 = l2
        self.seed = seed
        self.base = 0.0
        self.trees: list[Node] = []

    # -------------------------------------------------------------------- fit

    def fit(self, X: Sequence[Sequence[float]], y: Sequence[float]) -> "GBTModel":
        if not X:
            raise ValueError("bos egitim kumesi")
        n, p = len(X), len(X[0])
        rng = random.Random(self.seed)

        columns = [[float(row[j]) for row in X] for j in range(p)]
        edges = [_bin_edges(col, self.max_bins) for col in columns]
        binned = [
            [bisect_left(edges[j], v) for v in columns[j]] if edges[j] else [0] * n
            for j in range(p)
        ]
        n_bins = [len(edges[j]) + 1 for j in range(p)]

        self.base = sum(y) / n
        pred = [self.base] * n
        self.trees = []

        n_sub = max(1, int(n * self.subsample))
        n_col = max(1, int(p * self.colsample))
        builder = _Builder(
            binned, edges, n_bins, self.max_depth, self.min_samples_leaf, self.l2
        )

        for _ in range(self.n_trees):
            grad = [(y[i] - pred[i]) for i in range(n)]
            rows = (
                rng.sample(range(n), n_sub) if n_sub < n else list(range(n))
            )
            cols = (
                rng.sample(range(p), n_col) if n_col < p else list(range(p))
            )
            tree = builder.build(rows, grad, cols, 0)
            self._scale(tree, self.learning_rate)
            self.trees.append(tree)
            for i in range(n):
                pred[i] += _predict_tree(tree, X[i])
        return self

    def _scale(self, node: Node, factor: float) -> None:
        if "v" in node:
            node["v"] *= factor
            return
        self._scale(node["l"], factor)
        self._scale(node["r"], factor)

    # ---------------------------------------------------------------- tahmin

    def predict(self, x: Sequence[float]) -> float:
        total = self.base
        for tree in self.trees:
            total += _predict_tree(tree, x)
        return total

    def feature_uses(self, names: Sequence[str], k: int = 10) -> list[tuple[str, int]]:
        """Hangi oznitelik kac kez bolme icin kullanildi (kaba onem olcusu)."""
        counts: dict[int, int] = {}

        def walk(node: Node) -> None:
            if "v" in node:
                return
            counts[node["f"]] = counts.get(node["f"], 0) + 1
            walk(node["l"])
            walk(node["r"])

        for tree in self.trees:
            walk(tree)
        pairs = [(names[j] if j < len(names) else str(j), c) for j, c in counts.items()]
        pairs.sort(key=lambda kv: -kv[1])
        return pairs[:k]

    # -------------------------------------------------------------- depolama

    def _params(self) -> dict[str, Any]:
        return {
            "n_trees": self.n_trees,
            "learning_rate": self.learning_rate,
            "max_depth": self.max_depth,
            "min_samples_leaf": self.min_samples_leaf,
            "max_bins": self.max_bins,
            "subsample": self.subsample,
            "colsample": self.colsample,
            "l2": self.l2,
            "seed": self.seed,
            "base": self.base,
            "trees": self.trees,
        }

    def _load_params(self, params: dict[str, Any]) -> None:
        self.n_trees = int(params.get("n_trees", 60))
        self.learning_rate = float(params.get("learning_rate", 0.1))
        self.max_depth = int(params.get("max_depth", 3))
        self.min_samples_leaf = int(params.get("min_samples_leaf", 8))
        self.max_bins = int(params.get("max_bins", 24))
        self.subsample = float(params.get("subsample", 0.7))
        self.colsample = float(params.get("colsample", 0.7))
        self.l2 = float(params.get("l2", 1.0))
        self.seed = int(params.get("seed", 0))
        self.base = float(params.get("base", 0.0))
        self.trees = list(params.get("trees", []))
