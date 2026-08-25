"""KiCad XML netlist okuyucu: neyin neye BAGLI oldugu + pin islevleri.

Kaynak:  kicad-cli sch export netlist --format kicadxml
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class NetNode:
    """Bir netin uzerindeki tek bir pin."""

    ref: str
    pin: str
    pinfunction: str = ""
    pintype: str = ""

    def __str__(self) -> str:
        return f"{self.ref}.{self.pinfunction or self.pin}"


@dataclass
class Net:
    code: str
    name: str
    netclass: str = "Default"
    nodes: list[NetNode] = field(default_factory=list)

    @property
    def refs(self) -> set[str]:
        return {n.ref for n in self.nodes}


@dataclass
class SchComponent:
    ref: str
    value: str = ""
    footprint: str = ""
    libpart: str = ""


@dataclass
class Netlist:
    path: Path
    components: dict[str, SchComponent] = field(default_factory=dict)
    nets: list[Net] = field(default_factory=list)

    def net_of(self, ref: str, pin: str) -> Net | None:
        for net in self.nets:
            for node in net.nodes:
                if node.ref == ref and node.pin == pin:
                    return net
        return None

    def nets_of(self, ref: str) -> list[Net]:
        return [n for n in self.nets if ref in n.refs]


def netlist_from_board(board) -> Netlist:
    """Sematik olmadan, sadece .kicad_pcb'den baglanti bilgisi cikarir.

    KiCad 9+ pad'lerde hem net adini hem pin tipini saklar, bu yuzden
    kurallarimizin neredeyse tamami sematik olmadan da calisabilir.
    Sematige gore eksik kalanlar:
      * pin islev adlari (VCC_8 yerine sadece pad numarasi gorunur)
      * net siniflari (hepsi "Default" varsayilir)
      * karta henuz yerlestirilmemis bilesenler
    """
    netlist = Netlist(path=board.path)
    buckets: dict[str, list[NetNode]] = {}

    for comp in board.components:
        netlist.components[comp.ref] = SchComponent(
            ref=comp.ref, value=comp.value, footprint=comp.footprint_id
        )
        for pad in comp.pads:
            if not pad.net:
                continue
            buckets.setdefault(pad.net, []).append(
                NetNode(ref=comp.ref, pin=pad.number, pinfunction="", pintype=pad.pintype)
            )

    for code, (name, nodes) in enumerate(sorted(buckets.items()), start=1):
        netlist.nets.append(Net(code=str(code), name=name, netclass="Default", nodes=nodes))

    return netlist


def _text(el, tag: str, default: str = "") -> str:
    found = el.find(tag)
    if found is None or found.text is None:
        return default
    return found.text.strip()


def read_netlist(path: str | Path) -> Netlist:
    """kicadxml bicimindeki netlist dosyasini okur."""
    path = Path(path)
    root = ET.parse(path).getroot()
    netlist = Netlist(path=path)

    comps_el = root.find("components")
    if comps_el is not None:
        for comp in comps_el.findall("comp"):
            ref = comp.get("ref", "")
            if not ref:
                continue
            libsource = comp.find("libsource")
            netlist.components[ref] = SchComponent(
                ref=ref,
                value=_text(comp, "value"),
                footprint=_text(comp, "footprint"),
                libpart=libsource.get("part", "") if libsource is not None else "",
            )

    nets_el = root.find("nets")
    if nets_el is not None:
        for net_el in nets_el.findall("net"):
            net = Net(
                code=net_el.get("code", ""),
                name=net_el.get("name", ""),
                netclass=net_el.get("class", "Default"),
            )
            for node_el in net_el.findall("node"):
                net.nodes.append(
                    NetNode(
                        ref=node_el.get("ref", ""),
                        pin=node_el.get("pin", ""),
                        pinfunction=node_el.get("pinfunction", ""),
                        pintype=node_el.get("pintype", ""),
                    )
                )
            netlist.nets.append(net)

    return netlist
