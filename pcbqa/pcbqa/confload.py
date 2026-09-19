"""Yapilandirma okuma: YAML varsa YAML, yoksa yaninda duran JSON.

## Neden var (olculmus kisit)

Paketi KiCad'in KENDI Python'undan calistirmak istiyoruz - eklenti (API'siz
bagalanti) ancak oyle mumkun. Ama iki yorumlayici ayni degil:

    KiCad 10.0 python 3.11.5 : pcbnew VAR, pyyaml YOK
    proje .venv    python 3.13 : pcbnew YOK, pyyaml VAR

Yani `import yaml` modul duzeyinde kaldigi surece `pcbqa` KiCad icinde HIC
import edilemez. Bu modul o bagi kopariyor: YAML artik ISTEGE BAGLI.

## Neden JSON'a cevirip YAML'i atmiyoruz

Kural ve sablon dosyalarindaki YORUMLAR bu projenin belkemigi - her esigin
kaynagi orada yaziyor ("Kaynak: ST AN2586 Bolum 3.4"). JSON yorum tasimaz.
Bu yuzden YAML kalir (insan onu okur), JSON yalnizca CALISMA ZAMANI
kopyasidir. `python -m pcbqa.bundle` uretir, bir test de ikisinin
ayrismadigini korur.

## Sira

    1. dosya .json ise            -> stdlib json
    2. pyyaml varsa               -> yaml            (kaynak, en yetkili)
    3. `minyaml`                  -> yaml            (kendi okuyucumuz, KAYNAGI okur)
    4. yaninda .json varsa        -> stdlib json     (3 desteklemeyen bir yapiya
                                                      takilirsa emniyet agi)
    5. hicbiri                    -> ConfigError, sebebini soyleyerek

3. adim 4'ten ONCE gelir ve bu bilincli: JSON kopyasi URETILMIS bir seydir ve
bayat olabilir; kendi okuyucumuz ise dosyanin KENDISINI okur. Kullanicinin
kendi niyet/kural dosyasinin JSON esi zaten hic olmaz - o dosyalar ancak bu
sirayla okunabiliyor.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import minyaml

try:  # pyyaml zorunlu degil - bkz. modul basligi
    import yaml as _yaml
except ImportError:  # pragma: no cover - KiCad'in Python'unda bu dal calisir
    _yaml = None

# Calisma zamani kopyalarinin uzantisi
RUNTIME_SUFFIX = ".json"


class ConfigError(RuntimeError):
    """Yapilandirma dosyasi okunamadi ya da bicimi bozuk."""


def yaml_available() -> bool:
    return _yaml is not None


def runtime_twin(path: Path) -> Path:
    """Bir YAML dosyasinin calisma zamani JSON esi."""
    return Path(path).with_suffix(RUNTIME_SUFFIX)


def load_config(path: Path) -> tuple[dict, bool]:
    """Yapilandirmayi okur. Doner: (veri, json_kullanildi_mi).

    Bos dosya bos sozluk dondurur; sozluk olmayan icerik hatadir - liste
    donen bir kural dosyasi sessizce "hic kural yok" diye yorumlanirdi.
    """
    path = Path(path)

    if path.suffix.lower() == RUNTIME_SUFFIX:
        return _read_json(path), True

    if _yaml is not None:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigError(f"dosya okunamadi: {path} ({exc})") from exc
        try:
            data = _yaml.safe_load(text) or {}
        except _yaml.YAMLError as exc:
            raise ConfigError(f"YAML bozuk: {path} ({exc})") from exc
        return _as_mapping(data, path), False

    # Kendi okuyucumuz: KAYNAGI okur, yani uretilmis kopyadan daha guncel.
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"dosya okunamadi: {path} ({exc})") from exc
    try:
        return _as_mapping(minyaml.safe_load(text), path), False
    except minyaml.MiniYamlError as own_error:
        twin = runtime_twin(path)
        if twin.is_file():
            return _read_json(twin), True
        raise ConfigError(
            f"{path.name} okunamadi: {own_error}. "
            "Bu yapi bagimliliksiz okuyucunun altkumesinde yok; ya dosyayi "
            "sadelestirin ya da 'python -m pcbqa.bundle <dosya>' ile JSON "
            "kopyasini uretin."
        ) from own_error


def _read_json(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"dosya okunamadi: {path} ({exc})") from exc
    try:
        data = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON bozuk: {path} ({exc})") from exc
    return _as_mapping(data, path)


def _as_mapping(data, path: Path) -> dict:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(
            f"{path.name}: dosyanin koku bir eslesme olmali "
            f"({type(data).__name__} bulundu)"
        )
    return data
