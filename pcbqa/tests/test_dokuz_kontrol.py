"""Dokuz kontrol: her biri kendi amacini sinar; 'denetlenemedi' gecti sayilmaz."""

import copy
import unittest

from devre_ornek import FP_R, KOSUL_12V, dokum, graf, ldo_devresi, parca

from pcbqa.dogrulama import kontroller as k
from pcbqa.pcb import Pad


def durum(sonuc):
    return sonuc.durum


class BaglantiEsligiTests(unittest.TestCase):
    def test_tutarli_kart_gecer(self):
        self.assertEqual(durum(k.baglanti_esligi(graf(ldo_devresi(), KOSUL_12V))), "gecti")

    def test_kartta_kisa_devre(self):
        p = ldo_devresi()
        g = graf(p, KOSUL_12V)
        # C3'un 3V3 padi kartta GND'ye bagli: sematik 3V3 ve GND tek kart aginda.
        # Graf PCB karsiligini kurulurken okur; karsiligin kendisi degistirilir.
        g.bilesen("C3").pinler["1"].padler[0].ag = "GND"
        s = k.baglanti_esligi(g)
        self.assertEqual(durum(s), "kaldi")
        self.assertTrue(any("kisa devre" in f.message for f in s.bulgular))

    def test_kart_yoksa_denetlenemedi(self):
        self.assertEqual(durum(k.baglanti_esligi(graf(ldo_devresi(), KOSUL_12V, kart=False))), "denetlenemedi")


class PinEsligiTests(unittest.TestCase):
    def test_eksik_pad(self):
        g = graf(ldo_devresi(), KOSUL_12V)
        g.board.by_ref("U1").pads.pop()  # VI padi yok
        s = k.pin_esligi(g)
        self.assertEqual(durum(s), "kaldi")
        self.assertIn("U1", s.bulgular[0].refs)

    def test_veri_kaydi_pin_adi_uyusmuyor(self):
        p = ldo_devresi()
        for x in p:
            if x["ref"] == "U1":  # sembol pin adlari kaydirilmis
                x["pinler"] = [("1", "VI", "power_in", "VBUS", 14.0, 14.0),
                               ("2", "VO", "power_out", "3V3", 16.0, 14.0),
                               ("3", "GND", "power_in", "GND", 18.0, 14.0)]
        s = k.pin_esligi(graf(p, KOSUL_12V))
        self.assertTrue(any("sembol yanlis parcaya" in f.message for f in s.bulgular))


class YuklenmeTermalTests(unittest.TestCase):
    def test_termal_regulator(self):
        s = k.termal(graf(ldo_devresi(), KOSUL_12V))
        self.assertEqual(durum(s), "kaldi")

    def test_yuklenme_kismen(self):
        s = k.bilesen_yuklenmesi(graf(ldo_devresi(), KOSUL_12V))
        # anma gerilimi bilinmeyen kondansatorler var -> gecti DEGIL
        self.assertIn(durum(s), ("kismen", "uyari", "kaldi"))
        self.assertNotEqual(durum(s), "gecti")


class KorumaTests(unittest.TestCase):
    def _sigortali(self, deger, tvs="SMBJ15A"):
        p = ldo_devresi()
        for x in p:
            for i, pin in enumerate(x["pinler"]):
                if pin[3] == "VBUS" and x["ref"] == "J1":
                    x["pinler"][i] = (pin[0], pin[1], pin[2], "GIRIS", *pin[4:])
        p.append(parca("F1", deger, "Device", "Fuse", "Fuse:Fuse_1206_3216Metric",
                       [("1", "", "passive", "GIRIS", 4.0, 10.0), ("2", "", "passive", "VBUS", 6.0, 10.0)]))
        p.append(parca("D5", tvs, "Device", "D_TVS", "Diode_SMD:D_SMB",
                       [("1", "K", "passive", "VBUS", 7.0, 12.0), ("2", "A", "passive", "GND", 7.0, 14.0)]))
        kos = copy.deepcopy(KOSUL_12V)
        kos["kaynaklar"] = ["GIRIS"]
        kos["raylar"]["GIRIS"] = {"nom": 12, "max": 12.6}
        return graf(p, kos)

    def test_sigorta_normal_yukte_atar(self):
        s = k.koruma_koordinasyonu(self._sigortali("100mA"))
        self.assertTrue(any("normal calismada atar" in f.message for f in s.bulgular))

    def test_tvs_standoff_raydan_dusuk(self):
        s = k.koruma_koordinasyonu(self._sigortali("1A", tvs="SMBJ5.0A"))
        self.assertTrue(any("TVS normal" in f.message for f in s.bulgular))
        s2 = k.koruma_koordinasyonu(self._sigortali("1A", tvs="SMBJ15A"))
        self.assertFalse(any(f.severity == "error" for f in s2.bulgular))


class UretimMekanikTests(unittest.TestCase):
    def test_ince_iz_ve_kucuk_via(self):
        g = graf(ldo_devresi(), KOSUL_12V,
                 izler=[("3V3", 0.1, "F.Cu", 16.0, 14.0, 20.0, 10.0)],
                 vialar=[("GND", 30.0, 30.0, 0.4, 0.2)])
        s = k.uretilebilirlik(g)
        adlar = {f.rule_id for f in s.bulgular}
        self.assertTrue({"uretim-iz", "uretim-delik", "uretim-halka"} <= adlar)

    def test_dar_aciklik(self):
        g = graf(ldo_devresi(), KOSUL_12V,
                 izler=[("3V3", 0.2, "F.Cu", 30.0, 30.0, 40.0, 30.0),
                        ("GND", 0.2, "F.Cu", 30.0, 30.3, 40.0, 30.3)])
        s = k.uretilebilirlik(g)
        self.assertIn("uretim-aciklik", {f.rule_id for f in s.bulgular})

    def test_pad_kart_disinda_ve_montaj(self):
        g = graf(ldo_devresi(), KOSUL_12V)
        g.board.by_ref("C1").pads[0].x = 120.0
        s = k.mekanik_montaj(g)
        self.assertEqual(durum(s), "kaldi")
        self.assertIn("montaj-deligi", {f.rule_id for f in s.bulgular})

    def test_konnektor_kenar(self):
        g = graf(ldo_devresi(), KOSUL_12V)
        self.assertNotIn("konnektor-erisimi", {f.rule_id for f in k.mekanik_montaj(g).bulgular})
        for pad in g.board.by_ref("J1").pads:
            pad.x += 30
        self.assertIn("konnektor-erisimi", {f.rule_id for f in k.mekanik_montaj(g).bulgular})


class DonusYoluTests(unittest.TestCase):
    def test_toprak_dokumu_yok(self):
        g = graf(ldo_devresi(), KOSUL_12V, izler=[("3V3", 0.5, "F.Cu", 16.0, 14.0, 40.0, 40.0)])
        s = k.donus_yolu(g)
        self.assertIn("donus-yolu", {f.rule_id for f in s.bulgular})

    def test_toprak_dokumu_ustunde(self):
        kare = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
        g = graf(ldo_devresi(), KOSUL_12V, izler=[("3V3", 0.5, "F.Cu", 16.0, 14.0, 40.0, 40.0)],
                 dokumler=[dokum("GND", "B.Cu", kare)])
        s = k.donus_yolu(g)
        self.assertEqual(s.olcumler["3V3_toprak_kapsama"], 1.0)
        self.assertFalse([f for f in s.bulgular if f.rule_id == "donus-yolu"])


class TestEdilebilirlikTests(unittest.TestCase):
    def test_ray_olcum_noktasi(self):
        g = graf(ldo_devresi(), KOSUL_12V)
        s = k.test_edilebilirlik(g)
        self.assertTrue(any("3V3" in f.message for f in s.bulgular))
        p = ldo_devresi()
        p.append(parca("TP1", "TP", "Connector", "TestPoint", "TestPoint:TestPoint_Pad_D1.0mm",
                       [("1", "1", "passive", "3V3", 70.0, 70.0)]))
        s2 = k.test_edilebilirlik(graf(p, KOSUL_12V))
        self.assertFalse(any("3V3" in f.message for f in s2.bulgular))

    def test_mcu_programlama(self):
        p = ldo_devresi()
        for x in p:
            if x["ref"] == "U2":
                x["deger"], x["part"] = "STM32G031K8T6", "STM32G031K8Tx"
                x["pinler"] += [("5", "PA13", "bidirectional", "SWDIO", 44.0, 44.0),
                                ("6", "PA14", "bidirectional", "SWCLK", 44.0, 46.0)]
        s = k.test_edilebilirlik(graf(p, KOSUL_12V))
        self.assertIn("programlama", {f.rule_id for f in s.bulgular})
        p.append(parca("J9", "SWD", "Connector_Generic", "Conn_01x03", "PinHeader_1x03",
                       [("1", "Pin_1", "passive", "SWDIO", 90.0, 90.0), ("2", "Pin_2", "passive", "SWCLK", 90.0, 92.5),
                        ("3", "Pin_3", "passive", "GND", 90.0, 95.0)]))
        s2 = k.test_edilebilirlik(graf(p, KOSUL_12V))
        self.assertNotIn("programlama", {f.rule_id for f in s2.bulgular if f.severity == "warning"})


class DokuzKontrolTests(unittest.TestCase):
    def test_dokuz_kontrol_ve_durumlar(self):
        sonuclar = k.dokuz_kontrol(graf(ldo_devresi(), KOSUL_12V))
        self.assertEqual(len(sonuclar), 9)
        self.assertEqual(len({s.ad for s in sonuclar}), 9)
        for s in sonuclar:
            self.assertIn(s.durum, ("gecti", "uyari", "kaldi", "kismen", "denetlenemedi"))


if __name__ == "__main__":
    unittest.main()
