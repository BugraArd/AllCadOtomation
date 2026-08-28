"""`decoupling_count` kurali (TI SPRABV2 6).

Bu kural MESAFE degil ADET olcuyor - `hs-decoupling-mesafesi` ile kardes ama
farkli soru soruyor. Testler iki seyi koruyor: kaynagin konustugu yerde
konusmak, konusmadigi yerde SUSMAK.

Beklenen sayilar TI SPRABV2'den gelir (2 guc pinine 1 x 0.1 uF, ~10 guc pinine
1 x bulk), koddan turetilmez.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pcbqa.circuit import decoupling_counts
from pcbqa.harness import load_design
from pcbqa.rules import CHECKS, Rule, RuleError

ROOT = Path(__file__).resolve().parent.parent
PIC = ROOT / "samples" / "pic_programmer" / "pic_programmer.kicad_pcb"
DEMOS = Path(r"C:\Program Files\KiCad\10.0\share\kicad\demos")
# 29 guc pinli +3.3V rayi, 2 bulk - bulk esiginin ustunde kalan gercek kart
COLDFIRE = DEMOS / "kit-dev-coldfire-xilinx_5213" / "kit-dev-coldfire-xilinx_5213.kicad_pcb"
# +12V rayinda C104 "47uF/20V" - cozulemeyen ama GERCEK bir bulk kondansatoru
HIER = DEMOS / "complex_hierarchy" / "complex_hierarchy.kicad_pcb"

GROUNDS = ["GND", "AGND", "DGND", "/GND"]


def run(design, spec: dict, severity: str = "warning", ignore=GROUNDS):
    rule = Rule(
        id="dc",
        type="decoupling_count",
        severity=severity,
        spec=spec,
        ignore_nets=list(ignore),
    )
    return CHECKS["decoupling_count"](design, rule)


def ceramic(findings):
    return [f for f in findings if "seramik" in f.message]


def bulk(findings):
    return [f for f in findings if "bulk" in f.message]


class SourceRatioTests(unittest.TestCase):
    """Oranlar TI SPRABV2'nin kendi sayilari olmali."""

    def test_two_power_pins_need_one_ceramic(self):
        self.assertEqual(decoupling_counts(2)[0], 1)

    def test_twenty_power_pins_need_ten_ceramic_and_two_bulk(self):
        self.assertEqual(decoupling_counts(20), (10, 2))


class GroundExclusionTests(unittest.TestCase):
    """Toprak pinleri de `power_in` tasir - sayilsalardi gereken adet iki
    katina cikardi. TI guc TOPLARINI sayiyor, topragi degil."""

    def setUp(self):
        self.design = load_design(PIC)

    def test_ground_pins_are_not_counted_as_power_pins(self):
        with_gnd = run(self.design, {"select": {"kind": "ic"}}, ignore=[])
        without = run(self.design, {"select": {"kind": "ic"}})
        # U1'in iki `power_in` pini var (VCC_PIC + GND); toprak elenince bir.
        msg_with = next(f.message for f in ceramic(with_gnd) if f.refs == ["U1"])
        msg_without = next(f.message for f in ceramic(without) if f.refs == ["U1"])
        self.assertIn("2 guc pini", msg_with)
        self.assertIn("1 guc pini", msg_without)


class BulkFloorTests(unittest.TestCase):
    """Kaynagin birimi "~10 guc topu"; altina INMIYORUZ.

    ceil(n/10) matematiksel olarak tek guc pininde bile 1 bulk ister, ama TI
    bunu soylemiyor - o sayi tavan fonksiyonunun artifakti. Korpusta olculdu:
    esiksiz hali 19 kartin 9'unda atesliyordu, esikle 2'sinde.
    """

    def setUp(self):
        self.design = load_design(PIC)

    def test_no_bulk_finding_below_the_sources_own_unit(self):
        # pic_programmer'daki hicbir rayda 10 IC guc pini yok.
        self.assertEqual(bulk(run(self.design, {"select": {"kind": "ic"}})), [])

    def test_lowering_the_floor_makes_the_same_board_report_bulk(self):
        # Esigin GERCEKTEN susturan sey oldugunu kanitlar; kural bozuk oldugu
        # icin sessiz olsaydi bu test de sessiz kalirdi.
        found = bulk(
            run(self.design, {"select": {"kind": "ic"}, "bulk_min_power_pins": 1})
        )
        self.assertTrue(found, "esik indirilince bulk bulgusu gelmeliydi")

    def test_bulk_is_reported_per_net_not_per_component(self):
        # VCC_PIC uzerinde uc IC var (U1, U5, U6); bulgu BIR tane olmali.
        found = bulk(
            run(self.design, {"select": {"kind": "ic"}, "bulk_min_power_pins": 1})
        )
        rails = [f for f in found if "VCC_PIC" in f.message]
        self.assertEqual(len(rails), 1, "ayni ray icin birden fazla bulgu")
        self.assertEqual(sorted(rails[0].refs), ["U1", "U5", "U6"])


@unittest.skipUnless(HIER.is_file(), "KiCad demolari kurulu degil")
class ValueClassificationTests(unittest.TestCase):
    """Cozulemeyen deger HER IKI kovaya sayilir - yanlilik yon degistirmesin.

    complex_hierarchy iki rayi yan yana koyuyor ve KARSITLIK kanit sayiliyor:
      * `+12V`: tek kondansator C104, degeri "47uF/20V" ve `parse_value` bunu
        COZEMIYOR. Gercekte bir bulk kondansatorudur. Sessiz kalmali.
      * `-VAA`: hic kondansator yok. Ateslemeli.
    Ikinci ray olmasa birinci testin sessizligi "kural bozuk" ile ayirt
    edilemezdi.
    """

    @classmethod
    def setUpClass(cls):
        cls.design = load_design(HIER)
        cls.found = bulk(
            run(cls.design, {"select": {"kind": "ic"}, "bulk_min_power_pins": 1})
        )

    def test_the_value_really_is_unparseable(self):
        from pcbqa.circuit import parse_value

        self.assertEqual(self.design.value_of("C104"), "47uF/20V")
        self.assertIsNone(
            parse_value("47uF/20V"), "artik cozuluyor - bu testin dayanagi bayat"
        )

    def test_unparseable_capacitor_satisfies_the_bulk_requirement(self):
        rails = [f for f in self.found if "+12V" in f.message]
        self.assertEqual(rails, [], "cozulemeyen bulk sayilmadi - yanlilik ters dondu")

    def test_a_rail_with_no_capacitor_at_all_still_fires(self):
        rails = [f for f in self.found if "-VAA" in f.message]
        self.assertEqual(len(rails), 1, "kondansatorsuz ray sessiz kaldi - kural olu")
        self.assertEqual(rails[0].measured, 0)


class ConfigTests(unittest.TestCase):
    def test_non_positive_bulk_threshold_is_an_error(self):
        design = load_design(PIC)
        with self.assertRaisesRegex(RuleError, "bulk_min_uf"):
            run(design, {"select": {"kind": "ic"}, "bulk_min_uf": 0})

    def test_check_bulk_false_silences_only_the_bulk_half(self):
        design = load_design(PIC)
        spec = {"select": {"kind": "ic"}, "bulk_min_power_pins": 1}
        with_bulk = run(design, spec)
        without = run(design, dict(spec, check_bulk=False))
        self.assertTrue(bulk(with_bulk))
        self.assertEqual(bulk(without), [])
        self.assertEqual(len(ceramic(with_bulk)), len(ceramic(without)))


class SilenceTests(unittest.TestCase):
    """Bu projenin en onemli olcutu: gereksiz yerde susmak."""

    def setUp(self):
        self.design = load_design(PIC)

    def test_no_match_no_findings(self):
        self.assertEqual(run(self.design, {"select": {"ref": "^ASLA_ESLESMEZ"}}), [])

    def test_components_without_power_pins_are_skipped(self):
        # Direncler `power_in` tasimaz - kural onlar icin hicbir sey soylememeli.
        self.assertEqual(run(self.design, {"select": {"kind": "resistor"}}), [])

    def test_a_close_enough_capacitor_satisfies_the_ceramic_rule(self):
        """U1'in VCC_PIC pini 10.64 mm otede C6'ya (100nF) sahip.

        6.35 mm'de bulgu VAR, mesafe 12 mm'ye acilinca KALKMALI - kuralin
        gercekten mesafeye baktiginin kaniti.
        """
        near = ceramic(run(self.design, {"select": {"ref": "^U1$"}}))
        self.assertEqual(len(near), 1)
        far = ceramic(
            run(self.design, {"select": {"ref": "^U1$"}, "max_distance_mm": 12.0})
        )
        self.assertEqual(far, [], "12 mm'de C6 sayilmaliydi")

    def test_a_bulk_capacitor_does_not_satisfy_the_ceramic_requirement(self):
        """U4'un VCC rayindaki tek kondansator C1 (100 uF) - bir BULK.

        Mesafe 20 mm'ye acilsa bile seramik eksigi surmeli: 100 uF elektrolitik
        0.1 uF seramigin isini gormez, TI'in iki kovasi ayri sebeple var.
        """
        far = ceramic(
            run(self.design, {"select": {"ref": "^U4$"}, "max_distance_mm": 20.0})
        )
        self.assertEqual(len(far), 1)


@unittest.skipUnless(COLDFIRE.is_file(), "KiCad demolari kurulu degil")
class RealBoardTests(unittest.TestCase):
    """Kaynagin GERCEKTEN konustugu olcek: 29 guc pinli bir ray."""

    def test_large_rail_bulk_shortfall_is_reported(self):
        design = load_design(COLDFIRE)
        found = bulk(run(design, {"select": {"kind": "ic"}}))
        rails = [f for f in found if "+3.3V" in f.message]
        self.assertEqual(len(rails), 1)
        f = rails[0]
        # 29 guc pini -> ceil(29/10) = 3 bulk; kartta 2 var.
        self.assertEqual(f.limit, decoupling_counts(29)[1])
        self.assertEqual(f.limit, 3)
        self.assertEqual(f.measured, 2)


if __name__ == "__main__":
    unittest.main()
