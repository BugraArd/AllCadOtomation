"""Devre grafindan SPICE netlisti.

Ne modellenir, ne modellenmez - ve her ikisi de KAYIT altina alinir:

  pasifler (R/C/L)   SPICE ilkel elemani; degeri parcanin degeri
  LDO / regulator    DAVRANISSAL model (ideal): Vout = min(Vnom, Vin - dusum),
                     giris akimi = cikis akimi + Iq. Iq bilinmiyorsa 0 alinir
                     ve `idealler` listesine yazilir.
  diyot              varsayilan SPICE diyot modeli (ideal; Vf parcaya ozgu degil)
  MOSFET / entegre   ureticinin .subckt'i parca kaydinda varsa o; yoksa
                     ATLANIR ve `atlananlar`a yazilir (bkz. Kicad-5d6.5 -
                     SPICE gelistirilmeli)
  MCU / diger IC     atlanir; akimi kosullar.yukler ile akim kaynagi olarak girer
  besleme            kosullar.kaynaklar ya da guc-girisi rolundeki raylar

Her toprak agi SPICE'in 0 dugumune baglanir. Birden fazla toprak agi varsa
(AGND/DGND) bu bir yaklasimdir ve nota yazilir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..devre.graf import BilesenDugumu, DevreGrafi

# Yuzen dugumleri onlemek icin her dugumden topraga: yalnizca sayisal.
# 1 Tohm, 3.3 V'ta 3.3 pA cekiyor - hicbir olcumu etkilemez.
SIZINTI_OHM = 1e12

_GECERSIZ = re.compile(r"[^A-Za-z0-9_]")


def dugum_adi(ag: str) -> str:
    return "N_" + _GECERSIZ.sub("_", ag.lstrip("/")) if ag else ""


def eleman_adi(harf: str, ref: str, ek: str = "") -> str:
    return f"{harf}_{_GECERSIZ.sub('_', ref)}{('_' + ek) if ek else ''}"


@dataclass
class Pasif:
    eleman: str
    ref: str
    harf: str
    nominal: float
    tolerans: float | None
    tcr_ppm: float | None = None
    yaslanma_yuzde: float | None = None
    yaslanma_test_saat: float | None = None
    # Omur sapmasinin sabit kismi: RC_L Tablo 8 "+-(1% + 50 mohm)" (Kicad-7cb)
    yaslanma_ek_ohm: float = 0.0


@dataclass
class Regulator:
    ref: str
    sense: str           # cikis akimini olcen 0 V kaynak
    vin: str
    vout: str
    vnom: float
    dusum: float
    iq: float


@dataclass
class SpiceDevresi:
    satirlar: list[str] = field(default_factory=list)
    modeller: list[str] = field(default_factory=list)
    dugumler: dict[str, str] = field(default_factory=dict)       # ag -> dugum
    kaynaklar: dict[str, tuple[str, float, float | None, float | None]] = field(default_factory=dict)
    yukler: dict[str, tuple[str, float]] = field(default_factory=dict)  # eleman -> (ag, akim)
    pasifler: dict[str, Pasif] = field(default_factory=dict)
    regulatorler: dict[str, Regulator] = field(default_factory=dict)
    atlananlar: list[tuple[str, str]] = field(default_factory=list)
    idealler: list[tuple[str, str]] = field(default_factory=list)
    notlar: list[str] = field(default_factory=list)

    def metin(self, kontrol: list[str], baslik: str = "pcbqa devre") -> str:
        govde = [f"* {baslik}", "* pcbqa tarafindan uretildi - elle duzenlemeyin", *self.satirlar,
                 *self.modeller, ".control", *kontrol, ".endc", ".end", ""]
        return "\n".join(govde)

    def as_dict(self) -> dict:
        return {
            "dugumler": dict(self.dugumler),
            "kaynaklar": {k: list(v) for k, v in self.kaynaklar.items()},
            "yukler": {k: list(v) for k, v in self.yukler.items()},
            "pasifler": {k: vars(p) for k, p in self.pasifler.items()},
            "regulatorler": {k: vars(r) for k, r in self.regulatorler.items()},
            "atlananlar": [list(x) for x in self.atlananlar],
            "idealler": [list(x) for x in self.idealler],
            "notlar": list(self.notlar),
        }


def _dugum(g: DevreGrafi, d: SpiceDevresi, ag: str) -> str:
    if not ag:
        return ""
    if g.toprak_mi(ag):
        d.dugumler[ag] = "0"
        return "0"
    n = d.dugumler.get(ag) or dugum_adi(ag)
    d.dugumler[ag] = n
    return n


def _pasif(g: DevreGrafi, d: SpiceDevresi, b: BilesenDugumu) -> None:
    uclar = g.iki_uc(b)
    deger = b.parca.deger.deger if b.parca.deger.bilinen else None
    if uclar is None or not all(uclar) or not isinstance(deger, float) or deger <= 0:
        d.atlananlar.append((b.ref, "iki uclu ve sayisal degerli olmali"))
        return
    harf = {"resistor": "R", "capacitor": "C", "inductor": "L"}[b.tur]
    n1, n2 = (_dugum(g, d, a) for a in uclar)
    if n1 == n2:
        d.atlananlar.append((b.ref, "iki ucu ayni dugumde"))
        return
    ad = eleman_adi(harf, b.ref)
    d.satirlar.append(f"{ad} {n1} {n2} {deger:.9g}")
    tol = b.parca.tolerans.deger if b.parca.tolerans.bilinen else None
    tk = b.parca.sicaklik_katsayisi.deger if b.parca.sicaklik_katsayisi.bilinen else None
    ya = b.parca.yaslanma.deger if b.parca.yaslanma.bilinen else None
    d.pasifler[ad] = Pasif(
        eleman=ad, ref=b.ref, harf=harf, nominal=deger, tolerans=tol,
        tcr_ppm=float(tk["ppm_c"]) if isinstance(tk, dict) and "ppm_c" in tk else None,
        yaslanma_yuzde=float(ya["sapma_yuzde"]) if isinstance(ya, dict) and "sapma_yuzde" in ya else None,
        yaslanma_test_saat=float(ya["test_saat"]) if isinstance(ya, dict) and "test_saat" in ya else None,
        yaslanma_ek_ohm=float(ya.get("ek_ohm") or 0.0) if isinstance(ya, dict) else 0.0,
    )


def _regulator(g: DevreGrafi, d: SpiceDevresi, b: BilesenDugumu) -> None:
    rol = b.rol("regulator")
    sp = b.parca.spice
    if rol is None or sp is None or sp.tur != "davranissal":
        if sp is not None and sp.tur == "altdevre" and sp.metin:
            _altdevre(g, d, b)
        else:
            d.atlananlar.append((b.ref, f"regulator modeli yok: {b.parca.spice_eksik}"))
        return
    vin_ag, vout_ag = rol.aglar.get("giris"), rol.aglar.get("cikis")
    gnd_ag = next((p.ag for p in b.pinler.values() if p.islev == "gnd" and p.ag), None)
    if not (vin_ag and vout_ag):
        d.atlananlar.append((b.ref, "regulator giris/cikis agi bulunamadi"))
        return
    vin, vout = _dugum(g, d, vin_ag), _dugum(g, d, vout_ag)
    gnd = _dugum(g, d, gnd_ag) if gnd_ag else "0"
    vnom = float(sp.parametreler.get("vnom", 0))
    dusum = float(sp.parametreler.get("dusum", 0))
    iq_s = b.parca.sinir("iq")
    iq = iq_s.onerilen_max if iq_s and iq_s.onerilen_max is not None else 0.0
    ic = "NI_" + _GECERSIZ.sub("_", b.ref)   # ideal kaynagin ic dugumu
    sense = eleman_adi("V", b.ref, "s")
    d.satirlar += [
        f"* {b.ref} {b.deger}: davranissal LDO ({sp.kaynak})",
        f"{eleman_adi('B', b.ref, 'out')} {ic} {gnd} V = max(0, min({vnom:g}, V({vin},{gnd}) - {dusum:g}))",
        f"{sense} {ic} {vout} DC 0",
        f"{eleman_adi('B', b.ref, 'in')} {vin} {gnd} I = max(0, I({sense})) + {iq:g}",
    ]
    d.regulatorler[b.ref] = Regulator(b.ref, sense, vin_ag, vout_ag, vnom, dusum, iq)
    d.idealler.append((b.ref, "davranissal LDO: dusum sabit (en kotu durum), akim siniri / "
                              "termal kapanma / gecici yanit yok"
                       + ("" if iq_s else "; Iq bilinmiyor, 0 alindi")))


def _altdevre(g: DevreGrafi, d: SpiceDevresi, b: BilesenDugumu) -> None:
    sp = b.parca.spice
    dugumler = []
    for model_dugum in sp.dugumler:
        pin_no = next((no for no, md in sp.pin_esleme.items() if md == model_dugum), None)
        pin = b.pinler.get(pin_no) if pin_no else None
        if pin is None or not pin.ag:
            d.atlananlar.append((b.ref, f"model dugumu {model_dugum} bir sembol pinine eslenmemis"))
            return
        dugumler.append(_dugum(g, d, pin.ag))
    d.satirlar.append(f"{eleman_adi('X', b.ref)} {' '.join(dugumler)} {sp.ad}")
    if sp.metin not in d.modeller:
        d.modeller.append(sp.metin)


def _diyot(g: DevreGrafi, d: SpiceDevresi, b: BilesenDugumu) -> None:
    anot = next((p.ag for p in b.pinler.values() if p.islev == "anot"), None)
    katot = next((p.ag for p in b.pinler.values() if p.islev == "katot"), None)
    if not (anot and katot):
        # KiCad Device:D: 1 = K, 2 = A
        pins = {p.numara: p.ag for p in b.pinler.values()}
        katot, anot = pins.get("1"), pins.get("2")
    if not (anot and katot):
        d.atlananlar.append((b.ref, "anot/katot pinleri bulunamadi"))
        return
    d.satirlar.append(f"{eleman_adi('D', b.ref)} {_dugum(g, d, anot)} {_dugum(g, d, katot)} PCBQA_D")
    if ".model PCBQA_D D" not in d.modeller:
        d.modeller.append(".model PCBQA_D D")
    d.idealler.append((b.ref, "varsayilan SPICE diyot modeli (Vf, IS parcaya ozgu degil)"))


def devre_kur(g: DevreGrafi) -> SpiceDevresi:
    d = SpiceDevresi()
    topraklar = sorted(a.ad for a in g.aglar.values() if a.toprak)
    if len(topraklar) > 1:
        d.notlar.append(f"birden fazla toprak agi tek 0 dugumune baglandi: {', '.join(topraklar)}")

    for b in sorted(g.bilesenler.values(), key=lambda x: x.ref):
        if b.dnp:
            continue
        k = b.parca.kategori
        if b.tur in ("resistor", "capacitor", "inductor"):
            _pasif(g, d, b)
        elif b.rol("regulator"):
            _regulator(g, d, b)
        elif k in ("diyot", "zener"):
            _diyot(g, d, b)
        elif b.parca.spice is not None and b.parca.spice.tur == "altdevre" and b.parca.spice.metin:
            _altdevre(g, d, b)
        elif b.tur in ("connector", "testpoint", "other") and k in ("konnektor", "test-noktasi", "genel"):
            continue  # elektriksel olarak yalnizca ag; model gerekmez
        else:
            neden = b.parca.spice_eksik if b.parca.spice is None else f"model turu {b.parca.spice.tur} desteklenmiyor"
            d.atlananlar.append((b.ref, neden))

    # Besleme kaynaklari
    kaynak_aglari: list[str] = []
    for ad in g.kosullar.kaynaklar:
        a = g.ag(ad)
        if a is not None:
            kaynak_aglari.append(a.ad)
    if not kaynak_aglari:
        for b, rol in g.rolle("guc-girisi"):
            ray = rol.aglar.get("ray")
            if ray and ray not in kaynak_aglari:
                kaynak_aglari.append(ray)
    regulator_cikislari = {r.vout for r in d.regulatorler.values()}
    for ag in kaynak_aglari:
        if ag in regulator_cikislari:
            continue
        v = g.gerilim(ag)
        if not v.bilinen:
            d.notlar.append(f"kaynak agi {ag} gerilimi bilinmiyor - kaynak eklenmedi")
            continue
        ray = g.kosullar.ray(ag)
        ad = eleman_adi("V", ag.lstrip("/"))
        d.satirlar.append(f"{ad} {_dugum(g, d, ag)} 0 DC {float(v.deger):g}")
        d.kaynaklar[ad] = (ag, float(v.deger), ray.min if ray else None, ray.max if ray else None)

    # Yukler
    for i, y in enumerate(g.kosullar.yukler):
        a = g.ag(y.ag)
        if a is None:
            d.notlar.append(f"yuk agi bulunamadi: {y.ag}")
            continue
        ad = f"I_yuk{i}"
        d.satirlar.append(f"{ad} {_dugum(g, d, a.ad)} 0 DC {y.akim_a:g}")
        d.yukler[ad] = (a.ad, y.akim_a)

    for ag, n in sorted(d.dugumler.items()):
        if n != "0":
            d.satirlar.append(f"R_sizinti_{n} {n} 0 {SIZINTI_OHM:g}")
    return d
