"""Donanim gereksinim sozlesmesi testleri."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from pcbqa.requirements import RequirementsError, load_contract, main


ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "samples" / "gereksinimler" / "g031-urun-sozlesmesi.yaml"


class RequirementsTests(unittest.TestCase):
    def test_draft_sample_keeps_all_product_decisions_open(self):
        contract = load_contract(SAMPLE)
        self.assertEqual(contract.profile, "mcu-stm32g031k8")
        self.assertEqual(contract.status, "draft")
        self.assertEqual(len(contract.decisions), 6)
        self.assertEqual(len(contract.open_decisions), 6)
        self.assertFalse(contract.accepted)

    def test_accepted_contract_needs_nonempty_decisions(self):
        text = """\
version: 1
profile: x
status: accepted
decisions:
  - id: input_supply
    status: decided
    value: 5V
  - id: current_budget
    status: decided
    value: 500mA
  - id: interfaces
    status: decided
    value: [SWD]
  - id: gpio_and_peripherals
    status: decided
    value: {gpio: 8}
  - id: mechanical_and_manufacturing
    status: decided
    value: {layers: 2}
  - id: temperature_and_package
    status: decided
    value: {grade: commercial}
"""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "accepted.yaml"
            path.write_text(text, encoding="utf-8")
            contract = load_contract(path)
        self.assertTrue(contract.accepted)
        self.assertEqual(len(contract.open_decisions), 0)

    def test_accepted_contract_rejects_blocked_decision(self):
        text = SAMPLE.read_text(encoding="utf-8").replace("status: draft", "status: accepted", 1)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "blocked.yaml"
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(RequirementsError, "accepted"):
                load_contract(path)

    def test_missing_or_unknown_decision_is_rejected(self):
        text = SAMPLE.read_text(encoding="utf-8").replace("input_supply", "typo_supply", 1)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "invalid.yaml"
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(RequirementsError, "bilinmiyor"):
                load_contract(path)

    def test_fail_on_open_reports_a_nonzero_gate(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main([str(SAMPLE), "--fail-on-open"])
        self.assertEqual(code, 1)
        self.assertIn("6 gereksinim karari acik", stderr.getvalue())
        self.assertIn("input_supply", stdout.getvalue())
