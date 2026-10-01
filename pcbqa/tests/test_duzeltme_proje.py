"""Gercek KiCad projesinde duzeltme adayi dogrulama (Kicad-ecd) - ENTEGRASYON.

Sahte yanit YOK: referans projeler `generate` ile gercek sembol / footprint
kutuphanelerinden uretilir, kontroller kurulu kicad-cli (ERC, DRC + parite)
ve KiCad'in ngspice.dll'i ile kosar. Biri yoksa sinif ATLANIR - atlanan test
gecti sayilmaz, uctan uca dogrulama yapilmamis olur.

Arac/model eksigini taklit eden iki test (kicad-cli calismiyor, ngspice
calismiyor) kontrollerin BIRINI sahte yapar ama digerleri gercektir; bunlar
durum ayriminin ("arac-hatasi" basari sayilmaz) gercek akista korundugunu gosterir.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from pcbqa.duzeltme import proje as P
from pcbqa.duzeltme.adaylar import Aday
from pcbqa.duzeltme.tasarim import Degisiklik
from pcbqa.spice import arka_uc_bul


def _kicad_cli_var() -> bool:
    try:
        from pcbqa.kicadcli import find_kicad_cli

        return find_kicad_cli().is_file()
    except Exception:
        return False


def _kutuphane_var() -> bool:
    try:
        from pcbqa import symlib

        return symlib.footprint_path("Resistor_SMD:R_0603_1608Metric").is_file()
    except Exception:
        return False


ARACLAR = arka_uc_bul() is not None and _kicad_cli_var() and _kutuphane_var()


def _sch_degeri(proje: P.Proje, ref: str) -> tuple[str, str]:
    from pcbqa.schematic import read_schematic

    s = read_schematic(proje.sch).by_ref(ref)
    return s.value, s.footprint


@unittest.skipUnless(ARACLAR, "kicad-cli / KiCad kutuphanesi / ngspice yok - uctan uca dogrulama YAPILMADI")
class GercekProjeZinciriTesti(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-ecd-"))
        refs = P.referanslari_uret(cls.tmp / "ref")
        cls.gecerli, cls.hatali = refs["gecerli"], refs["hatali"]
        cls.ozet_gecerli, cls.ozet_hatali = cls.gecerli.ozetler(), cls.hatali.ozetler()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _kopya(self, kaynak: P.Proje, ad: str) -> P.Proje:
        return P.kopyala(kaynak, self.tmp / "mutasyon" / ad)

    def _temel(self, proje: P.Proje, ad: str, **kw) -> dict:
        r = P.deney(proje.klasor, self.tmp / "deney" / ad, en_fazla=0, **kw)
        return r["kayitlar"][0]

    # -- referanslar --------------------------------------------------------

    def test_gecerli_referans_yonlendirilmis_ve_butun_zincirden_gecer(self):
        k = self._temel(self.gecerli, "gecerli")
        self.assertEqual(k["durum"], "gecti", k["kontroller"])
        self.assertEqual(k["kicad"]["sayilar"], {"erc": 0, "drc": 0, "baglanmamis": 0, "parite": 0, "dislanan": 0})
        # Kart gercekten yonlendirilmis: bakir izler var ve iz analizi kostu
        from pcbqa.pcb import read_board

        self.assertEqual(len(read_board(self.gecerli.pcb).tracks), 7)
        self.assertEqual(k["kontroller"]["elektrik-pcb-iz"], "gecti")
        # Komutlar, cikis kodlari ve makinece okunur raporlar saklandi
        for adim in ("netlist", "erc", "drc"):
            a = k["kicad"]["adimlar"][adim]
            self.assertEqual(a["cikis_kodu"], 0)
            self.assertTrue((Path(k["rapor_klasoru"]) / a["rapor"]).is_file())
        self.assertIn("--schematic-parity", k["kicad"]["adimlar"]["drc"]["komut"])
        # Bastirma yok: PWR_FLAG / no-connect / dislama eklenmedi
        self.assertEqual(k["geri_okuma"]["bastirma"],
                         {"pwr_flag": 0, "no_connect": 0, "erc_dislama": 0, "drc_dislama": 0})
        # Beklenen elektriksel sonuc BAGIMSIZ el hesabiyla (Vout = R2 Vin / (R1 + R2))
        ol = k["elektrik"]["olcumler"]
        self.assertAlmostEqual(ol["vout_nom"], 10000 * (12 - 1e-5 * 28700) / 38700, places=5)
        self.assertTrue(k["elektrik"]["uyum"]["uyumlu"])
        self.assertTrue(k["egitim"]["aktarilabilir"])
        self.assertEqual(self.gecerli.ozetler(), self.ozet_gecerli)

    def test_hatali_referansta_aday_gercek_dosyada_uygulanir_ve_zincirden_gecer(self):
        """Kabul olcutu: yonlendirilmis gercek projede aday uygulanir; ERC,
        DRC, parite, geri okuma, ngspice ve iz analizi hepsi gecer."""
        class Oncelik:
            """Ureteci sirasindan bagimsiz: iki tek-direnc adayini one al."""
            kaynak = "test onceligi"

            def sirala(self, kayitlar):
                tercih = ["ust-yeniden-E96", "alt-yeniden-E96"]
                return sorted(range(len(kayitlar)), key=lambda i: (
                    tercih.index(kayitlar[i]["aday"]["kimlik"]) if kayitlar[i]["aday"]["kimlik"] in tercih else 9, i))

        r = P.deney(self.hatali.klasor, self.tmp / "deney" / "hatali", hepsi=True, en_fazla=2, siralayici=Oncelik())
        temel, a1, a2 = r["kayitlar"]
        self.assertEqual(temel["durum"], "kaldi")
        self.assertEqual(temel["kontroller"]["elektrik-gereksinim"], "kaldi")
        self.assertEqual(temel["kicad"]["sayilar"]["drc"], 0)       # hata KiCad'de degil, elektrikte
        self.assertEqual(a1["aday"]["kimlik"], "ust-yeniden-E96")
        self.assertEqual(a1["durum"], "gecti", a1["kontroller"])
        self.assertTrue(all(v == "gecti" for v in a1["kontroller"].values()))
        self.assertEqual(a1["kicad"]["sayilar"]["parite"], 0)
        self.assertTrue(a1["egitim"]["aktarilabilir"])
        self.assertTrue(a1["egitim"]["bellek_ile_uyumlu"])
        # Deger diskte ve kicad-cli'nin yeniden okudugu netlist'te; tolerans
        # metni korunur (regresyon: "47k 1%")
        p1 = P.Proje(Path(a1["klasor"]), self.hatali.ad)
        self.assertEqual(_sch_degeri(p1, "R1")[0], "28.7k 1%")
        from pcbqa.netlist import read_netlist

        n = read_netlist(Path(a1["rapor_klasoru"]) / "netlist.xml")
        self.assertEqual(n.components["R1"].value, "28.7k 1%")
        ol = a1["elektrik"]["olcumler"]
        self.assertGreaterEqual(ol["vout_min"], 2.64)
        self.assertLessEqual(ol["vout_max"], 3.36)
        # Yalitim: ikinci aday ilkinin degisikligini TASIMAZ
        p2 = P.Proje(Path(a2["klasor"]), self.hatali.ad)
        self.assertEqual(_sch_degeri(p2, "R1")[0], "47k 1%")
        self.assertNotEqual(_sch_degeri(p2, "R2")[0], "10k 1%")
        self.assertTrue(r["temel_degismedi"])
        self.assertEqual(self.hatali.ozetler(), self.ozet_hatali)
        self.assertTrue((self.tmp / "deney" / "hatali" / "deney.jsonl").is_file())
        # Secim (Kicad-d8k): 2/17 aday denendi -> kapsam kismi, kuresel iddia yok.
        # Iki aday da gecti ve maliyet 1: esitlik kararli ureteci kimligiyle
        # ('alt-...' < 'ust-...'); ilk gecen (eski kural) ayri alanda.
        s = r["secim"]
        self.assertEqual(s["kapsam"], "kismi")
        self.assertFalse(s["kuresel_en_dusuk"])
        self.assertEqual(a2["durum"], "gecti", a2["kontroller"])
        self.assertEqual(r["ilk_gecen"], a1["kimlik"])
        self.assertEqual(r["secilen"], a2["kimlik"])
        self.assertEqual(s["esit_maliyetliler"], [a1["kimlik"]])
        self.assertEqual(a1["egitim"]["etiket"], 1)          # gecerlilik etiketi secimden etkilenmez
        self.assertTrue(a2["tercih"]["secildi"] and not a1["tercih"]["secildi"])
        self.assertEqual(temel["aciklamalar"][0]["kod"], "elektrik-gereksinim")
        self.assertIn("Izin verilen aralik 2,64-3,36 V", temel["aciklamalar"][0]["metin"])
        self.assertEqual(a1["bilesenler"]["R1"]["paket"], "0603")
        self.assertEqual(a1["bilesenler"]["R1"]["deger"], "28.7k 1%")

    def test_footprint_degisimi_diskte_kimlik_korunur_ve_yeniden_yonlendirilir(self):
        roller = P.roller_oku(self.gecerli.klasor)
        o = P.Ortam(self.gecerli, json.loads((self.gecerli.klasor / "kosullar.json").read_text()), roller,
                    self.tmp / "fp", P.temel_durumu(self.gecerli), {}, onbellek=False)
        fp = "Resistor_SMD:R_1206_3216Metric"
        a = Aday("fp", "paket-buyut", [Degisiklik("R1", "footprint", "Resistor_SMD:R_0603_1608Metric", fp)], "")
        k = P.aday_dogrula(o, "fp", a, None)
        p = P.Proje(Path(k["klasor"]), self.gecerli.ad)
        self.assertEqual(_sch_degeri(p, "R1")[1], fp)
        kim = P.kart_kimlikleri(p.pcb)
        once = o.once["kart"]["R1"]
        self.assertEqual(kim["R1"]["footprint"], fp)
        self.assertEqual(kim["R1"]["uuid"], once["uuid"])
        self.assertEqual(kim["R1"]["path"], once["path"])
        self.assertEqual(kim["R1"]["pad_aglari"], {"1": "/VIN", "2": "/OUT"})
        from pcbqa.pcb import read_board

        b = read_board(p.pcb)
        r1 = b.by_ref("R1")
        vin = [t for t in b.tracks if t.net == "/VIN"]
        self.assertAlmostEqual(vin[0].x2, r1.pad("1").x, places=4)   # iz yeni pad'e gidiyor
        self.assertEqual(k["kicad"]["sayilar"]["parite"], 0)          # kutuphane kopyasiyla ayni
        self.assertEqual(k["kontroller"]["geri-okuma"], "gecti")
        self.assertEqual(k["durum"], "gecti", k["kontroller"])

    # -- kontrollu hatalar: ilgili kontrol yakalamali ------------------------

    def test_kontrollu_baglanti_hatasi_kicad_tarafindan_yakalanir(self):
        """R2'nin GND etiketi 'GDN' yazilir: sematikte ag kopar, kart eski
        baglantiyi tasir -> KiCad paritesi ve ERC yakalar."""
        from pcbqa.schematic import read_schematic
        from pcbqa.sexpr import QuotedStr, as_float, child, children, parse_with_stats
        from pcbqa.sch_write import write_tree

        p = self._kopya(self.gecerli, "baglanti")
        pin = next(x for x in read_schematic(p.sch).by_ref("R2").pins if x.number == "2")
        root, _ = parse_with_stats(p.sch.read_text(encoding="utf-8"))
        etiket = next(n for n in children(root, "label")
                      if abs(as_float(child(n, "at")[1]) - pin.x) < 1e-3
                      and abs(as_float(child(n, "at")[2]) - pin.y) < 1e-3)
        etiket[1] = QuotedStr("GDN")
        write_tree(p.sch, root, apply=True, backup=False)
        k = self._temel(p, "baglanti")
        self.assertEqual(k["durum"], "kaldi")
        self.assertEqual(k["kontroller"]["kicad-parite"], "kaldi", k["kicad"]["ihlaller"])
        self.assertTrue(any(v["grup"] == "schematic_parity" for v in k["kicad"]["ihlaller"]))

    def test_pcb_baglantisizligi_drc_ve_iz_analizi_yakalar(self):
        from pcbqa.pcb import read_board

        p = self._kopya(self.gecerli, "kopuk")
        izler = [t for t in read_board(p.pcb).tracks if t.net != "/VIN"]
        P.izleri_yaz(p.pcb, izler)
        k = self._temel(p, "kopuk")
        self.assertEqual(k["durum"], "kaldi")
        self.assertEqual(k["kontroller"]["kicad-drc"], "kaldi")
        self.assertGreaterEqual(k["kicad"]["sayilar"]["baglanmamis"], 1)
        self.assertEqual(k["kontroller"]["elektrik-pcb-iz"], "kaldi")

    def test_gercek_clearance_ihlali_drc_yakalar(self):
        p = self._kopya(self.gecerli, "aciklik")
        # 2.4 mm iz, 2.54 mm aralikli raylarda farkli aglari 0.2 mm'den yakin getirir
        P.yonlendir_dosya(p, P.roller_oku(p.klasor), genislik_mm=2.4)
        k = self._temel(p, "aciklik")
        self.assertEqual(k["kontroller"]["kicad-drc"], "kaldi")
        turler = {v["tur"] for v in k["kicad"]["ihlaller"]}
        self.assertTrue(turler & {"clearance", "shorting_items"}, turler)
        self.assertEqual(k["durum"], "kaldi")

    def test_elektriksel_sinir_ihlali_benzetimle_yakalanir(self):
        """Empedans /100 (287 ohm / 100 ohm): KiCad kontrolleri temiz, ama 0603
        (0.1 W) direncte ~0.27 W - direnc gucu kontrolu yakalamali."""
        p = P.referans_projesi(replace(P.REFERANS, kimlik="guc", r_ust=287.0, r_alt=100.0),
                               self.tmp / "ref" / "guc", "guc")
        k = self._temel(p, "guc")
        self.assertEqual(k["kicad"]["sayilar"]["drc"], 0)
        self.assertEqual(k["kicad"]["sayilar"]["erc"], 0)
        self.assertEqual(k["kontroller"]["elektrik-direnc-gucu"], "kaldi")
        self.assertEqual(k["durum"], "kaldi")

    # -- durum ayrimi ve onbellek -------------------------------------------

    def test_kicad_cli_calismazsa_arac_hatasi_basari_sayilmaz(self):
        from pcbqa.kicadcli import KicadCliError

        class Kirik:
            exe = Path("yok")

            def version(self):
                raise KicadCliError("kicad-cli yok (test)")

        k = self._temel(self.gecerli, "kicadsiz", cli=Kirik())
        self.assertEqual(k["kontroller"]["kicad-erc"], "arac-hatasi")
        self.assertEqual(k["durum"], "arac-hatasi")
        self.assertFalse(k["egitim"]["aktarilabilir"])
        self.assertIsNone(k["egitim"]["etiket"])

    def test_ngspice_calismazsa_arac_hatasi(self):
        from pcbqa.dogrulama.sonuc import SeviyeSonucu

        def calismayan(g, **kw):
            s = SeviyeSonucu(3, "sahte")
            s.calisti = False
            s.atlanma_nedeni = "ngspice bulunamadi (test)"
            return s

        k = self._temel(self.gecerli, "ngspicesiz", benzetim=calismayan)
        self.assertEqual(k["kontroller"]["elektrik-benzetim"], "arac-hatasi")
        self.assertEqual(k["kontroller"]["kicad-drc"], "gecti")
        self.assertEqual(k["durum"], "arac-hatasi")
        self.assertFalse(k["egitim"]["aktarilabilir"])

    def test_onbellek_ayni_girdide_kullanilir_kosul_degisince_gecersiz(self):
        kok = self.tmp / "ob"
        r1 = P.deney(self.gecerli.klasor, kok / "a", en_fazla=0)["kayitlar"][0]
        shutil.copytree(kok / "a" / "onbellek", kok / "b" / "onbellek")
        r2 = P.deney(self.gecerli.klasor, kok / "b", en_fazla=0)["kayitlar"][0]
        self.assertFalse(r1["onbellekten"])
        self.assertTrue(r2["onbellekten"])
        self.assertEqual(r1["onbellek_anahtari"], r2["onbellek_anahtari"])
        kos = json.loads((self.gecerli.klasor / "kosullar.json").read_text())
        kos["gereksinimler"][0]["min_v"] = 2.9
        yol = self.tmp / "kosullar-dar.json"
        yol.write_text(json.dumps(kos))
        shutil.copytree(kok / "a" / "onbellek", kok / "c" / "onbellek")
        r3 = P.deney(self.gecerli.klasor, kok / "c", kosullar_yolu=yol, en_fazla=0)["kayitlar"][0]
        self.assertNotEqual(r3["onbellek_anahtari"], r1["onbellek_anahtari"])
        self.assertFalse(r3["onbellekten"])
        self.assertEqual(r3["kontroller"]["elektrik-gereksinim"], "kaldi")


if __name__ == "__main__":
    unittest.main()
