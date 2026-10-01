"""`pcbqa dogrula` - uc seviyeli dogrulama + PCB dal akimi + dokuz kontrol.

    pcbqa dogrula <proje> [--kosullar kosullar.yaml] [--seviye 1,2,3]
                          [--json rapor.json] [--calisma klasor]

Cikis kodu: 0 hata yok | 1 en az bir hata | 2 calistirilamadi.

Rapor sirasi bilinclidir: once KiCad'in kendi kontrolleri (seviye 1), sonra
muhendislik kurallari (2), sonra benzetim (3); PCB tarafinda once yerlesim
kisitlari ve uretim sinirlari (yonlendirme girdisi), sonra iz analizi.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from ..devre.kosullar import KosulHatasi
from ..devre.yukle import ProjeHatasi, projeden_graf
from ..kicadcli import KicadCli, KicadCliError
from .kontroller import dokuz_kontrol
from .seviye1 import seviye1
from .seviye2 import seviye2
from .seviye3 import seviye3


def calistir(proje: Path, kosullar: Path | None, seviyeler: set[int], calisma: Path,
             cli: KicadCli | None = None) -> dict[str, Any]:
    from ..pcb_akim import iz_analizi, yonlendirme_girdisi

    graf, dosyalar = projeden_graf(proje, kosullar_yolu=kosullar, cli=cli, calisma=calisma)
    rapor: dict[str, Any] = {
        "proje": dosyalar.ad,
        "graf_ozeti": graf.ozet(),
        "seviyeler": [],
    }
    sonuclar = []
    if 1 in seviyeler:
        sonuclar.append(seviye1(dosyalar.sematik, dosyalar.kart, calisma / "seviye1", cli))
    if 2 in seviyeler:
        sonuclar.append(seviye2(graf))
    if 3 in seviyeler:
        sonuclar.append(seviye3(graf, calisma / "seviye3"))
    iz = iz_analizi(graf)
    sonuclar.append(iz)
    kontroller = dokuz_kontrol(graf, iz)

    gorulen: set[str] = set()
    for s in sonuclar:
        tekil = []
        for f in s.bulgular:
            if f.finding_id in gorulen:
                continue
            gorulen.add(f.finding_id)
            tekil.append(f)
        s.bulgular = tekil
        rapor["seviyeler"].append(s.as_dict())
    rapor["kontroller"] = []
    for k in kontroller:
        d = k.as_dict()
        # Seviyelerde zaten raporlanan bulgu tekrar sayilmaz; kontrol durumu korunur.
        d["bulgular"] = [f.as_dict() for f in k.bulgular if f.finding_id not in gorulen]
        rapor["kontroller"].append(d)
        gorulen |= {f.finding_id for f in k.bulgular}
    rapor["yonlendirme_girdisi"] = yonlendirme_girdisi(graf)
    rapor["eksik_bilgi"] = graf.eksik_raporu()
    rapor["hata_sayisi"] = sum(1 for s in rapor["seviyeler"] for f in s["bulgular"] if f["severity"] == "error") + \
        sum(1 for k in rapor["kontroller"] for f in k["bulgular"] if f["severity"] == "error")
    rapor["_graf"] = graf
    return rapor


_ISARET = {"error": "!!", "warning": " !", "info": " -"}


def metin(rapor: dict[str, Any], ayrinti: bool = False) -> str:
    o = rapor["graf_ozeti"]
    satir = [f"DOGRULAMA - {rapor['proje']}",
             f"  devre grafi: {o['bilesen']} bilesen, {o['ag']} ag, gerilimi bilinen ag {o['gerilimi_bilinen_ag']}, "
             f"rolu bilinen {o['rolu_bilinen_bilesen']}, eksiksiz {o['eksiksiz_bilesen']} "
             f"(kaynaklar: {', '.join(o['kaynaklar'])})", ""]
    for s in rapor["seviyeler"]:
        durum = ("ATLANDI - " + s["atlanma_nedeni"]) if not s["calisti"] else \
            ("GECTI" if s["gecti"] else "KALDI")
        sy = s["sayilar"]
        satir.append(f"[{s['seviye']}] {s['ad']}: {durum}  (hata {sy['error']}, uyari {sy['warning']}, bilgi {sy['info']})")
        for f in s["bulgular"]:
            if f["severity"] == "info" and not ayrinti:
                continue
            satir.append(f"   {_ISARET[f['severity']]} {f['rule_id']}: {f['message']}")
        for n in s["ekler"].get("notlar", []) if ayrinti else []:
            satir.append(f"    not: {n}")
    satir.append("")
    satir.append("KONTROLLER")
    for k in rapor["kontroller"]:
        satir.append(f"  {k['durum'].upper():<14} {k['ad']:<22} {k['amac']}")
        if k["neden"]:
            satir.append(f"                 neden: {k['neden']}")
        for f in k["bulgular"]:
            if f["severity"] == "info" and not ayrinti:
                continue
            satir.append(f"     {_ISARET[f['severity']]} {f['message']}")
    yg = rapor["yonlendirme_girdisi"]
    satir += ["", "YONLENDIRME GIRDISI (sira: yerlesim kisitlari -> uretim sinirlari -> dal akimlari)"]
    for kk in yg["yerlesim_kisitlari"]:
        durum = {True: "ok", False: "IHLAL", None: "?"}[kk["saglaniyor"]]
        satir.append(f"  {durum:<6}{kk['tur']}: {kk['bilesen']} -> {kk['hedef']} "
                     f"{kk['mevcut_mm'] if kk['mevcut_mm'] is not None else '?'} mm (azami {kk['azami_mm']:g})")
    u = yg["uretim_sinirlari"]
    satir.append(f"  uretim: {u['profil']} iz>={u['min_iz_mm']:g} aciklik>={u['min_aciklik_mm']:g} "
                 f"delik>={u['min_delik_mm']:g} halka>={u['min_halka_mm']:g} kenar>={u['min_kenar_mm']:g} mm")
    for ad, ag in yg["aglar"].items():
        for n in ag.get("notlar", []):
            satir.append(f"  {ad}: not - {n}")
        if "dallar" not in ag:
            continue
        satir.append(f"  {ad}: toplam {ag['toplam_a']:g} A, kaynak {ag['kaynak']}")
        for d in ag["dallar"]:
            ek = f", azami uzunluk {d['azami_uzunluk_mm']:g} mm" if "azami_uzunluk_mm" in d else ""
            satir.append(f"     {d['den']} -> {d['e']}: {d['surekli_a']:g} A, genislik >= "
                         f"{d['onerilen_genislik_mm']:g} mm (~{d['tahmini_uzunluk_mm']:g} mm){ek}")
    eksik = rapor["eksik_bilgi"]
    satir += ["", f"EKSIK BILGI: {len(eksik)} bilesende (ayrinti icin --ayrinti ya da --json)"]
    if ayrinti:
        for ref, liste in eksik.items():
            satir.append(f"  {ref}: " + " | ".join(liste))
    satir.append("")
    satir.append(f"toplam hata: {rapor['hata_sayisi']}")
    return "\n".join(satir)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="pcbqa.dogrula",
                                 description="Uc seviyeli devre dogrulamasi (ERC/DRC, muhendislik, ngspice) "
                                             "+ PCB dal akimi + dokuz kontrol")
    ap.add_argument("proje", type=Path, help="Proje klasoru ya da .kicad_pro/.kicad_sch/.kicad_pcb")
    ap.add_argument("--kosullar", type=Path, default=None, help="Calisma kosullari / gereksinimler (YAML/JSON)")
    ap.add_argument("--seviye", default="1,2,3", help="Calisacak seviyeler (varsayilan 1,2,3)")
    ap.add_argument("--json", type=Path, default=None, help="Raporu JSON olarak yaz")
    ap.add_argument("--graf-json", type=Path, default=None, help="Devre grafini JSON olarak yaz")
    ap.add_argument("--calisma", type=Path, default=None, help="Ara dosyalar (netlist, ERC/DRC, SPICE)")
    ap.add_argument("--ayrinti", action="store_true", help="Bilgi bulgularini ve eksikleri de yaz")
    ap.add_argument("--veri", type=Path, default=None,
                    help="Sonucu ML veri kumesine (JSONL, ml/dataset.py bicimi) ornek olarak ekle")
    ap.add_argument("--etiket", default="gecti", choices=("gecti", "tj_marj", "hata_sayisi"),
                    help="--veri ile yazilacak etiket")
    ap.add_argument("--kicad-cli", default=None)
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        seviyeler = {int(s) for s in args.seviye.split(",") if s.strip()}
    except ValueError:
        print(f"hata: --seviye 1,2,3 bicimindedir ({args.seviye!r})", file=sys.stderr)
        return 2
    calisma = args.calisma or Path(tempfile.mkdtemp(prefix="pcbqa-dogrula-"))
    try:
        cli = KicadCli(args.kicad_cli) if args.kicad_cli else None
        rapor = calistir(args.proje, args.kosullar, seviyeler, calisma, cli)
    except (ProjeHatasi, KosulHatasi, KicadCliError, OSError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2
    graf = rapor.pop("_graf")
    print(metin(rapor, args.ayrinti))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(rapor, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"JSON rapor: {args.json}")
    if args.graf_json:
        args.graf_json.parent.mkdir(parents=True, exist_ok=True)
        args.graf_json.write_text(json.dumps(graf.as_dict(), indent=2, ensure_ascii=False, default=str),
                                  encoding="utf-8")
        print(f"devre grafi: {args.graf_json}")
    if args.veri:
        from ..ml.devre_veri import ekle, ornek

        s = ornek(graf, rapor, etiket_turu=args.etiket)
        if s is None:
            print(f"ML verisi: '{args.etiket}' etiketi bu projede olculemedi - ornek yazilmadi")
        else:
            try:
                ds = ekle(args.veri, s)
                print(f"ML verisi: {args.veri} ({len(ds)} ornek)")
            except ValueError as exc:
                print(f"hata: ML verisi yazilamadi: {exc}", file=sys.stderr)
    return 1 if rapor["hata_sayisi"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
