"""Asama 4c/4d: atomik yazma ve baglanti koruyan sembol tasima."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from pcbqa.kicadcli import KicadCliError, find_kicad_cli
from pcbqa.schematic import read_schematic
from pcbqa.sch_move import SchMoveError, apply_move, plan_move
from pcbqa.sch_verify import compare, connectivity_of
from pcbqa.sch_write import (
    SchWriteError,
    atomic_write_text,
    backup_file,
    lock_files,
    write_tree,
)
from pcbqa.sexpr import parse_with_stats

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
PROJECT_DIR = SAMPLES / "pic_programmer"
ROOT_SCH = PROJECT_DIR / "pic_programmer.kicad_sch"


def kicad_cli_available() -> bool:
    try:
        find_kicad_cli()
        return True
    except KicadCliError:
        return False


class AtomicWriteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-write-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_writes_content(self):
        target = self.tmp / "a.txt"
        written = atomic_write_text(target, "merhaba")
        self.assertEqual(target.read_text(encoding="utf-8"), "merhaba")
        self.assertEqual(written, len("merhaba".encode("utf-8")))

    def test_replaces_existing_file(self):
        target = self.tmp / "a.txt"
        target.write_text("eski", encoding="utf-8")
        atomic_write_text(target, "yeni")
        self.assertEqual(target.read_text(encoding="utf-8"), "yeni")

    def test_leaves_no_temporary_files_behind(self):
        target = self.tmp / "a.txt"
        atomic_write_text(target, "icerik")
        leftovers = [p.name for p in self.tmp.iterdir() if p.name != "a.txt"]
        self.assertEqual(leftovers, [])

    def test_backup_never_overwrites_an_existing_backup(self):
        target = self.tmp / "a.txt"
        target.write_text("bir", encoding="utf-8")
        first = backup_file(target)
        target.write_text("iki", encoding="utf-8")
        second = backup_file(target)
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_text(encoding="utf-8"), "bir")
        self.assertEqual(second.read_text(encoding="utf-8"), "iki")


class LockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-lock-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.sch = self.tmp / "proje.kicad_sch"
        self.sch.write_text("(kicad_sch)", encoding="utf-8")

    def test_no_lock_when_project_is_closed(self):
        self.assertEqual(lock_files(self.sch), [])

    def test_detects_kicad_lock_file(self):
        (self.tmp / "~proje.kicad_pro.lck").touch()
        self.assertTrue(lock_files(self.sch))

    def test_write_refuses_while_the_project_is_open(self):
        (self.tmp / "~proje.kicad_pro.lck").touch()
        root, _ = parse_with_stats("(kicad_sch (version 1))")
        with self.assertRaises(SchWriteError) as caught:
            write_tree(self.sch, root, apply=True)
        self.assertIn("acik gorunuyor", str(caught.exception))

    def test_write_can_be_forced_past_the_lock(self):
        (self.tmp / "~proje.kicad_pro.lck").touch()
        root, _ = parse_with_stats("(kicad_sch (version 1))")
        result = write_tree(self.sch, root, apply=True, backup=False, allow_open_project=True)
        self.assertTrue(result.written)
        self.assertTrue(any("kilit" in n for n in result.notes))

    def test_dry_run_never_touches_the_file(self):
        before = self.sch.read_text(encoding="utf-8")
        root, _ = parse_with_stats("(kicad_sch (version 999))")
        result = write_tree(self.sch, root, apply=False)
        self.assertFalse(result.written)
        self.assertEqual(self.sch.read_text(encoding="utf-8"), before)


class MovePlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sch = read_schematic(ROOT_SCH)

    def test_unknown_reference_raises(self):
        with self.assertRaises(SchMoveError):
            plan_move(self.sch, "YOK99", 1.27, 0.0)

    def test_plan_drags_the_wires_attached_to_pins(self):
        plan = plan_move(self.sch, "R1", 2.54, 0.0)
        self.assertTrue(plan.ok, plan.blockers)
        self.assertEqual(plan.wire_endpoints, 2)
        self.assertEqual(plan.new_pos, (81.28, 43.18))

    def test_snapping_changes_the_effective_delta(self):
        """Izgaraya oturtma kaydirmayi degistirir; tel uclari AYNI miktarda
        kaymali, yoksa pinden kopar."""
        plan = plan_move(self.sch, "R1", 1.0, 0.0, snap=True)
        self.assertEqual(plan.dx, 1.27)
        loose = plan_move(self.sch, "R1", 1.0, 0.0, snap=False)
        self.assertEqual(loose.dx, 1.0)

    def test_zero_delta_is_reported_not_applied(self):
        plan = plan_move(self.sch, "R1", 0.1, 0.0, snap=True)
        self.assertEqual(plan.dx, 0.0)
        self.assertTrue(plan.warnings)

    def test_direct_pin_contact_blocks_the_move(self):
        """Guc sembolleri telsiz, dogrudan pine yapisir - uzatilacak tel yok."""
        plan = plan_move(self.sch, "#PWR022", 2.54, 0.0)
        self.assertFalse(plan.ok)
        self.assertIn("dogrudan temas", plan.blockers[0])


@unittest.skipUnless(kicad_cli_available(), "kicad-cli yok")
class MoveApplyTests(unittest.TestCase):
    """Uctan uca: gercek dosya, gercek netlist kalkani."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-move-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = self.tmp / "pic_programmer"
        shutil.copytree(PROJECT_DIR, self.project)
        for lock in self.project.glob("~*.lck"):
            lock.unlink()
        self.sch = self.project / "pic_programmer.kicad_sch"
        self.original = self.sch.read_bytes()

    def test_dry_run_passes_the_shield_without_writing(self):
        result = apply_move(self.sch, "R1", 2.54, 0.0, apply=False)
        self.assertIsNotNone(result.diff)
        self.assertTrue(result.diff.ok, result.diff.describe())
        self.assertFalse(result.applied)
        self.assertEqual(self.sch.read_bytes(), self.original)

    def test_apply_preserves_connectivity(self):
        before = connectivity_of(self.sch)
        result = apply_move(self.sch, "R1", 2.54, 0.0, apply=True)
        self.assertTrue(result.applied)
        self.assertTrue(compare(before, connectivity_of(self.sch)).ok)

        moved = read_schematic(self.sch).by_ref("R1")
        self.assertEqual((moved.x, moved.y), (81.28, 43.18))
        self.assertEqual(read_schematic(self.sch).stray_parens, 0)

    def test_apply_leaves_a_backup(self):
        result = apply_move(self.sch, "R1", 2.54, 0.0, apply=True)
        self.assertIsNotNone(result.write.backup)
        self.assertEqual(result.write.backup.read_bytes(), self.original)

    def test_a_move_that_would_merge_nets_is_refused(self):
        """Geometrik engeller bunu goremez - yalnizca netlist kalkani gorur.

        R1 buraya tasinirsa /VPP_ON agi VCC'ye kaynar.
        """
        result = apply_move(self.sch, "R1", 12.7, -10.16, apply=True)
        self.assertFalse(result.applied)
        self.assertIsNotNone(result.diff)
        self.assertFalse(result.diff.ok)
        self.assertEqual(self.sch.read_bytes(), self.original, "reddedilen yazma dosyaya dokunmus")

    def test_uuids_are_preserved(self):
        before = {s.ref: s.uuid for s in read_schematic(self.sch).symbols}
        apply_move(self.sch, "R1", 2.54, 0.0, apply=True)
        after = {s.ref: s.uuid for s in read_schematic(self.sch).symbols}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
