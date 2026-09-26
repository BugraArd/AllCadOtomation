"""Kaynakli BOM manifesti: bilinmeyeni gercek gibi gostermeme testleri."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pcbqa.bom import BomError, load_manifest, main


PROJECT = Path(__file__).resolve().parent.parent
MANIFEST = PROJECT / "samples" / "bom" / "g031-asgari.yaml"


class BomManifestTests(unittest.TestCase):
    def test_g031_manifest_has_one_verified_and_open_items(self):
        manifest = load_manifest(MANIFEST)
        self.assertEqual(manifest.profile, "mcu-stm32g031k8")
        self.assertEqual(len(manifest.items), 6)
        self.assertEqual(len(manifest.open_items), 5)
        mcu = next(item for item in manifest.items if item.item_id == "mcu")
        self.assertTrue(mcu.verified)
        self.assertEqual(mcu.mpn, "STM32G031K8T6")

    def test_verified_item_without_provenance_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="pcbqa-bom-") as tmp:
            path = Path(tmp) / "bad.yaml"
            path.write_text(
                "version: 1\n"
                "profile: x\n"
                "status: draft\n"
                "items:\n"
                "  - id: c1\n"
                "    template: x\n"
                "    value: 100nF\n"
                "    footprint: Device:C\n"
                "    status: verified\n",
                encoding="utf-8",
            )
            with self.assertRaises(BomError):
                load_manifest(path)

    def test_fail_on_open_is_explicit(self):
        self.assertEqual(main([str(MANIFEST)]), 0)
        self.assertEqual(main([str(MANIFEST), "--fail-on-open"]), 1)


if __name__ == "__main__":
    unittest.main()
