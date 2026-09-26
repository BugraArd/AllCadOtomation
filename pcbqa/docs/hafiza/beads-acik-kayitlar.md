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

## Kicad-3ha - Tekrarlanabilir blok modeli: ornek adi, yerel ag alani ve tipli portlar

- oncelik: P1  |  durum: open  |  tur: feature

Kullanici 2026-09-22'de gelistirme sirasini belirledi; bu, o siranin 2. adimi
(1. adim Kicad-mdm besleme/ERC acigi). Kicad-38l umbrella'sinin alt dilimi.

SORUN 1 - TEKRAR REDDEDILIYOR. intent.py:409 ayni sablon iki kez istenirse
"ayni ag adlarini iki blok birden surer" diyip ENGEL uretiyor. Uc fazli yarim
koprusu ya da iki motor surucusu bu yuzden ifade edilemiyor. Kullanici acikca
istedi: "Ayni yarim kopru veya olcum blogu farkli isimlerle kullanilabilsin.
Ic aglar birbirine karismasin; ortak aglar acikca baglansin."

SORUN 2 - BAGLANTILARIN ELEKTRIKSEL OZELLIGI YOK. Sablon pinleri duz ag adi
stringine bagliyor (${vdd} -> "3V3"). Yon, gerilim araligi, guc alani ve gorev
bilgisi hicbir yerde yok. ST modelinde bunlar sinyalin DOGASI; pcbqa'da kayip.
Bu ayni zamanda Kicad-mdm'in kok sebebi: requires/provides yalniz YETENEK ADI
esliyor, gercek ag/gerilim/yon esletmiyor.

ONERILEN MODEL (uygulama karari degil, oneri):
  - Her intent blogunun ORNEK ADI olur (ayni sablon n kez, farkli adla).
  - Sablon aglari VARSAYILAN OLARAK YEREL; ornek adiyla on ekleniyor
    (faz_U -> sur1.faz_U). Cakisma kalmaz.
  - Sablon `ports:` bildirir; port = ad + yon (in/out/bidir/power_in/power_out)
    + gerilim araligi + guc alani + gorev. Paylasilan aglar YALNIZ port
    uzerinden, niyette ACIKCA baglanir.
  - provides/requires port SOZLESMESINE bakar: tuketicinin power_in portu ile
    saglayicinin power_out portu AYNI AGDA mi ve gerilim araliklari ortusuyor
    mu? Ad esitligi yeterli sayilmaz.

Bu 2. sorunun cozumu Kicad-mdm'i kapatmanin da yolu; bu yuzden mdm once
gelmeli ve bu is ona dayanmali.

SINIR: ST'nin "pin dizisinde birden cok eleman = hepsi mi alternatif mi"
mugalaklaligi KOPYALANMAMALI; alternatif acikca isaretlenmeli.

Dosyalar: intent.py:409 (tekrar reddi), intent.py:418-440 (yetenek denetimi),
intent.py:286 PlannedComponent.label (su an "sablon/bilesen", ornek adi yok).

## Kicad-4m5 - MCU pin planlayicisi: PWM/ADC/break/SWD kisitlarini birlikte coz

- oncelik: P1  |  durum: open  |  tur: feature

Kullanici gelistirme sirasinin 3. adimi (2026-09-22). Kicad-38l alt dilimi.

ISTENEN: "PWM, tamamlayici PWM, ADC, donanimsal hata girisi, SWD ve haberlesme
gereksinimlerini BIRLIKTE cozsun." Yani tek tek pin atamasi degil, kisit
cozumu - ST acikca "sinyaller bagimsiz degil" diyor.

COZULECEK KISIT TURLERI (kaynak: ST MC Boards Description):
  1. Ayni cevre birimi ornegi: 6 PWM sinyali TEK advanced timer'da
  2. Kanal baglama: faz U<->CH1, V<->CH2, W<->CH3; high<->CHx, low<->CHxN
  3. Yetenek: advanced timer (tamamlayici+dead time+break); Hall icin ayni
     general-purpose timer'in CH1,CH2,CH3; quadrature icin CH1,CH2
  4. Capraz ozellik: OC_TRIGGER/DP_TRIGGER, PWM'i ureten AYNI timer'in
     BREAKIN/BREAKIN2'sine gitmeli
  5. Diskalifiye: SWD calinamaz; UART cifti tek USART orneginde

BULGU - VERI KAYNAGI YERELDE HAZIR (2026-09-22 dogrulandi):
KiCad 10.0 MCU_ST_STM32F1.kicad_sym icindeki STM32F103C8Tx sembolu 341 adet
(alternate "...") kaydi tasiyor. Onekler: ADC1 45, ADC2 45, TIM1 39, TIM2 30,
SPI1 24, USART1 21, SYS 18, TIM3 18, RCC 15, USART2 15, I2C1 15, CAN 12.
Ihtiyac duyulan her sey var:
  TIM1_CH1/CH1N/CH2/CH2N/CH3/CH3N  -> DrivingHighAndLowSides
  TIM1_BKIN                        -> OC_TRIGGER / DP_TRIGGER break yolu
  TIM1_ETR                         -> HF_ETR akim sinirlayici
  ADC1_IN0..  / ADC2_..            -> akim olcumu, VBUS, NTC, potansiyometre
  TIM2/3/4_CH1..CH4                -> Hall (CH1,2,3) ve quadrature (CH1,2)
  SYS_JTMS-SWDIO                   -> SWD diskalifiyesi
  USART1_TX/RX, CAN_RX/TX          -> haberlesme
SONUC: CubeMX veri tabanina ya da harici veri setine GEREK YOK. Planlayici,
pcbqa'nin zaten okudugu kutuphaneden beslenir - "uydurma sayi yazilmaz"
ilkesine uyar. F103'te dahili op-amp/komparator YOK; ST'nin InternalGain ve
IntRef varyantlari bu MCU'da dogal olarak elenir - dogru davranis.

ENGEL: symlib.LibPin (symlib.py:63) alternate fonksiyonlari AYRISTIRMIYOR -
alanlari yalnizca number/name/electrical/x/y/rotation/length/unit. Ilk somut
adim: LibPin'e alternates listesi eklemek. Kucuk degisiklik, planlayiciyi acan
sey bu.

COST FIKRI (ST'den alinmali): bir sinyali birden cok pin tasiyabiliyorsa
cost=0 hazir, cost>0 jumper/lehim koprusu/0R ister + help metni. Cozucunun
secimi boylece ACIKLANABILIR olur.

## Kicad-a27 - Evre 3d kapisi: etiketi tohumlar uzerinden ortalayip sinyal var mi diye olc

- oncelik: P1  |  durum: open  |  tur: task

3c OLCUMU: varyant siralayici ogrenmiyor - grup bazli 3 kat CV'de ridge ikili dogruluk 0.422, gbt 0.495, temel cizgi 0.500 (yazi tura). Gurultu tabani: aciklanabilir ust sinir %31.4; varyansin ~%69'u TOHUM. EN UMUT VERICI SONRAKI ADIM: model tek kosumu tahmin etmeye calisiyor, oysa tahmin edilebilir olan KOSULUN ORTALAMASIDIR. Ayni (topoloji, yogunluk) kosulunu K tohumla kosup etiketi ORTALAMAK gurultuyu K kat azaltir; sinyal varsa orada gorunur. IKINCI ADAY: veri kucuk (7 grup, 56 ornek) - sablon kutuphanesi buyudukce topoloji cesitliligi artar (su an 7 niyetin 6'si ayni MCU). UCUNCU: oznitelikler yetersiz olabilir (net topolojisinin grafik ozellikleri yok). KURAL: bu olcum yapilmadan model YAZILMAZ; learned yerlestirici dersi (HANDOFF 21.10) aynen gecerli - kazanc olculmeden terfi yok.

## Kicad-m54 - TIDA-010025 gercek kart kalibrasyonu: ag->gerilim modeli yetersiz cikti

- oncelik: P1  |  durum: open  |  tur: task

Kullanici TI TIDA-010025 referans tasarimini (Altium projesi, BOM, sema,
katman ciktilari) verip "su ana kadarki ciktilarinla karsilastir" dedi
(2026-09-23). Kart: 530 V DC bara, izole kapi surucu, uc fazli evirici.

YONTEM: kicad-cli pcb import --format altium ile .PcbDoc -> .kicad_pcb
(406 footprint, 1621 iz, 189 via, 72 bolge). pcbqa 0.4 sn'de ayristirdi.
Gerilim 530 V SEMADAN okundu, varsayilmadi. Izole parcalar: UCC23513
(kapi surucu), AMC1300 (izole akim), AMC1311 (izole DC bara gerilimi),
ISO7710 (dijital izolator).

BULGU 1 - VARSAYILAN PRESETLER SESSIZ, BU IYI:
  uretim preseti    : 7 bulgu (4 info, 3 warning) / 404 bilesen
  yuksek-hiz preseti: 4 "error" - HEPSI YANLIS (bkz. ayri kayit)
Gercek, uretilmis, yetkin tasarlanmis bir kartta uretim kurallarinin
neredeyse susmasi, kalibrasyonun makul oldugunu gosteriyor.

BULGU 2 - ASIL SONUC: AG->TEK GERILIM MODELI YANLIS.
Kurala gercek gerilimi (530 V) beyan edince 26 hata cikti. Incelendi:
  22 / 26 YANLIS ALARM - ayni referans alaninda olan agler.
  3-4 / 26 ice aktarma kusuru (asagida).
  0 / 26 kanitlanmis gercek IPC-2221 ihlali.
Sebep: IPC-2221 acikligi iki iletken arasindaki POTANSIYEL FARKINA baglidir,
tek bir agin mutlak gerilimine degil. pcbqa iki agdan yuksek olanini alip
otekini 0 V sayiyor.
KANIT (sema s3): kapi surucu sayfasi VCC_U/VEE_U, VCC_V/VEE_V, VCC_W/VEE_W
ve DC-'ye referansli VEE gosteriyor - yani faz basina YUZEN besleme.
Ornekler:
  DC- <-> VGE_UN  : kural 2.65 mm istedi. VGE_UN alt IGBT'nin kapi-emiter
                    gerilimi, emiter DC-'de. Gercek fark ~20 V -> 0.1 mm
                    gerekir. TI 0.200 mm vermis. TI HAKLI, kural yaniliyor.
  DC- <-> +5V_DC- : "+5V_DC-" adi zaten "DC-'ye referansli 5 V" demek.
                    Fark 5 V, 530 V degil.
SONUC: her agin bir REFERANS DUGUMU ve o referansa gore gerilimi olmali.
Kicad-3ha'daki "tipli port = yon + gerilim araligi + GUC ALANI" tasarimi
dogruymus; bu kart onun somut kaniti ve regresyon hedefi.

BULGU 3 - ICE AKTARMA KAYIPLI, ANALIZ SINIRLI:
kicad-cli 15 ic guc katmanini ("Internal Plane 2..16") eslestiremeyip
atladi. Iz katman dagilimi: F.Cu 1111, B.Cu 412, In2.Cu 92, In1.Cu 6.
0.000 mm cikan ciftler bundan ve izolator paketinin iki yakasindaki
padlerden (U17 = AMC1311; DC_LINKP ve NetC73_1 ayni parcada) kaynaklaniyor.
TI'de kisa devre YOK - boyle bir iddiada bulunulmamali.

BULGU 4 - E96 GEREKLIYDI (dun eksik birakilmisti, bkz. Kicad-0bs):
BOM'daki 20 direncin TAMAMI %1. Ucu (2490, 806, 3010) yalnizca E96'da.
Onlara E24 onerisi %3.6'ya varan sapma uretiyor - parca toleransindan
buyuk, yani oneri yanlis olur. E96 eklendi (asagidaki kayitta ayrinti).

ELDEKI DEGER: TIDA-010025 artik gercek bir kalibrasyon kartidir. Ag adlari
ST ozellik modeliyle birebir ortusuyor: DC_LINK/DC_LINK_REF (VBusSensing),
I_UP/I_UN/I_VP/I_VN/I_WP/I_WN (CurrentSensing, diferansiyel), VGE_* x7
(PhaseVoltageGeneration), I_*_Fault (OverCurrentProtection), +5V_U/V/W
(faz basina yuzen kapi besleme).

## Kicad-mdm - Sematik guc sozlesmesini ve ERC kabul kapisini dogrula

- oncelik: P1  |  durum: open  |  tur: bug

Kicad-7i5 incelemesinde gercek KiCad netlistiyle yeniden uretildi: f103-asgari bloklarinda yalniz MCU vdd parametresi MCU_3V3 yapilirken LDO cikisi 3V3 kalirsa expand_intent+resolve_plan plan.ok=True ve problems=[] donuyor. generate.verify_against_plan 6 agi sorunsuz dogruluyor; MCU beslemesi regulator cikisindan kopuk. requires/provides yalniz yetenek adini esliyor, gercek ag/gerilim/kaynak baglantisini degil. ERC farki: normalde 2 power_pin_not_driven, kopuk beslemede 3; ikisinde 37 kullanilmayan pin bildirimi. Normal dis besleme/GND kaynaklari acikca tanimlanmali; PWR_FLAG veya no-connect ile tum bildirimler korlemesine susturulmamali. Canli worker ve generate onay yollarinda ERC kabul kapisi yok; yalniz netlist dogrulamasi yeterli degil. Dosyalar intent.py:418,502; generate.py:635; canli_sematik_worker.py:85,146,205. Inceleme kapsaminda duzeltilmedi.

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

## Kicad-0bs - PCB Calculator verilerini isle: E-serisi, IPC-6012 siniflari, aciklik dogrulamasi

- oncelik: P2  |  durum: open  |  tur: feature

Kullanici KiCad PCB Calculator dokumanini ve 11 sekme ekran goruntusunu verip
"bu bilgileri isle ve sonuclari uygulamaya isle" dedi (2026-09-22).

YAPILAN 1 - DOGRULAMA (kod degismedi, ama sonuc kayda deger):
ipc2221.py _TABLE_6_1 aciklik tablosu, KiCad'in "Electrical Spacing" sekmesiyle
SATIR SATIR karsilastirildi: 9 gerilim araligi x 7 sinif (B1-B4, A5-A7), 63
hucrenin hepsi AYNI. Tablo bagimsiz bir kaynakla dogrulanmis oldu; tekrar
kontrol edilmesine gerek yok. pcbqa ayrica 500 V ustu icin volt basina
ekleme yapiyor (_ABOVE_500), KiCad bunu kullaniciya elle hesaplatiyor.

YAPILAN 2 - YENI MODUL: pcbqa/eseri.py (IEC 60063 E-serisi)
Gerekce: kural motoru "pull-up en az 966.7 ohm olmali" diyebiliyordu; boyle
bir direnc satilmiyor, yani bulgu eyleme donusmuyordu. Artik siniri SAGLAYAN
ilk seri degeri de soyleniyor (966.7 -> E24'te 1.0k).
API: E_SERIES, up(), down(), nearest(), ESeriError.
E48/E96/E192 BILINCLI OLARAK YOK: degerleri kaynakta sayi sayi verilmedi.
10^(n/96) formulunden turetmek cazip ama IEC 60063 yuvarlamada formulden
sapan girdiler icerir. Uydurulmadi.

YAPILAN 3 - IPC-6012 performans siniflari (ipc2221.py)
IPC6012_CLASSES: Class 1-6, min iz / min aciklik / via / kaplamali pad /
NP pad. Mevcut FAB_CLASSES'tan AYRI bir sorudur: FAB_CLASSES ureticinin ne
basabildigini, bu tablo urunun hangi guvenilirlik sinifinda oldugunu soyler.
TUZAK - KAYDA GECIYOR: tablo satirlari "(diam - drill)", yani CAP FARKI.
Halka genisligi (annular ring) bunun YARISIDIR. FAB_CLASSES.min_annular_ring_mm
ise yaricap cinsinden. Ikisini dogrudan kiyaslamak 2 KAT hata demek.
Class 1-2 icin via, Class 4-6 icin NP pad standartta YOK -> None (uydurulmadi).

YAPILAN 4 - rules.py entegrasyonu
_eseri_onerisi(): alt sinirda yukari, ust sinirda asagi yuvarlar (ters yon
oneriyi araligin disina atardi). IKI durumda sessiz kalir:
  - sinir zaten seride ise (oneri gurultu olurdu),
  - seride araliga SIGAN deger yoksa (dar aralik). Bu gercek bir tasarim
    sorunudur ama yanlis sayi onermektense susuluyor.
Dogrulama: I2C pull-up 966.7-1770.3 ohm araliginda alt sinir icin 1.0k, ust
sinir icin 1.6k oneriliyor; ikisi de araligin ICINDE ve satin alinabilir.

ISLENMEYEN (durust sinir): Regulators, RF Attenuators, TransLine, Via Size
termal/empedans hesaplari, Color Code okunmadi degil - pcbqa'nin su anki
kapsaminda karsiligi yok. Via Size'daki termal direnc ve ampacity ileride
ipc2221.via_current_a ile kiyaslanabilir; TransLine yuksek hiz kurallari
icin anlamli olur. Ayri is olarak acilmadi, burada not edildi.

## Kicad-10z - Amaca gore sablon katalogu: feature/variant katmani + motor surucu bloklari

- oncelik: P2  |  durum: open  |  tur: feature

Kullanici gelistirme sirasinin 4. adimi (2026-09-22). Kicad-38l alt dilimi.

ISTENEN KATALOG (kullanici, "amaca gore sablon katalogu"):
  - STM32: cekirdek + besleme + debug
  - Motor surucu: gate surucusu, faz blogu, akim olcumu, DC bara olcumu,
    sicaklik, asiri akim kapatma
  - Arduino: modul tasiyici kart ILE ciplak MCU tasarimi AYRI profiller
    (resmi UNO R3 sematigi baslangic ornegi olabilir)

EKSIK KATMAN - FEATURE. pcbqa sablonu ST'nin HW VARIANT'ina denk; ustundeki
FEATURE (amac) katmani yok. Katalog "amaca gore" olacaksa bu katman sart:
  feature: CurrentSensing
  variant: ThreeShunt_AmplifiedCurrents
Kazanc: (a) "CurrentSensing gerekiyor" denip alternatif uygulamalar
siralanabilir, (b) ayni amacin iki uygulamasi arasindaki DISLAMA (ST'nin
"concurrent" hali - kullanici birini secmek zorunda) ifade edilebilir,
(c) requires: CurrentSensing herhangi bir varyantla karsilanabilir.

ST'NIN FEATURE ADLARI (dogrudan alinabilir): CurrentSensing,
SpeedAndPositionSensing, PhaseVoltageGeneration, PhaseVoltageSensing,
DriverProtection, OverCurrentProtection, ICL, Brake, CurrentLimiter,
VBusSensing, TemperatureSensing, SerialPortCommunication, Potentiometer,
Button.

DOGRULANABILIR FORMULLER (rules katmanina; kaynak ST 3.1.4 - uydurma degil):
  V_ADC = opAmpGain * offsetNetworkAttenuation * V_shunt + polarizationOffset
  dahili op-amp: V_ADC = opAmpGain*(offsetNetworkAttenuation*V_shunt
                                     + rawPolarizationOffset)
  Kontrol: amplifyingNetworkImax'ta V_ADC [0,Vref] icinde kaliyor mu?
  Shunt gucu: P=I^2*R vs amplifyingNetworkPrating
  Profiler: Rs=(Rmeasure-resistorOffset)/2

ZAMANLAMA DEGERLERI parcadan gelir, uydurulmaz: minDeadTime, deadTime, tNoise,
tRise, maxSwitchingFreq. Kaynagi yazilmadan sablona girmez.

ST TABLOSUNDAKI HATA: MotorControlConnector'da MC13 "PWM_CHW_L, PWM_CHU_EN"
yaziyor; MC5=PWM_CHU_EN ve MC9=PWM_CHV_EN oldugundan MC13 PWM_CHW_EN olmali.
Tablo ice alinirsa DUZELTILEREK alinmali - koru kopya yapilmamali.

ILK SOMUT CIKTI (kullanici tanimi): secilmis bir STM32 ve belirlenmis
elektriksel gereksinimler icin kontrol, olcum ve koruma sematigini BIRLIKTE
ureten ornek kart. Gerilim, akim, MCU/paket ve surus yontemi uydurulmayacak -
kullanicidan alinacak.

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

## Kicad-38l - Motor surucu sematik otomasyonu icin blok ve pin sozlesmeleri

- oncelik: P2  |  durum: open  |  tur: feature

Kicad-7i5 beyin firtinasi; kullanici inverter ile guc elektronigi tabanli motor surucu kartlarini kastettigini netlestirdi. ONERI, uygulama karari degil: mevcut F103 niyet/BuildPlan temelini version 2 typed portlarla buyut. Blok instance kimligi ve yerel ag ad alani (faz_U/faz_V/faz_W), gerilim araligi/yon/kaynak/alici portlari, farkli guc alanlari; cok sayfa ve cok birimli sembol. Mevcut expand_intent ayni sablon tekrarini reddediyor; generate cok birimli sembolu, canli snapshot alt sayfayi reddediyor. Sablon katalogu: STM32 cekirdek+debug+besleme; Arduino profili modulu/shieldi ve ciplak MCUyu ayirsin; motor surucude gate driver, faz yarim koprusu, akim olcumu, DC bus olcumu, sicaklik, fault/enable ve donanimsal asiri akim->timer break yolu. MCU pin cozumleyici timer CHx/CHxN, ADC tetik/kanal, break, SWD ve iletisim cakismalarini gostersin. Tekrar uretimde kalici UUID ve blok kimligiyle yalniz fark uygulansin, kullanici duzenlemeleri korunsun. Gorsel blok yerlesimi ve kontrollu sematik-PCB esitleme takip eder. Ilk dikey dilim: net elektriksel gereksinimleri belirlenmis tek bir motor surucu kontrol/olcum/koruma sematigi; gerilim, akim, MCU/paket ve surus yontemi uydurulmayacak. Kaynak: ST Motor Control Boards Description (PWM ayni timer, ADC, dead time ve pin gereksinimleri), KiCad 10.0 schematic docs; resmi Arduino UNO R3 sematigi ornek profil.

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

## Kicad-ihy - Canli sematik performansini netlist tekrarlarini azaltarak iyilestir

- oncelik: P2  |  durum: open  |  tur: task

Kicad-7i5 incelemesi, uygulama degisikligi yapilmadi. 2026-09-22 kurulu nightly 10.99.0-3671-gbe90a7e200 ile C:/tmp icinde 26 sembollu gercek proje kopyasi, headless IPC, komut basina 3 tekrar. Medyan onizle/uygula saniye: R1=12k 0.404/0.465; 2C 1.826/0.444; 20C 1.845/0.486; 2C+2R 2.815/0.476. Yazma RPC medyani 15.9-19.2ms; uygulama suresi commit ve son dogrulamayi da icerir. Toplam netlist CLI sayisi 2/4/4/6, toplam netlist sureleri 0.533/1.222/1.202/1.750s. Hem KicadCli.export_netlist hem sch_verify.export_netlist olculdu; yalniz birini saymak iki cagrinin eksik sayilmasina yol acar. Tablo gercek gorunur GUI uctan uca gecikmesi degil, worker prepare/apply cekirdegidir; Python surec baslatma+import ayri medyan 0.267s. Direct get_netlist bu sunucuda 44 neti 0.022s tek denemede dondurdu; XML ile semantik esdegerlik, pin UUID-ref eslemesi ve multi-sheet henuz dogrulanmadi. Oneri: butun degisikligi tek planda topla ve once/sonra netlist denetimini plan seviyesinde yap; dogrudan API netlistini diferansiyel testle kabul et; surumu ayri tutulan kalici worker/okuyucu daha sonra. SHA256 eski plan, ISC_OK, tek undo ve son dogrulama korunacak. Sonraki olcumler 50/200/500 sembol, soguk/sicak, hata/zaman asimi ve GUI gecikmesini ayirmali. API zaten toplu CreateItems kullaniyor; sembol basina IPC yazma darboğazi yok. Ham veri C:/tmp/pcbqa-schematic-review-results.json.

## Kicad-tv3 - [bug] yuksek-hiz preseti: olmayan arayuz icin 'net bulunamadi' hatasi uretiyor

- oncelik: P2  |  durum: open  |  tur: bug

TIDA-010025 (uc fazli evirici, USB/Ethernet YOK) uzerinde yuksek-hiz preseti
4 ERROR uretti ve dordu de ayni sekilde yanlis:

  [error] hs-ethernet-cift-eslestirme: net bulunamadi: TRD0_P, TRD0_N
  [error] hs-ethernet-cift-eslestirme: net bulunamadi: TRD1_P, TRD1_N
  [error] hs-usb-cift-eslestirme     : net bulunamadi: USB_DP, USB_DM
  [error] hs-usb-cift-eslestirme     : net bulunamadi: D+, D-

KOK SEBEP: kural, arayuzun VARLIGINI degil, net adlarinin varligini sartliyor.
Arayuz kartta hic yoksa "net bulunamadi" bir HATA olarak raporlaniyor. Oysa
USB'si olmayan bir kartta USB kuralinin dogru davranisi SUSMAKTIR.

Bu, projenin kendi ilkesine aykiri: "testler davranistan cok SESSIZLIGI
korur; saglam bir gercek kartta kurallar sifir bulgu uretmelidir."

ETKI: yuksek-hiz preseti USB/Ethernet'i olmayan HER karta uygulandiginda 4
sahte hata verir. Skorlamada da agirlik tasidigi icin skoru bozar.

ONERI (uygulanmadi, karar kullanicinin): eslestirme kurallari icin "net yoksa
sessiz gec" varsayilani. Arayuzun BEKLENDIGINI soylemek isteyen, bunu niyet
dosyasinda ayrica beyan etmeli - kuralin kendisi varsayamaz.

DOGRULAMA VERISI: kart scratchpad'de kalici degil; yeniden uretmek icin
kicad-cli pcb import --format altium ile TIDA-010025_PCB.PcbDoc cevrilir.

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

## Kicad-ik9 - Canli PCB komutunun tek Ctrl+Z oldugunu GUI'de olc; flip/iz yazma degerlendir

- oncelik: P3  |  durum: open  |  tur: task

Kicad-7d2 takibi: canli_pcb yazmasinin KiCad undo yiginina tek islem girdigi bu komutla GUI'de yeniden olculmedi. Ayrica yuz degistirme (flip) ve iz/via yazma API guvenligi arastirilmali.

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
