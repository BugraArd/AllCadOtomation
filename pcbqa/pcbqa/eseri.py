"""IEC 60063 E-serisi: hesaplanan degeri SATIN ALINABILIR degere yuvarlar.

Neden gerekli: kural motoru "pull-up en az 2380 ohm olmali" diyebiliyor ama
2380 ohm diye bir direnc satilmiyor. Kullaniciya soylenecek sayi, rafta olan
sayi olmali - yoksa bulgu eyleme donusmuyor.

Kaynak: IEC 60063 (KiCad PCB Calculator "E-Series" sekmesinde de ayni liste).
Degerler bir ONDALIGA kadar tanimli ve her dekatta tekrarlar: E12'de 4.7 varsa
47, 470, 4700 de vardir.

IKI AYRI AILE, IKI AYRI KURAL (2026-09-23 olculdu):
  - 2 HANELI seriler (E3/E6/E12/E24) formulden SAPAR. 10^(n/24) ile uretilen
    24 degerin 21'i gercek E24'ten farkli cikiyor (1.21 vs 1.2, 2.61 vs 2.7,
    2.87 vs 3.0, 3.16 vs 3.3...). Bunlar tarihsel yuvarlamadir; ELLE yazildi.
  - 3 HANELI seriler (E48/E96/E192) formulu IZLER. 10^(n/N) degerini 3 anlamli
    haneye yuvarlamak dogru sonucu veriyor; bu yuzden turetiliyorlar.

TURETMENIN DOGRULANMASI: TI TIDA-010025 uretim BOM'undaki E96'ya ozgu uc
gercek deger (2.49k, 806R, 3.01k) turetilmis listede AYNEN cikiyor. Yani bu
sayilar uydurulmadi, bagimsiz bir kaynakla sinandi (bkz. test_eseri.py).

NEDEN ONEMLI: gercek %1 tasarimlar E96 kullanir. TIDA-010025'in 20 direncinin
TAMAMI %1; ucu yalnizca E96'da. Onlara E24 onermek %3.6'ya varan sapma demek -
parcanin kendi toleransindan buyuk, yani oneri yanlis olur.
"""

from __future__ import annotations

import math

# Her seri, [1, 10) araligindaki mantis degerleri. Parantez icindeki yuzde,
# serinin tasarlandigi tolerans (IEC 60063).
E_SERIES: dict[str, tuple[float, ...]] = {
    "E1": (1.0,),
    "E3": (1.0, 2.2, 4.7),  # %50
    "E6": (1.0, 1.5, 2.2, 3.3, 4.7, 6.8),  # %20
    "E12": (1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2),  # %10
    "E24": (  # %5
        1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0,
        2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3,
        4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1,
    ),
}



def _turet(n_adim: int) -> tuple[float, ...]:
    """3 haneli seriyi 10^(n/N) formulunden uretir (E48/E96/E192).

    Yalnizca 3 HANELI seriler icin dogrudur; 2 haneli seriler (E24 ve altI)
    tarihsel sapmalar icerdiginden elle yazilmistir.
    """
    from decimal import Decimal, ROUND_HALF_UP

    return tuple(
        float(
            Decimal(repr(10 ** (n / n_adim))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
        for n in range(n_adim)
    )


E_SERIES["E48"] = _turet(48)  # %2
E_SERIES["E96"] = _turet(96)  # %1
E_SERIES["E192"] = _turet(192)  # %0.5 ve altI

DEFAULT_SERIES = "E24"

# Kayan nokta payi: 4.7 gibi bir deger log10/pow'dan gectiginde 4.699999...
# olabiliyor; bu pay olmadan kendi serisindeki degeri "altinda" sayardik.
_EPS = 1e-9


class ESeriError(ValueError):
    """Bilinmeyen seri ya da gecersiz deger."""


def _mantis(value: float) -> tuple[float, int]:
    """Degeri (mantis, dekat) olarak ayirir; mantis [1, 10) araliginda."""
    dekat = math.floor(math.log10(value))
    mantis = value / (10.0**dekat)
    # log10 yuvarlama hatasi mantisi araligin disina itebilir
    if mantis >= 10.0 - _EPS:
        mantis /= 10.0
        dekat += 1
    elif mantis < 1.0:
        mantis *= 10.0
        dekat -= 1
    return mantis, dekat


def _adimlar(series: str) -> tuple[float, ...]:
    try:
        return E_SERIES[series]
    except KeyError:
        raise ESeriError(
            f"bilinmeyen E-serisi {series!r}; eldekiler: "
            f"{', '.join(sorted(E_SERIES, key=lambda s: int(s[1:])))}"
        ) from None


def _dogrula(value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ESeriError(f"deger pozitif ve sonlu olmali, verilen: {value!r}")


def up(value: float, series: str = DEFAULT_SERIES) -> float:
    """value'dan KUCUK OLMAYAN en yakin seri degeri.

    Ust sinirlar icin degil, ALT sinirlar icin dogru yon: "en az 2380 ohm"
    denmisse 2.4k secilir, 2.2k degil.
    """
    _dogrula(value)
    adimlar = _adimlar(series)
    mantis, dekat = _mantis(value)
    for adim in adimlar:
        if adim >= mantis - _EPS:
            return adim * 10.0**dekat
    return adimlar[0] * 10.0 ** (dekat + 1)


def down(value: float, series: str = DEFAULT_SERIES) -> float:
    """value'dan BUYUK OLMAYAN en yakin seri degeri.

    Ust sinirlarin dogru yonu: "en fazla 5.6k" denmisse 5.6k degil 4.7k
    secilmez - 5.6k zaten seride oldugu icin kendisi doner.
    """
    _dogrula(value)
    adimlar = _adimlar(series)
    mantis, dekat = _mantis(value)
    for adim in reversed(adimlar):
        if adim <= mantis + _EPS:
            return adim * 10.0**dekat
    return adimlar[-1] * 10.0 ** (dekat - 1)


def nearest(value: float, series: str = DEFAULT_SERIES) -> float:
    """value'ya mutlak olarak en yakin seri degeri.

    Esitlikte BUYUK olan secilir: direncte buyuge yuvarlamak akimi dusurur,
    yani tipik olarak guvenli yon.
    """
    _dogrula(value)
    alt = down(value, series)
    ust = up(value, series)
    if abs(ust - value) <= abs(value - alt):
        return ust
    return alt
