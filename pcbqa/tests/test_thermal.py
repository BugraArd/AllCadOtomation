"""Termal hesap ve `thermal` kurali.

Beklenen degerler DOKUMANDAN alinir (Richtek AN044 4.2 tablosu), koddan
turetilmez - yoksa test yalnizca kodun kendini tekrar ettigini dogrular.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pcbqa import thermal
from pcbqa.harness import load_design
from pcbqa.rules import CHECKS, Rule, RuleError

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
ROUTED = SAMPLES / "pic_programmer" / "pic_programmer.kicad_pcb"
DEMOS = Path(r"C:\Program Files\KiCad\10.0\share\kicad\demos")
# SOT-223 TLV1117 tasiyan tek demo; tab pin 2 -> +3V3
TINYTAPEOUT = DEMOS / "tiny_tapeout" / "tinytapeout-demo.kicad_pcb"


def run(design, spec: dict, severity: str = "warning"):
    return CHECKS["thermal"](
        design, Rule(id="t", type="thermal", severity=severity, spec=spec)
    )


class CurveTests(unittest.TestCase):
    """Egri, olculen noktalardan TAM gecmeli."""

    def test_measured_points_are_reproduced_exactly(self):
        for area, expected in (
            (16.0, 135.0),
            (100.0, 107.0),
            (2500.0, 50.0),
            (3600.0, 45.0),
        ):
            self.assertAlmostEqual(
                thermal.theta_ja_c_per_w("sot223", area), expected, places=6
            )

    def test_datasheet_power_rating_is_reproduced(self):
        # AN044: 16 mm2 standart footprint -> 0.741 W @ TA=25 C, TJ=125 C
        tj = thermal.junction_temp_c("sot223", 16.0, 0.741, 25.0)
        self.assertAlmostEqual(tj, 125.0, places=1)

    def test_interpolation_is_monotonic_decreasing(self):
        prev = thermal.theta_ja_c_per_w("sot223", 10.0)
        for area in (20, 50, 100, 300, 1000, 2500, 3600, 10000):
            cur = thermal.theta_ja_c_per_w("sot223", float(area))
            self.assertLessEqual(cur, prev + 1e-9, f"{area} mm2'de egri yukseldi")
            prev = cur

    def test_clamped_outside_measured_range(self):
        # Ekstrapolasyon YAPILMAZ; iki uc da olculen degerde sabitlenir.
        self.assertEqual(thermal.theta_ja_c_per_w("sot223", 1.0), 135.0)
        self.assertEqual(thermal.theta_ja_c_per_w("sot223", 1e6), 45.0)

    def test_single_point_packages_ignore_area(self):
        for pkg, expected in (("sot23", 220.0), ("so8", 128.4), ("dfn8", 59.0)):
            self.assertFalse(thermal.is_area_dependent(pkg))
            self.assertEqual(thermal.theta_ja_c_per_w(pkg, 10.0), expected)
            self.assertEqual(thermal.theta_ja_c_per_w(pkg, 10000.0), expected)


class RequiredAreaTests(unittest.TestCase):
    """Dokumandaki iki HESAP satiri ile karsilastirma."""

    def test_room_temperature_matches_document(self):
        # AN044 belgesi: TA=25 C, TJ<=125 C -> ~120-150 mm2
        area = thermal.required_area_mm2("sot223", 1.0, 25.0, 125.0)
        self.assertTrue(120 <= area <= 150, f"{area:.0f} mm2 beklenen araligin disinda")

    def test_hot_ambient_needs_two_orders_more_copper(self):
        # Belge ~2000-2200 mm2 diyor; bu serbest okuma. Log ara degeri 1885
        # veriyor. Iki sayi da AYNI SEYI soyluyor: ~20 cm2. Test buyukluk
        # mertebesini sabitler, belgenin serbest okumasini degil.
        area = thermal.required_area_mm2("sot223", 1.0, 70.0, 125.0)
        self.assertTrue(1500 <= area <= 2500, f"{area:.0f} mm2")
        room = thermal.required_area_mm2("sot223", 1.0, 25.0, 125.0)
        self.assertGreater(area / room, 10)

    def test_refuses_to_invent_a_number_when_copper_cannot_help(self):
        # 2 W @ 70 C: olculen en buyuk alanda (45 C/W) bile Tj = 160 C.
        self.assertIsNone(thermal.required_area_mm2("sot223", 2.0, 70.0, 125.0))

    def test_no_suggestion_for_packages_without_an_area_curve(self):
        self.assertIsNone(thermal.required_area_mm2("sot23", 0.5, 25.0, 125.0))

    def test_smallest_footprint_is_enough_for_tiny_power(self):
        self.assertEqual(thermal.required_area_mm2("sot223", 0.01, 25.0, 125.0), 16.0)


class RuleConfigTests(unittest.TestCase):
    """Yapilandirma hatasi SESSIZ gecmemeli - gorunmez etkisiz kural olurdu."""

    def setUp(self):
        self.design = load_design(ROUTED)

    def test_missing_package_is_an_error(self):
        with self.assertRaises(RuleError):
            run(self.design, {"power_w": 1, "ambient_c": 25, "tj_max_c": 125})

    def test_unknown_package_is_an_error(self):
        with self.assertRaisesRegex(RuleError, "olculmus theta_JA verisi yok"):
            run(
                self.design,
                {"package": "to220", "power_w": 1, "ambient_c": 25, "tj_max_c": 125},
            )

    def test_missing_declaration_is_an_error(self):
        with self.assertRaisesRegex(RuleError, "power_w"):
            run(self.design, {"package": "sot223", "ambient_c": 25, "tj_max_c": 125})

    @unittest.skipUnless(TINYTAPEOUT.is_file(), "KiCad demolari kurulu degil")
    def test_thermal_pin_that_matches_nothing_is_an_error(self):
        """Yazim hatasi kurali SESSIZCE etkisiz birakmamali.

        Bu projede ayni sinif hata iki kez oldu (HANDOFF 21.6 pin adlari,
        21.10 bayat model yolu). 'TAB' bilhassa secildi: on ayarin kendi
        yorumu o pad'e "tab" diyor, yani yazilmasi cok olasi bir deger.
        """
        design = load_design(TINYTAPEOUT)
        with self.assertRaisesRegex(RuleError, "thermal_pin"):
            run(
                design,
                {
                    "package": "sot223",
                    "select": {"ref": "^U2$"},
                    "thermal_pin": "TAB",
                    "power_w": 2.0,
                    "ambient_c": 25.0,
                    "tj_max_c": 125.0,
                },
            )

    def test_thermal_pin_is_not_checked_when_nothing_is_selected(self):
        """Secici hicbir seye uymuyorsa sessizlik korunur - beyan denetlenmez."""
        found = run(
            self.design,
            {
                "package": "sot223",
                "select": {"ref": "^ASLA_ESLESMEZ"},
                "thermal_pin": "TAB",
                "power_w": 1,
                "ambient_c": 25,
                "tj_max_c": 125,
            },
        )
        self.assertEqual(found, [])

    def test_negative_thermal_budget_is_an_error(self):
        with self.assertRaisesRegex(RuleError, "butce negatif"):
            run(
                self.design,
                {"package": "sot223", "power_w": 1, "ambient_c": 130, "tj_max_c": 125},
            )


class SilenceTests(unittest.TestCase):
    """Bu projenin en onemli olcutu: saglam kartta sessizlik."""

    def test_no_match_no_findings(self):
        design = load_design(ROUTED)
        found = run(
            design,
            {
                "package": "sot223",
                "select": {"ref": "^ASLA_ESLESMEZ"},
                "power_w": 1,
                "ambient_c": 25,
                "tj_max_c": 125,
            },
        )
        self.assertEqual(found, [])

    def test_unconnected_thermal_tab_is_skipped_silently(self):
        # pic_programmer U3 (7805, TO-220 tabdown): en buyuk pad tab'dir ama
        # netliste bagli DEGIL. Termal yol tanimsiz - susmak dogru cevap.
        # Yerine ikinci buyuk pad'i secmek YANLIS olurdu (o VI pini).
        design = load_design(ROUTED)
        u3 = [c for c in design.board.components if c.ref == "U3"]
        self.assertTrue(u3, "U3 bulunamadi - ornek kart degismis")
        biggest = max(u3[0].pads, key=lambda p: p.area_mm2)
        self.assertEqual(
            biggest.net, "", "U3'un tab pad'i artik bagli - test varsayimi bayat"
        )
        found = run(
            design,
            {
                "package": "sot223",
                "select": {"ref": "^U3$"},
                "power_w": 5,
                "ambient_c": 25,
                "tj_max_c": 125,
            },
        )
        self.assertEqual(found, [])


@unittest.skipUnless(TINYTAPEOUT.is_file(), "KiCad demolari kurulu degil")
class RealBoardTests(unittest.TestCase):
    """Gercek SOT-223 regulator: TLV1117LV33, tab pin 2 -> +3V3."""

    @classmethod
    def setUpClass(cls):
        cls.design = load_design(TINYTAPEOUT)

    def base(self, **over):
        spec = {
            "package": "sot223",
            "select": {"ref": "^U2$"},
            "power_w": 0.3,
            "ambient_c": 25.0,
            "tj_max_c": 125.0,
        }
        spec.update(over)
        return spec

    def test_finds_the_regulator_tab_without_being_told(self):
        # thermal_pin verilmedi; en buyuk pad = tab (pin 2) secilmeli.
        found = run(self.design, self.base(power_w=2.0))
        self.assertEqual(len(found), 1)
        self.assertIn("pad 2 -> +3V3", found[0].message)

    def test_explicit_thermal_pin_agrees_with_the_automatic_choice(self):
        # "en buyuk pad" sezgisinin dogrulanmasi: elle pin 2 vermek ayni
        # sonucu vermeli. Vermeseydi sezgi yanlis pad'i seciyor olurdu.
        auto = run(self.design, self.base(power_w=2.0))
        explicit = run(self.design, self.base(power_w=2.0, thermal_pin="2"))
        self.assertEqual(len(explicit), 1)
        self.assertEqual(explicit[0].message, auto[0].message)

    def test_modest_power_is_silent(self):
        # 0.3 W: 101 mm2'de theta_JA ~107 -> Tj ~57 C. Bulgu OLMAMALI.
        self.assertEqual(run(self.design, self.base()), [])

    def test_hot_ambient_turns_the_same_board_into_a_finding(self):
        # Ayni kart, ayni bakir, yalnizca ortam degisti - kuralin esik degil
        # HESAP oldugunun kaniti.
        found = run(self.design, self.base(power_w=1.0, ambient_c=85.0))
        self.assertEqual(len(found), 1)
        self.assertGreater(found[0].measured, 125.0)
        self.assertEqual(found[0].limit, 125.0)

    def test_suggested_area_would_actually_fix_it(self):
        # 60 C ortam BILEREK secildi: 85 C'de 1 W icin gereken theta_JA 40 C/W
        # olur ve bu, olculen en iyi degerin (3600 mm2'de 45) ALTINDADIR - yani
        # o kosulda bakir eklemek matematiksel olarak yetmez. Onerinin gercekten
        # ise yaradigini sinamak icin cozulebilir bir kosul gerekiyor.
        found = run(self.design, self.base(power_w=1.0, ambient_c=60.0))
        need = thermal.required_area_mm2("sot223", 1.0, 60.0, 125.0)
        self.assertIsNotNone(need)
        self.assertIn(f"~{need:.0f} mm2", found[0].message)
        self.assertLessEqual(
            thermal.junction_temp_c("sot223", need, 1.0, 60.0), 125.0 + 1e-6
        )

    def test_refuses_to_suggest_when_copper_cannot_fix_it(self):
        # 1 W @ 85 C bile cozulemiyor: gereken 40 C/W < olculen en iyi 45 C/W.
        # Cevap "bakir ekleyin" degil "paketi degistirin" olmali.
        found = run(self.design, self.base(power_w=1.0, ambient_c=85.0))
        self.assertEqual(len(found), 1)
        self.assertIn("cozum bakir degil", found[0].message)

    def test_reported_temperature_is_declared_as_a_lower_bound(self):
        # Alan fazla tahmin ediliyor + tek isi kaynagi varsayiliyor; ikisi de
        # iyimser. Bulgu bunu gizlememeli.
        found = run(self.design, self.base(power_w=2.0))
        self.assertIn("EN AZ", found[0].message)


if __name__ == "__main__":
    unittest.main()
