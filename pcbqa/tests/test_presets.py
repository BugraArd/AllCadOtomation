"""On ayar kutuphanesi ve `include` mekanizmasi.

En onemli olcut: `uretim` on ayari devre tipinden bagimsizdir ve saglam bir
gercek kartta HIC bulgu uretmemelidir. Uretmeye baslarsa ya bir esik yanlis
ya da olcum bozulmustur.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pcbqa.harness import load_design
from pcbqa.rules import RuleError, load_rules, run_rules

ROOT = Path(__file__).resolve().parent.parent
PRESETS = ROOT / "pcbqa" / "presets"
ROUTED = ROOT / "samples" / "pic_programmer" / "pic_programmer.kicad_pcb"


class PresetLoadTests(unittest.TestCase):
    def test_presets_exist(self):
        found = sorted(p.name for p in PRESETS.glob("*.yaml"))
        self.assertEqual(
            found,
            [
                "buck.rules.yaml",
                "lineer-koruma.rules.yaml",
                "uretim.rules.yaml",
                "yuksek-hiz.rules.yaml",
            ],
        )

    def test_every_preset_loads(self):
        for preset in sorted(PRESETS.glob("*.yaml")):
            with self.subTest(preset=preset.name):
                rules = load_rules(preset)
                self.assertTrue(rules, f"{preset.name} bos")

    def test_every_rule_has_description(self):
        """Aciklama, bulgunun hangi kaynaga dayandigini tasiyor - zorunlu."""
        for preset in sorted(PRESETS.glob("*.yaml")):
            for rule in load_rules(preset):
                with self.subTest(preset=preset.name, rule=rule.id):
                    self.assertTrue(rule.description, f"{rule.id} aciklamasiz")

    def test_every_rule_has_a_weight(self):
        """Faz 1c: severity tek basina yeterli degil, her kural agirlik tasimali."""
        for preset in sorted(PRESETS.glob("*.yaml")):
            for rule in load_rules(preset):
                with self.subTest(preset=preset.name, rule=rule.id):
                    self.assertIsNotNone(rule.weight, f"{rule.id} agirliksiz")
                    self.assertGreater(rule.weight, 0.0)

    def test_every_weight_cites_a_source(self):
        """Kaynaksiz agirlik yok - "uydurma sayi yazilmaz" kurali burada da gecerli.

        Satir bicimi:  weight: 20   # <kaynak notu>
        """
        for preset in sorted(PRESETS.glob("*.yaml")):
            for lineno, line in enumerate(
                preset.read_text(encoding="utf-8").splitlines(), start=1
            ):
                stripped = line.strip()
                if not stripped.startswith("weight:"):
                    continue
                with self.subTest(preset=preset.name, line=lineno):
                    self.assertIn("#", stripped, "agirligin yaninda kaynak notu yok")
                    note = stripped.split("#", 1)[1].strip()
                    self.assertGreater(len(note), 10, f"kaynak notu cok kisa: {note!r}")

    def test_scaling_only_where_the_source_is_a_formula(self):
        """`scale` yalnizca kaynagin SUREKLI bir iliski verdigi kurallarda.

        Kaynak bir ESIK veriyorsa ("< 5 mm") olcekleme uydurma olurdu: TI
        6.35 mm der, 12.7 mm'nin tam iki kat kotu oldugunu SOYLEMEZ.
        """
        formula_types = {"trace_width", "via_current", "clearance_voltage"}
        for preset in sorted(PRESETS.glob("*.yaml")):
            for rule in load_rules(preset):
                if rule.scale:
                    with self.subTest(preset=preset.name, rule=rule.id):
                        self.assertIn(
                            rule.type,
                            formula_types,
                            f"{rule.id}: kaynagi formul olmayan kuralda scale acik",
                        )

    def test_every_preset_runs_without_error(self):
        design = load_design(ROUTED)
        for preset in sorted(PRESETS.glob("*.yaml")):
            with self.subTest(preset=preset.name):
                run_rules(design, load_rules(preset))

    def test_manufacturing_preset_is_silent_on_sound_board(self):
        """`uretim` her tasarimda gecerli - saglam kartta susmali."""
        design = load_design(ROUTED)
        findings = run_rules(design, load_rules(PRESETS / "uretim.rules.yaml"))
        self.assertEqual(
            findings,
            [],
            f"saglam kartta yanlis alarm: {[f.message for f in findings]}",
        )


class IncludeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name: str, text: str) -> Path:
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_include_merges_rules(self):
        self.write(
            "temel.yaml",
            "rules:\n"
            "  - id: temel-kural\n"
            "    type: net_length\n"
            "    net: '.*'\n"
            "    max_hpwl_mm: 100\n",
        )
        proj = self.write(
            "proje.yaml",
            "include: [temel.yaml]\n"
            "rules:\n"
            "  - id: proje-kurali\n"
            "    type: net_length\n"
            "    net: '.*'\n"
            "    max_hpwl_mm: 200\n",
        )
        ids = [r.id for r in load_rules(proj)]
        self.assertEqual(ids, ["temel-kural", "proje-kurali"])

    def test_include_accepts_bare_string(self):
        self.write(
            "temel.yaml",
            "rules:\n  - id: a\n    type: net_length\n    net: '.*'\n    max_hpwl_mm: 100\n",
        )
        proj = self.write("proje.yaml", "include: temel.yaml\nrules: []\n")
        self.assertEqual([r.id for r in load_rules(proj)], ["a"])

    def test_nested_include(self):
        self.write(
            "c.yaml",
            "rules:\n  - id: c\n    type: net_length\n    net: '.*'\n    max_hpwl_mm: 1\n",
        )
        self.write("b.yaml", "include: [c.yaml]\nrules: []\n")
        proj = self.write("a.yaml", "include: [b.yaml]\nrules: []\n")
        self.assertEqual([r.id for r in load_rules(proj)], ["c"])

    def test_circular_include_rejected(self):
        self.write("b.yaml", "include: [a.yaml]\nrules: []\n")
        a = self.write("a.yaml", "include: [b.yaml]\nrules: []\n")
        with self.assertRaises(RuleError) as ctx:
            load_rules(a)
        self.assertIn("dairesel", str(ctx.exception))

    def test_duplicate_id_across_files_rejected(self):
        """Sessizce ezilen bir kural, fark edilmeyen bir bosluktur."""
        self.write(
            "temel.yaml",
            "rules:\n  - id: ayni\n    type: net_length\n    net: '.*'\n    max_hpwl_mm: 100\n",
        )
        proj = self.write(
            "proje.yaml",
            "include: [temel.yaml]\n"
            "rules:\n  - id: ayni\n    type: net_length\n    net: '.*'\n    max_hpwl_mm: 200\n",
        )
        with self.assertRaises(RuleError) as ctx:
            load_rules(proj)
        self.assertIn("tekrar eden", str(ctx.exception))

    def test_missing_include_reports_path(self):
        proj = self.write("proje.yaml", "include: [yok.yaml]\nrules: []\n")
        with self.assertRaises(RuleError) as ctx:
            load_rules(proj)
        self.assertIn("yok.yaml", str(ctx.exception))

    def test_relative_paths_resolve_against_including_file(self):
        sub = self.dir / "alt"
        sub.mkdir()
        (sub / "temel.yaml").write_text(
            "rules:\n  - id: alt-kural\n    type: net_length\n    net: '.*'\n    max_hpwl_mm: 1\n",
            encoding="utf-8",
        )
        proj = self.write("proje.yaml", "include: [alt/temel.yaml]\nrules: []\n")
        self.assertEqual([r.id for r in load_rules(proj)], ["alt-kural"])


if __name__ == "__main__":
    unittest.main()
