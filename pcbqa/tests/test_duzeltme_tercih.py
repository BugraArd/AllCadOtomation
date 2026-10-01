"""En az degisiklik tercihi (Kicad-apg) - BIRIM testleri, arac gerekmez.

Beklenen sayilar el hesabidir: maliyet = sum(agirlik x alan sayimi),
varsayilan agirliklar parca 1, footprint 1, yonlendirme 0.25 ...
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pcbqa.duzeltme import tercih as T
from pcbqa.duzeltme.bolucu import BolucuParametre, tasarim_kur
from pcbqa.duzeltme.maliyet import VARSAYILAN_AGIRLIKLAR, agirliklar, fark, maliyet
from pcbqa.duzeltme.tasarim import Degisiklik
from pcbqa.ml.dataset import Dataset, Sample


def param(**ek) -> BolucuParametre:
    d = dict(kimlik="t", vin_nom=12.0, vin_tol=0.02, vout_hedef=3.0, pencere=0.1, yuk_nom_a=1e-5,
             yuk_tepe_a=2e-5, ortam_c=25.0, sicakliklar=(-40.0, 85.0), r_ust=30100.0, r_alt=10000.0,
             tolerans=0.01, paket_ust="0603", paket_alt="0603", aralik_mm=3.2)
    d.update(ek)
    return BolucuParametre(**d)


class MaliyetTesti(unittest.TestCase):
    def setUp(self):
        self.t = tasarim_kur(param(), kart=False)

    def test_ayni_refte_deger_ve_tolerans_tek_parca(self):
        t2 = self.t.uygula([Degisiklik("R1", "deger", "30.1k", "28.7k"),
                            Degisiklik("R1", "tolerans", "1%", "5%")])
        m = maliyet(self.t, t2)
        self.assertEqual(m["alanlar"]["parca"], 1)        # iki alan, TEK BOM kalemi
        self.assertEqual(m["alanlar"]["deger"], 1)
        self.assertEqual(m["alanlar"]["tolerans"], 1)
        self.assertEqual(m["toplam"], 1.0)
        self.assertEqual(m["refler"], {"R1": ["deger", "tolerans"]})

    def test_etkisiz_ve_geri_alinan_degisiklik_maliyetsiz(self):
        etkisiz = self.t.uygula([Degisiklik("R2", "deger", "10k", "10000")])
        self.assertEqual(maliyet(self.t, etkisiz)["toplam"], 0.0)
        geri = self.t.uygula([Degisiklik("R1", "deger", "30.1k", "4.7k"),
                              Degisiklik("R1", "deger", "4.7k", "30.1k")])
        self.assertEqual(maliyet(self.t, geri)["toplam"], 0.0)

    def test_iki_direnc_iki_parca(self):
        t2 = self.t.uygula([Degisiklik("R1", "deger", "30.1k", "3.01k"), Degisiklik("R2", "deger", "10k", "1k")])
        self.assertEqual(maliyet(self.t, t2)["toplam"], 2.0)

    def test_footprint_parcaya_ek_ve_baglanti_degismez(self):
        t2 = self.t.uygula([Degisiklik("R1", "footprint", "Resistor_SMD:R_0603_1608Metric",
                                       "Resistor_SMD:R_1206_3216Metric")])
        m = maliyet(self.t, t2)
        self.assertEqual(m["alanlar"]["parca"], 0)
        self.assertEqual(m["alanlar"]["footprint"], 1)
        self.assertEqual(m["alanlar"]["baglanti"], 0)
        self.assertEqual(m["toplam"], VARSAYILAN_AGIRLIKLAR["footprint"])

    def test_baglanti_degisimi_pin_basina(self):
        t2 = self.t.uygula([])
        for net in t2.netlist.nets:                       # R2.2'yi OUT'a tasi (kisa devre)
            net.nodes = [n for n in net.nodes if not (n.ref == "R2" and n.pin == "2")]
        out = next(n for n in t2.netlist.nets if n.name == "OUT")
        from pcbqa.netlist import NetNode
        out.nodes.append(NetNode("R2", "2", "", "passive"))
        f = fark(self.t, t2)
        self.assertEqual(f["sayim"]["baglanti"], 1)
        self.assertEqual(f["pinler"], ["R2.2"])

    def test_proje_tercihi_agirliklari_ezer_bilinmeyen_reddedilir(self):
        k = dict(self.t.kosullar, degisiklik_maliyeti={"parca": 3.0})
        self.assertEqual(agirliklar(k)["parca"], 3.0)
        self.t.kosullar = k
        t2 = self.t.uygula([Degisiklik("R1", "deger", "30.1k", "28.7k")])
        self.assertEqual(maliyet(self.t, t2)["toplam"], 3.0)
        with self.assertRaisesRegex(ValueError, "bilinmeyen maliyet alani"):
            agirliklar({"degisiklik_maliyeti": {"renk": 1}})


def ornek(parti, sira, durum, maliyet_, yi=0, grup="g", a_gecer=False, n=1):
    return Sample([float(sira)], {"gecerli": 1.0, "gecersiz": 0.0}.get(durum, -1.0), grup, parti,
                  {"durum": durum, "sira": sira, "maliyet": maliyet_, "yeni_ihlal": yi, "n_degisiklik": n,
                   "a_gecer": a_gecer})


class HedefTesti(unittest.TestCase):
    def test_tek_degisiklik_yeterliyse_o_tercih_edilir(self):
        p = [ornek("v", 0, "gecerli", 4.0, n=4), ornek("v", 1, "gecerli", 1.0)]
        T.hedefleri_ekle(p)
        self.assertEqual([s.extra["tercih_hedefi"] for s in p], [0.5, 1.0])
        m = T.olc([p], T.sirala_uretec)              # uretec 4 degisikligi once onerir
        self.assertEqual(m["pismanlik"], 3.0)
        self.assertEqual(T.olc([p], None, "dogrudan")["pismanlik"], 0.0)

    def test_az_degisiklikli_aday_gecersizse_gecerlilik_once(self):
        p = [ornek("v", 0, "gecersiz", 1.0), ornek("v", 1, "gecerli", 4.0)]
        T.hedefleri_ekle(p)
        self.assertEqual([s.extra["tercih_hedefi"] for s in p], [0.0, 1.0])
        # en kotu gecerli bile her gecersizden yuksek
        q = [ornek("w", 0, "gecersiz", 0.0), ornek("w", 1, "gecerli", 9.0), ornek("w", 2, "gecerli", 1.0)]
        T.hedefleri_ekle(q)
        self.assertGreater(min(s.extra["tercih_hedefi"] for s in q if s.extra["durum"] == "gecerli"), 0.0)

    def test_esit_maliyet_esit_tercih_ek_tercih_yeni_ihlal(self):
        p = [ornek("v", 0, "gecerli", 2.0), ornek("v", 1, "gecerli", 2.0), ornek("v", 2, "gecerli", 2.0, yi=1)]
        T.hedefleri_ekle(p)
        h = [s.extra["tercih_hedefi"] for s in p]
        self.assertEqual(h[0], h[1])                   # esdeger
        self.assertEqual(p[0].extra["tercih_derecesi"], p[1].extra["tercih_derecesi"])
        self.assertGreater(h[0], h[2])                 # 3. seviye: daha az yeni ihlal

    def test_cozumsuz_parti_isaretlenir(self):
        p = [ornek("v", 0, "gecersiz", 1.0), ornek("v", 1, "gecersiz", 2.0)]
        T.hedefleri_ekle(p)
        self.assertTrue(all(s.extra["parti_cozumsuz"] for s in p))
        m = T.olc([p], T.sirala_uretec)
        self.assertEqual((m["cozulebilir"], m["cozumsuz"], m["cozumsuz_partide_harcanan"]), (0, 1, 2))

    def test_eksik_analiz_gecersizle_birlesmez(self):
        p = [ornek("v", 0, "denetlenemedi", 1.0), ornek("v", 1, "gecerli", 3.0)]
        T.hedefleri_ekle(p)
        self.assertIsNone(p[0].extra["tercih_hedefi"])
        self.assertEqual([s.extra["sira"] for s in T.hedef_ornekleri(p, T.HEDEF_ADI)], [1])
        self.assertEqual([s.extra["sira"] for s in T.hedef_ornekleri(p, T.GECERLILIK)], [1])
        # Siralamada bir benzetim harcar ama gecerli sayilmaz
        self.assertEqual(T.olc([p], T.sirala_uretec)["simulasyon"], 2)

    def test_farkli_partiler_ortak_siraya_konmaz(self):
        a = [ornek("x", 0, "gecerli", 1.0), ornek("x", 1, "gecerli", 2.0)]
        b = [ornek("y", 0, "gecerli", 5.0), ornek("y", 1, "gecerli", 6.0)]
        T.hedefleri_ekle(a + b)
        self.assertEqual([s.extra["tercih_hedefi"] for s in a], [s.extra["tercih_hedefi"] for s in b])


class PolitikaTesti(unittest.TestCase):
    def setUp(self):
        # sira: 0 gecersiz(1), 1 gecerli(4), 2 gecerli(2), 3 gecerli(1)
        self.p = [ornek("v", 0, "gecersiz", 1.0), ornek("v", 1, "gecerli", 4.0), ornek("v", 2, "gecerli", 2.0),
                  ornek("v", 3, "gecerli", 1.0)]

    def test_ilk_gecerli_ilk_k_dogrudan(self):
        g = T.olc([self.p], T.sirala_uretec, "ilk-gecerli")
        self.assertEqual((g["simulasyon"], g["pismanlik"], g["ilk_gecerli"], g["ilk3"]), (2, 3.0, 0.0, 1.0))
        k = T.olc([self.p], T.sirala_uretec, "ilk-k", k=3)  # ilk 3: {gecersiz, 4, 2} -> 2
        self.assertEqual((k["simulasyon"], k["pismanlik"]), (3, 1.0))
        d = T.olc([self.p], None, "dogrudan")
        self.assertEqual((d["simulasyon"], d["pismanlik"], d["en_az_secildi"]), (4, 0.0, 1.0))

    def test_kova_kurali_ayni_dilimde_dusuk_maliyet(self):
        puan = {0: 0.05, 1: 0.95, 2: 0.91, 3: 0.92}
        ham = T.sirala_puan(lambda s: puan[s.extra["sira"]])(self.p)
        kova = T.sirala_puan(lambda s: puan[s.extra["sira"]], 0.1, "maliyet")(self.p)
        self.assertEqual([s.extra["sira"] for s in ham], [1, 3, 2, 0])
        self.assertEqual([s.extra["sira"] for s in kova], [3, 2, 1, 0])


class UyumlulukTesti(unittest.TestCase):
    def test_v1_veri_kumesi_acik_hatayla_reddedilir(self):
        from pcbqa.duzeltme.egitim import veri_yukle
        from pcbqa.duzeltme.ozellik import HAM, OZNITELIK_SURUMU, TAM

        with tempfile.TemporaryDirectory() as d:
            for sema, adlar in (("ham", HAM), ("tam", TAM)):
                Dataset(feature_names=list(adlar), feature_version=OZNITELIK_SURUMU,
                        meta={"sema": sema}).save(Path(d) / f"veri-{sema}.jsonl")
            with self.assertRaisesRegex(ValueError, "kayit semasi v1"):
                veri_yukle(Path(d))

    def test_ayni_tasarim_imzasi_ayni_grupta(self):
        from pcbqa.duzeltme.veri import kopya_gruplari

        k = [{"tur": "aday", "temel": {"kimlik": "a", "imza": "x"}},
             {"tur": "aday", "temel": {"kimlik": "b", "imza": "x"}},
             {"tur": "aday", "temel": {"kimlik": "c", "imza": "y"}}]
        self.assertEqual(kopya_gruplari(k), {"a": "a", "b": "a", "c": "c"})


if __name__ == "__main__":
    unittest.main()
