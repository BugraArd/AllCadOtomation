"""Uc seviyeli devre dogrulamasi.

  Seviye 1 - KiCad'in kendi kontrolleri (kicad-cli): ERC, PCB DRC + sematik
             paritesi, netlist disa aktarimi.
  Seviye 2 - Muhendislik kurallari: parcaya ve devrenin amacina bagli
             (asiri gerilim, regulator kosullari, gate surme, pull-up /
             dekuplaj / serbest gecis diyotu, direnc gucu, kondansator
             gerilimi).
  Seviye 3 - Benzetim (ngspice): ERC'den gecen bir devre yine de yanlis
             calisabilir; netlist + test kosulu + calistir + gereksinimle
             karsilastir; tolerans, sicaklik, yaslanma.

Uc seviye ayri ayri calisabilir; her biri `SeviyeSonucu` dondurur ve
bulgulari mevcut `rules.Finding` bicimindedir (rapor/skor ayni kalir).
"""

from .sonuc import SeviyeSonucu, bulgu, eksik_bulgu

__all__ = ["SeviyeSonucu", "bulgu", "eksik_bulgu"]
