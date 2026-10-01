"""Gercek proje deneyinde aday SECIMI (Kicad-d8k).

Eski davranis (Kicad-ecd): `proje.deney` deneme sirasindaki ilk GECTI adayi
seciyordu. Maliyet hesaplaniyor ama secime girmiyordu; secim, siralayicinin
(model ya da ureteci) sirasina bagliydi.

Kural `en-dusuk-maliyet-v1` - tercih sirasi Kicad-apg ile ayni (tercih.py):

  1 secime yalnizca durum == "gecti" adaylar girer (zorunlu kontrollerin
    hepsi calisti ve gecti). kaldi / arac-hatasi / veri-model-eksik girmez.
  2 maliyet.toplam sonlu ve >= 0 bir sayi olmali. Eksik ya da gecersiz
    maliyet SIFIR SAYILMAZ: aday secim disi kalir, `maliyeti_eksik` altinda
    raporlanir ve kuresel en dusuk iddiasi dusar.
  3 en dusuk degisiklik maliyeti.
  4 esit maliyette belgelenmis ek tercih (tercih.py 3. seviye): daha az YENI
    ihlal. Yeni ihlal = adayin temel kayitta olmayan ihlal imzalari
    (elektrik imzasi + KiCad ERC/DRC/parite turu ve bilesenleri; kozmetik
    DRC dahil - kaydedilir ama adayi kaldirmaz).
  5 hala esitse kararli ureteci kimligi (aday.kimlik, alfabetik). "aday-02-"
    on eki siralayiciya gore degistigi icin anahtar DEGILDIR. Bu adim kalite
    farki degildir: esit maliyetli adaylar raporlanir ve daha kotu oldugu
    soylenmez.

Kapsam: butun adaylar degerlendirilmediyse (ilk gecende durma ya da
--en-fazla) secim "degerlendirilenler arasinda en dusuk"tur; kuresel en
dusuk iddia edilmez. `ilk_gecen` (eski davranis) ayri alanda kalir.

Secim gecerlilik etiketlerini DEGISTIRMEZ: kayit["durum"] ve kayit["egitim"]
yalnizca okunur. Tercih bilgisi ayri `tercih` sozlugunde dondurulur.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

KURAL = "en-dusuk-maliyet-v1"
_ESIT = 1e-9
# KiCad oge metninden bilesen referansi: "Ayak izi R1", "Pad 1 [VIN] of R1".
# Ag adlari koseli parantez icinde ve rakamsiz oldugundan karismaz.
_REF = re.compile(r"\b([A-Z]{1,4}[0-9]{1,4})\b")


def refler(ogeler: Any) -> list[str]:
    """KiCad ihlal ogelerinin metninden bilesen referanslari (sirali, tekil)."""
    bulunan: set[str] = set()
    for o in ogeler or []:
        bulunan.update(_REF.findall(str(o)))
    return sorted(bulunan, key=lambda r: (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r) or 0)))


def kararli_kimlik(k: dict[str, Any]) -> str:
    return str((k.get("aday") or {}).get("kimlik") or k.get("kimlik") or "")


def maliyet_degeri(k: dict[str, Any]) -> tuple[float | None, str]:
    """(maliyet, neden). Maliyet kullanilamiyorsa (None, neden) - asla 0."""
    m = k.get("maliyet")
    if not isinstance(m, dict) or "toplam" not in m:
        return None, "maliyet kaydi yok"
    t = m["toplam"]
    if isinstance(t, bool) or not isinstance(t, (int, float)):
        return None, f"maliyet sayi degil ({t!r})"
    if not math.isfinite(t) or t < 0:
        return None, f"maliyet gecersiz ({t!r})"
    return float(t), ""


def ihlal_imzalari(k: dict[str, Any]) -> set[str]:
    e = k.get("elektrik")
    out = {f"elektrik:{x}" for x in (e.get("ihlaller") or [])} if isinstance(e, dict) else set()
    for v in ((k.get("kicad") or {}).get("ihlaller") or []):
        out.add(f"kicad:{v.get('grup')}:{v.get('tur')}:{','.join(refler(v.get('ogeler')))}")
    return out


def yeni_ihlaller(temel: dict[str, Any] | None, k: dict[str, Any]) -> list[str] | None:
    """Temel kayit yoksa bilinmez (None) - 0 sayilmaz."""
    if temel is None:
        return None
    return sorted(ihlal_imzalari(k) - ihlal_imzalari(temel))


def sec(kayitlar: list[dict[str, Any]], *, aday_sayisi: int | None = None) -> dict[str, Any]:
    """Degerlendirilmis kayitlardan secim. `aday_sayisi` uretilen aday sayisidir;
    bilinmiyorsa (None) kapsam 'bilinmiyor' olur ve kuresel iddia kurulmaz."""
    temel = next((k for k in kayitlar if k.get("tur") == "gercek-temel"), None)
    adaylar = [k for k in kayitlar if k.get("tur") == "gercek-aday"]
    if aday_sayisi is None:
        kapsam = "bilinmiyor"
    else:
        kapsam = "tum-adaylar" if len(adaylar) >= aday_sayisi else "kismi"
    ilk_gecen = next((k["kimlik"] for k in adaylar if k.get("durum") == "gecti"), None)

    tercih: dict[str, dict[str, Any]] = {}
    uygun: list[dict[str, Any]] = []
    eksik: list[str] = []
    for k in adaylar:
        m, neden = maliyet_degeri(k)
        yi = yeni_ihlaller(temel, k)
        t = {"maliyet": m, "yeni_ihlal": None if yi is None else len(yi), "yeni_ihlaller": yi or [],
             "secime_uygun": False, "derece": None, "secildi": False, "esit_maliyet": False, "neden": ""}
        if k.get("durum") != "gecti":
            t["neden"] = f"gecerli degil (durum {k.get('durum')}) - secime girmez"
        elif m is None:
            t["neden"] = f"gecti ama {neden} - secim disi (sifir sayilmadi)"
            eksik.append(k["kimlik"])
        else:
            t["secime_uygun"] = True
            uygun.append(k)
        tercih[k["kimlik"]] = t

    def yi_anahtar(k):
        v = tercih[k["kimlik"]]["yeni_ihlal"]
        return math.inf if v is None else v

    sirali = sorted(uygun, key=lambda k: (tercih[k["kimlik"]]["maliyet"], yi_anahtar(k), kararli_kimlik(k),
                                          k["kimlik"]))
    # Yogun derece (maliyet, yeni ihlal): esit anahtar esit derece (tercih.py ile ayni)
    anahtarlar = sorted({(round(tercih[k["kimlik"]]["maliyet"], 6), yi_anahtar(k)) for k in sirali})
    for k in sirali:
        tercih[k["kimlik"]]["derece"] = anahtarlar.index((round(tercih[k["kimlik"]]["maliyet"], 6), yi_anahtar(k)))

    secilen = sirali[0] if sirali else None
    esit: list[str] = []
    cozum = "yok"
    if secilen is not None:
        ts = tercih[secilen["kimlik"]]
        ts["secildi"] = True
        ts["neden"] = "secildi: gecen adaylar arasinda en dusuk degisiklik maliyeti"
        for k in sirali[1:]:
            t = tercih[k["kimlik"]]
            if abs(t["maliyet"] - ts["maliyet"]) <= _ESIT:
                esit.append(k["kimlik"])
                t["esit_maliyet"] = True
                if yi_anahtar(k) > yi_anahtar(secilen):
                    t["neden"] = (f"ayni maliyet; belgelenmis ek tercih (daha az yeni ihlal) secileni one aldi "
                                  f"({t['yeni_ihlal']} > {ts['yeni_ihlal']})")
                    cozum = "ek-tercih-yeni-ihlal" if cozum == "yok" else cozum
                else:
                    t["neden"] = ("ayni maliyet ve ayni yeni ihlal: esdeger alternatif; esitlik kararli ureteci "
                                  "kimligiyle cozuldu (daha kotu degil)")
                    cozum = "kararli-kimlik"
            else:
                t["neden"] = f"gecti; maliyet {t['maliyet']:g} > secilen {ts['maliyet']:g}"
        if esit:
            ts["esit_maliyet"] = True

    return {
        "kural": KURAL, "kapsam": kapsam, "degerlendirilen": len(adaylar), "toplam_aday": aday_sayisi,
        "kuresel_en_dusuk": secilen is not None and kapsam == "tum-adaylar" and not eksik,
        "ilk_gecen": ilk_gecen,
        "secilen": secilen["kimlik"] if secilen else None,
        "secilen_maliyet": tercih[secilen["kimlik"]]["maliyet"] if secilen else None,
        "secilen_yeni_ihlal": tercih[secilen["kimlik"]]["yeni_ihlal"] if secilen else None,
        "esit_maliyetliler": esit, "esitlik_cozumu": cozum if esit else "yok",
        "maliyeti_eksik": eksik,
        "gecen_sirasi": [k["kimlik"] for k in sirali],
        "gecen_sayisi": sum(1 for k in adaylar if k.get("durum") == "gecti"),
        "gecerli_yok": secilen is None,
        "temel_kaydi": temel is not None,
        "durumlar": dict(sorted(Counter(k.get("durum") for k in adaylar).items(), key=lambda kv: str(kv[0]))),
        "tercih": tercih,
    }
