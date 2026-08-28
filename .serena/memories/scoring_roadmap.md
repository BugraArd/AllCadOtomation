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

## Test durumu

418 test geciyor (oturum basinda 214). KiCad demolarina bagli testler kurulum
yoksa atlanir.

## Kalan is

- Ayrik (harici FET) tasarimlarda sicak dongu - korpusta test verisi YOK
- Yonlendirme kapsam disi (dis otomatik yonlendirici + bizim bakir kurallarimiz)
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
