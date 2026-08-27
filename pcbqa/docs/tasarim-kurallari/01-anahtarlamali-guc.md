# 1. Anahtarlamalı güç dönüştürücüleri (buck / boost / buck-boost)

> **En önemli ön uyarı:** Bu alanda birinci sınıf kaynakların çoğu (TI, ADI,
> Richtek) **mm cinsinden sayı vermez** — "mümkün olduğunca yakın" der.
> Sistematik sayısal kriter veren tek kaynak **ROHM 66AN015E kontrol listesi**.
> Aşağıdaki "tipik" sütunu çoğu zaman ROHM'a, "ölçülmüş" veriler TI AN-2155'e
> dayanıyor. Kural motoruna eşik koyarken bunu bilerek koyuyoruz.

## 1.1 Giriş kondansatörü (CIN) — VIN pinine mesafe

| Büyüklük | Tipik | Sıkı | Gevşek | Kaynak |
|---|---|---|---|---|
| CIN'in VIN+PGND yolu toplam uzunluğu (senkron buck) | < 6 mm (VIN + GND toplamı) | ~3 mm/bacak | asenkron buck ≤10 mm | ROHM 66AN015E Öncelik 1 |
| Bypass kondansatörü — IC pinine | < 5 mm (0.2 inç) | en küçük | 5 mm üstü önerilmez | TI SLVA959B §5 |
| İz parazitik endüktansı | **1 nH/mm** (35 µm bakır) | - | - | ROHM 66AN015E Not 1 |
| Via parazitik endüktansı | 1 nH/via (ROHM) / 0.1-0.5 nH/via (Richtek) | - | - | ROHM; Richtek AN045 |
| Kaç adet CIN | Farklı boyutlarda birden fazla; **en küçük paket en yakına** | 0402 en yakın | - | Richtek AN045 §7.2 |

**Çelişki:** ROHM < 6 mm (toplam yol) · TI SLVA959B < 5 mm · popüler bloglar
"2 mm içinde" · TI SLVA773, ADI AN136/AN139, Richtek AN045 **hiç sayı vermiyor**.
ROHM 60AN066E ayrıca "yolu **1 mm bile** kısaltmak şiddetle tavsiye edilir"
diyor — yani mutlak eşikten çok **monotonluk** vurgusu var. Kural motoru için
doğru okuma: eşik uyarı üretsin, ama asıl değer "daha kısa hep daha iyi".

**Topoloji farkı (sık atlanır, kritik):** Boost'ta CIN'in VIN düğümü **kesikli
akım taşımaz**. TI SLVA773 açıkça: *"VIN bakır alanının büyük olması sorun
yaratmaz ve termal performansı iyileştirir; VIN pini input kondansatörüne via
ve başka katmandan uzun izle bile bağlanabilir."* Buck'taki "CIN çok yakın"
kuralı **boost'un girişine uygulanmaz** — boost'ta kritik olan **çıkış**
kondansatörüdür. Alt-devre farkındalıklı kural yazarken topolojiyi ayırmak şart.

## 1.2 Sıcak döngü (hot loop) alanı

**TI AN-2155'in ölçülmüş deneyi** (LM3102, 1 MHz, 12 V -> 3.3 V / 2.5 A,
CISPR 22 Class B, 3 m):

| Yerleşim | Döngü | Alan | SW spike | Vout p-p | Class B marj |
|---|---|---|---|---|---|
| 1 | 2 x 3 mm | **6 mm²** | 2.5 V | 47 mV | **8.3 dB** |
| 2 | 2 x 6 mm | **12 mm²** | 4.2 V | 64 mV | 7.8 dB |
| 3 | 6 x 3 mm | **18 mm²** | 6.1 V | 75 mV | **6.7 dB** |

6 -> 18 mm² (3x alan): SW spike **2.4x arttı**, EMI marjı **1.6 dB** kayboldu.

**Döngü endüktansı ve dielektrik kalınlığı** (ADI AN139 Tablo 1, 10x10 cm test
döngüsü, 27 MHz):

| Yapı | Endüktans |
|---|---|
| Tek katman (GND düzlemi yok) | 187 nH |
| 2 kat, 1.5 mm dielektrik | 42-53 nH |
| 0.5 mm | 23 nH |
| 0.27 mm | 21 nH |
| **0.12 mm** | **13 nH** (14.4x iyileşme) |

Endüktans -> verim: 0.4 nH -> 2.9 nH artışı verimi **%4'ten fazla** düşürüyor;
1.6 nH -> 0.4 nH aşımı **%75** azaltıyor (ADI, 4-anahtarlı buck-boost).

**Çelişki:** Bloglar "hedef < 10 mm²" veya "< 1 cm² yeterli" diyor. TI'ın ölçümü
12 mm²'de bile bozulma gösteriyor -> **< 10 mm² makul hedef, 100 mm² kesinlikle
gevşek.** ROHM'un 100 mm² kriteri **sıcak döngü için değil, SW bakır alanı
için** — bloglarda bu ikisi sürekli karıştırılıyor.

**Döngü sayısı:** buck 1 · boost 1 · **4-anahtarlı buck-boost 2** (giriş + çıkış).

## 1.3 Anahtarlama düğümü (SW) bakır alanı

| Büyüklük | Değer | Kaynak |
|---|---|---|
| SW bakır alanı (buck, IC + L lehim adaları dahil) | **<= 100 mm²** | ROHM 66AN015E Öncelik 2 |
| IC -> L (veya IC -> Di) SW izi uzunluğu | **her biri <= 4 mm** | ROHM 66AN015E Öncelik 2 |
| L altında bakır | **yok**, en az **3 mm** temizlik (kapalı manyetik devreli L muaf) | ROHM 66AN015E Not 2 |
| SW altında GND düzlemi | **olmalı, kesilmemeli** — kesmek EMI marjını **6 dB** kötüleştirdi | TI SNVA638A §4 |

**EMI/termal çelişkisi:** SW bakırı dv/dt gürültüsü için küçük, MOSFET soğutması
için büyük olmalı — ADI AN136 bunu açıkça "tasarım ödünleşimi" diye adlandırır.
Pratik formülasyon: SW bakırını **termal hesabın gerektirdiği kadar** yap, bir
mm² fazla değil.

ROHM'un 100 mm²'si elde edilen **tek sayısal üst sınır**; TI/ADI/Richtek yalnızca
niteliksel konuşuyor.

## 1.4 Geri besleme (FB) düğümü

| Büyüklük | Değer | Kaynak |
|---|---|---|
| FB bölücü (R1, R2) -> FB pini | **her biri <= 4 mm** | ROHM 66AN015E #4-2 |
| FB izi -> indüktör (L) | **>= 10 mm** | ROHM 66AN015E #4-1 |
| FB izi -> serbest geçiş diyodu (Di) | **>= 10 mm** | ROHM 66AN015E #4-1 |
| FB izi -> SW düğümü (mm) | **BULUNAMADI** — araya GND izi/katmanı koy, 3W kuralı uygula | ADI AN136 (niteliksel) |
| FB / küçük sinyal izi genişliği | **10-15 mil (0.25-0.38 mm)** | ADI AN136 |
| FB bölücü akımı | FB bias akımının **>= 100 katı** | Richtek AN033 |
| R1-R2 rotası | yan yana ve paralel çiz | ROHM 60AN066E §7c |

**FB asla SW ile yakın paralel gitmez**; L ve Di'nin altından geçirilmez
(TI SLVA773 Adım 4). FB bileşenlerinin GND'si IC GND noktasına yakın olmalı.

**Eksik:** "FB izi SW'den en az X mm uzak" diyen üretici sayısı yok. Bazı
bloglarda "3 mm" ve "FB > 20 mm ise diferansiyel rota" geçiyor ama bunlar
**app-note değil** — birincil kaynak gibi kullanılmamalı.

## 1.5 Bootstrap ve VCC/BIAS kondansatörleri

| Büyüklük | Değer | Kaynak |
|---|---|---|
| CBOOT -> BOOT/SW pini (mm) | **BULUNAMADI** — "döngü alanı minimum" | TI SLVAFJ3 §2.4 |
| CBOOT önceliği | **Giriş decoupling'i CBOOT izinden daha öncelikli** | Diodes AN1191 |
| CBOOT nereye yakın | **IC'ye** (FET'ler ~1 inç içindeyse fark yok) | TI |
| VCC / INTVCC döngüsü | minimize edilmeli; INTVCC dekuplaj akımının RF enerjisi ana sıcak döngüden **>20 dB yüksek** ölçüldü | **ADI AN139** |
| VCC/PGND/gate-drive izi genişliği | **>= 20 mil (0.51 mm)** | ADI AN136 |
| Rboot etkisi (referans) | 33 Ω: SW aşımı 5 V -> 3 V, ringing 238 MHz | Richtek AN045 §5 |

**ADI AN139'un az bilinen bulgusu:** INTVCC dekuplaj kondansatöründeki RF
enerjisi ana sıcak döngüdekinden **20 dB yüksek**. Yani VCC kondansatörü,
CIN'den sonra **ikinci öncelik** olmalı — üçüncü değil.

## 1.6 Çıkış kondansatörü ve indüktör

| Büyüklük | Değer | Kaynak |
|---|---|---|
| **Buck:** COUT -> L ve Di pini | **her biri <= 4 mm** | ROHM 66AN015E Öncelik 3 |
| **Buck:** CIN GND ile COUT GND **ayrımı** | **>= 10 mm** (yoksa giriş gürültüsü GND üzerinden çıkışa taşınır) | ROHM 66AN015E Öncelik 3 |
| **Buck:** COUT, CIN sıcak döngüsüyle çakışmamalı | çakışma yok | Richtek AN045 §7.3 |
| **Boost:** COUT | **en kritik bileşen**, IC'ye en yakın o | TI SLVA773 Adım 1 |
| Snubber (Rs, Cs) döngüsü | en küçük, SW ve power GND'ye en yakın | TI SLVA773 Adım 2 |
| İndüktör altında bakır | **olmamalı** (eddy akımı -> L düşer, Q düşer), >= 3 mm | ROHM 60AN066E §5 |
| Perdesiz indüktör | kullanma; perdeli EMI'yi ölçülebilir iyileştirir | Richtek AN045 §7.11 |
| Thermal relief | kritik döngülerde ve güç pad'lerinde **kullanma** | Richtek AN045 §7.6; ADI AN136 |

**Dikkat:** ROHM'un "CIN GND ile COUT GND arası >= 10 mm" kuralı, "her şeyi
birbirine yaklaştır" sezgisinin **tersi** yönde bir kısıt. Yerleştirici yalnızca
mesafe küçültmeye çalışırsa bu kuralı ihlal eder.

## 1.7 Güç izleri: akıma göre genişlik

IPC tabloları için bkz. [02-uretilebilirlik-ipc.md](02-uretilebilirlik-ipc.md).
Burada **üretici pratik kuralları** var:

| Kural | Değer | Kaynak |
|---|---|---|
| 1 oz (35 µm) pratik kural | **>= 1 mm / A** | ROHM 60AN066E §5 |
| 2 oz (70 µm) pratik kural | **>= 0.7 mm / A** | ROHM 60AN066E §5 |
| ROHM'un kendi ölçüm eğrisi | 2 A, 35 µm, ΔT=20 °C -> **0.53 mm** yeterli | ROHM 60AN066E Şekil 5 |
| Küçük sinyal izleri | 0.25-0.38 mm | ADI AN136 |
| Gate drive / VCC / PGND | >= 0.51 mm | ADI AN136 |

**Çelişki (önemli):** ROHM'un "1 mm/A" kuralı kendi ölçüm eğrisinden (2 A için
0.53 mm) yaklaşık **4x muhafazakâr**; ROHM bunu "ortam sıcaklığı ve komşu
bileşen ısısı için marj" diye gerekçelendiriyor. 3 A karşılaştırması:

| Yöntem | 3 A için genişlik |
|---|---|
| ROHM pratik kuralı | 3.00 mm |
| IPC-2152 evrensel eğri, ΔT=10 °C | 2.10 mm |
| IPC-2221 dış, ΔT=10 °C | 1.37 mm |
| IPC-2221 dış, ΔT=20 °C | 0.90 mm |

Aralık **3.3x**. Kural motorunda tek bir "doğru" sayı yok — bu yüzden yöntem
seçilebilir olmalı.

### IPC-2152 hakkında düzeltme (iki ajan çelişti)

Yaygın iddia "IPC-2152 daha gevşek, daha dar iz verir" **eksik bir doğru**:

- IPC-2152'nin **evrensel temel eğrisi** (Figure 5-1/5-2) aslında IPC-2221 dış
  katmanından **DAHA MUHAFAZAKÂR**: 3 A / 1 oz / 10 °C -> IPC-2221 dış 1.37 mm,
  IPC-2152 evrensel **2.10 mm**. Jouppi'nin ifadesiyle: *"Bu grafikten çıkan
  sonuçlar güvenilir ama çok muhafazakârdır."*
- IPC-2152 "gevşek" hale **çarpanlar uygulandıktan sonra** geliyor: bakır
  ağırlığı, kart kalınlığı, malzeme, **düzlem yakınlığı**, ortam. En büyük etken
  düzlem: 0.005 inç mesafede 2 oz / 5x5 inç düzlem varsa hesaplanan 30 °C artış
  gerçekte **~9 °C** oluyor (çarpan ~0.3).
- IPC-2221'in **iç katman** grafiği aslında **serbest havadaki** bir iletkeni
  temsil ediyor (1950'ler NBS verisi, orijinali "Tentative" etiketli) — gerçek
  kartlarla uyuşmamasının nedeni bu. IPC-2152 iç izlerin dışa **yakın** akım
  taşıdığını gösteriyor.
- IPC-2152'nin **paralel iletken** kuralı sıkı: 1 inç (25.4 mm) içindeki izler
  paralel sayılır; 0.10 inç aralıklı iki iz hedeflenen 10 °C yerine **~17 °C**,
  birkaç mil aralıkta **18 °C** ısınır.

**Sonuç:** "IPC-2152 = %12-20 daha dar" ifadesi yalnızca çarpanlar uygulanmış
tipik kart için doğru; çıplak temel eğri için yanlış. Kural motorunda
IPC-2221'de kalmamızın gerekçesi bu belirsizlikle de güçleniyor.

## 1.8 Via akım kapasitesi

**TI SLVA959B Tablo 3-1** (IPC-2152 tabanlı, 10 °C artış, 1 oz):

| Via çapı | mm | Akım |
|---|---|---|
| 6 mil | 0.15 | 0.20 A |
| 8 mil | 0.20 | 0.55 A |
| 10 mil | 0.25 | 0.81 A |
| 12 mil | 0.30 | **0.84 A** |
| 16 mil | 0.41 | 1.10 A |
| 24 mil | 0.60 | BULUNAMADI (TI tablosu 16 mil'de bitiyor) |

IPC-2221 namlu kesiti yöntemiyle hesap (`A = π(d−t)t`, k=0.048):

| Delik | Kaplama | ΔT=10 °C | ΔT=20 °C |
|---|---|---|---|
| 0.30 mm | 20 µm | 1.45 A | 1.97 A |
| 0.40 mm | 20 µm | 1.81 A | 2.46 A |
| 0.60 mm | 20 µm | 2.46 A | 3.34 A |
| 0.60 mm | 25 µm | 2.88 A | 3.90 A |

**Büyük çelişki:** 0.30 mm delik için TI **0.84 A**, IPC-2221 namlu formülü
**1.45-1.69 A** — yaklaşık **2x fark**. Güç yolunda TI'ın muhafazakâr
değerlerini kullan; IPC-2221 hesabına **%50 güvenlik marjı** uygula.

| Kural | Değer | Kaynak |
|---|---|---|
| Güç yolunda via sayısı | **amper başına 1 via** | TI SLVA773 |
| Bulk kondansatör | en az 2 via (güç + toprak) | TI SLVA959B |
| Via bağlantı şekli | **solid via**, thermal relief yok | TI SLVA959B |
| Sıcak döngüde via | **kullanma** — bypass kondansatörü ile aktif cihaz aynı katmanda | TI SLVA959B; ROHM |
| Sinyal via'ları | sıcak döngü altındaki GND düzlemini delme | Richtek AN045 §7.7 |

## 1.9 Anahtarlama frekansının etkisi

**Diferansiyel mod ışıma** (TI SNVA638A denklem 2):

```
E = 263e-16 · (f² · A · I) / r    [V/m],  r = 3 m
```

`f` **kareyle** giriyor -> **f iki katına çıkarsa aynı döngü alanı 4x daha fazla
ışır**; aynı EMI marjı için alan **1/4'e** inmeli. Işıyan bant genişliği
`BW = 0.35 / t_rise` (10 ns -> 35 MHz; 1-2 ns hızlı FET -> 175-350 MHz).

Bu denklemden **türetilmiş** pratik özet (doğrudan alıntı değil):

| f_sw | Sıcak döngü hedefi | Katman | L1->L2 dielektrik |
|---|---|---|---|
| < 500 kHz | <= 20 mm² | 2 kat kabul edilebilir | - |
| 500 kHz - 1 MHz | <= 10 mm² (TI: 6 iyi, 18 kötü) | 4 kat tercih | <= 0.25 mm |
| 1 - 2.2 MHz | <= 3-5 mm² | 4 kat zorunlu, GND L2'de | 0.10-0.13 mm |
| > 2.2 MHz (CISPR 25) | <= 1-2 mm², döngü L < 1 nH | 4+ kat, flip-chip | <= 0.10 mm |

Diğer ölçülmüş değerler: 4 kat ile 2 kat farkı **>26 MHz** üzerinde belirginleşir
(Diodes AN1191) · giriş filtresi ışınan EMI'yi **20 dB'ye kadar** azaltır ·
GND düzlemi eklemek CISPR-22 marjını **+4 dBµV/m** iyileştirir, o düzlemi yüksek
akım yolu altında kesmek **−6 dBµV/m** kaybettirir (TI SNVA638A §4).

## 1.10 Termal ped ve via dizisi

| Büyüklük | Değer | Kaynak |
|---|---|---|
| Termal via çapı | **0.33 mm (13 mil)**, 1 oz kaplama | TI SLMA002J §2.4 |
| Termal via çapı (alt.) | 0.30 mm iç çap — büyük çapta reflow'da **lehim emilmesi** | ROHM 60AN066E §4 |
| Termal via **aralığı** | **~1.2 mm** | ROHM 60AN066E Şekil 4 |
| Termal via pad/delik (TI) | 0.51 mm pad / 0.20 mm delik | TI SLVA959B §2.5 |
| Termal via **sayısı** | küçük die için **5-9 via** yeter; sonrası azalan getiri | TI SLMA002J Şekil 8/9 |
| Via bakır kesit oranı | toplam namlu kesiti ≈ termal land alanının **%1'i** | TI SLMA002J |
| Termal via bağlantısı | **doğrudan**, thermal relief yok | TI SLVA959B §2.4 |
| Termal direnç örneği | SOP-8 altına bakır: θJA **75 -> 64 °C/W** | Richtek AN033 |
| AGND-PGND birleşme noktası | **termal ped** olmalı | TI SLVAFJ3 §3 |

## 1.11 Katman yığını

| Büyüklük | Değer | Kaynak |
|---|---|---|
| Minimum katman (EMI için) | **4** | Diodes AN1191; TI SLYP680 |
| GND düzleminin konumu | **L2**, yüksek akım taşıyan üst katmanın hemen altında | Richtek AN045 §7.10 |
| L1->L2 dielektrik | tipik 0.25 mm; 0.12 mm -> döngü L = 13 nH | ADI AN139 |
| 4 kat vs 2 kat (1.5 mm) | **>3x** daha az endüktans | ADI AN139 |
| 4 kat vs tek katman | **>14x** daha az endüktans | ADI AN139 |
| İz-düzlem endüktansı | `L = 2·l·(h/w)` nH/cm; h=2.5 mm/w=25 mm -> 0.2 nH/cm | TI SLYP680 |

## Kaynaklar

| # | Başlık | URL | Destek |
|---|---|---|---|
| 1 | TI SNVA638A (AN-2155) Layout Tips for EMI Reduction in DC/DC | https://www.ti.com/lit/an/snva638a/snva638a.pdf | 1.2 ölçülmüş deney, 1.3, 1.9, 1.11 — **en değerli kaynak, gerçek ölçüm** |
| 2 | TI SLVA773 Five Steps to a Good PCB Layout of a Boost Converter | https://www.ti.com/lit/an/slva773/slva773.pdf | 1.1 boost farkı, 1.4, 1.6, 1.8 |
| 3 | TI SLVAFJ3 Layout Optimization of 4-Switch Buck-Boost | https://www.ti.com/lit/an/slvafj3/slvafj3.pdf | 1.2, 1.3, 1.5, 1.10 |
| 4 | TI SSZTAE3 Optimizing Hot Loops in the Power Stage | https://www.ti.com/lit/pdf/ssztae3 | 1.2, 1.3 |
| 5 | TI SLVA959B Best Practices for Board Layout of Motor Drivers | https://www.ti.com/lit/pdf/slva959 | 1.8 Tablo 3-1, 1.1, 1.10 |
| 6 | TI SLMA002J PowerPAD Thermally Enhanced Package | https://www.ti.com/lit/an/slma002j/slma002j.pdf | 1.10 |
| 7 | TI SLYP680 Influence of Layout on EMI of Buck-Boost | https://www.ti.com/lit/ml/slyp680/slyp680.pdf | 1.2, 1.11 |
| 8 | ADI/LT AN-139 Power Supply Layout and EMI | https://www.analog.com/en/resources/app-notes/an-139.html | 1.2 Tablo 1, 1.5 INTVCC, 1.11 |
| 9 | ADI/LT AN-136 PCB Layout for Non-Isolated SMPS | https://www.analog.com/en/resources/app-notes/an-136.html | 1.3, 1.4, 1.7 iz genişlikleri |
| 10 | ROHM 66AN015E PCB Layout Essential Check sheet | https://fscdn.rohm.com/en/products/databook/applinote/ic/power/switching_regulator/swregpcb_layout_essentialchecksheet_an-e.pdf | 1.1, 1.3, 1.4, 1.6 — **sayısal kriter veren tek sistematik kaynak** |
| 11 | ROHM 60AN066E PCB Layout Techniques of Buck Converter | https://fscdn.rohm.com/en/products/databook/applinote/ic/power/switching_regulator/converter_pcb_layout_appli-e.pdf | 1.7 mm/A kuralı, 1.10 |
| 12 | Richtek AN045 Reducing EMI in Buck Converters | https://www.richtek.com/m/~/media/AN%20PDF/AN045_EN.pdf | 1.1, 1.5, 1.6, 1.8, 1.11 |
| 13 | Richtek AN033 Buck Converter Selection Criteria | https://www.richtek.com/Design%20Support/Technical%20Document/AN033 | 1.3, 1.4, 1.10 |
| 14 | Diodes AN1191 DC-DC PCB Layout Design for EMC | https://www.diodes.com/assets/App-Note-Files/AN1191-DC-DC-PCB-Layout-Design-for-EMC.pdf | 1.4, 1.5, 1.9, 1.11 |
| 15 | Jouppi, The Value of IPC-2152 | https://www.electronics.org/system/files/technical_resource/E7&S22_03.pdf | 1.7 IPC-2152 düzeltmesi |
| 16 | smps.us IPC-2152 hesaplayıcı | https://www.smps.us/pcb-calculator.html | 1.7 IPC-2152 eğri uydurması |
| 17 | Sierra Circuits IPC-2152 / via akım kapasitesi | https://www.protoexpress.com/blog/how-to-design-via-with-current-carrying-capacity/ | 1.7, 1.8 |

## Bulunamayanlar

| Madde | Eksik |
|---|---|
| 1.3 | ROHM'un 100 mm²'si dışında SW alanı için ikinci bir sayısal üst sınır |
| 1.4 | FB izinin **SW düğümüne** minimum mm ayrımı (hiçbir app-note'ta yok) |
| 1.5 | CBOOT ve VCC kondansatörü için **mm cinsinden** mesafe |
| 1.8 | 0.6 mm via için üretici ölçümü (TI tablosu 0.41 mm'de bitiyor) |
| 1.9 | ">1 MHz için hot loop şu kadar" diyen doğrudan üretici cümlesi (f²'den türetildi) |
| - | Microchip'in SMPS yerleşimine özel sayısal app-note'u; MPS layout guide (site erişilemedi) |
