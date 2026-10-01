"""Oznitelikler - YALNIZCA tahmin aninda bilinen bilgiden.

Tahmin ani: kullanici devreyi acti, mevcut kontroller HATALI tasarim icin
calisti (bulgular ve olcumler elde), ureteci adaylari cikardi. Adaylarin
hicbiri henuz benzetilmedi. Dolayisiyla:

  GIRER   hatali tasarimin degerleri, kosullar, kart geometrisi; hatali
          tasarimin GERCEK kontrol sonuclari (marjlar, guc oranlari, hangi
          kontrolun kaldigi); adayin degisiklik tanimi ve ureteci sirasi
  GIRMEZ  adayin benzetim sonucu, adayin durumu, yeni ihlalleri, hata
          turu (kayitta duruyor ama ureteci ve model onu gormez)

`ozellikler(kayit)` kaydin "sonuc" ve "varyant.hata" alanlarina HIC
dokunmaz; bunu bir test, bu alanlari silip ayni vektoru alarak dogrular.

Iki sema:
  ham  - fizik bilgisi vermeyen sayilar (degerler, paketler, olculen
         marjlar, degisikligin buyuklugu). Kapali formu OLMAYAN ailelere
         tasinabilecek olan budur.
  tam  - ham + adayin KAPALI FORM on hesabi (el hesabi marji, guc orani,
         geometrik courtyard on kontrolu). Benzetim degil, aninda hesaplanir.

Sema degisirse OZNITELIK_SURUMU artirilir; model dosyasi semayi icinde
tasir ve uyusmazlikta tahmin reddedilir (ml.model.check_schema).
"""

from __future__ import annotations

import math
from typing import Any

from ..circuit import parse_value
from ..devre.parca import paket_kodu, tolerans_metinden
from .adaylar import OPERATORLER
from .bolucu import PAKETLER, Bolucu, analitik, bosluklar, courtyard_cakismalari
from .tasarim import Tasarim

# 2: degisiklik maliyeti oznitelikleri (Kicad-apg). Maliyet adayin
# degisiklik tanimindan ve kart geometrisinden ANINDA hesaplanir (benzetim
# degil) - tahmin aninda bilinir. v1 modelleri bu surumle reddedilir.
OZNITELIK_SURUMU = 2

HAM = [
    "log_r_ust", "log_r_alt", "oran_k", "log_r_toplam",
    "vin_nom", "vin_tol", "hedef_k", "pencere_rel", "log_yuk_tepe", "ortam_c", "dt_max",
    "tol_ust", "tol_alt", "paket_ust", "paket_alt", "bosluk_ust_mm", "bosluk_alt_mm",
    "h_gereksinim_alt", "h_gereksinim_ust", "h_guc", "h_cakisma", "h_sinir",
    "h_marj_alt_rel", "h_marj_ust_rel", "h_vnom_hata_rel", "h_p_ust_oran", "h_p_alt_oran",
    "h_gerilim", "h_v_oran", "h_paket_uyumu", "mpn_var",
    *[f"op_{o}" for o in OPERATORLER],
    "n_degisiklik", "dlog_r_ust", "dlog_r_alt", "d_oran_k_rel", "d_tol_ust", "d_tol_alt",
    "d_paket_ust", "d_paket_alt", "sira",
    "m_toplam", "m_parca", "m_footprint", "m_yonlendirme", "m_yerlesim",
]
ON_HESAP = ["a_marj_alt_rel", "a_marj_ust_rel", "a_guc_orani", "a_gerilim_orani", "a_gecer", "g_cakisma"]
TAM = HAM + ON_HESAP
SEMALAR = {"ham": HAM, "tam": TAM}


def tasarim_ozeti(t: Tasarim, b: Bolucu) -> dict[str, Any]:
    """Hatali tasarimin tahmin aninda bilinen tanimi (degerler, kosullar, kart)."""
    return {"bilesenler": t.bilesen_ozeti([b.ust, b.alt]), "kosullar": t.kosullar,
            "bosluk_mm": bosluklar(t.board, [b.ust, b.alt]), "imza": t.imza()}


def on_hesap(t: Tasarim, b: Bolucu) -> dict[str, Any]:
    """Adayin benzetimsiz on hesabi: kapali form + geometrik courtyard kontrolu.
    Aninda hesaplanir; tahmin aninda bilinebilir."""
    g = t.graf()
    return {"analitik": analitik(g, b).as_dict(),
            "cakisma": bool(courtyard_cakismalari(t.board, {b.ust, b.alt}))}


def _log(x: float | None) -> float:
    return math.log10(x) if x and x > 0 else 0.0


def _paket_idx(fp: str) -> float:
    p = paket_kodu(fp)
    return float(PAKETLER.index(p)) if p in PAKETLER else -1.0


def _tol(metin: str) -> float:
    t = tolerans_metinden(metin or "")
    return t if t is not None else 0.0


def _kirp(x: float | None, sinir: float = 10.0) -> float:
    if x is None or math.isnan(x):
        return 0.0
    return max(-sinir, min(sinir, x))


def ozellikler(kayit: dict[str, Any], sema: str = "tam") -> list[float]:
    v = kayit["varyant"]
    t = v["tasarim"]
    bol = v["degerlendirme"]["bolucu"]
    ust, alt = bol["ust"], bol["alt"]
    bil = t["bilesenler"]
    an = v["degerlendirme"]["analitik"]          # HATALI tasarimin el hesabi (on bilgi)
    ol = v["degerlendirme"]["olcumler"]          # HATALI tasarimin benzetimi (kontrol sonucu)
    ko = v["degerlendirme"]["kontroller"]
    ihl = set(v["degerlendirme"]["ihlaller"])

    r1, r2 = parse_value(bil[ust]["deger"]), parse_value(bil[alt]["deger"])
    k = r2 / (r1 + r2)
    vin = an["vin_nom"]
    lo, hi = an["pencere_min"], an["pencere_max"]
    vt = (lo + hi) / 2
    f: dict[str, float] = {
        "log_r_ust": _log(r1), "log_r_alt": _log(r2), "oran_k": k, "log_r_toplam": _log(r1 + r2),
        "vin_nom": vin, "vin_tol": (an["vin_max"] - an["vin_nom"]) / vin if vin else 0.0,
        "hedef_k": vt / vin if vin else 0.0, "pencere_rel": (hi - lo) / 2 / vt if vt else 0.0,
        "log_yuk_tepe": math.log10(an["yuk_tepe_a"] + 1e-9),
        "ortam_c": float(t["kosullar"].get("ortam_c") or 25.0), "dt_max": an["dt_max"],
        "tol_ust": _tol(bil[ust]["tolerans"]), "tol_alt": _tol(bil[alt]["tolerans"]),
        "paket_ust": _paket_idx(bil[ust]["footprint"]), "paket_alt": _paket_idx(bil[alt]["footprint"]),
        "bosluk_ust_mm": _kirp(t["bosluk_mm"].get(ust)), "bosluk_alt_mm": _kirp(t["bosluk_mm"].get(alt)),
        "h_gereksinim_alt": float("gereksinim-gerilim||error|alt" in ihl),
        "h_gereksinim_ust": float("gereksinim-gerilim||error|ust" in ihl),
        "h_guc": float(ko.get("direnc-gucu") == "kaldi"),
        "h_cakisma": float(ko.get("pcb-cakisma") == "kaldi"),
        "h_sinir": float(ko.get("pcb-sinir") == "kaldi"),
        "h_marj_alt_rel": _kirp((ol["vout_min"] - lo) / vt) if ol.get("vout_min") is not None else 0.0,
        "h_marj_ust_rel": _kirp((hi - ol["vout_max"]) / vt) if ol.get("vout_max") is not None else 0.0,
        "h_vnom_hata_rel": _kirp((ol["vout_nom"] - vt) / vt) if ol.get("vout_nom") is not None else 0.0,
        "h_p_ust_oran": _kirp(ol.get("p_ust_oran"), 100.0), "h_p_alt_oran": _kirp(ol.get("p_alt_oran"), 100.0),
        # Kicad-7cb: gerilim siniri ve MPN/footprint tutarliligi (hatali tasarimin kontrolleri)
        "h_gerilim": float(ko.get("direnc-gerilimi") == "kaldi"),
        "h_v_oran": _kirp(an.get("gerilim_orani"), 100.0),
        "h_paket_uyumu": float(ko.get("paket-uyumu") == "kaldi"),
        "mpn_var": float(any(b.get("mpn") for b in bil.values())),
    }

    a = kayit["aday"]
    for o in OPERATORLER:
        f[f"op_{o}"] = float(a["operator"] == o)
    yeni = {(d["ref"], d["alan"]): d for d in a["degisiklikler"]}

    def yeni_r(ref, eski):
        d = yeni.get((ref, "deger"))
        return parse_value(d["yeni"]) if d else eski

    n1, n2 = yeni_r(ust, r1), yeni_r(alt, r2)
    k2 = n2 / (n1 + n2)

    def d_tol(ref):
        d = yeni.get((ref, "tolerans"))
        return _tol(d["yeni"]) - _tol(bil[ref]["tolerans"]) if d else 0.0

    def d_paket(ref):
        d = yeni.get((ref, "footprint"))
        return _paket_idx(d["yeni"]) - _paket_idx(bil[ref]["footprint"]) if d else 0.0

    f.update({
        "n_degisiklik": float(len(a["degisiklikler"])),
        "dlog_r_ust": _log(n1) - _log(r1), "dlog_r_alt": _log(n2) - _log(r2),
        "d_oran_k_rel": (k2 - k) / k, "d_tol_ust": d_tol(ust), "d_tol_alt": d_tol(alt),
        "d_paket_ust": d_paket(ust), "d_paket_alt": d_paket(alt), "sira": float(a["sira"]),
    })
    m = a.get("maliyet")
    if m is None:
        raise ValueError("aday kaydinda maliyet yok (kayit semasi v1) - veriyi yeniden uretin (duzeltme.veri)")
    al = m["alanlar"]
    f.update(m_toplam=float(m["toplam"]), m_parca=float(al["parca"]), m_footprint=float(al["footprint"]),
             m_yonlendirme=float(al["yonlendirme"]), m_yerlesim=float(al["yerlesim"]))
    if sema == "tam":
        oh = a["on_hesap"]
        aa = oh["analitik"]
        if aa.get("hesaplanabilir"):
            f["a_marj_alt_rel"] = _kirp(aa["marj_alt"] / vt) if aa.get("marj_alt") is not None else 0.0
            f["a_marj_ust_rel"] = _kirp(aa["marj_ust"] / vt) if aa.get("marj_ust") is not None else 0.0
            f["a_guc_orani"] = _kirp(aa.get("guc_orani"), 100.0)
            f["a_gerilim_orani"] = _kirp(aa.get("gerilim_orani"), 100.0)
            f["a_gecer"] = float(bool(aa.get("gecer")))
        else:
            f.update(a_marj_alt_rel=0.0, a_marj_ust_rel=0.0, a_guc_orani=0.0, a_gerilim_orani=0.0, a_gecer=0.0)
        f["g_cakisma"] = float(bool(oh.get("cakisma")))
    return [float(f[ad]) for ad in SEMALAR[sema]]
