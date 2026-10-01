"""Seviye 3: SPICE netlisti, senaryolar, ngspice calistirma ve karsilastirma."""

import copy
import tempfile
import unittest
from pathlib import Path

from devre_ornek import FP_R, KOSUL_12V, graf, ldo_devresi, parca

from pcbqa.dogrulama.seviye3 import kontrol_blogu, senaryolar_uret, seviye3
from pcbqa.spice import arka_uc_bul, devre_kur, wrdata_oku


def bolucu(ust="10k 1%", alt="3.3k 1%"):
    return [
        parca("J1", "IN", "Connector_Generic", "Conn_01x02", "PinHeader_1x02",
              [("1", "Pin_1", "passive", "VIN12", 0, 0), ("2", "Pin_2", "passive", "GND", 0, 3)]),
        parca("R1", ust, "Device", "R", FP_R,
              [("1", "", "passive", "VIN12", 5, 0), ("2", "", "passive", "ORTA", 7, 0)]),
        parca("R2", alt, "Device", "R", FP_R,
              [("1", "", "passive", "ORTA", 9, 0), ("2", "", "passive", "GND", 11, 0)]),
    ]


BOLUCU_KOSUL = {"raylar": {"VIN12": {"nom": 12, "min": 11, "max": 13}}, "kaynaklar": ["VIN12"],
                "gereksinimler": [{"ag": "ORTA", "min_v": 2.9, "max_v": 3.1}],
                "analiz": {"monte_carlo": 5, "sicakliklar": [85]}}


class NetlistTests(unittest.TestCase):
    def test_ldo_devresi_netlisti(self):
        d = devre_kur(graf(ldo_devresi(), KOSUL_12V))
        metin = d.metin(["op"])
        self.assertIn("V_VBUS N_VBUS 0 DC 12", metin)
        self.assertIn("B_U1_out", metin)
        self.assertIn("I_yuk0 N_3V3 0 DC 0.3", metin)
        self.assertIn("R_R1 N_3V3 N_SDA 4700", metin)
        # MCU ve MOSFET icin model yok: atlandi ve KAYITLI
        atlanan = dict(d.atlananlar)
        self.assertIn("U2", atlanan)
        self.assertIn("Q1", atlanan)
        self.assertIn("U1", dict(d.idealler))
        self.assertIn("Iq bilinmiyor", dict(d.idealler)["U1"])
        # yuzen dugum onleyici
        self.assertIn("R_sizinti_N_SDA", metin)

    def test_kaynak_yoksa_benzetim_atlanir(self):
        k = copy.deepcopy(KOSUL_12V)
        k["kaynaklar"] = []
        k["raylar"] = {}
        s = seviye3(graf(ldo_devresi(), k))
        self.assertFalse(s.calisti)
        self.assertIn("besleme kaynagi yok", s.atlanma_nedeni)


class SenaryoTests(unittest.TestCase):
    def test_senaryolar(self):
        g = graf(bolucu(), BOLUCU_KOSUL)
        d = devre_kur(g)
        sn, notlar = senaryolar_uret(g, d)
        adlar = [s.ad for s in sn]
        for beklenen in ("nominal", "giris-min:VIN12", "giris-max:VIN12", "tolerans+", "tolerans-",
                         "monte-carlo-0", "sicaklik85+", "yaslanma+", "termal-en-kotu"):
            self.assertIn(beklenen, adlar)
        tp = next(s for s in sn if s.ad == "tolerans+")
        self.assertAlmostEqual(tp.degerler["R_R1"], 10100.0)
        # 85 C, TCR 100 ppm/C, (85-25) = 60 -> %0.6
        sc = next(s for s in sn if s.ad == "sicaklik85+")
        self.assertAlmostEqual(sc.degerler["R_R1"], 10000 * 1.006)
        blok = kontrol_blogu(d, sn)
        self.assertIn("alter V_VIN12 dc = 13", blok)
        self.assertIn("option temp=85", blok)

    def test_toleranssiz_direnc_notu(self):
        g = graf(bolucu(ust="10k", alt="3.3k"), BOLUCU_KOSUL)
        _sn, notlar = senaryolar_uret(g, devre_kur(g))
        self.assertTrue(any("toleransi bilinmeyen" in n for n in notlar))

    def test_wrdata_okuma(self):
        with tempfile.TemporaryDirectory() as tmp:
            yol = Path(tmp) / "s0.txt"
            yol.write_text(" in  v(out)  i(v1)\n 1.2e+01 2.97744361e+00 -9.0e-04\n", encoding="utf-8")
            satir = wrdata_oku(yol)[0]
        self.assertAlmostEqual(satir["v(out)"], 2.97744361)


@unittest.skipUnless(arka_uc_bul() is not None, "ngspice (KiCad ngspice.dll ya da konsol) yok")
class NgspiceTests(unittest.TestCase):
    def test_bolucu_gercek_benzetim(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = seviye3(graf(bolucu(), BOLUCU_KOSUL), Path(tmp))
        self.assertTrue(s.calisti, s.atlanma_nedeni)
        ozet = s.ekler["ag_ozeti"]["ORTA"]
        # 12 * 3.3 / 13.3
        self.assertAlmostEqual(ozet["nominal_v"], 12 * 3.3 / 13.3, places=4)
        # giris 11..13 V -> orta 2.73..3.23: gereksinim 2.9..3.1 IKI yonde asilir
        hatalar = [f for f in s.bulgular if f.rule_id == "gereksinim-gerilim" and f.severity == "error"]
        self.assertEqual(len(hatalar), 2)

    def test_ldo_ornegi_gerilim_dogru_termal_yanlis(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = seviye3(graf(ldo_devresi(), KOSUL_12V), Path(tmp))
        self.assertTrue(s.calisti, s.atlanma_nedeni)
        gerilim = [f for f in s.bulgular if f.rule_id == "gereksinim-gerilim"]
        self.assertEqual([f.severity for f in gerilim], ["info"])
        termal = [f for f in s.bulgular if f.rule_id == "benzetim-termal"][0]
        self.assertEqual(termal.severity, "error")
        reg = s.ekler["regulatorler"]["U1"]
        # termal en kotu: 12.6 V giris, 0.3 A surekli
        self.assertAlmostEqual(reg["guc_w"], (12.6 - 3.3) * 0.3, places=3)
        self.assertEqual(reg["senaryo"], "termal-en-kotu")

    def test_dusumde_regulasyon_kaybi(self):
        k = copy.deepcopy(KOSUL_12V)
        k["raylar"] = {"VBUS": {"nom": 5.0, "min": 4.0}}
        with tempfile.TemporaryDirectory() as tmp:
            s = seviye3(graf(ldo_devresi(), k), Path(tmp))
        self.assertIn("regulasyon-kaybi", [f.rule_id for f in s.bulgular])


if __name__ == "__main__":
    unittest.main()
