"""Gercek deney secimi, okunur gerekce ve gercek deney envanteri (Kicad-d8k).

Kayitlar elle kurulur (TEST verisi; proje.deney kayit bicimiyle ayni
alanlar). Gercek araclarla uctan uca kosu test_duzeltme_proje.py'dedir.
"""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pcbqa.duzeltme import aciklama, envanter, secim
from pcbqa.duzeltme.gorunum import KaynakHatasi, deney_yukle

OZETLER = {"t.kicad_pro": "a" * 64, "t.kicad_sch": "b" * 64, "t.kicad_pcb": "c" * 64}
KOSULLAR = {"version": 1, "ortam_c": 25.0, "raylar": {"VIN": {"nom": 12.0, "min": 11.76, "max": 12.24}},
            "yukler": [{"ag": "OUT", "akim_a": 1e-05, "tepe_a": 2e-05}],
            "gereksinimler": [{"ag": "OUT", "min_v": 2.64, "max_v": 3.36}],
            "analiz": {"sicakliklar": [-40.0, 85.0]}}
ANALITIK = {"pencere_min": 2.64, "pencere_max": 3.36, "p_ust_siniri": 0.1, "p_alt_siniri": 0.1,
            "v_ust_max": 9.0, "v_alt_max": 3.0, "v_ust_siniri": 50.0, "v_alt_siniri": 50.0}
BOLUCU = {"ust": "R1", "alt": "R2", "giris": "/VIN", "toprak": "GND", "cikis": "/OUT"}
GECTI = {"geri-okuma": "gecti", "kicad-erc": "gecti", "kicad-drc": "gecti", "kicad-parite": "gecti",
         "elektrik-benzetim": "gecti", "elektrik-gereksinim": "gecti", "elektrik-direnc-gucu": "gecti"}


def _temel(**ek):
    k = {"tur": "gercek-temel", "kimlik": "temel", "temel": {"klasor": "yok/temel", "ad": "t", "ozetler": OZETLER},
         "aday": None, "kosullar": KOSULLAR, "kapsam_disi": ["yuk ideal akim yutucu"], "durum": "kaldi",
         "kontroller": {**GECTI, "elektrik-gereksinim": "kaldi"},
         "kicad": {"ihlaller": [], "sayilar": {"erc": 0, "drc": 0, "parite": 0}},
         "elektrik": {"ihlaller": ["gereksinim-gerilim||error|alt", "montaj-deligi||warning"], "bolucu": BOLUCU,
                      "olcumler": {"vout_min": 1.8125, "vout_max": 2.242866}, "analitik": ANALITIK},
         "bilesenler": {"R1": {"paket": "0603", "tolerans": "1%"}, "R2": {"paket": "0603", "tolerans": "1%"}},
         "egitim": {"aktarilabilir": True, "etiket": 0}}
    k.update(ek)
    return k


def _aday(kimlik, durum, maliyet, degs=(("R1", "deger", "47k", "28.7k"),), ureteci=None, ihlal=(), kicad=(),
          kontroller=None, **ek):
    toplam = maliyet
    k = _temel(tur="gercek-aday", kimlik=kimlik, durum=durum,
               aday={"kimlik": ureteci or kimlik.split("-", 2)[-1], "degisiklikler": [
                   {"ref": r, "alan": a, "eski": e, "yeni": y} for r, a, e, y in degs]},
               kontroller=kontroller or ({**GECTI} if durum == "gecti" else {**GECTI, "elektrik-gereksinim": durum}),
               egitim={"aktarilabilir": durum in ("gecti", "kaldi"), "etiket": {"gecti": 1, "kaldi": 0}.get(durum)})
    k["elektrik"] = {**k["elektrik"], "ihlaller": ["montaj-deligi||warning", *ihlal],
                     "olcumler": {"vout_min": 2.77, "vout_max": 3.29} if durum == "gecti" else
                     {"vout_min": 1.8125, "vout_max": 2.242866}}
    k["kicad"] = {"ihlaller": list(kicad), "sayilar": {"erc": 0, "drc": len(kicad), "parite": 0}}
    if maliyet is not secim:          # 'secim' nesnesi = maliyet alani HIC yok
        k["maliyet"] = {"toplam": toplam, "alanlar": {"parca": 1}, "agirliklar": {"parca": 1.0}}
    k.update(ek)
    return k


class SecimTesti(unittest.TestCase):
    def test_ilk_gecen_daha_pahaliysa_en_ucuz_secilir_ve_ilk_gecen_ayri_kalir(self):
        k = [_temel(), _aday("aday-01-pahali", "gecti", 4.75), _aday("aday-02-kalan", "kaldi", 1),
             _aday("aday-03-ucuz", "gecti", 1)]
        s = secim.sec(k, aday_sayisi=3)
        self.assertEqual(s["ilk_gecen"], "aday-01-pahali")
        self.assertEqual(s["secilen"], "aday-03-ucuz")
        self.assertEqual(s["secilen_maliyet"], 1.0)
        self.assertTrue(s["kuresel_en_dusuk"])
        self.assertEqual(s["kapsam"], "tum-adaylar")
        self.assertIn("aday-01-pahali", " ".join(aciklama.secim_metni(s, k)))   # eski kural raporlanir

    def test_secim_gecerlilik_etiketlerini_degistirmez(self):
        k = [_temel(), _aday("aday-01-a", "gecti", 2), _aday("aday-02-b", "kaldi", 1)]
        once = copy.deepcopy(k)
        s = secim.sec(k, aday_sayisi=2)
        self.assertEqual(k, once)
        self.assertEqual(s["tercih"]["aday-02-b"]["secime_uygun"], False)

    def test_esit_maliyet_raporlanir_kararli_kimlikle_cozulur_daha_kotu_denmez(self):
        k = [_temel(), _aday("aday-01-x", "gecti", 1, ureteci="ust-yeniden-E96"),
             _aday("aday-02-y", "gecti", 1, ureteci="alt-yeniden-E96", degs=(("R2", "deger", "10k", "16.5k"),)),
             _aday("aday-03-z", "gecti", 2)]
        s = secim.sec(k, aday_sayisi=3)
        self.assertEqual(s["secilen"], "aday-02-y")            # 'alt-...' < 'ust-...' (siralama on eki degil)
        self.assertEqual(s["esit_maliyetliler"], ["aday-01-x"])
        self.assertEqual(s["esitlik_cozumu"], "kararli-kimlik")
        self.assertIn("daha kotu degil", s["tercih"]["aday-01-x"]["neden"])
        metin = " ".join(aciklama.secim_metni(s, k))
        self.assertIn("daha kotu degildir", metin)
        self.assertNotIn("daha kotu oldugu", metin)
        # Siralama on ekini (aday-NN) degistirmek secimi degistirmez
        k2 = [k[0], {**k[1], "kimlik": "aday-09-x"}, {**k[2], "kimlik": "aday-10-y"}, k[3]]
        self.assertEqual(secim.sec(k2, aday_sayisi=3)["secilen"], "aday-10-y")

    def test_esit_maliyette_belgelenmis_ek_tercih_yeni_ihlal(self):
        cak = {"grup": "violations", "tur": "silk_overlap", "siddet": "warning", "aciklama": "Silk",
               "ogeler": ["Ayak izi R1"]}
        k = [_temel(), _aday("aday-01-a", "gecti", 1, ureteci="a", kicad=[cak]), _aday("aday-02-b", "gecti", 1,
                                                                                    ureteci="b")]
        s = secim.sec(k, aday_sayisi=2)
        self.assertEqual(s["secilen"], "aday-02-b")             # kimlik sirasi 'a' once olurdu; ek tercih kazanir
        self.assertEqual(s["tercih"]["aday-01-a"]["yeni_ihlal"], 1)
        self.assertEqual(s["tercih"]["aday-02-b"]["yeni_ihlal"], 0)   # temelde de olan uyari yeni sayilmaz
        self.assertEqual(s["esitlik_cozumu"], "ek-tercih-yeni-ihlal")

    def test_gecerli_aday_yoksa_secilen_bos_ve_nedenler_gosterilir(self):
        k = [_temel(), _aday("aday-01-a", "kaldi", 1), _aday("aday-02-b", "arac-hatasi", 1,
                                                            kontroller={**GECTI, "kicad-drc": "arac-hatasi"})]
        s = secim.sec(k, aday_sayisi=2)
        self.assertIsNone(s["secilen"])
        self.assertTrue(s["gecerli_yok"])
        metin = " ".join(aciklama.secim_metni(s, k))
        self.assertIn("YOK", metin)
        self.assertIn("elektrik-gereksinim 1", metin)
        self.assertIn("kicad-drc 1", metin)

    def test_eksik_ya_da_gecersiz_maliyet_sifir_sayilmaz(self):
        for kotu in (secim, None, float("nan"), -1.0, "1", True):
            with self.subTest(maliyet=kotu):
                k = [_temel(), _aday("aday-01-eksik", "gecti", kotu), _aday("aday-02-pahali", "gecti", 3)]
                s = secim.sec(k, aday_sayisi=2)
                self.assertEqual(s["secilen"], "aday-02-pahali")
                self.assertEqual(s["maliyeti_eksik"], ["aday-01-eksik"])
                self.assertFalse(s["kuresel_en_dusuk"])
                self.assertIsNone(s["tercih"]["aday-01-eksik"]["maliyet"])
        k = [_temel(), _aday("aday-01-eksik", "gecti", None)]
        s = secim.sec(k, aday_sayisi=1)
        self.assertIsNone(s["secilen"])
        self.assertIn("maliyeti eksik", " ".join(aciklama.secim_metni(s, k)))

    def test_erken_durdurmada_kuresel_iddia_yok(self):
        k = [_temel(), _aday("aday-01-a", "kaldi", 1), _aday("aday-02-b", "gecti", 4)]
        s = secim.sec(k, aday_sayisi=17)
        self.assertEqual(s["kapsam"], "kismi")
        self.assertEqual(s["secilen"], "aday-02-b")
        self.assertFalse(s["kuresel_en_dusuk"])
        self.assertIn("DEGERLENDIRILENLER arasindadir", " ".join(aciklama.secim_metni(s, k)))
        self.assertEqual(secim.sec(k)["kapsam"], "bilinmiyor")
        self.assertFalse(secim.sec(k)["kuresel_en_dusuk"])


class AciklamaTesti(unittest.TestCase):
    def test_gereksinim_metni_olcum_birim_ve_sinir_icerir(self):
        a = aciklama.kontrol_aciklamalari(_temel())
        self.assertEqual([x["kod"] for x in a], ["elektrik-gereksinim"])
        self.assertEqual(a[0]["durum"], "kaldi")
        self.assertEqual(a[0]["metin"], "OUT cikis gerilimi benzetim senaryolari ve capraz koselerde 1,81-2,24 V "
                                        "araliginda. Izin verilen aralik 2,64-3,36 V oldugu icin gerilim "
                                        "gereksinimi karsilanmiyor (alt sinirin altina iniyor).")

    def test_sinira_yakin_olcum_sinirla_ayni_yazilmaz(self):
        k = _temel()
        k["elektrik"]["olcumler"] = {"vout_min": 2.6395, "vout_max": 3.2}
        self.assertIn("2,639-3,2", aciklama.kontrol_aciklamalari(k)[0]["metin"])

    def test_olcum_yoksa_sayi_uydurulmaz(self):
        k = _temel()
        k["elektrik"]["olcumler"] = {}
        m = aciklama.kontrol_aciklamalari(k)[0]["metin"]
        self.assertIn("kayitta yok", m)
        self.assertNotRegex(m, r"\d,\d")

    def test_courtyard_drc_raporun_referanslarini_kullanir(self):
        v = {"grup": "violations", "tur": "courtyards_overlap", "siddet": "error", "aciklama": "Courtyards overlap",
             "ogeler": ["Ayak �zi R1", "Ayak �zi R2"]}
        k = _aday("aday-09-paket", "kaldi", 2.75, kicad=[v],
                  kontroller={**GECTI, "kicad-drc": "kaldi", "elektrik-pcb-cakisma": "kaldi"},
                  ihlal=("cakisma|R1,R2|warning",))
        a = {x["kod"]: x["metin"] for x in aciklama.kontrol_aciklamalari(k)}
        self.assertTrue(a["kicad-drc"].startswith("R1 ve R2: courtyard alanlari cakisiyor"))
        self.assertIn("courtyards_overlap", a["kicad-drc"])      # teknik kod korunur
        self.assertIn("R1 ve R2 courtyard", a["elektrik-pcb-cakisma"])
        self.assertEqual(k["kontroller"]["kicad-drc"], "kaldi")  # ham kod ayri alanda, degismedi

    def test_bilinmeyen_kod_ve_tur_teknik_kodu_koruyan_yedek(self):
        k = _aday("aday-01-a", "kaldi", 1, kontroller={**GECTI, "yeni-kontrol-x": "kaldi", "kicad-erc": "kaldi"},
                  kicad=[{"grup": "erc", "tur": "garip_tur", "siddet": "error", "aciklama": "Odd", "ogeler": []}])
        a = {x["kod"]: x["metin"] for x in aciklama.kontrol_aciklamalari(k)}
        self.assertIn("'yeni-kontrol-x'", a["yeni-kontrol-x"])
        self.assertIn("teknik kod korunmustur", a["yeni-kontrol-x"])
        self.assertIn("'garip_tur'", a["kicad-erc"])
        self.assertIn('"Odd"', a["kicad-erc"])

    def test_guc_asimi_olculen_ve_sinirla(self):
        k = _aday("aday-01-a", "kaldi", 1, kontroller={**GECTI, "elektrik-direnc-gucu": "kaldi"})
        k["elektrik"]["olcumler"] = {"p_ust_w": 0.125, "p_ust_oran": 1.25, "p_alt_w": 0.01, "p_alt_oran": 0.1}
        m = aciklama.kontrol_aciklamalari(k)[0]["metin"]
        self.assertIn("R1 en kotu kosede 0,125 W", m)
        self.assertIn("0,1 W", m)
        self.assertNotIn("R2", m)

    def test_rapor_cli_ve_gorunum_ayni_metni_kullanir(self):
        k = [_temel(), _aday("aday-01-a", "gecti", 1)]
        from pcbqa.duzeltme import proje

        r = {"temel": "x", "adaylar": 1}
        self.assertEqual(proje.rapor_metni(k, r), aciklama.rapor_metni(k, r))


def _yaz(klasor: Path, kayitlar, ozet=None, ek_satirlar=()):
    klasor.mkdir(parents=True, exist_ok=True)
    satirlar = [json.dumps(k) for k in kayitlar] + list(ek_satirlar)
    (klasor / "deney.jsonl").write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    if ozet is not None:
        (klasor / "ozet.json").write_text(json.dumps(ozet), encoding="utf-8")
    return klasor


class EnvanterTesti(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-env-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.kayitlar = [_temel(), _aday("aday-01-a", "gecti", 1), _aday("aday-02-b", "kaldi", 2,
                                                                       degs=(("R2", "deger", "10k", "16k"),)),
                         _aday("aday-03-c", "gecti", 4.75, degs=(("R1", "footprint", "R_0603", "R_0402"),))]

    def test_referans_ve_aday_ayri_sayilir(self):
        d = _yaz(self.tmp / "k1", self.kayitlar, {"adaylar": 3})
        env = envanter.gercek_envanter([d])
        n = env["sayilar"]
        self.assertEqual((n["temel_tasarim"], n["deney_kosusu"], n["referans_kaydi"], n["aday_kaydi"],
                          n["aday_benzersiz"]), (1, 1, 1, 3, 3))
        self.assertEqual(env["kaynak_turu"], envanter.KAYNAK_GERCEK)
        self.assertEqual(env["dagilim"]["durum"], {"gecti": 2, "kaldi": 1})
        self.assertEqual(env["dagilim"]["maliyet_gecen"], {"1": 1, "4.75": 1})
        self.assertEqual(env["kosu_secimleri"][0]["secilen"], "aday-01-a")
        self.assertIn("yuk ideal akim yutucu", env["dagilim"]["kapsam_disi"])

    def test_tekrarlanan_kosu_tasarimi_sisirmez_farkli_adaylar_tek_kayda_inmez(self):
        d1 = _yaz(self.tmp / "k1", self.kayitlar, {"adaylar": 3})
        # Ayni deney, baska klasor, farkli siralama on ekleri (model sirasi): ayni tasarim, ayni adaylar
        yeniden = [self.kayitlar[0]] + [{**k, "kimlik": f"aday-{9 - i:02d}-{k['aday']['kimlik']}"}
                                        for i, k in enumerate(self.kayitlar[1:])]
        d2 = _yaz(self.tmp / "k2", yeniden, {"adaylar": 3})
        env = envanter.gercek_envanter([d1, d2])
        n = env["sayilar"]
        self.assertEqual(n["temel_tasarim"], 1)
        self.assertEqual(n["calisma_kosulu"], 1)
        self.assertEqual(n["deney_kosusu"], 2)
        self.assertEqual(n["tekrar_kosu"], 1)
        self.assertEqual(n["referans_kaydi"], 2)
        self.assertEqual(n["referans_benzersiz"], 1)
        self.assertEqual(n["aday_kaydi"], 6)
        self.assertEqual(n["aday_benzersiz"], 3)
        self.assertEqual(env["dagilim"]["durum"], {"gecti": 2, "kaldi": 1})     # bir kez sayildi
        # Ayni ureteci kimligi ama farkli degisiklik: AYRI aday
        farkli = _aday("aday-04-a", "gecti", 1, degs=(("R1", "deger", "47k", "30k"),), ureteci="a")
        d3 = _yaz(self.tmp / "k3", self.kayitlar + [farkli], {"adaylar": 4})
        self.assertEqual(envanter.gercek_envanter([d3])["sayilar"]["aday_benzersiz"], 4)

    def test_celiskili_tekrar_raporlanir(self):
        d1 = _yaz(self.tmp / "k1", self.kayitlar, {"adaylar": 3})
        bozulmus = copy.deepcopy(self.kayitlar)
        bozulmus[1]["durum"] = "kaldi"
        d2 = _yaz(self.tmp / "k2", bozulmus, {"adaylar": 3})
        env = envanter.gercek_envanter([d1, d2])
        self.assertEqual([c["aday"] for c in env["celiskili_tekrar"]], ["aday-01-a"])

    def test_bozuk_kayitlar_sayilmaz_ayri_listelenir_eksik_alan_ayri(self):
        eksik_maliyet = _aday("aday-04-d", "gecti", secim, degs=(("R2", "deger", "10k", "12k"),))
        alansiz = {"tur": "gercek-aday", "kimlik": "aday-05-e", "durum": "gecti"}       # temel.ozetler yok
        d = _yaz(self.tmp / "k1", self.kayitlar + [eksik_maliyet, alansiz], {"adaylar": 5},
                 ek_satirlar=["{bozuk json", "[1, 2]"])
        env = envanter.gercek_envanter([d])
        self.assertEqual(env["sayilar"]["bozuk_kayit"], 3)
        self.assertEqual(env["sayilar"]["aday_kaydi"], 4)
        nedenler = " ".join(b["neden"] for b in env["kaynaklar"][0]["bozuk_ayrinti"])
        self.assertIn("JSON okunamadi", nedenler)
        self.assertIn("temel.ozetler yok", nedenler)
        self.assertEqual(env["eksik_alanlar"].get("gercek-aday: maliyet"), 1)
        self.assertEqual(env["dagilim"]["maliyet"].get("eksik"), 1)

    def test_kaynak_turu_bellek_ve_gercek_ayri(self):
        d = _yaz(self.tmp / "gercek", self.kayitlar, {"adaylar": 3})
        b = self.tmp / "bellek"
        b.mkdir()
        (b / "kayitlar.jsonl").write_text(json.dumps({"tur": "referans", "kimlik": "r"}) + "\n", encoding="utf-8")
        self.assertEqual(envanter.kaynak_turu(d)[0], envanter.KAYNAK_GERCEK)
        self.assertEqual(envanter.kaynak_turu(d / "deney.jsonl")[0], envanter.KAYNAK_GERCEK)
        self.assertEqual(envanter.kaynak_turu(b)[0], envanter.KAYNAK_BELLEK)
        with self.assertRaises(envanter.KaynakHatasi):
            envanter.gercek_envanter([b])
        with self.assertRaises(envanter.KaynakHatasi):
            envanter.kaynak_turu(self.tmp / "yok")
        metin, _ = envanter_metni_gercek(d)
        self.assertIn("Kaynak turu: gercek-proje-deneyi", metin)
        self.assertIn(str(d / "deney.jsonl"), metin)

    def test_gorunum_gercek_deney_disini_reddeder_ve_yukler(self):
        d = _yaz(self.tmp / "gercek", self.kayitlar, {"adaylar": 3, "temel": "t"})
        g = deney_yukle(d)
        self.assertEqual(g.secim["secilen"], "aday-01-a")
        self.assertEqual([r["tercih"] for r in g.satirlar], ["temel", "SECILDI", "-", "daha pahali"])
        b = self.tmp / "bellek"
        b.mkdir()
        (b / "kayitlar.jsonl").write_text(json.dumps({"tur": "aday"}) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(KaynakHatasi, "gercek proje deneyi DEGIL"):
            deney_yukle(b)
        bos = _yaz(self.tmp / "temelsiz", self.kayitlar[1:])
        with self.assertRaisesRegex(KaynakHatasi, "temel kaydi yok"):
            deney_yukle(bos)


def envanter_metni_gercek(d):
    return envanter.envanter_metni([d])


if __name__ == "__main__":
    unittest.main()
