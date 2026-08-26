"""Asama 6 / Faz A: genis hamle repertuari.

En onemli test `CompoundSafetyTests`: birlesik hamleler tek bilesenli
hamlelerden cok daha buyuk pertürbasyonlar - takas iki bileseni birden
oynatir. Monotonluk garantisi (Asama 3) yine de bozulmamali.
"""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from pcbqa.harness import load_design, locked_refs, make_evaluator
from pcbqa.placement import refine
from pcbqa.placement.base import PlacementContext
from pcbqa.placement.repertoire import Repertoire, SWAP_EXTENT_RATIO
from pcbqa.rules import load_rules

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
BUDGET = 3.0


def bench_context(board: str = "bench_bad.kicad_pcb") -> tuple:
    design = load_design(SAMPLES / board)
    rules = load_rules(SAMPLES / "bench.rules.yaml")
    ctx = PlacementContext(
        design=copy.deepcopy(design),
        locked=locked_refs(design),
        seed=0,
        time_budget_s=BUDGET,
        evaluator=make_evaluator(design, rules),
    )
    return design, rules, ctx


class CompoundApplyTests(unittest.TestCase):
    def test_all_atoms_land_at_once(self):
        _, _, ctx = bench_context()
        placement = ctx.current()
        a, b = ctx.movable()[0], ctx.movable()[1]
        pa, pb = placement[a], placement[b]
        out = refine.with_moves(placement, ((a, pb), (b, pa)))
        self.assertEqual(out[a], pb)
        self.assertEqual(out[b], pa)
        # Girdi bozulmamali - hakem ayni yerlesimi baska adaylara da veriyor
        self.assertEqual(placement[a], pa)

    def test_single_move_is_a_one_atom_compound(self):
        _, _, ctx = bench_context()
        placement = ctx.current()
        ref = ctx.movable()[0]
        target = (placement[ref][0] + 1.0, placement[ref][1], placement[ref][2])
        self.assertEqual(
            refine.with_moves(placement, ((ref, target),)),
            refine.with_move(placement, ref, target),
        )

    def test_as_compounds_wraps_each_move(self):
        moves = [("R1", (1.0, 2.0, 0.0)), ("C1", (3.0, 4.0, 90.0))]
        self.assertEqual(
            refine.as_compounds(moves),
            [(("R1", (1.0, 2.0, 0.0)),), (("C1", (3.0, 4.0, 90.0)),)],
        )


class SwapTests(unittest.TestCase):
    def test_swap_exchanges_positions_and_keeps_rotations(self):
        _, _, ctx = bench_context()
        placement = ctx.current()
        rep = Repertoire(ctx)
        ref = ctx.movable()[0]
        for compound in rep.swaps(ref, placement):
            self.assertEqual(len(compound), 2)
            (ra, ta), (rb, tb) = compound
            self.assertEqual(ta[:2], placement[rb][:2])
            self.assertEqual(tb[:2], placement[ra][:2])
            # Her bilesen kendi donusunu korur
            self.assertEqual(ta[2], placement[ra][2])
            self.assertEqual(tb[2], placement[rb][2])

    def test_swap_partners_are_size_compatible(self):
        """0402 ile SOIC-20'yi takas etmek her zaman cakisma uretir."""
        _, _, ctx = bench_context()
        placement = ctx.current()
        rep = Repertoire(ctx)
        for ref in ctx.movable()[:5]:
            mine = rep.extent[ref]
            for (_, _), (other, _) in rep.swaps(ref, placement):
                ratio = rep.extent[other] / mine
                self.assertLessEqual(ratio, SWAP_EXTENT_RATIO + 1e-9)
                self.assertGreaterEqual(ratio, 1.0 / SWAP_EXTENT_RATIO - 1e-9)

    def test_locked_components_are_never_offered(self):
        _, _, ctx = bench_context()
        placement = ctx.current()
        rep = Repertoire(ctx)
        self.assertTrue(ctx.locked, "tezgahta kilitli bilesen olmali")
        for locked in ctx.locked:
            self.assertEqual(rep.swaps(locked, placement), [])
        for ref in ctx.movable()[:5]:
            for compound in rep.wide_moves(ref, placement):
                for moved_ref, _ in compound:
                    self.assertNotIn(moved_ref, ctx.locked)


class ClusterTests(unittest.TestCase):
    def test_cluster_moves_preserve_internal_geometry(self):
        """Kumenin ICINDEKI mesafeler degismemeli - tasinan sey kumenin yeri."""
        _, _, ctx = bench_context()
        placement = ctx.current()
        rep = Repertoire(ctx)
        found = False
        for ref in ctx.movable():
            for compound in rep.clusters(ref, placement):
                found = True
                deltas = {
                    r: (t[0] - placement[r][0], t[1] - placement[r][1])
                    for r, t in compound
                }
                first = next(iter(deltas.values()))
                for d in deltas.values():
                    self.assertAlmostEqual(d[0], first[0], places=9)
                    self.assertAlmostEqual(d[1], first[1], places=9)
        self.assertTrue(found, "tezgahta hic kume hamlesi uretilmedi")

    def test_cluster_contains_its_owner(self):
        _, _, ctx = bench_context()
        placement = ctx.current()
        rep = Repertoire(ctx)
        for ref in ctx.movable()[:8]:
            group = rep.cluster_of(ref, placement)
            self.assertEqual(group[0], ref)
            self.assertEqual(len(set(group)), len(group), "kumede tekrar var")


class BatchTests(unittest.TestCase):
    def test_batches_are_separate_and_ordered_by_richness(self):
        """Havuzlayip kesmek zengin damari suluyordu (bkz. wide_batches)."""
        _, _, ctx = bench_context()
        placement = ctx.current()
        rep = Repertoire(ctx)
        for ref in ctx.movable()[:6]:
            labels = [name for name, _ in rep.wide_batches(ref, placement)]
            if "kume" in labels and "takas" in labels:
                self.assertLess(labels.index("kume"), labels.index("takas"))
            self.assertNotIn("bolge", labels, "bolge varsayilan olarak kapali")

    def test_regions_can_be_enabled_explicitly(self):
        _, _, ctx = bench_context()
        placement = ctx.current()
        rep = Repertoire(ctx, include_regions=True)
        labels = set()
        for ref in ctx.movable()[:6]:
            labels |= {name for name, _ in rep.wide_batches(ref, placement)}
        self.assertIn("bolge", labels)


class CompoundSafetyTests(unittest.TestCase):
    """Genis repertuar Asama 3'un monotonluk garantisini bozmamali."""

    def test_polish_with_wide_moves_never_regresses(self):
        _, _, ctx = bench_context()
        start = ctx.current()
        before = ctx.evaluate(start)
        after = ctx.evaluate(polish_wide(ctx, start))
        self.assertGreaterEqual(after.key, before.key)

    def test_wide_phase_can_be_switched_off(self):
        """Sematik tarafi (Asama 4e) takas/kume kavramlarina sahip degil."""
        _, _, ctx = bench_context()
        start = ctx.current()
        before = ctx.evaluate(start)
        after = ctx.evaluate(refine.polish(start, ctx, budget_s=BUDGET, wide_keep=0))
        self.assertGreaterEqual(after.key, before.key)

    def test_good_board_is_not_damaged(self):
        _, _, ctx = bench_context("bench_good.kicad_pcb")
        start = ctx.current()
        before = ctx.evaluate(start)
        after = ctx.evaluate(polish_wide(ctx, start))
        self.assertGreaterEqual(after.key, before.key)


def polish_wide(ctx, start):
    return refine.polish(start, ctx, budget_s=BUDGET, wide_keep=refine.WIDE_KEEP)


if __name__ == "__main__":
    unittest.main()
