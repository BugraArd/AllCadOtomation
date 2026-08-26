"""LEARNED - `auto` ile ayni yerlestirici, ustune ogrenilmis hamle siralamasi.

`auto` ile arasindaki TEK fark, cilanin aday hamleleri hangi sirayla
denedigidir. Kabul karari, gerileme korumasi, taban aday - hepsi aynen
duruyor. Yani:

  * Model iyi calisirsa ayni butcede daha cok iyilesme yakalanir.
  * Model tamamen yanilirsa sonuc `auto` ile ayni kalir, sadece biraz yavas
    (oznitelik cikarimi bedava degil). **Gerileme uretemez** - cunku bir
    hamlenin kabulu hala `ctx.evaluate` ile karara baglaniyor.

Bu, ML'i sisteme sokmanin guvenli yolu: model KARAR vermez, SIRA onerir.

Model yoksa (`pcbqa/ml/models/move-v1.json` bulunamazsa) sinif sessizce
`auto` gibi davranir; yani depo modelsiz de calisir.
"""

from __future__ import annotations

import time
from pathlib import Path

from .base import Evaluation, Move, Placement, PlacementContext
from .cluster import ClusterPlacer
from . import refine

# Egitilmis modelin varsayilan yeri. `python -m pcbqa.ml.train --out ...`
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent / "ml" / "models" / "move-v1.json"

COARSE_SHARE = 0.45
# Oznitelik cikarimi da zaman yiyor; cok kisa listelerde siralamanin getirisi
# maliyetini karsilamaz.
MIN_MOVES_TO_RANK = 4


class ModelRanker:
    """Aday hamleleri modelin tahminine gore buyukten kucuge dizer.

    `top_k` verilirse liste kisaltilir da. Varsayilani None (eleme YOK) -
    eleme, modelin dusuk puan verdigi bir iyilesmeyi tamamen kaybettirebilir;
    yalnizca sira degistirmek ise hicbir sey kaybettirmez, sadece erken bulur.
    """

    def __init__(self, featurizer, model, top_k: int | None = None) -> None:
        self.featurizer = featurizer
        self.model = model
        self.top_k = top_k
        self.calls = 0
        self.ranked = 0
        self._stamp: tuple[int, float] | None = None

    def __call__(
        self, placement: Placement, evaluation: Evaluation, moves: list[Move]
    ) -> list[Move]:
        if len(moves) < MIN_MOVES_TO_RANK:
            return moves
        # Yerlesim degistiyse onbellekleri tazele. Kimlik + skor damgasi,
        # her cagride tam sozluk karsilastirmasindan cok daha ucuz.
        stamp = (id(placement), evaluation.score if evaluation else 0.0)
        if stamp != self._stamp:
            self.featurizer.refresh(placement, evaluation)
            self._stamp = stamp
        self.calls += 1
        self.ranked += len(moves)
        scored = []
        for move in moves:
            ref, xyr = move
            try:
                value = self.model.predict(self.featurizer.features(ref, xyr))
            except Exception:
                value = 0.0
            scored.append((value, move))
        scored.sort(key=lambda kv: -kv[0])
        ordered = [m for _, m in scored]
        return ordered[: self.top_k] if self.top_k else ordered


def make_ranker(ctx: PlacementContext, model_path: Path | None = None, top_k: int | None = None):
    """Model dosyasindan bir siralayici kurar. Model yoksa None doner."""
    from ..ml import features as F
    from ..ml import model as ml_model

    path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
    if not path.exists():
        return None
    model = ml_model.load(path)
    # Sema uyusmuyorsa sessizce yanlis tahmin etmektense siralamayi kapat.
    model.check_schema(F.FEATURE_NAMES, F.FEATURE_VERSION)
    featurizer = F.MoveFeaturizer(ctx.design, ctx.locked)
    return ModelRanker(featurizer, model, top_k=top_k)


class Learned:
    """Ogrenilmis siralamayla calisan uretim yerlestiricisi."""

    name = "learned"

    def __init__(self, model_path: Path | None = None, top_k: int | None = None) -> None:
        self.model_path = model_path
        self.top_k = top_k
        self.ranker: ModelRanker | None = None

    def run(self, ctx: PlacementContext) -> Placement:
        started = time.perf_counter()
        current = ctx.current()

        try:
            self.ranker = make_ranker(ctx, self.model_path, self.top_k)
        except Exception:
            self.ranker = None  # bozuk/eski model dosyasi arama'yi durdurmasin

        # ctx DEGISTIRILMEZ (sozlesme: girdi salt-okunur). Siralayici, cilaya
        # verilen turetilmis baglamlara takilir.
        def child(budget: float) -> PlacementContext:
            return PlacementContext(
                design=ctx.design,
                locked=ctx.locked,
                seed=ctx.seed,
                time_budget_s=budget,
                evaluator=ctx.evaluator,
                move_ranker=self.ranker,
            )

        coarse_budget = ctx.time_budget_s * COARSE_SHARE
        try:
            coarse = dict(current)
            coarse.update(ClusterPlacer().run(child(coarse_budget)))
        except Exception:
            coarse = dict(current)

        remaining = max(0.0, ctx.time_budget_s - (time.perf_counter() - started))
        polished_coarse = refine.polish(coarse, child(remaining * 0.6), budget_s=remaining * 0.6)
        polished_current = refine.polish(current, child(remaining * 0.4), budget_s=remaining * 0.4)

        _, best, _ = refine.keep_best(
            {
                "mevcut": current,
                "kaba": coarse,
                "cilali-kaba": polished_coarse,
                "cilali-mevcut": polished_current,
            },
            ctx,
        )
        return best
