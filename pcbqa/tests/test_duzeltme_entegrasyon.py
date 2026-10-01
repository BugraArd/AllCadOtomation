"""Duzeltme siralama (Kicad-u4k) - GERCEK ngspice + KiCad entegrasyon testleri.

Sahte yanit YOK: benzetim KiCad'in ngspice.dll'i (yan surec), footprint
geometrisi KiCad'in kendi kutuphanesi, uygulama testi kicad-cli ile uretilmis
gercek bir KiCad projesi. Bunlardan biri yoksa sinif ATLANIR (gecti sayilmaz).
Sahte benzetimli birim testleri `test_duzeltme.py`dadir.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from pcbqa.duzeltme.adaylar import adaylari_uret
from pcbqa.duzeltme.bolucu import (Bolucu, BolucuParametre, analitik, ek_senaryo_uretici, tasarim_kur)
from pcbqa.duzeltme.degerlendir import degerlendir
from pcbqa.duzeltme.tasarim import Degisiklik
from pcbqa.spice import arka_uc_bul

KOK = Path(__file__).resolve().parents[1]
B = Bolucu("R1", "R2", "VIN", "OUT", "GND")


def _footprint_kutuphanesi_var() -> bool:
    try:
        from pcbqa import symlib

        return symlib.footprint_path("Resistor_SMD:R_0603_1608Metric").is_file()
    except Exception:
        return False


def _kicad_cli_var() -> bool:
    try:
        from pcbqa.kicadcli import find_kicad_cli

        return find_kicad_cli().is_file()
    except Exception:
        return False


NGSPICE = arka_uc_bul() is not None
FOOTPRINT = _footprint_kutuphanesi_var()


def param(**ek) -> BolucuParametre:
    d = dict(kimlik="e", vin_nom=12.0, vin_tol=0.02, vout_hedef=3.0, pencere=0.12, yuk_nom_a=1e-5,
             yuk_tepe_a=2e-5, ortam_c=25.0, sicakliklar=(-40.0, 85.0), r_ust=28700.0, r_alt=10000.0,
             tolerans=0.01, paket_ust="0603", paket_alt="0603", aralik_mm=3.2)
    d.update(ek)
    return BolucuParametre(**d)


@unittest.skipUnless(NGSPICE and FOOTPRINT, "ngspice ya da KiCad footprint kutuphanesi yok")
class GercekDegerlendirmeTesti(unittest.TestCase):
    def test_referans_gecerli_ve_benzetim_el_hesabiyla_ayni(self):
        d = degerlendir(tasarim_kur(param()), bolucu=B)
        self.assertEqual(d.durum, "gecerli", (d.kontroller, d.hatalar, d.nedenler))
        self.assertTrue(d.uyum["uyumlu"], d.uyum)
        self.assertLess(abs(d.uyum["vout_min"][0] - d.uyum["vout_min"][1]), 2e-6)

    def test_capraz_kose_kancasi_tolerans_kosesinin_kacirdigini_yakalar(self):
        """seviye3'un tolerans+/- senaryosu iki direnci ayni yone kaydirir;
        bolucu orani degismez. Ayni tasarim kancasiz GECER, kancayla KALIR."""
        from pcbqa.dogrulama.seviye3 import seviye3

        t = tasarim_kur(param(r_ust=30100.0))
        t.kosullar["gereksinimler"] = [{"ag": "OUT", "min_v": 2.8, "max_v": 3.3}]
        g = t.graf()
        kancasiz = seviye3(g)
        self.assertFalse([f for f in kancasiz.bulgular if f.rule_id == "gereksinim-gerilim"
                          and f.severity == "error"])
        kancali = seviye3(g, ek_senaryolar=ek_senaryo_uretici(B, analitik(g, B)))
        hatalar = [f for f in kancali.bulgular if f.rule_id == "gereksinim-gerilim" and f.severity == "error"]
        self.assertTrue(hatalar)
        self.assertIn("capraz-kose", hatalar[0].message)
        self.assertEqual(kancali.ekler["senaryo_sayisi"], kancasiz.ekler["senaryo_sayisi"] + 16)

    def test_footprint_degisimi_gercek_geometri_ve_aglari_korur(self):
        t = tasarim_kur(param()).uygula([Degisiklik("R1", "footprint", "Resistor_SMD:R_0603_1608Metric",
                                                    "Resistor_SMD:R_1206_3216Metric")])
        r1 = next(c for c in t.board.components if c.ref == "R1")
        self.assertEqual(sorted((p.number, p.net) for p in r1.pads), [("1", "VIN"), ("2", "OUT")])
        xs = [x for x, _ in r1.courtyard_poly]
        ys = [y for _, y in r1.courtyard_poly]
        # KiCad R_1206_3216Metric courtyard'i +-2.28 x +-1.13 mm; R1 ust rayda
        # yatay (bolucu.yerlesim, Kicad-ecd)
        self.assertAlmostEqual((max(xs) - min(xs)) / 2, 2.28, places=2)
        self.assertAlmostEqual((max(ys) - min(ys)) / 2, 1.13, places=2)
        # Izler yeni pad'lere yeniden yonlendirildi (eski 0603 pad'inde kalmadi)
        vin = [tr for tr in t.board.tracks if tr.net == "VIN"]
        self.assertEqual(len(vin), 1)
        self.assertAlmostEqual(vin[0].x2, r1.pad("1").x, places=6)

    def test_hata_kalir_aday_duzeltir_sikisik_paket_pcbde_kalir(self):
        # 2.4 mm: 0603 courtyard'lari sigar (1.48 + 0.73), 1206 sigmaz (2.28 + 1.13)
        t = tasarim_kur(param(aralik_mm=2.4))
        hatali = t.uygula([Degisiklik("R1", "deger", "28.7k", "47k")])
        self.assertEqual(degerlendir(hatali, bolucu=B).durum, "gecersiz")
        adaylar = {a.kimlik: a for a in adaylari_uret(hatali, B)}
        iyi = degerlendir(hatali.uygula(adaylar["ust-yeniden-E96"].degisiklikler), bolucu=B)
        self.assertEqual(iyi.durum, "gecerli", (iyi.kontroller, iyi.hatalar))
        buyuk = degerlendir(hatali.uygula(adaylar["paket-buyut-ikisi-2"].degisiklikler), bolucu=B)
        self.assertEqual(buyuk.kontroller["pcb-cakisma"], "kaldi")

    def test_negatif_vout_siniri_gercek_ngspice_el_hesabiyla_uyusur(self):
        """KALICI sinir testi (Kicad-ww0): I_yuk x R_ust = Vin'in hemen alti,
        esitligi ve hemen ustu. Ilk surumde bu bolgede benzetim ile el hesabi
        53 kayitta uyusmuyordu (guc ust siniri varsayimi). Uc noktada da
        uyum kapisi gecmeli ve tasarim gereksinimde KALMALI (denetlenemedi degil)."""
        for oran in (1 - 1e-3, 1.0, 1 + 1e-3):
            i = oran * 12.0 / 28700.0
            d = degerlendir(tasarim_kur(param(yuk_nom_a=i, yuk_tepe_a=i)), bolucu=B)
            self.assertTrue(d.uyum.get("uyumlu"), (oran, d.uyum))
            self.assertEqual(d.durum, "gecersiz", (oran, d.kontroller, d.nedenler))
            self.assertEqual(d.kontroller["gereksinim"], "kaldi")
            self.assertLess(d.olcumler["vout_min"], 0.0)

    def test_yuksek_empedansli_bolucude_uyum_kapisi_sizintiyi_kapsar(self):
        """Regresyon (Kicad-7cb verisi): 825k / 6.65M bolucude 1 Tohm sizinti
        gucte ~1.1e-5 fark yaratir; sabit 1e-5 esik gecerli benzetimi
        'uyusmadi' sayiyordu. Esik artik R_ag / R_sizinti ile olceklenir."""
        p = param(vin_nom=15.0, vin_tol=0.05, vout_hedef=1.65, pencere=0.11, yuk_nom_a=0.0, yuk_tepe_a=0.0,
                  ortam_c=85.0, r_ust=825000.0, r_alt=6650000.0, paket_ust="0402", paket_alt="0402", aralik_mm=2.4)
        d = degerlendir(tasarim_kur(p), bolucu=B)
        self.assertTrue(d.uyum["uyumlu"], d.uyum)
        self.assertGreater(d.uyum["goreli_esik"], 1e-5)
        self.assertNotEqual(d.durum, "denetlenemedi")

    def test_buyuk_paket_de_gercek_benzetimde_yetersiz_kalabilir(self):
        """Kicad-7cb: 1206 (0.25 W) 12 V / ~300 ohm bolucude ~0.33 W -> guc kalir.
        Ayni tasarim 0201'de de kalir; neden paket boyu degil guc orani."""
        from pcbqa.duzeltme.degerlendir import neden_etiketleri

        t = tasarim_kur(param(r_ust=226.0, r_alt=75.0, paket_ust="1206", paket_alt="1206", yuk_nom_a=0.0,
                              yuk_tepe_a=0.0))
        d = degerlendir(t, bolucu=B)
        self.assertEqual(d.kontroller["direnc-gucu"], "kaldi", d.kontroller)
        self.assertEqual(neden_etiketleri(d.as_dict())["guc"], "var")
        self.assertTrue(d.uyum.get("uyumlu"), d.uyum)

    def test_ayni_tohum_ayni_kayitlar(self):
        """Kicad-7cb tekrarlanabilirlik: zaman ve sure alanlari disinda bayt bayt ayni."""
        import json

        from pcbqa.duzeltme.orneklem import POLITIKALAR, plan
        from pcbqa.duzeltme.veri import referans_isle

        def temizle(x):
            if isinstance(x, dict):
                return {k: temizle(v) for k, v in x.items() if k not in ("zaman", "sure_s", "onbellekten")}
            if isinstance(x, list):
                return [temizle(v) for v in x]
            return x

        pol = POLITIKALAR["dengeli"]
        satir = plan(4, 99, pol)[1]
        a = json.dumps(temizle(referans_isle(1, 99, None, pol, satir)), sort_keys=True)
        b = json.dumps(temizle(referans_isle(1, 99, None, pol, satir)), sort_keys=True)
        self.assertEqual(a, b)

    def test_veri_kaydi_alanlari(self):
        from pcbqa.duzeltme.veri import referans_isle

        kayitlar = referans_isle(0, 20261001)
        ref = kayitlar[0]
        self.assertTrue(ref["kabul"], ref.get("neden"))
        adaylar = [k for k in kayitlar if k["tur"] == "aday"]
        self.assertTrue(adaylar)
        for k in adaylar:
            self.assertEqual(k["temel"]["kimlik"], "bolucu-0000")
            self.assertIn("kosullar", k["varyant"]["tasarim"])
            self.assertTrue(k["aday"]["degisiklikler"])
            for alan in ("kicad", "ngspice", "pcbqa_git", "parca_kutuphanesi", "aile", "oznitelik"):
                self.assertIn(alan, k["surumler"])
            self.assertIn(k["sonuc"]["durum"], ("gecerli", "gecersiz", "denetlenemedi"))
            self.assertIn("yeni_ihlaller", k["sonuc"])


@unittest.skipUnless(NGSPICE and FOOTPRINT and _kicad_cli_var(), "ngspice / KiCad / kicad-cli yok")
class GercekProjeUygulamaTesti(unittest.TestCase):
    """`pcbqa devre-duzelt` gercek bir KiCad projesinde - dosyalar DEGISMEZ."""

    @classmethod
    def setUpClass(cls):
        from pcbqa.generate import generate_from_intent

        cls.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-duzelt-test-"))
        cls.proje = cls.tmp / "proje"
        generate_from_intent(KOK / "samples" / "bolucu" / "bolucu-hatali.yaml", cls.proje,
                             time_budget_s=3.0)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _ozet(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(self.proje.iterdir())}

    def test_model_yokken_ureteci_sirasiyla_duzeltir_ve_yazmaz(self):
        from pcbqa.duzeltme.sirala import duzelt, projeden_tasarim, siralayici_yukle

        once = self._ozet()
        t = projeden_tasarim(self.proje, KOK / "samples" / "bolucu" / "kosullar.yaml")
        s = duzelt(t, siralayici_yukle(self.tmp / "olmayan-model.json"))
        self.assertIn("model yok", s.siralama)
        self.assertEqual(s.durum, "duzeltildi", [d.sonuc.kontroller for d in s.denemeler])
        self.assertEqual(s.secilen.sonuc.durum, "gecerli")
        self.assertEqual(self._ozet(), once)


if __name__ == "__main__":
    unittest.main()
