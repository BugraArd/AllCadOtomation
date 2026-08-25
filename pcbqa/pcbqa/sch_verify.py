"""Netlist degismezligi kalkani (Asama 4b).

Sematikte baglanti GEOMETRIKTIR: tel ucu pine deger, o yuzden bagli sayilir.
PCB'de durum farkli - orada net, pad'in icinde ismiyle yazilidir. Sonuc: bir
sembolu sematikte kaydirmak baglantiyi SESSIZCE koparabilir.

Olculdu: pic_programmer uzerinde R1 12.7 mm kaydirildiginda pin 2 koptu ve
netlist'te `unconnected-(R1-Pad2)` olarak belirdi. Hicbir hata, hicbir uyari.

Bu modul o sessizligi kaldirir. Yazma islemlerinin oncesi ve sonrasi icin
`kicad-cli sch export netlist` calistirir, ciktiyi kanonik bir baglanti
yapisina cevirir ve karsilastirir.

## Dogru degismez nedir?

Ham XML metnini karsilastirmak yanlis olurdu: net KODLARI her ihracatta
yeniden numaralanir ve otomatik net ADLARI (`Net-(R1-Pad1)`,
`unconnected-(...)`) bilesen konumuna gore degisebilir. Bunlar gercek bir
baglanti degisikligi degildir.

Dogru degismez, pinlerin aglara BOLUNUSUDUR:

    {  {(R1,1), (U1,3)},  {(R1,2), (C4,1)},  ... }

Yani net adlarindan bagimsiz olarak, hangi pinlerin ayni agda oldugu.
Bu bolunme ayni kaldigi surece devre elektriksel olarak degismemistir.
"""

from __future__ import annotations

import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .kicadcli import KicadCliError, find_kicad_cli

# Bir pin: (bilesen referansi, pin numarasi)
PinKey = tuple[str, str]
# Bir ag: o agdaki pinlerin kumesi
NetKey = frozenset[PinKey]


class SchVerifyError(RuntimeError):
    """Netlist alinamadi."""


@dataclass
class Connectivity:
    """Bir sematigin kanonik baglanti yapisi."""

    source: Path
    # Ag bolunmesi: net adindan BAGIMSIZ
    partition: frozenset[NetKey] = frozenset()
    # Yalnizca raporlama icin: pin -> okunabilir net adi
    net_of: dict[PinKey, str] = field(default_factory=dict)
    components: frozenset[str] = frozenset()

    @property
    def pin_count(self) -> int:
        return sum(len(net) for net in self.partition)

    @property
    def net_count(self) -> int:
        return len(self.partition)


@dataclass
class ConnectivityDiff:
    """Iki baglanti yapisi arasindaki fark."""

    ok: bool
    lost_pins: list[PinKey] = field(default_factory=list)
    gained_pins: list[PinKey] = field(default_factory=list)
    # (pin, onceki_ag_adi, sonraki_ag_adi, onceki_ag_boyutu, sonraki_ag_boyutu)
    regrouped: list[tuple[PinKey, str, str, int, int]] = field(default_factory=list)
    added_components: list[str] = field(default_factory=list)
    removed_components: list[str] = field(default_factory=list)

    def describe(self) -> str:
        if self.ok:
            return "baglanti degismedi"
        parts = []
        if self.removed_components:
            parts.append(f"{len(self.removed_components)} bilesen kayboldu")
        if self.added_components:
            parts.append(f"{len(self.added_components)} bilesen eklendi")
        if self.lost_pins:
            parts.append(f"{len(self.lost_pins)} pin kayboldu")
        if self.gained_pins:
            parts.append(f"{len(self.gained_pins)} pin belirdi")
        if self.regrouped:
            parts.append(f"{len(self.regrouped)} pin baska aga tasindi")
        return "BAGLANTI DEGISTI: " + ", ".join(parts)

    def details(self, limit: int = 10) -> list[str]:
        lines: list[str] = []
        for ref in self.removed_components[:limit]:
            lines.append(f"  bilesen kayboldu: {ref}")
        for ref in self.added_components[:limit]:
            lines.append(f"  bilesen eklendi: {ref}")
        for ref, pin in self.lost_pins[:limit]:
            lines.append(f"  pin kayboldu: {ref}.{pin}")
        for ref, pin in self.gained_pins[:limit]:
            lines.append(f"  pin belirdi: {ref}.{pin}")
        for (ref, pin), before, after, n_before, n_after in self.regrouped[:limit]:
            if before == after:
                # Ag adi ayni kalabilir ama uyelik degismistir - asil olay budur
                lines.append(
                    f"  {ref}.{pin}: '{before}' agi degisti ({n_before} -> {n_after} pin)"
                )
            else:
                lines.append(f"  {ref}.{pin}: '{before}' ({n_before} pin) -> '{after}' ({n_after} pin)")
        return lines


def export_netlist(sch_path: Path, out_path: Path, kicad_cli: str | None = None) -> Path:
    """kicad-cli ile kicadxml netlist ihrac eder."""
    try:
        cli = find_kicad_cli(kicad_cli)
    except KicadCliError as exc:
        raise SchVerifyError(str(exc)) from exc
    out_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [str(cli), "sch", "export", "netlist", "--format", "kicadxml", "-o", str(out_path), str(sch_path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not out_path.is_file():
        message = (proc.stderr or proc.stdout or "").strip()[:400]
        raise SchVerifyError(f"netlist ihraci basarisiz ({sch_path.name}): {message}")
    return out_path


def parse_netlist(xml_path: Path, source: Path | None = None) -> Connectivity:
    """kicadxml netlist'i kanonik baglanti yapisina cevirir."""
    root = ET.parse(xml_path).getroot()

    nets: list[NetKey] = []
    net_of: dict[PinKey, str] = {}
    for net in root.iter("net"):
        name = net.get("name", "")
        pins: set[PinKey] = set()
        for node in net.findall("node"):
            ref = node.get("ref")
            pin = node.get("pin")
            if ref is None or pin is None:
                continue
            key = (ref, pin)
            pins.add(key)
            net_of[key] = name
        if pins:
            nets.append(frozenset(pins))

    components = {
        comp.get("ref") for comp in root.iter("comp") if comp.get("ref") is not None
    }

    return Connectivity(
        source=source or xml_path,
        partition=frozenset(nets),
        net_of=net_of,
        components=frozenset(components),
    )


def connectivity_of(
    sch_path: Path,
    kicad_cli: str | None = None,
    work_dir: Path | None = None,
) -> Connectivity:
    """Bir .kicad_sch dosyasinin kanonik baglanti yapisini dondurur."""
    sch_path = Path(sch_path)
    if work_dir is not None:
        work_dir.mkdir(parents=True, exist_ok=True)
        target = work_dir / f"{sch_path.stem}-netlist.xml"
        export_netlist(sch_path, target, kicad_cli)
        return parse_netlist(target, source=sch_path)

    with tempfile.TemporaryDirectory(prefix="pcbqa-net-") as tmp:
        target = Path(tmp) / "netlist.xml"
        export_netlist(sch_path, target, kicad_cli)
        return parse_netlist(target, source=sch_path)


def compare(before: Connectivity, after: Connectivity) -> ConnectivityDiff:
    """Iki baglanti yapisini karsilastirir.

    Net adlari ve kodlari yok sayilir; yalnizca pinlerin aglara bolunusu
    onemlidir. Bolunme ayniysa devre elektriksel olarak degismemistir.
    """
    if before.partition == after.partition:
        return ConnectivityDiff(ok=True)

    before_pins = set(before.net_of)
    after_pins = set(after.net_of)

    lost = sorted(before_pins - after_pins)
    gained = sorted(after_pins - before_pins)

    # Ortak pinlerden hangileri baska bir gruba tasinmis?
    def group_of(conn: Connectivity) -> dict[PinKey, NetKey]:
        return {pin: net for net in conn.partition for pin in net}

    before_group = group_of(before)
    after_group = group_of(after)

    regrouped: list[tuple[PinKey, str, str, int, int]] = []
    for pin in sorted(before_pins & after_pins):
        # Ayni agdaki komsu kumesi degistiyse gercek bir degisiklik vardir
        old_net = before_group.get(pin)
        new_net = after_group.get(pin)
        if old_net != new_net:
            regrouped.append(
                (
                    pin,
                    before.net_of.get(pin, ""),
                    after.net_of.get(pin, ""),
                    len(old_net) if old_net else 0,
                    len(new_net) if new_net else 0,
                )
            )

    return ConnectivityDiff(
        ok=False,
        lost_pins=lost,
        gained_pins=gained,
        regrouped=regrouped,
        added_components=sorted(after.components - before.components),
        removed_components=sorted(before.components - after.components),
    )


def verify_unchanged(
    before_sch: Path,
    after_sch: Path,
    kicad_cli: str | None = None,
    work_dir: Path | None = None,
) -> ConnectivityDiff:
    """Iki sematik dosyasinin ELEKTRIKSEL olarak ayni olup olmadigini soyler.

    Yazma islemlerinin kalkani budur: `ok=False` donerse yazma reddedilmelidir.
    """
    return compare(
        connectivity_of(before_sch, kicad_cli, work_dir),
        connectivity_of(after_sch, kicad_cli, work_dir),
    )
