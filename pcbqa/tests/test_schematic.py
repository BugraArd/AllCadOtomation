"""Asama 4a/4b: sematik okuyucu ve netlist degismezligi kalkani."""

from __future__ import annotations

import unittest
from pathlib import Path

from pcbqa.rules import run_schematic_checks
from pcbqa.schematic import (
    GRID_MM,
    Schematic,
    SchSheetRef,
    SchSymbol,
    place_point,
    read_schematic,
)
from pcbqa.sch_verify import Connectivity, ConnectivityDiff, compare

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
PROJECT = SAMPLES / "pic_programmer" / "pic_programmer.kicad_sch"


class TransformTests(unittest.TestCase):
    """Kutuphane -> sayfa donusumu (deneysel olarak secildi, bkz. schematic.py)."""

    def test_no_rotation_only_flips_y(self):
        self.assertEqual(place_point(0.0, 3.81, 0.0, None), (0.0, -3.81))
        self.assertEqual(place_point(2.54, 0.0, 0.0, None), (2.54, 0.0))

    def test_rotation_90(self):
        x, y = place_point(0.0, 3.81, 90.0, None)
        self.assertAlmostEqual(x, -3.81, places=6)
        self.assertAlmostEqual(y, 0.0, places=6)

    def test_rotation_180_negates_x_keeps_y(self):
        x, y = place_point(2.54, 3.81, 180.0, None)
        self.assertAlmostEqual(x, -2.54, places=6)
        self.assertAlmostEqual(y, 3.81, places=6)

    def test_mirror_is_applied_after_rotation(self):
        """Ters sirada uygulanirsa 90 derecede farkli sonuc cikar."""
        rotated = place_point(2.54, 0.0, 90.0, None)
        mirrored = place_point(2.54, 0.0, 90.0, "x")
        self.assertAlmostEqual(mirrored[0], rotated[0], places=6)
        self.assertAlmostEqual(mirrored[1], -rotated[1], places=6)


class ReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sch = read_schematic(PROJECT)

    def test_parses_without_stray_parens(self):
        self.assertEqual(self.sch.stray_parens, 0)
        self.assertEqual(self.sch.version, "20260101")
        self.assertEqual(self.sch.paper, "A4")

    def test_follows_hierarchy_into_subsheets(self):
        self.assertEqual(len(self.sch.files), 2)
        self.assertIn("/pic_sockets", self.sch.sheet_paths())
        self.assertTrue(any(not s.missing for s in self.sch.sheets))

    def test_resolves_pin_positions_for_a_rotated_symbol(self):
        """R1 90 derece donuk; pinleri govdenin iki yaninda, ayni Y'de olmali."""
        r1 = self.sch.by_ref("R1")
        self.assertIsNotNone(r1)
        self.assertEqual(r1.rotation, 90.0)
        self.assertEqual(len(r1.pins), 2)
        p1, p2 = r1.pin("1"), r1.pin("2")
        self.assertAlmostEqual(p1.y, r1.y, places=3)
        self.assertAlmostEqual(p2.y, r1.y, places=3)
        self.assertAlmostEqual(abs(p1.x - p2.x), 7.62, places=3)

    def test_pins_land_on_something_connectable(self):
        """Donusum dogruysa her pin bir capaya oturur.

        Capa yalnizca tel ucu degildir: bir pin junction'a, no_connect'e,
        etikete veya DOGRUDAN baska bir sembolun pinine de degebilir - guc
        sembolleri cogunlukla sonuncusuyle baglanir. Dar bir olcut bunu
        'kaciran pin' sanar; pic_programmer'da pinlerin %100'u oturuyor.
        """
        anchors = set()
        for w in self.sch.wires:
            for px, py in w.endpoints:
                anchors.add((w.sheet_path, round(px, 2), round(py, 2)))
        for pt in self.sch.junctions + self.sch.no_connects:
            anchors.add((pt.sheet_path, round(pt.x, 2), round(pt.y, 2)))
        for lb in self.sch.labels:
            anchors.add((lb.sheet_path, round(lb.x, 2), round(lb.y, 2)))

        pin_points: dict[tuple, set[str]] = {}
        for sym in self.sch.symbols:
            for pin in sym.pins:
                key = (sym.sheet_path, round(pin.x, 2), round(pin.y, 2))
                pin_points.setdefault(key, set()).add(sym.ref)

        pins = [(s, p) for s in self.sch.symbols for p in s.pins]
        hits = 0
        for sym, pin in pins:
            key = (sym.sheet_path, round(pin.x, 2), round(pin.y, 2))
            if key in anchors or (pin_points.get(key, set()) - {sym.ref}):
                hits += 1
        self.assertGreater(hits / len(pins), 0.98, "pin donusumu bozulmus olabilir")

    def test_separates_power_symbols_from_real_components(self):
        self.assertTrue(self.sch.real_symbols)
        self.assertLess(len(self.sch.real_symbols), len(self.sch.symbols))
        for sym in self.sch.symbols:
            if sym.ref.startswith("#PWR"):
                self.assertTrue(sym.is_power)

    def test_symbols_sit_on_the_schematic_grid(self):
        off_grid = [s.ref for s in self.sch.real_symbols if not s.on_grid(GRID_MM)]
        self.assertEqual(off_grid, [], f"izgara disi sembol: {off_grid}")

    def test_computes_a_body_bounding_box(self):
        r1 = self.sch.by_ref("R1")
        self.assertIsNotNone(r1.bbox)
        minx, miny, maxx, maxy = r1.bbox
        self.assertLess(minx, r1.x)
        self.assertGreater(maxx, r1.x)
        self.assertLess(miny, r1.y)
        self.assertGreater(maxy, r1.y)

    def test_reading_a_directory_picks_the_root_sheet(self):
        sch = read_schematic(PROJECT.parent)
        self.assertEqual(sch.root_path.name, PROJECT.name)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            read_schematic(SAMPLES / "yok-boyle-bir-sey.kicad_sch")


def conn(nets: dict[str, list[tuple[str, str]]]) -> Connectivity:
    """Test icin elle baglanti yapisi kurar."""
    partition = frozenset(frozenset(pins) for pins in nets.values() if pins)
    net_of = {pin: name for name, pins in nets.items() for pin in pins}
    components = frozenset(ref for pins in nets.values() for ref, _ in pins)
    return Connectivity(
        source=Path("test"), partition=partition, net_of=net_of, components=components
    )


class ShieldTests(unittest.TestCase):
    """Kalkanin dogru degismezi kullandigini dogrular."""

    def test_identical_connectivity_passes(self):
        a = conn({"VCC": [("U1", "1"), ("C1", "1")], "GND": [("U1", "2"), ("C1", "2")]})
        self.assertTrue(compare(a, a).ok)

    def test_net_renaming_alone_is_not_a_change(self):
        """Otomatik net adlari degisebilir; bolunme ayniysa devre aynidir."""
        a = conn({"Net-(U1-Pad1)": [("U1", "1"), ("C1", "1")]})
        b = conn({"Net-(C1-Pad1)": [("U1", "1"), ("C1", "1")]})
        self.assertTrue(compare(a, b).ok)

    def test_disconnected_pin_is_caught(self):
        a = conn({"VCC": [("U1", "1"), ("C1", "1")]})
        b = conn({"VCC": [("U1", "1")], "unconnected-(C1-Pad1)": [("C1", "1")]})
        diff = compare(a, b)
        self.assertFalse(diff.ok)
        self.assertTrue(diff.regrouped)
        self.assertIn("baska aga tasindi", diff.describe())

    def test_merged_nets_are_caught(self):
        a = conn({"A": [("U1", "1")], "B": [("U2", "1")]})
        b = conn({"A": [("U1", "1"), ("U2", "1")]})
        self.assertFalse(compare(a, b).ok)

    def test_removed_component_is_caught(self):
        a = conn({"VCC": [("U1", "1"), ("C1", "1")]})
        b = conn({"VCC": [("U1", "1")]})
        diff = compare(a, b)
        self.assertFalse(diff.ok)
        self.assertIn(("C1", "1"), diff.lost_pins)
        self.assertIn("C1", diff.removed_components)

    def test_details_explains_a_membership_change_with_the_same_name(self):
        diff = ConnectivityDiff(
            ok=False, regrouped=[(("R1", "2"), "Net-(D2-A)", "Net-(D2-A)", 4, 3)]
        )
        line = diff.details()[0]
        self.assertIn("agi degisti", line)
        self.assertIn("4 -> 3", line)


def symbol(ref: str, x: float, y: float, **kwargs) -> SchSymbol:
    defaults = {"lib_id": "test:X", "footprint": "Lib:FP"}
    defaults.update(kwargs)
    return SchSymbol(ref=ref, x=x, y=y, **defaults)


class SchematicCheckTests(unittest.TestCase):
    """Sematigin yapisal kontrolleri (rules.run_schematic_checks)."""

    @staticmethod
    def ids(findings) -> set[str]:
        return {f.rule_id for f in findings}

    def test_clean_schematic_produces_no_findings(self):
        sch = Schematic(root_path=Path("t.kicad_sch"), symbols=[symbol("R1", 1.27, 2.54)])
        self.assertEqual(run_schematic_checks(sch), [])

    def test_real_project_is_clean(self):
        self.assertEqual(run_schematic_checks(read_schematic(PROJECT)), [])

    def test_off_grid_symbol_is_flagged(self):
        sch = Schematic(root_path=Path("t.kicad_sch"), symbols=[symbol("R1", 1.0, 2.54)])
        self.assertIn("sematik-izgara-disi", self.ids(run_schematic_checks(sch)))

    def test_missing_footprint_is_flagged(self):
        sch = Schematic(
            root_path=Path("t.kicad_sch"), symbols=[symbol("R1", 1.27, 2.54, footprint="")]
        )
        self.assertIn("sematik-footprint-yok", self.ids(run_schematic_checks(sch)))

    def test_virtual_symbols_are_exempt_from_footprint_check(self):
        """#PWR ve #FLG'nin footprint'i olmaz - bunlari isaretlemek gurultudur."""
        sch = Schematic(
            root_path=Path("t.kicad_sch"),
            symbols=[
                symbol("#PWR01", 1.27, 2.54, footprint=""),
                symbol("#FLG01", 2.54, 2.54, footprint=""),
            ],
        )
        self.assertEqual(run_schematic_checks(sch), [])

    def test_dnp_symbol_is_exempt_from_footprint_check(self):
        sch = Schematic(
            root_path=Path("t.kicad_sch"),
            symbols=[symbol("R1", 1.27, 2.54, footprint="", dnp=True)],
        )
        self.assertEqual(run_schematic_checks(sch), [])

    def test_overlapping_symbol_bodies_are_flagged(self):
        a = symbol("R1", 1.27, 2.54)
        a.bbox = (0.0, 0.0, 5.0, 5.0)
        b = symbol("R2", 2.54, 2.54)
        b.bbox = (2.0, 2.0, 7.0, 7.0)
        sch = Schematic(root_path=Path("t.kicad_sch"), symbols=[a, b])
        self.assertIn("sematik-cakisan-sembol", self.ids(run_schematic_checks(sch)))

    def test_touching_bodies_do_not_overlap(self):
        a = symbol("R1", 1.27, 2.54)
        a.bbox = (0.0, 0.0, 5.0, 5.0)
        b = symbol("R2", 6.35, 2.54)
        b.bbox = (5.0, 0.0, 10.0, 5.0)
        sch = Schematic(root_path=Path("t.kicad_sch"), symbols=[a, b])
        self.assertNotIn("sematik-cakisan-sembol", self.ids(run_schematic_checks(sch)))

    def test_symbols_on_different_sheets_never_overlap(self):
        a = symbol("R1", 1.27, 2.54, sheet_path="/")
        a.bbox = (0.0, 0.0, 5.0, 5.0)
        b = symbol("R2", 1.27, 2.54, sheet_path="/alt")
        b.bbox = (0.0, 0.0, 5.0, 5.0)
        sch = Schematic(root_path=Path("t.kicad_sch"), symbols=[a, b])
        self.assertNotIn("sematik-cakisan-sembol", self.ids(run_schematic_checks(sch)))

    def test_missing_subsheet_file_is_an_error(self):
        sch = Schematic(
            root_path=Path("t.kicad_sch"),
            sheets=[
                SchSheetRef(
                    name="alt", filename="yok.kicad_sch", x=0, y=0, width=10, height=10, missing=True
                )
            ],
        )
        findings = run_schematic_checks(sch)
        self.assertIn("sematik-eksik-sayfa", self.ids(findings))
        self.assertEqual(findings[0].severity, "error")

    def test_broken_file_is_an_error(self):
        sch = Schematic(root_path=Path("t.kicad_sch"), stray_parens=3)
        findings = run_schematic_checks(sch)
        self.assertIn("sematik-bozuk-dosya", self.ids(findings))
        self.assertEqual(findings[0].severity, "error")


if __name__ == "__main__":
    unittest.main()
