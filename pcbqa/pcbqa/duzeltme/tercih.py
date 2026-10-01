"""Tercih sirasi ve sozluksel egitim hedefi (Kicad-apg).

Tercih sirasi (kullanici talimati, 2026-10-01):

  1. zorunlu elektriksel ve tasarim gereksinimlerini karsilamak (gecerlilik)
  2. gecerli adaylar arasinda DEGISIKLIK MALIYETINI azaltmak (maliyet.py)
  3. esdeger (ayni maliyetli) adaylarda tanimli ek tercih: daha az YENI ihlal

Iki ve uc yalnizca GECERLI adaylar arasinda uygulanir. `denetlenemedi`
(eksik model, yakinsamama) gecersiz ile birlestirilmez: hedefe girmez.
Gecerli adayi olmayan parti `cozumsuz` diye isaretlenir.

## Hedef (sozluksel-v1)

Parti = ayni hatali varyant (ayni sorun + ayni calisma kosulu). Parti
ICINDE gecerli adaylar (maliyet, yeni ihlal) anahtariyla YOGUN siralanir
(esit anahtar = esit derece). Derece r / R (R farkli anahtar sayisi):

    hedef = 1 - 0.5 * r / (R - 1)    gecerli   (R = 1 ise 1.0)  -> [0.5, 1]
    hedef = 0                        gecersiz
    hedef = yok                      denetlenemedi (egitime girmez)

Hedef parti-gorelidir: farkli devrelerin adaylari ortak bir maliyet
siralamasina KONMAZ (12 V bolucunun 2 birimlik adayi ile 5 V bolucunun 1
birimlik adayi karsilastirilmaz; her biri kendi partisinde derecelenir).
0.5'lik bosluk gecerliligin (1. seviye) tercihten (2.-3. seviye) her zaman
once gelmesini saglar: en kotu gecerli bile en iyi gecersizden yuksektir.

Neden noktasal regresyon (ilk surum icin en basit uygun yontem): mevcut
`ml/` ridge ve GBT'yi, model dosya bicimini ve yukleme/sema denetimini
degistirmeden kullanir. Ciftli (pairwise) siralama yeni bir ogrenici
gerektirirdi. Ciktilar SIRALAMA PUANIDIR, olasilik degildir (kalibre
edilmedi) - raporlarda "puan" diye gecer.

## Politikalar (simulasyon SONRASI secim)

  ilk-gecerli   adaylar sirayla dogrulanir, ilk gecerlide durulur
                (uygulamanin davranisi). Benzetim = ilk gecerlinin sirasi.
  ilk-k         ilk k aday dogrulanir, icindeki gecerlilerden en dusuk
                maliyetli secilir; ilk k'da gecerli yoksa ilk gecerliye kadar
                devam edilir. Benzetim >= k.
  dogrudan      BUTUN adaylar dogrulanir, gecerliler arasindan en dusuk
                maliyet secilir. Pismanlik tanim geregi 0; bedeli parti
                basina aday sayisi kadar benzetimdir.

Olcutler: ilk oneri gecerli, ilk 3'te cozum, benzetim (ilk gecerliye /
secime kadar), pismanlik = secilen maliyet - partideki en dusuk gecerli
maliyet, en dusuk maliyetin secilme orani.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from ..ml.dataset import Sample

HEDEF_ADI = "sozluksel-v1"
GECERLILIK = "gecerlilik"
HEDEFLER = (GECERLILIK, HEDEF_ADI)
_EPS = 1e-9


def _gecerli(s: Sample) -> bool:
    return s.extra.get("durum") == "gecerli"


def tercih_anahtari(s: Sample) -> tuple[float, int]:
    """2. ve 3. seviye: (maliyet, yeni ihlal). Kucuk olan tercih edilir."""
    return (round(float(s.extra["maliyet"]), 6), int(s.extra.get("yeni_ihlal", 0)))


def partiler(samples: Sequence[Sample]) -> list[list[Sample]]:
    by: dict[str, list[Sample]] = {}
    for s in samples:
        by.setdefault(f"{s.group}|{s.batch}", []).append(s)
    return list(by.values())


def hedefleri_ekle(samples: Sequence[Sample]) -> None:
    """Her ornege `tercih_hedefi`, `tercih_derecesi` ve `parti_cozumsuz` yazar."""
    for p in partiler(samples):
        anahtarlar = sorted({tercih_anahtari(s) for s in p if _gecerli(s)})
        r_say = len(anahtarlar)
        for s in p:
            s.extra["parti_cozumsuz"] = r_say == 0
            if _gecerli(s):
                r = anahtarlar.index(tercih_anahtari(s))
                s.extra["tercih_derecesi"] = r
                s.extra["tercih_hedefi"] = 1.0 - 0.5 * r / (r_say - 1) if r_say > 1 else 1.0
            elif s.extra.get("durum") == "gecersiz":
                s.extra["tercih_derecesi"] = None
                s.extra["tercih_hedefi"] = 0.0
            else:
                s.extra["tercih_derecesi"] = None
                s.extra["tercih_hedefi"] = None


def hedef_ornekleri(samples: Sequence[Sample], hedef: str) -> list[Sample]:
    """Egitim ornekleri: etiket = secilen hedef; denetlenemedi DISARIDA."""
    out = []
    for s in samples:
        if hedef == GECERLILIK:
            y = s.label if s.label in (0.0, 1.0) else None
        elif hedef == HEDEF_ADI:
            y = s.extra.get("tercih_hedefi")
        else:
            raise ValueError(f"bilinmeyen hedef: {hedef!r} (gecerli: {HEDEFLER})")
        if y is not None:
            out.append(Sample(list(s.features), float(y), s.group, s.batch, s.extra))
    return out


# --------------------------------------------------------------------------
# Siralama anahtarlari (simulasyon ONCESI)
# --------------------------------------------------------------------------


def kova_anahtari(p: float, ikincil: float, sira: int, kova: float | None) -> tuple:
    """GECICI siralama kurali (kullanici talimati: 0.1'lik dilimler gecici kural
    olarak kalsin). Puan `kova` genisliginde dilimlenir; ayni dilimde
    `ikincil` (degisiklik sayisi ya da maliyet) kucuk olan once."""
    if kova:
        return (-int(max(0.0, min(1.0, p)) / kova + 1e-9), ikincil, sira)
    return (-p, sira)


def sirala_puan(puan: Callable[[Sample], float], kova: float | None = None, ikincil: str = "n_degisiklik"
                ) -> Callable[[list[Sample]], list[Sample]]:
    return lambda parti: sorted(parti, key=lambda s: kova_anahtari(
        puan(s), float(s.extra[ikincil]), s.extra["sira"], kova))


def sirala_uretec(parti: list[Sample]) -> list[Sample]:
    return sorted(parti, key=lambda s: s.extra["sira"])


def sirala_kural_elektrik(parti: list[Sample]) -> list[Sample]:
    return sorted(parti, key=lambda s: (not s.extra["a_gecer"], s.extra["sira"]))


def sirala_kural_elektrik_maliyet(parti: list[Sample]) -> list[Sample]:
    """El hesabi gecenler once, aralarinda dusuk maliyet once (benzetimsiz kural)."""
    return sorted(parti, key=lambda s: (not s.extra["a_gecer"], s.extra["maliyet"], s.extra["sira"]))


# --------------------------------------------------------------------------
# Olcutler
# --------------------------------------------------------------------------


def _secim_anahtari(s: Sample) -> tuple:
    return (*tercih_anahtari(s), s.extra["sira"])


def olc(parts: list[list[Sample]], sirala: Callable[[list[Sample]], list[Sample]] | None,
        politika: str = "ilk-gecerli", k: int = 3) -> dict[str, Any]:
    """`sirala=None` ve politika 'dogrudan': butun adaylar dogrulanir."""
    cozulebilir = [p for p in parts if any(_gecerli(s) for s in p)]
    ilk, ilk3, sim, pis, en_az, mal, deg = [], [], [], [], [], [], []
    for p in cozulebilir:
        gecerliler = [s for s in p if _gecerli(s)]
        en_dusuk = min(s.extra["maliyet"] for s in gecerliler)
        if politika == "dogrudan":
            secilen = min(gecerliler, key=_secim_anahtari)
            sim.append(len(p))
        else:
            sira = sirala(p)
            j = next(i for i, s in enumerate(sira) if _gecerli(s))
            ilk.append(1.0 if j == 0 else 0.0)
            ilk3.append(1.0 if j < 3 else 0.0)
            if politika == "ilk-gecerli" or j >= k:
                secilen, n = sira[j], j + 1
            elif politika == "ilk-k":
                secilen = min((s for s in sira[:k] if _gecerli(s)), key=_secim_anahtari)
                n = min(k, len(p))
            else:
                raise ValueError(f"bilinmeyen politika: {politika}")
            sim.append(n)
        fark = secilen.extra["maliyet"] - en_dusuk
        pis.append(fark)
        en_az.append(1.0 if fark <= _EPS else 0.0)
        mal.append(secilen.extra["maliyet"])
        deg.append(secilen.extra["n_degisiklik"])

    def ort(x):
        return sum(x) / len(x) if x else None

    return {
        "parti": len(parts), "cozulebilir": len(cozulebilir), "cozumsuz": len(parts) - len(cozulebilir),
        "ilk_gecerli": ort(ilk), "ilk3": ort(ilk3), "simulasyon": ort(sim),
        "simulasyon_max": max(sim) if sim else None,
        "pismanlik": ort(pis), "pismanlik_max": max(pis) if pis else None, "en_az_secildi": ort(en_az),
        "maliyet": ort(mal), "degisiklik": ort(deg),
        # Cozumsuz partide hicbir siralama cozum bulamaz; uygulama hepsini dener.
        "cozumsuz_partide_harcanan": sum(len(p) for p in parts if p not in cozulebilir),
    }
