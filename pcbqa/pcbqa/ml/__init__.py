"""Asama 5 - makine ogrenimi altyapisi.

Katmanlar bilerek ayri tutuldu; ust katman KiCad'i bilir, alt katman bilmez:

    features.py   PCB'ye ozgu   Design + aday hamle -> sayi vektoru (DONMUS sema)
    collect.py    PCB'ye ozgu   gercek hakemle etiketli veri kumesi uretir
    ------------------------------------------------------------------------
    dataset.py    alan bagimsiz JSONL depolama + KART BAZLI bolme
    metrics.py    alan bagimsiz regresyon + siralama metrikleri
    model.py      alan bagimsiz model sozlesmesi, JSON kaydet/yukle, kayit
    linear.py     alan bagimsiz ridge regresyon
    trees.py      alan bagimsiz gradyan artirmali agaclar
    train.py      alan bagimsiz egitim/karsilastirma komut satiri

Bu ayrim `model.py`/`rules.py`nin KiCad'i bilmemesiyle ayni sebeple var:
sematik tarafi (Asama 4e) ayni cekirdegi kullanmak istediginde yalnizca yeni
bir `features`/`collect` cifti yazmak yetecek.

Kullanim:

    python -m pcbqa.ml.collect --suite "<demolar>" --out .work/moves.jsonl
    python -m pcbqa.ml.train .work/moves.jsonl --model all --out pcbqa/ml/models/move-v1.json
    python -m pcbqa.harness --placer learned --board samples/bench_bad.kicad_pcb
"""

from __future__ import annotations

from .dataset import Dataset, Sample
from .features import FEATURE_NAMES, FEATURE_VERSION, MoveFeaturizer
from .model import Model, build, load

__all__ = [
    "Dataset",
    "Sample",
    "FEATURE_NAMES",
    "FEATURE_VERSION",
    "MoveFeaturizer",
    "Model",
    "build",
    "load",
]
