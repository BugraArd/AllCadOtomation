"""PARCA TABLOSU - her bilesen icin ag, gerilim, akim, MPN, fiyat.

    pcbqa parcalar <sematik>
    pcbqa parcalar <sematik> --csv tablo.csv

## Bu modulun tek zor sorusu: neyi BILMIYORUZ

Bir parcanin uzerinden gecen akimi bilmek, genel halde, benzetim ister -
`pcbqa`nin SPICE'i yok. O yuzden buradaki kural sudur: her sayinin yaninda
NEREDEN BILINDIGI yazilir, ve turetilemeyen sayi BOS birakilir. Tabloda
"0.33 mA" gormek ile "-" gormek arasindaki fark, tahmin ile olcum
arasindaki farktir.

Gercekten turetilebilen uc sey var:

  1. RAY GERILIMI - net ADINDAN. KiCad guc sembolleri "+3V3", "+5V",
     "-12V", "+1V8" diye adlandirilir; bu ad bir kanittir, tahmin degil.
     GND ailesi 0 V'tur cunku referans dugumu odur. Buna karsilik "VCC" ya
     da "VDD" HICBIR SEY soylemez - 1.8 V da olabilir 24 V da; boyle bir ad
     gorulunce gerilim BILINMIYOR yazilir.
  2. DIRENC AKIMI - iki ucunun da gerilimi biliniyorsa Ohm yasasi:
     I = |dV| / R. Baska varsayim yok.
  3. KONDANSATOR AKIMI - kararli halde DC akim gecmez. Bu bir tahmin degil,
     elemanin tanimi (sizinti ve dalgalanma akimi disinda).

Bunlarin disinda kalan her sey - tumlesik devreler, diyotlar, LED'ler,
transistorler, bobinler - "benzetim gerekir" diye isaretlenir. Bir LED'in
akimi seri direncinden hesaplanabilirdi ama ileri gerilimi (Vf) parcaya
ozgudur ve kutuphanede yazmaz; Vf uydurmak tabloyu kirletirdi.

## MPN ve fiyat SENTETIKTIR

`mpn.py`nin verisi test icindir (her MPN "SENT-" ile baslar). Tablo bunu
saklamaz: yazili alan ile oneri ayri sutunda gosterilir.

Ana giris: `tablo(sch_path)` -> `[Satir]`. CLI: `python -m pcbqa.elektrik`.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import mpn
from .lexicon import DESIGNATORS, normalize_designator
from .sch_verify import SchVerifyError, connectivity_of
from .schematic import Schematic, read_schematic


class ElektrikError(RuntimeError):
    """Tablo cikarilamadi."""


# --------------------------------------------------------------------------
# 1) Ray gerilimi - net ADINDAN
# --------------------------------------------------------------------------
#
# Referans dugumu. "0 V" burada bir olcum degil TANIM: devrenin gerilimleri
# bu dugume gore sayilir.

TOPRAK = {"GND", "GNDA", "GNDD", "GNDPWR", "GNDREF", "AGND", "DGND", "PGND",
          "VSS", "VSSA", "EARTH", "0V"}

# Adi gerilim SOYLEMEYEN yaygin raylar. Bunlar tabloda bos kalir; "VCC 5V'tur"
# diye bir varsayim, sematikte 3.3 V ile calisan bir kartta yanlis akim
# hesaplatirdi.
SESSIZ = {"VCC", "VDD", "VCCA", "VDDA", "VCCIO", "VIN", "VOUT", "VBAT",
          "VREF", "VEE", "VPP", "AVDD", "AVCC", "VDDIO"}

# "+3V3" -> 3.3   ("V" ondalik ayraci yerine gecer; KiCad ve endustri gelenegi)
_RAY_HARFLI = re.compile(r"^([+-]?)(\d+)V(\d+)$", re.IGNORECASE)
# "+5V", "+3.3V", "-12V"
_RAY_DUZ = re.compile(r"^([+-]?)(\d+(?:\.\d+)?)V$", re.IGNORECASE)


def _sayiya(parca: str) -> float | None:
    m = _RAY_HARFLI.match(parca)
    if m:
        isaret, tam, kesir = m.groups()
        deger = float(f"{tam}.{kesir}")
        return -deger if isaret == "-" else deger
    m = _RAY_DUZ.match(parca)
    if m:
        isaret, sayi = m.groups()
        deger = float(sayi)
        return -deger if isaret == "-" else deger
    return None


# KiCad baglanmamis pine `unconnected-(R2-Pad1)` diye bir ad uydurur. Bu bir
# ag adi degil, "burada ag yok"un yazili halidir; tabloda oyle gosterilir.
_BAGSIZ = "unconnected-("


def bagli_mi(net_ad: str) -> bool:
    return bool(net_ad) and not net_ad.startswith(_BAGSIZ)


def ag_metni(net_ad: str) -> str:
    if not net_ad:
        return "?"
    return "(bagli degil)" if net_ad.startswith(_BAGSIZ) else net_ad


def ray_gerilimi(net_ad: str) -> tuple[float | None, str]:
    """Net ADINDAN gerilim. Doner: (volt ya da None, nereden bilindigi).

    Ad bir kanittir: "+3V3" adli bir agi 3.3 V saymak tahmin degil, KiCad'in
    guc sembolu adlandirma gelenegini okumaktir. Ama "VCC" bir kanit
    DEGILDIR ve None doner.
    """
    ad = (net_ad or "").strip()
    if not ad:
        return None, ""
    buyuk = ad.upper().lstrip("/")

    if buyuk in TOPRAK:
        return 0.0, "referans dugumu (0 V tanimi)"
    if buyuk in SESSIZ:
        return None, f"{ad!r} adi gerilimi soylemiyor (herhangi bir deger olabilir)"

    # USB 2.0 spec 7.2.1: VBUS nominal 5 V (4.75-5.25). Ad tek basina yeter.
    if buyuk in ("VBUS", "USB_VBUS", "VUSB"):
        return 5.0, "USB 2.0 spec 7.2.1: VBUS nominal 5 V"

    deger = _sayiya(buyuk.lstrip("+"))
    if deger is not None:
        return (deger if not buyuk.startswith("-") else -abs(deger),
                f"ray adi cozumlendi ({ad})")

    # "VDD_3V3", "3V3_MCU" gibi bilesik adlar: parcalarindan biri sayiysa o.
    for parca in re.split(r"[_\-/]", buyuk):
        deger = _sayiya(parca)
        if deger is not None:
            return deger, f"ray adinin {parca!r} parcasi cozumlendi"

    return None, ""


# --------------------------------------------------------------------------
# 2) Satir
# --------------------------------------------------------------------------


@dataclass
class Satir:
    """Tablodaki tek bir parca."""

    ref: str
    deger: str = ""
    lib_id: str = ""
    onek: str = ""              # C, R, U...
    tur: str = ""               # "Kondansator", "Direnc"...
    # (pin numarasi, ag adi, gerilim ya da None)
    baglantilar: list[tuple[str, str, float | None]] = field(default_factory=list)
    gerilim_v: float | None = None      # iki uclu parcada |dV|
    gerilim_kaynak: str = ""
    akim_a: float | None = None
    akim_kaynak: str = ""
    mpn: str = ""
    uretici: str = ""
    fiyat: float | None = None
    mpn_durum: str = ""         # "yazili" | "oneri" | ""

    @property
    def aglar(self) -> str:
        return ", ".join(f"{p}:{ag_metni(a)}" for p, a, _ in self.baglantilar)

    @property
    def bagsiz_pinler(self) -> list[str]:
        return [p for p, a, _ in self.baglantilar if not bagli_mi(a)]

    def gerilim_metni(self) -> str:
        if self.gerilim_v is not None:
            return f"{self.gerilim_v:g} V"
        bilinen = [(p, g) for p, _, g in self.baglantilar if g is not None]
        if bilinen:
            return " / ".join(f"{p}:{g:g}V" for p, g in bilinen)
        return "-"

    def akim_metni(self) -> str:
        if self.akim_a is None:
            return "-"
        if self.akim_a == 0.0:
            return "~0"
        if abs(self.akim_a) < 1e-3:
            return f"{self.akim_a * 1e6:.3g} uA"
        if abs(self.akim_a) < 1.0:
            return f"{self.akim_a * 1e3:.3g} mA"
        return f"{self.akim_a:.3g} A"

    def fiyat_metni(self) -> str:
        return "-" if self.fiyat is None else f"${self.fiyat:.4f}"

    def as_dict(self) -> dict:
        return {
            "ref": self.ref, "deger": self.deger, "lib_id": self.lib_id,
            "tur": self.tur, "aglar": self.aglar,
            "gerilim": self.gerilim_metni(), "gerilim_kaynak": self.gerilim_kaynak,
            "akim": self.akim_metni(), "akim_kaynak": self.akim_kaynak,
            "mpn": self.mpn, "uretici": self.uretici,
            "fiyat": self.fiyat_metni(), "mpn_durum": self.mpn_durum,
        }


# --------------------------------------------------------------------------
# 3) Akim turetme
# --------------------------------------------------------------------------


def _akim(satir: Satir) -> tuple[float | None, str]:
    """Akim ve nereden bilindigi. Turetilemiyorsa (None, NEDEN)."""
    gerilimler = [g for _, _, g in satir.baglantilar]
    bilinmeyen = [a for _, a, g in satir.baglantilar if g is None and bagli_mi(a)]
    bagsiz = satir.bagsiz_pinler

    # Baglanmamis pin "bilinmiyor" degil, "akim yok"tur - ama parcanin TAMAMI
    # bagsizsa bunu akim diye yazmak yaniltir; sebep olarak soylenir.
    if bagsiz:
        return None, ("baglanmamis pin: " + ", ".join(bagsiz))

    if satir.onek == "C":
        # Kondansatorun DC akimi sifirdir - bu bir tahmin degil, elemanin
        # tanimi. Sizinti ve dalgalanma akimi buna dahil degil.
        return 0.0, "kararli halde DC akim gecmez (sizinti/dalgalanma disi)"

    if satir.onek == "R":
        if len(satir.baglantilar) != 2:
            return None, f"{len(satir.baglantilar)} uclu direnc - iki uc bekleniyordu"
        if bilinmeyen:
            return None, f"ag gerilimi bilinmiyor: {', '.join(sorted(set(bilinmeyen)))}"
        direnc = mpn.parse_value(satir.deger)
        if direnc is None:
            return None, f"deger okunamadi: {satir.deger!r}"
        if direnc <= 0:
            return None, f"sifir direnc ({satir.deger}) - akim sinirsiz cikar"
        fark = abs(gerilimler[0] - gerilimler[1])
        return fark / direnc, f"Ohm yasasi: |{fark:g} V| / {satir.deger}"

    if bilinmeyen:
        return None, f"ag gerilimi bilinmiyor: {', '.join(sorted(set(bilinmeyen)))}"
    return None, "aktif bilesen - akim icin benzetim gerekir"


def _gerilim(satir: Satir) -> tuple[float | None, str]:
    """Iki uclu parcada uclar arasi fark; digerlerinde None."""
    if len(satir.baglantilar) != 2:
        return None, ""
    (_, a_ad, a), (_, b_ad, b) = satir.baglantilar
    if a is None or b is None:
        return None, ""
    return abs(a - b), f"{a_ad} ({a:g} V) - {b_ad} ({b:g} V)"


# --------------------------------------------------------------------------
# 4) Tablo
# --------------------------------------------------------------------------


_SAYI = re.compile(r"(\d+)")


def _sirala(ref: str) -> tuple[str, int, str]:
    """C2, C10 dogru sirada dursun diye sayiyi ayri anahtar yapariz."""
    m = _SAYI.search(ref)
    onek = ref[: m.start()] if m else ref
    return (onek, int(m.group(1)) if m else 0, ref)


def tablo(
    sch_path: Path | str,
    *,
    kicad_cli: str | None = None,
    oneri: bool = True,
) -> list[Satir]:
    """Sematigin parca tablosu.

    Aglar `kicad-cli`nin netlist'inden gelir - sematikte baglanti geometrik
    oldugu icin dosyaya bakarak "bu pin hangi agda" sorusu guvenle
    cevaplanamaz (bkz. `sch_verify`).
    """
    schematic: Schematic = read_schematic(sch_path)
    try:
        conn = connectivity_of(schematic.root_path, kicad_cli)
    except SchVerifyError as exc:
        raise ElektrikError(f"netlist alinamadi: {exc}") from exc

    yazili = {kayit["ref"]: kayit for kayit in mpn.read_assignments(schematic)}

    satirlar: list[Satir] = []
    for sym in schematic.real_symbols:
        m = re.match(r"^([A-Za-z]+)", sym.ref)
        onek = normalize_designator(m.group(1)) if m else ""
        satir = Satir(
            ref=sym.ref,
            deger=sym.value,
            lib_id=sym.lib_id,
            onek=onek,
            tur=DESIGNATORS.get(onek, {}).get("tr", ""),
        )
        for pin in sorted(sym.pins, key=lambda p: _sirala(p.number)):
            ag = conn.net_of.get((sym.ref, pin.number), "")
            volt, _nereden = ray_gerilimi(ag)
            satir.baglantilar.append((pin.number, ag, volt))

        satir.gerilim_v, satir.gerilim_kaynak = _gerilim(satir)
        satir.akim_a, satir.akim_kaynak = _akim(satir)

        kayit = yazili.get(sym.ref)
        if kayit and kayit.get("mpn"):
            satir.mpn = kayit.get("mpn", "")
            satir.uretici = kayit.get("uretici", "")
            fiyat = kayit.get("fiyat")
            satir.fiyat = float(fiyat) if fiyat not in (None, "") else None
            satir.mpn_durum = "yazili"
        elif oneri:
            adaylar = mpn.candidates(onek, sym.value)
            if adaylar:
                satir.mpn = adaylar[0].mpn
                satir.uretici = adaylar[0].manufacturer
                satir.fiyat = adaylar[0].price
                satir.mpn_durum = "oneri"

        satirlar.append(satir)

    satirlar.sort(key=lambda s: _sirala(s.ref))
    return satirlar


def ozet(satirlar: list[Satir]) -> dict:
    """Neyi bildigimizin sayisi - saklanmayacak oran."""
    toplam = len(satirlar)
    gerilim = sum(1 for s in satirlar
                  if s.gerilim_v is not None
                  or any(g is not None for _, _, g in s.baglantilar))
    akim = sum(1 for s in satirlar if s.akim_a is not None)
    fiyat = sum(1 for s in satirlar if s.fiyat is not None)
    return {
        "parca": toplam,
        "gerilimi_bilinen": gerilim,
        "akimi_turetilebilen": akim,
        "fiyati_olan": fiyat,
        "toplam_fiyat": round(sum(s.fiyat or 0.0 for s in satirlar), 4),
    }


BASLIKLAR = ["Ref", "Deger", "Tur", "Aglar", "Gerilim", "Akim",
             "MPN", "Fiyat", "Nasil bilindi"]


def satir_hucreleri(s: Satir) -> list[str]:
    nereden = s.akim_kaynak or s.gerilim_kaynak or ""
    mpn_metni = s.mpn + (" (oneri)" if s.mpn_durum == "oneri" else "")
    return [s.ref, s.deger, s.tur, s.aglar, s.gerilim_metni(), s.akim_metni(),
            mpn_metni, s.fiyat_metni(), nereden]


def metin_tablosu(satirlar: list[Satir], genislik: int = 34) -> str:
    """Hizalanmis metin tablosu (CLI ve arayuzun metin dokumu icin)."""
    hucreler = [BASLIKLAR] + [satir_hucreleri(s) for s in satirlar]
    kirp = [min(genislik, max(len(r[i]) for r in hucreler))
            for i in range(len(BASLIKLAR))]
    lines = []
    for j, row in enumerate(hucreler):
        parcalar = [(h if len(h) <= kirp[i] else h[: kirp[i] - 1] + "~").ljust(kirp[i])
                    for i, h in enumerate(row)]
        lines.append("  ".join(parcalar).rstrip())
        if j == 0:
            lines.append("  ".join("-" * w for w in kirp))
    return "\n".join(lines)


def csv_yaz(satirlar: list[Satir], hedef: Path) -> Path:
    hedef = Path(hedef)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    with hedef.open("w", encoding="utf-8-sig", newline="") as f:
        yazici = csv.writer(f, delimiter=";")
        yazici.writerow(BASLIKLAR)
        for s in satirlar:
            yazici.writerow(satir_hucreleri(s))
    return hedef


# --------------------------------------------------------------------------
# Komut satiri
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pcbqa.elektrik",
        description="Her parca icin ag, gerilim, akim, MPN ve fiyat tablosu.",
    )
    ap.add_argument("sch", type=Path, help="Kok .kicad_sch dosyasi")
    ap.add_argument("--csv", type=Path, default=None, help="Tabloyu CSV olarak yaz")
    ap.add_argument("--no-oneri", action="store_true",
                    help="Yazili MPN yoksa oneri gosterme")
    ap.add_argument("--kicad-cli", default=None)
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    try:
        satirlar = tablo(args.sch, kicad_cli=args.kicad_cli, oneri=not args.no_oneri)
    except (ElektrikError, OSError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 1

    if not satirlar:
        print("sematikte gercek bilesen yok")
        return 1

    print(metin_tablosu(satirlar))
    print()
    o = ozet(satirlar)
    print(f"  {o['parca']} parca | gerilimi bilinen {o['gerilimi_bilinen']} | "
          f"akimi turetilebilen {o['akimi_turetilebilen']} | "
          f"fiyati olan {o['fiyati_olan']} (toplam ${o['toplam_fiyat']:.4f})")
    print("  BOS hucre = turetilemedi; MPN ve fiyat SENTETIKTIR (test verisi).")
    if args.csv:
        print(f"  CSV: {csv_yaz(satirlar, args.csv)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
