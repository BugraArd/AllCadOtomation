"""Bir tasarimi GERCEK kontrollerden gecirir ve tek bir duruma indirger.

Kontroller (hepsi var olan pcbqa kodu; burada yalnizca toplanir):

  benzetim      seviye3 - ngspice calisti mi (yan surec, KiCad'in DLL'i)
  gereksinim    seviye3 - cikis gerilimi tum senaryo + capraz koselerde
                pencere icinde mi
  direnc-gucu   seviye3 (benzetimin gerilimleriyle) + seviye2 (beyan araligi)
  direnc-gerilimi  uclar arasi en kotu gerilim <= azami calisma gerilimi
                (kapali form koseleri, benzetimle uyumu dogrulanmis; Kicad-7cb).
                Sinir bilinmiyorsa denetlenemedi (veri-model).
  paket-uyumu   YALNIZCA direncte MPN varsa: MPN'in paketi footprint'le ayni
                mi, MPN sembol degeri/toleransiyla celisiyor mu, parca
                ureticinin katalogunda var mi (Kicad-7cb: pad/footprint
                uyusmazligi ayri bir hata nedenidir). MPN yoksa kontrol listeye
                girmez ve neden "belirsiz" kalir.
  pcb-cakisma   mekanik_montaj - direncin courtyard'i komsusuyla cakisiyor mu
                (gercek KiCad footprint geometrisi)
  pcb-sinir     mekanik_montaj - pad / courtyard kart sinirinin disinda mi
  parite        baglanti_esligi - kart netlist'le ayni baglantiyi tasiyor mu
  pcb-iz        YALNIZCA kart yonlendirilmisse (iz varsa): pcb_akim.iz_analizi -
                bolucu kol akimlariyla iz genisligi (IPC-2221B), gerilim dusumu,
                darbogaz (Kicad-ecd). Iz yoksa kontrol listesine girmez
                (yonlendirilmemis kullanici projesi icin geriye uyum); gercek
                proje hattinda (proje.py) bagsiz kart DRC'de zaten kalir.

Durumlar - BIRBIRINE KARISTIRILMAZ (kullanici talimati):

  gecerli        butun zorunlu kontroller calisti ve gecti
  gecersiz       en az bir zorunlu kontrol ELEKTRIKSEL/FIZIKSEL olarak kaldi
  denetlenemedi  bir kontrol calisamadi: ngspice yok/yakinsamadi, parca
                 bilgisi eksik (tolerans, anma gucu), bolucu taninmadi,
                 benzetim ile el hesabi uyusmadi. Bu bir tasarim hatasi
                 DEGILDIR; egitim etiketine "gecersiz" diye girmez.
                 `eksik_turu` nedenini ayirir: "veri-model" (parca bilgisi,
                 bolucu taninmadi, kart yok) ya da "arac" (ngspice yok /
                 yakinsamadi, benzetim el hesabiyla uyusmadi).

`ihlaller` her hata/uyarinin kararli imzasidir; bir duzeltmenin YENI
ihlallerini bulmak icin hatali tasarimin imzalariyla farki alinir.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..dogrulama.kontroller import baglanti_esligi, mekanik_montaj
from ..dogrulama.seviye2 import seviye2
from ..dogrulama.seviye3 import seviye3
from ..rules import Finding
from .bolucu import Bolucu, analitik, bolucu_bul, ek_senaryo_uretici, kol_akimlari, uyum
from .tasarim import Tasarim

ZORUNLU = ("benzetim", "gereksinim", "direnc-gucu", "pcb-cakisma", "pcb-sinir", "parite")
_SIM_CALISMADI = {"benzetim-calismadi", "benzetim-hatasi"}


@dataclass
class Degerlendirme:
    durum: str
    kontroller: dict[str, str] = field(default_factory=dict)
    nedenler: list[str] = field(default_factory=list)
    ihlaller: list[str] = field(default_factory=list)
    hatalar: list[str] = field(default_factory=list)
    olcumler: dict[str, Any] = field(default_factory=dict)
    analitik: dict[str, Any] = field(default_factory=dict)
    uyum: dict[str, Any] = field(default_factory=dict)
    bolucu: dict[str, str] | None = None
    simulasyon: int = 0
    sure_s: float = 0.0
    eksik_turu: str = ""        # denetlenemedi icin: "veri-model" | "arac"

    def as_dict(self) -> dict[str, Any]:
        return {
            "durum": self.durum, "kontroller": dict(self.kontroller),
            "nedenler": list(self.nedenler), "ihlaller": list(self.ihlaller),
            "hatalar": list(self.hatalar), "olcumler": dict(self.olcumler),
            "analitik": dict(self.analitik), "uyum": dict(self.uyum),
            "bolucu": self.bolucu, "simulasyon": self.simulasyon,
            "sure_s": round(self.sure_s, 3), "eksik_turu": self.eksik_turu,
        }

    @classmethod
    def from_dict(cls, ham: dict[str, Any]) -> "Degerlendirme":
        return cls(**{k: ham[k] for k in cls.__dataclass_fields__ if k in ham})


def imza(f: Finding) -> str:
    yon = ""
    if f.rule_id == "gereksinim-gerilim" and f.measured is not None and f.limit is not None:
        yon = "alt" if f.measured < f.limit else "ust"
    return f"{f.rule_id}|{','.join(sorted(f.refs))}|{f.severity}{('|' + yon) if yon else ''}"


def _ilgili(f: Finding, refler: set[str]) -> bool:
    return not f.refs or bool(set(f.refs) & refler)


def degerlendir(
    t: Tasarim,
    *,
    benzetim: Callable[..., Any] = seviye3,
    calisma_kok: Path | None = None,
    bolucu: Bolucu | None = None,
) -> Degerlendirme:
    """`benzetim` enjekte edilebilir: birim testleri sahte seviye3 verir,
    entegrasyon testleri gercek ngspice'i kullanir."""
    bas = time.perf_counter()
    g = t.graf()
    if bolucu is None:
        bolucular = bolucu_bul(g)
        if not bolucular:
            return Degerlendirme("denetlenemedi", {k: "denetlenemedi" for k in ZORUNLU},
                                 ["bolucu taninmadi (gereksinimli cikis aginda iki direnc yok)"],
                                 sure_s=time.perf_counter() - bas, eksik_turu="veri-model")
        bolucu = bolucular[0]
    refler = {bolucu.ust, bolucu.alt}
    an = analitik(g, bolucu)
    d = Degerlendirme("denetlenemedi", bolucu=bolucu.as_dict(), analitik=an.as_dict())
    if not an.hesaplanabilir:
        d.kontroller = {k: "denetlenemedi" for k in ZORUNLU}
        d.nedenler = list(an.eksikler)
        d.eksik_turu = "veri-model"
        d.sure_s = time.perf_counter() - bas
        return d

    calisma = Path(tempfile.mkdtemp(prefix="pcbqa-duzelt-", dir=calisma_kok))
    try:
        s3 = benzetim(g, calisma=calisma, ek_senaryolar=ek_senaryo_uretici(bolucu, an))
    finally:
        shutil.rmtree(calisma, ignore_errors=True)
    d.simulasyon = 1
    s2 = seviye2(g)
    mm = mekanik_montaj(g)
    pe = baglanti_esligi(g)

    bulgular = [f for f in (*s3.bulgular, *s2.bulgular, *mm.bulgular, *pe.bulgular)
                if f.severity in ("error", "warning") and f.rule_type != "eksik-bilgi"]
    d.ihlaller = sorted({imza(f) for f in bulgular})
    d.hatalar = sorted({f.message for f in bulgular if f.severity == "error"})

    k: dict[str, str] = {}
    sim_hata = [f for f in s3.bulgular if f.rule_id in _SIM_CALISMADI]
    if not s3.calisti or sim_hata:
        k["benzetim"] = "denetlenemedi"
        d.nedenler.append(s3.atlanma_nedeni or "; ".join(f.message for f in sim_hata)[:300])
    else:
        k["benzetim"] = "gecti"
    if k["benzetim"] == "gecti":
        ger = [f for f in s3.bulgular if f.rule_id == "gereksinim-gerilim" and f.severity == "error"]
        k["gereksinim"] = "kaldi" if ger else "gecti"
        guc = [f for f in (*s3.bulgular, *s2.bulgular)
               if f.rule_id in ("benzetim-direnc-gucu", "direnc-gucu") and f.severity == "error"
               and _ilgili(f, refler)]
        k["direnc-gucu"] = "kaldi" if guc else "gecti"
        ger = [f for f in s2.bulgular if f.rule_id == "direnc-gerilimi" and f.severity == "error"
               and _ilgili(f, refler)]
        if ger or an.gerilim_orani > 1.0 and an.gerilim_orani != float("inf"):
            k["direnc-gerilimi"] = "kaldi"
        elif an.gerilim_orani == float("inf"):
            k["direnc-gerilimi"] = "denetlenemedi"
            d.nedenler.append("azami calisma gerilimi bilinmiyor")
        else:
            k["direnc-gerilimi"] = "gecti"
    else:
        k["gereksinim"] = k["direnc-gucu"] = k["direnc-gerilimi"] = "denetlenemedi"
    pu = paket_uyumu(g, refler)
    if pu is not None:
        k["paket-uyumu"] = pu[0]
        d.olcumler["paket_uyumu"] = pu[1]
        if pu[0] == "denetlenemedi":
            d.nedenler.append("paket uyumu: " + "; ".join(pu[1])[:300])
    if g.board is None:
        k["pcb-cakisma"] = k["pcb-sinir"] = k["parite"] = "denetlenemedi"
        d.nedenler.append("kart yok - PCB kontrolleri yapilamadi")
    else:
        cak = [f for f in mm.bulgular if f.rule_id == "cakisma" and set(f.refs) & refler]
        k["pcb-cakisma"] = "kaldi" if cak else "gecti"
        sinir = [f for f in mm.bulgular if f.rule_id == "mekanik-sinir"
                 and f.severity in ("error", "warning") and set(f.refs) & refler]
        k["pcb-sinir"] = "kaldi" if sinir else "gecti"
        k["parite"] = "kaldi" if pe.durum == "kaldi" else ("gecti" if pe.durum in ("gecti", "uyari")
                                                             else "denetlenemedi")
        if k["parite"] == "denetlenemedi":
            d.nedenler.append(f"baglanti esligi: {pe.durum}")
        if g.board.tracks:
            iz_durum, iz_bulgular, iz_ozet = _iz_kontrolu(g, bolucu, an)
            k["pcb-iz"] = iz_durum
            bulgular += iz_bulgular
            d.ihlaller = sorted({imza(f) for f in bulgular})
            d.hatalar = sorted({f.message for f in bulgular if f.severity == "error"})
            if iz_durum == "denetlenemedi":
                d.nedenler.append("iz analizi: " + "; ".join(iz_ozet.get("notlar", []))[:300])
    d.kontroller = k

    ozet = s3.ekler.get("ag_ozeti", {})
    yuklenme = s3.ekler.get("pasif_yuklenme", {})
    cikis = ozet.get(bolucu.cikis, {})
    p1 = (yuklenme.get(bolucu.ust) or {}).get("guc_w")
    p2 = (yuklenme.get(bolucu.alt) or {}).get("guc_w")
    d.olcumler = {
        "vout_nom": cikis.get("nominal_v"), "vout_min": cikis.get("min_v"), "vout_max": cikis.get("max_v"),
        "p_ust_w": p1, "p_alt_w": p2,
        "p_ust_oran": (p1 / an.p_ust_siniri) if p1 is not None and an.p_ust_siniri else None,
        "p_alt_oran": (p2 / an.p_alt_siniri) if p2 is not None and an.p_alt_siniri else None,
        "senaryo_sayisi": s3.ekler.get("senaryo_sayisi"),
    }
    if "pcb-iz" in k:
        d.olcumler["iz"] = iz_ozet
    if k["benzetim"] == "gecti":
        d.uyum = uyum(an, ozet, yuklenme)
        if d.uyum.get("karsilastirildi") and not d.uyum.get("uyumlu"):
            # Benzetim ile el hesabi uyusmuyorsa hangisinin yanlis oldugunu
            # bilmiyoruz: kayit egitime GIRMEZ.
            d.nedenler.append("benzetim ile kapali form uyusmadi")
            d.durum = "denetlenemedi"
            d.eksik_turu = "arac"
            d.sure_s = time.perf_counter() - bas
            return d

    if any(v == "kaldi" for v in k.values()):
        d.durum = "gecersiz"
    elif all(v == "gecti" for v in k.values()):
        d.durum = "gecerli"
    else:
        d.durum = "denetlenemedi"
        # Arac (ngspice yok / yakinsamadi) mi, veri/model eksigi mi?
        d.eksik_turu = "arac" if k.get("benzetim") == "denetlenemedi" else "veri-model"
    d.sure_s = time.perf_counter() - bas
    return d


def paket_uyumu(g, refler: set[str]) -> tuple[str, list[str]] | None:
    """MPN'li direnclerde pad/footprint ve katalog tutarliligi (Kicad-7cb)."""
    from ..devre.parca import paket_kodu
    from .tasarim import MPN_KAYNAK_ALANI

    ilgili = [g.bilesenler[r] for r in sorted(refler) if r in g.bilesenler]
    mpnli = [b for b in ilgili if b.parca.mpn.bilinen or (b.alanlar.get(MPN_KAYNAK_ALANI) or "").endswith("katalog-disi")]
    if not mpnli:
        return None
    sorun, eksik = [], []
    for b in mpnli:
        pb = b.parca
        if not pb.mpn.bilinen:
            sorun.append(f"{b.ref}: katalogda karsiligi olmayan parca (MPN uretilemedi)")
            continue
        if pb.mpn_cozumu is None:
            eksik.append(f"{b.ref}: MPN {pb.mpn.deger} kutuphanede cozulemedi")
            continue
        fp = paket_kodu(b.footprint)
        if pb.mpn_cozumu["paket"] != fp:
            sorun.append(f"{b.ref}: MPN paketi {pb.mpn_cozumu['paket']} != footprint {fp or '?'}")
        sorun += [f"{b.ref}: {c}" for c in pb.celiskiler]
        if pb.katalog_disi:
            sorun.append(f"{b.ref}: {pb.katalog_disi}")
    if sorun:
        return "kaldi", sorun
    if eksik:
        return "denetlenemedi", eksik
    return "gecti", []


NEDENLER = ("gereksinim", "guc", "gerilim", "mekanik", "pad-footprint")


def neden_etiketleri(d: dict[str, Any]) -> dict[str, str]:
    """Gecersizligin AYRI nedenleri (Kicad-7cb): 'var' | 'yok' | 'belirsiz'.

    "Paket kucuk" tek basina bir neden DEGILDIR: guc dayanimi, gerilim siniri,
    mekanik uyumsuzluk (courtyard / kart siniri) ve pad/footprint uyusmazligi
    ayri ayri olculur. Gereken veri yoksa (kontrol calismadi ya da MPN yok)
    'belirsiz' - yok sayilmaz."""
    k = d.get("kontroller") or {}

    def durum(*adlar):
        v = [k.get(a) for a in adlar]
        if "kaldi" in v:
            return "var"
        if v and all(x == "gecti" for x in v):
            return "yok"
        return "belirsiz"

    return {"gereksinim": durum("gereksinim"), "guc": durum("direnc-gucu"), "gerilim": durum("direnc-gerilimi"),
            "mekanik": durum("pcb-cakisma", "pcb-sinir"), "pad-footprint": durum("paket-uyumu")}


def _iz_kontrolu(g, bolucu: Bolucu, an) -> tuple[str, list[Finding], dict[str, Any]]:
    """Yonlendirilmis kartta dal akimi / iz genisligi / gerilim dusumu."""
    from ..pcb_akim import iz_analizi

    akimlar, notlar = kol_akimlari(g, bolucu, an)
    if not akimlar:
        return "denetlenemedi", [], {"notlar": notlar}
    s = iz_analizi(g, akimlar)
    aglar = s.ekler.get("aglar", {})
    ozet = {"notlar": notlar + ([s.atlanma_nedeni] if s.atlanma_nedeni else []),
            "aglar": {ad: {"en_yuklu_kol_a": v.get("en_yuklu_kol_a"), "kayip_mw": v.get("kayip_mw"),
                           "dusum_max_mv": max((v.get("dusumler_mv") or {}).values(), default=0.0)}
                      for ad, v in aglar.items()}}
    hatalar = [f for f in s.bulgular if f.severity in ("error", "warning") and f.rule_type != "eksik-bilgi"]
    # Kaynaga bakirla baglanmayan pin (eksik iz) da kalistir: baglanmamis
    # kart basarili sayilmaz (Kicad-ecd).
    if any(f.severity == "error" or f.rule_id == "dal-akimi-kopuk" for f in hatalar):
        return "kaldi", hatalar, ozet
    if not s.calisti or set(akimlar) - set(aglar):
        ozet["notlar"].append(f"cozulemeyen ag: {sorted(set(akimlar) - set(aglar))}")
        return "denetlenemedi", hatalar, ozet
    return "gecti", hatalar, ozet


def yeni_ihlaller(once: Degerlendirme, sonra: Degerlendirme) -> list[str]:
    return sorted(set(sonra.ihlaller) - set(once.ihlaller))
