"""Yerlestirme stratejileri.

Yeni bir yerlestirici eklemek icin:
  1. Bu klasorde bir modul yazin (or. `force.py`)
  2. base.Placer arayuzunu uygulayin
  3. Asagidaki PLACERS sozlugune kaydedin

Hakem `python -m pcbqa.harness --placer <ad>` ile calistirir.
"""

from __future__ import annotations

from .base import Placement, PlacementContext, Placer, validate
from .baseline import Identity, RandomShuffle

# ad -> yerlestirici fabrikasi
PLACERS: dict[str, type] = {
    "identity": Identity,
    "random": RandomShuffle,
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
