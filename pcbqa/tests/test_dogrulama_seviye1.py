"""Seviye 1: kicad-cli ERC / DRC (sematik paritesi) / netlist, uygulamanin icinden."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pcbqa.dogrulama.seviye1 import seviye1
from pcbqa.kicadcli import CliResult, KicadCli, KicadCliError

ROOT = Path(__file__).resolve().parents[1]
PIC = ROOT / "samples" / "pic_programmer"


def kicad_var() -> bool:
    try:
        KicadCli()
        return True
    except KicadCliError:
        return False


class DrcParitesiTests(unittest.TestCase):
    def test_parite_bayragi_komuta_gecer(self):
        with mock.patch("pcbqa.kicadcli.find_kicad_cli", return_value=Path("kicad-cli")):
            cli = KicadCli()
        with mock.patch.object(KicadCli, "_run", return_value=CliResult(True, None, "", "", 0)) as run:
            cli.drc(Path("k.kicad_pcb"), Path(tempfile.gettempdir()) / "d.json", schematic_parity=True)
            self.assertIn("--schematic-parity", run.call_args[0][0])
            cli.drc(Path("k.kicad_pcb"), Path(tempfile.gettempdir()) / "d.json")
            self.assertNotIn("--schematic-parity", run.call_args[0][0])

    def test_dosya_yoksa_atlanir(self):
        s = seviye1(None, None, Path(tempfile.gettempdir()))
        self.assertFalse(s.calisti)
        self.assertIsNone(s.gecti)


@unittest.skipUnless(kicad_var() and PIC.is_dir(), "kicad-cli ya da ornek proje yok")
class GercekKicadTests(unittest.TestCase):
    def test_pic_programmer(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = seviye1(PIC / "pic_programmer.kicad_sch", PIC / "pic_programmer.kicad_pcb", Path(tmp))
            self.assertTrue(s.calisti)
            self.assertTrue(s.ekler["parite_denetlendi"])
            self.assertTrue(Path(s.ekler["netlist"]).is_file())
            self.assertTrue(Path(s.ekler["erc"]).is_file())
            self.assertTrue(Path(s.ekler["drc"]).is_file())
        kaynaklar = {f.source for f in s.bulgular}
        self.assertTrue(kaynaklar <= {"kicad-erc", "kicad-drc", "kicad-parite", "kicad-cli"})


if __name__ == "__main__":
    unittest.main()
