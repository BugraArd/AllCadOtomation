"""Bakir okuma: yonlendirilmis iz ve via'lar.

Akim tasima kurallari (iz genisligi, via akimi) yalnizca YONLENDIRILMIS
kartlarda anlamli. Bu yuzden iki durum da test edilir: yonlendirilmis
pic_programmer ve henuz yonlendirilmemis bench kartlari.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pcbqa.pcb import read_board

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
ROUTED = SAMPLES / "pic_programmer" / "pic_programmer.kicad_pcb"
UNROUTED = SAMPLES / "bench_bad.kicad_pcb"


class CopperReadTests(unittest.TestCase):
    def test_routed_board_has_tracks(self):
        board = read_board(ROUTED)
        self.assertGreater(len(board.tracks), 50)
        for track in board.tracks:
            self.assertGreater(track.width, 0.0, "iz genisligi pozitif olmali")
            self.assertTrue(track.layer, "iz bir katmanda olmali")

    def test_track_net_names_match_pads(self):
        """Iz net ADI tasimali; pad'lerle ayni isim uzayinda olmali.

        (net 5 "VCC") ve (net "VCC") bicimlerinin ikisinde de ad son elemandir.
        Isimler pad'lerle ortusmezse akim kurallari netleri eslestiremez.
        """
        board = read_board(ROUTED)
        pad_nets = {pad.net for comp in board.components for pad in comp.pads if pad.net}
        track_nets = {t.net for t in board.tracks if t.net}
        self.assertTrue(track_nets)
        self.assertTrue(
            track_nets & pad_nets,
            f"iz netleri pad netleriyle kesismiyor: {sorted(track_nets)[:5]}",
        )

    def test_vias_have_size_and_drill(self):
        board = read_board(ROUTED)
        self.assertTrue(board.vias)
        for via in board.vias:
            self.assertGreater(via.drill, 0.0)
            self.assertGreaterEqual(via.size, via.drill, "pad capi delikten kucuk olamaz")

    def test_outer_layer_detection(self):
        board = read_board(ROUTED)
        outer = [t for t in board.tracks if t.is_outer]
        self.assertTrue(outer, "iki katli kartta dis katman izi olmali")
        for track in outer:
            self.assertIn(track.layer, ("F.Cu", "B.Cu"))

    def test_track_length(self):
        board = read_board(ROUTED)
        total = sum(t.length_mm for t in board.tracks)
        self.assertGreater(total, 0.0)

    def test_unrouted_board_reports_empty(self):
        """Yonlendirilmemis kart: bos liste, hata degil."""
        board = read_board(UNROUTED)
        self.assertEqual(board.tracks, [])
        self.assertEqual(board.vias, [])
        self.assertTrue(board.components, "bilesenler yine de okunmali")


if __name__ == "__main__":
    unittest.main()
