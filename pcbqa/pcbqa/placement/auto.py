"""AUTO - uretim yerlestiricisi (Asama 3'un ciktisi).

Yarisan dort motorun tek tek zaafi vardi: sentetik tezgahta hedefi tutturuyor
ama gercek kartta (`pic_programmer`) uctan ucu bozabiliyorlardi. `auto` bunu
uc katmanla cozer:

  1. KABA YERLESIM - `cluster` ile sifirdan bir aday uretilir. (Yarismada
     gercek kartta gerilemeyen tek motor oydu.)
  2. CILA - `refine.polish` hakemin gercek puanini optimize eder; hamleler
     bulgulardan uretildigi icin kil payi kacan kurallar kapanir.
  3. TABAN - kartin MEVCUT hali de bir aday olarak yarisir. Kaba yerlesim
     iyi bir karti bozuyorsa `auto` mevcut hali secer.

3. madde yuzunden `auto` tanim geregi hicbir karti kotulestiremez.
"""

from __future__ import annotations

import time

from .base import Placement, PlacementContext
from .cluster import ClusterPlacer
from . import refine

# Butcenin kaba yerlesime ayrilan payi; kalani cilaya gider.
COARSE_SHARE = 0.45


class Auto:
    """Kaba yerlesim + hakem gudumlu cila + regresyon tabani."""

    name = "auto"

    def run(self, ctx: PlacementContext) -> Placement:
        started = time.perf_counter()
        current = ctx.current()

        # 1) Kaba yerlesim - kendi butcesiyle
        coarse_budget = ctx.time_budget_s * COARSE_SHARE
        coarse_ctx = PlacementContext(
            design=ctx.design,
            locked=ctx.locked,
            seed=ctx.seed,
            time_budget_s=coarse_budget,
            evaluator=ctx.evaluator,
        )
        try:
            coarse = dict(current)
            coarse.update(ClusterPlacer().run(coarse_ctx))
        except Exception:
            # Kaba motor patlarsa mevcut yerlesimle devam et - cila yine calisir.
            coarse = dict(current)

        # 2) Cila - kalan butce, iki aday icin bolusturulur
        remaining = max(0.0, ctx.time_budget_s - (time.perf_counter() - started))
        polished_coarse = refine.polish(coarse, ctx, budget_s=remaining * 0.6)
        polished_current = refine.polish(current, ctx, budget_s=remaining * 0.4)

        # 3) Taban dahil en iyisini sec
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
