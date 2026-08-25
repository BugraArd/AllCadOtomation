"""Asama 4e: sematik yerlestirme kalitesi ve toplu uygulama."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from pcbqa.kicadcli import KicadCliError, find_kicad_cli
from pcbqa.schematic import GRID_MM, read_schematic
from pcbqa.sch_apply import apply_placement, optimize_and_apply
from pcbqa.sch_place import SchematicArena, changed_only, improve
from pcbqa.sch_verify import compare, connectivity_of

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
PROJECT_DIR = SAMPLES / "pic_programmer"
ROOT_SCH = PROJECT_DIR / "pic_programmer.kicad_sch"
BUDGET = 3.0

# R1'i bu kadar kaydirmak pin 1'ini D2'nin pinine oturtur ve /VPP_ON agini
# VCC'ye kaynatir. Deger olculerek secildi (bkz. sch_verify testleri).
MERGE_DELTA = (12.7, -10.16)


def kicad_cli_available() -> bool:
    try:
        find_kicad_cli()
        return True
    except KicadCliError:
        return False


class ArenaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sch = read_schematic(ROOT_SCH)
        cls.arena = SchematicArena(cls.sch, "/")

    def test_keys_symbols_by_uuid_not_reference(self):
        """Cok birimli bilesenin her birimi ayri girdidir.

        Referansla anahtarlamak U2'nin dort birimini tek girdiye cokertip
        "U2 ve U2 cakisiyor" gibi hayali bulgular uretiyordu.
        """
        u2 = [s for s in self.sch.symbols if s.ref == "U2" and s.sheet_path == "/"]
        self.assertGreater(len(u2), 1, "test cok birimli bir sembol bekliyor")
        keys = [k for k, info in self.arena._symbols.items() if info.ref == "U2"]
        self.assertEqual(len(keys), len(u2))

    def test_the_untouched_schematic_scores_clean(self):
        ev = self.arena.evaluate(self.arena.current())
        self.assertEqual(ev.errors, 0)
        self.assertEqual(ev.warnings, 0)
        self.assertEqual(ev.score, 100.0)
        self.assertGreater(ev.total_hpwl_mm, 0.0)

    def test_virtual_symbols_are_locked(self):
        """Guc sembolleri pine kaynakli; bagimsiz hareketleri baglantiyi koparir."""
        for key, info in self.arena._symbols.items():
            if info.virtual:
                self.assertIn(key, self.arena.locked)

    def test_evaluation_is_fast_enough_for_local_search(self):
        import time

        current = self.arena.current()
        started = time.perf_counter()
        for _ in range(50):
            self.arena.evaluate(current)
        per_call = (time.perf_counter() - started) / 50
        self.assertLess(per_call, 0.05, "degerlendirme yerel arama icin cok yavas")

    def test_landing_a_pin_on_a_foreign_pin_is_an_error(self):
        """Netleri birlestiren tasima ucuz olcutle de yakalanmali.

        Bu delta olculerek secildi: R1 boyle tasinirsa pin 1'i D2'nin pinine
        oturur ve `/VPP_ON` agi `VCC`'ye kaynar. Kalkan da ayni sonucu verir.
        """
        current = self.arena.current()
        r1_key = next(k for k, i in self.arena._symbols.items() if i.ref == "R1")
        base = self.arena._symbols[r1_key].base
        candidate = dict(current)
        candidate[r1_key] = (base[0] + MERGE_DELTA[0], base[1] + MERGE_DELTA[1])
        ev = self.arena.evaluate(candidate)
        self.assertGreater(ev.errors, 0)
        self.assertLess(ev.score, 100.0)

    def test_moving_a_symbol_onto_another_body_is_not_a_connectivity_error(self):
        """Govde cakismasi bir UYARIDIR, baglanti kopmasi degil.

        Sembol tasinirken telleri de suruklendigi icin baska bir sembolun
        konumuna oturmak baglantiyi bozmaz - kalkan da bunu onaylar.
        """
        current = self.arena.current()
        r1_key = next(k for k, i in self.arena._symbols.items() if i.ref == "R1")
        d2_key = next(k for k, i in self.arena._symbols.items() if i.ref == "D2")
        candidate = dict(current)
        candidate[r1_key] = self.arena._symbols[d2_key].base
        ev = self.arena.evaluate(candidate)
        self.assertEqual(ev.errors, 0)

    def test_rounding_does_not_change_the_measurement(self):
        """Arama ile son olcum ayni koordinatlari gormeli.

        Kayan noktali bir konum (308.60999999999996) dosyaya yazilirken
        yuvarlanir (308.61). Bu 4e-14 mm'lik fark, tam kenar kenara duran iki
        govdenin cakisma testini ters cevirip skoru 100'den 97.4'e
        dusuruyordu - monotonluk garantisi kagit uzerinde kaliyordu.
        """
        current = self.arena.current()
        noisy = {k: (x + 1e-13, y - 1e-13) for k, (x, y) in current.items()}
        self.assertEqual(self.arena.evaluate(current).key, self.arena.evaluate(noisy).key)

    def test_exactly_touching_bodies_are_not_an_overlap(self):
        """1.27 mm izgarasinda bitisik semboller cok yaygin; tam temas
        cakisma sayilirsa her yerlesim hatali gorunur."""
        from pcbqa.rules import _boxes_overlap

        self.assertFalse(_boxes_overlap((0.0, 0.0, 5.0, 5.0), (5.0, 0.0, 10.0, 5.0)))
        self.assertFalse(_boxes_overlap((0.0, 0.0, 5.0, 5.0), (5.0 - 1e-14, 0.0, 10.0, 5.0)))
        self.assertTrue(_boxes_overlap((0.0, 0.0, 5.0, 5.0), (4.9, 0.0, 10.0, 5.0)))

    def test_nudge_steps_are_grid_multiples(self):
        """Izgara disi adim her denemeyi kural ihlaline dusurur."""
        for step in self.arena.nudge_steps:
            self.assertAlmostEqual(step / GRID_MM, round(step / GRID_MM), places=9)
        self.assertFalse(self.arena.allow_rotation)


class ImproveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sch = read_schematic(ROOT_SCH)

    def test_improvement_is_never_worse_than_the_start(self):
        _, before, after = improve(self.sch, "/", budget_s=BUDGET)
        self.assertGreaterEqual(after.key, before.key)

    def test_improvement_keeps_the_schematic_error_free(self):
        _, before, after = improve(self.sch, "/", budget_s=BUDGET)
        self.assertEqual(after.errors, 0)
        self.assertLessEqual(after.total_hpwl_mm, before.total_hpwl_mm)

    def test_result_is_deterministic_for_a_seed(self):
        first, _, _ = improve(self.sch, "/", budget_s=BUDGET, seed=7)
        second, _, _ = improve(self.sch, "/", budget_s=BUDGET, seed=7)
        self.assertEqual(
            changed_only(self.sch, first, "/").keys(),
            changed_only(self.sch, second, "/").keys(),
        )

    def test_changed_only_drops_untouched_symbols(self):
        placement, _, _ = improve(self.sch, "/", budget_s=BUDGET)
        moved = changed_only(self.sch, placement, "/")
        self.assertLess(len(moved), len(placement))
        for uuid, (x, y) in moved.items():
            sym = next(s for s in self.sch.symbols if s.uuid == uuid)
            self.assertFalse(abs(sym.x - x) < 1e-9 and abs(sym.y - y) < 1e-9)

    def test_locked_references_are_not_moved(self):
        placement, _, _ = improve(self.sch, "/", budget_s=BUDGET, locked={"R1"})
        moved = changed_only(self.sch, placement, "/")
        r1_uuids = {s.uuid for s in self.sch.symbols if s.ref == "R1" and s.sheet_path == "/"}
        self.assertFalse(r1_uuids & set(moved))


@unittest.skipUnless(kicad_cli_available(), "kicad-cli yok")
class BatchApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-4e-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = self.tmp / "pic_programmer"
        shutil.copytree(PROJECT_DIR, self.project)
        for lock in self.project.glob("~*.lck"):
            lock.unlink()
        self.sch = self.project / "pic_programmer.kicad_sch"
        self.original = self.sch.read_bytes()

    def test_empty_placement_changes_nothing(self):
        result = apply_placement(self.sch, {}, apply=True)
        self.assertFalse(result.applied)
        self.assertEqual(self.sch.read_bytes(), self.original)

    def test_dry_run_verifies_without_writing(self):
        moves, _, _, result = optimize_and_apply(self.sch, budget_s=BUDGET, apply=False)
        if not moves:
            self.skipTest("bu butcede iyilestirme bulunamadi")
        self.assertIsNotNone(result.diff)
        self.assertTrue(result.diff.ok, result.diff.describe())
        self.assertFalse(result.applied)
        self.assertEqual(self.sch.read_bytes(), self.original)

    def test_apply_preserves_connectivity(self):
        before = connectivity_of(self.sch)
        moves, _, _, result = optimize_and_apply(self.sch, budget_s=BUDGET, apply=True)
        if not moves:
            self.skipTest("bu butcede iyilestirme bulunamadi")
        self.assertTrue(result.applied)
        self.assertTrue(compare(before, connectivity_of(self.sch)).ok)
        self.assertEqual(read_schematic(self.sch).stray_parens, 0)

    def test_a_placement_that_breaks_connectivity_is_refused(self):
        """Netleri birlestiren yerlestirme: kalkan yakalamali, dosya el degmemeli."""
        sch = read_schematic(self.sch)
        r1 = next(s for s in sch.symbols if s.ref == "R1")
        target = (r1.x + MERGE_DELTA[0], r1.y + MERGE_DELTA[1])
        result = apply_placement(self.sch, {r1.uuid: target}, apply=True)
        self.assertFalse(result.applied)
        self.assertIsNotNone(result.diff)
        self.assertFalse(result.diff.ok)
        self.assertEqual(self.sch.read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()
