"""BAGLA - var olan sembolleri telle birlestirir.

    pcbqa bagla <sematik> --ag "R1.1 C1.1" --ag "#PWR01.1 R1.2"
    pcbqa bagla <sematik> --oner                 sayfaya bakip ONERSIN
    pcbqa bagla <sematik> --oner --uygula        oneriyi ciz

## Neden ayri bir komut

`sch_add` yeni bir sembol EKLERKEN baglantiyi da kurar. Ama sayfada zaten
duran semboller icin bir yol yoktu: elle s-expression yazmak ya da KiCad'de
tikitiklamak gerekiyordu. Bu komut o bosluğu kapatir - karar disarida, cizim
ve dogrulama burada.

## Iki giris yolu

  --ag   BEYAN: hangi pinlerin ayni aga girecegini sen soylersin. Belirsizlik
         yok, uygulama tahmin etmez.
  --oner CIKARIM: `propose.py` sayfadaki YERLESIMDEN niyet okur (hizalama,
         guc inisi) ve gerekcesiyle onerir. Kaniti olmayani onermez.

## Junction kurali

KiCad bir noktada UCTEN FAZLA baglanabilir oge bulusuyorsa junction ister
(`SCH_SCREEN::IsJunctionNeeded` de boyle yapar). Burada da oyle sayiyoruz:
pin bir oge, her tel ucu bir oge. Yeni tellerin kendi araindaki bulusmalar da
sayilir - `sch_wire.junctions_needed` yalnizca AGACTA OLAN tellere bakar ve
ayni anda eklenen tellerin bulusmasini goremez.

## Hakem

Yazdiktan sonra `kicad-cli`den netlist alinir ve istenen pinlerin GERCEKTEN
ayni aga girdigi dogrulanir. Kendi geometrimize degil KiCad'in kendi
cikarimina bakiyoruz; ikisi ayrisirsa haksiz olan biziz.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import propose, sch_wire
from .schematic import Schematic, read_schematic
from .sch_write import SchWriteError, write_tree
from .sexpr import head, parse

Point = tuple[float, float]
TOL = 1e-6


class ConnectError(RuntimeError):
    """Baglanti planlanamadi."""


@dataclass
class NetCheck:
    """Hakemin dogrulayacagi tek bir ag.

    Guc sembolleri (`#PWR`, `#FLG`) netlist'te HIC GORUNMEZ - KiCad onlari
    sanal sayar ve dugum olarak yazmaz. Olculdu: uc pinli `+10V/R1.1/C1.1`
    agi icin netlist yalnizca `C1.1, R1.1` donuyor. Bu yuzden guc pinini
    aramak yerine agin ADINA bakiyoruz: KiCad agi guc sembolunun degeriyle
    adlandirir, yani ad "+10V" ise guc gercekten baglanmistir.
    """

    pins: list[tuple[str, str]] = field(default_factory=list)   # gercek pinler
    power_name: str | None = None                               # beklenen ag adi
    label: str = ""


@dataclass
class ConnectPlan:
    sheet_path: str = "/"
    paths: list[list[Point]] = field(default_factory=list)
    junctions: list[Point] = field(default_factory=list)
    nets: list[NetCheck] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def wire_count(self) -> int:
        return sum(len(sch_wire._segments(p)) for p in self.paths)


# --------------------------------------------------------------------------
# Giris ayrıştırma
# --------------------------------------------------------------------------


def parse_net(text: str) -> list[tuple[str, str]]:
    """"R1.1 C1.1 #PWR01.1" -> [("R1","1"), ("C1","1"), ("#PWR01","1")]"""
    pins: list[tuple[str, str]] = []
    for parca in text.replace(",", " ").split():
        if "." not in parca:
            raise ConnectError(f"pin adi 'REF.PIN' biciminde olmali: {parca!r}")
        ref, _, number = parca.rpartition(".")
        if not ref or not number:
            raise ConnectError(f"pin adi eksik: {parca!r}")
        pins.append((ref, number))
    if len(pins) < 2:
        raise ConnectError(f"bir ag en az iki pin ister: {text!r}")
    return pins


def pin_point(schematic: Schematic, ref: str, number: str,
              sheet_path: str = "/") -> Point:
    for sym in schematic.symbols:
        if sym.ref != ref or sym.sheet_path != sheet_path:
            continue
        for pin in sym.pins:
            if pin.number == number:
                return (round(pin.x, 4), round(pin.y, 4))
        mevcut = ", ".join(sorted(p.number for p in sym.pins))
        raise ConnectError(f"{ref} sembolunde {number!r} pini yok (var olanlar: {mevcut})")
    raise ConnectError(f"{ref} diye bir sembol yok (sayfa {sheet_path})")


# --------------------------------------------------------------------------
# Yol cikarma
# --------------------------------------------------------------------------


def _order_chain(points: list[Point]) -> list[Point]:
    """Pinleri en yakin komsu zinciriyle sirala.

    Ucten fazla pinli bir agda hangi ciftlerin telleneceği serbesttir; en
    yakin komsu zinciri toplam tel boyunu kucuk tutar ve carpik yollar
    uretmez.
    """
    kalan = list(points[1:])
    zincir = [points[0]]
    while kalan:
        son = zincir[-1]
        yakin = min(kalan, key=lambda p: abs(p[0] - son[0]) + abs(p[1] - son[1]))
        kalan.remove(yakin)
        zincir.append(yakin)
    return zincir


def junctions_for(paths: list[list[Point]], schematic: Schematic,
                  sheet_path: str) -> list[Point]:
    """Ucten fazla oge bulusan noktalar - KiCad'in kendi kurali.

    Sayilanlar: bu sayfadaki pinler, agactaki tel uclari, ve YENI yollarin
    uclari. Ayrica bir uc baska bir telin ORTASINA denk geliyorsa orada da
    junction gerekir (ortadan gecen tel ikiye bolunmus sayilir).
    """
    sayim: dict[Point, int] = {}

    def ekle(point: Point, adet: int = 1) -> None:
        key = (round(point[0], 4), round(point[1], 4))
        sayim[key] = sayim.get(key, 0) + adet

    for (sheet, x, y) in schematic.pin_points():
        if sheet == sheet_path:
            ekle((x, y))
    for wire in schematic.wires:
        if wire.sheet_path != sheet_path:
            continue
        for end in wire.endpoints:
            ekle(end)
    for path in paths:
        for a, b in sch_wire._segments(path):
            ekle(a)
            ekle(b)

    # Bir ucun baska bir parcanin ortasina degmesi: o parca iki uca bolunur,
    # yani o noktada iki oge daha vardir.
    parcalar: list[tuple[Point, Point]] = []
    for wire in schematic.wires:
        if wire.sheet_path == sheet_path:
            parcalar.append(wire.endpoints)
    for path in paths:
        parcalar.extend(sch_wire._segments(path))

    for point in list(sayim):
        for a, b in parcalar:
            if sch_wire._on_segment(point, a, b):   # strict: uclar haric
                ekle(point, 2)
                break

    mevcut = {(round(j.x, 4), round(j.y, 4)) for j in schematic.junctions
              if getattr(j, "sheet_path", "/") == sheet_path}
    return sorted(p for p, n in sayim.items() if n >= 3 and p not in mevcut)


def _net_check(schematic: Schematic, pins: list[tuple[str, str]]) -> NetCheck:
    """Gercek pinleri ayirir, guc sembolu varsa beklenen ag adini bulur."""
    gercek = [(ref, number) for ref, number in pins if not ref.startswith("#")]
    ad = None
    for ref, _ in pins:
        sym = schematic.by_ref(ref)
        if sym is not None and sym.is_power:
            ad = sym.value or sym.properties.get("Value")
            break
    return NetCheck(pins=gercek, power_name=ad,
                    label=" - ".join(f"{r}.{n}" for r, n in pins))


def plan_nets(schematic: Schematic, nets: list[list[tuple[str, str]]],
              sheet_path: str = "/") -> ConnectPlan:
    """Beyan edilmis aglari yollara cevirir."""
    plan = ConnectPlan(sheet_path=sheet_path)
    for pins in nets:
        points = [pin_point(schematic, ref, number, sheet_path) for ref, number in pins]
        adlar = [f"{ref}.{number}" for ref, number in pins]
        if len(set(points)) != len(points):
            plan.problems.append(f"{' - '.join(adlar)}: ayni noktada iki pin var")
            continue
        zincir = _order_chain(points)
        temiz = True
        for a, b in zip(zincir, zincir[1:]):
            path = sch_wire.route(a, b, schematic, sheet_path)
            if path is None:
                plan.problems.append(
                    f"{' - '.join(adlar)}: ({a[0]:g},{a[1]:g}) -> ({b[0]:g},{b[1]:g}) "
                    "arasinda temiz bir yol yok (arada baska pin ya da tel ucu var)"
                )
                temiz = False
                break
            plan.paths.append(path)
        if temiz:
            plan.nets.append(_net_check(schematic, list(pins)))
    plan.junctions = junctions_for(plan.paths, schematic, sheet_path)
    return plan


def plan_from_proposals(schematic: Schematic, suggestion: propose.Suggestion,
                        sheet_path: str = "/") -> ConnectPlan:
    """Onerileri yollara cevirir. Oneriler zaten dik ve temiz yollardir.

    Guc inisi TEK pinli bir oneridir ama kendi basina bir ag degildir: indigi
    rayin agina KATILIR. Hakem de onu orada aramali, yoksa "1 pinli ag"
    dogrulanamaz ve guc baglantisi hic sinanmamis olur.
    """
    plan = ConnectPlan(sheet_path=sheet_path)
    hizali = [p for p in suggestion.proposals if p.kind != "guc-inisi"]
    inisler = [p for p in suggestion.proposals if p.kind == "guc-inisi"]

    gruplar: list[list[propose.PinRef]] = []
    for proposal in hizali:
        plan.paths.append(proposal.path)
        plan.notes.append(str(proposal))
        gruplar.append(list(proposal.pins))

    for drop in inisler:
        plan.paths.append(drop.path)
        plan.notes.append(str(drop))
        inis = drop.path[-1]
        for grup, proposal in zip(gruplar, hizali):
            if any(sch_wire._on_segment(inis, a, b, strict=False)
                   for a, b in sch_wire._segments(proposal.path)):
                grup.extend(drop.pins)
                break
        else:  # hicbir raya oturmadiysa oneri uretilmemeliydi
            plan.problems.append(f"{drop.pins[0]}: inis noktasi hicbir tele oturmuyor")

    for grup in gruplar:
        if len(grup) >= 2:
            plan.nets.append(_net_check(schematic, [(p.ref, p.number) for p in grup]))
    plan.notes.extend(f"onerilmedi: {s}" for s in suggestion.skipped)
    plan.junctions = junctions_for(plan.paths, schematic, sheet_path)
    return plan


# --------------------------------------------------------------------------
# Yazma
# --------------------------------------------------------------------------


def build_nodes(plan: ConnectPlan) -> list[list]:
    nodes: list[list] = []
    for path in plan.paths:
        nodes.extend(sch_wire.wire_nodes(path))
    for x, y in plan.junctions:
        nodes.append(sch_wire.junction_node(x, y))
    return nodes


def edit_tree(root, plan: ConnectPlan) -> int:
    """Dugumleri agaca ekler. Doner: eklenen dugum sayisi.

    Teller `lib_symbols`dan hemen sonra girer - KiCad kendi yazarken de bu
    sirayi kullaniyor, ve dosyayi acip kapatinca fark dogmasin istiyoruz.
    """
    nodes = build_nodes(plan)
    if not nodes:
        return 0
    nerede = next((i for i, n in enumerate(root)
                   if isinstance(n, list) and head(n) == "lib_symbols"), None)
    if nerede is None:
        raise ConnectError("sematikte lib_symbols yok - dosya beklendigi gibi degil")
    root[nerede + 1:nerede + 1] = nodes
    return len(nodes)


def apply_to_file(path: Path, plan: ConnectPlan, *, apply: bool = False,
                  backup: bool = True, allow_open_project: bool = False):
    root = parse(Path(path).read_text(encoding="utf-8"))
    edit_tree(root, plan)
    return write_tree(Path(path), root, apply=apply, backup=backup,
                      allow_open_project=allow_open_project)


# --------------------------------------------------------------------------
# Hakem
# --------------------------------------------------------------------------


def verify(path: Path, plan: ConnectPlan, kicad_cli: str | None = None) -> list[str]:
    """Istenen pinler GERCEKTEN ayni aga girmis mi. Doner: sikayetler.

    Kendi geometrimize degil KiCad'in cikarimina bakiyoruz - ayrisirsak
    haksiz olan biziz. `sch_verify` zaten netlist'i kanonik bir ag bolunmesine
    ceviriyor; ikinci bir okuyucu yazmak iki gercek uretirdi.
    """
    from .sch_verify import connectivity_of

    baglanti = connectivity_of(Path(path), kicad_cli)
    sikayet: list[str] = []
    for check in plan.nets:
        hedef = set(check.pins)
        if len(hedef) < 2:
            sikayet.append(f"{check.label}: netlist'te gorunen iki gercek pin yok, "
                           "hakem bu agi dogrulayamiyor")
            continue
        if not any(hedef <= net for net in baglanti.partition):
            nerede = [sorted(f"{r}.{n}" for r, n in (net & hedef))
                      for net in baglanti.partition if net & hedef]
            sikayet.append(f"{check.label} ayni aga girmedi; "
                           f"netlist onlari {nerede or 'hicbir agda'} diye bolmus")
            continue
        # Guc sembolu netlist'te dugum olarak YOK; baglandigini agin ADINDAN
        # anliyoruz - KiCad agi guc sembolunun degeriyle adlandirir.
        if check.power_name:
            gercek_ad = baglanti.net_of.get(next(iter(hedef)), "")
            if check.power_name not in gercek_ad:
                sikayet.append(
                    f"{check.label}: guc baglanmamis gorunuyor - ag adi "
                    f"{gercek_ad!r}, beklenen {check.power_name!r}"
                )
    return sikayet


# --------------------------------------------------------------------------
# Komut satiri
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pcbqa.connect",
        description="Var olan sembolleri telle birlestir (beyanla ya da oneriyle).",
    )
    ap.add_argument("sch", help="sematik dosyasi ya da proje klasoru")
    ap.add_argument("--ag", action="append", default=[], metavar="PINLER",
                    help='ayni aga girecek pinler, or: "R1.1 C1.1 #PWR01.1"')
    ap.add_argument("--oner", action="store_true",
                    help="sayfaya bakip baglanti oner (gerekcesiyle)")
    ap.add_argument("--sayfa", default="/", help="sayfa yolu (varsayilan /)")
    ap.add_argument("--uygula", action="store_true",
                    help="dosyaya yaz (varsayilan kuru calisma)")
    ap.add_argument("--no-verify", action="store_true",
                    help="netlist hakemini atla (ONERILMEZ)")
    ap.add_argument("--no-backup", action="store_true", help="yedek alma")
    ap.add_argument("--kicad-acikken", dest="acikken", action="store_true",
                    help="proje KiCad'de acikken de yaz")
    ap.add_argument("--kicad-cli", default=None)
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    if not args.ag and not args.oner:
        print("hata: ya --ag verin ya da --oner kullanin", file=sys.stderr)
        return 2

    try:
        schematic = read_schematic(args.sch)
        path = schematic.file_of_sheet.get(args.sayfa, schematic.root_path)

        if args.oner:
            suggestion = propose.suggest(schematic, args.sayfa)
            plan = plan_from_proposals(schematic, suggestion, args.sayfa)
        else:
            nets = [parse_net(text) for text in args.ag]
            plan = plan_nets(schematic, nets, args.sayfa)
    except (ConnectError, FileNotFoundError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2

    print(f"  {path.name}  (sayfa {args.sayfa})")
    for note in plan.notes:
        print(f"    {note}")
    for path_points in plan.paths:
        print("    tel: " + " -> ".join(f"({x:g},{y:g})" for x, y in path_points))
    if plan.junctions:
        print("    junction: " + ", ".join(f"({x:g},{y:g})" for x, y in plan.junctions))
    for problem in plan.problems:
        print(f"    ENGEL: {problem}")

    if not plan.paths:
        print("\n  cizilecek bir sey yok")
        return 1 if plan.problems else 0

    try:
        result = apply_to_file(path, plan, apply=args.uygula,
                               backup=not args.no_backup,
                               allow_open_project=args.acikken)
    except (ConnectError, SchWriteError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2

    print()
    print(f"  {plan.wire_count} tel, {len(plan.junctions)} junction"
          f"  ->  {'YAZILDI' if result.written else 'kuru calisma (yazmak icin --uygula)'}")
    for note in result.notes:
        print(f"    {note}")

    if result.written and not args.no_verify:
        sikayet = verify(path, plan, args.kicad_cli)
        if sikayet:
            print("\n  HAKEM REDDETTI:")
            for s in sikayet:
                print(f"    {s}")
            if result.backup:
                print(f"    geri almak icin: {result.backup}")
            return 3
        print(f"  hakem: {len(plan.nets)} ag dogrulandi (kicad-cli netlist)")
    return 2 if plan.problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
