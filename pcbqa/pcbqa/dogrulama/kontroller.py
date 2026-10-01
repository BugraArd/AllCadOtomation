"""Dokuz kontrol - devre grafi uzerinde, her biri ayri bir amac icin.

| Kontrol                         | Amac                                                  |
|---------------------------------|-------------------------------------------------------|
| baglanti-esligi                 | PCB hedef devreyle ayni baglantilari tasiyor mu       |
| pin-esligi                      | sembol - footprint - SPICE modeli pin numaralari      |
| bilesen-yuklenmesi              | guc, gerilim, akim ve calisma sinirlari               |
| termal                          | regulator Tj ve bakir isinmasi                        |
| koruma-koordinasyonu            | sigorta / TVS ile korunan parcanin uyumu              |
| donus-yolu                      | guc ve sinyal akimlarinin uygun yoldan donmesi        |
| uretilebilirlik                 | ureticinin iz, aciklik, delik, halka, kenar sinirlari |
| mekanik-montaj                  | kart siniri, montaj delikleri, konnektor erisimi,     |
|                                 | cakismalar                                            |
| test-edilebilirlik              | olcum noktalari ve programlama baglantisi             |

Her kontrol bir `KontrolSonucu` dondurur: durum "gecti" | "uyari" | "kaldi"
| "kismen" | "denetlenemedi". "Denetlenemedi" ve "kismen" GECTI DEMEK
DEGILDIR; nedeni yazilir.

Muhendislik secimleri (kaynaksiz, ayarlanabilir):
  KONNEKTOR_KENAR_MM = 5.0     konnektor govdesinin kart kenarina en fazla uzakligi
  DUZLEM_KAPSAMA_ORANI = 0.5   guc izinin altinda toprak dokumu orani alt siniri
  DONGU_CARPANI = 2            dekuplaj dongusu <= 2 x TI SBAA113 mesafesi
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from .. import geom, ipc2221
from ..devre.graf import DevreGrafi
from ..rules import Finding
from .sonuc import SeviyeSonucu, bulgu, eksik_bulgu

KAYNAK = "pcbqa-kontrol"
KONNEKTOR_KENAR_MM = 5.0
DUZLEM_KAPSAMA_ORANI = 0.5
DONGU_CARPANI = 2.0

_SWDIO = re.compile(r"SWDIO|PA13", re.IGNORECASE)
_SWCLK = re.compile(r"SWCLK|PA14", re.IGNORECASE)
_NRST = re.compile(r"NRST|RESET", re.IGNORECASE)
_MONTAJ = re.compile(r"MountingHole|Mounting_Hole", re.IGNORECASE)


@dataclass
class KontrolSonucu:
    ad: str
    amac: str
    durum: str = "gecti"
    bulgular: list[Finding] = field(default_factory=list)
    olcumler: dict[str, Any] = field(default_factory=dict)
    neden: str = ""

    def sonlandir(self) -> "KontrolSonucu":
        if self.durum == "denetlenemedi":
            return self
        if any(f.severity == "error" for f in self.bulgular):
            self.durum = "kaldi"
        elif any(f.severity == "warning" for f in self.bulgular):
            self.durum = "uyari"
        elif any(f.rule_type == "eksik-bilgi" for f in self.bulgular):
            # Bir kismi denetlendi, bir kismi bilgi eksikligi yuzunden
            # denetlenemedi: "gecti" demek yanlis guven verir.
            self.durum = "kismen"
        return self

    def as_dict(self) -> dict[str, Any]:
        return {"ad": self.ad, "amac": self.amac, "durum": self.durum, "neden": self.neden,
                "bulgular": [f.as_dict() for f in self.bulgular], "olcumler": self.olcumler}


def _denetlenemedi(k: KontrolSonucu, neden: str) -> KontrolSonucu:
    k.durum = "denetlenemedi"
    k.neden = neden
    k.bulgular.append(eksik_bulgu(k.ad, neden, source=KAYNAK))
    return k


# --------------------------------------------------------------------------
# 1) sematik - PCB baglanti esligi
# --------------------------------------------------------------------------


def baglanti_esligi(g: DevreGrafi) -> KontrolSonucu:
    k = KontrolSonucu("baglanti-esligi", "PCB'nin hedef devreyle ayni baglantilari tasimasi")
    if g.board is None:
        return _denetlenemedi(k, "kart yok")
    if "netlist" not in g.kaynaklar:
        return _denetlenemedi(k, "sematik netlist yok; baglanti kartin kendisinden okundu, karsilastirilacak hedef yok")

    sch_to_pcb: dict[str, set[str]] = {}
    pcb_to_sch: dict[str, set[str]] = {}
    padsiz = []
    for b in g.bilesenler.values():
        if b.pcb is None:
            continue
        for p in b.pinler.values():
            if not p.ag or not p.padler:
                continue
            for pad in p.padler:
                if not pad.ag:
                    padsiz.append(p.tam)
                    continue
                sch_to_pcb.setdefault(p.ag, set()).add(pad.ag)
                pcb_to_sch.setdefault(pad.ag, set()).add(p.ag)
    for sch, pcbs in sorted(sch_to_pcb.items()):
        if len(pcbs) > 1:
            k.bulgular.append(bulgu("baglanti-esligi", "error",
                                    f"sematik agi {sch} kartta {len(pcbs)} aga bolunmus: {', '.join(sorted(pcbs))}",
                                    source=KAYNAK))
    for pcb, schs in sorted(pcb_to_sch.items()):
        if len(schs) > 1:
            k.bulgular.append(bulgu("baglanti-esligi", "error",
                                    f"kart agi {pcb} {len(schs)} sematik agini birlestiriyor (kisa devre): "
                                    f"{', '.join(sorted(schs))}", source=KAYNAK))
    if padsiz:
        k.bulgular.append(bulgu("baglanti-esligi", "warning",
                                f"sematikte bagli ama kartta agsiz {len(padsiz)} pad: {', '.join(sorted(padsiz)[:10])} "
                                "(kart sematikten guncellenmemis olabilir)", source=KAYNAK))
    yalniz_sch = sorted(r for r, b in g.bilesenler.items() if b.pcb is None and not b.dnp)
    yalniz_pcb = sorted(r for r, b in g.bilesenler.items() if not b.sematikte)
    if yalniz_sch:
        k.bulgular.append(bulgu("baglanti-esligi", "error", f"sematikte var, kartta yok: {', '.join(yalniz_sch)}",
                                source=KAYNAK, refs=yalniz_sch))
    if yalniz_pcb:
        k.bulgular.append(bulgu("baglanti-esligi", "warning", f"kartta var, sematikte yok: {', '.join(yalniz_pcb)}",
                                source=KAYNAK, refs=yalniz_pcb))
    k.olcumler = {"sematik_ag": len(sch_to_pcb), "kart_ag": len(pcb_to_sch)}
    return k.sonlandir()


# --------------------------------------------------------------------------
# 2) sembol - footprint - model pin esligi
# --------------------------------------------------------------------------


def _ad_norm(ad: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (ad or "").upper())


def pin_esligi(g: DevreGrafi) -> KontrolSonucu:
    k = KontrolSonucu("pin-esligi", "pin numarasi ya da model baglantisi hatalarini bulmak")
    denetlenen = 0
    for b in sorted(g.bilesenler.values(), key=lambda x: x.ref):
        # (a) sembol pini <-> footprint padi
        if b.pcb is not None and b.sematikte and g.board is not None:
            comp = g.board.by_ref(b.ref)
            pad_no = {p.number for p in comp.pads if p.number} if comp else set()
            sembol_no = set(b.pinler)
            eksik_pad = sorted(n for n in sembol_no - pad_no if b.pinler[n].tip != "no_connect")
            fazla_pad = sorted(pad_no - sembol_no)
            if eksik_pad:
                k.bulgular.append(bulgu("pin-esligi", "error",
                                        f"{b.ref}: sembol pinleri {', '.join(eksik_pad)} footprint'te yok "
                                        f"({b.footprint})", source=KAYNAK, refs=[b.ref]))
            if fazla_pad:
                bagli = [n for n in fazla_pad
                         if any(p.number == n and p.net for p in comp.pads)]
                k.bulgular.append(bulgu("pin-esligi", "warning" if bagli else "info",
                                        f"{b.ref}: footprint padleri {', '.join(fazla_pad)} sembolde yok"
                                        + (" (aga bagli!)" if bagli else " (termal/mekanik pad olabilir)"),
                                        source=KAYNAK, refs=[b.ref]))
            denetlenen += 1
        # (b) parca kaydinin pin adi <-> sembol pin adi
        for no, pb in b.parca.pinler.items():
            pin = b.pinler.get(no)
            if pin is None or not pin.ad or not pb.ad:
                continue
            a, c = _ad_norm(pin.ad), _ad_norm(pb.ad)
            if a and c and not (a.startswith(c) or c.startswith(a)):
                k.bulgular.append(bulgu("pin-esligi", "error",
                                        f"{b.ref} pin {no}: sembolde {pin.ad!r}, parca veri kaydinda {pb.ad!r} "
                                        f"({b.parca.kutuphane_kaydi}) - sembol yanlis parcaya ait olabilir",
                                        source=KAYNAK, refs=[b.ref], pins=[pin.tam]))
        # (c) SPICE modeli pin eslemesi
        sp = b.parca.spice
        # Davranissal modeller pinlere rol uzerinden baglanir; esleme yalnizca
        # beyan edildiyse (ya da uretici altdevresiyse) denetlenir.
        if sp is not None and (sp.tur == "altdevre" or sp.pin_esleme):
            eslenmemis = [d for d in sp.dugumler if d not in sp.pin_esleme.values()]
            olmayan = [no for no in sp.pin_esleme if no not in b.pinler]
            if eslenmemis:
                k.bulgular.append(bulgu("model-pin-esligi", "error",
                                        f"{b.ref}: model dugumleri {', '.join(eslenmemis)} hicbir pine eslenmemis",
                                        source=KAYNAK, refs=[b.ref]))
            if olmayan:
                k.bulgular.append(bulgu("model-pin-esligi", "error",
                                        f"{b.ref}: model eslemesindeki pinler {', '.join(olmayan)} sembolde yok",
                                        source=KAYNAK, refs=[b.ref]))
            for no, dugum in sp.pin_esleme.items():
                pin = b.pinler.get(no)
                pb = b.parca.pinler.get(no)
                if pin and pb and pb.islev == "gnd" and pin.ag and not g.toprak_mi(pin.ag):
                    k.bulgular.append(bulgu("model-pin-esligi", "warning",
                                            f"{b.ref}: model {dugum} (GND) pini {pin.ag} agina bagli",
                                            source=KAYNAK, refs=[b.ref], pins=[pin.tam]))
    k.olcumler["denetlenen_bilesen"] = denetlenen
    if denetlenen == 0 and not k.bulgular:
        return _denetlenemedi(k, "hem sembol pin listesi hem kart gerekir")
    return k.sonlandir()


# --------------------------------------------------------------------------
# 3-4) yuklenme ve termal - seviye 2 / iz analizi bulgularini toplar
# --------------------------------------------------------------------------


def bilesen_yuklenmesi(g: DevreGrafi) -> KontrolSonucu:
    from .seviye2 import _ayrik_gerilimler, kontrol_regulator, kontrol_yuklenme

    k = KontrolSonucu("bilesen-yuklenmesi", "guc, gerilim, akim ve calisma sinirlari")
    k.bulgular += kontrol_yuklenme(g)
    k.bulgular += _ayrik_gerilimler(g)
    k.bulgular += [f for f in kontrol_regulator(g) if f.rule_id != "regulator-termal"]
    return k.sonlandir()


def termal(g: DevreGrafi, iz_sonucu: SeviyeSonucu | None = None) -> KontrolSonucu:
    from .seviye2 import kontrol_regulator

    k = KontrolSonucu("termal", "uygun modellerle bilesen ve bakir isinmasi")
    reg = [f for f in kontrol_regulator(g) if f.rule_id == "regulator-termal"]
    k.bulgular += reg
    if iz_sonucu is not None and iz_sonucu.calisti:
        en_sicak = 0.0
        for ozet in iz_sonucu.ekler.get("aglar", {}).values():
            for kenar in ozet.get("kenarlar", []):
                en_sicak = max(en_sicak, kenar.get("sicaklik_artisi_c", 0.0))
        k.olcumler["en_sicak_iz_artisi_c"] = round(en_sicak, 2)
        k.bulgular += [f for f in iz_sonucu.bulgular if f.rule_id in ("iz-darbogaz", "iz-pad-cikisi", "iz-darbe")]
    elif iz_sonucu is not None:
        k.bulgular.append(eksik_bulgu("termal", f"bakir isinmasi: {iz_sonucu.atlanma_nedeni}", source=KAYNAK))
    if not reg and not g.rolle("regulator"):
        k.olcumler["not"] = "regulator yok"
    return k.sonlandir()


# --------------------------------------------------------------------------
# 5) koruma koordinasyonu
# --------------------------------------------------------------------------


def _ag_yuku(g: DevreGrafi, ag: str) -> float | None:
    from ..pcb_akim import akim_dagilimi

    kayit = akim_dagilimi(g).get(g.ag(ag).ad if g.ag(ag) else ag)
    return kayit.toplam_a if kayit and kayit.noktalar else None


def koruma_koordinasyonu(g: DevreGrafi) -> KontrolSonucu:
    k = KontrolSonucu("koruma-koordinasyonu", "sigorta, koruma elemani ve korunacak parcanin uyumu")
    sigortalar = g.rolle("sigorta")
    tvsler = g.rolle("tvs")
    for b, rol in sigortalar:
        anma = b.parca.sinir("akim")
        uclar = [a for a in rol.aglar.values() if a]
        giris = next((a for a in uclar if any(r.rol("guc-girisi") for r in g.bilesenler_on(a))
                      or g.kosullar.kaynak_mi(a)), None)
        cikis = next((a for a in uclar if a != giris), None)
        if anma is None or anma.onerilen_max is None:
            k.bulgular.append(eksik_bulgu(k.ad, f"{b.ref}: sigorta anma akimi bilinmiyor", source=KAYNAK, refs=[b.ref]))
            continue
        if cikis is None:
            continue
        yuk = _ag_yuku(g, cikis)
        if yuk is not None and yuk > anma.onerilen_max:
            k.bulgular.append(bulgu("koruma-koordinasyonu", "error",
                                    f"{b.ref} {anma.onerilen_max:g} A; korunan agin ({cikis}) normal yuku {yuk:g} A - "
                                    "sigorta normal calismada atar", source=KAYNAK, refs=[b.ref],
                                    measured=yuk, limit=anma.onerilen_max))
        # Korunan bakir: cikis agindaki en ince iz sigortadan once dayanmali
        a = g.ag(cikis)
        if a and a.min_iz_genisligi_mm:
            kap = ipc2221.current_capacity_a(a.min_iz_genisligi_mm,
                                             float(g.kosullar.pcb.get("dT_c") or 10.0),
                                             float(g.kosullar.pcb.get("bakir_oz") or 1.0))
            if anma.onerilen_max > kap:
                k.bulgular.append(bulgu("koruma-koordinasyonu", "error",
                                        f"{b.ref} {anma.onerilen_max:g} A > korunan agin en ince izinin "
                                        f"({a.min_iz_genisligi_mm:g} mm) tasima kapasitesi {kap:.2f} A - "
                                        "iz sigortadan once isinir", source=KAYNAK, refs=[b.ref],
                                        measured=anma.onerilen_max, limit=kap))
        for c in g.bilesenler_on(cikis, "connector"):
            s = c.parca.sinir("akim")
            if s and s.onerilen_max is not None and anma.onerilen_max > s.onerilen_max:
                k.bulgular.append(bulgu("koruma-koordinasyonu", "error",
                                        f"{b.ref} {anma.onerilen_max:g} A > {c.ref} pin siniri {s.onerilen_max:g} A",
                                        source=KAYNAK, refs=[b.ref, c.ref]))
    for b, rol in tvsler:
        vr = b.parca.sinir("vrwm")
        ray = next((a for a in rol.aglar.values() if a and not g.toprak_mi(a)), None)
        if ray is None:
            continue
        rv = g.kosullar.ray(ray)
        v = rv.en_yuksek if rv else (g.gerilim(ray).deger if g.gerilim(ray).bilinen else None)
        if vr is None or vr.onerilen_max is None or v is None:
            k.bulgular.append(eksik_bulgu(k.ad, f"{b.ref}: TVS stand-off ya da ray gerilimi bilinmiyor",
                                          source=KAYNAK, refs=[b.ref]))
            continue
        if vr.onerilen_max < v:
            k.bulgular.append(bulgu("koruma-koordinasyonu", "error",
                                    f"{b.ref} stand-off {vr.onerilen_max:g} V < ray {v:g} V - TVS normal "
                                    "calismada iletir", source=KAYNAK, refs=[b.ref], measured=v, limit=vr.onerilen_max))
        from .seviye2 import _pin_siniri

        for c in g.bilesenler_on(ray, "ic"):
            for p in c.pinler.values():
                if p.ag != ray:
                    continue
                s = _pin_siniri(c, p)
                if s and s[0] is not None and vr.onerilen_max > s[0]:
                    k.bulgular.append(bulgu("koruma-koordinasyonu", "warning",
                                            f"{b.ref} stand-off {vr.onerilen_max:g} V, korunan {p.gorunen} mutlak "
                                            f"maks {s[0]:g} V'un ustunde; kenetleme gerilimi daha da yuksek",
                                            source=KAYNAK, refs=[b.ref, c.ref]))
    if not sigortalar and not tvsler:
        girisler = [b.ref for b, _ in g.rolle("guc-girisi")]
        if girisler:
            k.bulgular.append(bulgu("koruma-koordinasyonu", "info",
                                    f"guc girisinde ({', '.join(girisler)}) sigorta/TVS yok - koruma gereksinimi "
                                    "urune bagli, bilincli secim olduguna emin olun", source=KAYNAK))
        k.olcumler["koruma_elemani"] = 0
    return k.sonlandir()


# --------------------------------------------------------------------------
# 6) donus yolu ve kritik donguler
# --------------------------------------------------------------------------


def _komsu_katman(katman: str, bakir: list[str]) -> str | None:
    if katman not in bakir:
        return None
    i = bakir.index(katman)
    if i + 1 < len(bakir):
        return bakir[i + 1]
    return bakir[i - 1] if i > 0 else None


def donus_yolu(g: DevreGrafi) -> KontrolSonucu:
    k = KontrolSonucu("donus-yolu", "guc ve sinyal akimlarinin uygun yoldan donmesi")
    if g.board is None:
        return _denetlenemedi(k, "kart yok")
    board = g.board
    katmanlar = {t.layer for t in board.tracks} | {lyr for z in board.zones for lyr in z.layers}
    bakir = sorted((lyr for lyr in katmanlar if lyr.endswith(".Cu")),
                   key=lambda s: (0 if s == "F.Cu" else 2 if s == "B.Cu" else 1, s))
    toprak_dokum = [z for z in board.zones if g.toprak_mi(z.net)]

    # (a) yuklu aglarin altinda toprak duzlemi
    from ..pcb_akim import akim_dagilimi

    yuklu = [ad for ad, kayit in akim_dagilimi(g).items() if kayit.toplam_a > 0 and not g.toprak_mi(ad)]
    for ad in yuklu:
        izler = [t for t in board.tracks if t.net == ad]
        if not izler:
            continue
        if not toprak_dokum:
            k.bulgular.append(bulgu("donus-yolu", "warning",
                                    f"{ad} yuk akimi tasiyor ama kartta toprak dokumu yok - donus akimi izden "
                                    "doner, dongu alani buyur", source=KAYNAK))
            break
        ortulu = toplam = 0.0
        for t in izler:
            komsu = _komsu_katman(t.layer, bakir) or t.layer
            orta = ((t.x1 + t.x2) / 2, (t.y1 + t.y2) / 2)
            toplam += t.length_mm
            for z in toprak_dokum:
                polys = [f.points for f in z.fills if f.layer == komsu] or \
                        ([z.outline] if komsu in z.layers else [])
                if any(p and geom.contains(p, orta) for p in polys):
                    ortulu += t.length_mm
                    break
        oran = ortulu / toplam if toplam else 0.0
        k.olcumler[f"{ad}_toprak_kapsama"] = round(oran, 3)
        if oran < DUZLEM_KAPSAMA_ORANI:
            k.bulgular.append(bulgu("donus-yolu", "warning",
                                    f"{ad} izlerinin yalnizca %{oran * 100:.0f}'i komsu katmanda toprak dokumu "
                                    f"uzerinde (< %{DUZLEM_KAPSAMA_ORANI * 100:.0f}, muhendislik secimi)",
                                    source=KAYNAK, measured=oran, limit=DUZLEM_KAPSAMA_ORANI))

    # (b) dekuplaj dongusu: IC guc pini -> C -> IC toprak pini
    sinir = DONGU_CARPANI * ipc2221.DECOUPLING_MAX_MM
    for c, rol in g.rolle("dekuplaj"):
        ray = rol.aglar.get("ray")
        c_ray = next((p for p in c.pinler.values() if p.ag == ray and p.padler), None)
        c_gnd = next((p for p in c.pinler.values() if p.ag and g.toprak_mi(p.ag) and p.padler), None)
        if not (c_ray and c_gnd):
            continue
        en_iyi = None
        for hedef in rol.hedefler:
            ref, _, no = hedef.partition(".")
            ic = g.bilesenler.get(ref)
            ip = g.pin(ref, no)
            if ic is None or ip is None or not ip.padler:
                continue
            gnd = [p for p in ic.pinler.values() if p.ag and g.toprak_mi(p.ag) and p.padler]
            if not gnd:
                continue
            d1 = math.hypot(ip.padler[0].x - c_ray.padler[0].x, ip.padler[0].y - c_ray.padler[0].y)
            d2 = min(math.hypot(q.padler[0].x - c_gnd.padler[0].x, q.padler[0].y - c_gnd.padler[0].y) for q in gnd)
            dongu = d1 + d2
            en_iyi = dongu if en_iyi is None else min(en_iyi, dongu)
        if en_iyi is not None:
            k.olcumler[f"{c.ref}_dongu_mm"] = round(en_iyi, 3)
            if en_iyi > sinir:
                k.bulgular.append(bulgu("kritik-dongu", "warning",
                                        f"{c.ref} dekuplaj dongusu (guc pini->C->toprak pini) {en_iyi:.1f} mm > "
                                        f"{sinir:.1f} mm ({DONGU_CARPANI:g} x TI SBAA113)",
                                        source=KAYNAK, refs=[c.ref] + [h.split('.')[0] for h in rol.hedefler],
                                        measured=en_iyi, limit=sinir))

    # (c) yukun toprak pini kaynagin toprak pinine bakirla ulasiyor mu
    if board.tracks or board.zones:
        from ..pcb_akim import _bagli_bilesen, bakir_agi_kur

        for ad, kayit in akim_dagilimi(g).items():
            if not g.toprak_mi(ad) or not kayit.noktalar:
                continue
            if any(z.net == ad for z in board.zones):
                continue  # dokum varsa baglantiyi KiCad'in DRC'si (unconnected) denetler
            agi = bakir_agi_kur(board, ad, g.kosullar.pcb)
            kok = agi.pad_dugumu.get(kayit.noktalar[0].pin)
            if kok is None:
                continue
            bagli = _bagli_bilesen(agi.dugum_sayisi, agi.kenarlar, kok)
            kopuk = [n.pin for n in kayit.noktalar if agi.pad_dugumu.get(n.pin) not in bagli]
            if kopuk:
                k.bulgular.append(bulgu("donus-yolu", "error",
                                        f"{ad}: donus akimi noktalari {', '.join(kopuk)} kaynaga bakirla baglanmiyor",
                                        source=KAYNAK))
    if not yuklu and not g.rolle("dekuplaj"):
        neden = ("yuk akimi hicbir pine atanamadi (kosullar.yukler icinde ref/pin verin)"
                 if g.kosullar.yukler else "yuk akimi beyan edilmedi")
        return _denetlenemedi(k, neden + " ve dekuplaj rolunde kondansator yok")
    return k.sonlandir()


# --------------------------------------------------------------------------
# 7) uretilebilirlik
# --------------------------------------------------------------------------


def uretilebilirlik(g: DevreGrafi) -> KontrolSonucu:
    k = KontrolSonucu("uretilebilirlik", "secilen ureticinin yol, bosluk, delik ve diger sinirlarina uyum")
    if g.board is None:
        return _denetlenemedi(k, "kart yok")
    ad = str(g.kosullar.pcb.get("uretici") or "standart")
    fab = ipc2221.FAB_CLASSES.get(ad)
    if fab is None:
        return _denetlenemedi(k, f"bilinmeyen uretici profili {ad!r}; {sorted(ipc2221.FAB_CLASSES)}")
    board = g.board
    k.olcumler["profil"] = fab.name
    ince = [t for t in board.tracks if t.width + 1e-9 < fab.min_track_mm]
    if ince:
        t = min(ince, key=lambda t: t.width)
        k.bulgular.append(bulgu("uretim-iz", "error",
                                f"{len(ince)} iz parcasi {fab.min_track_mm:g} mm'den ince (en ince {t.width:g} mm, "
                                f"{t.net}, {t.layer})", source=KAYNAK, measured=t.width, limit=fab.min_track_mm))
    for v in board.vias:
        halka = (v.size - v.drill) / 2
        if v.drill + 1e-9 < fab.min_drill_mm:
            k.bulgular.append(bulgu("uretim-delik", "error",
                                    f"via ({v.x:.2f}, {v.y:.2f}) delik {v.drill:g} mm < {fab.min_drill_mm:g} mm",
                                    source=KAYNAK, measured=v.drill, limit=fab.min_drill_mm))
        if halka + 1e-9 < fab.min_annular_ring_mm:
            k.bulgular.append(bulgu("uretim-halka", "error",
                                    f"via ({v.x:.2f}, {v.y:.2f}) halka {halka:.3f} mm < {fab.min_annular_ring_mm:g} mm",
                                    source=KAYNAK, measured=halka, limit=fab.min_annular_ring_mm))
    for c in board.components:
        for p in c.pads:
            if p.drill <= 0:
                continue
            if p.drill + 1e-9 < fab.min_drill_mm:
                k.bulgular.append(bulgu("uretim-delik", "error",
                                        f"{c.ref}.{p.number} delik {p.drill:g} mm < {fab.min_drill_mm:g} mm",
                                        source=KAYNAK, refs=[c.ref], measured=p.drill, limit=fab.min_drill_mm))
            if p.kind == "thru_hole":
                halka = (min(p.size_x, p.size_y) - p.drill) / 2
                if halka + 1e-9 < fab.min_annular_ring_mm:
                    k.bulgular.append(bulgu("uretim-halka", "error",
                                            f"{c.ref}.{p.number} halka {halka:.3f} mm < {fab.min_annular_ring_mm:g} mm",
                                            source=KAYNAK, refs=[c.ref], measured=halka,
                                            limit=fab.min_annular_ring_mm))
    if board.outline:
        x0, y0, x1, y1 = board.outline
        en_yakin = None
        for t in board.tracks:
            for x, y in ((t.x1, t.y1), (t.x2, t.y2)):
                d = min(x - x0, x1 - x, y - y0, y1 - y) - t.width / 2
                en_yakin = d if en_yakin is None else min(en_yakin, d)
        if en_yakin is not None:
            k.olcumler["iz_kenar_min_mm"] = round(en_yakin, 3)
            if en_yakin + 1e-9 < fab.min_edge_clearance_mm:
                k.bulgular.append(bulgu("uretim-kenar", "error",
                                        f"bakir kart kenarina {en_yakin:.3f} mm (< {fab.min_edge_clearance_mm:g} mm; "
                                        "kenar sinir kutusuyla yaklasik)", source=KAYNAK,
                                        measured=en_yakin, limit=fab.min_edge_clearance_mm))
    # farkli aglarin izleri arasi aciklik (sinir kutusu on elemeli)
    izler = board.tracks
    ihlal = 0
    en_kucuk = None
    for i, a in enumerate(izler):
        ax0, ax1 = sorted((a.x1, a.x2))
        ay0, ay1 = sorted((a.y1, a.y2))
        for b in izler[i + 1:]:
            if a.net == b.net or a.layer != b.layer:
                continue
            pay = fab.min_clearance_mm + (a.width + b.width) / 2
            bx0, bx1 = sorted((b.x1, b.x2))
            by0, by1 = sorted((b.y1, b.y2))
            if bx0 > ax1 + pay or ax0 > bx1 + pay or by0 > ay1 + pay or ay0 > by1 + pay:
                continue
            d = geom.segment_distance((a.x1, a.y1), (a.x2, a.y2), (b.x1, b.y1), (b.x2, b.y2)) - (a.width + b.width) / 2
            en_kucuk = d if en_kucuk is None else min(en_kucuk, d)
            if d + 1e-9 < fab.min_clearance_mm:
                ihlal += 1
    if en_kucuk is not None:
        k.olcumler["iz_iz_min_aciklik_mm"] = round(en_kucuk, 4)
    if ihlal:
        k.bulgular.append(bulgu("uretim-aciklik", "error",
                                f"{ihlal} iz cifti {fab.min_clearance_mm:g} mm acikligin altinda (en kucuk {en_kucuk:.3f} mm)",
                                source=KAYNAK, measured=en_kucuk, limit=fab.min_clearance_mm))
    if not board.tracks:
        k.bulgular.append(eksik_bulgu(k.ad, "kart yonlendirilmemis - iz ve aciklik denetimi yapilamadi",
                                      source=KAYNAK))
    return k.sonlandir()


# --------------------------------------------------------------------------
# 8) mekanik ve montaj
# --------------------------------------------------------------------------


def _govde(c) -> list[tuple[float, float]]:
    if c.courtyard_poly:
        return c.courtyard_poly
    box = c.pad_bbox
    if box is None:
        return [(c.x, c.y)]
    x0, y0, x1, y1 = box
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def mekanik_montaj(g: DevreGrafi) -> KontrolSonucu:
    k = KontrolSonucu("mekanik-montaj", "kart siniri, montaj delikleri, konnektor erisimi ve cakismalar")
    if g.board is None:
        return _denetlenemedi(k, "kart yok")
    board = g.board
    if not board.outline:
        k.bulgular.append(bulgu("mekanik-sinir", "error", "kart siniri (Edge.Cuts) yok", source=KAYNAK))
        return k.sonlandir()
    x0, y0, x1, y1 = board.outline

    def disarida_mi(x, y):
        return x < x0 - 1e-6 or x > x1 + 1e-6 or y < y0 - 1e-6 or y > y1 + 1e-6

    pad_disarida, govde_tasan = [], []
    for c in board.components:
        if any(disarida_mi(p.x, p.y) for p in c.pads):
            pad_disarida.append(c.ref)
        elif any(disarida_mi(x, y) for x, y in _govde(c)):
            govde_tasan.append(c.ref)
    if pad_disarida:
        k.bulgular.append(bulgu("mekanik-sinir", "error",
                                f"padi kart sinirinin disinda kalan: {', '.join(pad_disarida)}",
                                source=KAYNAK, refs=pad_disarida))
    konn = [r for r in govde_tasan if r.upper().startswith(("J", "P", "CN"))]
    diger = [r for r in govde_tasan if r not in konn]
    if konn:
        k.bulgular.append(bulgu("mekanik-sinir", "info",
                                f"govdesi kenardan tasan konnektorler (kenar konnektoru icin olagan): "
                                f"{', '.join(konn)}", source=KAYNAK, refs=konn))
    if diger:
        k.bulgular.append(bulgu("mekanik-sinir", "warning",
                                f"courtyard'i kart sinirindan tasan: {', '.join(diger)}",
                                source=KAYNAK, refs=diger))
    montaj = [c.ref for c in board.components if _MONTAJ.search(c.footprint_id)
              or re.match(r"^(MH|H)\d+$", c.ref)]
    k.olcumler["montaj_deligi"] = len(montaj)
    if not montaj:
        k.bulgular.append(bulgu("montaj-deligi", "warning", "kartta montaj deligi yok", source=KAYNAK))
    for c in board.components:
        if not c.ref.upper().startswith(("J", "P", "CN")) or _MONTAJ.search(c.footprint_id):
            continue
        govde = _govde(c)
        mesafe = min(min(x - x0, x1 - x, y - y0, y1 - y) for x, y in govde)
        k.olcumler[f"{c.ref}_kenar_mm"] = round(mesafe, 3)
        if mesafe > KONNEKTOR_KENAR_MM:
            k.bulgular.append(bulgu("konnektor-erisimi", "warning",
                                    f"{c.ref} kart kenarina {mesafe:.1f} mm uzakta (> {KONNEKTOR_KENAR_MM:g} mm, "
                                    "muhendislik secimi) - kablo/fis erisimi", source=KAYNAK, refs=[c.ref],
                                    measured=mesafe, limit=KONNEKTOR_KENAR_MM))
    comps = [c for c in board.components if c.courtyard_poly]
    for i, a in enumerate(comps):
        for b in comps[i + 1:]:
            if a.layer != b.layer:
                continue
            if geom.overlap(a.courtyard_poly, b.courtyard_poly):
                k.bulgular.append(bulgu("cakisma", "warning", f"{a.ref} ile {b.ref} courtyard'lari cakisiyor",
                                        source=KAYNAK, refs=[a.ref, b.ref]))
    return k.sonlandir()


# --------------------------------------------------------------------------
# 9) test edilebilirlik
# --------------------------------------------------------------------------


def test_edilebilirlik(g: DevreGrafi) -> KontrolSonucu:
    k = KontrolSonucu("test-edilebilirlik", "gerekli olcum noktalari ve programlama baglantilari")
    erisim_tur = ("testpoint", "connector")

    def erisilebilir(ag: str) -> bool:
        a = g.ag(ag)
        return bool(a) and any(g.bilesenler[p.ref].tur in erisim_tur for p in a.pinler)

    raylar = [a.ad for a in g.aglar.values() if g.ray_mi(a.ad) and len(a.pinler) > 1]
    erisimsiz = [r for r in raylar if not erisilebilir(r)]
    k.olcumler["ray"] = len(raylar)
    k.olcumler["olculebilir_ray"] = len(raylar) - len(erisimsiz)
    if erisimsiz:
        k.bulgular.append(bulgu("olcum-noktasi", "warning",
                                f"test noktasi ya da konnektor pini olmayan raylar: {', '.join(sorted(erisimsiz))}",
                                source=KAYNAK))
    topraklar = [a.ad for a in g.aglar.values() if a.toprak]
    if topraklar and not any(erisilebilir(t) for t in topraklar):
        k.bulgular.append(bulgu("olcum-noktasi", "warning", "toprak icin erisilebilir olcum noktasi yok",
                                source=KAYNAK))
    mculer = g.kategoride("mcu")
    for m in mculer:
        swd = {"SWDIO": None, "SWCLK": None}
        for p in m.pinler.values():
            for ad_, desen in (("SWDIO", _SWDIO), ("SWCLK", _SWCLK)):
                if desen.search(p.ad or "") or desen.search(p.ag or ""):
                    swd[ad_] = p.ag
        eksik = [ad_ for ad_, ag in swd.items() if not ag or not erisilebilir(ag)]
        if eksik:
            k.bulgular.append(bulgu("programlama", "warning",
                                    f"{m.ref} programlama hatlari ({', '.join(eksik)}) bir konnektore/test "
                                    "noktasina ulasmiyor", source=KAYNAK, refs=[m.ref]))
        nrst = next((p.ag for p in m.pinler.values() if _NRST.search(p.ad or "")), None)
        if nrst and not erisilebilir(nrst):
            k.bulgular.append(bulgu("programlama", "info", f"{m.ref} NRST bir konnektore ulasmiyor "
                                    "(bazi programlayicilar ister)", source=KAYNAK, refs=[m.ref]))
    k.olcumler["mcu"] = len(mculer)
    return k.sonlandir()


# --------------------------------------------------------------------------


def dokuz_kontrol(g: DevreGrafi, iz_sonucu: SeviyeSonucu | None = None) -> list[KontrolSonucu]:
    return [
        baglanti_esligi(g),
        pin_esligi(g),
        bilesen_yuklenmesi(g),
        termal(g, iz_sonucu),
        koruma_koordinasyonu(g),
        donus_yolu(g),
        uretilebilirlik(g),
        mekanik_montaj(g),
        test_edilebilirlik(g),
    ]
