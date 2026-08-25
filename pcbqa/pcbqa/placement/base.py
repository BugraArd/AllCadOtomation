"""DONMUS ARAYUZ - yerlestirme motorlarinin uymak zorunda oldugu sozlesme.

Bu dosyayi degistirmeyin. Birden fazla agent paralel calisiyor ve hepsi bu
arayuzu uyguluyor; arayuz degisirse hepsinin ciktisi uyumsuz hale gelir ve
karsilastirilamaz. Yeni bir ihtiyac varsa once bu dosyanin sahibiyle konusun.

Bir yerlestirici yazmak icin tek yapmaniz gereken:

    from pcbqa.placement.base import Placer, PlacementContext, Placement

    class MyPlacer:
        name = "benim-yontemim"

        def run(self, ctx: PlacementContext) -> Placement:
            return {ref: (x, y, rot), ...}

...ve pcbqa/placement/__init__.py icindeki PLACERS sozlugune kaydetmek.

Sonra hakem calistirir ve puanlar:

    python -m pcbqa.harness --placer benim-yontemim
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..model import Design

# ref -> (x_mm, y_mm, rotation_derece)
Placement = dict[str, tuple[float, float, float]]


@dataclass
class PlacementContext:
    """Yerlestiriciye verilen her sey. Salt-okunur kabul edin.

    `design` uzerinden erisebileceginiz isinize yarayacak seyler:
        design.board.components        bilesenler (x, y, rotation, pads, courtyard_poly)
        design.board.outline           (minx, miny, maxx, maxy) kart siniri
        design.net_names()             net adlari
        design.pins_on_net(ad)         netin pinleri, konumlari cozulmus
        design.hpwl(ad)                netin yari-cevre tel uzunlugu
        design.kind_of(ref)            'ic' | 'capacitor' | 'resistor' | ...
        design.metrics()               toplam HPWL, yogunluk, en uzun netler
    """

    design: Design
    # Dokunulmamasi gereken referanslar (konnektorler, montaj delikleri...)
    locked: set[str] = field(default_factory=set)
    # Tekrarlanabilirlik icin. Rastgelelik kullaniyorsaniz BUNU kullanin.
    seed: int = 0
    # Saniye cinsinden yumusak butce. Asarsaniz hakem yine de bekler ama
    # karsilastirma adil olmaz.
    time_budget_s: float = 30.0

    def movable(self) -> list[str]:
        """Tasinabilir bilesenlerin referanslari."""
        return [c.ref for c in self.design.board.components if c.ref not in self.locked]

    def outline(self) -> tuple[float, float, float, float]:
        """Kart siniri. Yoksa bilesenleri saran kutuya duser."""
        if self.design.board.outline:
            return self.design.board.outline
        xs = [c.x for c in self.design.board.components] or [0.0]
        ys = [c.y for c in self.design.board.components] or [0.0]
        return min(xs), min(ys), max(xs), max(ys)


@runtime_checkable
class Placer(Protocol):
    """Bir yerlestirme stratejisi."""

    name: str

    def run(self, ctx: PlacementContext) -> Placement:
        """Yeni konumlari dondurur.

        Kurallar:
          * `ctx.locked` icindeki referanslari SONUCA KOYMAYIN (veya ayni
            konumu koyun) - hakem kilitli bilesenlerin oynatilmasini ihlal
            sayar.
          * Donmedigi bilesenler yerinde birakilmis kabul edilir.
          * Rotasyon 0/90/180/270 disinda olabilir ama pratikte bu dorde
            baglanmasi onerilir.
          * Girdiyi (ctx.design) DEGISTIRMEYIN; hakem ayni tasarimi baska
            yerlestiricilere de verir.
        """
        ...


def validate(placement: Placement, ctx: PlacementContext) -> list[str]:
    """Yerlestirmenin sozlesmeye uydugunu dogrular. Sorun listesi dondurur."""
    problems: list[str] = []
    known = {c.ref for c in ctx.design.board.components}

    for ref, value in placement.items():
        if ref not in known:
            problems.append(f"{ref}: kartta boyle bir bilesen yok")
            continue
        if not (isinstance(value, (tuple, list)) and len(value) == 3):
            problems.append(f"{ref}: (x, y, rot) uclusu bekleniyordu, gelen: {value!r}")
            continue
        x, y, rot = value
        if not all(isinstance(v, (int, float)) for v in (x, y, rot)):
            problems.append(f"{ref}: konum sayisal olmali, gelen: {value!r}")
            continue
        if ref in ctx.locked:
            comp = ctx.design.component(ref)
            if comp and (abs(comp.x - x) > 1e-6 or abs(comp.y - y) > 1e-6):
                problems.append(f"{ref}: kilitli bilesen oynatilmis")

    return problems
