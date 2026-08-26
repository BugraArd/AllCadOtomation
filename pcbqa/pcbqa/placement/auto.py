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
#
# 19 kartlik pakette olculdu (butce 15 sn): kaba fazi tamamen kaldirmak
# toplam skoru 60,4 puan DUSURUYOR (complex_hierarchy -24,0, mixer-unrouted
# -15,6, video -11,8, sonde -7,7), payi 0,30'a cekmek ise gurultu bandinda
# kaliyor (+4,9, tamami iki oynak karttan). Yani 0,45 pahali ama hak ediyor.
COARSE_SHARE = 0.45

# Cila butcesinin KABA adaya ayrilan payi; kalani mevcut hale gider.
#
# Eskiden 0,60 idi. Olcum: cila(mevcut) dali DOYUYOR - payini %40'tan %100'e
# cikarmak 17 kartin yalnizca 3'unde bir sey degistiriyor (toplam +23).
# Kaba dali ise hala tirmaniyor. Payi 0,75'e cekmek toplam skoru
# 1433,5 -> 1444,9 yapti (interf_u +7,6, complex_hierarchy +2,8, video +1,8,
# tinytapeout -0,8). Mevcut hal yarista aday olarak durdugu icin gerileme
# garantisi bu degisiklikten etkilenmez.
POLISH_SPLIT = 0.75


class Auto:
    """Kaba yerlesim + hakem gudumlu cila + regresyon tabani."""

    name = "auto"

    def run(self, ctx: PlacementContext) -> Placement:
        started = time.perf_counter()
        deadline = started + ctx.time_budget_s
        current = ctx.current()
        current_eval = ctx.evaluate(current)

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
        coarse_eval = ctx.evaluate(coarse)

        # 2) Cila - kalan butce, iki aday icin bolusturulur.
        #
        # Ikinci payin duvar saatinden YENIDEN hesaplanmasi sart: birinci cila
        # erken tukenebiliyor (kucuk kartlarda payinin dortte birini kullanip
        # donuyor) ve onceden bolusturuldugunde o artik kimseye gecmiyordu.
        remaining = max(0.0, deadline - time.perf_counter())
        polished_coarse, polished_coarse_eval = refine.polish_scored(
            coarse, ctx, budget_s=remaining * POLISH_SPLIT, start_eval=coarse_eval
        )
        remaining = max(0.0, deadline - time.perf_counter())
        polished_current, polished_current_eval = refine.polish_scored(
            current, ctx, budget_s=remaining, start_eval=current_eval
        )

        # 3) Taban dahil en iyisini sec. Dort adayin da puani ELDE - secim
        # asamasi butce disinda kaldigi icin yeniden puanlamak dogrudan
        # asim demek (buyuk kartlarda aday basina saniyeler).
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
