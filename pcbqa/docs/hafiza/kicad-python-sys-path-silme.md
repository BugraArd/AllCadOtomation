# Kicad python sys path silme

> Beads kalici hafizasi (`bd recall kicad-python-sys-path-silme`). Kaynak Dolt veritabani;
> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.

KiCad'in Python'u PYTHONPATH'i YOK SAYAR - olculmus, 2026-08-30

C:\Program Files\KiCad\10.0\bin\Lib\site-packages\sitecustomize.py icinde:
    in_venv = sys.prefix != sys.base_prefix
    if not in_venv:
        sys.path = []
Sonra site.addsitedir ile DLLs / Lib / Lib-site-packages / 3rdparty ekleniyor.

SONUCLARI:
1) PYTHONPATH ise YARAMAZ. Olcum: set PYTHONPATH=<paket> + python -c print(sys.path)
   -> paket yolu listede YOK.
2) -m ve -c icin cwd, ve betik calistirmada betigin klasoru sys.path[0]'a
   site'DAN SONRA eklenir, yani silmeden KURTULUR.
3) Bir venv icindeysek (sys.prefix != sys.base_prefix) silme HIC olmaz; bu
   yuzden .venv ile kosan gelistirme testleri sorunu hic gormedi.

BIZDEKI KULLANIMI: pcbqa.cmd artik 'python -m pcbqa.app' DEGIL, paketin
yanindaki baslat.py'yi calistiriyor. Ayni tuzak tests/test_swig_bridge.py
run_in_kicad icinde de vardi.

KURAL: KiCad'in yorumlayicisina paket gostermek icin PYTHONPATH KULLANMA;
ya betigi paketin yaninda tut ya da betik icinde sys.path.insert yap.
