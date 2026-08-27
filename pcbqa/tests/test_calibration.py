"""Korpus kalibrasyonu (Faz 1d) ve ondan cikan duzeltmeler.

Kalibrasyonun sorusu "yerlestiricim iyi mi" degil, **"olcutum iyi mi"**:

    Sahaya cikmis, profesyonelce uretilmis bir karta skorumuz dusuk veriyorsa
    yanlis olan kart degil SKORDUR.

Bu bir yanlislanabilir testtir ve kendi esiklerimizi kendimize dogrulatmamizi
engelleyen tek mekanizmadir.

Korpus: KiCad'in kendi demo projeleri (19 kart, kurulumla birlikte gelir,
lisansi temiz). KiCad kurulu degilse ilgili testler ATLANIR.

Bu kosum iki gercek kusur yakaladi ve ikisi de burada korunuyor:
  1. Pad'ler "tum katmanlarda" varsayiliyordu -> kart kenari konnektorlerinde
     on/arka yuz pad'leri arasinda 0.000 mm aciklik olculuyordu (interf_u).
  2. `uretim` on ayari courtyard kuralini error/16 yapmisti; projenin kendi
     default_rules.yaml'i warning diyor ve gerekcesini yazmisti.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pcbqa.harness import evaluate_design, load_design, score_corpus
from pcbqa.rules import load_rules

ROOT = Path(__file__).resolve().parent.parent
PRESETS = ROOT / "pcbqa" / "presets"
DEMOS = Path(r"C:\Program Files\KiCad\10.0\share\kicad\demos")
INTERF_U = DEMOS / "interf_u" / "interf_u.kicad_pcb"


def demos_available() -> bool:
    return DEMOS.is_dir()


class PadLayerTests(unittest.TestCase):
    """Pad'in bakir katmanlari - kalibrasyonun yakaladigi hata."""

    def test_through_hole_pads_span_all_layers(self):
        design = load_design(ROOT / "samples" / "pic_programmer" / "pic_programmer.kicad_pcb")
        found = False
        for comp in design.board.components:
            for pad in comp.pads:
                if pad.shape in ("circle", "oval") and pad.on_all_layers:
                    found = True
        self.assertTrue(found, "delikli pad tum katmanlarda olmali")

    @unittest.skipUnless(demos_available(), "KiCad demolari kurulu degil")
    def test_card_edge_connector_pads_are_layer_separated(self):
        """interf_u'daki BUS1: ayni x/y, farkli net, farkli YUZ.

        BUS1.29 (VCC) ve BUS1.60 (/PC-A2) ayni koordinatta cunku bu bir kart
        kenari konnektoru - biri on, digeri arka yuzde. Katman ayrimi olmadan
        aralarinda 0.000 mm aciklik olculuyor ve skor 1.6'ya dusuyordu.
        """
        design = load_design(INTERF_U)
        bus = design.component("BUS1")
        self.assertIsNotNone(bus, "interf_u'da BUS1 yok")

        same_spot = [
            pad
            for pad in bus.pads
            if abs(pad.x - 98.42) < 0.01 and abs(pad.y - 138.43) < 0.01
        ]
        self.assertGreaterEqual(len(same_spot), 2, "ayni noktada iki pad bekleniyordu")
        nets = {pad.net for pad in same_spot}
        self.assertGreater(len(nets), 1, "pad'ler farkli netlerde olmali")

        layer_sets = [frozenset(pad.copper_layers) for pad in same_spot]
        self.assertNotIn(frozenset(), layer_sets, "kart kenari pad'i tum katmanlarda olamaz")
        self.assertNotEqual(
            layer_sets[0], layer_sets[1], "on ve arka yuz pad'leri ayni katmanda gorunuyor"
        )

    @unittest.skipUnless(demos_available(), "KiCad demolari kurulu degil")
    def test_no_false_clearance_error_on_interf_u(self):
        """Gercek, calisan bir kartta 0.000 mm aciklik = kisa devre demek olurdu."""
        design = load_design(INTERF_U)
        ev = evaluate_design(design, load_rules(PRESETS / "uretim.rules.yaml"))
        clearance = [f for f in ev.findings if f.rule_id == "uretim-gerilim-acikligi"]
        self.assertEqual(
            clearance, [], f"yanlis aciklik alarmi: {[f.message for f in clearance]}"
        )


@unittest.skipUnless(demos_available(), "KiCad demolari kurulu degil")
class CorpusCalibrationTests(unittest.TestCase):
    """`uretim` on ayari gercek kartlarda makul davranmali."""

    @classmethod
    def setUpClass(cls):
        from pcbqa.harness import discover_boards

        cls.report = score_corpus(
            discover_boards(DEMOS), load_rules(PRESETS / "uretim.rules.yaml")
        )

    def test_corpus_is_big_enough_to_mean_something(self):
        self.assertGreaterEqual(self.report["scored"], 10)

    def test_no_board_is_skipped(self):
        """Ayristirici gercek kartlarin hepsini okuyabilmeli."""
        failed = [r for r in self.report["rows"] if "error" in r]
        self.assertEqual(failed, [], f"okunamayan kart: {failed}")

    def test_median_professional_board_scores_well(self):
        """`uretim` devre tipinden bagimsiz; profesyonel kartlarda yuksek olmali.

        Olculdu (2026-08-28): medyan 95.9, ceyrekler 80.7/95.9/100.0.
        Esik 85 secildi - olculen degerin biraz altinda, gurultuye yer birakir
        ama gercek bir gerilemeyi yakalar.
        """
        self.assertGreaterEqual(
            self.report["median"],
            85.0,
            f"medyan skor dustu: {self.report['median']} (kural mi bozuldu?)",
        )

    def test_no_rule_fires_on_most_boards(self):
        """Bir kural gercek kartlarin cogunda atesleniyorsa KURAL suphelidir.

        Kartlar profesyonelce uretilmis; cogunlukta atesleyen bir kural, kartlarin
        degil kendisinin ya da esiginin yanlis oldugunu gosterir.
        """
        scored = self.report["scored"]
        for rule_id, count in self.report["rule_fire_counts"].items():
            with self.subTest(rule=rule_id):
                self.assertLessEqual(
                    count / scored,
                    0.5,
                    f"{rule_id} kartlarin %{count / scored * 100:.0f}'inde atesliyor",
                )


if __name__ == "__main__":
    unittest.main()
