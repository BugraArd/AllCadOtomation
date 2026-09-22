"""Devre dogrulugu hesaplari: bilesen DEGERI dogru mu?

Mevcut kural tipleri geometriyi (mesafe, aciklik) ve bakiri (genislik, alan)
olcuyordu. Hicbiri "bu pull-up 4k7, 400 pF bus icin dogru mu" sorusunu soramaz.
Bu modul o hesaplari tasir.

Neden ayri bir modul: `ipc2221.py` ile ayni desen - saf fonksiyonlar, KiCad'i
bilmez, her sabitin yaninda kaynagi yazili, testler beklenen degerleri
dokumandan alir.

ONEMLI - bu hesaplarin cogu tasarim dosyasinda OLMAYAN bilgi ister: bus
kapasitansi, besleme gerilimi, FB bias akimi, kristalin yuk kapasitansi. Bunlar
kural YAML'inda BEYAN EDILMELIDIR. Beyan yoksa kural sessizce atlanir; varsayilan
uydurmak yanlis guven verirdi.

Kaynaklar: docs/tasarim-kurallari/03-yuksek-hiz-sinyal.md (3.2, 3.8),
01-anahtarlamali-guc.md (1.4)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

# --- Deger ayristirici ------------------------------------------------------
#
# KiCad deger alanlari duzensizdir. Ayni direnc su bicimlerin hepsinde yazilir:
#   4k7   4.7k   4700   4700R   4.7K   "4k7 1%"   "4K7 0603"
# Kondansatorler icin:
#   100n  100nF  0.1uF  0.1µF   "100nF 50V X7R"
#
# IEC 60062 (RKM kodu): carpan harfi ONDALIK NOKTANIN YERINE gecer. "4k7" =
# 4.7k demektir, "4 k 7" degil. Bu, ondalik noktanin fotokopide kaybolmasina
# karsi tasarlanmisti ve hala yaygin.

# Buyuk/kucuk harf AYRIMI onemlidir: "M" mega (1e6), "m" mili (1e-3).
# "R" carpan degil, birim isaretidir (ohm) ve 1.0 gibi davranir.
_MULTIPLIERS: dict[str, float] = {
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "µ": 1e-6,  # MICRO SIGN
    "μ": 1e-6,  # GREEK SMALL LETTER MU - KiCad bazen bunu yaziyor
    "m": 1e-3,
    "R": 1.0,  # carpan degil, ohm isareti: "1R0" = 1.0 ohm
    "r": 1.0,
    "E": 1.0,  # bazi Avrupa kutuphanelerinde ohm isareti
    "k": 1e3,
    "K": 1e3,
    "M": 1e6,
    "G": 1e9,
}

# Yerlestirilmeyecek bilesenler - deger degil, niyet bildirir.
_NOT_FITTED = {"dnp", "nf", "n/f", "no fit", "nofit", "-", "*", "?", ""}

# Ozensiz kutuphanelerde deger alanina PAKET KODU yaziliyor. "0603" duz sayi
# olarak 603 ohm diye ayristirilir ve 1k-10k bekleyen bir kural yanlis alarm
# verir. Kimse 603 ohm'luk bir direnci "0603" diye yazmaz; bunlari coz(ul)emez
# saymak gurultuyu keser.
_PACKAGE_CODES = {
    "0201", "0402", "0603", "0805", "1206", "1210", "1218",
    "1812", "2010", "2512", "2920",
}

# 4k7 / 1R0 / 100n bicimi: sayi, carpan harfi, sayi
_RKM = re.compile(r"^(\d+)([pnuµμmRrEkKMG])(\d+)$")
# 4.7k / 100nF / 0.1uF bicimi: sayi, istege bagli carpan, istege bagli birim
_PLAIN = re.compile(r"^(\d*\.?\d+)\s*([pnuµμmRrEkKMG])?\s*([FfHhΩ]|ohm|OHM|R)?$")


def parse_value(text: str | None) -> float | None:
    """Bir bilesen degerini SI taban birimine cevirir (ohm / farad / henry).

    Birimi DONDURMEZ: "100n" bir kondansatorde 100 nF, bir bobinde 100 nH'dir.
    Hangi birim oldugunu cagiran bilir (bilesen turunden).

    Coz(ul)emeyen ya da takilmayacak bilesen icin None doner - hata degil.
    Kural motoru None'i "olculemez" diye ele almalidir; deger alanina serbest
    metin yazmak yaygindir ve bunu hata saymak gurultu uretir.
    """
    if text is None:
        return None
    raw = str(text).strip()
    if raw.lower() in _NOT_FITTED:
        return None
    if raw in _PACKAGE_CODES:
        return None

    # Ilk parcayi al: "100nF 50V X7R 0603" -> "100nF"
    token = raw.split()[0] if raw.split() else ""
    if not token:
        return None
    # Sondaki birim/tolerans isaretlerini at: "4k7," "100nF;" gibi
    token = token.rstrip(",;")

    match = _RKM.match(token)
    if match:
        whole, mult, frac = match.groups()
        return float(f"{whole}.{frac}") * _MULTIPLIERS[mult]

    match = _PLAIN.match(token)
    if match:
        number, mult, _unit = match.groups()
        return float(number) * (_MULTIPLIERS[mult] if mult else 1.0)

    return None


# --- I2C pull-up boyutlandirma (NXP UM10204) --------------------------------
#
# Rp(max) = tr / (0.8473 * Cb)      -- yukselme suresi butcesi
# Rp(min) = (VDD - VOL(max)) / IOL  -- surucunun cekebilecegi akim
#
# 0.8473 katsayisi RC egrisinin VIL=0.3*VDD -> VIH=0.7*VDD arasindaki kismindan
# gelir; UM10204 7.1'de tureti(li)yor.

I2C_RC_FACTOR = 0.8473
I2C_MAX_BUS_CAPACITANCE_F = 400e-12  # UM10204 Tablo 10 - tum kipler icin
I2C_IOL_A = 3e-3  # standart I2C surucu; SMBus high power 4 mA
I2C_VOL_MAX_V = 0.4

# Kip -> izin verilen maksimum yukselme suresi (UM10204 Tablo 10)
I2C_RISE_TIME_S: dict[str, float] = {
    "standard": 1000e-9,
    "fast": 300e-9,
    "fast_plus": 120e-9,
}


def i2c_pullup_max_ohms(bus_capacitance_f: float, mode: str = "fast") -> float:
    """Yukselme suresi butcesinin izin verdigi EN BUYUK pull-up direnci."""
    if bus_capacitance_f <= 0:
        raise ValueError("bus_capacitance_f pozitif olmali")
    if mode not in I2C_RISE_TIME_S:
        raise ValueError(f"bilinmeyen I2C kipi {mode!r}; {sorted(I2C_RISE_TIME_S)}")
    return I2C_RISE_TIME_S[mode] / (I2C_RC_FACTOR * bus_capacitance_f)


def i2c_pullup_min_ohms(
    vdd_v: float, iol_a: float = I2C_IOL_A, vol_max_v: float = I2C_VOL_MAX_V
) -> float:
    """Surucunun sifira cekebilmesi icin gereken EN KUCUK pull-up direnci."""
    if vdd_v <= vol_max_v:
        raise ValueError("vdd_v, vol_max_v'den buyuk olmali")
    if iol_a <= 0:
        raise ValueError("iol_a pozitif olmali")
    return (vdd_v - vol_max_v) / iol_a


def i2c_needs_current_source(bus_capacitance_f: float) -> bool:
    """200 pF ustunde duz direnc yetmez (UM10204 7.1).

    UM10204: 200-400 pF arasi Fast-mode'da akim kaynagi ya da anahtarlamali
    direnc devresi gerekir; 400 pF ustu hicbir kipte gecerli degildir.
    """
    return bus_capacitance_f > 200e-12


# --- Kristal yuk kondansatoru (Microchip AN826) -----------------------------
#
# CL = (C1 * C2) / (C1 + C2) + Cstray      -- kristalin gordugu yuk
# C1 = C2 = C icin:  CL = C/2 + Cstray  ->  C = 2 * (CL - Cstray)

CRYSTAL_STRAY_C_MIN_F = 2e-12  # AN826: PCB + pin stray 2-5 pF
CRYSTAL_STRAY_C_MAX_F = 5e-12


def crystal_load_capacitor_f(cl_f: float, stray_f: float) -> float:
    """Kristalin CL'sini karsilamak icin gereken TEK kondansator degeri."""
    if cl_f <= stray_f:
        raise ValueError("kristalin CL'si stray kapasitanstan buyuk olmali")
    return 2.0 * (cl_f - stray_f)


def crystal_load_capacitor_range_f(cl_f: float) -> tuple[float, float]:
    """Stray belirsizliginden (2-5 pF) dogan kabul edilebilir aralik.

    Stray BUYUDUKCE gereken kondansator KUCULUR, bu yuzden alt sinir max
    stray'den, ust sinir min stray'den gelir.
    """
    low = crystal_load_capacitor_f(cl_f, CRYSTAL_STRAY_C_MAX_F)
    high = crystal_load_capacitor_f(cl_f, CRYSTAL_STRAY_C_MIN_F)
    return (low, high)


# --- Geri besleme bolucu (Richtek AN033) ------------------------------------
#
# Bolucuden gecen akim, FB pininin bias akiminin en az 100 KATI olmali; yoksa
# bias akimi cikis gerilimini kaydirir.

FB_DIVIDER_CURRENT_RATIO = 100.0


def fb_divider_max_bottom_ohms(
    vfb_v: float, bias_current_a: float, ratio: float = FB_DIVIDER_CURRENT_RATIO
) -> float:
    """Alt bolucu direncinin ust siniri.

    I_bolucu = Vfb / R2 >= ratio * I_bias  ->  R2 <= Vfb / (ratio * I_bias)
    """
    if vfb_v <= 0:
        raise ValueError("vfb_v pozitif olmali")
    if bias_current_a <= 0:
        raise ValueError("bias_current_a pozitif olmali")
    return vfb_v / (ratio * bias_current_a)


# --- Decoupling yogunlugu (TI SPRABV2) --------------------------------------

DECOUPLING_POWER_PINS_PER_100N = 2
DECOUPLING_POWER_PINS_PER_BULK = 10


def decoupling_counts(power_pins: int) -> tuple[int, int]:
    """(gereken 0.1 uF sayisi, gereken bulk sayisi) - TI SPRABV2 6.

    TI: her 2 guc topu icin bir 0.1 uF, her ~10 guc topu icin bir >= 15 uF bulk.
    """
    if power_pins <= 0:
        return (0, 0)
    return (
        math.ceil(power_pins / DECOUPLING_POWER_PINS_PER_100N),
        math.ceil(power_pins / DECOUPLING_POWER_PINS_PER_BULK),
    )


# --- Kural motoruna acilan hesaplar -----------------------------------------


@dataclass(frozen=True)
class ValueRange:
    """Bir bilesen degerinin kabul araligi ve nereden geldigi."""

    low: float | None
    high: float | None
    source: str
    # Hangi E-serisinden oneri yapilmali. Tolerans kontrole gore degisir:
    # hassas bolucu E96 ister, pull-up E24 yeter, kondansator E12 stoklanir.
    series: str = "E24"

    def contains(self, value: float) -> bool:
        if self.low is not None and value < self.low:
            return False
        if self.high is not None and value > self.high:
            return False
        return True


def i2c_pullup_range(params: dict) -> ValueRange:
    """`vdd` ve `bus_capacitance_pf` beyanlarindan pull-up araligi."""
    vdd = float(params["vdd"])
    cb = float(params["bus_capacitance_pf"]) * 1e-12
    mode = str(params.get("mode", "fast"))
    return ValueRange(
        low=i2c_pullup_min_ohms(vdd, float(params.get("iol_ma", 3.0)) * 1e-3),
        high=i2c_pullup_max_ohms(cb, mode),
        source=f"NXP UM10204 ({mode}, VDD={vdd:g} V, Cb={params['bus_capacitance_pf']:g} pF)",
        # Pull-up genis bir araliktir; %5 (E24) fazlasiyla yeter.
        series="E24",
    )


def crystal_load_range(params: dict) -> ValueRange:
    """`cl_pf` beyanindan yuk kondansatoru araligi."""
    cl = float(params["cl_pf"]) * 1e-12
    low, high = crystal_load_capacitor_range_f(cl)
    return ValueRange(
        low=low,
        high=high,
        source=f"Microchip AN826 (CL={params['cl_pf']:g} pF, stray 2-5 pF)",
        # Seramik kondansator pratikte E6/E12 olarak stoklanir; E24 onermek
        # bulunamayacak bir deger onermek olur.
        series="E12",
    )


def fb_divider_range(params: dict) -> ValueRange:
    """`vfb` ve `bias_current_na` beyanlarindan alt direnc ust siniri."""
    vfb = float(params["vfb"])
    bias = float(params["bias_current_na"]) * 1e-9
    return ValueRange(
        low=None,
        high=fb_divider_max_bottom_ohms(vfb, bias),
        source=f"Richtek AN033 (Vfb={vfb:g} V, Ibias={params['bias_current_na']:g} nA, 100x)",
        # Geri besleme bolucusu cikis gerilimini DOGRUDAN belirler; %1 (E96)
        # gerekir. TIDA-010025 olcumu: gercek %1 tasarimlarda E24 onerisi
        # %3.6'ya varan sapma uretiyor - parca toleransindan buyuk.
        series="E96",
    )


# ad -> hesaplayici. Kural YAML'inda `check:` ile secilir.
CHECKS: dict[str, object] = {
    "i2c_pullup": i2c_pullup_range,
    "crystal_load": crystal_load_range,
    "fb_divider": fb_divider_range,
}
