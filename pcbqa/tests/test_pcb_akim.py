"""Dal akimi: bir aga tek akim atanmaz; ana kol toplami, dallar kendi yukunu tasir."""

import math
import unittest

from devre_ornek import graf, parca

from pcbqa import ipc2221
from pcbqa.pcb_akim import (
    akim_dagilimi, iz_analizi, iz_direnci_ohm, onderdonk_erime_a, sicaklik_artisi_c,
    via_direnci_ohm, yonlendirme_girdisi,
)


class TemelHesapTests(unittest.TestCase):
    def test_iz_direnci(self):
        # rho L / (w t) = 1.7241e-8 * 0.01 / (0.254e-3 * 0.035e-3)
        self.assertAlmostEqual(iz_direnci_ohm(10, 0.254, 0.035), 1.7241e-8 * 0.01 / (0.254e-3 * 0.035e-3))
        sicak = iz_direnci_ohm(10, 0.254, 0.035, sicaklik_c=70)
        self.assertAlmostEqual(sicak / iz_direnci_ohm(10, 0.254, 0.035), 1 + 0.00393 * 50)

    def test_ipc_tersi(self):
        w = ipc2221.trace_width_mm(1.0, 10.0, 1.0, True)
        self.assertAlmostEqual(sicaklik_artisi_c(1.0, w, 1.0, True), 10.0, places=6)

    def test_onderdonk_ve_via(self):
        a = onderdonk_erime_a(0.25 * 0.035, 0.01)
        self.assertGreater(a, onderdonk_erime_a(0.25 * 0.035, 1.0))  # kisa darbe daha cok
        self.assertGreater(via_direnci_ohm(0.3, 1.6, 0.02), 0)


def dal_karti(kol_genislik=1.0, dal_genislik=1.0, darbe=False, izin=None, via=False):
    """Kaynak J1 (0,0) -> eklem (10,0) -> U2 (10,6) 0.2 A ve U3 (20,0) 0.5 A.

    U3'e giden kolun ucu (20,0); U2'nin dali (10,0)'dan baslar - eklem
    NOKTASI ayri bir iz ucu degil, kol izinin ORTASINDA (T birlesimi).
    """
    p = [
        parca("J1", "IN", "Connector_Generic", "Conn_01x02", "PinHeader",
              [("1", "Pin_1", "passive", "P5V", 0.0, 0.0), ("2", "Pin_2", "passive", "GND", 0.0, 30.0)]),
        parca("U2", "IC", "X", "IC", "SOIC",
              [("1", "VDD", "power_in", "P5V", 10.0, 6.0), ("2", "GND", "power_in", "GND", 10.0, 30.0)]),
        parca("U3", "IC", "X", "IC", "SOIC",
              [("1", "VDD", "power_in", "P5V", 20.0, 0.0), ("2", "GND", "power_in", "GND", 20.0, 30.0)]),
    ]
    izler = [("P5V", kol_genislik, "F.Cu", 0.0, 0.0, 20.0, 0.0),
             ("P5V", dal_genislik, "F.Cu", 10.0, 0.0, 10.0, 6.0),
             ("GND", 2.0, "F.Cu", 0.0, 30.0, 20.0, 30.0)]
    yukler = [{"ag": "P5V", "akim_a": 0.2, "ref": "U2", "pin": "1"},
              {"ag": "P5V", "akim_a": 0.5, "ref": "U3", "pin": "1"}]
    if darbe:
        yukler[1].update({"tepe_a": 60.0, "darbe_s": 0.5})
    kos = {"raylar": {"P5V": 5.0}, "kaynaklar": ["P5V"], "yukler": yukler}
    if izin is not None:
        kos["pcb"] = {"izin_dV_yuzde": izin}
    vialar = []
    if via:
        # kolun ortasina ikinci katmana gecis: (5,0)'da via, B.Cu uzerinden (5,0)->(10,0)
        izler = [("P5V", kol_genislik, "F.Cu", 0.0, 0.0, 5.0, 0.0),
                 ("P5V", kol_genislik, "B.Cu", 5.0, 0.0, 10.0, 0.0),
                 ("P5V", kol_genislik, "F.Cu", 10.0, 0.0, 20.0, 0.0),
                 ("P5V", dal_genislik, "F.Cu", 10.0, 0.0, 10.0, 6.0),
                 ("GND", 2.0, "F.Cu", 0.0, 30.0, 20.0, 30.0)]
        vialar = [("P5V", 5.0, 0.0, 0.4, 0.15), ("P5V", 10.0, 0.0, 0.4, 0.15)]
    return graf(p, kos, izler=izler, vialar=vialar)


class DalAkimiTests(unittest.TestCase):
    def test_akim_noktalari_ve_donus(self):
        g = dal_karti()
        d = akim_dagilimi(g)
        p5 = {n.pin: n.surekli_a for n in d["P5V"].noktalar}
        self.assertAlmostEqual(p5["J1.1"], 0.7)
        self.assertAlmostEqual(p5["U2.1"], -0.2)
        gnd = {n.pin: n.surekli_a for n in d["GND"].noktalar}
        self.assertAlmostEqual(gnd["J1.2"], -0.7)
        self.assertAlmostEqual(gnd["U3.2"], 0.5)

    def test_ana_kol_toplami_dallar_kendi_yuku(self):
        s = iz_analizi(dal_karti())
        self.assertTrue(s.calisti, s.atlanma_nedeni)
        kenarlar = s.ekler["aglar"]["P5V"]["kenarlar"]
        akim = {(k["x"], k["y"]): k["surekli_a"] for k in kenarlar}
        self.assertAlmostEqual(akim[(5.0, 0.0)], 0.7, places=6)    # ana kol
        self.assertAlmostEqual(akim[(15.0, 0.0)], 0.5, places=6)   # U3 dali
        self.assertAlmostEqual(akim[(10.0, 3.0)], 0.2, places=6)   # U2 dali (T birlesimi)

    def test_donus_akimi_pad_iz_ortasinda(self):
        # GND izi U2.2'nin (10,30) USTUNDEN geciyor; iz orada bolunmeli
        s = iz_analizi(dal_karti())
        akim = {(k["x"], k["y"]): k["surekli_a"] for k in s.ekler["aglar"]["GND"]["kenarlar"]}
        self.assertAlmostEqual(akim[(5.0, 30.0)], 0.7, places=6)
        self.assertAlmostEqual(akim[(15.0, 30.0)], 0.5, places=6)

    def test_dar_dal_darbogaz(self):
        s = iz_analizi(dal_karti(kol_genislik=0.05))
        hatalar = [f for f in s.bulgular if f.rule_id in ("iz-darbogaz", "iz-pad-cikisi")]
        self.assertTrue(hatalar)
        self.assertTrue(all(f.measured == 0.05 for f in hatalar))

    def test_gerilim_dusumu_beyani(self):
        s = iz_analizi(dal_karti(kol_genislik=0.2, dal_genislik=0.2, izin=0.1))
        self.assertIn("iz-gerilim-dusumu", [f.rule_id for f in s.bulgular])
        s2 = iz_analizi(dal_karti())
        self.assertIn("iz-gerilim-dusumu-eksik-bilgi", [f.rule_id for f in s2.bulgular])

    def test_darbe(self):
        s = iz_analizi(dal_karti(kol_genislik=0.15, dal_genislik=0.15, darbe=True))
        self.assertIn("iz-darbe", [f.rule_id for f in s.bulgular])

    def test_via_akimi(self):
        s = iz_analizi(dal_karti(via=True))
        vialar = [f for f in s.bulgular if f.rule_id == "via-akimi"]
        # 0.15 mm via TI tablosunda 0.20 A; kol 0.7 A tasiyor
        self.assertTrue(vialar)

    def test_yonlendirilmemis_kart_atlanir(self):
        g = dal_karti()
        g.board.tracks = []
        s = iz_analizi(g)
        self.assertFalse(s.calisti)
        self.assertIn("yonlendirilmemis", s.atlanma_nedeni)


class YonlendirmeGirdisiTests(unittest.TestCase):
    def test_dal_butcesi(self):
        g = dal_karti()
        g.board.tracks = []
        yg = yonlendirme_girdisi(g)
        self.assertEqual(yg["sira"][0], "1-yerlesim-kisitlari")
        dallar = yg["aglar"]["P5V"]["dallar"]
        toplam = max(d["surekli_a"] for d in dallar)
        self.assertAlmostEqual(toplam, 0.7)
        for d in dallar:
            self.assertGreaterEqual(d["onerilen_genislik_mm"], yg["uretim_sinirlari"]["min_iz_mm"])
            beklenen = ipc2221.trace_width_mm(d["surekli_a"], 10.0, 1.0, True)
            self.assertAlmostEqual(d["gereken_genislik_mm"], round(beklenen, 4))

    def test_toprak_dali_net_enjeksiyon(self):
        g = dal_karti()
        g.board.tracks = []
        dallar = yonlendirme_girdisi(g)["aglar"]["GND"]["dallar"]
        # J1.2 (kaynak donusu) agacin yapragi: kenari toplam donusu tasir
        j1 = [d for d in dallar if d["e"] == "J1.2"][0]
        self.assertTrue(math.isclose(j1["surekli_a"], 0.7, rel_tol=1e-9))


if __name__ == "__main__":
    unittest.main()
