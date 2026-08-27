"""Bakir kurallari: iz genisligi, via akimi, gerilim acikligi, keep_apart.

Bu testlerin en onemli olcutu SESSIZLIK: saglam bir gercek kart (KiCad'in
pic_programmer demosu) uzerinde bu kurallar yanlis alarm uretmemeli. Gelistirme
sirasinda iki kez uretti - pad once cevreleyen daireye, sonra kareye
yuvarlandigi icin - ve ikisi de burada yakalandi.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pcbqa.harness import load_design
from pcbqa.rules import CHECKS, Rule, RuleError

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
ROUTED = SAMPLES / "pic_programmer" / "pic_programmer.kicad_pcb"
UNROUTED = SAMPLES / "bench_bad.kicad_pcb"

IGNORE_GND = ["GND", "/GND", "earth"]


def run(design, rtype: str, spec: dict, severity: str = "error"):
    rule = Rule(
        id="t",
        type=rtype,
        severity=severity,
        spec=spec,
        ignore_nets=list(IGNORE_GND),
    )
    return CHECKS[rtype](design, rule)


class Boards:
    """Kartlar test basina bir kez okunur - okuma pahali."""

    _routed = None
    _unrouted = None

    @classmethod
    def routed(cls):
        if cls._routed is None:
            cls._routed = load_design(ROUTED)
        return cls._routed

    @classmethod
    def unrouted(cls):
        if cls._unrouted is None:
            cls._unrouted = load_design(UNROUTED)
        return cls._unrouted


class TraceWidthRuleTests(unittest.TestCase):
    def test_unrouted_board_is_silent(self):
        """Yerlestirme asamasinda kartta bakir yok - kural susmali."""
        findings = run(Boards.unrouted(), "trace_width", {"net": ".*", "current_a": 5.0})
        self.assertEqual(findings, [])

    def test_narrow_trace_flagged(self):
        """VCC izi 0.8 mm; 5 A icin IPC-2221 2.765 mm ister."""
        findings = run(Boards.routed(), "trace_width", {"net": "^VCC$", "current_a": 5.0})
        self.assertEqual(len(findings), 1)
        self.assertAlmostEqual(findings[0].measured, 0.8, places=3)
        self.assertAlmostEqual(findings[0].limit, 2.765, places=2)

    def test_adequate_trace_passes(self):
        """0.8 mm iz, 2 A icin IPC-2221'e (0.781 mm) gore YETERLI."""
        findings = run(Boards.routed(), "trace_width", {"net": "^VCC$", "current_a": 2.0})
        self.assertEqual(findings, [])

    def test_rohm_rule_is_stricter_than_ipc(self):
        """ROHM 1 mm/A ayni izi reddeder - belgelenen 3.3x yayilim."""
        ipc = run(Boards.routed(), "trace_width", {"net": "^VCC$", "current_a": 2.0})
        rohm = run(
            Boards.routed(),
            "trace_width",
            {"net": "^VCC$", "current_a": 2.0, "method": "mm_per_amp"},
        )
        self.assertEqual(ipc, [])
        self.assertEqual(len(rohm), 1)
        self.assertAlmostEqual(rohm[0].limit, 2.0, places=3)

    def test_delta_t_loosens_requirement(self):
        """20 C artis 10 C'ye gore daha dar ize izin verir."""
        strict = run(Boards.routed(), "trace_width", {"net": "^VCC$", "current_a": 5.0})
        loose = run(
            Boards.routed(),
            "trace_width",
            {"net": "^VCC$", "current_a": 5.0, "delta_t_c": 20.0},
        )
        self.assertGreater(strict[0].limit, loose[0].limit)

    def test_min_width_floor_applies(self):
        """Fab alt siniri, akimin gerektirdiginden buyukse o gecerli olur."""
        findings = run(
            Boards.routed(),
            "trace_width",
            {"net": "^VCC$", "current_a": 0.1, "min_width_mm": 1.5},
        )
        self.assertEqual(len(findings), 1)
        self.assertAlmostEqual(findings[0].limit, 1.5, places=3)

    def test_unrouted_net_on_routed_board_is_info(self):
        findings = run(
            Boards.routed(),
            "trace_width",
            {"net": "^BOYLE_BIR_NET_YOK$", "current_a": 1.0},
        )
        self.assertEqual(findings, [])  # net hic yok -> bulgu da yok

    def test_missing_current_rejected(self):
        with self.assertRaises(RuleError):
            run(Boards.routed(), "trace_width", {"net": ".*"})

    def test_invalid_method_rejected(self):
        with self.assertRaises(RuleError):
            run(Boards.routed(), "trace_width", {"net": ".*", "current_a": 1.0, "method": "x"})


class ViaCurrentRuleTests(unittest.TestCase):
    def test_unrouted_board_is_silent(self):
        findings = run(Boards.unrouted(), "via_current", {"net": ".*", "current_a": 10.0})
        self.assertEqual(findings, [])

    def test_low_current_passes(self):
        findings = run(Boards.routed(), "via_current", {"net": ".*", "current_a": 0.5})
        self.assertEqual(findings, [])

    def test_high_current_flagged(self):
        """0.6 mm via TI tablosunda 1.1 A'de sabitlenir; 5 A tasiyamaz."""
        findings = run(Boards.routed(), "via_current", {"net": ".*", "current_a": 5.0})
        self.assertTrue(findings)
        for f in findings:
            self.assertLess(f.measured, 5.0)

    def test_net_without_vias_skipped(self):
        """Katman degistirmeyen net icin via kurali anlamsiz - sessiz kalmali."""
        design = Boards.routed()
        no_via_nets = {
            n for n in design.net_names() if not any(v.net == n for v in design.board.vias)
        }
        self.assertTrue(no_via_nets, "via'siz net bulunamadi, test anlamsiz")
        target = sorted(no_via_nets)[0]
        findings = run(
            design, "via_current", {"net": f"^{target}$".replace("(", r"\("), "current_a": 99.0}
        )
        self.assertEqual(findings, [])

    def test_missing_current_rejected(self):
        with self.assertRaises(RuleError):
            run(Boards.routed(), "via_current", {"net": ".*"})


class ClearanceVoltageRuleTests(unittest.TestCase):
    def test_sound_board_at_logic_voltage_is_silent(self):
        """EN ONEMLI TEST: saglam kart, 5 V - hicbir bulgu olmamali.

        Bu test gelistirme sirasinda iki kez kirildi: pad'i cevreleyen daireye
        yuvarlamak 0.5 mm, kareye yuvarlamak 0.03 mm hayali ihlal uretiyordu.
        """
        findings = run(
            Boards.routed(),
            "clearance_voltage",
            {"voltages": {"^VCC$": 5.0, "^VPP$": 13.0}, "class": "B2"},
        )
        self.assertEqual(
            findings, [], f"saglam kartta yanlis alarm: {[f.message for f in findings]}"
        )

    def test_higher_voltage_finds_violation(self):
        """60 V'ta B2 sinifi 0.6 mm ister; kartta 0.37 mm var."""
        findings = run(
            Boards.routed(), "clearance_voltage", {"voltages": {"^VPP$": 60.0}, "class": "B2"}
        )
        self.assertEqual(len(findings), 1)
        self.assertAlmostEqual(findings[0].limit, 0.6, places=3)
        self.assertLess(findings[0].measured, 0.6)

    def test_mains_voltage_adds_creepage_warning(self):
        findings = run(
            Boards.routed(), "clearance_voltage", {"voltages": {"^VPP$": 400.0}, "class": "B2"}
        )
        self.assertTrue(findings)
        self.assertIn("creepage", findings[0].message)

    def test_class_changes_threshold(self):
        """B1 (ic katman) B2'den (dis, kaplamasiz) daha gevsek."""
        b1 = run(
            Boards.routed(), "clearance_voltage", {"voltages": {"^VPP$": 60.0}, "class": "B1"}
        )
        b2 = run(
            Boards.routed(), "clearance_voltage", {"voltages": {"^VPP$": 60.0}, "class": "B2"}
        )
        self.assertEqual(b1, [])
        self.assertTrue(b2)

    def test_no_declared_voltage_is_silent(self):
        findings = run(
            Boards.routed(), "clearance_voltage", {"voltages": {"^HIC_BOYLE_NET_YOK$": 400.0}}
        )
        self.assertEqual(findings, [])

    def test_empty_voltages_rejected(self):
        with self.assertRaises(RuleError):
            run(Boards.routed(), "clearance_voltage", {"voltages": {}})


class KeepApartRuleTests(unittest.TestCase):
    def test_far_requirement_flags_close_parts(self):
        findings = run(
            Boards.routed(),
            "keep_apart",
            {"a": {"kind": "inductor"}, "b": {"kind": "capacitor"}, "min_distance_mm": 200.0},
        )
        self.assertTrue(findings, "200 mm istenirse kartta ihlal olmali")
        for f in findings:
            self.assertLess(f.measured, 200.0)
            self.assertEqual(len(f.refs), 2)

    def test_tiny_requirement_is_silent(self):
        findings = run(
            Boards.routed(),
            "keep_apart",
            {"a": {"kind": "inductor"}, "b": {"kind": "capacitor"}, "min_distance_mm": 0.01},
        )
        self.assertEqual(findings, [])

    def test_pairs_reported_once(self):
        findings = run(
            Boards.routed(),
            "keep_apart",
            {"a": {"kind": "resistor"}, "b": {"kind": "resistor"}, "min_distance_mm": 500.0},
        )
        pairs = [tuple(sorted(f.refs)) for f in findings]
        self.assertEqual(len(pairs), len(set(pairs)), "ayni cift iki kez raporlanmis")

    def test_component_never_compared_with_itself(self):
        findings = run(
            Boards.routed(),
            "keep_apart",
            {"a": {"kind": "resistor"}, "b": {"kind": "resistor"}, "min_distance_mm": 500.0},
        )
        for f in findings:
            self.assertNotEqual(f.refs[0], f.refs[1])

    def test_empty_selector_is_silent(self):
        findings = run(
            Boards.routed(),
            "keep_apart",
            {"a": {"ref": "^ZZZ"}, "b": {"kind": "capacitor"}, "min_distance_mm": 50.0},
        )
        self.assertEqual(findings, [])

    def test_missing_distance_rejected(self):
        with self.assertRaises(RuleError):
            run(
                Boards.routed(),
                "keep_apart",
                {"a": {"kind": "inductor"}, "b": {"kind": "capacitor"}},
            )


class PadShapeTests(unittest.TestCase):
    """Pad sekli olcumu belirliyor - regresyon korumasi."""

    def test_circle_pad_is_point_plus_radius(self):
        design = Boards.routed()
        for comp in design.board.components:
            for pad in comp.pads:
                if pad.shape == "circle":
                    pts, radius = pad.copper_shape()
                    self.assertEqual(len(pts), 1)
                    self.assertAlmostEqual(radius, pad.size_x / 2.0, places=6)
                    return
        self.fail("kartta daire pad yok")

    def test_oval_pad_is_segment_plus_radius(self):
        design = Boards.routed()
        for comp in design.board.components:
            for pad in comp.pads:
                if pad.shape == "oval" and abs(pad.size_x - pad.size_y) > 1e-9:
                    pts, radius = pad.copper_shape()
                    self.assertEqual(len(pts), 2)
                    self.assertAlmostEqual(radius, min(pad.size_x, pad.size_y) / 2.0, places=6)
                    return
        self.fail("kartta oval pad yok")

    def test_rect_pad_is_four_corners(self):
        design = Boards.routed()
        for comp in design.board.components:
            for pad in comp.pads:
                if pad.shape in ("rect", "roundrect") and abs(pad.size_x - pad.size_y) > 1e-9:
                    pts, radius = pad.copper_shape()
                    self.assertEqual(len(pts), 4)
                    self.assertEqual(radius, 0.0)
                    return
        self.fail("kartta dikdortgen pad yok")

    def test_square_pad_treated_as_circle_is_conservative_enough(self):
        """Kare pad daireye dusurulur; yaricap KISA kenarin yarisi olmali.

        Cevreleyen daire (kosegen/2) degil - o, TO-92'de saglam karti
        ihlalli gosteriyordu.
        """
        design = Boards.routed()
        for comp in design.board.components:
            for pad in comp.pads:
                if pad.size_x > 0 and abs(pad.size_x - pad.size_y) < 1e-9:
                    _, radius = pad.copper_shape()
                    self.assertAlmostEqual(radius, pad.size_x / 2.0, places=6)
                    self.assertLess(radius, pad.radius_mm)
                    return
        self.fail("kartta kare pad yok")


if __name__ == "__main__":
    unittest.main()
