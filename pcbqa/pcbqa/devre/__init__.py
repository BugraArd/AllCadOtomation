"""Ortak devre modeli (devre grafi).

Okuyucularin (sematik, netlist, kart, parca kutuphanesi, calisma kosullari)
urettigi bilgi tek bir grafikte birlesir: her bilesen hangi pinlerle hangi
aga bagli, devredeki gorevi ne, sinirlari ne, PCB'deki karsiligi nerede.

Ilke (elektrik.py ile ayni): bilinmeyen sayi UYDURULMAZ. Her alan ya
kaynagiyla birlikte bilinir ya da NEDEN bilinmedigiyle birlikte eksik
kaydedilir (bkz. bilgi.Bilgi).
"""

from .bilgi import Bilgi, bilinen, eksik
from .graf import DevreGrafi, graf_kur
from .kosullar import Kosullar, kosullari_oku
from .parca import Kutuphane, ParcaBilgisi, varsayilan_kutuphane

__all__ = [
    "Bilgi",
    "bilinen",
    "eksik",
    "DevreGrafi",
    "graf_kur",
    "Kosullar",
    "kosullari_oku",
    "Kutuphane",
    "ParcaBilgisi",
    "varsayilan_kutuphane",
]
