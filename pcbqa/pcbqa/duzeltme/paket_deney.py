"""Paket bazli karsilastirmali degerlendirme (Kicad-7cb).

    python -m pcbqa.duzeltme.paket_deney --dogal .work/duzeltme-dogal --dengeli .work/duzeltme-dengeli

Soru: dengesiz (dogal) veriyle egitilen gecerlilik modeli, dengeli veriyle
egitilene gore paketle ilgili davranislari ne kadar iyi temsil ediyor?

Kurgu (AYNI model ve AYNI degerlendirme yontemi; yalnizca egitim verisi degisir):

  her veri kumesi temel tasarim GRUBUNA gore egitim / test olarak bolunur
  (egitim.gelistirme_test_bolmesi; ayni temelin paket varyantlari tek tarafta)

  dogal -> dengeli-test           temel sonuc (mevcut dengesiz veri)
  dogal+cogaltma -> dengeli-test  dogal egitimdeki az paketli gruplar COGALTILIR
                                  (yalnizca egitim tarafinda, bolmeden SONRA):
                                  "cogaltmak" ile "uretmek" farkini olcer
  dengeli -> dengeli-test         yeni veri
  dogal -> dogal-test, dengeli -> dogal-test   ters yonde kontrol

Model: gecerlilik hedefli GBT, iki sema: `ham` (fizik formulu gormez -
paket kestirmesini ogrenebilecek olan budur) ve `tam` (kapali form on hesabi).
Karar esigi 0.5: model puani OLASILIK DEGILDIR (kalibre edilmedi); esik
yalnizca hata sayimlari icin MUHENDISLIK SECIMIDIR.

Sayimlar adayin uygulandiktan sonraki R1 paketi ve gecersizlik nedeni
bazinda: ornek, gercek gecersiz, yakalanan (gecersiz dedi, gecersiz),
kacirilan (gecerli dedi, gecersiz), yanlis uyari (gecersiz dedi, gecerli).
`denetlenemedi` adaylar sayima girmez. AZ_ORNEK'ten az ornekli hucreler
"az ornek" isaretlenir - oradan guclu basari iddiasi kurulmaz.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..ml.dataset import Dataset, Sample
from . import tercih as T
from .egitim import MODELLER, TOHUM, _egit, gelistirme_test_bolmesi, veri_yukle

ESIK = 0.5
AZ_ORNEK = 30
SEMALAR_DENEY = ("ham", "tam")


def bol(ds: Dataset, tohum: int = TOHUM, oran: float = 0.2) -> tuple[list[Sample], list[Sample]]:
    test_g = gelistirme_test_bolmesi(ds.groups(), oran, tohum)
    return ([s for s in ds.samples if s.group not in test_g], [s for s in ds.samples if s.group in test_g])


def egitim_cogalt(samples: list[Sample], tohum: int = TOHUM, anahtar: str = "ref_paket_ust") -> list[Sample]:
    """YALNIZCA egitim tarafi: az temsil edilen paketlerin GRUPLARINI (temel
    tasarim butun halinde) rastgele kopyalayarak her paketin ornek sayisini en
    buyuge yaklastirir. Kopyalar yeni bilgi tasimaz - bu satir 'uretmeden
    dengelemenin' ne kazandirdigini (kazandirmadigini) olcmek icindir."""
    rng = random.Random(tohum + 3)
    gruplar: dict[str, dict[str, list[Sample]]] = defaultdict(dict)
    for s in samples:
        gruplar[s.extra.get(anahtar, "")].setdefault(s.group, []).append(s)
    say = {p: sum(len(v) for v in g.values()) for p, g in gruplar.items()}
    hedef = max(say.values()) if say else 0
    out = list(samples)
    for p, g in gruplar.items():
        adlar = sorted(g)
        k = 0
        while say[p] < hedef and adlar:
            ad = rng.choice(adlar)
            k += 1
            out += [Sample(list(s.features), s.label, f"{s.group}#{k}", f"{s.batch}#{k}", s.extra) for s in g[ad]]
            say[p] += len(g[ad])
    return out


def _sayim(test: list[Sample], tahmin: dict[int, float]) -> dict[str, Any]:
    hucre: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for s in test:
        if s.extra["durum"] not in ("gecerli", "gecersiz"):
            continue
        dedi_gecersiz = tahmin[id(s)] < ESIK
        gercek_gecersiz = s.extra["durum"] == "gecersiz"
        for anahtar in ((s.extra.get("aday_paket_ust", "?"), "hepsi"), (s.extra.get("aday_paket_ust", "?"),
                                                                       s.extra.get("neden", "?")),
                        ("hepsi", "hepsi"), ("hepsi", s.extra.get("neden", "?"))):
            h = hucre[anahtar]
            h["ornek"] += 1
            h["gecersiz"] += gercek_gecersiz
            h["yakalanan"] += gercek_gecersiz and dedi_gecersiz
            h["kacirilan"] += gercek_gecersiz and not dedi_gecersiz
            h["yanlis_uyari"] += (not gercek_gecersiz) and dedi_gecersiz
    out = {}
    for (paket, neden), h in sorted(hucre.items()):
        d = dict(h)
        d["az_ornek"] = d["ornek"] < AZ_ORNEK
        d["kacirma_orani"] = d["kacirilan"] / d["gecersiz"] if d["gecersiz"] else None
        gecerli = d["ornek"] - d["gecersiz"]
        d["yanlis_uyari_orani"] = d["yanlis_uyari"] / gecerli if gecerli else None
        out[f"{paket}|{neden}"] = d
    return out


def _siralama(test: list[Sample], tahmin: dict[int, float]) -> dict[str, Any]:
    """Uygulamadaki gibi: puan + 0.1 kova (degisiklik) - referans paketine gore."""
    sirala = T.sirala_puan(lambda s: tahmin[id(s)], 0.1, "n_degisiklik")
    out = {}
    paketler = sorted({s.extra.get("ref_paket_ust", "?") for s in test})
    for p in ["hepsi", *paketler]:
        parts = T.partiler([s for s in test if p == "hepsi" or s.extra.get("ref_paket_ust") == p])
        out[p] = T.olc(parts, sirala, "ilk-gecerli")
    return out


def degerlendir_satir(veriler_egitim: dict[str, Dataset], egitim: dict[str, list[Sample]],
                      test: dict[str, list[Sample]], tohum: int) -> dict[str, Any]:
    out = {}
    ayar = dict(MODELLER)["gbt"]
    for sema in SEMALAR_DENEY:
        m = _egit(veriler_egitim[sema], egitim[sema], T.GECERLILIK, {"model": "gbt", **ayar}, tohum)
        tahmin = {id(s): m.predict(s.features) for s in test[sema]}
        out[f"gbt-{sema}"] = {"hata_sayimi": _sayim(test[sema], tahmin), "siralama": _siralama(test[sema], tahmin),
                              "egitim_ornegi": len(egitim[sema]), "test_ornegi": len(test[sema])}
    return out


def _sizinti(a: list[Sample], b: list[Sample]) -> int:
    return len({s.extra.get("temel_imza") for s in a} & {s.extra.get("temel_imza") for s in b} - {None})


def deney(dogal: Path, dengeli: Path, tohum: int = TOHUM) -> dict[str, Any]:
    A, B = veri_yukle(dogal), veri_yukle(dengeli)
    a_tr, a_te, b_tr, b_te = {}, {}, {}, {}
    for sema in SEMALAR_DENEY:
        a_tr[sema], a_te[sema] = bol(A[sema], tohum)
        b_tr[sema], b_te[sema] = bol(B[sema], tohum)
    a_cog = {sema: egitim_cogalt(a_tr[sema], tohum) for sema in SEMALAR_DENEY}

    def dagilim(samples: list[Sample]) -> dict[str, int]:
        d: dict[str, int] = defaultdict(int)
        for s in samples:
            d[s.extra.get("ref_paket_ust", "?")] += 1
        return dict(sorted(d.items()))

    sonuc = {
        "dagilim": {"dogal_egitim": dagilim(a_tr["ham"]), "dogal_cogaltilmis_egitim": dagilim(a_cog["ham"]),
                    "dengeli_egitim": dagilim(b_tr["ham"]), "dogal_test": dagilim(a_te["ham"]),
                    "dengeli_test": dagilim(b_te["ham"])},
        "grup": {"dogal_egitim": len({s.group for s in a_tr["ham"]}), "dogal_test": len({s.group for s in a_te["ham"]}),
                 "dengeli_egitim": len({s.group for s in b_tr["ham"]}),
                 "dengeli_test": len({s.group for s in b_te["ham"]})},
        "sizinti_temel_imza": {"dogal_egitim~dengeli_test": _sizinti(a_tr["ham"], b_te["ham"]),
                               "dengeli_egitim~dogal_test": _sizinti(b_tr["ham"], a_te["ham"])},
        "satirlar": {
            "dogal -> dengeli-test": degerlendir_satir(A, a_tr, b_te, tohum),
            "dogal+cogaltma -> dengeli-test": degerlendir_satir(A, a_cog, b_te, tohum),
            "dengeli -> dengeli-test": degerlendir_satir(B, b_tr, b_te, tohum),
            "dogal -> dogal-test": degerlendir_satir(A, a_tr, a_te, tohum),
            "dengeli -> dogal-test": degerlendir_satir(B, b_tr, a_te, tohum),
        },
        "esik": ESIK, "az_ornek": AZ_ORNEK,
    }
    return sonuc


def rapor(r: dict[str, Any]) -> str:
    def f(x, yuzde=True):
        if x is None:
            return "-"
        return f"%{x * 100:.1f}" if yuzde else f"{x:.2f}"

    out = ["## Dagilim (temel tasarimin R1 paketi -> aday sayisi)\n"]
    for ad, d in r["dagilim"].items():
        out.append(f"- {ad}: {d}")
    out.append(f"\nGrup sayilari: {r['grup']}; temel imza sizintisi: {r['sizinti_temel_imza']}")
    for satir, modeller in r["satirlar"].items():
        for model, m in modeller.items():
            out.append(f"\n### {satir} - {model} (egitim {m['egitim_ornegi']}, test {m['test_ornegi']} aday)\n")
            out.append("| aday R1 paketi | neden | ornek | gecersiz | yakalanan | kacirilan | yanlis uyari | not |")
            out.append("|---|---|---|---|---|---|---|---|")
            for anahtar, h in m["hata_sayimi"].items():
                paket, neden = anahtar.split("|")
                if neden != "hepsi" and paket != "hepsi":
                    continue
                out.append(f"| {paket} | {neden} | {h['ornek']} | {h['gecersiz']} | {h['yakalanan']} | "
                           f"{h['kacirilan']} ({f(h['kacirma_orani'])}) | {h['yanlis_uyari']} "
                           f"({f(h['yanlis_uyari_orani'])}) | {'AZ ORNEK' if h['az_ornek'] else ''} |")
            out.append("\n| referans paketi | parti | ilk oneri gecerli | benzetim | pismanlik |")
            out.append("|---|---|---|---|---|")
            for p, s in m["siralama"].items():
                out.append(f"| {p} | {s['cozulebilir']} | {f(s['ilk_gecerli'])} | {f(s['simulasyon'], False)} | "
                           f"{f(s['pismanlik'], False)} |")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pcbqa.duzeltme.paket_deney", description=__doc__.splitlines()[0])
    ap.add_argument("--dogal", type=Path, required=True)
    ap.add_argument("--dengeli", type=Path, required=True)
    ap.add_argument("--cikti", type=Path, default=None, help="varsayilan: --dengeli klasoru")
    ap.add_argument("--tohum", type=int, default=TOHUM)
    args = ap.parse_args(argv)
    bas = time.perf_counter()
    r = deney(args.dogal, args.dengeli, args.tohum)
    r["sure_s"] = round(time.perf_counter() - bas, 1)
    cikti = args.cikti or args.dengeli
    (cikti / "paket-deney.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    metin = rapor(r)
    (cikti / "paket-deney.md").write_text(metin + "\n", encoding="utf-8")
    print(metin)
    return 0


if __name__ == "__main__":
    sys.exit(main())
