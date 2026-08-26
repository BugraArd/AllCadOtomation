"""Asama 3 garantileri: hakem gudumlu cila ve gerileme korumasi."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from pcbqa.harness import (
    Result,
    Score,
    best_result,
    load_design,
    locked_refs,
    make_evaluator,
)
from pcbqa.ipc_apply import Candidate, select_winner
from pcbqa.placement import get as get_placer
from pcbqa.placement.base import Evaluation, PlacementContext
from pcbqa.placement.refine import keep_best, polish
from pcbqa.rules import load_rules

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
BUDGET = 3.0


def context_for(board_name: str, rules_name: str = "bench.rules.yaml") -> tuple:
    design = load_design(SAMPLES / board_name)
    rules = load_rules(SAMPLES / rules_name)
    ctx = PlacementContext(
        design=copy.deepcopy(design),
        locked=locked_refs(design),
        seed=0,
        time_budget_s=BUDGET,
        evaluator=make_evaluator(design, rules),
    )
    return design, rules, ctx


class EvaluationTests(unittest.TestCase):
    def test_ordering_prefers_score_then_fewer_errors(self):
        a = Evaluation(score=67.0, errors=1, warnings=0, total_hpwl_mm=300.0)
        b = Evaluation(score=67.0, errors=2, warnings=0, total_hpwl_mm=300.0)
        c = Evaluation(score=70.0, errors=5, warnings=0, total_hpwl_mm=900.0)
        self.assertTrue(a.better_than(b))
        self.assertFalse(b.better_than(a))
        self.assertTrue(c.better_than(a))
        self.assertTrue(a.better_than(None))


class PolishTests(unittest.TestCase):
    def test_polish_never_returns_worse_than_start(self):
        _, _, ctx = context_for("bench_bad.kicad_pcb")
        start = ctx.current()
        before = ctx.evaluate(start)
        after = ctx.evaluate(polish(start, ctx, budget_s=BUDGET))
        self.assertGreaterEqual(after.key, before.key)

    def test_polish_improves_a_defective_board(self):
        _, _, ctx = context_for("bench_bad.kicad_pcb")
        start = ctx.current()
        before = ctx.evaluate(start)
        after = ctx.evaluate(polish(start, ctx, budget_s=BUDGET))
        self.assertGreater(after.score, before.score)
        self.assertLess(after.errors, before.errors)

    def test_polish_is_a_no_op_without_an_evaluator(self):
        design = load_design(SAMPLES / "bench_bad.kicad_pcb")
        ctx = PlacementContext(design=design, locked=locked_refs(design), time_budget_s=BUDGET)
        start = ctx.current()
        self.assertEqual(polish(start, ctx, budget_s=BUDGET), start)

    def test_polish_does_not_move_locked_components(self):
        _, _, ctx = context_for("bench_bad.kicad_pcb")
        start = ctx.current()
        result = polish(start, ctx, budget_s=BUDGET)
        for ref in ctx.locked:
            self.assertEqual(result.get(ref), start.get(ref), f"{ref} kilitliyken oynatildi")

    def test_keep_best_falls_back_to_the_current_placement(self):
        _, _, ctx = context_for("bench_good.kicad_pcb")
        current = ctx.current()
        wrecked = {ref: (x + 40.0, y + 40.0, r) for ref, (x, y, r) in current.items()
                   if ref not in ctx.locked}
        name, best, _ = keep_best({"mevcut": current, "bozuk": wrecked}, ctx)
        self.assertEqual(name, "mevcut")
        self.assertEqual(best, current)


class AutoPlacerTests(unittest.TestCase):
    def test_auto_does_not_degrade_an_already_good_board(self):
        design, rules, ctx = context_for("bench_good.kicad_pcb")
        before = Score.of(design, rules)
        placement = get_placer("auto").run(ctx)
        after = ctx.evaluate(placement)
        self.assertGreaterEqual(after.score, before.score - 0.05)

    def test_auto_respects_the_locked_contract(self):
        _, _, ctx = context_for("bench_bad.kicad_pcb")
        placement = get_placer("auto").run(ctx)
        for ref in ctx.locked:
            comp = ctx.design.component(ref)
            if ref in placement and comp is not None:
                self.assertAlmostEqual(placement[ref][0], comp.x, places=6)
                self.assertAlmostEqual(placement[ref][1], comp.y, places=6)


class RegressionGuardTests(unittest.TestCase):
    @staticmethod
    def _result(name: str, before: float, after: float, problems=None) -> Result:
        return Result(
            placer=name,
            before=Score(before, 0, 0, 100.0),
            after=Score(after, 0, 0, 100.0),
            seconds=1.0,
            moved=3,
            problems=list(problems or []),
        )

    def test_best_result_rejects_a_regressing_placer(self):
        worse = self._result("worse", 83.0, 70.0)
        self.assertIsNone(best_result([worse]))

    def test_best_result_prefers_the_improving_placer(self):
        worse = self._result("worse", 83.0, 70.0)
        better = self._result("better", 83.0, 90.0)
        self.assertIs(best_result([worse, better]), better)

    def test_best_result_accepts_a_neutral_placer(self):
        neutral = self._result("identity", 83.0, 83.0)
        self.assertIs(best_result([neutral]), neutral)

    def test_select_winner_refuses_to_apply_a_regression(self):
        worse = Candidate("worse", self._result("worse", 83.0, 70.0), {})
        with self.assertRaises(ValueError) as caught:
            select_winner([worse])
        self.assertIn("iyilestiremedi", str(caught.exception))


if __name__ == "__main__":
    unittest.main()


class MetropolisTests(unittest.TestCase):
    """Faz E: gevsetilmis kabul kurali monotonluk garantisini bozmamali.

    Tavlama benzeri kabul `polish`in GEZINEN durumunu etkiler; dondurulen
    sonuc her zaman gorulen en iyidir. Bu ayrim bozulursa Asama 3'ten beri
    duran "hicbir karti kotulestirme" garantisi de bozulur.
    """

    def hot(self):
        from pcbqa.placement.refine import Metropolis

        # warmup=1, heat=1e6 -> pratikte her kotulesmeyi kabul eder
        return Metropolis(cooling=1.0, warmup=1, heat=1e6)

    def test_improving_move_is_always_accepted(self):
        from pcbqa.placement.refine import Metropolis
        import random as _random

        acc = Metropolis()
        better = Evaluation(score=90.0, errors=0, warnings=0, total_hpwl_mm=100.0)
        worse = Evaluation(score=80.0, errors=1, warnings=0, total_hpwl_mm=200.0)
        self.assertTrue(acc(better, worse, 0.5, _random.Random(0)))

    def test_cold_end_refuses_worsening_moves(self):
        from pcbqa.placement.refine import Metropolis
        import random as _random

        acc = Metropolis(cooling=1e9, warmup=1)
        good = Evaluation(score=90.0, errors=0, warnings=0, total_hpwl_mm=100.0)
        bad = Evaluation(score=70.0, errors=2, warnings=0, total_hpwl_mm=300.0)
        rng = _random.Random(0)
        acc(bad, good, 0.0, rng)  # warmup
        self.assertFalse(acc(bad, good, 1.0, rng), "sonda sicaklik ~0 olmali")

    def test_wandering_acceptance_still_never_returns_worse(self):
        _, _, ctx = context_for("bench_bad.kicad_pcb")
        start = ctx.current()
        before = ctx.evaluate(start)
        after = ctx.evaluate(polish(start, ctx, budget_s=BUDGET, accept=self.hot()))
        self.assertGreaterEqual(after.key, before.key)

    def test_a_good_board_is_not_damaged_by_wandering(self):
        _, _, ctx = context_for("bench_good.kicad_pcb")
        start = ctx.current()
        before = ctx.evaluate(start)
        after = ctx.evaluate(polish(start, ctx, budget_s=BUDGET, accept=self.hot()))
        self.assertGreaterEqual(after.key, before.key)

    def test_gain_over_agrees_with_better_than(self):
        """Skaler fark ile sozluksel siralama ayni seyi soylemeli."""
        cases = [
            (Evaluation(50.1, 0, 0, 2000.0), Evaluation(50.0, 0, 0, 1000.0)),
            (Evaluation(50.0, 0, 0, 900.0), Evaluation(50.0, 0, 0, 1000.0)),
            (Evaluation(49.9, 0, 0, 10.0), Evaluation(50.0, 0, 0, 1000.0)),
            (Evaluation(50.0, 0, 0, 1100.0), Evaluation(50.0, 0, 0, 1000.0)),
        ]
        for cand, base in cases:
            self.assertEqual(
                cand.gain_over(base) > 0.0,
                cand.better_than(base),
                f"{cand} vs {base}",
            )
