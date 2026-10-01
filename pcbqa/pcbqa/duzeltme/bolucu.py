"""Devre ailesi: YUKLU REZISTIF GERILIM BOLUCU (Kicad-u4k).

    VIN --[R_ust]--+--[R_alt]-- GND
                   |
                  OUT --> yuk (ADC girisi, referans pini...) 0..I_tepe

Neden ilk aile bu: ngspice'ta direnc ILKEL elemandir (uretici modeli
gerekmez, "ideal" isareti yoktur) ve devrenin kapali form cozumu vardir.
Boylece her benzetim sonucu bagimsiz bir el hesabiyla karsilastirilabilir.
LDO (davranissal), diyot (varsayilan model) ve MOSFET (model yok) bugun bu
guveni vermiyor (bkz. Kicad-5d6.5).

## Kapali form

    Vout = R2 (Vin - I R1) / (R1 + R2)

Vout her degiskende monotondur (Vin ve R2 ile artar, I ve R1 ile azalir),
yani en kotu durum kutunun KOSELERINDEDIR: Vin {min, max} x I {0, tepe} x
R1 {asagi, yukari} x R2 {asagi, yukari} = 16 kose.

Direnc sapmasi (EVA - extreme value analysis, muhendislik secimi):

    sapma = tolerans + TCR x dT_max + omur testi sapmasi

Uc katki da parca kutuphanesinden gelir (Yageo kalin film kaydi: TCR 100
ppm/C, 1000 saatte %1). dT_max, beyan edilen (yoksa seviye3'un varsayilan
-40/85 C) sicakliklarin 25 C'den en buyuk uzakligidir.

Guc monoton DEGILDIR: P_R1 = R1 (Vin + I R2)^2 / (R1 + R2)^2, R1 = R2'de
tepe yapar. Bu yuzden guc icin kutu ici gercek en buyuk deger kapali formla
bulunur (asagida `_guc_ust_siniri`), koseler yetmez.

## Mevcut seviye3 ile fark (olculdu)

seviye3'un `tolerans+/-` senaryosu TUM direncleri ayni yone kaydirir;
bolucude oran degismez ve en kotu durum (R1 yukari, R2 asagi) gorulmez.
Bu modul 16 capraz koseyi `seviye3(ek_senaryolar=...)` kancasiyla ekler.
"""

from __future__ import annotations

import itertools
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .. import geom
from ..devre.graf import DevreGrafi
from ..devre.kosullar import ag_anahtari
from ..dogrulama.seviye2 import direnc_guc_siniri
from ..dogrulama.seviye3 import VARSAYILAN_SICAKLIKLAR, Senaryo, nominal_degerler
from ..netlist import LibPin, Net, Netlist, NetNode, SchComponent
from ..pcb import Board, Track
from ..spice.netlist import SpiceDevresi, eleman_adi
from .tasarim import (MPN_KAYNAK_ALANI, MPN_KURAL, TOLERANS_ALANI, Tasarim, deger_metni, kutuphane_bileseni,
                      mpn_esitle, tolerans_metni)

AILE = "rezistif-bolucu"
AILE_SURUMU = 1

# Direnc paketleri, kucukten buyuge. Footprint adlari KiCad 10 standart
# kutuphanesindeki dosya adlaridir (Resistor_SMD.pretty, olculdu).
PAKETLER = ("0201", "0402", "0603", "0805", "1206", "1210", "2010", "2512")
FOOTPRINT = {
    "0201": "Resistor_SMD:R_0201_0603Metric",
    "0402": "Resistor_SMD:R_0402_1005Metric",
    "0603": "Resistor_SMD:R_0603_1608Metric",
    "0805": "Resistor_SMD:R_0805_2012Metric",
    "1206": "Resistor_SMD:R_1206_3216Metric",
    "1210": "Resistor_SMD:R_1210_3225Metric",
    "2010": "Resistor_SMD:R_2010_5025Metric",
    "2512": "Resistor_SMD:R_2512_6332Metric",
}
HEADER_FP = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"

# Benzetim / el hesabi uyum esigi. Fark yalnizca seviye3'un her dugume
# koydugu 1 Tohm sizinti direncinden gelir: goreli hata ~ R_ag / R_sizinti
# (gerilimde), gucte iki kati (karesel). Esik = max(1e-5, 10 x 2 x R_ag /
# R_sizinti) (muhendislik secimi). Ilk surum sabit 1e-5 idi: 7.5 Mohm'luk
# bolucude gucte 1.14e-5 fark cikti ve kapi gecerli bir benzetimi
# 'uyusmadi' saydi (Kicad-7cb verisi, bolucu-0070/deger-takas/olcek-x10).
UYUM_GORELI = 1e-5
UYUM_MUTLAK_V = 1e-6
IZIN_DV_YUZDE = 0.1


@dataclass(frozen=True)
class Bolucu:
    ust: str        # VIN tarafi direnc
    alt: str        # GND tarafi direnc
    giris: str
    cikis: str
    toprak: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def bolucu_bul(g: DevreGrafi) -> list[Bolucu]:
    """Gereksinimi beyan edilmis bir cikis agina bagli iki direncli bolucular.

    Kosul: cikis agi uzerinde TAM iki direnc; biri topraga, digeri gerilimi
    beyan edilmis bir raya gider. Ayni agdaki kondansator DC'de acik devredir
    ve sonucu degistirmez; baska tuketiciler `kosullar.yukler` ile girer.
    """
    out: list[Bolucu] = []
    for ag in sorted(g.aglar.values(), key=lambda a: a.ad):
        if ag.toprak:
            continue
        ger = g.kosullar.gereksinim_ag(ag.ad)
        if ger is None or (ger.min_v is None and ger.max_v is None):
            continue
        direncler = [b for b in g.bilesenler_on(ag.ad, "resistor") if not b.dnp]
        if len(direncler) != 2:
            continue
        ust = alt = None
        for b in direncler:
            uclar = g.iki_uc(b)
            if uclar is None:
                break
            diger = uclar[1] if ag_anahtari(uclar[0]) == ag_anahtari(ag.ad) else uclar[0]
            if g.toprak_mi(diger):
                alt = (b.ref, diger)
            elif g.kosullar.ray(diger) is not None:
                ust = (b.ref, diger)
        if ust and alt:
            out.append(Bolucu(ust[0], alt[0], ust[1], ag.ad, alt[1]))
    return out


# --------------------------------------------------------------------------
# Kapali form (bagimsiz el hesabi)
# --------------------------------------------------------------------------


@dataclass
class DirencBilgisi:
    ref: str
    r: float | None
    tolerans: float | None
    tcr_ppm: float | None
    yaslanma_yuzde: float | None
    guc_siniri_w: float | None
    paket: str
    eksikler: list[str] = field(default_factory=list)
    yaslanma_ek_ohm: float = 0.0
    gerilim_siniri_v: float | None = None

    def sapma(self, dt_max: float) -> float:
        # Omur sapmasinin sabit kismi (RC_L Tablo 8: +-50 mohm) goreli sapmaya
        # cevrilir: 23.7 ohm'luk direncte %0.21 - ihmal edilemez (Kicad-7cb).
        ek = self.yaslanma_ek_ohm / self.r if self.r else 0.0
        return ((self.tolerans or 0.0) + (self.tcr_ppm or 0.0) * 1e-6 * dt_max
                + (self.yaslanma_yuzde or 0.0) / 100.0 + ek)


def direnc_bilgisi(g: DevreGrafi, ref: str) -> DirencBilgisi:
    b = g.bilesenler[ref]
    pb = b.parca
    r = pb.deger.deger if pb.deger.bilinen and isinstance(pb.deger.deger, float) else None
    tol = pb.tolerans.deger if pb.tolerans.bilinen else None
    tk = pb.sicaklik_katsayisi.deger if pb.sicaklik_katsayisi.bilinen else None
    ya = pb.yaslanma.deger if pb.yaslanma.bilinen else None
    siniri = direnc_guc_siniri(g, b)
    d = DirencBilgisi(
        ref=ref, r=r, tolerans=tol,
        tcr_ppm=float(tk["ppm_c"]) if isinstance(tk, dict) and "ppm_c" in tk else None,
        yaslanma_yuzde=float(ya["sapma_yuzde"]) if isinstance(ya, dict) and "sapma_yuzde" in ya else None,
        guc_siniri_w=siniri[0] if siniri else None, paket=pb.paket,
        yaslanma_ek_ohm=float(ya.get("ek_ohm") or 0.0) if isinstance(ya, dict) else 0.0,
        gerilim_siniri_v=pb.sinir("gerilim").onerilen_max if pb.sinir("gerilim") else None)
    if r is None or r <= 0:
        d.eksikler.append(f"{ref} degeri sayi degil ({b.deger!r})")
    if tol is None:
        d.eksikler.append(f"{ref} toleransi bilinmiyor - en kotu durum hesaplanamaz")
    if siniri is None:
        d.eksikler.append(f"{ref} anma gucu bilinmiyor (paket cozulemedi, Power alani yok)")
    return d


def vout(vin: float, i: float, r1: float, r2: float) -> float:
    return r2 * (vin - i * r1) / (r1 + r2)


@dataclass
class Kose:
    ad: str
    vin: float
    i: float
    r1: float
    r2: float


@dataclass
class Analitik:
    hesaplanabilir: bool
    eksikler: list[str] = field(default_factory=list)
    bolucu: Bolucu | None = None
    vin_min: float = 0.0
    vin_nom: float = 0.0
    vin_max: float = 0.0
    yuk_nom_a: float = 0.0
    yuk_tepe_a: float = 0.0
    pencere_min: float | None = None
    pencere_max: float | None = None
    dt_max: float = 0.0
    sapma_ust: float = 0.0
    sapma_alt: float = 0.0
    r_ust: float = 0.0
    r_alt: float = 0.0
    vout_nom: float = 0.0
    vout_min: float = 0.0
    vout_max: float = 0.0
    p_ust_max: float = 0.0
    p_alt_max: float = 0.0
    p_ust_kose: float = 0.0
    p_alt_kose: float = 0.0
    p_ust_siniri: float | None = None
    p_alt_siniri: float | None = None
    # Uclar arasi en kotu gerilim ve azami calisma gerilimi (Kicad-7cb)
    v_ust_max: float = 0.0
    v_alt_max: float = 0.0
    v_ust_siniri: float | None = None
    v_alt_siniri: float | None = None
    koseler: list[Kose] = field(default_factory=list)

    @property
    def marj_alt(self) -> float:
        return self.vout_min - self.pencere_min if self.pencere_min is not None else float("inf")

    @property
    def marj_ust(self) -> float:
        return self.pencere_max - self.vout_max if self.pencere_max is not None else float("inf")

    @property
    def pencere_icinde(self) -> bool:
        return self.marj_alt >= 0 and self.marj_ust >= 0

    @property
    def guc_orani(self) -> float:
        """En yuklu direncin (en kotu guc / anma) orani."""
        oranlar = [p / s for p, s in ((self.p_ust_max, self.p_ust_siniri),
                                      (self.p_alt_max, self.p_alt_siniri)) if s]
        return max(oranlar) if oranlar else float("inf")

    @property
    def gerilim_orani(self) -> float:
        """En zorlanan direncin (en kotu uc gerilimi / azami calisma gerilimi)."""
        oranlar = [v / s for v, s in ((self.v_ust_max, self.v_ust_siniri),
                                      (self.v_alt_max, self.v_alt_siniri)) if s]
        return max(oranlar) if oranlar else float("inf")

    @property
    def gecer(self) -> bool:
        return (self.hesaplanabilir and self.pencere_icinde and self.guc_orani <= 1.0
                and self.gerilim_orani <= 1.0)

    def as_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in asdict(self).items() if k not in ("koseler", "bolucu")}
        d.update(bolucu=self.bolucu.as_dict() if self.bolucu else None,
                 marj_alt=_sonlu(self.marj_alt), marj_ust=_sonlu(self.marj_ust),
                 guc_orani=_sonlu(self.guc_orani), gerilim_orani=_sonlu(self.gerilim_orani),
                 gecer=self.gecer)
        return d


def _sonlu(x: float) -> float | None:
    return None if x in (float("inf"), float("-inf")) else x


def _p_r1(vin, i, r1, r2):
    return r1 * (vin + i * r2) ** 2 / (r1 + r2) ** 2


def _p_r2(vin, i, r1, r2):
    return (vin - i * r1) ** 2 * r2 / (r1 + r2) ** 2


def _guc_ust_siniri(vins, akimlar, r1s, r2s) -> tuple[float, float]:
    """Kutu ici gercek en buyuk guc (kapali form, varsayimsiz).

    P_R1 = R1 (Vin + I R2)^2 / (R1 + R2)^2
      Vin ve I ile artar (Vin + I R2 > 0). R2 boyunca (Vin + I R2)/(R1 + R2)
      monotondur ama YONU (I R1 - Vin)'in isaretine bagli -> R2 iki uc.
      R1 boyunca R1/(R1 + R2)^2, R1 = R2'de tepe yapar -> uclar + kirpilmis R2.
    P_R2 = R2 (Vin - I R1)^2 / (R1 + R2)^2
      (Vin - I R1)^2 Vin'de ve I'da dis bukey -> uclar. (Vin - I R1)/(R1 + R2)
      R1'de monoton azalan, karesi -> uclar. R2'de R1'de tepe -> uclar +
      kirpilmis R1.

    Ilk surum "Vin - I R1 > 0" varsayiyordu (P_R1 R2 ile azalir, P_R2 I ile
    azalir). Yuk akimi x R_ust > Vin olunca (empedans x100 hatasi) Vout
    negatife iner ve varsayim cokar: benzetim ile el hesabi 53 kayitta
    uyusmadi, uyum kapisi yakaladi (Kicad-u4k, olculdu).
    """
    def kirp(x, aralik):
        return min(max(x, aralik[0]), aralik[1])

    p1 = max(_p_r1(max(vins), max(akimlar), r1, r2)
             for r2 in r2s for r1 in (*r1s, kirp(r2, r1s)))
    p2 = max(_p_r2(v, i, r1, r2)
             for v in vins for i in akimlar for r1 in r1s for r2 in (*r2s, kirp(r1, r2s)))
    return p1, p2


def analitik(g: DevreGrafi, b: Bolucu) -> Analitik:
    a = Analitik(hesaplanabilir=False, bolucu=b)
    ust, alt = direnc_bilgisi(g, b.ust), direnc_bilgisi(g, b.alt)
    a.eksikler = ust.eksikler + alt.eksikler
    ray = g.kosullar.ray(b.giris)
    if ray is None:
        a.eksikler.append(f"{b.giris} rayi beyan edilmedi")
    elif not g.kosullar.kaynak_mi(b.giris):
        a.eksikler.append(f"{b.giris} benzetimde kaynak degil (kosullar.kaynaklar)")
    ger = g.kosullar.gereksinim_ag(b.cikis)
    if a.eksikler or ray is None or ger is None:
        return a
    yukler = g.kosullar.yukler_on(b.cikis)
    a.yuk_nom_a = sum(y.akim_a for y in yukler)
    a.yuk_tepe_a = sum(y.tepe for y in yukler)
    a.vin_nom, a.vin_min, a.vin_max = ray.nom, ray.en_dusuk, ray.en_yuksek
    a.pencere_min, a.pencere_max = ger.min_v, ger.max_v
    ortam = g.kosullar.ortam_c if g.kosullar.ortam_c is not None else 25.0
    sicakliklar = [float(t) for t in g.kosullar.analiz.get("sicakliklar", VARSAYILAN_SICAKLIKLAR)]
    a.dt_max = max(abs(t - 25.0) for t in [ortam, *sicakliklar])
    a.sapma_ust, a.sapma_alt = ust.sapma(a.dt_max), alt.sapma(a.dt_max)
    a.r_ust, a.r_alt = ust.r, alt.r
    a.p_ust_siniri, a.p_alt_siniri = ust.guc_siniri_w, alt.guc_siniri_w
    a.v_ust_siniri, a.v_alt_siniri = ust.gerilim_siniri_v, alt.gerilim_siniri_v

    r1s = (ust.r * (1 - a.sapma_ust), ust.r * (1 + a.sapma_ust))
    r2s = (alt.r * (1 - a.sapma_alt), alt.r * (1 + a.sapma_alt))
    for vin, i, r1, r2 in itertools.product((a.vin_min, a.vin_max), (0.0, a.yuk_tepe_a), r1s, r2s):
        ad = (f"capraz-kose:vin{'-' if vin == a.vin_min else '+'}"
              f":yuk{'0' if i == 0 else '+'}:r1{'-' if r1 == r1s[0] else '+'}:r2{'-' if r2 == r2s[0] else '+'}")
        a.koseler.append(Kose(ad, vin, i, r1, r2))
    vs = [vout(k.vin, k.i, k.r1, k.r2) for k in a.koseler]
    a.vout_min, a.vout_max = min(vs), max(vs)
    a.vout_nom = vout(a.vin_nom, a.yuk_nom_a, ust.r, alt.r)
    a.p_ust_kose = max(_p_r1(k.vin, k.i, k.r1, k.r2) for k in a.koseler)
    a.p_alt_kose = max(_p_r2(k.vin, k.i, k.r1, k.r2) for k in a.koseler)
    a.p_ust_max, a.p_alt_max = _guc_ust_siniri((a.vin_min, a.vin_max), (0.0, a.yuk_tepe_a), r1s, r2s)
    # Gerilim de her degiskende monoton (Vout gibi) -> koseler yeter
    a.v_ust_max = max(abs(k.vin - vout(k.vin, k.i, k.r1, k.r2)) for k in a.koseler)
    a.v_alt_max = max(abs(vout(k.vin, k.i, k.r1, k.r2)) for k in a.koseler)
    a.hesaplanabilir = True
    return a


def ek_senaryo_uretici(b: Bolucu, a: Analitik):
    """seviye3 kancasi: 16 capraz koseyi benzetime ekler."""

    def uret(g: DevreGrafi, d: SpiceDevresi) -> tuple[list[Senaryo], list[str]]:
        notlar: list[str] = []
        if not a.hesaplanabilir:
            return [], ["capraz kose eklenmedi: " + "; ".join(a.eksikler)]
        kaynak = next((ad for ad, (ag, *_r) in d.kaynaklar.items()
                       if ag_anahtari(ag) == ag_anahtari(b.giris)), None)
        yukler = [ad for ad, (ag, _i) in d.yukler.items() if ag_anahtari(ag) == ag_anahtari(b.cikis)]
        r1, r2 = eleman_adi("R", b.ust), eleman_adi("R", b.alt)
        if kaynak is None or r1 not in d.pasifler or r2 not in d.pasifler:
            return [], [f"capraz kose eklenmedi: kaynak/direnc SPICE'ta yok ({kaynak}, {r1}, {r2})"]
        taban = nominal_degerler(d)
        ortam = g.kosullar.ortam_c if g.kosullar.ortam_c is not None else 25.0
        tepe_toplam = sum(d.yukler[y][1] for y in yukler) or 0.0
        out = []
        for k in a.koseler:
            deg = dict(taban)
            deg.update({kaynak: k.vin, r1: k.r1, r2: k.r2})
            for y in yukler:
                # Toplam tepe akim yukler arasinda nominal oranla paylasilir.
                pay = d.yukler[y][1] / tepe_toplam if tepe_toplam > 0 else 1.0 / len(yukler)
                deg[y] = k.i * pay
            out.append(Senaryo(k.ad, "capraz-kose", ortam, deg,
                               "EVA: tolerans + TCR x dT + omur sapmasi, ters yonlerde"))
        notlar.append(f"{len(out)} capraz kose eklendi (EVA, muhendislik secimi; sapma "
                      f"{b.ust} %{a.sapma_ust * 100:.2f}, {b.alt} %{a.sapma_alt * 100:.2f})")
        return out, notlar

    return uret


def uyum(a: Analitik, ag_ozeti: dict[str, Any], yuklenme: dict[str, Any]) -> dict[str, Any]:
    """Benzetim ile kapali form ayni sonucu veriyor mu? (bagimsiz dogrulama)"""
    o = ag_ozeti.get(a.bolucu.cikis) if a.bolucu else None
    if not a.hesaplanabilir or o is None:
        return {"karsilastirildi": False}
    p1 =(yuklenme.get(a.bolucu.ust) or {}).get("guc_w")
    p2 = (yuklenme.get(a.bolucu.alt) or {}).get("guc_w")
    sonuc = {
        "karsilastirildi": True,
        "vout_nom": [a.vout_nom, o["nominal_v"]],
        "vout_min": [a.vout_min, o["min_v"]],
        "vout_max": [a.vout_max, o["max_v"]],
        "p_ust": [a.p_ust_kose, p1, a.p_ust_max],
        "p_alt": [a.p_alt_kose, p2, a.p_alt_max],
    }
    # ag_ozeti 6 haneye yuvarlanir; mutlak esik (1 uV) o yuvarlamayi kapsar.
    from ..spice.netlist import SIZINTI_OHM

    goreli = max(UYUM_GORELI, 10 * 2 * (a.r_ust * (1 + a.sapma_ust) + a.r_alt * (1 + a.sapma_alt)) / SIZINTI_OHM)
    sonuc["goreli_esik"] = goreli
    v_ok = all(abs(x - y) <= UYUM_MUTLAK_V + goreli * max(abs(x), abs(y))
               for x, y in (sonuc["vout_nom"], sonuc["vout_min"], sonuc["vout_max"]))

    def guc_ok(kose, sim, ust):
        # Benzetim koseleri ve seviye3'un kendi senaryolarini gorur: sonuc
        # kose en buyugunden kucuk, kutu ici gercek en buyukten buyuk olamaz.
        if sim is None:
            return False
        return kose * (1 - goreli) - 1e-12 <= sim <= ust * (1 + goreli) + 1e-12

    sonuc["uyumlu"] = bool(v_ok and guc_ok(a.p_ust_kose, p1, a.p_ust_max)
                           and guc_ok(a.p_alt_kose, p2, a.p_alt_max))
    return sonuc


# --------------------------------------------------------------------------
# Referans tasarim kurulumu (bellekte netlist + gercek footprint'li kart)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BolucuParametre:
    kimlik: str
    vin_nom: float
    vin_tol: float          # oran (0.05 = +-%5)
    vout_hedef: float
    pencere: float          # yari genislik orani
    yuk_nom_a: float
    yuk_tepe_a: float
    ortam_c: float
    sicakliklar: tuple[float, ...]
    r_ust: float
    r_alt: float
    tolerans: float
    paket_ust: str
    paket_alt: str
    aralik_mm: float        # iki direncin merkezleri arasi (kart yogunlugu)
    # True: direnclere uretici kuralindan MPN yazilir (Yageo RC_L, Kicad-7cb)
    mpn: bool = False

    def kosullar(self) -> dict[str, Any]:
        return {
            "version": 1,
            "ortam_c": self.ortam_c,
            "raylar": {"VIN": {"nom": self.vin_nom, "min": round(self.vin_nom * (1 - self.vin_tol), 9),
                               "max": round(self.vin_nom * (1 + self.vin_tol), 9)}},
            "kaynaklar": ["VIN"],
            "yukler": [{"ag": "OUT", "akim_a": self.yuk_nom_a, "tepe_a": self.yuk_tepe_a}],
            "gereksinimler": [{"ag": "OUT", "min_v": round(self.vout_hedef * (1 - self.pencere), 9),
                               "max_v": round(self.vout_hedef * (1 + self.pencere), 9)}],
            "analiz": {"monte_carlo": 0, "sicakliklar": list(self.sicakliklar)},
            # Iz uzerindeki gerilim dusumu rayin %0.1'ini gecmesin (muhendislik
            # secimi: en dar cikis penceresi %6, dusum onun 1/60'i). Kicad-ecd.
            "pcb": {"izin_dV_yuzde": IZIN_DV_YUZDE},
        }

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["sicakliklar"] = list(self.sicakliklar)
        return d


_R_PINLERI = [LibPin("1", "~", "passive"), LibPin("2", "~", "passive")]
_J_PINLERI = [LibPin("1", "Pin_1", "passive"), LibPin("2", "Pin_2", "passive")]


# --------------------------------------------------------------------------
# Kart yerlesimi ve yonlendirme - bellekteki tasarim ile GERCEK KiCad projesi
# AYNI geometriyi kullanir (Kicad-ecd). Boylece bellekte uretilen egitim
# etiketi ile gercek projedeki kicad-cli DRC sonucu karsilastirilabilir.
#
#   y = RAY_UST_Y   J1.1 --VIN-- [R1] --OUT--+-------- J2.1
#                                            |
#                                           [R2]  (dikey, OUT padi ustte)
#                                            |
#   y = RAY_ALT_Y   J1.2 --GND---------------+-------- J2.2
#
# Iki ray header pin adimi kadar aralikli (2.54 mm); R1 ust rayin uzerinde
# yatay, R2 raylar arasinda dikey. Yonlendirme pad konumlarindan HER SEFERINDE
# yeniden hesaplanir: footprint degisen adayda izler yeni pad'lere gider.
# Genel amacli bir autorouter DEGILDIR (kapsam disi); yalnizca bu topoloji.
# --------------------------------------------------------------------------

RAY_UST_Y = 5.0
HEADER_ADIM = 2.54
RAY_ALT_Y = RAY_UST_Y + HEADER_ADIM
X_J1 = 3.0
# R1 merkezi: J1 courtyard'i (+-1.8 mm) ile 2010'a kadar R1 courtyard'i
# arasinda bosluk kalsin (KiCad Resistor_SMD courtyard'lari).
X_R1 = 9.0
J2_ARALIK = 6.0      # R2 merkezinden J2'ye; header courtyard'i +-1.8 mm
KART_KENAR_PAY = 3.0
KART_YUKSEKLIK = 12.0
# Iz genisligi: KiCad varsayilan ag sinifi 0.2 mm; 0.25 mm muhendislik
# secimi. Akim kapasitesi her adayda pcb_akim.iz_analizi ile olculur.
IZ_MM = 0.25
BAKIR = "F.Cu"


def yerlesim(aralik_mm: float) -> dict[str, tuple[float, float, float]]:
    """Ref -> (x, y, aci). `aralik_mm` R1 ile R2 merkezleri arasi (kart yogunlugu).

    R2 270 derece: KiCad donme konvansiyonunda (pcb._rotate) pad 1 USTTE
    kalir; pad 1 OUT'a bagli oldugundan OUT kolu GND padinin ustunden gecmez."""
    x_r2 = X_R1 + aralik_mm
    return {"J1": (X_J1, RAY_UST_Y, 0.0), "R1": (X_R1, RAY_UST_Y, 0.0),
            "R2": (x_r2, (RAY_UST_Y + RAY_ALT_Y) / 2, 270.0), "J2": (x_r2 + J2_ARALIK, RAY_UST_Y, 0.0)}


def kart_siniri(aralik_mm: float) -> tuple[float, float, float, float]:
    return (0.0, 0.0, X_R1 + aralik_mm + J2_ARALIK + KART_KENAR_PAY, KART_YUKSEKLIK)


class YonlendirmeHatasi(RuntimeError):
    """Kart bu yonlendiricinin varsaydigi topolojide degil (sessizce yanlis iz
    cizmek yerine durur)."""


@dataclass(frozen=True)
class Roller:
    """Bolucu kartindaki referanslar ve ag adlari."""
    giris_header: str = "J1"
    ust: str = "R1"
    alt: str = "R2"
    cikis_header: str = "J2"
    giris: str = "VIN"
    cikis: str = "OUT"
    toprak: str = "GND"

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _pad_agda(board: Board, ref: str, ag: str):
    c = board.by_ref(ref)
    if c is None:
        raise YonlendirmeHatasi(f"kartta {ref} yok")
    pads = [p for p in c.pads if ag_anahtari(p.net) == ag_anahtari(ag)]
    if len(pads) != 1:
        raise YonlendirmeHatasi(f"{ref}: {ag} aginda {len(pads)} pad (1 bekleniyordu)")
    return pads[0]


def rayli_yonlendir(board: Board, roller: Roller = Roller(), genislik_mm: float = IZ_MM) -> list[Track]:
    """Pad konumlarindan iki rayli yonlendirme (yukaridaki cizim)."""
    j1v, j1g = _pad_agda(board, roller.giris_header, roller.giris), _pad_agda(board, roller.giris_header, roller.toprak)
    r1v, r1o = _pad_agda(board, roller.ust, roller.giris), _pad_agda(board, roller.ust, roller.cikis)
    r2o, r2g = _pad_agda(board, roller.alt, roller.cikis), _pad_agda(board, roller.alt, roller.toprak)
    j2o, j2g = _pad_agda(board, roller.cikis_header, roller.cikis), _pad_agda(board, roller.cikis_header, roller.toprak)
    y_ust, y_alt = j1v.y, j1g.y
    eps = 1e-6
    if not (abs(r1v.y - y_ust) < eps and abs(r1o.y - y_ust) < eps and abs(j2o.y - y_ust) < eps
            and abs(j2g.y - y_alt) < eps and abs(r2o.x - r2g.x) < eps and r2o.y < r2g.y):
        raise YonlendirmeHatasi("yerlesim rayli topolojide degil (R1 ust rayda, R2 dikey ve OUT padi ustte olmali)")
    x2 = r2o.x
    yollar = [
        (j1v.net, [(j1v.x, y_ust), (r1v.x, y_ust)]),
        (r1o.net, [(r1o.x, y_ust), (x2, y_ust), (j2o.x, y_ust)]),
        (r1o.net, [(x2, y_ust), (x2, r2o.y)]),
        (j1g.net, [(j1g.x, y_alt), (x2, y_alt), (j2g.x, y_alt)]),
        (j1g.net, [(x2, y_alt), (x2, r2g.y)]),
    ]
    out: list[Track] = []
    for ag, noktalar in yollar:
        for (xa, ya), (xb, yb) in zip(noktalar, noktalar[1:]):
            if abs(xa - xb) > eps or abs(ya - yb) > eps:
                out.append(Track(ag, genislik_mm, BAKIR, round(xa, 6), round(ya, 6), round(xb, 6), round(yb, 6)))
    return out


def tasarim_kur(p: BolucuParametre, kart: bool = True) -> Tasarim:
    """Parametrelerden netlist + YONLENDIRILMIS kart (gercek projeyle ayni geometri).

    `kart=False`: yalnizca netlist (KiCad footprint kutuphanesi gerekmez;
    birim testleri ve el hesabi icin). PCB kontrolleri o zaman denetlenemez."""
    n = Netlist(path=Path(f"{p.kimlik}.xml"))
    tol = tolerans_metni(p.tolerans)
    parcalar = [
        ("J1", "GIRIS", "Connector_Generic", "Conn_01x02", HEADER_FP, {"1": "VIN", "2": "GND"}, {}),
        ("R1", deger_metni(p.r_ust), "Device", "R", FOOTPRINT[p.paket_ust], {"1": "VIN", "2": "OUT"},
         {TOLERANS_ALANI: tol}),
        ("R2", deger_metni(p.r_alt), "Device", "R", FOOTPRINT[p.paket_alt], {"1": "OUT", "2": "GND"},
         {TOLERANS_ALANI: tol}),
        ("J2", "CIKIS", "Connector_Generic", "Conn_01x02", HEADER_FP, {"1": "OUT", "2": "GND"}, {}),
    ]
    aglar: dict[str, Net] = {}
    for ref, deger, lib, part, fp, baglar, alanlar in parcalar:
        n.components[ref] = SchComponent(ref=ref, value=deger, footprint=fp, libpart=part, lib=lib,
                                         fields=dict(alanlar))
        n.libparts.setdefault((lib, part), _R_PINLERI if part == "R" else _J_PINLERI)
        for pin, ag in baglar.items():
            ad = "~" if part == "R" else f"Pin_{pin}"
            aglar.setdefault(ag, Net(code=str(len(aglar) + 1), name=ag)).nodes.append(
                NetNode(ref, pin, f"{ad}_{pin}" if part != "R" else "", "passive"))
    n.nets = list(aglar.values())
    if p.mpn:
        for ref in ("R1", "R2"):
            n.components[ref].fields[MPN_KAYNAK_ALANI] = MPN_KURAL
            mpn_esitle(n.components[ref])
    if not kart:
        return Tasarim(n, None, p.kosullar(), proje=p.kimlik)

    konum = yerlesim(p.aralik_mm)
    comps = []
    for ref, deger, _lib, _part, fp, baglar, _alanlar in parcalar:
        c = kutuphane_bileseni(fp)
        c.ref, c.value = ref, deger
        for pad in c.pads:
            pad.net = baglar.get(pad.number, "")
        x, y, aci = konum[ref]
        c.place(x, y, aci)
        comps.append(c)
    board = Board(path=Path(f"{p.kimlik}.kicad_pcb"), components=comps, outline=kart_siniri(p.aralik_mm))
    board.tracks = rayli_yonlendir(board)
    return Tasarim(n, board, p.kosullar(), proje=p.kimlik, yonlendirici=rayli_yonlendir)


def bosluklar(board: Board | None, refler: list[str]) -> dict[str, float | None]:
    """Her direncin courtyard sinir kutusunun en yakin komsuya eksen boslugu
    (mm; negatif = cakisma). Kart geometrisidir, benzetim degil."""
    if board is None:
        return {r: None for r in refler}
    kutular = {c.ref: geom.bbox(c.courtyard_poly) for c in board.components if c.courtyard_poly}
    out: dict[str, float | None] = {}
    for r in refler:
        a = kutular.get(r)
        if a is None:
            out[r] = None
            continue
        en = None
        for ref, b in kutular.items():
            if ref == r:
                continue
            dx = max(b[0] - a[2], a[0] - b[2])
            dy = max(b[1] - a[3], a[1] - b[3])
            bosluk = max(dx, dy)
            en = bosluk if en is None else min(en, bosluk)
        out[r] = en
    return out


def courtyard_cakismalari(board: Board | None, refler: set[str] | None = None) -> list[tuple[str, str]]:
    """Geometrik on kontrol (benzetim degil): ayni yuzde cakisan courtyard'lar."""
    if board is None:
        return []
    comps = [c for c in board.components if c.courtyard_poly]
    out = []
    for i, a in enumerate(comps):
        for b in comps[i + 1:]:
            if a.layer != b.layer:
                continue
            if refler is not None and not ({a.ref, b.ref} & refler):
                continue
            if geom.overlap(a.courtyard_poly, b.courtyard_poly):
                out.append((a.ref, b.ref))
    return out


def kol_akimlari(g: DevreGrafi, b: Bolucu, a: Analitik) -> tuple[dict[str, Any], list[str]]:
    """En kotu kose kol akimlari -> `pcb_akim.iz_analizi` akim noktalari.

    `pcb_akim.akim_dagilimi` pasif kol akimini bilmez (yalnizca yuk, regulator,
    guc girisi). Bolucude R1 akimi kartin ana akimidir; en buyuk R1 akimini
    veren kose secilir ve ayni kosede Kirchhoff saglanir: I1 = I2 + I_yuk.
    DC bolucu oldugu icin tepe = surekli (darbe beyan edilmez)."""
    from ..pcb_akim import AgAkimlari, AkimNoktasi

    if not a.hesaplanabilir or not a.koseler:
        return {}, ["el hesabi yok - kol akimi bilinmiyor"]

    def i1_of(k: Kose) -> float:
        return (k.vin - vout(k.vin, k.i, k.r1, k.r2)) / k.r1

    k = max(a.koseler, key=lambda k: abs(i1_of(k)))
    v = vout(k.vin, k.i, k.r1, k.r2)
    i1, i2, iy = i1_of(k), v / k.r2, k.i

    def pin_on(ref: str, ag: str) -> str | None:
        bd = g.bilesenler.get(ref)
        if bd is None:
            return None
        return next((p.tam for p in bd.pinler.values() if ag_anahtari(p.ag) == ag_anahtari(ag)), None)

    def konnektorler(ag: str) -> list[str]:
        d = g.ag(ag)
        return sorted({p.ref for p in d.pinler if g.bilesenler[p.ref].tur == "connector"}) if d else []

    notlar: list[str] = []
    kaynak = konnektorler(b.giris)
    if len(kaynak) != 1:
        return {}, [f"{b.giris} aginda {len(kaynak)} konnektor (1 bekleniyordu) - kaynak pini belirsiz"]
    yuk = [r for r in konnektorler(b.cikis) if r not in kaynak]
    if iy > 0 and len(yuk) != 1:
        return {}, [f"{b.cikis} yuku icin {len(yuk)} konnektor (1 bekleniyordu)"]
    pinler = {
        "kaynak": pin_on(kaynak[0], b.giris), "kaynak_t": pin_on(kaynak[0], b.toprak),
        "r1_g": pin_on(b.ust, b.giris), "r1_c": pin_on(b.ust, b.cikis),
        "r2_c": pin_on(b.alt, b.cikis), "r2_t": pin_on(b.alt, b.toprak),
    }
    if yuk:
        pinler.update(yuk=pin_on(yuk[0], b.cikis), yuk_t=pin_on(yuk[0], b.toprak))
    eksik = [ad for ad, p in pinler.items() if p is None]
    if eksik:
        return {}, [f"pin bulunamadi: {', '.join(eksik)}"]

    def ag_adi(ad: str) -> str:
        d = g.ag(ad)
        return d.ad if d else ad

    def nokta(pin: str, akim: float) -> AkimNoktasi:
        return AkimNoktasi(pin, akim, akim)

    out = {
        ag_adi(b.giris): AgAkimlari(ag_adi(b.giris), [nokta(pinler["kaynak"], i1), nokta(pinler["r1_g"], -i1)]),
        ag_adi(b.cikis): AgAkimlari(ag_adi(b.cikis), [nokta(pinler["r1_c"], i1), nokta(pinler["r2_c"], -i2)]),
        ag_adi(b.toprak): AgAkimlari(ag_adi(b.toprak), [nokta(pinler["r2_t"], i2),
                                                         nokta(pinler["kaynak_t"], -(i2 + iy))]),
    }
    if yuk:
        out[ag_adi(b.cikis)].noktalar.append(nokta(pinler["yuk"], -iy))
        out[ag_adi(b.toprak)].noktalar.append(nokta(pinler["yuk_t"], iy))
    notlar.append(f"kol akimlari kose {k.ad}: I_R1 {i1 * 1e3:.4g} mA, I_R2 {i2 * 1e3:.4g} mA, "
                  f"I_yuk {iy * 1e3:.4g} mA")
    return out, notlar


def roller_bul(g: DevreGrafi, b: Bolucu) -> Roller | None:
    """Bolucunun giris/cikis konnektorlerini bulur (rayli yonlendirici icin).
    Topoloji uymazsa None: o kartin izleri bu modulle yeniden uretilemez."""
    def konnektorler(ag: str) -> list[str]:
        d = g.ag(ag)
        return sorted({p.ref for p in d.pinler if g.bilesenler[p.ref].tur == "connector"}) if d else []

    giris = konnektorler(b.giris)
    cikis = [r for r in konnektorler(b.cikis) if r not in giris]
    if len(giris) != 1 or len(cikis) != 1:
        return None
    return Roller(giris[0], b.ust, b.alt, cikis[0], b.giris, b.cikis, b.toprak)


def yonlendirici_kur(t: Tasarim, b: Bolucu) -> bool:
    """Kart bu modulun rayli topolojisindeyse `t.yonlendirici`yi kurar.

    Dogrulama: mevcut izler, rayli yonlendiricinin AYNI kartta uretecegi
    izlerle birebir ayniysa (kart bu modulle yonlendirilmis). Degilse kurulmaz:
    kullanicinin kendi yonlendirmesi bu modulle EZILMEZ."""
    if t.board is None or not t.board.tracks:
        return False
    roller = roller_bul(t.graf(), b)
    if roller is None:
        return False
    try:
        izler = rayli_yonlendir(t.board, roller)
    except YonlendirmeHatasi:
        return False

    def anahtar(ts):
        return sorted((ag_anahtari(x.net), x.layer, round(x.width, 4), round(x.x1, 4), round(x.y1, 4),
                       round(x.x2, 4), round(x.y2, 4)) for x in ts)
    if anahtar(izler) != anahtar(t.board.tracks):
        return False
    genislik = t.board.tracks[0].width
    t.yonlendirici = lambda kart: rayli_yonlendir(kart, roller, genislik)
    return True
