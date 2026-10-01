"""Duzeltme siralamasinin olcutleri - kullanicinin tanimladigi bes olcut.

Bir PARTI = bir hatali varyant + onun butun adaylari. Uygulama adaylari
siraya gore GERCEK kontrollerden gecirir ve ilk gecerlide durur; her deneme
bir ngspice kosusudur. Buna gore:

  ilk_gecerli     ilk onerinin butun zorunlu kontrolleri gecme orani
  ilk3            ilk uc oneride en az bir gecerli cozum bulunma orani
  simulasyon      ilk gecerli cozume ulasmak icin gereken benzetim sayisi
                  (= ilk gecerlinin sirasi; denetlenemedi aday da bir
                  benzetim harcar ama gecerli sayilmaz)
  yeni_ihlal_ilk  ilk onerinin olusturdugu yeni ihlal sayisi (hata + uyari)
  yeni_ihlal_cozum bulunan cozumun (ilk gecerli) yeni ihlal sayisi
  degisiklik      bulunan cozumun degisiklik sayisi (kucuk olan iyi)

Oranlar COZULEBILIR partiler uzerinden verilir (en az bir gecerli aday);
cozumsuz partiler ayrica sayilir - hicbir siralama onlari kurtaramaz.
"Egitimde bulunmayan tasarimlar" olcutu ayrica bir olcut degil, bu olcutlerin
gruplu (temel tasarim) ve dagilim disi bolmelerde hesaplanmasidir
(bkz. egitim.py).

`rastgele` satiri kapali formla hesaplanir (beklenen deger), ornekleme yok:
  P(ilk gecerli) = k/n,  P(ilk3) = 1 - C(n-k, 3)/C(n, 3),
  E[ilk gecerlinin sirasi] = (n + 1)/(k + 1).
"""

from __future__ import annotations

from math import comb
from typing import Any, Callable, Sequence

from ..ml.dataset import Sample


def _gecerli(s: Sample) -> bool:
    return s.extra.get("durum") == "gecerli"


def partiler(samples: Sequence[Sample]) -> list[list[Sample]]:
    by: dict[str, list[Sample]] = {}
    for s in samples:
        by.setdefault(f"{s.group}|{s.batch}", []).append(s)
    return list(by.values())


def sirala_uretec(parti: list[Sample]) -> list[Sample]:
    return sorted(parti, key=lambda s: s.extra["sira"])


def puan_anahtari(p: float, n_degisiklik: int, sira: int, kova: float | None) -> tuple:
    """Siralama anahtari. `kova` verilirse puan o genislikte kovalara ayrilir
    ve AYNI kovada az degisiklik one gecer.

    Neden (olculdu, Kicad-u4k): etiket yalnizca gecerliligi odullendirir;
    gecerli adaylar arasinda model puani gurultudur ve ham puanla siralayan
    gbt-tam, tek direnc yeterken 4 degisiklikli yeniden tasarimi (paket
    kucultme dahil) secti - cozum basina ortalama 2.38 degisiklik, ureteci
    1.52. Kova genisligi 0.1 muhendislik secimidir.
    """
    if kova:
        return (-int(max(0.0, min(1.0, p)) / kova + 1e-9), n_degisiklik, sira)
    return (-p, sira)


def sirala_puan(puan: Callable[[Sample], float], kova: float | None = None
                ) -> Callable[[list[Sample]], list[Sample]]:
    """Azalan puan; esitlikte ureteci sirasi (kararli)."""
    return lambda parti: sorted(parti, key=lambda s: puan_anahtari(
        puan(s), s.extra["n_degisiklik"], s.extra["sira"], kova))


def sirala_kural_elektrik(parti: list[Sample]) -> list[Sample]:
    """El hesabi gecenler once (benzetim yok, kapali form)."""
    return sorted(parti, key=lambda s: (not s.extra["a_gecer"], s.extra["sira"]))


def sirala_kural_tam(parti: list[Sample]) -> list[Sample]:
    """El hesabi gecen VE geometrik courtyard on kontrolunu gecenler once."""
    return sorted(parti, key=lambda s: (not (s.extra["a_gecer"] and not s.extra["g_cakisma"]),
                                        s.extra["sira"]))


def olc(parts: list[list[Sample]], sirala: Callable[[list[Sample]], list[Sample]]) -> dict[str, Any]:
    cozulebilir = [p for p in parts if any(_gecerli(s) for s in p)]
    ilk, ilk3, sim, yi_ilk, yi_coz, deg = [], [], [], [], [], []
    for p in parts:
        sira = sirala(p)
        yi_ilk.append(sira[0].extra["yeni_ihlal"])
    for p in cozulebilir:
        sira = sirala(p)
        j = next(i for i, s in enumerate(sira) if _gecerli(s))
        ilk.append(1.0 if j == 0 else 0.0)
        ilk3.append(1.0 if j < 3 else 0.0)
        sim.append(j + 1)
        yi_coz.append(sira[j].extra["yeni_ihlal"])
        deg.append(sira[j].extra["n_degisiklik"])
    return _ozet(len(parts), len(cozulebilir), ilk, ilk3, sim, yi_ilk, yi_coz, deg,
                 cozumsuz_sim=sum(len(p) for p in parts if p not in cozulebilir))


def olc_rastgele(parts: list[list[Sample]]) -> dict[str, Any]:
    cozulebilir = [p for p in parts if any(_gecerli(s) for s in p)]
    ilk, ilk3, sim, yi_ilk, yi_coz, deg = [], [], [], [], [], []
    for p in parts:
        yi_ilk.append(sum(s.extra["yeni_ihlal"] for s in p) / len(p))
    for p in cozulebilir:
        n, k = len(p), sum(1 for s in p if _gecerli(s))
        ilk.append(k / n)
        ilk3.append(1.0 - (comb(n - k, 3) / comb(n, 3) if n >= 3 else 0.0))
        sim.append((n + 1) / (k + 1))
        gecerliler = [s for s in p if _gecerli(s)]
        yi_coz.append(sum(s.extra["yeni_ihlal"] for s in gecerliler) / k)
        deg.append(sum(s.extra["n_degisiklik"] for s in gecerliler) / k)
    return _ozet(len(parts), len(cozulebilir), ilk, ilk3, sim, yi_ilk, yi_coz, deg,
                 cozumsuz_sim=sum(len(p) for p in parts if p not in cozulebilir))


def _ort(x: list[float]) -> float | None:
    return sum(x) / len(x) if x else None


def _ozet(n, nc, ilk, ilk3, sim, yi_ilk, yi_coz, deg, cozumsuz_sim) -> dict[str, Any]:
    return {
        "parti": n, "cozulebilir": nc,
        "ilk_gecerli": _ort(ilk), "ilk3": _ort(ilk3), "simulasyon": _ort(sim),
        "simulasyon_max": max(sim) if sim else None,
        "yeni_ihlal_ilk": _ort(yi_ilk), "yeni_ihlal_cozum": _ort(yi_coz), "degisiklik": _ort(deg),
        "cozumsuz_partide_harcanan": cozumsuz_sim,
    }
