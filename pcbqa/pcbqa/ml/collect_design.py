"""TASARIM SEVIYESI VERI TOPLAMA (Evre 3c) - varyant siralayici icin.

    python -m pcbqa.ml.collect_design --intents samples/niyetler \
        --out .work/tasarim.jsonl --variants 8 --budget 8

`ml/collect.py` HAMLE seviyesinde toplar: bir yerlestirme aramasi icindeki
aday hamleler. Bu modul bir ust katmanda toplar: bir NIYETTEN uretilen kart
VARYANTLARI. Iki veri kumesi ayni bicimi (`ml/dataset.py`) paylasir, yani
ayni egitici ve ayni siralama metrikleri ikisinde de calisir.

## Grup ve parti

    grup  = niyetin adi   -> bolme buna gore (model niyeti EZBERLEMESIN)
    parti = tek bir kesif kosumu -> siralama parti icinde olculur

Bu, `ml/dataset.py`nin kart-bazli bolme gerekcesinin aynisidir: ayni niyetten
gelen varyantlar birbirine cok benzer; satirlari rastgele bolmek egitim ve
testin ayni niyeti paylasmasi demektir.

## Etiket neden HPWL uzerinden

Uretilen kartta SKOR DOYUYOR (Evre 3b olcumu: 40x28'den 100x70'e kadar hepsi
100.0). Ham skoru etiket yapmak butun ornekleri ayni etiketle isaretlemek,
yani modele hicbir sey ogretmemek demektir. Bu yuzden etiket, `collect.py`nin
sozlesmesini koruyarak parti MEDYANINA gore yazilir:

    etiket = d_skor + 0.05 * clamp(-d_HPWL / medyan_HPWL, -1, +1)

Skorlar esitken (olagan durum) geriye bagil HPWL iyilesmesi kalir. Olcek
kucuktur ama siralama metrikleri yalnizca SIRAYI umursar.

## Tohum bilerek OZNITELIK DEGIL

Tohum bir tasarim karari degil, aramanin rastgeleligidir. Oznitelige koymak
modeli gurultuyu ezberlemeye davet ederdi. Disarida birakinca ayni oznitelik
vektoru farkli etiketlerle birden fazla kez gorunur - bu bir kusur degil,
GURULTU TABANININ olculebilir hale gelmesidir. `--ozet` bunu bildirir.

## Olculmus uyari: sinyal zayif

Evre 3c olcumu (F103 karti, 4 yogunluk x 5 tohum): yogunluk sonucun
varyansinin yalnizca **%21.4**'unu acikliyor, kalani tohum. Butceyi 6'dan
20 saniyeye cikarmak yayilimi AZALTMADI (std 13.0 -> 25.3). Yani varyant
siralayicinin ogrenebilecegi tavan dusuk; model terfi etmeden once
`ml/metrics.py` ile parti ici siralama kazanci OLCULMELIDIR. Bu, learned
yerlestirici dersinin (HANDOFF 21.10) dogrudan tekrari.

## Kaynak ve lisans

Her kayit nereden geldigini soyler. Uretilen kartlarda `lisans: "uretilmis"`
(kendi ciktimiz). DISARIDAN gelen bir kart eklenirken lisans ZORUNLUDUR ve
verilmezse hata atilir - LM5116 emsali: lisansi olmayan kart korpusa
alinamadi (HANDOFF 1).
"""

from __future__ import annotations

import argparse
import shutil
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from ..explore import DENSITIES, ExploreResult, Variant, explore
from ..generate import DEFAULT_RULES, DEFAULT_TIME_BUDGET_S, GenerateError
from ..intent import BuildPlan, IntentError, plan_from_file
from ..model import Design
from ..pcb import read_board
from .dataset import Dataset, Sample

# Oznitelik semasi degistiginde ARTIRIN - eski dosyalarla karistirmamak icin.
FEATURE_VERSION = 1

# HPWL teriminin etiketteki agirligi. `ml/collect.py` ile AYNI sayi:
# iki veri kumesi ayni etiket sozlesmesini paylasmali.
HPWL_WEIGHT = 0.05

FEATURE_NAMES = [
    # --- topoloji (yerlestirmeden ONCE bilinir) ---
    "bilesen_sayisi",
    "net_sayisi",
    "pin_sayisi",
    "ortalama_net_derecesi",
    "en_yuksek_net_derecesi",
    "toplam_bilesen_alani",
    "en_buyuk_bilesen_alani",
    "ic_sayisi",
    "pasif_sayisi",
    "konnektor_sayisi",
    # --- varyant kosullari (tasarim kararlari) ---
    "yogunluk",
    "kart_genisligi",
    "kart_yuksekligi",
    "kart_alani",
    "en_boy_orani",
]

GENERATED_LICENSE = "uretilmis"


class CollectError(RuntimeError):
    """Toplama yapilamadi."""


# --------------------------------------------------------------------------
# Oznitelikler
# --------------------------------------------------------------------------


@dataclass
class Topology:
    """Bir tasarimin yerlestirmeden ONCE bilinen ozellikleri."""

    components: int
    nets: int
    pins: int
    mean_degree: float
    max_degree: int
    total_area: float
    largest_area: float
    ics: int
    passives: int
    connectors: int

    @classmethod
    def of(cls, design: Design) -> "Topology":
        board = design.board
        degrees = [len(design.pins_on_net(name)) for name in design.net_names()]
        areas = [c.area_mm2 for c in board.components]
        kinds = [design.kind_of(c.ref) for c in board.components]
        return cls(
            components=len(board.components),
            nets=len(degrees),
            pins=sum(degrees),
            mean_degree=(sum(degrees) / len(degrees)) if degrees else 0.0,
            max_degree=max(degrees) if degrees else 0,
            total_area=sum(areas),
            largest_area=max(areas) if areas else 0.0,
            ics=sum(1 for k in kinds if k == "ic"),
            passives=sum(1 for k in kinds if k in ("capacitor", "resistor", "inductor")),
            connectors=sum(1 for k in kinds if k == "connector"),
        )


def features_of(topology: Topology, variant: Variant) -> list[float]:
    """FEATURE_NAMES ile AYNI sirada oznitelik vektoru.

    Tohum bilerek yok (bkz. modul basligi): tasarim karari degil, arama
    rastgeleligi.
    """
    return [
        float(topology.components),
        float(topology.nets),
        float(topology.pins),
        float(topology.mean_degree),
        float(topology.max_degree),
        float(topology.total_area),
        float(topology.largest_area),
        float(topology.ics),
        float(topology.passives),
        float(topology.connectors),
        float(variant.density),
        float(variant.width),
        float(variant.height),
        float(variant.area_mm2),
        float(variant.width / variant.height) if variant.height else 0.0,
    ]


# --------------------------------------------------------------------------
# Etiket
# --------------------------------------------------------------------------


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def label_of(variant: Variant, median_score: float, median_hpwl: float) -> float:
    """Parti medyanina gore kalite. Buyuk olan daha iyi.

    Skor farki baskindir (kaliteden odun verilmez); skorlar esitken bagil
    HPWL iyilesmesi kalir. `ml/collect.py`nin etiket sozlesmesiyle ayni bicim.
    """
    d_score = variant.score - median_score
    if median_hpwl <= 0:
        return d_score
    relative = (median_hpwl - variant.hpwl_mm) / median_hpwl
    return d_score + HPWL_WEIGHT * _clamp(relative)


def samples_from_run(
    result: ExploreResult,
    topology: Topology,
    group: str,
    batch: str,
    license_name: str = GENERATED_LICENSE,
    source: str = "uretilmis",
) -> list[Sample]:
    """Bir kesif kosumunu egitim orneklerine cevirir."""
    if not license_name:
        raise CollectError(
            f"{group}: lisans bos birakilamaz - kaynagi bilinmeyen veri korpusa "
            "alinmaz (LM5116 emsali)"
        )
    variants = result.variants
    if not variants:
        return []
    median_score = statistics.median(v.score for v in variants)
    median_hpwl = statistics.median(v.hpwl_mm for v in variants)

    out: list[Sample] = []
    for variant in variants:
        out.append(Sample(
            features=features_of(topology, variant),
            label=label_of(variant, median_score, median_hpwl),
            group=group,
            batch=batch,
            extra={
                "kaynak": source,
                "lisans": license_name,
                "tohum": variant.seed,
                "skor": variant.score,
                "hata": variant.errors,
                "uyari": variant.warnings,
                "hpwl_mm": round(variant.hpwl_mm, 2),
                "alan_mm2": round(variant.area_mm2, 1),
                "saniye": round(variant.seconds, 2),
                "secilen": variant is result.best,
            },
        ))
    return out


# --------------------------------------------------------------------------
# Toplama
# --------------------------------------------------------------------------


def collect_intent(
    intent_path: Path,
    work_dir: Path,
    *,
    variants: int = len(DENSITIES) * 2,
    time_budget_s: float = DEFAULT_TIME_BUDGET_S,
    base_seed: int = 0,
    rules_path: Path | None = None,
    templates_dir: Path | None = None,
    kicad_cli: str | None = None,
) -> list[Sample]:
    """Tek bir niyetten bir kesif kosumu yapip orneklerini dondurur."""
    plan: BuildPlan = plan_from_file(intent_path, templates_dir=templates_dir, resolve=True)
    result = explore(
        plan, work_dir, plan.name,
        variants=variants,
        rules_path=rules_path,
        time_budget_s=time_budget_s,
        base_seed=base_seed,
        no_connect_unused=True,
        kicad_cli=kicad_cli,
    )
    if not result.ok:
        raise CollectError(
            f"{intent_path.name}: kesif basarisiz - " + "; ".join(result.problems[:3])
        )

    design = _design_of(result.generated.pcb)
    topology = Topology.of(design)
    batch = f"{plan.name}#{int(time.time() * 1000)}"
    return samples_from_run(result, topology, group=plan.name, batch=batch)


def _design_of(pcb_path: Path) -> Design:
    from ..model import build_design
    from ..netlist import netlist_from_board

    board = read_board(pcb_path)
    return build_design(board, netlist_from_board(board), project_name=pcb_path.stem)


def collect(
    intent_paths: list[Path],
    *,
    variants: int = len(DENSITIES) * 2,
    time_budget_s: float = DEFAULT_TIME_BUDGET_S,
    base_seed: int = 0,
    rules_path: Path | None = None,
    templates_dir: Path | None = None,
    work_root: Path | None = None,
    kicad_cli: str | None = None,
    on_progress=None,
) -> Dataset:
    """Butun niyetleri gezip tek bir veri kumesi uretir."""
    dataset = Dataset(
        feature_names=list(FEATURE_NAMES),
        feature_version=FEATURE_VERSION,
        meta={
            "veri_turu": "tasarim-varyanti",
            "hpwl_weight": HPWL_WEIGHT,
            "densities": list(DENSITIES),
            "budget_s": time_budget_s,
            "variants_per_run": variants,
        },
    )
    temporary = work_root is None
    root = Path(work_root) if work_root else Path(tempfile.mkdtemp(prefix="pcbqa-veri-"))
    try:
        for path in intent_paths:
            folder = root / path.stem
            shutil.rmtree(folder, ignore_errors=True)
            samples = collect_intent(
                path, folder,
                variants=variants, time_budget_s=time_budget_s, base_seed=base_seed,
                rules_path=rules_path, templates_dir=templates_dir, kicad_cli=kicad_cli,
            )
            for sample in samples:
                dataset.add(sample)
            if on_progress is not None:
                on_progress(path, samples)
    finally:
        if temporary:
            shutil.rmtree(root, ignore_errors=True)
    return dataset


# --------------------------------------------------------------------------
# Gurultu tabani - 3d'nin kapisi
# --------------------------------------------------------------------------


def noise_floor(dataset: Dataset) -> dict:
    """Ayni oznitelik vektorunun etiket yayilimi: modelin ASAMAYACAGI taban.

    Tohum oznitelik olmadigi icin ayni tasarim kararlari birden fazla satir
    uretir. Bu satirlar arasindaki etiket farki YALNIZCA aramanin
    rastgeleligidir; hicbir model onu tahmin edemez. Toplam etiket yayilimina
    orani, varyant siralayicinin ogrenebilecegi tavani verir.
    """
    by_key: dict[tuple, list[float]] = {}
    for sample in dataset.samples:
        by_key.setdefault(tuple(round(v, 6) for v in sample.features), []).append(sample.label)

    repeated = [labels for labels in by_key.values() if len(labels) > 1]
    labels = [s.label for s in dataset.samples]
    total = statistics.pvariance(labels) if len(labels) > 1 else 0.0
    within = (
        statistics.mean([statistics.pvariance(v) for v in repeated]) if repeated else 0.0
    )
    return {
        "ornek": len(dataset),
        "ayrik_oznitelik": len(by_key),
        "tekrarli_oznitelik": len(repeated),
        "toplam_varyans": total,
        "gurultu_varyansi": within,
        "aciklanabilir_ust_sinir": (1.0 - within / total) if total > 0 else 0.0,
    }


# --------------------------------------------------------------------------
# Komut satiri
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pcbqa.ml.collect_design",
        description="Niyetlerden kart varyantlari uretip egitim verisi toplar.",
    )
    ap.add_argument("--intents", type=Path, required=True,
                    help="Niyet dosyasi ya da niyet dosyalari klasoru")
    ap.add_argument("--out", type=Path, required=True, help="Cikti .jsonl")
    ap.add_argument("--variants", type=int, default=len(DENSITIES) * 2,
                    help="Niyet basina varyant sayisi")
    ap.add_argument("--budget", type=float, default=DEFAULT_TIME_BUDGET_S,
                    help="VARYANT BASINA yerlestirici sure butcesi (saniye)")
    ap.add_argument("--seed", type=int, default=0, help="Ilk tohum")
    ap.add_argument("--rules", type=Path, default=None, help="Kural dosyasi")
    ap.add_argument("--templates", type=Path, default=None, help="Sablon klasoru")
    ap.add_argument("--work", type=Path, default=None,
                    help="Uretilen projelerin birakilacagi klasor (varsayilan: gecici)")
    ap.add_argument("--append", action="store_true",
                    help="Var olan .jsonl uzerine ekle (sema ayni olmali)")
    ap.add_argument("--kicad-cli", default=None)
    return ap


def intent_files(target: Path) -> list[Path]:
    target = Path(target)
    if target.is_dir():
        found = sorted(target.glob("*.yaml"))
        if not found:
            raise CollectError(f"klasorde niyet dosyasi yok: {target}")
        return found
    if target.is_file():
        return [target]
    raise CollectError(f"bulunamadi: {target}")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    try:
        paths = intent_files(args.intents)
    except CollectError as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2

    print(f"{len(paths)} niyet, niyet basina {args.variants} varyant, "
          f"varyant basina {args.budget:g} sn")

    def progress(path: Path, samples: list[Sample]) -> None:
        best = next((s for s in samples if s.extra.get("secilen")), None)
        detay = ""
        if best is not None:
            detay = (f"  en iyi: {best.extra['alan_mm2']:.0f} mm2, "
                     f"hpwl {best.extra['hpwl_mm']:.1f} mm")
        print(f"  {path.stem:<28} {len(samples):>3} ornek{detay}")

    started = time.perf_counter()
    try:
        dataset = collect(
            paths,
            variants=args.variants,
            time_budget_s=args.budget,
            base_seed=args.seed,
            rules_path=args.rules,
            templates_dir=args.templates,
            work_root=args.work,
            kicad_cli=args.kicad_cli,
            on_progress=progress,
        )
    except (CollectError, GenerateError, IntentError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 1

    if args.append and args.out.exists():
        existing = Dataset.load(args.out)
        existing.extend(dataset)
        dataset = existing
    dataset.save(args.out)

    floor = noise_floor(dataset)
    print(f"\nyazildi: {args.out}  ({len(dataset)} ornek, "
          f"{len(dataset.groups())} grup, {len(dataset.batches())} parti, "
          f"{time.perf_counter() - started:.0f} sn)")
    print("\ngurultu tabani (3d'nin kapisi):")
    print(f"  ayrik oznitelik vektoru      : {floor['ayrik_oznitelik']}"
          f" ({floor['tekrarli_oznitelik']} tanesi tekrarli)")
    print(f"  toplam etiket varyansi       : {floor['toplam_varyans']:.6f}")
    print(f"  tohum kaynakli (indirgenemez): {floor['gurultu_varyansi']:.6f}")
    print(f"  aciklanabilir ust sinir      : %{100 * floor['aciklanabilir_ust_sinir']:.1f}")
    print("\n  Bu ust sinir, hicbir modelin asamayacagi tavandir. Model ancak"
          "\n  parti ici siralamayi OLCULEBILIR sekilde iyilestirirse terfi eder"
          "\n  (bkz. ml/metrics.py; learned yerlestirici dersi HANDOFF 21.10).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
