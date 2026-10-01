"""Seviye 2: kurallar parcaya ve devrenin amacina bagli."""

import copy
import unittest

from devre_ornek import FP_R, KOSUL_12V, graf, ldo_devresi, parca

from pcbqa.dogrulama.seviye2 import (
    kontrol_asiri_gerilim, kontrol_gate, kontrol_gerekli, kontrol_regulator, kontrol_yuklenme, seviye2,
)


def ids(bulgular, severity=None):
    return [f.rule_id for f in bulgular if severity is None or f.severity == severity]


def kosul(**degisim):
    k = copy.deepcopy(KOSUL_12V)
    k.update(degisim)
    return k


class RegulatorTests(unittest.TestCase):
    def test_12v_300ma_ldo_termal_hata(self):
        g = graf(ldo_devresi(), KOSUL_12V)
        f = [x for x in kontrol_regulator(g) if x.rule_id == "regulator-termal"][0]
        self.assertEqual(f.severity, "error")
        # (12.6 - 3.3) x 0.3 = 2.79 W
        self.assertIn("2.79 W", f.message)
        self.assertGreater(f.measured, 125)

    def test_dusuk_kayip_gecer(self):
        k = kosul(raylar={"VBUS": {"nom": 5.0, "min": 4.75, "max": 5.25}},
                  yukler=[{"ag": "3V3", "akim_a": 0.05, "ref": "U2", "pin": "1"}])
        g = graf(ldo_devresi(), k)
        f = [x for x in kontrol_regulator(g) if x.rule_id == "regulator-termal"][0]
        self.assertEqual(f.severity, "info")

    def test_dusum_marji(self):
        g = graf(ldo_devresi(), kosul(raylar={"VBUS": {"nom": 4.5, "min": 4.0}}))
        f = [x for x in kontrol_regulator(g) if "dusum" in x.message][0]
        self.assertEqual(f.severity, "error")
        self.assertAlmostEqual(f.measured, 0.7, places=6)

    def test_giris_mutlak_maks(self):
        g = graf(ldo_devresi(), kosul(raylar={"VBUS": 16}))
        self.assertIn("regulator-kosullari", ids(kontrol_regulator(g), "error"))

    def test_yuk_beyani_yoksa_denetlenemedi(self):
        g = graf(ldo_devresi(), kosul(yukler=[]))
        bul = kontrol_regulator(g)
        self.assertTrue(all(f.severity == "info" for f in bul))
        self.assertTrue(any("yuk akimi beyan edilmedi" in f.message for f in bul))


class GateTests(unittest.TestCase):
    def test_2n7002_3v3_ile_uyari(self):
        g = graf(ldo_devresi(mosfet="2N7002"), KOSUL_12V)
        f = kontrol_gate(g)
        self.assertEqual(ids(f, "warning"), ["gate-surme"])
        self.assertIn("Rds(on)", f[0].message)

    def test_ao3400a_3v3_yeter(self):
        g = graf(ldo_devresi(mosfet="AO3400A"), KOSUL_12V)
        self.assertEqual(kontrol_gate(g), [])

    def test_esik_altinda_hata(self):
        k = kosul(raylar={"VBUS": 12, "3V3": 1.8})
        g = graf(ldo_devresi(mosfet="2N7002"), k)
        self.assertIn("gate-surme", ids(kontrol_gate(g), "error"))


class GerekliElemanTests(unittest.TestCase):
    def test_serbest_gecis_diyotu(self):
        g = graf(ldo_devresi(diyot=False), KOSUL_12V)
        self.assertIn("enduktif-koruma-eksik", ids(kontrol_gerekli(g), "error"))
        g2 = graf(ldo_devresi(diyot=True), KOSUL_12V)
        self.assertNotIn("enduktif-koruma-eksik", ids(kontrol_gerekli(g2)))
        self.assertTrue(g2.bilesen("D2").rol("serbest-gecis-diyotu"))

    def test_i2c_pullup_ve_dekuplaj(self):
        g = graf(ldo_devresi(pullup=False, dekuplaj=False), KOSUL_12V)
        bul = ids(kontrol_gerekli(g), "warning")
        self.assertIn("pull-up-eksik", bul)
        self.assertIn("dekuplaj-eksik", bul)
        g2 = graf(ldo_devresi(), KOSUL_12V)
        self.assertEqual(ids(kontrol_gerekli(g2), "warning"), [])

    def test_cikis_kapasitesi_veri_sayfasi_alt_siniri(self):
        g = graf(ldo_devresi(cikis_kond="10uF"), KOSUL_12V)
        self.assertIn("regulator-kond-eksik", ids(kontrol_gerekli(g), "warning"))


class YuklenmeTests(unittest.TestCase):
    def test_direnc_gucu_ve_kond_gerilimi(self):
        p = ldo_devresi()
        p.append(parca("R9", "100", "Device", "R", FP_R,
                       [("1", "", "passive", "VBUS", 80.0, 80.0), ("2", "", "passive", "GND", 82.0, 80.0)]))
        p.append(parca("C9", "1uF 6.3V", "Device", "C", "C_0603",
                       [("1", "", "passive", "VBUS", 80.0, 85.0), ("2", "", "passive", "GND", 82.0, 85.0)]))
        g = graf(p, KOSUL_12V)
        bul = kontrol_yuklenme(g)
        r9 = [f for f in bul if "R9" in f.refs][0]
        self.assertEqual(r9.severity, "error")
        # 12.6^2 / 100 = 1.5876 W > 0.1 W (0603)
        self.assertAlmostEqual(r9.measured, 12.6 ** 2 / 100)
        c9 = [f for f in bul if "C9" in f.refs][0]
        self.assertEqual((c9.severity, c9.limit), ("error", 6.3))

    def test_anma_bilinmeyen_kondansator_raporlanir(self):
        g = graf(ldo_devresi(), KOSUL_12V)
        bilgi = [f for f in kontrol_yuklenme(g) if f.rule_type == "eksik-bilgi"]
        self.assertTrue(any("C1" in f.message for f in bilgi))


class AsiriGerilimTests(unittest.TestCase):
    def test_vdd_mutlak_maks_ve_cmos_kurali(self):
        p = ldo_devresi()
        for x in p:
            if x["ref"] == "U2":
                x["deger"], x["part"] = "STM32G031K8T6", "STM32G031K8Tx"
        g = graf(p, kosul(raylar={"VBUS": 12, "3V3": 5.0, "SDA": 5.0}))
        bul = kontrol_asiri_gerilim(g)
        vdd = [f for f in bul if "U2.1" in f.pins][0]
        self.assertEqual((vdd.severity, vdd.limit), ("error", 4.0))

    def test_sinirsiz_ic_cmos_genel_kurali(self):
        g = graf(ldo_devresi(), kosul(raylar={"VBUS": 12, "SDA": 5.0}))
        bul = [f for f in kontrol_asiri_gerilim(g) if "U2.3" in f.pins]
        self.assertEqual(bul[0].severity, "warning")
        self.assertAlmostEqual(bul[0].limit, 3.6)
        self.assertIn("muhendislik secimi", bul[0].message)


class Seviye2Tests(unittest.TestCase):
    def test_ozet(self):
        s = seviye2(graf(ldo_devresi(), KOSUL_12V))
        self.assertTrue(s.calisti)
        self.assertFalse(s.gecti)
        self.assertGreaterEqual(s.ekler["regulator-kosullari"], 1)


if __name__ == "__main__":
    unittest.main()
