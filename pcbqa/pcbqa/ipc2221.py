"""IPC-2221B hesaplari: akima gore iz genisligi, gerilime gore aciklik.

Neden IPC-2221, IPC-2152 degil: IPC-2152 (2009) gercek olcumlere dayanir ama
ham tablolari teliflidir ve acik bir formulu yoktur. Ayrica "IPC-2152 hep daha
gevsek" yaygin inanisi YANLIS: ciplak temel egrisi IPC-2221 dis katmanindan
DAHA muhafazakardir (3 A/1 oz/10 C: 1.37 mm vs 2.10 mm); gevseme ancak duzlem
yakinligi gibi carpanlar uygulaninca geliyor. Iki standardin hangisinin gevsek
oldugu duruma bagli oldugu icin, formulu acik olan IPC-2221B kullanilir ve
dT ile bakir agirligi PARAMETRE olarak alinir - tek bir "dogru sayi" iddiasi
edilmez.

Kaynak ve capraz dogrulama: docs/tasarim-kurallari/02-uretilebilirlik-ipc.md
"""

from __future__ import annotations

from dataclasses import dataclass

# --- IPC-2221B iz genisligi -------------------------------------------------
#   A[mil^2] = ( I / (k * dT^0.44) )^(1/0.725)
#   W[mil]   = A / (kalinlik[oz] * 1.378)
K_OUTER = 0.048  # dis katman: isiyi ~2x daha iyi atar
K_INNER = 0.024  # ic katman
_EXP_T = 0.44
_EXP_A = 0.725

# 1 oz bakir = 1.378 mil = 35 um (nominal folyo)
MIL_PER_OZ = 1.378
MM_PER_MIL = 0.0254

# Varsayilanlar: 1 oz bakir, 10 C sicaklik artisi. 10 C tuketici/endustriyel
# kartlarda yaygin kabul; 20 C daha gevsek ve yine standart icinde.
DEFAULT_COPPER_OZ = 1.0
DEFAULT_DELTA_T = 10.0


def trace_width_mm(
    current_a: float,
    delta_t_c: float = DEFAULT_DELTA_T,
    copper_oz: float = DEFAULT_COPPER_OZ,
    outer: bool = True,
) -> float:
    """Verilen akim icin IPC-2221B'nin istedigi minimum iz genisligi (mm)."""
    if current_a <= 0:
        return 0.0
    if delta_t_c <= 0:
        raise ValueError("delta_t_c pozitif olmali")
    if copper_oz <= 0:
        raise ValueError("copper_oz pozitif olmali")

    k = K_OUTER if outer else K_INNER
    area_mil2 = (current_a / (k * delta_t_c**_EXP_T)) ** (1.0 / _EXP_A)
    width_mil = area_mil2 / (copper_oz * MIL_PER_OZ)
    return width_mil * MM_PER_MIL


def current_capacity_a(
    width_mm: float,
    delta_t_c: float = DEFAULT_DELTA_T,
    copper_oz: float = DEFAULT_COPPER_OZ,
    outer: bool = True,
) -> float:
    """trace_width_mm'in tersi: bu genislikteki iz kac amper tasir."""
    if width_mm <= 0:
        return 0.0
    k = K_OUTER if outer else K_INNER
    area_mil2 = (width_mm / MM_PER_MIL) * copper_oz * MIL_PER_OZ
    return k * delta_t_c**_EXP_T * area_mil2**_EXP_A


# --- IPC-2221B Tablo 6-1: gerilime gore minimum iletken acikligi ------------
#
# B1 ic katman | B2 dis, kaplamasiz, <=3050 m | B3 dis, kaplamasiz, >3050 m
# B4 dis, polimer kaplamali | A5/A6/A7 montajli kart
#
# Not: bu tablo CLEARANCE (hava araligi) verir, CREEPAGE degil. Sebeke
# izolasyonu icin IEC 60664-1/62368-1 gerekir (bkz. dokuman 2.5) - bu modul
# onu hesaplamaz, kural motoru sebeke gerilimlerinde ayrica uyarir.
CLEARANCE_CLASSES = ("B1", "B2", "B3", "B4", "A5", "A6", "A7")

# (ust_gerilim, {sinif: mm}) - ust_gerilim dahil
_TABLE_6_1: tuple[tuple[float, dict[str, float]], ...] = (
    (15, {"B1": 0.05, "B2": 0.10, "B3": 0.10, "B4": 0.05, "A5": 0.13, "A6": 0.13, "A7": 0.13}),
    (30, {"B1": 0.05, "B2": 0.10, "B3": 0.10, "B4": 0.05, "A5": 0.13, "A6": 0.25, "A7": 0.13}),
    (50, {"B1": 0.10, "B2": 0.60, "B3": 0.60, "B4": 0.13, "A5": 0.13, "A6": 0.40, "A7": 0.13}),
    (100, {"B1": 0.10, "B2": 0.60, "B3": 1.50, "B4": 0.13, "A5": 0.13, "A6": 0.50, "A7": 0.13}),
    (150, {"B1": 0.20, "B2": 0.60, "B3": 3.20, "B4": 0.40, "A5": 0.40, "A6": 0.80, "A7": 0.40}),
    (170, {"B1": 0.20, "B2": 1.25, "B3": 3.20, "B4": 0.40, "A5": 0.40, "A6": 0.80, "A7": 0.40}),
    (250, {"B1": 0.20, "B2": 1.25, "B3": 6.40, "B4": 0.40, "A5": 0.40, "A6": 0.80, "A7": 0.40}),
    (300, {"B1": 0.20, "B2": 1.25, "B3": 12.50, "B4": 0.40, "A5": 0.40, "A6": 0.80, "A7": 0.80}),
    (500, {"B1": 0.25, "B2": 2.50, "B3": 12.50, "B4": 0.80, "A5": 0.80, "A6": 1.50, "A7": 0.80}),
)

# 500 V ustu: 301-500 satirindaki tabana, her volt icin bu kadar eklenir (mm/V)
_ABOVE_500 = {
    "B1": 0.0025,
    "B2": 0.005,
    "B3": 0.025,
    "B4": 0.00305,
    "A5": 0.00305,
    "A6": 0.00305,
    "A7": 0.00305,
}


def clearance_mm(voltage_v: float, klass: str = "B2") -> float:
    """IPC-2221B Tablo 6-1: bu gerilimde minimum iletken acikligi (mm).

    voltage_v: DC ya da AC TEPE gerilim (RMS degil).
    """
    if klass not in CLEARANCE_CLASSES:
        raise ValueError(f"gecersiz aciklik sinifi {klass!r}; {CLEARANCE_CLASSES}")
    v = abs(voltage_v)
    for upper, row in _TABLE_6_1:
        if v <= upper:
            return row[klass]
    base = _TABLE_6_1[-1][1][klass]
    return base + (v - 500.0) * _ABOVE_500[klass]


# --- Sebeke izolasyonu (IEC 62368-1) - kural motoru icin esik --------------
#
# Tam creepage tablosu dokumanda; burada yalnizca en sik gereken karar var.
# FR-4 tipik olarak malzeme grubu IIIa, kapali ekipman kirlilik derecesi 2.
MAINS_CREEPAGE_BASIC_MM = 2.5  # 250 V, PD2, Grup IIIa
MAINS_CREEPAGE_REINFORCED_MM = 5.0  # temel deger x2


@dataclass(frozen=True)
class FabClass:
    """Bir uretim sinifinin minimumlari (mm)."""

    name: str
    min_track_mm: float
    min_clearance_mm: float
    min_drill_mm: float
    min_annular_ring_mm: float
    min_edge_clearance_mm: float


# Dokuman 2.6/2.7'den. "standart" her uretici tarafindan ek ucretsiz karsilanir.
FAB_CLASSES: dict[str, FabClass] = {
    "standart": FabClass("standart", 0.15, 0.15, 0.30, 0.15, 0.30),
    "ucuz": FabClass("ucuz", 0.10, 0.10, 0.20, 0.15, 0.25),
    "gelismis": FabClass("gelismis", 0.09, 0.09, 0.15, 0.13, 0.20),
}


# --- Via akim kapasitesi ----------------------------------------------------
#
# TI SLVA959B Tablo 3-1 (IPC-2152 tabanli, 10 C artis, 1 oz kart). Bu tablo
# IPC-2221'in namlu-kesiti hesabindan yaklasik 2 KAT muhafazakar: 0.30 mm delik
# icin TI 0.84 A derken IPC-2221 1.45-1.69 A veriyor. Guc yolunda TI'in degeri
# kullanilir - bkz. docs/tasarim-kurallari/01-anahtarlamali-guc.md 1.8.
_VIA_CURRENT_TI: tuple[tuple[float, float], ...] = (
    (0.15, 0.20),
    (0.20, 0.55),
    (0.25, 0.81),
    (0.30, 0.84),
    (0.41, 1.10),
)


def via_current_a(drill_mm: float) -> float:
    """Bir via'nin tasiyabilecegi akim (A), delik capina gore.

    Tablo disindaki capraslar icin dogrusal ara deger; 0.41 mm ustu icin
    tablonun son degerinde SABITLENIR (ekstrapolasyon yapilmaz - TI tablosu
    orada bitiyor ve buyuk via'lar icin uretici olcumu bulunamadi).
    """
    if drill_mm <= 0:
        return 0.0
    first_d, first_i = _VIA_CURRENT_TI[0]
    if drill_mm <= first_d:
        return first_i * (drill_mm / first_d)
    prev_d, prev_i = first_d, first_i
    for d, i in _VIA_CURRENT_TI[1:]:
        if drill_mm <= d:
            span = d - prev_d
            t = (drill_mm - prev_d) / span if span else 0.0
            return prev_i + t * (i - prev_i)
        prev_d, prev_i = d, i
    return prev_i  # tablo disi: son deger, ekstrapolasyon yok


# --- Decoupling: lambda/40 kurali (Xilinx UG483) ---------------------------
#
# Decoupling mesafesi sabit bir sayi degil; kondansatorun MONTAJLI rezonans
# frekansinin fonksiyonu. UG483 formulu verir, tabloyu vermez.
FR4_PROPAGATION_MM_PER_NS = 152.0  # er ~ 4, 6 inc/ns


def decoupling_max_distance_mm(f_ris_hz: float) -> float:
    """lambda/40: bu rezonans frekansindaki kondansator icin max mesafe (mm)."""
    if f_ris_hz <= 0:
        raise ValueError("f_ris_hz pozitif olmali")
    wavelength_mm = FR4_PROPAGATION_MM_PER_NS * 1e9 / f_ris_hz
    return wavelength_mm / 40.0


# TI SBAA113: kaynakli tek sabit ust sinir. Bloglardaki "1-2 mm" degerinin
# birincil kaynagi yok (bkz. dokuman 3.1).
DECOUPLING_MAX_MM = 6.35

# ROHM 60AN066E pratik kurali: kendi olcum egrisinden ~4x muhafazakar, ama
# ortam sicakligi ve komsu bilesen isisi icin marj birakiyor.
ROHM_MM_PER_AMP = {1.0: 1.0, 2.0: 0.7}


def rohm_width_mm(current_a: float, copper_oz: float = 1.0) -> float:
    """ROHM'un pratik kurali: 1 oz icin 1 mm/A, 2 oz icin 0.7 mm/A."""
    per_amp = ROHM_MM_PER_AMP.get(copper_oz)
    if per_amp is None:
        # ara/ustu degerler: 1 oz degerini bakir oraniyla olcekle
        per_amp = 1.0 / copper_oz
    return max(0.0, current_a) * per_amp
