"""Asama 4g: sematikten karta yansitma (Update PCB from Schematic).

Kabul olcutu tek cumle: sematige eklenen bilesen, karta DOGRU AGLARLA ve
mevcut yerlesimi bozmadan gitmeli.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from pcbqa import symlib
from pcbqa.kicadcli import KicadCliError, find_kicad_cli
from pcbqa.pcb import read_board
from pcbqa.pcb_sync import PcbSyncError, board_paths, plan_sync, symbol_path, sync
from pcbqa.sch_add import add_symbols
from pcbqa.schematic import read_schematic
from pcbqa.sexpr import parse_with_stats

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
PROJECT_DIR = SAMPLES / "pic_programmer"
LOCK_NAME = "~pic_programmer.kicad_pro.lck"


def kicad_cli_available() -> bool:
    try:
        find_kicad_cli()
        return True
    except KicadCliError:
        return False


def device_library_available() -> bool:
    try:
        symlib.get_symbol("Device:R")
        return True
    except symlib.SymLibError:
        return False


class SandboxProject(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-sync-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = self.tmp / "proje"
        shutil.copytree(PROJECT_DIR, self.project)
        (self.project / LOCK_NAME).unlink(missing_ok=True)
        self.sch = self.project / "pic_programmer.kicad_sch"
        self.pcb = self.project / "pic_programmer.kicad_pcb"

    def unlock(self):
        (self.project / LOCK_NAME).unlink(missing_ok=True)


class PathMatchingTests(SandboxProject):
    def test_board_footprints_carry_schematic_paths(self):
        root, _ = parse_with_stats(self.pcb.read_text(encoding="utf-8", errors="replace"))
        paths = board_paths(root)
        self.assertTrue(paths, "kartta hic yol bagi yok")
        self.assertTrue(all(p.startswith("/") for p in paths))

    def test_symbol_path_matches_the_board(self):
        """Esleme referansla degil UUID YOLUYLA yapilir - kart da oyle saklar."""
        root, _ = parse_with_stats(self.pcb.read_text(encoding="utf-8", errors="replace"))
        paths = board_paths(root)
        schematic = read_schematic(self.sch)
        for path, ref in list(paths.items())[:5]:
            if ref:
                self.assertEqual(symbol_path(schematic, ref), path)

    def test_unknown_reference_raises(self):
        schematic = read_schematic(self.sch)
        with self.assertRaises(KeyError):
            symbol_path(schematic, "YOK99")


@unittest.skipUnless(kicad_cli_available(), "kicad-cli yok")
class UpToDateBoardTests(SandboxProject):
    def test_untouched_project_needs_no_change(self):
        plan, _ = plan_sync(self.sch, self.pcb)
        self.unlock()
        self.assertEqual(plan.add, [], "dokunulmamis projede eklenecek bir sey olmamali")

    def test_sync_is_a_no_op_when_up_to_date(self):
        before = self.pcb.read_bytes()
        result = sync(self.sch, self.pcb, apply=True)
        self.unlock()
        self.assertFalse(result.applied)
        self.assertEqual(self.pcb.read_bytes(), before)


@unittest.skipUnless(kicad_cli_available() and device_library_available(),
                     "kicad-cli veya sembol kutuphanesi yok")
class SyncTests(SandboxProject):
    FP = "Resistor_SMD:R_0805_2012Metric"

    def _add(self, count=2, connect=("1=VCC", "2=GND")):
        result = add_symbols(self.sch, "Device:R", count, value="4k7", footprint=self.FP,
                             connect=list(connect), apply=True)
        self.unlock()
        self.assertTrue(result.applied, result.plan.describe())
        return [s.ref for s in result.plan.symbols]

    def test_new_symbols_reach_the_board_with_their_nets(self):
        refs = self._add()
        result = sync(self.sch, self.pcb, apply=True)
        self.unlock()
        self.assertTrue(result.applied, result.plan.describe())
        self.assertEqual(sorted(result.verified), sorted(refs))

        board = read_board(self.pcb)
        for ref in refs:
            comp = board.by_ref(ref)
            self.assertIsNotNone(comp, f"{ref} karta gitmedi")
            self.assertEqual(comp.footprint_id, self.FP)
            self.assertEqual({p.net for p in comp.pads}, {"VCC", "GND"})

    def test_existing_components_are_not_moved(self):
        before = {c.ref: (c.x, c.y, c.rotation, c.footprint_id)
                  for c in read_board(self.pcb).components}
        self._add(1, connect=())
        sync(self.sch, self.pcb, apply=True)
        self.unlock()
        after = {c.ref: (c.x, c.y, c.rotation, c.footprint_id)
                 for c in read_board(self.pcb).components}
        for ref, value in before.items():
            self.assertEqual(after[ref], value, f"{ref} kart uzerinde degismis")

    def test_new_components_land_outside_the_existing_ones(self):
        board_before = read_board(self.pcb)
        right_edge = max(c.x for c in board_before.components)
        refs = self._add(1, connect=())
        sync(self.sch, self.pcb, apply=True)
        self.unlock()
        comp = read_board(self.pcb).by_ref(refs[0])
        self.assertGreater(comp.x, right_edge, "yeni bilesen mevcutlarin ustune kondu")

    def test_dry_run_writes_nothing(self):
        self._add(1, connect=())
        before = self.pcb.read_bytes()
        result = sync(self.sch, self.pcb)
        self.unlock()
        self.assertFalse(result.applied)
        self.assertEqual(self.pcb.read_bytes(), before)
        self.assertEqual(len(result.plan.add), 1)

    def test_backup_is_written(self):
        self._add(1, connect=())
        result = sync(self.sch, self.pcb, apply=True)
        self.unlock()
        self.assertIsNotNone(result.write.backup)
        self.assertTrue(result.write.backup.exists())

    def test_running_twice_adds_nothing_the_second_time(self):
        self._add(1, connect=())
        sync(self.sch, self.pcb, apply=True)
        self.unlock()
        second = sync(self.sch, self.pcb, apply=True)
        self.unlock()
        self.assertEqual(second.plan.add, [])

    def test_symbol_without_footprint_is_reported_not_written(self):
        result_add = add_symbols(self.sch, "Device:R", 1, footprint="",
                                 check_footprint=False, apply=True)
        self.unlock()
        ref = result_add.plan.symbols[0].ref
        result = sync(self.sch, self.pcb, apply=True)
        self.unlock()
        self.assertIn(ref, result.plan.without_footprint)
        self.assertIsNone(read_board(self.pcb).by_ref(ref))

    def test_missing_footprint_library_blocks(self):
        add_symbols(self.sch, "Device:R", 1, footprint="Uydurma:Sey",
                    check_footprint=False, apply=True)
        self.unlock()
        result = sync(self.sch, self.pcb, apply=True)
        self.unlock()
        self.assertFalse(result.applied)
        self.assertTrue(result.plan.problems)


@unittest.skipUnless(kicad_cli_available() and device_library_available(),
                     "kicad-cli veya sembol kutuphanesi yok")
class MultiUnitSyncTests(SandboxProject):
    """Cok birimli sembol kartta TEK paket olmali."""

    def test_gates_of_one_reference_become_one_footprint(self):
        result_add = add_symbols(self.sch, "74xx:74LS125", 3,
                                 footprint="Package_DIP:DIP-14_W7.62mm", apply=True)
        self.unlock()
        refs = {s.ref for s in result_add.plan.symbols}
        self.assertEqual(len(refs), 1, "3 kapi tek referansta olmali")

        result = sync(self.sch, self.pcb, apply=True)
        self.unlock()
        self.assertEqual(len(result.plan.add), 1, "kartta tek footprint olmali")

        board = read_board(self.pcb)
        placed = [c for c in board.components if c.ref in refs]
        self.assertEqual(len(placed), 1)

    def test_unit_map_is_written(self):
        add_symbols(self.sch, "74xx:74LS125", 2,
                    footprint="Package_DIP:DIP-14_W7.62mm", apply=True)
        self.unlock()
        sync(self.sch, self.pcb, apply=True)
        self.unlock()
        text = self.pcb.read_text(encoding="utf-8", errors="replace")
        self.assertIn('(name "A")', text)
        self.assertIn('(name "B")', text)


@unittest.skipUnless(kicad_cli_available() and device_library_available(),
                     "kicad-cli veya sembol kutuphanesi yok")
class KicadAcceptsTheBoardTests(SandboxProject):
    """KiCad'in KENDI dogrulamasi: DRC + sematik paritesi."""

    def test_drc_and_parity_stay_clean(self):
        import json
        import subprocess

        add_symbols(self.sch, "Device:R", 2, value="4k7",
                    footprint="Resistor_SMD:R_0805_2012Metric",
                    connect=["1=VCC", "2=GND"], apply=True)
        self.unlock()
        sync(self.sch, self.pcb, apply=True)
        self.unlock()

        report = self.tmp / "drc.json"
        subprocess.run(
            [str(find_kicad_cli()), "pcb", "drc", "--schematic-parity",
             "--format", "json", "-o", str(report), str(self.pcb)],
            capture_output=True, check=False,
        )
        self.unlock()
        data = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(data.get("violations") or [], [])
        self.assertEqual(data.get("schematic_parity") or [], [],
                         "kart ile sematik arasinda parite farki var")
        # Baglanmamis bakir: her yeni pad bir ag istiyor ama henuz yol yok.
        # Bu BEKLENEN durumdur - yansitma yerlestirme/routing yapmaz.
        self.assertEqual(len(data.get("unconnected_items") or []), 4)


if __name__ == "__main__":
    unittest.main()
