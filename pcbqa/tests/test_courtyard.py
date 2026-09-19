"""Courtyard okuma ve cakisma geometrisi.

Bu dosyadaki testlerin tamami Evre 3a'da UCTAN UCA bir uretim kosumu
sirasinda bulunan iki gercek olcum hatasini koruyor. Ikisi de sessizdi:
kimse hata vermiyordu, olcum yalnizca YANLIS cevap veriyordu.

  1. `fp_rect` ile cizilen courtyard'lar DUSUYORDU. Sekil iki kosegen
     kosesini sakliyor; okuyucu iki noktayi poligon sayamayip atiyordu.
     Etkilenen: 0603/0805 gibi en yaygin pasifler - yani hemen her kartin
     bilesenlerinin cogu COURTYARD'SIZ goruluyordu.

  2. ICBUKEY courtyard'lar dısbukey kabuga cevriliyor, sonra SAT ile
     sinaniyordu. Ikisi de L bicimli bir konnektorun BOSLUGUNU dolu sayar.
     `pic_programmer`da P3 konnektorunun L'sinin bosluguna oturan C7
     "cakisiyor" cikiyordu; KiCad'in kendi DRC'si ayni kartta sifir ihlal
     buluyor.

Hakem her iki durumda da KiCad'in kendi DRC'si oldu.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pcbqa import geom
from pcbqa.pcb import read_board
from pcbqa.sexpr import parse_with_stats

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
SOUND_BOARD = SAMPLES / "pic_programmer" / "pic_programmer.kicad_pcb"

# Courtyard'i tek bir fp_rect ile cizilmis bir footprint (0603 gelenegi)
RECT_FOOTPRINT = """(footprint "C_0603"
\t(at 0 0)
\t(fp_rect (start -1.48 -0.73) (end 1.48 0.73)
\t\t(stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))
\t(pad "1" smd roundrect (at -0.7875 0) (size 0.875 0.95) (layers "F.Cu"))
)"""

# Ayni courtyard, dort ayri fp_line olarak (ve dosyada KARISIK sirada)
LINE_FOOTPRINT = """(footprint "C_0603_lines"
\t(at 0 0)
\t(fp_line (start 1.48 -0.73) (end 1.48 0.73) (layer "F.CrtYd"))
\t(fp_line (start -1.48 -0.73) (end 1.48 -0.73) (layer "F.CrtYd"))
\t(fp_line (start -1.48 0.73) (end -1.48 -0.73) (layer "F.CrtYd"))
\t(fp_line (start 1.48 0.73) (end -1.48 0.73) (layer "F.CrtYd"))
)"""

# L bicimli (icbukey) courtyard: sag alt ceyrek BOS
L_FOOTPRINT = """(footprint "L_shape"
\t(at 0 0)
\t(fp_line (start 0 0) (end 10 0) (layer "F.CrtYd"))
\t(fp_line (start 10 0) (end 10 4) (layer "F.CrtYd"))
\t(fp_line (start 10 4) (end 4 4) (layer "F.CrtYd"))
\t(fp_line (start 4 4) (end 4 10) (layer "F.CrtYd"))
\t(fp_line (start 4 10) (end 0 10) (layer "F.CrtYd"))
\t(fp_line (start 0 10) (end 0 0) (layer "F.CrtYd"))
)"""


def _courtyard(text: str) -> list[tuple[float, float]]:
    from pcbqa.pcb import _read_courtyard_local

    root, stray = parse_with_stats(text)
    assert stray == 0
    return _read_courtyard_local(root)


class CourtyardReadTests(unittest.TestCase):
    def test_rect_courtyard_becomes_four_corners(self):
        """Iki kosegen kose dort koseye acilmali - yoksa sekil dusuyordu."""
        poly = _courtyard(RECT_FOOTPRINT)
        self.assertEqual(len(poly), 4)
        self.assertAlmostEqual(geom.area(poly), 2.96 * 1.46, places=6)

    def test_lines_in_any_order_give_the_same_rectangle(self):
        rect = _courtyard(RECT_FOOTPRINT)
        lines = _courtyard(LINE_FOOTPRINT)
        self.assertEqual(sorted(rect), sorted(lines))

    def test_concave_courtyard_keeps_its_notch(self):
        """L bicimli courtyard dısbukey kabuga cevrilmemeli."""
        poly = _courtyard(L_FOOTPRINT)
        self.assertEqual(len(poly), 6)
        # Dısbukey kabuk 100 mm2 verirdi; gercek L 64 mm2.
        self.assertAlmostEqual(geom.area(poly), 64.0, places=6)
        # Bosluktaki bir nokta ICERIDE sayilmamali
        self.assertFalse(geom.contains(poly, (8.0, 8.0)))
        self.assertTrue(geom.contains(poly, (2.0, 2.0)))

    def test_shape_without_courtyard_is_empty(self):
        poly = _courtyard('(footprint "bos" (at 0 0) (pad "1" smd rect (at 0 0)))')
        self.assertEqual(poly, [])


class OverlapTests(unittest.TestCase):
    def setUp(self):
        self.l_shape = _courtyard(L_FOOTPRINT)

    def test_shape_in_the_notch_does_not_overlap(self):
        """Icbukey boslukta duran kucuk bir sekil cakismaz."""
        small = [(6.0, 6.0), (8.0, 6.0), (8.0, 8.0), (6.0, 8.0)]
        self.assertFalse(geom.overlap(self.l_shape, small))
        self.assertGreater(geom.distance(self.l_shape, small), 0.0)

    def test_shape_on_the_arm_overlaps(self):
        small = [(1.0, 1.0), (3.0, 1.0), (3.0, 3.0), (1.0, 3.0)]
        self.assertTrue(geom.overlap(self.l_shape, small))
        self.assertEqual(geom.distance(self.l_shape, small), 0.0)

    def test_fully_contained_shape_overlaps(self):
        """Kenarlar kesismese de icerme cakismadir."""
        inner = [(1.0, 1.0), (2.0, 1.0), (2.0, 2.0), (1.0, 2.0)]
        self.assertTrue(geom.overlap(self.l_shape, inner))

    def test_touching_edges_do_not_overlap(self):
        """Bitisik duran iki courtyard cakismis sayilmaz (clearance_mm: 0.0)."""
        a = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
        b = [(2.0, 0.0), (4.0, 0.0), (4.0, 2.0), (2.0, 2.0)]
        self.assertFalse(geom.overlap(a, b))

    def test_separated_shapes_do_not_overlap(self):
        a = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        b = [(5.0, 5.0), (6.0, 5.0), (6.0, 6.0), (5.0, 6.0)]
        self.assertFalse(geom.overlap(a, b))
        self.assertAlmostEqual(geom.distance(a, b), (4**2 + 4**2) ** 0.5, places=6)


class SoundBoardTests(unittest.TestCase):
    """Gercek kartta olculen iki degismez."""

    def test_passives_have_courtyards(self):
        """0603/0805 pasifler courtyard tasimali - dusuyorlardi."""
        board = read_board(SOUND_BOARD)
        passives = [c for c in board.components if c.ref.startswith(("C", "R"))]
        self.assertTrue(passives)
        without = [c.ref for c in passives if not c.courtyard_poly]
        self.assertEqual(without, [], f"courtyard'siz pasif: {without}")

    def test_concave_connector_does_not_touch_its_neighbour(self):
        """P3'un L bicimli courtyard'i, boslugundaki C7 ile cakismaz.

        KiCad'in kendi DRC'si bu kartta sifir ihlal buluyor; dısbukey kabuk
        kullanildiginda burada yanlis alarm cikiyordu.
        """
        board = read_board(SOUND_BOARD)
        p3, c7 = board.by_ref("P3"), board.by_ref("C7")
        self.assertIsNotNone(p3)
        self.assertIsNotNone(c7)
        self.assertGreater(len(p3.courtyard_poly), 4, "L bicimi korunmali")
        self.assertFalse(geom.overlap(p3.courtyard_poly, c7.courtyard_poly))



class PadAngleTests(unittest.TestCase):
    """Pad acisi dosyada MUTLAKTIR; footprint donmesiyle toplanmaz.

    Okuyucu `footprint_donmesi + kayitli_aci` hesapliyordu. KiCad bir
    footprint'i dondururken donmeyi zaten her pad'in acisina isliyor, yani
    toplama donmeyi CIFT sayiyordu. Dikdortgen pad'ler 180 derece simetrik
    oldugu icin hata 90/270 donmus bilesenlerde gorunur hale geliyor ve
    bakir aciklik olcumunu (pad seklinin yonu) yanlislastiriyordu.
    """

    def test_rotated_component_pads_keep_the_board_angle(self):
        board = read_board(SOUND_BOARD)
        rotated = [c for c in board.components if c.rotation and c.pads]
        self.assertTrue(rotated)
        for comp in rotated:
            for pad in comp.pads:
                self.assertLess(
                    abs(pad.angle) % 360.0, 360.0,
                    f"{comp.ref}.{pad.number} acisi tur disina tasmis: {pad.angle}",
                )
        u2 = board.by_ref("U2")
        self.assertEqual(u2.rotation, 90.0)
        self.assertEqual({p.angle for p in u2.pads}, {90.0})

    def test_pads_stay_inside_their_courtyard(self):
        """Konum donmesi ile aci donmesi karistirilmamali."""
        board = read_board(SOUND_BOARD)
        disarida = []
        for comp in board.components:
            if not comp.courtyard_poly:
                continue
            x0, y0, x1, y1 = geom.bbox(comp.courtyard_poly)
            for pad in comp.pads:
                if not (x0 - 0.6 <= pad.x <= x1 + 0.6 and y0 - 0.6 <= pad.y <= y1 + 0.6):
                    disarida.append(f"{comp.ref}.{pad.number}")
        self.assertEqual(disarida, [], f"courtyard disina dusen pad: {disarida[:5]}")

if __name__ == "__main__":
    unittest.main()
