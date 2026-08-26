"""Asama 5 garantileri: oznitelik dogrulugu, model cekirdegi, guvenli baglanti.

En onemli test `AdversarialRankerTests`: siralayici kasten EN KOTU hamleyi one
alsa bile `polish` baslangictan kotu bir sonuc dondurmemeli. ML'in sisteme
girmesi bu garantiyi bozmadigi surece guvenlidir.
"""

from __future__ import annotations

import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

from pcbqa.harness import apply_placement, load_design, locked_refs, make_evaluator
from pcbqa.ml.dataset import Dataset, Sample
from pcbqa.ml.features import FEATURE_COUNT, FEATURE_NAMES, FEATURE_VERSION, MoveFeaturizer
from pcbqa.ml import metrics as M
from pcbqa.ml.collect import label_of
from pcbqa.ml.linear import RidgeModel
from pcbqa.ml.model import MeanModel, load as load_model
from pcbqa.ml.trees import GBTModel
from pcbqa.placement.base import Evaluation, PlacementContext
from pcbqa.placement.learned import Learned, ModelRanker
from pcbqa.placement.refine import polish
from pcbqa.rules import load_rules

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
BUDGET = 3.0


def bench_context(board_name: str = "bench_bad.kicad_pcb") -> tuple:
    design = load_design(SAMPLES / board_name)
    rules = load_rules(SAMPLES / "bench.rules.yaml")
    ctx = PlacementContext(
        design=copy.deepcopy(design),
        locked=locked_refs(design),
        seed=0,
        time_budget_s=BUDGET,
        evaluator=make_evaluator(design, rules),
    )
    return design, rules, ctx


def named(vector: list[float]) -> dict[str, float]:
    return dict(zip(FEATURE_NAMES, vector))


# ------------------------------------------------------------------ oznitelik


class FeatureSchemaTests(unittest.TestCase):
    def test_schema_is_consistent(self):
        self.assertEqual(FEATURE_COUNT, len(FEATURE_NAMES))
        self.assertEqual(len(set(FEATURE_NAMES)), len(FEATURE_NAMES), "tekrar eden ad")
        self.assertGreaterEqual(FEATURE_VERSION, 1)

    def test_vector_length_and_determinism(self):
        design, _, ctx = bench_context()
        fz = MoveFeaturizer(design, ctx.locked)
        placement = ctx.current()
        fz.refresh(placement, ctx.evaluate(placement))
        ref = ctx.movable()[0]
        x, y, rot = placement[ref]
        first = fz.features(ref, (x + 2.0, y, rot))
        second = fz.features(ref, (x + 2.0, y, rot))
        self.assertEqual(len(first), FEATURE_COUNT)
        self.assertEqual(first, second)
        self.assertTrue(all(math.isfinite(v) for v in first))

    def test_refresh_required_before_features(self):
        design, _, ctx = bench_context()
        fz = MoveFeaturizer(design, ctx.locked)
        with self.assertRaises(RuntimeError):
            fz.features(ctx.movable()[0], (0.0, 0.0, 0.0))


class FeatureCorrectnessTests(unittest.TestCase):
    """Yerel hesaplarin GERCEK olcumle ayni sonucu verdigini kanitlar.

    Oznitelikler hiz icin yerel; yerel hesap sessizce yanlis olursa model
    saglam veriyle egitiliyor sanilir. Bu yuzden `d_hpwl` tam yeniden
    hesaplamayla karsilastiriliyor.
    """

    def test_d_hpwl_matches_full_recomputation(self):
        design, _, ctx = bench_context()
        fz = MoveFeaturizer(design, ctx.locked)
        placement = ctx.current()
        fz.refresh(placement, ctx.evaluate(placement))

        for ref in ctx.movable()[:5]:
            x, y, rot = placement[ref]
            target = (x + 5.0, y - 3.0, rot)
            local = named(fz.features(ref, target))["d_hpwl"]

            moved = dict(placement)
            moved[ref] = target
            base = apply_placement(design, placement)
            after = apply_placement(design, moved)
            nets = {
                p.net
                for p in base.pins_of(ref)
            }
            exact = sum(after.hpwl(n) - base.hpwl(n) for n in nets if n)
            self.assertAlmostEqual(local, exact, places=6, msg=f"{ref} icin d_hpwl sapti")

    def test_null_move_has_zero_deltas(self):
        design, _, ctx = bench_context()
        fz = MoveFeaturizer(design, ctx.locked)
        placement = ctx.current()
        fz.refresh(placement, ctx.evaluate(placement))
        ref = ctx.movable()[0]
        f = named(fz.features(ref, placement[ref]))
        self.assertAlmostEqual(f["move_dist"], 0.0)
        self.assertAlmostEqual(f["d_hpwl"], 0.0)
        self.assertAlmostEqual(f["d_overlaps"], 0.0)
        self.assertEqual(f["move_rot_changed"], 0.0)

    def test_stacking_two_components_is_seen_as_overlap(self):
        design, _, ctx = bench_context()
        fz = MoveFeaturizer(design, ctx.locked)
        placement = ctx.current()
        fz.refresh(placement, ctx.evaluate(placement))
        movable = ctx.movable()
        mover, victim = movable[0], movable[1]
        on_top = (placement[victim][0], placement[victim][1], placement[mover][2])
        f = named(fz.features(mover, on_top))
        self.assertGreaterEqual(f["overlaps_after"], 1.0)
        self.assertGreater(f["d_overlaps"], 0.0)
        self.assertAlmostEqual(f["clearance_after"], 0.0)

    def test_kind_one_hot_has_exactly_one_bit(self):
        design, _, ctx = bench_context()
        fz = MoveFeaturizer(design, ctx.locked)
        placement = ctx.current()
        fz.refresh(placement, ctx.evaluate(placement))
        for ref in ctx.movable()[:6]:
            f = named(fz.features(ref, placement[ref]))
            bits = [v for k, v in f.items() if k.startswith("kind_")]
            self.assertEqual(sum(bits), 1.0, f"{ref} tur one-hot bozuk")


# ------------------------------------------------------------------ veri kumesi


class DatasetTests(unittest.TestCase):
    def make(self) -> Dataset:
        ds = Dataset(feature_names=["a", "b"], feature_version=FEATURE_VERSION)
        for board in ("k1", "k2", "k3", "k4"):
            for batch in range(3):
                for i in range(4):
                    ds.add(Sample([float(i), float(batch)], float(i) - 1.5, board, str(batch)))
        return ds

    def test_roundtrip(self):
        ds = self.make()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "d.jsonl"
            ds.save(path)
            back = Dataset.load(path)
        self.assertEqual(len(back), len(ds))
        self.assertEqual(back.feature_names, ds.feature_names)
        self.assertEqual(back.samples[5].features, ds.samples[5].features)

    def test_split_keeps_boards_whole(self):
        """Ayni kart hem egitimde hem testte OLMAMALI - yoksa metrikler ezberi olcer."""
        ds = self.make()
        train, test = ds.split_by_group(0.5, seed=1)
        self.assertTrue(set(train.groups()).isdisjoint(set(test.groups())))
        self.assertEqual(len(train) + len(test), len(ds))

    def test_folds_keep_boards_whole(self):
        ds = self.make()
        folds = ds.folds_by_group(3, seed=0)
        self.assertGreaterEqual(len(folds), 2)
        for train, test in folds:
            self.assertTrue(set(train.groups()).isdisjoint(set(test.groups())))

    def test_batches_group_by_board_and_batch(self):
        ds = self.make()
        self.assertEqual(len(ds.batches()), 12)
        self.assertTrue(all(len(b) == 4 for b in ds.batches()))

    def test_wrong_width_is_rejected(self):
        ds = Dataset(feature_names=["a", "b"])
        with self.assertRaises(ValueError):
            ds.add(Sample([1.0], 0.0))


# ---------------------------------------------------------------------- model


class ModelTests(unittest.TestCase):
    def linear_data(self):
        X, y = [], []
        for i in range(200):
            a, b = i % 7, (i * 3) % 11
            X.append([float(a), float(b), 1.0])
            y.append(2.0 * a - 3.0 * b + 5.0)
        return X, y

    def test_ridge_recovers_a_linear_rule(self):
        X, y = self.linear_data()
        model = RidgeModel(alpha=1e-6).fit(X, y)
        errors = [abs(model.predict(x) - t) for x, t in zip(X, y)]
        self.assertLess(max(errors), 0.05)

    def test_gbt_beats_the_mean_baseline_on_a_nonlinear_rule(self):
        X, y = [], []
        for i in range(400):
            a, b = (i % 20) / 20.0, ((i * 7) % 20) / 20.0
            X.append([a, b])
            y.append(1.0 if a * b > 0.25 else 0.0)
        gbt = GBTModel(n_trees=40, max_depth=3, seed=0).fit(X, y)
        mean = MeanModel().fit(X, y)
        self.assertLess(
            M.rmse(y, gbt.predict_many(X)), M.rmse(y, mean.predict_many(X)) * 0.6
        )

    def test_json_roundtrip_preserves_predictions(self):
        X, y = self.linear_data()
        for model in (RidgeModel(alpha=0.1).fit(X, y), GBTModel(n_trees=8, seed=0).fit(X, y)):
            model.feature_names = ["a", "b", "c"]
            model.feature_version = FEATURE_VERSION
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "m.json"
                model.save(path)
                back = load_model(path)
            self.assertEqual(back.feature_names, ["a", "b", "c"])
            for x in X[:20]:
                self.assertAlmostEqual(back.predict(x), model.predict(x), places=9)

    def test_schema_mismatch_is_loud(self):
        """Sessizce yanlis sayilari okumaktansa hata vermeli."""
        model = MeanModel(value=1.0)
        model.feature_names = ["a", "b"]
        model.feature_version = 1
        model.check_schema(["a", "b"], 1)
        with self.assertRaises(ValueError):
            model.check_schema(["a", "c"], 1)
        with self.assertRaises(ValueError):
            model.check_schema(["a", "b"], 2)

    def test_model_file_is_plain_json(self):
        model = MeanModel(value=0.5)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            model.save(path)
            raw = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(raw["model"], "mean")


# -------------------------------------------------------------------- metrik


class MetricTests(unittest.TestCase):
    def test_perfect_and_constant_predictors(self):
        actual = [1.0, 2.0, 3.0, 4.0]
        self.assertAlmostEqual(M.r2(actual, actual), 1.0)
        self.assertAlmostEqual(M.spearman(actual, actual), 1.0)
        self.assertAlmostEqual(M.spearman(actual, [-v for v in actual]), -1.0)

    def test_constant_prediction_scores_exactly_half(self):
        """Taban cizgisi 0.5 vermeli; vermiyorsa metrik sisiyordur."""
        batch = [(1.0, 0.0), (0.0, 0.0), (-1.0, 0.0)]
        self.assertAlmostEqual(M.pairwise_accuracy([batch]), 0.5)

    def test_perfect_ranking_finds_the_gain_first(self):
        batch = [(-1.0, -1.0), (-2.0, -2.0), (3.0, 3.0)]
        out = M.evals_to_first_gain([batch])
        self.assertAlmostEqual(out["model"], 1.0)
        self.assertAlmostEqual(out["order"], 3.0)
        self.assertGreater(out["speedup"], 1.0)

    def test_batches_without_a_gain_are_ignored(self):
        out = M.evals_to_first_gain([[(-1.0, 0.5), (-2.0, 0.1)]])
        self.assertEqual(out["batches"], 0.0)


class LabelTests(unittest.TestCase):
    def ev(self, score: float, hpwl: float) -> Evaluation:
        return Evaluation(score=score, errors=0, warnings=0, total_hpwl_mm=hpwl)

    def test_score_dominates_hpwl(self):
        before = self.ev(50.0, 1000.0)
        self.assertGreater(label_of(before, self.ev(50.1, 2000.0)), 0.0)
        self.assertLess(label_of(before, self.ev(49.9, 10.0)), 0.0)

    def test_hpwl_breaks_a_score_tie(self):
        before = self.ev(50.0, 1000.0)
        self.assertGreater(label_of(before, self.ev(50.0, 900.0)), 0.0)
        self.assertLess(label_of(before, self.ev(50.0, 1100.0)), 0.0)
        self.assertAlmostEqual(label_of(before, self.ev(50.0, 1000.0)), 0.0)


# --------------------------------------------------------- guvenli baglanti


class RankerTests(unittest.TestCase):
    def test_ranker_orders_by_prediction(self):
        design, _, ctx = bench_context()
        fz = MoveFeaturizer(design, ctx.locked)
        placement = ctx.current()
        ev = ctx.evaluate(placement)
        fz.refresh(placement, ev)

        class Descending:
            """Tahmini = hamle mesafesi; en uzak hamle basa gelmeli."""

            def predict(self, x):
                return x[FEATURE_NAMES.index("move_dist")]

        ranker = ModelRanker(fz, Descending())
        ref = ctx.movable()[0]
        x, y, rot = placement[ref]
        moves = [(ref, (x + d, y, rot)) for d in (1.0, 9.0, 3.0, 5.0)]
        ordered = ranker(placement, ev, list(moves))
        self.assertEqual([m[1][0] - x for m in ordered], [9.0, 5.0, 3.0, 1.0])

    def test_short_lists_are_left_alone(self):
        design, _, ctx = bench_context()
        fz = MoveFeaturizer(design, ctx.locked)
        placement = ctx.current()
        ev = ctx.evaluate(placement)
        fz.refresh(placement, ev)
        ranker = ModelRanker(fz, MeanModel(value=0.0))
        ref = ctx.movable()[0]
        moves = [(ref, placement[ref])]
        self.assertEqual(ranker(placement, ev, list(moves)), moves)
        self.assertEqual(ranker.calls, 0)


class AdversarialRankerTests(unittest.TestCase):
    """Model tamamen yanilsa bile sistem gerileyemez.

    ML'i uretim hattina sokmanin sarti buydu: model KARAR vermiyor, SIRA
    oneriyor; kabul karari hala hakemde.
    """

    def worst_first(self, placement, evaluation, moves):
        return list(reversed(moves))

    def exploding(self, placement, evaluation, moves):
        raise RuntimeError("bozuk model")

    def test_reversed_order_cannot_make_things_worse(self):
        _, _, ctx = bench_context()
        ctx.move_ranker = self.worst_first
        start = ctx.current()
        before = ctx.evaluate(start)
        after = ctx.evaluate(polish(start, ctx, budget_s=BUDGET))
        self.assertGreaterEqual(after.key, before.key)

    def test_broken_ranker_does_not_break_the_search(self):
        _, _, ctx = bench_context()
        ctx.move_ranker = self.exploding
        start = ctx.current()
        before = ctx.evaluate(start)
        result = polish(start, ctx, budget_s=BUDGET)
        self.assertGreaterEqual(ctx.evaluate(result).key, before.key)

    def test_missing_model_falls_back_to_auto_behaviour(self):
        _, _, ctx = bench_context()
        placer = Learned(model_path=Path("yok-boyle-bir-model.json"))
        before = ctx.evaluate(ctx.current())
        result = placer.run(ctx)
        self.assertIsNone(placer.ranker)
        self.assertGreaterEqual(ctx.evaluate(result).key, before.key)

    def test_shipped_model_matches_the_frozen_schema(self):
        path = Path(__file__).resolve().parent.parent / "pcbqa" / "ml" / "models" / "move-v1.json"
        if not path.exists():
            self.skipTest("depoda egitilmis model yok")
        model = load_model(path)
        model.check_schema(FEATURE_NAMES, FEATURE_VERSION)  # hata verirse test duser


if __name__ == "__main__":
    unittest.main()
