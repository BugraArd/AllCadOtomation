"""Devre dogrulugu hesaplari (`pcbqa/circuit.py`).

Kural motoru simdiye kadar geometriyi ve bakiri olcuyordu; hicbiri "bu pull-up
4k7, 400 pF bus icin dogru mu" sorusunu soramiyordu.

Beklenen degerler docs/tasarim-kurallari/ altindaki kaynaklardan alindi
(NXP UM10204, Microchip AN826, Richtek AN033, TI SPRABV2).
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pcbqa.circuit import (
    CRYSTAL_STRAY_C_MAX_F,
    CRYSTAL_STRAY_C_MIN_F,
    I2C_MAX_BUS_CAPACITANCE_F,
    ValueRange,
    crystal_load_capacitor_f,
    crystal_load_capacitor_range_f,
    decoupling_counts,
    fb_divider_max_bottom_ohms,
    i2c_needs_current_source,
    i2c_pullup_max_ohms,
    i2c_pullup_min_ohms,
    parse_value,
)
from pcbqa.harness import load_design
from pcbqa.rules import CHECKS, Rule, RuleError

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "samples" / "bench_bad.kicad_pcb"


class ParseValueTests(unittest.TestCase):
    """KiCad deger alanlari duzensizdir; ayristirici bunu yutmali."""

    def test_rkm_code(self):
        """IEC 60062: carpan harfi ONDALIK NOKTANIN yerine gecer."""
        cases = {
            "4k7": 4700.0,
            "1R0": 1.0,
            "2M2": 2.2e6,
            "4K7": 4700.0,
            "1n5": 1.5e-9,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertAlmostEqual(parse_value(text), expected, places=12)

    def test_plain_with_multiplier(self):
        cases = {
            "4.7k": 4700.0,
            "100n": 100e-9,
            "22p": 22e-12,
            "0.1u": 0.1e-6,
            "10M": 10e6,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertAlmostEqual(parse_value(text), expected, places=15)

    def test_unit_suffix_is_ignored(self):
        for text in ("100nF", "4700R", "10uF", "4700ohm"):
            with self.subTest(text=text):
                self.assertIsNotNone(parse_value(text))
        self.assertAlmostEqual(parse_value("100nF"), 100e-9, places=15)
        self.assertAlmostEqual(parse_value("4700R"), 4700.0, places=9)

    def test_bare_number(self):
        self.assertEqual(parse_value("4700"), 4700.0)
        self.assertEqual(parse_value("0"), 0.0)

    def test_trailing_junk_is_dropped(self):
        """Deger alanina gerilim/tolerans/paket yazmak yaygin."""
        self.assertAlmostEqual(parse_value("100nF 50V X7R 0603"), 100e-9, places=15)
        self.assertAlmostEqual(parse_value("4k7 1%"), 4700.0, places=9)

    def test_case_matters_for_milli_and_mega(self):
        """'M' mega, 'm' mili. Karistirmak 10^9 kat hata demek."""
        self.assertAlmostEqual(parse_value("2M2"), 2.2e6, places=3)
        self.assertAlmostEqual(parse_value("2m2"), 2.2e-3, places=9)

    def test_not_fitted_is_none(self):
        for text in ("DNP", "dnp", "-", "", "   ", "?"):
            with self.subTest(text=text):
                self.assertIsNone(parse_value(text))

    def test_package_code_is_not_a_value(self):
        """Ozensiz kutuphanelerde deger alanina paket kodu yaziliyor.

        "0603" duz sayi olarak 603 ohm diye ayristirilirdi ve 1k-10k bekleyen
        bir kural yanlis alarm verirdi. Kimse 603 ohm'u "0603" diye yazmaz.
        """
        for text in ("0402", "0603", "0805", "1206"):
            with self.subTest(text=text):
                self.assertIsNone(parse_value(text))
        # ama acikca birim yazilmissa deger olarak kabul edilir
        self.assertEqual(parse_value("603R"), 603.0)

    def test_unparseable_is_none_not_an_error(self):
        """Deger alanina serbest metin yazmak yaygin; hata saymak gurultu uretir."""
        for text in ("abc", "MCP1700", "~", "TBD"):
            with self.subTest(text=text):
                self.assertIsNone(parse_value(text))

    def test_none_input(self):
        self.assertIsNone(parse_value(None))


class I2CPullupTests(unittest.TestCase):
    """NXP UM10204 7.1."""

    def test_max_from_rise_time_budget(self):
        # Rp(max) = tr / (0.8473 * Cb); fast mode tr = 300 ns
        self.assertAlmostEqual(
            i2c_pullup_max_ohms(200e-12, "fast"), 300e-9 / (0.8473 * 200e-12), places=3
        )

    def test_tighter_mode_allows_smaller_resistor(self):
        cb = 100e-12
        self.assertGreater(
            i2c_pullup_max_ohms(cb, "standard"), i2c_pullup_max_ohms(cb, "fast")
        )
        self.assertGreater(
            i2c_pullup_max_ohms(cb, "fast"), i2c_pullup_max_ohms(cb, "fast_plus")
        )

    def test_min_from_driver_current(self):
        # (VDD - VOL) / IOL = (3.3 - 0.4) / 3 mA
        self.assertAlmostEqual(i2c_pullup_min_ohms(3.3), 2.9 / 3e-3, places=6)

    def test_higher_supply_needs_bigger_minimum(self):
        self.assertGreater(i2c_pullup_min_ohms(5.0), i2c_pullup_min_ohms(3.3))

    def test_spec_limit_is_400pf(self):
        self.assertEqual(I2C_MAX_BUS_CAPACITANCE_F, 400e-12)

    def test_at_the_spec_limit_a_plain_resistor_is_impossible(self):
        """Formuller UM10204'un KENDI sonucunu bagimsiz olarak uretiyor.

        400 pF fast-mode'da min (967 ohm) > max (885 ohm): duz dirençle
        cozulemez. UM10204 tam bunu soyluyor - 200 pF ustunde akim kaynagi ya da
        anahtarlamali direnc devresi gerekir.
        """
        low = i2c_pullup_min_ohms(3.3)
        high = i2c_pullup_max_ohms(400e-12, "fast")
        self.assertGreater(low, high, "400 pF'de duz direnc calisiyor gorunuyor")
        self.assertTrue(i2c_needs_current_source(400e-12))

    def test_current_source_threshold_is_200pf(self):
        self.assertFalse(i2c_needs_current_source(150e-12))
        self.assertTrue(i2c_needs_current_source(250e-12))

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            i2c_pullup_max_ohms(0)
        with self.assertRaises(ValueError):
            i2c_pullup_max_ohms(100e-12, "ultra")
        with self.assertRaises(ValueError):
            i2c_pullup_min_ohms(0.2)


class CrystalLoadTests(unittest.TestCase):
    """Microchip AN826: CL = C/2 + Cstray, stray 2-5 pF."""

    def test_standard_formula(self):
        # CL = 12 pF, stray 3 pF -> C = 2*(12-3) = 18 pF (yaygin secim)
        self.assertAlmostEqual(
            crystal_load_capacitor_f(12e-12, 3e-12), 18e-12, places=15
        )

    def test_range_brackets_the_common_choice(self):
        low, high = crystal_load_capacitor_range_f(12e-12)
        self.assertAlmostEqual(low, 14e-12, places=15)
        self.assertAlmostEqual(high, 20e-12, places=15)
        self.assertLess(low, 18e-12)
        self.assertGreater(high, 18e-12)

    def test_more_stray_means_smaller_capacitor(self):
        """Stray buyudukce gereken kondansator KUCULUR - aralik yonu bundan."""
        big_stray = crystal_load_capacitor_f(20e-12, CRYSTAL_STRAY_C_MAX_F)
        small_stray = crystal_load_capacitor_f(20e-12, CRYSTAL_STRAY_C_MIN_F)
        self.assertLess(big_stray, small_stray)

    def test_cl_below_stray_is_rejected(self):
        with self.assertRaises(ValueError):
            crystal_load_capacitor_f(1e-12, 5e-12)


class FeedbackDividerTests(unittest.TestCase):
    """Richtek AN033: bolucu akimi >= 100 x FB bias akimi."""

    def test_upper_bound(self):
        # Vfb 0.8 V, Ibias 100 nA -> R2 <= 0.8 / (100 * 100n) = 80 kohm
        self.assertAlmostEqual(
            fb_divider_max_bottom_ohms(0.8, 100e-9), 80e3, places=6
        )

    def test_smaller_bias_allows_bigger_resistor(self):
        self.assertGreater(
            fb_divider_max_bottom_ohms(0.8, 10e-9),
            fb_divider_max_bottom_ohms(0.8, 100e-9),
        )

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            fb_divider_max_bottom_ohms(0, 100e-9)
        with self.assertRaises(ValueError):
            fb_divider_max_bottom_ohms(0.8, 0)


class DecouplingCountTests(unittest.TestCase):
    """TI SPRABV2 6: her 2 guc topu icin 0.1 uF, her ~10 icin bulk."""

    def test_counts(self):
        self.assertEqual(decoupling_counts(0), (0, 0))
        self.assertEqual(decoupling_counts(1), (1, 1))
        self.assertEqual(decoupling_counts(2), (1, 1))
        self.assertEqual(decoupling_counts(3), (2, 1))
        self.assertEqual(decoupling_counts(20), (10, 2))

    def test_negative_is_zero(self):
        self.assertEqual(decoupling_counts(-5), (0, 0))


class ValueRangeTests(unittest.TestCase):
    def test_two_sided(self):
        r = ValueRange(low=1000.0, high=2000.0, source="t")
        self.assertTrue(r.contains(1500.0))
        self.assertFalse(r.contains(999.0))
        self.assertFalse(r.contains(2001.0))

    def test_open_ended(self):
        upper_only = ValueRange(low=None, high=80e3, source="t")
        self.assertTrue(upper_only.contains(1.0))
        self.assertFalse(upper_only.contains(90e3))

    def test_boundaries_are_inclusive(self):
        r = ValueRange(low=10.0, high=20.0, source="t")
        self.assertTrue(r.contains(10.0))
        self.assertTrue(r.contains(20.0))


class ComponentValueRuleTests(unittest.TestCase):
    """`component_value` kural tipi - hesabi devreye baglar.

    bench_bad kartinda gercek bir I2C durumu var:
      R1 (4k7) -> 3V3 / SDA      pull-up
      R2 (4k7) -> 3V3 / SCL      pull-up
      R4 (22R) -> USB_DM         seri direnc, I2C DEGIL
      R5 (22R) -> USB_DP         seri direnc, I2C DEGIL
      C7/C8 (22pF)               kristal yuk kondansatoru
    """

    @classmethod
    def setUpClass(cls):
        cls.design = load_design(BENCH)

    def run_rule(self, spec: dict, severity: str = "warning"):
        rule = Rule(id="t", type="component_value", severity=severity, spec=spec)
        return CHECKS["component_value"](self.design, rule)

    def test_on_net_narrows_to_the_right_components(self):
        """Filtre olmadan USB seri dirençleri de yakalanir - `on_net` bunu ayirir."""
        without = self.run_rule(
            {
                "select": {"kind": "resistor"},
                "check": "i2c_pullup",
                "params": {"vdd": 3.3, "bus_capacitance_pf": 200},
            }
        )
        with_net = self.run_rule(
            {
                "select": {"kind": "resistor"},
                "on_net": "(SDA|SCL)",
                "check": "i2c_pullup",
                "params": {"vdd": 3.3, "bus_capacitance_pf": 200},
            }
        )
        self.assertEqual({f.refs[0] for f in without}, {"R1", "R2", "R4", "R5"})
        self.assertEqual({f.refs[0] for f in with_net}, {"R1", "R2"})

    def test_pullup_too_large_for_the_bus(self):
        """4k7, 200 pF fast-mode icin fazla buyuk (max ~1770 ohm)."""
        findings = self.run_rule(
            {
                "select": {"kind": "resistor"},
                "on_net": "(SDA|SCL)",
                "check": "i2c_pullup",
                "params": {"vdd": 3.3, "bus_capacitance_pf": 200},
            }
        )
        self.assertEqual(len(findings), 2)
        for f in findings:
            self.assertAlmostEqual(f.measured, 4700.0, places=6)
            self.assertIn("UM10204", f.message)

    def test_pullup_fine_on_a_light_bus(self):
        """Ayni 4k7, 50 pF'lik hafif bir bus'ta sorunsuz."""
        findings = self.run_rule(
            {
                "select": {"kind": "resistor"},
                "on_net": "(SDA|SCL)",
                "check": "i2c_pullup",
                "params": {"vdd": 3.3, "bus_capacitance_pf": 50},
            }
        )
        self.assertEqual(findings, [])

    def test_explicit_bounds_accept_rkm_strings(self):
        """Sinirlar "1k"/"10k" gibi yazilabilmeli; farad'i ondalikla yazmak eziyet."""
        findings = self.run_rule(
            {"select": {"kind": "resistor"}, "on_net": "(SDA|SCL)", "min": "1k", "max": "10k"}
        )
        self.assertEqual(findings, [])
        tight = self.run_rule(
            {"select": {"kind": "resistor"}, "on_net": "(SDA|SCL)", "min": "1k", "max": "2k"}
        )
        self.assertEqual(len(tight), 2)

    def test_crystal_load_capacitors(self):
        findings = self.run_rule(
            {"select": {"kind": "capacitor"}, "check": "crystal_load", "params": {"cl_pf": 12}}
        )
        self.assertTrue(findings)
        self.assertIn("AN826", findings[0].message)

    def test_unparseable_values_are_skipped_silently(self):
        """Deger alanina serbest metin yazmak yaygin - hata degil, sessiz gecis."""
        findings = self.run_rule(
            {"select": {"kind": "ic"}, "min": "1k", "max": "10k"}
        )
        self.assertEqual(findings, [], "IC degerleri sayi degil, atlanmaliydi")

    def test_empty_range_is_reported_not_swallowed(self):
        """400 pF fast-mode'da duz direncle COZUM YOK - kural bunu soylemeli.

        Sessizce gecmek, kurali gorunmez bicimde etkisiz birakirdi.
        """
        findings = self.run_rule(
            {
                "select": {"kind": "resistor"},
                "check": "i2c_pullup",
                "params": {"vdd": 3.3, "bus_capacitance_pf": 400},
            }
        )
        self.assertEqual(len(findings), 1)
        self.assertIn("BOS", findings[0].message)
        self.assertIn("cozum yok", findings[0].message)

    def test_missing_declaration_is_a_config_error(self):
        """Eksik BEYAN, eksik olcum degildir - sessiz gecmemeli."""
        with self.assertRaises(RuleError) as ctx:
            self.run_rule(
                {"select": {"kind": "resistor"}, "check": "i2c_pullup", "params": {"vdd": 3.3}}
            )
        self.assertIn("bus_capacitance_pf", str(ctx.exception))

    def test_unknown_check_rejected(self):
        with self.assertRaises(RuleError) as ctx:
            self.run_rule({"select": {"kind": "resistor"}, "check": "sihirli_hesap"})
        self.assertIn("sihirli_hesap", str(ctx.exception))

    def test_no_bounds_at_all_rejected(self):
        with self.assertRaises(RuleError):
            self.run_rule({"select": {"kind": "resistor"}})

    def test_unparseable_bound_rejected(self):
        with self.assertRaises(RuleError) as ctx:
            self.run_rule({"select": {"kind": "resistor"}, "min": "cok buyuk"})
        self.assertIn("min", str(ctx.exception))

    def test_findings_carry_measurement_for_scaling(self):
        """measured/limit dolu olmali ki `scale: true` calisabilsin."""
        findings = self.run_rule(
            {"select": {"kind": "resistor"}, "on_net": "(SDA|SCL)", "max": "1k"}
        )
        self.assertTrue(findings)
        for f in findings:
            self.assertIsNotNone(f.measured)
            self.assertIsNotNone(f.limit)


if __name__ == "__main__":
    unittest.main()
