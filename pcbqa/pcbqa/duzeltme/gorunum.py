"""Var olan bir gercek deney kaynagini okur ve gosterime hazirlar (Kicad-d8k).

`pcbqa duzeltme-proje goster` ve arayuzun Deney sekmesi AYNI fonksiyonu
cagirir; secim (secim.py), gerekce (aciklama.py) ve kaynak turu
(envanter.py) burada yeniden yazilmaz.

Kaynak bir gercek deney degilse (bellek veri kumesi, bos klasor) hata
verilir: gercek proje degerlendirmesi yapilmis izlenimi verilmez.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .aciklama import (degisiklik_metni, gecti_ozeti, kontrol_aciklamalari, rapor_metni, secim_metni,
                       tercih_hucresi)
from .envanter import KAYNAK_GERCEK, KaynakHatasi, gercek_kayit_sorunu, jsonl_oku, kaynak_turu
from .secim import maliyet_degeri, sec

__all__ = ["DeneyGorunumu", "KaynakHatasi", "deney_yukle"]


@dataclass
class DeneyGorunumu:
    yol: Path
    dosya: Path
    kayitlar: list[dict[str, Any]]
    bozuk: list[dict[str, Any]]
    rapor: dict[str, Any]
    secim: dict[str, Any]
    satirlar: list[dict[str, Any]] = field(default_factory=list)
    metin: str = ""
    secim_satirlari: list[str] = field(default_factory=list)


def deney_yukle(yol: Path) -> DeneyGorunumu:
    tur, dosya = kaynak_turu(Path(yol))
    if tur != KAYNAK_GERCEK:
        raise KaynakHatasi(f"{yol}: {tur} - gercek proje deneyi DEGIL (sentetik bellek verisi). Aday secimi ve "
                           "gerekce gosterilmez; dagilim icin envanteri kullanin.")
    ham, bozuk = jsonl_oku(dosya)
    kayitlar = []
    for k in ham:
        sorun = gercek_kayit_sorunu(k)
        if sorun:
            bozuk.append({"satir": k.get("_satir"), "neden": sorun})
        else:
            kayitlar.append(k)
    if not any(k["tur"] == "gercek-temel" for k in kayitlar):
        raise KaynakHatasi(f"{dosya}: okunabilir temel kaydi yok ({len(bozuk)} bozuk satir) - gercek deney "
                           "olarak gosterilemez")
    try:
        rapor = json.loads((dosya.parent / "ozet.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rapor = {}
    temel = next(k for k in kayitlar if k["tur"] == "gercek-temel")
    rapor.setdefault("temel", temel["temel"].get("klasor", "?"))
    rapor.setdefault("adaylar", None)       # bilinmiyorsa kapsam 'bilinmiyor' (kuresel iddia yok)
    s = sec(kayitlar, aday_sayisi=rapor.get("adaylar"))
    satirlar = []
    for k in kayitlar:
        t = s["tercih"].get(k["kimlik"])
        m, _ = maliyet_degeri(k)
        aciklamalar = kontrol_aciklamalari(k)
        if k.get("durum") == "gecti":
            aciklamalar = [{"kod": "-", "durum": "gecti", "metin": gecti_ozeti(k)}] + aciklamalar
        satirlar.append({
            "kimlik": k["kimlik"], "tur": k["tur"], "degisiklik": degisiklik_metni(k),
            "maliyet": "-" if m is None else f"{m:g}", "durum": k.get("durum"),
            "tercih": tercih_hucresi(t) if t else "temel", "tercih_nedeni": (t or {}).get("neden", ""),
            "aciklamalar": aciklamalar,
        })
    metin = rapor_metni(kayitlar, rapor)
    if bozuk:
        metin += "\n\n## Okunamayan kayitlar\n\n" + "\n".join(f"- satir {b['satir']}: {b['neden']}" for b in bozuk)
    return DeneyGorunumu(Path(yol), dosya, kayitlar, bozuk, rapor, s, satirlar, metin, secim_metni(s, kayitlar))
