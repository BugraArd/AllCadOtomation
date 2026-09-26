"""STM32G031K8 ilk profilinin gercek KiCad kutuphanesiyle sozlesme testleri."""

from __future__ import annotations

import unittest

from pcbqa import symlib
from pcbqa.intent import Intent, IntentBlock, expand_intent, load_templates, resolve_plan


def _kicad_symbol_available() -> bool:
    try:
        symlib.get_symbol("MCU_ST_STM32G0:STM32G031K8Tx")
        return True
    except Exception:  # noqa: BLE001 - test ortami eksikse skip eder
        return False


class STM32G0TemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.templates = load_templates()

    def test_g031_template_is_in_catalog(self):
        template = self.templates["mcu-stm32g031k8"]
        self.assertEqual(template.components[0].lib_id,
                         "MCU_ST_STM32G0:STM32G031K8Tx")
        caps = next(c for c in template.components if c.name == "vdd-decoupling")
        self.assertEqual(caps.count, 1)
        self.assertNotIn("BOOT0", template.components[0].connect)

    def test_minimum_intent_expands_without_problems(self):
        intent = Intent(
            name="g031-asgari",
            blocks=[
                IntentBlock("mcu-stm32g031k8"),
                IntentBlock("ldo-ams1117-3v3"),
                IntentBlock("guc-girisi-header"),
            ],
        )
        plan = expand_intent(intent, self.templates)
        self.assertTrue(plan.ok, plan.problems)
        mcu = next(c for c in plan.components if c.label.endswith("/mcu"))
        self.assertIn(("PF2", "NRST"), mcu.connect)
        self.assertNotIn("USB_DP", plan.nets())

    @unittest.skipUnless(_kicad_symbol_available(), "KiCad STM32G0 sembolu yok")
    def test_g031_symbol_and_footprint_resolve(self):
        intent = Intent(
            name="g031-resolve",
            blocks=[
                IntentBlock("mcu-stm32g031k8"),
                IntentBlock("ldo-ams1117-3v3"),
                IntentBlock("guc-girisi-header"),
            ],
        )
        plan = resolve_plan(expand_intent(intent, self.templates))
        self.assertTrue(plan.ok, plan.problems)
        mcu = next(c for c in plan.components if c.label.endswith("/mcu"))
        self.assertEqual(mcu.footprint, "Package_QFP:LQFP-32_7x7mm_P0.8mm")
        self.assertEqual(mcu.pin_connect, [("4", "3V3"), ("5", "GND"), ("6", "NRST")])


if __name__ == "__main__":
    unittest.main()
