"""Model sozlesmesi + JSON kaydet/yukle + kayit defteri.

Modeller **JSON** olarak saklanir, pickle olarak degil. Sebep uc tane:
depoya girip git diff'i okunabiliyor, Python surumleri arasi tasinabiliyor,
ve bir model dosyasi calistirilabilir kod tasimadigi icin baskasindan gelen
bir modeli acmak guvenlik sorunu olmuyor.

Her model dosyasi hangi OZNITELIK SEMASIYLA egitildigini icinde tasir
(`feature_names` + `feature_version`). Yukleyen taraf `check_schema` ile
karsilastirir; uyusmazsa sessizce yanlis tahmin etmek yerine hata verir.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

MODEL_KIND = "pcbqa-model"


class Model:
    """Tum modellerin ortak yuzeyi.

    Alt siniflar `kind`, `_params()`, `_load_params()` ve `predict()` verir.
    """

    kind = "base"

    def __init__(
        self,
        feature_names: Sequence[str] | None = None,
        feature_version: int = 0,
        meta: dict[str, Any] | None = None,
    ) -> None:
        self.feature_names = list(feature_names or [])
        self.feature_version = feature_version
        self.meta: dict[str, Any] = dict(meta or {})

    # ------------------------------------------------------------------ tahmin

    def predict(self, x: Sequence[float]) -> float:
        raise NotImplementedError

    def predict_many(self, X: Sequence[Sequence[float]]) -> list[float]:
        return [self.predict(x) for x in X]

    # -------------------------------------------------------------------- sema

    def check_schema(self, names: Sequence[str], version: int | None = None) -> None:
        """Modelin egitildigi sema ile cagiranin semasini karsilastirir."""
        if self.feature_names and list(names) != self.feature_names:
            missing = [n for n in self.feature_names if n not in names]
            extra = [n for n in names if n not in self.feature_names]
            raise ValueError(
                "oznitelik semasi uyusmuyor - model yeniden egitilmeli "
                f"(eksik: {missing[:3]}, fazla: {extra[:3]}, "
                f"model {len(self.feature_names)} vs cagiran {len(names)})"
            )
        if version is not None and self.feature_version and version != self.feature_version:
            raise ValueError(
                f"oznitelik surumu uyusmuyor: model v{self.feature_version}, "
                f"cagiran v{version}"
            )

    # ---------------------------------------------------------------- depolama

    def _params(self) -> dict[str, Any]:
        raise NotImplementedError

    def _load_params(self, params: dict[str, Any]) -> None:
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": MODEL_KIND,
            "model": self.kind,
            "feature_version": self.feature_version,
            "feature_names": self.feature_names,
            "meta": self.meta,
            "params": self._params(),
        }

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8"
        )

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Model":
        if raw.get("kind") != MODEL_KIND:
            raise ValueError("pcbqa model dosyasi degil")
        model = build(str(raw.get("model", "")))
        model.feature_names = list(raw.get("feature_names") or [])
        model.feature_version = int(raw.get("feature_version", 0))
        model.meta = dict(raw.get("meta") or {})
        model._load_params(raw.get("params") or {})
        return model


class MeanModel(Model):
    """Taban cizgisi: her zaman egitim ortalamasini soyler.

    `placement/baseline.py`'deki `identity` ile ayni gorevi gorur - bir modelin
    ise yarayip yaramadigi ancak bunun ustune ne kattigiyla olculur. Siralama
    metriklerinde rastgeleye esittir; bir aday model bunu gecemiyorsa
    ogrenilecek bir sey bulamamis demektir.
    """

    kind = "mean"

    def __init__(self, value: float = 0.0, **kw: Any) -> None:
        super().__init__(**kw)
        self.value = value

    def fit(self, X: Sequence[Sequence[float]], y: Sequence[float]) -> "MeanModel":
        self.value = (sum(y) / len(y)) if y else 0.0
        return self

    def predict(self, x: Sequence[float]) -> float:
        return self.value

    def _params(self) -> dict[str, Any]:
        return {"value": self.value}

    def _load_params(self, params: dict[str, Any]) -> None:
        self.value = float(params.get("value", 0.0))


# ad -> sinif. `linear`/`trees` import edildiginde dolar (asagida).
MODELS: dict[str, type[Model]] = {"mean": MeanModel}


def register(cls: type[Model]) -> type[Model]:
    MODELS[cls.kind] = cls
    return cls


def build(name: str, **kw: Any) -> Model:
    """Ada gore bos bir model ornegi uretir."""
    _ensure_registry()
    if name not in MODELS:
        raise KeyError(f"bilinmeyen model: {name!r}. Mevcut: {', '.join(sorted(MODELS))}")
    return MODELS[name](**kw)


def _ensure_registry() -> None:
    """Kayit defterini doldurur (dairesel import olmasin diye gec yapilir)."""
    if len(MODELS) <= 1:
        from . import linear, trees  # noqa: F401


def load(path: Path) -> Model:
    _ensure_registry()
    return Model.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
