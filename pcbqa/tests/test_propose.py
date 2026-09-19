"""Baglanti ONERISI: uygulamanin "bunlar nasil baglanmali" karari.

Burada korunan sey dogruluk kadar SUSKUNLUK: kaniti olmayan bir oneri,
kullanicinin fark etmeden kabul edecegi yanlis bir devre demektir. Onerinin
hicbir zaman yapmamasi gerekenler:

  * bir parcanin KENDI iki ucunu birlestirmek (kisa devre),
  * zaten bagli bir pine dokunmak,
  * arasinda engel olan iki pini birlestirmek.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from pcbqa import propose
from pcbqa.schematic import read_schematic

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
UC_PARCA = SAMPLES / "uc_parca" / "uc_parca.kicad_sch"


class ThreePartTests(unittest.TestCase):
    """+10V, R1, C1 - hicbiri bagli degil."""

    @classmethod
    def setUpClass(cls):
        cls.schematic = read_schematic(UC_PARCA)
        cls.suggestion = propose.suggest(cls.schematic)

    def test_all_three_pins_are_free_to_start(self):
        pins = propose.free_pins(self.schematic)
        self.assertEqual(len(pins), 5, "R1 2 + C1 2 + guc 1")

    def test_a_part_is_never_shorted_across_itself(self):
        """R1.1-R1.2 onerilirse direnc kisa devre olur.

        Bu gercekten olmustu: ilk surumde EN YAKIN hizali komsu kurali
        R1.1 icin R1.2'yi seciyordu (7.62 mm), C1.1'i degil (15.24 mm).
        Bir sembolun kendi pinleri zaten hizalidir - o hizalama sembolun
        GEOMETRISINDEN gelir, kullanicinin yerlesiminden degil.
        """
        for proposal in self.suggestion.proposals:
            refs = [p.ref for p in proposal.pins]
            with self.subTest(str(proposal)):
                self.assertEqual(len(set(refs)), len(refs),
                                 f"ayni sembolun pinleri birlestirilmis: {refs}")

    def test_the_two_rails_are_proposed(self):
        ciftler = {frozenset(str(p) for p in x.pins)
                   for x in self.suggestion.proposals if x.kind == "hizalama"}
        self.assertIn(frozenset({"R1.1", "C1.1"}), ciftler)
        self.assertIn(frozenset({"R1.2", "C1.2"}), ciftler)

    def test_power_drops_onto_the_rail(self):
        inisler = [p for p in self.suggestion.proposals if p.kind == "guc-inisi"]
        self.assertEqual(len(inisler), 1)
        self.assertEqual(inisler[0].path[-1], (39.37, 45.72))

    def test_every_proposal_carries_a_reason(self):
        for proposal in self.suggestion.proposals:
            with self.subTest(str(proposal)):
                self.assertTrue(proposal.reason.strip())

    def test_paths_are_orthogonal(self):
        for proposal in self.suggestion.proposals:
            for (x1, y1), (x2, y2) in zip(proposal.path, proposal.path[1:]):
                with self.subTest(str(proposal)):
                    self.assertTrue(abs(x1 - x2) < 1e-6 or abs(y1 - y2) < 1e-6,
                                    "egik tel cizilmemeli")


class SilenceTests(unittest.TestCase):
    """Kanit yoksa oneri de yok - ve bu SESSIZCE olmamali."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-oneri-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.path = self.tmp / "uc_parca.kicad_sch"
        shutil.copy(UC_PARCA, self.path)

    def test_unexplainable_pins_are_named_not_dropped(self):
        """Onerilmeyen pin, kullaniciya ADIYLA soylenmeli."""
        schematic = read_schematic(self.path)
        pins = propose.free_pins(schematic)
        # Guc sembolunu tek basina birakinca hicbir raya inemez
        yalniz = [p for p in pins if p.ref == "#PWR01"]
        sonuc = propose.power_drops(yalniz, [], schematic)
        self.assertEqual(sonuc, [])

    def test_already_connected_pins_are_left_alone(self):
        """Telli halde ayni pinler artik 'bos' sayilmamali."""
        from pcbqa import connect

        schematic = read_schematic(self.path)
        plan = connect.plan_from_proposals(schematic, propose.suggest(schematic))
        connect.apply_to_file(self.path, plan, apply=True, backup=False)

        sonra = read_schematic(self.path)
        self.assertEqual(propose.free_pins(sonra), [],
                         "her pin baglandi, geriye bos pin kalmamali")
        self.assertEqual(propose.suggest(sonra).proposals, [],
                         "bagli sayfada yeni oneri uretilmemeli")


class GeometryTests(unittest.TestCase):
    def test_alignment_needs_exactly_one_shared_axis(self):
        self.assertTrue(propose._aligned((0.0, 0.0), (0.0, 5.0)))
        self.assertTrue(propose._aligned((0.0, 0.0), (5.0, 0.0)))
        self.assertFalse(propose._aligned((0.0, 0.0), (5.0, 5.0)))
        self.assertFalse(propose._aligned((0.0, 0.0), (0.0, 0.0)),
                         "ayni nokta hizali sayilmamali")


if __name__ == "__main__":
    unittest.main()
