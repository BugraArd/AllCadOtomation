# Acik beads kayitlari

> Beads kayitlari (`bd list --json`). Her kayit bir kararin ya da
> olcumun gerekcesini tasir; kod bunlari anlatmaz.

## Kicad-204 - Arayuz + parca tablosu: arayuz.py, elektrik.py

- oncelik: P1  |  durum: open  |  tur: task

KARAR (2026-09-03): Masaustu arayuzu ve parca tablosu eklendi.
Kullanici istegi: 'kullanabilecegim bir python arayuzu yaz, islerimi o
arayuz uzerinden de gerceklestirebileyim' + 'MPN bilgisi fiyat ve ustunden
gecen amperi voltaji tablo olarak gostersin her parca icin'.

YENI MODULLER:
  pcbqa/pcbqa/arayuz.py   (CLI: pcbqa arayuz)  - tkinter, 5 sekme
  pcbqa/pcbqa/elektrik.py (CLI: pcbqa parcalar) - parca tablosu

--- OLCULMUS KISIT: KiCad'in Python'unda tkinter YOK ---
  "C:\Program Files\KiCad\10.0\bin\python.exe" -c "import tkinter"
  -> ModuleNotFoundError: No module named '_tkinter'
pcbqa.cmd yorumlayici olarak ONCE KiCad'inkini secer, yani arayuz
baslaticinin varsayilan Python'uyla ACILAMAZ. Karsilik: arayuz.main()
tkinter'i olan bir Python arar (py -3, PATH python), bulursa baslat.py
uzerinden yeniden baslatir ve NE YAPTIGINI YAZAR; bulamazsa ne yapilacagini
soyleyip CLI'ye yonlendirir. Sessizce baska yorumlayiciya gecmez.
Kullanici tkinter'i bilerek secti (secenekler sunuldu: tarayici/tkinter/API).

--- IKI ADIMLI GUVENLIK (CLI'deki --uygula'nin karsiligi) ---
'Uygula' dugmesi baslangicta KAPALI. Yalnizca AYNI cumle + AYNI proje icin
bir kuru kosum gectikten sonra acilir; cumle ya da proje degisirse kapanir;
yazdiktan sonra kapanir. _uygula() dugme gorunumune GUVENMEZ, imzayi
kendisi de dogrular. Yazmadan once onay diyalogu.

--- ELEKTRIK: NEYI BILMEDIGIMIZ ---
SPICE yok; akim genel halde turetilemez. Kural: her sayinin yaninda NEREDEN
BILINDIGI yazilir, turetilemeyen BOS kalir. Turetilebilen uc sey:
  1. RAY GERILIMI net ADINDAN: '+3V3'->3.3, '+1V8'->1.8, '-12V'->-12,
     GND ailesi 0 V (referans dugumu tanimi), VBUS 5 V (USB 2.0 spec 7.2.1).
     'VCC'/'VDD'/'VIN' HICBIR SEY soylemez -> BILINMIYOR. Bu en onemli
     karar: 'VCC 5V'tur' varsayimi 3.3 V'luk kartta yanlis akim hesaplatir.
  2. DIRENC AKIMI: iki ucun gerilimi biliniyorsa I = |dV| / R (Ohm yasasi).
  3. KONDANSATOR: kararli halde DC akim ~0 - tahmin degil, elemanin tanimi.
Digerleri (IC, diyot, LED, transistor, bobin) 'benzetim gerekir'. LED akimi
seri direncten hesaplanabilirdi ama Vf parcaya ozgu ve kutuphanede yok;
Vf uydurmak tabloyu kirletirdi.

--- BULUNAN GERCEK HATA (mpn.py) ---
_base_price degeri 0 olan parcada math.log10(0) -> ValueError ile COKUYORDU.
Olculdu: samples/pic_programmer C4'un degeri '0'; 'pcbqa mpn' o kartta
cokuyor. Kicad-9jy'deki karar ('degeri okunamayan parcaya fiyat yazilmaz,
None doner') SIFIR'i kapsamiyordu. Duzeltme ayni kararin uzantisi, tersi
degil: buyukluk <= 0 da None. Ek gerekce: 0 ohm koprunun fiyati
buyuklukten turetilemez.

ETKILENEN DOSYALAR:
  pcbqa/pcbqa/arayuz.py (yeni), pcbqa/pcbqa/elektrik.py (yeni)
  pcbqa/tests/test_arayuz.py (yeni), pcbqa/tests/test_elektrik.py (yeni, 24)
  pcbqa/pcbqa/mpn.py (_base_price sifir korumasi)
  pcbqa/pcbqa/app.py (COMMANDS: arayuz, parcalar)

DOGRULAMA: test_elektrik 24/24 OK, test_app+test_komut+test_mpn 75/75 OK.
Gercek kart: samples/pic_programmer 30+ parca, GND pinleri 0 V taniniyor,
akimi turetilemeyen HER satirda sebep yazili.

## Kicad-a27 - Evre 3d kapisi: etiketi tohumlar uzerinden ortalayip sinyal var mi diye olc

- oncelik: P1  |  durum: open  |  tur: task

3c OLCUMU: varyant siralayici ogrenmiyor - grup bazli 3 kat CV'de ridge ikili dogruluk 0.422, gbt 0.495, temel cizgi 0.500 (yazi tura). Gurultu tabani: aciklanabilir ust sinir %31.4; varyansin ~%69'u TOHUM. EN UMUT VERICI SONRAKI ADIM: model tek kosumu tahmin etmeye calisiyor, oysa tahmin edilebilir olan KOSULUN ORTALAMASIDIR. Ayni (topoloji, yogunluk) kosulunu K tohumla kosup etiketi ORTALAMAK gurultuyu K kat azaltir; sinyal varsa orada gorunur. IKINCI ADAY: veri kucuk (7 grup, 56 ornek) - sablon kutuphanesi buyudukce topoloji cesitliligi artar (su an 7 niyetin 6'si ayni MCU). UCUNCU: oznitelikler yetersiz olabilir (net topolojisinin grafik ozellikleri yok). KURAL: bu olcum yapilmadan model YAZILMAZ; learned yerlestirici dersi (HANDOFF 21.10) aynen gecerli - kazanc olculmeden terfi yok.

## Kicad-ow3 - Gelecek plani: bagla + uygula-ipc canli zinciri

- oncelik: P1  |  durum: open  |  tur: feature

PLAN (2026-08-31, kullanici yol haritasi):
Sematik telleme (pcbqa bagla) ile canli PCB yerlestirmeyi (uygula-ipc) tek
zincire baglamak.

NEDEN AYRI DURUYORLAR: sematige canli yazma KiCad 10.0.4'te YOK (Kicad-5be);
PCB tarafinda VAR ve dogrulandi (16 footprint canli tasindi, undo'ya tek islem
olarak girdi).

HEDEF AKIS:
  1. sematik editoru KAPALIYKEN: pcbqa bagla --oner --uygula (netlist hakemi)
  2. pcb_sync ile kartı sematige esitle
  3. pcbnew ACIKKEN: pcbqa uygula-ipc --apply -> yerlesim canli iyilesir,
     kullanici Ctrl+Z ile mudahale edebilir

ACIK SORULAR:
  * adim 1 ile 2 arasinda netlist degismezligi nasil dogrulanir (sch_verify var)
  * kullanici sematigi acik unutursa akis nerede durmali
  * uygula-ipc su an bench_bad'e ozel bir hakem kosuyor; uretilen kartta ne
    olacagi olculmedi

## Kicad-rkj - Dogal dil komutu: 'yap' katmani (komut.py)

- oncelik: P1  |  durum: open  |  tur: task

KARAR (2026-09-03): Basit dogal dil gorevlerini anlayan bir katman eklendi:
pcbqa/pcbqa/komut.py + CLI alt komutu "yap".

PROBLEM: "su anki modelimize 10 adet kapasitor koy" cumlesini arac
anlamiyordu. Alt katmanlar (sch_add.add_symbols) zaten hazirdi; eksik olan
CUMLEYI o cagriya ceviren katmandi.

KARAR: Modelsiz (regex + kapali sozluk) cozumleyici, TIPLI cikti.
  anla(metin) -> Yorum{eylemler[Eylem], notlar, engeller}
  uygula(yorum, sch) -> [sch_add.AddResult]

GEREKCE:
  1. pcbqa'nin calisma zamani bagimliligi YOK ve KiCad'in kendi Python'unda
     kosuyor; bir model istemcisi bunu bozardi.
  2. Testler sessizligi korur - ayni cumle her kosuda ayni plani uretmeli.
  3. "Basit gorev" dagarcigi KAPALI kume: fiil, adet, tur, deger, paket.
  Yine de Yorum/Eylem TIPLI bir sozlesme: ileride bir model dogrudan Eylem
  listesi uretebilir, uygulayici degismez.

DOKTRIN (projenin geri kalaniyla ayni):
  - bilinmeyen fiil, bilinmeyen bilesen, belirsiz sozcuk (transistor) ->
    ENGEL, adaylariyla. Sessiz tahmin yok.
  - deger verilmezse UYDURULMAZ; kutuphanedeki deger kullanilir + not.
  - lib_id ve footprint kimlikleri calistirma aninda dogrulanir.

BASARISIZ / DUZELTILEN DENEMELER:
  - "on" Ingilizce edat diye DOLGU'ya konmustu; Turkce "on adet kapasitor"
    komutundaki 10 sessizce 1'e dustu. DOLGU'dan cikarildi ve
    test_filler_words_never_shadow_a_number_or_a_component nobetci testi
    yazildi.
  - Device:Ferrite_Bead diye yazilmisti; KiCad'de adi Device:FerriteBead.
    KutuphaneTests.test_every_lib_id_resolves ilk kosuda yakaladi.
  - Deger sadelestirilmis kelimeden okunuyordu; "10M" (mega) ile "10m"
    (mili) ayni seye dusuyordu. Deger artik HAM kelimeden okunuyor.
  - Virgul kosulsuz ayracti; Turkce ondalik "4,7k" ikiye bolunuyordu.
    Ayrac artik (?<!\d)[,;](?!\d).

ETKILENEN DOSYALAR:
  pcbqa/pcbqa/komut.py (yeni), pcbqa/tests/test_komut.py (yeni, 41 test),
  pcbqa/pcbqa/app.py (COMMANDS'a "yap" satiri)

DOGRULAMA: tests.test_komut 41/41 OK; tests.test_app 20/20 OK.
Uctan uca: samples/pic_programmer kopyasina 10 kapasitor yazildi, netlist
kalkani gecti, yedek alindi.

KAPSAM SINIRI (bilincli): v1 yalnizca EKLER. sil/tasi/bagla/degistir
taninir ama reddedilir - "anlamadim" ile "henuz yapmiyorum" ayri seylerdir.

## Kicad-2ys - Gelecek plani: elektrik tablosunun bilebilecegi ama henuz bilmedigi seyler

- oncelik: P2  |  durum: open  |  tur: task

GELECEK PLANI (2026-09-03) - elektrik.py (Kicad-204) uzerine.

Tablo su an 3 seyi turetiyor: ray gerilimi (net adindan), direnc akimi
(Ohm), kondansator DC akimi (~0). Turetilebilecek ama HENUZ turetilmeyenler,
degerine gore sirali:

1. REGULATOR CIKIS RAYI. subcircuit.py buck donusturucuyu topolojiden
   taniyor; ayni yerden 'bu ag bir regulatorun cikisi' bilgisi cikarilabilir.
   O zaman adi 'VCC' olan bir ag bile gerilimini kazanir - su an en cok
   bilgi kaybettigimiz yer burasi (pic_programmer'da 30+ parcanin cogu
   VCC yuzunden bos kaliyor).
2. GERILIM BOLUCU. Iki seri direnc iki bilinen ray arasindaysa ortadaki
   dugumun gerilimi hesaplanabilir (R2/(R1+R2)*dV). Yayilim: bir kez
   bilinen dugum, komsu parcalarin akimini da acar. Kucuk bir cozum agi
   (iteratif yayilim) ister.
3. LED / DIYOT AKIMI. Seri direncten hesaplanabilir ama Vf gerekir. Vf
   parcaya ozgu ve kutuphanede YOK. Dogru kaynak: MPN katalogu gercege
   baglandiginda (su an sentetik) Vf oradan gelir. O zamana kadar
   uydurulmaz.
4. IZ AKIM KAPASITESI. ipc2221.py iz genisliginden TASIYABILECEGI akimi
   veriyor. Bu 'gecen akim' DEGIL, sinir. Ayri bir sutun olarak eklenebilir
   ve gecen akim biliniyorsa 'kapasitenin %kaci' diye kiyaslanabilir -
   asil degerli olan bu kiyas. PCB dosyasi gerektirir (tablo su an yalnizca
   sematige bakiyor).
5. GUC TUKETIMI. Akimi bilinen her parca icin P = I*dV; kart toplami
   'en az su kadar' diye ALT SINIR olarak verilebilir (aktif parcalar
   bilinmedigi icin ust sinir degil). Alt sinir oldugunu SOYLEMEK sart.

SINIR (degismemeli): turetilemeyen sayi BOS kalir ve sebebi yazilir.
Vf, VCC gerilimi ya da 'tipik' akim UYDURULMAZ - tablo bir tahmin listesi
degil, bilinenlerin listesidir.

## Kicad-4af - Arayuz kisayolu ve ayri baslaticisi (pcbqa-arayuz.cmd)

- oncelik: P2  |  durum: open  |  tur: task

KARAR (2026-09-04): Arayuz icin ayri baslatici + Windows kisayolu.
Kullanici: 'acilmasi icin kisayolu klasore koy'.

YENI: pcbqa/pcbqa-arayuz.cmd  (kisayolun hedefi)
      Kicad/pcbqa Arayuz.lnk  (izlenmiyor - .gitignore'a *.lnk eklendi)

NEDEN AYRI BASLATICI: pcbqa.cmd yorumlayici olarak ONCE KiCad'inkini secer
(dogru karar, §27) ama KiCad Python'unu Tk OLMADAN paketliyor. Arayuz o
yorumlayiciyla acilamaz. pcbqa-arayuz.cmd tkinter'i GERCEKTEN olan bir
Python arar - varsaymaz, her adayi calistirip sinar - ve konsol penceresi
acilmasin diye onun KENDI pythonw.exe'siyle baslatir.
Aday sirasi: PCBQA_PYTHON, proje .venv, py, python, python3.

BULUNAN GERCEK HATALAR (uc tanesi de olcumle cikti):

1. YANLIS KURULUMUN pythonw'su. Ilk surum pythonw'yu PATH'ten aliyordu.
   Bu makinede PATH'teki `pythonw` Microsoft Store TAKMA ADI, yani
   tkinter'i sinadigimiz .venv'den BASKA bir kurulum. `start` onu
   calistiramadigi icin ARAYUZ SESSIZCE HIC ACILMIYOR, baslatici yine de 0
   donuyordu - en kotu hata turu. Duzeltme: konsolsuz ikiz YALNIZCA secilen
   yorumlayicinin kendi klasorunden alinir; bulunamazsa konsollu acilir.
   Nobetci test: ArayuzLauncherTests.
   test_the_windowless_twin_belongs_to_the_same_installation

2. for /f "usebackq" ICINDEKI IC ICE TIRNAKLAR cmd'de cozumlenmiyordu -
   pythonw yolunu ureten dongu HIC sonuc uretmedi (sessizce). Yol artik ara
   dosyaya yazilip `set /p` ile okunuyor.

3. `if exist` YETMIYOR. Store takma adinin sys.executable'i
   "C:\Program Files\WindowsApps\..." altini gosteriyor ve o klasorun ACL'si
   yuzunden `if exist` YANLIS olarak 'yok' diyor. Hem tkinter hem pythonw
   denetimi artik adayi CALISTIRIP cikis koduna bakarak yapiliyor.

EK DUZELTME (baslat.py): belge dizgesi icindeki '...\pcbqa' Python 3.12+
tarafindan gecersiz kacis dizisi sayilip HER CALISTIRMADA SyntaxWarning
bastiriyordu - kullanicinin gordugu ilk sey oydu. Dizge ham (r\"\"\") yapildi.

TANILAMA: `pcbqa-arayuz.cmd --nerede` hangi yorumlayici ciftinin secildigini
yazar. Kisayol calismadiginda ilk sorulacak soru bu.

OLCULEN SONUC: kisayoldan acilinca
  .venv\Scripts\pythonw.exe baslat.py arayuz   (konsol penceresi kalmiyor)
Pencerenin gercekten haritalandigi uygulamanin kendisine sorularak
dogrulandi: winfo_ismapped=1, viewable=1, 1180x760, 5 sekme, Uygula kilitli.
(EnumWindows ile dogrulanamadi - bu oturumdan pythonw pencereleri
gorunmuyor; CIPLAK Tk de ayni sekilde gorunmuyor, yani olcum siniri.)

DOGRULAMA: tests.test_app 24/24 OK (4 yeni baslatici testi dahil).

## Kicad-4ro - Courtyard cakismasinda mikron seviyesi degme icin esik kaynagi bulunmali

- oncelik: P2  |  durum: open  |  tur: task

OLCUM (Evre 3a, CM5_MINIMA_3 demosu): courtyard_overlap kurali 0.005-0.006 mm derinlikte 'cakisma' bildiriyor. Bunlar tasarimcinin BILEREK bitisik koydugu bilesenler; CM5 projesinin kendi .kicad_pro'sunda iki courtyards_overlap ihlali drc_exclusions ile muaf tutulmus (yani KiCad de goruyor, tasarimci kabul etmis). Uretim acisindan 6 mikronluk ortusme anlamsiz. EMSAL: pad seklinde ayni sinif hata icin HANDOFF'ta '0.03 mm cakisma TO-92'de yanlis alarm uretiyordu' kaydi var. YAPILMASI GEREKEN: ihlal DERINLIGINI olcup uretim acisindan anlamsiz olanlari elemek - ama esik UYDURULMAMALI, IPC-7351B courtyard toleransi ya da uretici verisi kaynak gosterilmeli. Bu is yapilana kadar kural literal davraniyor (clearance_mm: 0.0 = hic ortusmesin), ki configure edilen sey de bu. Etkilenen: pcbqa/rules.py _check_courtyard_overlap, pcbqa/geom.py overlap.

## Kicad-d8f - Gelecek plani: 'yap' katmaninin sonraki fiilleri ve baglama

- oncelik: P2  |  durum: open  |  tur: task

GELECEK PLANI (2026-09-03) - komut.py (Kicad-rkj) uzerine.

v1 yalnizca EKLIYOR. Siradaki adimlar, degerine gore siralanmis:

1. BAGLAMA fiili: "10 adet 100nF kapasitor ekle ve hepsini VCC-GND arasina
   bagla". sch_add zaten connect= aliyor (PIN=HEDEF); komut katmani
   "X ile Y arasina" kalibini ayristirip ona cevirmeli. En yuksek deger:
   suanki ekleme BAGLANTISIZ sembol birakiyor.
2. SILME fiili: "C5'i sil", "son ekledigin 3 kapasitoru geri al". Silme
   icin netlist kalkaninin TERSI gerekir (compare_subtractive) - mevcut
   compare_additive yalnizca ekleme dogruluyor. Yeni is.
3. REFERANSLA konusma: "C5", "R1-R4", "son eklediklerim". Cozumleyici su an
   yalnizca TUR biliyor, ORNEK bilmiyor.
4. DAGARCIK BUYUTME: TURLER tablosu elle. lexicon.py'de zaten 22.776
   sembolun olculmus aciklamasi var (Kicad-hpg); tur tablosunu oradan
   turetmek elle bakimini bitirir. Ama belirsizlik artar - "regulator"
   deyince hangi parca sorusu buyur.
5. MODEL ON YUZU (istege bagli): Yorum/Eylem tipli sozlesme zaten hazir.
   Bir model cumleyi dogrudan Eylem listesine cevirebilir; uygulayici,
   kalkan ve testler degismez. Sart degil, kapali kume buyudukce degerlenir.

SINIR (degismemeli): cozumleyici KUTUPHANEYE DOKUNMAZ ki testler KiCad'siz
kossun; dogrulama uygulama asamasinda.

## Kicad-hpg - Sozluk gelecek plani: dil hacmini buyutmek ve ML'e baglamak

- oncelik: P3  |  durum: open  |  tur: task

PLAN (kullanici: 'simdilik ileride dil hacmini buyutebiliriz').

SU ANKI DURUM: EN + TR, 67 onek / 252 terim / 31 kalip, 22.776 sembol.
Turkce kapsama %94.6 (kalan %5.4 cogunlukla saf parca numarasi - dogru davranis).

BUYUTME YOLLARI (henuz karar verilmedi):
  a) Terim sozlugunu genisletmek: siklik listesinin kuyruguna inmek. Kazanc
     azalan verimli - bas taraf zaten alindi.
  b) Ucuncu dil eklemek: TERMS yapisi {en: tr} yerine {en: {tr:, de:, ...}}
     olmali. SIMDI degistirmek ucuz, 22.776 kayit uretildikten sonra degil.
  c) ki_keywords alanini da Turkcelestirmek - su an yalnizca Description
     ceviriliyor. Anahtar kelimeler arama icin daha degerli olabilir.
  d) Footprint kutuphanesi (155 kutuphane) sozluge hic girmedi.

ML BAGLANTISI (asil amac): sozluk henuz hicbir ML boru hattina bagli DEGIL.
ml/features.py bilesen turunu lib_id'den cikariyor; sozluk oradaki _kind_index
yerine gecebilir ve iki dilli sorgu/etiketlemeyi acar. Once olculmeli:
sozluge dayali tur bilgisi skorda ya da yerlestirmede fark yaratiyor mu?

## Kicad-xpi - Ayrik sicak dongu tanimasini GERCEK bir kartta dogrula

- oncelik: P3  |  durum: open  |  tur: task

Kicad-z1d'nin uygulama kismi bitti: roller topolojiden cikiyor (ust kol VIN+SW, alt kol SW+GND), dongu altigen, geometri analitik olarak dogrulandi (sentetik kart, beklenen 12 mm2 elle hesaplandi).

DOGRULANMAYAN sey: taniyicinin GERCEK bir ayrik kartta calistigi. Korpusta ayrik regulator yok - KiCad demolarindaki alti regulatorun altisi da entegre, sistemde baska .kicad_pcb yok (arandi).

Gerceklesince sinanacaklar:
- external_switches gercek FET'leri buluyor mu (paket/sembol cesitliligi)
- ust/alt kol dogru atanip atanmadigi
- bootstrap diyodu, snubber, ters polarite FET'i yanlis rol almiyor mu
- olculen alanin buyukluk mertebesi makul mu (TI AN-2155 6 mm2 esigi)

BLOKE: gercek ayrik (harici FET'li) buck referans karti bulunmasi. Lisansi temiz olmali (HANDOFF 1: korpus buyurken her kartin lisansi kaydedilir).

DIKKAT: sentetik kartla ESIK dogrulamak YASAK - 1d'nin 'korpusa uydurma' yasagina girer. Sentetik kart yalnizca geometriyi sinar.

## Kicad-ywm - Uretilen kartta ipek baski cakismasi (silk_overlap/silk_over_copper)

- oncelik: P3  |  durum: open  |  tur: task

OLCUM (Evre 3a, ornek-f103): uretilen kartta KiCad DRC'si 17 silk_over_copper + 14 silk_overlap uyariyor. Sebep: auto yerlestirici referans metinlerini hesaba katmiyor - yalnizca courtyard ve HPWL goruyor. %25 yogunlukta bir kartta referans etiketleri kacinilmaz olarak komsu pad'lerin uzerine dusuyor. Kozmetik ama gercek (uretimde okunamayan referans montaji zorlastirir). SECENEKLER: (a) yerlestirme sonrasi bir 'etiket yerlestirme' adimi (KiCad'in kendi otomatik metin yerlesimi yok), (b) kendi kural setimize silk kurali eklemek, (c) kabul edip belgelemek. Su an (c) gecerli. Bkz. HANDOFF 23.
