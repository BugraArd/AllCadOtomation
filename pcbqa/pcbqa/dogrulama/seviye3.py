"""Seviye 3 - benzetim: ERC'den gecen devre yine de yanlis calisabilir.

Akis (Python yonetir, ngspice yan surecte hesaplar):
  1. devre grafindan SPICE netlisti (spice/netlist.py)
  2. test kosullari: kosullar dosyasindaki kaynaklar, yukler ve senaryolar
  3. ngspice'i calistir (tek oturum; senaryolar `alter` + `op` ile)
  4. sonuclari oku (wrdata)
  5. tasarim gereksinimleriyle ve parca sinirlariyla karsilastir

"Ileride cikabilecek sorunlar" icin senaryolar:
  nominal         beyan edilen ortam (yoksa 25 C), nominal degerler
  giris-min/max   beyan edilen kaynak araliginin uclari
  tepe-yuk        yuklerin beyan edilen tepe akimi
  tolerans+/-     tum direncler toleranslarinin ust/alt ucunda (kose)
  monte-carlo-N   toleranslar icinde duzgun dagilimli ornekleme (tohum sabit)
  sicaklik-T+/-   direncler TCR siniriyla T'ye tasinir (+/- en kotu yon)
  yaslanma+/-     veri sayfasi omur testi sapmasi; daha uzun sureye
                  EKSTRAPOLE EDILMEZ (oran bilinmiyor) - bu not raporda gecer

DC calisma noktasinda kondansator acik devre, bobin kisa devredir; bu yuzden
C/L tolerans ve sicaklik etkileri bu seviyede gorunmez (geçici analiz
Kicad-5d6.5 kapsaminda).

Ornek (kullanicinin verdigi): varsayimsal bir LDO 12 V'u 3.3 V'a indirip
300 mA verirse Vout gereksinimi saglanir AMA kayip (12 - 3.3) x 0.3 = 2.61 W
olur; SOT-223'te Tj yuzlerce C'ye cikar. ERC bunu goremez, benzetim
kaybi olcer, termal model Tj'yi verir.
"""

from __future__ import annotations

import random
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..devre.graf import DevreGrafi
from ..spice import SpiceHatasi, arka_uc_bul, calistir, devre_kur, wrdata_oku
from ..spice.netlist import SpiceDevresi
from .seviye2 import DIRENC_GUC_ORANI, KOND_GERILIM_ORANI, direnc_guc_siniri, regulator_termal
from .sonuc import SeviyeSonucu, bulgu, eksik_bulgu

KAYNAK = "pcbqa-spice"

# Muhendislik secimi: beyan yoksa endustriyel aralik koseleri.
VARSAYILAN_SICAKLIKLAR = (-40.0, 85.0)
VARSAYILAN_MONTE_CARLO = 30
TOHUM = 20261001
# Regulasyon kaybi esigi: cikis nominalin bu kadar altindaysa dusumde
REGULASYON_PAYI_V = 1e-3


@dataclass
class Senaryo:
    ad: str
    tur: str
    sicaklik_c: float
    degerler: dict[str, float] = field(default_factory=dict)
    aciklama: str = ""


def nominal_degerler(d: SpiceDevresi) -> dict[str, float]:
    """Her senaryonun TAM deger kumesinin tabani.

    `alter` bir sonraki senaryoya tasindigi icin her senaryo butun degerleri
    yeniden yazar; ek senaryo ureten cagiranlar da bu tabandan baslamali.
    """
    nominal: dict[str, float] = {}
    for ad, p in d.pasifler.items():
        nominal[ad] = p.nominal
    for ad, (_ag, v, _mn, _mx) in d.kaynaklar.items():
        nominal[ad] = v
    for ad, (_ag, i) in d.yukler.items():
        nominal[ad] = i
    return nominal


# Ek senaryo kancasi: (graf, spice devresi) -> (senaryolar, notlar)
EkSenaryolar = Callable[[DevreGrafi, SpiceDevresi], "tuple[list[Senaryo], list[str]]"]


def senaryolar_uret(g: DevreGrafi, d: SpiceDevresi) -> tuple[list[Senaryo], list[str]]:
    notlar: list[str] = []
    analiz = g.kosullar.analiz
    ortam = g.kosullar.ortam_c if g.kosullar.ortam_c is not None else 25.0

    nominal = nominal_degerler(d)

    def s(ad, tur, t, degisim=None, aciklama=""):
        deg = dict(nominal)
        deg.update(degisim or {})
        return Senaryo(ad, tur, t, deg, aciklama)

    out = [s("nominal", "nominal", ortam, aciklama=f"nominal degerler, {ortam:g} C")]

    for ad, (ag, v, mn, mx) in d.kaynaklar.items():
        if mn is None and mx is None:
            notlar.append(f"{ag}: kaynak araligi (min/max) beyan edilmedi - giris koseleri yok")
        if mn is not None:
            out.append(s(f"giris-min:{ag}", "kaynak-kose", ortam, {ad: mn}, f"{ag} = {mn:g} V"))
        if mx is not None:
            out.append(s(f"giris-max:{ag}", "kaynak-kose", ortam, {ad: mx}, f"{ag} = {mx:g} V"))

    tepe = {f"I_yuk{i}": y.tepe_a for i, y in enumerate(g.kosullar.yukler)
            if y.tepe_a is not None and f"I_yuk{i}" in d.yukler}
    if tepe:
        out.append(s("tepe-yuk", "tepe-yuk", ortam, tepe, "yukler beyan edilen tepe akiminda"))

    direncler = {ad: p for ad, p in d.pasifler.items() if p.harf == "R"}
    toleransli = {ad: p for ad, p in direncler.items() if p.tolerans is not None}
    toleranssiz = sorted(p.ref for ad, p in direncler.items() if p.tolerans is None)
    if toleranssiz:
        notlar.append("toleransi bilinmeyen direncler nominalde tutuldu: " + ", ".join(toleranssiz))
    if toleransli:
        for isaret, ek in ((1, "+"), (-1, "-")):
            out.append(s(f"tolerans{ek}", "tolerans-kose", ortam,
                         {ad: p.nominal * (1 + isaret * p.tolerans) for ad, p in toleransli.items()},
                         f"tum direncler tolerans {ek} ucunda"))
        n = int(analiz.get("monte_carlo", VARSAYILAN_MONTE_CARLO))
        rng = random.Random(TOHUM)
        for k in range(n):
            out.append(s(f"monte-carlo-{k}", "monte-carlo", ortam,
                         {ad: p.nominal * (1 + rng.uniform(-p.tolerans, p.tolerans))
                          for ad, p in toleransli.items()}))

    sicakliklar = [float(t) for t in analiz.get("sicakliklar", VARSAYILAN_SICAKLIKLAR)]
    if "sicakliklar" not in analiz:
        notlar.append("sicaklik koseleri beyan edilmedi; -40/85 C kullanildi (muhendislik secimi)")
    tcr = {ad: p for ad, p in direncler.items() if p.tcr_ppm is not None}
    for t in sicakliklar:
        if abs(t - ortam) < 1e-9:
            continue
        for isaret, ek in ((1, "+"), (-1, "-")):
            out.append(s(f"sicaklik{t:g}{ek}", "sicaklik", t,
                         {ad: p.nominal * (1 + isaret * p.tcr_ppm * 1e-6 * (t - 25.0)) for ad, p in tcr.items()},
                         f"{t:g} C, TCR {ek} yonde"))
    if direncler and not tcr:
        notlar.append("hicbir direncin sicaklik katsayisi bilinmiyor - sicaklik senaryolari yalnizca ortam degistirir")

    # Termal en kotu durum: en yuksek giris + en sicak ortam, SUREKLI yuk.
    # Tepe yuk termalde kullanilmaz (kisa darbe isil zaman sabitinin altinda).
    en_sicak = max([ortam, *sicakliklar])
    maksimumlar = {ad: mx for ad, (_ag, _v, _mn, mx) in d.kaynaklar.items() if mx is not None}
    if maksimumlar or en_sicak > ortam:
        out.append(s("termal-en-kotu", "termal", en_sicak, maksimumlar,
                     f"giris en yuksek, ortam {en_sicak:g} C, surekli yuk"))

    yaslanan = {ad: p for ad, p in direncler.items() if p.yaslanma_yuzde is not None}
    if yaslanan:
        saat = analiz.get("yaslanma_saat")
        test = max((p.yaslanma_test_saat or 0) for p in yaslanan.values())
        if saat is not None and float(saat) > test:
            notlar.append(f"yaslanma: beyan {float(saat):g} saat, veri sayfasi testi {test:g} saat - "
                          "daha uzun sure icin EKSTRAPOLASYON YAPILMADI; sonuc test suresine aittir")
        for isaret, ek in ((1, "+"), (-1, "-")):
            out.append(s(f"yaslanma{ek}", "yaslanma", ortam,
                         {ad: p.nominal * (1 + isaret * p.yaslanma_yuzde / 100.0) + isaret * p.yaslanma_ek_ohm
                          for ad, p in yaslanan.items()},
                         f"veri sayfasi omur testi sapmasi {ek} yonde"))
    elif direncler:
        notlar.append("yaslanma verisi olan direnc yok - yaslanma senaryosu kurulmadi")
    return out, notlar


def kontrol_blogu(d: SpiceDevresi, senaryolar: list[Senaryo]) -> list[str]:
    vektorler = [f"v({n})" for n in sorted(set(d.dugumler.values())) if n != "0"]
    vektorler += [f"i({ad})" for ad in d.kaynaklar]
    vektorler += [f"i({r.sense})" for r in d.regulatorler.values()]
    satirlar = ["set wr_singlescale", "set wr_vecnames"]
    for k, sn in enumerate(senaryolar):
        satirlar.append(f"* senaryo {k}: {sn.ad}")
        satirlar.append(f"option temp={sn.sicaklik_c:g}")
        for ad, deger in sn.degerler.items():
            if ad.startswith(("V_", "I_")):
                satirlar.append(f"alter {ad} dc = {deger:.9g}")
            else:
                satirlar.append(f"alter {ad} = {deger:.9g}")
        satirlar.append("op")
        satirlar.append(f"wrdata s{k}.txt {' '.join(vektorler)}")
    return satirlar


def _deger(sonuc: dict[str, float], vektor: str) -> float | None:
    return sonuc.get(vektor.lower())


def seviye3(g: DevreGrafi, calisma: Path | None = None, zaman_asimi: float = 180.0,
            ek_senaryolar: EkSenaryolar | None = None) -> SeviyeSonucu:
    """`ek_senaryolar`: aileye ozgu kose senaryolari (or. bolucude capraz
    tolerans kosesi - yukaridaki `tolerans+/-` tum direncleri AYNI yone
    kaydirir ve bolucu oranini degistirmez; olculdu, Kicad-u4k)."""
    sonuc = SeviyeSonucu(3, "Benzetim (ngspice)")
    d = devre_kur(g)
    sonuc.ekler["devre"] = d.as_dict()
    if not d.kaynaklar:
        sonuc.calisti = False
        sonuc.atlanma_nedeni = ("besleme kaynagi yok: kosullar.kaynaklar ile bir ray beyan edin "
                                "ya da guc-girisi konnektorunun rayina gerilim verin")
        return sonuc
    arka = arka_uc_bul()
    if arka is None:
        sonuc.calisti = False
        sonuc.atlanma_nedeni = "ngspice bulunamadi (PCBQA_NGSPICE ya da KiCad ngspice.dll)"
        return sonuc
    sonuc.ekler["arka_uc"] = arka.aciklama()

    senaryolar, notlar = senaryolar_uret(g, d)
    if ek_senaryolar is not None:
        ek, ek_notlar = ek_senaryolar(g, d)
        senaryolar += ek
        notlar += ek_notlar
    sonuc.ekler["notlar"] = notlar + d.notlar
    calisma = Path(calisma) if calisma else Path(tempfile.mkdtemp(prefix="pcbqa-spice-"))
    calisma.mkdir(parents=True, exist_ok=True)
    yol = calisma / "devre.cir"
    yol.write_text(d.metin(kontrol_blogu(d, senaryolar), baslik=g.proje or "pcbqa"), encoding="utf-8")
    sonuc.ekler["netlist"] = str(yol)

    try:
        cal = calistir(yol, arka, zaman_asimi)
    except SpiceHatasi as exc:
        sonuc.bulgular.append(bulgu("benzetim-calismadi", "error", str(exc), source=KAYNAK))
        return sonuc
    if not cal.ok:
        sonuc.bulgular.append(bulgu("benzetim-hatasi", "error",
                                    "ngspice hata bildirdi: " + " | ".join(cal.hatalar[-5:])[:400],
                                    source=KAYNAK))
        sonuc.ekler["gunluk"] = cal.gunluk[-40:]
        return sonuc

    sonuclar: list[tuple[Senaryo, dict[str, float]]] = []
    for k, sn in enumerate(senaryolar):
        try:
            satir = wrdata_oku(calisma / f"s{k}.txt")
        except SpiceHatasi as exc:
            sonuc.bulgular.append(bulgu("benzetim-hatasi", "error", f"{sn.ad}: {exc}", source=KAYNAK))
            continue
        if satir:
            sonuclar.append((sn, satir[0]))
    sonuc.ekler["senaryo_sayisi"] = len(sonuclar)
    sonuc.bulgular += _karsilastir(g, d, sonuclar, sonuc.ekler)
    for ref, neden in d.atlananlar:
        sonuc.bulgular.append(eksik_bulgu("spice-modeli", f"{ref} benzetime girmedi: {neden}",
                                          source=KAYNAK, refs=[ref]))
    for ref, neden in d.idealler:
        sonuc.bulgular.append(bulgu("spice-ideal-model", "info", f"{ref}: {neden}",
                                    source=KAYNAK, refs=[ref], rule_type="eksik-bilgi"))
    return sonuc


def _karsilastir(g, d: SpiceDevresi, sonuclar, ekler: dict) -> list:
    out = []
    ozet: dict[str, dict] = {}
    ag_dugum = {ag: n for ag, n in d.dugumler.items() if n != "0"}

    def v_of(sonuc, ag):
        n = ag_dugum.get(ag)
        if n is None:
            return 0.0 if g.toprak_mi(ag) else None
        return _deger(sonuc, f"v({n})")

    # --- ag gerilimleri ve gereksinimler ---
    for ag in sorted(ag_dugum):
        degerler = [(sn.ad, v_of(r, ag)) for sn, r in sonuclar if v_of(r, ag) is not None]
        if not degerler:
            continue
        nom = next((v for ad, v in degerler if ad == "nominal"), degerler[0][1])
        en_d = min(degerler, key=lambda x: x[1])
        en_y = max(degerler, key=lambda x: x[1])
        ozet[ag] = {"nominal_v": round(nom, 6), "min_v": round(en_d[1], 6), "min_senaryo": en_d[0],
                    "max_v": round(en_y[1], 6), "max_senaryo": en_y[0]}
        ger = g.kosullar.gereksinim_ag(ag)
        if ger is None:
            continue
        if ger.min_v is not None and en_d[1] < ger.min_v:
            out.append(bulgu("gereksinim-gerilim", "error",
                             f"{ag} {en_d[1]:.4g} V < gereksinim {ger.min_v:g} V (senaryo {en_d[0]})",
                             source=KAYNAK, measured=en_d[1], limit=ger.min_v))
        if ger.max_v is not None and en_y[1] > ger.max_v:
            out.append(bulgu("gereksinim-gerilim", "error",
                             f"{ag} {en_y[1]:.4g} V > gereksinim {ger.max_v:g} V (senaryo {en_y[0]})",
                             source=KAYNAK, measured=en_y[1], limit=ger.max_v))
        if (ger.min_v is None or en_d[1] >= ger.min_v) and (ger.max_v is None or en_y[1] <= ger.max_v):
            marj = min(x for x in ((en_d[1] - ger.min_v) if ger.min_v is not None else None,
                                   (ger.max_v - en_y[1]) if ger.max_v is not None else None) if x is not None)
            out.append(bulgu("gereksinim-gerilim", "info",
                             f"{ag} tum senaryolarda gereksinim icinde ({en_d[1]:.4g}..{en_y[1]:.4g} V), "
                             f"en dar marj {marj * 1e3:.1f} mV", source=KAYNAK, measured=marj))
    if not g.kosullar.gereksinimler:
        out.append(eksik_bulgu("gereksinim-gerilim", "tasarim gereksinimi beyan edilmedi "
                               "(kosullar.gereksinimler); yalnizca parca sinirlari karsilastirildi",
                               source=KAYNAK))
    ekler["ag_ozeti"] = ozet

    # --- regulatorler: kayip, dusum, Tj ---
    reg_ozet = {}
    for ref, r in d.regulatorler.items():
        b = g.bilesenler[ref]
        en_kotu = None
        dusumde = []
        for sn, res in sonuclar:
            vin, vout = v_of(res, r.vin), v_of(res, r.vout)
            iout = _deger(res, f"i({r.sense})")
            if None in (vin, vout, iout):
                continue
            guc = (vin - vout) * max(iout, 0.0) + vin * r.iq
            if vout < r.vnom - REGULASYON_PAYI_V:
                dusumde.append(sn.ad)
            if sn.tur == "tepe-yuk":
                continue  # termalde surekli akim gecerli; tepe yalnizca dusum icin
            t = regulator_termal(g, b, guc)
            tj = sn.sicaklik_c + guc * t["theta_ja"] if "theta_ja" in t else None
            kayit = {"senaryo": sn.ad, "vin": vin, "vout": vout, "iout": iout, "guc_w": guc,
                     "tj_c": tj, "ortam_c": sn.sicaklik_c}
            if en_kotu is None or guc > en_kotu["guc_w"] or (tj and en_kotu["tj_c"] and tj > en_kotu["tj_c"]):
                en_kotu = kayit
            limit = (t.get("tj_hedef_c") or t.get("tj_max_c")) if t else None
            kayit["tj_sinir_c"] = limit
        if en_kotu is None:
            continue
        reg_ozet[ref] = en_kotu
        if dusumde:
            out.append(bulgu("regulasyon-kaybi", "error",
                             f"{ref} cikisi {len(dusumde)} senaryoda nominalin altinda (dusumde): "
                             + ", ".join(dusumde[:6]), source=KAYNAK, refs=[ref]))
        limit = en_kotu.get("tj_sinir_c")
        if en_kotu["tj_c"] is not None and limit is not None:
            mesaj = (f"{ref} benzetim: en kotu senaryo {en_kotu['senaryo']} - Vin {en_kotu['vin']:.3g} V, "
                     f"Vout {en_kotu['vout']:.3g} V, Iout {en_kotu['iout'] * 1e3:.0f} mA, kayip "
                     f"{en_kotu['guc_w']:.2f} W, Tj {en_kotu['tj_c']:.0f} C (sinir {limit:g} C)")
            sev = "error" if en_kotu["tj_c"] > limit else "info"
            out.append(bulgu("benzetim-termal", sev, mesaj + (" - ASILIYOR" if sev == "error" else ""),
                             source=KAYNAK, refs=[ref], measured=round(en_kotu["tj_c"], 2), limit=limit))
    ekler["regulatorler"] = reg_ozet

    # --- pasif yuklenme (benzetimin cozdugu gerilimlerle) ---
    for ad, p in d.pasifler.items():
        b = g.bilesenler[p.ref]
        uclar = g.iki_uc(b)
        if uclar is None:
            continue
        en_kotu_v = 0.0
        en_kotu_p = 0.0
        senaryo = ""
        for sn, res in sonuclar:
            v1, v2 = v_of(res, uclar[0]), v_of(res, uclar[1])
            if v1 is None or v2 is None:
                continue
            dv = abs(v1 - v2)
            deger = sn.degerler.get(ad, p.nominal)
            guc = dv * dv / deger if p.harf == "R" else 0.0
            if dv > en_kotu_v or guc > en_kotu_p:
                en_kotu_v, en_kotu_p, senaryo = max(dv, en_kotu_v), max(guc, en_kotu_p), sn.ad
        # Bulgu olmasa da olcum saklanir: duzeltme siralamasi (Kicad-u4k)
        # hatali tasarimin marjini oznitelik olarak okur.
        ekler.setdefault("pasif_yuklenme", {})[p.ref] = {
            "gerilim_v": en_kotu_v, "guc_w": en_kotu_p, "senaryo": senaryo}
        if p.harf == "R":
            siniri = direnc_guc_siniri(g, b)
            if siniri and en_kotu_p > siniri[0]:
                out.append(bulgu("benzetim-direnc-gucu", "error",
                                 f"{p.ref} {en_kotu_p * 1e3:.1f} mW > {siniri[0] * 1e3:.1f} mW (senaryo {senaryo})",
                                 source=KAYNAK, refs=[p.ref], measured=en_kotu_p, limit=siniri[0]))
            elif siniri and en_kotu_p > DIRENC_GUC_ORANI * siniri[0]:
                out.append(bulgu("benzetim-direnc-gucu", "warning",
                                 f"{p.ref} {en_kotu_p * 1e3:.1f} mW, anma gucunun %{100 * en_kotu_p / siniri[0]:.0f}'i "
                                 f"(senaryo {senaryo})", source=KAYNAK, refs=[p.ref],
                                 measured=en_kotu_p, limit=DIRENC_GUC_ORANI * siniri[0]))
        elif p.harf == "C":
            s = b.parca.sinir("gerilim")
            if s and s.onerilen_max is not None:
                if en_kotu_v > s.onerilen_max:
                    out.append(bulgu("benzetim-kond-gerilimi", "error",
                                     f"{p.ref} {en_kotu_v:.3g} V > anma {s.onerilen_max:g} V (senaryo {senaryo})",
                                     source=KAYNAK, refs=[p.ref], measured=en_kotu_v, limit=s.onerilen_max))
                elif en_kotu_v > KOND_GERILIM_ORANI * s.onerilen_max:
                    out.append(bulgu("benzetim-kond-gerilimi", "warning",
                                     f"{p.ref} {en_kotu_v:.3g} V, anma geriliminin "
                                     f"%{100 * en_kotu_v / s.onerilen_max:.0f}'i (senaryo {senaryo})",
                                     source=KAYNAK, refs=[p.ref], measured=en_kotu_v,
                                     limit=KOND_GERILIM_ORANI * s.onerilen_max))
    return out
