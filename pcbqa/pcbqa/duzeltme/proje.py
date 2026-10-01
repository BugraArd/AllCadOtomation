"""Duzeltme adaylarini GERCEK KiCad projesinde dogrulama (Kicad-ecd).

Bellekteki deney (veri.py) adaylari KiCad'in okuyucularinin urettigi veri
yapilariyla kuruyordu. Bu modul ayni adaylari gercek .kicad_sch / .kicad_pcb
dosyalarina uygular ve butun dogrulama zincirinden gecirir:

  1 kopya      temel proje klasoru adayin AYRI klasorune kopyalanir (KiCad
               kilit dosyalari ve yedek klasorleri haric; kilit dosyasina
               DOKUNULMAZ). Temel proje ve kutuphaneler salt okunur; deney
               sonunda temel dosyalarin ozeti yeniden alinir.
  2 uygula     degisiklikler SEMATIGE (Value / Tolerance / Footprint alani)
               ve KARTA (Value; footprint takasi KiCad kutuphanesinin kendi
               .kicad_mod dosyasindan, UUID / sembol yolu / konum / pad aglari
               korunarak) yazilir. Footprint degistiyse kart yeniden
               yonlendirilir (bolucu.rayli_yonlendir; genel autorouter degil).
  3 geri oku   dosyalar yeniden okunur: degisiklik diskte mi, UUID / referans /
               pin-pad / sematik baglantisi korunmus mu, bastirma envanteri
               (PWR_FLAG, no-connect, dislama) degismemis mi
  4 KiCad      kicad-cli: netlist, ERC, DRC + sematik paritesi. Komut, cikis
               kodu ve JSON rapor saklanir. Bakir dokumu varsa DRC dolguyu
               yeniler (--refill-zones, dosya kaydedilmez).
  5 elektrik   KAYDEDILMIS sematigin kicad-cli netlist'inden devre grafi ->
               ngspice (seviye3 + 16 capraz kose), seviye2, PCB geometrisi ve
               iz analizi (yol direnci, gerilim dusumu, darbogaz)
  6 durum      gecti | kaldi | veri-model-eksik | arac-hatasi
  7 kayit      deney.jsonl: temel/aday kimligi, degisiklikler, dosya ozetleri,
               arac/model/kutuphane surumleri, kosullar, ERC/DRC ve elektriksel
               sonuclar, egitime aktarilabilirlik. Onbellek anahtari dosya,
               kosul, kural, kod ve surumlerin ozetidir; biri degisince gecersiz.
  8 secim      GECTI adaylar arasinda en dusuk degisiklik maliyeti (secim.py,
               Kicad-d8k); esitlikte daha az yeni ihlal, sonra kararli ureteci
               kimligi. Gecerlilik (durum, egitim), tercih (`tercih`) ve
               okunur gerekce (`aciklamalar`, aciklama.py) ayri alanlardir.

Komutlar (pcbqa/ icinden):

    python -m pcbqa.duzeltme.proje referans --cikti samples/bolucu/referans
    python -m pcbqa.duzeltme.proje deney --temel samples/bolucu/referans/bolucu-hatali \\
        --cikti .work/gercek-deney [--hepsi] [--model yol]
    python -m pcbqa.duzeltme.proje goster .work/gercek-deney

Bastirma YOK: ERC/DRC ihlali PWR_FLAG, no-connect isareti ya da ihlal
dislamasi eklenerek gizlenmez. Envanter temel ile aday arasinda karsilastirilir.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
import tempfile
import time
import uuid as uuidlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..dogrulama.seviye3 import seviye3
from ..sexpr import QuotedStr, as_float, child, children, head, parse_with_stats, value
from .adaylar import Aday, adaylari_uret
from .bolucu import (FOOTPRINT, IZ_MM, Bolucu, BolucuParametre, Roller, YonlendirmeHatasi,
                     kart_siniri, rayli_yonlendir, yerlesim, yonlendirici_kur)
from .degerlendir import Degerlendirme, degerlendir
from .maliyet import maliyet
from .tasarim import MPN_ALANI, TOLERANS_ALANI, Degisiklik, Tasarim, deger_metni, tolerans_metni

DENEY_SEMASI = 1
DURUMLAR = ("gecti", "kaldi", "veri-model-eksik", "arac-hatasi")

# Kozmetik DRC turleri: kaydedilir ama adayi KALDIRMAZ (muhendislik secimi:
# elektriksel ya da uretim sonucu yok). Digerleri - uyari dahil - kaldirir.
KOZMETIK_DRC = frozenset({"silk_overlap", "silk_over_copper", "silk_edge_clearance",
                          "text_height", "text_thickness"})
# Kopyalanmayan dosyalar: KiCad kilitleri (acik proje), yedekler, raporlar.
KOPYALANMAZ = ("~*.lck", "*-backups", "*.pcbqa-bak", "_pcbqa")
# Deterministik UUID ad alani: ayni aday ayni dosyayi uretsin (onbellek).
_UUID_AD = uuidlib.UUID("8f0c2a4e-6b1d-4e0a-9c55-0d1e2f3a4b5c")


class ProjeHatasi(RuntimeError):
    """Gercek proje hattinda bir adim yapilamadi (arac / dosya)."""


# --------------------------------------------------------------------------
# Proje dosyalari
# --------------------------------------------------------------------------


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass
class Proje:
    klasor: Path
    ad: str

    @property
    def pro(self) -> Path:
        return self.klasor / f"{self.ad}.kicad_pro"

    @property
    def sch(self) -> Path:
        return self.klasor / f"{self.ad}.kicad_sch"

    @property
    def pcb(self) -> Path:
        return self.klasor / f"{self.ad}.kicad_pcb"

    def ozetler(self) -> dict[str, str]:
        return {p.name: _sha(p) for p in (self.pro, self.sch, self.pcb) if p.is_file()}

    @classmethod
    def bul(cls, yol: Path) -> "Proje":
        yol = Path(yol)
        if yol.is_file():
            return cls(yol.parent, yol.stem)
        pros = sorted(yol.glob("*.kicad_pro"))
        if len(pros) != 1:
            raise ProjeHatasi(f"{yol}: tek .kicad_pro bekleniyordu ({len(pros)} bulundu)")
        return cls(yol, pros[0].stem)


def kopyala(temel: Proje, hedef: Path) -> Proje:
    """Temel projeyi `hedef`e kopyalar. Hedef VARSA silinmez - hata verir
    (bir adayin dosyasi baska adaya tasinmasin)."""
    if hedef.exists():
        raise ProjeHatasi(f"{hedef} zaten var - aday klasoru her seferinde bostan kurulur")
    shutil.copytree(temel.klasor, hedef, ignore=shutil.ignore_patterns(*KOPYALANMAZ))
    return Proje(hedef, temel.ad)


# --------------------------------------------------------------------------
# Referans proje uretimi (gercek sembol + footprint kutuphaneleri)
# --------------------------------------------------------------------------


def _deger_tolerans_metni(r: float, tol: float) -> str:
    # Tolerans deger metninde durur ("28.7k 1%"): sablon ornegiyle ayni bicim
    # ve devre/parca bunu oradan okur (regresyon: "47k 1%").
    return f"{deger_metni(r)} {tolerans_metni(tol)}"


def niyet(p: BolucuParametre, ad: str) -> dict[str, Any]:
    return {
        "version": 1, "name": ad,
        "blocks": [
            {"template": "guc-girisi-header", "params": {"vin": "VIN", "gnd": "GND", "etiket": "GIRIS"}},
            {"template": "gerilim-bolucu", "params": {
                "vin": "VIN", "vout": "OUT", "gnd": "GND",
                "r_ust": _deger_tolerans_metni(p.r_ust, p.tolerans),
                "r_alt": _deger_tolerans_metni(p.r_alt, p.tolerans),
                "fp_ust": FOOTPRINT[p.paket_ust], "fp_alt": FOOTPRINT[p.paket_alt]}},
        ],
    }


_ROL_ETIKETI = {"giris_header": "guc-girisi-header/header", "ust": "gerilim-bolucu/ust-direnc",
                "alt": "gerilim-bolucu/alt-direnc", "cikis_header": "gerilim-bolucu/olcum-header"}


def _uuid5(*parca: str) -> str:
    return str(uuidlib.uuid5(_UUID_AD, "/".join(parca)))


def izleri_yaz(pcb: Path, izler: list) -> int:
    """Kartin TUM iz/via dugumlerini verilen izlerle degistirir (bu kartin
    yonlendirmesi bastan sona bu modulun uretimidir)."""
    from ..sch_write import write_tree

    root, stray = parse_with_stats(pcb.read_text(encoding="utf-8"))
    if stray:
        raise ProjeHatasi(f"{pcb.name} bozuk ({stray} kacak parantez)")
    root[:] = [n for n in root if not (isinstance(n, list) and head(n) in ("segment", "arc", "via"))]
    for t in izler:
        root.append(["segment", ["start", f"{t.x1:g}", f"{t.y1:g}"], ["end", f"{t.x2:g}", f"{t.y2:g}"],
                     ["width", f"{t.width:g}"], ["layer", QuotedStr(t.layer)], ["net", QuotedStr(t.net)],
                     ["uuid", QuotedStr(_uuid5("iz", t.net, t.layer, f"{t.x1:g},{t.y1:g},{t.x2:g},{t.y2:g}"))]])
    write_tree(pcb, root, apply=True, backup=False)
    return len(izler)


def roller_oku(klasor: Path) -> Roller:
    meta = json.loads((klasor / "pcbqa-referans.json").read_text(encoding="utf-8"))
    return Roller(**meta["roller"])


def yonlendir_dosya(proje: Proje, roller: Roller, genislik_mm: float = IZ_MM) -> int:
    from ..pcb import read_board

    return izleri_yaz(proje.pcb, rayli_yonlendir(read_board(proje.pcb), roller, genislik_mm))


def referans_projesi(p: BolucuParametre, klasor: Path, ad: str, *, iz_mm: float = IZ_MM,
                     kicad_cli: str | None = None) -> Proje:
    """Parametrelerden KiCad'de acilabilir, YONLENDIRILMIS bir bolucu projesi.

    Sematik ve kart `generate` ile gercek sembol / footprint kutuphanelerinden
    kurulur (kalkan: KiCad netlist'i plani birebir kuruyor mu). Yerlesim ve
    yonlendirme bellekteki tasarimla AYNIDIR (bolucu.yerlesim)."""
    from ..generate import draw_outline, generate
    from ..harness import write_board
    from ..intent import plan_from_file

    klasor = Path(klasor)
    with tempfile.TemporaryDirectory(prefix="pcbqa-niyet-") as d:
        yol = Path(d) / f"{ad}.json"
        yol.write_text(json.dumps(niyet(p, ad), ensure_ascii=False, indent=1), encoding="utf-8")
        plan = plan_from_file(yol, kicad_cli=kicad_cli)
    sonuc = generate(plan, klasor, ad, place=False, kicad_cli=kicad_cli)
    if not sonuc.ok:
        raise ProjeHatasi("proje uretilemedi: " + "; ".join(sonuc.problems))
    refs = {rol: sonuc.refs[etiket] for rol, etiket in _ROL_ETIKETI.items()}
    roller = Roller(**refs)
    proje = Proje(klasor, ad)
    konum = yerlesim(p.aralik_mm)
    sira = {"giris_header": "J1", "ust": "R1", "alt": "R2", "cikis_header": "J2"}
    write_board(proje.pcb, {refs[rol]: konum[k] for rol, k in sira.items()}, proje.pcb)
    x0, y0, x1, y1 = kart_siniri(p.aralik_mm)
    draw_outline(proje.pcb, x1 - x0, y1 - y0)
    n_iz = yonlendir_dosya(proje, roller, iz_mm)
    (klasor / "kosullar.json").write_text(json.dumps(p.kosullar(), ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8")
    meta = {"aile": "rezistif-bolucu", "parametre": p.as_dict(), "roller": roller.as_dict(),
            "iz_mm": iz_mm, "iz_sayisi": n_iz, "uretim": time.strftime("%Y-%m-%d"),
            "not": "pcbqa.duzeltme.proje referans ile uretildi; yerlesim/yonlendirme bolucu.yerlesim"}
    (klasor / "pcbqa-referans.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n",
                                                encoding="utf-8")
    return proje


# --------------------------------------------------------------------------
# Degisiklikleri dosyaya yazma
# --------------------------------------------------------------------------


def _ozellik(node, ad: str):
    return next((pr for pr in children(node, "property") if len(pr) > 2 and str(pr[1]) == ad), None)


def _sembol_dugumleri(root) -> dict[str, list]:
    out: dict[str, list] = {}
    for n in children(root, "symbol"):
        if child(n, "lib_id") is None:
            continue
        pr = _ozellik(n, "Reference")
        if pr is not None:
            out.setdefault(str(pr[2]), []).append(n)
    return out


def _footprint_dugumleri(root) -> dict[str, list]:
    out = {}
    for n in children(root, "footprint"):
        pr = _ozellik(n, "Reference")
        if pr is not None:
            out[str(pr[2])] = n
    return out


def _yeni_deger(eski: str, d: Degisiklik) -> str:
    # Deger metnindeki ek bilgiler (tolerans "1%") korunur - Tasarim.uygula ile ayni.
    return " ".join([d.yeni, *eski.split()[1:]])


def _gizli_ozellik(kaynak, ad: str, deger: str, uuid: str | None = None) -> list:
    yeni = copy.deepcopy(kaynak)
    yeni[1], yeni[2] = QuotedStr(ad), QuotedStr(deger)
    if child(yeni, "hide") is None:
        yeni.insert(4, ["hide", "yes"])
    if uuid is not None and child(yeni, "uuid") is not None:
        child(yeni, "uuid")[1] = QuotedStr(uuid)
    return yeni


def sematige_uygula(sch: Path, degisiklikler: list[Degisiklik]) -> list[str]:
    from ..sch_write import write_tree

    root, stray = parse_with_stats(sch.read_text(encoding="utf-8"))
    if stray:
        raise ProjeHatasi(f"{sch.name} bozuk ({stray} kacak parantez)")
    semboller = _sembol_dugumleri(root)
    notlar = []
    for d in degisiklikler:
        if d.ref not in semboller:
            raise ProjeHatasi(f"sematikte {d.ref} yok")
        for n in semboller[d.ref]:
            deger = _ozellik(n, "Value")
            if d.alan == "deger":
                deger[2] = QuotedStr(_yeni_deger(str(deger[2]), d))
            elif d.alan == "tolerans":
                tol = _ozellik(n, TOLERANS_ALANI)
                if tol is None:
                    n.insert(n.index(_ozellik(n, "Footprint")) + 1,
                             _gizli_ozellik(_ozellik(n, "Footprint"), TOLERANS_ALANI, d.yeni))
                else:
                    tol[2] = QuotedStr(d.yeni)
                # Deger metninde de tolerans yaziyorsa celismesin
                deger[2] = QuotedStr(" ".join(x for x in str(deger[2]).split() if not x.endswith("%")))
            elif d.alan == "footprint":
                _ozellik(n, "Footprint")[2] = QuotedStr(d.yeni)
            elif d.alan == "mpn":
                pr = _ozellik(n, MPN_ALANI)
                if pr is None:
                    n.insert(n.index(_ozellik(n, "Footprint")) + 1,
                             _gizli_ozellik(_ozellik(n, "Footprint"), MPN_ALANI, d.yeni))
                else:
                    pr[2] = QuotedStr(d.yeni)
            else:
                raise ProjeHatasi(f"bilinmeyen degisiklik alani: {d.alan}")
        notlar.append(f"sematik: {d.metin()}")
    write_tree(sch, root, apply=True, backup=False)
    return notlar


def _sematik_alanlari(sch: Path, ref: str) -> dict[str, str]:
    """pcb_sync ile ayni kural: karta tasinan sembol alanlari."""
    from ..schematic import read_schematic

    s = read_schematic(sch).by_ref(ref)
    if s is None:
        return {}
    return {k: v for k, v in s.properties.items()
            if not k.startswith("ki_") and k not in ("Reference", "Value", "Footprint")}


def _footprint_takas(eski: list, footprint_id: str, sch: Path) -> list:
    """Eski footprint dugumunun yerine kutuphanedeki `footprint_id`.

    Korunanlar: footprint UUID'si, sembol yolu (path), sayfa, konum, aci,
    katman, Reference/Value ve pad numarasina gore pad aglari. Kutuphane
    kopyasi oldugu gibi gelir (parite 'kutuphaneyle eslesmiyor' demesin);
    aci `harness._turn_parts` ile icerige de uygulanir."""
    from ..harness import _turn_parts
    from ..pcb_sync import NewFootprint, build_footprint_node

    ref = str(_ozellik(eski, "Reference")[2])
    deger = str(_ozellik(eski, "Value")[2])
    at = child(eski, "at")
    x, y = as_float(at[1]), as_float(at[2])
    aci = as_float(at[3]) if len(at) > 3 else 0.0
    eski_uuid = str(value(eski, "uuid"))
    aglar = {}
    for pad in children(eski, "pad"):
        net = child(pad, "net")
        if net is not None and len(net) > 1:
            aglar[str(pad[1])] = str(net[-1])
    yeni = build_footprint_node(
        NewFootprint(ref, footprint_id, deger, str(value(eski, "path") or ""), x, y, aglar,
                     _sematik_alanlari(sch, ref)),
        str(value(eski, "sheetfile") or sch.name), str(value(eski, "sheetname") or "/"),
        project_dir=sch.parent)
    if aci:
        child(yeni, "at")[:] = ["at", f"{x:g}", f"{y:g}", f"{aci:g}"]
        _turn_parts(yeni, aci)
    # Kimlik: footprint UUID'si AYNI kalir; ic UUID'ler deterministik.
    sayac = 0

    def uuidleri_ata(node, kok: bool):
        nonlocal sayac
        for item in node:
            if not isinstance(item, list):
                continue
            if head(item) == "uuid" and len(item) > 1:
                if kok:
                    item[1] = QuotedStr(eski_uuid)
                else:
                    sayac += 1
                    item[1] = QuotedStr(_uuid5(eski_uuid, footprint_id, str(sayac)))
            elif head(item) in ("property", "pad", "fp_text"):
                uuidleri_ata(item, False)

    uuidleri_ata(yeni, True)
    layer = child(eski, "layer")
    if layer is not None and child(yeni, "layer") is not None:
        child(yeni, "layer")[1] = layer[1]
    return yeni


def karta_uygula(proje: Proje, degisiklikler: list[Degisiklik], roller: Roller,
                 iz_mm: float = IZ_MM) -> list[str]:
    from ..sch_write import write_tree

    root, stray = parse_with_stats(proje.pcb.read_text(encoding="utf-8"))
    if stray:
        raise ProjeHatasi(f"{proje.pcb.name} bozuk ({stray} kacak parantez)")
    fps = _footprint_dugumleri(root)
    notlar = []
    footprint_degisti = False
    for d in degisiklikler:
        n = fps.get(d.ref)
        if n is None:
            raise ProjeHatasi(f"kartta {d.ref} yok")
        if d.alan == "deger":
            pr = _ozellik(n, "Value")
            pr[2] = QuotedStr(_yeni_deger(str(pr[2]), d))
        elif d.alan == "tolerans":
            # Sematikle ayni alan: parite icin karta da tasinir.
            pr = _ozellik(n, TOLERANS_ALANI)
            if pr is None:
                kaynak = _ozellik(n, "Value")
                i = n.index(kaynak) + 1
                n.insert(i, _gizli_ozellik(kaynak, TOLERANS_ALANI, d.yeni,
                                           _uuid5(str(value(n, "uuid")), TOLERANS_ALANI)))
            else:
                pr[2] = QuotedStr(d.yeni)
            v = _ozellik(n, "Value")
            v[2] = QuotedStr(" ".join(x for x in str(v[2]).split() if not x.endswith("%")))
        elif d.alan == "mpn":
            pr = _ozellik(n, MPN_ALANI)
            if pr is None:
                kaynak = _ozellik(n, "Value")
                n.insert(n.index(kaynak) + 1, _gizli_ozellik(kaynak, MPN_ALANI, d.yeni,
                                                            _uuid5(str(value(n, "uuid")), MPN_ALANI)))
            else:
                pr[2] = QuotedStr(d.yeni)
        elif d.alan == "footprint":
            yeni = _footprint_takas(n, d.yeni, proje.sch)
            root[root.index(n)] = yeni
            fps[d.ref] = yeni
            footprint_degisti = True
        else:
            raise ProjeHatasi(f"bilinmeyen degisiklik alani: {d.alan}")
        notlar.append(f"kart: {d.metin()}")
    write_tree(proje.pcb, root, apply=True, backup=False)
    if footprint_degisti:
        n_iz = yonlendir_dosya(proje, roller, iz_mm)
        notlar.append(f"kart: footprint degisti -> {n_iz} iz parcasi yeniden yonlendirildi")
    return notlar


# --------------------------------------------------------------------------
# Geri okuma
# --------------------------------------------------------------------------


def kart_kimlikleri(pcb: Path) -> dict[str, dict[str, Any]]:
    root, _ = parse_with_stats(pcb.read_text(encoding="utf-8"))
    out = {}
    for ref, n in _footprint_dugumleri(root).items():
        pads = {}
        for pad in children(n, "pad"):
            net = child(pad, "net")
            pads[str(pad[1])] = str(net[-1]) if net is not None and len(net) > 1 else ""
        out[ref] = {"uuid": str(value(n, "uuid")), "path": str(value(n, "path") or ""),
                    "footprint": str(n[1]), "deger": str(_ozellik(n, "Value")[2]),
                    "tolerans": str(_ozellik(n, TOLERANS_ALANI)[2]) if _ozellik(n, TOLERANS_ALANI) else "",
                    "pad_aglari": pads}
    return out


def bilesen_ozeti(proje: Proje) -> dict[str, dict[str, str]]:
    """Kopyadaki kartin bilesenleri (deger, footprint, paket, tolerans) - envanter
    paket/tolerans dagilimini kayittan sayar (Kicad-d8k). Okunamazsa bos."""
    from ..devre.parca import paket_kodu

    try:
        kimlik = kart_kimlikleri(proje.pcb)
    except (OSError, ValueError, TypeError, IndexError):
        return {}
    out = {}
    for ref, k in sorted(kimlik.items()):
        tol = k["tolerans"] or next((x for x in k["deger"].split()[1:] if x.endswith("%")), "")
        out[ref] = {"deger": k["deger"], "footprint": k["footprint"], "paket": paket_kodu(k["footprint"]) or "",
                    "tolerans": tol}
    return out


def bastirma_envanteri(proje: Proje) -> dict[str, int]:
    """ERC/DRC'yi gizleyebilecek ogeler: aday bunlari EKLEMEMELI."""
    metin = proje.sch.read_text(encoding="utf-8")
    pro = json.loads(proje.pro.read_text(encoding="utf-8")) if proje.pro.is_file() else {}
    return {
        "pwr_flag": metin.count('(lib_id "power:PWR_FLAG")'),
        "no_connect": metin.count("(no_connect"),
        "erc_dislama": len((pro.get("erc") or {}).get("erc_exclusions") or []),
        "drc_dislama": len(((pro.get("board") or {}).get("design_settings") or {}).get("drc_exclusions") or []),
    }


def geri_oku(proje: Proje, beklenen: dict[str, dict[str, str]], once: dict[str, Any]) -> dict[str, Any]:
    """Yazilan degisiklik diskte mi; kimlik ve baglanti korunmus mu?"""
    from ..sch_verify import SchVerifyError, compare, connectivity_of
    from ..schematic import read_schematic

    sorunlar: list[str] = []
    sch = read_schematic(proje.sch)
    for ref, b in beklenen.items():
        s = sch.by_ref(ref)
        if s is None:
            sorunlar.append(f"sematikte {ref} okunamadi")
            continue
        tol = s.properties.get(TOLERANS_ALANI) or next((x for x in s.value.split()[1:] if x.endswith("%")), "")
        for alan, okunan in (("deger", s.value), ("footprint", s.footprint), ("tolerans", tol)):
            if okunan != b[alan]:
                sorunlar.append(f"sematik {ref} {alan}: diskte {okunan!r}, beklenen {b[alan]!r}")
    kimlik = kart_kimlikleri(proje.pcb)
    for ref, k0 in once["kart"].items():
        k1 = kimlik.get(ref)
        if k1 is None:
            sorunlar.append(f"kartta {ref} kayboldu")
            continue
        for alan in ("uuid", "path"):
            if k1[alan] != k0[alan]:
                sorunlar.append(f"kart {ref} {alan} degisti: {k0[alan]} -> {k1[alan]}")
        if k1["pad_aglari"] != k0["pad_aglari"]:
            sorunlar.append(f"kart {ref} pad-ag eslemesi degisti: {k0['pad_aglari']} -> {k1['pad_aglari']}")
        if ref in beklenen:
            b = beklenen[ref]
            for alan in ("footprint", "deger"):
                if k1[alan] != b[alan]:
                    sorunlar.append(f"kart {ref} {alan}: diskte {k1[alan]!r}, beklenen {b[alan]!r}")
    try:
        fark = compare(once["baglanti"], connectivity_of(proje.sch))
        if not fark.ok:
            sorunlar.append(fark.describe())
    except SchVerifyError as exc:
        return {"durum": "arac-hatasi", "sorunlar": [f"baglanti okunamadi: {exc}"]}
    env = bastirma_envanteri(proje)
    if env != once["bastirma"]:
        sorunlar.append(f"bastirma envanteri degisti: {once['bastirma']} -> {env}")
    return {"durum": "kaldi" if sorunlar else "gecti", "sorunlar": sorunlar, "bastirma": env}


# --------------------------------------------------------------------------
# KiCad kontrolleri (kicad-cli)
# --------------------------------------------------------------------------


def _ihlaller(rapor: Path, gruplar: tuple[str, ...]) -> list[dict[str, Any]]:
    data = json.loads(rapor.read_text(encoding="utf-8"))
    out = []
    for sheet in data.get("sheets", []) or []:
        for v in sheet.get("violations", []) or []:
            out.append({"grup": "erc", "tur": v.get("type"), "siddet": v.get("severity"),
                        "aciklama": v.get("description"),
                        "ogeler": [i.get("description") for i in v.get("items", [])]})
    for g in gruplar:
        for v in data.get(g, []) or []:
            out.append({"grup": g, "tur": v.get("type"), "siddet": v.get("severity"),
                        "aciklama": v.get("description"),
                        "ogeler": [i.get("description") for i in v.get("items", [])]})
    return out


def _kontrol_durumu(ihlaller: list[dict[str, Any]], kozmetik: frozenset = frozenset()) -> str:
    sayilan = [v for v in ihlaller if v["siddet"] in ("error", "warning") and v["tur"] not in kozmetik]
    return "kaldi" if sayilan else "gecti"


def _adim(res, kok: Path) -> dict[str, Any]:
    return {"komut": [str(x) for x in res.komut], "cikis_kodu": res.returncode,
            "rapor": str(res.output_path.relative_to(kok)) if res.output_path else None,
            "stderr": (res.stderr or "").strip()[-400:]}


def kicad_kontrolleri(proje: Proje, rapor_klasoru: Path, cli=None) -> dict[str, Any]:
    from ..kicadcli import KicadCli, KicadCliError
    from ..pcb import read_board

    rapor_klasoru.mkdir(parents=True, exist_ok=True)
    out: dict[str, Any] = {"kontroller": {}, "adimlar": {}, "ihlaller": [], "notlar": []}
    try:
        cli = cli or KicadCli()
        out["kicad_cli"] = {"yol": str(cli.exe), "surum": cli.version()}
    except (KicadCliError, OSError) as exc:
        out["kontroller"] = {k: "arac-hatasi" for k in ("netlist", "erc", "drc", "parite")}
        out["notlar"].append(f"kicad-cli calistirilamadi: {exc}")
        return out
    try:
        net = cli.export_netlist(proje.sch, rapor_klasoru / "netlist.xml")
        erc = cli.erc(proje.sch, rapor_klasoru / "erc.json")
        dokum = bool(read_board(proje.pcb).zones)
        drc = cli.drc(proje.pcb, rapor_klasoru / "drc.json", schematic_parity=True, refill_zones=dokum)
    except (KicadCliError, OSError) as exc:
        out["kontroller"] = {k: "arac-hatasi" for k in ("netlist", "erc", "drc", "parite")}
        out["notlar"].append(f"kicad-cli hatasi: {exc}")
        return out
    out["notlar"].append("bakir dokumu var: DRC dolguyu yeniledi (--refill-zones)" if dokum
                         else "bakir dokumu yok: dolgu gerekmiyor")
    for ad, res in (("netlist", net), ("erc", erc), ("drc", drc)):
        out["adimlar"][ad] = _adim(res, rapor_klasoru)
    k = out["kontroller"]
    k["netlist"] = "gecti" if net.output_path else "arac-hatasi"
    out["netlist"] = str(net.output_path) if net.output_path else None
    if erc.output_path is None:
        k["erc"] = "arac-hatasi"
    else:
        e = _ihlaller(erc.output_path, ())
        out["ihlaller"] += e
        k["erc"] = _kontrol_durumu(e)
    if drc.output_path is None:
        k["drc"] = k["parite"] = "arac-hatasi"
    else:
        d = _ihlaller(drc.output_path, ("violations", "unconnected_items"))
        p = _ihlaller(drc.output_path, ("schematic_parity",))
        out["ihlaller"] += d + p
        k["drc"] = _kontrol_durumu(d, KOZMETIK_DRC)
        k["parite"] = _kontrol_durumu(p)
    out["sayilar"] = {
        "erc": sum(1 for v in out["ihlaller"] if v["grup"] == "erc"),
        "drc": sum(1 for v in out["ihlaller"] if v["grup"] in ("violations", "unconnected_items")),
        "baglanmamis": sum(1 for v in out["ihlaller"] if v["grup"] == "unconnected_items"),
        "parite": sum(1 for v in out["ihlaller"] if v["grup"] == "schematic_parity"),
        "dislanan": sum(1 for v in out["ihlaller"] if v["siddet"] == "exclusion"),
    }
    return out


# --------------------------------------------------------------------------
# Elektriksel dogrulama (kaydedilmis sematikten)
# --------------------------------------------------------------------------

# Bu hattin modellemedigi etkiler - kayda ve rapora AYNEN yazilir.
KAPSAM_DISI = [
    "yuk ideal akim yutucu (ADC giris empedansi / ornekleme akimi modellenmedi)",
    "bakir iz direnci DC; enduktans, kapasitif kuplaj ve EMI modellenmedi",
    "direnclerin kendi isinmasi (oz isinma) ile ortam sicakligi ayri ayri; termal kuplaj yok",
    "konnektor pin akim siniri parca kutuphanesinde yok (EKSIK; bolucu akimi mA altinda)",
    "direnc asiri yuk / darbe gerilimi kontrol edilmiyor (azami calisma gerilimi Kicad-7cb'den beri "
    "direnc-gerilimi kontroluyle denetleniyor)",
]


def tasarim_oku(proje: Proje, netlist_xml: Path, kosullar: dict[str, Any]) -> Tasarim:
    from ..netlist import read_netlist
    from ..pcb import read_board

    return Tasarim(read_netlist(netlist_xml), read_board(proje.pcb), copy.deepcopy(kosullar), proje=proje.ad)


_ELEKTRIK_ARAC = ("benzetim", "gereksinim", "direnc-gucu")


def _elektrik_durumlari(d: Degerlendirme) -> dict[str, str]:
    out = {}
    for ad, v in d.kontroller.items():
        if v in ("gecti", "kaldi"):
            out[ad] = v
        elif ad in _ELEKTRIK_ARAC and d.eksik_turu == "arac":
            out[ad] = "arac-hatasi"
        else:
            out[ad] = "veri-model-eksik"
    if d.uyum.get("karsilastirildi"):
        out["benzetim-el-hesabi"] = "gecti" if d.uyum.get("uyumlu") else "arac-hatasi"
    return out


def birlesik_durum(kontroller: dict[str, str]) -> str:
    """kaldi > arac-hatasi > veri-model-eksik > gecti. Bilinen bir kalis
    tasarimi gecersiz kilar; bilinmeyen kontrol basari SAYILMAZ."""
    degerler = set(kontroller.values())
    for d in ("kaldi", "arac-hatasi", "veri-model-eksik"):
        if d in degerler:
            return d
    return "gecti" if degerler else "veri-model-eksik"


# --------------------------------------------------------------------------
# Surumler, onbellek
# --------------------------------------------------------------------------

_KOD_DOSYALARI = ("duzeltme/*.py", "dogrulama/*.py", "spice/*.py", "devre/*.py", "pcb_akim.py",
                  "kicadcli.py", "netlist.py", "pcb.py", "schematic.py", "pcb_sync.py",
                  "data/parcalar/*.json")


def kod_ozeti() -> str:
    kok = Path(__file__).resolve().parents[1]
    h = hashlib.sha256()
    for desen in _KOD_DOSYALARI:
        for p in sorted(kok.glob(desen)):
            h.update(p.relative_to(kok).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


def kutuphane_ozetleri(proje: Proje) -> dict[str, str]:
    """Kartta kullanilan footprint'lerin KiCad kutuphanesindeki dosya ozeti."""
    from .. import symlib
    from ..pcb import read_board

    out = {}
    for c in read_board(proje.pcb).components:
        try:
            out[c.footprint_id] = _sha(symlib.footprint_path(c.footprint_id, proje.klasor))[:16]
        except Exception as exc:
            out[c.footprint_id] = f"okunamadi ({exc})"
    return dict(sorted(out.items()))


def onbellek_anahtari(proje: Proje, kosullar: dict[str, Any], surum: dict[str, Any],
                      kutuphane: dict[str, str]) -> str:
    """Dosya, kosul, kural (KOZMETIK, KiCad proje dosyasi), kod ve surum ozeti."""
    ham = json.dumps({"sema": DENEY_SEMASI, "dosyalar": proje.ozetler(), "kosullar": kosullar,
                      "surumler": {k: surum.get(k) for k in ("kicad", "ngspice", "parca_kutuphanesi")},
                      "kod": kod_ozeti(), "kutuphane": kutuphane, "kozmetik": sorted(KOZMETIK_DRC)},
                     sort_keys=True, default=str)
    return hashlib.sha256(ham.encode("utf-8")).hexdigest()[:24]


# --------------------------------------------------------------------------
# Tek aday (ya da temel) icin butun zincir
# --------------------------------------------------------------------------


@dataclass
class Ortam:
    """Bir deneyin sabitleri (her aday ayni ortamda)."""
    temel: Proje
    kosullar: dict[str, Any]
    roller: Roller
    cikti: Path
    once: dict[str, Any]                       # temel kartin kimlikleri, baglanti, bastirma
    surum: dict[str, Any] = field(default_factory=dict)
    benzetim: Callable[..., Any] = seviye3
    cli: Any = None
    onbellek: bool = True
    iz_mm: float = IZ_MM
    yonlendirilebilir: bool = True     # temel kart rayli yonlendirmeyle mi cizilmis


def temel_durumu(temel: Proje) -> dict[str, Any]:
    from ..sch_verify import connectivity_of

    return {"kart": kart_kimlikleri(temel.pcb), "baglanti": connectivity_of(temel.sch),
            "bastirma": bastirma_envanteri(temel)}


def aday_dogrula(o: Ortam, kimlik: str, aday: Aday | None, beklenen_t: Tasarim | None,
                 bellek_durumu: str | None = None) -> dict[str, Any]:
    """Temel projenin AYRI kopyasinda adayi uygular ve tum zinciri kosar."""
    bas = time.perf_counter()
    klasor = o.cikti / "adaylar" / kimlik.replace("/", "_")
    kayit: dict[str, Any] = {
        "tur": "gercek-aday" if aday else "gercek-temel", "sema": DENEY_SEMASI, "kimlik": kimlik,
        "temel": {"klasor": str(o.temel.klasor), "ad": o.temel.ad, "ozetler": o.temel.ozetler()},
        "aday": aday.as_dict() if aday else None, "kosullar": o.kosullar, "kapsam_disi": KAPSAM_DISI,
        "zaman": time.strftime("%Y-%m-%dT%H:%M:%S"), "klasor": str(klasor),
    }
    proje = kopyala(o.temel, klasor)
    degs = aday.degisiklikler if aday else []
    kontroller: dict[str, str] = {}
    try:
        if any(d.alan == "footprint" for d in degs) and not o.yonlendirilebilir:
            raise ProjeHatasi("temel kart rayli yonlendirmeyle cizilmemis - footprint degisimi yeniden "
                              "yonlendirilemez")
        kayit["yazma"] = sematige_uygula(proje.sch, degs) + karta_uygula(proje, degs, o.roller, o.iz_mm) \
            if degs else []
    except (ProjeHatasi, YonlendirmeHatasi, OSError) as exc:
        kayit["yazma"] = [f"HATA: {exc}"]
        kontroller["yazma"] = "arac-hatasi"
    kayit["dosya_ozetleri"] = proje.ozetler()
    kayit["bilesenler"] = bilesen_ozeti(proje)
    if "yazma" not in kontroller:
        beklenen = beklenen_t.bilesen_ozeti(sorted({d.ref for d in degs})) if beklenen_t and degs else {}
        go = geri_oku(proje, beklenen, o.once)
        kayit["geri_okuma"] = go
        kontroller["geri-okuma"] = go["durum"]

    kutuphane = kutuphane_ozetleri(proje)
    anahtar = onbellek_anahtari(proje, o.kosullar, o.surum, kutuphane)
    kayit["onbellek_anahtari"] = anahtar
    kayit["kutuphane"] = kutuphane
    ob_klasor = o.cikti / "onbellek" / anahtar
    ob_dosya = ob_klasor / "sonuc.json"
    if o.onbellek and ob_dosya.is_file() and "yazma" not in kontroller:
        sonuc = json.loads(ob_dosya.read_text(encoding="utf-8"))
        kayit["onbellekten"] = True
    else:
        if ob_klasor.exists():
            shutil.rmtree(ob_klasor)
        sonuc = _kontroller(o, proje, ob_klasor) if "yazma" not in kontroller else {
            "kicad": {"kontroller": {}}, "elektrik": None, "elektrik_kontroller": {}}
        if "yazma" not in kontroller:
            ob_klasor.mkdir(parents=True, exist_ok=True)
            ob_dosya.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        kayit["onbellekten"] = False
    kayit["rapor_klasoru"] = str(ob_klasor)
    kayit["kicad"] = sonuc["kicad"]
    kayit["elektrik"] = sonuc["elektrik"]
    for ad, v in sonuc["kicad"].get("kontroller", {}).items():
        kontroller[f"kicad-{ad}"] = v
    for ad, v in sonuc["elektrik_kontroller"].items():
        kontroller[f"elektrik-{ad}"] = v
    kayit["kontroller"] = kontroller
    kayit["durum"] = birlesik_durum(kontroller)
    # Egitim etiketi yalnizca bilinen sonuctan: gecti=1, kaldi=0. Arac /
    # model eksigi ya da geri okunamayan dosya etikete GIRMEZ.
    aktar = kayit["durum"] in ("gecti", "kaldi") and kontroller.get("geri-okuma") == "gecti"
    kayit["egitim"] = {"aktarilabilir": aktar, "etiket": {"gecti": 1, "kaldi": 0}.get(kayit["durum"]) if aktar
                       else None,
                       "bellek_durumu": bellek_durumu,
                       "bellek_ile_uyumlu": None if bellek_durumu is None else
                       ({"gecerli": "gecti", "gecersiz": "kaldi"}.get(bellek_durumu) == kayit["durum"])}
    kayit["surumler"] = o.surum
    kayit["sure_s"] = round(time.perf_counter() - bas, 2)
    (klasor / "_pcbqa").mkdir(exist_ok=True)
    (klasor / "_pcbqa" / "kayit.json").write_text(json.dumps(kayit, ensure_ascii=False, indent=1, default=str),
                                                  encoding="utf-8")
    return kayit


def _kontroller(o: Ortam, proje: Proje, rapor: Path) -> dict[str, Any]:
    kicad = kicad_kontrolleri(proje, rapor, o.cli)
    elektrik = None
    ek: dict[str, str] = {}
    if kicad.get("netlist"):
        try:
            t = tasarim_oku(proje, Path(kicad["netlist"]), o.kosullar)
            d = degerlendir(t, benzetim=o.benzetim)
            elektrik = d.as_dict()
            ek = _elektrik_durumlari(d)
        except Exception as exc:  # arac/analiz hatasi basari sayilmaz
            ek = {"analiz": "arac-hatasi"}
            elektrik = {"hata": f"{type(exc).__name__}: {exc}"}
    else:
        ek = {"analiz": "arac-hatasi"}
        elektrik = {"hata": "netlist yok - elektriksel dogrulama kaydedilmis sematikten yapilamadi"}
    return {"kicad": kicad, "elektrik": elektrik, "elektrik_kontroller": ek}


# --------------------------------------------------------------------------
# Deney
# --------------------------------------------------------------------------


def _kosullari_oku(temel: Proje, yol: Path | None) -> dict[str, Any]:
    if yol is None:
        yol = temel.klasor / "kosullar.json"
    from ..confload import load_config

    k, _ = load_config(Path(yol))
    return dict(k)


def deney(temel_yolu: Path, cikti: Path, *, kosullar_yolu: Path | None = None, siralayici=None,
          hepsi: bool = False, en_fazla: int | None = None, benzetim: Callable[..., Any] = seviye3,
          cli=None, onbellek: bool = True, roller: Roller | None = None,
          bellek_karsilastir: bool = True) -> dict[str, Any]:
    """Temel projede kontroller -> adaylar -> (sira) -> her aday gercek dosyada.

    `hepsi=False`: ilk GECTI adayda durulur (uygulama davranisi). `hepsi=True`:
    butun adaylar dogrulanir (deney / karsilastirma)."""
    from .veri import surumler

    temel = Proje.bul(temel_yolu)
    cikti = Path(cikti)
    if (cikti / "adaylar").exists():
        raise ProjeHatasi(f"{cikti / 'adaylar'} zaten var - her deney bos bir klasorde baslar "
                          "(onbellek klasoru korunabilir)")
    cikti.mkdir(parents=True, exist_ok=True)
    temel_once = temel.ozetler()
    kosullar = _kosullari_oku(temel, kosullar_yolu)
    roller = roller or roller_oku(temel.klasor)
    o = Ortam(temel, kosullar, roller, cikti, temel_durumu(temel), surumler(), benzetim, cli, onbellek)
    kayitlar = [aday_dogrula(o, "temel", None, None)]
    ilk = kayitlar[0]
    rapor: dict[str, Any] = {"temel": str(temel.klasor), "temel_durum": ilk["durum"], "adaylar": 0,
                             "denenen": 0, "secilen": None}
    if ilk["durum"] == "kaldi" and isinstance(ilk.get("elektrik"), dict) and ilk["elektrik"].get("bolucu"):
        t0 = tasarim_oku(Proje(Path(ilk["klasor"]), temel.ad),
                         Path(ilk["rapor_klasoru"]) / "netlist.xml", kosullar)
        b = Bolucu(**ilk["elektrik"]["bolucu"])
        # Temel kart bu modulun rayli yonlendirmesiyle AYNI degilse (elle
        # degistirilmis, eksik iz) footprint adayi izleri yeniden URETEMEZ:
        # uretse bozuk karti sessizce "onarmis" olurdu. O adaylar arac-hatasi.
        o.yonlendirilebilir = yonlendirici_kur(Tasarim(t0.netlist, t0.board, kosullar), b)
        rapor["yonlendirilebilir"] = o.yonlendirilebilir
        if o.yonlendirilebilir:
            t0.yonlendirici = lambda kart: rayli_yonlendir(kart, roller, o.iz_mm)
        adaylar = adaylari_uret(t0, b)
        sira = list(range(len(adaylar)))
        if siralayici is not None:
            from .ozellik import on_hesap, tasarim_ozeti

            varyant = {"tasarim": tasarim_ozeti(t0, b),
                       "degerlendirme": Degerlendirme.from_dict(ilk["elektrik"]).as_dict()}
            sira = siralayici.sirala([{"varyant": varyant, "aday": {
                **a.as_dict(), "on_hesap": on_hesap(t0.uygula(a.degisiklikler), b),
                "maliyet": maliyet(t0, t0.uygula(a.degisiklikler))}} for a in adaylar])
        rapor["adaylar"] = len(adaylar)
        rapor["siralama"] = getattr(siralayici, "kaynak", "ureteci sirasi")
        for j, i in enumerate(sira if en_fazla is None else sira[:en_fazla]):
            a = adaylar[i]
            ta = t0.uygula(a.degisiklikler)
            # Ayni aday BELLEKTE (egitim verisinin yolu) - gercek dosya sonucuyla
            # tutarli mi? Fark, bellek etiketinin gercegi temsil etmedigini gosterir.
            bellek = degerlendir(ta, benzetim=benzetim, bolucu=b).durum if bellek_karsilastir else None
            k = aday_dogrula(o, f"aday-{j + 1:02d}-{a.kimlik}", a, ta, bellek)
            k["maliyet"] = maliyet(t0, ta)      # Kicad-apg: ozgun tasarimla fark
            kayitlar.append(k)
            if k["durum"] == "gecti" and not hepsi:
                break           # uygulama davranisi: ilk gecende dur (secim kapsami 'kismi' olur)
        rapor["denenen"] = len(kayitlar) - 1
    # Secim (Kicad-d8k): gecenler arasinda en dusuk maliyet. Gecerlilik
    # etiketleri (durum, egitim) okunur, degistirilmez.
    from .aciklama import kontrol_aciklamalari
    from .secim import sec

    s = sec(kayitlar, aday_sayisi=rapor["adaylar"])
    rapor["secilen"] = s["secilen"]
    rapor["ilk_gecen"] = s["ilk_gecen"]
    rapor["secim"] = {a: v for a, v in s.items() if a != "tercih"}
    for k in kayitlar:
        if k["kimlik"] in s["tercih"]:
            k["tercih"] = s["tercih"][k["kimlik"]]
        k["aciklamalar"] = kontrol_aciklamalari(k)
    temel_sonra = temel.ozetler()
    rapor["temel_degismedi"] = temel_sonra == temel_once
    if not rapor["temel_degismedi"]:
        raise ProjeHatasi(f"TEMEL PROJE DEGISTI: {temel_once} -> {temel_sonra}")
    with (cikti / "deney.jsonl").open("w", encoding="utf-8") as f:
        for k in kayitlar:
            f.write(json.dumps(k, ensure_ascii=False, default=str) + "\n")
    rapor["durumlar"] = {}
    for k in kayitlar[1:]:
        rapor["durumlar"][k["durum"]] = rapor["durumlar"].get(k["durum"], 0) + 1
    (cikti / "ozet.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    (cikti / "rapor.md").write_text(rapor_metni(kayitlar, rapor) + "\n", encoding="utf-8")
    rapor["kayitlar"] = kayitlar
    return rapor


def rapor_metni(kayitlar: list[dict[str, Any]], rapor: dict[str, Any]) -> str:
    """CLI, rapor.md ve arayuz AYNI metni kullanir (aciklama.rapor_metni)."""
    from .aciklama import rapor_metni as metin

    return metin(kayitlar, rapor)


# --------------------------------------------------------------------------
# Referans projeler (depoya giren ornekler)
# --------------------------------------------------------------------------

# 12 V -> 3.0 V ADC girisi (samples/bolucu ornegiyle ayni kosul). Gecerli:
# R1 28.7k (E96) / R2 10k. Hatali: R1 47k (BOM'da yanlis deger) -> Vout
# ~1.8 V, pencerenin (2.64..3.36 V) altinda.
REFERANS = BolucuParametre(
    kimlik="bolucu-gercek", vin_nom=12.0, vin_tol=0.02, vout_hedef=3.0, pencere=0.12, yuk_nom_a=1e-5,
    yuk_tepe_a=2e-5, ortam_c=25.0, sicakliklar=(-40.0, 85.0), r_ust=28700.0, r_alt=10000.0, tolerans=0.01,
    paket_ust="0603", paket_alt="0603", aralik_mm=3.2)
REFERANS_HATALI_R_UST = 47000.0


def referanslari_uret(cikti: Path, kicad_cli: str | None = None) -> dict[str, Proje]:
    from dataclasses import replace

    cikti = Path(cikti)
    gecerli = referans_projesi(REFERANS, cikti / "bolucu-gecerli", "bolucu-gecerli", kicad_cli=kicad_cli)
    hatali = referans_projesi(replace(REFERANS, kimlik="bolucu-gercek-hatali", r_ust=REFERANS_HATALI_R_UST),
                              cikti / "bolucu-hatali", "bolucu-hatali", kicad_cli=kicad_cli)
    return {"gecerli": gecerli, "hatali": hatali}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="pcbqa.duzeltme.proje", description=__doc__.splitlines()[0])
    alt = ap.add_subparsers(dest="komut", required=True)
    r = alt.add_parser("referans", help="gecerli + kontrollu hatali referans KiCad projelerini uret")
    r.add_argument("--cikti", type=Path, required=True)
    d = alt.add_parser("deney", help="temel projede adaylari gercek dosyalarda dogrula")
    d.add_argument("--temel", type=Path, required=True, help="temel proje klasoru (pcbqa-referans.json ile)")
    d.add_argument("--cikti", type=Path, required=True)
    d.add_argument("--kosullar", type=Path, default=None, help="varsayilan: <temel>/kosullar.json")
    d.add_argument("--hepsi", action="store_true", help="ilk gecende durma; butun adaylari dogrula")
    d.add_argument("--en-fazla", type=int, default=None)
    d.add_argument("--model", type=Path, default=None, help="siralama modeli (yoksa ureteci sirasi)")
    d.add_argument("--onbelleksiz", action="store_true")
    g = alt.add_parser("goster", help="var olan deney klasorunu (deney.jsonl) secim + gerekcelerle raporla")
    g.add_argument("deney", type=Path, help="deney klasoru ya da deney.jsonl")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.komut == "referans":
        for ad, p in referanslari_uret(args.cikti).items():
            print(f"{ad}: {p.klasor} ({', '.join(p.ozetler())})")
        return 0
    if args.komut == "goster":
        from .gorunum import KaynakHatasi, deney_yukle

        try:
            g = deney_yukle(args.deney)
        except KaynakHatasi as exc:
            print(f"HATA: {exc}", file=sys.stderr)
            return 2
        print(g.metin)
        return 0 if g.secim and g.secim["secilen"] else 1
    from .sirala import siralayici_yukle

    s = siralayici_yukle(args.model) if args.model else None
    r = deney(args.temel, args.cikti, kosullar_yolu=args.kosullar, siralayici=s, hepsi=args.hepsi,
              en_fazla=args.en_fazla, onbellek=not args.onbelleksiz)
    print(rapor_metni(r.pop("kayitlar"), r))
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["temel_durum"] == "gecti" or r["secilen"] else 1


if __name__ == "__main__":
    sys.exit(main())
