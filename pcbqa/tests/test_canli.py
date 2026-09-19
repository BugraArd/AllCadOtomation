"""Canli onizlemenin baska/eski bir karta uygulanmasini engelleyen sinirlar."""
from contextlib import contextmanager
from pathlib import Path
import hashlib
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pcbqa import canli
from pcbqa.ipc import IpcApplyError
from tests.test_ipc_apply import FakeBoard, FakeVector2, FakeAngle


class LiveBoard(FakeBoard):
    def __init__(self, folder):
        super().__init__()
        self.document = SimpleNamespace(project=SimpleNamespace(path=str(folder)))
        self.content = b"live board including unsaved edits"

    def save_as(self, filename, **kwargs):
        Path(filename).write_bytes(self.content)


class LiveTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.board = LiveBoard(self.folder)
        self.target = self.folder / self.board.name
        self.target.write_bytes(b"old disk board")

        @contextmanager
        def connection(*args):
            yield SimpleNamespace(get_board=lambda: self.board)

        self.enterContext(patch.object(canli, "connection", connection))
        self.enterContext(patch.object(canli, "_load_kipy", return_value=(None, FakeVector2, FakeAngle)))
        self.plan = canli.LivePlan(self.target, canli.board_identity(self.board),
            hashlib.sha256(self.board.content).hexdigest(),
            {"U1": (11, 12, 90)}, set(), "preview")

    def test_unsaved_live_snapshot_is_used_instead_of_disk(self):
        summary = canli.apply_plan(self.plan)
        self.assertEqual(summary.changed, 1)
        self.assertTrue(self.board.pushed)
        self.assertFalse(self.board.saved)
        self.assertEqual(self.target.read_bytes(), b"old disk board")

    def test_user_edit_after_preview_prevents_any_commit(self):
        self.board.content += b" user changed a net"
        with self.assertRaisesRegex(IpcApplyError, "onizlemeden sonra degisti"):
            canli.apply_plan(self.plan)
        self.assertEqual(self.board.commits, 0)

    def test_same_filename_in_another_folder_is_refused(self):
        self.board.document.project.path = str(self.folder / "other")
        with self.assertRaisesRegex(IpcApplyError, "secilen PCB"):
            canli.apply_plan(self.plan)
        self.assertEqual(self.board.commits, 0)

    def test_missing_document_path_is_not_treated_as_a_match(self):
        self.board.document.project.path = ""
        with self.assertRaises(IpcApplyError):
            canli.apply_plan(self.plan)
        self.assertEqual(self.board.commits, 0)

    def test_multiple_boards_require_an_explicit_target(self):
        (self.folder / "other.kicad_pcb").write_text("")
        with self.assertRaisesRegex(IpcApplyError, "tek bir"):
            canli.project_file(self.folder, ".kicad_pcb")

    def test_missing_project_does_not_select_working_directory(self):
        with self.assertRaisesRegex(IpcApplyError, "proje secin"):
            canli.project_file("", ".kicad_pcb")


if __name__ == "__main__":
    unittest.main()
