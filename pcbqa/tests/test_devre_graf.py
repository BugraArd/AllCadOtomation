"""Devre grafi ve parca bilgisi: neyi biliyoruz, nereden biliyoruz, neyi bilmiyoruz."""

import tempfile
import unittest
from pathlib import Path

from devre_ornek import KOSUL_12V, graf, ldo_devresi

from pcbqa.devre.bilgi import bilinen, eksik
from pcbqa.devre.kosullar import KosulHatasi, ag_anahtari, kosullari_ayristir
from pcbqa.devre.parca import (
    KutuphaneHatasi, Kutuphane, dielektrik_sicaklik, gerilim_metinden, guc_metinden,
    kutuphane_ayristir, paket_kodu, parca_bilgisi, tolerans_metinden,
)
from pcbqa.netlist import read_netlist


class MetinAyristirmaTests(unittest.TestCase):
    def test_tolerans_gerilim_guc(self):
        self.assertAlmostEqual(tolerans_metinden("4k7 1% 0603"), 0.01)
        self.assertEqual(gerilim_metinden("100nF 50V X7R"), 50.0)
        # "3V3" bir ray adidir, anma gerilimi DEGIL (ilk parca atlanir)
        self.assertIsNone(gerilim_metinden("3V3"))
        self.assertAlmostEqual(guc_metinden("10k 1/4W"), 0.25)
        self.assertAlmostEqual(guc_metinden("0R1 500mW"), 0.5)
        self.assertEqual(paket_kodu("Resistor_SMD:R_0603_1608Metric"), "0603")
        self.assertEqual(paket_kodu("Package_QFP:LQFP-32"), "")

    def test_dielektrik_kodu_tanimdir(self):
        x7r = dielektrik_sicaklik("X7R")
        self.assertEqual((x7r["min_c"], x7r["max_c"]), (-55.0, 125.0))
        self.assertEqual(x7r["degisim_min_yuzde"], -15.0)
        self.assertEqual(dielektrik_sicaklik("C0G")["ppm_c"], 30.0)
        self.assertIsNone(dielektrik_sicaklik("ABC"))


class ParcaBilgisiTests(unittest.TestCase):
    def test_0603_direnc_paket_tipik_guc(self):
        pb = parca_bilgisi(tur="resistor", deger="10k", footprint="Resistor_SMD:R_0603_1608Metric")
        self.assertEqual(pb.kategori, "direnc")
        self.assertAlmostEqual(pb.deger.deger, 10e3)
        self.assertAlmostEqual(pb.sinir("guc").onerilen_max, 0.1)
        self.assertEqual(pb.sinir("guc").guven, "paket-tipik")
        self.assertIn("tolerans", " ".join(pb.eksikler()))
        self.assertEqual(pb.spice.tur, "primitif")

    def test_kondansator_anma_gerilimi_metinden_ya_da_eksik(self):
        pb = parca_bilgisi(tur="capacitor", deger="100nF 50V X7R", footprint="C_0402")
        self.assertEqual(pb.sinir("gerilim").onerilen_max, 50.0)
        self.assertEqual(pb.sicaklik_katsayisi.guven, "turetilmis")
        pb2 = parca_bilgisi(tur="capacitor", deger="100nF", footprint="C_0402")
        self.assertIsNone(pb2.sinir("gerilim"))
        self.assertTrue(any("anma gerilimi" in e for e in pb2.eksikler()))

    def test_ams1117_kaydi_desenle(self):
        pb = parca_bilgisi(tur="ic", deger="AMS1117-3.3", libpart="AMS1117-3.3")
        self.assertEqual(pb.kategori, "ldo")
        self.assertEqual(pb.sinir("vin").mutlak_max, 15.0)
        self.assertEqual(pb.termal["paket"].deger, "sot223")
        self.assertEqual(pb.dogrulama, "dogrulanmamis")
        # Desenle eslesen kaydin MPN'i sematigin MPN'i SAYILMAZ
        self.assertFalse(pb.mpn.bilinen)
        self.assertTrue(pb.spice.ideal)

    def test_mpn_alani_tam_eslesme(self):
        pb = parca_bilgisi(tur="transistor", deger="Q", alanlar={"MPN": "AO3400A", "Manufacturer": "AOS"})
        self.assertEqual(pb.kutuphane_kaydi, "AO3400A")
        self.assertEqual(pb.mpn.guven, "beyan")
        self.assertEqual(pb.sinir("rds_on_vgs").onerilen_min, 2.5)

    def test_sentetik_mpn_gercek_sanilmaz(self):
        pb = parca_bilgisi(tur="ic", deger="X", alanlar={"MPN": "SENT-R-0603-10K", "MPN_Kaynak": "sentetik-test"})
        self.assertEqual(pb.mpn.guven, "sentetik")
        self.assertEqual(pb.kutuphane_kaydi, "")

    def test_78xx_cikis_addan_dusum_eksik(self):
        pb = parca_bilgisi(tur="ic", deger="7805")
        self.assertEqual(pb.kutuphane_kaydi, "78xx-serisi")
        s = pb.sinir("vout")
        self.assertEqual((s.onerilen_min, s.onerilen_max), (5.0, 5.0))
        self.assertIsNone(pb.spice)
        self.assertIn("dusum", pb.spice_eksik)

    def test_tvs_standoff_addan(self):
        pb = parca_bilgisi(tur="diode", deger="SMBJ5.0A")
        self.assertEqual(pb.kategori, "tvs")
        self.assertEqual(pb.sinir("vrwm").onerilen_max, 5.0)

    def test_kaynaksiz_kayit_reddedilir(self):
        with self.assertRaises(KutuphaneHatasi):
            kutuphane_ayristir({"version": 1, "parcalar": [{"anahtar": "x", "kategori": "ldo"}]})

    def test_bos_kutuphane_her_seyi_eksik_birakir(self):
        pb = parca_bilgisi(tur="ic", deger="BILINMEYEN", kutuphane=Kutuphane())
        self.assertEqual(pb.kategori, "genel")
        self.assertIsNone(pb.spice)


class BilgiTests(unittest.TestCase):
    def test_bilinen_none_alamaz_ve_veya(self):
        with self.assertRaises(ValueError):
            bilinen(None, "x")
        b = eksik("a").veya(eksik("b"))
        self.assertFalse(b.bilinen)
        self.assertEqual(b.eksik_neden, "a; b")
        self.assertEqual(eksik("a").veya(bilinen(1.0, "k")).deger, 1.0)


class KosullarTests(unittest.TestCase):
    def test_ayristirma_ve_hatalar(self):
        k = kosullari_ayristir(KOSUL_12V)
        self.assertEqual(k.ray("/VBUS").max, 12.6)
        self.assertTrue(k.kaynak_mi("/vbus"))
        self.assertEqual(k.yukler_on("/3V3")[0].akim_a, 0.3)
        self.assertEqual(k.pcb["bakir_oz"], 1.0)
        self.assertNotIn("bakir_oz", k.pcb_beyan)
        with self.assertRaises(KosulHatasi):
            kosullari_ayristir({"raylar": {"X": {"min": 1}}})
        with self.assertRaises(KosulHatasi):
            kosullari_ayristir({"pcb": {"bilinmeyen": 1}})
        self.assertEqual(ag_anahtari("/3v3"), "3V3")


class GrafTests(unittest.TestCase):
    def setUp(self):
        self.g = graf(ldo_devresi(), KOSUL_12V)

    def test_roller(self):
        g = self.g
        reg = g.bilesen("U1").rol("regulator")
        self.assertEqual(reg.aglar, {"giris": "VBUS", "cikis": "3V3"})
        self.assertTrue(g.bilesen("C1").rol("regulator-giris-kond"))
        self.assertTrue(g.bilesen("C2").rol("regulator-cikis-kond"))
        self.assertEqual(g.bilesen("C3").rol("dekuplaj").hedefler, ["U2.1"])
        self.assertEqual(g.bilesen("R1").rol("pull-up").aglar["sinyal"], "SDA")
        self.assertEqual(g.bilesen("R2").rol("led-seri-direnci").hedefler, ["D1"])
        self.assertEqual(g.bilesen("Q1").rol("anahtar").aglar["gate"], "GATE")
        self.assertEqual(g.bilesen("L1").rol("enduktif-yuk").hedefler, ["Q1"])
        self.assertTrue(g.bilesen("J1").rol("guc-girisi"))

    def test_gerilim_kaynak_sirasi(self):
        g = self.g
        self.assertEqual(g.gerilim("VBUS").guven, "beyan")
        self.assertEqual(g.gerilim("VBUS").deger, 12.0)
        self.assertEqual(g.gerilim("3V3").deger, 3.3)
        self.assertTrue(g.toprak_mi("GND"))
        self.assertFalse(g.gerilim("SDA").bilinen)

    def test_regulator_cikisi_adi_sessiz_aga_gerilim_verir(self):
        p = ldo_devresi()
        for x in p:
            x["pinler"] = [tuple("VOUT_ANA" if v == "3V3" else v for v in pin) for pin in x["pinler"]]
        g = graf(p, KOSUL_12V)
        v = g.gerilim("VOUT_ANA")
        self.assertAlmostEqual(v.deger, 3.3)
        self.assertIn("U1", v.kaynak)

    def test_pcb_karsiligi_ve_pin_adi(self):
        b = self.g.bilesen("U1")
        self.assertEqual(b.pinler["2"].ad, "VO")
        self.assertEqual(b.pinler["2"].padler[0].ag, "3V3")
        self.assertIsNotNone(b.pcb)
        self.assertIn("AMS1117", self.g.bilesen_cumlesi("U1"))

    def test_eksik_raporu_nedenli(self):
        rapor = self.g.eksik_raporu()
        self.assertIn("C1", rapor)
        self.assertTrue(any("anma gerilimi" in s for s in rapor["C1"]))
        self.assertTrue(any("SPICE" in s for s in rapor["U2"]))

    def test_kart_olmadan_pcb_eksik(self):
        g = graf(ldo_devresi(), KOSUL_12V, kart=False)
        self.assertTrue(any("PCB karsiligi yok" in s for s in g.bilesen("U1").eksikler()))

    def test_as_dict_serilestirilebilir(self):
        import json

        json.dumps(self.g.as_dict(), default=str)


class NetlistOkumaTests(unittest.TestCase):
    XML = """<?xml version="1.0"?>
<export version="E"><components>
<comp ref="U1"><value>AMS1117-3.3</value><footprint>P:SOT</footprint>
<datasheet>http://x</datasheet><fields><field name="MPN">AMS1117-3.3</field>
<field name="Tolerance">1%</field></fields><libsource lib="Regulator_Linear" part="AMS1117-3.3"/></comp>
</components><libparts><libpart lib="Regulator_Linear" part="AMS1117-3.3"><pins>
<pin num="1" name="GND" type="power_in"/><pin num="2" name="VO" type="power_out"/>
<pin num="3" name="VI" type="power_in"/></pins></libpart></libparts>
<nets><net code="1" name="/3V3" class="Default"><node ref="U1" pin="2" pinfunction="VO_2" pintype="power_out"/></net></nets>
</export>"""

    def test_alanlar_ve_libparts(self):
        with tempfile.TemporaryDirectory() as tmp:
            yol = Path(tmp) / "n.xml"
            yol.write_text(self.XML, encoding="utf-8")
            n = read_netlist(yol)
        c = n.components["U1"]
        self.assertEqual(c.fields["MPN"], "AMS1117-3.3")
        self.assertEqual(c.lib, "Regulator_Linear")
        self.assertEqual([p.name for p in n.lib_pins_of("U1")], ["GND", "VO", "VI"])


if __name__ == "__main__":
    unittest.main()
