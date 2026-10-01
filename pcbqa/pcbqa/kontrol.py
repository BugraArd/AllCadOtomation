"""`pcbqa kontrol` - butun kontroller TEK kosuda: kalite skoru + dogrulama.

    pcbqa kontrol <proje> [--kosullar k.yaml] [--seviye 1,2,3] [--kalite-yok]
                          [--ayrinti] [--json rapor.json]

Cikis kodu: 0 hata yok | 1 en az bir hata | 2 calistirilamadi.

Neden ayri bir komut: `analiz` (kalite kurallari + ERC/DRC + skor) ile
`dogrula` (seviye 1 ERC/DRC/parite, 2 muhendislik, 3 ngspice, PCB dal akimi,
9 kontrol) ayni projede ard arda kosuldugunda ERC ve DRC IKI KEZ calisiyordu.
Burada seviye 1'in urettigi `erc.json` / `drc.json` kalite skoruna da verilir;
KiCad bir kez kosar. Analiz DRC'yi paritesiz kosar, seviye 1 `--schematic-parity`
ile - parite grubu skordan atlanir ki skor `pcbqa analiz` ile AYNI kalsin
(pic_programmer'da olculdu, bkz. tests/test_kontrol.py).

Masaustu arayuzunun Kontrol sekmesi bu modulu cagirir; ikinci bir mantik
yazilmaz. Satirlar (`KontrolSatiri`) arayuzun ozet tablosudur, `metin` CLI'nin
ve arayuzun tam raporudur.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_ISARET = {"error": "!!", "warning": " !", "info": " -"}


@dataclass
class KontrolSatiri:
    """Ozet tablosunun bir satiri: bir seviye, bir kontrol ya da kalite skoru."""

    grup: str          # "kalite" | "seviye" | "kontrol" | "bilgi"
    ad: str
    durum: str
    hata: int = 0
    uyari: int = 0
    bilgi: int = 0
    ayrinti: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"grup": self.grup, "ad": self.ad, "durum": self.durum, "hata": self.hata,
                "uyari": self.uyari, "bilgi": self.bilgi, "ayrinti": self.ayrinti}


@dataclass
class KontrolRaporu:
    proje: str
    satirlar: list[KontrolSatiri]
    metin: str
    hata_sayisi: int
    skor: float | None = None
    # True: ERC/DRC yalnizca seviye 1'de kostu, kalite skoru onun raporunu kullandi
    erc_drc_tek_kosu: bool = False
    dogrulama: dict[str, Any] | None = None
    kalite: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"proje": self.proje, "hata_sayisi": self.hata_sayisi, "skor": self.skor,
                "erc_drc_tek_kosu": self.erc_drc_tek_kosu,
                "satirlar": [s.as_dict() for s in self.satirlar],
                "dogrulama": self.dogrulama, "kalite": self.kalite}


def _bulgu_satirlari(bulgular: list[dict], ayrinti: bool = True) -> list[str]:
    return [f"{_ISARET.get(f['severity'], ' ?')} {f.get('source', '')}:{f['rule_id']}: {f['message']}"
            for f in bulgular if ayrinti or f["severity"] != "info"]


def _sayilar(bulgular: list[dict]) -> tuple[int, int, int]:
    return tuple(sum(1 for f in bulgular if f["severity"] == s) for s in ("error", "warning", "info"))


def _seviye1_raporlari(dogrulama: dict[str, Any] | None) -> tuple[Path | None, Path | None] | None:
    """Seviye 1 ERC/DRC'yi eksiksiz kosturduysa raporlarin yollari, yoksa None.

    Eksik bir rapor (ERC calismadi, kicad-cli yok) yeniden KULLANILMAZ: o
    durumda analiz kendi ERC/DRC'sini kosar - sessizce eksik skor uretmek
    yerine bir kez fazla calismak.
    """
    if not dogrulama:
        return None
    for s in dogrulama["seviyeler"]:
        if s["seviye"] != 1 or not s["calisti"]:
            continue
        e = s["ekler"]
        drc = Path(e["drc"]) if e.get("drc") else None
        erc = Path(e["erc"]) if e.get("erc") else None
        if drc is None or not drc.is_file():
            return None
        if "erc" in e and (erc is None or not erc.is_file()):
            return None
        return erc, drc
    return None


def kalite_raporu(proje: Path, calisma: Path, seviye1: tuple[Path | None, Path | None] | None = None):
    """`pcbqa analiz`in raporu; `seviye1` verilirse ERC/DRC oradan okunur."""
    from . import __main__ as ana

    argv = [str(proje), "--work-dir", str(calisma)]
    if seviye1 is not None:
        argv.append("--no-kicad-checks")
    args = ana.build_parser().parse_args(argv)
    calisma.mkdir(parents=True, exist_ok=True)
    rapor = ana.analyze(args, calisma)
    if seviye1 is not None:
        erc, drc = seviye1
        if erc is not None:
            rapor.findings += ana.kicad_findings(erc, "kicad-erc")
        rapor.findings += ana.kicad_findings(drc, "kicad-drc", skip_groups=("schematic_parity",))
        ana.sort_findings(rapor.findings)
    return rapor


def calistir(proje: Path, kosullar: Path | None = None, seviyeler: set[int] | None = None,
             kalite: bool = True, calisma: Path | None = None, ayrinti: bool = False) -> KontrolRaporu:
    from .dogrulama import dogrula
    from .report import render

    proje = Path(proje)
    seviyeler = {1, 2, 3} if seviyeler is None else set(seviyeler)
    calisma = Path(calisma) if calisma else Path(tempfile.mkdtemp(prefix="pcbqa-kontrol-"))
    satirlar: list[KontrolSatiri] = []
    metinler: list[str] = []
    hata = 0

    # 1) Dogrulama (seviye 1 ERC/DRC'yi BURADA kosar)
    d = dogrula.calistir(proje, kosullar, seviyeler, calisma / "dogrula")
    d.pop("_graf", None)

    # 2) Kalite skoru - mumkunse seviye 1'in raporlariyla
    skor = None
    tek_kosu = False
    kalite_dict = None
    if kalite:
        s1 = _seviye1_raporlari(d)
        try:
            r = kalite_raporu(proje, calisma / "kalite", s1)
        except Exception as exc:  # noqa: BLE001 - kart yoksa analiz calismaz; dogrulama yine gosterilir
            satirlar.append(KontrolSatiri("kalite", "Kalite skoru (analiz)", "ATLANDI",
                                          ayrinti=[f"calistirilamadi: {exc}"]))
            metinler.append(f"KALITE SKORU: atlandi - {exc}")
        else:
            tek_kosu = s1 is not None
            skor = round(r.score, 1)
            kalite_dict = r.as_dict()
            bulgular = [f.as_dict() for f in r.findings]
            h, u, b = _sayilar(bulgular)
            not_ = ("ERC/DRC seviye 1 ile ortak (tek kosu)" if tek_kosu
                    else "ERC/DRC analiz icinde ayrica kostu")
            satirlar.append(KontrolSatiri("kalite", "Kalite skoru (analiz)", f"skor {skor:g}", h, u, b,
                                          [f"skor {skor:g}/100 - {not_}", ""] + (_bulgu_satirlari(bulgular) or ["(bulgu yok)"])))
            metinler.append(render(r, color=False) + f"\n({not_})")
            # ERC/DRC bulgulari seviye 1'de de var: yalnizca kendi kurallari sayilir.
            hata += sum(1 for f in r.findings if f.severity == "error"
                        and not f.source.startswith("kicad-"))

    # 3) Seviyeler + 9 kontrol
    for s in d["seviyeler"]:
        h, u, b = (s["sayilar"][k] for k in ("error", "warning", "info"))
        durum = "ATLANDI" if not s["calisti"] else ("GECTI" if s["gecti"] else "KALDI")
        ayr = [f"atlanma nedeni: {s['atlanma_nedeni']}"] if not s["calisti"] else []
        ayr += _bulgu_satirlari(s["bulgular"], ayrinti=True)
        ayr += [f"not: {n}" for n in s["ekler"].get("notlar", [])]
        satirlar.append(KontrolSatiri("seviye", f"[{s['seviye']}] {s['ad']}", durum, h, u, b,
                                      ayr or ["(bulgu yok)"]))
    for k in d["kontroller"]:
        h, u, b = _sayilar(k["bulgular"])
        ayr = [f"amac: {k['amac']}"] + ([f"neden: {k['neden']}"] if k["neden"] else [])
        ayr += _bulgu_satirlari(k["bulgular"]) or ["(yeni bulgu yok - seviyelerde raporlananlar tekrar sayilmaz)"]
        satirlar.append(KontrolSatiri("kontrol", k["ad"], k["durum"].upper(), h, u, b, ayr))
    eksik = d["eksik_bilgi"]
    satirlar.append(KontrolSatiri("bilgi", "Eksik bilgi", f"{len(eksik)} bilesen", bilgi=len(eksik),
                                  ayrinti=[f"{ref}: " + " | ".join(liste) for ref, liste in eksik.items()]
                                  or ["(eksik yok)"]))
    metinler.append(dogrula.metin(d, ayrinti))
    hata += d["hata_sayisi"]
    metinler.append(f"TOPLAM HATA: {hata}")
    return KontrolRaporu(proje=d["proje"], satirlar=satirlar, metin="\n\n".join(metinler), hata_sayisi=hata,
                         skor=skor, erc_drc_tek_kosu=tek_kosu, dogrulama=d, kalite=kalite_dict)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="pcbqa.kontrol",
                                 description="Butun kontroller tek kosuda: kalite skoru + uc seviyeli "
                                             "dogrulama + PCB dal akimi + dokuz kontrol")
    ap.add_argument("proje", type=Path, help="Proje klasoru ya da .kicad_pro/.kicad_sch/.kicad_pcb")
    ap.add_argument("--kosullar", type=Path, default=None, help="Calisma kosullari / gereksinimler (YAML/JSON)")
    ap.add_argument("--seviye", default="1,2,3", help="Dogrulama seviyeleri (varsayilan 1,2,3)")
    ap.add_argument("--kalite-yok", action="store_true", help="Kalite skorunu (analiz) atla")
    ap.add_argument("--calisma", type=Path, default=None, help="Ara dosyalar")
    ap.add_argument("--ayrinti", action="store_true", help="Bilgi bulgularini ve eksikleri de yaz")
    ap.add_argument("--json", type=Path, default=None, help="Raporu JSON olarak yaz")
    return ap


def main(argv: list[str] | None = None) -> int:
    from .devre.kosullar import KosulHatasi
    from .devre.yukle import ProjeHatasi
    from .kicadcli import KicadCliError

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        seviyeler = {int(s) for s in args.seviye.split(",") if s.strip()}
    except ValueError:
        print(f"hata: --seviye 1,2,3 bicimindedir ({args.seviye!r})", file=sys.stderr)
        return 2
    try:
        r = calistir(args.proje, args.kosullar, seviyeler, kalite=not args.kalite_yok,
                     calisma=args.calisma, ayrinti=args.ayrinti)
    except (ProjeHatasi, KosulHatasi, KicadCliError, OSError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2
    print(r.metin)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(r.as_dict(), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"JSON rapor: {args.json}")
    return 1 if r.hata_sayisi else 0


if __name__ == "__main__":
    raise SystemExit(main())
