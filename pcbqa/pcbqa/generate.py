"""Insa plani -> gercek KiCad projesi (Evre 3a surucusu).

`intent.py` niyeti bir plana ceviriyordu ama plan bir VERI YAPISIydi. Bu
modul zinciri kapatir: plandan sifirdan bir KiCad projesi uretir, karta
yansitir, yerlestirir ve SKORLAR. Yani "sistem kendi kartini tasarlasin"
cumlesinin ilk deterministik (ML'siz) hali.

    niyet.yaml --intent--> plan --generate--> .kicad_sch
                                          --pcb_sync--> .kicad_pcb
                                          --auto------> yerlesim
                                          --run_rules--> skor

## Neden `sch_add` dongusu degil, tek gecis

`sch_add.add_symbols` her cagrida netlist kalkanini iki kez kosturur
(~4 sn x 2). 18 bilesenlik bir plan icin bu iki dakikadan fazla eder ve
kalkanin sordugu soru burada zaten yanlis: kalkan "MEVCUT devre bozulmasin"
der, oysa burada mevcut devre YOKTUR. Bu yuzden semboller tek geciste
kurulur (`sch_add`in dugum ureticileri aynen kullanilir) ve sonunda BIR KEZ
daha guclu bir soru sorulur:

    KiCad'in kendi netlist'i, PLANIN kurmak istedigi aglarin AYNISINI mi
    okuyor?

Bu kalkandan gecmek "her planlanan ag, tam olarak planlanan pinlerle,
KiCad'in gozunde de var" demektir. Eksik pin (etiket tutmamis) ve fazla pin
(sessiz kisa devre) ayri ayri raporlanir.

## Baglanti neden hep ETIKETLE

Plan pin -> ag adi dilinde konusuyor; etiket de tam olarak bunu ifade eder
ve mesafeden bagimsizdir (bkz. `sch_wire` modul basligi). Tel cizmek
sayfa yerlesimine bagimlilik yaratir ve uretilen bir sematikte hicbir sey
kazandirmaz.

## Kilitli bilesen YOK (bilincli sapma)

`harness.locked_refs` konnektorleri (J*, P*...) kilitli sayar - gercek bir
kartta konnektor mekanik olarak sabittir. URETILEN kartta boyle bir kisit
henuz yoktur: konnektorun nerede olacagina da bu zincir karar verir. Kilitli
saysaydik `pcb_sync`in dizdigi ARA konumda (kartin sagi, sinirin disi)
donup kalirlardi.

Ana giris: `generate(plan, out_dir)`, CLI: `python -m pcbqa.generate`.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import uuid as uuidlib
from dataclasses import dataclass, field
from pathlib import Path

from . import pcb_sync, sch_add, sch_wire, symlib
from .harness import apply_placement, evaluate_design, load_design, make_evaluator, write_board
from .intent import BuildPlan, IntentError, plan_from_file
from .placement.auto import Auto
from .placement.base import PlacementContext
from .pcb import read_board
from .rules import load_rules
from .sch_add import PAPER_SIZES, NewSymbol
from .sch_verify import Connectivity, SchVerifyError, connectivity_of
from .sch_write import write_tree
from .schematic import GRID_MM, read_schematic
from .sexpr import parse_with_stats, value
# Kart iskeletinin katman tablosu sentetik kart ureticisiyle AYNIDIR; iki
# kopya tutmak kacinilmaz olarak birbirinden ayrisirdi.
from .synth import KICAD_VERSION as PCB_FILE_VERSION, LAYER_TABLE

# Sematik dosya surumu (KiCad 10 demolarindan)
SCH_FILE_VERSION = "20260101"

# Sayfa kenarindan birakilan bosluk ve semboller arasi aciklik.
# Aciklik cizim degil BAGLANTI meselesi: iki sembolun pinleri ayni noktaya
# duserse KiCad onlari birlestirir. Etiket metnine de yer birakir.
SHEET_MARGIN_MM = 12.7
SHEET_GAP_MM = 7.62

# Buyukten kucuge denenecek kagitlar
PAPER_ORDER = ("A4", "A3", "A2", "A1", "A0")

# Kart boyutu secimi: bilesen alanlarinin toplami / kart alani.
# Gercek kartlarda %20-40 arasi; %25 yerlestiriciye rahat calisma alani
# birakir (muhendislik secimi - kaynak degil, olcum de degil).
TARGET_DENSITY = 0.25
BOARD_ASPECT = 1.4  # genislik / yukseklik
MIN_BOARD_MM = (30.0, 20.0)

# Yerlestiriciye verilen varsayilan sure
DEFAULT_TIME_BUDGET_S = 20.0

# Paketle gelen, devre tipinden bagimsiz kural seti
DEFAULT_RULES = Path(__file__).parent / "presets" / "uretim.rules.yaml"


class GenerateError(RuntimeError):
    """Proje uretilemedi."""


@dataclass
class GenerateResult:
    """Uretimin sonucu - her adim ayri ayri gorunur."""

    name: str
    folder: Path
    sch: Path
    pcb: Path
    refs: dict[str, str] = field(default_factory=dict)  # plan etiketi -> referans
    paper: str = "A4"
    board_size: tuple[float, float] = (0.0, 0.0)
    verified_nets: int = 0
    synced: int = 0
    moved: int = 0
    score_before: float | None = None
    score_after: float | None = None
    errors_after: int = 0
    warnings_after: int = 0
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def describe(self) -> str:
        lines = [f"uretildi: {self.name} -> {self.folder}"]
        lines.append(f"  sematik : {self.sch.name} ({len(self.refs)} bilesen, "
                     f"kagit {self.paper})")
        lines.append(f"  kalkan  : {self.verified_nets} planlanan agin tamami "
                     "KiCad netlist'inde birebir dogrulandi"
                     if self.verified_nets else "  kalkan  : calistirilmadi")
        lines.append(f"  kart    : {self.pcb.name} "
                     f"({self.board_size[0]:g} x {self.board_size[1]:g} mm, "
                     f"{self.synced} bilesen yansitildi)")
        if self.score_before is not None:
            gain = (self.score_after or 0.0) - self.score_before
            lines.append(f"  skor    : {self.score_before:.1f} -> "
                         f"{self.score_after:.1f} ({gain:+.1f}), "
                         f"{self.moved} bilesen tasindi, "
                         f"{self.errors_after} hata / {self.warnings_after} uyari")
        for note in self.notes:
            lines.append(f"  not: {note}")
        for problem in self.problems:
            lines.append(f"  ENGEL: {problem}")
        return "\n".join(lines)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "folder": str(self.folder),
            "sch": str(self.sch),
            "pcb": str(self.pcb),
            "paper": self.paper,
            "board_size_mm": list(self.board_size),
            "components": len(self.refs),
            "refs": dict(self.refs),
            "verified_nets": self.verified_nets,
            "synced": self.synced,
            "moved": self.moved,
            "score_before": self.score_before,
            "score_after": self.score_after,
            "errors_after": self.errors_after,
            "warnings_after": self.warnings_after,
            "notes": list(self.notes),
            "problems": list(self.problems),
        }


# --------------------------------------------------------------------------
# Proje iskeleti
# --------------------------------------------------------------------------


def _q(text: str) -> str:
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def empty_schematic_text(uuid: str, paper: str = "A4", title: str = "") -> str:
    """Bos ama GECERLI bir .kicad_sch.

    `kicad-cli sch export netlist` bu dosyayi .kicad_pro olmadan da okuyor
    (denendi); yani proje dosyasi yalnizca KiCad'in GUI'si icin gerekli.

    `sheet_instances` bos dosyada gereksiz gorunur ama SART: olmadan dosya
    bos haliyle okunuyor, icine sembol konunca `kicad-cli` hicbir mesaj
    vermeden 3 koduyla cikiyor (olculdu). Sembollerin `instances` bloklari
    sayfa yolunu isaret ediyor; o yolun sayfa tarafindaki karsiligi burasi.
    """
    block = ""
    if title:
        block = f"\t(title_block\n\t\t(title {_q(title)})\n\t)\n"
    return (
        "(kicad_sch\n"
        f"\t(version {SCH_FILE_VERSION})\n"
        '\t(generator "pcbqa")\n'
        '\t(generator_version "10.0")\n'
        f"\t(uuid {_q(uuid)})\n"
        f"\t(paper {_q(paper)})\n"
        f"{block}"
        "\t(lib_symbols)\n"
        '\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)\n'
        "\t(embedded_fonts no)\n"
        ")\n"
    )


def empty_board_text(paper: str = "A4") -> str:
    """Bos bir .kicad_pcb: katman tablosu var, Edge.Cuts YOK.

    Sinir bilerek sonra cizilir: dogru boyut ancak bilesenler karta
    yansitilip courtyard alanlari OLCULDUKTEN sonra bilinir (bkz.
    `fit_outline`). Bos sinirla baslamak `pcb_sync`i de kolaylastirir -
    yeni bilesenleri bir kenara dizerken sinirin disina cikmis olmaz.
    """
    return (
        "(kicad_pcb\n"
        f"\t(version {PCB_FILE_VERSION})\n"
        '\t(generator "pcbqa")\n'
        '\t(generator_version "10.0")\n'
        "\t(general\n\t\t(thickness 1.6)\n\t\t(legacy_teardrops no)\n\t)\n"
        f"\t(paper {_q(paper)})\n"
        f"{LAYER_TABLE}\n"
        "\t(setup\n\t\t(pad_to_mask_clearance 0)\n\t)\n"
        "\t(embedded_fonts no)\n"
        ")\n"
    )


def project_json(name: str) -> str:
    """En kucuk gecerli .kicad_pro.

    KiCad eksik alanlari kendi varsayilanlariyla tamamliyor; buradaki amac
    projenin GUI'de tek tikla acilabilmesi, tam bir ayar dosyasi uretmek
    degil.
    """
    return json.dumps(
        {
            "board": {"design_settings": {}},
            "meta": {"filename": f"{name}.kicad_pro", "version": 3},
            "schematic": {},
            "sheets": [],
            "text_variables": {},
        },
        indent=2,
    ) + "\n"


def create_skeleton(folder: Path, name: str, paper: str, title: str = "") -> tuple[Path, Path, Path]:
    """Bos proje uclusunu yazar: (.kicad_pro, .kicad_sch, .kicad_pcb)."""
    folder.mkdir(parents=True, exist_ok=True)
    pro = folder / f"{name}.kicad_pro"
    sch = folder / f"{name}.kicad_sch"
    pcb = folder / f"{name}.kicad_pcb"
    for path in (pro, sch, pcb):
        if path.exists():
            raise GenerateError(
                f"{path.name} zaten var - uretim var olan bir projeye yazmaz "
                "(baska bir --out ya da --name secin)"
            )
    pro.write_text(project_json(name), encoding="utf-8")
    sch.write_text(empty_schematic_text(str(uuidlib.uuid4()), paper, title), encoding="utf-8")
    pcb.write_text(empty_board_text(paper), encoding="utf-8")
    return pro, sch, pcb


# --------------------------------------------------------------------------
# Sayfa yerlesimi
# --------------------------------------------------------------------------


def _snap(value: float) -> float:
    return round(round(value / GRID_MM) * GRID_MM, 4)


def pack_rows(
    sizes: list[tuple[float, float]],
    paper: str,
) -> tuple[list[tuple[float, float]], float]:
    """Sembolleri satir satir dizer: (merkezler, kullanilan yukseklik).

    Satir yuksekligi o satirin EN YUKSEK sembolune gore belirlenir; boylece
    LQFP-48 gibi 81 mm'lik bir sembol yanindaki 0603 kondansatorleri
    ezmez.
    """
    width, height = PAPER_SIZES.get(paper, PAPER_SIZES["A4"])
    usable = width - 2 * SHEET_MARGIN_MM

    centers: list[tuple[float, float]] = []
    x = SHEET_MARGIN_MM
    y = SHEET_MARGIN_MM
    row_height = 0.0
    for w, h in sizes:
        if centers and x + w > SHEET_MARGIN_MM + usable:
            x = SHEET_MARGIN_MM
            y += row_height + SHEET_GAP_MM
            row_height = 0.0
        centers.append((_snap(x + w / 2), _snap(y + h / 2)))
        x += w + SHEET_GAP_MM
        row_height = max(row_height, h)
    used = y + row_height + SHEET_MARGIN_MM
    return centers, used


def choose_paper(sizes: list[tuple[float, float]]) -> tuple[str, list[tuple[float, float]], str]:
    """Isin sigdigi en kucuk standart kagit; (kagit, merkezler, not)."""
    for paper in PAPER_ORDER:
        width, height = PAPER_SIZES[paper]
        if any(w + 2 * SHEET_MARGIN_MM > width for w, _ in sizes):
            continue  # tek bir sembol bile yatay sigmiyorsa buyut
        centers, used = pack_rows(sizes, paper)
        if used <= height:
            return paper, centers, ""
    paper = PAPER_ORDER[-1]
    centers, used = pack_rows(sizes, paper)
    return paper, centers, (
        f"semboller {paper} sayfasina sigmadi ({used:.0f} mm gerekti); "
        "kagidin altina tasti"
    )


# --------------------------------------------------------------------------
# Sematik uretimi
# --------------------------------------------------------------------------


def allocate_refs(
    plan: BuildPlan,
    symbols: dict[str, symlib.LibSymbol],
) -> dict[str, str]:
    """Plan etiketi -> referans (C1, C2, R1, U1...).

    Numaralandirma plan sirasini izler: ayni niyet her zaman ayni referanslari
    uretir. `sch_add.next_references` burada kullanilamaz - o MEVCUT bir
    sematige gore numaralandirir, burada sematik henuz bostur.
    """
    counters: dict[str, int] = {}
    out: dict[str, str] = {}
    for comp in plan.components:
        symbol = symbols[comp.lib_id]
        prefix = comp.ref_prefix or symbol.reference_prefix
        counters[prefix] = counters.get(prefix, 0) + 1
        out[comp.label] = f"{prefix}{counters[prefix]}"
    return out


def build_schematic_tree(
    plan: BuildPlan,
    sch_path: Path,
    symbols: dict[str, symlib.LibSymbol],
    refs: dict[str, str],
    centers: list[tuple[float, float]],
    no_connect_unused: bool = False,
) -> tuple[list, list[str], list[str]]:
    """Bos sematigi doldurur: (agac, engeller, notlar).

    Dosyaya YAZMAZ. Semboller `sch_add`in dugum ureticileriyle kurulur;
    baglantilar pinin tam ustune konan yerel etiketlerle yapilir.
    """
    schematic = read_schematic(sch_path)
    root, stray = parse_with_stats(sch_path.read_text(encoding="utf-8"))
    if stray:
        raise GenerateError(f"{sch_path.name} bozuk uretildi ({stray} kacak parantez)")

    problems: list[str] = []
    notes: list[str] = []
    # Ayni noktaya dusen pinler. KiCad onlari SESSIZCE birlestirir, yani
    # dogru degismez "cakisma olmasin" degil, "cakisanlar AYNI AGDA olsun":
    #
    #   * Ayni sembolun ustuste yigilmis guc pinleri KiCad'in kendi
    #     gelenegidir - STM32F103C8Tx'in uc VSS pini (23/35/47) tek
    #     noktada durur, cizimde biri gorunur. Ayni aga gittikleri surece
    #     dogru olan da budur.
    #   * Farkli aglardaki iki pin ayni noktaya duserse bu sessiz kisa
    #     devredir; sayfa yerlesimi ya da plan hatalidir.
    #
    # Yigili pinlere etiket BIR KEZ konur: uc ayni etiket ayni noktada
    # dosyayi sisirir ve KiCad'in kendisi de oyle yazmaz.
    at_point: dict[tuple[float, float], tuple[str, str]] = {}

    for comp, (cx, cy) in zip(plan.components, centers):
        symbol = symbols[comp.lib_id]
        ref = refs[comp.label]
        if symbol.unit_count > 1:
            problems.append(
                f"{ref} ({comp.lib_id}): cok birimli semboller henuz "
                "uretilemiyor (birimlerin sayfaya dagitilmasi ayri bir karar)"
            )
            continue

        new = NewSymbol(ref=ref, x=cx, y=cy, rotation=0.0, unit=1)
        sch_add.merge_lib_symbol(root, symbol)
        root.append(sch_add.build_symbol_node(
            root, schematic, symbol, new, comp.value, comp.footprint
        ))

        points = sch_add.new_pin_points(symbol, new)
        net_of_pin = dict(comp.pin_connect)
        for number, net in comp.pin_connect:
            if number not in points:
                problems.append(f"{ref}: {number!r} pini sembolde yok")

        # Bagli pinler ONCE islenir: yigili bir noktada once baglanmamis pini
        # gorseydik oraya no-connect koyar, etiketi hic yazmazdik.
        for number, point in sorted(points.items(),
                                    key=lambda kv: (kv[0] not in net_of_pin, kv[0])):
            net = net_of_pin.get(number, "")
            previous = at_point.get(point)
            if previous is not None:
                other, other_net = previous
                if net and other_net and net != other_net:
                    problems.append(
                        f"{ref}.{number} ({net}) ile {other} ({other_net}) ayni "
                        f"noktada ({point[0]:g}, {point[1]:g}) - sessiz kisa devre"
                    )
                elif not other.startswith(f"{ref}."):
                    problems.append(
                        f"{ref}.{number} pini {other} ile ayni noktada "
                        f"({point[0]:g}, {point[1]:g}) - sayfa yerlesimi cakisti"
                    )
                continue
            at_point[point] = (f"{ref}.{number}", net)
            if net:
                rotation = sch_wire.label_rotation(sch_add.pin_rotation(symbol, new, number))
                root.append(sch_wire.label_node(point[0], point[1], net, rotation))
            elif no_connect_unused:
                root.append(["no_connect",
                             ["at", f"{point[0]:g}", f"{point[1]:g}"],
                             ["uuid", f'"{uuidlib.uuid4()}"']])

    unused = sum(
        len([p for p in symbols[c.lib_id].pins if p.unit in (0, 1)]) - len(c.pin_connect)
        for c in plan.components
        if symbols[c.lib_id].unit_count == 1
    )
    if unused and not no_connect_unused:
        notes.append(
            f"{unused} pin bagli degil (cogu kullanilmayan GPIO); KiCad ERC'si "
            "bunlari 'unconnected pin' diye bildirir - susturmak icin "
            "--no-connect-unused"
        )
    return root, problems, notes


# --------------------------------------------------------------------------
# Kalkan: KiCad planin kurdugu aglari mi okuyor?
# --------------------------------------------------------------------------


def expected_nets(plan: BuildPlan, refs: dict[str, str]) -> dict[str, frozenset[tuple[str, str]]]:
    """Planin kurmak istedigi aglar: ag adi -> {(referans, pin numarasi)}."""
    out: dict[str, set[tuple[str, str]]] = {}
    for comp in plan.components:
        for number, net in comp.pin_connect:
            out.setdefault(net, set()).add((refs[comp.label], number))
    return {name: frozenset(pins) for name, pins in out.items()}


def verify_against_plan(
    conn: Connectivity,
    expected: dict[str, frozenset[tuple[str, str]]],
    refs: dict[str, str],
) -> tuple[int, list[str]]:
    """KiCad'in netlist'i plani birebir kuruyor mu? (dogrulanan ag, engeller).

    Ug ayri sessiz hata sinifi ayri ayri aranir:

      * eksik pin - etiket tutmamis, pin agin disinda kalmis;
      * bolunmus ag - ayni ad iki ayri aga dagilmis (KiCad'in gozunde);
      * fazla pin - planda olmayan bir pin aga girmis (sessiz kisa devre).

    Ag ADI karsilastirilmaz, PINLERIN BOLUNUSU karsilastirilir - `sch_verify`
    modulunun kararinin aynisi: adlar yeniden uretilebilir, bolunme devrenin
    kendisidir.
    """
    problems: list[str] = []
    missing_components = sorted(set(refs.values()) - set(conn.components))
    if missing_components:
        problems.append(
            "netlist'te olmayan bilesen(ler): " + ", ".join(missing_components[:8])
        )

    group_of = {pin: net for net in conn.partition for pin in net}
    verified = 0
    for name, pins in sorted(expected.items()):
        groups = {group_of.get(pin) for pin in pins}
        absent = sorted(pin for pin in pins if group_of.get(pin) is None)
        if absent:
            problems.append(
                f"{name}: netlist'te bulunamayan pin(ler): "
                + ", ".join(f"{r}.{p}" for r, p in absent[:6])
            )
            continue
        if len(groups) > 1:
            problems.append(
                f"{name}: plan tek ag istedi ama netlist {len(groups)} ayri aga "
                "boldu (etiketlerden biri tutmamis)"
            )
            continue
        actual = groups.pop()
        extra = sorted(actual - pins)
        if extra:
            problems.append(
                f"{name}: planda olmayan pin(ler) bu aga girmis: "
                + ", ".join(f"{r}.{p}" for r, p in extra[:6])
            )
            continue
        verified += 1
    return verified, problems


# --------------------------------------------------------------------------
# Kart siniri
# --------------------------------------------------------------------------


def fit_outline(pcb_path: Path, density: float = TARGET_DENSITY) -> tuple[float, float]:
    """Karta yansitilmis bilesenlerin OLCULEN alanindan makul bir sinir.

    Tahmin degil olcum: `pcb_sync` footprint'leri gercek courtyard'lariyla
    karta koydu, `read_board` onlari geri okuyor. `density` bilesen alaninin
    kart alanina orani - kucultmek daha kucuk (ve ucuz) kart demektir, ama
    bir yerden sonra yerlestirici sigdiramaz (bkz. `explore`).
    """
    board = read_board(pcb_path)
    total = sum(c.area_mm2 for c in board.components)
    if total <= 0:
        return MIN_BOARD_MM
    area = total / max(density, 0.01)
    height = math.sqrt(area / BOARD_ASPECT)
    width = area / height
    # 5 mm'nin katina yuvarla - gercek kartlar da yuvarlak olculerde kesilir
    width = max(MIN_BOARD_MM[0], math.ceil(width / 5.0) * 5.0)
    height = max(MIN_BOARD_MM[1], math.ceil(height / 5.0) * 5.0)
    return width, height


def draw_outline(pcb_path: Path, width: float, height: float) -> None:
    """Karta Edge.Cuts dikdortgeni cizer (sol ust kose 0,0).

    Var olan Edge.Cuts dikdortgenleri SILINIR: cagri yinelenebilir olmali
    (varyant arama ayni karta farkli boyutlar dener) ve iki sinir cizgisi
    birakmak kartin sinirini belirsiz kilardi.
    """
    root, stray = parse_with_stats(pcb_path.read_text(encoding="utf-8"))
    if stray:
        raise GenerateError(f"{pcb_path.name} bozuk gorunuyor ({stray} kacak parantez)")
    root[:] = [
        n for n in root
        if not (isinstance(n, list) and n and str(n[0]) == "gr_rect"
                and value(n, "layer") == "Edge.Cuts")
    ]
    root.append([
        "gr_rect",
        ["start", "0", "0"],
        ["end", f"{width:g}", f"{height:g}"],
        ["stroke", ["width", "0.1"], ["type", "solid"]],
        ["fill", "no"],
        ["layer", '"Edge.Cuts"'],
        ["uuid", f'"{uuidlib.uuid4()}"'],
    ])
    write_tree(pcb_path, root, apply=True, backup=False)


# --------------------------------------------------------------------------
# Ana akis
# --------------------------------------------------------------------------


def generate(
    plan: BuildPlan,
    out_dir: Path,
    name: str | None = None,
    *,
    rules_path: Path | None = None,
    place: bool = True,
    time_budget_s: float = DEFAULT_TIME_BUDGET_S,
    seed: int = 0,
    no_connect_unused: bool = False,
    verify: bool = True,
    kicad_cli: str | None = None,
) -> GenerateResult:
    """Cozumlenmis bir plandan calisir bir KiCad projesi uretir.

    Her adim bir sonrakinin ON KOSULUdur: kalkan reddederse karta gecilmez,
    kart yansitilmadiysa yerlestirme yapilmaz. Yarim bir proje birakmaktansa
    nerede durdugunu soylemek yeglenir.
    """
    if not plan.resolved:
        raise GenerateError(
            "plan cozumlenmemis - once intent.resolve_plan calistirilmali "
            "(pin numaralari olmadan sematik uretilemez)"
        )
    if not plan.ok:
        raise GenerateError(
            "planda engel var, uretim baslamadi: " + "; ".join(plan.problems[:3])
        )

    name = name or plan.name
    folder = Path(out_dir)

    symbols: dict[str, symlib.LibSymbol] = {}
    for comp in plan.components:
        if comp.lib_id not in symbols:
            try:
                symbols[comp.lib_id] = symlib.get_symbol(comp.lib_id, kicad_cli=kicad_cli)
            except symlib.SymLibError as exc:
                raise GenerateError(f"{comp.label}: {exc}") from exc

    sizes = [
        sch_add.symbol_size(symbols[c.lib_id], 1)
        for c in plan.components
    ]
    paper, centers, paper_note = choose_paper(sizes)

    pro, sch, pcb = create_skeleton(folder, name, paper, title=plan.name)
    result = GenerateResult(name=name, folder=folder, sch=sch, pcb=pcb, paper=paper)
    if paper_note:
        result.notes.append(paper_note)

    # 1) Sematik
    refs = allocate_refs(plan, symbols)
    result.refs = refs
    root, problems, notes = build_schematic_tree(
        plan, sch, symbols, refs, centers, no_connect_unused=no_connect_unused
    )
    result.problems += problems
    result.notes += notes
    if result.problems:
        return result
    write_tree(sch, root, apply=True, backup=False)

    # 2) Kalkan: KiCad netlist'i plani birebir kuruyor mu?
    if verify:
        try:
            conn = connectivity_of(sch, kicad_cli)
        except SchVerifyError as exc:
            result.problems.append(f"kalkan calistirilamadi: {exc}")
            return result
        verified, problems = verify_against_plan(conn, expected_nets(plan, refs), refs)
        result.verified_nets = verified
        result.problems += problems
        if result.problems:
            return result

    # 3) Karta yansitma
    try:
        sync_result = pcb_sync.sync(sch, pcb, apply=True, backup=False, kicad_cli=kicad_cli)
    except (pcb_sync.PcbSyncError, symlib.SymLibError) as exc:
        result.problems.append(f"karta yansitma basarisiz: {exc}")
        return result
    result.problems += sync_result.plan.problems
    result.synced = len(sync_result.verified)
    if result.problems:
        return result
    if result.synced != len(refs):
        result.problems.append(
            f"karta {result.synced}/{len(refs)} bilesen gitti - eksik olanlar "
            "sessizce atlanmis olurdu"
        )
        return result

    # 4) Kart siniri (olculen courtyard alanindan)
    width, height = fit_outline(pcb)
    draw_outline(pcb, width, height)
    result.board_size = (width, height)

    # 5) Yerlestirme ve skor
    if not place:
        return result

    rules = load_rules(rules_path or DEFAULT_RULES)
    design = load_design(pcb)
    before = evaluate_design(design, rules)
    result.score_before = before.score

    # Uretilen kartta mekanik kisit YOK - bkz. modul basligi.
    ctx = PlacementContext(
        design=design,
        locked=set(),
        seed=seed,
        time_budget_s=time_budget_s,
        evaluator=make_evaluator(design, rules),
    )
    placement = Auto().run(ctx)
    placed_design = apply_placement(design, placement)
    after = evaluate_design(placed_design, rules)

    # `auto` gerileme yapamaz (mevcut hal de aday) ama olcumu yine de
    # kaydediyoruz: sessiz bir gerileme fark edilmeden gecmesin.
    if after.score + 1e-9 < before.score:
        result.problems.append(
            f"yerlestirme skoru dusurdu ({before.score:.1f} -> {after.score:.1f}); "
            "karta yazilmadi"
        )
        return result

    write_board(pcb, placement, pcb)
    result.moved = sum(
        1
        for c in design.board.components
        if c.ref in placement
        and (abs(c.x - placement[c.ref][0]) > 1e-6 or abs(c.y - placement[c.ref][1]) > 1e-6)
    )
    result.score_after = after.score
    result.errors_after = after.errors
    result.warnings_after = after.warnings
    return result


def generate_from_intent(
    intent_path: Path,
    out_dir: Path,
    name: str | None = None,
    *,
    templates_dir: Path | None = None,
    **kwargs,
) -> GenerateResult:
    """Niyet dosyasindan tek adimda proje."""
    plan = plan_from_file(intent_path, templates_dir=templates_dir, resolve=True)
    return generate(plan, out_dir, name, **kwargs)


# --------------------------------------------------------------------------
# Komut satiri
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pcbqa.generate",
        description="Niyet beyanindan calisir bir KiCad projesi uretir "
                    "(sematik + kart + yerlesim + skor).",
    )
    ap.add_argument("--intent", type=Path, required=True, help="Niyet dosyasi (YAML)")
    ap.add_argument("--out", type=Path, required=True, help="Projenin yazilacagi klasor")
    ap.add_argument("--name", default=None, help="Proje adi (varsayilan: niyetin adi)")
    ap.add_argument("--templates", type=Path, default=None, help="Sablon klasoru")
    ap.add_argument("--rules", type=Path, default=None,
                    help=f"Kural dosyasi (varsayilan: {DEFAULT_RULES.name})")
    ap.add_argument("--no-place", action="store_true", help="Yerlestirme ve skoru atla")
    ap.add_argument("--budget", type=float, default=DEFAULT_TIME_BUDGET_S,
                    help="Yerlestirici sure butcesi (saniye)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-connect-unused", action="store_true",
                    help="Baglanmamis pinlere no-connect bayragi koy (ERC sessizligi)")
    ap.add_argument("--no-verify", action="store_true",
                    help="Netlist kalkanini atla (onerilmez)")
    ap.add_argument("--json", type=Path, default=None, help="Sonucu JSON olarak da yaz")
    ap.add_argument("--kicad-cli", default=None)
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    try:
        result = generate_from_intent(
            args.intent, args.out, args.name,
            templates_dir=args.templates,
            rules_path=args.rules,
            place=not args.no_place,
            time_budget_s=args.budget,
            seed=args.seed,
            no_connect_unused=args.no_connect_unused,
            verify=not args.no_verify,
            kicad_cli=args.kicad_cli,
        )
    except (GenerateError, IntentError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2

    print(result.describe())
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(result.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"JSON sonuc: {args.json}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
