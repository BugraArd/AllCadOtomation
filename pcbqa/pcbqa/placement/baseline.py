"""Referans yerlestiriciler - hakemin dogru calistigini kanitlamak icin.

Bunlar akilli degil, bilerek boyle. Isleri sunlari garanti etmek:

  identity : hicbir sey yapmaz. Hakemin "sonra" skoru "once" skoruyla AYNI
             cikmali. Cikmiyorsa hakemde hata var, yerlestiricide degil.
  random   : bilesenleri rastgele dagitir. Skoru DUSURMELI. Dusurmuyorsa
             skor fonksiyonu yerlesim kalitesine duyarli degil demektir.

Gercek yerlestiriciler bu ikisinin arasinda bir yerde olmali: identity'den
belirgin sekilde iyi, random'dan cok daha iyi.
"""

from __future__ import annotations

import random

from .base import Placement, PlacementContext


class Identity:
    """Hicbir seyi oynatmaz. Hakemin alt sinir testi."""

    name = "identity"

    def run(self, ctx: PlacementContext) -> Placement:
        return {
            c.ref: (c.x, c.y, c.rotation)
            for c in ctx.design.board.components
            if c.ref not in ctx.locked
        }


class RandomShuffle:
    """Tasinabilir bilesenleri kart icine rastgele dagitir.

    Kasitli olarak kotu: skorun gercekten yerlesim kalitesini olctugunu
    dogrulamak icin bir kontrol grubu.
    """

    name = "random"

    def run(self, ctx: PlacementContext) -> Placement:
        rng = random.Random(ctx.seed)
        minx, miny, maxx, maxy = ctx.outline()
        margin = 2.0

        placement: Placement = {}
        for ref in ctx.movable():
            placement[ref] = (
                rng.uniform(minx + margin, maxx - margin),
                rng.uniform(miny + margin, maxy - margin),
                rng.choice((0.0, 90.0, 180.0, 270.0)),
            )
        return placement
