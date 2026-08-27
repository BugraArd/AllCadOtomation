"""Kural bazli agirlik (Faz 1a).

Skor eskiden yalnizca severity sayiyordu: her hata 8, her uyari 2. Yani
olculmus etkisi olan bir kural (TI AN-2155'in sicak dongu deneyi) ile kaynaksiz
bir muhendislik secimi ayni cezayi yiyordu. `weight` bunu ayirir.

Buradaki en kritik test `test_existing_rule_files_score_identically`: agirlik
kullanmayan bir kural dosyasi BIREBIR eski skoru uretmeli. Uretmezse mevcut tum
esikler ve olcumler (ML egitim verisi dahil) sessizce kayar.
"""

from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

from pcbqa.harness import evaluate_design, load_design
from pcbqa.report import MIN_COMPONENTS_FOR_SCORE, PENALTY, penalty_of
from pcbqa.rules import Finding, RuleError, load_rules

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "samples" / "pic_programmer" / "pic_programmer.kicad_pcb"
SAMPLE_RULES = ROOT / "samples" / "pic_programmer.rules.yaml"

# pic_programmer uzerinde deterministik olarak hata ureten tek kural.
PROBE = """version: 1
defaults:
  severity: warning
  ignore_nets: ["GND", "/GND", "earth"]
rules:
  - id: sonda
    type: proximity
    severity: {severity}
    description: "Olcum sondasi"
    pin: {{ kind: ic, pintype: power_in }}
    partner: {{ kind: capacitor }}
    max_distance_mm: 10
    require_partner: true
{weight_line}"""


class PenaltyOfTests(unittest.TestCase):
    """`penalty_of` saf bir fonksiyon - once onu tek basina sinayalim."""

    def test_falls_back_to_severity_when_no_weight(self):
        for severity, expected in PENALTY.items():
            with self.subTest(severity=severity):
                f = Finding(rule_id="x", severity=severity, message="m")
                self.assertEqual(penalty_of(f), expected)

    def test_weight_overrides_severity(self):
        f = Finding(rule_id="x", severity="error", message="m", weight=16.0)
        self.assertEqual(penalty_of(f), 16.0)

    def test_zero_weight_costs_nothing(self):
        f = Finding(rule_id="x", severity="error", message="m", weight=0.0)
        self.assertEqual(penalty_of(f), 0.0)

    def test_info_is_always_free(self):
        """Agirlik ne olursa olsun `info` sifirdir.

        Somut nedeni: `max_findings` sinirina takilan kural sentetik bir
        "...ve N benzer bulgu daha" bilgisi uretir, `trace_width` ise
        yonlendirilmemis net icin bilgi verir. Agirlik bunlara uygulansaydi
        agirligi 24 olan bir kural HICBIR ihlal olmadan 24 puan yazdirirdi.
        """
        f = Finding(rule_id="x", severity="info", message="m", weight=24.0)
        self.assertEqual(penalty_of(f), 0.0)

    def test_weighted_warning_can_outrank_a_default_error(self):
        """Agirlik severity sirasini bilerek bozabilir - amac bu."""
        warn = Finding(rule_id="x", severity="warning", message="m", weight=20.0)
        err = Finding(rule_id="y", severity="error", message="m")
        self.assertGreater(penalty_of(warn), penalty_of(err))

    def test_external_findings_keep_old_behaviour(self):
        """KiCad ERC/DRC ve sematik kontrolleri weight doldurmaz."""
        f = Finding(rule_id="drc", severity="error", message="m", source="kicad-drc")
        self.assertIsNone(f.weight)
        self.assertEqual(penalty_of(f), PENALTY["error"])


class WeightedScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.design = load_design(BOARD)
        cls.size = max(len(cls.design.board.components), MIN_COMPONENTS_FOR_SCORE)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def probe(self, weight=None, severity="error"):
        line = "" if weight is None else f"    weight: {weight}\n"
        path = self.tmp / "sonda.yaml"
        path.write_text(
            PROBE.format(severity=severity, weight_line=line), encoding="utf-8"
        )
        return evaluate_design(self.design, load_rules(path))

    def expected_score(self, count: int, per_finding: float) -> float:
        penalty = count * per_finding
        if penalty <= 0:
            return 100.0
        return round(100.0 * math.exp(-penalty / self.size), 1)

    def test_existing_rule_files_score_identically(self):
        """EN KRITIK TEST: agirliksiz dosya birebir eski skoru uretmeli."""
        ev = evaluate_design(self.design, load_rules(SAMPLE_RULES))
        self.assertEqual(ev.score, 82.7)

    def test_default_matches_severity_table(self):
        ev = self.probe()
        self.assertGreater(ev.errors, 0, "sonda kurali hic bulgu uretmedi")
        self.assertEqual(ev.score, self.expected_score(ev.errors, PENALTY["error"]))

    def test_double_weight_doubles_the_penalty(self):
        plain = self.probe()
        heavy = self.probe(weight=PENALTY["error"] * 2)
        self.assertEqual(plain.errors, heavy.errors)
        self.assertEqual(
            heavy.score, self.expected_score(heavy.errors, PENALTY["error"] * 2)
        )
        self.assertLess(heavy.score, plain.score)

    def test_explicit_weight_equal_to_default_changes_nothing(self):
        self.assertEqual(self.probe().score, self.probe(weight=PENALTY["error"]).score)

    def test_zero_weight_keeps_findings_but_not_penalty(self):
        ev = self.probe(weight=0.0)
        self.assertGreater(ev.errors, 0, "bulgular raporda kalmali")
        self.assertEqual(ev.score, 100.0, "sifir agirlik skoru etkilememeli")

    def test_weight_reaches_the_findings(self):
        ev = self.probe(weight=5.0)
        self.assertTrue(ev.findings)
        for f in ev.findings:
            if f.rule_id == "sonda":
                self.assertEqual(f.weight, 5.0)


class WeightValidationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, weight_line: str):
        path = self.tmp / "k.yaml"
        path.write_text(
            "version: 1\nrules:\n"
            "  - id: k\n"
            "    type: net_length\n"
            "    net: '.*'\n"
            "    max_hpwl_mm: 100\n" + weight_line,
            encoding="utf-8",
        )
        return path

    def test_negative_weight_rejected(self):
        with self.assertRaises(RuleError) as ctx:
            load_rules(self.write("    weight: -1\n"))
        self.assertIn("negatif", str(ctx.exception))

    def test_non_numeric_weight_rejected(self):
        with self.assertRaises(RuleError) as ctx:
            load_rules(self.write("    weight: cok\n"))
        self.assertIn("sayi", str(ctx.exception))

    def test_weight_does_not_leak_into_spec(self):
        """`spec` kural tipine giden alanlardir; `weight` oraya sizmamali."""
        rule = load_rules(self.write("    weight: 3\n"))[0]
        self.assertEqual(rule.weight, 3.0)
        self.assertNotIn("weight", rule.spec)

    def test_absent_weight_is_none(self):
        self.assertIsNone(load_rules(self.write(""))[0].weight)

    def test_integer_weight_becomes_float(self):
        self.assertIsInstance(load_rules(self.write("    weight: 7\n"))[0].weight, float)


if __name__ == "__main__":
    unittest.main()
