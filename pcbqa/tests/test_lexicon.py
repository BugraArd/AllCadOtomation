"""Iki dilli bilesen sozlugu.

Bu sozluk ilerideki makine ogreniminin GIRDISI olacak; icindeki bir yanlis,
egitilen modele dogruymus gibi gecer. Korunanlar:

  * Turkce karsilik UYDURULMAZ - yalnizca TERMS'ten uretilir, tutmazsa bos.
  * Bilincli cevrilmeyenler (paket/uretici adlari) TERMS'e sizmamali.
  * Referans oneki tablosu ile kutuphanenin gercegi tutmali.
"""

from __future__ import annotations

import unittest

from pcbqa import lexicon


class TermTableTests(unittest.TestCase):
    def test_every_designator_has_both_languages(self):
        for onek, kayit in lexicon.DESIGNATORS.items():
            with self.subTest(onek):
                self.assertTrue(kayit.get("en", "").strip(), f"{onek}: EN yok")
                self.assertTrue(kayit.get("tr", "").strip(), f"{onek}: TR yok")

    def test_every_designator_cites_its_evidence(self):
        """Ad ezberden degil olcumden geldi; `ornek` o olcumun izidir."""
        for onek, kayit in lexicon.DESIGNATORS.items():
            with self.subTest(onek):
                self.assertTrue(kayit.get("ornek", "").strip(),
                                f"{onek}: kanit alani bos")

    def test_terms_are_lowercase_keys(self):
        """Arama kucuk harfle yapiliyor; buyuk harfli anahtar hic tutmaz."""
        for en in lexicon.TERMS:
            self.assertEqual(en, en.lower(), f"{en!r} kucuk harf degil")

    def test_untranslated_words_stay_out_of_the_terms_table(self):
        """Paket ve uretici adlari CEVRILMEZ; TERMS'e girerlerse cevrilirler."""
        for kelime in lexicon.CEVRILMEZ:
            with self.subTest(kelime):
                self.assertNotIn(kelime, lexicon.TERMS,
                                 f"{kelime!r} cevrilmemeliydi ama TERMS'te")

    def test_turkish_side_is_ascii(self):
        """Kod ve veri ASCII (proje kurali); 'kondansator', 'kondansatör' degil."""
        for onek, kayit in lexicon.DESIGNATORS.items():
            with self.subTest(onek):
                kayit["tr"].encode("ascii")
        for en, tr in lexicon.TERMS.items():
            with self.subTest(en):
                tr.encode("ascii")


class NormalizeTests(unittest.TestCase):
    """`U6`, `RL2`, `MES?` ayri onek DEGIL - kutuphane yazim tutarsizligi."""

    def test_trailing_digits_and_question_marks_are_trimmed(self):
        self.assertEqual(lexicon.normalize_designator("U6"), "U")
        self.assertEqual(lexicon.normalize_designator("RL2"), "RL")
        self.assertEqual(lexicon.normalize_designator("U?"), "U")
        self.assertEqual(lexicon.normalize_designator("MES?"), "MES")

    def test_known_prefixes_are_left_alone(self):
        for onek in ("C", "R", "U", "#PWR", "BAR"):
            self.assertEqual(lexicon.normalize_designator(onek), onek)

    def test_unknown_prefix_is_not_silently_swallowed(self):
        """Kirpma sonucu tanimli bir onege dusmuyorsa dokunulmaz.

        Yoksa gercekten yeni bir onek sessizce baska bir seye donusurdu.
        """
        self.assertEqual(lexicon.normalize_designator("ZZZ9"), "ZZZ9")
        self.assertEqual(lexicon.normalize_designator(""), "")


class GlossTests(unittest.TestCase):
    def test_known_words_are_translated(self):
        self.assertEqual(lexicon.gloss("Resistor"), "direnc")
        self.assertIn("kondansator", lexicon.gloss("Unpolarized capacitor"))

    def test_nothing_known_yields_empty_not_a_fake_translation(self):
        """Hicbir terim tutmazsa BOS doner - yarim ceviriyi Turkce diye sunmayiz."""
        self.assertEqual(lexicon.gloss("STM32F103C8Tx"), "")
        self.assertEqual(lexicon.gloss(""), "")

    def test_phrases_beat_word_by_word(self):
        """Kelime kelime cevirmek bunlari bozuyordu: 'Through hole' -> 'Through delik'."""
        self.assertIn("delikli montaj", lexicon.gloss("Through Hole connector"))
        self.assertIn("gunes pili", lexicon.gloss("Single solar cell"))
        self.assertIn("basmali dugme", lexicon.gloss("Push button switch"))

    def test_part_numbers_survive_untouched(self):
        """Parca numarasi ve paket adi cevrilmemeli."""
        sonuc = lexicon.gloss("1A Low Dropout regulator, SOT-223")
        self.assertIn("SOT-223", sonuc)
        self.assertIn("dusuk dusumlu", sonuc)


class LookupTests(unittest.TestCase):
    def test_abbreviation_resolves_to_both_names(self):
        sonuc = lexicon.lookup("C")
        self.assertEqual(sonuc["onek"]["en"], "Capacitor")
        self.assertEqual(sonuc["onek"]["tr"], "Kondansator")

    def test_turkish_word_finds_the_english_term(self):
        self.assertIn("resistor", lexicon.lookup("direnc")["terim_en"])

    def test_search_is_whole_word_not_substring(self):
        """Olculdu: alt dizi aramasi 'C' icin 41 onek donduruyordu - gurultu."""
        sonuc = lexicon.lookup("C")
        self.assertLessEqual(len(sonuc.get("eslesen_onekler", [])), 3)

    def test_unknown_term_returns_only_the_query(self):
        self.assertEqual(set(lexicon.lookup("zzzyok")), {"sorgu"})


@unittest.skipUnless(lexicon.SOZLUK_DOSYASI.is_file(),
                     "uretilmis sozluk yok - 'pcbqa sozluk --uret'")
class BuiltLexiconTests(unittest.TestCase):
    """Uretilmis sozluk - KiCad kurulu makinede."""

    @classmethod
    def setUpClass(cls):
        cls.veri = lexicon.load()

    def test_every_symbol_has_a_known_category(self):
        tanimsiz = self.veri["kapsam"]["tanimsiz_onek"]
        self.assertEqual(tanimsiz, [], f"tanimsiz onek kaldi: {tanimsiz}")

    def test_known_symbols_are_present(self):
        idler = {e["id"] for e in self.veri["semboller"]}
        for lid in ("Device:C", "Device:R", "Device:L", "power:+3V3"):
            self.assertIn(lid, idler)

    def test_capacitor_maps_to_kondansator(self):
        """Kullanicinin ornegi: C = kapasitor/kondansator, iki dilde."""
        kayit = next(e for e in self.veri["semboller"] if e["id"] == "Device:C")
        self.assertEqual(kayit["ref"], "C")
        self.assertIn("kondansator", kayit.get("tr", ""))
        self.assertEqual(self.veri["designators"]["C"]["tr"], "Kondansator")

    def test_turkish_coverage_is_reported_not_assumed(self):
        oran = self.veri["kapsam"]["turkce_oran"]
        self.assertGreater(oran, 50.0, "kapsama beklenenden dusuk")
        self.assertLess(oran, 100.0,
                        "%100 supheli - parca numaralarinin Turkcesi olmamali")


if __name__ == "__main__":
    unittest.main()
