"""MPN KATALOGU - her bilesen icin parca numarasi ve fiyat alanlari.

    pcbqa mpn <sematik>                        sematikteki MPN/fiyat alanlarini goster
    pcbqa mpn <sematik> --katalog C            bir tur icin aday parcalari listele
    pcbqa mpn <sematik> --ata C --uygula       kondansatorlere MPN + fiyat yaz
    pcbqa mpn <sematik> --ata C --sirala ucuz  en ucuzdan pahaliya sirala

## !!! BU KATALOG SENTETIKTIR - GERCEK PARCA DEGILDIR !!!

Uretilen her MPN `SENT-` ile baslar ve fiyatlar uydurmadir. Bu bilincli bir
karar: su an sinanan sey ALAN YAZMA yolu (uygulama sematige MPN ve fiyat
yazabiliyor mu, KiCad geri okuyabiliyor mu), tedarik verisinin dogrulugu
degil.

Her sembole ayrica `MPN_Kaynak = sentetik-test` alani yazilir. Ileride gercek
bir tedarikci baglandiginda o alan `sentetik-test` olan her kayit GUVENLE
uzerine yazilabilir; boyle bir isaret olmasaydi uydurma fiyatlar gercek
sanilirdi. Sessizce gercekmis gibi duran veri, hic veri olmamasindan kotudur.

## Katalog nasil uretiliyor

Deterministik: ayni (lib_id, deger) ikilisi her zaman ayni adaylari verir.
Rastgelelik yok - `hashlib` ile tohumlanmis sabit bir turetme. Boylece iki
kosuda farkli fiyat cikip "neden degisti" sorusu dogmaz.

Fiyat, bilesenin BUYUKLUGUYLE artar (deger buyudukce pahali) ve her adayda
paket/tolerans farkiyla catallanir. Gercekci degil ama TUTARLI: en ucuz
gercekten en ucuz, siralama anlamli.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from .schematic import Schematic, read_schematic
from .sch_write import SchWriteError, write_tree
from .sexpr import child, children, head, parse

KAYNAK_ALANI = "MPN_Kaynak"
KAYNAK_DEGERI = "sentetik-test"
MPN_ALANI = "MPN"
FIYAT_ALANI = "Price"
URETICI_ALANI = "Manufacturer"

# Sentetik uretici adlari - gercek firma adi KULLANILMIYOR, cunku uydurma bir
# fiyatin yanina gercek bir marka yazmak yanlis izlenim birakir.
URETICILER = ("SentCo", "TestParts", "MockElec", "DemoComp")

# Paket varyantlari: tur -> (paket, fiyat carpani). Carpanlar uydurma ama
# SIRALI: kucuk paket ucuz, genis toleransli ucuz.
PAKETLER: dict[str, tuple[tuple[str, float], ...]] = {
    "C": (("0402", 1.00), ("0603", 1.15), ("0805", 1.35), ("1206", 1.70)),
    "R": (("0402", 1.00), ("0603", 1.10), ("0805", 1.25), ("1206", 1.55)),
    "L": (("0603", 1.00), ("0805", 1.30), ("1210", 1.90)),
    "D": (("SOD-323", 1.00), ("SOD-123", 1.20), ("SMA", 1.60)),
    "Q": (("SOT-23", 1.00), ("SOT-223", 1.80), ("DPAK", 2.60)),
    "U": (("SOT-23-5", 1.00), ("SOIC-8", 1.40), ("QFN-16", 2.10)),
}
VARSAYILAN_PAKETLER = (("STD", 1.00), ("ALT", 1.35))


# --------------------------------------------------------------------------
# Deger ayristirma
# --------------------------------------------------------------------------

_DEGER = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*([pnumkMG]?)\s*([FHR]|ohm|Ohm)?\s*$")
_CARPAN = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3,
           "": 1.0, "k": 1e3, "M": 1e6, "G": 1e9}


def parse_value(text: str) -> float | None:
    """"10uF" -> 1e-5, "5k" -> 5000. Anlasilmazsa None.

    Fiyati degere baglayabilmek icin gerekiyor. Anlasilmayan deger fiyatsiz
    kalir - uydurma bir sayi atamaktansa bosluk birakmak dogru.
    """
    m = _DEGER.match(text or "")
    if not m:
        return None
    sayi, onek, _birim = m.groups()
    try:
        return float(sayi) * _CARPAN.get(onek, 1.0)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Katalog
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Part:
    """Sentetik bir aday parca."""

    mpn: str
    manufacturer: str
    package: str
    price: float          # birim fiyat, USD (uydurma)

    def as_dict(self) -> dict:
        return {"mpn": self.mpn, "uretici": self.manufacturer,
                "paket": self.package, "fiyat": round(self.price, 4)}


def _seed(*parts: str) -> int:
    ham = "|".join(parts).encode("utf-8")
    return int(hashlib.sha256(ham).hexdigest()[:8], 16)


def _base_price(designator: str, value: str) -> float | None:
    """Temel fiyat: buyuk deger daha pahali. Doner: fiyat, ya da anlasilmazsa None.

    Deger okunamiyorsa None doner - uydurma bir sayi atamaktansa bosluk
    birakmak dogru. (Ilk surumde burada 0.10 sabiti vardi ve `Device:C`'nin
    varsayilan "C" degeri de fiyat aliyordu; yani hicbir sey bilinmeyen bir
    parcaya guvenle fiyat yazilmis oluyordu.)
    """
    buyukluk = parse_value(value)
    if buyukluk is None or buyukluk <= 0:
        # SIFIR da "okunamadi" ile ayni kovaya girer, iki sebeple. Birincisi
        # matematik: log10(0) ValueError atar - olculdu, samples/pic_programmer
        # C4'un degeri "0" ve `pcbqa mpn` o kartta cokuyordu. Ikincisi anlam:
        # 0 ohm'luk bir kopru direncinin fiyati BUYUKLUKTEN turetilemez, o
        # yuzden tahmin etmektense bos birakmak dogru olan.
        return None
    # Onlu logaritma kaba bir olcek verir: 1pF ile 100uF arasi ~8 kademe.
    # Egim BILINCLI OLARAK dik (0.08/kademe): asagidaki sapmanin siralamayi
    # BOZMAMASI gerekiyor. Olculdu - ilk surumde egim 0.012 ve sapma %17'ye
    # kadardi, sonucta 5uF'lik kondansator 10uF'likten pahali cikiyordu.
    import math

    kademe = max(0.0, math.log10(buyukluk) + 12.0)   # pF tabanli
    return round(0.02 + 0.08 * kademe, 4)


def candidates(designator: str, value: str, count: int = 4) -> list[Part]:
    """Bir (tur, deger) icin sentetik aday parcalar - fiyata gore ARTAN.

    Deger anlasilmiyorsa BOS liste doner.
    """
    taban = _base_price(designator, value)
    if taban is None:
        return []
    paketler = PAKETLER.get(designator, VARSAYILAN_PAKETLER)
    tohum = _seed(designator, value)

    out: list[Part] = []
    for i, (paket, carpan) in enumerate(paketler[:count]):
        # Fiyat SAF bir (deger, paket) fonksiyonudur - rastgele sapma YOK.
        #
        # Ilk iki surumde "fiyatlar birbirinin tam kati gorunmesin" diye
        # deterministik bir sapma vardi. Gercekci duruyordu ama ISTENEN SEYI
        # BOZUYORDU: ust kademelerde adimlar kuculuyor (40uF -> 45uF yalnizca
        # %0.4) ve %2'lik sapma siralamayi ters ceviriyordu - olculdu, C10
        # (45uF) C9'dan (40uF) ucuz cikti. Gorsel bir suslemenin, istenen
        # degismezi (deger buyuduce fiyat artar) bozmasina izin verilmez.
        fiyat = round(taban * carpan, 4)
        seri = f"{(tohum >> (i * 5)) % 9000 + 1000}"
        out.append(Part(
            mpn=f"SENT-{designator}{seri}-{paket.replace('-', '')}",
            manufacturer=URETICILER[(tohum + i) % len(URETICILER)],
            package=paket,
            price=fiyat,
        ))
    return sorted(out, key=lambda p: p.price)


# --------------------------------------------------------------------------
# Sematikteki alanlar
# --------------------------------------------------------------------------


def _q(text: str) -> str:
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _symbol_nodes(root) -> list:
    return [n for n in root if isinstance(n, list) and head(n) == "symbol"
            and child(n, "lib_id") is not None]


def _ref_of(node) -> str:
    for p in children(node, "property"):
        if len(p) > 2 and str(p[1]).strip('"') == "Reference":
            return str(p[2]).strip('"')
    return ""


def set_property(node, name: str, value: str) -> bool:
    """Sembol dugumunde bir ozelligi yazar ya da gunceller. Doner: degisti mi.

    Yeni alan eklerken konum olarak Reference alaninin `at` degeri kopyalanip
    GIZLENIR: MPN ve fiyat sayfada gorunmemeli, yoksa sematik okunmaz hale
    gelir. KiCad bunlari BOM'da yine de gorur.
    """
    for p in children(node, "property"):
        if len(p) > 2 and str(p[1]).strip('"') == name:
            if str(p[2]).strip('"') == value:
                return False
            p[2] = _q(value)
            return True

    ornek = None
    for p in children(node, "property"):
        if len(p) > 2 and str(p[1]).strip('"') in ("Datasheet", "Footprint", "Reference"):
            ornek = p
            break
    at = child(ornek, "at") if ornek is not None else None
    yeni = ["property", _q(name), _q(value)]
    if at is not None:
        yeni.append(["at", at[1], at[2], at[3] if len(at) > 3 else "0"])
    yeni += [["hide", "yes"], ["show_name", "no"], ["do_not_autoplace", "no"],
             ["effects", ["font", ["size", "1.27", "1.27"]]]]
    node.append(yeni)
    return True


@dataclass
class Assignment:
    ref: str
    value: str
    part: Part
    rank: int             # 0 = en ucuz


@dataclass
class AssignPlan:
    assignments: list[Assignment]
    problems: list[str]

    def describe(self) -> str:
        return (f"{len(self.assignments)} bilesene MPN ve fiyat"
                + (f", {len(self.problems)} engel" if self.problems else ""))


def plan_assignment(schematic: Schematic, designator: str,
                    order: str = "ucuz", sheet_path: str = "/") -> AssignPlan:
    """Bir turdeki butun bilesenlere aday parca dagitir.

    `order="ucuz"`: referans numarasi kucuk olana en ucuz parca. Kullanicinin
    istedigi sinav bu - C2 en ucuz, C11 en pahali.
    """
    hedefler = [s for s in schematic.symbols
                if s.sheet_path == sheet_path
                and not s.is_virtual
                and s.ref.startswith(designator)
                and s.ref[len(designator):].isdigit()]
    hedefler.sort(key=lambda s: int(s.ref[len(designator):]))

    atamalar: list[Assignment] = []
    engeller: list[str] = []
    # Butun adaylari topla, fiyata gore sirala, sonra bilesenlere dagit.
    havuz: list[tuple[Part, str]] = []
    secim: dict[str, Part] = {}
    for sym in hedefler:
        adaylar = candidates(designator, sym.value)
        if not adaylar:
            engeller.append(
                f"{sym.ref}: degeri ({sym.value!r}) okunamadi, fiyat atanmadi"
            )
            continue
        secim[sym.ref] = adaylar[0] if order == "ucuz" else adaylar[-1]
        havuz.append((secim[sym.ref], sym.ref))

    havuz.sort(key=lambda ikili: ikili[0].price)
    sira_of = {ref: i for i, (_p, ref) in enumerate(havuz)}

    for sym in hedefler:
        if sym.ref not in secim:
            continue
        atamalar.append(Assignment(ref=sym.ref, value=sym.value,
                                   part=secim[sym.ref], rank=sira_of[sym.ref]))
    return AssignPlan(assignments=atamalar, problems=engeller)


def apply_assignment(path: Path, plan: AssignPlan, *, apply: bool = False,
                     backup: bool = True, allow_open_project: bool = False):
    root = parse(Path(path).read_text(encoding="utf-8"))
    by_ref = {_ref_of(n): n for n in _symbol_nodes(root)}
    degisen = 0
    for a in plan.assignments:
        node = by_ref.get(a.ref)
        if node is None:
            plan.problems.append(f"{a.ref}: sembol agacta bulunamadi")
            continue
        degisen += set_property(node, MPN_ALANI, a.part.mpn)
        degisen += set_property(node, FIYAT_ALANI, f"{a.part.price:.4f}")
        degisen += set_property(node, URETICI_ALANI, a.part.manufacturer)
        degisen += set_property(node, KAYNAK_ALANI, KAYNAK_DEGERI)
    return write_tree(Path(path), root, apply=apply, backup=backup,
                      allow_open_project=allow_open_project), degisen


def read_assignments(schematic: Schematic) -> list[dict]:
    """Sematikteki mevcut MPN/fiyat alanlarini okur."""
    out = []
    for s in schematic.symbols:
        if s.is_virtual:
            continue
        mpn = s.properties.get(MPN_ALANI, "")
        if not mpn:
            continue
        out.append({
            "ref": s.ref, "deger": s.value, "mpn": mpn,
            "fiyat": s.properties.get(FIYAT_ALANI, ""),
            "uretici": s.properties.get(URETICI_ALANI, ""),
            "kaynak": s.properties.get(KAYNAK_ALANI, ""),
        })
    return sorted(out, key=lambda d: float(d["fiyat"] or 0))


# --------------------------------------------------------------------------
# Komut satiri
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pcbqa.mpn",
        description="Bilesenlere SENTETIK MPN ve fiyat alani yazar (test amacli).",
    )
    ap.add_argument("sch", help="sematik dosyasi ya da proje klasoru")
    ap.add_argument("--katalog", metavar="ONEK",
                    help="Bir tur icin aday parcalari listele (or. C)")
    ap.add_argument("--deger", default="10uF", help="--katalog ile: hangi deger")
    ap.add_argument("--ata", metavar="ONEK", help="Bu turdeki bilesenlere ata (or. C)")
    ap.add_argument("--sirala", default="ucuz", choices=("ucuz", "pahali"),
                    help="ucuz: en ucuz adayi sec (varsayilan)")
    ap.add_argument("--sayfa", default="/")
    ap.add_argument("--uygula", action="store_true", help="dosyaya yaz")
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--kicad-acikken", dest="acikken", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)

    if args.katalog:
        print(f"SENTETIK katalog - {args.katalog} / {args.deger}")
        print("  (gercek parca DEGIL; MPN'ler SENT- ile baslar)")
        for i, p in enumerate(candidates(args.katalog, args.deger)):
            print(f"  {i}. {p.mpn:<26} {p.manufacturer:<10} {p.package:<9} "
                  f"${p.price:.4f}")
        return 0

    try:
        schematic = read_schematic(args.sch)
    except FileNotFoundError as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2
    path = schematic.file_of_sheet.get(args.sayfa, schematic.root_path)

    if not args.ata:
        kayitlar = read_assignments(schematic)
        if not kayitlar:
            print("sematikte MPN alani olan bilesen yok")
            print("atamak icin: pcbqa mpn <sematik> --ata C --uygula")
            return 0
        print(f"{path.name}: {len(kayitlar)} bilesende MPN alani var "
              "(ucuzdan pahaliya)")
        toplam = 0.0
        for k in kayitlar:
            fiyat = float(k["fiyat"] or 0)
            toplam += fiyat
            isaret = "" if k["kaynak"] == KAYNAK_DEGERI else "  [KAYNAK ISARETSIZ]"
            print(f"  {k['ref']:<6} {k['deger']:<8} {k['mpn']:<26} "
                  f"{k['uretici']:<10} ${fiyat:.4f}{isaret}")
        print(f"  {'toplam':<6} {'':<8} {'':<26} {'':<10} ${toplam:.4f}")
        return 0

    plan = plan_assignment(schematic, args.ata, args.sirala, args.sayfa)
    if not plan.assignments:
        print(f"'{args.ata}' onekli bilesen bulunamadi")
        return 1

    print(f"{path.name}  ({plan.describe()})")
    for a in sorted(plan.assignments, key=lambda x: x.part.price):
        print(f"  {a.ref:<6} {a.value:<8} -> {a.part.mpn:<26} "
              f"{a.part.package:<9} ${a.part.price:.4f}")
    for e in plan.problems:
        print(f"  ENGEL: {e}")

    try:
        sonuc, degisen = apply_assignment(path, plan, apply=args.uygula,
                                          backup=not args.no_backup,
                                          allow_open_project=args.acikken)
    except SchWriteError as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2

    print()
    print(f"  {degisen} alan {'YAZILDI' if sonuc.written else 'yazilacak (kuru calisma)'}")
    if sonuc.written:
        print(f"  yedek: {sonuc.backup}")
        print(f"  NOT: bu veri SENTETIKTIR - her sembolde {KAYNAK_ALANI}="
              f"{KAYNAK_DEGERI} isareti var.")
    return 2 if plan.problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
