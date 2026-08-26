"""Asama 4f: kutuphaneden sembol okuma ve sematige ekleme."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from pcbqa import symlib
from pcbqa.kicadcli import KicadCliError, find_kicad_cli
from pcbqa.sch_add import (
    SchAddError,
    add_symbols,
    free_slots,
    next_references,
    plan_add,
)
from pcbqa.sch_verify import Connectivity, compare_additive
from pcbqa.schematic import read_schematic

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
PROJECT_DIR = SAMPLES / "pic_programmer"
ROOT_SCH = PROJECT_DIR / "pic_programmer.kicad_sch"
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
    """Ornek projeyi gecici bir klasore kopyalar (asil dosyaya dokunulmaz)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-add-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = self.tmp / "proje"
        shutil.copytree(PROJECT_DIR, self.project)
        # `kicad-cli` calismalarindan kalmis olabilecek bayat kilit
        (self.project / LOCK_NAME).unlink(missing_ok=True)
        self.sch = self.project / ROOT_SCH.name


# --------------------------------------------------------------------------
# symlib
# --------------------------------------------------------------------------


@unittest.skipUnless(device_library_available(), "KiCad sembol kutuphanesi yok")
class SymLibTests(unittest.TestCase):
    def test_resolves_a_stock_symbol(self):
        sym = symlib.get_symbol("Device:R")
        self.assertEqual(sym.name, "R")
        self.assertEqual(sym.library, "Device")
        self.assertEqual(sym.reference_prefix, "R")
        self.assertEqual({p.number for p in sym.pins}, {"1", "2"})

    def test_unknown_library_names_the_problem(self):
        with self.assertRaises(symlib.SymLibError) as ctx:
            symlib.get_symbol("YokBoyleBirKutuphane:R")
        self.assertIn("kutuphane bulunamadi", str(ctx.exception))

    def test_unknown_symbol_names_the_problem(self):
        with self.assertRaises(symlib.SymLibError) as ctx:
            symlib.get_symbol("Device:YokBoyleBirSembol")
        self.assertIn("sembol bulunamadi", str(ctx.exception))

    def test_lib_id_must_have_a_colon(self):
        with self.assertRaises(symlib.SymLibError):
            symlib.get_symbol("R")

    def test_definition_is_named_for_the_schematic(self):
        """Dosya icine yazilan tanim `Kutuphane:Ad` adini tasir."""
        definition = symlib.resolve_definition(symlib.get_symbol("Device:R"))
        self.assertEqual(symlib.head_atom(definition), "Device:R")

    def test_versioned_variable_falls_back(self):
        """Tablo eski surum adini tasiyorsa ayni turden degiskene duser."""
        env = {"KICAD10_SYMBOL_DIR": "C:/kicad/symbols"}
        self.assertEqual(
            symlib.expand("${KICAD9_SYMBOL_DIR}/Device.kicad_sym", env),
            "C:/kicad/symbols/Device.kicad_sym",
        )

    def test_unknown_variable_is_left_alone(self):
        self.assertEqual(symlib.expand("${YOK}/a.kicad_sym", {}), "${YOK}/a.kicad_sym")


# --------------------------------------------------------------------------
# Referans numaralandirma ve yerlestirme (kutuphane gerekmez)
# --------------------------------------------------------------------------


class ReferenceNumberingTests(unittest.TestCase):
    def test_continues_after_the_highest_used_number(self):
        schematic = read_schematic(ROOT_SCH)
        used = {s.ref for s in schematic.symbols}
        new = next_references(schematic, "R", 3)
        self.assertEqual(len(new), 3)
        self.assertFalse(used & set(new), "var olan referans yeniden verildi")

    def test_fills_gaps_before_extending(self):
        """R1 ve R3 kullanimdaysa sirada R2 vardir - KiCad de boyle yapar."""

        class FakeSymbol:
            def __init__(self, ref):
                self.ref = ref

        class FakeSchematic:
            symbols = [FakeSymbol("R1"), FakeSymbol("R3")]

        self.assertEqual(next_references(FakeSchematic(), "R", 3), ["R2", "R4", "R5"])

    def test_other_prefixes_are_ignored(self):
        class FakeSymbol:
            def __init__(self, ref):
                self.ref = ref

        class FakeSchematic:
            symbols = [FakeSymbol("C1"), FakeSymbol("C2"), FakeSymbol("RV1")]

        self.assertEqual(next_references(FakeSchematic(), "R", 1), ["R1"])


class FreeSlotTests(unittest.TestCase):
    def test_slots_do_not_land_on_existing_symbols(self):
        schematic = read_schematic(ROOT_SCH)
        slots, _notes = free_slots(schematic, "/", 5, (2.54, 7.62))
        self.assertEqual(len(slots), 5)
        boxes = [
            s.bbox for s in schematic.symbols if s.sheet_path == "/" and s.bbox
        ]
        for x, y in slots:
            for x0, y0, x1, y1 in boxes:
                self.assertFalse(
                    x0 <= x <= x1 and y0 <= y <= y1,
                    f"({x}, {y}) mevcut bir govdenin icine dustu",
                )

    def test_slots_are_distinct(self):
        schematic = read_schematic(ROOT_SCH)
        slots, _ = free_slots(schematic, "/", 8, (2.54, 7.62))
        self.assertEqual(len(set(slots)), 8)


# --------------------------------------------------------------------------
# Kalkanin ekleme surumu (kicad-cli gerekmez - dogrudan yapi uzerinde)
# --------------------------------------------------------------------------


class AdditiveShieldTests(unittest.TestCase):
    def _conn(self, nets: dict[str, list[tuple[str, str]]]) -> Connectivity:
        partition = frozenset(frozenset(pins) for pins in nets.values())
        net_of = {pin: name for name, pins in nets.items() for pin in pins}
        components = frozenset(pin[0] for pins in nets.values() for pin in pins)
        return Connectivity(
            source=Path("x"), partition=partition, net_of=net_of, components=components
        )

    def test_pure_addition_passes(self):
        before = self._conn({"N1": [("R1", "1"), ("U1", "3")]})
        after = self._conn({
            "N1": [("R1", "1"), ("U1", "3")],
            "unconnected-(R2-Pad1)": [("R2", "1")],
        })
        self.assertTrue(compare_additive(before, after, {"R2"}).ok)

    def test_silently_touching_an_existing_net_is_rejected(self):
        """Yeni sembol var olan bir tele degerse kalkan yakalamali."""
        before = self._conn({"N1": [("R1", "1"), ("U1", "3")]})
        after = self._conn({"N1": [("R1", "1"), ("U1", "3"), ("R2", "1")]})
        diff = compare_additive(before, after, {"R2"})
        self.assertFalse(diff.ok)
        self.assertTrue(diff.regrouped)

    def test_breaking_an_existing_net_is_rejected(self):
        before = self._conn({"N1": [("R1", "1"), ("U1", "3")]})
        after = self._conn({"N1": [("R1", "1")], "N2": [("U1", "3")]})
        self.assertFalse(compare_additive(before, after, set()).ok)

    def test_unexpected_component_is_rejected(self):
        before = self._conn({"N1": [("R1", "1")]})
        after = self._conn({"N1": [("R1", "1")], "N2": [("R9", "1")]})
        self.assertFalse(compare_additive(before, after, {"R2"}).ok)

    def test_losing_a_component_is_rejected(self):
        before = self._conn({"N1": [("R1", "1"), ("U1", "3")]})
        after = self._conn({"N1": [("U1", "3")]})
        self.assertFalse(compare_additive(before, after, set()).ok)


# --------------------------------------------------------------------------
# Ekleme - dosya duzeyinde (kutuphane gerekir, kicad-cli gerekmez)
# --------------------------------------------------------------------------


@unittest.skipUnless(device_library_available(), "KiCad sembol kutuphanesi yok")
class AddSymbolsTests(SandboxProject):
    def test_dry_run_touches_nothing(self):
        before = self.sch.read_bytes()
        result = add_symbols(self.sch, "Device:R", 3, verify=False)
        self.assertFalse(result.applied)
        self.assertEqual(self.sch.read_bytes(), before)
        self.assertEqual(len(result.plan.symbols), 3)

    def test_apply_writes_readable_symbols(self):
        result = add_symbols(self.sch, "Device:R", 5, value="10k", verify=False, apply=True)
        self.assertTrue(result.applied)

        schematic = read_schematic(self.sch)
        for new in result.plan.symbols:
            sym = schematic.by_ref(new.ref)
            self.assertIsNotNone(sym, f"{new.ref} geri okunamadi")
            self.assertEqual(sym.lib_id, "Device:R")
            self.assertEqual(sym.value, "10k")
            self.assertEqual(len(sym.pins), 2)
            self.assertTrue(sym.on_grid(), f"{new.ref} izgarada degil")

    def test_existing_symbols_are_untouched(self):
        before = {s.ref: (s.x, s.y, s.uuid) for s in read_schematic(self.sch).symbols}
        add_symbols(self.sch, "Device:R", 2, verify=False, apply=True)
        after = {s.ref: (s.x, s.y, s.uuid) for s in read_schematic(self.sch).symbols}
        for ref, value in before.items():
            self.assertEqual(after[ref], value, f"{ref} degismis")

    def test_library_definition_is_merged_once(self):
        first = add_symbols(self.sch, "Device:R", 1, verify=False, apply=True)
        self.assertTrue(first.plan.library_merged)
        second = add_symbols(self.sch, "Device:R", 1, verify=False, apply=True)
        self.assertFalse(second.plan.library_merged, "tanim ikinci kez eklendi")

        text = self.sch.read_text(encoding="utf-8")
        self.assertEqual(text.count('(symbol "Device:R"'), 1)

    def test_second_run_continues_numbering(self):
        first = add_symbols(self.sch, "Device:R", 2, verify=False, apply=True)
        second = add_symbols(self.sch, "Device:R", 2, verify=False, apply=True)
        firsts = {s.ref for s in first.plan.symbols}
        seconds = {s.ref for s in second.plan.symbols}
        self.assertFalse(firsts & seconds, "ayni referans iki kez verildi")

    def test_backup_is_written(self):
        result = add_symbols(self.sch, "Device:R", 1, verify=False, apply=True)
        self.assertIsNotNone(result.write.backup)
        self.assertTrue(result.write.backup.exists())

    def test_explicit_position_is_snapped_to_the_grid(self):
        """Izgara disi konum sessizce kabul edilmez: oturtulur ve soylenir."""
        result = add_symbols(self.sch, "Device:R", 2, at=(200.0, 30.0), step=10.16,
                             verify=False, apply=True)
        xs = [s.x for s in result.plan.symbols]
        self.assertEqual(xs, [199.39, 209.55])  # 200.0 -> 157 x 1.27
        self.assertTrue(any("izgara" in n for n in result.plan.notes))
        schematic = read_schematic(self.sch)
        self.assertAlmostEqual(schematic.by_ref(result.plan.symbols[0].ref).x, 199.39)

    def test_on_grid_position_is_kept_exactly(self):
        result = add_symbols(self.sch, "Device:R", 1, at=(203.2, 30.48),
                             verify=False, apply=True)
        self.assertEqual((result.plan.symbols[0].x, result.plan.symbols[0].y), (203.2, 30.48))
        self.assertFalse(any("izgara" in n for n in result.plan.notes))

    def test_value_and_footprint_defaults_come_from_the_library(self):
        result = add_symbols(self.sch, "Device:R", 1, verify=False, apply=True)
        sym = read_schematic(self.sch).by_ref(result.plan.symbols[0].ref)
        self.assertEqual(sym.value, "R")
        self.assertEqual(sym.footprint, "")

    def test_footprint_is_written(self):
        fp = "Resistor_SMD:R_0805_2012Metric"
        result = add_symbols(self.sch, "Device:R", 1, footprint=fp, verify=False, apply=True)
        sym = read_schematic(self.sch).by_ref(result.plan.symbols[0].ref)
        self.assertEqual(sym.footprint, fp)

    def test_unknown_sheet_is_refused(self):
        with self.assertRaises(SchAddError):
            add_symbols(self.sch, "Device:R", 1, sheet_path="/yok", verify=False)

    def test_count_must_be_positive(self):
        with self.assertRaises(SchAddError):
            add_symbols(self.sch, "Device:R", 0, verify=False)

    def test_open_project_blocks_writing(self):
        (self.project / LOCK_NAME).write_text("{}", encoding="utf-8")
        from pcbqa.sch_write import SchWriteError

        with self.assertRaises(SchWriteError):
            add_symbols(self.sch, "Device:R", 1, verify=False, apply=True)


# --------------------------------------------------------------------------
# Uctan uca: gercek netlist kalkaniyla
# --------------------------------------------------------------------------


@unittest.skipUnless(kicad_cli_available() and device_library_available(),
                     "kicad-cli veya sembol kutuphanesi yok")
class EndToEndTests(SandboxProject):
    def test_shield_accepts_a_clean_addition(self):
        result = add_symbols(self.sch, "Device:R", 5, value="10k", apply=True)
        self.assertTrue(result.applied)
        self.assertIsNotNone(result.diff)
        self.assertTrue(result.diff.ok, result.diff)
        self.assertEqual(
            set(result.diff.added_components), {s.ref for s in result.plan.symbols}
        )

    def test_kicad_reads_the_new_symbols_back(self):
        from pcbqa.sch_verify import connectivity_of

        result = add_symbols(self.sch, "Device:R", 3, apply=True)
        conn = connectivity_of(self.sch)
        (self.project / LOCK_NAME).unlink(missing_ok=True)
        for new in result.plan.symbols:
            self.assertIn(new.ref, conn.components)

    def test_shield_leaves_no_lock_in_the_project(self):
        """Kalkan kum havuzunda calisir; kullanicinin klasorune kilit birakmaz."""
        add_symbols(self.sch, "Device:R", 1)
        self.assertFalse((self.project / LOCK_NAME).exists())


if __name__ == "__main__":
    unittest.main()
