"""Yerlestirme stratejileri.

Yeni bir yerlestirici eklemek icin:
  1. Bu klasorde bir modul yazin (or. `force.py`)
  2. base.Placer arayuzunu uygulayin
  3. Asagidaki PLACERS sozlugune kaydedin

Hakem `python -m pcbqa.harness --placer <ad>` ile calistirir.
"""

from __future__ import annotations

from .base import Placement, PlacementContext, Placer, validate
from .anneal import SimulatedAnnealing
from .auto import Auto
from .baseline import Identity, RandomShuffle
from .cluster import ClusterPlacer
from .codex import Codex
from .force import ForcePlacer
from .learned import Learned

# ad -> yerlestirici fabrikasi
PLACERS: dict[str, type] = {
    # Referans alt sinirlar (hakem dogrulamasi)
    "identity": Identity,
    "random": RandomShuffle,
    # Uretim yerlestiricisi (Asama 3 ciktisi)
    "auto": Auto,
    # Asama 5: auto + ogrenilmis hamle siralamasi (bkz. pcbqa/ml/)
    "learned": Learned,
    # Yarisan yerlestiriciler
    "cluster": ClusterPlacer,
    "force": ForcePlacer,
    "anneal": SimulatedAnnealing,
    "codex": Codex,
}


def get(name: str):
    """Ada gore yerlestirici ornegi olusturur."""
    if name not in PLACERS:
        raise KeyError(f"bilinmeyen yerlestirici: {name!r}. Mevcut: {', '.join(sorted(PLACERS))}")
    return PLACERS[name]()


__all__ = [
    "PLACERS",
    "Placement",
    "PlacementContext",
    "Placer",
    "get",
    "validate",
]
