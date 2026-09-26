"""Canli PCB okuma/yazma: komut dili, kilit, eski plan ve commit sonrasi dogrulama."""
from contextlib import contextmanager
import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pcbqa import canli_pcb
from pcbqa.ipc import IpcApplyError
from tests.test_ipc_apply import FakeAngle, FakeField, FakeFootprint, FakeVector2
from tests.test_canli import LiveBoard


def footprint(ref, x, y, rot=0.0, locked=False, value="10k"):
    fp = FakeFootprint(ref, x, y, rot, locked)
    fp.value_field = FakeField(value)
    return fp


class CommandTests(unittest.TestCase):
    def test_turkish_and_suffixed_commands_parse(self):
        edits = canli_pcb.parse_commands(
            "R1'i konumunu 50 30,5 yap; c2 5 -2.5 mm kaydir\nU1 90 derece döndür; "
            "J1 kilidini aç; R1 değerini 4.7k yap")
        self.assertEqual([(e.ref, e.kind, e.args) for e in edits], [
            ("R1", "tasi", (50.0, 30.5)), ("C2", "kaydir", (5.0, -2.5)),
            ("U1", "dondur", (90.0,)), ("J1", "kilit_ac", ()), ("R1", "deger", ("4.7k",))])

    def test_one_unknown_part_rejects_the_whole_command(self):
        with self.assertRaisesRegex(IpcApplyError, "Anlasilmadi"):
            canli_pcb.parse_commands("R1 90 dondur; R1 sil")

    def test_edits_accumulate_and_angles_are_normalized(self):
        before = {"U1": canli_pcb.FpState("U1", 10, 10, 90, False, "x")}
        after, _ = canli_pcb.plan_states(before, canli_pcb.parse_commands(
            "U1 2 3 kaydir; U1 2 3 kaydir; U1 180 dondur"))
        self.assertEqual((after["U1"].x, after["U1"].y, after["U1"].rot), (14, 16, -90))
        self.assertEqual(before["U1"].x, 10)

    def test_locked_part_needs_explicit_unlock(self):
        before = {"J1": canli_pcb.FpState("J1", 0, 0, 0, True, "x")}
        with self.assertRaisesRegex(IpcApplyError, "kilitli"):
            canli_pcb.plan_states(before, canli_pcb.parse_commands("J1 1 1 kaydir"))
        after, _ = canli_pcb.plan_states(before, canli_pcb.parse_commands("J1 kilidini ac; J1 1 1 kaydir"))
        self.assertEqual((after["J1"].x, after["J1"].locked), (1, False))

    def test_value_edit_warns_about_schematic_sync(self):
        before = {"R1": canli_pcb.FpState("R1", 0, 0, 0, False, "10k")}
        _, warnings = canli_pcb.plan_states(before, canli_pcb.parse_commands("R1 degerini 12k yap"))
        self.assertIn("F8", warnings[0])

    def test_missing_ref_and_no_op_are_refused(self):
        before = {"R1": canli_pcb.FpState("R1", 5, 5, 0, False, "10k")}
        with self.assertRaisesRegex(IpcApplyError, "yok"):
            canli_pcb.plan_states(before, canli_pcb.parse_commands("R9 90 dondur"))
        after, w = canli_pcb.plan_states(before, canli_pcb.parse_commands("R1 konumunu 5 5 yap"))
        with self.assertRaisesRegex(IpcApplyError, "hicbir seyi"):
            canli_pcb.describe_plan(Path("x.kicad_pcb"), before, after, w)


class LivePcbTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.board = LiveBoard(self.folder)
        self.board.footprints = [footprint("U1", 10, 10), footprint("R1", 20, 20),
                                 footprint("J1", 0, 0, locked=True)]
        self.target = self.folder / self.board.name
        self.target.write_bytes(b"old disk board")
        # Gercek KiCad gibi: commit gorunur olana kadar okuma eski hali verir.
        visible = []

        def get_footprints():
            return copy.deepcopy(self.board.footprints if self.board.pushed or not visible else visible[0])

        def update(items):
            visible[:] = [copy.deepcopy(self.board.footprints)]
            by_id = {fp.reference_field.text.value: fp for fp in items}
            self.board.footprints = [by_id.get(fp.reference_field.text.value, fp) for fp in self.board.footprints]
            return items
        self.board.get_footprints = get_footprints
        self.board.update_items = update

        @contextmanager
        def connection(*args):
            yield SimpleNamespace(get_board=lambda: self.board)

        self.enterContext(patch.object(canli_pcb, "connection", connection))
        self.enterContext(patch.object(canli_pcb, "_load_kipy", return_value=(None, FakeVector2, FakeAngle)))

    def test_read_lists_live_footprints(self):
        text = canli_pcb.read_live(self.target)
        self.assertIn("3 bilesen", text)
        self.assertRegex(text, r"J1 .* evet")

    def test_preview_does_not_touch_board_and_apply_writes_one_commit(self):
        plan = canli_pcb.prepare_edit(self.target, "U1 konumunu 12 14 yap; R1 degerini 12k yap")
        self.assertEqual(self.board.commits, 0)
        self.assertEqual(plan.changed, ["R1", "U1"])
        message = canli_pcb.apply_edit(plan)
        self.assertEqual(self.board.commits, 1)
        self.assertTrue(self.board.pushed)
        self.assertFalse(self.board.saved)
        self.assertIn("2 bilesen", message)
        by_ref = {fp.reference_field.text.value: fp for fp in self.board.footprints}
        self.assertEqual((by_ref["U1"].position.x, by_ref["R1"].value_field.text.value), (12_000_000, "12k"))
        self.assertEqual(self.target.read_bytes(), b"old disk board")

    def test_edit_after_preview_prevents_commit(self):
        plan = canli_pcb.prepare_edit(self.target, "U1 90 dondur")
        self.board.content += b" user moved something"
        with self.assertRaisesRegex(IpcApplyError, "onizlemeden sonra degisti"):
            canli_pcb.apply_edit(plan)
        self.assertEqual(self.board.commits, 0)

    def test_wrong_board_is_refused(self):
        self.board.document.project.path = str(self.folder / "other")
        with self.assertRaisesRegex(IpcApplyError, "secilen PCB"):
            canli_pcb.prepare_edit(self.target, "U1 90 dondur")

    def test_readback_mismatch_asks_for_undo(self):
        plan = canli_pcb.prepare_edit(self.target, "U1 1 0 kaydir")
        self.board.update_items = lambda items: items  # KiCad kabul etti ama yazmadi
        with self.assertRaisesRegex(IpcApplyError, "Ctrl\\+Z"):
            canli_pcb.apply_edit(plan)

    def test_rejected_update_drops_commit(self):
        plan = canli_pcb.prepare_edit(self.target, "U1 1 0 kaydir")
        self.board.update_items = lambda items: []
        with self.assertRaisesRegex(IpcApplyError, "guncelledi"):
            canli_pcb.apply_edit(plan)
        self.assertFalse(self.board.pushed)

    def test_duplicate_references_block_writes(self):
        self.board.footprints.append(footprint("U1", 50, 50))
        with self.assertRaisesRegex(IpcApplyError, "tekrar eden"):
            canli_pcb.prepare_edit(self.target, "U1 90 dondur")


if __name__ == "__main__":
    unittest.main()
