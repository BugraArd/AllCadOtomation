"""Devre grafi + dogrulama sonuclari -> ML veri satiri.

ML henuz karar VERMIYOR (bkz. evre-3-uretken-tasarim-fazlama: 3d kapisi
acik degil). Bu modul onun YAKITINI uretir: her `pcbqa dogrula --veri`
kosusu, ml/dataset.py bicimine (JSONL, grup = proje) bir ornek ekler.

Neden bu oznitelikler: yerlestirme verisi (collect_design) yalnizca
geometriyi goruyordu; burada devrenin ELEKTRIKSEL durumu var - regulator
kaybi, Tj marji, gerilim marji, eksik bilgi orani, hangi kontrolun kaldigi.
Ileride ogrenilebilecek sorular:
  * pahali benzetimden ONCE hangi tasarimin kalacagini tahmin etmek
  * hangi eksik bilginin (MPN, tolerans) sonucu en cok degistirdigi
  * Tj / gerilim marjini sablon parametrelerinden tahmin etmek

Etiket secenekleri (`--etiket`):
  gecti        1.0 hata yoksa, 0.0 varsa (varsayilan)
  tj_marj      en kotu regulator icin (sinir - Tj) C; regulator yoksa ornek yazilmaz
  hata_sayisi  toplam hata

KURAL (proje ilkesi): eksik bilgi sifirla DOLDURULMAZ ve gizlenmez.
Olculemeyen oznitelik NaN yerine ayri bir "_var" bayragiyla 0 yazilir ve
eksik orani satirin kendisine (`e.eksik_orani`) islenir; sentetik ya da
dogrulanmamis kaynak orani da oyle.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .dataset import Dataset, Sample

FEATURE_VERSION = 1

OZNITELIKLER = [
    "bilesen", "ag", "oran_gerilim_bilinen", "oran_rol_bilinen", "oran_eksiksiz",
    "eksik_alan_ort", "oran_dogrulanmamis_kaynak", "oran_sentetik_kaynak",
    "regulator", "ldo", "mosfet", "dekuplaj", "pullup", "mcu", "konnektor",
    "toplam_yuk_a", "toplam_yuk_var",
    "ldo_kayip_w", "ldo_kayip_var", "tj_marj_c", "tj_marj_var",
    "gerilim_marj_mv", "gerilim_marj_var",
    "s1_hata", "s1_uyari", "s1_calisti", "s2_hata", "s2_uyari", "s3_hata", "s3_calisti",
    "pcb_hata", "pcb_calisti", "iz_kayip_mw", "kontrol_kaldi", "kontrol_uyari",
    "kontrol_denetlenemedi", "yerlesim_kisit_ihlal", "yerlesim_kisit_sayisi",
]


def _seviye(rapor: dict, no: int) -> dict | None:
    return next((s for s in rapor.get("seviyeler", []) if s["seviye"] == no), None)


def ozellikler(graf, rapor: dict[str, Any]) -> dict[str, float]:
    """Sabit sirali oznitelik sozlugu (OZNITELIKLER)."""
    bs = list(graf.bilesenler.values())
    n = max(len(bs), 1)
    o = graf.ozet()
    guvenler = [b.parca.dogrulama for b in bs]
    eksik_alan = [len(b.eksikler()) for b in bs]
    x: dict[str, float] = {k: 0.0 for k in OZNITELIKLER}
    x.update({
        "bilesen": float(len(bs)),
        "ag": float(len(graf.aglar)),
        "oran_gerilim_bilinen": o["gerilimi_bilinen_ag"] / max(len(graf.aglar), 1),
        "oran_rol_bilinen": o["rolu_bilinen_bilesen"] / n,
        "oran_eksiksiz": o["eksiksiz_bilesen"] / n,
        "eksik_alan_ort": sum(eksik_alan) / n,
        "oran_dogrulanmamis_kaynak": sum(1 for gv in guvenler if gv == "dogrulanmamis") / n,
        "oran_sentetik_kaynak": sum(1 for b in bs if b.parca.mpn.guven == "sentetik") / n,
        "regulator": float(len(graf.rolle("regulator"))),
        "ldo": float(len(graf.kategoride("ldo"))),
        "mosfet": float(len(graf.kategoride("mosfet-n", "mosfet-p"))),
        "dekuplaj": float(len(graf.rolle("dekuplaj"))),
        "pullup": float(len(graf.rolle("pull-up"))),
        "mcu": float(len(graf.kategoride("mcu"))),
        "konnektor": float(len([b for b in bs if b.tur == "connector"])),
    })
    if graf.kosullar.yukler:
        x["toplam_yuk_a"] = sum(y.akim_a for y in graf.kosullar.yukler)
        x["toplam_yuk_var"] = 1.0

    for no, onek in ((1, "s1"), (2, "s2"), (3, "s3"), (4, "pcb")):
        s = _seviye(rapor, no)
        if s is None:
            continue
        if f"{onek}_hata" in x:
            x[f"{onek}_hata"] = float(s["sayilar"]["error"])
        if f"{onek}_uyari" in x:
            x[f"{onek}_uyari"] = float(s["sayilar"]["warning"])
        if f"{onek}_calisti" in x:
            x[f"{onek}_calisti"] = 1.0 if s["calisti"] else 0.0

    s3 = _seviye(rapor, 3)
    if s3 and s3["calisti"]:
        regler = s3["ekler"].get("regulatorler", {})
        kayiplar = [r["guc_w"] for r in regler.values() if r.get("guc_w") is not None]
        marjlar = [r["tj_sinir_c"] - r["tj_c"] for r in regler.values()
                   if r.get("tj_c") is not None and r.get("tj_sinir_c") is not None]
        if kayiplar:
            x["ldo_kayip_w"], x["ldo_kayip_var"] = max(kayiplar), 1.0
        if marjlar:
            x["tj_marj_c"], x["tj_marj_var"] = min(marjlar), 1.0
        gmarj = [f["measured"] for f in s3["bulgular"]
                 if f["rule_id"] == "gereksinim-gerilim" and f["severity"] == "info" and f["measured"] is not None]
        if gmarj:
            x["gerilim_marj_mv"], x["gerilim_marj_var"] = min(gmarj) * 1e3, 1.0

    pcb = _seviye(rapor, 4)
    if pcb and pcb["calisti"]:
        x["iz_kayip_mw"] = sum(a.get("kayip_mw", 0.0) for a in pcb["ekler"].get("aglar", {}).values())

    for k in rapor.get("kontroller", []):
        if k["durum"] == "kaldi":
            x["kontrol_kaldi"] += 1
        elif k["durum"] == "uyari":
            x["kontrol_uyari"] += 1
        elif k["durum"] in ("denetlenemedi", "kismen"):
            x["kontrol_denetlenemedi"] += 1
    kisitlar = rapor.get("yonlendirme_girdisi", {}).get("yerlesim_kisitlari", [])
    x["yerlesim_kisit_sayisi"] = float(len(kisitlar))
    x["yerlesim_kisit_ihlal"] = float(sum(1 for kk in kisitlar if kk.get("saglaniyor") is False))
    return x


def etiket(rapor: dict[str, Any], tur: str) -> float | None:
    if tur == "gecti":
        return 0.0 if rapor.get("hata_sayisi") else 1.0
    if tur == "hata_sayisi":
        return float(rapor.get("hata_sayisi", 0))
    if tur == "tj_marj":
        s3 = _seviye(rapor, 3)
        if not s3 or not s3["calisti"]:
            return None
        marjlar = [r["tj_sinir_c"] - r["tj_c"] for r in s3["ekler"].get("regulatorler", {}).values()
                   if r.get("tj_c") is not None and r.get("tj_sinir_c") is not None]
        return min(marjlar) if marjlar else None
    raise ValueError(f"bilinmeyen etiket turu {tur!r}")


def ornek(graf, rapor: dict[str, Any], *, etiket_turu: str = "gecti", parti: str = "") -> Sample | None:
    y = etiket(rapor, etiket_turu)
    if y is None:
        return None
    x = ozellikler(graf, rapor)
    eksik = graf.eksik_raporu()
    return Sample(
        features=[float(x[k]) for k in OZNITELIKLER],
        label=y,
        group=rapor.get("proje", graf.proje),
        batch=parti,
        extra={
            "etiket_turu": etiket_turu,
            "eksik_orani": len(eksik) / max(len(graf.bilesenler), 1),
            "kosullar": str(graf.kosullar.yol) if graf.kosullar.yol else None,
            "kaynaklar": list(graf.kaynaklar),
        },
    )


def ekle(yol: Path, s: Sample) -> Dataset:
    """Ornegi JSONL veri kumesine ekler; sema uyusmuyorsa reddeder."""
    yol = Path(yol)
    if yol.is_file():
        ds = Dataset.load(yol)
        if ds.feature_names != OZNITELIKLER or ds.feature_version != FEATURE_VERSION:
            raise ValueError(f"{yol}: oznitelik semasi farkli (surum {ds.feature_version}); yeni dosya kullanin")
    else:
        ds = Dataset(feature_names=list(OZNITELIKLER), feature_version=FEATURE_VERSION,
                     meta={"kaynak": "pcbqa.ml.devre_veri"})
    ds.add(s)
    ds.save(yol)
    return ds


def ozet_metin(x: dict[str, float]) -> str:
    return json.dumps({k: round(v, 4) for k, v in x.items()}, ensure_ascii=False)
