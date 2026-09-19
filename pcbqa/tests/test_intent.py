"""Evre 3a: niyet beyani -> sablon kutuphanesi -> insa plani.

Iki katman test edilir:

  * SAF katman (kutuphane gerektirmez): sema dogrulama, acilim, yetenek
    denetimi, arayuz aktiflesmesi, parametreler. Her hata GORUNUR olmali -
    sessiz hata dersinin dogrudan uygulamasi.
  * KUTUPHANE katmani (KiCad kuruluysa): paketle gelen sablonlarin tamami
    gercek sembollere/footprint'lere karsi cozulmeli. Bu, "sablon yazildi
    ama kutuphaneyle hic sinanmadi" durumunu kalici olarak engeller.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pcbqa import symlib
from pcbqa.intent import (
    BuildPlan,
    Intent,
    IntentBlock,
    IntentError,
    PlannedComponent,
    expand_intent,
    load_templates,
    read_intent,
    read_template,
    resolve_plan,
)

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def device_library_available() -> bool:
    try:
        symlib.get_symbol("Device:R")
        return True
    except symlib.SymLibError:
        return False


def _write(folder: Path, name: str, text: str) -> Path:
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


MINIMAL_TEMPLATE = """\
version: 1
id: {id}
description: "test"
provides: {provides}
requires: {requires}
params: {{net: "N1"}}
components:
  - name: parca
    lib_id: Device:R
    value: 10k
    footprint: Resistor_SMD:R_0603_1608Metric
    connect: {{"#1": "${{net}}", "#2": "GND"}}
"""


def make_templates(folder: Path) -> None:
    _write(folder, "a.yaml", MINIMAL_TEMPLATE.format(
        id="blok-a", provides="[guc]", requires="[]"))
    _write(folder, "b.yaml", MINIMAL_TEMPLATE.format(
        id="blok-b", provides="[]", requires="[guc]"))


def intent_of(*blocks: IntentBlock | str, name: str = "test") -> Intent:
    parsed = [b if isinstance(b, IntentBlock) else IntentBlock(template=b)
              for b in blocks]
    return Intent(name=name, blocks=parsed)


# --------------------------------------------------------------------------
# Sablon bicimi
# --------------------------------------------------------------------------


class TemplateFormatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-intent-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def test_unknown_key_is_loud(self):
        path = _write(self.tmp, "t.yaml", "version: 1\nid: x\nbilesenler: []\n")
        with self.assertRaises(IntentError) as ctx:
            read_template(path)
        self.assertIn("bilinmeyen anahtar", str(ctx.exception))

    def test_wrong_version_is_loud(self):
        path = _write(self.tmp, "t.yaml", "version: 2\nid: x\ncomponents: []\n")
        with self.assertRaises(IntentError) as ctx:
            read_template(path)
        self.assertIn("version", str(ctx.exception))

    def test_empty_components_is_loud(self):
        path = _write(self.tmp, "t.yaml", "version: 1\nid: x\ncomponents: []\n")
        with self.assertRaises(IntentError):
            read_template(path)

    def test_duplicate_component_names_are_loud(self):
        path = _write(self.tmp, "t.yaml", """\
version: 1
id: x
components:
  - {name: p, lib_id: Device:R}
  - {name: p, lib_id: Device:C}
""")
        with self.assertRaises(IntentError) as ctx:
            read_template(path)
        self.assertIn("benzersiz", str(ctx.exception))

    def test_interface_must_reference_existing_component(self):
        path = _write(self.tmp, "t.yaml", """\
version: 1
id: x
components:
  - {name: p, lib_id: Device:R}
interfaces:
  arabirim:
    yok-boyle-parca: {"#1": "N"}
""")
        with self.assertRaises(IntentError) as ctx:
            read_template(path)
        self.assertIn("yok-boyle-parca", str(ctx.exception))

    def test_duplicate_template_id_across_files_is_loud(self):
        _write(self.tmp, "a.yaml", MINIMAL_TEMPLATE.format(
            id="ayni", provides="[]", requires="[]"))
        _write(self.tmp, "b.yaml", MINIMAL_TEMPLATE.format(
            id="ayni", provides="[]", requires="[]"))
        with self.assertRaises(IntentError) as ctx:
            load_templates(self.tmp)
        self.assertIn("cakisiyor", str(ctx.exception))


# --------------------------------------------------------------------------
# Niyet bicimi
# --------------------------------------------------------------------------


class IntentFormatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-intent-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def test_short_and_long_block_forms(self):
        path = _write(self.tmp, "n.yaml", """\
version: 1
name: deneme
blocks:
  - kisa-bicim
  - template: uzun-bicim
    params: {vdd: "5V"}
""")
        intent = read_intent(path)
        self.assertEqual([b.template for b in intent.blocks], ["kisa-bicim", "uzun-bicim"])
        self.assertEqual(intent.blocks[1].params, {"vdd": "5V"})

    def test_unknown_key_is_loud(self):
        path = _write(self.tmp, "n.yaml", "version: 1\nbloklar: [x]\n")
        with self.assertRaises(IntentError):
            read_intent(path)

    def test_empty_blocks_is_loud(self):
        path = _write(self.tmp, "n.yaml", "version: 1\nname: x\nblocks: []\n")
        with self.assertRaises(IntentError):
            read_intent(path)

    def test_name_falls_back_to_filename(self):
        path = _write(self.tmp, "kartim.yaml", "version: 1\nblocks: [a]\n")
        self.assertEqual(read_intent(path).name, "kartim")


# --------------------------------------------------------------------------
# Acilim
# --------------------------------------------------------------------------


class ExpandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-intent-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        make_templates(self.tmp)
        self.templates = load_templates(self.tmp)

    def test_unknown_template_is_a_problem(self):
        plan = expand_intent(intent_of("yok-boyle-sablon"), self.templates)
        self.assertFalse(plan.ok)
        self.assertTrue(any("sablon bulunamadi" in p for p in plan.problems))

    def test_duplicate_template_is_a_problem(self):
        plan = expand_intent(intent_of("blok-a", "blok-a"), self.templates)
        self.assertTrue(any("iki kez" in p for p in plan.problems))

    def test_unsatisfied_require_names_candidates(self):
        plan = expand_intent(intent_of("blok-b"), self.templates)
        self.assertFalse(plan.ok)
        problem = next(p for p in plan.problems if "karsilanmiyor" in p)
        self.assertIn("guc", problem)
        self.assertIn("blok-a", problem)  # kim saglayabilirdi soylenmeli

    def test_satisfied_require_is_silent(self):
        plan = expand_intent(intent_of("blok-a", "blok-b"), self.templates)
        self.assertTrue(plan.ok, plan.problems)
        self.assertEqual(len(plan.components), 2)

    def test_param_override_changes_net(self):
        block = IntentBlock(template="blok-a", params={"net": "OZEL"})
        plan = expand_intent(intent_of(block), self.templates)
        self.assertIn(("#1", "OZEL"), plan.components[0].connect)

    def test_unknown_param_is_a_problem(self):
        block = IntentBlock(template="blok-a", params={"nte": "X"})  # yazim hatasi
        plan = expand_intent(intent_of(block), self.templates)
        self.assertTrue(any("nte" in p for p in plan.problems))

    def test_undefined_variable_in_template_is_a_problem(self):
        _write(self.tmp, "c.yaml", """\
version: 1
id: blok-c
components:
  - name: p
    lib_id: Device:R
    connect: {"#1": "${tanimsiz}"}
""")
        plan = expand_intent(intent_of("blok-c"), load_templates(self.tmp))
        self.assertTrue(any("tanimsiz" in p for p in plan.problems))


class RealTemplatesExpandTests(unittest.TestCase):
    """Paketle gelen sablonlar - kutuphane gerektirmeyen kisim."""

    @classmethod
    def setUpClass(cls):
        cls.templates = load_templates()

    def full_intent(self) -> Intent:
        return intent_of("mcu-stm32f103c8", "ldo-ams1117-3v3", "usb-micro-b",
                         "swd-header", "crystal-hse")

    def test_full_example_expands_without_problems(self):
        plan = expand_intent(self.full_intent(), self.templates)
        self.assertTrue(plan.ok, plan.problems)

    def test_interface_pins_only_when_requested(self):
        # Kristal blogu yokken MCU'nun PD0/PD1'i etiketlenmemeli
        with_crystal = expand_intent(self.full_intent(), self.templates)
        without = expand_intent(
            intent_of("mcu-stm32f103c8", "ldo-ams1117-3v3", "guc-girisi-header"),
            self.templates,
        )
        mcu_with = next(c for c in with_crystal.components if c.label.endswith("/mcu"))
        mcu_without = next(c for c in without.components if c.label.endswith("/mcu"))
        self.assertIn(("PD0", "HSE_IN"), mcu_with.connect)
        self.assertNotIn(("PD0", "HSE_IN"), mcu_without.connect)
        self.assertNotIn("HSE_IN", without.nets())

    def test_mcu_without_power_source_is_a_problem(self):
        plan = expand_intent(intent_of("mcu-stm32f103c8"), self.templates)
        self.assertTrue(any("guc-3v3" in p for p in plan.problems))

    def test_two_vbus_sources_produce_a_note(self):
        plan = expand_intent(
            intent_of("mcu-stm32f103c8", "ldo-ams1117-3v3", "usb-micro-b",
                      "guc-girisi-header"),
            self.templates,
        )
        self.assertTrue(any("guc-vbus" in n for n in plan.notes), plan.notes)

    def test_crystal_load_param_reaches_value(self):
        block = IntentBlock(template="crystal-hse", params={"load": "20pF"})
        plan = expand_intent(
            intent_of("mcu-stm32f103c8", "ldo-ams1117-3v3", "guc-girisi-header", block),
            self.templates,
        )
        caps = [c for c in plan.components if "yuk-kondansatoru" in c.label]
        self.assertEqual(len(caps), 2)
        self.assertTrue(all(c.value == "20pF" for c in caps))

    def test_shared_nets_tie_blocks_together(self):
        plan = expand_intent(self.full_intent(), self.templates)
        nets = plan.nets()
        # LDO cikisi ile MCU beslemesi ayni agda bulusmali
        labels_3v3 = {label for label, _ in nets["3V3"]}
        self.assertTrue(any("ldo-ams1117-3v3/ldo" == lb for lb in labels_3v3))
        self.assertTrue(any("mcu-stm32f103c8/mcu" == lb for lb in labels_3v3))
        # USB verisi konnektorden MCU'ya ulasmali
        labels_dp = {label for label, _ in nets["USB_DP"]}
        self.assertIn("usb-micro-b/konnektor", labels_dp)
        self.assertIn("mcu-stm32f103c8/mcu", labels_dp)
        # Cift pin gerektiren agda tek pin kalmamali
        for net in ("3V3", "GND", "VBUS", "HSE_IN", "HSE_OUT",
                    "USB_DM", "USB_DP", "SWDIO", "SWCLK", "NRST", "BOOT0"):
            self.assertGreaterEqual(len(nets[net]), 2, net)


# --------------------------------------------------------------------------
# Kutuphaneye karsi cozumleme
# --------------------------------------------------------------------------


@unittest.skipUnless(device_library_available(), "KiCad sembol kutuphanesi yok")
class ResolveTests(unittest.TestCase):
    """Sablonlar gercek kutuphaneyle SINANMADAN yasayamaz.

    Sessiz hata dersinin sablon kutuphanesine uygulanmis hali: yanlis
    yazilmis bir lib_id, footprint ya da pin adi ancak cozumlemede belli
    olur; bu sinif paketteki HER sablonu gercek kutuphaneden gecirir.
    """

    @classmethod
    def setUpClass(cls):
        cls.templates = load_templates()

    def test_every_bundled_template_resolves_cleanly(self):
        # usb + guc-girisi ayni anda: tum sablonlar tek planda sinanir
        intent = intent_of("mcu-stm32f103c8", "ldo-ams1117-3v3", "usb-micro-b",
                           "swd-header", "crystal-hse", "guc-girisi-header")
        plan = resolve_plan(expand_intent(intent, self.templates))
        self.assertTrue(plan.ok, plan.problems)
        self.assertTrue(plan.resolved)
        # Her bilesen referans on ekini kutuphaneden almis olmali
        self.assertTrue(all(c.ref_prefix for c in plan.components))

    def test_vdd_decoupling_count_matches_symbol(self):
        """AN2586: VDD pini basina bir 100 nF - sayi kutuphaneyle eslesmeli.

        Sablondaki `count: 3` elle yazildi; sembol degisirse (baska paket,
        kutuphane guncellemesi) bu test bagirir.
        """
        symbol = symlib.get_symbol("MCU_ST_STM32F1:STM32F103C8Tx")
        vdd_pins = [p for p in symbol.pins if p.name == "VDD"]
        tpl = self.templates["mcu-stm32f103c8"]
        caps = next(c for c in tpl.components if c.name == "vdd-decoupling")
        self.assertEqual(caps.count, len(vdd_pins))

    def test_name_match_connects_all_same_named_pins(self):
        intent = intent_of("mcu-stm32f103c8", "ldo-ams1117-3v3", "guc-girisi-header")
        plan = resolve_plan(expand_intent(intent, self.templates))
        mcu = next(c for c in plan.components if c.label.endswith("/mcu"))
        vdd_numbers = {pin for pin, net in mcu.pin_connect if net == "3V3"}
        # VDD x3 + VBAT + VDDA
        self.assertEqual(vdd_numbers, {"24", "36", "48", "1", "9"})

    def test_missing_pin_name_is_a_problem(self):
        plan = BuildPlan(name="t", components=[PlannedComponent(
            label="x/mcu", template_id="x",
            lib_id="MCU_ST_STM32F1:STM32F103C8Tx", value="", footprint="",
            connect=[("YOK_BOYLE_PIN", "N")],
        )])
        resolve_plan(plan)
        self.assertTrue(any("YOK_BOYLE_PIN" in p for p in plan.problems))

    def test_missing_pin_number_is_a_problem(self):
        plan = BuildPlan(name="t", components=[PlannedComponent(
            label="x/r", template_id="x", lib_id="Device:R", value="", footprint="",
            connect=[("#99", "N")],
        )])
        resolve_plan(plan)
        self.assertTrue(any("99" in p for p in plan.problems))

    def test_unconnected_power_in_pin_is_a_problem(self):
        # VDD'ler bilerek baglanmadi - cozumleme bagirmali
        plan = BuildPlan(name="t", components=[PlannedComponent(
            label="x/mcu", template_id="x",
            lib_id="MCU_ST_STM32F1:STM32F103C8Tx", value="", footprint="",
            connect=[("VSS", "GND")],
        )])
        resolve_plan(plan)
        self.assertTrue(any("guc girisi pini baglanmamis" in p for p in plan.problems))

    def test_missing_footprint_is_a_problem(self):
        plan = BuildPlan(name="t", components=[PlannedComponent(
            label="x/r", template_id="x", lib_id="Device:R", value="",
            footprint="Resistor_SMD:Yok_Boyle_Footprint",
            connect=[("#1", "A"), ("#2", "B")],
        )])
        resolve_plan(plan)
        self.assertTrue(any("footprint bulunamadi" in p for p in plan.problems))


@unittest.skipUnless(device_library_available(), "KiCad sembol kutuphanesi yok")
class SampleIntentTests(unittest.TestCase):
    def test_sample_intent_file_produces_clean_plan(self):
        from pcbqa.intent import plan_from_file

        plan = plan_from_file(SAMPLES / "ornek-niyet.yaml")
        self.assertTrue(plan.ok, plan.problems)
        self.assertEqual(plan.name, "ornek-f103")
        # 18 bilesen: MCU blogu 9, LDO 3, USB 2, SWD 1, kristal 3
        self.assertEqual(len(plan.components), 18)


if __name__ == "__main__":
    unittest.main()
