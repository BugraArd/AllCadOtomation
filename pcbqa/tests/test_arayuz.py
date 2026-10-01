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
        self.assertEqual(adlar, ["Yap", "Devre", "Kontrol", "Duzelt", "Deney", "Uret", "Canli"])

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

    # -- dagarcik (Yap sekmesinde) -----------------------------------------

    def test_the_vocabulary_tab_lists_known_types(self):
        self.a._dagarcik()
        self._bekle(30)
        metin = self.a.yap_cikti.get("1.0", "end")
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


    # -- Kontrol / Devre / elektriksel duzeltme / Uret (Kicad-5d6.11) -----

    def test_kontrol_proje_yokken_baslamaz(self):
        self.a.proje.set("")
        with patch("pcbqa.kontrol.calistir") as calistir:
            self.a._kontrol()
        calistir.assert_not_called()
        self.assertFalse(self.a.mesgul)
        self.assertIn("proje", self.a.kontrol_cikti.get("1.0", "end"))

    def test_kontrol_secimleri_servise_aynen_gider(self):
        """Kutucuklar seviye kumesine ve kalite bayragina birebir donusur."""
        from pcbqa.kontrol import KontrolRaporu

        self.a.kontrol_secim[3].set(False)
        self.a.kontrol_secim["kalite"].set(False)
        self.a.kosullar.set(str(self.tmp / "k.yaml"))
        with patch("pcbqa.kontrol.calistir",
                   return_value=KontrolRaporu("p", [], "rapor", 0)) as calistir:
            self.a._kontrol()
            self._bekle(30)
        args, kwargs = calistir.call_args
        self.assertEqual(args[1], self.tmp / "k.yaml")
        self.assertEqual(args[2], {1, 2})
        self.assertFalse(kwargs["kalite"])

    @unittest.skipUnless(kicad_available(), "KiCad kurulu degil")
    def test_kontrol_gercek_projede_tabloyu_doldurur_ve_cli_ile_ayni(self):
        """GERCEK kicad-cli: arayuz tablosu `pcbqa kontrol` raporuyla ayni satirlar."""
        from pcbqa import kontrol

        self.a.kontrol_secim[3].set(False)
        self.a._kontrol()
        self._bekle()
        satirlar = [self.a.kontrol_agac.item(i, "values") for i in self.a.kontrol_agac.get_children()]
        r = kontrol.calistir(self.proje, None, {1, 2})
        self.assertEqual([(x[0], x[1]) for x in satirlar], [(s.ad, s.durum) for s in r.satirlar])
        adlar = [x[0] for x in satirlar]
        self.assertIn("Kalite skoru (analiz)", adlar)
        self.assertIn("baglanti-esligi", adlar)          # 9 kontrolden biri
        self.assertIn("ERC/DRC tek kosu", self.a.durum.get())
        self.a.kontrol_agac.selection_set("0")
        self.a._kontrol_secildi()
        self.assertIn("skor", self.a.kontrol_cikti.get("1.0", "end"))

    @unittest.skipUnless(kicad_available(), "KiCad kurulu degil")
    def test_devre_grafi_cli_ciktisinin_aynisi(self):
        from pcbqa.devre import __main__ as devre_ana

        self.a._devre_grafi()
        self._bekle()
        metin = self.a.devre_cikti.get("1.0", "end").strip()
        _kod, beklenen = arayuz._yakala(devre_ana.main, [str(self.proje)])
        self.assertTrue(metin.startswith("DEVRE GRAFI"), metin[:200])
        self.assertEqual(metin, beklenen.strip())

    def test_elektriksel_duzeltme_kosullarsiz_baslamaz(self):
        self.a.kosullar.set("")
        with patch("pcbqa.duzeltme.sirala.main") as main:
            self.a._devre_duzelt()
        main.assert_not_called()
        self.assertIn("kosullar", self.a.duzelt_cikti.get("1.0", "end"))

    def test_elektriksel_duzeltme_ayni_cli_fonksiyonunu_cagirir(self):
        self.a.kosullar.set(str(self.tmp / "k.yaml"))
        with patch("pcbqa.duzeltme.sirala.main", return_value=0) as main:
            self.a._devre_duzelt()
            self._bekle(30)
        main.assert_called_once_with([str(self.proje), "--kosullar", str(self.tmp / "k.yaml")])

    def test_proje_secilince_yanindaki_kosullar_onerilir(self):
        (self.proje / "kosullar.yaml").write_text("version: 1\n", encoding="utf-8")
        self.a.kosullar.set("")
        self.a._proje_secildi(str(self.proje))
        self.assertEqual(self.a.kosullar.get(), str(self.proje / "kosullar.yaml"))
        # Kullanici bir kosullar dosyasi sectiyse uzerine YAZILMAZ.
        self.a.kosullar.set("benim.yaml")
        self.a._proje_secildi(str(self.proje))
        self.assertEqual(self.a.kosullar.get(), "benim.yaml")

    def test_uret_ardindan_kontrol_seviye_1_2(self):
        from pcbqa.kontrol import KontrolRaporu

        self.a.niyet.set(str(self.tmp / "n.yaml"))
        self.a.hedef.set(str(self.tmp / "cikti"))
        self.a.uret_kontrol.set(True)
        rapor = KontrolRaporu("p", [], "KONTROL-RAPORU", 0)
        with patch("pcbqa.generate.main", return_value=0), \
                patch("pcbqa.kontrol.calistir", return_value=rapor) as k:
            self.a._uret(False)
            self._bekle(30)
        args, kwargs = k.call_args
        self.assertEqual(args[0], self.tmp / "cikti")
        self.assertEqual(kwargs["seviyeler"], {1, 2})
        self.assertIn("KONTROL-RAPORU", self.a.uret_cikti.get("1.0", "end"))

    def test_closing_remembers_conditions(self):
        self.a.kosullar.set("k.yaml")
        self.a._kapat()
        self.assertEqual(arayuz.ayar_oku().get("kosullar"), "k.yaml")


    # -- Deney sekmesi (Kicad-d8k) ----------------------------------------

    def _deney_klasoru(self):
        """Elle kurulmus kucuk bir deney (TEST verisi; test_duzeltme_secim ile ayni bicim)."""
        import json

        from test_duzeltme_secim import _aday, _temel

        d = self.tmp / "deney"
        d.mkdir()
        kayitlar = [_temel(), _aday("aday-01-pahali", "gecti", 4.75), _aday("aday-02-ucuz", "gecti", 1),
                    _aday("aday-03-esit", "gecti", 1, ureteci="zz-esit")]
        (d / "deney.jsonl").write_text("\n".join(json.dumps(k) for k in kayitlar) + "\n", encoding="utf-8")
        (d / "ozet.json").write_text(json.dumps({"temel": "t", "adaylar": 3}), encoding="utf-8")
        return d

    def test_deney_kaynagi_yokken_gercek_degerlendirme_izlenimi_yok(self):
        self.assertIn("GOSTERILMIYOR", str(self.a.deney_durum["text"]))
        self.assertEqual(self.a.deney_agac.get_children(), ())
        self.a.deney_kaynak.set("")
        self.a._deney_yukle()
        self.assertFalse(self.a.mesgul)
        self.assertIn("GOSTERILMIYOR", str(self.a.deney_durum["text"]))

    def test_deney_yuklenir_secim_esitler_ve_gerekce_gorunur(self):
        self.a.deney_kaynak.set(str(self._deney_klasoru()))
        self.a._deney_yukle()
        self._bekle(30)
        satirlar = [self.a.deney_agac.item(i, "values") for i in self.a.deney_agac.get_children()]
        self.assertEqual([r[0] for r in satirlar], ["temel", "aday-01-pahali", "aday-02-ucuz", "aday-03-esit"])
        self.assertEqual([r[4] for r in satirlar], ["temel", "daha pahali", "SECILDI", "esit maliyet"])
        durum = str(self.a.deney_durum["text"])
        self.assertIn("Secilen: aday-02-ucuz", durum)
        self.assertIn("esit maliyetli: aday-03-esit", durum)
        detay = self.a.deney_detay.get("1.0", "end")
        self.assertIn("aday-01-pahali adayini secerdi", detay)        # eski kural ayri
        self.a.deney_agac.selection_set("0")
        self.a._deney_secildi()
        self.assertIn("1,81-2,24 V", self.a.deney_detay.get("1.0", "end"))

    def test_bellek_veri_kumesi_gercek_deney_gibi_gosterilmez(self):
        import json

        b = self.tmp / "bellek"
        b.mkdir()
        (b / "kayitlar.jsonl").write_text(json.dumps({"tur": "referans", "kimlik": "r"}) + "\n", encoding="utf-8")
        self.a.deney_kaynak.set(str(b))
        self.a._deney_yukle()
        self._bekle(30)
        self.assertEqual(self.a.deney_agac.get_children(), ())
        self.assertIn("gercek proje deneyi DEGIL", str(self.a.deney_durum["text"]))

    def test_deney_envanteri_ayni_servisten(self):
        from pcbqa.duzeltme.envanter import envanter_metni

        d = self._deney_klasoru()
        self.a.deney_kaynak.set(str(d))
        self.a._deney_envanter()
        self._bekle(30)
        self.assertEqual(self.a.deney_detay.get("1.0", "end").strip(), envanter_metni([d])[0].strip())

    def test_desteklenmeyen_proje_icin_deney_baslatilmaz(self):
        """pic_programmer'da pcbqa-referans.json yok: is hic baslamaz."""
        self.a.deney_cikti.set(str(self.tmp / "cikti"))
        self.a._deney_calistir()
        self.assertFalse(self.a.mesgul)
        self.assertIn("pcbqa-referans.json yok", str(self.a.deney_durum["text"]))
        self.assertFalse((self.tmp / "cikti").exists())

if __name__ == "__main__":
    unittest.main()
