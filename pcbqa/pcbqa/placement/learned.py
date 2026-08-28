"""LEARNED - `auto` ile ayni yerlestirici, ustune ogrenilmis hamle siralamasi.

`auto` ile arasindaki TEK fark, cilanin aday hamleleri hangi sirayla
denedigidir. Kabul karari, gerileme korumasi, taban aday - hepsi aynen
duruyor. Yani:

  * Model iyi calisirsa ayni butcede daha cok iyilesme yakalanir.
  * Model tamamen yanilirsa sonuc `auto` ile ayni kalir, sadece biraz yavas
    (oznitelik cikarimi bedava degil). **Gerileme uretemez** - cunku bir
    hamlenin kabulu hala `ctx.evaluate` ile karara baglaniyor.

Bu, ML'i sisteme sokmanin guvenli yolu: model KARAR vermez, SIRA onerir.

Model yoksa (`pcbqa/ml/models/move-v<sema>.json` bulunamazsa) sinif sessizce
`auto` gibi davranir; yani depo modelsiz de calisir.
"""

from __future__ import annotations

import time
from pathlib import Path

from .base import Compound, Evaluation, Placement, PlacementContext
from .cluster import ClusterPlacer
from . import refine
# Butce politikasi `auto` ile ORTAK tutulur: `learned`in tek farki hamle
# SIRALAYICISI olmali. Bolusum de ayrilirsa iki kolun karsilastirmasi
# anlamini yitirir (olcum notlari icin bkz. `auto.py`).
from .auto import COARSE_SHARE, POLISH_SPLIT

# Egitilmis modelin varsayilan yeri. `python -m pcbqa.ml.train --out ...`
#
# Dosya adi OZNITELIK SURUMUNDEN turetilir, elle yazilmaz. Neden: Faz C'de
# sema v3'e cikip model move-v3.json olarak egitildi ama buradaki sabit
# "move-v2.json" olarak kaldi. Model bulunamayinca sinif - belgelendigi gibi -
# sessizce `auto` gibi davraniyor, yani `learned` FAZ C'DEN BERI ETKISIZDI.
#
# Fark edilmemesinin sebebi ogretici: beklenen sonuc zaten "learned ~ auto"
# oldugu icin hata kendi kamuflajini yapti. Ada surumu baglamak, sema
# degistiginde yolun da degismesini ve model egitilmemisse SESSIZ degil
# gorunur bir bosluk olusmasini saglar.
MODELS_DIR = Path(__file__).resolve().parent.parent / "ml" / "models"


def default_model_path() -> Path:
    """Su anki oznitelik semasina karsilik gelen model dosyasi."""
    from ..ml import features as F

    return MODELS_DIR / f"move-v{F.FEATURE_VERSION}.json"

# Oznitelik cikarimi da zaman yiyor; cok kisa listelerde siralamanin getirisi
# maliyetini karsilamaz.
MIN_MOVES_TO_RANK = 4


class ModelRanker:
    """Aday BIRLESIK hamleleri modelin tahminine gore buyukten kucuge dizer.

    `top_k` verilirse liste kisaltilir da. Varsayilani None (eleme YOK):
    eleme, modelin dusuk puan verdigi bir iyilesmeyi tamamen kaybettirebilir,
    sira degistirmek ise hicbir sey kaybettirmez. Genis repertuar asamasinda
    (Asama 6) eleme ZORUNLU hale gelir - takas O(n^2) aday uretir ve hepsini
    gercek hakemle denemek imkansiz - ama orada kesmeyi `refine.polish`
    yapiyor, cunku ayni kesme `auto` icin de rastgele uygulanmali (adil A/B).
    """

    def __init__(self, featurizer, model, top_k: int | None = None) -> None:
        self.featurizer = featurizer
        self.model = model
        self.top_k = top_k
        self.calls = 0
        self.ranked = 0
        self._stamp: tuple[int, float] | None = None

    def __call__(
        self, placement: Placement, evaluation: Evaluation, moves: list[Compound]
    ) -> list[Compound]:
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
        for compound in moves:
            try:
                value = self.model.predict(self.featurizer.features_compound(compound))
            except Exception:
                value = 0.0
            scored.append((value, compound))
        scored.sort(key=lambda kv: -kv[0])
        ordered = [m for _, m in scored]
        return ordered[: self.top_k] if self.top_k else ordered


def make_ranker(ctx: PlacementContext, model_path: Path | None = None, top_k: int | None = None):
    """Model dosyasindan bir siralayici kurar. Model yoksa None doner."""
    from ..ml import features as F
    from ..ml import model as ml_model

    path = Path(model_path) if model_path else default_model_path()
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

    def __init__(
        self,
        model_path: Path | None = None,
        top_k: int | None = None,
        wide: bool = False,
    ) -> None:
        self.model_path = model_path
        self.top_k = top_k
        # Genis repertuar (Asama 6 / Faz A) varsayilan olarak KAPALI - `auto`
        # ile ayni sebeple (bkz. refine.WIDE_SHARE). Acildiginda modelin isi
        # nitel olarak degisir: siralamak degil, ELEMEK.
        self.wide = wide
        self.ranker: ModelRanker | None = None

    def run(self, ctx: PlacementContext) -> Placement:
        started = time.perf_counter()
        deadline = started + ctx.time_budget_s
        current = ctx.current()
        current_eval = ctx.evaluate(current)

        try:
            self.ranker = make_ranker(ctx, self.model_path, self.top_k)
        except Exception:
            self.ranker = None  # bozuk/eski model dosyasi arama'yi durdurmasin

        # ctx DEGISTIRILMEZ (sozlesme: girdi salt-okunur). Siralayici, cilaya
        # verilen turetilmis baglamlara takilir.
        def child(budget: float) -> PlacementContext:
            sub = PlacementContext(
                design=ctx.design,
                locked=ctx.locked,
                seed=ctx.seed,
                time_budget_s=budget,
                evaluator=ctx.evaluator,
                move_ranker=self.ranker,
            )
            sub.allow_wide_moves = self.wide or getattr(ctx, "allow_wide_moves", False)
            return sub

        coarse_budget = ctx.time_budget_s * COARSE_SHARE
        try:
            coarse = dict(current)
            coarse.update(ClusterPlacer().run(child(coarse_budget)))
        except Exception:
            coarse = dict(current)
        coarse_eval = ctx.evaluate(coarse)

        # Cila paylari: ilki sabit oran, ikincisi duvar saatinden - birinci
        # cila erken tukenirse artik ikinciye gecsin (bkz. auto.py).
        remaining = max(0.0, deadline - time.perf_counter())
        first = remaining * POLISH_SPLIT
        polished_coarse, polished_coarse_eval = refine.polish_scored(
            coarse, child(first), budget_s=first, start_eval=coarse_eval
        )
        remaining = max(0.0, deadline - time.perf_counter())
        polished_current, polished_current_eval = refine.polish_scored(
            current, child(remaining), budget_s=remaining, start_eval=current_eval
        )

        _, best, _ = refine.keep_best(
            {
                "mevcut": current,
                "kaba": coarse,
                "cilali-kaba": polished_coarse,
                "cilali-mevcut": polished_current,
            },
            ctx,
            known={
                "mevcut": current_eval,
                "kaba": coarse_eval,
                "cilali-kaba": polished_coarse_eval,
                "cilali-mevcut": polished_current_eval,
            },
        )
        return best
