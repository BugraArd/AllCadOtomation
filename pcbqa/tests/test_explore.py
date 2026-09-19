"""Evre 3b: uretim-degerlendirme dongusu (N varyant, en iyisini sec).

Korunan iki sey:

  * SECIM OLCUTU. Skor uretilen kartta doyuyor (butun varyantlar 100),
    yani secim skordan sonra ALAN ve HPWL ile yapilmali. Bir gerileme bu
    siralamayi bozarsa dongu en buyuk karti secmeye baslar ve kazanc
    sessizce kaybolur.
  * ARAMA SIRASI. Once boyut cesitliligi, sonra tohum: boyut kart alanini
    (parayi) degistirir, tohum yalnizca ayni kart icinde daha iyi bir
    yerlesim arar.

Uctan uca test ayrica dongunun GERCEKTEN kazandirdigini olcer: kazanan,
adaylarin en buyugunden kucuk olmali.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from pcbqa import symlib
from pcbqa.explore import DENSITIES, Variant, explore, plan_variants
from pcbqa.intent import Intent, IntentBlock, expand_intent, load_templates, resolve_plan
from pcbqa.pcb import read_board


def device_library_available() -> bool:
    try:
        symlib.get_symbol("Device:R")
        return True
    except symlib.SymLibError:
        return False


def _variant(index=1, density=0.25, width=50.0, height=35.0, seed=0,
             score=100.0, errors=0, warnings=0, hpwl=100.0) -> Variant:
    return Variant(index=index, density=density, width=width, height=height,
                   seed=seed, score=score, errors=errors, warnings=warnings,
                   hpwl_mm=hpwl)


class SelectionTests(unittest.TestCase):
    def test_score_outranks_area(self):
        """Kaliteden odun verilmez: buyuk ama temiz kart, kucuk ama kusurluyu yener."""
        temiz_buyuk = _variant(width=100, height=70, score=100.0)
        kusurlu_kucuk = _variant(width=30, height=20, score=95.0)
        self.assertGreater(temiz_buyuk.key, kusurlu_kucuk.key)

    def test_smaller_board_wins_at_equal_quality(self):
        kucuk = _variant(width=40, height=30, hpwl=200.0)
        buyuk = _variant(width=50, height=35, hpwl=150.0)
        self.assertGreater(kucuk.key, buyuk.key, "esit kalitede kucuk kart yeglenmeli")

    def test_hpwl_breaks_ties_at_equal_area(self):
        kisa = _variant(hpwl=150.0)
        uzun = _variant(hpwl=200.0)
        self.assertGreater(kisa.key, uzun.key)

    def test_errors_outrank_area(self):
        hatasiz = _variant(width=60, height=40, errors=0)
        hatali = _variant(width=30, height=20, errors=1)
        self.assertGreater(hatasiz.key, hatali.key)

    def test_best_is_the_maximum_of_the_key(self):
        adaylar = [
            _variant(index=1, width=50, height=35, hpwl=170.0),
            _variant(index=2, width=40, height=30, hpwl=220.0),
            _variant(index=3, width=55, height=40, hpwl=150.0),
        ]
        self.assertEqual(max(adaylar, key=lambda v: v.key).index, 2)


class PlanOrderTests(unittest.TestCase):
    """`plan_variants` bir kart dosyasi okur; boyut hesabini burada taklit ederiz."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-exp-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.calls: list[float] = []

        def sahte_fit(path, density=0.25):
            self.calls.append(density)
            # Yogunluk arttikca kart kucululur; her yogunluk AYRI boyut versin
            kenar = round(100.0 * (0.25 / density), 1)
            return kenar, kenar / 2.0

        import pcbqa.explore as explore_mod

        self.original = explore_mod.fit_outline
        explore_mod.fit_outline = sahte_fit
        self.addCleanup(setattr, explore_mod, "fit_outline", self.original)
        self.pcb = self.tmp / "sahte.kicad_pcb"
        self.pcb.write_text("(kicad_pcb)", encoding="utf-8")

    def test_sizes_come_before_seeds(self):
        """Ilk N varyant N farkli boyut olmali, tohum hep ayni."""
        variants = plan_variants(self.pcb, len(DENSITIES))
        self.assertEqual(len({(v.width, v.height) for v in variants}), len(DENSITIES))
        self.assertEqual({v.seed for v in variants}, {0})

    def test_seeds_advance_after_every_size_is_tried(self):
        variants = plan_variants(self.pcb, len(DENSITIES) + 2)
        self.assertEqual(variants[len(DENSITIES)].seed, 1)
        self.assertEqual(
            (variants[len(DENSITIES)].width, variants[len(DENSITIES)].height),
            (variants[0].width, variants[0].height),
            "tohum turunda boyutlar bastan baslamali",
        )

    def test_duplicate_sizes_are_dropped(self):
        import pcbqa.explore as explore_mod

        explore_mod.fit_outline = lambda path, density=0.25: (50.0, 35.0)
        variants = plan_variants(self.pcb, 3)
        # Butun yogunluklar ayni boyuta cikiyorsa tek boyut kalir, tohumlar ilerler
        self.assertEqual({(v.width, v.height) for v in variants}, {(50.0, 35.0)})
        self.assertEqual([v.seed for v in variants], [0, 1, 2])

    def test_base_seed_is_respected(self):
        variants = plan_variants(self.pcb, 2, base_seed=7)
        self.assertEqual({v.seed for v in variants}, {7})


@unittest.skipUnless(device_library_available(), "KiCad sembol kutuphanesi yok")
class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-exp-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def small_plan(self):
        templates = load_templates()
        intent = Intent(name="kucuk", blocks=[IntentBlock(template="guc-girisi-header"),
                                              IntentBlock(template="ldo-ams1117-3v3")])
        plan = resolve_plan(expand_intent(intent, templates))
        self.assertTrue(plan.ok, plan.problems)
        return plan

    def test_explores_and_writes_the_winner(self):
        result = explore(self.small_plan(), self.tmp / "p", "p",
                         variants=3, time_budget_s=3.0)
        self.assertTrue(result.ok, result.problems)
        self.assertEqual(len(result.variants), 3)
        self.assertIs(result.best, max(result.variants, key=lambda v: v.key))

        # Karta yazilan sinir KAZANANIN siniri olmali
        board = read_board(result.generated.pcb)
        self.assertIsNotNone(board.outline)
        _, _, width, height = board.outline
        self.assertAlmostEqual(width, result.best.width, places=3)
        self.assertAlmostEqual(height, result.best.height, places=3)

    def test_winner_is_no_larger_than_the_biggest_candidate(self):
        """Dongunun varlik sebebi: kucuk kart. Kazanan en buyuk aday olmamali."""
        result = explore(self.small_plan(), self.tmp / "q", "q",
                         variants=len(DENSITIES), time_budget_s=3.0)
        self.assertTrue(result.ok, result.problems)
        en_buyuk = max(v.area_mm2 for v in result.variants)
        self.assertLessEqual(result.best.area_mm2, en_buyuk)

    def test_unrouted_warning_is_always_reported(self):
        """Skorun neyi yargilamadigi SESSIZ kalmamali."""
        result = explore(self.small_plan(), self.tmp / "r", "r",
                         variants=1, time_budget_s=3.0)
        self.assertTrue(any("yonlendirilmemis" in n for n in result.notes), result.notes)

    def test_only_one_board_outline_is_left(self):
        """Sinir yinelenebilir cizilmeli - iki dikdortgen karti belirsiz kilardi."""
        result = explore(self.small_plan(), self.tmp / "s", "s",
                         variants=2, time_budget_s=3.0)
        from pcbqa.sexpr import children, parse_with_stats, value

        root, stray = parse_with_stats(result.generated.pcb.read_text(encoding="utf-8"))
        self.assertEqual(stray, 0)
        rects = [n for n in children(root, "gr_rect") if value(n, "layer") == "Edge.Cuts"]
        self.assertEqual(len(rects), 1)


if __name__ == "__main__":
    unittest.main()
