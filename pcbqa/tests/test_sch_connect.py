"""Asama 4f devami: cok birim, footprint dogrulama ve BAGLAMA.

`test_sch_add.py` eklemenin kendisini sinar; burada eklenen parcanin
devreye baglanmasi ve ekleme sinirlarinin kaldirilmasi sinaniyor.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from pcbqa import sch_wire, symlib
from pcbqa.kicadcli import KicadCliError, find_kicad_cli
from pcbqa.sch_add import SchAddError, add_symbols, allocate_units
from pcbqa.sch_verify import Connectivity, compare_additive, connectivity_of
from pcbqa.schematic import Schematic, read_schematic

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
PROJECT_DIR = SAMPLES / "pic_programmer"
LOCK_NAME = "~pic_programmer.kicad_pro.lck"


def kicad_cli_available() -> bool:
    try:
        find_kicad_cli()
        return True
    except KicadCliError:
        return False


def device_library_available() -> bool:
    try:
        symlib.get_symbol("Device:R")
        return True
    except symlib.SymLibError:
        return False


class SandboxProject(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-conn-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = self.tmp / "proje"
        shutil.copytree(PROJECT_DIR, self.project)
        (self.project / LOCK_NAME).unlink(missing_ok=True)
        self.sch = self.project / "pic_programmer.kicad_sch"


# --------------------------------------------------------------------------
# Cok birimli semboller
# --------------------------------------------------------------------------


class FakeSymbol:
    def __init__(self, units):
        self.unit_count = units
        self.name = "X"


class UnitAllocationTests(unittest.TestCase):
    def test_single_unit_symbol_gets_one_reference_each(self):
        self.assertEqual(allocate_units(FakeSymbol(1), 3), [(0, 1), (1, 1), (2, 1)])

    def test_multi_unit_fills_a_reference_before_opening_the_next(self):
        """74LS125 -> 4 kapi + guc birimi; 6 istek iki referansa dagilir."""
        self.assertEqual(
            allocate_units(FakeSymbol(5), 6),
            [(0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (1, 1)],
        )

    def test_explicit_unit_gives_each_its_own_reference(self):
        self.assertEqual(allocate_units(FakeSymbol(5), 3, unit=3),
                         [(0, 3), (1, 3), (2, 3)])

    def test_unit_out_of_range_is_refused(self):
        with self.assertRaises(SchAddError):
            allocate_units(FakeSymbol(4), 1, unit=9)


@unittest.skipUnless(device_library_available(), "KiCad sembol kutuphanesi yok")
class MultiUnitAddTests(SandboxProject):
    def test_units_are_written_and_read_back(self):
        result = add_symbols(self.sch, "74xx:74LS125", 6, verify=False, apply=True)
        units = [(s.ref, s.unit) for s in result.plan.symbols]
        self.assertEqual(len({r for r, _ in units}), 2, "6 kapi iki referansa dagilmali")

        schematic = read_schematic(self.sch)
        placed = [(s.ref, s.unit) for s in schematic.symbols
                  if s.lib_id == "74xx:74LS125" and (s.ref, s.unit) in units]
        self.assertEqual(sorted(placed), sorted(units))

    def test_only_the_chosen_unit_pins_are_written(self):
        result = add_symbols(self.sch, "74xx:74LS125", 1, unit=2, verify=False, apply=True)
        sym = read_schematic(self.sch).by_ref(result.plan.symbols[0].ref)
        self.assertEqual(sym.unit, 2)
        self.assertEqual(len(sym.pins), 3)  # 2. kapi: 3 pin


# --------------------------------------------------------------------------
# Footprint dogrulama
# --------------------------------------------------------------------------


@unittest.skipUnless(device_library_available(), "KiCad sembol kutuphanesi yok")
class FootprintCheckTests(SandboxProject):
    def test_missing_footprint_blocks_the_plan(self):
        result = add_symbols(self.sch, "Device:R", 1,
                             footprint="Resistor_SMD:YOK_BOYLE_BIR_SEY",
                             verify=False, apply=True)
        self.assertFalse(result.applied)
        self.assertTrue(result.plan.problems)

    def test_known_footprint_passes(self):
        result = add_symbols(self.sch, "Device:R", 1,
                             footprint="Resistor_SMD:R_0805_2012Metric",
                             verify=False, apply=True)
        self.assertTrue(result.applied)

    def test_check_can_be_disabled(self):
        result = add_symbols(self.sch, "Device:R", 1, footprint="Uydurma:Sey",
                             check_footprint=False, verify=False, apply=True)
        self.assertTrue(result.applied)


@unittest.skipUnless(device_library_available(), "KiCad footprint kutuphanesi yok")
class FootprintLookupTests(unittest.TestCase):
    def test_known_footprint_resolves_to_a_file(self):
        path = symlib.footprint_path("Resistor_SMD:R_0805_2012Metric")
        self.assertTrue(path.is_file())
        self.assertEqual(path.suffix, ".kicad_mod")

    def test_unknown_footprint_names_the_problem(self):
        with self.assertRaises(symlib.SymLibError) as ctx:
            symlib.footprint_path("Resistor_SMD:YOK")
        self.assertIn("footprint bulunamadi", str(ctx.exception))

    def test_unknown_library_names_the_problem(self):
        with self.assertRaises(symlib.SymLibError) as ctx:
            symlib.footprint_path("YokBoyleKutuphane:X")
        self.assertIn("footprint kutuphanesi bulunamadi", str(ctx.exception))


# --------------------------------------------------------------------------
# Baglanti istegi ve yol cikarma
# --------------------------------------------------------------------------


class ConnectionParsingTests(unittest.TestCase):
    def test_net_target(self):
        conn = sch_wire.Connection.parse("1=VCC")
        self.assertEqual((conn.pin, conn.target), ("1", "VCC"))
        self.assertFalse(conn.is_pin_target)

    def test_pin_target(self):
        conn = sch_wire.Connection.parse("2=R1.1")
        self.assertTrue(conn.is_pin_target)
        self.assertEqual(conn.target_pin, ("R1", "1"))

    def test_bad_format_is_refused(self):
        for text in ("VCC", "=VCC", "1=", ""):
            with self.assertRaises(ValueError):
                sch_wire.Connection.parse(text)


class RouteTests(unittest.TestCase):
    def _schematic(self, wires=(), pins=()):
        from pcbqa.schematic import SchPin, SchSymbol, SchWire

        symbols = [
            SchSymbol(ref=f"X{i}", lib_id="l:x", x=x, y=y,
                      pins=[SchPin(number="1", name="", x=x, y=y)])
            for i, (x, y) in enumerate(pins)
        ]
        return Schematic(
            root_path=Path("x.kicad_sch"),
            symbols=symbols,
            wires=[SchWire(x1=a, y1=b, x2=c, y2=d) for a, b, c, d in wires],
        )

    def test_aligned_pins_get_a_straight_wire(self):
        path = sch_wire.route((0, 0), (10, 0), self._schematic(), "/")
        self.assertEqual(path, [(0, 0), (10, 0)])

    def test_offset_pins_get_an_l_route(self):
        path = sch_wire.route((0, 0), (10, 5), self._schematic(), "/")
        self.assertEqual(len(path), 3)
        self.assertIn(path[1], [(10, 0), (0, 5)])

    def test_route_avoids_running_over_another_pin(self):
        """Ilk aday baska bir pinin ustunden geciyorsa ikincisi secilir."""
        blocked = self._schematic(pins=[(5.0, 0.0)])
        path = sch_wire.route((0, 0), (10, 5), blocked, "/")
        self.assertEqual(path, [(0, 0), (0, 5), (10, 5)])

    def test_no_clean_route_returns_none(self):
        blocked = self._schematic(pins=[(5.0, 0.0), (0.0, 2.5)])
        self.assertIsNone(sch_wire.route((0, 0), (10, 5), blocked, "/"))

    def test_junction_is_added_when_an_end_lands_mid_wire(self):
        sch = self._schematic(wires=[(10.0, -5.0, 10.0, 5.0)])
        self.assertEqual(sch_wire.junctions_needed([(0, 0), (10, 0)], sch, "/"),
                         [(10, 0)])

    def test_no_junction_when_ends_meet_end_to_end(self):
        sch = self._schematic(wires=[(10.0, 0.0, 20.0, 0.0)])
        self.assertEqual(sch_wire.junctions_needed([(0, 0), (10, 0)], sch, "/"), [])


# --------------------------------------------------------------------------
# Kalkan: beklenen baglanti gerceklesti mi?
# --------------------------------------------------------------------------


class ExpectedJoinShieldTests(unittest.TestCase):
    def _conn(self, nets):
        partition = frozenset(frozenset(pins) for pins in nets.values())
        net_of = {pin: name for name, pins in nets.items() for pin in pins}
        components = frozenset(pin[0] for pins in nets.values() for pin in pins)
        return Connectivity(source=Path("x"), partition=partition,
                            net_of=net_of, components=components)

    def test_intended_connection_passes(self):
        before = self._conn({"VCC": [("C1", "1"), ("U1", "7")]})
        after = self._conn({"VCC": [("C1", "1"), ("U1", "7"), ("R2", "1")],
                            "unconnected-(R2-Pad2)": [("R2", "2")]})
        diff = compare_additive(before, after, {"R2"},
                                expected_joins={("R2", "1"): {("C1", "1")}})
        self.assertTrue(diff.ok, diff)

    def test_connection_that_did_not_happen_is_reported(self):
        """Tel cizilip baglanmadiysa sessizce gecmemeli."""
        before = self._conn({"VCC": [("C1", "1"), ("U1", "7")]})
        after = self._conn({"VCC": [("C1", "1"), ("U1", "7")],
                            "unconnected-(R2-Pad1)": [("R2", "1")]})
        diff = compare_additive(before, after, {"R2"},
                                expected_joins={("R2", "1"): {("C1", "1")}})
        self.assertFalse(diff.ok)
        self.assertTrue(diff.regrouped)

    def test_connecting_to_the_wrong_net_is_rejected(self):
        before = self._conn({"VCC": [("C1", "1")], "GND": [("C1", "2")]})
        after = self._conn({"VCC": [("C1", "1")],
                            "GND": [("C1", "2"), ("R2", "1")]})
        diff = compare_additive(before, after, {"R2"},
                                expected_joins={("R2", "1"): {("C1", "1")}})
        self.assertFalse(diff.ok)


# --------------------------------------------------------------------------
# Dosyaya yazma
# --------------------------------------------------------------------------


@unittest.skipUnless(device_library_available(), "KiCad sembol kutuphanesi yok")
class ConnectWritingTests(SandboxProject):
    def test_label_is_written_at_the_pin(self):
        result = add_symbols(self.sch, "Device:R", 1, connect=["1=VCC"],
                             verify=False, apply=True)
        new = result.plan.symbols[0]
        self.assertIn("(label ", self.sch.read_text(encoding="utf-8"))
        self.assertEqual(result.plan.connections[0][2], "VCC")

        schematic = read_schematic(self.sch)
        pin = schematic.by_ref(new.ref).pin("1")
        placed = [lab for lab in schematic.labels
                  if abs(lab.x - pin.x) < 1e-6 and abs(lab.y - pin.y) < 1e-6]
        self.assertTrue(placed, "etiket pinin ustune konmadi")

    def test_wire_is_written_for_a_pin_target(self):
        before = len(read_schematic(self.sch).wires)
        add_symbols(self.sch, "Device:R", 1, connect=["1=R1.1"],
                    verify=False, apply=True)
        self.assertGreater(len(read_schematic(self.sch).wires), before)

    def test_unknown_target_pin_blocks_and_writes_nothing(self):
        before = self.sch.read_bytes()
        result = add_symbols(self.sch, "Device:R", 1, connect=["1=YOK9.1"],
                             verify=False, apply=True)
        self.assertFalse(result.applied)
        self.assertTrue(result.plan.problems)
        self.assertEqual(self.sch.read_bytes(), before)

    def test_unknown_pin_number_blocks(self):
        result = add_symbols(self.sch, "Device:R", 1, connect=["7=VCC"],
                             verify=False, apply=True)
        self.assertFalse(result.applied)
        self.assertTrue(any("pini yok" in p for p in result.plan.problems))

    def test_bad_connect_syntax_is_refused(self):
        with self.assertRaises(SchAddError):
            add_symbols(self.sch, "Device:R", 1, connect=["bozuk"], verify=False)


# --------------------------------------------------------------------------
# Uctan uca: baglanti GERCEKTEN kuruldu mu (KiCad'in kendi netlist'i)
# --------------------------------------------------------------------------


@unittest.skipUnless(kicad_cli_available() and device_library_available(),
                     "kicad-cli veya sembol kutuphanesi yok")
class ConnectEndToEndTests(SandboxProject):
    def test_label_really_joins_the_net(self):
        result = add_symbols(self.sch, "Device:R", 2, connect=["1=VCC", "2=GND"],
                             apply=True)
        self.assertTrue(result.applied, result.diff)
        conn = connectivity_of(self.sch)
        (self.project / LOCK_NAME).unlink(missing_ok=True)
        for new in result.plan.symbols:
            self.assertEqual(conn.net_of[(new.ref, "1")], "VCC")
            self.assertEqual(conn.net_of[(new.ref, "2")], "GND")

    def test_wire_really_joins_the_target_pin(self):
        result = add_symbols(self.sch, "Device:R", 1, connect=["1=R1.1"], apply=True)
        self.assertTrue(result.applied, result.diff)
        conn = connectivity_of(self.sch)
        (self.project / LOCK_NAME).unlink(missing_ok=True)
        ref = result.plan.symbols[0].ref
        group = next(net for net in conn.partition if (ref, "1") in net)
        self.assertIn(("R1", "1"), group)


if __name__ == "__main__":
    unittest.main()
