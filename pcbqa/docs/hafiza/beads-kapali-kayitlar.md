# Kapali beads kayitlari

> Beads kayitlari (`bd list --json`). Her kayit bir kararin ya da
> olcumun gerekcesini tasir; kod bunlari anlatmaz.

## Kicad-76v - Pin adlari pad'den okunmuyordu - function: kurallari sessizce etkisizdi

- oncelik: P0  |  durum: closed  |  tur: bug
- kapanis: 2026-08-28T00:13:42Z

netlist_from_board pinfunction'i BOS birakiyordu ve docstring'i 'pin islev
adlari yalnizca sematikten gelir' diyordu. YANLISTI: 19 gercek KiCad demo
kartinin hepsinde pad'lerde pinfunction var (vme-wren 6828, jetson 2875,
video 1797...).

Etkisi sessizdi: function: seciciSini kullanan TUM kurallar hicbir zaman
eslesmiyordu. buck-giris-kondansatoru (VIN), buck-sw-induktor (SW),
buck-fb-bolucu (FB), ldo-giris/cikis-kondansatoru - hepsi sifir bulgu
uretiyordu ve bu 'temiz kart' gibi gorunuyordu.

NASIL BULUNDU: alt-devre tanima icin korpusta buck converter aranirken hicbiri
bulunamadi. Once 'demolarda buck yok' sandim; taramayi gevsetince pin adlarinin
tamamen bos oldugu ortaya cikti. Ham dosyada (pinfunction "A2") acikca
duruyordu. Yani bir varsayimi sinamak baska bir hatayi acti.

Duzeltmeden sonra ayni tarama UC buck buluyor (CM5_MINIMA_3, jetson,
One-Air-Max) ve buck on ayari anlamli bulgu uretiyor (once sifirdi).

Duzeltme: pcb.py Pad.function + netlist.py aktarimi + yanlis docstring.
Test: tests/test_calibration.py PinFunctionTests.
Commit: 0f8178b

## Kicad-eb9 - KiCad 5 kartlari SESSIZCE bos okunuyor - skor 100 veriyor

- oncelik: P0  |  durum: closed  |  tur: bug
- kapanis: 2026-08-28T11:24:15Z

KiCad 5 dosyalarinda footprint dugumu '(module ...)' adini tasir; KiCad 6+ 'footprint' der. pcb.py:651 yalnizca children(root,'footprint') donuyor.

SONUC: 43 modullu gercek bir kart 0 bilesen olarak okunuyor, parse_warnings 0 kaliyor ve uretim on ayari SKOR 100.0 / sifir bulgu veriyor. Yani KiCad 5 projesi acan kullaniciya 'kartiniz kusursuz' deniyor.

Bu, projedeki sessiz hata sinifinin BESINCI ornegi (HANDOFF 21.6 pinfunction, 21.10 model yolu, 21.13 baglanmamis decoupling_counts, 21.14 ayrik sicak dongu) ve en kotusu: digerleri tek kural sustururken bu TUM kurallari susturuyor.

Bulunus yolu: Kicad-xpi icin gercek ayrik buck karti indirildi (LM5116, KiCad 5.1) ve taniyici sifir dondurdu. Dogrulama isi, dogrulamaya baslamadan once bir hata buldu.

YAPILACAK:
1. EN AZINDAN gurultulu basarisizlik: modul var ama footprint yoksa hata ver. Sessiz 0 bilesen kabul edilemez.
2. Mumkunse 'module' takma adiyla KiCad 5 destegi (yapi buyuk olcude ayni).
3. Genel koruma: 0 bilesenle okunan kart supheli - harness bunu bildirmeli.

## Kicad-vf0 - Iz ve via netleri NUMARA olarak okunuyor - trace_width ve via_current hicbir kartta calismadi

- oncelik: P0  |  durum: closed  |  tur: bug
- kapanis: 2026-08-28T11:24:16Z

KiCad .kicad_pcb'de segment/via/arc dugumleri net'i yalnizca NUMARA ile tasir: '(net 2)'. Ad, kartin kokundeki net tablosundadir: '(net 2 "+3.3V")'. Bu KiCad 5'te de 9'da da boyle.

pcb.py _node_net() son elemani aliyor, yani iz/via icin net adi '2' oluyor.

OLCULDU (video.kicad_pcb, KiCad 9, 7932 iz):
  pad netleri  -> AD   ('+3.3V')  dogru
  zone netleri -> AD   ('GND')    dogru
  iz netleri   -> NUMARA ('2')    %100 yanlis
  via netleri  -> NUMARA          yanlis

SONUC:
  * trace_width kurali '+5V netinde yonlendirilmis iz yok' info'su veriyor -
    7932 izi olan bir kartta. Ceza 0, yani skorda GORUNMEZ.
  * via_current ayni sekilde.
  * copper_area_mm2('+5V', sources=('track',)) = 0.0 (zone 19495, pad 265).

Yani 16 kural tipinden IKISI (on ayarlarda weight 12 ve 10, scale:true) hicbir
gercek kartta bulgu uretmemis. Sessiz hata sinifinin ALTINCI ve en genis ornegi.

Bulunus yolu: Kicad-eb9 (KiCad 5) arastirilirken iz netlerinin sayisal oldugu
fark edildi ve KiCad 9'da da ayni cikti.

YAPILACAK: kokteki '(net N "AD")' tablosunu oku; iz/via/zone netini sayisalsa
tablodan coz. Sonra KALIBRASYONU YENIDEN OLC - bu kurallar ilk kez gercekten
calisacagi icin skorlar degisebilir.

## Kicad-170 - Canli PCB arayuzu ve bagimlilik tanisini dogrula

- oncelik: P1  |  durum: closed  |  tur: task
- kapanis: 2026-09-07T15:55:53Z

Kicad-rfz kapsaminda tamamlanan 2026-09-07 parcasi: gercek paket import denetimi, erisim hatasini eksiklikten ayirma, Canli sekmesi, mevcut bellekten onizleme ve tek undo ile uygulama, eski/yanlis kart reddi. 78 ilgili test gecti ve KiCad 10.0.4 test kopyasinda 16 parca canli tasinip geri yuklendi. Sematik destegi Kicad-5be altinda tamamlanmamis durumda.

## Kicad-43c - Kural motoru IPC-2221B kullanir; dT ve bakir agirligi parametredir

- oncelik: P1  |  durum: closed  |  tur: task
- kapanis: 2026-08-27T17:47:38Z

**Problem:** Akima gore iz genisligi kurali icin hangi standart kullanilmali?
IPC-2221B mi IPC-2152 mi? Iki bagimsiz arastirma ajani BIRBIRIYLE CELISEN
sonuc verdi: biri "IPC-2152 %12-20 daha dar", digeri "IPC-2152 temel egrisi
IPC-2221'den DAHA muhafazakar" dedi.

**Karar:** Kural motoru **IPC-2221B** kullanir. `delta_t_c` ve `copper_oz`
PARAMETRE olarak alinir; tek bir "dogru sayi" iddia edilmez. Ayrica `method`
secenegi ile ROHM'un pratik kurali (1 mm/A @ 1 oz) da secilebilir.

**Neden:** Hesap yapilip Jouppi'nin "The Value of IPC-2152" makalesi okununca
iki ajanin da kismen hakli oldugu gorildu:
- IPC-2152'nin CIPLAK temel egrisi (Figure 5-1/5-2) IPC-2221 dis katmanindan
  daha muhafazakardir: 3 A / 1 oz / 10 C -> IPC-2221 1.37 mm, IPC-2152 2.10 mm.
- IPC-2152 "gevsek" hale ancak carpanlar (duzlem yakinligi, kart kalinligi,
  ortam) uygulaninca gelir. Duzlem carpani buyuk: hesaplanan 30 C artis
  gercekte ~9 C olabiliyor.
- IPC-2152'nin ham tablolari teliflidir ve acik bir formulu yoktur;
  IPC-2221'in formulu aciktir: A = (I/(k*dT^0.44))^(1/0.725).

Ayni akim icin savunulabilir kaynaklar 3.3 KAT farkli sonuc veriyor
(3 A: ROHM 3.00 / IPC-2152 2.10 / IPC-2221@10C 1.37 / IPC-2221@20C 0.90 mm).
Bu yuzden tek sayi dayatmak yanlis olurdu.

**Etkilenen dosya ve semboller:**
- `pcbqa/pcbqa/ipc2221.py`: `trace_width_mm()`, `current_capacity_a()`,
  `clearance_mm()`, `_TABLE_6_1`, `rohm_width_mm()`, modul docstring'i
- `pcbqa/pcbqa/rules.py`: `_check_trace_width()` (`method` parametresi)
- `pcbqa/docs/tasarim-kurallari/01-anahtarlamali-guc.md` 1.7
- `pcbqa/docs/tasarim-kurallari/02-uretilebilirlik-ipc.md` 2.2

**Denenip basarisiz olan yaklasimlar:** Ilk yazilan modul docstring'i
"IPC-2152 tipik olarak %12-20 daha dar" diyordu - eksik bir dogruydu,
duzeltildi.

**Dogrulama:** `tests/test_ipc2221.py` (15 test). Beklenen degerler
dokumantasyondaki tablolardan; o tablolar da yayinlanmis hesaplayicilarla
capraz dogrulandi. Altium'un yayinladigi ornek (B1, 580 V -> 0.45 mm) testte.
Gercek kartta olculdu: VCC izi 0.8 mm, 2 A icin IPC-2221 gecer (0.781 mm),
ROHM kalir (2.0 mm).

**Ilgili commit SHA:** henuz commit edilmedi.

**Geri alinabilecegi kosullar:** IPC-2152'nin carpan tablolarina yasal erisim
saglanirsa ve carpanlar uygulanabilir hale gelirse ikinci bir `method` olarak
eklenebilir. IPC-2221'i tamamen kaldirmak icin gecerli bir neden YOK -
muhafazakar taraftadir.

## Kicad-5be - Eeschema 10.0.4 IPC'de oge komutlarini uygulamiyor - canli sematik yazma yok

- oncelik: P1  |  durum: closed  |  tur: task
- kapanis: 2026-09-08T08:19:51Z

OLCUM (2026-08-30, KiCad 10.0.4):
  GetOpenDocuments(DOCTYPE_SCHEMATIC) -> CALISIYOR, KicadOtomasyon1.kicad_sch donuyor
  GetItems (ayni belge, dogru header)  -> 'no handler available for request of
                                          type kiapi.common.commands.GetItems'

Ikili tarama da ayni yone isaret ediyor: _pcbnew.dll icinde 'GetItems' 65 kez,
_eeschema.dll icinde 1 kez geciyor.

Handler'lar ACIK EDITORE gore kayitli: bagimsiz eeschema.exe surecinin API'si
kicad.exe'nin soketine (Temp\kicad\api.sock) hic katilmiyor; sematik editoru
PROJE YONETICISINDEN acilmali.

kipy 0.7.1 tam bir Schematic sarmalayicisi sunuyor (create_items, get_lines,
get_symbols) ve KICAD_API_VERSION 10.0.1 diyor, ama kendi
schematic_types_pb2'sinde sembol/tel tipleri YOK - paket kendi icinde tutarsiz.

Eeschema disaridan degisen dosyayi da FARK ETMIYOR (_eeschema.dll icinde
'changed on disk' benzeri bir uyari metni yok).

SONUC: KiCad 10.0.4'te sematige CANLI mudahale mumkun degil. Denenmemis tek
yol: RevertDocument/SaveDocument - dosyayi yazip Eeschema'ya yeniden okutmak.
Bunun icin sematik editoru proje yoneticisinden acik olmali.

DIKKAT: bicimsiz protobuf istekleriyle KiCad'i COKERTTIM (bos GetItems vb).
Canli sondalamada yalnizca tam bicimli istek gonder, her adimda surecin
ayakta oldugunu dogrula.

## Kicad-6r2 - API'siz baglanti: KiCad'in kendi Python'undan surec-ici uygulama

- oncelik: P1  |  durum: closed  |  tur: feature
- kapanis: 2026-08-28T17:34:09Z

IPC API sunucusu KiCad'de VARSAYILAN KAPALI (kicad_common.json api.enable_server=false) - dagitimda her kullanicidan Tercihler'i acmasini istemek kabul edilemez. Cozum: swig_apply.py (pcbnew SWIG, surec-ici, kurulum adimi yok) + confload.py/bundle.py (pyyaml artik istege bagli; YAML kaynak, JSON calisma zamani kopyasi). Sozlesme ipc.py ile ayni. 14 test, 5'i KiCad'in yorumlayicisinda alt surec olarak kosuyor.

## Kicad-805 - Evre 3b onunde karar: uretilen kart yonlendirilecek mi

- oncelik: P1  |  durum: closed  |  tur: task
- kapanis: 2026-08-28T16:20:06Z

Uretilen kart yonlendirilmemis olunca bakir kurallari (trace_width, via_current, clearance_voltage, copper_area) SUSUYOR - skor yarim konusuyor. ORNEK-F103 OLCUMU: KiCad DRC'si 52 'unconnected_items' bildiriyor, bizim kurallarimiz 0 bulgu ve skor 100 diyor. Yani 'kusursuz' skoru yonlendirilmemis bir karta veriliyor. SECENEKLER: (a) freerouting gibi dis autorouter entegrasyonu - cikti bizim kurallarimizla denetlenir, bakir kurallari konusmaya baslar; (b) yonlendirilmemis skoru kabul edip HPWL/yerlesim kurallariyla yetinmek ama bunu skorun icinde GORUNUR kilmak (or. 'yonlendirilmemis' bilgisi rapora yazilsin, tam puan verilmesin). Bu karar 3b (uretim-degerlendirme dongusu) baslamadan verilmeli: N varyanti yarim konusan bir skorla siralamak yaniltici olur.

## Kicad-8ow - Evre 3c: tasarim seviyesi veri toplama (varyant siralayici verisi)

- oncelik: P1  |  durum: closed  |  tur: feature
- kapanis: 2026-08-28T17:03:00Z

ml/collect_design.py + samples/niyetler/ (7 niyet) + 20 test. Veri ml/dataset.py bicimini paylasiyor, mevcut train.py/metrics.py dogrudan tuketiyor (dogrulandi).

## Kicad-8vp - Canli mod KiCad'in Python'unda calismaz: kipy ve bagimliliklari yok

- oncelik: P1  |  durum: closed  |  tur: task
- kapanis: 2026-08-30T14:43:56Z

OLCUM (2026-08-30, KiCad 10.0.4):
  KiCad python.exe -c 'import kipy'          -> ModuleNotFoundError
  google.protobuf / pynng / nng              -> hicbiri yok
  kicad-python 0.7.1 gerektirir: jsonschema>=4.23, protobuf>=5.29,<6,
                                 pynng>=0.9,<0.10, typing_extensions

SONUC: dagitilan uygulama KiCad'in kendi Python'uyla kosuyor (baslat.py),
ama CANLI MOD orada import edilemez. API'siz mod etkilenmiyor - onun hicbir
calisma zamani bagimliligi yok.

GELISTIRME ORTAMINDA sorun yok: .venv (3.13) icinde kipy 0.7.1 var, sonda
oradan kosabilir.

SECENEKLER (karar verilmedi):
  a) 'pcbqa kurulum --canli-bagimliliklar': KiCad python'uyla
     pip install --target <Belgeler>\KiCad\10.0\3rdparty\Python311\site-packages
     pynng'in cp311 win_amd64 tekerlegi var, calisir gorunuyor.
  b) kipy'yi atlayip ham protobuf+nng'yi kendimiz tasimak (pynng yine native).
  c) Canli modu ayri bir yorumlayici gerektiren opsiyonel ozellik ilan etmek.

Ayrica hatirla: kipy 0.7.1'in ust duzey sematik sarmalayicisi zaten bozuk
(BusEntryType yok); ham KiCadClient.send kullaniyoruz.

## Kicad-ab6 - Evre 3a surucusu: insa plani -> .kicad_sch -> pcb_sync -> auto -> skor

- oncelik: P1  |  durum: closed  |  tur: feature
- kapanis: 2026-08-28T15:53:32Z

intent.py'nin urettigi cozumlenmis plani gercek projeye donusturen zincir: bos KiCad proje iskeleti uret, her PlannedComponent icin sch_add.add_symbols(connect=pin=ag) cagir, pcb_sync ile karta yansit, auto ile yerlestir, skorla dogrula. Plan cikti dili sch_add ile bire bir uyumlu tasarlandi (pin numarasi = ag adi). Ek is: kullanilmayan GPIO'lara no-connect bayragi (ERC gurultusu). Bkz. HANDOFF 22.4.

## Kicad-akm - Bakir dokum (zone) okuma - uc kritik guc kuralini acar

- oncelik: P1  |  durum: closed  |  tur: feature
- kapanis: 2026-08-27T23:38:50Z

Arastirmanin en yuksek getirili eksigi (docs/tasarim-kurallari/README.md
'Olculemeyenler'). Tek basina uc kurali olculebilir hale getirir:

  - Sicak dongu ALANI: TI AN-2155'in OLCTUGU deney - 6 mm2 iyi, 12 mm2 sinirda,
    18 mm2 kotu (SW spike 2.5 V -> 6.1 V, EMI marji 8.3 -> 6.7 dB).
  - SW bakir alani <= 100 mm2 (ROHM 66AN015E Oncelik 2).
  - Termal bakir alani: 1 W icin ~20 cm2 (TA=70 C'de, Richtek AN044 SOT-223
    olcum egrisi). TI SLPA015'in 1 in2 kurali ~2 kat iyimser.

Ayrica indüktör altinda bakir olmamasi (ROHM, >= 3 mm temizlik) ve referans
duzlem surekliligi (TI SPRAAR7E) de buna bagli.

Gereken: .kicad_pcb icindeki (zone ...) dugumlerinin okunmasi - poligon
sinirlari, katman, net, doldurulmus alan. pcb.py'daki Track/Via/Pad okumasiyla
ayni desende; geom.py'da poligon alani ve mesafe zaten var.

Not: zone poligonlari Track/Via'dan daha karmasik - dolgu (filled_polygon)
alt dugumleri, thermal relief, keepout bolgeleri var. Ilk adim yalnizca
sinir + katman + net okumak olabilir.

## Kicad-ec5 - auto skoruna keep_apart cezasi ekle (uzaklastirma kisitlari)

- oncelik: P1  |  durum: closed  |  tur: task
- kapanis: 2026-08-27T21:35:48Z

**Problem:** `auto` yerlestiricisi yalnizca HPWL (mesafe) kucultmeye calisir.
Ama uretici app-note'larindaki kurallarin sasirtici bir kismi "yaklastir"
degil **"uzaklastir"** der:

- FB izi -> indüktör >= 10 mm (ROHM 66AN015E #4-1)
- FB izi -> serbest gecis diyodu >= 10 mm (ROHM 66AN015E #4-1)
- I2C pull-up -> sicaklik sensoru >= 10 mm (TI SNOA986A, oz-isinma olcumu bozar)
- CIN GND -> COUT GND >= 10 mm (ROHM, giris gurultusu GND uzerinden cikisa
  tasinmasin)
- Ethernet on ucu -> diger yuksek hizli izler >= 7.62 mm (Microchip DS00002054A)

Yalnizca mesafe kucultmeye calisan bir yerlestirici bu kisitlari SISTEMATIK
olarak ihlal eder.

**Karar (bu asamada):** Kural motoruna `keep_apart` kural tipi eklendi; ihlal
RAPORLANIYOR. Skor fonksiyonuna henuz ceza EKLENMEDI.

**Neden:** Once olcebilmek, sonra optimize etmek. Skor fonksiyonunu degistirmek
Faz A/E'de gorildugu gibi riskli - once bu kisitlarin gercek kartlarda ne
siklikta ihlal edildigini gormek gerekiyor.

**Etkilenen dosya ve semboller:**
- `pcbqa/pcbqa/rules.py`: `_check_keep_apart()`, CHECKS kaydi
- `pcbqa/pcbqa/presets/buck.rules.yaml`: `buck-fb-induktorden-uzak`,
  `buck-fb-diyottan-uzak`
- `pcbqa/pcbqa/presets/lineer-koruma.rules.yaml`: `sensor-pullup-uzak-dursun`,
  `manyetik-sensor-guc-izinden-uzak`

**Kalan is (bu bead ACIK kalir):** `placement/` skoruna `keep_apart` cezasi
eklemek. Aday yer: `PlacementContext.evaluate()` uzerinden kural bulgularini
skora katan mevcut mekanizma.

**Bilinen sinir:** `keep_apart` bilesen MERKEZLERI arasi mesafeyi olcer, iz
guzergahini degil. "FB izi indüktörden 10 mm uzak" kurali bu yuzden bir
YAKLASIMDIR - FB bolucu induktore yakinsa izi de yakin gecer varsayimina
dayanir.

**Dogrulama:** `tests/test_copper_rules.py::KeepApartRuleTests` (6 test).

**Ilgili commit SHA:** henuz commit edilmedi.

## Kicad-ek2 - Guc sembolleri sematige hic eklenemiyordu - kalkan netlist'te olmayan referansi bekliyordu

- oncelik: P1  |  durum: closed  |  tur: bug
- kapanis: 2026-08-31T10:45:56Z

BELIRTI: 'pcbqa.sch_add --lib-id power:+24V --apply' -> 'KALKAN REDDETTI:' ve
mesaj TAMAMEN BOS. Kuru calisma geciyor, uygulama dusuyor.

KOK SEBEP: KiCad netlist'inde SANAL semboller (#PWR, #FLG) bilesen olarak HIC
gorunmez. Olculdu: power:+24V eklendikten SONRA netlist bilesen kumesi hic
degismiyor (17 -> 17). sch_add ise kalkana beklenen eklenenler olarak
{s.ref for s in plan.symbols} veriyordu, yani '#PWR2'yi de bekliyordu.
compare_additive'deki 'set(added) == set(expected_added)' sarti bu yuzden HER
ZAMAN dusuyordu: hicbir guc sembolu eklenemiyordu.

Ayni kok sebep daha once connect.py'nin hakeminde de cikmisti (netlist'te guc
pini aranmasi). Yani bu SINIF bir hata: 'netlist'te gorunmeyen seyi netlist'te
aramak'.

IKINCI KUSUR: red mesaji bostu. sch_add yalnizca regrouped/removed/lost
listelerini basiyordu; 'eklenenler beklenenle tutmadi' durumunda ucu de bos
oldugu icin ekranda gerekcesiz bir 'KALKAN REDDETTI:' kaliyordu.

DUZELTME:
  sch_add.py  beklenen listesinden '#' ile baslayan referanslar cikarildi
  sch_add.py  red mesaji artik diff.describe() + diff.details() basiyor

DOGRULAMA: 4 guc sembolu (+24V/+12V/+5V/+3V3) eklendi, kalkan gecti, KiCad'in
kendi netlist'i 17 bileseni dogru degerlerle okudu. tests/test_sch_add.py
34 -> 37 test: guc sembolu eklenebilmeli, sanal sembol netlist'te beklenmemeli,
ret her zaman gerekce icermeli.

## Kicad-fqn - Bagimsiz uygulama: tek giris noktasi + baslatici + bagimliliksiz YAML

- oncelik: P1  |  durum: closed  |  tur: feature
- kapanis: 2026-08-28T18:03:34Z

Urun sekli karari: BAGIMSIZ UYGULAMA (kullanici sectiler). 'Bagimsiz' = ayri Python kurulumu gerektirmez; KiCad'siz calismaz (kicad-cli ve kutuphaneler zorunlu). KiCad kendi python 3.11.5'ini getirdigi ve pcbqa'nin calisma zamani bagimliligi olmadigi icin ikinci yorumlayici/PyInstaller gereksiz. Parcalar: app.py (tek giris + tani), pcbqa.cmd (baslatici), minyaml.py (bagimliliksiz YAML), KURULUM.md.

## Kicad-i6z - Baslatici PYTHONPATH'e guveniyordu; KiCad'in Python'u onu siliyor

- oncelik: P1  |  durum: closed  |  tur: bug
- kapanis: 2026-08-30T14:21:29Z

KiCad'in sitecustomize.py'si (bin/Lib/site-packages) site asamasinda 'sys.path = []' yapip yeniden kuruyor. Bu, PYTHONPATH girdilerini de cwd'yi de siliyor.

SONUC: pcbqa.cmd 'python -m pcbqa.app' cagiriyordu ve YALNIZCA calisma dizini paket klasoruyken calisiyordu. Baska bir klasorden 'No module named pcbqa' (cikis 1). Testler cwd=PROJECT ile kostugu icin goremedi.

COZUM: paketin yaninda duran baslat.py onyukleyicisi. CPython betik klasorunu site'dan SONRA sys.path[0]'a koyuyor, yani silmeden kurtuluyor; baslat.py ayrica kendi klasorunu acikca ekliyor.

AYNI KOK SEBEP ikinci yerde: tests/test_swig_bridge.py run_in_kicad da PYTHONPATH veriyordu; yalnizca cwd sayesinde calisiyordu. Betik onsozune sys.path.insert eklendi, cwd bilerek PROJECT.parent yapildi.

DOGRULAMA: C:\Windows, C:\Users, proje koku ve paket klasorunden 'pcbqa --version' -> hepsi cikis 0. Yeni testler: test_launcher_runs_from_an_unrelated_directory, test_pythonpath_alone_is_not_relied_upon, test_bootstrap_sits_next_to_the_package.

## Kicad-o2c - Evre 3a: niyet semasi + STM32 sablon kutuphanesi (intent.py + templates/)

- oncelik: P1  |  durum: closed  |  tur: feature
- kapanis: 2026-08-28T15:04:15Z

Uretken tasarimin ilk adimi. YAML niyet beyani ('STM32F103 + USB + 3V3 LDO + kristal') -> sablon kutuphanesinden bilesen/baglanti planina acilim. Kapsam: intent.py (sema dogrulama, sablon yukleme, acilim, symlib ile pin cozumleme, CLI), pcbqa/templates/ altinda STM32F103C8 ailesi (mcu, ldo, kristal, usb, swd), testler. Sematigi fiilen ureten surucu AYRI is (3a devami). Deger/esik kaynaklari: ST AN2586 (decoupling/NRST/BOOT0), AN2867 (kristal yuk kondansatoru).

## Kicad-os1 - Faz 1a: agirlik mekanizmasi (Rule.weight, Finding.weight)

- oncelik: P1  |  durum: closed  |  tur: feature
- kapanis: 2026-08-27T22:34:47Z

report.py su an yalnizca severity sayiyor: PENALTY = {error 8, warning 2, info 0}.
Olculmus etkisi olan kural ile kaynaksiz muhendislik secimi ayni cezayi aliyor.

Yapilacak:
- Rule sinifina weight: float | None (ust duzey alan, spec'e sizmamali)
- Finding sinifina weight: float; run_rules MERKEZI olarak doldursun (rule_type gibi)
- report.score PENALTY[severity] yerine f.weight kullansin
- weight verilmemisse PENALTY[severity]'den turetilsin

Kabul: 279 test degismeden gecmeli. weight 16 -> error varsayilaninin 2 kati.
weight 0 -> skoru etkilemesin ama raporda gorunsun.

Dosyalar: pcbqa/rules.py, pcbqa/report.py, tests/test_score_weights.py (yeni).
Ayrinti: pcbqa/docs/yol-haritasi-skorlama.md

## Kicad-qav - Baglama fiili: 'yap' katmani eklerken baglar

- oncelik: P1  |  durum: closed  |  tur: task
- kapanis: 2026-09-04T10:47:06Z

KARAR (2026-09-04): "yap" katmanina BAGLAMA fiili eklendi (Kicad-d8f/1).

PROBLEM: `pcbqa yap "10 kapasitor ekle"` sayfaya ON TANE BAGLANTISIZ sembol
birakiyordu. Kullanicinin gercekten yazdigi cumle "...ve hepsini VCC-GND
arasina bagla"ydi. Alt katman hazirdi (sch_add.add_symbols(connect=...)
etiketi/teli ciziyor, _expected_joins ile kalkana "bu pin su pinlerle ayni
aga girmeli" diyor); eksik olan KALIBI o cagriya ceviren katmandi.

KARAR:
  1. Kalip cumleden EN BASTA ayrilir, ekleme cozumlemesinden ONCE
     (_baglama_ayir). Kalip: "<A> ile|ve|- <B> arasina|arasinda",
     "between <A> and <B>". Cikan connect listesi EKLENEN HER sembole
     uygulanir.
  2. TURLER tablosuna "uclar" (pin numaralari) ve kutuplu turlerde
     "uc_adlari" eklendi. Once yazilan hedef 1. uca gider.
  3. Ag adinin YAZIMI uygula() asamasinda sematige sorulur (_aglari_coz):
     birebir varsa aynen, yalnizca harf farkiyla varsa duzeltilir + NOT,
     hic yoksa UYARI + mevcut adlar.
  4. HENUZ_YOK'tan "bagla"/"connect" cikarildi; BAGLA_FIILLERI ve
     KAPSAM_SOZCUKLERI tablolari eklendi.

GEREKCE:

  * Kalip neden en basta ayrilir - iki olculmus sebep: (a) ayrac "ve"dir,
    "VCC ve GND arasina" cumlede kalirsa _AYRAC onu ikiye boler; (b)
    "toprak" hem AG adi hem BILESEN turudur (power:GND), kalip ayrilmazsa
    "VCC ile toprak arasina bagla" sayfaya istenmeyen bir toprak sembolu
    de ekler.
  * Ag adi neden sematige sorulur: KiCad'de ag adlari buyuk/kucuk harfe
    DUYARLIDIR. "vcc" yazan kullanici VCC agina baglanmis olmaz. NETLIST
    KALKANI BUNU YAKALAMAZ - yeni ag olusturmak da gecerli bir islemdir,
    kalkan yalnizca ESKI devrenin degismedigini olcer. Tek koruma bu
    esleme ve uyaridir.
  * Birden fazla ekleme varsa "hepsini" SARTTIR: baglamanin hangi gruba
    ait oldugu tahmin edilmez.
  * Kutuplu bilesende yon ELEKTRIKSEL bir karardir, cumle onu soylemez;
    secilen yon NOT olarak yazilir, sessizce secilmez.

BASARISIZ / DUZELTILEN DENEMELER:

  * YAPI SOZCUGU AG ADI SANILDI. Ayrac " ve " oldugu ve regex en soldan
    esledigi icin "2 diyot ekle ve VCC-GND arasina bagla" cumlesinde
    hedefler ("ekle", "VCC-GND") diye okundu - iki diyotun katoduna "ekle"
    adinda bir ag yazilacakti. Hedef artik yapi sozcugu (fiil, dolgu,
    kapsam, sayi) olamaz. BILESEN sozcukleri bu listeye GIRMEZ: "LED",
    "CLOCK" gercek ag adlaridir.
  * Reddedilen eslesmeden sonra tarama hedefin BASINDAN devam ediyordu;
    "ekle" bu kez "kle" diye eslesti. Tarama artik hedefin SONUNDAN devam
    eder (_kalip_bul).
  * uygula() ASAMASINDAKI NOTLAR HIC BASILMIYORDU. main() once
    yorum.describe() yaziyor, sonra uygula'yi cagiriyordu; uygula'nin
    ekledigi notlar - "VCCC diye bir ag YOK" uyarisi ve DAHA ESKI olan
    dry-run numaralama notu - ekrana hic cikmiyordu. (Bu, baglamadan once
    de var olan bir hataydi.)
  * "ekle," fiil sayilmiyordu: _TEMIZ kelime sonundan virgul kirpmiyordu.
    "4 kapasitor ekle, hepsini ... bagla" dogal yazimdir ve "fiil yok"
    diye reddediliyordu. Virgul/noktali virgul _TEMIZ'e eklendi.

ETKILENEN DOSYALAR/SIMGELER:
  pcbqa/pcbqa/komut.py - TURLER(uclar, uc_adlari), BAGLA_FIILLERI,
    KAPSAM_SOZCUKLERI, AG_ADLARI, _HEDEF_OLMAZ, _hizali_sade,
    _spanlari_cikar, _kalip_bul, _hedef_temizle, _baglama_ayir,
    _baglantilari_dagit, Baglama, Eylem.baglar, mevcut_aglar, _aglari_coz,
    uygula(connect=), main(yeni notlar), _dagarcik
  pcbqa/tests/test_komut.py - BaglamaTests (18), test_declared_pins_exist,
    test_polarity_names_match_the_library, uctan uca 5 test
  pcbqa/HANDOFF.md 34.6

DOGRULAMA: tests.test_komut 41 -> 67, hepsi OK. Uctan uca: samples/
pic_programmer kopyasina 6 kapasitor yazildi; KiCad'in cikardigi NETLIST'te
her birinin 1. pini VCC, 2. pini GND agina girdi ve ESKI her pinin agi
degismedi.

GERI ALMA KOSULU: kalip listesi buyurse (regex + tablo) yerine model onyuzu
dusunulebilir; sozlesme (Yorum/Eylem) zaten tipli oldugu icin uygulayici,
kalkan ve testler degismez.

## Kicad-raz - Evre 3b: uretim-degerlendirme dongusu (N varyant uret, olc, en iyisini sec)

- oncelik: P1  |  durum: closed  |  tur: feature
- kapanis: 2026-08-28T16:29:39Z

Ayni niyetten N varyant uretip olcup en iyisini secen dongu. OLCULEN GEREKCE: (1) skor uretilen kartta DOYUYOR - 40x28'den 100x70'e kadar hepsi 100.0, yani skor tek basina siralayamiyor; (2) buna karsilik varyant dongusu gercek kazanc sagliyor - sabit 50x35'te 6 tohum HPWL 174.5-216.2 mm, en iyisi %19.3 daha iyi; (3) skorun cozunurlugu dar kartta var - 25x18 -> 24.7, 30x20 -> 74.1, 35x25 -> 100.0, yani 35x25 skoru tam tutturan EN KUCUK kart ve 50x35'in yari alani. SECIM OLCUTU: Evaluation.key mantigi (skor -> hata -> uyari) ile en iyi katman, sonra EN KUCUK ALAN, sonra en dusuk HPWL. Kart alani gercek uretim maliyeti ve skor onu hic gormuyor.

## Kicad-rfz - Canli mod: kurulumda izinle alinan IPC + sematige canli yazma

- oncelik: P1  |  durum: closed  |  tur: feature
- kapanis: 2026-09-08T08:19:52Z

Kullanici KiCad acikken degisiklik istedi (kendi hatasina mudahale edebilmek icin) ve API iznini KURULUMDA alalim dedi. pcbqa/kurulum.py yazildi: api.enable_server'i izinle acar, KiCad calisirken REDDEDER, yedekler, geri alinabilir. ONEMLI DUZELTME: 'KiCad 10'da sematik API'si yok' tespitim YANLISTI - editor_commands BELGE TURUNDEN BAGIMSIZ (CreateItems, ParseAndCreateItemsFromString, BeginCommit/EndCommit) ve DOCTYPE_SCHEMATIC=1 tanimli. BeginCommit/EndCommit degisikligi KiCad'in geri alma yiginina koyar = kullanici Ctrl+Z ile mudahale eder. KALAN: sunucunun bunlari sematik icin gercekten uyguladigi DOGRULANMADI; sonda hazir (scratchpad/sonda_canli.py), API acilinca kosacak.

## Kicad-tm1 - Evre 2: devre dogrulugu kural ailesi (circuit.py)

- oncelik: P1  |  durum: closed  |  tur: feature
- kapanis: 2026-08-27T23:52:05Z

Yol haritasindaki Evre 2 devir promptunun uygulanmasi.

## Kicad-vdt - Pad bakiri sekline gore tam modellenir (aciklik yanlis alarmi)

- oncelik: P1  |  durum: closed  |  tur: task
- kapanis: 2026-08-27T17:47:37Z

**Problem:** `clearance_voltage` kurali saglam bir gercek kartta
(samples/pic_programmer, KiCad'in kendi demosu) hayali aciklik ihlali
uretiyordu. Iki tur yanlis alarm gorildu: once -0.051 mm, sonra 0.000 mm.

**Karar:** Pad bakiri sekline gore TAM modellenir. `Pad.copper_shape()`
`(noktalar, sisme_yaricapi)` doner:
- circle -> tek nokta + r (kusursuz)
- oval   -> uzun eksen boyunca parca + kisa yarim genislik (stadyum, kusursuz)
- rect/roundrect -> donmus dortgen + 0

Aciklik olcumu tek ifadeye iner: `shape_distance(A,B) - rA - rB`.

**Neden:** Pad'i once cevreleyen daireye (kosegen/2), sonra kareye yuvarladim;
ikisi de olculen acikligi bilesen ayak izi mertebesinde kuculttugu icin saglam
kart ihlalli gorundu. TO-92'nin 1.27 mm kosegen araliktaki iki 1.3 mm yuvarlak
pad'i kare kabul edilince koseleri 0.03 mm cakisiyor; gercekte aralarinda
0.50 mm var.

**Etkilenen dosya ve semboller:**
- `pcbqa/pcbqa/pcb.py`: `Pad.size_x/size_y/angle/shape`, `Pad.copper_shape()`,
  `_read_footprint()` (pad boyutu/sekli okuma)
- `pcbqa/pcbqa/geom.py`: `shape_distance()`, `segment_distance()`
- `pcbqa/pcbqa/rules.py`: `_copper_items()`, `_check_clearance_voltage()`

**Denenip basarisiz olan yaklasimlar:**
1. Pad = nokta + cevreleyen daire yaricapi (hypot(sx,sy)/2) -> 0.5 mm fazla
   tahmin, -0.051 mm hayali cakisma.
2. Pad = donmus dortgen (tum sekiller icin) -> 0.03 mm hayali cakisma; yuvarlak
   pad'lerde kose fazlaligi.

**Dogrulama:** `tests/test_copper_rules.py`
- `test_sound_board_at_logic_voltage_is_silent` (5 V'ta sifir bulgu)
- `test_higher_voltage_finds_violation` (60 V'ta 0.6 mm esigiyle bulgu)
- `PadShapeTests` (4 test, sekil basina gosterim)
Tam paket: 277 test, hepsi geciyor.

**Ilgili commit SHA:** henuz commit edilmedi (calisma agacinda).

**Geri alinabilecegi kosullar:** Yalnizca zone (bakir dokum) okuma eklenirse ve
aciklik olcumu poligon tabanli hale gelirse bu gosterim yerini birakabilir.
O durumda bile daire/oval'i dortgene yuvarlamak YANLIStir - yukaridaki iki
yanlis alarm geri doner.

## Kicad-zoi - Faz 1b: orantili ceza (ihlal buyuklugune gore)

- oncelik: P1  |  durum: closed  |  tur: feature
- kapanis: 2026-08-27T22:49:11Z

Ceza su an IKILI: 0.01 mm ihlal ile 2 mm ihlal esit. Oysa 11 kural tipinden
9'u measured/limit zaten dolduruyor.

asim = |measured - limit| / limit
carpan = clamp(1.0 + asim, 1.0, scale_max)   # varsayilan tavan 3.0
ceza = weight * carpan

Tasarim kararlari: yon yok mutlak deger var (bazi kurallarda measured>limit,
bazilarinda <). limit == 0 korumasi SART (courtyard_overlap'te clearance_mm 0.0
yaygin). Tavan sart, yoksa via_current'ta oran patlar. Opt-in (scale: true).

require_on_net ve same_net measured tasimaz - scale verilse bile sabit agirlik,
hata degil sessiz geri dusus.

IKI RISK - atlanirsa is yarim kalir:
1) Yerlestirici bu skoru optimize ediyor. harness --all --suite GERILEME
   kontrolu degisiklikten ONCE ve SONRA kosulup karsilastirilmali.
2) ml/collect.py ornekleri d_score ile etiketli. Skor degisirse
   .work/moves*.jsonl icindeki 49699 ornek bayatlar, yeniden toplanmali.

Ayrinti: pcbqa/docs/yol-haritasi-skorlama.md

## Kicad-0nb - Faz 1c: on ayar kurallarina kaynakli agirlik ver

- oncelik: P2  |  durum: closed  |  tur: task
- kapanis: 2026-08-27T23:01:01Z

presets/ altindaki 28 kurala gercek agirlik. Ilke: kanit gucu agirligi belirler.

olculmus etki (TI AN-2155 sicak dongu)        -> 16-24
standart / sayisal app-note (IPC-2221B, ROHM) -> 8-16
kaynakli ama nitel                            -> 4-8
muhendislik secimi (hs-kristal-regulatorden)  -> 1-2
guvenlik (clearance_voltage, sebeke)          -> en yuksek

Kabul: her weight satirinin yaninda KAYNAGI yazili. Kaynaksiz agirlik yok.

## Kicad-47f - learned hala auto'yu gecmiyor - skor zenginlestikten SONRA da

- oncelik: P2  |  durum: closed  |  tur: task
- kapanis: 2026-08-28T01:52:56Z

HANDOFF 11'deki olcum skor yalnizca severity sayarken yapilmisti. Skor o
zamandan beri degisti (agirlik, orantili ceza, copper_area/component_value/
buck_layout, pin adlarinin okunur olmasi). Olcum tekrarlandi.

SONUC DEGISMEDI: uc ornek kartta learned ile auto arasindaki fark +0.0.

Yolda IKI GERCEK SORUN bulundu ve duzeltildi (ayri commit):
  1. apply_placement yonlendirmeyi gecersiz kilmiyordu -> bakir kurallari
     tasinmis pad'lerle sabit izleri karsilastiriyordu
  2. clearance_voltage 459 ms suruyordu -> yerlestirici 8 s'de 17 deneme
     yapabiliyordu; sinir kutusu filtresiyle 6.2x hizlandi

Duzeltmelerden sonra bile learned = auto.

YANLIS CIKAN HIPOTEZ (kaydedilmeli): 'skor zenginlesince auto zorlanir, o zaman
siralamanin degeri artar' diye dusunmustum. Zenginlesen skor auto'yu
zorlamadi, TAKTI - ve takilmanin nedeni gradyan degil MALIYET idi.

SIRADAKI ADIM icin fikir: learned'in degeri 'ayni butcede daha cok deneme'
demek. Degerlendirme maliyeti dustukce auto zaten daha cok deneme yapiyor, yani
siralamanin marjinal degeri AZALIYOR. learned'in kazanacagi yer, degerlendirmenin
PAHALI oldugu buyuk kartlar olmali (jetson 1125 bilesen). Orada olculmedi.

## Kicad-5or - Karar katmani: propose.py + connect.py (pcbqa bagla)

- oncelik: P2  |  durum: closed  |  tur: feature
- kapanis: 2026-08-30T15:14:41Z

KULLANICI SORUSU: 'bu baglantiyi yaparken kendi zihnini de kullandin mi yoksa
uygulama mi tum isi yapti'. Dogru cevap: TOPOLOJI KARARI BENDEYDI, uygulamada
o karari verecek katman yoktu. Bu is o boslugu kapatti.

propose.py - sayfaya bakip oneri uretir. Kanit: DOSYADA NIYET YAZMAZ AMA
YERLESIM YAZAR.
  hizalama  : iki bos pin ayni x/y'de, arada engel yok, VE birbirinin en yakin
              hizali komsusu (karsiliklilik sarti - tek yonlu yakinlik bir
              tercih yapmak demek olurdu)
  guc-inisi : guc sembolunun bos pini bir tel parcasinin ORTASINA dik iniyorsa
  Kaniti olmayan onerilmez ve ATLANAN PIN ADIYLA SOYLENIR.

connect.py (pcbqa bagla) - karari yurutur. --ag (beyan) / --oner (cikarim).
Junction'i KiCad'in kendi kuraliyla sayar (bir noktada 3+ oge). Yazdiktan
sonra kicad-cli netlist HAKEMDIR.

OLCUM IKI GERCEK HATA BULDU:
1) Ilk oneri 'R1.1 - R1.2' idi = direncin uzerinden KISA DEVRE. Sebep: en
   yakin hizali komsu R1 icin R1.2 (7.62mm), C1.1 degil (15.24mm). Kural:
   ayni sembolun pinleri asla eslesmez - o hizalama sembolun GEOMETRISINDEN
   gelir, kullanicinin yerlesiminden degil.
2) Hakem DOGRU bir tellemeyi reddetti: KiCad netlist'inde guc sembolleri
   dugum olarak HIC GORUNMEZ. Duzeltme: guc icin agin ADINA bakiliyor
   (NetCheck.power_name).

SONUC: uygulama ayni uc parca uzerinde elle verdigim kararin AYNISINI uretti -
uc tel, ayni koordinatlar, ayni junction, gerekceleriyle.

Ornek: samples/uc_parca/  Testler: test_propose 9 + test_connect 19.

## Kicad-99q - Iki dilli bilesen sozlugu: lexicon.py (KiCad kutuphanelerinden, EN/TR)

- oncelik: P2  |  durum: closed  |  tur: feature
- kapanis: 2026-08-31T11:13:42Z

KULLANICI ISTEGI (2026-08-31): 'kicad kutuphanesi uzerinden tum komponent
isimlerini uygulamamiza ekle, ileride makine ogrenimi yaparken tanimasina
yardim olsun, ozellikle kisaltmalarini ve tam isimlerini koy, ornek C:kapasitor,
ingilizce turkce iki turde de'.

YAPILDI: pcbqa/lexicon.py + pcbqa/data/kicad-sozluk.json.gz (424 KB)
  DESIGNATORS  67 onek   (kisaltma -> EN ad + TR ad)
  TERMS        252 terim (EN -> TR)
  PHRASES      31 kalip  (cok kelimeli)
  semboller    22.776    (223 kutuphaneden)
Komut: pcbqa sozluk [--uret] [--ara TERIM]

ONEK ADLARI EZBERDEN DEGIL OLCUMDEN: her onek icin, o oneki kullanan
sembollerin aciklamalarinda en sik gecen kelimeler sayildi ve ad ona gore
verildi. Tablodaki 'ornek' alani o olcumun izidir.
TERIM SECIMI DE OLCUMLU: 45.187 aciklama alani, 266.284 kelime, siklik listesi.

KAPSAM (olculdu): kategori %100.0, Turkce karsilik %94.6.
%100 Turkce HEDEF DEGIL - 22.776 sembolun cogu parca numarasi (STM32F103C8Tx)
ve bunlarin Turkcesi YOKTUR. Test %100'u SUPHELI sayiyor.

OLCUMUN BULDUGU IKI SEY:
1) Kelime kelime ceviri bozuyordu: 'Through hole' -> 'Through delik'.
   Cozum PHRASES: cok kelimeli kaliplar, uzundan kisaya, kelime degisiminden
   ONCE.
2) U6 / RL2 / MES? / U? ayri onek DEGIL, kutuphane yazim tutarsizligi
   (7 varyant, 71 sembol). normalize_designator() kirpiyor ama YALNIZCA sonuc
   tanimli bir onege dusuyorsa - yoksa yeni bir onek sessizce yutulurdu.
   Kategori kapsamasi %99.5 -> %100.

Arama TAM KELIME esler: alt dizi aramasi 'C' icin 41 onek donduruyordu.

Testler: test_lexicon 20.

## Kicad-9jy - Sentetik MPN ve fiyat alanlari: mpn.py

- oncelik: P2  |  durum: closed  |  tur: feature
- kapanis: 2026-08-31T11:24:15Z

KULLANICI ISTEGI (2026-08-31): 'her bir komponent icin mpn kutuphanesi cikar,
gercekci olmasi gerekmiyor, test icin sematikteki her kapasitore en ucuzdan
pahaliya mpn ve price tag ekle, uygulama uzerinden de yapabilelim'.

YAPILDI: pcbqa/mpn.py, komut 'pcbqa mpn'
  --katalog C --deger 10uF   aday parcalari listele
  --ata C --uygula           turdeki bilesenlere MPN + fiyat yaz
Alanlar: MPN, Price, Manufacturer, MPN_Kaynak (gizli yazilir, BOM'da gorunur)

UYDURMA VERI UYDURMA GORUNMELI (bu modulun asil riski):
  * her MPN 'SENT-' ile baslar
  * her sembolde MPN_Kaynak=sentetik-test -> gercek tedarikci baglandiginda
    bu isaretli kayitlar GUVENLE uzerine yazilabilir
  * uretici adlari uydurma (SentCo/TestParts/MockElec/DemoComp); test bunlarin
    gercek firma adlarina benzemedigini koruyor

OLCUM IKI HATA BULDU:
1) 'Gercekci dursun' diye eklenen deterministik fiyat sapmasi (+-%2) ISTENEN
   SIRALAMAYI BOZUYORDU: ust kademelerde adim kuculuyor (40uF -> 45uF %0.4)
   ve C10 (45uF), C9'dan (40uF) ucuz cikti. Sapma KALDIRILDI; fiyat artik saf
   bir (deger, paket) fonksiyonu. DERS: gorsel susleme istenen degismezi
   bozamaz.
2) _base_price degeri okunamayan bilesene 0.10 sabiti veriyordu; Device:C'nin
   varsayilan 'C' degeri de fiyat aliyordu. Artik None doner ve bilesen ENGEL
   olarak raporlanir - sessizce atlanmaz.

SONUC (KicadOtomasyon1): 10 kondansator, 40 alan, C2 $0.5559 -> C11 $0.6359,
siralama istisnasiz. KiCad netlist'i alanlari geri okuyor.
Testler: test_mpn 14.

## Kicad-9ve - Evre 2 son satir: decoupling ADEDI kurali (TI SPRABV2)

- oncelik: P2  |  durum: closed  |  tur: feature
- kapanis: 2026-08-28T03:52:00Z

circuit.decoupling_counts() yazildi ve test edildi (test_circuit.py 218-225) ama HICBIR KURAL onu cagirmiyor - grep ile dogrulandi. Yol haritasinin Evre 2 tablosundaki son doldurulmamis satir bu.

Mevcut hs-decoupling-mesafesi kurali MESAFE olcuyor (TI SBAA113, 6.35 mm): 'kondansator yeterince yakin mi'. ADET sorusunu sormuyor: 'yeterince kondansator VAR MI'. Bir IC'nin tek kondansatoru 2 mm otede olabilir ve mesafe kurali susar; TI SPRABV2 ise 20 guc pini icin 10 adet ister.

Yapilacak: yeni kural tipi decoupling_count. IC'nin guc pinlerini sayar, decoupling_counts() ile gerekeni hesaplar, o guc netine bagli ve IC'ye yakin kondansatorleri sayar, eksigi bildirir.

Kabul: (1) pic_programmer'da yanlis alarm YOK. (2) korpus kalibrasyonu medyani >= 85 kalmali ve yeni kural kartlarin %50'sinden azinda ateslemeli. (3) beyan eksikse davranis bilincli secilmeli ve yazilmali.

## Kicad-f0b - Faz 1d: korpus kalibrasyonu (harness --score-only)

- oncelik: P2  |  durum: closed  |  tur: feature
- kapanis: 2026-08-27T23:23:22Z

Ilke: sahaya cikmis profesyonel bir karta skorumuz dusuk veriyorsa yanlis olan
kart degil SKORDUR. Bu, kendi esiklerimizi kendimize dogrulatmamizi engelleyen
tek mekanizma.

Yapilacak: harness.py'a yerlestirme yapmadan yalnizca skorlayan kip.
discover_boards() ve run_suite() iskeleti zaten var. Rapor: skor dagilimi +
kural bazli atesleme orani. Bir kural gercek kartlarin cogunda atesleniyorsa
o kural ya da esigi yanlistir.

Capa olcumu: KiCad pic_programmer demosu kendi kural dosyasiyla 82.7.
Lisans: korpus buyurken her kartin lisansi kaydedilmeli (HANDOFF 1).

## Kicad-guq - Tum projeyi AllCadOtomation deposuna yayinla

- oncelik: P2  |  durum: closed  |  tur: task
- kapanis: 2026-09-19T21:54:59Z

Kullanici tum projeyi origin main dalina push istedi. Contributors yalniz BugraArd R00kie_RealG olacak. Yayin gecmisinde tek eposta var ve co-author yok; gecmis korunacak. Kaynaklar, belgeler ve canli proje dosyalari dahil; makine ayarlari, yedekler, sanal ortamlar ve gecici kopyalar haric. Graphify metin ve AST aktarimi yapilacak.

## Kicad-j78 - graphify update elle verilen topluluk adlarini siliyor

- oncelik: P2  |  durum: closed  |  tur: bug
- kapanis: 2026-08-31T10:24:33Z

OLCUM (2026-08-31): 'graphify update .' yeniden kumeliyor (174 -> 165 topluluk).
Iki sonucu var:
  * topluluk NUMARALARI kayiyor
  * community_name ELLE VERILEN adlardan en yuksek dereceli dugumun adina
    donuyor: 'Design', 'load_design', 'parse_with_stats', 'run'...

ETKI: post-commit kancasi kurulu oldugu icin bu HER COMMIT'te tekrarlanirdi;
grafik zamanla sessizce okunmaz hale gelirdi.

COZUM: adlar topluluk numarasina degil CAPA DUGUMUNE baglandi.
  .claude/graphify-etiketler.json  - 29 capa (dugum kimligi -> ad)
  .claude/graphify-etiketle.py     - capanin dustugu toplulugu adlandirir
  SessionStart kancasina eklendi (durum kancasindan ONCE calisir)
Capa kimlikleri dosya yolundan turedigi icin yeniden kumelemede sabit.
Capasi olmayan topluluk graphify'in kendi adiyla kaliyor - uydurma ad yok.
Bir capa kaybolursa betik SOYLUYOR (bir kez oldu, capa duzeltildi).

NOT: graphify'in kendi .graphify_labels.json dosyasi bu isi yapmiyor; zaten
temizlik adiminda siliniyor ve numara tabanli oldugu icin yeniden kumelemede
gecersiz.

## Kicad-qz5 - Canli PCB duzenleme DOGRULANDI (KiCad 10.0.4) - uygula-ipc calisiyor

- oncelik: P2  |  durum: closed  |  tur: task
- kapanis: 2026-08-30T15:09:41Z

OLCUM (2026-08-30, acik pcbnew, samples/bench_bad kopyasi):
  GetItems(KOT_PCB_FOOTPRINT) -> 18 oge OKUNDU
  begin_commit + update_items + push_commit -> KABUL; J1 8.000 -> 9.000 mm,
    geri okundu ve degismis gorundu
  python -m pcbqa.ipc_apply --apply -> 16 footprint canli tasindi, 2 kilitli
    (J1, J2) atlandi, 'KiCad undo gecmisine tek islem olarak eklendi'

Yani CANLI DUZENLEME VAR - PCB tarafinda. Sematik tarafinda yok (Kicad-5be).
uygula-ipc zaten yazilmisti ama API kapali oldugu icin hic dogrulanmamisti.

AYRICA ONCEKI BIR TESPITIM DUZELDI: 'bagimsiz editor sunucuya kaydolmuyor'
demistim - YANLIS. Tek basina calisan pcbnew.exe soketi KENDISI bariniyor.
Onceki eeschema denemesinde kicad.exe zaten soketi tutuyordu, yani cakisma
vardi. Kural: ayni anda TEK KiCad ornegi.

kipy notu: Vector2(x=..., y=...) YOK; Vector2.from_xy(...) / from_xy_mm(...).

## Kicad-vdb - Graphify kullanimini proje boyunca kalici kil

- oncelik: P2  |  durum: closed  |  tur: task
- kapanis: 2026-09-07T15:19:09Z

Kullanici 2026-09-07: Serena MCP gerekmiyor; Graphify kurulu olsun ve proje boyunca kullanilsin. Mevcut kurulumu gercek sorguyla dogrula, AGENTS.md ve CLAUDE.md icinde ortak talimati belirt, Beads hafizasini ve Graphify aktarimini guncelle.

## Kicad-z1d - Ayrik (harici FET) tasarimlarda sicak dongu alani

- oncelik: P2  |  durum: closed  |  tur: feature
- kapanis: 2026-08-28T05:01:17Z

TI AN-2155'in OLCTUGU deney: sicak dongu alani 6 mm2 -> 18 mm2 oldugunda SW
spike 2.5 V -> 6.1 V, CISPR-22 Class B marji 8.3 -> 6.7 dB. Projedeki en guclu
sayisal kanit bu ve hala olculemiyor.

Zone okuma (Kicad-akm) eklendi ama YETMEDI: sicak dongu alani tek bir netin
bakir alani degil, CIN -> high-side anahtar -> low-side anahtar -> CIN yolunun
CEVRELEDIGI alan. Yani gereken sey:
  1) hangi bilesenlerin dongu uzerinde oldugunu bulmak (topoloji)
  2) o bilesenlerin pad'lerini sirayla baglayan kapali poligonu kurmak
  3) alanini olcmek

(1) icin alt-devre tanima gerekiyor: bir IC'nin SW/BOOT/VIN pinleri + CIN + L.
Bu, Evre 2'deki 'niyet -> topoloji' isiyle ayni altyapiya dayaniyor.

Ayni altyapi induktor altinda bakir kuralini da acmaz (o zone ∩ courtyard
kesisimi ister) - onu ayri tutun.
