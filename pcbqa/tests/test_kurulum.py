"""Canli mod kurulumu: KULLANICININ ayar dosyasina dokunuyor.

Bu modul projedeki tek yer ki KiCad'in KENDI yapilandirmasini degistiriyor.
Bir hata kullanicinin temasini, kutuphane yollarini ya da pencere konumlarini
kaybettirebilir. Korunan degismezler bu yuzden sert:

  * KiCad CALISIYORSA yazilmaz. Sebep somut: KiCad ayarlari bellekte tutar ve
    CIKARKEN dosyanin uzerine yazar - simdi yazarsak degisiklik kaybolur.
  * YALNIZCA `api.enable_server` degisir. Dosyanin geri kalani bayt bayt ayni
    anlama gelmeli.
  * Yedek alinir ve her sey GERI ALINABILIR.
  * Yazdiktan sonra dosya geri okunup dogrulanir.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
import subprocess
import io
from contextlib import redirect_stdout
from pathlib import Path

from pcbqa import kurulum
from pcbqa.kurulum import ConfigFile, SetupError, SetupStatus, describe, set_api_enabled

ORNEK_AYAR = {
    "api": {"enable_server": False, "interpreter_path": "C:\\KiCad\\python.exe"},
    "appearance": {"app_theme": 2, "toolbar_icon_size": 24},
    "dialog": {"controls": {"'MNP' Alanini Duzenle": {"wxCheckBox_0": True}}},
    "environment": {"vars": {"KICAD10_SYMBOL_DIR": "C:\\KiCad\\symbols"}},
    "system": {"working_dir": "C:\\isler"},
}


class ConfigWriteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-kurulum-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.path = self.tmp / "kicad_common.json"
        self.path.write_text(
            json.dumps(ORNEK_AYAR, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _read(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def test_enabling_sets_only_the_one_flag(self):
        """Tema, kutuphane yollari, pencere ayarlari AYNEN kalmali."""
        onceki = self._read()
        self.assertTrue(set_api_enabled(self.path, True))
        sonraki = self._read()

        self.assertTrue(sonraki["api"]["enable_server"])
        # Tek fark bu alan olmali
        onceki["api"]["enable_server"] = True
        self.assertEqual(sonraki, onceki)

    def test_interpreter_path_is_not_touched(self):
        set_api_enabled(self.path, True)
        self.assertEqual(self._read()["api"]["interpreter_path"], "C:\\KiCad\\python.exe")

    def test_non_ascii_keys_survive(self):
        """KiCad'in ayarlarinda Turkce anahtarlar var; ensure_ascii bozmamali."""
        set_api_enabled(self.path, True)
        self.assertIn("'MNP' Alanini Duzenle", self._read()["dialog"]["controls"])

    def test_disabling_returns_to_the_original(self):
        onceki = self._read()
        set_api_enabled(self.path, True)
        set_api_enabled(self.path, False)
        self.assertEqual(self._read(), onceki)

    def test_no_change_reports_false(self):
        self.assertFalse(set_api_enabled(self.path, False), "zaten kapali")
        self.assertTrue(set_api_enabled(self.path, True))
        self.assertFalse(set_api_enabled(self.path, True), "zaten acik")

    def test_backup_is_written(self):
        set_api_enabled(self.path, True, backup=True)
        yedekler = list(self.tmp.glob("*.pcbqa-bak*"))
        self.assertEqual(len(yedekler), 1)
        # Yedek ESKI hali tasimali
        eski = json.loads(yedekler[0].read_text(encoding="utf-8"))
        self.assertFalse(eski["api"]["enable_server"])

    def test_missing_api_section_is_created(self):
        self.path.write_text(json.dumps({"appearance": {}}), encoding="utf-8")
        self.assertTrue(set_api_enabled(self.path, True))
        self.assertTrue(self._read()["api"]["enable_server"])
        self.assertIn("appearance", self._read())

    def test_broken_json_is_refused_without_writing(self):
        self.path.write_text("{ bu json degil", encoding="utf-8")
        onceki = self.path.read_text(encoding="utf-8")
        with self.assertRaises(SetupError) as ctx:
            set_api_enabled(self.path, True)
        self.assertIn("bozuk", str(ctx.exception))
        self.assertEqual(self.path.read_text(encoding="utf-8"), onceki)


class RunningKicadTests(unittest.TestCase):
    """KiCad acikken yazmak degisikligi kaybettirir - reddedilmeli."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-kurulum-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.path = self.tmp / "kicad_common.json"
        self.path.write_text(json.dumps(ORNEK_AYAR, indent=2), encoding="utf-8")

        self.original_configs = kurulum.config_files
        self.original_running = kurulum.running_kicad
        kurulum.config_files = lambda: [
            ConfigFile(path=self.path, version="10.0", enabled=False)
        ]
        self.addCleanup(setattr, kurulum, "config_files", self.original_configs)
        self.addCleanup(setattr, kurulum, "running_kicad", self.original_running)

    def test_apply_is_refused_while_kicad_runs(self):
        kurulum.running_kicad = lambda: ["kicad.exe (pid 1234)"]
        onceki = self.path.read_text(encoding="utf-8")
        with self.assertRaises(SetupError) as ctx:
            kurulum.apply(True)
        mesaj = str(ctx.exception)
        self.assertIn("calisiyor", mesaj)
        self.assertIn("pid 1234", mesaj, "hangi surec oldugu soylenmeli")
        self.assertEqual(self.path.read_text(encoding="utf-8"), onceki,
                         "reddedilen istek dosyaya dokunmamali")

    def test_apply_works_when_kicad_is_closed(self):
        kurulum.running_kicad = lambda: []
        changed = kurulum.apply(True)
        self.assertEqual(changed, [self.path])
        self.assertTrue(json.loads(self.path.read_text(encoding="utf-8"))["api"]["enable_server"])

    def test_explicit_override_is_possible(self):
        """Bilerek devam etmek mumkun olmali ama VARSAYILAN olmamali."""
        kurulum.running_kicad = lambda: ["kicad.exe (pid 1234)"]
        changed = kurulum.apply(True, allow_running=True)
        self.assertEqual(changed, [self.path])

    def test_missing_config_is_reported(self):
        kurulum.running_kicad = lambda: []
        kurulum.config_files = lambda: []
        with self.assertRaises(SetupError) as ctx:
            kurulum.apply(True)
        self.assertIn("bulunamadi", str(ctx.exception))


class ReportTests(unittest.TestCase):
    def test_report_explains_both_modes(self):
        text = describe(SetupStatus(
            configs=[ConfigFile(path=Path("x.json"), version="10.0", enabled=False)]
        ))
        self.assertIn("API'siz mod", text)
        self.assertIn("Canli mod", text)
        self.assertIn("Ctrl+Z", text, "kullanicinin mudahale yolu yazmali")

    def test_report_names_the_exact_change(self):
        text = describe(SetupStatus(
            configs=[ConfigFile(path=Path("x.json"), version="10.0", enabled=False)]
        ))
        self.assertIn("api.enable_server", text)
        self.assertIn("--uygula", text)

    def test_report_warns_when_kicad_runs(self):
        text = describe(SetupStatus(
            configs=[ConfigFile(path=Path("x.json"), version="10.0", enabled=False)],
            running=["kicad.exe (pid 99)"],
        ))
        self.assertIn("pid 99", text)

    def test_enabled_state_needs_no_action(self):
        text = describe(SetupStatus(
            configs=[ConfigFile(path=Path("x.json"), version="10.0", enabled=True)]
        ))
        self.assertIn("ACIK", text)
        self.assertNotIn("--uygula", text)


class RealEnvironmentTests(unittest.TestCase):
    """Gercek makinede yalnizca OKUMA - kullanicinin ayarina dokunulmaz."""

    def test_status_reads_without_writing(self):
        state = kurulum.status()
        for config in state.configs:
            self.assertTrue(config.path.is_file())
            self.assertIsInstance(config.enabled, bool)

    def test_process_check_returns_a_list(self):
        self.assertIsInstance(kurulum.running_kicad(), list)


class LiveDepsTests(unittest.TestCase):
    """Canli modun ISTEMCI tarafi - sunucuyu acmak yetmiyor.

    Olcum (KiCad 10.0.4): KiCad'in Python'unda kipy/protobuf/pynng YOK.
    Bu yuzden ayri bir kurulum adimi var. API'siz mod etkilenmiyor.
    """

    def test_pinned_package_is_declared(self):
        """Surum SABIT olmali - 0.7.1 ile olculdu."""
        self.assertTrue(kurulum.LIVE_PACKAGES)
        for spec in kurulum.LIVE_PACKAGES:
            self.assertIn("==", spec, f"{spec} sabitlenmemis")

    def test_every_import_has_a_reason(self):
        for name, why in kurulum.LIVE_IMPORTS:
            with self.subTest(name):
                self.assertTrue(why.strip(), f"{name} ne ise yariyor yazilmamis")

    def test_missing_interpreter_is_refused_without_running_pip(self):
        original = kurulum.kicad_python
        kurulum.kicad_python = lambda: None
        self.addCleanup(setattr, kurulum, "kicad_python", original)
        with self.assertRaises(SetupError) as ctx:
            kurulum.install_live_deps()
        self.assertIn("bulunamadi", str(ctx.exception))

    def test_deps_report_every_module(self):
        """Yorumlayici bulunamasa bile her modul icin bir cevap donmeli."""
        original = kurulum.kicad_python
        kurulum.kicad_python = lambda: None
        self.addCleanup(setattr, kurulum, "kicad_python", original)
        sonuc = kurulum.live_deps()
        self.assertEqual(set(sonuc), {name for name, _ in kurulum.LIVE_IMPORTS})
        self.assertTrue(all(v is False for v in sonuc.values()))

    def test_report_mentions_the_client_side(self):
        text = describe(SetupStatus(
            configs=[ConfigFile(path=Path("x.json"), version="10.0", enabled=True)]
        ))
        self.assertIn("bagimlilik", text.lower())

    def test_failed_process_is_unknown_not_three_missing_packages(self):
        with patch.object(kurulum.subprocess, "run", side_effect=PermissionError("denied")):
            result = kurulum.live_deps(Path("python.exe"))
        self.assertTrue(all(value is None for value in result.values()))

    def test_one_failed_import_does_not_hide_the_other_packages(self):
        def fake_import(name):
            if name == "google.protobuf":
                raise ModuleNotFoundError("No module named google")

        def run(command, **kwargs):
            output = io.StringIO()
            with patch("importlib.import_module", side_effect=fake_import), redirect_stdout(output):
                exec(command[2], {})
            return subprocess.CompletedProcess(command, 0, output.getvalue(), "")

        with patch.object(kurulum.subprocess, "run", side_effect=run):
            result = kurulum.live_deps(Path("python.exe"))
        self.assertEqual(result, {"kipy": True, "google.protobuf": False, "pynng": True})

    def test_pythonw_probe_uses_console_twin(self):
        with patch.object(kurulum.subprocess, "run", side_effect=PermissionError) as run:
            kurulum.live_deps(Path("C:/example/pythonw.exe"))
        self.assertTrue(run.call_args.args[0][0].endswith("python.exe"))

    def test_venv_install_does_not_use_user_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "pyvenv.cfg").write_text("home = example")
            with patch.object(kurulum.subprocess, "run", return_value=
                              subprocess.CompletedProcess([], 0, "", "")) as run:
                kurulum.install_live_deps(folder / "Scripts/python.exe", dry_run=True, echo=lambda _: None)
            command = run.call_args.args[0]
            self.assertNotIn("--user", command)
            self.assertIn("--no-input", command)


if __name__ == "__main__":
    unittest.main()
