"""Masaustu arayuzu.

Arayuzun goruntusu sinanmaz. Onizleme/silahlanma kapisi 2026-09-27'de kullanici
talimatiyla KALDIRILDI; "Uygula" dugmeleri surekli acik ve tek tikla yazar. Bu
yuzden sinanan sey artik kilit degil, YAZMA KAPILARI: anlasilmayan cumle dosyaya
dokunmaz, eksik girdi is baslatmaz ve plan ile yazma tek kosumda zincirlenir.

Canli YERLESTIRME plani (`b_canli_uygula`) bu degisiklikten muaftir - hala iki
adimlidir ve kilidi burada sinanmaya devam eder.

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

    def test_all_tabs_are_present(self):
        adlar = [self.a.defter.tab(t, "text") for t in self.a.defter.tabs()]
        self.assertEqual(adlar, ["Yap", "Parcalar", "Analiz", "Duzelt", "Uret", "Canli", "Ortam"])

    def test_fix_apply_is_always_available(self):
        """Onizleme kapisi kalkti: dugme bir kuru kosum beklemez."""
        self.assertEqual(str(self.a.b_duzelt_uygula["state"]), "normal")

    def test_fix_apply_without_a_finding_id_does_not_start(self):
        """Finding ID yoksa is baslatilmaz - sessizce degil, ekrana yazarak."""
        self.a.duzelt_finding.set("")
        with patch("pcbqa.duzelt.main") as main:
            self.a._duzelt_uygula()
        main.assert_not_called()
        self.assertIn("gerekli", self.a.duzelt_cikti.get("1.0", "end"))

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

    def test_apply_starts_unlocked(self):
        """Yazma dugmeleri artik baslangicta aciktir."""
        self.assertEqual(str(self.a.b_uygula["state"]), "normal")
        self.assertEqual(str(self.a.b_sematik_uygula["state"]), "normal")
        self.assertEqual(str(self.a.b_pcb_uygula["state"]), "normal")

    def test_live_schematic_chains_prepare_and_apply(self):
        """Plan ile yazma AYNI kosumda zincirlenir; arada bayatlama olamaz."""
        with patch("pcbqa.canli_sematik.request") as request:
            request.return_value = {"description": "plan"}
            self.a._sematik_uygula()
            self._bekle(30)
        eylemler = [cagri.args[0] for cagri in request.call_args_list]
        self.assertEqual(eylemler, ["prepare", "apply"])

    # -- yazma kapilari ----------------------------------------------------

    def test_a_refused_sentence_writes_nothing(self):
        """Anlasilmayan cumle tek tikla bile dosyaya dokunamaz."""
        sch = self.proje / "pic_programmer.kicad_sch"
        onceki = sch.read_text(encoding="utf-8")
        self.a.komut.set("bir transistor ekle")   # belirsiz -> ENGEL
        self.a._uygula()
        self._bekle(30)
        self.assertEqual(sch.read_text(encoding="utf-8"), onceki)
        # Sessizce vazgecmek yetmez - kullaniciya NEDEN yazilmali.
        self.assertIn("komut uygulanmadi", self.a.durum.get())

    def test_an_empty_sentence_does_not_start_a_job(self):
        self.a.komut.set("")
        with patch("pcbqa.komut.anla") as anla:
            self.a._uygula()
        anla.assert_not_called()
        self.assertIn("komut cumlesi", self.a.yap_cikti.get("1.0", "end"))

    @unittest.skipUnless(kicad_available(), "KiCad kurulu degil")
    def test_a_good_sentence_writes_in_one_step(self):
        """Onizleme yok: tek tik hem cozumler hem yazar, yedegi birakir."""
        sch = self.proje / "pic_programmer.kicad_sch"
        onceki = sch.read_text(encoding="utf-8")
        self.a.komut.set("10 adet kapasitor ekle")
        self.a._uygula()
        self._bekle()
        cikti = self.a.yap_cikti.get("1.0", "end")
        self.assertIn("yazildi:", cikti, cikti[:400])
        self.assertNotEqual(sch.read_text(encoding="utf-8"), onceki)
        self.assertIn("eylem yazildi", self.a.durum.get())

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
    def test_writing_does_not_ask_for_confirmation(self):
        """Onay diyalogu da kaldirildi: tek tik = yazma, arada soru yok."""
        self.a.komut.set("10 adet kapasitor ekle")
        self.diyaloglar.clear()
        self.a._uygula()
        self._bekle()
        self.assertFalse([ad for ad, _ in self.diyaloglar if ad == "askokcancel"],
                         f"beklenmeyen onay sorusu: {self.diyaloglar}")


if __name__ == "__main__":
    unittest.main()
