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

from pcbqa.harness import load_design
from pcbqa.subcircuit import find_buck_converters, normalize_pin_name

ROOT = Path(__file__).resolve().parent.parent
DEMOS = Path(r"C:\Program Files\KiCad\10.0\share\kicad\demos")
BENCH = ROOT / "samples" / "bench_bad.kicad_pcb"


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


if __name__ == "__main__":
    unittest.main()
