"""Ridge (L2 cezali) dogrusal regresyon - saf Python.

Neden saf Python: proje bugune kadar `pyyaml` disinda bagimlilik almadi ve
`sexpr.py` bilerek bagimliliksiz yazildi. numpy/scikit-learn eklemek Windows
Store Python'da tekerlek/derleyici sorunlarina kapi acar; buradaki problem
boyutu (~50 oznitelik, birkac bin satir) ise saf Python icin fazlasiyla
kucuk. Normal denklemler + Cholesky, 50x50 icin milisaniyeler surer.

Ridge cezasi SIFIR DEGIL cunku oznitelikler kasten iliskili (or. `d_hpwl` ve
`d_hpwl_norm`); cezasiz cozumde XtX neredeyse tekil olur ve katsayilar
patlar.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

from .model import Model, register


def _standardize(X: Sequence[Sequence[float]]) -> tuple[list[float], list[float]]:
    """Sutun ortalamalari ve standart sapmalari (sifir sapma -> 1)."""
    n = len(X)
    p = len(X[0]) if n else 0
    means = [0.0] * p
    for row in X:
        for j in range(p):
            means[j] += row[j]
    means = [m / n for m in means] if n else means
    var = [0.0] * p
    for row in X:
        for j in range(p):
            d = row[j] - means[j]
            var[j] += d * d
    stds = [math.sqrt(v / n) if n else 1.0 for v in var]
    stds = [s if s > 1e-12 else 1.0 for s in stds]
    return means, stds


def _cholesky_solve(A: list[list[float]], b: list[float]) -> list[float]:
    """A simetrik pozitif tanimli iken A x = b cozumu."""
    n = len(A)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = A[i][j] - sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                if s <= 1e-12:
                    s = 1e-12  # sayisal guvenlik: matris tekile yaklastiysa
                L[i][i] = math.sqrt(s)
            else:
                L[i][j] = s / L[j][j]
    # ileri yerine koyma
    yv = [0.0] * n
    for i in range(n):
        yv[i] = (b[i] - sum(L[i][k] * yv[k] for k in range(i))) / L[i][i]
    # geri yerine koyma
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (yv[i] - sum(L[k][i] * x[k] for k in range(i + 1, n))) / L[i][i]
    return x


@register
class RidgeModel(Model):
    """Standartlastirilmis ridge regresyon."""

    kind = "ridge"

    def __init__(self, alpha: float = 1.0, **kw: Any) -> None:
        super().__init__(**kw)
        self.alpha = alpha
        self.weights: list[float] = []
        self.bias = 0.0
        self.means: list[float] = []
        self.stds: list[float] = []

    def fit(self, X: Sequence[Sequence[float]], y: Sequence[float]) -> "RidgeModel":
        if not X:
            raise ValueError("bos egitim kumesi")
        n, p = len(X), len(X[0])
        self.means, self.stds = _standardize(X)
        Z = [
            [(row[j] - self.means[j]) / self.stds[j] for j in range(p)]
            for row in X
        ]
        y_mean = sum(y) / n
        yc = [v - y_mean for v in y]

        # XtX ve Xty (simetriden yararlanarak yarim hesap)
        XtX = [[0.0] * p for _ in range(p)]
        Xty = [0.0] * p
        for i in range(n):
            row = Z[i]
            t = yc[i]
            for a in range(p):
                ra = row[a]
                if ra:
                    Xty[a] += ra * t
                    target = XtX[a]
                    for b in range(a, p):
                        target[b] += ra * row[b]
        for a in range(p):
            for b in range(a):
                XtX[a][b] = XtX[b][a]
            XtX[a][a] += self.alpha

        self.weights = _cholesky_solve(XtX, Xty)
        self.bias = y_mean
        return self

    def predict(self, x: Sequence[float]) -> float:
        total = self.bias
        for j, w in enumerate(self.weights):
            if w:
                total += w * (x[j] - self.means[j]) / self.stds[j]
        return total

    def top_features(self, names: Sequence[str], k: int = 10) -> list[tuple[str, float]]:
        """En buyuk mutlak katsayili oznitelikler.

        Standartlastirilmis uzayda oldugu icin katsayilar dogrudan
        karsilastirilabilir; hangi sinyalin isi yaptigini gorunur kilar.
        """
        pairs = list(zip(names, self.weights))
        pairs.sort(key=lambda kv: -abs(kv[1]))
        return pairs[:k]

    def _params(self) -> dict[str, Any]:
        return {
            "alpha": self.alpha,
            "bias": self.bias,
            # 12 hane: dosya hala okunabilir ama yeniden yuklenen model
            # birebir ayni tahmini verir. 8 hanede ortalama/sapma yuvarlamasi
            # bolme sirasinda 1e-8 mertebesinde sapma uretiyordu.
            "weights": [round(w, 12) for w in self.weights],
            "means": [round(m, 12) for m in self.means],
            "stds": [round(s, 12) for s in self.stds],
        }

    def _load_params(self, params: dict[str, Any]) -> None:
        self.alpha = float(params.get("alpha", 1.0))
        self.bias = float(params.get("bias", 0.0))
        self.weights = [float(v) for v in params.get("weights", [])]
        self.means = [float(v) for v in params.get("means", [])]
        self.stds = [float(v) for v in params.get("stds", [])]
