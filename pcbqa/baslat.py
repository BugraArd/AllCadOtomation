r"""Onyukleyici - KiCad'in Python'u `PYTHONPATH`'i YOK SAYAR, bu yuzden var.

(Belge dizgesi HAM: icinde Windows yollari geciyor ve `...\pcbqa` gibi bir
dizi Python 3.12+ tarafindan gecersiz kacis dizisi sayilip her calistirmada
`SyntaxWarning` bastiriyordu - kullanicinin gordugu ilk sey oydu.)

Olculmus sebep: KiCad kendi yorumlayicisina bir `sitecustomize.py` koyuyor ve
orada su satir var (KiCad 10.0.4, bin/Lib/site-packages/sitecustomize.py):

    in_venv = sys.prefix != sys.base_prefix
    if not in_venv:
        sys.path = []

Yani site asamasinda `sys.path` KOMPLE silinip yeniden kuruluyor. Silinenler
arasinda `PYTHONPATH` girdileri de var. Olcum:

    set PYTHONPATH=...\pcbqa
    python.exe -c "import sys; print(sys.path)"
    -> ['', DLLs, Lib, site-packages, 3rdparty]      # pcbqa YOK

Bu yuzden baslatici `PYTHONPATH` ile paketi bulduramaz. Onun yerine paketin
YANINDA duran bu dosya calistirilir: CPython betigin bulundugu klasoru site'dan
SONRA `sys.path[0]`'a koydugu icin silinmeden kurtulur. Yine de asagida acikca
ekliyoruz - siralamaya degil, kendi bildigimiz yola guveniyoruz.

Once bu yoktu ve baslatici `python -m pcbqa.app` cagiriyordu; o yalnizca
CALISMA DIZINI paket klasoruyken calisiyordu, cunku `-m` de cwd'yi site'dan
sonra ekliyor. Baska bir klasorden "No module named pcbqa" veriyordu.
"""

import os
import sys

_HOME = os.path.dirname(os.path.abspath(__file__))
if _HOME not in sys.path:
    sys.path.insert(0, _HOME)

from pcbqa.app import main  # noqa: E402  (yol ayarlandiktan SONRA)

if __name__ == "__main__":
    raise SystemExit(main())
