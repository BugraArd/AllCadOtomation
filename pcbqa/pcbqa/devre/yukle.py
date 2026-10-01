"""Bir KiCad projesinden devre grafi: dosyalari bul, netlist uret, oku, kur.

    from pcbqa.devre.yukle import projeden_graf
    graf, dosyalar = projeden_graf("samples/pic_programmer", kosullar_yolu=None)

Netlist `kicad-cli sch export netlist` ile uretilir - sematikte baglanti
geometriktir ve dosyaya bakarak guvenle cikarilamaz (bkz. sch_verify).
Sematik yoksa baglanti kartin pad aglarindan okunur.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..kicadcli import KicadCli
from ..netlist import read_netlist
from ..pcb import read_board
from .graf import DevreGrafi, graf_kur
from .kosullar import Kosullar, kosullari_oku
from .parca import Kutuphane


class ProjeHatasi(RuntimeError):
    pass


@dataclass
class ProjeDosyalari:
    ad: str
    klasor: Path
    sematik: Path | None
    kart: Path | None
    netlist: Path | None = None


def proje_bul(hedef: Path | str) -> ProjeDosyalari:
    """Klasor ya da .kicad_pro/.kicad_sch/.kicad_pcb dosyasindan proje uclusu."""
    hedef = Path(hedef).resolve()
    if hedef.is_file():
        kok, klasor = hedef.stem, hedef.parent
    elif hedef.is_dir():
        klasor = hedef
        pro = sorted(klasor.glob("*.kicad_pro"))
        adaylar = pro or sorted(klasor.glob("*.kicad_pcb")) or sorted(klasor.glob("*.kicad_sch"))
        if not adaylar:
            raise ProjeHatasi(f"{klasor} icinde KiCad projesi bulunamadi")
        kok = adaylar[0].stem
    else:
        raise ProjeHatasi(f"bulunamadi: {hedef}")
    sch = klasor / f"{kok}.kicad_sch"
    pcb = klasor / f"{kok}.kicad_pcb"
    return ProjeDosyalari(kok, klasor, sch if sch.is_file() else None,
                          pcb if pcb.is_file() else None)


def projeden_graf(
    hedef: Path | str,
    *,
    kosullar_yolu: Path | str | None = None,
    kosullar: Kosullar | None = None,
    cli: KicadCli | None = None,
    calisma: Path | None = None,
    kutuphane: Kutuphane | None = None,
    sematik_oku: bool = True,
) -> tuple[DevreGrafi, ProjeDosyalari]:
    dosyalar = proje_bul(hedef)
    if dosyalar.sematik is None and dosyalar.kart is None:
        raise ProjeHatasi(f"{dosyalar.ad}: ne sematik ne kart var")
    if kosullar is None:
        kosullar = kosullari_oku(kosullar_yolu) if kosullar_yolu else Kosullar()

    netlist = None
    sematik = None
    if dosyalar.sematik is not None:
        cli = cli or KicadCli()
        hedef_dosya = (Path(calisma) if calisma else Path(tempfile.mkdtemp(prefix="pcbqa-graf-"))) / "netlist.xml"
        res = cli.export_netlist(dosyalar.sematik, hedef_dosya)
        if not res.ok or res.output_path is None:
            raise ProjeHatasi(f"netlist uretilemedi: {res.stderr or res.stdout}")
        dosyalar.netlist = res.output_path
        netlist = read_netlist(res.output_path)
        if sematik_oku:
            try:
                from ..schematic import read_schematic

                sematik = read_schematic(dosyalar.sematik)
            except Exception:  # sematik okunamazsa netlist yine yeter
                sematik = None

    board = read_board(dosyalar.kart) if dosyalar.kart is not None else None
    graf = graf_kur(netlist=netlist, board=board, kosullar=kosullar,
                    kutuphane=kutuphane, sematik=sematik, proje=dosyalar.ad)
    return graf, dosyalar
