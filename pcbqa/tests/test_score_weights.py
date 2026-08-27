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
from pcbqa.report import (
    MIN_COMPONENTS_FOR_SCORE,
    PENALTY,
    overshoot_factor,
    penalty_of,
)
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


class OvershootFactorTests(unittest.TestCase):
    """Ihlalin buyuklugune gore ceza carpani (Faz 1b)."""

    @staticmethod
    def f(measured=None, limit=None, scale_max=None, severity="error"):
        return Finding(
            rule_id="x",
            severity=severity,
            message="m",
            measured=measured,
            limit=limit,
            scale_max=scale_max,
        )

    def test_off_by_default(self):
        self.assertEqual(overshoot_factor(self.f(measured=150.0, limit=100.0)), 1.0)

    def test_exact_limit_is_unscaled(self):
        self.assertEqual(
            overshoot_factor(self.f(measured=100.0, limit=100.0, scale_max=3.0)), 1.0
        )

    def test_overshoot_above_limit(self):
        """Net uzunlugu gibi: measured > limit."""
        self.assertAlmostEqual(
            overshoot_factor(self.f(measured=150.0, limit=100.0, scale_max=3.0)), 1.5
        )

    def test_overshoot_below_limit_is_symmetric(self):
        """Iz genisligi gibi: measured < limit. Ayni oran, ayni carpan."""
        self.assertAlmostEqual(
            overshoot_factor(self.f(measured=0.5, limit=1.0, scale_max=3.0)), 1.5
        )

    def test_clamped_at_scale_max(self):
        """Tavan olmasa via_current'ta tek bulgu butun skoru yutardi."""
        self.assertEqual(
            overshoot_factor(self.f(measured=1000.0, limit=1.0, scale_max=3.0)), 3.0
        )

    def test_negative_measured_counts_as_worse(self):
        """Cakisan bakir (negatif aciklik), dar aciklikitan daha kotudur."""
        tight = overshoot_factor(self.f(measured=0.05, limit=0.1, scale_max=3.0))
        overlap = overshoot_factor(self.f(measured=-0.05, limit=0.1, scale_max=3.0))
        self.assertGreater(overlap, tight)

    def test_binary_findings_fall_back_silently(self):
        """`require_on_net`/`same_net` measured tasimaz - hata degil, 1.0."""
        self.assertEqual(overshoot_factor(self.f(scale_max=3.0)), 1.0)
        self.assertEqual(overshoot_factor(self.f(measured=5.0, scale_max=3.0)), 1.0)

    def test_zero_limit_does_not_divide(self):
        """`courtyard_overlap`'te clearance_mm 0.0 yaygin - NaN uretmemeli."""
        factor = overshoot_factor(self.f(measured=0.3, limit=0.0, scale_max=3.0))
        self.assertEqual(factor, 1.0)

    def test_penalty_of_applies_the_factor(self):
        f = self.f(measured=150.0, limit=100.0, scale_max=3.0)
        f.weight = 10.0
        self.assertAlmostEqual(penalty_of(f), 15.0)

    def test_info_stays_free_even_when_scaled(self):
        f = self.f(measured=1000.0, limit=1.0, scale_max=3.0, severity="info")
        f.weight = 24.0
        self.assertEqual(penalty_of(f), 0.0)


class ScaledScoreTests(unittest.TestCase):
    """Uctan uca: buyuk ihlal, kucuk ihlalden daha pahali olmali."""

    NET_LENGTH = """version: 1
rules:
  - id: sonda
    type: net_length
    severity: error
    description: "Olcum sondasi"
    net: ".*"
    max_hpwl_mm: {limit}
    max_findings: 200
{scale_lines}"""

    @classmethod
    def setUpClass(cls):
        cls.design = load_design(BOARD)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def probe(self, limit: float, scale: bool):
        lines = "    scale: true\n" if scale else ""
        path = self.tmp / "sonda.yaml"
        path.write_text(
            self.NET_LENGTH.format(limit=limit, scale_lines=lines), encoding="utf-8"
        )
        return evaluate_design(self.design, load_rules(path))

    def test_scale_off_is_unchanged(self):
        """Ayni kural, olcekleme kapali -> Faz 1a davranisi."""
        ev = self.probe(limit=50.0, scale=False)
        size = max(len(self.design.board.components), MIN_COMPONENTS_FOR_SCORE)
        expected = round(100.0 * math.exp(-(ev.errors * PENALTY["error"]) / size), 1)
        self.assertEqual(ev.score, expected)

    @staticmethod
    def penalty_per_finding(ev) -> float:
        """BULGU BASINA ceza; cezalar dogrudan toplanir.

        Bulgu sayisina bolmek sart: limiti sikilastirmak ihlalin buyuklugunu de
        bulgu SAYISINI da artiriyor (limit 50 -> 6 bulgu, limit 5 -> 32 bulgu).
        Ikisini ayirmadan "buyuk ihlal daha pahali" iddiasi olculemez.

        Skoru tersine cozmuyoruz: skor 1 ondaliga yuvarlaniyor ve agir ihlalli
        kartlarda 0.0'a DOYUYOR (32 bulgu x 8 x 3.0 carpan -> exp(-12.2)), o da
        logaritmayi tanimsiz birakiyor.
        """
        return sum(penalty_of(f) for f in ev.findings) / ev.errors

    def test_bigger_violation_costs_more(self):
        """Bulgu basina ceza, ihlal buyudukce artmali.

        Faz 1b'nin butun gerekcesi bu: eskiden 0.01 mm ile 2 mm ayni 8 puani
        yiyordu. Olcekleme kapaliyken iki kolda da bulgu basina ceza tam olarak
        PENALTY['error'] olmali; acikken siki limitte daha yuksek.
        """
        # 100 -> 50: AYNI alti net bulgu veriyor, ama ihlal oranlari iki katina
        # cikiyor. Limiti daha da sikmak (or. 5) karsilastirmayi BOZAR: o zaman
        # hafif ihlal eden kisa netler de bulguya girer ve ortalamayi asagi
        # ceker (olculdu: limit 5 -> 32 bulgu, carpan 1.14'e kadar iniyor).
        loose_off = self.probe(limit=100.0, scale=False)
        tight_off = self.probe(limit=50.0, scale=False)
        self.assertEqual(loose_off.errors, tight_off.errors, "bulgu sayisi ayni olmali")
        for ev in (loose_off, tight_off):
            self.assertAlmostEqual(
                self.penalty_per_finding(ev), PENALTY["error"], places=6
            )

        loose_on = self.probe(limit=100.0, scale=True)
        tight_on = self.probe(limit=50.0, scale=True)
        self.assertEqual(loose_on.errors, tight_on.errors)
        self.assertGreater(
            self.penalty_per_finding(tight_on),
            self.penalty_per_finding(loose_on),
            "daha buyuk ihlal, bulgu basina daha pahali olmali",
        )

    def test_scaling_never_helps(self):
        """Olcekleme cezayi yalnizca BUYUTUR, asla azaltmaz."""
        plain = self.probe(limit=50.0, scale=False)
        scaled = self.probe(limit=50.0, scale=True)
        self.assertLessEqual(scaled.score, plain.score)

    def test_findings_carry_scale_max(self):
        ev = self.probe(limit=50.0, scale=True)
        self.assertTrue(ev.findings)
        for f in ev.findings:
            if f.severity != "info":
                self.assertEqual(f.scale_max, 3.0)


class ScaleValidationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, extra: str):
        path = self.tmp / "k.yaml"
        path.write_text(
            "version: 1\nrules:\n"
            "  - id: k\n"
            "    type: net_length\n"
            "    net: '.*'\n"
            "    max_hpwl_mm: 100\n" + extra,
            encoding="utf-8",
        )
        return path

    def test_non_boolean_scale_rejected(self):
        with self.assertRaises(RuleError) as ctx:
            load_rules(self.write("    scale: belki\n"))
        self.assertIn("true/false", str(ctx.exception))

    def test_scale_max_below_one_rejected(self):
        """Carpan cezayi azaltmak icin degil, buyutmek icindir."""
        with self.assertRaises(RuleError) as ctx:
            load_rules(self.write("    scale: true\n    scale_max: 0.5\n"))
        self.assertIn("1.0", str(ctx.exception))

    def test_defaults(self):
        rule = load_rules(self.write(""))[0]
        self.assertFalse(rule.scale)
        self.assertEqual(rule.scale_max, 3.0)

    def test_scale_does_not_leak_into_spec(self):
        rule = load_rules(self.write("    scale: true\n    scale_max: 2.0\n"))[0]
        self.assertTrue(rule.scale)
        self.assertEqual(rule.scale_max, 2.0)
        self.assertNotIn("scale", rule.spec)
        self.assertNotIn("scale_max", rule.spec)


if __name__ == "__main__":
    unittest.main()
