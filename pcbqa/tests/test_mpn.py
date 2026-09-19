"""Sentetik MPN ve fiyat alanlari.

Bu modul sematige TEDARIK VERISI yaziyor ve o veri UYDURMA. En buyuk risk
teknik degil: birinin bu fiyatlari gercek sanmasi. Korunanlar:

  * her MPN `SENT-` ile baslar ve her sembolde `MPN_Kaynak=sentetik-test` olur,
  * fiyat degerle ARTAR - istenen degismez bu ve bir susleme onu bozmamali,
  * degeri okunamayan bilesene fiyat ATANMAZ.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from pcbqa import mpn
from pcbqa.schematic import read_schematic

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
UC_PARCA = SAMPLES / "uc_parca" / "uc_parca.kicad_sch"


class ValueParsingTests(unittest.TestCase):
    def test_si_prefixes(self):
        self.assertAlmostEqual(mpn.parse_value("10uF"), 1e-5)
        self.assertAlmostEqual(mpn.parse_value("5k"), 5000.0)
        self.assertAlmostEqual(mpn.parse_value("100n"), 1e-7)
        self.assertAlmostEqual(mpn.parse_value("4.7"), 4.7)

    def test_unparseable_value_is_none_not_a_guess(self):
        for kotu in ("C", "R", "", "abc", "??"):
            with self.subTest(kotu):
                self.assertIsNone(mpn.parse_value(kotu))


class SyntheticMarkerTests(unittest.TestCase):
    """Uydurma veri UYDURMA GORUNMELI."""

    def test_every_mpn_is_marked_synthetic(self):
        for deger in ("1uF", "10uF", "100n", "5k"):
            for part in mpn.candidates("C", deger):
                with self.subTest(f"{deger} {part.mpn}"):
                    self.assertTrue(part.mpn.startswith("SENT-"),
                                    f"{part.mpn} sentetik gorunmuyor")

    def test_manufacturers_are_not_real_companies(self):
        gercek = {"murata", "tdk", "samsung", "kemet", "vishay", "yageo",
                  "panasonic", "nichicon", "wurth", "avx"}
        for ad in mpn.URETICILER:
            self.assertNotIn(ad.lower(), gercek,
                             f"{ad} gercek bir firma adina benziyor")

    def test_source_field_constant_is_used(self):
        self.assertEqual(mpn.KAYNAK_DEGERI, "sentetik-test")


class PricingTests(unittest.TestCase):
    def test_price_rises_with_value(self):
        """Istenen degismez: buyuk deger daha pahali.

        Olculdu: ilk iki surumde "gercekci dursun" diye eklenen deterministik
        sapma bu siralamayi BOZUYORDU - C10 (45uF), C9'dan (40uF) ucuz cikti.
        Fiyat artik saf bir (deger, paket) fonksiyonu.
        """
        degerler = ["5uF", "10uF", "15uF", "20uF", "25uF",
                    "30uF", "35uF", "40uF", "45uF", "50uF"]
        fiyatlar = [mpn.candidates("C", d)[0].price for d in degerler]
        for onceki, sonraki, d1, d2 in zip(fiyatlar, fiyatlar[1:],
                                           degerler, degerler[1:]):
            self.assertLess(onceki, sonraki,
                            f"{d1} ({onceki}) >= {d2} ({sonraki}) - siralama bozuk")

    def test_candidates_are_sorted_cheapest_first(self):
        fiyatlar = [p.price for p in mpn.candidates("C", "10uF")]
        self.assertEqual(fiyatlar, sorted(fiyatlar))

    def test_unparseable_value_yields_no_candidates(self):
        """Deger bilinmiyorsa fiyat UYDURULMAZ."""
        self.assertEqual(mpn.candidates("C", "C"), [])
        self.assertEqual(mpn.candidates("R", "R"), [])

    def test_catalogue_is_deterministic(self):
        """Ayni girdi ayni katalog - iki kosuda fiyat degisirse guven biter."""
        self.assertEqual(mpn.candidates("C", "10uF"), mpn.candidates("C", "10uF"))


class SandboxSchematic(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-mpn-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.sch = self.tmp / "uc_parca.kicad_sch"
        shutil.copy(UC_PARCA, self.sch)
        shutil.copy(UC_PARCA.with_suffix(".kicad_pro"),
                    self.sch.with_suffix(".kicad_pro"))


class AssignmentTests(SandboxSchematic):
    def test_dry_run_touches_nothing(self):
        onceki = self.sch.read_bytes()
        schematic = read_schematic(self.sch)
        plan = mpn.plan_assignment(schematic, "C")
        sonuc, _ = mpn.apply_assignment(self.sch, plan, apply=False)
        self.assertFalse(sonuc.written)
        self.assertEqual(self.sch.read_bytes(), onceki)

    def test_default_value_is_refused_not_priced(self):
        """Ornekte C1'in degeri 'C' - okunamaz, fiyat almamali."""
        schematic = read_schematic(self.sch)
        plan = mpn.plan_assignment(schematic, "C")
        self.assertEqual(plan.assignments, [])
        self.assertTrue(any("C1" in p for p in plan.problems))

    def test_written_fields_come_back(self):
        schematic = read_schematic(self.sch)
        # Once okunabilir bir deger ver
        from pcbqa.sch_add import add_symbols

        add_symbols(self.sch, "Device:C", 2, value="22uF", verify=False, apply=True)
        schematic = read_schematic(self.sch)
        plan = mpn.plan_assignment(schematic, "C")
        self.assertEqual(len(plan.assignments), 2)
        mpn.apply_assignment(self.sch, plan, apply=True, backup=False)

        kayitlar = mpn.read_assignments(read_schematic(self.sch))
        self.assertEqual(len(kayitlar), 2)
        for k in kayitlar:
            self.assertTrue(k["mpn"].startswith("SENT-"))
            self.assertEqual(k["kaynak"], mpn.KAYNAK_DEGERI)
            self.assertGreater(float(k["fiyat"]), 0.0)

    def test_reassigning_updates_instead_of_duplicating(self):
        """Ikinci kez atamak alani COGALTMAMALI."""
        from pcbqa.sch_add import add_symbols

        add_symbols(self.sch, "Device:C", 1, value="33uF", verify=False, apply=True)
        for _ in range(2):
            schematic = read_schematic(self.sch)
            plan = mpn.plan_assignment(schematic, "C")
            mpn.apply_assignment(self.sch, plan, apply=True, backup=False)

        metin = self.sch.read_text(encoding="utf-8")
        self.assertEqual(metin.count('"MPN"'), 1, "MPN alani cogalmis")
        self.assertEqual(metin.count('"MPN_Kaynak"'), 1)

    def test_existing_symbols_keep_their_value_and_position(self):
        from pcbqa.sch_add import add_symbols

        add_symbols(self.sch, "Device:C", 1, value="47uF", verify=False, apply=True)
        once = {s.ref: (s.x, s.y, s.value) for s in read_schematic(self.sch).symbols}
        schematic = read_schematic(self.sch)
        mpn.apply_assignment(self.sch, mpn.plan_assignment(schematic, "C"),
                             apply=True, backup=False)
        sonra = {s.ref: (s.x, s.y, s.value) for s in read_schematic(self.sch).symbols}
        self.assertEqual(once, sonra, "MPN yazmak konumu ya da degeri degistirdi")


if __name__ == "__main__":
    unittest.main()
