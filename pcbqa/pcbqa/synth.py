"""Sentetik test karti ureteci.

Neden gerekli: yerlestirme motorunu (Asama 3) gelistirmek icin KOTU bir karta
ihtiyac var. Temiz bir kartta optimize edilecek bir sey yoktur - skor zaten
yuksektir, motor "iyilestirdim" diyemez.

Bu modul ayni devreden iki kart uretir:

    bench_good.kicad_pcb   makul yerlesim  -> hedef skor
    bench_bad.kicad_pcb    bozuk yerlesim  -> motorun duzeltmesi gereken kart

Devrenin dogru cevabi bizde: hangi kondansatorun hangi IC'ye ait oldugunu,
hangi netlerin diferansiyel cift oldugunu kod belirliyor. Yani kurallarin
gercekten dogru seyi yakalayip yakalamadigini kanitlayabiliyoruz.

Kullanim:
    python -m pcbqa.synth --out samples
"""

from __future__ import annotations

import argparse
import random
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# KiCad 10 dosya surumu (demo dosyalarindan)
KICAD_VERSION = "20260206"

LAYER_TABLE = """\t(layers
\t\t(0 "F.Cu" signal "top_layer")
\t\t(2 "B.Cu" signal "bottom_layer")
\t\t(13 "F.Paste" user)
\t\t(15 "B.Paste" user)
\t\t(5 "F.SilkS" user "F.Silkscreen")
\t\t(7 "B.SilkS" user "B.Silkscreen")
\t\t(1 "F.Mask" user)
\t\t(3 "B.Mask" user)
\t\t(17 "Dwgs.User" user "User.Drawings")
\t\t(19 "Cmts.User" user "User.Comments")
\t\t(25 "Edge.Cuts" user)
\t\t(27 "Margin" user)
\t\t(31 "F.CrtYd" user "F.Courtyard")
\t\t(29 "B.CrtYd" user "B.Courtyard")
\t\t(35 "F.Fab" user)
\t\t(33 "B.Fab" user)
\t)"""


def _uuid() -> str:
    return str(uuid.uuid4())


# --------------------------------------------------------------------- veri tipi


@dataclass
class PadSpec:
    """Tek bir pad: konum footprint'e gore yerel (mm)."""

    number: str
    dx: float
    dy: float
    w: float
    h: float
    net: str = ""
    pintype: str = "passive"


@dataclass
class Part:
    """Karta yerlestirilecek bir bilesen."""

    ref: str
    value: str
    footprint: str
    pads: list[PadSpec]
    # Courtyard yarim boyutlari (merkeze gore +/- w/2, h/2)
    cw: float
    ch: float
    x: float = 0.0
    y: float = 0.0
    rot: float = 0.0
    layer: str = "F.Cu"


@dataclass
class BoardSpec:
    name: str
    width: float
    height: float
    parts: list[Part] = field(default_factory=list)
    # Devrenin "dogru cevabi": kural dosyasini ve motoru dogrularken kullanilir
    truth: dict = field(default_factory=dict)


# ----------------------------------------------------------------- footprint'ler


def two_pad(ref: str, value: str, net_a: str, net_b: str, size: str = "0603") -> Part:
    """Iki uclu SMD bilesen (kondansator, direnc, bobin)."""
    dims = {
        "0402": (0.5, 0.55, 0.45, 1.5, 0.9),
        "0603": (0.75, 0.8, 0.9, 2.2, 1.3),
        "0805": (0.9, 1.0, 1.25, 2.6, 1.6),
        "1206": (1.4, 1.15, 1.8, 3.8, 2.0),
    }
    pitch, w, h, cw, ch = dims.get(size, dims["0603"])
    return Part(
        ref=ref,
        value=value,
        footprint=f"Gen:C_{size}",
        cw=cw,
        ch=ch,
        pads=[
            PadSpec("1", -pitch, 0, w, h, net_a, "passive"),
            PadSpec("2", +pitch, 0, w, h, net_b, "passive"),
        ],
    )


def soic(ref: str, value: str, pins: list[tuple[str, str]], pitch: float = 1.27) -> Part:
    """SOIC benzeri govde. `pins` = [(net, pintype), ...] 1. pinden baslayarak.

    Pin duzeni gercek SOIC gibi: sol sutun asagi dogru, sag sutun yukari dogru.
    """
    n = len(pins)
    if n % 2:
        raise ValueError("SOIC pin sayisi cift olmali")
    per_side = n // 2
    span = (per_side - 1) * pitch
    body_w = 3.9
    pad_w, pad_h = 1.5, 0.6
    x_off = body_w / 2 + pad_w / 2 - 0.3

    pads: list[PadSpec] = []
    for i, (net, ptype) in enumerate(pins, start=1):
        if i <= per_side:  # sol sutun, yukaridan asagi
            dx = -x_off
            dy = -span / 2 + (i - 1) * pitch
        else:  # sag sutun, asagidan yukari
            k = i - per_side - 1
            dx = +x_off
            dy = +span / 2 - k * pitch
        pads.append(PadSpec(str(i), dx, dy, pad_w, pad_h, net, ptype))

    return Part(
        ref=ref,
        value=value,
        footprint=f"Gen:SOIC-{n}",
        cw=x_off + pad_w / 2 + 0.25,
        ch=span / 2 + 1.0,
        pads=pads,
    )


def sot23_5(ref: str, value: str, pins: list[tuple[str, str]]) -> Part:
    """5 pinli SOT-23 (regulator)."""
    if len(pins) != 5:
        raise ValueError("SOT-23-5 tam 5 pin ister")
    coords = [(-0.95, 1.1), (0.0, 1.1), (0.95, 1.1), (0.95, -1.1), (-0.95, -1.1)]
    pads = [
        PadSpec(str(i + 1), cx, cy, 0.6, 1.0, net, ptype)
        for i, ((cx, cy), (net, ptype)) in enumerate(zip(coords, pins))
    ]
    return Part(ref=ref, value=value, footprint="Gen:SOT-23-5", cw=1.7, ch=1.75, pads=pads)


def crystal(ref: str, value: str, net_a: str, net_b: str, gnd: str = "GND") -> Part:
    """3225 kristal: 1 ve 3 sinyal, 2 ve 4 govde toprak."""
    pads = [
        PadSpec("1", -1.1, -0.85, 1.2, 1.0, net_a, "passive"),
        PadSpec("2", 1.1, -0.85, 1.2, 1.0, gnd, "passive"),
        PadSpec("3", 1.1, 0.85, 1.2, 1.0, net_b, "passive"),
        PadSpec("4", -1.1, 0.85, 1.2, 1.0, gnd, "passive"),
    ]
    return Part(ref=ref, value=value, footprint="Gen:Crystal_3225", cw=1.9, ch=1.7, pads=pads)


def header(ref: str, value: str, nets: list[tuple[str, str]], pitch: float = 2.54) -> Part:
    """Tek sira dik konnektor."""
    n = len(nets)
    span = (n - 1) * pitch
    pads = [
        PadSpec(str(i + 1), -span / 2 + i * pitch, 0, 1.7, 1.7, net, ptype)
        for i, (net, ptype) in enumerate(nets)
    ]
    return Part(
        ref=ref,
        value=value,
        footprint=f"Gen:PinHeader_1x{n:02d}",
        cw=span / 2 + 1.27,
        ch=1.6,
        pads=pads,
    )


# ------------------------------------------------------------------- dosya uretimi


def _fmt(v: float) -> str:
    return f"{v:.4f}".rstrip("0").rstrip(".") or "0"


def _render_pad(pad: PadSpec) -> str:
    net = f'\n\t\t\t(net "{pad.net}")' if pad.net else ""
    return (
        f'\t\t(pad "{pad.number}" smd roundrect\n'
        f"\t\t\t(at {_fmt(pad.dx)} {_fmt(pad.dy)})\n"
        f"\t\t\t(size {_fmt(pad.w)} {_fmt(pad.h)})\n"
        f'\t\t\t(layers "F.Cu" "F.Paste" "F.Mask")\n'
        f"\t\t\t(roundrect_rratio 0.25)"
        f"{net}\n"
        f'\t\t\t(pintype "{pad.pintype}")\n'
        f'\t\t\t(uuid "{_uuid()}")\n'
        f"\t\t)"
    )


def _render_part(part: Part) -> str:
    cw, ch = part.cw, part.ch
    courtyard = (
        f"\t\t(fp_poly\n"
        f"\t\t\t(pts\n"
        f"\t\t\t\t(xy {_fmt(-cw)} {_fmt(-ch)}) (xy {_fmt(cw)} {_fmt(-ch)})"
        f" (xy {_fmt(cw)} {_fmt(ch)}) (xy {_fmt(-cw)} {_fmt(ch)})\n"
        f"\t\t\t)\n"
        f"\t\t\t(stroke (width 0.05) (type solid))\n"
        f"\t\t\t(fill no)\n"
        f'\t\t\t(layer "F.CrtYd")\n'
        f'\t\t\t(uuid "{_uuid()}")\n'
        f"\t\t)"
    )

    def prop(name: str, val: str, dy: float, layer: str) -> str:
        return (
            f'\t\t(property "{name}" "{val}"\n'
            f"\t\t\t(at 0 {_fmt(dy)} 0)\n"
            f'\t\t\t(layer "{layer}")\n'
            f'\t\t\t(uuid "{_uuid()}")\n'
            f"\t\t\t(effects (font (size 1 1) (thickness 0.15)))\n"
            f"\t\t)"
        )

    parts = [
        f'\t(footprint "{part.footprint}"',
        f'\t\t(layer "{part.layer}")',
        f'\t\t(uuid "{_uuid()}")',
        f"\t\t(at {_fmt(part.x)} {_fmt(part.y)}"
        + (f" {_fmt(part.rot)})" if part.rot else ")"),
        prop("Reference", part.ref, -(ch + 0.8), "F.SilkS"),
        prop("Value", part.value, ch + 0.8, "F.Fab"),
        courtyard,
        *[_render_pad(p) for p in part.pads],
        "\t)",
    ]
    return "\n".join(parts)


def render_board(spec: BoardSpec) -> str:
    """BoardSpec -> .kicad_pcb metni."""
    edge = (
        f"\t(gr_rect\n"
        f"\t\t(start 0 0)\n"
        f"\t\t(end {_fmt(spec.width)} {_fmt(spec.height)})\n"
        f"\t\t(stroke (width 0.1) (type solid))\n"
        f"\t\t(fill no)\n"
        f'\t\t(layer "Edge.Cuts")\n'
        f'\t\t(uuid "{_uuid()}")\n'
        f"\t)"
    )

    lines = [
        "(kicad_pcb",
        f"\t(version {KICAD_VERSION})",
        '\t(generator "pcbqa-synth")',
        '\t(generator_version "10.0")',
        "\t(general\n\t\t(thickness 1.6)\n\t\t(legacy_teardrops no)\n\t)",
        '\t(paper "A4")',
        LAYER_TABLE,
        "\t(setup\n\t\t(pad_to_mask_clearance 0)\n\t)",
        *[_render_part(p) for p in spec.parts],
        edge,
        "\t(embedded_fonts no)",
        ")",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- ornek devre


def build_bench() -> BoardSpec:
    """Kucuk bir MCU karti: regulator + MCU + EEPROM + kristal + USB.

    Dort kural alanini da tetikleyecek sekilde tasarlandi:
      guc butunlugu  : decoupling kondansatorleri, regulator giris/cikis
      sinyal but.    : USB diferansiyel cifti, kristal netleri
      baglanti niyeti: I2C pull-up'lari, kristal yuk kondansatorleri
      uretilebilirlik: courtyard cakismasi, kart kenari mesafesi
    """
    P = "power_in"
    O = "power_out"
    B = "bidirectional"
    I = "input"
    p = "passive"

    parts: list[Part] = []

    # --- Guc girisi ve regulator ------------------------------------------
    parts.append(
        header("J1", "USB-C", [("VBUS", p), ("USB_DM", p), ("USB_DP", p), ("GND", p)])
    )
    parts.append(
        sot23_5(
            "U2",
            "AP2112K-3.3",
            [("VBUS", P), ("GND", P), ("VBUS", I), ("NC", p), ("3V3", O)],
        )
    )
    parts.append(two_pad("C1", "10uF", "VBUS", "GND", "0805"))  # regulator girisi
    parts.append(two_pad("C2", "10uF", "3V3", "GND", "0805"))  # regulator cikisi

    # --- MCU ---------------------------------------------------------------
    mcu_pins = [
        ("3V3", P),      # 1  VDD
        ("GND", P),      # 2  GND
        ("XIN", I),      # 3
        ("XOUT", "output"),  # 4
        ("nRESET", I),   # 5
        ("SDA", B),      # 6
        ("SCL", B),      # 7
        ("TX", "output"),# 8
        ("RX", I),       # 9
        ("GND", P),      # 10
        ("DM_MCU", B),   # 11
        ("DP_MCU", B),   # 12
        ("GPIO1", B),    # 13
        ("GPIO2", B),    # 14
        ("GPIO3", B),    # 15
        ("GPIO4", B),    # 16
        ("AVDD", P),     # 17
        ("AGND", P),     # 18
        ("GPIO5", B),    # 19
        ("3V3", P),      # 20 VDD
    ]
    parts.append(soic("U1", "MCU32", mcu_pins))

    # MCU decoupling: C3 -> pin 1, C4 -> pin 20, C5 -> AVDD
    parts.append(two_pad("C3", "100nF", "3V3", "GND", "0402"))
    parts.append(two_pad("C4", "100nF", "3V3", "GND", "0402"))
    parts.append(two_pad("C5", "100nF", "AVDD", "AGND", "0402"))

    # --- EEPROM ------------------------------------------------------------
    parts.append(
        soic(
            "U3",
            "24C16",
            [
                ("GND", I), ("GND", I), ("GND", I), ("GND", P),
                ("SDA", B), ("SCL", I), ("GND", I), ("3V3", P),
            ],
        )
    )
    parts.append(two_pad("C6", "100nF", "3V3", "GND", "0402"))  # U3 decoupling

    # --- Kristal ve yuk kondansatorleri ------------------------------------
    parts.append(crystal("Y1", "12MHz", "XIN", "XOUT"))
    parts.append(two_pad("C7", "22pF", "XIN", "GND", "0402"))
    parts.append(two_pad("C8", "22pF", "XOUT", "GND", "0402"))

    # --- Pull-up'lar -------------------------------------------------------
    parts.append(two_pad("R1", "4k7", "SDA", "3V3", "0402"))
    parts.append(two_pad("R2", "4k7", "SCL", "3V3", "0402"))
    # nRESET icin pull-up BILEREK KONULMADI -> baglanti niyeti kurali yakalamali.
    # Bu bir DEVRE kusuru, yerlesim kusuru degil: her iki kartta da var ve
    # yerlestirme motoru bunu asla duzeltemez. Kasitli olarak boyle birakildi.

    # --- USB seri dirpercleri ----------------------------------------------
    # Diferansiyel cift uzunlugunu YERLESIMLE kontrol edebilmek icin gercek
    # USB tasarimlarindaki gibi seri direnc konuldu. Bunlar olmasa cift
    # uzunlugu tamamen pin geometrisine baglanir ve yerlesimle degistirilemezdi.
    parts.append(two_pad("R4", "22R", "USB_DM", "DM_MCU", "0402"))
    parts.append(two_pad("R5", "22R", "USB_DP", "DP_MCU", "0402"))

    # --- Seri port konnektoru ----------------------------------------------
    parts.append(header("J2", "UART", [("3V3", p), ("TX", p), ("RX", p), ("GND", p)]))

    truth = {
        "decoupling": {
            "C3": "U1", "C4": "U1", "C5": "U1", "C6": "U3", "C2": "U2", "C1": "U2",
        },
        "crystal_caps": {"C7": "Y1", "C8": "Y1"},
        "diff_pairs": [["USB_DP", "USB_DM"], ["DP_MCU", "DM_MCU"]],
        "series_terminators": {"R4": "USB_DM", "R5": "USB_DP"},
        "pullups": {"SDA": "R1", "SCL": "R2", "nRESET": None},
        "planted_defects": [],
    }

    return BoardSpec(name="bench", width=60.0, height=45.0, parts=parts, truth=truth)


# ------------------------------------------------------------------ yerlesimler


def place_good(spec: BoardSpec) -> None:
    """Makul yerlesim: her kondansator ait oldugu pinin yaninda.

    Bu kart hedeftir. Yerlesimle ilgili tum kurallardan gecmesi beklenir;
    geriye sadece devre kaynakli (yerlesimle duzeltilemeyen) bulgu kalir.
    """
    # U1 (SOIC-20) pin konumlari, merkez (34,25):
    #   pin 1..10  sol sutun, x=31.6, y=19.285'ten 1.27 araliklarla asagi
    #   pin 11..20 sag sutun, x=36.4, y=30.715'ten 1.27 araliklarla YUKARI
    # Yani pin 20, pin 1'in tam karsisindadir (ikisi de ustte) - gercek SOIC gibi.
    layout = {
        # USB girisi ve seri direncler (cift simetrik yerlesmis)
        "J1": (8, 25, 90),
        "R4": (16, 26.27, 0),
        "R5": (16, 23.73, 0),
        # Guc yolu
        "C1": (15, 33, 0),
        "U2": (20, 33, 0),
        "C2": (26, 33, 0),
        # MCU ve kendi decoupling'leri
        "U1": (34, 25, 0),
        "C3": (31.6, 16.5, 0),      # U1.1  (31.6, 19.285)
        "C4": (39.5, 19.285, 0),    # U1.20 (36.4, 19.285)
        "C5": (39.5, 23.095, 0),    # U1.17 (36.4, 23.095) AVDD
        # EEPROM
        "U3": (50, 32, 0),
        "C6": (55.5, 30.095, 0),    # U3.8  (52.4, 30.095)
        # Kristal ve yuk kondansatorleri
        "Y1": (26, 22.5, 0),
        "C7": (24.9, 19, 0),
        "C8": (28.2, 19, 0),
        # Pull-up'lar ve seri port
        "R1": (44, 20, 0),
        "R2": (44, 22.5, 0),
        "J2": (34, 39, 0),
    }
    _apply(spec, layout)


def place_bad(spec: BoardSpec, seed: int = 7) -> None:
    """Bozuk yerlesim: kasitli kusurlar + rastgele dagitma.

    Buradaki her kusur bilerek konuldu; kural motorunun hepsini yakalamasi
    beklenir. Motorun (Asama 3) isi bu karti place_good'a yaklastirmak.
    """
    rng = random.Random(seed)

    layout = {
        "U1": (34, 25, 0),
        "C3": (31.6, 16.5, 0),      # SAGLAM birakildi: kural yanlis alarm vermemeli
        "C4": (54, 41, 0),          # KUSUR: U1 decoupling'i kartin obur ucunda
        "C5": (52, 6, 0),           # KUSUR: AVDD decoupling'i cok uzak
        "U3": (50, 32, 0),
        "C6": (8, 40, 0),           # KUSUR: U3 decoupling'i uzak
        "Y1": (14, 12, 0),
        "C7": (15.6, 12, 0),        # KUSUR: Y1 ile courtyard cakismasi
        "C8": (45, 15, 0),          # KUSUR: kristal yuk kondansatoru cok uzak
        "U2": (20, 33, 0),
        "C1": (15, 33, 0),
        "C2": (26, 33, 0),
        # J1/J2 KILITLI bilesenlerdir (konnektorler mekanik olarak sabittir) ve
        # bu yuzden bench_good ile AYNI konumda dururlar. Kilitli bir bilesene
        # kusur ekmek tutarsiz olurdu: yerlestirici onu tasiyamayacagi icin
        # duzeltilemez bir ceza olur ve ulasilabilir tavani dusururdu.
        # Ekilen kusurlar yalnizca tasinabilir bilesenlerde.
        "J1": (8, 25, 90),
        "J2": (34, 39, 0),
        "R1": (44, 20, 0),
        "R2": (44, 20.9, 0),        # KUSUR: R1 ile cakisma
        "R4": (16, 26.27, 0),
        "R5": (16, 9, 0),           # KUSUR: diferansiyel cift simetrisi bozuk
    }
    _apply(spec, layout)

    # Kalan bilesenleri hafifce dagit (motorun temizleyecegi gurultu)
    for part in spec.parts:
        if part.ref in {"U1", "U2", "U3", "Y1", "J1", "J2"}:
            continue
        part.x += rng.uniform(-1.5, 1.5)
        part.y += rng.uniform(-1.5, 1.5)

    # Ekilen kusurlarin tamami TASINABILIR bilesenlerde, yani yerlestirme
    # motorunun duzeltebilecegi seyler. Hepsi kapanirsa skor bench_good ile
    # ayni seviyeye (67) cikar.
    spec.truth["planted_defects"] = [
        "C4 uzak (U1 decoupling)",
        "C5 uzak (AVDD decoupling)",
        "C6 uzak (U3 decoupling)",
        "C8 uzak (kristal yuk kondansatoru)",
        "C7/Y1 courtyard cakismasi",
        "R1/R2 courtyard cakismasi",
        "R5 yanlis yerde -> USB cift simetrisi bozuk",
    ]
    spec.truth["circuit_defects"] = [
        "nRESET pull-up yok (her iki kartta da var, yerlesimle duzeltilemez)",
    ]
    spec.truth["locked_components"] = {
        "J1": "konnektor - mekanik olarak sabit, bench_good ile ayni konumda",
        "J2": "konnektor - mekanik olarak sabit, bench_good ile ayni konumda",
    }


def _apply(spec: BoardSpec, layout: dict[str, tuple[float, float, float]]) -> None:
    missing = [p.ref for p in spec.parts if p.ref not in layout]
    if missing:
        raise ValueError(f"yerlesimde eksik bilesen: {missing}")
    for part in spec.parts:
        part.x, part.y, part.rot = layout[part.ref]


# ------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="pcbqa.synth", description="Sentetik test karti uretir (iyi + kotu yerlesim)."
    )
    ap.add_argument("--out", type=Path, default=Path("samples"), help="Cikis klasoru")
    ap.add_argument("--seed", type=int, default=7, help="Dagitma icin rastgelelik tohumu")
    args = ap.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)

    good = build_bench()
    place_good(good)
    good_path = args.out / "bench_good.kicad_pcb"
    good_path.write_text(render_board(good), encoding="utf-8")

    bad = build_bench()
    place_bad(bad, seed=args.seed)
    bad_path = args.out / "bench_bad.kicad_pcb"
    bad_path.write_text(render_board(bad), encoding="utf-8")

    print(f"yazildi: {good_path}  ({len(good.parts)} bilesen)")
    print(f"yazildi: {bad_path}   ({len(bad.parts)} bilesen)")
    print("\nkasitli kusurlar:")
    for defect in bad.truth["planted_defects"]:
        print(f"  - {defect}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
