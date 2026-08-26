"""DONMUS ARAYUZ - yerlestirme motorlarinin uymak zorunda oldugu sozlesme.

Bu dosyayi GERI UYUMSUZ sekilde degistirmeyin. Birden fazla agent paralel
calisiyor ve hepsi bu arayuzu uyguluyor; arayuz degisirse hepsinin ciktisi
uyumsuz hale gelir ve karsilastirilamaz. Yeni bir ihtiyac varsa once bu
dosyanin sahibiyle konusun.

Asama 3'te eklenen (varsayilanli, eski yerlestiriciler etkilenmez):
`ctx.evaluate(placement)` -> hakemin gercek puani. Vekil maliyet yerine bunu
optimize edin; genelleme farki buradan cikiyor.

Asama 5'te eklenen (yine varsayilanli): `ctx.move_ranker` -> aday hamleleri
denenme sirasina dizen istege bagli fonksiyon. Ogrenilmis model buraya
baglanir. Kabul karari degismedi, hala `evaluate`.

Asama 6'da hamle kavrami BIRLESIK hamleye genisledi (`Compound`): takas ve
kume tasima gibi ayni anda birden fazla bileseni oynatan hamleler. Tek
bilesenli hamle 1 elemanli birlesik olarak ifade edilir, yani `Placer`
arayuzu degismedi - bu yalnizca cila katmanini ve siralayiciyi ilgilendirir.

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
from typing import Any, Callable, Protocol, runtime_checkable

from ..model import Design

# ref -> (x_mm, y_mm, rotation_derece)
Placement = dict[str, tuple[float, float, float]]

# Tek bir bilesenin yer degistirmesi: (ref, (x, y, rot))
Move = tuple[str, tuple[float, float, float]]
# BIRLESIK HAMLE (Asama 6): ayni anda uygulanan bir veya daha fazla yer
# degistirme. Tek bilesenli bir hamle 1 elemanli birlesiktir, yani eski hamle
# kavrami bunun ozel halidir. Takas ve kume tasima ancak boyle ifade edilebilir:
# iki bilesen AYNI ANDA yer degistirmezse aradaki adim hep cakisma uretir ve
# hakem hicbirini kabul etmez.
Compound = tuple[Move, ...]
# Adaylari denenme sirasina dizer. Hamleleri ELEYEBILIR de - kabul karari
# yine hakemde oldugu icin bu yalnizca hizi etkiler, dogrulugu degil.
#
# Asama 6'da imza `list[Move]` -> `list[Compound]` olarak genisletildi. Bu
# alani uygulayan tek yer `pcbqa/ml`; hicbir yerlestirici kendi siralayicisini
# yazmiyordu, o yuzden kirilma alani yok.
MoveRanker = Callable[[Placement, "Evaluation", list[Compound]], list[Compound]]


@dataclass
class Evaluation:
    """Hakemin bir yerlestirme icin verdigi gercek olcum.

    Yerlestiriciler vekil maliyet yerine BUNU optimize etmeli - hakem
    puanlamayi bununla yapiyor.
    """

    score: float
    errors: int
    warnings: int
    total_hpwl_mm: float
    findings: list[Any] = field(default_factory=list)

    @property
    def key(self) -> tuple:
        """Siralamada kullanilan anahtar; buyuk olan daha iyidir."""
        return (self.score, -self.errors, -self.warnings, -self.total_hpwl_mm)

    def better_than(self, other: "Evaluation | None") -> bool:
        return other is None or self.key > other.key


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
    # Hakemin gercek hedef fonksiyonu; harness dolduruyor. None ise
    # yerlestirici kendi vekil maliyetiyle calisir (eski davranis korunur).
    evaluator: Callable[[Placement], Evaluation] | None = None
    # Asama 5: aday hamleleri DENENME SIRASINA gore dizen istege bagli
    # siralayici (bkz. `pcbqa/ml/`). Kabul karari hala `evaluate` iledir;
    # bu yalnizca "once hangisini deneyelim" sorusunu cevaplar. None ise
    # arama kendi sirasiyla calisir (eski davranis korunur).
    move_ranker: MoveRanker | None = None

    def movable(self) -> list[str]:
        """Tasinabilir bilesenlerin referanslari."""
        return [c.ref for c in self.design.board.components if c.ref not in self.locked]

    def evaluate(self, placement: Placement) -> Evaluation | None:
        """Bir yerlestirmeyi hakemin kendi olcutuyle puanlar.

        Vekil maliyetle ugrasmak yerine bunu cagirin: 60 bilesenli bir kartta
        ~5 ms surer, yani 30 saniyelik butcede binlerce deneme yapabilirsiniz.
        `None` donerse hakem hedef fonksiyonu vermemistir (eski cagri yolu).
        """
        return self.evaluator(placement) if self.evaluator is not None else None

    def current(self) -> Placement:
        """Kartin su anki yerlesimi - iyilestirmeye buradan baslamak
        gercek kartlarda sifirdan baslamaktan neredeyse her zaman iyidir."""
        return {
            c.ref: (c.x, c.y, c.rotation) for c in self.design.board.components
        }

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
