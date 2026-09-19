"""Asama 4g: dogal dil komutu -> ekleme.

Burada korunan sey DOGRU ANLAMA degil, YANLIS ANLAMAMA'dir. Bir cozumleyici
icin tehlikeli olan cevap veremedigi cumle degil, yanlis cevap verdigi
cumledir: "10 kapasitor" isteyip 10 farad'lik tek bir kapasitor almak,
"transistor" deyip rastgele bir NPN almak, tanimadigi bir kelimeyi sessizce
atlamak. Testlerin cogu bu yuzden REDDI olcer.

Cozumleme testleri KiCad'siz kosar (`anla` kutuphaneye dokunmaz); kutuphane
ve uctan uca testleri KiCad kuruluysa kosar.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from pcbqa import symlib
from pcbqa.kicadcli import KicadCliError, find_kicad_cli
from pcbqa.komut import (
    AG_ADLARI,
    BAGLA_FIILLERI,
    BELIRSIZ,
    DOLGU,
    EKLE_FIILLERI,
    HENUZ_YOK,
    KAPSAM_SOZCUKLERI,
    NITELEYICILER,
    SAYILAR,
    SOZCUKLER,
    TURLER,
    KomutError,
    _HEDEF_OLMAZ,
    anla,
    deger_coz,
    kok_sematik,
    mevcut_aglar,
    sadelestir,
    uygula,
)
from pcbqa.sch_verify import connectivity_of
from pcbqa.schematic import read_schematic

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
PROJECT_DIR = SAMPLES / "pic_programmer"
LOCK_NAME = "~pic_programmer.kicad_pro.lck"


def kicad_cli_available() -> bool:
    try:
        find_kicad_cli()
        return True
    except KicadCliError:
        return False


def device_library_available() -> bool:
    try:
        symlib.get_symbol("Device:R")
        return True
    except symlib.SymLibError:
        return False


# --------------------------------------------------------------------------
# Sadelestirme
# --------------------------------------------------------------------------


class SadelestirTests(unittest.TestCase):
    def test_turkish_uppercase_i_does_not_leave_a_combining_dot(self):
        """Python'un `lower()`i "İ"yi "i" + U+0307 yapar - tablo eslesmesi kacar."""
        self.assertEqual(sadelestir("İNDÜKTÖR"), "induktor")
        self.assertNotIn("̇", sadelestir("İ"))

    def test_dotless_i_and_other_letters_fold_to_ascii(self):
        self.assertEqual(sadelestir("KAPASİTÖR"), "kapasitor")
        self.assertEqual(sadelestir("Direnç"), "direnc")
        self.assertEqual(sadelestir("ışık"), "isik")
        self.assertEqual(sadelestir("µF"), "uf")


# --------------------------------------------------------------------------
# Deger
# --------------------------------------------------------------------------


class DegerTests(unittest.TestCase):
    def test_a_bare_number_is_a_count_not_a_value(self):
        """"10 kapasitor" 10 ADET demektir, 10 farad degil."""
        self.assertIsNone(deger_coz("10"))
        self.assertIsNone(deger_coz("4.7"))

    def test_prefix_case_is_preserved(self):
        """"10M" mega, "10m" milidir - sadelestirilmis kelimeden okunsaydi
        ikisi ayni olurdu."""
        self.assertEqual(deger_coz("10M"), "10M")
        self.assertEqual(deger_coz("10m"), "10m")

    def test_unit_is_normalised_but_number_is_not_touched(self):
        self.assertEqual(deger_coz("100nf"), "100nF")
        self.assertEqual(deger_coz("4.7uF"), "4.7uF")
        self.assertEqual(deger_coz("22p"), "22p")

    def test_iec_60062_letter_notation(self):
        self.assertEqual(deger_coz("4u7"), "4u7")
        self.assertEqual(deger_coz("4k7"), "4k7")

    def test_ohm_is_written_the_kicad_way(self):
        self.assertEqual(deger_coz("10ohm"), "10R")
        self.assertEqual(deger_coz("10R"), "10R")
        self.assertEqual(deger_coz("10k"), "10k")

    def test_words_are_not_values(self):
        self.assertIsNone(deger_coz("kapasitor"))
        self.assertIsNone(deger_coz("0603"))


# --------------------------------------------------------------------------
# Cozumleme
# --------------------------------------------------------------------------


class AnlaTests(unittest.TestCase):
    def test_the_sentence_this_module_exists_for(self):
        yorum = anla("su anki modelimize 10 adet kapasitör koy")
        self.assertTrue(yorum.ok, yorum.describe())
        self.assertEqual(len(yorum.eylemler), 1)
        eylem = yorum.eylemler[0]
        self.assertEqual(eylem.adet, 10)
        self.assertEqual(eylem.lib_id, "Device:C")

    def test_turkish_number_words_are_read(self):
        """"on" bir dolgu kelimesi sayilirsa Turkce 10 kaybolur."""
        self.assertEqual(anla("on adet LED ekle").eylemler[0].adet, 10)
        self.assertEqual(anla("iki buton koy").eylemler[0].adet, 2)

    def test_count_and_value_do_not_collide(self):
        eylem = anla("5 tane 100nF kondansatör ekle").eylemler[0]
        self.assertEqual(eylem.adet, 5)
        self.assertEqual(eylem.deger, "100nF")

    def test_package_code_is_a_footprint_not_a_count(self):
        eylem = anla("3 adet 0603 direnç ekle").eylemler[0]
        self.assertEqual(eylem.adet, 3)
        self.assertEqual(eylem.footprint, "Resistor_SMD:R_0603_1608Metric")

    def test_package_without_a_table_is_refused_not_ignored(self):
        yorum = anla("3 adet 1206 bobin ekle")
        self.assertFalse(yorum.ok)
        self.assertTrue(any("1206" in e for e in yorum.engeller), yorum.engeller)

    def test_an_adjective_can_change_the_symbol(self):
        eylem = anla("2 polarize kapasitör ekle").eylemler[0]
        self.assertEqual(eylem.lib_id, "Device:C_Polarized")

    def test_ve_splits_one_sentence_into_two_actions(self):
        yorum = anla("5 adet 100nF kondansatör ve 3 adet 10k direnç ekle")
        self.assertTrue(yorum.ok, yorum.describe())
        self.assertEqual([(e.adet, e.lib_id, e.deger) for e in yorum.eylemler],
                         [(5, "Device:C", "100nF"), (3, "Device:R", "10k")])

    def test_a_decimal_comma_does_not_split_the_sentence(self):
        """Turkce ondalik ayraci virguldur; "4,7k" bolunurse deger kaybolur."""
        yorum = anla("2 adet 4,7k direnç ekle")
        self.assertEqual(len(yorum.eylemler), 1, yorum.describe())

    def test_suffixes_are_stripped_only_onto_a_known_word(self):
        """"kapasitorleri" taninir; "zimbirti" TANINMAZ ve engel olur."""
        self.assertTrue(anla("kapasitörleri ekle: 6 tane").ok)
        yorum = anla("5 adet zımbırtı ekle")
        self.assertFalse(yorum.ok)
        self.assertTrue(any("zımbırtı" in e for e in yorum.engeller), yorum.engeller)

    def test_english_works_too(self):
        eylem = anla("add 4 crystals").eylemler[0]
        self.assertEqual((eylem.adet, eylem.lib_id), (4, "Device:Crystal"))


class RedTests(unittest.TestCase):
    """Reddedilmesi gerekenler. Bir cozumleyicinin degeri buradadir."""

    def test_no_verb_is_refused(self):
        yorum = anla("kapasitör")
        self.assertFalse(yorum.ok)
        self.assertTrue(any("fiil" in e for e in yorum.engeller), yorum.engeller)

    def test_a_verb_we_do_not_implement_says_so_by_name(self):
        """"Anlamadim" ile "henuz yapmiyorum" ayri seylerdir."""
        yorum = anla("C5'i sil")
        self.assertFalse(yorum.ok)
        self.assertTrue(any("sil" in e for e in yorum.engeller), yorum.engeller)

    def test_an_ambiguous_word_lists_its_candidates(self):
        yorum = anla("bir transistör ekle")
        self.assertFalse(yorum.ok)
        self.assertEqual(yorum.eylemler, [])
        self.assertTrue(any("Q_NPN" in e for e in yorum.engeller), yorum.engeller)

    def test_an_unknown_component_lists_what_is_known(self):
        yorum = anla("5 adet flux kapasitörü ekle")
        # "kapasitoru" tanindigi icin bu gecerli sayilir; ama "flux" yutulmaz.
        self.assertTrue(any("flux" in n for n in yorum.notlar), yorum.notlar)

    def test_two_component_types_in_one_clause_are_refused(self):
        yorum = anla("5 kapasitör direnç ekle")
        self.assertFalse(yorum.ok)

    def test_empty_command_is_refused(self):
        self.assertFalse(anla("   ").ok)

    def test_a_missing_value_is_reported_never_invented(self):
        """Kaynagi olmayan varsayilan (or. "kondansator = 100nF") yazilmaz."""
        yorum = anla("10 adet kapasitör ekle")
        self.assertEqual(yorum.eylemler[0].deger, "")
        self.assertTrue(any("deger verilmedi" in n for n in yorum.notlar), yorum.notlar)


# --------------------------------------------------------------------------
# Baglama
# --------------------------------------------------------------------------


class BaglamaTests(unittest.TestCase):
    """Baglama EKLEME ile ayni cumlede yapilir.

    Buradaki tehlike ekleme tarafindakinden buyuktur: yanlis uca yanlis ag
    adi yazmak sematikte GECERLI bir islemdir ve netlist kalkani da onu
    kabul eder (yeni bir ag olusturmak mesru bir istektir). Kalkan
    yakalamadigi icin testlerin cogu yine REDDI olcer.
    """

    def test_the_sentence_this_feature_exists_for(self):
        yorum = anla("10 adet 100nF kapasitör ekle ve hepsini VCC-GND "
                     "arasına bağla")
        self.assertTrue(yorum.ok, yorum.engeller)
        self.assertEqual(len(yorum.eylemler), 1)
        eylem = yorum.eylemler[0]
        self.assertEqual(eylem.adet, 10)
        self.assertEqual(eylem.baglar, ["1=VCC", "2=GND"])

    def test_ve_inside_the_clause_does_not_split_the_sentence(self):
        """Ayrac "ve"dir; kalip once ayrilmazsa cumle ikiye bolunur."""
        yorum = anla("4 kapasitör ekle ve hepsini VCC ve GND arasına bağla")
        self.assertTrue(yorum.ok, yorum.engeller)
        self.assertEqual(len(yorum.eylemler), 1)
        self.assertEqual(yorum.eylemler[0].baglar, ["1=VCC", "2=GND"])

    def test_a_net_named_toprak_is_not_a_ground_symbol(self):
        """"toprak" hem ag adi hem bilesen turudur (power:GND). Kalip
        ayrilmazsa sayfaya istenmeyen bir toprak sembolu de eklenir."""
        yorum = anla("3 kapasitör ekle ve hepsini VCC ile toprak arasına bağla")
        self.assertEqual([e.lib_id for e in yorum.eylemler], ["Device:C"])
        self.assertEqual(yorum.eylemler[0].baglar, ["1=VCC", "2=GND"])

    def test_a_structural_word_is_never_read_as_a_net(self):
        """Olculdu: ayrac " ve " oldugu icin kalip en soldan esliyordu ve
        "2 diyot ekle ve VCC-GND arasina bagla" cumlesinde hedefler
        ("ekle", "VCC-GND") diye okunuyordu - iki diyotun katoduna "ekle"
        adinda bir ag yazilacakti."""
        yorum = anla("2 diyot ekle ve VCC-GND arasına bağla")
        self.assertEqual(yorum.eylemler[0].baglar, ["1=VCC", "2=GND"])

    def test_the_hyphen_form_says_it_split_the_word(self):
        yorum = anla("2 kapasitör ekle ve VCC-GND arasına bağla")
        self.assertEqual(yorum.eylemler[0].baglar, ["1=VCC", "2=GND"])
        self.assertTrue(any("iki ag adi" in n for n in yorum.notlar), yorum.notlar)

    def test_a_hyphen_inside_a_net_name_survives(self):
        """Gercek kartta ag adi tireli olur (CLOCK-RB6, samples/pic_programmer).
        Acik ayrac varsa tire bolunmemeli."""
        yorum = anla("2 kapasitör ekle ve hepsini CLOCK-RB6 ile DATA-RB7 "
                     "arasına bağla")
        self.assertEqual(yorum.eylemler[0].baglar,
                         ["1=CLOCK-RB6", "2=DATA-RB7"])

    def test_english_between_and(self):
        yorum = anla("add 4 10k resistors between VCC and GND")
        self.assertTrue(yorum.ok, yorum.engeller)
        self.assertEqual(yorum.eylemler[0].baglar, ["1=VCC", "2=GND"])

    def test_net_name_case_is_not_touched_while_parsing(self):
        """KiCad'de "VCC" ile "vcc" ayri iki agdir. Yazim `uygula`da
        sematige BAKILARAK duzeltilir, cozumlemede tahmin edilmez."""
        yorum = anla("2 kapasitör ekle ve hepsini vcc ile Vpp arasına bağla")
        self.assertEqual(yorum.eylemler[0].baglar, ["1=vcc", "2=Vpp"])

    def test_connect_without_a_pattern_is_refused(self):
        """Baglantisiz sembol birakmaktansa hic eklememek yeglenir."""
        yorum = anla("10 kapasitör ekle ve bağla")
        self.assertFalse(yorum.ok)
        self.assertEqual(yorum.eylemler, [])

    def test_connect_without_an_add_verb_is_refused(self):
        """Sayfada duran sembolleri baglamak ayri bir istir: bu katman
        baglanacak sembolleri kendisi uretir."""
        yorum = anla("C5 ile C6 arasına bağla")
        self.assertFalse(yorum.ok)
        self.assertEqual(yorum.eylemler, [])

    def test_a_reference_is_not_a_net_name(self):
        """"C5" adinda bir etiket yazmak, istenenin tam tersidir."""
        yorum = anla("2 kapasitör ekle ve hepsini C5 ile GND arasına bağla")
        self.assertFalse(yorum.ok)
        self.assertEqual(yorum.eylemler, [])
        self.assertTrue(any("C5" in e for e in yorum.engeller), yorum.engeller)

    def test_two_additions_without_a_scope_word_are_refused(self):
        yorum = anla("5 direnç ve 5 kapasitör ekle ve VCC ile GND arasına bağla")
        self.assertFalse(yorum.ok)
        self.assertTrue(any("belirsiz" in e for e in yorum.engeller), yorum.engeller)

    def test_hepsini_binds_every_addition(self):
        yorum = anla("5 direnç ve 5 kapasitör ekle, hepsini VCC ile GND "
                     "arasına bağla")
        self.assertTrue(yorum.ok, yorum.engeller)
        self.assertEqual([e.baglar for e in yorum.eylemler],
                         [["1=VCC", "2=GND"]] * 2)

    def test_a_one_terminal_symbol_cannot_be_bound(self):
        yorum = anla("3 toprak ekle ve VCC-GND arasına bağla")
        self.assertFalse(yorum.ok)
        self.assertTrue(any("iki uclu degil" in e for e in yorum.engeller),
                        yorum.engeller)

    def test_polarity_is_stated_never_silently_chosen(self):
        """Kutuplu bilesende yon ELEKTRIKSEL bir karardir; cumle onu
        soylemez, biz de sessizce secmeyiz."""
        yorum = anla("2 LED ekle ve hepsini VCC ile GND arasına bağla")
        self.assertTrue(yorum.ok, yorum.engeller)
        self.assertTrue(any("katot" in n for n in yorum.notlar), yorum.notlar)

    def test_a_verb_glued_to_a_comma_is_still_a_verb(self):
        """"... ekle, hepsini ..." dogal yazimdir; "ekle," fiil sayilmazsa
        cumle "fiil yok" diye reddedilirdi."""
        yorum = anla("4 kapasitör ekle, hepsini VCC ile GND arasına bağla")
        self.assertTrue(yorum.ok, yorum.engeller)

    def test_adding_without_binding_still_works(self):
        """Baglama katmani, baglama istenmeyen cumleye dokunmamali."""
        yorum = anla("10 adet kapasitör ekle")
        self.assertTrue(yorum.ok, yorum.engeller)
        self.assertEqual(yorum.eylemler[0].baglar, [])


# --------------------------------------------------------------------------
# Dagarcigin ic tutarliligi
# --------------------------------------------------------------------------


class DagarcikTests(unittest.TestCase):
    """Tablolar buyudukce bozulur; bu testler bozulmayi ilk kosuda yakalar."""

    def test_every_word_points_at_a_real_type(self):
        for kelime, tur in SOZCUKLER.items():
            with self.subTest(kelime):
                self.assertIn(tur, TURLER)

    def test_every_type_has_at_least_one_word(self):
        kullanilan = set(SOZCUKLER.values()) | {
            hedef for tablo in NITELEYICILER.values() for hedef in tablo.values()
        }
        for tur in TURLER:
            with self.subTest(tur):
                self.assertIn(tur, kullanilan)

    def test_filler_words_never_shadow_a_number_or_a_component(self):
        """Bir kere oldu: "on" Ingilizce edat diye dolguya kondu ve Turkce
        "on adet" komutundaki 10 sessizce 1'e dustu."""
        self.assertEqual(DOLGU & set(SAYILAR), set())
        self.assertEqual(DOLGU & set(SOZCUKLER), set())
        self.assertEqual(DOLGU & set(BELIRSIZ), set())
        self.assertEqual(DOLGU & EKLE_FIILLERI, set())

    def test_a_word_is_either_ambiguous_or_resolved_never_both(self):
        self.assertEqual(set(BELIRSIZ) & set(SOZCUKLER), set())

    def test_verbs_do_not_overlap(self):
        self.assertEqual(EKLE_FIILLERI & set(HENUZ_YOK), set())
        self.assertEqual(EKLE_FIILLERI & BAGLA_FIILLERI, set())
        self.assertEqual(BAGLA_FIILLERI & set(HENUZ_YOK), set())
        self.assertEqual(BAGLA_FIILLERI & DOLGU, set())
        self.assertEqual(KAPSAM_SOZCUKLERI & DOLGU, set())

    def test_every_type_declares_its_terminals(self):
        """Baglama pin NUMARASI ister; tabloya tur eklenip `uclar`
        unutulursa `_baglantilari_dagit` KeyError verirdi."""
        for tur, bilgi in TURLER.items():
            with self.subTest(tur):
                self.assertIn("uclar", bilgi)
                self.assertIn(len(bilgi["uclar"]), (0, 2))
                if bilgi.get("uc_adlari"):
                    self.assertEqual(len(bilgi["uc_adlari"]), 2)
                    self.assertEqual(len(bilgi["uclar"]), 2)

    def test_a_net_word_is_never_treated_as_a_structural_word(self):
        """"toprak" gecerli bir hedeftir; yapi sozcugu sayilsaydi
        "VCC ile toprak arasina" kalibi hic eslesmezdi."""
        self.assertEqual(_HEDEF_OLMAZ & set(AG_ADLARI), set())

    def test_qualifiers_target_existing_types(self):
        for kelime, tablo in NITELEYICILER.items():
            for kaynak, hedef in tablo.items():
                with self.subTest(f"{kelime}:{kaynak}"):
                    self.assertIn(kaynak, TURLER)
                    self.assertIn(hedef, TURLER)


@unittest.skipUnless(device_library_available(), "KiCad sembol kutuphanesi yok")
class KutuphaneTests(unittest.TestCase):
    """Tablodaki her kimlik GERCEK olmali - uydurma sembol adi yazilmaz."""

    def test_every_lib_id_resolves(self):
        for tur, bilgi in TURLER.items():
            with self.subTest(tur):
                symbol = symlib.get_symbol(bilgi["lib_id"])
                self.assertTrue(symbol.pins, f"{bilgi['lib_id']} pinsiz")

    def test_declared_pins_exist(self):
        """`uclar` uydurulmaz: baglanti tam bu numaralarla kurulur."""
        for tur, bilgi in TURLER.items():
            with self.subTest(tur):
                symbol = symlib.get_symbol(bilgi["lib_id"])
                numaralar = {pin.number for pin in symbol.pins}
                for uc in bilgi["uclar"]:
                    self.assertIn(uc, numaralar)
                if not bilgi["uclar"]:
                    self.assertNotEqual(
                        len(numaralar), 2,
                        f"{tur} iki uclu ama tabloda uclari bos - baglanamaz")

    def test_polarity_names_match_the_library(self):
        """Kutupluluk NOTU kullanicinin karti nasil baglayacagini belirler.
        KiCad diyot pin sirasini degistirirse not sessizce yanlislasmasin."""
        kisaltma = {"katot (K)": "K", "anot (A)": "A"}
        for tur, bilgi in TURLER.items():
            adlar = bilgi.get("uc_adlari")
            if not adlar:
                continue
            symbol = symlib.get_symbol(bilgi["lib_id"])
            for uc, ad in zip(bilgi["uclar"], adlar):
                with self.subTest(f"{tur}/{uc}"):
                    pin = next(p for p in symbol.pins if p.number == uc)
                    beklenen = kisaltma.get(ad)
                    if beklenen is None:
                        # Polarize kondansatorde kutuphane pin ADI vermez
                        # (isaret govde cizimindedir); dogrulanacak bir sey
                        # yoksa bunu da sinariz - bir gun ad gelirse bu test
                        # duser ve tabloyu gozden geciririz.
                        self.assertEqual(pin.name, "")
                    else:
                        self.assertEqual(pin.name, beklenen)

    def test_every_footprint_resolves(self):
        for tur, bilgi in TURLER.items():
            for paket, footprint in bilgi["paketler"].items():
                with self.subTest(f"{tur}/{paket}"):
                    self.assertTrue(symlib.footprint_exists(footprint),
                                    f"{footprint} bulunamadi")


# --------------------------------------------------------------------------
# Hedef secimi
# --------------------------------------------------------------------------


class KokSematikTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-komut-hedef-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_a_single_project_is_found(self):
        (self.tmp / "kart.kicad_pro").write_text("{}", encoding="utf-8")
        (self.tmp / "kart.kicad_sch").write_text("(kicad_sch)", encoding="utf-8")
        self.assertEqual(kok_sematik(self.tmp).name, "kart.kicad_sch")

    def test_two_projects_are_refused_rather_than_guessed(self):
        (self.tmp / "a.kicad_sch").write_text("(kicad_sch)", encoding="utf-8")
        (self.tmp / "b.kicad_sch").write_text("(kicad_sch)", encoding="utf-8")
        with self.assertRaises(KomutError):
            kok_sematik(self.tmp)

    def test_an_empty_folder_says_what_to_do(self):
        with self.assertRaises(KomutError) as ctx:
            kok_sematik(self.tmp)
        self.assertIn("--sch", str(ctx.exception))

    def test_a_wrong_file_type_is_refused(self):
        yol = self.tmp / "kart.kicad_pcb"
        yol.write_text("(kicad_pcb)", encoding="utf-8")
        with self.assertRaises(KomutError):
            kok_sematik(yol)


# --------------------------------------------------------------------------
# Uctan uca
# --------------------------------------------------------------------------


@unittest.skipUnless(kicad_cli_available() and device_library_available(),
                     "KiCad kurulu degil")
class UctanUcaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-komut-e2e-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = self.tmp / "proje"
        shutil.copytree(PROJECT_DIR, self.project)
        (self.project / LOCK_NAME).unlink(missing_ok=True)
        self.sch = self.project / "pic_programmer.kicad_sch"

    def _refs(self) -> set[str]:
        return {s.ref for s in read_schematic(self.sch).real_symbols}

    def test_a_sentence_becomes_ten_capacitors_on_disk(self):
        once = self._refs()
        yorum = anla("su anki modelimize 10 adet kapasitör koy")
        sonuclar = uygula(yorum, self.sch, apply=True)
        self.assertEqual(len(sonuclar), 1)
        self.assertTrue(sonuclar[0].applied, sonuclar[0].plan.describe())
        self.assertTrue(sonuclar[0].diff.ok, "netlist kalkani reddetti")
        self.assertEqual(len(self._refs() - once), 10)

    def test_dry_run_touches_nothing(self):
        once = self.sch.read_text(encoding="utf-8")
        uygula(anla("10 adet kapasitör ekle"), self.sch)
        self.assertEqual(self.sch.read_text(encoding="utf-8"), once)

    def test_two_actions_number_on_top_of_each_other(self):
        """Ikinci eylem, birincisinin YAZILMIS halini okumali - yoksa iki
        plan da ayni referanslari verir ve dosyada cakisma olur."""
        yorum = anla("2 adet 100nF kondansatör ve 2 adet 10k direnç ekle")
        sonuclar = uygula(yorum, self.sch, apply=True)
        self.assertEqual(len(sonuclar), 2)
        self.assertTrue(all(s.applied for s in sonuclar))
        refs = self._refs()
        self.assertEqual(len(refs), len(set(refs)))

    def test_an_unparsed_command_never_reaches_the_disk(self):
        with self.assertRaises(KomutError):
            uygula(anla("bir transistör ekle"), self.sch, apply=True)

    def _net_of(self) -> dict:
        return connectivity_of(self.sch).net_of

    def test_a_sentence_becomes_capacitors_that_are_really_on_the_net(self):
        """Isin olcusu sematikteki etiket degil, KiCad'in cikardigi
        NETLIST'tir: yeni pinler gercekten VCC ve GND agina girdi mi."""
        once = self._refs()
        yorum = anla("6 adet 100nF kondansatör ekle ve hepsini VCC ile GND "
                     "arasına bağla")
        sonuclar = uygula(yorum, self.sch, apply=True)
        self.assertTrue(sonuclar[0].applied, sonuclar[0].plan.describe())
        self.assertTrue(sonuclar[0].diff.ok, "netlist kalkani reddetti")

        yeni = self._refs() - once
        self.assertEqual(len(yeni), 6)
        net_of = self._net_of()
        for ref in yeni:
            with self.subTest(ref):
                self.assertEqual(net_of[(ref, "1")].lstrip("/"), "VCC")
                self.assertEqual(net_of[(ref, "2")].lstrip("/"), "GND")

    def test_the_existing_circuit_keeps_its_nets(self):
        """Baglama, mevcut aglara pin EKLER; onlardan pin ALMAZ."""
        once = self._net_of()
        uygula(anla("3 kapasitör ekle ve hepsini VCC ile GND arasına bağla"),
               self.sch, apply=True)
        sonra = self._net_of()
        for pin, net in once.items():
            with self.subTest(str(pin)):
                self.assertEqual(sonra.get(pin), net)

    def test_a_lowercase_net_name_is_corrected_from_the_schematic(self):
        """"vcc" diye yazan kullanici "VCC" agina baglanmis olmaz; yazim
        sematige bakilarak duzeltilir."""
        yorum = anla("2 kapasitör ekle ve hepsini vcc ile gnd arasına bağla")
        self.assertEqual(yorum.eylemler[0].baglar, ["1=vcc", "2=GND"])
        uygula(yorum, self.sch)  # dry-run: cozumleme yeter
        self.assertEqual(yorum.eylemler[0].baglar, ["1=VCC", "2=GND"])

    def test_an_unknown_net_name_is_warned_about_not_silently_created(self):
        """Netlist kalkani bunu YAKALAMAZ - yeni ag olusturmak gecerli bir
        islemdir. Uyari tek koruma."""
        yorum = anla("2 kapasitör ekle ve hepsini VCCC ile GND arasına bağla")
        uygula(yorum, self.sch)
        self.assertTrue(any("VCCC" in n and "YOK" in n for n in yorum.notlar),
                        yorum.notlar)

    def test_the_schematic_knows_its_own_net_names(self):
        adlar = mevcut_aglar(read_schematic(self.sch))
        self.assertLessEqual({"VCC", "GND", "VPP"}, adlar)


if __name__ == "__main__":
    unittest.main()
