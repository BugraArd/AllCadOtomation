"""Kontrollu hatali varyantlar - referans tasarimdan bilinen bir hatayla.

Her hata gercek dunyada gorulen bir tasarim/montaj yanlisinin karsiligidir:

  deger-ust / deger-alt  BOM'da yanlis deger (komsu E24 degeri, x0.33..x3.3)
  deger-takas            R_ust ile R_alt yer degistirmis (montaj karisikligi)
  tolerans-gevsek        %1 yerine %5 parca
  paket-kucuk            guc icin secilmis paket kucuk bir pakete inmis (BOM + footprint
                         birlikte; MPN varsa yeni pakete esitlenir). Gecersizlik nedeni
                         guc, gerilim ya da hicbiri olabilir - "kucuk = hata" DEGIL.
  paket-buyuk            iki paket buyuk parca (BOM + footprint) sikisik kartta
                         (mekanik neden: courtyard) - Kicad-7cb
  mpn-paket              BOM'da yanlis paketli parca: MPN baska paket, footprint
                         ayni (pad/footprint uyusmazligi) - yalnizca MPN'li tasarimda
  empedans-yuksek        iki direnc de x10..x100 (oran ayni, yuk etkisi buyur)
  empedans-dusuk         iki direnc de /10../100 (oran ayni, kayip buyur)

Hata turu YALNIZCA kayda yazilir; aday ureteci ve model onu GORMEZ (gercek
kullanimda kimse hatanin turunu soylemez - bulgulari gorur).
"""

from __future__ import annotations

import random
from typing import Any

from .. import eseri
from ..circuit import parse_value
from ..devre.parca import e_serisinde, paket_kodu
from .bolucu import FOOTPRINT, PAKETLER
from .tasarim import MPN_ALANI, TOLERANS_ALANI, Degisiklik, Tasarim, deger_metni, tolerans_metni

HATA_TURLERI = ("deger-ust", "deger-alt", "deger-takas", "tolerans-gevsek", "paket-kucuk",
               "empedans-yuksek", "empedans-dusuk", "paket-buyuk", "mpn-paket")


def _deger(t: Tasarim, ref: str) -> float:
    v = parse_value(t.netlist.components[ref].value)
    if v is None:
        raise ValueError(f"{ref} degeri okunamadi")
    return v


def _paket(t: Tasarim, ref: str) -> str:
    return paket_kodu(t.netlist.components[ref].footprint)


def hata_degisiklikleri(t: Tasarim, ust: str, alt: str, tur: str, rng: random.Random,
                        hedef_paket: str | None = None) -> tuple[list[Degisiklik], dict[str, Any]] | None:
    """Hatanin degisiklik listesi; bu tasarimda anlamsizsa None.

    `hedef_paket`: paket-kucuk icin ornekleme politikasinin sectigi hedef
    (dengeli politika guc oranini sinir bantlarina gore hedefler)."""
    c = t.netlist.components
    r1, r2 = _deger(t, ust), _deger(t, alt)
    if tur in ("deger-ust", "deger-alt"):
        ref, r = (ust, r1) if tur == "deger-ust" else (alt, r2)
        carpan = rng.choice((0.33, 0.5, 0.68, 1.5, 2.2, 3.3))
        yeni = eseri.nearest(r * carpan, "E24")
        if abs(yeni - r) / r < 1e-6:
            return None
        return [Degisiklik(ref, "deger", c[ref].value.split()[0], deger_metni(yeni))], {"carpan": carpan}
    if tur == "deger-takas":
        if abs(r1 - r2) / max(r1, r2) < 0.05:
            return None
        return [Degisiklik(ust, "deger", c[ust].value.split()[0], c[alt].value.split()[0]),
                Degisiklik(alt, "deger", c[alt].value.split()[0], c[ust].value.split()[0])], {}
    if tur == "tolerans-gevsek":
        if any(c[r].fields.get(TOLERANS_ALANI) == "5%" for r in (ust, alt)):
            return None
        # RC_L %5 yalnizca E24: E96 degerin %5'lik parcasi yok (uydurulmaz)
        if any(not e_serisinde(v, "E24") for v in (r1, r2)):
            return None
        return [Degisiklik(r, "tolerans", c[r].fields.get(TOLERANS_ALANI, ""), tolerans_metni(0.05))
                for r in (ust, alt)], {}
    if tur in ("paket-buyuk", "mpn-paket"):
        out = []
        for r in (ust, alt):
            p = _paket(t, r)
            if p not in PAKETLER:
                return None
            if tur == "paket-buyuk":
                j = PAKETLER.index(p) + 2
                if j < len(PAKETLER):
                    out.append(Degisiklik(r, "footprint", c[r].footprint, FOOTPRINT[PAKETLER[j]]))
            else:
                mpn = c[r].fields.get(MPN_ALANI)
                if not mpn or PAKETLER.index(p) == 0:
                    return None
                yeni = mpn.replace(f"RC{p}", f"RC{PAKETLER[PAKETLER.index(p) - 1]}", 1)
                out.append(Degisiklik(r, "mpn", mpn, yeni))
                break      # tek direncte BOM hatasi
        return (out, {}) if out else None
    if tur == "paket-kucuk":
        out = []
        hedef = hedef_paket or rng.choice(("0201", "0402"))
        for r in (ust, alt):
            p = _paket(t, r)
            if p and PAKETLER.index(p) > PAKETLER.index(hedef):
                out.append(Degisiklik(r, "footprint", c[r].footprint, FOOTPRINT[hedef]))
        return (out, {"hedef_paket": hedef}) if out else None
    if tur in ("empedans-yuksek", "empedans-dusuk"):
        carpan = rng.choice((10.0, 33.0, 100.0))
        if tur == "empedans-dusuk":
            carpan = 1.0 / carpan
        out = []
        for r, v in ((ust, r1), (alt, r2)):
            yeni = eseri.nearest(min(max(v * carpan, 1.0), 10e6), "E96")
            out.append(Degisiklik(r, "deger", c[r].value.split()[0], deger_metni(yeni)))
        return out, {"carpan": carpan}
    raise ValueError(f"bilinmeyen hata turu: {tur}")
