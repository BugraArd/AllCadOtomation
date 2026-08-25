"""Tasarim modeli: sematik BAGLANTI bilgisi + PCB KONUM bilgisi ayni yerde.

KiCad bu ikisini ayri tutar. "C3 elektriksel olarak U1.VDD'ye bagli, AMA
fiziksel olarak 12 mm uzakta" gibi bir cumleyi kurabilmek icin ikisinin
birlestirilmesi gerekir; bu modulun tek isi bu.

Kural motoru (rules.py) ve ileride yerlestirme motoru sadece bu modeli gorur,
KiCad'i hic bilmez.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .netlist import NetNode, Netlist
from .pcb import Board, Component

# Referans onekinden bilesen turu. Yerlestirme kurallarinin cogu tur bazli.
REF_KINDS: list[tuple[str, str]] = [
    (r"^C\d", "capacitor"),
    (r"^R\d", "resistor"),
    (r"^L\d", "inductor"),
    (r"^D\d", "diode"),
    (r"^Q\d", "transistor"),
    (r"^U\d", "ic"),
    (r"^Y\d|^X\d", "crystal"),
    (r"^J\d|^P\d|^CON", "connector"),
    (r"^SW\d", "switch"),
    (r"^F\d", "fuse"),
    (r"^TP\d", "testpoint"),
]


def ref_kind(ref: str) -> str:
    for pattern, kind in REF_KINDS:
        if re.match(pattern, ref, re.IGNORECASE):
            return kind
    return "other"


@dataclass
class PinRef:
    """Fiziksel konumu cozulmus bir pin."""

    ref: str
    pin: str
    function: str
    pintype: str
    net: str
    x: float | None = None
    y: float | None = None

    @property
    def placed(self) -> bool:
        return self.x is not None and self.y is not None

    def distance_to(self, other: "PinRef") -> float | None:
        if not (self.placed and other.placed):
            return None
        return math.hypot(self.x - other.x, self.y - other.y)

    def __str__(self) -> str:
        return f"{self.ref}.{self.function or self.pin}"


@dataclass
class Metrics:
    """Tasarimin olculebilir buyuklukleri.

    Asama 3'teki yerlestirme motoru tam olarak bu sayilari kucultmeye calisacak.
    """

    component_count: int = 0
    placed_count: int = 0
    net_count: int = 0
    total_hpwl_mm: float = 0.0
    board_area_mm2: float | None = None
    component_area_mm2: float = 0.0
    # Yuz basina kaplanan alan: {"F": mm2, "B": mm2}
    area_by_side: dict[str, float] = field(default_factory=dict)
    longest_nets: list[tuple[str, float]] = field(default_factory=list)
    parse_warnings: int = 0

    @property
    def density_pct(self) -> float | None:
        """En yogun yuzun doluluk orani.

        Cift tarafli kartlarda iki yuzun alanini toplamak %100'u asan anlamsiz
        sonuclar verir; bu yuzden yuzler ayri hesaplanip en yuksegi alinir.
        """
        if not self.board_area_mm2:
            return None
        busiest = max(self.area_by_side.values(), default=self.component_area_mm2)
        return 100.0 * busiest / self.board_area_mm2


@dataclass
class Design:
    """Birlestirilmis tasarim: sematik + PCB."""

    board: Board
    netlist: Netlist
    project_name: str = ""

    # ref -> Component (PCB tarafi)
    _by_ref: dict[str, Component] = field(default_factory=dict, repr=False)
    # net adi -> konumu cozulmus pinler
    _net_pins: dict[str, list[PinRef]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._by_ref = {c.ref: c for c in self.board.components}
        self._build_net_pins()

    # ------------------------------------------------------------------ kurulum

    def _build_net_pins(self) -> None:
        """Netlist'teki her pini, PCB'deki pad konumuyla eslestirir."""
        for net in self.netlist.nets:
            pins: list[PinRef] = []
            for node in net.nodes:
                pin = PinRef(
                    ref=node.ref,
                    pin=node.pin,
                    function=node.pinfunction,
                    pintype=node.pintype,
                    net=net.name,
                )
                comp = self._by_ref.get(node.ref)
                if comp is not None:
                    pad = comp.pad(node.pin)
                    if pad is not None:
                        pin.x, pin.y = pad.x, pad.y
                pins.append(pin)
            self._net_pins[net.name] = pins

    # ------------------------------------------------------------------ sorgular

    def component(self, ref: str) -> Component | None:
        return self._by_ref.get(ref)

    def value_of(self, ref: str) -> str:
        sch = self.netlist.components.get(ref)
        if sch and sch.value:
            return sch.value
        comp = self._by_ref.get(ref)
        return comp.value if comp else ""

    def kind_of(self, ref: str) -> str:
        return ref_kind(ref)

    def pins_on_net(self, net_name: str) -> list[PinRef]:
        return self._net_pins.get(net_name, [])

    def all_pins(self):
        for pins in self._net_pins.values():
            yield from pins

    def pins_of(self, ref: str) -> list[PinRef]:
        return [p for p in self.all_pins() if p.ref == ref]

    def net_names(self) -> list[str]:
        return list(self._net_pins)

    def unplaced_refs(self) -> list[str]:
        """Sematikte var, PCB'de yok."""
        return sorted(r for r in self.netlist.components if r not in self._by_ref)

    def orphan_refs(self) -> list[str]:
        """PCB'de var, sematikte yok."""
        return sorted(r for r in self._by_ref if r not in self.netlist.components)

    # ------------------------------------------------------------------ olcumler

    def hpwl(self, net_name: str) -> float:
        """Yari-cevre tel uzunlugu (Half-Perimeter Wire Length).

        Netin tum pinlerini iceren en kucuk dikdortgenin genislik+yukseklik
        toplami. Yonlendirme (routing) yapilmadan once gercek bakir uzunlugu
        icin kullanilan endustri standardi tahmindir: hizli ve yeterince dogru.
        """
        pts = [(p.x, p.y) for p in self.pins_on_net(net_name) if p.placed]
        if len(pts) < 2:
            return 0.0
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (max(xs) - min(xs)) + (max(ys) - min(ys))

    def metrics(self, top_n: int = 5) -> Metrics:
        lengths = [(name, self.hpwl(name)) for name in self.net_names()]
        lengths.sort(key=lambda kv: kv[1], reverse=True)

        return Metrics(
            component_count=len(self.netlist.components),
            placed_count=len(self._by_ref),
            net_count=len(self.netlist.nets),
            total_hpwl_mm=sum(v for _, v in lengths),
            board_area_mm2=self.board.area_mm2,
            component_area_mm2=sum(c.area_mm2 for c in self.board.components),
            area_by_side=self.board.area_by_side(),
            longest_nets=[kv for kv in lengths[:top_n] if kv[1] > 0],
            parse_warnings=self.board.parse_warnings,
        )


def build_design(board: Board, netlist: Netlist, project_name: str = "") -> Design:
    return Design(board=board, netlist=netlist, project_name=project_name)
