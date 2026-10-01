"""Testler icin sentetik devre: netlist + kart + kosullar -> devre grafi.

Koordinatlari ve degerleri BIZ seciyoruz; boylece beklenen sonuc (rol,
akim, Tj) koddan bagimsiz olarak elle hesaplanabilir.
"""

from __future__ import annotations

from pathlib import Path

from pcbqa.devre import graf_kur
from pcbqa.devre.kosullar import kosullari_ayristir
from pcbqa.netlist import LibPin, Net, Netlist, NetNode, SchComponent
from pcbqa.pcb import Board, Component, Pad, Track, Via, Zone, ZoneFill


def parca(ref, deger, lib, part, footprint, pinler, alanlar=None, x=None, y=None):
    """pinler: [(no, ad, tip, ag, px, py)]"""
    return {"ref": ref, "deger": deger, "lib": lib, "part": part, "fp": footprint,
            "pinler": pinler, "alanlar": alanlar or {}, "x": x, "y": y}


def netlist_kur(parcalar) -> Netlist:
    n = Netlist(path=Path("sentetik.xml"))
    aglar: dict[str, Net] = {}
    for p in parcalar:
        n.components[p["ref"]] = SchComponent(ref=p["ref"], value=p["deger"], footprint=p["fp"],
                                              libpart=p["part"], lib=p["lib"], fields=dict(p["alanlar"]))
        n.libparts.setdefault((p["lib"], p["part"]),
                              [LibPin(no, ad, tip) for no, ad, tip, *_ in p["pinler"]])
        for no, ad, tip, ag, *_ in p["pinler"]:
            if not ag:
                continue
            net = aglar.setdefault(ag, Net(code=str(len(aglar) + 1), name=ag))
            net.nodes.append(NetNode(p["ref"], no, f"{ad}_{no}" if ad else "", tip))
    n.nets = list(aglar.values())
    return n


def kart_kur(parcalar, izler=(), vialar=(), dokumler=(), outline=(0.0, 0.0, 100.0, 100.0),
             pad_boyut=1.0) -> Board:
    comps = []
    for p in parcalar:
        pads = []
        for no, ad, tip, ag, px, py, *ek in p["pinler"]:
            kind, drill = (ek[0], ek[1]) if ek else ("smd", 0.0)
            pads.append(Pad(number=no, net=ag, x=px, y=py, pintype=tip, function=ad,
                            size_x=pad_boyut, size_y=pad_boyut, shape="rect",
                            copper_layers=() if kind == "thru_hole" else ("F.Cu",),
                            kind=kind, drill=drill))
        x = p["x"] if p["x"] is not None else pads[0].x
        y = p["y"] if p["y"] is not None else pads[0].y
        comps.append(Component(ref=p["ref"], value=p["deger"], footprint_id=p["fp"], x=x, y=y,
                               rotation=0.0, layer="F.Cu", pads=pads))
    b = Board(path=Path("sentetik.kicad_pcb"), components=comps, outline=outline)
    b.tracks = [Track(net, w, lyr, x1, y1, x2, y2) for net, w, lyr, x1, y1, x2, y2 in izler]
    b.vias = [Via(net, x, y, size, drill, ("F.Cu", "B.Cu")) for net, x, y, size, drill in vialar]
    b.zones = list(dokumler)
    return b


def dokum(net, layer, poly):
    return Zone(net=net, layers=(layer,), outline=list(poly), fills=[ZoneFill(layer, list(poly))])


def graf(parcalar, kosullar=None, kart=True, **kart_ayar):
    k = kosullari_ayristir(kosullar or {})
    board = kart_kur(parcalar, **kart_ayar) if kart else None
    return graf_kur(netlist=netlist_kur(parcalar), board=board, kosullar=k, proje="sentetik")


# --------------------------------------------------------------------------
# Hazir devre: 12 V giris -> AMS1117-3.3 -> MCU benzeri U2, I2C pull-up,
# dekuplaj, LED, 2N7002 ile anahtarlanan bobin (serbest gecis diyotu YOK).
# --------------------------------------------------------------------------

FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_C = "Capacitor_SMD:C_0805_2012Metric"


def ldo_devresi(*, diyot=False, pullup=True, dekuplaj=True, mosfet="2N7002", cikis_kond="22uF"):
    p = [
        parca("J1", "GIRIS", "Connector_Generic", "Conn_01x02",
              "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
              [("1", "Pin_1", "passive", "VBUS", 2.0, 10.0, "thru_hole", 1.0),
               ("2", "Pin_2", "passive", "GND", 2.0, 12.54, "thru_hole", 1.0)]),
        parca("C1", "10uF", "Device", "C", FP_C,
              [("1", "", "passive", "VBUS", 10.0, 10.0), ("2", "", "passive", "GND", 10.0, 12.0)]),
        parca("U1", "AMS1117-3.3", "Regulator_Linear", "AMS1117-3.3",
              "Package_TO_SOT_SMD:SOT-223-3_TabPin2",
              [("1", "GND", "power_in", "GND", 14.0, 14.0), ("2", "VO", "power_out", "3V3", 16.0, 14.0),
               ("3", "VI", "power_in", "VBUS", 18.0, 14.0)]),
        parca("C2", cikis_kond, "Device", "C", FP_C,
              [("1", "", "passive", "3V3", 20.0, 10.0), ("2", "", "passive", "GND", 20.0, 12.0)]),
        parca("U2", "MCU", "MCU_Sentetik", "MCU",
              "Package_QFP:LQFP-32_7x7mm_P0.8mm",
              [("1", "VDD", "power_in", "3V3", 40.0, 40.0), ("2", "VSS", "power_in", "GND", 40.0, 42.0),
               ("3", "PA1", "bidirectional", "SDA", 42.0, 40.0), ("4", "PA2", "output", "GATE", 42.0, 42.0)]),
        parca("D1", "LED", "Device", "LED", "LED_SMD:LED_0603_1608Metric",
              [("1", "K", "passive", "GND", 60.0, 60.0), ("2", "A", "passive", "LED_A", 62.0, 60.0)]),
        parca("R2", "1k", "Device", "R", FP_R,
              [("1", "", "passive", "3V3", 64.0, 60.0), ("2", "", "passive", "LED_A", 66.0, 60.0)]),
        parca("Q1", mosfet, "Transistor_FET", mosfet, "Package_TO_SOT_SMD:SOT-23",
              [("1", "G", "input", "GATE", 50.0, 50.0), ("2", "S", "passive", "GND", 52.0, 50.0),
               ("3", "D", "passive", "BOBIN", 54.0, 50.0)]),
        parca("L1", "10mH", "Device", "L", "Inductor_SMD:L_1210_3225Metric",
              [("1", "", "passive", "BOBIN", 56.0, 50.0), ("2", "", "passive", "VBUS", 58.0, 50.0)]),
    ]
    if pullup:
        p.append(parca("R1", "4k7", "Device", "R", FP_R,
                       [("1", "", "passive", "3V3", 44.0, 40.0), ("2", "", "passive", "SDA", 46.0, 40.0)]))
    if dekuplaj:
        p.append(parca("C3", "100nF 16V", "Device", "C", "Capacitor_SMD:C_0402_1005Metric",
                       [("1", "", "passive", "3V3", 40.0, 38.0), ("2", "", "passive", "GND", 41.0, 38.0)]))
    if diyot:
        p.append(parca("D2", "1N4007", "Device", "D", "Diode_SMD:D_SMA",
                       [("1", "K", "passive", "VBUS", 58.0, 52.0), ("2", "A", "passive", "BOBIN", 56.0, 52.0)]))
    return p


KOSUL_12V = {
    "raylar": {"VBUS": {"nom": 12, "min": 11.4, "max": 12.6}},
    "kaynaklar": ["VBUS"],
    "yukler": [{"ag": "3V3", "akim_a": 0.3, "ref": "U2", "pin": "1"}],
    "gereksinimler": [{"ag": "3V3", "min_v": 3.2, "max_v": 3.4}],
    "analiz": {"monte_carlo": 4, "sicakliklar": [85]},
}
