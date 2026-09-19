"""Uretim-degerlendirme dongusu (Evre 3b): ayni niyetten N varyant, en iyisi.

`generate.py` bir niyetten BIR kart uretiyordu. Bu modul aynisini N kez
farkli kosullarla yapar, hepsini olcer ve en iyisini secer. Sematik bir kez
uretilir (netlist her varyantta AYNIDIR - niyet degismedi); degisen yalnizca
kart sinirinin boyutu ve yerlestiricinin tohumu.

## Neden skor tek basina yetmiyor (olculdu)

Uretilen 18 bilesenlik F103 kartinda skor DOYUYOR:

    40x28 mm -> 100.0      70x50 mm -> 100.0
    50x35 mm -> 100.0     100x70 mm -> 100.0

Skor bir IHLAL sayacidir; ihlal kalmadigi anda ayrim gucu biter. Yani "en
yuksek skorlu varyanti sec" demek, dort karti da esit gormek demektir.

Iki olcum bu tikanikligi aciyor:

  1. TOHUM gercek fark yaratiyor. Sabit 50x35'te alti tohum HPWL'i 174.5 ile
     216.2 mm arasinda dagitti - en iyisi en kotusunden %19.3 iyi.
  2. SKORUN COZUNURLUGU DAR KARTTA VAR. 25x18 -> 24.7, 30x20 -> 74.1,
     35x25 -> 100.0. Yani 35x25 skoru tam tutturan EN KUCUK karttir ve
     50x35'in yari alanidir.

Ikincisi asil kazanctir: ayni kalite, yari kart alani. Kart alani gercek bir
uretim maliyetidir ve skor onu HIC gormez - bu yuzden secim olcutune ayrica
konur.

## Secim olcutu

Sozluksel, buyuk olan kazanir:

    (skor, -hata, -uyari, -alan, -HPWL)

Skor once gelir: kaliteden odun verilmez. Esit kalite katmaninda EN KUCUK
kart yeglenir (para). Alan da esitse HPWL ayirir (yonlendirilebilirlik
vekili) - bu, projenin `Evaluation.key` sozlesmesinin alan eklenmis hali.

## Yonlendirme uyarisi

Uretilen kartlar YONLENDIRILMEMISTIR, yani bakir kurallari susar ve skor
yalnizca yerlesimi yargilar (bkz. Kicad-805 karari). Bu, varyantlari
karsilastirmayi bozmaz - hepsi ayni netlist'e sahip ve hepsi
yonlendirilmemis, yani korluk SABIT bir kaymadir. Bozdugu sey MUTLAK
sayidir: 100 "kusursuz kart" demek degil, "yerlesimde ihlal yok" demektir.
Rapor bunu acikca yazar.

Ana giris: `explore(plan, out_dir)`, CLI: `python -m pcbqa.explore`.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .generate import (
    DEFAULT_RULES,
    DEFAULT_TIME_BUDGET_S,
    GenerateError,
    GenerateResult,
    draw_outline,
    fit_outline,
    generate,
)
from .harness import apply_placement, evaluate_design, make_evaluator, write_board
from .intent import BuildPlan, IntentError, plan_from_file
from .model import build_design
from .netlist import netlist_from_board
from .pcb import read_board
from .placement.auto import Auto
from .placement.base import Placement, PlacementContext
from .rules import load_rules

# Denenen yogunluk hedefleri: bilesen alani / kart alani.
# Buyuk yogunluk = kucuk kart. 0.45'in ustu pratikte yerlestirilemiyor
# (olculdu: 18 bilesenlik kartta 25x18 mm dort uyari uretiyor), 0.15'in
# altinda ise kart bosuna buyuyor. Arama bu araligi tarar.
DENSITIES = (0.40, 0.32, 0.25, 0.18)

# Varsayilan varyant sayisi: dort yogunluk x bir tohum.
DEFAULT_VARIANTS = 4


@dataclass
class Variant:
    """Tek bir deneme: hangi kosullarla, ne cikti."""

    index: int
    density: float
    width: float
    height: float
    seed: int
    score: float = 0.0
    errors: int = 0
    warnings: int = 0
    hpwl_mm: float = 0.0
    seconds: float = 0.0
    placement: Placement = field(default_factory=dict)

    @property
    def area_mm2(self) -> float:
        return self.width * self.height

    @property
    def key(self) -> tuple:
        """Sozluksel siralama anahtari; BUYUK olan daha iyidir.

        `placement.base.Evaluation.key`in alan eklenmis hali. Alan skorun
        hic gormedigi bir maliyettir; esit kalitede kucuk kart yeglenir.
        """
        return (self.score, -self.errors, -self.warnings, -self.area_mm2, -self.hpwl_mm)

    def describe(self, best: bool = False) -> str:
        mark = " <- secilen" if best else ""
        return (
            f"  {self.index:>2}  yogunluk %{self.density * 100:>4.0f}  "
            f"{self.width:>5.0f}x{self.height:<5.0f} {self.area_mm2:>6.0f} mm2  "
            f"tohum {self.seed}  skor {self.score:>5.1f}  "
            f"{self.errors}h/{self.warnings}u  hpwl {self.hpwl_mm:>6.1f} mm{mark}"
        )


@dataclass
class ExploreResult:
    generated: GenerateResult
    variants: list[Variant] = field(default_factory=list)
    best: Variant | None = None
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems and self.best is not None

    def describe(self) -> str:
        lines = [self.generated.describe(), "", f"varyantlar ({len(self.variants)}):"]
        for v in self.variants:
            lines.append(v.describe(best=v is self.best))
        if self.best is not None and len(self.variants) > 1:
            en_buyuk = max(v.area_mm2 for v in self.variants)
            kazanc = 100.0 * (en_buyuk - self.best.area_mm2) / en_buyuk
            lines.append(
                f"  secilen kart en buyuk adaydan %{kazanc:.0f} kucuk "
                f"({self.best.area_mm2:.0f} / {en_buyuk:.0f} mm2)"
            )
        for note in self.notes:
            lines.append(f"  not: {note}")
        for problem in self.problems:
            lines.append(f"  ENGEL: {problem}")
        return "\n".join(lines)

    def as_dict(self) -> dict:
        return {
            "generated": self.generated.as_dict(),
            "variants": [
                {
                    "index": v.index,
                    "density": v.density,
                    "width_mm": v.width,
                    "height_mm": v.height,
                    "area_mm2": round(v.area_mm2, 1),
                    "seed": v.seed,
                    "score": v.score,
                    "errors": v.errors,
                    "warnings": v.warnings,
                    "hpwl_mm": round(v.hpwl_mm, 1),
                    "seconds": round(v.seconds, 2),
                    "best": v is self.best,
                }
                for v in self.variants
            ],
            "notes": list(self.notes),
            "problems": list(self.problems),
        }


def candidate_sizes(
    pcb_path: Path,
    densities: tuple[float, ...] = DENSITIES,
) -> list[tuple[float, float, float]]:
    """(yogunluk, genislik, yukseklik) adaylari - OLCULEN bilesen alanindan.

    Ayni boyuta cikan yogunluklar elenir (5 mm'ye yuvarlama yuzunden yakin
    yogunluklar ayni karti verebiliyor); ayni karti iki kez yerlestirmek
    butceyi bosa harcardi.
    """
    out: list[tuple[float, float, float]] = []
    seen: set[tuple[float, float]] = set()
    for density in densities:
        width, height = fit_outline(pcb_path, density)
        if (width, height) in seen:
            continue
        seen.add((width, height))
        out.append((density, width, height))
    return out


def plan_variants(
    pcb_path: Path,
    count: int,
    densities: tuple[float, ...] = DENSITIES,
    base_seed: int = 0,
) -> list[Variant]:
    """Denenecek varyantlar: once BOYUT cesitliligi, sonra tohum cesitliligi.

    Sira bilincli: butce yeterse her boyut bir kez denenir, ancak ondan sonra
    ayni boyutlar farkli tohumlarla tekrarlanir. Boyut kart alanini (parayi)
    degistirir, tohum yalnizca ayni kart icinde daha iyi bir yerlesim arar -
    yani once genis sonra derin aranir.
    """
    sizes = candidate_sizes(pcb_path, densities)
    variants: list[Variant] = []
    for i in range(max(1, count)):
        density, width, height = sizes[i % len(sizes)]
        variants.append(Variant(
            index=i + 1,
            density=density,
            width=width,
            height=height,
            seed=base_seed + i // len(sizes),
        ))
    return variants


def run_variant(board, rules, variant: Variant, budget: float) -> Variant:
    """Tek bir varyanti yerlestirir ve olcer. Dosyaya DOKUNMAZ.

    Kart her denemede taze bir kopyadan kurulur; sinir dosyaya yazilmadan
    dogrudan modele konur - varyant basina dosya yazip okumak butcenin
    onemli bir kismini disk islemlerine harcardi.
    """
    import time

    work = copy.deepcopy(board)
    work.outline = (0.0, 0.0, variant.width, variant.height)
    design = build_design(work, netlist_from_board(work), project_name="varyant")

    started = time.perf_counter()
    ctx = PlacementContext(
        design=design,
        # Uretilen kartta mekanik kisit yok (bkz. generate modul basligi)
        locked=set(),
        seed=variant.seed,
        time_budget_s=budget,
        evaluator=make_evaluator(design, rules),
    )
    placement = Auto().run(ctx)
    placed = apply_placement(design, placement)
    evaluation = evaluate_design(placed, rules)

    variant.seconds = time.perf_counter() - started
    variant.score = evaluation.score
    variant.errors = evaluation.errors
    variant.warnings = evaluation.warnings
    variant.hpwl_mm = placed.metrics().total_hpwl_mm
    variant.placement = placement
    return variant


def explore(
    plan: BuildPlan,
    out_dir: Path,
    name: str | None = None,
    *,
    variants: int = DEFAULT_VARIANTS,
    densities: tuple[float, ...] = DENSITIES,
    rules_path: Path | None = None,
    time_budget_s: float = DEFAULT_TIME_BUDGET_S,
    base_seed: int = 0,
    no_connect_unused: bool = False,
    verify: bool = True,
    kicad_cli: str | None = None,
) -> ExploreResult:
    """Bir niyetten N varyant uretir, olcer ve en iyisini karta yazar."""
    generated = generate(
        plan, out_dir, name,
        rules_path=rules_path,
        place=False,  # yerlestirme varyant dongusunun isi
        no_connect_unused=no_connect_unused,
        verify=verify,
        kicad_cli=kicad_cli,
    )
    result = ExploreResult(generated=generated)
    if not generated.ok:
        result.problems += generated.problems
        return result

    rules = load_rules(rules_path or DEFAULT_RULES)
    board = read_board(generated.pcb)
    todo = plan_variants(generated.pcb, variants, densities, base_seed)

    for variant in todo:
        result.variants.append(run_variant(board, rules, variant, time_budget_s))

    result.best = max(result.variants, key=lambda v: v.key)

    # Kazanani karta yaz: once sinir, sonra yerlesim.
    draw_outline(generated.pcb, result.best.width, result.best.height)
    write_board(generated.pcb, result.best.placement, generated.pcb)

    generated.board_size = (result.best.width, result.best.height)
    generated.score_after = result.best.score
    generated.errors_after = result.best.errors
    generated.warnings_after = result.best.warnings
    generated.moved = len(result.best.placement)

    # Yonlendirme korlugu: mutlak sayi yaniltici, karsilastirma degil.
    result.notes.append(
        "kart yonlendirilmemis - bakir kurallari olcmedi; skor yalnizca "
        "yerlesimi yargiliyor (varyant karsilastirmasi bundan etkilenmez, "
        "hepsi ayni durumda)"
    )
    if all(v.score >= 100.0 for v in result.variants) and len(result.variants) > 1:
        result.notes.append(
            "butun varyantlar tam puan aldi; secim alan ve HPWL ile yapildi"
        )
    return result


def explore_from_intent(
    intent_path: Path,
    out_dir: Path,
    name: str | None = None,
    *,
    templates_dir: Path | None = None,
    **kwargs,
) -> ExploreResult:
    plan = plan_from_file(intent_path, templates_dir=templates_dir, resolve=True)
    return explore(plan, out_dir, name, **kwargs)


# --------------------------------------------------------------------------
# Komut satiri
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pcbqa.explore",
        description="Bir niyetten N kart varyanti uretir, olcer ve en iyisini secer.",
    )
    ap.add_argument("--intent", type=Path, required=True, help="Niyet dosyasi (YAML)")
    ap.add_argument("--out", type=Path, required=True, help="Projenin yazilacagi klasor")
    ap.add_argument("--name", default=None, help="Proje adi (varsayilan: niyetin adi)")
    ap.add_argument("--templates", type=Path, default=None, help="Sablon klasoru")
    ap.add_argument("--rules", type=Path, default=None, help="Kural dosyasi")
    ap.add_argument("--variants", type=int, default=DEFAULT_VARIANTS,
                    help=f"Denenecek varyant sayisi (varsayilan {DEFAULT_VARIANTS})")
    ap.add_argument("--budget", type=float, default=DEFAULT_TIME_BUDGET_S,
                    help="VARYANT BASINA yerlestirici sure butcesi (saniye)")
    ap.add_argument("--seed", type=int, default=0, help="Ilk tohum")
    ap.add_argument("--no-connect-unused", action="store_true",
                    help="Baglanmamis pinlere no-connect bayragi koy")
    ap.add_argument("--no-verify", action="store_true", help="Netlist kalkanini atla")
    ap.add_argument("--json", type=Path, default=None, help="Sonucu JSON olarak da yaz")
    ap.add_argument("--kicad-cli", default=None)
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    try:
        result = explore_from_intent(
            args.intent, args.out, args.name,
            templates_dir=args.templates,
            rules_path=args.rules,
            variants=args.variants,
            time_budget_s=args.budget,
            base_seed=args.seed,
            no_connect_unused=args.no_connect_unused,
            verify=not args.no_verify,
            kicad_cli=args.kicad_cli,
        )
    except (GenerateError, IntentError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2

    print(result.describe())
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(result.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"JSON sonuc: {args.json}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
