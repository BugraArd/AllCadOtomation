"""Termal hesaplar: bakir alanindan jonksiyon sicakligina.

`ipc2221.py` ile ayni desen: saf fonksiyonlar, KiCad bilmez, her sabitin
yaninda kaynagi yazili, testler beklenen degerleri dokumandan alir.

NEDEN BU MODUL: `copper_area` kurali ham mm2 olcuyordu ve on ayarda YORUM
SATIRINDA birakilmisti - cunku "en az 2000 mm2" gibi sabit bir esik, guc
dissipasyonu ve ortam sicakligi bilinmeden savunulamaz. 1 W'lik bir
regulator icin 25 C ortamda ~150 mm2 yeterken 70 C ortamda ~1900 mm2
gerekiyor; ayni sayi ikisine birden uyamaz. Burada esik degil HESAP var:
alan -> theta_JA -> Tj.
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Olculmus theta_JA egrileri: (bakir alani mm2, theta_JA C/W)
#
# SOT-223: Richtek AN044 Bolum 4.2, JESD51 kartinda OLCULMUS. Bu projedeki
# en degerli termal veri - cunku alanin FONKSIYONU, tek bir sayi degil.
#
# Tek noktali paketler (MaxLinear ANP-02, 4 katli JEDEC karti): alan
# bagimliligi olculmemis. Onlari da tutuyoruz ama `area_dependent` False -
# kural "bakir ekleyin" diyemez, cunku o oneriyi destekleyen olcum yok.
# ---------------------------------------------------------------------------

THETA_JA_CURVES: dict[str, tuple[tuple[float, float], ...]] = {
    # Richtek AN044 4.2 - dort nokta, tek kat, JESD51
    "sot223": ((16.0, 135.0), (100.0, 107.0), (2500.0, 50.0), (3600.0, 45.0)),
    # MaxLinear ANP-02 - 4 katli JEDEC karti, TEK nokta
    "sot23": ((None, 220.0),),
    "so8": ((None, 128.4),),
    "dfn8": ((None, 59.0),),
}

SOURCES: dict[str, str] = {
    "sot223": "Richtek AN044 4.2 (JESD51, tek kat)",
    "sot23": "MaxLinear ANP-02 (4 katli JEDEC karti)",
    "so8": "MaxLinear ANP-02 (4 katli JEDEC karti)",
    "dfn8": "MaxLinear ANP-02 (4 katli JEDEC karti)",
}


def is_area_dependent(package: str) -> bool:
    """Bu paket icin theta_JA'nin bakir alanina bagimliligi OLCULMUS mu?"""
    curve = THETA_JA_CURVES[package]
    return len(curve) > 1


def theta_ja_c_per_w(package: str, area_mm2: float) -> float:
    """Verilen bakir alaninda theta_JA (C/W).

    Ara degerler log10(alan) uzerinde DOGRUSAL ara deger ile bulunur. Neden
    log: olculen dort nokta on yillik alan araliginda (16 -> 3600 mm2) ve
    aralarindaki egim decade basina neredeyse sabit (-35, -41, -32 C/W).
    Dogrusal alan uzerinde ara deger alsaydik 100-2500 arasi asiri iyimser
    cikardi. Ara deger olculen noktalardan TAM gecer; yeni bir egri uydurmaz.

    Aralik disi CLAMP edilir:
      * En kucuk olculen alanin (16 mm2) altinda ekstrapolasyon yapilmaz.
        Zaten SOT-223'un cip pad'i tek basina ~16 mm2; altina inmek fiziksel
        olarak zor. Clamp burada IYIMSER yonde (gercek theta_JA daha yuksek
        olurdu) - bu bilincli bir sinir, asagida kurala uyari olarak gecer.
      * En buyuk olculen alanin ustunde clamp MUHAFAZAKAR: doygunluk gercek
        (TI SLPA015 2: yuzey basina ~4.5 in2'de doyuyor), yani gercek
        theta_JA biraz daha dusuk olabilir; biz sicagi fazla tahmin ederiz.
    """
    curve = THETA_JA_CURVES[package]
    if not is_area_dependent(package):
        return curve[0][1]
    if area_mm2 <= 0:
        raise ValueError("bakir alani pozitif olmali")

    if area_mm2 <= curve[0][0]:
        return curve[0][1]
    if area_mm2 >= curve[-1][0]:
        return curve[-1][1]

    la = math.log10(area_mm2)
    for (a0, t0), (a1, t1) in zip(curve, curve[1:]):
        if a0 <= area_mm2 <= a1:
            f = (la - math.log10(a0)) / (math.log10(a1) - math.log10(a0))
            return t0 + f * (t1 - t0)
    raise AssertionError("egri sirali degil")  # pragma: no cover


def junction_temp_c(
    package: str, area_mm2: float, power_w: float, ambient_c: float
) -> float:
    """Tj = TA + P * theta_JA(alan).

    Kararli hal, tek isi kaynagi. Komsu bilesenlerin isitmasi HESABA
    KATILMAZ; bu yuzden sonuc bir ALT SINIRDIR - gercek kart daha sicaktir.
    """
    return ambient_c + power_w * theta_ja_c_per_w(package, area_mm2)


def required_area_mm2(
    package: str, power_w: float, ambient_c: float, tj_max_c: float
) -> float | None:
    """Tj'yi sinirda tutan EN KUCUK bakir alani.

    None doner:
      * paketin alan bagimliligi olculmemisse (oneri verecek veri yok),
      * en buyuk olculen alanda bile Tj asiliyorsa - o zaman cozum bakir
        degil paket/soguturucu degisikligidir; uydurma bir sayi vermeyiz.
    """
    if power_w <= 0:
        raise ValueError("guc pozitif olmali")
    if not is_area_dependent(package):
        return None

    needed_theta = (tj_max_c - ambient_c) / power_w
    curve = THETA_JA_CURVES[package]
    if needed_theta >= curve[0][1]:
        return curve[0][0]  # en kucuk footprint bile yetiyor
    if needed_theta < curve[-1][1]:
        return None  # olculen en buyuk alan bile yetmiyor

    for (a0, t0), (a1, t1) in zip(curve, curve[1:]):
        if t1 <= needed_theta <= t0:
            f = (needed_theta - t0) / (t1 - t0)
            return 10 ** (math.log10(a0) + f * (math.log10(a1) - math.log10(a0)))
    raise AssertionError("egri azalan degil")  # pragma: no cover
