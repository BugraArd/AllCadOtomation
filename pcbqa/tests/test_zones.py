"""Bakir dokum (zone) okuma ve `copper_area` kurali.

Bu, arastirmanin "en yuksek getirili eksik" diye isaretledigi parcaydi
(docs/tasarim-kurallari/README.md): dokum alani okunmadan uc kaynakli kural
olculemiyordu - sicak dongu alani, SW bakir alani <= 100 mm2 (ROHM 66AN015E) ve
termal bakir alani (Richtek AN044).

`copper_area` bunlardan ikisini karsilar. Sicak dongu alani hala olculemez:
o, akimin izledigi YOLU bilmeyi gerektiriyor, tek bir netin alanini degil.
"""

from __future__ import annotations

import math
import unittest
from pathlib import Path

from pcbqa.harness import load_design
from pcbqa.pcb import Zone, ZoneFill, read_board
from pcbqa.rules import CHECKS, Rule, RuleError

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "samples" / "pic_programmer" / "pic_programmer.kicad_pcb"
UNZONED = ROOT / "samples" / "bench_bad.kicad_pcb"


def run(design, spec: dict, severity: str = "warning"):
    rule = Rule(id="t", type="copper_area", severity=severity, spec=spec)
    return CHECKS["copper_area"](design, rule)


class ZoneReadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.board = read_board(BOARD)

    def test_zone_is_read(self):
        self.assertEqual(len(self.board.zones), 1)

    def test_zone_carries_layer_and_fill(self):
        zone = self.board.zones[0]
        self.assertEqual(zone.layers, ("B.Cu",))
        self.assertTrue(zone.filled)
        self.assertEqual(len(zone.fills), 3, "dokum uc adaya bolunmus")

    def test_unnamed_net_is_empty_string(self):
        """KiCad'de nete BAGLI OLMAYAN dokum olabilir; ad bos string gelir."""
        self.assertEqual(self.board.zones[0].net, "")

    def test_area_comes_from_fills_not_outline(self):
        """Sinir poligonu kullanicinin cizdigi; GERCEK bakir doldurulmus olandir.

        Ikisi ayni degildir: aciklik ve termal koprular doldurulmus alandan
        dusulur. Sinirdan olcmek FAZLA tahmin verir.
        """
        zone = self.board.zones[0]
        from pcbqa import geom

        outline_area = geom.area(zone.outline)
        self.assertGreater(outline_area, 0.0)
        self.assertNotAlmostEqual(zone.area_mm2, outline_area, places=1)
        self.assertAlmostEqual(
            zone.area_mm2, sum(f.area_mm2 for f in zone.fills), places=6
        )

    def test_area_on_layer_filters(self):
        zone = self.board.zones[0]
        self.assertAlmostEqual(zone.area_on("B.Cu"), zone.area_mm2, places=6)
        self.assertEqual(zone.area_on("F.Cu"), 0.0)

    def test_unfilled_zone_falls_back_to_outline(self):
        """Doldurulmamis kartta sinirdan olcmek FAZLA tahmindir - `filled` bunu soyler."""
        zone = Zone(net="GND", layers=("F.Cu",), outline=[(0, 0), (10, 0), (10, 5), (0, 5)])
        self.assertFalse(zone.filled)
        self.assertAlmostEqual(zone.area_mm2, 50.0, places=6)
        self.assertAlmostEqual(zone.area_on("F.Cu"), 50.0, places=6)
        self.assertEqual(zone.area_on("B.Cu"), 0.0)

    def test_fill_area_is_shoelace(self):
        fill = ZoneFill(layer="F.Cu", points=[(0, 0), (4, 0), (4, 3), (0, 3)])
        self.assertAlmostEqual(fill.area_mm2, 12.0, places=6)

    def test_board_without_zones_is_empty(self):
        self.assertEqual(read_board(UNZONED).zones, [])


class PadAreaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.board = read_board(BOARD)

    def pad_of_shape(self, shape: str):
        for comp in self.board.components:
            for pad in comp.pads:
                if pad.shape == shape and pad.size_x > 0:
                    return pad
        return None

    def test_circle_pad_is_pi_r_squared(self):
        pad = self.pad_of_shape("circle")
        self.assertIsNotNone(pad, "kartta daire pad yok")
        r = pad.size_x / 2.0
        self.assertAlmostEqual(pad.area_mm2, math.pi * r * r, places=6)

    def test_oval_pad_is_a_stadium(self):
        for comp in self.board.components:
            for pad in comp.pads:
                if pad.shape == "oval" and abs(pad.size_x - pad.size_y) > 1e-9:
                    short, long_ = min(pad.size_x, pad.size_y), max(pad.size_x, pad.size_y)
                    r = short / 2.0
                    expected = math.pi * r * r + (long_ - short) * short
                    self.assertAlmostEqual(pad.area_mm2, expected, places=6)
                    # stadyum, ayni kutuyu dolduran dikdortgenden KUCUK olmali
                    self.assertLess(pad.area_mm2, pad.size_x * pad.size_y)
                    return
        self.fail("kartta oval pad yok")

    def test_zero_size_pad_has_no_area(self):
        from pcbqa.pcb import Pad

        self.assertEqual(Pad(number="1", net="", x=0, y=0).area_mm2, 0.0)


class CopperAreaMeasurementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.board = read_board(BOARD)

    def test_total_is_the_sum_of_sources(self):
        parts = sum(
            self.board.copper_area_mm2("VCC", sources=(src,))
            for src in ("zone", "track", "pad")
        )
        self.assertAlmostEqual(self.board.copper_area_mm2("VCC"), parts, places=6)

    def test_sources_filter_works(self):
        only_pads = self.board.copper_area_mm2("VCC", sources=("pad",))
        self.assertGreater(only_pads, 0.0)
        self.assertLess(only_pads, self.board.copper_area_mm2("VCC"))

    def test_unknown_net_has_no_copper(self):
        self.assertEqual(self.board.copper_area_mm2("BOYLE_BIR_NET_YOK"), 0.0)


class CopperAreaRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.design = load_design(BOARD)
        cls.vcc = cls.design.board.copper_area_mm2("VCC")

    def test_max_area_fires_when_exceeded(self):
        """SW bakir alani <= 100 mm2 (ROHM 66AN015E) bu bicimde ifade edilir."""
        findings = run(self.design, {"net": "^VCC$", "max_mm2": self.vcc / 2})
        self.assertEqual(len(findings), 1)
        self.assertAlmostEqual(findings[0].measured, round(self.vcc, 2), places=1)

    def test_max_area_silent_when_within_budget(self):
        self.assertEqual(run(self.design, {"net": "^VCC$", "max_mm2": self.vcc * 2}), [])

    def test_min_area_fires_when_too_small(self):
        """Termal bakir alani (Richtek AN044) bu bicimde ifade edilir."""
        findings = run(self.design, {"net": "^VCC$", "min_mm2": self.vcc * 2})
        self.assertEqual(len(findings), 1)
        self.assertIn("en az", findings[0].message)

    def test_min_area_silent_when_generous(self):
        self.assertEqual(run(self.design, {"net": "^VCC$", "min_mm2": 1.0}), [])

    def test_nets_without_copper_are_skipped(self):
        """Bakiri olmayan net sessiz gecilir - min_mm2 orada yanlis alarm olurdu."""
        findings = run(self.design, {"net": ".*", "min_mm2": 10.0})
        for f in findings:
            self.assertGreater(f.measured, 0.0)

    def test_missing_bounds_rejected(self):
        with self.assertRaises(RuleError):
            run(self.design, {"net": ".*"})

    def test_empty_range_rejected(self):
        with self.assertRaises(RuleError) as ctx:
            run(self.design, {"net": ".*", "min_mm2": 100, "max_mm2": 10})
        self.assertIn("bos", str(ctx.exception))

    def test_unknown_source_rejected(self):
        with self.assertRaises(RuleError) as ctx:
            run(self.design, {"net": ".*", "max_mm2": 10, "sources": ["zone", "sihir"]})
        self.assertIn("sihir", str(ctx.exception))

    def test_layer_filter_narrows_the_measurement(self):
        both = run(self.design, {"net": "^VCC$", "max_mm2": 0.001})
        one = run(self.design, {"net": "^VCC$", "max_mm2": 0.001, "layer": "F.Cu"})
        self.assertTrue(both and one)
        self.assertLessEqual(one[0].measured, both[0].measured)
        self.assertIn("F.Cu", one[0].message)


if __name__ == "__main__":
    unittest.main()
