"""Duzeltme siralayicisini egitir ve mevcut yontemlerle KARSILASTIRIR.

    python -m pcbqa.duzeltme.egitim --veri .work/duzeltme
    python -m pcbqa.duzeltme.egitim --veri .work/duzeltme --model-cikti pcbqa/data/modeller/duzeltme-bolucu.json

Gorev: "bu devre ve calisma kosullarinda hangi duzeltme adayini once
denemeliyim?" Etiket: aday gercek kontrollerde GECERLI mi (1/0).
`denetlenemedi` adaylar egitime girmez (elektriksel basarisizlik degildir);
degerlendirmede siraya girer, bir benzetim harcar, gecerli sayilmaz.

Yaristirilan siralayicilar:
  rastgele          kapali form beklenen deger
  uretec            ureteci sirasi = MODEL YOKKEN uygulamanin kullandigi yontem
  kural-elektrik    kapali form el hesabi gecenler once (benzetimsiz)
  kural-tam         el hesabi + geometrik courtyard on kontrolu gecenler once
  <model>-<sema>    ridge / gbt; sema `ham` (fizik vermeyen) ya da `tam`

Bolmeler (hepsi "egitimde bulunmayan tasarim" sorusunu farkli sorar):
  gruplu-cv     5 kat, GRUP = temel tasarim: bir referansin hicbir varyanti
                hem egitimde hem testte olamaz
  dagilim-disi  egitim Vin <= 12 V, test Vin >= 15 V
  hata-disi     her hata turu icin: o tur egitimde YOK, testte VAR

Uygulamaya gidecek model gruplu-cv'de en az benzetimi isteyendir; ama
YALNIZCA `uretec`i geciyorsa yazilir. Gecemiyorsa model dosyasi yazilmaz ve
uygulama ureteci sirasiyla calismaya devam eder.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any, Callable

from ..ml.dataset import Dataset, Sample
from ..ml.train import fit_model
from . import olcut
from .ozellik import OZNITELIK_SURUMU, SEMALAR

MODELLER: tuple[tuple[str, dict[str, Any]], ...] = (("ridge", {"alpha": 1.0}), ("gbt", {}))
TOHUM = 20261001
# "+az" satirlari: puan kovasi icinde az degisiklik once (bkz. olcut.puan_anahtari)
KOVA = 0.1
VARSAYILAN_MODEL = Path(__file__).resolve().parents[1] / "data" / "modeller" / "duzeltme-bolucu.json"


def _anahtar(s: Sample) -> tuple[str, str, int]:
    return (s.group, s.batch, int(s.extra["sira"]))


def _egitilebilir(ds: Dataset, samples: list[Sample]) -> Dataset:
    return ds.subset([s for s in samples if s.label in (0.0, 1.0)])


def _kat_gruplari(gruplar: list[str], k: int, tohum: int) -> list[set[str]]:
    adlar = list(gruplar)
    random.Random(tohum).shuffle(adlar)
    kovalar: list[set[str]] = [set() for _ in range(k)]
    for i, ad in enumerate(adlar):
        kovalar[i % k].add(ad)
    return kovalar


def _bolmeler(ds: Dataset, kat: int, tohum: int) -> dict[str, list[tuple[Callable[[Sample], bool], str]]]:
    """Bolme adi -> [(test_mi(s), etiket)] listesi."""
    gruplar = ds.groups()
    out: dict[str, list[tuple[Callable[[Sample], bool], str]]] = {}
    out["gruplu-cv"] = [((lambda s, h=h: s.group in h), f"kat{i}")
                        for i, h in enumerate(_kat_gruplari(gruplar, kat, tohum))]
    out["dagilim-disi"] = [((lambda s: s.extra["vin_nom"] >= 15.0), "vin>=15")]
    turler = sorted({s.extra["hata"] for s in ds.samples})
    out["hata-disi"] = [((lambda s, t=t: s.extra["hata"] == t), t) for t in turler]
    return out


def karsilastir(veriler: dict[str, Dataset], kat: int = 5, tohum: int = TOHUM) -> dict[str, Any]:
    """Her bolmede her siralayicinin olcutleri. `veriler`: sema -> Dataset
    (ayni orneklerin farkli oznitelikleri, ayni sirada)."""
    ana = veriler["ham"]
    for ad, ds in veriler.items():
        if [_anahtar(s) for s in ds.samples] != [_anahtar(s) for s in ana.samples]:
            raise ValueError(f"{ad} veri kumesi ham ile ayni orneklere sahip degil")
    sonuc: dict[str, Any] = {}
    for bolme, testler in _bolmeler(ana, kat, tohum).items():
        tahmin: dict[str, dict[tuple, float]] = {}
        test_ornekleri: list[Sample] = []
        egitim_boyu = []
        for test_mi, _etiket in testler:
            test = [s for s in ana.samples if test_mi(s)]
            if not test:
                continue
            test_ornekleri += test
            for sema, ds in veriler.items():
                egitim = _egitilebilir(ds, [s for s in ds.samples if not test_mi(s)])
                egitim_boyu.append(len(egitim))
                hedef = {_anahtar(s): s for s in ds.samples if test_mi(s)}
                for model_adi, ayar in MODELLER:
                    m = fit_model(model_adi, egitim, seed=tohum, target="value", **ayar)
                    d = tahmin.setdefault(f"{model_adi}-{sema}", {})
                    for k_, s in hedef.items():
                        d[k_] = m.predict(s.features)
        parts = olcut.partiler(test_ornekleri)
        satirlar = {
            "rastgele": olcut.olc_rastgele(parts),
            "uretec": olcut.olc(parts, olcut.sirala_uretec),
            "kural-elektrik": olcut.olc(parts, olcut.sirala_kural_elektrik),
            "kural-tam": olcut.olc(parts, olcut.sirala_kural_tam),
        }
        for ad, d in sorted(tahmin.items()):
            satirlar[ad] = olcut.olc(parts, olcut.sirala_puan(lambda s, d=d: d[_anahtar(s)]))
            satirlar[f"{ad}+az"] = olcut.olc(parts, olcut.sirala_puan(lambda s, d=d: d[_anahtar(s)], KOVA))
        sonuc[bolme] = {"siralayicilar": satirlar, "test_ornegi": len(test_ornekleri),
                        "egitim_ornegi_ort": (sum(egitim_boyu) / len(egitim_boyu)) if egitim_boyu else 0}
    return sonuc


def model_sec(sonuc: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    satirlar = sonuc["gruplu-cv"]["siralayicilar"]
    modeller = {ad: s for ad, s in satirlar.items() if ad.split("-")[0] in dict(MODELLER)}
    # Once benzetim sayisi, sonra ilk oneri, sonra KUCUK degisiklik (kullanici
    # tek direnc yeterken yeniden tasarim gormek istemez), sonra yeni ihlal.
    ad = min(modeller, key=lambda a: (round(modeller[a]["simulasyon"], 3), -modeller[a]["ilk_gecerli"],
                                      round(modeller[a]["degisiklik"], 3), modeller[a]["yeni_ihlal_cozum"]))
    return ad, modeller[ad]


def tablo(sonuc: dict[str, Any]) -> str:
    def f(x, yuzde=False):
        if x is None:
            return "-"
        return f"%{x * 100:.1f}" if yuzde else f"{x:.2f}"

    out = []
    for bolme, b in sonuc.items():
        sat = b["siralayicilar"]
        ilk = next(iter(sat.values()))
        out.append(f"\n### {bolme} (test {b['test_ornegi']} aday, {ilk['parti']} varyant, "
                   f"{ilk['cozulebilir']} cozulebilir)\n")
        out.append("| siralayici | ilk oneri gecerli | ilk 3'te gecerli | benzetim (ort / en cok) "
                   "| yeni ihlal (ilk oneri) | yeni ihlal (cozum) | degisiklik |")
        out.append("|---|---|---|---|---|---|---|")
        for ad, s in sat.items():
            out.append(f"| {ad} | {f(s['ilk_gecerli'], True)} | {f(s['ilk3'], True)} | "
                       f"{f(s['simulasyon'])} / {s['simulasyon_max'] if s['simulasyon_max'] else '-'} | "
                       f"{f(s['yeni_ihlal_ilk'])} | {f(s['yeni_ihlal_cozum'])} | {f(s['degisiklik'])} |")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Kicad-apg: en az degisiklik tercihi - dort yontemin karsilastirmasi
# --------------------------------------------------------------------------

TEST_ORANI = 0.2
ILK_K = 3


def veri_yukle(klasor: Path) -> dict[str, Dataset]:
    """Veri kumelerini yukler; kayit semasi uyusmazsa ACIK hata (eski veri
    yeni hedefle sessizce yorumlanmaz)."""
    from .veri import KAYIT_SEMASI

    veriler = {sema: Dataset.load(Path(klasor) / f"veri-{sema}.jsonl") for sema in SEMALAR}
    for sema, ds in veriler.items():
        surum = ds.meta.get("kayit_semasi", 1)
        if surum != KAYIT_SEMASI:
            raise ValueError(f"veri-{sema}.jsonl kayit semasi v{surum}, beklenen v{KAYIT_SEMASI} "
                             "(maliyet / tercih hedefi yok) - veriyi yeniden uretin: python -m pcbqa.duzeltme.veri")
        if ds.feature_version != OZNITELIK_SURUMU:
            raise ValueError(f"veri-{sema}.jsonl oznitelik v{ds.feature_version}, beklenen v{OZNITELIK_SURUMU}")
    return veriler


def gelistirme_test_bolmesi(gruplar: list[str], oran: float, tohum: int) -> set[str]:
    """SON TEST gruplari (secim ve ayarda hic kullanilmaz)."""
    adlar = sorted(gruplar)
    random.Random(tohum + 7).shuffle(adlar)
    return set(adlar[:max(1, int(round(len(adlar) * oran)))]) if len(adlar) > 1 else set()


def _varyantlar() -> list[tuple[str, str, str, dict[str, Any]]]:
    """(ad, hedef, sema, model ayari) - 'gec' gecerlilik, 'soz' sozluksel hedef."""
    from .tercih import GECERLILIK, HEDEF_ADI

    out = []
    for hedef, kisa in ((GECERLILIK, "gec"), (HEDEF_ADI, "soz")):
        for model_adi, ayar in MODELLER:
            for sema in SEMALAR:
                out.append((f"{kisa}-{model_adi}-{sema}", hedef, sema, {"model": model_adi, **ayar}))
    return out


def _egit(ds: Dataset, samples: list[Sample], hedef: str, ayar: dict[str, Any], tohum: int):
    from .tercih import hedef_ornekleri

    ayar = dict(ayar)
    model_adi = ayar.pop("model")
    return fit_model(model_adi, ds.subset(hedef_ornekleri(samples, hedef)), seed=tohum, target="value", **ayar)


def _satirlar(parts, tahminler: dict[str, dict[tuple, float]], k: int = ILK_K) -> dict[str, Any]:
    from . import tercih as T

    sat: dict[str, Any] = {}

    def ekle(ad, sirala):
        sat[ad] = {pol: T.olc(parts, sirala, pol, k) for pol in ("ilk-gecerli", "ilk-k")}

    ekle("uretec (mevcut kural)", T.sirala_uretec)
    ekle("kural-elektrik", T.sirala_kural_elektrik)
    ekle("kural-elektrik+maliyet", T.sirala_kural_elektrik_maliyet)
    sat["dogrudan-en-az (hepsi dogrulanir)"] = {"dogrudan": T.olc(parts, None, "dogrudan")}
    for ad, d in sorted(tahminler.items()):
        def puan(s, d=d):
            return d[_anahtar(s)]
        ekle(f"{ad} (ham puan)", T.sirala_puan(puan))
        ekle(f"{ad}+kova0.1/degisiklik", T.sirala_puan(puan, KOVA, "n_degisiklik"))
        ekle(f"{ad}+kova0.1/maliyet", T.sirala_puan(puan, KOVA, "maliyet"))
    return sat


def _sec_anahtari(m: dict[str, Any]) -> tuple:
    g = m["ilk-gecerli"]
    return (round(g["simulasyon"], 3), round(g["pismanlik"], 4), -g["ilk_gecerli"])


def tercih_deneyi(veriler: dict[str, Dataset], kat: int = 5, tohum: int = TOHUM, test_orani: float = TEST_ORANI,
                  k: int = ILK_K) -> dict[str, Any]:
    """Gelistirme (gruplu CV, model secimi) ve dokunulmamis SON TEST.

    Son test gruplari secim ve ayar icin HIC kullanilmaz: modeller yalnizca
    gelistirme gruplarinda egitilir ve secilir, son testte bir kez olculur."""
    from . import tercih as T

    ana = veriler["ham"]
    for ad, ds in veriler.items():
        if [_anahtar(s) for s in ds.samples] != [_anahtar(s) for s in ana.samples]:
            raise ValueError(f"{ad} veri kumesi ham ile ayni orneklere sahip degil")
    test_g = gelistirme_test_bolmesi(ana.groups(), test_orani, tohum)
    gel_g = [g for g in ana.groups() if g not in test_g]
    varyant = _varyantlar()

    # 1) Gelistirme: kat-disi tahminler
    kd: dict[str, dict[tuple, float]] = {ad: {} for ad, *_ in varyant}
    for hold in _kat_gruplari(gel_g, kat, tohum):
        for ad, hedef, sema, ayar in varyant:
            ds = veriler[sema]
            egitim = [s for s in ds.samples if s.group not in test_g and s.group not in hold]
            m = _egit(ds, egitim, hedef, ayar, tohum)
            for s in ds.samples:
                if s.group in hold:
                    kd[ad][_anahtar(s)] = m.predict(s.features)
    gel_parts = T.partiler([s for s in ana.samples if s.group not in test_g])
    gel = _satirlar(gel_parts, kd, k)

    # 2) Secim (YALNIZCA gelistirme): uygulamadaki kural (+kova0.1/maliyet)
    adaylar = {ad: gel[f"{ad}+kova0.1/maliyet"] for ad, *_ in varyant}
    secilen = min(adaylar, key=lambda a: _sec_anahtari(adaylar[a]))
    secilen_soz = min((a for a in adaylar if a.startswith("soz-")), key=lambda a: _sec_anahtari(adaylar[a]))
    mevcut = "gec-gbt-tam"     # Kicad-u4k'nin GBT'si; mevcut 0.1 kurali ile

    # 3) Son test: gelistirmenin tamaminda egit, testte bir kez olc
    test_tahmin: dict[str, dict[tuple, float]] = {}
    for ad, hedef, sema, ayar in varyant:
        if ad not in {secilen, secilen_soz, mevcut, "gec-ridge-tam", "gec-gbt-ham", "soz-gbt-ham"}:
            continue
        ds = veriler[sema]
        m = _egit(ds, [s for s in ds.samples if s.group not in test_g], hedef, ayar, tohum)
        test_tahmin[ad] = {_anahtar(s): m.predict(s.features) for s in ds.samples if s.group in test_g}
    test_parts = T.partiler([s for s in ana.samples if s.group in test_g])
    test = _satirlar(test_parts, test_tahmin, k)

    # 4) Gorulmemis hata turu (gelistirme icinde): tur egitimde YOK, testte VAR
    hata: dict[str, Any] = {}
    for tur in sorted({s.extra["hata"] for s in ana.samples}):
        tah: dict[str, dict[tuple, float]] = {}
        for ad, hedef, sema, ayar in varyant:
            if ad not in {secilen_soz, mevcut}:
                continue
            ds = veriler[sema]
            egitim = [s for s in ds.samples if s.group not in test_g and s.extra["hata"] != tur]
            m = _egit(ds, egitim, hedef, ayar, tohum)
            tah[ad] = {_anahtar(s): m.predict(s.features) for s in ds.samples
                       if s.group not in test_g and s.extra["hata"] == tur}
        parts = T.partiler([s for s in ana.samples if s.group not in test_g and s.extra["hata"] == tur])
        if parts:
            hata[tur] = _satirlar(parts, tah, k)

    def sayim(samples):
        d: dict[str, int] = {}
        for s in samples:
            d[s.extra["durum"]] = d.get(s.extra["durum"], 0) + 1
        return d

    return {
        "bolme": {"gelistirme_grup": len(gel_g), "test_grup": len(test_g),
                  "gelistirme_parti": len(gel_parts), "test_parti": len(test_parts),
                  "gelistirme_durum": sayim(s for s in ana.samples if s.group not in test_g),
                  "test_durum": sayim(s for s in ana.samples if s.group in test_g),
                  "test_gruplari": sorted(test_g)},
        "gelistirme": gel, "test": test, "hata_disi": hata,
        "secilen": secilen, "secilen_sozluksel": secilen_soz, "mevcut": mevcut, "ilk_k": k,
    }


def tercih_tablosu(satirlar: dict[str, Any], baslik: str, filtre: Callable[[str], bool] = lambda a: True) -> str:
    def f(x, yuzde=False):
        if x is None:
            return "-"
        return f"%{x * 100:.1f}" if yuzde else f"{x:.2f}"

    out = [f"\n### {baslik}\n",
           "| siralayici | politika | ilk oneri gecerli | ilk 3'te cozum | benzetim (ort / en cok) | "
           "pismanlik (ort / en cok) | en dusuk maliyet secildi | secilen maliyet | degisiklik |",
           "|---|---|---|---|---|---|---|---|---|"]
    for ad, pols in satirlar.items():
        if not filtre(ad):
            continue
        for pol, m in pols.items():
            out.append(f"| {ad} | {pol} | {f(m['ilk_gecerli'], True)} | {f(m['ilk3'], True)} | "
                       f"{f(m['simulasyon'])} / {m['simulasyon_max'] or '-'} | {f(m['pismanlik'])} / "
                       f"{f(m['pismanlik_max'])} | {f(m['en_az_secildi'], True)} | {f(m['maliyet'])} | "
                       f"{f(m['degisiklik'])} |")
    return "\n".join(out)


def tercih_raporu(r: dict[str, Any]) -> str:
    b = r["bolme"]
    sec, soz, mev = r["secilen"], r["secilen_sozluksel"], r["mevcut"]

    def onemli(ad: str) -> bool:
        return (not any(ad.startswith(p) for p in ("gec-", "soz-"))
                or any(ad.startswith(x + " ") or ad.startswith(x + "+") for x in {sec, soz, mev}))

    out = [f"Gelistirme {b['gelistirme_grup']} grup / {b['gelistirme_parti']} parti, son test {b['test_grup']} "
           f"grup / {b['test_parti']} parti. Secilen (gelistirme CV, +kova0.1/maliyet): {sec}; "
           f"en iyi sozluksel: {soz}; mevcut: {mev}+kova0.1/degisiklik."]
    out.append(tercih_tablosu(r["test"], "SON TEST (secimde kullanilmadi)"))
    out.append(tercih_tablosu(r["gelistirme"], "Gelistirme - gruplu CV (kat disi)", onemli))
    for tur, sat in r["hata_disi"].items():
        out.append(tercih_tablosu(sat, f"Gorulmemis hata turu: {tur}",
                                  lambda a: not a.startswith("kural") and "ham puan" not in a))
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pcbqa.duzeltme.egitim", description=__doc__.splitlines()[0])
    ap.add_argument("--veri", type=Path, default=Path(".work/duzeltme"))
    ap.add_argument("--kat", type=int, default=5)
    ap.add_argument("--tohum", type=int, default=TOHUM)
    ap.add_argument("--test-orani", type=float, default=TEST_ORANI)
    ap.add_argument("--eski", action="store_true",
                    help="Kicad-u4k karsilastirmasini da kos (yalnizca gecerlilik etiketi)")
    ap.add_argument("--model-cikti", type=Path, default=None,
                    help=f"secilen model buraya yazilir (uretec'i gecerse). Ornek: {VARSAYILAN_MODEL}")
    args = ap.parse_args(argv)

    from . import tercih as T
    from .maliyet import MALIYET_SURUMU, VARSAYILAN_AGIRLIKLAR

    bas = time.perf_counter()
    veriler = veri_yukle(args.veri)
    ana = veriler["ham"]
    durumlar: dict[str, int] = {}
    for s in ana.samples:
        durumlar[s.extra["durum"]] = durumlar.get(s.extra["durum"], 0) + 1
    cozumsuz = len({(s.group, s.batch) for s in ana.samples if s.extra.get("parti_cozumsuz")})
    print(f"veri: {len(ana)} aday, {len(ana.groups())} grup, {len(ana.batches())} parti "
          f"({cozumsuz} cozumsuz), durumlar {durumlar}")
    r = tercih_deneyi(veriler, args.kat, args.tohum, args.test_orani)
    rapor = {"veri": {"aday": len(ana), "grup": len(ana.groups()), "parti": len(ana.batches()),
                      "cozumsuz_parti": cozumsuz, "durumlar": durumlar}, "tercih": r}
    metin = tercih_raporu(r)
    if args.eski:
        sonuc = karsilastir(veriler, args.kat, args.tohum)
        rapor["gecerlilik_karsilastirmasi"] = sonuc
        metin += "\n\n## Kicad-u4k karsilastirmasi (yalnizca gecerlilik)\n" + tablo(sonuc)
    rapor["sure_s"] = round(time.perf_counter() - bas, 1)
    (args.veri / "egitim-rapor.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
    (args.veri / "egitim-rapor.md").write_text(metin + "\n", encoding="utf-8")
    print(metin)

    secilen = r["secilen"]
    gel = r["gelistirme"]
    olcu = gel[f"{secilen}+kova0.1/maliyet"]["ilk-gecerli"]
    uretec = gel["uretec (mevcut kural)"]["ilk-gecerli"]
    geciyor = olcu["simulasyon"] < uretec["simulasyon"]
    print(f"\nsecilen: {secilen}+kova0.1/maliyet (gelistirme CV benzetim {olcu['simulasyon']:.2f}, "
          f"pismanlik {olcu['pismanlik']:.3f}; uretec {uretec['simulasyon']:.2f} / {uretec['pismanlik']:.3f})")
    if args.model_cikti is not None:
        if not geciyor:
            print("model yazilmadi: ureteci sirasini gecemedi; uygulama ureteci sirasiyla calisir")
            return 0
        ad = next(v for v in _varyantlar() if v[0] == secilen)
        _ad, hedef, sema, ayar = ad
        ds = veriler[sema]
        # Dagitilan model butun veriyle egitilir; raporlanan sayilar gelistirme
        # CV'si ve gelistirmede egitilmis modelin SON TEST olcumudur.
        m = _egit(ds, ds.samples, hedef, ayar, args.tohum)
        ozet_yolu = args.veri / "ozet.json"
        m.meta.update({
            "gorev": "duzeltme-siralama", "aile": ds.meta.get("aile"), "sema": sema,
            "hedef": hedef, "kova": KOVA, "kova_ikincil": "maliyet", "secilen_satir": f"{secilen}+kova0.1/maliyet",
            "puan": "siralama puani - OLASILIK DEGIL (kalibre edilmedi)",
            "oznitelik_surumu": OZNITELIK_SURUMU, "maliyet_surumu": MALIYET_SURUMU,
            "maliyet_agirliklari": VARSAYILAN_AGIRLIKLAR, "tercih_sirasi": T.__doc__.split("\n\n")[1].strip(),
            "egitim_tarihi": time.strftime("%Y-%m-%d"), "veri": rapor["veri"],
            "gelistirme_cv": olcu, "uretec_gelistirme_cv": uretec,
            "son_test": r["test"].get(f"{secilen}+kova0.1/maliyet", {}).get("ilk-gecerli"),
            "surumler": json.loads(ozet_yolu.read_text(encoding="utf-8")).get("surumler")
            if ozet_yolu.is_file() else None,
        })
        m.save(args.model_cikti)
        print(f"model yazildi: {args.model_cikti}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
