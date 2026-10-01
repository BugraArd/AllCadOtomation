"""ML veri baglantisi: dogrulama raporundan veri kumesi satiri."""

import tempfile
import unittest
from pathlib import Path

from devre_ornek import KOSUL_12V, graf, ldo_devresi

from pcbqa.dogrulama.kontroller import dokuz_kontrol
from pcbqa.dogrulama.seviye2 import seviye2
from pcbqa.ml.dataset import Dataset
from pcbqa.ml.devre_veri import OZNITELIKLER, ekle, etiket, ornek, ozellikler


def rapor_kur(g):
    s2 = seviye2(g)
    kontroller = dokuz_kontrol(g)
    return {
        "proje": "sentetik",
        "seviyeler": [s2.as_dict()],
        "kontroller": [x.as_dict() for x in kontroller],
        "yonlendirme_girdisi": {"yerlesim_kisitlari": [{"saglaniyor": False}, {"saglaniyor": True}]},
        "hata_sayisi": s2.sayi("error"),
    }


class DevreVeriTests(unittest.TestCase):
    def setUp(self):
        self.g = graf(ldo_devresi(), KOSUL_12V)
        self.rapor = rapor_kur(self.g)

    def test_oznitelikler_sabit_sirali(self):
        x = ozellikler(self.g, self.rapor)
        self.assertEqual(list(x), OZNITELIKLER)
        self.assertEqual(x["ldo"], 1.0)
        self.assertEqual(x["toplam_yuk_var"], 1.0)
        self.assertEqual(x["yerlesim_kisit_ihlal"], 1.0)
        # Seviye 3 kosmadi: olculemeyen oznitelik bayragi 0
        self.assertEqual(x["tj_marj_var"], 0.0)
        self.assertGreater(x["s2_hata"], 0)

    def test_etiketler(self):
        self.assertEqual(etiket(self.rapor, "gecti"), 0.0)
        self.assertIsNone(etiket(self.rapor, "tj_marj"))  # seviye 3 yok
        with self.assertRaises(ValueError):
            etiket(self.rapor, "uydurma")

    def test_ekle_ve_oku(self):
        s = ornek(self.g, self.rapor)
        self.assertGreater(s.extra["eksik_orani"], 0)
        with tempfile.TemporaryDirectory() as tmp:
            yol = Path(tmp) / "devre.jsonl"
            ekle(yol, s)
            ekle(yol, s)
            ds = Dataset.load(yol)
            self.assertEqual(len(ds), 2)
            self.assertEqual(ds.feature_names, OZNITELIKLER)
            self.assertEqual(ds.groups(), ["sentetik"])
            # Sema farkli bir dosyaya eklemek reddedilir
            yabanci = Dataset(feature_names=["a"], feature_version=9)
            yabanci.save(Path(tmp) / "y.jsonl")
            with self.assertRaises(ValueError):
                ekle(Path(tmp) / "y.jsonl", s)


if __name__ == "__main__":
    unittest.main()
