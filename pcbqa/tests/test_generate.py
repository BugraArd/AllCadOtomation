"""Evre 3a surucusu: insa planindan gercek KiCad projesi.

Uc katman ayri ayri korunur:

  * ISKELET ve GEOMETRI (kutuphane gerekmez): dosya bicimleri, sayfa
    paketleme, referans dagitimi.
  * KALKAN (kutuphane gerekmez): `verify_against_plan` uc sessiz hata
    sinifini da yakalamali - eksik pin, bolunmus ag, fazla pin.
  * UCTAN UCA (KiCad kuruluysa): kucuk bir niyetten gercek proje uretilir,
    KiCad'in KENDI netlist'i planla karsilastirilir, kart yansitilir ve
    skorlanir.

En degerli olan sonuncusu: uretilen dosyanin KiCad tarafindan okunabildigini
yalnizca KiCad kanitlayabilir. Sessiz hata dersinin uretim tarafina
uygulanmis hali - `sheet_instances` eksikligi ve turev sembollerin birim
adlari bu testler yazilirken degil, tam olarak bu koşumla bulundu.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pcbqa import symlib
from pcbqa.generate import (
    GenerateError,
    allocate_refs,
    choose_paper,
    create_skeleton,
    empty_board_text,
    empty_schematic_text,
    expected_nets,
    generate,
    pack_rows,
    project_json,
    verify_against_plan,
)
from pcbqa.intent import (
    BuildPlan,
    Intent,
    IntentBlock,
    PlannedComponent,
    expand_intent,
    load_templates,
    resolve_plan,
)
from pcbqa.sch_add import PAPER_SIZES
from pcbqa.sch_verify import Connectivity
from pcbqa.sexpr import parse_with_stats

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def device_library_available() -> bool:
    try:
        symlib.get_symbol("Device:R")
        return True
    except symlib.SymLibError:
        return False


class TempFolder(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-gen-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# Iskelet
# --------------------------------------------------------------------------


class SkeletonTests(TempFolder):
    def test_empty_schematic_parses_and_has_sheet_instances(self):
        text = empty_schematic_text("11111111-2222-3333-4444-555555555555", "A3")
        root, stray = parse_with_stats(text)
        self.assertEqual(stray, 0)
        self.assertEqual(root[0], "kicad_sch")
        # Olculdu: bu blok olmadan icine sembol konan dosyayi kicad-cli
        # hicbir mesaj vermeden reddediyor.
        self.assertIn("sheet_instances", text)
        self.assertIn("A3", text)

    def test_empty_board_parses_and_has_no_outline(self):
        root, stray = parse_with_stats(empty_board_text())
        self.assertEqual(stray, 0)
        self.assertEqual(root[0], "kicad_pcb")
        # Sinir bilerek sonra cizilir (olculen courtyard alanindan)
        self.assertNotIn("Edge.Cuts", "".join(str(n) for n in root if not isinstance(n, list)))

    def test_project_file_is_valid_json(self):
        data = json.loads(project_json("kartim"))
        self.assertEqual(data["meta"]["filename"], "kartim.kicad_pro")

    def test_skeleton_refuses_to_overwrite(self):
        create_skeleton(self.tmp, "p", "A4")
        with self.assertRaises(GenerateError) as ctx:
            create_skeleton(self.tmp, "p", "A4")
        self.assertIn("zaten var", str(ctx.exception))

    def test_skeleton_writes_three_files(self):
        pro, sch, pcb = create_skeleton(self.tmp, "p", "A4")
        for path in (pro, sch, pcb):
            self.assertTrue(path.is_file(), path.name)


# --------------------------------------------------------------------------
# Sayfa yerlesimi
# --------------------------------------------------------------------------


class LayoutTests(unittest.TestCase):
    def test_packed_boxes_do_not_overlap(self):
        sizes = [(35.0, 81.0)] + [(5.0, 7.6)] * 17
        paper, centers, note = choose_paper(sizes)
        self.assertEqual(len(centers), len(sizes))
        boxes = [
            (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
            for (cx, cy), (w, h) in zip(centers, sizes)
        ]
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                overlaps = (a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1])
                self.assertFalse(overlaps, f"{a} ve {b} cakisiyor ({paper})")

    def test_small_design_stays_on_a4(self):
        paper, _, note = choose_paper([(5.0, 7.6)] * 6)
        self.assertEqual(paper, "A4")
        self.assertEqual(note, "")

    def test_large_design_escalates_paper(self):
        paper, centers, note = choose_paper([(40.0, 60.0)] * 60)
        self.assertNotEqual(paper, "A4")
        self.assertEqual(note, "")
        self.assertEqual(len(centers), 60)

    def test_rows_stay_inside_paper_width(self):
        sizes = [(20.0, 10.0)] * 30
        centers, _ = pack_rows(sizes, "A4")
        width = PAPER_SIZES["A4"][0]
        for (cx, _), (w, _) in zip(centers, sizes):
            self.assertGreaterEqual(cx - w / 2, 0.0)
            self.assertLessEqual(cx + w / 2, width)


# --------------------------------------------------------------------------
# Referans dagitimi
# --------------------------------------------------------------------------


class FakeSymbol:
    """Kutuphane gerektirmeden referans on eki tasiyan en kucuk sembol."""

    def __init__(self, prefix: str):
        self.reference_prefix = prefix


def _plan_with(*lib_ids: str) -> BuildPlan:
    return BuildPlan(
        name="t",
        components=[
            PlannedComponent(label=f"b/{i}", template_id="b", lib_id=lib_id,
                             value="", footprint="")
            for i, lib_id in enumerate(lib_ids)
        ],
    )


class RefTests(unittest.TestCase):
    def test_numbering_is_per_prefix_and_follows_plan_order(self):
        plan = _plan_with("Device:C", "Device:R", "Device:C", "MCU:X")
        symbols = {"Device:C": FakeSymbol("C"), "Device:R": FakeSymbol("R"),
                   "MCU:X": FakeSymbol("U")}
        refs = allocate_refs(plan, symbols)
        self.assertEqual(list(refs.values()), ["C1", "R1", "C2", "U1"])

    def test_same_plan_gives_same_refs(self):
        symbols = {"Device:C": FakeSymbol("C")}
        first = allocate_refs(_plan_with("Device:C", "Device:C"), symbols)
        second = allocate_refs(_plan_with("Device:C", "Device:C"), symbols)
        self.assertEqual(list(first.values()), list(second.values()))


# --------------------------------------------------------------------------
# Kalkan
# --------------------------------------------------------------------------


def _plan_two_resistors() -> tuple[BuildPlan, dict[str, str]]:
    plan = BuildPlan(
        name="t",
        resolved=True,
        components=[
            PlannedComponent(label="b/r1", template_id="b", lib_id="Device:R",
                             value="10k", footprint="",
                             pin_connect=[("1", "VCC"), ("2", "GND")]),
            PlannedComponent(label="b/r2", template_id="b", lib_id="Device:R",
                             value="10k", footprint="",
                             pin_connect=[("1", "VCC"), ("2", "GND")]),
        ],
    )
    return plan, {"b/r1": "R1", "b/r2": "R2"}


def _conn(nets: list[set[tuple[str, str]]], components: set[str]) -> Connectivity:
    return Connectivity(
        source=Path("t"),
        partition=frozenset(frozenset(n) for n in nets),
        net_of={pin: f"N{i}" for i, n in enumerate(nets) for pin in n},
        components=frozenset(components),
    )


class ShieldTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.refs = _plan_two_resistors()
        self.expected = expected_nets(self.plan, self.refs)

    def test_expected_nets_use_allocated_references(self):
        self.assertEqual(self.expected["VCC"], frozenset({("R1", "1"), ("R2", "1")}))

    def test_matching_netlist_passes(self):
        conn = _conn(
            [{("R1", "1"), ("R2", "1")}, {("R1", "2"), ("R2", "2")}], {"R1", "R2"}
        )
        verified, problems = verify_against_plan(conn, self.expected, self.refs)
        self.assertEqual(problems, [])
        self.assertEqual(verified, 2)

    def test_split_net_is_caught(self):
        """Etiket tutmamis: ayni ad iki ayri aga bolunmus."""
        conn = _conn(
            [{("R1", "1")}, {("R2", "1")}, {("R1", "2"), ("R2", "2")}], {"R1", "R2"}
        )
        _, problems = verify_against_plan(conn, self.expected, self.refs)
        self.assertTrue(any("ayri aga boldu" in p for p in problems), problems)

    def test_silent_extra_pin_is_caught(self):
        """Planda olmayan bir pin aga girmis - sessiz kisa devre."""
        conn = _conn(
            [{("R1", "1"), ("R2", "1"), ("R9", "1")}, {("R1", "2"), ("R2", "2")}],
            {"R1", "R2"},
        )
        _, problems = verify_against_plan(conn, self.expected, self.refs)
        self.assertTrue(any("planda olmayan pin" in p for p in problems), problems)

    def test_missing_pin_is_caught(self):
        conn = _conn([{("R1", "1")}, {("R1", "2"), ("R2", "2")}], {"R1", "R2"})
        _, problems = verify_against_plan(conn, self.expected, self.refs)
        self.assertTrue(any("bulunamayan pin" in p for p in problems), problems)

    def test_missing_component_is_caught(self):
        conn = _conn([{("R1", "1")}, {("R1", "2")}], {"R1"})
        _, problems = verify_against_plan(conn, self.expected, self.refs)
        self.assertTrue(any("olmayan bilesen" in p for p in problems), problems)


# --------------------------------------------------------------------------
# Uctan uca
# --------------------------------------------------------------------------


@unittest.skipUnless(device_library_available(), "KiCad sembol kutuphanesi yok")
class EndToEndTests(TempFolder):
    """Kucuk bir niyetten gercek proje - KiCad kendi netlist'iyle dogruluyor."""

    @classmethod
    def setUpClass(cls):
        cls.templates = load_templates()

    def small_plan(self) -> BuildPlan:
        intent = Intent(name="kucuk", blocks=[IntentBlock(template="guc-girisi-header"),
                                              IntentBlock(template="ldo-ams1117-3v3")])
        plan = resolve_plan(expand_intent(intent, self.templates))
        self.assertTrue(plan.ok, plan.problems)
        return plan

    def test_generates_a_scored_project(self):
        plan = self.small_plan()
        result = generate(plan, self.tmp / "proje", "kucuk", time_budget_s=4.0)
        self.assertTrue(result.ok, result.problems)
        # KiCad'in kendi netlist'i planin butun aglarini birebir kurmus olmali
        self.assertEqual(result.verified_nets, len(plan.nets()))
        self.assertEqual(result.synced, len(plan.components))
        self.assertTrue(result.sch.is_file())
        self.assertTrue(result.pcb.is_file())
        self.assertGreater(result.board_size[0], 0)
        # Yerlestirme kartı kotulestiremez (auto'nun gerileme garantisi)
        self.assertGreaterEqual(result.score_after, result.score_before)

    def test_unresolved_plan_is_refused(self):
        plan = expand_intent(
            Intent(name="x", blocks=[IntentBlock(template="guc-girisi-header")]),
            self.templates,
        )
        with self.assertRaises(GenerateError) as ctx:
            generate(plan, self.tmp / "cozumlenmemis", "x")
        self.assertIn("cozumlenmemis", str(ctx.exception))

    def test_no_place_stops_before_scoring(self):
        plan = self.small_plan()
        result = generate(plan, self.tmp / "yerlessiz", "y", place=False)
        self.assertTrue(result.ok, result.problems)
        self.assertIsNone(result.score_before)
        self.assertEqual(result.synced, len(plan.components))


# --------------------------------------------------------------------------
# Karta yazma: donme metinleri de dondurur
# --------------------------------------------------------------------------


class BoardWriteTests(TempFolder):
    """`harness.write_board` bir HARNESS islevi ama hatasi burada bulundu.

    Uretilen 18 bilesenlik kartta KiCad'in parite kontrolu 11 bileseni
    "kutuphanedeki kopyasiyla eslesmiyor" diye isaretledi ve o 11 bilesen,
    kartta DONMUS olan 11 bilesenin tam olarak kendisiydi. Sebep: govde
    donuyordu ama icindeki metinlerin acisi oldugu gibi kaliyordu; KiCad
    kendi dondurdugunde her metnin acisini da gunceller.
    """

    BOARD = """(kicad_pcb
	(version 20260206)
	(footprint "Capacitor_SMD:C_0603_1608Metric"
		(at 10 10)
		(property "Reference" "C1" (at 0 -1.43 0) (layer "F.SilkS"))
		(property "Value" "100nF" (at 0 1.43 0) (layer "F.Fab"))
		(fp_text user "${REFERENCE}" (at 0 0 0) (layer "F.Fab"))
		(pad "1" smd roundrect (at -0.7875 0) (size 0.9 0.95) (layers "F.Cu"))
	)
)"""

    def _write(self, rotation: float):
        from pcbqa.harness import write_board

        source = self.tmp / "kaynak.kicad_pcb"
        source.write_text(self.BOARD, encoding="utf-8")
        target = self.tmp / f"hedef{rotation:g}.kicad_pcb"
        write_board(source, {"C1": (20.0, 30.0, rotation)}, target)
        root, stray = parse_with_stats(target.read_text(encoding="utf-8"))
        self.assertEqual(stray, 0)
        return root

    def _angles(self, root) -> list[float]:
        from pcbqa.sexpr import child, children

        footprint = next(iter(children(root, "footprint")))
        out = []
        for item in footprint:
            if isinstance(item, list) and item and item[0] in ("property", "fp_text", "pad"):
                at = child(item, "at")
                out.append(float(at[3]) if at and len(at) > 3 else 0.0)
        return out

    def test_rotation_turns_every_text_and_pad(self):
        """Metinler VE pad'ler donmeli - KiCad kendi dondurdugunde oyle yazar.

        Pad acisi eksik kalinca KiCad kart footprint'ini kutuphanedekinden
        farkli goruyor (`lib_footprint_mismatch`); uretilen kartta 12 bilesen
        boyle isaretlenmisti ve hepsi donmus olanlardi.
        """
        angles = self._angles(self._write(90.0))
        self.assertEqual(angles, [90.0, 90.0, 90.0, 90.0])

    def test_no_rotation_leaves_everything_alone(self):
        angles = self._angles(self._write(0.0))
        self.assertEqual(angles, [0.0, 0.0, 0.0, 0.0])

    def test_position_is_written(self):
        from pcbqa.sexpr import child, children

        footprint = next(iter(children(self._write(270.0), "footprint")))
        at = child(footprint, "at")
        self.assertEqual([str(v) for v in at[1:]], ["20", "30", "270"])


if __name__ == "__main__":
    unittest.main()
