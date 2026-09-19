"""Parca tablosu: ag, gerilim, akim, MPN, fiyat.

Bu modulun sinandigi sey DOGRU SAYI degil, DOGRU SUSKUNLUK: turetilemeyen
bir akimin yerine bir tahmin yazilmamasi. Testlerin cogu bir hucrenin BOS
kaldigini ve NEDENININ yazildigini korur.
"""

from __future__ import annotations

import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from pcbqa import symlib
from pcbqa.elektrik import (
    BASLIKLAR,
    Satir,
    _akim,
    _gerilim,
    ag_metni,
    bagli_mi,
    csv_yaz,
    metin_tablosu,
    ozet,
    ray_gerilimi,
    tablo,
)
from pcbqa.kicadcli import KicadCliError, find_kicad_cli

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
PIC = SAMPLES / "pic_programmer" / "pic_programmer.kicad_sch"


def kicad_available() -> bool:
    try:
        find_kicad_cli()
        symlib.get_symbol("Device:R")
        return True
    except (KicadCliError, symlib.SymLibError):
        return False


def _satir(onek: str, deger: str, *baglantilar: tuple[str, str]) -> Satir:
    """Test icin elle bir satir; gerilimler ag ADINDAN turetilir."""
    s = Satir(ref=f"{onek}1", deger=deger, onek=onek)
    for pin, ag in baglantilar:
        volt, _ = ray_gerilimi(ag)
        s.baglantilar.append((pin, ag, volt))
    s.gerilim_v, s.gerilim_kaynak = _gerilim(s)
    s.akim_a, s.akim_kaynak = _akim(s)
    return s


# --------------------------------------------------------------------------
# Ray gerilimi
# --------------------------------------------------------------------------


class RayTests(unittest.TestCase):
    def test_kicad_power_names_are_evidence(self):
        """"+3V3" adli bir agi 3.3 V saymak tahmin degil, adi okumaktir."""
        self.assertEqual(ray_gerilimi("+3V3")[0], 3.3)
        self.assertEqual(ray_gerilimi("+5V")[0], 5.0)
        self.assertEqual(ray_gerilimi("+1V8")[0], 1.8)
        self.assertEqual(ray_gerilimi("+3.3V")[0], 3.3)

    def test_negative_rails_keep_their_sign(self):
        self.assertEqual(ray_gerilimi("-12V")[0], -12.0)
        self.assertEqual(ray_gerilimi("-5V")[0], -5.0)

    def test_ground_family_is_the_reference_node(self):
        for ad in ("GND", "gnd", "AGND", "VSS", "0V"):
            with self.subTest(ad):
                volt, neden = ray_gerilimi(ad)
                self.assertEqual(volt, 0.0)
                self.assertIn("referans", neden)

    def test_vcc_and_vdd_say_nothing_and_admit_it(self):
        """En onemli test: "VCC 5V'tur" varsayimi 3.3 V'luk kartta yanlis
        akim hesaplatirdi."""
        for ad in ("VCC", "VDD", "VIN", "VREF"):
            with self.subTest(ad):
                volt, neden = ray_gerilimi(ad)
                self.assertIsNone(volt)
                self.assertIn("soylemiyor", neden)

    def test_vbus_is_known_from_a_cited_spec(self):
        volt, neden = ray_gerilimi("VBUS")
        self.assertEqual(volt, 5.0)
        self.assertIn("USB 2.0", neden)

    def test_a_compound_name_is_resolved_from_its_parts(self):
        self.assertEqual(ray_gerilimi("VDD_3V3")[0], 3.3)
        self.assertEqual(ray_gerilimi("3V3_MCU")[0], 3.3)

    def test_a_signal_net_has_no_voltage(self):
        for ad in ("SDA", "Net-(R1-Pad2)", "/SWDIO", ""):
            with self.subTest(ad):
                self.assertIsNone(ray_gerilimi(ad)[0])

    def test_kicad_unconnected_names_are_not_nets(self):
        self.assertFalse(bagli_mi("unconnected-(R2-Pad1)"))
        self.assertTrue(bagli_mi("GND"))
        self.assertEqual(ag_metni("unconnected-(R2-Pad1)"), "(bagli degil)")


# --------------------------------------------------------------------------
# Akim
# --------------------------------------------------------------------------


class AkimTests(unittest.TestCase):
    def test_a_resistor_between_two_known_rails_is_ohms_law(self):
        s = _satir("R", "10k", ("1", "+3V3"), ("2", "GND"))
        self.assertAlmostEqual(s.akim_a, 3.3 / 10000)
        self.assertIn("Ohm yasasi", s.akim_kaynak)
        self.assertEqual(s.akim_metni(), "330 uA")

    def test_a_resistor_with_an_unknown_rail_stays_empty(self):
        s = _satir("R", "10k", ("1", "VCC"), ("2", "GND"))
        self.assertIsNone(s.akim_a)
        self.assertIn("bilinmiyor", s.akim_kaynak)
        self.assertEqual(s.akim_metni(), "-")

    def test_a_resistor_whose_value_is_unreadable_stays_empty(self):
        s = _satir("R", "R", ("1", "+5V"), ("2", "GND"))
        self.assertIsNone(s.akim_a)
        self.assertIn("okunamadi", s.akim_kaynak)

    def test_a_zero_ohm_link_is_refused_not_divided_by(self):
        s = _satir("R", "0", ("1", "+5V"), ("2", "GND"))
        self.assertIsNone(s.akim_a)
        self.assertIn("sifir", s.akim_kaynak)

    def test_a_capacitor_passes_no_dc_and_that_is_a_definition(self):
        s = _satir("C", "100nF", ("1", "+3V3"), ("2", "GND"))
        self.assertEqual(s.akim_a, 0.0)
        self.assertEqual(s.akim_metni(), "~0")
        self.assertIn("kararli halde", s.akim_kaynak)

    def test_an_active_part_asks_for_a_simulator(self):
        s = _satir("U", "STM32", ("1", "+3V3"), ("2", "GND"))
        self.assertIsNone(s.akim_a)
        self.assertIn("benzetim", s.akim_kaynak)

    def test_an_unconnected_pin_is_named_as_the_reason(self):
        s = _satir("R", "10k", ("1", "unconnected-(R1-Pad1)"), ("2", "GND"))
        self.assertIsNone(s.akim_a)
        self.assertIn("baglanmamis pin: 1", s.akim_kaynak)

    def test_voltage_across_a_two_pin_part(self):
        s = _satir("R", "1k", ("1", "+5V"), ("2", "GND"))
        self.assertEqual(s.gerilim_v, 5.0)
        self.assertEqual(s.gerilim_metni(), "5 V")

    def test_current_units_scale(self):
        self.assertEqual(_satir("R", "1", ("1", "+5V"), ("2", "GND")).akim_metni(),
                         "5 A")
        self.assertEqual(_satir("R", "1k", ("1", "+5V"), ("2", "GND")).akim_metni(),
                         "5 mA")


# --------------------------------------------------------------------------
# Bicimlendirme
# --------------------------------------------------------------------------


class TabloBicimTests(unittest.TestCase):
    def setUp(self):
        self.satirlar = [
            _satir("R", "10k", ("1", "+3V3"), ("2", "GND")),
            _satir("C", "100nF", ("1", "+3V3"), ("2", "GND")),
        ]

    def test_text_table_has_a_header_for_every_column(self):
        metin = metin_tablosu(self.satirlar)
        basliklar = metin.splitlines()[0]
        for ad in BASLIKLAR:
            self.assertIn(ad, basliklar)

    def test_csv_round_trips(self):
        tmp = Path(tempfile.mkdtemp(prefix="pcbqa-elektrik-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        hedef = csv_yaz(self.satirlar, tmp / "tablo.csv")
        with hedef.open(encoding="utf-8-sig", newline="") as f:
            satirlar = list(csv.reader(f, delimiter=";"))
        self.assertEqual(satirlar[0], BASLIKLAR)
        self.assertEqual(len(satirlar), 3)

    def test_summary_counts_what_is_known(self):
        o = ozet(self.satirlar)
        self.assertEqual(o["parca"], 2)
        self.assertEqual(o["akimi_turetilebilen"], 2)  # direnc + kondansator


# --------------------------------------------------------------------------
# Gercek kart
# --------------------------------------------------------------------------


@unittest.skipUnless(kicad_available(), "KiCad kurulu degil")
class GercekKartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Netlist ihraci pahali - kart bir kez okunur.
        cls.satirlar = tablo(PIC)

    def test_the_board_produces_a_row_per_real_component(self):
        self.assertGreater(len(self.satirlar), 20)
        self.assertTrue(all(not s.ref.startswith("#") for s in self.satirlar))

    def test_ground_pins_are_recognised_as_zero_volts(self):
        gnd = [s for s in self.satirlar
               if any(a.upper().lstrip("/") == "GND" for _, a, _ in s.baglantilar)]
        self.assertTrue(gnd, "kartta GND'ye bagli parca bulunamadi")
        for s in gnd:
            for _pin, ag, volt in s.baglantilar:
                if ag.upper().lstrip("/") == "GND":
                    self.assertEqual(volt, 0.0)

    def test_every_row_without_a_current_says_why(self):
        """Bos hucrenin yaninda sebep yoksa kullanici hatamizi goremez."""
        for s in self.satirlar:
            if s.akim_a is None:
                with self.subTest(s.ref):
                    self.assertTrue(s.akim_kaynak, f"{s.ref}: sebep yazilmamis")

    def test_a_zero_valued_part_gets_no_price(self):
        """samples/pic_programmer C4'un degeri "0" - fiyat uydurulmaz.

        Bu satir bir zamanlar `math domain error` ile cokuyordu (log10(0)).
        """
        c4 = next((s for s in self.satirlar if s.ref == "C4"), None)
        self.assertIsNotNone(c4)
        self.assertIsNone(c4.fiyat)


if __name__ == "__main__":
    unittest.main()
