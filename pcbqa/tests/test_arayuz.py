"""Masaustu arayuzu.

Arayuzun goruntusu sinanmaz - sinanan sey GUVENLIK KILIDIDIR: "Uygula"
dugmesi yalnizca EKRANDA GORULEN planla AYNI cumle ve AYNI proje icin acik
olabilir. CLI'de bu is `--uygula` bayragini yazmak zorunda kalmakla
saglaniyor; arayuzde bir dugme oldugu icin kilidin kendisi sinanmali.

Tk baslatilamayan bir ortamda (uzak oturum, ekransiz makine) butun sinif
atlanir.
"""

from __future__ import annotations

import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from pcbqa import arayuz, symlib
from pcbqa.kicadcli import KicadCliError, find_kicad_cli

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
PROJECT_DIR = SAMPLES / "pic_programmer"
LOCK_NAME = "~pic_programmer.kicad_pro.lck"


def tk_calisiyor() -> bool:
    if not arayuz.tkinter_var():
        return False
    try:
        import tkinter as tk

        kok = tk.Tk()
        kok.destroy()
        return True
    except Exception:  # noqa: BLE001 - ekransiz ortamda TclError
        return False


def kicad_available() -> bool:
    try:
        find_kicad_cli()
        symlib.get_symbol("Device:C")
        return True
    except (KicadCliError, symlib.SymLibError):
        return False


class YorumlayiciTests(unittest.TestCase):
    """Bunlar Tk penceresi ACMADAN kosar."""

    def test_this_interpreter_reports_its_tkinter_honestly(self):
        import importlib.util

        beklenen = importlib.util.find_spec("tkinter") is not None
        self.assertEqual(arayuz.tkinter_var(), beklenen)

    def test_a_python_without_tkinter_is_detected(self):
        """KiCad'in Python'unda tkinter yok; ayirt edebilmeliyiz."""
        self.assertFalse(arayuz.tkinter_var("bu-python-yok-12345"))

    def test_the_help_text_says_what_to_do(self):
        self.assertIn("PCBQA_PYTHON", arayuz._YARDIM)
        self.assertIn("pcbqa yap", arayuz._YARDIM)

    def test_missing_settings_file_is_not_an_error(self):
        eski = arayuz.AYAR_DOSYASI
        arayuz.AYAR_DOSYASI = Path(tempfile.gettempdir()) / "pcbqa-yok-12345.json"
        self.addCleanup(setattr, arayuz, "AYAR_DOSYASI", eski)
        self.assertEqual(arayuz.ayar_oku(), {})


@unittest.skipUnless(tk_calisiyor(), "Tk baslatilamiyor (ekransiz ortam?)")
class PencereTests(unittest.TestCase):
    """Her test icin TEK bir Tk yorumlayicisi, ayri bir Toplevel penceresi.

    Test basina `tk.Tk()` kurup yikmak `Tcl_AsyncDelete: async handler deleted
    by the wrong thread` ile YIKILIYORDU (olculdu): Tk yorumlayicisi bir kez
    kurulur, pencereler onun altinda gelip gider.
    """

    @classmethod
    def setUpClass(cls):
        import tkinter as tk

        cls.kok = tk.Tk()
        cls.kok.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.kok.destroy()

    def setUp(self):
        import tkinter as tk

        # Kullanicinin gercek ayar dosyasina DOKUNMA.
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-arayuz-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        eski = arayuz.AYAR_DOSYASI
        arayuz.AYAR_DOSYASI = self.tmp / "arayuz.json"
        self.addCleanup(setattr, arayuz, "AYAR_DOSYASI", eski)

        self.proje = self.tmp / "proje"
        shutil.copytree(PROJECT_DIR, self.proje)
        (self.proje / LOCK_NAME).unlink(missing_ok=True)

        # Diyaloglar MODALDIR: acilirsa test sonsuza kadar bekler. Cagrilip
        # cagrilmadigini da bilmek istiyoruz, o yuzden yutmuyoruz - kaydediyoruz.
        from tkinter import messagebox

        self.diyaloglar: list[tuple[str, str]] = []
        for ad, cevap in (("showwarning", None), ("showerror", None),
                          ("showinfo", None), ("askokcancel", False)):
            eski_fn = getattr(messagebox, ad)
            self.addCleanup(setattr, messagebox, ad, eski_fn)
            setattr(messagebox, ad,
                    lambda *a, _ad=ad, _c=cevap, **k: (
                        self.diyaloglar.append((_ad, " ".join(map(str, a)))) or _c))

        self.root = tk.Toplevel(self.kok)
        self.root.withdraw()  # test ekrani kirletmesin
        self.addCleanup(self._guvenli_kapat)
        self.a = arayuz.Arayuz(self.root, proje=str(self.proje))
        self.root.update()

    def _guvenli_kapat(self):
        # Once zamanlayici, sonra pencere: tersi sirada bekleyen `after`
        # yok edilmis bir pencereye ates ediyor.
        try:
            self.a.durdur()
            self.root.destroy()
        except Exception:  # noqa: BLE001 - test zaten kapatmis olabilir
            pass

    def _bekle(self, saniye: float = 180.0):
        """Arka plan isi bitene kadar olay dongusunu cevir."""
        son = time.time() + saniye
        while self.a.mesgul and time.time() < son:
            self.root.update()
            time.sleep(0.02)
        self.root.update()
        self.assertFalse(self.a.mesgul, "arka plan isi zaman asimina ugradi")

    # -- kurulum -----------------------------------------------------------

    def test_all_six_tabs_are_present(self):
        adlar = [self.a.defter.tab(t, "text") for t in self.a.defter.tabs()]
        self.assertEqual(adlar, ["Yap", "Parcalar", "Analiz", "Uret", "Canli", "Ortam"])

    def test_live_apply_needs_preview(self):
        self.assertEqual(str(self.a.b_canli_uygula["state"]), "disabled")
        self.a._canli_uygula()
        self.assertTrue(any(ad == "showwarning" for ad, _ in self.diyaloglar))

    def test_project_change_disarms_live_preview(self):
        self.a.canli_plan = object()
        self.a.canli_proje = str(self.proje)
        self.a.b_canli_uygula.config(state="normal")
        self.a.proje.set(str(self.tmp / "baska"))
        self.a._sil_silah()
        self.assertIsNone(self.a.canli_plan)
        self.assertEqual(str(self.a.b_canli_uygula["state"]), "disabled")

    def test_apply_starts_locked(self):
        self.assertEqual(str(self.a.b_uygula["state"]), "disabled")

    def test_live_schematic_requires_matching_preview(self):
        with patch('pcbqa.canli_sematik.request') as request:
            self.a._sematik_uygula()
        request.assert_not_called()
        self.assertEqual(str(self.a.b_sematik_uygula['state']), 'disabled')

    def test_live_schematic_command_edit_disarms_preview(self):
        self.a.sematik_plan = {'description': 'old plan'}
        self.a.b_sematik_uygula.config(state='normal')
        self.a.sematik_komut.set('R1 degerini 10k yap')
        self.assertIsNone(self.a.sematik_plan)
        self.assertEqual(str(self.a.b_sematik_uygula['state']), 'disabled')

    # -- guvenlik kilidi ---------------------------------------------------

    def test_a_refused_sentence_never_arms_apply(self):
        self.a.komut.set("bir transistor ekle")   # belirsiz -> ENGEL
        self.a._anla()
        self._bekle(30)
        self.assertIsNone(self.a.kuru_imza)
        self.assertEqual(str(self.a.b_uygula["state"]), "disabled")

    def test_applying_without_a_dry_run_is_refused(self):
        """Kilit sadece dugmenin gorunumu degil: `_uygula` kendisi de bakar."""
        self.a.komut.set("10 adet kapasitor ekle")
        self.a.kuru_imza = None
        onceki = (self.proje / "pic_programmer.kicad_sch").read_text(encoding="utf-8")
        self.a._uygula()
        self._bekle(30)
        self.assertEqual(
            (self.proje / "pic_programmer.kicad_sch").read_text(encoding="utf-8"),
            onceki)
        # Sessizce vazgecmek yetmez - kullaniciya NEDEN yazilmali.
        self.assertTrue(any(ad == "showwarning" for ad, _ in self.diyaloglar),
                        f"uyari verilmedi: {self.diyaloglar}")

    @unittest.skipUnless(kicad_available(), "KiCad kurulu degil")
    def test_a_good_sentence_arms_apply_and_editing_disarms_it(self):
        self.a.komut.set("10 adet kapasitor ekle")
        self.a._anla()
        self._bekle()
        self.assertEqual(str(self.a.b_uygula["state"]), "normal",
                         self.a.yap_cikti.get("1.0", "end")[:400])
        self.assertIsNotNone(self.a.kuru_imza)

        # Cumle degisti - ekrandaki plan artik bu cumleye ait degil.
        self.a.komut.set("10 adet direnc ekle")
        self.a._sil_silah()
        self.assertIsNone(self.a.kuru_imza)
        self.assertEqual(str(self.a.b_uygula["state"]), "disabled")

    @unittest.skipUnless(kicad_available(), "KiCad kurulu degil")
    def test_changing_the_project_also_disarms(self):
        self.a.komut.set("10 adet kapasitor ekle")
        self.a._anla()
        self._bekle()
        self.assertEqual(str(self.a.b_uygula["state"]), "normal")
        self.a.proje.set(str(self.tmp))
        self.a._sil_silah()
        self.assertEqual(str(self.a.b_uygula["state"]), "disabled")

    @unittest.skipUnless(kicad_available(), "KiCad kurulu degil")
    def test_a_dry_run_writes_nothing(self):
        sch = self.proje / "pic_programmer.kicad_sch"
        onceki = sch.read_text(encoding="utf-8")
        self.a.komut.set("10 adet kapasitor ekle")
        self.a._anla()
        self._bekle()
        self.assertEqual(sch.read_text(encoding="utf-8"), onceki)

    # -- parcalar ----------------------------------------------------------

    @unittest.skipUnless(kicad_available(), "KiCad kurulu degil")
    def test_the_parts_table_fills_the_grid(self):
        self.a._parcalar()
        self._bekle()
        self.assertTrue(self.a.agac.get_children(), self.a.durum.get())
        self.assertEqual(len(self.a.satirlar), len(self.a.agac.get_children()))
        self.assertIn("parca", self.a.durum.get())

    # -- ortam -------------------------------------------------------------

    def test_the_vocabulary_tab_lists_known_types(self):
        self.a._dagarcik()
        self._bekle(30)
        metin = self.a.ortam_cikti.get("1.0", "end")
        self.assertIn("Device:C", metin)
        self.assertIn("Kondansator", metin)

    # -- ayarlar -----------------------------------------------------------

    def test_closing_remembers_the_project(self):
        self.a._kapat()
        self.assertEqual(arayuz.ayar_oku().get("proje"), str(self.proje))

    @unittest.skipUnless(kicad_available(), "KiCad kurulu degil")
    def test_apply_asks_before_writing_and_a_cancel_writes_nothing(self):
        """Onay diyalogu iptal edilirse hicbir sey yazilmamali."""
        sch = self.proje / "pic_programmer.kicad_sch"
        onceki = sch.read_text(encoding="utf-8")
        self.a.komut.set("10 adet kapasitor ekle")
        self.a._anla()
        self._bekle()
        self.assertEqual(str(self.a.b_uygula["state"]), "normal")
        self.diyaloglar.clear()
        self.a._uygula()          # askokcancel yamasi False doner = iptal
        self._bekle(30)
        self.assertTrue(any(ad == "askokcancel" for ad, _ in self.diyaloglar),
                        f"onay sorulmadi: {self.diyaloglar}")
        self.assertEqual(sch.read_text(encoding="utf-8"), onceki)


if __name__ == "__main__":
    unittest.main()
