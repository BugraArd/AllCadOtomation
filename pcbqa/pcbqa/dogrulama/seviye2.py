"""Seviye 2 - parcaya ve devrenin amacina bagli muhendislik kurallari.

ERC "bu pin bagli mi" der; burada sorulan "bagli oldugu sey ona uygun mu":

  giris-asiri-gerilim   Bir pine izin verilenden yuksek gerilim uygulaniyor mu?
                        (pin siniri > parca siniri > CMOS genel kurali VDD+0.3)
  regulator-kosullari   Giris mutlak maksimumu, dusum marji, yuk akimi, guc
                        kaybi ve jonksiyon sicakligi (thermal.py egrisiyle)
  gate-surme            MOSFET'in gate surme gerilimi secilen parcaya yetiyor
                        mu? (Vgs(th) max, Rds(on)'un tanimlandigi Vgs, Vgs max)
  gerekli-eleman        Acik-drain/I2C pull-up, IC dekuplaji, regulator
                        giris/cikis kondansatoru, enduktif yuk korumasi
  bilesen-yuklenmesi    Direnc gucu ve gerilimi, kondansator anma gerilimi

Her kural PARCA bilgisini (sinirlar) ve bilesenin ROLUNU (roller.py) kullanir;
gerekli bilgi yoksa sessizce gecmez, "denetlenemedi" (info) bulgusu birakir.

Muhendislik secimleri (kaynakli degil, ayarlanabilir sabitler):
  CMOS_GIRIS_PAYI_V     = 0.3   genel CMOS mutlak maks kurali (VDD + 0.3 V);
                                 5 V toleransli pinlerde YANLIS ALARM verebilir,
                                 pin siniri girilince kullanilmaz
  KOND_GERILIM_ORANI    = 0.8   anma geriliminin %80'i ustu uyari (sinif II
                                 seramikte DC bias kaybi da buyur)
  DIRENC_GUC_ORANI      = 0.5   anma gucunun %50'si ustu uyari
"""

from __future__ import annotations

import re

from .. import thermal
from ..devre.graf import BilesenDugumu, DevreGrafi, PinDugumu
from ..rules import Finding
from .sonuc import SeviyeSonucu, bulgu, eksik_bulgu

KAYNAK = "pcbqa-muh"

CMOS_GIRIS_PAYI_V = 0.3
KOND_GERILIM_ORANI = 0.8
DIRENC_GUC_ORANI = 0.5
# Ortam beyan edilmediyse termal hesap oda sicakligiyla ALT SINIR olarak
# yapilir ve bulgu bunu soyler (gercek kart daha sicak olabilir).
VARSAYILAN_ORTAM_C = 25.0

_I2C = re.compile(r"(^|[/_])(SDA|SCL)\d*($|_)", re.IGNORECASE)


# --------------------------------------------------------------------------
# yardimcilar
# --------------------------------------------------------------------------


def ag_araligi(g: DevreGrafi, ag: str) -> tuple[float, float] | None:
    """Agin (en dusuk, en yuksek) gerilimi: beyan araligi ya da nominal."""
    if not ag:
        return None
    ray = g.kosullar.ray(ag)
    if ray is not None:
        return ray.en_dusuk, ray.en_yuksek
    v = g.gerilim(ag)
    if v.bilinen:
        return float(v.deger), float(v.deger)
    return None


def _besleme(g: DevreGrafi, b: BilesenDugumu) -> float | None:
    """Bir IC'nin besleme gerilimi: guc-giris pinlerindeki en yuksek ray."""
    degerler = []
    for p in b.pinler.values():
        if p.islev == "guc-giris" or p.tip == "power_in":
            ar = ag_araligi(g, p.ag)
            if ar and ar[1] > 0:
                degerler.append(ar[1])
    return max(degerler) if degerler else None


def _ortam(g: DevreGrafi) -> tuple[float, str]:
    if g.kosullar.ortam_c is not None:
        return g.kosullar.ortam_c, f"ortam {g.kosullar.ortam_c:g} C (beyan)"
    return VARSAYILAN_ORTAM_C, (f"ortam beyan edilmedi; {VARSAYILAN_ORTAM_C:g} C ile ALT SINIR "
                                "hesaplandi (gercek kart daha sicak olabilir)")


def _yuk_akimi(g: DevreGrafi, ag: str) -> float | None:
    yukler = g.kosullar.yukler_on(ag)
    if not yukler:
        return None
    return sum(y.akim_a for y in yukler)


# --------------------------------------------------------------------------
# 1) asiri gerilim
# --------------------------------------------------------------------------


def _pin_siniri(b: BilesenDugumu, p: PinDugumu):
    """(mutlak_max, onerilen_max, kaynak) ya da None."""
    if p.bilgi and "gerilim" in p.bilgi.sinirlar:
        s = p.bilgi.sinirlar["gerilim"]
        return s.mutlak_max, s.onerilen_max, s.kaynak
    if p.islev == "guc-giris":
        for ad in ("vin", "vdd", "vcc"):
            s = b.parca.sinir(ad)
            if s is not None:
                return s.mutlak_max, s.onerilen_max, s.kaynak
    return None


def kontrol_asiri_gerilim(g: DevreGrafi) -> list[Finding]:
    out: list[Finding] = []
    eksikler: list[str] = []
    for b in g.bilesenler.values():
        if b.tur != "ic":
            continue
        vdd = _besleme(g, b)
        for p in b.pinler.values():
            if p.islev not in ("giris", "iki-yonlu", "acik-kolektor", "guc-giris") or not p.ag:
                continue
            ar = ag_araligi(g, p.ag)
            if ar is None:
                continue
            v = ar[1]
            sinir = _pin_siniri(b, p)
            if sinir is not None:
                mutlak, onerilen, kaynak = sinir
                if mutlak is not None and v > mutlak:
                    out.append(bulgu("giris-asiri-gerilim", "error",
                                     f"{p.gorunen} pinine {v:g} V uygulaniyor; mutlak maksimum "
                                     f"{mutlak:g} V ({kaynak})",
                                     source=KAYNAK, refs=[b.ref], pins=[p.tam],
                                     measured=v, limit=mutlak))
                elif onerilen is not None and v > onerilen:
                    out.append(bulgu("giris-asiri-gerilim", "warning",
                                     f"{p.gorunen} pinine {v:g} V; onerilen calisma ust siniri "
                                     f"{onerilen:g} V ({kaynak})",
                                     source=KAYNAK, refs=[b.ref], pins=[p.tam],
                                     measured=v, limit=onerilen))
                continue
            if p.islev == "guc-giris":
                eksikler.append(p.tam)
                continue
            if vdd is None:
                eksikler.append(p.tam)
                continue
            limit = vdd + CMOS_GIRIS_PAYI_V
            if v > limit + 1e-9:
                out.append(bulgu("giris-asiri-gerilim", "warning",
                                 f"{p.gorunen} pinine {v:g} V; {b.ref} beslemesi {vdd:g} V. "
                                 f"Pin siniri girilmemis - CMOS genel kurali VDD+{CMOS_GIRIS_PAYI_V:g} V "
                                 f"= {limit:g} V (muhendislik secimi; 5 V toleransli pinse sinirini girin)",
                                 source=KAYNAK, refs=[b.ref], pins=[p.tam],
                                 measured=v, limit=limit))
    if eksikler:
        out.append(eksik_bulgu("giris-asiri-gerilim",
                               f"{len(eksikler)} pinin siniri ya da IC beslemesi bilinmiyor: "
                               + ", ".join(sorted(eksikler)[:12]), source=KAYNAK))
    out += _ayrik_gerilimler(g)
    return out


def _ayrik_gerilimler(g: DevreGrafi) -> list[Finding]:
    """MOSFET Vds/Vgs ve diyot ters gerilimi."""
    out: list[Finding] = []
    for b, rol in g.rolle("anahtar"):
        d, s, gt = (ag_araligi(g, rol.aglar.get(k, "")) for k in ("drain", "source", "gate"))
        vds = b.parca.sinir("vds")
        if d and s and vds and vds.mutlak_max is not None:
            v = abs(d[1] - s[0])
            if v > vds.mutlak_max:
                out.append(bulgu("giris-asiri-gerilim", "error",
                                 f"{b.ref} Vds {v:g} V > mutlak {vds.mutlak_max:g} V ({vds.kaynak})",
                                 source=KAYNAK, refs=[b.ref], measured=v, limit=vds.mutlak_max))
    for b in g.kategoride("diyot", "zener"):
        vr = b.parca.sinir("vrrm")
        if vr is None or vr.mutlak_max is None:
            continue
        katot = next((p.ag for p in b.pinler.values() if p.islev == "katot"), None)
        anot = next((p.ag for p in b.pinler.values() if p.islev == "anot"), None)
        k_ar, a_ar = ag_araligi(g, katot or ""), ag_araligi(g, anot or "")
        if k_ar and a_ar:
            v = k_ar[1] - a_ar[0]
            if v > vr.mutlak_max:
                out.append(bulgu("giris-asiri-gerilim", "error",
                                 f"{b.ref} ters gerilim {v:g} V > VRRM {vr.mutlak_max:g} V",
                                 source=KAYNAK, refs=[b.ref], measured=v, limit=vr.mutlak_max))
    return out


# --------------------------------------------------------------------------
# 2) regulator
# --------------------------------------------------------------------------


def regulator_termal(g: DevreGrafi, b: BilesenDugumu, guc_w: float) -> dict:
    """Tj hesabi: thermal.py egrisi + karttaki tab bakir alani."""
    paket = b.parca.termal.get("paket")
    tj_max = b.parca.termal.get("tj_max")
    ortam, ortam_m = _ortam(g)
    out = {"ortam_c": ortam, "ortam_aciklama": ortam_m, "guc_w": guc_w}
    if not paket or not paket.bilinen or paket.deger not in thermal.THETA_JA_CURVES:
        out["eksik"] = "paketin theta_JA egrisi yok (thermal.py)"
        return out
    alan = None
    alan_m = "kart yok: en kucuk olculmus alan (yalnizca pad) - MUHAFAZAKAR"
    if g.board is not None:
        comp = g.board.by_ref(b.ref)
        if comp and comp.pads:
            tab = max(comp.pads, key=lambda p: p.area_mm2)
            if tab.net:
                alan = g.board.copper_area_mm2(tab.net)
                alan_m = (f"tab agi {tab.net}: {alan:.0f} mm2 bakir (pad+iz+dokum, "
                          "ust uste binme cift sayilir - IYIMSER)")
    curve = thermal.THETA_JA_CURVES[paket.deger]
    alan_hesap = alan if alan else (curve[0][0] or 1.0)
    theta = thermal.theta_ja_c_per_w(paket.deger, alan_hesap)
    out.update({
        "paket": paket.deger, "alan_mm2": alan, "alan_aciklama": alan_m,
        "theta_ja": theta, "theta_kaynak": thermal.SOURCES.get(paket.deger, ""),
        "tj_c": ortam + guc_w * theta,
        "tj_max_c": tj_max.deger if tj_max and tj_max.bilinen else None,
    })
    gereksinim = g.kosullar.gereksinim_ref(b.ref)
    if gereksinim and gereksinim.tj_max_c is not None:
        out["tj_hedef_c"] = gereksinim.tj_max_c
    return out


def kontrol_regulator(g: DevreGrafi) -> list[Finding]:
    out: list[Finding] = []
    for b, rol in g.rolle("regulator"):
        giris, cikis = rol.aglar.get("giris"), rol.aglar.get("cikis")
        vin = ag_araligi(g, giris or "")
        vout = ag_araligi(g, cikis or "")
        if vin is None or vout is None:
            out.append(eksik_bulgu("regulator-kosullari",
                                   f"{b.ref}: giris ya da cikis gerilimi bilinmiyor "
                                   f"(giris={giris}, cikis={cikis}); kosullar dosyasinda ray beyan edin",
                                   source=KAYNAK, refs=[b.ref]))
            continue
        vin_s = b.parca.sinir("vin")
        if vin_s and vin_s.mutlak_max is not None and vin[1] > vin_s.mutlak_max:
            out.append(bulgu("regulator-kosullari", "error",
                             f"{b.ref} girisi {vin[1]:g} V > mutlak maks {vin_s.mutlak_max:g} V ({vin_s.kaynak})",
                             source=KAYNAK, refs=[b.ref], measured=vin[1], limit=vin_s.mutlak_max))
        dusum = b.parca.sinir("dusum")
        if dusum and dusum.onerilen_max is not None:
            marj = vin[0] - vout[1]
            if marj < dusum.onerilen_max:
                out.append(bulgu("regulator-kosullari", "error",
                                 f"{b.ref}: en dusuk giris {vin[0]:g} V - cikis {vout[1]:g} V = {marj:.2f} V; "
                                 f"azami dusum {dusum.onerilen_max:g} V ({dusum.kosul}) - regulasyon kaybolur",
                                 source=KAYNAK, refs=[b.ref], measured=marj, limit=dusum.onerilen_max))
        elif not dusum:
            out.append(eksik_bulgu("regulator-kosullari", f"{b.ref}: dusum gerilimi parca bilgisinde yok",
                                   source=KAYNAK, refs=[b.ref]))

        yuk = _yuk_akimi(g, cikis or "")
        if yuk is None:
            out.append(eksik_bulgu("regulator-kosullari",
                                   f"{b.ref}: cikis agi {cikis} icin yuk akimi beyan edilmedi "
                                   "(kosullar.yukler) - guc ve Tj hesaplanamadi",
                                   source=KAYNAK, refs=[b.ref]))
            continue
        iout = b.parca.sinir("iout")
        if iout and iout.onerilen_max is not None and yuk > iout.onerilen_max:
            out.append(bulgu("regulator-kosullari", "warning",
                             f"{b.ref} yuk {yuk:g} A > {iout.onerilen_max:g} A ({iout.kosul})",
                             source=KAYNAK, refs=[b.ref], measured=yuk, limit=iout.onerilen_max))
        asinir = b.parca.sinir("akim_siniri")
        if asinir and asinir.onerilen_min is not None and yuk > asinir.onerilen_min:
            out.append(bulgu("regulator-kosullari", "error",
                             f"{b.ref} yuk {yuk:g} A, garanti edilen akim siniri {asinir.onerilen_min:g} A'i asiyor",
                             source=KAYNAK, refs=[b.ref], measured=yuk, limit=asinir.onerilen_min))

        if b.parca.kategori == "ldo":
            guc = (vin[1] - vout[0]) * yuk
            t = regulator_termal(g, b, guc)
            if "eksik" in t:
                out.append(eksik_bulgu("regulator-kosullari", f"{b.ref}: {t['eksik']}",
                                       source=KAYNAK, refs=[b.ref]))
                continue
            limit = t.get("tj_hedef_c") or t.get("tj_max_c")
            if limit is None:
                out.append(eksik_bulgu("regulator-kosullari", f"{b.ref}: Tj max bilinmiyor",
                                       source=KAYNAK, refs=[b.ref]))
                continue
            mesaj = (f"{b.ref} LDO kaybi ({vin[1]:g} - {vout[0]:g} V) x {yuk:g} A = {guc:.2f} W; "
                     f"theta_JA {t['theta_ja']:.0f} C/W ({t['alan_aciklama']}); {t['ortam_aciklama']}; "
                     f"Tj = {t['tj_c']:.0f} C, sinir {limit:g} C")
            if t["tj_c"] > limit:
                out.append(bulgu("regulator-termal", "error", mesaj + " - ASILIYOR",
                                 source=KAYNAK, refs=[b.ref], measured=round(t["tj_c"], 2), limit=limit))
            else:
                out.append(bulgu("regulator-termal", "info", mesaj,
                                 source=KAYNAK, refs=[b.ref], measured=round(t["tj_c"], 2), limit=limit))
    return out


# --------------------------------------------------------------------------
# 3) gate surme
# --------------------------------------------------------------------------


def kontrol_gate(g: DevreGrafi) -> list[Finding]:
    out: list[Finding] = []
    for b, rol in g.rolle("anahtar"):
        gate, source = rol.aglar.get("gate"), rol.aglar.get("source")
        vs = ag_araligi(g, source or "")
        # Gate surme: gate agi bir raysa o; degilse sureni IC'nin beslemesi
        vg = ag_araligi(g, gate or "")
        nereden = "gate agi gerilimi"
        if vg is None or vg[1] == 0:
            surucu = [h.split(".")[0] for h in rol.hedefler]
            beslemeler = [v for v in (_besleme(g, g.bilesenler[r]) for r in surucu if r in g.bilesenler) if v]
            if beslemeler:
                vg = (min(beslemeler), min(beslemeler))
                nereden = (f"surucu {', '.join(surucu)} beslemesi (cikis yuksek seviyesi ~besleme; "
                           "muhendislik yaklasimi)")
        if vg is None or vs is None:
            out.append(eksik_bulgu("gate-surme", f"{b.ref}: gate surme ya da source gerilimi bilinmiyor",
                                   source=KAYNAK, refs=[b.ref]))
            continue
        if b.parca.kategori == "mosfet-p":
            # Yuksek taraf P-kanal: source rayda, gate 0 V'a cekilerek acilir.
            vgs = vs[0]
        else:
            # En kotu durum: en dusuk surme, en yuksek source
            vgs = vg[0] - vs[1]
        esik = b.parca.sinir("vgs_esik")
        rds = b.parca.sinir("rds_on_vgs")
        vgs_max = b.parca.sinir("vgs")
        if not (esik or rds or vgs_max):
            out.append(eksik_bulgu("gate-surme", f"{b.ref}: Vgs(th) / Rds(on) Vgs / Vgs max parca bilgisinde yok",
                                   source=KAYNAK, refs=[b.ref]))
            continue
        if vgs_max and vgs_max.mutlak_max is not None and vgs > vgs_max.mutlak_max:
            out.append(bulgu("gate-surme", "error",
                             f"{b.ref} Vgs {vgs:g} V > mutlak maks {vgs_max.mutlak_max:g} V",
                             source=KAYNAK, refs=[b.ref], measured=vgs, limit=vgs_max.mutlak_max))
        if esik and esik.onerilen_max is not None and vgs <= esik.onerilen_max:
            out.append(bulgu("gate-surme", "error",
                             f"{b.ref} gate surme {vgs:g} V <= Vgs(th) max {esik.onerilen_max:g} V ({nereden}) - "
                             "MOSFET guvenle iletime gecmeyebilir",
                             source=KAYNAK, refs=[b.ref], measured=vgs, limit=esik.onerilen_max))
        elif rds and rds.onerilen_min is not None and vgs < rds.onerilen_min:
            out.append(bulgu("gate-surme", "warning",
                             f"{b.ref} gate surme {vgs:g} V < Rds(on)'un tanimlandigi en dusuk Vgs "
                             f"{rds.onerilen_min:g} V ({rds.kosul}) - iletim direnci garanti degil; "
                             "mantik seviyeli MOSFET secin ya da surucu ekleyin",
                             source=KAYNAK, refs=[b.ref], measured=vgs, limit=rds.onerilen_min))
    return out


# --------------------------------------------------------------------------
# 4) gerekli elemanlar
# --------------------------------------------------------------------------


def kontrol_gerekli(g: DevreGrafi) -> list[Finding]:
    out: list[Finding] = []
    pullup_aglari = {r.aglar.get("sinyal") for _, r in g.rolle("pull-up")}
    # Acik-drain pinler ve I2C hatlari pull-up ister
    for a in g.aglar.values():
        if a.toprak or g.ray_mi(a.ad):
            continue
        acik = [p for p in a.pinler if p.islev == "acik-kolektor"]
        i2c = bool(_I2C.search(a.ad)) and any(g.bilesenler[p.ref].tur == "ic" for p in a.pinler)
        if (acik or i2c) and a.ad not in pullup_aglari:
            neden = "acik-drain/kolektor pin " + ", ".join(p.tam for p in acik) if acik else "I2C hatti"
            out.append(bulgu("pull-up-eksik", "warning",
                             f"{a.ad} agi pull-up istiyor ({neden}) ama ray ile arasinda direnc yok",
                             source=KAYNAK, refs=sorted(a.refler)))

    # IC dekuplaji
    dekuplajli = {h.split(".")[0] for _, r in g.rolle("dekuplaj") for h in r.hedefler}
    for b in g.bilesenler.values():
        if b.tur != "ic" or b.rol("regulator"):
            continue
        guc_pinleri = [p for p in b.pinler.values()
                       if (p.islev == "guc-giris" or p.tip == "power_in") and p.ag and not g.toprak_mi(p.ag)]
        if guc_pinleri and b.ref not in dekuplajli:
            out.append(bulgu("dekuplaj-eksik", "warning",
                             f"{b.ref} guc pinleri ({', '.join(sorted(p.gorunen for p in guc_pinleri))}) "
                             "icin ray-toprak arasinda dekuplaj kondansatoru yok",
                             source=KAYNAK, refs=[b.ref]))

    # Regulator kondansatorleri
    for b, rol in g.rolle("regulator"):
        for taraf, rol_adi in (("giris", "regulator-giris-kond"), ("cikis", "regulator-cikis-kond")):
            kondlar = [c for c, r in g.rolle(rol_adi) if b.ref in r.hedefler]
            if rol.aglar.get(taraf) and not kondlar:
                out.append(bulgu("regulator-kond-eksik", "warning",
                                 f"{b.ref} {taraf}inde ({rol.aglar[taraf]}) topraga kondansator yok",
                                 source=KAYNAK, refs=[b.ref]))
            if taraf == "cikis" and kondlar:
                cmin = b.parca.sinir("cout")
                toplam = sum(float(c.parca.deger.deger) for c in kondlar
                             if c.parca.deger.bilinen and isinstance(c.parca.deger.deger, float))
                if cmin and cmin.onerilen_min is not None and toplam < cmin.onerilen_min:
                    out.append(bulgu("regulator-kond-eksik", "warning",
                                     f"{b.ref} cikis kapasitesi {toplam * 1e6:g} uF < {cmin.onerilen_min * 1e6:g} uF "
                                     f"({cmin.kosul}; {cmin.kaynak})",
                                     source=KAYNAK, refs=[b.ref] + [c.ref for c in kondlar],
                                     measured=toplam, limit=cmin.onerilen_min))

    # Enduktif yuk korumasi
    korunan = {h for _, r in g.rolle("serbest-gecis-diyotu") for h in r.hedefler}
    for b, rol in g.rolle("enduktif-yuk"):
        if b.ref not in korunan:
            out.append(bulgu("enduktif-koruma-eksik", "error",
                             f"{b.ref} enduktif yuku {', '.join(rol.hedefler)} ile anahtarlaniyor ama ters "
                             "paralel (serbest gecis) diyotu yok - kapanista Vds asiri gerilimi",
                             source=KAYNAK, refs=[b.ref] + rol.hedefler))
    return out


# --------------------------------------------------------------------------
# 5) bilesen yuklenmesi
# --------------------------------------------------------------------------


def direnc_guc_siniri(g: DevreGrafi, b: BilesenDugumu) -> tuple[float, str] | None:
    s = b.parca.sinir("guc")
    if s is None or s.onerilen_max is None:
        return None
    p = s.onerilen_max
    ortam = g.kosullar.ortam_c
    tam = b.parca.termal.get("tam_guc_ortam_c")
    sifir = b.parca.termal.get("sifir_guc_ortam_c")
    if ortam is not None and tam and sifir and tam.bilinen and sifir.bilinen and ortam > tam.deger:
        oran = max(0.0, (sifir.deger - ortam) / (sifir.deger - tam.deger))
        return p * oran, f"{p:g} W, {ortam:g} C ortamda azaltilmis ({s.kaynak})"
    return p, f"{p:g} W ({s.kaynak}, {s.guven or 'beyan'})"


def kontrol_yuklenme(g: DevreGrafi) -> list[Finding]:
    out: list[Finding] = []
    kond_eksik: list[str] = []
    direnc_eksik: list[str] = []
    for b in g.bilesenler.values():
        uclar = g.iki_uc(b)
        if uclar is None or b.dnp:
            continue
        a1, a2 = (ag_araligi(g, a) for a in uclar)
        if a1 is None or a2 is None:
            continue
        dv = max(abs(a1[1] - a2[0]), abs(a2[1] - a1[0]))
        if b.tur == "resistor":
            r = b.parca.deger.deger if b.parca.deger.bilinen else None
            if not isinstance(r, float) or r <= 0:
                continue
            guc = dv * dv / r
            siniri = direnc_guc_siniri(g, b)
            if siniri is None:
                direnc_eksik.append(b.ref)
                continue
            limit, aciklama = siniri
            if guc > limit:
                out.append(bulgu("direnc-gucu", "error",
                                 f"{b.ref} uzerinde {dv:g} V -> {guc * 1e3:.1f} mW > {limit * 1e3:.1f} mW ({aciklama})",
                                 source=KAYNAK, refs=[b.ref], measured=guc, limit=limit))
            elif guc > DIRENC_GUC_ORANI * limit:
                out.append(bulgu("direnc-gucu", "warning",
                                 f"{b.ref} {guc * 1e3:.1f} mW, anma gucunun %{100 * guc / limit:.0f}'i "
                                 f"(> %{DIRENC_GUC_ORANI * 100:.0f} muhendislik secimi; {aciklama})",
                                 source=KAYNAK, refs=[b.ref], measured=guc, limit=DIRENC_GUC_ORANI * limit))
            vs = b.parca.sinir("gerilim")
            if vs and vs.onerilen_max is not None and dv > vs.onerilen_max:
                out.append(bulgu("direnc-gerilimi", "error",
                                 f"{b.ref} uclari arasi {dv:g} V > azami calisma gerilimi {vs.onerilen_max:g} V",
                                 source=KAYNAK, refs=[b.ref], measured=dv, limit=vs.onerilen_max))
        elif b.tur == "capacitor":
            vs = b.parca.sinir("gerilim")
            if vs is None or vs.onerilen_max is None:
                kond_eksik.append(f"{b.ref}({dv:g} V)")
                continue
            if dv > vs.onerilen_max:
                out.append(bulgu("kondansator-gerilimi", "error",
                                 f"{b.ref} uzerinde {dv:g} V > anma {vs.onerilen_max:g} V ({vs.kaynak})",
                                 source=KAYNAK, refs=[b.ref], measured=dv, limit=vs.onerilen_max))
            elif dv > KOND_GERILIM_ORANI * vs.onerilen_max:
                out.append(bulgu("kondansator-gerilimi", "warning",
                                 f"{b.ref} {dv:g} V, anma geriliminin %{100 * dv / vs.onerilen_max:.0f}'i "
                                 f"(> %{KOND_GERILIM_ORANI * 100:.0f}; sinif II seramikte DC bias kaybi)",
                                 source=KAYNAK, refs=[b.ref], measured=dv,
                                 limit=KOND_GERILIM_ORANI * vs.onerilen_max))
    if kond_eksik:
        out.append(eksik_bulgu("kondansator-gerilimi",
                               "anma gerilimi bilinmeyen kondansatorler: " + ", ".join(sorted(kond_eksik)),
                               source=KAYNAK))
    if direnc_eksik:
        out.append(eksik_bulgu("direnc-gucu", "anma gucu bilinmeyen direncler: " + ", ".join(sorted(direnc_eksik)),
                               source=KAYNAK))
    return out


KONTROLLER = (
    ("giris-asiri-gerilim", kontrol_asiri_gerilim),
    ("regulator-kosullari", kontrol_regulator),
    ("gate-surme", kontrol_gate),
    ("gerekli-eleman", kontrol_gerekli),
    ("bilesen-yuklenmesi", kontrol_yuklenme),
)


def seviye2(g: DevreGrafi) -> SeviyeSonucu:
    sonuc = SeviyeSonucu(2, "Muhendislik kurallari")
    for ad, fn in KONTROLLER:
        bulgular = fn(g)
        sonuc.bulgular += bulgular
        sonuc.ekler[ad] = len([f for f in bulgular if f.rule_type != "eksik-bilgi"])
    return sonuc
