"""BAGLA: var olan sembolleri tellemek.

Bu komut sematige YAZIYOR, yani bir hatasi kullanicinin devresini sessizce
degistirir. Korunan degismezler:

  * kuru calisma varsayilan; `--uygula` denmedikce dosyaya dokunulmaz,
  * yanlis pin/sembol adi SESSIZ gecmez,
  * ucten fazla oge bulusan noktaya junction konur (KiCad'in kendi kurali),
  * ve en onemlisi: yazdiktan sonra KiCad'in KENDI netlist'i hakemdir.
    Kendi geometrimize inanmiyoruz.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from pcbqa import connect, propose
from pcbqa.connect import ConnectError, ConnectPlan, NetCheck
from pcbqa.schematic import read_schematic

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
UC_PARCA = SAMPLES / "uc_parca" / "uc_parca.kicad_sch"


class ParseTests(unittest.TestCase):
    def test_pins_are_split_on_the_last_dot(self):
        self.assertEqual(connect.parse_net("R1.1 C1.2"), [("R1", "1"), ("C1", "2")])

    def test_power_refs_with_hash_survive(self):
        self.assertEqual(connect.parse_net("#PWR01.1 R1.1")[0], ("#PWR01", "1"))

    def test_commas_are_accepted(self):
        self.assertEqual(connect.parse_net("R1.1, C1.1"), [("R1", "1"), ("C1", "1")])

    def test_a_net_needs_two_pins(self):
        with self.assertRaises(ConnectError):
            connect.parse_net("R1.1")

    def test_missing_pin_number_is_refused(self):
        with self.assertRaises(ConnectError):
            connect.parse_net("R1 C1")


class LookupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schematic = read_schematic(UC_PARCA)

    def test_pin_point_is_the_page_coordinate(self):
        self.assertEqual(connect.pin_point(self.schematic, "R1", "1"), (30.48, 45.72))

    def test_unknown_symbol_names_itself(self):
        with self.assertRaises(ConnectError) as ctx:
            connect.pin_point(self.schematic, "R7", "1")
        self.assertIn("R7", str(ctx.exception))

    def test_unknown_pin_lists_the_real_ones(self):
        with self.assertRaises(ConnectError) as ctx:
            connect.pin_point(self.schematic, "R1", "9")
        self.assertIn("1, 2", str(ctx.exception))


class JunctionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schematic = read_schematic(UC_PARCA)

    def test_a_plain_two_pin_net_needs_no_junction(self):
        plan = connect.plan_nets(self.schematic, [[("R1", "1"), ("C1", "1")]])
        self.assertEqual(plan.junctions, [])

    def test_a_tee_gets_a_junction(self):
        """Guc, rayin ORTASINA iniyor -> uc oge bulusuyor -> junction."""
        plan = connect.plan_from_proposals(
            self.schematic, propose.suggest(self.schematic))
        self.assertIn((39.37, 45.72), plan.junctions)

    def test_junction_count_matches_the_tee_count(self):
        plan = connect.plan_from_proposals(
            self.schematic, propose.suggest(self.schematic))
        self.assertEqual(len(plan.junctions), 1)


class WriteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-bagla-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.path = self.tmp / "uc_parca.kicad_sch"
        shutil.copy(UC_PARCA, self.path)
        shutil.copy(UC_PARCA.with_suffix(".kicad_pro"),
                    self.path.with_suffix(".kicad_pro"))

    def test_dry_run_touches_nothing(self):
        onceki = self.path.read_bytes()
        schematic = read_schematic(self.path)
        plan = connect.plan_nets(schematic, [[("R1", "1"), ("C1", "1")]])
        result = connect.apply_to_file(self.path, plan, apply=False)
        self.assertFalse(result.written)
        self.assertEqual(self.path.read_bytes(), onceki)

    def test_applying_adds_wires_and_keeps_the_symbols(self):
        schematic = read_schematic(self.path)
        plan = connect.plan_from_proposals(schematic, propose.suggest(schematic))
        connect.apply_to_file(self.path, plan, apply=True, backup=False)

        sonra = read_schematic(self.path)
        self.assertEqual(len(sonra.symbols), len(schematic.symbols),
                         "telleme sembol EKLEMEZ ya da SILMEZ")
        self.assertEqual(len(sonra.wires), plan.wire_count)
        self.assertEqual(len(sonra.junctions), len(plan.junctions))

    def test_backup_holds_the_previous_content(self):
        onceki = self.path.read_bytes()
        schematic = read_schematic(self.path)
        plan = connect.plan_nets(schematic, [[("R1", "1"), ("C1", "1")]])
        result = connect.apply_to_file(self.path, plan, apply=True, backup=True)
        self.assertIsNotNone(result.backup)
        self.assertEqual(result.backup.read_bytes(), onceki)


class ArbiterTests(unittest.TestCase):
    """Hakem gercekten REDDEDEBILMELI - yoksa gecmesi bir sey kanitlamaz."""

    def test_power_absence_is_caught_by_the_net_name(self):
        """Guc sembolu netlist'te dugum olarak GORUNMEZ; adindan anlariz.

        Olculdu: `+10V/R1.1/C1.1` agi icin netlist yalnizca `C1.1, R1.1`
        donuyor. Ilk surumde hakem `#PWR01.1`i netlist'te aradigi icin
        DOGRU bir telleme reddedilmisti.
        """
        from unittest import mock

        from pcbqa.sch_verify import Connectivity

        sahte = Connectivity(
            source=Path("x"),
            partition=frozenset({frozenset({("R1", "1"), ("C1", "1")})}),
            net_of={("R1", "1"): "Net-(C1-Pad1)", ("C1", "1"): "Net-(C1-Pad1)"},
        )
        plan = ConnectPlan(nets=[NetCheck(pins=[("R1", "1"), ("C1", "1")],
                                          power_name="+10V",
                                          label="#PWR01.1 - R1.1 - C1.1")])
        with mock.patch("pcbqa.sch_verify.connectivity_of", return_value=sahte):
            sikayet = connect.verify(Path("x.kicad_sch"), plan)
        self.assertEqual(len(sikayet), 1)
        self.assertIn("+10V", sikayet[0])

    def test_correct_power_name_passes(self):
        from unittest import mock

        from pcbqa.sch_verify import Connectivity

        sahte = Connectivity(
            source=Path("x"),
            partition=frozenset({frozenset({("R1", "1"), ("C1", "1")})}),
            net_of={("R1", "1"): "+10V", ("C1", "1"): "+10V"},
        )
        plan = ConnectPlan(nets=[NetCheck(pins=[("R1", "1"), ("C1", "1")],
                                          power_name="+10V", label="ag")])
        with mock.patch("pcbqa.sch_verify.connectivity_of", return_value=sahte):
            self.assertEqual(connect.verify(Path("x.kicad_sch"), plan), [])

    def test_split_pins_are_reported(self):
        from unittest import mock

        from pcbqa.sch_verify import Connectivity

        sahte = Connectivity(
            source=Path("x"),
            partition=frozenset({frozenset({("R1", "1")}), frozenset({("C1", "1")})}),
            net_of={},
        )
        plan = ConnectPlan(nets=[NetCheck(pins=[("R1", "1"), ("C1", "1")],
                                          label="R1.1 - C1.1")])
        with mock.patch("pcbqa.sch_verify.connectivity_of", return_value=sahte):
            sikayet = connect.verify(Path("x.kicad_sch"), plan)
        self.assertEqual(len(sikayet), 1)
        self.assertIn("ayni aga girmedi", sikayet[0])


class EndToEndTests(unittest.TestCase):
    """Gercek `kicad-cli` ile: uygulama kendi isini KiCad'e onaylatiyor mu."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-bagla-e2e-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.path = self.tmp / "uc_parca.kicad_sch"
        shutil.copy(UC_PARCA, self.path)
        shutil.copy(UC_PARCA.with_suffix(".kicad_pro"),
                    self.path.with_suffix(".kicad_pro"))

    def test_proposal_produces_a_circuit_kicad_agrees_with(self):
        code = connect.main([str(self.path), "--oner", "--uygula"])
        self.assertEqual(code, 0, "hakem onaylamali")

        from pcbqa.sch_verify import connectivity_of

        baglanti = connectivity_of(self.path)
        self.assertEqual(baglanti.net_count, 2, "ust ray ve alt ray")
        adlar = set(baglanti.net_of.values())
        self.assertIn("+10V", adlar, "guc sembolu agi adlandirmali")

    def test_declared_nets_reach_the_same_circuit(self):
        code = connect.main([str(self.path), "--ag", "#PWR01.1 R1.1 C1.1",
                             "--ag", "R1.2 C1.2", "--uygula"])
        self.assertEqual(code, 0)

        from pcbqa.sch_verify import connectivity_of

        baglanti = connectivity_of(self.path)
        self.assertIn(frozenset({("R1", "1"), ("C1", "1")}), baglanti.partition)
        self.assertIn(frozenset({("R1", "2"), ("C1", "2")}), baglanti.partition)


if __name__ == "__main__":
    unittest.main()
