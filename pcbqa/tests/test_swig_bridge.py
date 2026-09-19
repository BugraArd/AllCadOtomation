"""API'siz baglanti: yapilandirma tasinabilirligi + surec-ici uygulama.

## Korunan sey

KiCad'in IPC API sunucusu VARSAYILAN OLARAK KAPALI. Dagitilacak bir uygulama
ya da eklenti icin "once Tercihler'den su ayari acin" kabul edilemez bir
kurulum adimidir. Bu yuzden ikinci bir yol var: KiCad'in KENDI Python'unda
(3.11.5) `pcbnew` SWIG baglamalariyla calismak.

O yolun onunde tek bir engel vardi ve olculdu:

    KiCad 10.0 python 3.11.5 : pcbnew VAR, pyyaml YOK
    proje .venv    python 3.13 : pcbnew YOK, pyyaml VAR

`import yaml` modul duzeyinde durdugu surece `pcbqa` KiCad icinde HIC import
edilemiyordu. `confload` + `bundle` o bagi kopardi: YAML kaynak, JSON calisma
zamani kopyasi.

## Iki katman

  * TASINABILIRLIK (her yerde kosar): confload'un secim sirasi ve bundle'in
    ayrisma denetimi.
  * GERCEK KOPRU (KiCad'in python'u gerekir): alt surec olarak KiCad'in
    yorumlayicisi cagrilir ve zincir orada kosturulur. Baska turlu bu yol
    hic sinanmaz - bizim .venv'imizde `pcbnew` YOKTUR.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from pcbqa import bundle
from pcbqa.confload import ConfigError, load_config, runtime_twin, yaml_available

PROJECT = Path(__file__).resolve().parent.parent
SAMPLES = PROJECT / "samples"

# KiCad'in kendi yorumlayicisi - eklentinin gercekte kosacagi yer
KICAD_PYTHON = Path(r"C:\Program Files\KiCad\10.0\bin\python.exe")


def kicad_python_available() -> bool:
    return KICAD_PYTHON.is_file()


class ConfigLoadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-conf-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_json_file_is_read_directly(self):
        path = self.tmp / "x.json"
        path.write_text('{"a": 1}', encoding="utf-8")
        data, used_json = load_config(path)
        self.assertEqual(data, {"a": 1})
        self.assertTrue(used_json)

    def test_yaml_is_preferred_when_available(self):
        if not yaml_available():
            self.skipTest("pyyaml yok")
        path = self.tmp / "x.yaml"
        path.write_text("a: 1\n", encoding="utf-8")
        runtime_twin(path).write_text('{"a": 999}', encoding="utf-8")
        data, used_json = load_config(path)
        self.assertEqual(data, {"a": 1}, "kaynak YAML olmali, kopya degil")
        self.assertFalse(used_json)

    def test_empty_file_is_an_empty_mapping(self):
        path = self.tmp / "bos.json"
        path.write_text("", encoding="utf-8")
        data, _ = load_config(path)
        self.assertEqual(data, {})

    def test_non_mapping_root_is_loud(self):
        """Liste donen bir kural dosyasi sessizce 'hic kural yok' olmamali."""
        path = self.tmp / "liste.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        with self.assertRaises(ConfigError) as ctx:
            load_config(path)
        self.assertIn("eslesme", str(ctx.exception))

    def test_broken_json_names_the_file(self):
        path = self.tmp / "bozuk.json"
        path.write_text("{ bu json degil", encoding="utf-8")
        with self.assertRaises(ConfigError) as ctx:
            load_config(path)
        self.assertIn("bozuk.json", str(ctx.exception))


class BundleTests(unittest.TestCase):
    def test_shipped_copies_are_not_stale(self):
        """YAML duzeltilip JSON eski kalirsa KiCad ICINDE eski kural kosar.

        Bu testin kirilmasi 'python -m pcbqa.bundle' calistirmayi unuttun
        demektir - sessiz bir davranis farki degil.
        """
        if not yaml_available():
            self.skipTest("pyyaml yok - kaynak okunamaz")
        _fresh, stale = bundle.build(write=False)
        self.assertEqual(
            [p.name for p in stale], [],
            "calisma zamani kopyalari ayrismis; 'python -m pcbqa.bundle' calistirin",
        )

    def test_every_bundled_yaml_has_a_twin(self):
        for source in bundle.yaml_sources():
            self.assertTrue(
                runtime_twin(source).is_file(),
                f"{source.name} icin calisma zamani kopyasi yok",
            )

    def test_twin_content_matches_the_source(self):
        if not yaml_available():
            self.skipTest("pyyaml yok")
        for source in bundle.yaml_sources():
            with self.subTest(source.name):
                kaynak, _ = load_config(source)
                kopya = json.loads(runtime_twin(source).read_text(encoding="utf-8"))
                self.assertEqual(kaynak, kopya)

    def test_arbitrary_file_can_be_converted(self):
        """Kullanicinin KENDI kural dosyasi da KiCad icinde okunabilmeli."""
        if not yaml_available():
            self.skipTest("pyyaml yok")
        tmp = Path(tempfile.mkdtemp(prefix="pcbqa-bundle-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        source = tmp / "benim.rules.yaml"
        source.write_text("version: 1\nrules: []\n", encoding="utf-8")
        _fresh, stale = bundle.build(sources=[source])
        self.assertEqual(len(stale), 1)
        self.assertTrue(runtime_twin(source).is_file())


@unittest.skipUnless(kicad_python_available(), "KiCad'in Python'u bulunamadi")
class InProcessBridgeTests(unittest.TestCase):
    """KiCad'in KENDI yorumlayicisinda kosar - baska turlu bu yol sinanmaz."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-swig-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def run_in_kicad(self, script: str) -> str:
        # Paketi PYTHONPATH ile GOSTEREMEYIZ: KiCad'in sitecustomize.py'si site
        # asamasinda `sys.path = []` yapip yeniden kuruyor, PYTHONPATH girdileri
        # o silmede kayboluyor (bkz. baslat.py). Yolu betigin ICINDE ekliyoruz.
        onsoz = 'import sys; sys.path.insert(0, r"%s")\n' % PROJECT
        proc = subprocess.run(
            [str(KICAD_PYTHON), "-c", onsoz + textwrap.dedent(script)],
            capture_output=True, text=True,
            cwd=str(PROJECT.parent),  # cwd'ye YASLANMADIGIMIZI kanitlar
            env={"PATH": ""},
        )
        if proc.returncode != 0:
            self.fail(
                f"KiCad python'unda hata (kod {proc.returncode}):\n"
                f"{proc.stderr[-1500:]}"
            )
        return proc.stdout

    def test_package_imports_without_pyyaml(self):
        """Asil degismez: pyyaml OLMADAN kural okunabilmeli."""
        out = self.run_in_kicad(f"""
            from pathlib import Path
            from pcbqa.confload import yaml_available
            from pcbqa.rules import load_rules
            print("yaml:", yaml_available())
            r = load_rules(Path(r"{PROJECT}") / "pcbqa" / "presets" / "uretim.rules.yaml")
            print("kural:", len(r))
        """)
        self.assertIn("yaml: False", out, "KiCad python'unda pyyaml BEKLENMIYOR")
        self.assertRegex(out, r"kural: [1-9]")

    def test_templates_load_without_pyyaml(self):
        out = self.run_in_kicad("""
            from pcbqa.intent import load_templates
            print("sablon:", len(load_templates()))
        """)
        self.assertRegex(out, r"sablon: [1-9]")

    def test_placement_is_applied_in_process_and_survives_a_reload(self):
        """API yok: dogrudan pcbnew ile tasi, sonra DISKTEN geri oku."""
        board = self.tmp / "bench_bad.kicad_pcb"
        shutil.copy(SAMPLES / "bench_bad.kicad_pcb", board)
        out = self.run_in_kicad(f"""
            from pathlib import Path
            from pcbqa.swig_apply import apply_placement, open_board
            from pcbqa.pcb import read_board

            pcb = Path(r"{board}")
            once = read_board(pcb)
            hedef = {{c.ref: (c.x + 1.0, c.y + 2.0, c.rotation) for c in once.components}}

            kart = open_board(pcb)
            kuru = apply_placement(kart, hedef, apply=False)
            print("dry_run_degisen:", kuru.changed, "yazildi:", kuru.dry_run)

            gercek = apply_placement(kart, hedef, apply=True, save=True)
            print("uygulanan:", gercek.changed, "hata:", len(gercek.verify_errors))

            sonra = read_board(pcb)
            kayma = max(abs(c.x - once.by_ref(c.ref).x) for c in sonra.components)
            print("diskteki_kayma_mm:", round(kayma, 3))
        """)
        self.assertIn("yazildi: True", out, "dry-run yazmamali")
        self.assertIn("hata: 0", out, "geri okuma dogrulamasi temiz olmali")
        self.assertIn("diskteki_kayma_mm: 1.0", out,
                      "tasima diske gercekten yansimali")

    def test_dry_run_does_not_touch_the_file(self):
        board = self.tmp / "kuru.kicad_pcb"
        shutil.copy(SAMPLES / "bench_bad.kicad_pcb", board)
        before = board.read_bytes()
        self.run_in_kicad(f"""
            from pathlib import Path
            from pcbqa.swig_apply import apply_placement, open_board
            from pcbqa.pcb import read_board
            pcb = Path(r"{board}")
            hedef = {{c.ref: (c.x + 5.0, c.y, c.rotation) for c in read_board(pcb).components}}
            ozet = apply_placement(open_board(pcb), hedef, apply=False)
            print("degisecek:", ozet.changed)
        """)
        self.assertEqual(board.read_bytes(), before, "dry-run dosyaya dokunmamali")

    def test_locked_footprints_are_skipped(self):
        board = self.tmp / "kilit.kicad_pcb"
        shutil.copy(SAMPLES / "bench_bad.kicad_pcb", board)
        out = self.run_in_kicad(f"""
            from pathlib import Path
            from pcbqa.swig_apply import apply_placement, open_board
            from pcbqa.pcb import read_board
            pcb = Path(r"{board}")
            hedef = {{c.ref: (c.x + 1.0, c.y, c.rotation) for c in read_board(pcb).components}}
            ozet = apply_placement(open_board(pcb), hedef, apply=False,
                                   locked_refs={{"U1"}})
            print("atlanan:", ",".join(ozet.skipped_locked_refs))
        """)
        self.assertIn("atlanan: U1", out)


if __name__ == "__main__":
    unittest.main()
