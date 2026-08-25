from __future__ import annotations

import unittest

from pcbqa.ipc import apply_placement_to_board
from pcbqa.ipc_apply import Candidate, select_winner


class FakeVector2:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    @classmethod
    def from_xy_mm(cls, x: float, y: float):
        return cls(round(x * 1_000_000), round(y * 1_000_000))


class FakeAngle:
    def __init__(self, degrees: float) -> None:
        self.degrees = degrees

    @classmethod
    def from_degrees(cls, degrees: float):
        return cls(degrees)


class FakeText:
    def __init__(self, value: str) -> None:
        self.value = value


class FakeField:
    def __init__(self, ref: str) -> None:
        self.text = FakeText(ref)


class FakeFootprint:
    def __init__(self, ref: str, x: float, y: float, rot: float = 0.0, locked: bool = False) -> None:
        self.reference_field = FakeField(ref)
        self.position = FakeVector2.from_xy_mm(x, y)
        self.orientation = FakeAngle.from_degrees(rot)
        self.locked = locked


class FakeBoard:
    name = "bench_bad.kicad_pcb"

    def __init__(self) -> None:
        self.footprints = [
            FakeFootprint("U1", 10.0, 10.0),
            FakeFootprint("C1", 20.0, 20.0),
            FakeFootprint("J1", 0.0, 0.0, locked=True),
        ]
        self.commits = 0
        self.pushed = False
        self.saved = False

    def get_footprints(self):
        return self.footprints

    def begin_commit(self):
        self.commits += 1
        return object()

    def update_items(self, items):
        return list(items)

    def push_commit(self, _commit, _message):
        self.pushed = True

    def drop_commit(self, _commit):
        self.pushed = False

    def save(self):
        self.saved = True


class Score:
    def __init__(self, score: float, errors: int = 0, warnings: int = 0, hpwl: float = 0.0) -> None:
        self.score = score
        self.errors = errors
        self.warnings = warnings
        self.total_hpwl_mm = hpwl


class Result:
    def __init__(self, name: str, score: float, problems=None, errors: int = 0) -> None:
        self.placer = name
        self.after = Score(score, errors=errors)
        self.gain = score
        self.seconds = 1.0
        self.problems = list(problems or [])


class IpcApplyTests(unittest.TestCase):
    def test_dry_run_does_not_mutate_board(self):
        board = FakeBoard()
        summary = apply_placement_to_board(
            board,
            {"U1": (11.0, 12.0, 90.0), "J1": (5.0, 5.0, 0.0), "ZZ": (1.0, 1.0, 0.0)},
            vector2=FakeVector2,
            angle=FakeAngle,
            apply=False,
            locked_refs={"J1"},
        )

        self.assertEqual(summary.changed, 1)
        self.assertEqual(summary.missing_refs, ["ZZ"])
        self.assertEqual(summary.skipped_locked_refs, ["J1"])
        self.assertFalse(board.pushed)
        self.assertEqual(board.footprints[0].position.x, 10_000_000)

    def test_apply_updates_only_movable_footprints(self):
        board = FakeBoard()
        summary = apply_placement_to_board(
            board,
            {"U1": (11.0, 12.0, 90.0), "J1": (5.0, 5.0, 0.0)},
            vector2=FakeVector2,
            angle=FakeAngle,
            apply=True,
            save=True,
            locked_refs={"J1"},
        )

        self.assertEqual(summary.changed, 1)
        self.assertTrue(board.pushed)
        self.assertTrue(board.saved)
        self.assertEqual(board.footprints[0].position.x, 11_000_000)
        self.assertEqual(board.footprints[0].orientation.degrees, 90.0)
        self.assertEqual(board.footprints[2].position.x, 0)

    def test_select_winner_ignores_contract_violations(self):
        bad = Candidate("bad", Result("bad", 100, problems=["locked moved"]), {})
        good = Candidate("good", Result("good", 67), {})
        self.assertIs(select_winner([bad, good]), good)


if __name__ == "__main__":
    unittest.main()
