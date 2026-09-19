"""Bagimliliksiz YAML okuyucu - PyYAML ile KARSILASTIRARAK korunur.

Bu okuyucunun tek gercek tehlikesi sessizce YANLIS okumasidir: hata vermez,
ama baska bir kural agaci uretir ve kullanici bunu asla fark etmez. Bu yuzden
testlerin merkezinde tek bir fikir var:

    Depodaki HER YAML dosyasi iki okuyucudan gecirilir ve sonuclar
    BIREBIR esit olmalidir.

PyYAML kurulu degilse (KiCad'in Python'unda oyle) karsilastirma atlanir -
ama o ortamda zaten gelistirme yapilmiyor; bu testler gelistirici
makinesinde kosar.

Ikinci grup: DESTEKLENMEYEN yapilar. Okuyucu anlamadigi bir seyi tahmin
etmemeli, HATA atmali. Sessiz yanlis okuma ile gurultulu ret arasindaki fark
budur.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pcbqa import minyaml

try:
    import yaml as pyyaml
except ImportError:  # pragma: no cover
    pyyaml = None

PROJECT = Path(__file__).resolve().parent.parent
YAML_FILES = sorted(
    list((PROJECT / "pcbqa").rglob("*.yaml")) + list((PROJECT / "samples").rglob("*.yaml"))
)


@unittest.skipUnless(pyyaml is not None, "pyyaml yok - karsilastirma yapilamaz")
class DifferentialTests(unittest.TestCase):
    """Asil koruma: iki okuyucu ayni cevabi vermeli."""

    def test_repository_yaml_files_are_found(self):
        self.assertGreater(len(YAML_FILES), 10, "tarama YAML dosyalarini bulamadi")

    def test_every_repository_file_parses_identically(self):
        for path in YAML_FILES:
            with self.subTest(path.relative_to(PROJECT).as_posix()):
                text = path.read_text(encoding="utf-8")
                self.assertEqual(minyaml.safe_load(text), pyyaml.safe_load(text))

    def test_constructs_corpus_parses_identically(self):
        """Kullanicinin yazabilecegi yapilar - depoda gecmese bile."""
        corpus = [
            "a: 1\nb: iki\n",
            "a:\n  b:\n    c: derin\n",
            "liste:\n  - bir\n  - iki\n",
            "kayitlar:\n  - ad: x\n    deger: 1\n  - ad: y\n    deger: 2\n",
            "satir_ici: [1, 2, 3]\n",
            "eslesme: {a: 1, b: iki}\n",
            'tirnak: "icinde: iki nokta"\n',
            "tek_tirnak: 'merhaba dunya'\n",
            "sayilar:\n  tam: 42\n  eksi: -7\n  ondalik: 0.25\n  us: 1.0e+3\n",
            "mantik:\n  a: true\n  b: false\n  c: yes\n  d: no\n",
            "bos_deger:\n",
            "null_deger: null\n",
            "tilde: ~\n",
            "# bastan yorum\na: 1  # satir sonu yorum\n",
            "metin: 100nF\n",
            "desen: '^BUS'\n",
            "ic_ice_liste:\n  - [1, 2]\n  - [3, 4]\n",
            "karisik:\n  ad: test\n  etiketler: [a, b]\n  ayar: {x: 1}\n",
            "yol: C:\\\\bir\\\\yol\n",
            "bos_liste: []\n",
            "bos_eslesme: {}\n",
        ]
        for text in corpus:
            with self.subTest(text[:40]):
                self.assertEqual(minyaml.safe_load(text), pyyaml.safe_load(text))

    def test_yaml_1_1_number_traps_match(self):
        """YAML 1.1'in tuzakli sayi kurallari birebir taklit edilmeli.

        Olculdu: 012 sekizliktir (10), 0603 de oyle (387), ama 0805 METINdir
        (8 sekizlik degil); us gosteriminde isaret ZORUNLUDUR (1e3 metin,
        1.0e+3 sayi). Bunlari "duzeltmek" iki ortamda iki farkli kural
        yuklenmesi demek olurdu.
        """
        for text in ("a: 012", "a: 0603", "a: 0805", "a: 1e3", "a: 1.0e+3",
                     "a: 1:30", "a: 1_000", "a: 0x1f"):
            with self.subTest(text):
                self.assertEqual(minyaml.safe_load(text), pyyaml.safe_load(text))

    def test_hash_inside_a_quoted_value_is_not_a_comment(self):
        text = 'renk: "#ff0000"\n'
        self.assertEqual(minyaml.safe_load(text), pyyaml.safe_load(text))
        self.assertEqual(minyaml.safe_load(text)["renk"], "#ff0000")


class UnsupportedTests(unittest.TestCase):
    """Anlamadigini SESSIZCE gecmemeli."""

    def _refuses(self, text: str, expect: str) -> None:
        with self.assertRaises(minyaml.MiniYamlError) as ctx:
            minyaml.safe_load(text)
        self.assertIn(expect, str(ctx.exception).lower())

    def test_anchor_is_refused(self):
        self._refuses("ortak: &capa\n  a: 1\n", "capa")

    def test_alias_is_refused(self):
        self._refuses("a: *capa\n", "capa")

    def test_multiline_scalar_is_refused(self):
        self._refuses("metin: |\n  bir\n  iki\n", "cok satirli")

    def test_document_separator_is_refused(self):
        self._refuses("---\na: 1\n", "belge ayraci")

    def test_tag_is_refused(self):
        self._refuses("a: !!python/object x\n", "etiket")

    def test_tab_indentation_is_refused(self):
        self._refuses("a:\n\tb: 1\n", "sekme")

    def test_broken_indentation_is_refused(self):
        with self.assertRaises(minyaml.MiniYamlError):
            minyaml.safe_load("a: 1\n   b: 2\n")

    def test_unclosed_quote_is_refused(self):
        with self.assertRaises(minyaml.MiniYamlError):
            minyaml.safe_load('a: "kapanmadi\n')

    def test_unclosed_bracket_is_refused(self):
        with self.assertRaises(minyaml.MiniYamlError):
            minyaml.safe_load("a: [1, 2\n")

    def test_error_names_the_line(self):
        with self.assertRaises(minyaml.MiniYamlError) as ctx:
            minyaml.safe_load("a: 1\nb: |\n  metin\n")
        self.assertIn("satir 2", str(ctx.exception))


class ScalarTests(unittest.TestCase):
    def test_plain_types(self):
        self.assertEqual(minyaml.parse_scalar("42"), 42)
        self.assertEqual(minyaml.parse_scalar("-3.5"), -3.5)
        self.assertIs(minyaml.parse_scalar("true"), True)
        self.assertIs(minyaml.parse_scalar("no"), False)
        self.assertIsNone(minyaml.parse_scalar(""))
        self.assertEqual(minyaml.parse_scalar("0603"), 387)  # sekizlik!

    def test_quoted_stays_a_string(self):
        self.assertEqual(minyaml.parse_scalar('"0603"'), "0603")
        self.assertEqual(minyaml.parse_scalar("'true'"), "true")

    def test_value_like_text_is_kept(self):
        self.assertEqual(minyaml.parse_scalar("100nF"), "100nF")
        self.assertEqual(minyaml.parse_scalar("4k7"), "4k7")


class RealFileTests(unittest.TestCase):
    """PyYAML olmadan da paketin kendi dosyalari okunabilmeli."""

    def test_a_preset_loads_without_pyyaml(self):
        text = (PROJECT / "pcbqa" / "presets" / "uretim.rules.yaml").read_text(encoding="utf-8")
        data = minyaml.safe_load(text)
        self.assertEqual(data["version"], 1)
        self.assertTrue(data["rules"])
        self.assertTrue(all("id" in r for r in data["rules"]))

    def test_a_template_loads_without_pyyaml(self):
        text = (PROJECT / "pcbqa" / "templates" / "mcu-stm32f103c8.yaml").read_text(
            encoding="utf-8"
        )
        data = minyaml.safe_load(text)
        self.assertEqual(data["id"], "mcu-stm32f103c8")
        # Sablonun pin baglantilari satir ici eslesme olarak yaziliyor
        caps = next(c for c in data["components"] if c["name"] == "vdd-decoupling")
        self.assertEqual(caps["count"], 3)
        self.assertEqual(caps["connect"]["#2"], "${gnd}")

    def test_an_intent_loads_without_pyyaml(self):
        text = (PROJECT / "samples" / "niyetler" / "f103-usb-kristal-swd.yaml").read_text(
            encoding="utf-8"
        )
        data = minyaml.safe_load(text)
        self.assertEqual(len(data["blocks"]), 5)


if __name__ == "__main__":
    unittest.main()
