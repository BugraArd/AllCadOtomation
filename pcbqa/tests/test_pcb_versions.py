"""Dosya surumu uyumlulugu: KiCad 5 "module" ve sayisal net referanslari.

Iki P0 hata birlikte bulundu (2026-08-28, ayrik buck karti aranirken):

  1. KiCad 5 footprint dugumune "(module ...)" der ve referansi
     "(fp_text reference U1 ...)" icinde tutar. Ayristirici yalnizca
     "footprint" + "property" taniyordu: 43 modullu gercek bir kart SIFIR
     bilesenle okunuyor, parse_warnings 0 kaliyor ve skor 100 cikiyordu.
     "Kartiniz kusursuz" - sessiz hata sinifinin en genis ornegi.

  2. Iz/via dugumleri neti yalnizca NUMARAYLA tasir: "(net 2)". Ad kokteki
     tabloda: "(net 2 "+3.3V")". Bu KiCad 5'te de 9'da da boyle. _node_net
     son elemani aldigi icin iz netleri "2" oluyordu ve net ADINA gore calisan
     kurallar (trace_width, via_current, copper_area'nin track kaynagi)
     HICBIR kartta eslesmiyordu - 7932 izli kartta "yonlendirilmis iz yok".

Buradaki sentetik dosyalar bilerek kucuk: her biri tek bir davranisi sabitler.
Gercek kart dogrulamasi ayrica asagida (KiCad demolari kuruluysa).
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pcbqa.pcb import BoardParseError, read_board

DEMOS = Path(r"C:\Program Files\KiCad\10.0\share\kicad\demos")
VIDEO = DEMOS / "video" / "video.kicad_pcb"

# KiCad 5.1'in gercek bicimi (lm5116 kartindan sadelestirildi):
# module + fp_text reference/value + pad'de (net N AD) + segment'te (net N).
KICAD5 = """(kicad_pcb (version 20171130) (host pcbnew "(5.1.8)-1")
  (net 0 "")
  (net 1 GND)
  (net 2 VIN)
  (module Lib:SOT23 (layer F.Cu) (tedit 0) (tstamp 1)
    (at 100 100)
    (fp_text reference Q1 (at 0 -2) (layer F.SilkS)
      (effects (font (size 1 1) (thickness 0.15)))
    )
    (fp_text value FET (at 0 2) (layer F.Fab)
      (effects (font (size 1 1) (thickness 0.15)))
    )
    (pad 1 smd rect (at -1 0) (size 0.6 0.6) (layers F.Cu F.Paste F.Mask)
      (net 2 VIN))
    (pad 2 smd rect (at 1 0) (size 0.6 0.6) (layers F.Cu F.Paste F.Mask)
      (net 1 GND))
  )
  (segment (start 100 100) (end 105 100) (width 0.25) (layer F.Cu) (net 2))
  (via (at 105 100) (size 0.8) (drill 0.4) (layers F.Cu B.Cu) (net 2))
)
"""

# Ayni iskelet ama footprint'ler taninmayan bir bicimde: dugum var, referans
# cozulemiyor. Sessiz "0 bilesen" yerine GURULTULU hata bekliyoruz.
KICAD_UNREADABLE = """(kicad_pcb (version 99999999)
  (net 0 "")
  (module Lib:X (layer F.Cu)
    (at 10 10)
  )
  (module Lib:Y (layer F.Cu)
    (at 20 20)
  )
)
"""


def write_tmp(tmpdir: Path, name: str, text: str) -> Path:
    p = tmpdir / name
    p.write_text(text, encoding="utf-8")
    return p


class KiCad5Tests(unittest.TestCase):
    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_module_nodes_are_read_as_components(self):
        board = read_board(write_tmp(self.tmp, "k5.kicad_pcb", KICAD5))
        self.assertEqual([c.ref for c in board.components], ["Q1"])
        self.assertEqual(board.components[0].value, "FET")
        self.assertEqual(
            sorted(p.net for p in board.components[0].pads), ["GND", "VIN"]
        )

    def test_numeric_track_and_via_nets_resolve_through_the_root_table(self):
        board = read_board(write_tmp(self.tmp, "k5.kicad_pcb", KICAD5))
        self.assertEqual([t.net for t in board.tracks], ["VIN"])
        self.assertEqual([v.net for v in board.vias], ["VIN"])

    def test_unreadable_footprints_fail_loudly_not_silently(self):
        """Dosyada footprint VAR ama hicbiri okunamiyorsa bu ayristirici
        hatasidir. Sessiz "0 bilesen" butun kurallari susturur ve skoru 100
        gosterir - kabul edilemez."""
        p = write_tmp(self.tmp, "bad.kicad_pcb", KICAD_UNREADABLE)
        with self.assertRaisesRegex(BoardParseError, "hicbiri okunamadi"):
            read_board(p)

    def test_a_board_with_no_footprints_at_all_is_not_an_error(self):
        """Bos kart (henuz bilesen konmamis) mesru bir ara durumdur."""
        p = write_tmp(self.tmp, "empty.kicad_pcb", '(kicad_pcb (version 1)\n  (net 0 "")\n)\n')
        board = read_board(p)
        self.assertEqual(board.components, [])


@unittest.skipUnless(VIDEO.is_file(), "KiCad demolari kurulu degil")
class RealBoardNetResolutionTests(unittest.TestCase):
    """video.kicad_pcb: 7932 iz, duzeltmeden once HEPSI sayisal net tasiyordu."""

    @classmethod
    def setUpClass(cls):
        cls.board = read_board(VIDEO)

    def test_no_track_is_left_with_a_numeric_net(self):
        numeric = [t.net for t in self.board.tracks if t.net.isdigit()]
        self.assertEqual(numeric, [], f"sayisal iz neti kaldi: {numeric[:5]}")
        self.assertGreater(len(self.board.tracks), 1000, "iz sayisi supheli az")

    def test_no_via_is_left_with_a_numeric_net(self):
        numeric = [v.net for v in self.board.vias if v.net.isdigit()]
        self.assertEqual(numeric, [])

    def test_track_copper_now_contributes_to_named_net_area(self):
        # Duzeltmeden once 0.0 idi - iz bakiri hicbir nete sayilmiyordu.
        self.assertGreater(self.board.copper_area_mm2("+5V", sources=("track",)), 0.0)


if __name__ == "__main__":
    unittest.main()
