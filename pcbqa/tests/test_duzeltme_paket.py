"""Paket kapsami ve dengeli ornekleme (Kicad-7cb) - BIRIM testleri.

Parca sinirlari koddan bagimsiz, ureticinin veri sayfasindan yazildi:
Yageo RC_L V.10 (2018-12-12) Tablo 2: 0201 1/20 W 25 V +-200 ppm (125 C'de
sifir guc), 0402 1/16 W 50 V, 0603 1/10 W 75 V, 0805 1/8 W 150 V, 1206 1/4 W
200 V; Tablo 8: F +-(1% + 50 mohm), J +-(3% + 50 mohm). Siparis kodu ornegi
veri sayfasinin kendisinden: RC0402JR-07100KL.
"""

from __future__ import annotations

import random
import unittest
from collections import Counter

from pcbqa.devre.parca import mpn_deger_kodu, parca_bilgisi, rc_l_siparis_kodu
from pcbqa.duzeltme import orneklem as O
from pcbqa.duzeltme.adaylar import adaylari_uret
from pcbqa.duzeltme.bolucu import Bolucu, BolucuParametre, analitik, tasarim_kur
from pcbqa.duzeltme.degerlendir import neden_etiketleri, paket_uyumu
from pcbqa.duzeltme.hatalar import hata_degisiklikleri
from pcbqa.duzeltme.tasarim import MPN_ALANI, Degisiklik
from pcbqa.ml.dataset import Sample

B = Bolucu("R1", "R2", "VIN", "OUT", "GND")


def param(**ek) -> BolucuParametre:
    d = dict(kimlik="t", vin_nom=12.0, vin_tol=0.02, vout_hedef=3.0, pencere=0.1, yuk_nom_a=1e-5,
             yuk_tepe_a=2e-5, ortam_c=25.0, sicakliklar=(-40.0, 85.0), r_ust=30100.0, r_alt=10000.0,
             tolerans=0.01, paket_ust="0603", paket_alt="0603", aralik_mm=3.2, mpn=True)
    d.update(ek)
    return BolucuParametre(**d)


def pb(fp: str, deger: str = "10k 1%", **alan):
    return parca_bilgisi(tur="resistor", deger=deger, footprint=f"Resistor_SMD:R_{fp}", alanlar=alan)


class GercekParcaSinirlariTesti(unittest.TestCase):
    def test_veri_sayfasi_tablo_2(self):
        beklenen = {"0201_0603Metric": (0.05, 25, 200, 125), "0402_1005Metric": (0.0625, 50, 100, 155),
                    "0603_1608Metric": (0.1, 75, 100, 155), "0805_2012Metric": (0.125, 150, 100, 155),
                    "1206_3216Metric": (0.25, 200, 100, 155)}
        for fp, (w, v, ppm, sifir) in beklenen.items():
            p = pb(fp)
            self.assertEqual(p.sinir("guc").onerilen_max, w, fp)
            self.assertEqual(p.sinir("gerilim").onerilen_max, v, fp)
            self.assertEqual(p.sicaklik_katsayisi.deger["ppm_c"], ppm, fp)
            self.assertEqual(p.termal["sifir_guc_ortam_c"].deger, sifir, fp)

    def test_omur_sapmasi_tolerans_sinifina_bagli(self):
        self.assertEqual(pb("0603_1608Metric", "10k 1%").yaslanma.deger["sapma_yuzde"], 1.0)
        self.assertEqual(pb("0603_1608Metric", "10k 5%").yaslanma.deger["sapma_yuzde"], 3.0)
        self.assertEqual(pb("0603_1608Metric", "10k 1%").yaslanma.deger["ek_ohm"], 0.05)

    def test_siparis_kodu_ve_katalog(self):
        self.assertEqual(rc_l_siparis_kodu("0402", 0.05, 100e3), "RC0402JR-07100KL")   # veri sayfasi ornegi
        self.assertEqual(rc_l_siparis_kodu("0603", 0.01, 28.7e3), "RC0603FR-0728K7L")
        self.assertEqual(rc_l_siparis_kodu("2512", 0.01, 4990), "RC2512FK-074K99L")    # 2512 kabartmali
        self.assertIsNone(rc_l_siparis_kodu("0603", 0.05, 28.7e3))                   # %5 E96 yok
        self.assertIsNone(rc_l_siparis_kodu("0603", 0.02, 10e3))                     # %2 seride yok
        self.assertEqual(mpn_deger_kodu("97R6"), 97.6)
        self.assertEqual(mpn_deger_kodu("9K76"), 9760.0)
        self.assertEqual(mpn_deger_kodu("1M"), 1e6)
        self.assertIn("katalog", pb("0603_1608Metric", "2M 0.5%").katalog_disi)       # %0.5 en fazla 1 Mohm
        self.assertEqual(pb("0603_1608Metric", "1M 0.5%").katalog_disi, "")

    def test_mpn_paketi_footprintten_degil_mpnden(self):
        p = pb("0603_1608Metric", "28.7k", MPN="RC0402FR-0728K7L")
        self.assertEqual(p.mpn_cozumu["paket"], "0402")
        self.assertEqual(p.sinir("guc").onerilen_max, 0.0625)
        self.assertEqual(p.dogrulama, "parcaya-ozel")
        self.assertEqual(p.tolerans.deger, 0.01)                                     # MPN tolerans kodundan
        genel = pb("0603_1608Metric", "28.7k 1%")
        self.assertEqual(genel.dogrulama, "paket-tipik")


class PaketEtiketiTesti(unittest.TestCase):
    """'Paket kucuk' tek basina hata DEGIL: guc, gerilim, mekanik, pad/footprint ayri."""

    def test_kucuk_paket_gecerli_olabilir(self):
        a = analitik(tasarim_kur(param(paket_ust="0201", paket_alt="0201", pencere=0.15), kart=False).graf(), B)
        self.assertTrue(a.gecer, (a.guc_orani, a.gerilim_orani, a.marj_alt, a.marj_ust))
        self.assertLess(a.guc_orani, 0.1)
        # Paketin GUC DISI etkisi: 0201'in TCR'si +-200 ppm (0603: +-100) -> ayni
        # tasarimda en kotu durum marji daha dar.
        m0603 = analitik(tasarim_kur(param(pencere=0.15), kart=False).graf(), B)
        self.assertLess(a.marj_alt, m0603.marj_alt)

    def test_buyuk_paket_de_yetersiz_kalabilir(self):
        # 1206 (0.25 W) uzerinde 12 V / 300 ohm -> ~0.33 W
        a = analitik(tasarim_kur(param(r_ust=226.0, r_alt=75.0, paket_ust="1206", paket_alt="1206"),
                                 kart=False).graf(), B)
        self.assertGreater(a.guc_orani, 1.0)
        self.assertFalse(a.gecer)

    def test_gerilim_siniri_gucten_ayri_neden(self):
        # 48 V, 0402 (50 V azami calisma gerilimi): guc dusuk ama gerilim sinirda/ustunde
        a = analitik(tasarim_kur(param(vin_nom=48.0, vin_tol=0.05, vout_hedef=1.0, r_ust=4.75e6, r_alt=1e5,
                                       yuk_nom_a=0.0, yuk_tepe_a=0.0, paket_ust="0402", paket_alt="0402"),
                                 kart=False).graf(), B)
        self.assertLess(a.guc_orani, 0.1)
        self.assertEqual(a.v_ust_siniri, 50.0)
        self.assertGreater(a.gerilim_orani, 0.9)

    def test_mpn_paketi_uyumsuzlugu_ve_duzeltmesi(self):
        t = tasarim_kur(param(), kart=False)
        degs, _ = hata_degisiklikleri(t, "R1", "R2", "mpn-paket", random.Random(0))
        self.assertEqual([d.alan for d in degs], ["mpn"])
        tv = t.uygula(degs)
        durum, sorun = paket_uyumu(tv.graf(), {"R1", "R2"})
        self.assertEqual(durum, "kaldi")
        self.assertIn("!= footprint 0603", sorun[0])
        esle = next(a for a in adaylari_uret(tv, B) if a.operator == "mpn-paket-esle")
        self.assertEqual(paket_uyumu(tv.uygula(esle.degisiklikler).graf(), {"R1", "R2"})[0], "gecti")

    def test_mpn_footprint_degisiminde_esitlenir(self):
        t = tasarim_kur(param(), kart=False)
        t2 = t.uygula([Degisiklik("R1", "footprint", "x", "Resistor_SMD:R_1206_3216Metric"),
                       Degisiklik("R1", "deger", "30.1k", "28.7k")])
        self.assertEqual(t2.netlist.components["R1"].fields[MPN_ALANI], "RC1206FR-0728K7L")
        t3 = t.uygula([Degisiklik("R1", "tolerans", "1%", "5%")])           # 30.1k %5'te yok
        self.assertNotIn(MPN_ALANI, t3.netlist.components["R1"].fields)
        self.assertEqual(paket_uyumu(t3.graf(), {"R1", "R2"})[0], "kaldi")   # katalog disi parca

    def test_eksik_veri_belirsiz_isaretlenir(self):
        # MPN yok -> pad/footprint nedeni belirsiz (yok sayilmaz)
        t = tasarim_kur(param(mpn=False), kart=False)
        self.assertIsNone(paket_uyumu(t.graf(), {"R1", "R2"}))
        n = neden_etiketleri({"kontroller": {"gereksinim": "kaldi", "direnc-gucu": "gecti",
                                             "direnc-gerilimi": "denetlenemedi"}})
        self.assertEqual(n, {"gereksinim": "var", "guc": "yok", "gerilim": "belirsiz", "mekanik": "belirsiz",
                             "pad-footprint": "belirsiz"})
        # Tabloda olmayan paket -> anma gucu yok -> el hesabi yapilamaz (uydurulmaz)
        t2 = tasarim_kur(param(mpn=False), kart=False)
        t2.netlist.components["R1"].footprint = "Resistor_SMD:R_0505_1313Metric"
        a = analitik(t2.graf(), B)
        self.assertFalse(a.hesaplanabilir)
        self.assertTrue(any("anma gucu" in e for e in a.eksikler))


class OrneklemPolitikasiTesti(unittest.TestCase):
    def test_bantlar_sinirda(self):
        self.assertEqual([O.bant(x) for x in (0.0, 0.8999, 0.9, 1.0, 1.1, 1.1001, float("inf"), None)],
                         ["alt", "alt", "yakin", "yakin", "yakin", "ust", "bilinmiyor", "bilinmiyor"])

    def test_ulasilabilir_bant_fizikten(self):
        # 0402 -> 0201 en fazla 0.5 x 0.0625 / 0.05 = 0.625
        self.assertEqual(O.ulasilabilir_bantlar("0402", ("alt", "yakin", "ust")), ("alt",))
        self.assertEqual(O.ulasilabilir_bantlar("1206", ("alt", "yakin", "ust")), ("alt", "yakin", "ust"))

    def test_plan_kotaya_uyar_ve_tekrarlanabilir(self):
        pol = O.POLITIKALAR["dengeli"]
        p = O.plan(80, 7, pol)
        self.assertEqual(Counter(s.paket for s in p), {"0402": 20, "0603": 20, "0805": 20, "1206": 20})
        self.assertEqual(sum(s.kip == "asiri-boy" for s in p), 24)               # 0.3 x 20 x 4
        self.assertEqual([s.as_dict() for s in p], [s.as_dict() for s in O.plan(80, 7, pol)])
        ozel = O.Politika("dengeli", paket_hedefi=(("0402", 0.5), ("1206", 0.5)), asiri_boy_orani=0.0)
        self.assertEqual(Counter(s.paket for s in O.plan(10, 7, ozel)), {"0402": 5, "1206": 5})

    def test_dengeli_referans_plana_uyar_ve_ayni_tohum_ayni_sonuc(self):
        pol = O.POLITIKALAR["dengeli"]
        satir = O.PlanSatiri("1206", "guc-gudumlu", "yakin")
        p1, _t, _r, ek1 = O.referans_bul(random.Random(5), "x", pol, satir)
        p2, _t, _r, ek2 = O.referans_bul(random.Random(5), "x", pol, satir)
        self.assertEqual(p1, p2)
        self.assertEqual(ek1, ek2)
        self.assertEqual(p1.paket_ust, "1206")
        self.assertEqual(O.bant(ek1["hedef_guc_orani"]), "yakin")
        a = analitik(tasarim_kur(p1, kart=False).graf(), B)
        self.assertLessEqual(a.guc_orani, O.REF_GUC_ORANI)                       # referans temiz
        # asiri-boy: bir kucuk paket de yeterli
        p3, _t, _r, ek3 = O.referans_bul(random.Random(5), "y", pol, O.PlanSatiri("0805", "asiri-boy", "alt"))
        self.assertLessEqual(ek3["hedef_guc_orani"], O.REF_GUC_ORANI)


class BolmeVeCogaltmaTesti(unittest.TestCase):
    def test_cogaltma_yalnizca_egitimde_ve_grup_butun(self):
        from pcbqa.duzeltme.egitim import gelistirme_test_bolmesi
        from pcbqa.duzeltme.paket_deney import egitim_cogalt

        samples = [Sample([0.0], 1.0, f"g{i}", f"g{i}/v", {"ref_paket_ust": "0402" if i < 8 else "1206",
                                                           "durum": "gecerli"}) for i in range(10)]
        test_g = gelistirme_test_bolmesi([s.group for s in samples], 0.2, 1)
        egitim = [s for s in samples if s.group not in test_g]
        cog = egitim_cogalt(egitim, 1)
        say = Counter(s.extra["ref_paket_ust"] for s in cog)
        self.assertEqual(say["0402"], say["1206"]) if say["1206"] else None
        # kopyalar yeni grup adi tasir; hicbir test grubuyla cakismaz
        self.assertFalse({s.group.split("#")[0] for s in cog} & test_g)
        self.assertEqual(len(egitim), sum(1 for s in cog if "#" not in s.group))


if __name__ == "__main__":
    unittest.main()
