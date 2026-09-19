"""Bagimsiz uygulama: tek giris noktasi ve baslatici.

Dagitilan sey bu: bir klasor + `pcbqa.cmd`. Kullanicinin gordugu ilk sey
`pcbqa tani` ciktisidir; oradaki bir yanlis "her sey yerinde" satiri, sonra
anlasilmaz bir hataya donusur. Bu yuzden burada korunanlar:

  * KOMUT TABLOSU ile gercek moduller tutarli olmali - tabloya yazilip
    modulu olmayan bir komut ancak kullanici denedigine ortaya cikardi.
  * `tani` eksik parcalari GORUNUR kilmali ve cikis koduyla bildirmeli.
  * BASLATICI KiCad'in Python'unu kendi bulmali; bulamazsa ne yapilacagini
    soylemeli.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from pcbqa import app

PROJECT = Path(__file__).resolve().parent.parent
LAUNCHER = PROJECT / "pcbqa.cmd"


class CommandTableTests(unittest.TestCase):
    def test_every_command_points_at_a_real_cli(self):
        """Tabloya yazilan her komutun `main()`i olmali."""
        from importlib import import_module

        for name, module_name, _help in app.COMMANDS:
            if not module_name:  # `tani` uygulamanin kendi icinde
                continue
            with self.subTest(name):
                module = import_module(module_name)
                self.assertTrue(callable(getattr(module, "main", None)),
                                f"{module_name} bir main() sunmuyor")

    def test_command_names_are_unique(self):
        names = [c for c, _, _ in app.COMMANDS]
        self.assertEqual(len(names), len(set(names)))

    def test_every_command_has_help_text(self):
        for name, _module, help_text in app.COMMANDS:
            with self.subTest(name):
                self.assertTrue(help_text.strip(), f"{name} icin aciklama yok")

    def test_usage_lists_all_commands(self):
        text = app.usage()
        for name, _module, _help in app.COMMANDS:
            self.assertIn(name, text)


class DispatchTests(unittest.TestCase):
    def test_no_arguments_prints_usage(self):
        self.assertEqual(app.main([]), 0)

    def test_help_is_accepted_in_both_languages(self):
        for flag in ("--help", "-h", "help", "yardim"):
            with self.subTest(flag):
                self.assertEqual(app.main([flag]), 0)

    def test_unknown_command_fails_loudly(self):
        self.assertEqual(app.main(["yokboylekomut"]), 2)

    def test_unknown_command_suggests_near_matches(self, ):
        import io
        from contextlib import redirect_stderr

        buffer = io.StringIO()
        with redirect_stderr(buffer):
            app.main(["ure"])  # "uret" kastedilmis
        self.assertIn("uret", buffer.getvalue())

    def test_version_is_reported(self):
        self.assertEqual(app.main(["--version"]), 0)


class DiagnoseTests(unittest.TestCase):
    def test_diagnose_reports_the_essentials(self):
        lines, _problems = app.diagnose()
        text = "\n".join(lines)
        for anahtar in ("yorumlayici", "kicad-cli", "sembol kutuphanesi",
                        "calisma zamani kopyalari", "sablon kutuphanesi"):
            self.assertIn(anahtar, text)

    def test_problems_are_marked_and_counted(self):
        lines, problems = app.diagnose()
        isaretli = sum(1 for line in lines if line.startswith("  !!"))
        self.assertEqual(isaretli, problems,
                         "engel sayisi '!!' satirlariyla uyusmali")

    def test_exit_code_follows_the_problem_count(self):
        _lines, problems = app.diagnose()
        self.assertEqual(app.run_diagnose(), 1 if problems else 0)


@unittest.skipUnless(sys.platform == "win32", "baslatici Windows toplu dosyasi")
class LauncherTests(unittest.TestCase):
    """Baslatici son kullanicinin gordugu sey - sanal ortam olmadan kosar."""

    def _run(self, args: list[str], env_extra: dict | None = None,
             cwd: str | None = None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        # Gelistirici ortamini SIL: kullanicinin makinesinde bunlar yok.
        env.pop("PYTHONPATH", None)
        env.pop("PCBQA_PYTHON", None)
        env.update(env_extra or {})
        return subprocess.run(
            ["cmd", "/c", str(LAUNCHER)] + args,
            capture_output=True, text=True, cwd=cwd or str(PROJECT), env=env,
        )

    def test_launcher_exists(self):
        self.assertTrue(LAUNCHER.is_file())

    def test_launcher_finds_an_interpreter_and_runs(self):
        proc = self._run(["--version"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("pcbqa", proc.stdout)

    def test_launcher_reports_the_environment(self):
        proc = self._run(["tani"])
        self.assertIn("ortam denetimi", proc.stdout)
        self.assertIn("kicad-cli", proc.stdout)

    def test_launcher_runs_from_an_unrelated_directory(self):
        """Regresyon: kullanici paket klasorunde DEGILDIR.

        Baslatici once `python -m pcbqa.app` cagiriyordu ve yalnizca calisma
        dizini paket klasoruyken calisiyordu; baska yerden "No module named
        pcbqa" veriyordu. Sebep KiCad'in sitecustomize.py'si: site asamasinda
        `sys.path = []` yapiyor, yani PYTHONPATH ise yaramiyor ve geriye
        yalnizca `-m`'in ekledigi cwd kaliyor. Bu test o cwd'yi elinden alir.
        """
        yabanci = os.environ.get("SystemRoot", r"C:\Windows")
        proc = self._run(["--version"], cwd=yabanci)
        self.assertEqual(proc.returncode, 0,
                         "paket disi dizinden calismadi:\n" + proc.stderr)
        self.assertIn("pcbqa", proc.stdout)

    def test_pythonpath_alone_is_not_relied_upon(self):
        """KiCad'in Python'u PYTHONPATH'i YOK SAYIYOR - buna guvenilmemeli.

        Olcum (KiCad 10.0.4): set PYTHONPATH=<paket>; python -c "print(sys.path)"
        -> paket yolu listede YOK. Baslatici bu yuzden `baslat.py` cagiriyor.
        """
        import subprocess as sp

        from tests.test_swig_bridge import KICAD_PYTHON

        if not KICAD_PYTHON.is_file():
            self.skipTest("KiCad'in Python'u bulunamadi")
        yorumlayici = KICAD_PYTHON
        env = dict(os.environ)
        env["PYTHONPATH"] = str(PROJECT)
        proc = sp.run([str(yorumlayici), "-c", "import sys; print(sys.path)"],
                      capture_output=True, text=True,
                      cwd=os.environ.get("SystemRoot", r"C:\Windows"), env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn(str(PROJECT), proc.stdout,
                         "PYTHONPATH artik sayiliyor - baslat.py'nin gerekcesi "
                         "degismis olabilir, baslat.py basligini guncelleyin")

    def test_bootstrap_sits_next_to_the_package(self):
        """`baslat.py` paketin YANINDA olmali - sys.path[0]'i o konum veriyor."""
        bootstrap = PROJECT / "baslat.py"
        self.assertTrue(bootstrap.is_file())
        self.assertTrue((PROJECT / "pcbqa" / "app.py").is_file())

    def test_explicit_interpreter_is_honoured(self):
        proc = self._run(["--version"], {"PCBQA_PYTHON": sys.executable})
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_missing_interpreter_is_reported(self):
        proc = self._run(["tani"], {"PCBQA_PYTHON": r"C:\yok\boyle\python.exe"})
        self.assertEqual(proc.returncode, 2)
        self.assertIn("PCBQA_PYTHON", proc.stderr)


@unittest.skipUnless(sys.platform == "win32", "baslatici Windows toplu dosyasi")
class ArayuzLauncherTests(unittest.TestCase):
    """Arayuzun kendi baslaticisi (kisayolun hedefi).

    Ayri bir dosya olmasinin sebebi olculdu: KiCad'in Python'unda tkinter YOK
    ve `pcbqa.cmd` once onu secer. Buradaki testler baslaticinin DOGRU CIFTI
    sectigini korur.
    """

    ARAYUZ = PROJECT / "pcbqa-arayuz.cmd"

    def _nerede(self) -> dict[str, str]:
        """`--nerede` tanilamasini calistirir; etiket -> deger."""
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.pop("PCBQA_PYTHON", None)
        proc = subprocess.run(
            ["cmd", "/c", str(self.ARAYUZ), "--nerede"],
            capture_output=True, text=True, cwd=str(PROJECT), env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        bulunan: dict[str, str] = {}
        for satir in proc.stdout.splitlines():
            if ":" in satir and satir.startswith("  "):
                etiket, _, deger = satir.partition(":")
                bulunan[etiket.strip()] = deger.strip()
        return bulunan

    def test_launcher_exists(self):
        self.assertTrue(self.ARAYUZ.is_file())

    def test_it_finds_an_interpreter_that_really_has_tkinter(self):
        """Varsayilmaz, sinanir: secilen yorumlayici tkinter'i ICE AKTARABILMELI."""
        secilen = self._nerede().get("tkinter'li", "")
        self.assertTrue(secilen, "hicbir yorumlayici secilmedi")
        proc = subprocess.run([secilen, "-c", "import tkinter"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0,
                         f"{secilen} tkinter'i ice aktaramiyor: {proc.stderr}")

    def test_the_windowless_twin_belongs_to_the_same_installation(self):
        """Ilk surumdeki gercek hata buydu.

        `pythonw` PATH'ten aliniyordu ve bu makinede o, Microsoft Store takma
        adi - yani tkinter'i sinadigimizdan BASKA bir kurulum. `start` onu
        calistiramadigi icin arayuz sessizce hic acilmiyor, baslatici yine de
        0 donuyordu. Konsolsuz ikiz, secilen yorumlayicinin KENDI klasorunden
        gelmeli.
        """
        bulunan = self._nerede()
        pyw = bulunan.get("konsolsuz", "")
        if pyw.startswith("YOK"):
            self.skipTest("bu kurulumda pythonw yok - konsollu acilir")
        python = Path(bulunan["tkinter'li"])
        self.assertEqual(Path(pyw).parent.resolve(), python.parent.resolve(),
                         "pythonw baska bir Python kurulumundan geliyor")

    def test_kicad_python_is_never_chosen(self):
        """KiCad'in Python'u tkinter getirmiyor; secilirse arayuz acilmaz.

        Denetim YOL METNIYLE yapilmaz - yazarken oyle yapildi ve dustu:
        kullanicinin proje klasorunun adi da "Kicad" oldugu icin secilen
        yolda zaten "kicad\\" geciyor. Karsilastirma KiCad'in GERCEK
        yorumlayici dosyasiyla.
        """
        from tests.test_swig_bridge import KICAD_PYTHON

        if not KICAD_PYTHON.is_file():
            self.skipTest("KiCad'in Python'u bulunamadi")
        secilen = self._nerede().get("tkinter'li", "")
        self.assertNotEqual(Path(secilen).resolve(), KICAD_PYTHON.resolve(),
                            "KiCad'in Python'u secilmis - onda tkinter yok")


if __name__ == "__main__":
    unittest.main()
