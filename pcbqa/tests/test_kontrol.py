"""`pcbqa kontrol` - analiz + dogrulama tek kosuda (Kicad-5d6.11).

Korunan iddia: birlestirme SKORU DEGISTIRMEZ. Seviye 1'in `--schematic-parity`
ile kosulmus DRC raporu kalite skoruna verilirken parite grubu atlanir; skor
ve bulgu kumesi `pcbqa analiz` ile birebir ayni kalmalidir (pic_programmer'da
olculdu: 45,2 = 45,2). Gercek kicad-cli / ngspice gerektiren siniflar araclar
yoksa ATLANIR - atlanan test gecti sayilmaz.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from pcbqa import __main__ as ana
from pcbqa import kontrol
from pcbqa.spice import arka_uc_bul

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
PIC = SAMPLES / "pic_programmer"
BOLUCU = SAMPLES / "bolucu" / "referans" / "bolucu-hatali"


def _kicad_cli_var() -> bool:
    try:
        from pcbqa.kicadcli import find_kicad_cli

        return find_kicad_cli().is_file()
    except Exception:
        return False


KICAD = _kicad_cli_var()


def _ozet(klasor: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(klasor.iterdir()) if p.is_file()}


class BirimTestleri(unittest.TestCase):
    """Arac gerektirmez."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-kontrol-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _dogrulama(self, ekler: dict, calisti: bool = True) -> dict:
        return {"seviyeler": [{"seviye": 1, "calisti": calisti, "ekler": ekler}]}

    def test_seviye1_raporu_eksiksizse_yeniden_kullanilir(self):
        erc, drc = self.tmp / "erc.json", self.tmp / "drc.json"
        erc.write_text("{}", encoding="utf-8")
        drc.write_text("{}", encoding="utf-8")
        self.assertEqual(kontrol._seviye1_raporlari(self._dogrulama({"erc": str(erc), "drc": str(drc)})),
                         (erc, drc))

    def test_eksik_ya_da_calismamis_seviye1_kullanilmaz(self):
        """Eksik rapor skoru sessizce eksik birakmasin: analiz kendi ERC/DRC'sini kosar."""
        drc = self.tmp / "drc.json"
        drc.write_text("{}", encoding="utf-8")
        self.assertIsNone(kontrol._seviye1_raporlari(None))
        self.assertIsNone(kontrol._seviye1_raporlari({"seviyeler": []}))
        self.assertIsNone(kontrol._seviye1_raporlari(self._dogrulama({"drc": str(drc)}, calisti=False)))
        self.assertIsNone(kontrol._seviye1_raporlari(self._dogrulama({"erc": None, "drc": str(drc)})))
        self.assertIsNone(kontrol._seviye1_raporlari(self._dogrulama({"drc": str(self.tmp / "yok.json")})))
        # sematik yoksa ERC hic kosmaz (anahtar yok) - yalniz DRC yeterli
        self.assertEqual(kontrol._seviye1_raporlari(self._dogrulama({"drc": str(drc)})), (None, drc))

    def test_parite_grubu_kalite_skorundan_atlanir(self):
        drc = self.tmp / "drc.json"
        drc.write_text(json.dumps({
            "violations": [{"type": "clearance", "severity": "error", "description": "aciklik"}],
            "unconnected_items": [],
            "schematic_parity": [{"type": "missing_footprint", "severity": "warning", "description": "parite"}],
        }), encoding="utf-8")
        hepsi = ana.kicad_findings(drc, "kicad-drc")
        paritesiz = ana.kicad_findings(drc, "kicad-drc", skip_groups=("schematic_parity",))
        self.assertEqual(len(hepsi), 2)
        self.assertEqual([f.rule_id for f in paritesiz], ["clearance"])

    def test_olmayan_proje_cli_kodu_2(self):
        tampon = io.StringIO()
        with contextlib.redirect_stderr(tampon), contextlib.redirect_stdout(io.StringIO()):
            kod = kontrol.main([str(self.tmp / "yok")])
        self.assertEqual(kod, 2)
        self.assertIn("hata", tampon.getvalue())


@unittest.skipUnless(KICAD, "kicad-cli yok - birlestirme esitligi OLCULMEDI")
class GercekKicadTestleri(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="pcbqa-kontrol-"))
        cls.proje = cls.tmp / "pic"
        shutil.copytree(PIC, cls.proje)
        cls.once = _ozet(cls.proje)
        cls.rapor = kontrol.calistir(cls.proje, None, {1, 2})
        with tempfile.TemporaryDirectory() as w:
            cls.analiz = ana.analyze(ana.build_parser().parse_args([str(cls.proje)]), Path(w))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_tek_kosu_skoru_analiz_ile_ayni(self):
        self.assertTrue(self.rapor.erc_drc_tek_kosu)
        self.assertEqual(self.rapor.skor, round(self.analiz.score, 1))

    def test_tek_kosu_bulgu_kumesi_analiz_ile_ayni(self):
        birlesik = Counter((f["source"], f["rule_id"], f["severity"], f["message"])
                           for f in self.rapor.kalite["findings"])
        ayri = Counter((f.source, f.rule_id, f.severity, f.message) for f in self.analiz.findings)
        self.assertEqual(birlesik, ayri)

    def test_seviye1_yoksa_analiz_kendi_erc_drc_sini_kosar(self):
        r = kontrol.calistir(self.proje, None, {2})
        self.assertFalse(r.erc_drc_tek_kosu)
        self.assertEqual(r.skor, round(self.analiz.score, 1))

    def test_satirlar_seviyeleri_ve_dokuz_kontrolu_icerir(self):
        gruplar = Counter(s.grup for s in self.rapor.satirlar)
        self.assertEqual(gruplar["kalite"], 1)
        self.assertEqual(gruplar["kontrol"], 9)
        self.assertEqual(gruplar["bilgi"], 1)
        # seviye 1, 2 ve PCB iz analizi (seviye 4) her zaman
        self.assertEqual(gruplar["seviye"], 3)

    def test_erc_drc_hatasi_iki_kez_sayilmaz(self):
        d = self.rapor.dogrulama
        kendi = sum(1 for f in self.rapor.kalite["findings"]
                    if f["severity"] == "error" and not f["source"].startswith("kicad-"))
        self.assertEqual(self.rapor.hata_sayisi, d["hata_sayisi"] + kendi)

    def test_kaynak_dosyalar_degismez(self):
        self.assertEqual(_ozet(self.proje), self.once)

    def test_kalite_yok_bayragi(self):
        r = kontrol.calistir(self.proje, None, {2}, kalite=False)
        self.assertIsNone(r.skor)
        self.assertNotIn("kalite", {s.grup for s in r.satirlar})


@unittest.skipUnless(KICAD and arka_uc_bul() is not None, "kicad-cli / ngspice yok - seviye 3 OLCULMEDI")
class GercekBenzetimTesti(unittest.TestCase):
    def test_hatali_bolucu_seviye3_te_kalir_cli_kodu_1(self):
        tmp = Path(tempfile.mkdtemp(prefix="pcbqa-kontrol-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        json_yol = tmp / "rapor.json"
        with contextlib.redirect_stdout(io.StringIO()):
            kod = kontrol.main([str(BOLUCU), "--kosullar", str(BOLUCU / "kosullar.json"),
                                "--json", str(json_yol)])
        self.assertEqual(kod, 1)
        r = json.loads(json_yol.read_text(encoding="utf-8"))
        s3 = next(s for s in r["satirlar"] if s["ad"].startswith("[3]"))
        self.assertEqual(s3["durum"], "KALDI")
        self.assertTrue(any("gereksinim-gerilim" in a for a in s3["ayrinti"]), s3["ayrinti"])


if __name__ == "__main__":
    unittest.main()
