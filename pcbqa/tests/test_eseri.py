"""IEC 60063 E-serisi ve IPC-6012 performans siniflari."""

from __future__ import annotations

import math
import unittest

from pcbqa import eseri
from pcbqa.ipc2221 import IPC6012_CLASSES


class KaynakDegerleriTests(unittest.TestCase):
    """KiCad PCB Calculator E-Series sekmesindeki belgelenmis ornekler."""

    def test_bes_ohm_civari(self):
        # KiCad: enearest(5)=5.1, eup(5)=5.1, edown(5)=4.7
        self.assertAlmostEqual(eseri.nearest(5), 5.1)
        self.assertAlmostEqual(eseri.up(5), 5.1)
        self.assertAlmostEqual(eseri.down(5), 4.7)

    def test_e6_kaba_seri(self):
        # E6'da 4.6k'ya en yakin 4.7k'dir (KiCad ornegi 4.6 kOhm / E6)
        self.assertAlmostEqual(eseri.nearest(4600, "E6"), 4700.0)

    def test_seri_listeleri_eksiksiz(self):
        # Seri adindaki sayi, o seride kac deger oldugunu soyler
        for ad, degerler in eseri.E_SERIES.items():
            self.assertEqual(len(degerler), int(ad[1:]), ad)


class YonTests(unittest.TestCase):
    def test_up_asla_kucultmez(self):
        for v in (1.0, 2.38, 47.0, 999.0, 0.0047, 6.9e5):
            self.assertGreaterEqual(eseri.up(v) + 1e-12, v, v)

    def test_down_asla_buyutmez(self):
        for v in (1.0, 2.38, 47.0, 999.0, 0.0047, 6.9e5):
            self.assertLessEqual(eseri.down(v) - 1e-12, v, v)

    def test_seride_olan_deger_kendisi_doner(self):
        # Yuvarlamanin kayan noktada kaymamasi kritik: 4.7k'yi 3.9k yapamaz
        for v in (4700.0, 1.0, 100.0, 8.2e6, 0.0022):
            self.assertAlmostEqual(eseri.down(v), v, msg=f"down({v})")
            self.assertAlmostEqual(eseri.up(v), v, msg=f"up({v})")

    def test_dekat_sarmasi(self):
        # 9.5, E24'un son degeri 9.1'in ustunde -> sonraki dekatin 1.0'i
        self.assertAlmostEqual(eseri.up(9.5), 10.0)
        # 1.05, ilk degerin altinda -> onceki dekatin son degeri
        self.assertAlmostEqual(eseri.down(1.05), 1.0)

    def test_dekatlar_arasi_tutarli(self):
        # Ayni mantis her dekatta ayni sonucu vermeli
        for us in (-6, -3, 0, 3, 6):
            self.assertAlmostEqual(
                eseri.up(2.38 * 10**us) / 10**us, 2.4, places=9, msg=f"10^{us}"
            )


class HataTests(unittest.TestCase):
    def test_bilinmeyen_seri(self):
        # E96 2026-09-23'te eklendi; bu test onun yoklugunu sinamak icin
        # yazilmisti ve eklenince kirildi - istenen davranis buydu.
        with self.assertRaises(eseri.ESeriError):
            eseri.up(100, "E7")

    def test_gecersiz_deger(self):
        for kotu in (0.0, -5.0, float("inf"), float("nan")):
            with self.assertRaises(eseri.ESeriError):
                eseri.nearest(kotu)


class IPC6012Tests(unittest.TestCase):
    """KiCad PCB Calculator Board Classes sekmesindeki tablo."""

    def test_siniflar_siki_laser(self):
        # Sinif numarasi buyudukce geometri sikilasir
        onceki = None
        for ad in ("1", "2", "3", "4", "5", "6"):
            k = IPC6012_CLASSES[ad]
            if onceki is not None:
                self.assertLess(k.min_track_mm, onceki.min_track_mm, ad)
                self.assertLessEqual(k.min_clearance_mm, onceki.min_clearance_mm, ad)
            onceki = k

    def test_tablodaki_bosluklar_none(self):
        # Standart Class 1-2 icin via, Class 4-6 icin NP pad vermiyor
        self.assertIsNone(IPC6012_CLASSES["1"].via_diam_minus_drill_mm)
        self.assertIsNone(IPC6012_CLASSES["2"].via_diam_minus_drill_mm)
        self.assertIsNone(IPC6012_CLASSES["4"].np_pad_diam_minus_drill_mm)

    def test_halka_cap_farkinin_yarisi(self):
        # En kolay kacan hata: cap farkini halka sanmak (2 kat)
        k = IPC6012_CLASSES["3"]
        self.assertAlmostEqual(k.via_diam_minus_drill_mm, 0.45)
        self.assertAlmostEqual(k.via_annular_ring_mm, 0.225)
        self.assertAlmostEqual(k.plated_pad_annular_ring_mm, 0.30)

    def test_halka_yok_ise_none(self):
        self.assertIsNone(IPC6012_CLASSES["1"].via_annular_ring_mm)


if __name__ == "__main__":
    unittest.main()


class UcHaneliSeriTests(unittest.TestCase):
    """E48/E96/E192 formulden turetiliyor - turetmenin dogrulanmasi."""

    # TI TIDA-010025 uretim BOM'undaki, YALNIZCA E96'da bulunan gercek
    # degerler. Turetme bozulursa bu sayilar tutmaz.
    TIDA_E96 = (2490.0, 806.0, 3010.0)

    def test_gercek_bom_degerleri_e96da_var(self):
        for v in self.TIDA_E96:
            self.assertAlmostEqual(eseri.nearest(v, "E96"), v, msg=f"{v} E96'da yok")

    def test_bu_degerler_e24te_YOK(self):
        # Testin anlami: E96 eklemek gerekliydi, suslu degil.
        for v in self.TIDA_E96:
            self.assertNotAlmostEqual(eseri.nearest(v, "E24"), v, msg=f"{v}")

    def test_e24_onerisi_tolerans_disina_cikabilir(self):
        # 2490 icin E24 -> 2400, sapma %3.6; parcanin %1 toleransindan buyuk.
        sapma = abs(eseri.nearest(2490.0, "E24") - 2490.0) / 2490.0
        self.assertGreater(sapma, 0.01)

    def test_seriler_ic_ice(self):
        kume = {ad: set(v) for ad, v in eseri.E_SERIES.items()}
        self.assertLessEqual(kume["E48"], kume["E96"])
        self.assertLessEqual(kume["E96"], kume["E192"])

    def test_uzunluklar(self):
        for ad in ("E48", "E96", "E192"):
            self.assertEqual(len(eseri.E_SERIES[ad]), int(ad[1:]), ad)

    def test_e24_formulden_TURETILEMEZ(self):
        """2 haneli seriler tarihsel sapma icerir - elle yazilmasinin sebebi."""
        turetilmis = eseri._turet(24)
        gercek = eseri.E_SERIES["E24"]
        sapan = sum(1 for a, b in zip(turetilmis, gercek) if abs(a - b) > 1e-9)
        self.assertGreater(sapan, 15, "E24 formulle ayni cikti - varsayim degismis")


class KontrolBasinaSeriTests(unittest.TestCase):
    """Her hesap kendi tolerans sinifini beyan etmeli."""

    def test_seriler_amaca_uygun(self):
        from pcbqa import circuit

        self.assertEqual(
            circuit.i2c_pullup_range({"vdd": 3.3, "bus_capacitance_pf": 200}).series,
            "E24",
        )
        self.assertEqual(circuit.crystal_load_range({"cl_pf": 12.5}).series, "E12")
        # Cikis gerilimini belirleyen bolucu hassas olmali
        self.assertEqual(
            circuit.fb_divider_range({"vfb": 0.8, "bias_current_na": 100}).series,
            "E96",
        )
