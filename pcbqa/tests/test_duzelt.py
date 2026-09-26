"""Paket 01 bulgu kimliği ve güvenli düzeltme sözleşmesi testleri."""

from __future__ import annotations

import json
import unittest

from pcbqa.duzelt import _same_finding
from pcbqa.rules import Finding


class FindingContractTests(unittest.TestCase):
    def proximity(self, message="U1.VDD için C1 uzak"):
        return Finding(
            rule_id="decoupling-mesafe",
            rule_type="proximity",
            severity="error",
            message=message,
            refs=["U1", "C1"],
            pins=["U1.1", "C1.1"],
            measured=12.5,
            limit=10.0,
        )

    def test_id_is_stable_and_machine_readable(self):
        first = self.proximity()
        second = self.proximity()
        self.assertEqual(first.finding_id, second.finding_id)
        self.assertRegex(first.finding_id, r"^F-[0-9a-f]{12}$")

    def test_id_changes_when_physical_evidence_changes(self):
        first = self.proximity()
        second = self.proximity("U1.VDD için C2 uzak")
        self.assertNotEqual(first.finding_id, second.finding_id)

    def test_evidence_and_auto_fix_contract(self):
        finding = self.proximity()
        data = finding.as_dict()
        self.assertTrue(finding.auto_fixable)
        self.assertEqual(data["finding_id"], finding.finding_id)
        self.assertEqual(data["evidence"]["measured"], 12.5)
        self.assertEqual(data["evidence"]["relation"], "over_limit")
        json.dumps(data, ensure_ascii=False)

    def test_non_proximity_finding_is_not_auto_fixable(self):
        finding = Finding(
            rule_id="courtyard-cakisma",
            rule_type="courtyard_overlap",
            severity="warning",
            message="R1 ve R2 cakisiyor",
            refs=["R1", "R2"],
        )
        self.assertFalse(finding.auto_fixable)

    def test_same_finding_ignores_new_measurement_but_not_pin_pair(self):
        first = self.proximity()
        after = self.proximity("U1.VDD için C1 artık 9 mm")
        after.measured = 9.0
        self.assertTrue(_same_finding(after, first))
        different = self.proximity()
        different.pins = ["U1.2", "C1.1"]
        self.assertFalse(_same_finding(different, first))


if __name__ == "__main__":
    unittest.main()
