# Skorlama yol haritasi - TAMAMLANDI + sonrasi (2026-08-28)

Tam metin: `pcbqa/docs/yol-haritasi-skorlama.md`, `pcbqa/HANDOFF.md` 21.

## Nihai hedef (kullanicinin koydugu)

Uretken tasarim: sistem kendi bilesenini ekleyip baglayip PCB uretsin. Sonra
binlerce gercek kartla egitim, KiCad uzerinden test, birden fazla model.
Uzmanlasma once STM32, sonra genel CPU devreleri.

Uretim zincirinin MEKANIGI zaten var (sch_add / sch_wire / pcb_sync / auto).
Eksik olan KARAR katmani. Skor uretimin uygunluk fonksiyonudur.

## Evre 1 - BITTI (dort faz)

- 1a agirlik mekanizmasi: Rule.weight / Finding.weight / report.penalty_of()
- 1b orantili ceza: carpan = min(1 + |m-l|/|l|, scale_max), opt-in, tavan 3.0
- 1c 28 on ayar kuralina kanit gucune gore agirlik
- 1d korpus kalibrasyonu: harness --score-only, 19 KiCad demo karti

Kalibrasyon IKI GERCEK KUSUR yakaladi:
  1. Pad katmanlari okunmuyordu -> kart kenari konnektorlerinde 0.000 mm
     aciklik. interf_u skoru 1.6 -> 72.6.
  2. uretim on ayari projenin kendi kararindan sapmisti (courtyard error/16
     yerine warning/6 olmaliydi).
Medyan skor 88.9 -> 95.9.

## Sonrasinda yapilanlar

- Zone okuma + copper_area kurali. Tahmin fazla iyimserdi: uc kuraldan biri
  acildi, biri kismen, ikisi baska veri istiyor.
- Evre 2: circuit.py (parse_value, i2c_pullup, crystal_load, fb_divider) +
  component_value kural tipi.
- SESSIZ HATA BULUNDU: netlist_from_board pinfunction'i bos birakiyordu ve
  docstring "yalnizca sematikten gelir" diyordu. YANLISTI - 19 kartin hepsinde
  pad'lerde var. function: seciciSini kullanan TUM kurallar hicbir zaman
  eslesmiyordu. Duzeltince uc gercek buck converter gorunur oldu.
- subcircuit.py: regulatorleri TOPOLOJIDEN bulma (SW pini + o nette induktor).
  Net adi ise yaramiyor - KiCad FB netini "Net-(U2-FB{slash}VSET)" adlandiriyor.
- buck_layout kurali: ROHM listesi tespit edilen rollere karsi.
  Kesinlik: CM5_MINIMA 19 bulgu -> 1, One-Air-Max 32 -> 4.
  On ayar 9 kuraldan 4'e indi, yerlesim icin uyarlama gerektirmiyor.
- Sicak dongu alani OLCULEBILIYOR (entegre regulatorlerde): dongu
  CIN.VIN -> IC.VIN -> IC.GND -> CIN.GND dortgeni. Anahtarlarin IC ici
  baglantisini bilmeye gerek yok. Olculdu: 0.73-1.13 mm2 (TI'in "iyi" degeri 6).

## Kanitlanan celiski

ROHM 66AN015E kendi icinde tutarsiz: #4-2 "FB direnci FB pinine <= 4 mm" ve
Oncelik 2 "induktor SW pinine <= 4 mm" verilmisken, #4-1'in istedigi
"FB izi induktorden >= 10 mm" ucgen esitsizligiyle SAGLANAMAZ.
One-Air-Max U6'da pin ayrimi 1.20 mm -> ust sinir 9.20 mm < 10.
Bu yuzden fb_inductor_min_mm on ayarda VERILMEDI.

## Evre 2 tamamlandi (2026-08-28)

Yol haritasinin Evre 2 tablosundaki ALTI satirin altisi da kapandi:
i2c_pullup, crystal_load, fb_divider (component_value ile), via_current
(zaten vardi), thermal, decoupling_count. 16 kural tipi.

- `thermal` (Richtek AN044): esik yerine HESAP. Sabit "en az N mm2"
  savunulamaz - ayni 1 W 25 C'de ~148 mm2, 70 C'de ~1885 mm2 ister.
  Modul olculen egri disina cikmayi REDDEDER.
- `decoupling_count` (TI SPRABV2): seramik IC basina (6.35 mm), bulk NET
  basina (mesafe siniri yok - TI vermiyor). `bulk_min_power_pins: 10` altinda
  bulk hic sorulmaz; ceil(n/10) tek pinde bile bulk isterdi ama TI'in birimi
  "~10 guc topu". Korpusta olculdu: esiksiz %47 atesliyordu, esikle %11.
- Ayrik (harici FET) sicak dongu OLCULUYOR: roller topolojiden (ust kol
  VIN+SW, alt kol SW+GND), dongu ALTIGEN. Bootstrap diyodu alt kol sanilmaz.

## Sessiz hata sinifi - DORT ornek

Bu projenin tekrar eden kusuru: yazilmis ama BAGLANMAMIS / sessizce etkisiz
kod. Dordu de gercek bulgu kaybettiriyordu:
1. netlist_from_board pinfunction'i bos birakiyordu (HANDOFF 21.6)
2. learned'in model yolu bayatlamisti - Faz C'den beri etkisiz (21.10)
3. circuit.decoupling_counts() yazilmis, test edilmis, HICBIR KURAL
   cagirmiyordu (21.13)
4. ayrik regulatorde sicak dongu YANLIS olculuyordu ve hata yonu iyimserdi -
   IC'ye bitisik dort pad kucuk alan verir, sorunlu kart temiz gorunurdu
   (21.14)
Ayrica `thermal_pin` yazim hatasi kurali sessizce etkisiz birakiyordu.

DERS: bir hesap modulu yazildiginda "hangi kural bunu cagiriyor?" diye
grep'le dogrula. Modul basina tarama yapildi; baska bosluk yok
(current_capacity_a trace_width_mm'in kullanilmayan tersi,
i2c_needs_current_source bos aralik yolu tarafindan kapsaniyor).

## Test durumu

473 test geciyor (oturum basinda 214). KiCad demolarina bagli testler kurulum
yoksa atlanir. `uretim` kalibrasyonu: medyan 95.9, ceyrekler 80.7/95.9/100.0.

## Kalan is

- Kicad-xpi (P3, BLOKE): ayrik sicak dongu tanimasini GERCEK bir ayrik kartta
  dogrula. Uygulama bitti, geometri analitik sinandi (12 mm2); dogrulanmayan
  sey taniyicinin gercek kartta calistigi. Korpusta ayrik regulator yok -
  alti regulatorun altisi entegre, sistemde baska .kicad_pcb yok (arandi).
- Yonlendirme kapsam disi (dis otomatik yonlendirici + bizim bakir kurallar).
- EVRE 3 (asil hedef, yol haritasinda FAZ OLARAK YAZILMAMIS): uretken tasarim.
  Skor artik uygunluk fonksiyonu olacak olgunlukta; eksik olan niyet -> topoloji
  karari.
- Kalan kural fikirleri on ayarlarin "BU MOTORLA OLCULEMEYENLER" bloklarinda
  listeli; cogu okunmayan veri istiyor (maske katmani, katman yigini, 3B
  yukseklik, Edge.Cuts ic hatlari). Veri gerektirmeyen ikisi: annular ring ve
  delik-delik mesafesi (uretim on ayari) - altyapi hazir, kural yok.
(learned vs auto olcumu YAPILDI - asagi bak.)

## ML: olculdu, sonuc degismedi, ama yolda sessiz bir hata bulundu

`learned` hala `auto`yu gecmiyor: bench_bad 16.5=16.5, pic_programmer 3.0=3.0,
jetson (1125 bilesen) 64.3=64.3, vme-wren (1508 bilesen) 86.7=86.7.

CURUYEN IKI HIPOTEZ:
1. "Skor zenginlesince auto zorlanir, siralamanin degeri artar" - hayir.
   Zenginlesen skor auto'yu zorlamadi TAKTI ve nedeni gradyan degil MALIYET idi
   (clearance_voltage 8.9 -> 467 ms, butce ~900 denemeden ~17'ye dustu).
2. "learned'in degeri degerlendirmenin pahali oldugu buyuk kartlarda gorunur" -
   hayir. vme-wren'de tek olcum 2983 ms; 45 s butcede ~15 deneme kaliyor ve o
   kadar denemede ne auto ne learned bir sey yapabiliyor.

SESSIZ HATA (commit 673fb3c): learned'in DEFAULT_MODEL_PATH'i "move-v2.json"
diyordu, diskteki tek model move-v3.json. Model bulunamayinca sinif sessizce
auto gibi davraniyor -> learned FAZ C'DEN BERI ETKISIZDI. Yol artik oznitelik
SURUMUNDEN turetiliyor (move-v{FEATURE_VERSION}.json) ve
test_learned_actually_invokes_the_ranker ranker'in gercekten cagrildigini
dogruluyor.

DERS: beklenen sonucu dogrulayan bir olcum, olcumun kendisinin bozuk oldugunu
GIZLEYEBILIR. Ayni +0.0'i uc kez gorup "siralamanin degeri yok" diye
yorumladim; dorduncude "birebir AYNI olmasi supheli" deyip modele baktim.
"Sonuc beklendigi gibi cikti" bir dogrulama degil, bir uyaridir.

## Iki performans/anlam duzeltmesi (commit 75e95c4)

1. apply_placement yalnizca bilesenleri tasiyordu; iz/via/dokum yerinde
   kaliyordu, yani bakir kurallari TASINMIS pad'lerle SABIT izleri
   karsilastiriyordu - fiziksel olarak anlamsiz. Artik bir bilesen gercekten
   oynadiysa bakir temizleniyor.
2. clearance_voltage'a sinir kutusu on filtresi: 467 -> 74.8 ms (6.2x), skor
   degismedi. Profil kalan maliyetin filtrenin KENDISI oldugunu gosterdi
   (81 bin kutu karsilastirmasi, 2.3 bin gercek sekil hesabi).
