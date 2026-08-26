"""Veri kumesi: JSONL depolama + KART BAZLI bolme.

Alan bagimsizdir - burada ne KiCad ne de yerlestirme gecer. Girdi sadece
"oznitelik vektoru + etiket + grup + parti" dortlusudur.

## Neden kart bazli bolme (bunu bozmayin)

Ornekler kart kart toplanir ve ayni karttan gelen yuzlerce ornek birbirine
cok benzer (ayni kart baglami, ayni bilesenler, komsu konumlar). Satirlari
rastgele bolerseniz egitim ve test kumesi AYNI karti paylasir; model karti
ezberler, metrikler harika cikar ve yeni bir kartta cokerler. `split_by_group`
ve `folds_by_group` bu yuzden her zaman kart butunluyle bir tarafa koyar.

## Parti (batch) nedir

Yerel arama, bir anda TEK bir aday listesi uretir ve icinden birini secer.
Modelin gercek isi bu liste icinde dogru siralama yapmaktir - mutlak degeri
dogru tahmin etmek degil. Ayni listeden uretilen ornekler ayni `batch`
degerini tasir; siralama metrikleri (`ml/metrics.py`) parti icinde olculur.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Sequence

DATASET_KIND = "pcbqa-dataset"


@dataclass
class Sample:
    """Tek bir egitim ornegi."""

    features: list[float]
    label: float
    group: str = ""            # kart adi - bolme bu alana gore yapilir
    batch: str = ""            # ayni aday listesinden gelen ornekler
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "x": [round(float(v), 6) for v in self.features],
            "y": round(float(self.label), 6),
            "g": self.group,
            "b": self.batch,
        }
        if self.extra:
            out["e"] = self.extra
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Sample":
        return cls(
            features=[float(v) for v in raw["x"]],
            label=float(raw["y"]),
            group=str(raw.get("g", "")),
            batch=str(raw.get("b", "")),
            extra=raw.get("e") or {},
        )


@dataclass
class Dataset:
    """Ornek kumesi + hangi semayla uretildigi."""

    feature_names: list[str]
    feature_version: int = 0
    samples: list[Sample] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.samples)

    def __iter__(self) -> Iterator[Sample]:
        return iter(self.samples)

    @property
    def X(self) -> list[list[float]]:
        return [s.features for s in self.samples]

    @property
    def y(self) -> list[float]:
        return [s.label for s in self.samples]

    def groups(self) -> list[str]:
        seen: list[str] = []
        for s in self.samples:
            if s.group not in seen:
                seen.append(s.group)
        return seen

    def subset(self, samples: Sequence[Sample]) -> "Dataset":
        return Dataset(
            feature_names=list(self.feature_names),
            feature_version=self.feature_version,
            samples=list(samples),
            meta=dict(self.meta),
        )

    def add(self, sample: Sample) -> None:
        if len(sample.features) != len(self.feature_names):
            raise ValueError(
                f"oznitelik sayisi uyusmuyor: {len(sample.features)} != "
                f"{len(self.feature_names)}"
            )
        self.samples.append(sample)

    def extend(self, other: "Dataset") -> None:
        if other.feature_names != self.feature_names:
            raise ValueError("oznitelik semalari farkli, birlestirilemez")
        self.samples.extend(other.samples)

    # -------------------------------------------------------------------- bolme

    def split_by_group(
        self, test_frac: float = 0.3, seed: int = 0
    ) -> tuple["Dataset", "Dataset"]:
        """Gruplari (kartlari) butun halinde egitim/test olarak ayirir."""
        names = self.groups()
        rng = random.Random(seed)
        rng.shuffle(names)
        n_test = max(1, int(round(len(names) * test_frac))) if len(names) > 1 else 0
        test_groups = set(names[:n_test])
        train = [s for s in self.samples if s.group not in test_groups]
        test = [s for s in self.samples if s.group in test_groups]
        return self.subset(train), self.subset(test)

    def folds_by_group(self, k: int = 5, seed: int = 0) -> list[tuple["Dataset", "Dataset"]]:
        """Gruplu k-kat capraz dogrulama. Az grup varsa kat sayisi kisilir."""
        names = self.groups()
        rng = random.Random(seed)
        rng.shuffle(names)
        k = max(2, min(k, len(names)))
        buckets: list[set[str]] = [set() for _ in range(k)]
        for i, name in enumerate(names):
            buckets[i % k].add(name)
        folds = []
        for hold in buckets:
            train = [s for s in self.samples if s.group not in hold]
            test = [s for s in self.samples if s.group in hold]
            if train and test:
                folds.append((self.subset(train), self.subset(test)))
        return folds

    def batches(self) -> list[list[Sample]]:
        """Ornekleri aday listesine gore gruplar (siralama metrikleri icin)."""
        order: list[str] = []
        by_key: dict[str, list[Sample]] = {}
        for s in self.samples:
            key = f"{s.group}|{s.batch}"
            if key not in by_key:
                by_key[key] = []
                order.append(key)
            by_key[key].append(s)
        return [by_key[k] for k in order]

    # ---------------------------------------------------------------- depolama

    def save(self, path: Path) -> None:
        """JSONL: ilk satir baslik, sonraki her satir bir ornek."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        header = {
            "kind": DATASET_KIND,
            "feature_version": self.feature_version,
            "features": self.feature_names,
            "count": len(self.samples),
            **self.meta,
        }
        lines = [json.dumps(header, ensure_ascii=False)]
        lines.extend(json.dumps(s.as_dict(), ensure_ascii=False) for s in self.samples)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Dataset":
        path = Path(path)
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if not lines:
            raise ValueError(f"bos veri kumesi: {path}")
        header = json.loads(lines[0])
        if header.get("kind") != DATASET_KIND:
            raise ValueError(f"{path}: pcbqa veri kumesi degil")
        meta = {
            k: v
            for k, v in header.items()
            if k not in ("kind", "feature_version", "features", "count")
        }
        ds = cls(
            feature_names=list(header["features"]),
            feature_version=int(header.get("feature_version", 0)),
            meta=meta,
        )
        ds.samples = [Sample.from_dict(json.loads(ln)) for ln in lines[1:]]
        return ds

    # ---------------------------------------------------------------- ozetleme

    def summary(self) -> dict[str, Any]:
        labels = self.y
        positives = sum(1 for v in labels if v > 1e-9)
        negatives = sum(1 for v in labels if v < -1e-9)
        return {
            "samples": len(labels),
            "groups": len(self.groups()),
            "batches": len(self.batches()),
            "features": len(self.feature_names),
            "feature_version": self.feature_version,
            "label_mean": (sum(labels) / len(labels)) if labels else 0.0,
            "label_max": max(labels) if labels else 0.0,
            "label_min": min(labels) if labels else 0.0,
            "improving": positives,
            "worsening": negatives,
            "neutral": len(labels) - positives - negatives,
        }
