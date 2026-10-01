"""Referans tasarim ornekleme politikalari (Kicad-7cb).

Ilk deneyde (Kicad-u4k) referans "guc orani <= %50 olan EN KUCUK paketi"
secerek kuruldu. Bolucu akimlari cogunlukla mA altinda oldugu icin 80
referansin 62'si 0402'de toplandi ve `paket-kucuk` hatasi yalnizca 6 varyantta
gorulebildi. Dengesizlik mevcut ornekleri COGALTARAK giderilmez (ayni temel
tasarim yalnizca kimlik degistirmis olurdu); farkli temel tasarim ve calisma
kosullari URETILIR.

Politikalar (yapilandirilabilir, kayda aynen yazilir):

  dogal    eski davranis: kosullar ornekle, guc orani <= REF_GUC_ORANI olan en
           kucuk paket. Paket dagilimi fizikten kendiliginden cikar.
  dengeli  katmanli ornekleme: her referansa ONCE bir paket katmani atanir
           (kota: `paket_hedefi`), sonra o paketi gerektiren kosullar uretilir.
           Iki kip:
             guc-gudumlu  paket gucun gerektirdigi en kucuk pakettir; daha
                          kucuk hedef paketin (paket-kucuk hatasinin hedefi)
                          guc orani secilen SINIR BANDINA dusurulur
             asiri-boy    paket gerekenden buyuktur (bir kucugu de yeterli).
                          Boylece "buyuk paket = yuksek guc" korelasyonu kirilir.
           Tolerans ve yuk paketten BAGIMSIZ ornekleniyor (paketle birlikte
           degismesin). Gerilim siniri ornekleri icin Vin 36 / 48 V eklendi.

Sinir bantlari (guc orani = en kotu guc / sicaklikla azaltilmis anma gucu;
1.0 kalis siniri; esikler MUHENDISLIK SECIMIDIR, +-%10):

  alt    oran < 0.9           sinirin altinda (hata zararsiz olabilir)
  yakin  0.9 <= oran <= 1.1   sinira yakin (iki tarafta da ornek)
  ust    oran > 1.1           sinirin ustunde

Bant hedefi her zaman tutturulamaz: referansin kendisi temiz olmali (guc
orani <= 0.5) ve hedef paketin anma gucu ile oran sinirlidir (or. 0805 ->
0603: 0.125/0.1 W, en fazla 0.5 x 1.25 = 0.625 -> 'ust' imkansiz). Tutmayan
plan satiri en yakin ulasilabilir banda duser ve kayda YAZILIR.
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from .. import eseri
from .bolucu import PAKETLER, Bolucu, BolucuParametre, analitik, courtyard_cakismalari, tasarim_kur
from .tasarim import Tasarim

VIN = (3.3, 5.0, 9.0, 12.0, 15.0, 24.0)
VIN_GENIS = VIN + (36.0, 48.0)
VIN_TOL = (0.01, 0.02, 0.05)
VOUT = (0.6, 0.9, 1.0, 1.2, 1.65, 1.8, 2.0, 2.5, 3.0, 3.3, 4.0, 5.0)
PENCERE_EK = (0.06, 0.08, 0.10)
YUK_TEPE = (0.0, 1e-6, 1e-5, 1e-4, 5e-4)
ORTAM = (25.0, 40.0, 60.0, 85.0)
SICAKLIK = ((-40.0, 85.0), (0.0, 70.0))
# R1-R2 merkez araligi (mm). Kicad-ecd yerlesiminde (R1 yatay, R2 dikey)
# 0603 ciftinin courtyard'lari 2.21 mm'de degir; 1206 icin 3.41 mm.
ARALIK = (2.4, 2.8, 3.2, 4.0, 4.8)
AKIM_KATI = (20.0, 50.0, 100.0, 200.0)
SABIT_AKIM = (20e-6, 100e-6, 500e-6, 2e-3)
REF_PAKETLER = ("0402", "0603", "0805", "1206")
REF_GUC_ORANI = 0.5   # seviye2 uyari esigi: referans uyarisiz olmali
BANTLAR = {"alt": (0.0, 0.9), "yakin": (0.9, 1.1), "ust": (1.1, math.inf)}
B = Bolucu("R1", "R2", "VIN", "OUT", "GND")


def bant(oran: float | None) -> str:
    """Guc (ya da gerilim) oraninin siniri gore bandi; sinir bilinmiyorsa 'bilinmiyor'."""
    if oran is None or not math.isfinite(oran):
        return "bilinmiyor"
    if oran < BANTLAR["yakin"][0]:
        return "alt"
    if oran <= BANTLAR["yakin"][1]:
        return "yakin"
    return "ust"


@dataclass(frozen=True)
class Politika:
    ad: str = "dogal"
    paket_hedefi: tuple[tuple[str, float], ...] = (("0402", 0.25), ("0603", 0.25), ("0805", 0.25), ("1206", 0.25))
    asiri_boy_orani: float = 0.3
    bantlar: tuple[str, ...] = ("alt", "yakin", "ust")
    vin: tuple[float, ...] = VIN
    toleranslar: tuple[float, ...] = (0.01,)
    mpn: bool = True

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["paket_hedefi"] = dict(self.paket_hedefi)
        d["bant_esikleri"] = {k: list(v) for k, v in BANTLAR.items()}
        return d


POLITIKALAR = {
    "dogal": Politika("dogal"),
    "dengeli": Politika("dengeli", vin=VIN_GENIS, toleranslar=(0.01, 0.005)),
}


@dataclass
class PlanSatiri:
    paket: str
    kip: str = "guc-gudumlu"     # | asiri-boy
    bant: str = "alt"

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def plan(n: int, tohum: int, pol: Politika) -> list[PlanSatiri | None]:
    """Referans indeksi -> katman (dengeli). Kotalar tam sayiya yuvarlanir,
    artan en buyuk kesirlilere dagitilir; sira tohumla karistirilir."""
    if pol.ad == "dogal":
        return [None] * n
    agirlik = dict(pol.paket_hedefi)
    toplam = sum(agirlik.values())
    ham = {p: n * w / toplam for p, w in agirlik.items()}
    say = {p: int(v) for p, v in ham.items()}
    for p in sorted(ham, key=lambda p: -(ham[p] - say[p]))[: n - sum(say.values())]:
        say[p] += 1
    rng = random.Random(tohum * 7919 + 11)
    satirlar: list[PlanSatiri] = []
    for p in sorted(say):
        k = say[p]
        n_asiri = int(round(k * pol.asiri_boy_orani))
        bantlar = ulasilabilir_bantlar(p, pol.bantlar)
        for j in range(k):
            if j < n_asiri:
                satirlar.append(PlanSatiri(p, "asiri-boy", "alt"))
            else:
                satirlar.append(PlanSatiri(p, "guc-gudumlu", bantlar[(j - n_asiri) % len(bantlar)]))
    rng.shuffle(satirlar)
    return satirlar


def anma_gucu(paket: str) -> float:
    """70 C anma gucu - parca kutuphanesinin RC_L paket tablosundan (uydurma yok)."""
    from ..devre.parca import varsayilan_kutuphane

    kayit = varsayilan_kutuphane().genel("resistor")
    return float(kayit.ham["paket_tablosu"][paket]["guc"]["onerilen_max"])


def ulasilabilir_bantlar(P: str, bantlar: tuple[str, ...]) -> tuple[str, ...]:
    """Temiz bir P referansindan (oran <= 0.5) paket-kucuk hatasiyla ulasilabilen
    bantlar. Ornek: 0402 -> 0201 en fazla 0.5 x 0.0625/0.05 = 0.625: yalnizca
    'alt'. Kapsanamayan bant raporda KAPSAM ACIGI olarak gecer."""
    kucukler = PAKETLER[:PAKETLER.index(P)]
    out = tuple(b for b in bantlar
                if any(REF_GUC_ORANI * anma_gucu(P) / anma_gucu(T) > BANTLAR[b][0] * 1.02 for T in kucukler))
    return out or ("alt",)


def _kosullar(rng: random.Random, pol: Politika) -> dict[str, Any]:
    vin = rng.choice(pol.vin)
    vout = rng.choice([v for v in VOUT if 0.08 * vin <= v <= 0.75 * vin])
    vin_tol = rng.choice(VIN_TOL)
    tepe = rng.choice(YUK_TEPE)
    sic = rng.choice(SICAKLIK)
    return {"vin": vin, "vout": vout, "vin_tol": vin_tol, "pencere": vin_tol + rng.choice(PENCERE_EK),
            "tepe": tepe, "nom": tepe * rng.choice((0.5, 1.0)), "sic": sic,
            "ortam": rng.choice([o for o in ORTAM if sic[0] <= o <= sic[1]]), "aralik": rng.choice(ARALIK),
            "tolerans": rng.choice(pol.toleranslar)}


def _degerler(k: dict[str, Any], i_div: float) -> tuple[float, float] | None:
    from .adaylar import _r_ust_hedef

    r2 = eseri.nearest(k["vout"] / i_div, "E96")
    r1 = _r_ust_hedef(r2, k["vin"], k["vout"], k["nom"])
    if r1 is None:
        return None
    r1 = eseri.nearest(r1, "E96")
    lo, hi = (10.0, 1e6) if k["tolerans"] < 0.01 else (10.0, 10e6)   # RC_L Tablo 2 araliklari
    if not (lo <= r1 <= hi and lo <= r2 <= hi):
        return None
    return r1, r2


def _param(kimlik: str, k: dict[str, Any], r1: float, r2: float, paket: str, mpn: bool) -> BolucuParametre:
    return BolucuParametre(kimlik, k["vin"], k["vin_tol"], k["vout"], k["pencere"], k["nom"], k["tepe"], k["ortam"],
                           k["sic"], r1, r2, k["tolerans"], paket, paket, k["aralik"], mpn)


def _analitik(p: BolucuParametre):
    return analitik(tasarim_kur(p, kart=False).graf(), B)


def _referans_kontrol(p: BolucuParametre) -> tuple[Tasarim | None, str]:
    an = _analitik(p)
    if not an.hesaplanabilir:
        return None, "el hesabi yapilamadi: " + "; ".join(an.eksikler)
    if not an.pencere_icinde:
        return None, "el hesabi: pencere tutmadi"
    if an.guc_orani > REF_GUC_ORANI:
        return None, f"{p.paket_ust} guc orani {an.guc_orani:.2f} > {REF_GUC_ORANI}"
    if an.gerilim_orani > 1.0:
        return None, f"{p.paket_ust} gerilim orani {an.gerilim_orani:.2f} > 1"
    t = tasarim_kur(p)
    if courtyard_cakismalari(t.board, {"R1", "R2"}):
        return None, f"{p.paket_ust} courtyard cakisiyor (aralik {p.aralik_mm} mm)"
    return t, ""


def ornekle_dogal(rng: random.Random, kimlik: str, pol: Politika
                  ) -> tuple[BolucuParametre | None, Tasarim | None, str, dict[str, Any]]:
    k = _kosullar(rng, pol)
    i_div = k["tepe"] * rng.choice(AKIM_KATI) if k["tepe"] > 0 else rng.choice(SABIT_AKIM)
    rr = _degerler(k, i_div)
    if rr is None:
        return None, None, "deger araligi disi", {}
    for paket in REF_PAKETLER:
        p = _param(kimlik, k, *rr, paket, pol.mpn)
        an = _analitik(p)
        if not an.hesaplanabilir:
            return None, None, "el hesabi yapilamadi: " + "; ".join(an.eksikler), {}
        if not an.pencere_icinde:
            return None, None, "el hesabi: pencere tutmadi", {}
        if an.guc_orani <= REF_GUC_ORANI and an.gerilim_orani <= 1.0:
            t, neden = _referans_kontrol(p)
            return (p, t, "", {"hedef_paket": rng.choice(("0201", "0402"))}) if t else (None, None, neden, {})
    return None, None, "guc icin uygun paket yok (<= 1206)", {}


def ornekle_dengeli(rng: random.Random, kimlik: str, pol: Politika, satir: PlanSatiri
                    ) -> tuple[BolucuParametre | None, Tasarim | None, str, dict[str, Any]]:
    """Katman paketini GEREKTIREN (ya da asiri-boy kipinde kaldiran) kosul uretir."""
    P = satir.paket
    k = _kosullar(rng, pol)
    kucukler = list(reversed(PAKETLER[:PAKETLER.index(P)]))      # P-1, P-2, ...
    if not kucukler:
        return None, None, "daha kucuk paket yok", {}
    if satir.kip == "asiri-boy":
        hedef, rho_lo, rho_hi = kucukler[0], 0.05, REF_GUC_ORANI * 0.95
    else:
        lo, hi = BANTLAR[satir.bant]
        # Referans temiz (P'de oran <= 0.5) oldugundan hedefte ulasilabilecek en
        # buyuk oran ~ 0.5 x anma(P) / anma(T). Banda yetisen hedefler arasindan sec.
        uygun = [T for T in kucukler if REF_GUC_ORANI * anma_gucu(P) / anma_gucu(T) > lo * 1.02]
        if not uygun:
            return None, None, f"bant {satir.bant}: {P} icin ulasilabilir hedef paket yok", {}
        hedef = rng.choice(uygun)
        rho_lo = max(lo, REF_GUC_ORANI * 1.02)
        rho_hi = min(hi, REF_GUC_ORANI * anma_gucu(P) / anma_gucu(hedef) * 0.98, 2.5)
        if rho_hi <= rho_lo:
            return None, None, f"bant {satir.bant}: {P}->{hedef} oran araligi bos", {}
    rho = math.exp(rng.uniform(math.log(rho_lo), math.log(rho_hi)))
    # Guc ~ bolucu akimi (gerilimler sabit): bir deneme akimiyla olc, olcekle.
    i_div = 1e-3
    for _ in range(3):
        rr = _degerler(k, i_div)
        if rr is None:
            return None, None, "deger araligi disi", {}
        an_h = _analitik(_param(kimlik, k, *rr, hedef, pol.mpn))
        if not an_h.hesaplanabilir or not math.isfinite(an_h.guc_orani) or an_h.guc_orani <= 0:
            return None, None, "hedef paket el hesabi yapilamadi", {}
        if abs(an_h.guc_orani / rho - 1) < 0.02:
            break
        i_div *= rho / an_h.guc_orani
        if not 1e-6 <= i_div <= 0.2:
            return None, None, "bolucu akimi aralik disi", {}
    rr = _degerler(k, i_div)
    if rr is None:
        return None, None, "deger araligi disi", {}
    an_h = _analitik(_param(kimlik, k, *rr, hedef, pol.mpn))
    if satir.kip == "asiri-boy":
        if an_h.guc_orani > REF_GUC_ORANI:
            return None, None, "asiri-boy: kucuk paket yeterli degil", {}
    else:
        # P gercekten EN KUCUK yeterli paket olmali (aradaki paketler yetmez)
        for ara in PAKETLER[PAKETLER.index(hedef) + 1:PAKETLER.index(P)]:
            if _analitik(_param(kimlik, k, *rr, ara, pol.mpn)).guc_orani <= REF_GUC_ORANI:
                return None, None, "guc-gudumlu: ara paket yeterli", {}
        if an_h.guc_orani <= REF_GUC_ORANI:
            return None, None, "guc-gudumlu: hedef paket yeterli", {}
        if bant(an_h.guc_orani) != satir.bant:
            return None, None, f"bant tutmadi ({bant(an_h.guc_orani)} != {satir.bant})", {}
    p = _param(kimlik, k, *rr, P, pol.mpn)
    t, neden = _referans_kontrol(p)
    if t is None:
        return None, None, neden, {}
    return p, t, "", {"hedef_paket": hedef, "hedef_guc_orani": round(an_h.guc_orani, 6),
                      "hedef_gerilim_orani": round(an_h.gerilim_orani, 6), "plan": satir.as_dict()}


def referans_bul(rng: random.Random, kimlik: str, pol: Politika, satir: PlanSatiri | None,
                 deneme: int = 400) -> tuple[BolucuParametre | None, Tasarim | None, dict[str, int], dict[str, Any]]:
    """Plan satirina uyan referans; tutmazsa bant gevsetilir ve KAYDEDILIR."""
    reddedilen: dict[str, int] = {}
    denenecek = [satir]
    if satir is not None and satir.kip == "guc-gudumlu":
        sira = {"ust": ["ust", "yakin", "alt"], "yakin": ["yakin", "alt"], "alt": ["alt"]}[satir.bant]
        denenecek = [replace(satir, bant=b) for b in sira]
    for s in denenecek:
        for _ in range(deneme):
            if s is None:
                p, t, neden, ek = ornekle_dogal(rng, kimlik, pol)
            else:
                p, t, neden, ek = ornekle_dengeli(rng, kimlik, pol, s)
            if p is not None:
                if satir is not None and s.bant != satir.bant:
                    ek["plan_sapmasi"] = f"bant {satir.bant} ulasilamadi -> {s.bant}"
                return p, t, reddedilen, ek
            reddedilen[neden] = reddedilen.get(neden, 0) + 1
    return None, None, reddedilen, {}
