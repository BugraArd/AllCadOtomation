"""IPC-2221B hesaplari.

Bu testlerin degeri, sayilarin BAGIMSIZ olarak dogrulanabilmesinde: beklenen
degerler docs/tasarim-kurallari/02-uretilebilirlik-ipc.md tablolarindan
aliniyor, o tablolar da yayinlanmis hesaplayicilarla capraz dogrulandi.
Formul degisirse test kirilir.
"""

from __future__ import annotations

import math
import unittest

from pcbqa.ipc2221 import (
    FAB_CLASSES,
    MIL_PER_OZ,
    MM_PER_MIL,
    clearance_mm,
    current_capacity_a,
    trace_width_mm,
    via_current_a,
)


class TraceWidthTests(unittest.TestCase):
    # (akim, dT, oz, dis_mi, beklenen_mm) - dokuman 2.3
    CASES = [
        (0.1, 10, 1.0, True, 0.013),
        (0.5, 10, 1.0, True, 0.115),
        (1.0, 10, 1.0, True, 0.300),
        (2.0, 10, 1.0, True, 0.781),
        (3.0, 10, 1.0, True, 1.367),
        (5.0, 10, 1.0, True, 2.765),
        (10.0, 10, 1.0, True, 7.194),
        (1.0, 20, 1.0, True, 0.197),
        (5.0, 20, 1.0, True, 1.816),
        (1.0, 10, 2.0, True, 0.150),
        (5.0, 10, 2.0, True, 1.383),
        (1.0, 10, 1.0, False, 0.781),
        (5.0, 10, 1.0, False, 7.194),
        (5.0, 20, 2.0, False, 2.362),
    ]

    def test_matches_published_tables(self):
        for current, dt, oz, outer, expected in self.CASES:
            with self.subTest(current=current, dt=dt, oz=oz, outer=outer):
                self.assertAlmostEqual(
                    trace_width_mm(current, dt, oz, outer), expected, places=2
                )

    def test_inner_layer_needs_2_61x_wider(self):
        """Yaygin '2 kati' ezberi yanlis: dogru oran 2^(1/0.725) = 2.601."""
        for current in (0.5, 1.0, 5.0):
            ratio = trace_width_mm(current, outer=False) / trace_width_mm(current, outer=True)
            self.assertAlmostEqual(ratio, 2.6014, places=3)

    def test_thicker_copper_needs_less_width(self):
        self.assertAlmostEqual(
            trace_width_mm(3.0, copper_oz=2.0), trace_width_mm(3.0, copper_oz=1.0) / 2.0, places=3
        )

    def test_zero_and_negative_current(self):
        self.assertEqual(trace_width_mm(0.0), 0.0)
        self.assertEqual(trace_width_mm(-1.0), 0.0)

    def test_invalid_parameters(self):
        with self.assertRaises(ValueError):
            trace_width_mm(1.0, delta_t_c=0)
        with self.assertRaises(ValueError):
            trace_width_mm(1.0, copper_oz=0)

    def test_capacity_is_inverse_of_width(self):
        for current in (0.25, 1.0, 3.0, 8.0):
            for outer in (True, False):
                width = trace_width_mm(current, outer=outer)
                self.assertAlmostEqual(
                    current_capacity_a(width, outer=outer), current, places=6
                )

    def test_capacity_zero_width(self):
        self.assertEqual(current_capacity_a(0.0), 0.0)


class ClearanceTests(unittest.TestCase):
    def test_table_6_1_rows(self):
        cases = [
            (5, "B1", 0.05),
            (12, "B2", 0.10),
            (30, "B2", 0.10),
            (31, "B2", 0.60),
            (48, "B4", 0.13),
            (100, "B3", 1.50),
            (150, "B1", 0.20),
            (170, "B2", 1.25),
            (230, "B3", 6.40),
            (300, "A7", 0.80),
            (500, "B2", 2.50),
        ]
        for voltage, klass, expected in cases:
            with self.subTest(voltage=voltage, klass=klass):
                self.assertAlmostEqual(clearance_mm(voltage, klass), expected, places=3)

    def test_boundaries_are_inclusive(self):
        """15 V hala ilk satirda, 16 V ikinci satirda olmali."""
        self.assertAlmostEqual(clearance_mm(15, "A6"), 0.13, places=3)
        self.assertAlmostEqual(clearance_mm(16, "A6"), 0.25, places=3)

    def test_above_500v_extrapolation(self):
        """Altium'un yayinladigi ornek: B1, 580 V -> 0.45 mm."""
        self.assertAlmostEqual(clearance_mm(580, "B1"), 0.45, places=3)
        # B2: 2.5 + (V-500) * 0.005
        self.assertAlmostEqual(clearance_mm(600, "B2"), 3.0, places=3)

    def test_negative_voltage_uses_magnitude(self):
        self.assertEqual(clearance_mm(-230, "B2"), clearance_mm(230, "B2"))

    def test_invalid_class(self):
        with self.assertRaises(ValueError):
            clearance_mm(12, "Z9")

    def test_outer_uncoated_is_never_tighter_than_coated(self):
        """B2 (kaplamasiz dis) hicbir gerilimde B4'ten (kaplamali) gevsek olamaz."""
        for voltage in (10, 40, 90, 140, 200, 280, 450, 700):
            self.assertGreaterEqual(
                clearance_mm(voltage, "B2"), clearance_mm(voltage, "B4"), f"{voltage} V"
            )


class FabClassTests(unittest.TestCase):
    def test_classes_get_tighter(self):
        std = FAB_CLASSES["standart"]
        cheap = FAB_CLASSES["ucuz"]
        adv = FAB_CLASSES["gelismis"]
        self.assertGreater(std.min_track_mm, cheap.min_track_mm)
        self.assertGreater(cheap.min_track_mm, adv.min_track_mm)
        self.assertGreater(std.min_drill_mm, adv.min_drill_mm)

    def test_all_values_positive(self):
        for name, fab in FAB_CLASSES.items():
            with self.subTest(name=name):
                for field in (
                    fab.min_track_mm,
                    fab.min_clearance_mm,
                    fab.min_drill_mm,
                    fab.min_annular_ring_mm,
                    fab.min_edge_clearance_mm,
                ):
                    self.assertGreater(field, 0.0)


if __name__ == "__main__":
    unittest.main()


class KiCadCaprazDogrulamaTests(unittest.TestCase):
    """Bagimsiz bir uygulamaya (KiCad PCB Calculator) karsi capraz kontrol.

    Bu sayilar KiCad 9.0 PCB Calculator ekranlarindan alindi. Formulu birisi
    "sadelestirirse" burasi bagirir; asil degeri bu.
    """

    # KiCad'in varsayilani 0.035 mm bakir kalinligi; bu ~1 oz'dur
    OZ = (0.035 / MM_PER_MIL) / MIL_PER_OZ

    def test_track_width_sekmesi(self):
        # KiCad Track Width: I=1.0 A, dT=10 C, H=0.035 mm
        for dis, beklenen in ((True, 0.300387), (False, 0.781437)):
            w = trace_width_mm(1.0, 10.0, copper_oz=self.OZ, outer=dis)
            self.assertAlmostEqual(w, beklenen, places=5, msg="dis" if dis else "ic")

    def test_via_size_sekmesi_ampacity(self):
        # KiCad Via Size: D=0.4 mm, T=0.035 mm, dT=10 C -> 2.9993 A
        # Namlu, kesiti pi*(D+T)*T olan duz bir iz gibi hesaplanir.
        D, T = 0.4, 0.035
        esdeger_genislik = math.pi * (D + T) * T / T
        akim = current_capacity_a(esdeger_genislik, 10.0, copper_oz=self.OZ, outer=True)
        self.assertAlmostEqual(akim, 2.9993, places=3)

    def test_ti_tablosu_bilincli_olarak_muhafazakar(self):
        # via_current_a TI SLVA959B'yi kullanir ve IPC-2221'den ~2-3 kat
        # dusuktur. Bu bir HATA DEGIL, guc yolu icin secilmis tutumdur;
        # biri "duzeltmeye" kalkarsa test gerekcesi hatirlatsin.
        D, T = 0.41, 0.035
        ipc = current_capacity_a(
            math.pi * (D + T) * T / T, 10.0, copper_oz=self.OZ, outer=True
        )
        ti = via_current_a(0.41)
        self.assertGreater(ipc / ti, 2.0)
        self.assertLess(ipc / ti, 3.5)
