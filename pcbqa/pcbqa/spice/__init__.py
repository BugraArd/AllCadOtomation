"""ngspice entegrasyonu: devre grafindan netlist, test kosullari, calistirma.

Ilk surum bilincli olarak DC calisma noktasi (op) senaryolarina odaklanir:
nominal, tolerans (Monte Carlo + koseler), sicaklik ve modellenmis yaslanma.
Aktif parcalarin cogu davranissal/ideal modelle girer ve bu raporda acikca
yazilir. Gelecek plani: Kicad-5d6.5 (SPICE gelistirilmeli).
"""

from .calistir import ArkaUc, SpiceHatasi, arka_uc_bul, calistir, wrdata_oku
from .netlist import SpiceDevresi, devre_kur

__all__ = ["ArkaUc", "SpiceHatasi", "arka_uc_bul", "calistir", "wrdata_oku",
           "SpiceDevresi", "devre_kur"]
