# Kicad baglanti yollari

> Beads kalici hafizasi (`bd recall kicad-baglanti-yollari`). Kaynak Dolt veritabani;
> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.

KICAD'E BAGLANMA VE DAGITIM (2026-08-28'de olculdu, urun sekli KARARLASTIRILDI)

URUN SEKLI: BAGIMSIZ UYGULAMA (kullanici sectiler, 2026-08-28).
'Bagimsiz' = AYRI PYTHON KURULUMU GEREKTIRMEZ. 'KiCad'siz calisir' DEGIL -
kicad-cli ve sembol/footprint kutuphaneleri zorunlu. KiCad kendi python
3.11.5'ini getirdigi ve pcbqa'nin calisma zamani bagimliligi olmadigi icin
ikinci yorumlayici gomme / PyInstaller GEREKSIZ (daha buyuk, kirilgan,
AV uyarilari; kazanc sifir). Dagitim = klasor + pcbqa.cmd.
  Giris: pcbqa/app.py (alt komutlar mevcut modullerin main()'ini cagirir)
  Baslatici: pcbqa.cmd (KiCad python'unu kendi bulur, PCBQA_PYTHON ezer)
  Ilk komut her zaman: pcbqa tani  (ortam denetimi, engelde cikis kodu 1)
  Kullanici belgesi: KURULUM.md

UC BAGLANTI YOLU:
 1. DOSYA TABANLI (uret, kesfet, yerlestir): KiCad ayari gerekmez. KiCad
    ACIKKEN reddeder (~*.lck kilidi) - koruma bilincli.
 2. SUREC-ICI / API'SIZ (swig_apply.py): KiCad'in kendi python'unda pcbnew
    (SWIG) ile. Ayar gerekmez. 'pcbqa uygula' bunu kullanir.
 3. IPC (ipc.py): API sunucusu KiCad'de VARSAYILAN KAPALI
    (kicad_common.json api.enable_server=false) - DAGITIMDA KULLANMA.
    'pcbqa uygula-ipc' olarak durur.

YORUMLAYICI AYRIMI:
    KiCad 10.0 python 3.11.5 : pcbnew VAR, pyyaml YOK
    proje .venv    python 3.13 : pcbnew YOK, pyyaml VAR

YAML SORUNU VE COZUMU (uc katman):
  confload.py sirasi: .json -> pyyaml -> minyaml -> .json esi -> hata.
  minyaml KAYNAGI okudugu icin uretilmis kopyadan ONCE gelir.
  bundle.py paketin kendi dosyalarinin JSON kopyalarini uretir (emniyet agi).
  minyaml.py BAGIMLILIKSIZ YAML okuyucu - kullanicinin KENDI dosyasi icin sart
  ('once JSON'a cevir' kabul edilemez). Desteklenmeyen yapida (capa, cok
  satirli, etiket, ---, sekme) HATA ATAR, tahmin etmez.

MINYAML'A NEDEN GUVENILIYOR: PyYAML ile DIFERANSIYEL TEST (21/21 dosya,
26/26 skaler birebir). Test yazilir yazilmaz IKI GERCEK AYRISMA buldu:
1e3 PyYAML'de METIN (us icin isaret zorunlu), %50 gecersiz YAML.
YAML 1.1 TUZAKLARI birebir taklit edildi (PyYAML'in cozumleyici desenleri
kopyalandi): 012=10 ve 0603=387 SEKIZLIK, 0805 METIN, 1:30=90 altmislik,
1_000=1000. Bunlari 'duzeltmek' iki ortamda iki farkli kural yuklerdi.
minyaml'i degistirirken tests/test_minyaml.py'yi MUTLAKA kosun.

YAN DUZELTME: karta yazmada acik-proje kilidi korumasi YOKTU (sematikte
vardi). harness.write_board'a eklendi - generate/explore/yerlestir'i birden
korur.
