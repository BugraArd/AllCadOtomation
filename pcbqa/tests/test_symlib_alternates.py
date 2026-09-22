"""KiCad 10 sembol ozellikleri: alternate fonksiyonlar ve yigin pin numaralari.

Bu iki ozellik KiCad 10.0 dokumaninda tarif edilir ve kurulu kutuphanede
GERCEKTEN kullanilir. Testler kurulu KiCad'e bagimlidir; yoksa atlanir.
"""

from __future__ import annotations

import unittest

from pcbqa import symlib


class YiginGosterimiTests(unittest.TestCase):
    """Saf metin ayristirmasi - KiCad kurulumu gerekmez."""

    def test_duz_numara_degismez(self):
        self.assertEqual(symlib.expand_pin_numbers("7"), ("7",))
        self.assertEqual(symlib.expand_pin_numbers("A1"), ("A1",))

    def test_virgullu_liste(self):
        self.assertEqual(symlib.expand_pin_numbers("[2,13]"), ("2", "13"))

    def test_aralik(self):
        self.assertEqual(symlib.expand_pin_numbers("[1-3]"), ("1", "2", "3"))

    def test_karisik(self):
        # KiCad dokumani: [1-3], [1,2,3] ve [1-2,3] ayni kumedir
        self.assertEqual(
            symlib.expand_pin_numbers("[1-2,3]"), symlib.expand_pin_numbers("[1,2,3]")
        )

    def test_sayisal_olmayan_aralik_aynen_kalir(self):
        # Uydurma genisletme yapilmamali
        self.assertEqual(symlib.expand_pin_numbers("[A-B]"), ("A-B",))

    def test_bos_parantez_cokmez(self):
        self.assertEqual(symlib.expand_pin_numbers("[]"), ("[]",))


def _sembol(lib_id):
    try:
        return symlib.get_symbol(lib_id)
    except symlib.SymLibError:
        return None


class KutuphaneTests(unittest.TestCase):
    """Kurulu KiCad kutuphanesine karsi - yoksa atlanir."""

    def test_stm32_alternate_fonksiyonlari_okunuyor(self):
        s = _sembol("MCU_ST_STM32F1:STM32F103C8Tx")
        if s is None:
            self.skipTest("KiCad sembol kutuphanesi yok")
        alt = {a for p in s.pins for a in p.alternates}
        # Pin planlayicisinin ihtiyaci: tamamlayici timer cikislari, break,
        # ADC kanali, SWD. Bunlar varsa harici veri tabanina gerek yok.
        for beklenen in ("TIM1_CH1", "TIM1_CH1N", "TIM1_BKIN", "ADC1_IN0"):
            self.assertIn(beklenen, alt, f"{beklenen} okunamadi")
        self.assertTrue(any(a.startswith("SYS_JTMS") for a in alt), "SWD yok")

    def test_alternatesiz_pin_bos_demet(self):
        s = _sembol("Device:R")
        if s is None:
            self.skipTest("KiCad sembol kutuphanesi yok")
        for p in s.pins:
            self.assertEqual(p.alternates, ())

    def test_yigin_pinli_gercek_sembol(self):
        # TI step motor surucusu: 6 pini koseli parantezli
        s = _sembol("Driver_Motor:DRV8434PWP")
        if s is None:
            self.skipTest("KiCad sembol kutuphanesi yok")
        yigin = [p for p in s.pins if len(p.numbers) > 1]
        self.assertTrue(yigin, "yigin pin bulunamadi - sembol degismis olabilir")
        vm = [p for p in s.pins if p.name == "VM"]
        self.assertEqual(vm[0].numbers, ("2", "13"))
        # HAM numara korunur: semaya bu yazilir
        self.assertEqual(vm[0].number, "[2,13]")


if __name__ == "__main__":
    unittest.main()
