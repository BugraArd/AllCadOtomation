"""Veri kapsami envanteri ve kopya tespiti (Kicad-7cb).

    python -m pcbqa.duzeltme.envanter --veri .work/duzeltme-dogal [--veri .work/duzeltme-dengeli]

Referans (temel tasarim) ile ondan turetilen varyant/aday sayilari AYRI
raporlanir: 80 referansin 427 varyanti 80 bagimsiz ornek degildir.

Sayimlar: paket, MPN, deger dekadi, tolerans, guc dayanimi (paket + sicaklik
azaltmasi), calisma kosulu (Vin, ortam), hata turu, gecersizlik NEDENI
(guc / gerilim / mekanik / pad-footprint / gereksinim; veri yoksa belirsiz),
paket-kucuk hedefinin guc / gerilim bandi, temel tasarim kimligi.

Kopya: icerigi ayni (kimlik ve zaman haric) referans ya da aday kayitlari.
"Yalnizca kimligi degismis" bir kayit veri kumesini sisirir ve gruplu bolmeyi
deler; bu yuzden her uretimde ozet.json'a yazilir.

## Iki kaynak turu - BIRLESTIRILMEZ (Kicad-d8k)

    pcbqa duzeltme-envanter <yol> [<yol> ...] [--json cikti.json]

  bellek-veri-kumesi    `kayitlar.jsonl` (veri.py): bellekte kurulan SENTETIK
                        tasarimlar. Yukaridaki sayimlar.
  gercek-proje-deneyi   `deney.jsonl` ya da onu iceren deney klasoru
                        (proje.py): gercek KiCad dosyalarinda degerlendirilmis
                        adaylar. Birden fazla kosu birlikte sayilir.

Gercek deney kimliklendirme ve tekrar kurali:

  temel tasarim   temel proje dosyalarinin SHA-256 ozetleri (.kicad_pro /
                  .kicad_sch / .kicad_pcb icerigi; klasor yolu ve ad HARIC).
                  Ayni dosyalarin baska klasorden ya da yeniden kosulmasi
                  yeni tasarim saymaz.
  calisma kosulu  temel tasarim + kosullar.json icerigi.
  deney kosusu    bir deney.jsonl dosyasi (girdi basina bir kosu).
  referans kaydi  kosu basina `gercek-temel` kaydi; benzersizi calisma kosulu.
  aday kaydi      `gercek-aday`; benzersiz anahtar = calisma kosulu + ureteci
                  kimligi (aday.kimlik) + degisiklik listesi (ref, alan, eski,
                  yeni). "aday-02-" on eki siralamaya bagli oldugu icin anahtara
                  GIRMEZ; degisiklikleri farkli iki aday asla tek kayda inmez.
                  Ayni anahtarli tekrar kayitlar dagilimlara BIR kez girer;
                  sonuclari (durum, kontroller) farkliysa `celiskili_tekrar`.
  tekrar kosu     calisma kosulu ve aday anahtar kumesi daha onceki bir
                  kosuyla ayni olan kosu.
  bozuk kayit     JSON olarak okunamayan ya da zorunlu alani (tur, kimlik,
                  temel.ozetler, durum, kontroller; aday icin
                  aday.degisiklikler) olmayan satir: sayilmaz, ayri listelenir.
  eksik alan      gecerli kayitta olmayan istege bagli alan (maliyet,
                  bilesenler, olcumler, kosullar, kapsam_disi): ayri sayilir.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from ..devre.parca import paket_kodu
from .degerlendir import neden_etiketleri
from .orneklem import bant

KAYNAK_BELLEK = "bellek-veri-kumesi"
KAYNAK_GERCEK = "gercek-proje-deneyi"
KAYNAK_ACIKLAMA = {
    KAYNAK_BELLEK: "bellekte kurulan SENTETIK tasarimlar (veri.py, kayitlar.jsonl) - gercek KiCad dosyasi degil",
    KAYNAK_GERCEK: "gercek KiCad proje kopyalarinda degerlendirilmis adaylar (proje.py, deney.jsonl)",
}


class KaynakHatasi(ValueError):
    """Girdi bir deney kaynagi degil ya da turu belirlenemedi."""


def _ozet(x: Any) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def _referans_icerigi(k: dict[str, Any]) -> dict[str, Any]:
    p = dict(k.get("parametre") or {})
    p.pop("kimlik", None)
    return p


def kopyalar(kayitlar: list[dict[str, Any]]) -> dict[str, Any]:
    """Icerigi ayni kayitlar: referans parametreleri (kimlik haric) ve aday
    (temel icerigi + varyant tasarimi + degisiklikler)."""
    ref: dict[str, list[str]] = {}
    for k in kayitlar:
        if k.get("tur") == "referans" and k.get("kabul"):
            ref.setdefault(_ozet(_referans_icerigi(k)), []).append(k["kimlik"])
    aday: dict[str, list[str]] = {}
    for k in kayitlar:
        if k.get("tur") == "aday":
            icerik = [k["varyant"]["tasarim"]["imza"],
                      sorted((d["ref"], d["alan"], d["yeni"]) for d in k["aday"]["degisiklikler"])]
            aday.setdefault(_ozet(icerik), []).append(k["kimlik"])
    ref_k = [v for v in ref.values() if len(v) > 1]
    aday_k = [v for v in aday.values() if len(v) > 1]
    return {"referans_kopya_grubu": ref_k, "aday_kopya_grubu_sayisi": len(aday_k),
            "aday_kopya_ornek": aday_k[:5],
            "not": "aday kopyasi ayni varyantta ayni degisiklik demektir; uretec bunu zaten eler "
                   "(beklenen 0). Farkli temellerde ayni icerik: kopya_gruplari ayni bolme grubuna koyar."}


def _dekad(ohm: float) -> str:
    if not ohm or ohm <= 0:
        return "?"
    e = math.floor(math.log10(ohm))
    return f"1e{e}-1e{e + 1}"


def aday_paketleri(k: dict[str, Any]) -> tuple[str, str]:
    """Adayin uygulandiktan SONRAKI direnc paketleri."""
    bol = k["varyant"]["degerlendirme"]["bolucu"]
    bil = k["varyant"]["tasarim"]["bilesenler"]
    paket = {r: paket_kodu(bil[r]["footprint"]) for r in (bol["ust"], bol["alt"]) if r in bil}
    for d in k["aday"]["degisiklikler"]:
        if d["alan"] == "footprint" and d["ref"] in paket:
            paket[d["ref"]] = paket_kodu(d["yeni"])
    return paket.get(bol["ust"], ""), paket.get(bol["alt"], "")


def neden_metni(sonuc: dict[str, Any]) -> str:
    """'gecerli', 'denetlenemedi', ya da '+' ile birlesik nedenler; hicbir
    neden 'var' degilken gecersizse 'belirsiz'."""
    if sonuc.get("durum") == "gecerli":
        return "gecerli"
    if sonuc.get("durum") == "denetlenemedi":
        return "denetlenemedi"
    n = neden_etiketleri(sonuc)
    var = [k for k, v in n.items() if v == "var"]
    return "+".join(var) if var else "belirsiz"


def envanter(kayitlar: list[dict[str, Any]]) -> dict[str, Any]:
    refs = [k for k in kayitlar if k.get("tur") == "referans" and k.get("kabul")]
    vars_ = [k for k in kayitlar if k.get("tur") == "varyant" and k.get("kullanildi")]
    ads = [k for k in kayitlar if k.get("tur") == "aday"]
    r = Counter
    ref = {
        "sayi": len(refs),
        "paket": r(k["parametre"]["paket_ust"] for k in refs),
        "tolerans": r(f"%{k['parametre']['tolerans'] * 100:g}" for k in refs),
        "deger_dekadi_r_ust": r(_dekad(k["parametre"]["r_ust"]) for k in refs),
        "vin": r(f"{k['parametre']['vin_nom']:g} V" for k in refs),
        "ortam": r(f"{k['parametre']['ortam_c']:g} C" for k in refs),
        "guc_dayanimi_w": r(f"{k['degerlendirme']['analitik'].get('p_ust_siniri') or 0:.4g}" for k in refs),
        "mpn_farkli": len({b.get("mpn") for k in refs for b in k["tasarim"]["bilesenler"].values() if b.get("mpn")}),
        "mpn_ornek": sorted({b.get("mpn") for k in refs for b in k["tasarim"]["bilesenler"].values()
                             if b.get("mpn")})[:8],
        "kip": r(((k.get("plan") or {}).get("kip") or "dogal") for k in refs),
        "plan_sapmasi": r((k.get("orneklem") or {}).get("plan_sapmasi") for k in refs
                          if (k.get("orneklem") or {}).get("plan_sapmasi")),
    }
    var = {
        "sayi": len(vars_), "temel_tasarim": len({k["temel"]["kimlik"] for k in vars_}),
        "hata_turu": r(k["hata"]["tur"] for k in vars_),
        "neden": r(neden_metni(k["degerlendirme"]) for k in vars_),
        "paket_ust": r(paket_kodu(k["tasarim"]["bilesenler"]["R1"]["footprint"]) for k in vars_
                       if "R1" in k["tasarim"]["bilesenler"]),
    }
    pk = [k for k in vars_ if k["hata"]["tur"] == "paket-kucuk"]
    var["paket_kucuk"] = {
        "sayi": len(pk),
        "ref_paket_hedef": r(f"{k['temel']['parametre']['paket_ust']}->{k['hata'].get('hedef_paket')}" for k in pk),
        "guc_bandi": r(bant(k["degerlendirme"]["analitik"].get("guc_orani")) for k in pk),
        "gerilim_bandi": r(bant(k["degerlendirme"]["analitik"].get("gerilim_orani")) for k in pk),
        "neden": r(neden_metni(k["degerlendirme"]) for k in pk),
    }
    # Zararsiz cikan paket-kucuk varyantlari da kayitta (kullanildi=False):
    # kucuk paketin GECERLI olabildiginin kaniti.
    zarar = [k for k in kayitlar if k.get("tur") == "varyant" and k["hata"]["tur"] == "paket-kucuk"
             and not k.get("kullanildi") and k.get("degerlendirme")]
    var["paket_kucuk_zararsiz"] = {"sayi": len(zarar),
                                   "guc_bandi": r(bant(k["degerlendirme"]["analitik"].get("guc_orani"))
                                                  for k in zarar)}
    ad = {
        "sayi": len(ads),
        "durum": r(k["sonuc"]["durum"] for k in ads),
        "neden": r(neden_metni(k["sonuc"]) for k in ads),
        "paket_ust_sonra": r(aday_paketleri(k)[0] for k in ads),
        "paket_x_durum": r(f"{aday_paketleri(k)[0]}:{k['sonuc']['durum']}" for k in ads),
    }
    return {"referans": _dict(ref), "varyant": _dict(var), "aday": _dict(ad), "kopyalar": kopyalar(kayitlar)}


def _dict(x):
    if isinstance(x, Counter):
        return dict(sorted(x.items(), key=lambda kv: str(kv[0])))
    if isinstance(x, dict):
        return {k: _dict(v) for k, v in x.items()}
    return x


def rapor(env: dict[str, Any], baslik: str) -> str:
    out = [f"## {baslik}"]
    for bolum in ("referans", "varyant", "aday"):
        out.append(f"\n### {bolum}\n")
        for ad, v in env[bolum].items():
            out.append(f"- **{ad}**: {json.dumps(v, ensure_ascii=False)}")
    k = env["kopyalar"]
    out.append(f"\nkopya: referans gruplari {k['referans_kopya_grubu']}, aday kopya grubu "
               f"{k['aday_kopya_grubu_sayisi']}")
    return "\n".join(out)



# --------------------------------------------------------------------------
# Kaynak turu ve okuma (Kicad-d8k)
# --------------------------------------------------------------------------


def jsonl_oku(yol: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(kayitlar, bozuk). Okunamayan satir atlanmaz - `bozuk`a satir no ile girer."""
    kayitlar, bozuk = [], []
    for i, satir in enumerate(Path(yol).read_text(encoding="utf-8").splitlines(), 1):
        if not satir.strip():
            continue
        try:
            k = json.loads(satir)
        except ValueError as exc:
            bozuk.append({"satir": i, "neden": f"JSON okunamadi: {exc}"})
            continue
        if not isinstance(k, dict):
            bozuk.append({"satir": i, "neden": "kayit nesne degil"})
            continue
        k["_satir"] = i
        kayitlar.append(k)
    return kayitlar, bozuk


def kaynak_turu(yol: Path) -> tuple[str, Path]:
    """(tur, jsonl dosyasi). Klasorde deney.jsonl -> gercek, kayitlar.jsonl ->
    bellek; dosyada ilk okunabilir kaydin `tur` alani belirler."""
    yol = Path(yol)
    if yol.is_dir():
        if (yol / "deney.jsonl").is_file():
            return KAYNAK_GERCEK, yol / "deney.jsonl"
        if (yol / "kayitlar.jsonl").is_file():
            return KAYNAK_BELLEK, yol / "kayitlar.jsonl"
        raise KaynakHatasi(f"{yol}: deney.jsonl (gercek proje deneyi) ya da kayitlar.jsonl (bellek veri kumesi) yok")
    if not yol.is_file():
        raise KaynakHatasi(f"{yol}: bulunamadi")
    for k in jsonl_oku(yol)[0]:
        tur = str(k.get("tur") or "")
        if tur.startswith("gercek-"):
            return KAYNAK_GERCEK, yol
        if tur in ("referans", "varyant", "aday"):
            return KAYNAK_BELLEK, yol
    raise KaynakHatasi(f"{yol}: kaynak turu belirlenemedi (tanidik 'tur' alani olan kayit yok)")


_GERCEK_TURLER = ("gercek-temel", "gercek-aday")


def gercek_kayit_sorunu(k: dict[str, Any]) -> str:
    """Zorunlu alan eksigi; bos dize = kayit gecerli."""
    if k.get("tur") not in _GERCEK_TURLER:
        return f"bilinmeyen tur {k.get('tur')!r}"
    if not k.get("kimlik"):
        return "kimlik yok"
    temel = k.get("temel")
    if not isinstance(temel, dict) or not isinstance(temel.get("ozetler"), dict) or not temel["ozetler"]:
        return "temel.ozetler yok (temel tasarim kimligi kurulamaz)"
    if not k.get("durum"):
        return "durum yok"
    if not isinstance(k.get("kontroller"), dict):
        return "kontroller yok"
    if k["tur"] == "gercek-aday" and not isinstance((k.get("aday") or {}).get("degisiklikler"), list):
        return "aday.degisiklikler yok"
    return ""


def tasarim_kimligi(k: dict[str, Any]) -> str:
    return _ozet(sorted(k["temel"]["ozetler"].items()))


def kosul_kimligi(k: dict[str, Any]) -> str:
    return _ozet([tasarim_kimligi(k), k.get("kosullar")])


def gercek_aday_anahtari(k: dict[str, Any]) -> str:
    a = k.get("aday") or {}
    return _ozet([kosul_kimligi(k), a.get("kimlik"),
                  sorted((str(d.get("ref")), str(d.get("alan")), str(d.get("eski")), str(d.get("yeni")))
                         for d in a.get("degisiklikler") or [])])


def _sonuc_imzasi(k: dict[str, Any]) -> str:
    return _ozet([k.get("durum"), sorted((k.get("kontroller") or {}).items())])


_EKSIK_ALANLAR = {
    "gercek-aday": ("maliyet", "bilesenler", "elektrik.olcumler", "kosullar", "kapsam_disi", "kicad.sayilar"),
    "gercek-temel": ("bilesenler", "elektrik.olcumler", "kosullar", "kapsam_disi", "kicad.sayilar"),
}


def _alan_var(k: dict[str, Any], yol: str) -> bool:
    x: Any = k
    for p in yol.split("."):
        if not isinstance(x, dict) or not x.get(p):
            return False
        x = x[p]
    return True


def _neden_metni_gercek(k: dict[str, Any]) -> str:
    """Gercek aday: gecerli / arac / veri eksigi ya da birlesik nedenler."""
    d = k.get("durum")
    if d == "gecti":
        return "gecerli"
    if d in ("arac-hatasi", "veri-model-eksik"):
        return d
    e = k.get("elektrik") if isinstance(k.get("elektrik"), dict) else {}
    var = [a for a, v in neden_etiketleri(e).items() if v == "var"]
    kk = k.get("kontroller") or {}
    var += [a for a in ("kicad-erc", "kicad-drc", "kicad-parite") if kk.get(a) == "kaldi"]
    return "+".join(var) if var else "belirsiz"


def _aile(k: dict[str, Any]) -> str:
    try:
        meta = json.loads((Path(k["temel"]["klasor"]) / "pcbqa-referans.json").read_text(encoding="utf-8"))
        return str(meta.get("aile") or "bilinmiyor")
    except (OSError, ValueError, KeyError, TypeError):
        return "bilinmiyor (pcbqa-referans.json okunamadi)"


def _kosul_sayimlari(refs: list[dict[str, Any]]) -> dict[str, Counter]:
    def ks(k):
        return k.get("kosullar") or {}

    def ray(a, v):
        try:
            return f"{a} {float(v['nom']):g} V ({float(v['min']):g}-{float(v['max']):g})"
        except (KeyError, TypeError, ValueError):
            return f"{a} ?"
    return {
        "vin": Counter(", ".join(ray(a, v) for a, v in sorted((ks(k).get("raylar") or {}).items())) or "?"
                       for k in refs),
        "ortam": Counter(f"{ks(k).get('ortam_c', '?')} C" for k in refs),
        "sicakliklar": Counter(str((ks(k).get("analiz") or {}).get("sicakliklar", "?")) for k in refs),
        "gereksinim": Counter("; ".join(f"{g.get('ag')} {g.get('min_v')}-{g.get('max_v')} V"
                                        for g in ks(k).get("gereksinimler") or []) or "?" for k in refs),
        "yuk": Counter("; ".join(f"{y.get('ag')} {y.get('akim_a')} A (tepe {y.get('tepe_a')})"
                                 for y in ks(k).get("yukler") or []) or "?" for k in refs),
    }


def gercek_envanter(yollar: list[Path]) -> dict[str, Any]:
    """Bir ya da daha fazla gercek deney kosusunun envanteri (kurallar: modul basi)."""
    from .secim import maliyet_degeri, sec

    kaynaklar: list[dict[str, Any]] = []
    temeller: dict[str, dict[str, Any]] = {}            # calisma kosulu -> ilk temel kaydi
    adaylar: dict[str, list[dict[str, Any]]] = {}       # aday anahtari -> kayitlar
    kosu_imzalari: list[str] = []
    eksik: Counter = Counter()
    referans_kaydi = tekrar_kosu = 0
    secimler = []
    for y in yollar:
        tur, dosya = kaynak_turu(y)
        if tur != KAYNAK_GERCEK:
            raise KaynakHatasi(f"{y}: {tur} - gercek proje deneyi degil (ayri raporlanir)")
        kayitlar, bozuk = jsonl_oku(dosya)
        n_satir = len(kayitlar) + len(bozuk)
        gecerli = []
        for k in kayitlar:
            sorun = gercek_kayit_sorunu(k)
            if sorun:
                bozuk.append({"satir": k.get("_satir"), "neden": sorun})
            else:
                gecerli.append(k)
        bozuk.sort(key=lambda b: b["satir"] or 0)
        for k in gecerli:
            for alan in _EKSIK_ALANLAR[k["tur"]]:
                if not _alan_var(k, alan):
                    eksik[f"{k['tur']}: {alan}"] += 1
            if k["tur"] == "gercek-temel":
                referans_kaydi += 1
                temeller.setdefault(kosul_kimligi(k), k)
            else:
                adaylar.setdefault(gercek_aday_anahtari(k), []).append(k)
        imza = _ozet(sorted({kosul_kimligi(k) for k in gecerli}
                            | {gercek_aday_anahtari(k) for k in gecerli if k["tur"] == "gercek-aday"}))
        tekrar = bool(gecerli) and imza in kosu_imzalari
        tekrar_kosu += tekrar
        kosu_imzalari.append(imza)
        try:
            n_aday = json.loads((dosya.parent / "ozet.json").read_text(encoding="utf-8")).get("adaylar")
        except (OSError, ValueError, AttributeError):
            n_aday = None
        s = sec(gecerli, aday_sayisi=n_aday)
        secimler.append({"kaynak": str(dosya), "secilen": s["secilen"], "ilk_gecen": s["ilk_gecen"],
                         "kapsam": s["kapsam"], "esit_maliyetliler": s["esit_maliyetliler"]})
        kaynaklar.append({"yol": str(dosya), "kayit": n_satir, "gecerli": len(gecerli), "bozuk": len(bozuk),
                          "bozuk_ayrinti": bozuk[:20], "tekrar_kosu": tekrar, "uretilen_aday": n_aday})

    tekil = [v[0] for v in adaylar.values()]
    refs = list(temeller.values())
    celiskili = [{"aday": v[0]["kimlik"], "kayit": len(v)} for v in adaylar.values()
                 if len({_sonuc_imzasi(k) for k in v}) > 1]

    def bilesen_say(alan: str) -> Counter:
        c: Counter = Counter()
        for k in tekil:
            for ref, b in sorted((k.get("bilesenler") or {}).items()):
                if ref.startswith("R"):
                    c[f"{ref}:{b.get(alan) or '?'}"] += 1
        return c

    maliyetler = [maliyet_degeri(k)[0] for k in tekil]
    m_gecen = [maliyet_degeri(k)[0] for k in tekil if k["durum"] == "gecti"]
    return {
        "kaynak_turu": KAYNAK_GERCEK, "kaynak_aciklamasi": KAYNAK_ACIKLAMA[KAYNAK_GERCEK],
        "kaynaklar": kaynaklar,
        "kapsam": {"aile": _dict(Counter(_aile(k) for k in refs)),
                   "not": "proje.deney yalnizca rezistif bolucu ailesini ve pcbqa-referans.json iceren temel "
                          "projeleri destekler; bu envanter baska aile icin bilgi tasimaz"},
        "sayilar": {
            "temel_tasarim": len({tasarim_kimligi(k) for k in refs + tekil}),
            "calisma_kosulu": len(temeller),
            "deney_kosusu": len(kaynaklar), "tekrar_kosu": tekrar_kosu,
            "referans_kaydi": referans_kaydi, "referans_benzersiz": len(temeller),
            "aday_kaydi": sum(len(v) for v in adaylar.values()), "aday_benzersiz": len(adaylar),
            "tekrar_aday_kaydi": sum(len(v) - 1 for v in adaylar.values()),
            "bozuk_kayit": sum(x["bozuk"] for x in kaynaklar),
        },
        "celiskili_tekrar": celiskili,
        "kosu_secimleri": secimler,
        "dagilim": {
            "paket_sonra": _dict(bilesen_say("paket")),
            "tolerans_sonra": _dict(bilesen_say("tolerans")),
            "calisma_kosulu": _dict(_kosul_sayimlari(refs)),
            "durum": _dict(Counter(k["durum"] for k in tekil)),
            "egitime_aktarilabilir": _dict(Counter(str(bool((k.get("egitim") or {}).get("aktarilabilir")))
                                                   for k in tekil)),
            "gecmeyen_kontrol": _dict(Counter(a for k in tekil for a, v in k["kontroller"].items() if v != "gecti")),
            "neden": _dict(Counter(_neden_metni_gercek(k) for k in tekil)),
            "maliyet": _dict(Counter(f"{m:g}" if m is not None else "eksik" for m in maliyetler)),
            "maliyet_gecen": _dict(Counter(f"{m:g}" if m is not None else "eksik" for m in m_gecen)),
            "kapsam_disi": _dict(Counter(x for k in refs for x in k.get("kapsam_disi") or [])),
        },
        "eksik_alanlar": _dict(eksik),
        "kimlik_kurali": ("temel tasarim = dosya ozetleri (yol haric); calisma kosulu = tasarim + kosullar; aday "
                          "= kosul + ureteci kimligi + degisiklik listesi; tekrar kayit dagilima bir kez girer"),
    }


def gercek_rapor(env: dict[str, Any]) -> str:
    out = [f"## Kaynak turu: {env['kaynak_turu']}", "", env["kaynak_aciklamasi"], ""]
    for kay in env["kaynaklar"]:
        out.append(f"- kaynak `{kay['yol']}`: {kay['kayit']} satir, {kay['gecerli']} gecerli, {kay['bozuk']} bozuk"
                   + (" (TEKRAR KOSU)" if kay["tekrar_kosu"] else ""))
        for b in kay["bozuk_ayrinti"]:
            out.append(f"  - bozuk satir {b['satir']}: {b['neden']}")
    out += ["", f"Kapsam: aile {json.dumps(env['kapsam']['aile'], ensure_ascii=False)} - {env['kapsam']['not']}",
            "", "### Sayilar", ""]
    out += [f"- **{ad}**: {v}" for ad, v in env["sayilar"].items()]
    if env["celiskili_tekrar"]:
        out.append(f"- **celiskili_tekrar**: {json.dumps(env['celiskili_tekrar'], ensure_ascii=False)}")
    out += ["", "### Kosu secimleri", ""]
    for s in env["kosu_secimleri"]:
        out.append(f"- `{s['kaynak']}`: secilen {s['secilen'] or '-'} (kapsam {s['kapsam']}; ilk gecen "
                   f"{s['ilk_gecen'] or '-'}; esit maliyetli {', '.join(s['esit_maliyetliler']) or '-'})")
    out += ["", "### Dagilimlar (benzersiz kayitlar; tekrarlar bir kez)", ""]
    out += [f"- **{ad}**: {json.dumps(v, ensure_ascii=False)}" for ad, v in env["dagilim"].items()]
    out += ["", "### Eksik alanlar", ""]
    out += [f"- {a}: {n} kayit" for a, n in env["eksik_alanlar"].items()] or ["- yok"]
    out += ["", f"Kimlik kurali: {env['kimlik_kurali']}"]
    return "\n".join(out)


def envanter_metni(yollar: list[Path]) -> tuple[str, dict[str, Any]]:
    """Kaynaklari turlerine ayirir; her tur AYRI bolum (birlestirilmez).
    Donus: (metin, {tur: envanter})."""
    from .veri import kayitlari_oku

    gruplar: dict[str, list[Path]] = {}
    for y in yollar:
        gruplar.setdefault(kaynak_turu(y)[0], []).append(Path(y))
    bolumler: list[str] = []
    sonuc: dict[str, Any] = {}
    if KAYNAK_GERCEK in gruplar:
        env = gercek_envanter(gruplar[KAYNAK_GERCEK])
        sonuc[KAYNAK_GERCEK] = env
        bolumler.append(gercek_rapor(env))
    for y in gruplar.get(KAYNAK_BELLEK, []):
        env = envanter(kayitlari_oku(kaynak_turu(y)[1]))
        sonuc.setdefault(KAYNAK_BELLEK, {})[str(y)] = env
        bolumler.append(f"## Kaynak turu: {KAYNAK_BELLEK}\n\n{KAYNAK_ACIKLAMA[KAYNAK_BELLEK]}\n\n"
                        + rapor(env, str(y)))
    return "\n\n".join(bolumler), sonuc


def main(argv: list[str] | None = None) -> int:
    from .veri import kayitlari_oku

    ap = argparse.ArgumentParser(prog="pcbqa duzeltme-envanter", description=__doc__.splitlines()[0])
    ap.add_argument("yol", type=Path, nargs="*", help="deney klasoru / deney.jsonl (gercek) ya da veri klasoru "
                                                     "/ kayitlar.jsonl (bellek)")
    ap.add_argument("--veri", type=Path, action="append", default=[],
                    help="bellek veri klasoru (eski bicim; envanter.json/md klasore yazilir)")
    ap.add_argument("--json", type=Path, default=None, help="butun envanteri JSON olarak yaz")
    args = ap.parse_args(argv)
    if not args.yol and not args.veri:
        ap.error("en az bir kaynak gerekli")
    for d in args.veri:
        env = envanter(kayitlari_oku(d / "kayitlar.jsonl"))
        (d / "envanter.json").write_text(json.dumps(env, ensure_ascii=False, indent=1), encoding="utf-8")
        metin = rapor(env, str(d))
        (d / "envanter.md").write_text(metin + "\n", encoding="utf-8")
        print(f"## Kaynak turu: {KAYNAK_BELLEK}\n\n{KAYNAK_ACIKLAMA[KAYNAK_BELLEK]}\n\n{metin}")
    if args.yol:
        try:
            metin, sonuc = envanter_metni(args.yol)
        except KaynakHatasi as exc:
            print(f"HATA: {exc}", file=sys.stderr)
            return 2
        print(metin)
        if args.json:
            args.json.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
