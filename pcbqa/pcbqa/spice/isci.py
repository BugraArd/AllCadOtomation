"""ngspice paylasimli kutuphanesini (KiCad'in ngspice.dll'i) AYRI SURECTE kosturur.

    python isci.py --dll "C:/Program Files/KiCad/10.0/bin/ngspice.dll" devre.cir

Neden ayri surec ("yan uygulama"):
  * ngspice hata durumunda surecin kendisini sonlandirabilir (controlled
    exit) ya da kilitlenebilir; ana uygulama bunu zaman asimiyla keser.
  * paylasimli kutuphane surec basina bir kez yuklenir ve durum tasir;
    her benzetim taze bir surecte temiz baslar.

BU DOSYA BILEREK BAGIMSIZDIR (yalnizca stdlib): KiCad'in Python'u sys.path'i
siler (bkz. kicad-python-sys-path-silme) ve dosya dogrudan yoluyla
calistirilir; pcbqa paketini ice aktarmaz.

Lisans notu: ngspice'in ana lisansi degistirilmis (3 maddeli) BSD'dir
(ayrintilar ngspice kaynagindaki COPYING dosyasinda). pcbqa onu DAGITMAZ;
kullanicinin KiCad kurulumundaki kopyayi ayri bir surecte cagirir.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
from ctypes import CFUNCTYPE, c_bool, c_char_p, c_int, c_void_p

SendChar = CFUNCTYPE(c_int, c_char_p, c_int, c_void_p)
SendStat = CFUNCTYPE(c_int, c_char_p, c_int, c_void_p)
ControlledExit = CFUNCTYPE(c_int, c_int, c_bool, c_bool, c_int, c_void_p)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll", required=True)
    ap.add_argument("devre")
    args = ap.parse_args(argv)

    dll_klasoru = os.path.dirname(os.path.abspath(args.dll))
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(dll_klasoru)
    lib = ctypes.CDLL(args.dll)

    gunluk: list[str] = []
    cikis: dict[str, int] = {}

    def send_char(metin, _id, _veri):
        gunluk.append((metin or b"").decode("utf-8", errors="replace"))
        return 0

    def send_stat(_metin, _id, _veri):
        return 0

    def controlled_exit(durum, _bosalt, _cikis, _id, _veri):
        cikis["durum"] = int(durum)
        return 0

    geri = (SendChar(send_char), SendStat(send_stat), ControlledExit(controlled_exit))
    lib.ngSpice_Init(geri[0], geri[1], geri[2], None, None, None, None)
    yol = os.path.abspath(args.devre).replace("\\", "/")
    kod = lib.ngSpice_Command(f"source {yol}".encode("utf-8"))
    hatalar = [s for s in gunluk if s.startswith("stderr") and "spinit" not in s]
    print(json.dumps({
        "kod": int(kod),
        "cikis": cikis.get("durum"),
        "hatalar": hatalar[-20:],
        "gunluk": gunluk[-60:],
    }))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
