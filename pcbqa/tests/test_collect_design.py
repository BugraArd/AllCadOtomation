"""Evre 3c: tasarim seviyesi veri toplama (varyant siralayici icin).

Korunan degismezler:

  * OZNITELIK SEMASI. Vektor uzunlugu ile ad listesi ayrisirsa veri kumesi
    sessizce yanlis yorumlanir - `Dataset.add` uzunlugu denetler, bu testler
    de sirayi ve icerigi denetler.
  * TOHUM OZNITELIK DEGIL. Ayni tasarim kararlari farkli tohumlarla AYNI
    oznitelik vektorunu vermeli; aksi halde model arama gurultusunu
    ezberlemeye davet edilir ve gurultu tabani olculemez.
  * ETIKET SIRASI. Skor baskin, sonra HPWL. Bu bozulursa veri kumesi
    "kotu karti iyi" diye etiketler ve hata modelde degil VERIDE olur.
  * LISANS. Kaynagi bilinmeyen veri korpusa alinmaz (LM5116 emsali).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pcbqa.explore import ExploreResult, Variant
from pcbqa.generate import GenerateResult
from pcbqa.ml.collect_design import (
    FEATURE_NAMES,
    FEATURE_VERSION,
    CollectError,
    Topology,
    features_of,
    intent_files,
    label_of,
    noise_floor,
    samples_from_run,
)
from pcbqa.ml.dataset import Dataset, Sample

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
INTENTS = SAMPLES / "niyetler"


def _topology(**kwargs) -> Topology:
    base = dict(components=18, nets=11, pins=60, mean_degree=5.5, max_degree=20,
                total_area=280.0, largest_area=98.0, ics=2, passives=13, connectors=2)
    base.update(kwargs)
    return Topology(**base)


def _variant(index=1, density=0.25, width=50.0, height=35.0, seed=0,
             score=100.0, errors=0, warnings=0, hpwl=180.0) -> Variant:
    return Variant(index=index, density=density, width=width, height=height,
                   seed=seed, score=score, errors=errors, warnings=warnings,
                   hpwl_mm=hpwl)


def _result(variants: list[Variant], best: Variant | None = None) -> ExploreResult:
    generated = GenerateResult(name="t", folder=Path("."), sch=Path("t.kicad_sch"),
                               pcb=Path("t.kicad_pcb"))
    return ExploreResult(generated=generated, variants=variants,
                         best=best or max(variants, key=lambda v: v.key))


class FeatureTests(unittest.TestCase):
    def test_vector_matches_the_name_list(self):
        vector = features_of(_topology(), _variant())
        self.assertEqual(len(vector), len(FEATURE_NAMES))

    def test_seed_is_not_a_feature(self):
        """Ayni tasarim, farkli tohum -> AYNI oznitelik vektoru.

        Gurultu tabani olcumu tam olarak bu esitlige dayanir.
        """
        topology = _topology()
        first = features_of(topology, _variant(seed=0))
        second = features_of(topology, _variant(seed=7))
        self.assertEqual(first, second)

    def test_variant_conditions_reach_the_vector(self):
        topology = _topology()
        kucuk = features_of(topology, _variant(width=40.0, height=30.0, density=0.40))
        buyuk = features_of(topology, _variant(width=50.0, height=35.0, density=0.25))
        self.assertNotEqual(kucuk, buyuk)
        alan = FEATURE_NAMES.index("kart_alani")
        self.assertLess(kucuk[alan], buyuk[alan])

    def test_topology_reads_a_real_design(self):
        """Topoloji gercek bir tasarimdan okunabilmeli."""
        from pcbqa.harness import load_design

        design = load_design(SAMPLES / "bench_good.kicad_pcb")
        topology = Topology.of(design)
        self.assertGreater(topology.components, 10)
        self.assertGreater(topology.nets, 5)
        self.assertGreater(topology.total_area, 0.0)
        self.assertGreaterEqual(topology.pins, topology.nets)


class LabelTests(unittest.TestCase):
    def test_shorter_hpwl_scores_higher(self):
        kisa = label_of(_variant(hpwl=150.0), 100.0, 180.0)
        uzun = label_of(_variant(hpwl=200.0), 100.0, 180.0)
        self.assertGreater(kisa, uzun)

    def test_median_variant_labels_zero(self):
        self.assertAlmostEqual(label_of(_variant(hpwl=180.0), 100.0, 180.0), 0.0)

    def test_score_dominates_hpwl(self):
        """Kaliteden odun verilmez: dusuk skorlu ama kisa telli kart yenilmeli."""
        temiz = label_of(_variant(score=100.0, hpwl=200.0), 95.0, 180.0)
        kusurlu = label_of(_variant(score=90.0, hpwl=100.0), 95.0, 180.0)
        self.assertGreater(temiz, kusurlu)

    def test_zero_median_hpwl_falls_back_to_score(self):
        self.assertAlmostEqual(label_of(_variant(score=100.0), 100.0, 0.0), 0.0)


class SampleTests(unittest.TestCase):
    def test_group_and_batch_are_carried(self):
        samples = samples_from_run(_result([_variant(hpwl=150.0), _variant(hpwl=200.0)]),
                                   _topology(), group="niyetim", batch="parti-1")
        self.assertEqual({s.group for s in samples}, {"niyetim"})
        self.assertEqual({s.batch for s in samples}, {"parti-1"})

    def test_raw_measurements_are_kept(self):
        samples = samples_from_run(_result([_variant(hpwl=150.0, seed=3)]),
                                   _topology(), group="g", batch="b")
        extra = samples[0].extra
        self.assertEqual(extra["tohum"], 3)
        self.assertEqual(extra["hpwl_mm"], 150.0)
        self.assertEqual(extra["lisans"], "uretilmis")
        self.assertTrue(extra["secilen"])

    def test_missing_license_is_refused(self):
        """Kaynagi bilinmeyen veri korpusa alinmaz (LM5116 emsali)."""
        with self.assertRaises(CollectError) as ctx:
            samples_from_run(_result([_variant()]), _topology(),
                             group="g", batch="b", license_name="")
        self.assertIn("lisans", str(ctx.exception))

    def test_samples_fit_a_dataset(self):
        dataset = Dataset(feature_names=list(FEATURE_NAMES),
                          feature_version=FEATURE_VERSION)
        for sample in samples_from_run(_result([_variant(hpwl=150.0), _variant(hpwl=210.0)]),
                                       _topology(), group="g", batch="b"):
            dataset.add(sample)  # uzunluk uyusmazsa burada patlar
        self.assertEqual(len(dataset), 2)
        self.assertEqual(len(dataset.batches()), 1)


class NoiseFloorTests(unittest.TestCase):
    def _dataset(self, rows: list[tuple[list[float], float]]) -> Dataset:
        ds = Dataset(feature_names=["a", "b"], feature_version=1)
        for i, (x, y) in enumerate(rows):
            ds.add(Sample(features=x, label=y, group="g", batch=f"b{i // 2}"))
        return ds

    def test_identical_features_expose_irreducible_noise(self):
        ds = self._dataset([([1.0, 1.0], 0.0), ([1.0, 1.0], 1.0),
                            ([2.0, 2.0], 5.0), ([2.0, 2.0], 6.0)])
        floor = noise_floor(ds)
        self.assertEqual(floor["ayrik_oznitelik"], 2)
        self.assertEqual(floor["tekrarli_oznitelik"], 2)
        self.assertGreater(floor["gurultu_varyansi"], 0.0)
        self.assertLess(floor["aciklanabilir_ust_sinir"], 1.0)

    def test_noiseless_data_has_full_upper_bound(self):
        ds = self._dataset([([1.0, 1.0], 0.0), ([2.0, 2.0], 5.0)])
        floor = noise_floor(ds)
        self.assertEqual(floor["tekrarli_oznitelik"], 0)
        self.assertAlmostEqual(floor["aciklanabilir_ust_sinir"], 1.0)


class ReservedMetaTests(unittest.TestCase):
    """`meta` baslikta ayrilmis bir adi ezerse dosya SESSIZCE bozulur.

    Olculdu: meta'da "kind" olan bir veri kumesi sorunsuz yaziliyor, sonra
    `Dataset.load` "pcbqa veri kumesi degil" diye reddediyor ve sebebi
    hicbir yerde yazmiyor.
    """

    def test_reserved_key_is_refused_loudly(self):
        ds = Dataset(feature_names=["a"], feature_version=1, meta={"kind": "benim"})
        ds.add(Sample(features=[1.0], label=0.0))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as ctx:
                ds.save(Path(tmp) / "x.jsonl")
        self.assertIn("kind", str(ctx.exception))

    def test_ordinary_meta_survives_a_round_trip(self):
        ds = Dataset(feature_names=["a"], feature_version=1,
                     meta={"veri_turu": "tasarim-varyanti"})
        ds.add(Sample(features=[1.0], label=0.5, group="g", batch="b"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.jsonl"
            ds.save(path)
            geri = Dataset.load(path)
        self.assertEqual(geri.meta.get("veri_turu"), "tasarim-varyanti")
        self.assertEqual(len(geri), 1)


class IntentLibraryTests(unittest.TestCase):
    def test_library_is_discovered(self):
        paths = intent_files(INTENTS)
        self.assertGreaterEqual(len(paths), 5, "veri cesitliligi icin birden fazla niyet")

    def test_single_file_is_accepted(self):
        paths = intent_files(SAMPLES / "ornek-niyet.yaml")
        self.assertEqual(len(paths), 1)

    def test_missing_target_is_loud(self):
        with self.assertRaises(CollectError):
            intent_files(SAMPLES / "yok-boyle-bir-sey")

    def test_every_library_intent_resolves(self):
        """Kutuphanedeki her niyet plana acilabilmeli - veri toplama onlara dayaniyor."""
        from pcbqa import symlib
        from pcbqa.intent import plan_from_file

        try:
            symlib.get_symbol("Device:R")
        except symlib.SymLibError:
            self.skipTest("KiCad sembol kutuphanesi yok")
        for path in intent_files(INTENTS):
            plan = plan_from_file(path)
            self.assertTrue(plan.ok, f"{path.name}: {plan.problems}")
            self.assertGreater(len(plan.components), 0)


if __name__ == "__main__":
    unittest.main()
