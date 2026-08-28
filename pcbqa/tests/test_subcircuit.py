"""Alt-devre tanima: karttaki regulatorleri TOPOLOJIDEN bulmak.

Neden gerekli: on ayarlar net ADINA bakiyordu (`net: "^(FB|VFB)$"`). Gercek
kartlarda tutmuyor - KiCad geri besleme netini `Net-(U2-FB{slash}VSET)` diye
otomatik adlandiriyor. Ama IC'nin PIN ADI "FB/VSET" olarak duruyor.

Bu testlerin cogu KiCad demolarina bagli; kurulu degilse ATLANIR. Gercek
kartlara bagli olmalari bilincli: tanima iki kusuru da gercek veride gosterdi
(V_{IN} isaretlemesi ve buck-boost topolojisi), sentetik kartta ikisi de
gorunmezdi.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pcbqa.harness import evaluate_design, load_design
from pcbqa.rules import CHECKS, Rule, RuleError, load_rules
from pcbqa.subcircuit import find_buck_converters, normalize_pin_name

ROOT = Path(__file__).resolve().parent.parent
DEMOS = Path(r"C:\Program Files\KiCad\10.0\share\kicad\demos")
BENCH = ROOT / "samples" / "bench_bad.kicad_pcb"
PRESET = ROOT / "pcbqa" / "presets" / "buck.rules.yaml"


def demos_available() -> bool:
    return DEMOS.is_dir()


def find_demo(name: str) -> Path | None:
    hits = list(DEMOS.rglob(name)) if demos_available() else []
    return hits[0] if hits else None


class PinNameNormalisationTests(unittest.TestCase):
    """KiCad sembollerinde pin adi bicimleme isaretlemesi tasiyabilir."""

    def test_subscript(self):
        """jetson'daki TPS564247'nin VIN pini dosyada "V_{IN}" yaziyor."""
        self.assertEqual(normalize_pin_name("V_{IN}"), "VIN")

    def test_overbar_and_superscript(self):
        self.assertEqual(normalize_pin_name("~{RESET}"), "RESET")
        self.assertEqual(normalize_pin_name("A^{2}"), "A2")

    def test_plain_names_untouched(self):
        for name in ("SW", "FB/VSET", "PVIN", "BOOT"):
            with self.subTest(name=name):
                self.assertEqual(normalize_pin_name(name), name)

    def test_empty(self):
        self.assertEqual(normalize_pin_name(""), "")
        self.assertEqual(normalize_pin_name(None), "")


class NoFalsePositiveTests(unittest.TestCase):
    def test_ldo_board_has_no_switching_regulator(self):
        """bench_bad'da AP2112K var - LDO, anahtarlamali degil.

        Imza SW pini + o nette induktor. LDO'da ikisi de yok.
        """
        self.assertEqual(find_buck_converters(load_design(BENCH)), [])


@unittest.skipUnless(demos_available(), "KiCad demolari kurulu degil")
class RealBoardDetectionTests(unittest.TestCase):
    def buck_of(self, board_name: str, ic: str):
        path = find_demo(board_name)
        self.assertIsNotNone(path, f"{board_name} bulunamadi")
        found = {b.ic: b for b in find_buck_converters(load_design(path))}
        self.assertIn(ic, found, f"{ic} taninmadi (bulunanlar: {sorted(found)})")
        return found[ic]

    def test_detects_roles_on_a_real_buck(self):
        """CM5_MINIMA_3 / U702: rollerin tamami cikmalı."""
        buck = self.buck_of("CM5_MINIMA_3.kicad_pcb", "U702")
        self.assertEqual(buck.topology, "buck")
        self.assertEqual(buck.inductor, "L701")
        self.assertEqual(buck.vin_net, "+5V")
        self.assertTrue(buck.fb_net)
        self.assertTrue(buck.out_net)
        self.assertTrue(buck.cin, "giris kondansatoru bulunamadi")
        self.assertTrue(buck.cout, "cikis kondansatoru bulunamadi")
        self.assertEqual(buck.fb_resistors, ["R705", "R706"])

    def test_feedback_found_despite_generated_net_name(self):
        """One-Air-Max / U2: FB neti "Net-(U2-FB{slash}VSET)".

        Hicbir net ADI deseni bunu tutmaz; pin adindan gidildigi icin bulunuyor.
        """
        buck = self.buck_of("One-Air-Max.kicad_pcb", "U2")
        self.assertTrue(buck.fb_net)
        self.assertNotIn(buck.fb_net.upper(), ("FB", "VFB", "VSENSE"))
        self.assertEqual(buck.fb_resistors, ["R52", "R56"])

    def test_markup_in_pin_name_does_not_hide_vin(self):
        """jetson / U69: VIN pini "V_{IN}" yaziyor.

        Normalizasyon olmadan vin_net None kaliyor ve CIN listesi BOS cikiyordu -
        yani giris kondansatoru kurallari sessizce hicbir sey olcmuyordu.
        """
        buck = self.buck_of("jetson-agx-thor-baseboard.kicad_pcb", "U69")
        self.assertEqual(buck.vin_net, "+5V")
        self.assertTrue(buck.cin, "V_{IN} normalize edilmeden CIN bulunamaz")

    def test_buck_boost_is_not_mistaken_for_a_buck(self):
        """One-Air-Max / U5 (BQ25672): induktor IKI anahtar arasinda.

        Orada "diger uc" cikis DEGIL, ikinci anahtardir; out_net iddia edilmemeli.
        """
        buck = self.buck_of("One-Air-Max.kicad_pcb", "U5")
        self.assertEqual(buck.topology, "buck-boost")
        self.assertIsNone(buck.out_net, "buck-boost'ta cikis bu yolla bilinemez")

    def test_every_detection_has_the_minimal_signature(self):
        """Tanınan her devrede SW neti ve o nette bir induktor olmali."""
        for board in DEMOS.rglob("*.kicad_pcb"):
            try:
                design = load_design(board)
            except Exception:
                continue
            for buck in find_buck_converters(design):
                with self.subTest(board=board.stem, ic=buck.ic):
                    self.assertTrue(buck.sw_net)
                    self.assertIsNotNone(buck.inductor)
                    on_sw = {p.ref for p in design.pins_on_net(buck.sw_net)}
                    self.assertIn(buck.inductor, on_sw)
                    self.assertIn(buck.ic, on_sw)


class BuckLayoutRuleTests(unittest.TestCase):
    """`buck_layout` - ROHM kontrol listesi, tespit edilen rollere karsi."""

    LIMITS = {
        "cin_max_mm": 3.0,
        "sw_max_mm": 4.0,
        "cout_max_mm": 4.0,
        "fb_max_mm": 4.0,
        "sw_area_max_mm2": 100,
    }

    def run_rule(self, design, spec=None):
        # `spec or LIMITS` YAZILAMAZ: bos sozluk falsy'dir ve "esik verilmedi"
        # durumu sessizce varsayilana duserdi - tam da sinamak istedigimiz sey.
        if spec is None:
            spec = dict(self.LIMITS)
        return CHECKS["buck_layout"](
            design, Rule(id="t", type="buck_layout", severity="warning", spec=spec)
        )

    def test_silent_on_a_board_without_switching_regulators(self):
        """LDO kartinda hicbir sey tanınmaz - bulgu da olmamali."""
        self.assertEqual(self.run_rule(load_design(BENCH)), [])

    def test_at_least_one_threshold_required(self):
        with self.assertRaises(RuleError):
            self.run_rule(load_design(BENCH), spec={})

    @unittest.skipUnless(demos_available(), "KiCad demolari kurulu degil")
    def test_findings_name_the_actual_parts(self):
        """Bulgu "bir yerde bir direnc" degil, GERCEK parcayi soylemeli."""
        path = find_demo("CM5_MINIMA_3.kicad_pcb")
        findings = self.run_rule(load_design(path))
        self.assertTrue(findings)
        for f in findings:
            self.assertIn("U702", f.refs)
            self.assertIsNotNone(f.measured)
            self.assertIsNotNone(f.limit)

    @unittest.skipUnless(demos_available(), "KiCad demolari kurulu degil")
    def test_loose_thresholds_are_satisfied(self):
        """Esikler gevsetilince ayni kart temiz cikmali - olcum tutarli mi."""
        path = find_demo("CM5_MINIMA_3.kicad_pcb")
        loose = {k: (v * 10 if "max_mm" in k else v * 100) for k, v in self.LIMITS.items()}
        self.assertEqual(self.run_rule(load_design(path), loose), [])

    @unittest.skipUnless(demos_available(), "KiCad demolari kurulu degil")
    def test_the_rohm_checklist_contradicts_itself_on_small_packages(self):
        """ROHM'un uc esigi kucuk paketlerde AYNI ANDA saglanamaz.

        FB direnci FB pinine <= 4 mm (#4-2) ve induktor SW pinine <= 4 mm
        (Oncelik 2) ise, ucgen esitsizligiyle:
            FB <-> L  <=  4 + (IC ici SW-FB pin ayrimi) + 4
        One-Air-Max U6'da pin ayrimi 1.20 mm -> ust sinir 9.20 mm < 10 mm.
        Yani #4-1'in istedigi ">= 10 mm" MATEMATIKSEL OLARAK imkansiz.

        Bu yuzden on ayarda `fb_inductor_min_mm` verilmiyor. Test o kararin
        gerekcesini korur.
        """
        import math

        from pcbqa.rules import _pin_xy

        design = load_design(find_demo("One-Air-Max.kicad_pcb"))
        buck = {b.ic: b for b in find_buck_converters(design)}["U6"]
        sw = _pin_xy(design, buck.ic, buck.sw_net)
        fb = _pin_xy(design, buck.ic, buck.fb_net)
        self.assertIsNotNone(sw)
        self.assertIsNotNone(fb)
        pin_gap = math.hypot(sw[0] - fb[0], sw[1] - fb[1])
        upper_bound = 4.0 + pin_gap + 4.0
        self.assertLess(
            upper_bound,
            10.0,
            f"pin ayrimi {pin_gap:.2f} mm -> ust sinir {upper_bound:.2f} mm; "
            "10 mm ulasilabilir gorunuyor, on ayardaki gerekce gozden gecirilmeli",
        )


@unittest.skipUnless(demos_available(), "KiCad demolari kurulu degil")
class BuckPresetTests(unittest.TestCase):
    """On ayar artik UYARLAMA GEREKTIRMEDEN gercek kartlarda calisiyor."""

    def test_preset_is_precise_on_real_boards(self):
        """Ad desenleriyle 19-32 bulgu cikiyordu; topolojiyle bir avuc.

        Olculdu: CM5_MINIMA 19 -> 1, One-Air-Max 32 -> 4.
        """
        rules = load_rules(PRESET)
        for name, limit in (("CM5_MINIMA_3", 3), ("One-Air-Max", 8)):
            with self.subTest(board=name):
                design = load_design(find_demo(f"{name}.kicad_pcb"))
                ev = evaluate_design(design, rules)
                real = [f for f in ev.findings if f.severity != "info"]
                self.assertLessEqual(
                    len(real), limit, f"kesinlik geriledi: {[f.message for f in real]}"
                )

    def test_preset_is_silent_on_a_board_without_bucks(self):
        rules = load_rules(PRESET)
        ev = evaluate_design(load_design(BENCH), rules)
        self.assertEqual([f for f in ev.findings if f.severity != "info"], [])


if __name__ == "__main__":
    unittest.main()
