"""Duzeltme siralama (Kicad-u4k) - BIRIM testleri, SAHTE benzetimle.

Bu dosya ngspice ve KiCad kutuphanesi GEREKTIRMEZ: kart kurulmaz
(`tasarim_kur(kart=False)`), benzetim `degerlendir(benzetim=...)` ile
enjekte edilen sahte bir seviye3'tur. Gercek ngspice / KiCad footprint'i
kullanan testler `test_duzeltme_entegrasyon.py`dadir.

Beklenen sayilar koddan bagimsiz, el hesabiyla yazildi:
    Vout = R2 (Vin - I R1) / (R1 + R2)
"""

from __future__ import annotations

import inspect
import json
import random
import tempfile
import unittest
from itertools import permutations
from pathlib import Path

from pcbqa import eseri
from pcbqa.dogrulama.sonuc import SeviyeSonucu, bulgu
from pcbqa.duzeltme import olcut
from pcbqa.duzeltme.adaylar import adaylari_uret
from pcbqa.duzeltme.bolucu import Bolucu, BolucuParametre, _guc_ust_siniri, _p_r1, _p_r2, analitik, tasarim_kur
from pcbqa.duzeltme.degerlendir import degerlendir
from pcbqa.duzeltme.egitim import _bolmeler
from pcbqa.duzeltme.maliyet import maliyet
from pcbqa.duzeltme.ozellik import HAM, OZNITELIK_SURUMU, TAM, on_hesap, ozellikler, tasarim_ozeti
from pcbqa.duzeltme.sirala import siralayici_yukle
from pcbqa.duzeltme.tasarim import TOLERANS_ALANI, Degisiklik
from pcbqa.ml.dataset import Dataset, Sample
from pcbqa.ml.model import MeanModel

B = Bolucu("R1", "R2", "VIN", "OUT", "GND")


def param(**ek) -> BolucuParametre:
    d = dict(kimlik="t", vin_nom=12.0, vin_tol=0.02, vout_hedef=3.0, pencere=0.1, yuk_nom_a=1e-5,
             yuk_tepe_a=2e-5, ortam_c=25.0, sicakliklar=(-40.0, 85.0), r_ust=30100.0, r_alt=10000.0,
             tolerans=0.01, paket_ust="0603", paket_alt="0603", aralik_mm=3.2)
    d.update(ek)
    return BolucuParametre(**d)


class AnalitikTesti(unittest.TestCase):
    def test_nominal_ve_en_kotu_kose_el_hesabi(self):
        a = analitik(tasarim_kur(param(), kart=False).graf(), B)
        self.assertTrue(a.hesaplanabilir, a.eksikler)
        self.assertAlmostEqual(a.vout_nom, 10000 * (12 - 1e-5 * 30100) / 40100, places=12)
        # sapma = %1 tolerans + 100 ppm/C x 65 C (25 -> -40) + omur testi (%1 + 50 mohm)
        # Yageo RC_L V.10 Tablo 2 (0603 TCR +-100 ppm) ve Tablo 8 (F: +-(1% + 50 mohm))
        s1, s2 = 0.0265 + 0.05 / 30100, 0.0265 + 0.05 / 10000
        self.assertAlmostEqual(a.sapma_ust, s1, places=12)
        self.assertAlmostEqual(a.sapma_alt, s2, places=12)
        r1y, r2a = 30100 * (1 + s1), 10000 * (1 - s2)
        self.assertAlmostEqual(a.vout_min, r2a * (11.76 - 2e-5 * r1y) / (r1y + r2a), places=12)
        r1a, r2y = 30100 * (1 - s1), 10000 * (1 + s2)
        self.assertAlmostEqual(a.vout_max, r2y * 12.24 / (r1a + r2y), places=12)
        self.assertEqual(len(a.koseler), 16)
        # 0603 kalin film 0.1 W, azami calisma gerilimi 75 V (Tablo 2), 25 C'de azaltma yok
        self.assertEqual(a.p_ust_siniri, 0.1)
        self.assertEqual(a.v_ust_siniri, 75.0)
        self.assertAlmostEqual(a.v_ust_max, max(k.vin - k.r2 * (k.vin - k.i * k.r1) / (k.r1 + k.r2)
                                                for k in a.koseler), places=12)

    def test_guc_ust_siniri_izgaradan_asla_kucuk_degil(self):
        # Negatif Vout bolgesi (I R1 > Vin) dahil - ilk surum orada yaniliyordu.
        rng = random.Random(7)
        for _ in range(300):
            vin = rng.uniform(1, 24)
            i = rng.choice([0, 1e-5, 1e-3])
            r1, r2 = 10 ** rng.uniform(1, 7), 10 ** rng.uniform(1, 7)
            vins, ak = (vin * 0.95, vin * 1.05), (0.0, i)
            r1s, r2s = (r1 * 0.97, r1 * 1.03), (r2 * 0.97, r2 * 1.03)
            p1, p2 = _guc_ust_siniri(vins, ak, r1s, r2s)

            def izgara(a):
                return [a[0] + (a[1] - a[0]) * k / 6 for k in range(7)]
            g1 = max(_p_r1(v, x, a, b) for v in izgara(vins) for x in izgara(ak)
                     for a in izgara(r1s) for b in izgara(r2s))
            g2 = max(_p_r2(v, x, a, b) for v in izgara(vins) for x in izgara(ak)
                     for a in izgara(r1s) for b in izgara(r2s))
            self.assertLessEqual(g1, p1 * (1 + 1e-12))
            self.assertLessEqual(g2, p2 * (1 + 1e-12))

    def test_tolerans_bilinmiyorsa_hesaplanamaz(self):
        t = tasarim_kur(param(), kart=False)
        del t.netlist.components["R1"].fields[TOLERANS_ALANI]
        a = analitik(t.graf(), B)
        self.assertFalse(a.hesaplanabilir)
        self.assertTrue(any("tolerans" in e for e in a.eksikler), a.eksikler)


def sahte_benzetim(*, calisti=True, bulgular=(), ozet=None):
    def benzetim(g, calisma=None, ek_senaryolar=None):
        s = SeviyeSonucu(3, "sahte")
        s.calisti = calisti
        s.atlanma_nedeni = "" if calisti else "ngspice bulunamadi"
        s.bulgular = list(bulgular)
        s.ekler["ag_ozeti"] = ozet or {}
        benzetim.cagrildi += 1
        return s
    benzetim.cagrildi = 0
    return benzetim


class DegerlendirmeDurumTesti(unittest.TestCase):
    """Eksik model / yakinsamama ELEKTRIKSEL basarisizlik sayilmaz."""

    def setUp(self):
        self.t = tasarim_kur(param(), kart=False)

    def test_benzetim_calismadiysa_denetlenemedi(self):
        d = degerlendir(self.t, benzetim=sahte_benzetim(calisti=False), bolucu=B)
        self.assertEqual(d.durum, "denetlenemedi")
        self.assertEqual(d.kontroller["benzetim"], "denetlenemedi")
        self.assertNotIn("kaldi", d.kontroller.values())

    def test_yakinsamama_denetlenemedi(self):
        f = bulgu("benzetim-hatasi", "error", "ngspice: timestep too small", source="t")
        d = degerlendir(self.t, benzetim=sahte_benzetim(bulgular=[f]), bolucu=B)
        self.assertEqual(d.durum, "denetlenemedi")
        self.assertEqual(d.kontroller["gereksinim"], "denetlenemedi")

    def test_gereksinim_hatasi_gecersiz(self):
        f = bulgu("gereksinim-gerilim", "error", "OUT 2.5 V < 2.7 V", source="t", measured=2.5, limit=2.7)
        d = degerlendir(self.t, benzetim=sahte_benzetim(bulgular=[f]), bolucu=B)
        self.assertEqual(d.durum, "gecersiz")
        self.assertIn("gereksinim-gerilim||error|alt", d.ihlaller)

    def test_parca_bilgisi_eksikse_benzetim_cagrilmaz(self):
        del self.t.netlist.components["R2"].fields[TOLERANS_ALANI]
        sahte = sahte_benzetim()
        d = degerlendir(self.t, benzetim=sahte, bolucu=B)
        self.assertEqual(d.durum, "denetlenemedi")
        self.assertEqual(sahte.cagrildi, 0)
        self.assertEqual(d.simulasyon, 0)


class AdayUreteciTesti(unittest.TestCase):
    def setUp(self):
        hatali = tasarim_kur(param(), kart=False)
        self.t = hatali.uygula([Degisiklik("R1", "deger", "30.1k", "47k")])

    def test_ust_yeniden_el_hesabi(self):
        adaylar = {a.kimlik: a for a in adaylari_uret(self.t, B)}
        # Vt = pencere merkezi 3.0 V; R1 = R2 (Vin - Vt) / (Vt + I R2), I = 10 uA
        beklenen = eseri.nearest(10000 * (12 - 3.0) / (3.0 + 1e-5 * 10000), "E96")
        a = adaylar["ust-yeniden-E96"]
        self.assertEqual(a.degisiklikler, [Degisiklik("R1", "deger", "47k", f"{beklenen / 1e3:.3g}k")])

    def test_ureteci_hatayi_ve_sonucu_gormez(self):
        imza = inspect.signature(adaylari_uret)
        self.assertEqual(list(imza.parameters), ["t", "b"])

    def test_belirlenimci_ve_tekrarsiz(self):
        a1, a2 = adaylari_uret(self.t, B), adaylari_uret(self.t, B)
        self.assertEqual([a.as_dict() for a in a1], [a.as_dict() for a in a2])
        kumeler = [frozenset((d.ref, d.alan, d.yeni) for d in a.degisiklikler) for a in a1]
        self.assertEqual(len(kumeler), len(set(kumeler)))
        self.assertEqual([a.sira for a in a1], list(range(len(a1))))


class OznitelikSizintiTesti(unittest.TestCase):
    """Tahmin aninda olmayan bilgi oznitelige giremez."""

    def kayit(self):
        t = tasarim_kur(param(), kart=False).uygula([Degisiklik("R1", "deger", "30.1k", "47k")])
        f = bulgu("gereksinim-gerilim", "error", "x", source="t", measured=2.0, limit=2.7)
        d = degerlendir(t, benzetim=sahte_benzetim(bulgular=[f]), bolucu=B)
        a = adaylari_uret(t, B)[0]
        return {
            "varyant": {"tasarim": tasarim_ozeti(t, B), "degerlendirme": d.as_dict(),
                        "hata": {"tur": "deger-ust"}},
            "aday": {**a.as_dict(), "on_hesap": on_hesap(t.uygula(a.degisiklikler), B),
                     "maliyet": maliyet(t, t.uygula(a.degisiklikler))},
            "sonuc": {"durum": "gecerli", "yeni_ihlaller": ["x"], "olcumler": {"vout_min": 99.0}},
        }

    def test_sonuc_ve_hata_turu_oznitelik_degistirmez(self):
        k = self.kayit()
        for sema in ("ham", "tam"):
            once = ozellikler(k, sema)
            k2 = json.loads(json.dumps(k))
            del k2["sonuc"]
            del k2["varyant"]["hata"]
            self.assertEqual(once, ozellikler(k2, sema))
            k3 = json.loads(json.dumps(k))
            k3["sonuc"]["durum"] = "gecersiz"
            k3["varyant"]["hata"]["tur"] = "paket-kucuk"
            self.assertEqual(once, ozellikler(k3, sema))

    def test_sema_uzunluklari(self):
        k = self.kayit()
        self.assertEqual(len(ozellikler(k, "ham")), len(HAM))
        self.assertEqual(len(ozellikler(k, "tam")), len(TAM))

    def test_v1_kaydi_sessizce_yorumlanmaz(self):
        k = self.kayit()
        del k["aday"]["maliyet"]
        with self.assertRaisesRegex(ValueError, "maliyet yok"):
            ozellikler(k, "ham")


def ornek(grup, parti, sira, durum, yi=0, n=1, vin=12.0, hata="deger-ust", a_gecer=False, g_cakisma=False):
    return Sample([0.0], 1.0 if durum == "gecerli" else 0.0, grup, parti,
                  {"durum": durum, "sira": sira, "yeni_ihlal": yi, "n_degisiklik": n, "vin_nom": vin,
                   "hata": hata, "a_gecer": a_gecer, "g_cakisma": g_cakisma})


class OlcutTesti(unittest.TestCase):
    def setUp(self):
        # parti A: gecerli 3. sirada; parti B: gecerli 1. sirada; parti C: cozumsuz
        self.parts = olcut.partiler([
            ornek("g1", "A", 0, "gecersiz", yi=2), ornek("g1", "A", 1, "denetlenemedi"),
            ornek("g1", "A", 2, "gecerli", n=2, a_gecer=True), ornek("g1", "A", 3, "gecersiz"),
            ornek("g2", "B", 0, "gecerli", yi=1), ornek("g2", "B", 1, "gecersiz"),
            ornek("g3", "C", 0, "gecersiz"), ornek("g3", "C", 1, "gecersiz"),
        ])

    def test_uretec_sirasi_el_hesabi(self):
        m = olcut.olc(self.parts, olcut.sirala_uretec)
        self.assertEqual((m["parti"], m["cozulebilir"]), (3, 2))
        self.assertAlmostEqual(m["ilk_gecerli"], 0.5)        # B evet, A hayir
        self.assertAlmostEqual(m["ilk3"], 1.0)               # A'da 3. sirada
        self.assertAlmostEqual(m["simulasyon"], (3 + 1) / 2)  # denetlenemedi de bir benzetim
        self.assertAlmostEqual(m["yeni_ihlal_ilk"], (2 + 1 + 0) / 3)
        self.assertAlmostEqual(m["degisiklik"], (2 + 1) / 2)
        self.assertEqual(m["cozumsuz_partide_harcanan"], 2)

    def test_kural_once_el_hesabi_gecenler(self):
        m = olcut.olc(self.parts, olcut.sirala_kural_elektrik)
        # A'da el hesabi gecen (sira 2) one gelir; B'de kimse gecmez -> ureteci
        # sirasi, gecerli zaten basta.
        self.assertAlmostEqual(m["ilk_gecerli"], 1.0)
        self.assertAlmostEqual(m["simulasyon"], 1.0)

    def test_kova_icinde_az_degisiklik_once(self):
        a = ornek("g", "P", 0, "gecerli", n=4)       # 0.97 puan, 4 degisiklik
        b = ornek("g", "P", 1, "gecerli", n=1)       # 0.93 puan, 1 degisiklik
        c = ornek("g", "P", 2, "gecersiz", n=1)      # 0.40 puan
        puan = {0: 0.97, 1: 0.93, 2: 0.40}
        ham = olcut.sirala_puan(lambda s: puan[s.extra["sira"]])([a, b, c])
        kovali = olcut.sirala_puan(lambda s: puan[s.extra["sira"]], 0.1)([a, b, c])
        self.assertEqual([s.extra["sira"] for s in ham], [0, 1, 2])
        self.assertEqual([s.extra["sira"] for s in kovali], [1, 0, 2])

    def test_rastgele_kapali_form_permutasyon_ortalamasina_esit(self):
        m = olcut.olc_rastgele(self.parts)
        p = self.parts[0]
        sims, ilk3 = [], []
        for perm in permutations(p):
            j = next(i for i, s in enumerate(perm) if s.extra["durum"] == "gecerli")
            sims.append(j + 1)
            ilk3.append(j < 3)
        beklenen_sim = (sum(sims) / len(sims) + 1.5) / 2     # B: n=2, k=1 -> 1.5
        self.assertAlmostEqual(m["simulasyon"], beklenen_sim)
        self.assertAlmostEqual(m["ilk3"], (sum(ilk3) / len(ilk3) + 1.0) / 2)


class BolmeTesti(unittest.TestCase):
    def test_temel_tasarim_iki_tarafta_olamaz(self):
        ds = Dataset(["x"])
        for g in range(12):
            for p in range(3):
                for s in range(4):
                    ds.add(ornek(f"g{g}", f"p{p}", s, "gecersiz", vin=24.0 if g % 4 == 0 else 5.0,
                                 hata=["deger-ust", "paket-kucuk"][p % 2]))
        bolmeler = _bolmeler(ds, 5, 1)
        for test_mi, _ in bolmeler["gruplu-cv"]:
            test = {s.group for s in ds.samples if test_mi(s)}
            egitim = {s.group for s in ds.samples if not test_mi(s)}
            self.assertFalse(test & egitim)
        (test_mi, _), = bolmeler["dagilim-disi"]
        self.assertTrue(all(s.extra["vin_nom"] >= 15 for s in ds.samples if test_mi(s)))
        self.assertTrue(all(s.extra["vin_nom"] < 15 for s in ds.samples if not test_mi(s)))
        for test_mi, tur in bolmeler["hata-disi"]:
            self.assertTrue(all(s.extra["hata"] != tur for s in ds.samples if not test_mi(s)))


class SiralayiciGeriDonusTesti(unittest.TestCase):
    """Model yoksa / bozuksa uygulama ureteci sirasiyla CALISMAYA DEVAM eder."""

    def kayitlar(self, n=4):
        return [{"aday": {"sira": i}} for i in range(n)]

    def test_model_dosyasi_yoksa_ureteci_sirasi(self):
        s = siralayici_yukle(Path(tempfile.gettempdir()) / "olmayan-model-u4k.json")
        self.assertIsNone(s.model)
        self.assertIn("model yok", s.kaynak)
        self.assertEqual(s.sirala(self.kayitlar()), [0, 1, 2, 3])

    def test_bozuk_ya_da_uyusmaz_model_ureteci_sirasi(self):
        with tempfile.TemporaryDirectory() as d:
            bozuk = Path(d) / "bozuk.json"
            bozuk.write_text("{bozuk", encoding="utf-8")
            self.assertIn("kullanilamadi", siralayici_yukle(bozuk).kaynak)
            m = MeanModel(feature_names=["eski_oznitelik"], feature_version=1, meta={"sema": "ham"})
            yol = Path(d) / "eski.json"
            m.save(yol)
            s = siralayici_yukle(yol)
            self.assertIsNone(s.model)
            self.assertIn("kullanilamadi", s.kaynak)

    def test_uyumlu_model_kullanilir(self):
        with tempfile.TemporaryDirectory() as d:
            m = MeanModel(feature_names=HAM, feature_version=OZNITELIK_SURUMU, meta={"sema": "ham"})
            yol = Path(d) / "m.json"
            m.save(yol)
            s = siralayici_yukle(yol)
            self.assertIsNotNone(s.model)
            self.assertTrue(s.kaynak.startswith("model mean-ham"))

    def test_v1_modeli_ve_bilinmeyen_hedef_reddedilir(self):
        """Kicad-u4k modeli (oznitelik v1) yeni semayla SESSIZCE kullanilmaz;
        hedefi bilinmeyen model de reddedilir - uygulama ureteci sirasina doner."""
        with tempfile.TemporaryDirectory() as d:
            eski = MeanModel(feature_names=HAM[:-5], feature_version=1, meta={"sema": "ham", "kova": 0.1})
            eski.save(Path(d) / "v1.json")
            s = siralayici_yukle(Path(d) / "v1.json")
            self.assertIsNone(s.model)
            self.assertIn("kullanilamadi", s.kaynak)
            garip = MeanModel(feature_names=HAM, feature_version=OZNITELIK_SURUMU,
                              meta={"sema": "ham", "hedef": "olasilik-v9"})
            garip.save(Path(d) / "garip.json")
            s = siralayici_yukle(Path(d) / "garip.json")
            self.assertIsNone(s.model)
            self.assertIn("bilinmeyen hedef", s.kaynak)


class NegatifVoutSinirTesti(unittest.TestCase):
    """KALICI sinir testi (Kicad-ww0 regresyonu): I_yuk x R_ust = Vin sinirinin
    hemen alti, esitligi ve hemen ustu.

    Ilk surum "Vin - I R1 > 0" varsayiyordu: P_R1'i R2'nin EN KUCUGUNDE,
    P_R2'yi I = 0'da en buyuk saniyordu. Sinirin ustunde ikisi de tersine
    doner. Beklenen degerler koddan bagimsiz, turevin isaretinden:
        d/dR2 [(Vin + I R2)/(R1 + R2)] isareti = isaret(I R1 - Vin)
        esitlikte (Vin + I R2)/(R1 + R2) = I  ->  P_R1 = R1 I^2 (R2'den bagimsiz)
    """

    VIN, R1, R2 = 12.0, 28700.0, 10000.0
    R2S = (9000.0, 11000.0)

    def _i(self, oran: float) -> float:
        return oran * self.VIN / self.R1

    def test_vout_isareti_sinirda(self):
        from pcbqa.duzeltme.bolucu import vout

        self.assertGreater(vout(self.VIN, self._i(1 - 1e-6), self.R1, self.R2), 0.0)
        self.assertAlmostEqual(vout(self.VIN, self._i(1.0), self.R1, self.R2), 0.0, places=12)
        self.assertLess(vout(self.VIN, self._i(1 + 1e-6), self.R1, self.R2), 0.0)

    def test_guc_ust_siniri_sinirin_alti_esitligi_ustu(self):
        vin, r1 = self.VIN, self.R1
        for oran, beklenen_r2 in ((1 - 1e-3, self.R2S[0]), (1.0, None), (1 + 1e-3, self.R2S[1])):
            i = self._i(oran)
            p1, p2 = _guc_ust_siniri((vin, vin), (i, i), (r1, r1), self.R2S)
            if beklenen_r2 is None:
                self.assertAlmostEqual(p1, r1 * i * i, delta=1e-12 * p1)
                self.assertAlmostEqual(_p_r1(vin, i, r1, self.R2S[0]), _p_r1(vin, i, r1, self.R2S[1]),
                                       delta=1e-12 * p1)
            else:
                self.assertEqual(p1, _p_r1(vin, i, r1, beklenen_r2), oran)
            # Izgara her durumda ust sinirin altinda kalmali
            izgara = [self.R2S[0] + (self.R2S[1] - self.R2S[0]) * k / 50 for k in range(51)]
            self.assertLessEqual(max(_p_r1(vin, i, r1, r2) for r2 in izgara), p1 * (1 + 1e-12))
            self.assertLessEqual(max(_p_r2(vin, i, r1, r2) for r2 in izgara), p2 * (1 + 1e-12) + 1e-18)

    def test_sinirin_ustunde_p_r2_yuk_akimiyla_artar(self):
        # I R1 > 2 Vin'de (Vin - I R1)^2 > Vin^2: en buyuk P_R2 I = 0'da DEGIL.
        vin, r1, r2 = self.VIN, self.R1, self.R2
        i = self._i(2.5)
        p1, p2 = _guc_ust_siniri((vin, vin), (0.0, i), (r1, r1), (r2, r2))
        self.assertEqual(p2, _p_r2(vin, i, r1, r2))
        self.assertGreater(p2, _p_r2(vin, 0.0, r1, r2))

    def test_negatif_vout_gereksinimde_kalir(self):
        for oran in (1 - 1e-3, 1.0, 1 + 1e-3):
            i = self._i(oran)
            a = analitik(tasarim_kur(param(r_ust=self.R1, r_alt=self.R2, yuk_nom_a=i, yuk_tepe_a=i),
                                     kart=False).graf(), B)
            self.assertTrue(a.hesaplanabilir)
            self.assertLess(a.vout_min, 0.0)       # sapma kosesinde sinir zaten asilir
            self.assertFalse(a.pencere_icinde)


class GercekProjeDurumTesti(unittest.TestCase):
    """Gercek proje hattinin durum birlestirmesi (araclar gerekmez)."""

    def test_oncelik_kaldi_arac_veri_gecti(self):
        from pcbqa.duzeltme.proje import birlesik_durum

        self.assertEqual(birlesik_durum({"a": "gecti", "b": "gecti"}), "gecti")
        self.assertEqual(birlesik_durum({"a": "gecti", "b": "veri-model-eksik"}), "veri-model-eksik")
        self.assertEqual(birlesik_durum({"a": "arac-hatasi", "b": "veri-model-eksik"}), "arac-hatasi")
        # Bilinen bir kalis tasarimi gecersiz kilar - arac eksigi onu ortmez
        self.assertEqual(birlesik_durum({"a": "arac-hatasi", "b": "kaldi"}), "kaldi")
        # Hic kontrol yoksa basari DEGIL
        self.assertEqual(birlesik_durum({}), "veri-model-eksik")

    def test_elektrik_durumlari_eksik_turunu_ayirir(self):
        from pcbqa.duzeltme.degerlendir import Degerlendirme
        from pcbqa.duzeltme.proje import _elektrik_durumlari

        d = Degerlendirme("denetlenemedi", {"benzetim": "denetlenemedi", "gereksinim": "denetlenemedi",
                                            "pcb-cakisma": "gecti"}, eksik_turu="arac")
        self.assertEqual(_elektrik_durumlari(d), {"benzetim": "arac-hatasi", "gereksinim": "arac-hatasi",
                                                  "pcb-cakisma": "gecti"})
        d = Degerlendirme("denetlenemedi", {"benzetim": "denetlenemedi"}, eksik_turu="veri-model")
        self.assertEqual(_elektrik_durumlari(d), {"benzetim": "veri-model-eksik"})
        d = Degerlendirme("denetlenemedi", {"benzetim": "gecti"}, uyum={"karsilastirildi": True, "uyumlu": False})
        self.assertEqual(_elektrik_durumlari(d)["benzetim-el-hesabi"], "arac-hatasi")

    def test_degerlendir_eksik_turu(self):
        """denetlenemedi: ngspice -> arac; parca bilgisi -> veri-model."""
        t = tasarim_kur(param(), kart=False)
        self.assertEqual(degerlendir(t, benzetim=sahte_benzetim(calisti=False), bolucu=B).eksik_turu, "arac")
        t.netlist.components["R1"].fields.pop(TOLERANS_ALANI)
        self.assertEqual(degerlendir(t, benzetim=sahte_benzetim(), bolucu=B).eksik_turu, "veri-model")


if __name__ == "__main__":
    unittest.main()
