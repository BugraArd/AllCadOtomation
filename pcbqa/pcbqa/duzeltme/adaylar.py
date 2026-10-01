"""Duzeltme adayi ureteci - bolucu ailesi.

Ureteci YALNIZCA tasarimi ve beyan edilen kosullari gorur: hatanin turunu
(kayitta saklidir) ve adaylarin benzetim sonucunu bilmez. Gercek kullanimda
da durum budur: kullanici "R1 yanlis" demez, kontroller bir bulgu verir.

Adaylar SABIT bir sirayla uretilir ve bu sira "mevcut yontemdir": en kucuk
degisiklik once (tek deger < tolerans < paket < olcek < yeniden tasarim).
Model bulunmadiginda uygulama tam olarak bu sirayla dener; model yalnizca
SIRAYI degistirir, aday kumesini degil (eleme yok -> hicbir aday kaybolmaz).

Operatorler:
  tolerans-sik      %1'den gevsek direncleri %1'e ceker
  tolerans-cok-sik  iki direnci %0.1'e ceker - YALNIZCA katalogda varsa (RC_L
                    %0.1: 10 ohm - 1 Mohm, Tablo 2; Kicad-7cb). Ilk surumdeki
                    "kutuphanede %1'den siki kayit yok" notu yanlisti.
  mpn-paket-esle    MPN'in paketi footprint'ten farkliysa MPN'i footprint
                    paketine esitler (BOM duzeltmesi; footprint degismez)
  ust-yeniden       R_ust'u, R_alt sabitken hedefi verecek E96/E24 degerine
  alt-yeniden       R_alt'i, R_ust sabitken ayni sekilde
  paket-buyut       bir ya da iki direnci bir/iki paket buyutur (guc)
  olcek             iki direnci ayni carpanla olcekler (oran ayni, empedans)
  yeniden-tasarla   bolucu akimini yukun m katina (ya da sabit akima) kurar,
                    degerleri E96'dan, paketi el hesabinin gucunden secer
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import eseri
from ..circuit import parse_value
from ..devre.kosullar import ag_anahtari
from ..devre.parca import paket_kodu, tolerans_metinden
from ..dogrulama.seviye2 import DIRENC_GUC_ORANI
from .bolucu import FOOTPRINT, PAKETLER, Bolucu, analitik
from .tasarim import MPN_ALANI, TOLERANS_ALANI, Degisiklik, Tasarim, deger_metni, tolerans_metni

URETEC_SURUMU = 2
OPERATORLER = ("mpn-paket-esle", "tolerans-sik", "tolerans-cok-sik", "ust-yeniden", "alt-yeniden", "paket-buyut",
               "olcek", "yeniden-tasarla")
HEDEF_TOLERANS = 0.01
COK_SIKI_TOLERANS = 0.001
COK_SIKI_ARALIK = (10.0, 1e6)     # RC_L Tablo 2, %0.1 ve %0.5'in deger araligi
R_MIN, R_MAX = 1.0, 10e6        # kalin film kaydinin TCR kosulu: 10 ohm - 10 Mohm
OLCEKLER = (0.1, 0.3, 3.0, 10.0)
AKIM_KATLARI = (20.0, 100.0)    # bolucu akimi = m x tepe yuk (muhendislik secimi)
SABIT_AKIMLAR = (100e-6, 1e-3)


@dataclass
class Aday:
    kimlik: str
    operator: str
    degisiklikler: list[Degisiklik]
    gerekce: str
    sira: int = 0
    ek: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"kimlik": self.kimlik, "operator": self.operator, "sira": self.sira,
                "gerekce": self.gerekce, "degisiklikler": [d.as_dict() for d in self.degisiklikler],
                "ek": dict(self.ek)}

    @classmethod
    def from_dict(cls, ham: dict[str, Any]) -> "Aday":
        return cls(ham["kimlik"], ham["operator"], [Degisiklik.from_dict(d) for d in ham["degisiklikler"]],
                   ham.get("gerekce", ""), int(ham.get("sira", 0)), dict(ham.get("ek") or {}))


def _r_ust_hedef(r2: float, vin: float, vt: float, i: float) -> float | None:
    """Vt = R2 (Vin - I R1)/(R1 + R2)  ->  R1 = R2 (Vin - Vt) / (Vt + I R2)."""
    pay, payda = r2 * (vin - vt), vt + i * r2
    return pay / payda if pay > 0 and payda > 0 else None


def _r_alt_hedef(r1: float, vin: float, vt: float, i: float) -> float | None:
    """R2 = Vt R1 / (Vin - Vt - I R1)."""
    payda = vin - vt - i * r1
    return vt * r1 / payda if payda > 0 else None


def _sinirda(r: float | None) -> bool:
    return r is not None and R_MIN <= r <= R_MAX


def adaylari_uret(t: Tasarim, b: Bolucu) -> list[Aday]:
    k = t.kosullar
    c = t.netlist.components
    # Gercek projede ag adlari hiyerarsi onekiyle gelir ("/VBUS"); beyan "VBUS".
    giris, cikis = ag_anahtari(b.giris), ag_anahtari(b.cikis)
    ray = next((v for ad, v in (k.get("raylar") or {}).items() if ag_anahtari(ad) == giris), None)
    ger = next((x for x in (k.get("gereksinimler") or []) if ag_anahtari(str(x.get("ag", ""))) == cikis), None)
    if ray is None or ger is None:
        return []
    vin = float(ray["nom"]) if isinstance(ray, dict) else float(ray)
    lo, hi = ger.get("min_v"), ger.get("max_v")
    vt = (float(lo) + float(hi)) / 2 if lo is not None and hi is not None else float(lo if lo is not None else hi)
    yukler = [y for y in (k.get("yukler") or []) if ag_anahtari(str(y.get("ag", ""))) == cikis]
    i_nom = sum(float(y["akim_a"]) for y in yukler)
    i_tepe = sum(float(y.get("tepe_a") if y.get("tepe_a") is not None else y["akim_a"]) for y in yukler)
    r1, r2 = parse_value(c[b.ust].value), parse_value(c[b.alt].value)
    if not r1 or not r2:
        return []

    def deg(ref: str, yeni: float) -> Degisiklik:
        return Degisiklik(ref, "deger", c[ref].value.split()[0], deger_metni(yeni))

    def tol_sik() -> list[Degisiklik]:
        out = []
        for ref in (b.ust, b.alt):
            # Tolerans alanda ya da deger metninde ("47k 1%") durabilir.
            eski = c[ref].fields.get(TOLERANS_ALANI) or next(
                (p for p in c[ref].value.split()[1:] if p.endswith("%")), "")
            mevcut = tolerans_metinden(eski)
            if mevcut is None or mevcut > HEDEF_TOLERANS + 1e-12:
                out.append(Degisiklik(ref, "tolerans", eski, tolerans_metni(HEDEF_TOLERANS)))
        return out

    def paket(ref: str, adim: int) -> Degisiklik | None:
        p = paket_kodu(c[ref].footprint)
        if p not in PAKETLER:
            return None
        j = PAKETLER.index(p) + adim
        if j >= len(PAKETLER):
            return None
        return Degisiklik(ref, "footprint", c[ref].footprint, FOOTPRINT[PAKETLER[j]])

    adaylar: list[Aday] = []

    def mpn_esle() -> list[Degisiklik]:
        from ..devre.parca import rc_l_siparis_kodu, tolerans_metinden
        out = []
        for ref in (b.ust, b.alt):
            mpn = c[ref].fields.get(MPN_ALANI) or ""
            fp = paket_kodu(c[ref].footprint)
            if not mpn.startswith("RC") or mpn[2:6] == fp:
                continue
            tol_m = c[ref].fields.get(TOLERANS_ALANI) or next(
                (x for x in c[ref].value.split()[1:] if x.endswith("%")), "")
            tol = tolerans_metinden(tol_m) if tol_m else None
            kod = rc_l_siparis_kodu(fp, tol, parse_value(c[ref].value)) if tol is not None else None
            if kod:
                out.append(Degisiklik(ref, "mpn", mpn, kod))
        return out

    def ekle(kimlik, operator, degs, gerekce, **ek):
        degs = [d for d in degs if d is not None and d.eski != d.yeni]
        if degs:
            adaylar.append(Aday(kimlik, operator, degs, gerekce, ek=ek))

    me = mpn_esle()
    if me:
        ekle("mpn-paket-esle", "mpn-paket-esle", me, "MPN paketi footprint paketine esitlendi (BOM)")
    ts = tol_sik()
    if ts:
        ekle("tolerans-sik", "tolerans-sik", ts, "gevsek toleransli direncler %1'e cekildi")
    if all(COK_SIKI_ARALIK[0] <= v <= COK_SIKI_ARALIK[1] for v in (r1, r2)):
        cs = []
        for ref in (b.ust, b.alt):
            eski = c[ref].fields.get(TOLERANS_ALANI) or next(
                (x for x in c[ref].value.split()[1:] if x.endswith("%")), "")
            mevcut = tolerans_metinden(eski)
            if mevcut is None or mevcut > COK_SIKI_TOLERANS + 1e-12:
                cs.append(Degisiklik(ref, "tolerans", eski, tolerans_metni(COK_SIKI_TOLERANS)))
        if cs:
            ekle("tolerans-cok-sik", "tolerans-cok-sik", cs, "iki direnc %0.1'e cekildi (katalogda var)")
    for seri in ("E96", "E24"):
        v = _r_ust_hedef(r2, vin, vt, i_nom)
        if _sinirda(v):
            ekle(f"ust-yeniden-{seri}", "ust-yeniden", [deg(b.ust, eseri.nearest(v, seri))],
                 f"{b.ust} hedef {vt:.4g} V icin yeniden hesaplandi ({seri})", seri=seri)
        v = _r_alt_hedef(r1, vin, vt, i_nom)
        if _sinirda(v):
            ekle(f"alt-yeniden-{seri}", "alt-yeniden", [deg(b.alt, eseri.nearest(v, seri))],
                 f"{b.alt} hedef {vt:.4g} V icin yeniden hesaplandi ({seri})", seri=seri)
    ekle("paket-buyut-ust", "paket-buyut", [paket(b.ust, 1)], f"{b.ust} bir paket buyuk", adim=1)
    ekle("paket-buyut-alt", "paket-buyut", [paket(b.alt, 1)], f"{b.alt} bir paket buyuk", adim=1)
    ekle("paket-buyut-ikisi", "paket-buyut", [paket(b.ust, 1), paket(b.alt, 1)], "iki direnc bir paket buyuk",
         adim=1)
    ekle("paket-buyut-ikisi-2", "paket-buyut", [paket(b.ust, 2), paket(b.alt, 2)], "iki direnc iki paket buyuk",
         adim=2)
    for m in OLCEKLER:
        a, z = r1 * m, r2 * m
        if _sinirda(a) and _sinirda(z):
            ekle(f"olcek-x{m:g}", "olcek", [deg(b.ust, eseri.nearest(a, "E96")), deg(b.alt, eseri.nearest(z, "E96"))],
                 f"iki direnc x{m:g} (oran korunur, empedans degisir)", carpan=m)

    akimlar = [(f"m{m:g}", m * i_tepe) for m in AKIM_KATLARI if i_tepe > 0]
    akimlar += [(f"{ia * 1e3:g}mA", ia) for ia in SABIT_AKIMLAR]
    for etiket, i_div in akimlar:
        if i_div <= 0:
            continue
        r2y = eseri.nearest(vt / i_div, "E96") if vt / i_div > 0 else None
        r1y = _r_ust_hedef(r2y, vin, vt, i_nom) if r2y else None
        if not (_sinirda(r1y) and _sinirda(r2y)):
            continue
        r1y = eseri.nearest(r1y, "E96")
        degs = [deg(b.ust, r1y), deg(b.alt, r2y), *ts]
        # Paket: el hesabiyla guc orani <= %50 (seviye2'nin uyari esigi) olan
        # en kucuk paket. Benzetim degil - kapali form, aninda.
        secilen = None
        for p in PAKETLER[1:]:
            fp = FOOTPRINT[p]
            deneme = degs + [Degisiklik(b.ust, "footprint", c[b.ust].footprint, fp),
                             Degisiklik(b.alt, "footprint", c[b.alt].footprint, fp)]
            g = t.uygula([d for d in deneme if d.eski != d.yeni]).graf()
            an = analitik(g, b)
            if an.hesaplanabilir and an.guc_orani <= DIRENC_GUC_ORANI and an.gerilim_orani <= 1.0:
                secilen = deneme
                break
        if secilen is None:
            continue
        ekle(f"yeniden-tasarla-{etiket}", "yeniden-tasarla", secilen,
             f"bolucu akimi {i_div * 1e6:.3g} uA'e gore yeniden tasarlandi (E96, %1, guc <= %50)",
             akim_a=i_div)

    # Ayni degisiklik kumesini veren adaylardan ilki kalir.
    gorulen: set[frozenset] = set()
    tekil: list[Aday] = []
    for a in adaylar:
        anahtar = frozenset((d.ref, d.alan, d.yeni) for d in a.degisiklikler)
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        a.sira = len(tekil)
        tekil.append(a)
    return tekil
