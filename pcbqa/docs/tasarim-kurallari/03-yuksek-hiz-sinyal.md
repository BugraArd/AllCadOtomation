# 3. Yüksek hızlı ve hassas sinyal arayüzleri

## 3.0 Birim dönüşümü: ps <-> mm <-> mil

Tüm uzunluk-eşleştirme tablolarının temeli bu.

| Ortam | Yayılım hızı | Gecikme | Kaynak |
|---|---|---|---|
| FR4 iç katman (stripline) | ~154 mm/ns | **6.5 ps/mm** = 165 ps/inç | Micron TN-41-13 |
| FR4 dış katman (mikroşerit) | iç katmandan %10 hızlı, ~170 mm/ns | **~5.9 ps/mm** = 150 ps/inç | Micron TN-41-13 |
| FR4 genel (εr≈4) | 6 inç/ns = 152 mm/ns | 6.56 ps/mm | Bogatin |

**Pratik varsayılan: 6.5 ps/mm.** Micron'un kendi örneği: *"To match all traces
within 10 ps, traces must be held within a range of 1.5 mm, 60 mils."*

| mil | mm | ps |
|---|---|---|
| 1 | 0.025 | 0.17 |
| 5 | 0.127 | 0.83 |
| 10 | 0.254 | 1.65 |
| 50 | 1.27 | 8.3 |
| 100 | 2.54 | 16.5 |
| 550 | 13.97 | 90.8 |

## 3.1 Decoupling / bypass kondansatörü

| Kural | Sıkı | Tipik | Üst sınır | Kaynak |
|---|---|---|---|---|
| 100 nF HF kondansatör -> güç pini | doğrudan bağlı | < 2-3 mm | **< 6.35 mm (0.25")** | TI SBAA113 §2.3 |
| Orta frekans (0603/0805) -> FPGA | en yakın | pin altı/bitişik | 2 "elektriksel inç" (~50 mm) | Xilinx UG483 s.24 |
| Bulk (10-15 µF) | - | mümkün olduğunca yakın | **konum kritik değil** | Xilinx UG483; TI SPRABV2 |
| Pad -> via bağlantı izi | via-in-pad | via pad'e dayalı | **< 0.254 mm** | Microchip DS00002054A |
| Kondansatör GND bağlantısı | 2 via | 2 via | 1 via | Microchip DS00002054A |
| Güç/GND düzlem çifti ayrımı | - | **< 0.254 mm** | - | TI SPRABV2 §6 |
| Bakır dolgu <-> komşu iz | - | **0.38-0.51 mm** min | - | TI SPRABV2 §4 |

**BGA yoğunluk kuralı (TI SPRABV2):** 0.1 µF (0402/0201) **her 2 güç topu için
1 adet** · bulk >=15 µF **her ~10 güç topu için 1 adet** · via paylaşımı **max 2
top/via** · kondansatör montaj endüktansı 300 pH - 4 nH, kondansatörün kendi
ESL'ine **eşit veya fazla** katkı yapar (Xilinx UG483 s.29).

### Frekansa göre: λ/40 kuralı (Xilinx UG483)

> *"...leads to placing a capacitor within **one-fortieth of a wavelength** of
> the power pins it is decoupling. The wavelength corresponds to the capacitor's
> mounted resonant frequency, F_RIS."*

Buradan **türetilmiş** (v = 152 mm/ns):

| F_RIS | λ | λ/40 = max mesafe |
|---|---|---|
| 100 MHz | 1524 mm | **38 mm** |
| 200 MHz | 762 mm | **19 mm** |
| 500 MHz | 305 mm | **7.6 mm** |
| 1 GHz | 152 mm | **3.8 mm** |
| 2 GHz | 76 mm | **1.9 mm** |

**Bu, kural motoru için en değerli formülasyon:** decoupling mesafesi sabit bir
sayı değil, kondansatörün montajlı rezonans frekansının fonksiyonu.

### Uyarılar

- **"1-2 mm" değeri birincil kaynakta YOK.** Bloglarda geçiyor ama
  TI/Xilinx/Microchip app-note'larında bulunmuyor. Bulunan tek sayısal sınır
  **TI SBAA113'ün < 6.35 mm** değeri.
- **TI SPRABV2:** *"Short capacitor trace length is the most important measure
  of inductance... Where you place them in relation to the BGA is a **secondary
  concern** to this."* -> İzin kısalığı mesafeden önemli.
- **TI SPRABV2 karışık değere karşı:** farklı değerlerde (0.1 / 0.01 / 1 µF)
  kondansatör karışımı **anti-rezonans** yaratır; tek değer (0.1-0.2 µF, en
  küçük paket) önerilir. Bu, yaygın "log dağılımlı değerler" pratiğiyle
  **çelişir**.
- **Ferrit bead uyarısı:** dijital besleme hatlarında **önerilmez** — planar
  kapasitansı devre dışı bırakır, ~200 MHz üstü anlık akımda gerilim çökmesi.

## 3.2 Kristal / osilatör

**ÖNEMLİ BULGU: kristal -> MCU pini mesafesi için mm cinsinden sayı BULUNAMADI.**
ST AN2867, Microchip AN826, NXP AN10897, Silabs AN0016 — hiçbiri sayı vermiyor,
hepsi "as short as possible" diyor. Yaygın alıntılanan "5 mm / 10 mm"
değerlerinin doğrulanabilir birincil kaynağı yok.

| Kural | Değer | Kaynak |
|---|---|---|
| Kristal -> MCU OSC pini | "as short as possible" — **BULUNAMADI** | ST AN2867 §7 |
| Yük kondansatörleri -> kristal | "close to each other", **eşit uzunlukta** | Microchip; Silabs |
| Kristal <-> diğer sinyaller | **iz genişliğinin 5 katı** (ör. 0.635 mm) | Microchip AN15.17 |
| Diff çift <-> saat/periyodik sinyal | **1.27 mm (50 mil)** min | TI SPRAAR7E §3.1 |
| Saat izleri arası | merkez-merkez >= **3 × iz genişliği** | TI USB 2.0 Layout Guidelines |
| Kristal altındaki bakır | **yerel** GND düzlemi, guard ring'in hemen altındaki katmanda (tüm kartta değil) | ST AN2867 §7 |
| Kristal altında başka iz | **hiçbiri** — "bottom side is solid ground under this circuit" | Microchip AN15.17 |
| Kristal kapağı GND pinleri | topraklanmalı | Silabs AN0016 |
| Yüksek hızlı izler kristal yakınında | **yasak** | TI SPRAAR7E §3.2 |
| Saat serisi sönümleme direnci | **10-130 Ω**, saat kaynağına yakın | TI USB 2.0 Layout Guidelines |
| PCB + pin stray kapasitans | 2-5 pF | Microchip AN826 |
| Kristal shunt kapasitansı C0 | 3-7 pF | Microchip AN826 |

**Türetilebilir sağlam sınır:** TI'ın "diff çift <-> saat >= 1.27 mm" ve
Microchip'in "5 × iz genişliği" kuralları, kristal izlerinden ayrım için
kullanılabilir tek sayısal dayanaklar.

## 3.3 USB 2.0 Hi-Speed (480 Mbps)

### Empedans

| Kural | Min | Tipik | Max | Kaynak |
|---|---|---|---|---|
| Diferansiyel | 81 | **90** | 99 Ω (±%15) | USB 2.0 spec; TI |
| Tek uçlu | 40.5 | **45** | 49.5 Ω | TI SPRAAR7E |

### Uzunluk eşleştirme — BÜYÜK ÇELİŞKİ

| Kaynak | Intra-pair tolerans | mm | ps |
|---|---|---|---|
| TI USB 2.0 Board Design and Layout Guidelines §2.5 | **2 mil** | 0.051 | 0.33 |
| TI SPRAAR7E Tablo 3/4/5 | **50 mil (MAX)** | 1.27 | 8.3 |
| TI SPRABT8A §2.5 | **100 mil** | 2.54 | 16.5 |
| TI SPRABT8A §2.1 (**aynı doküman**) | **150 mil (MAX)** | 3.81 | 24.8 |

Aynı üreticinin dört dokümanı **75 kat** farklı değer veriyor; SPRABT8A kendi
içinde bile tutarsız.

**Pratik yorum:** 480 Mbps'de UI = 2.08 ns. 50 mil = 8.3 ps = UI'nin %0.4'ü.
**50 mil (1.27 mm) savunulabilir hedef**; 2 mil gereksiz sıkı, 150 mil ancak kısa
izlerde geçerli. En sık alıntılanan resmi TI cihaz parametresi: **50 mil MAX**.

### Uzunluk, stub, via

| Kural | Tipik | Üst sınır | Kaynak |
|---|---|---|---|
| Toplam iz uzunluğu | 4000 mil (101.6 mm) | **12000 mil (304.8 mm)** | TI SPRAAR7E |
| İzin verilen stub sayısı | 0 | **0** | TI SPRAAR7E |
| Kaçınılmaz stub uzunluğu | - | **< 5.08 mm** | TI USB 2.0 Guidelines |
| Via stub (backdrill eşiği) | - | **< 0.381 mm** | TI SPRAAR7E §3.6 |
| Hat başına via sayısı | <=2 | **4** | TI SPRAAR7E |
| Test noktası | 0 | **0** | TI SPRAAR7E |

### Ayrım / keep-out

| Kural | Değer (mm) | Kaynak |
|---|---|---|
| Diff çift <-> başka diff çift | **5W**; 1.27 (50 mil) | TI SPRAAR7E §3.1 |
| Diff çift <-> başka diff çift (yeni rev.) | 0.762 (30 mil) | TI SLLA414 (2026) |
| Diff çift <-> herhangi sinyal | **0.762** min | TI SPRAAR7E |
| Diff çift <-> saat/periyodik | **1.27** min | TI SPRAAR7E |
| Referans düzlem kenarından | >= **2.29** | TI SPRAAR7E §3.2 |
| Referans düzlemdeki boşluktan | >= 1.5W | TI SPRAAR7E §3.2 |
| GND dikiş via'sı <-> sinyal via'sı | <= **5.08** merkez-merkez | TI SPRAAR7E §2.5 |
| Via anti-pad çapı | 0.762 (mümkün olduğunca büyük) | TI SPRAAR7E §3.8 |
| Büküm açısı | **> 135°** (90° yasak) | TI SPRAAR7E §3.11 |

### ESD / common-mode choke

Sıra: **konnektör -> ESD -> CMC -> R/C** (TI SPRABT8A §2.5). ESD klemp
konnektöre en yakın; CMC de yakın ama **ESD daha yakın olmalı**. Diff hat
üzerindeki SMD max **0603** (0402 önerilir). DP/DM üzerinde sonlandırma ve
decoupling kondansatörü **gerekmiyor**.

**Çelişki:** SMD pad altı referans düzlem boşaltma — SPRAAR7E (2015) **%60**,
SLLA414A (2026) **%100** diyor. Aynı üretici, ters yönde revizyon.

**USB-IF notu:** USB 2.0 spesifikasyonu yalnızca 90 Ω ±%15'i normatif tanımlar;
**mil/mm layout toleransı yayınlamaz**. Dolaşan "USB-IF layout guideline"
sayıları aslında silikon üreticilerinin app-note'larından geliyor.

## 3.4 Ethernet (100BASE-TX / 1000BASE-T)

| Kural | Değer | Kaynak |
|---|---|---|
| MDI diferansiyel / tek uçlu Z | **100 Ω / 50 Ω** | Microchip DS00002054A |
| **Intra-pair skew** | **< 50 mil (1.27 mm ≈ 8.3 ps)** | Microchip DS00002054A |
| **Inter-pair skew** | **< 600 mil (15.24 mm ≈ 99 ps)** | Microchip DS00002054A |
| PHY <-> magnetics | **< 25.4 mm**, max 76.2 mm | Microchip DS00002054A |
| Magnetics <-> RJ45 | **< 25.4 mm** | Microchip DS00002054A |
| Toplam diff çift uzunluğu | **< 101.6 mm** | Microchip DS00002054A |
| Diğer yüksek hızlı izler <-> Ethernet ön uç | >= **7.62 mm** | Microchip DS00002054A |
| Hat başına via bütçesi | **2** | Microchip DS00002054A |
| **Yüksek gerilim bariyeri** | magnetics ortasından RJ45'e kadar **tüm düzlemler temizlenir**; bu bölgede sadece TRxP/TRxN izleri | Microchip DS00002054A |
| Bariyer izolasyon ayrımı | >= **6.35 mm** | Microchip DS00002054A |
| Magnetics altında toprak düzlemi | **yok** | Microchip DS00002054A |
| Bob Smith sonlandırma | 75 Ω + 1000 pF/3 kV veya 1500 pF/2 kV | Microchip; TI SNLA079D |
| EFT kondansatörü <-> iz/komponent | >= **1.27 mm** | Microchip DS00002054A |
| Şasi GND <-> devre GND | **örtüşme yok**, boşluk; üzerine 2-3 adet 1206 pad | Microchip; TI SNLA079D |
| Magnetics izolasyon gerilimi | 1500 Vrms tipik | Microchip DS00002054A |
| MII/RMII iz uzunluğu | **< 152 mm**, eşleştirme 50.8 mm içinde | TI SNLA079D §5.2 |
| MII empedansı (IEEE) | 68 Ω | TI SNLA079D §5.1 |

**Çelişki:** Bloglar 1000BASE-T intra-pair için 20 mil diyor; Microchip'in resmi
app-note'u **50 mil**. Blog değeri daha muhafazakâr ama kaynağı zayıf.

## 3.5 HDMI / DisplayPort / PCIe / SATA / USB3 / MIPI / LVDS

### TI SLLA414A (Ocak 2026) protokol tablosu

| Protokol | Diff Z | Tek uçlu Z | Max intra-pair skew | AC kondansatör |
|---|---|---|---|---|
| USB 2.0 | 90 ±%15 | 45 ±%15 | (tablo yok) | **yasak** |
| USB 3.2 / USB4 | 90 ±%15 | 45 ±%15 | **15 ps/m** (TI: 5 mil önerir) | TX'te zorunlu |
| HDMI | 100 ±%15 | 50 ±%15 | **0.15 × Tbit** | **yasak** |
| DisplayPort | 100 ±%10 | 50 ±%15 | **20 ps** (TI: ~5 mil) | **zorunlu** |

**HDMI türetilmiş** (Tcharacter = 10 × Tbit):

| HDMI | Veri hızı/lane | Tbit | Intra-pair (0.15×Tbit) | mm |
|---|---|---|---|---|
| 1.4b | 3.4 Gbps | 294 ps | **44 ps** | 6.8 |
| 2.0b | 6 Gbps | 167 ps | **25 ps** | 3.85 |
| 2.1b FRL | 12 Gbps | 83 ps | **12.5 ps** | 1.92 |

### TI SPRAAR7E cihaz-parametre tabloları

| Parametre | MAX |
|---|---|
| USB3.0 toplam iz uzunluğu | 3500 mil (88.9 mm) |
| SATA toplam iz uzunluğu | 3050 mil (77.5 mm) |
| PCIe toplam iz uzunluğu | 4700 mil (119.4 mm) |
| USB2.0 toplam iz uzunluğu | 12000 mil (304.8 mm) |
| **Skew — USB3/SATA/PCIe çift içi** | **5 mil (0.127 mm ≈ 0.83 ps)** |
| **Skew — PCIe RX/TX çiftleri arası (toplam)** | **550 mil (13.97 mm ≈ 91 ps)** |
| **Skew — USB2.0 çift içi** | **50 mil (1.27 mm ≈ 8.3 ps)** |
| PCIe diff Z | 90 / **100** / 110 Ω |
| SATA diff Z | 85 / **100** / 115 Ω |
| PCIe/SATA diff izinde via | **0** |
| USB3 diff izinde via | 2 |
| Stub (herhangi diff çift) | **0** |

**MIPI D-PHY: BULUNAMADI** (MIPI Alliance üye belgesi, halka açık değil).
**LVDS (ANSI/TIA/EIA-644): BULUNAMADI** (standart açılamadı).

## 3.6 DDR3 / DDR4

### TI SPRABI1 — mil cinsinden kesin değerler

| Sinyal grubu | Kural | Değer | mm |
|---|---|---|---|
| **Veri (DQ/DM) — byte-lane içi** | eşleştirme | **±10 mil** | ±0.254 |
| **DQS diferansiyel çifti** | çift içi | **±1 mil** | ±0.025 |
| **Clock (CK/CK#) çifti** | çift içi | **±1 mil** | ±0.025 |
| Clock stub | max | < 40 mil | 1.02 |
| **Address/Command (fly-by)** | clock'a göre | **±20 mil** | ±0.508 |
| Address/Command grup içi | | ±10 mil | ±0.254 |
| Address/Command stub | | < 80 mil | 2.03 |
| **Control (fly-by)** | clock'a göre | ±20 mil | ±0.508 |
| Empedans | tek uçlu / diff | 50 Ω / 100 Ω | - |
| **İz aralığı (crosstalk)** | merkez-merkez, serpentine dahil | **>= 5W** | - |
| İz aralığı (gevşek) | | 4W — **>1066 MT/s için UYGUN DEĞİL** | - |
| VTT sonlandırma izi | son SDRAM'de | <= 500 mil | 12.7 |
| VREF izi | genişlik / ayrım | >= 30 mil / >= 15 mil | 0.762 / 0.381 |

**Ek katı kurallar:** veri netlerinde **orta-nokta via'sı yasak** · bir
byte-lane'in tüm netleri **aynı katmanda** · aynı segmentteki tüm rotalar **aynı
sayıda via** · uzun rotalar stripline · eşleştirme "equivalent stripline length"
üzerinden · **byte lane'ler arası eşleştirme gerekmez**, sadece grup içi.

### Micron TN-41-13 — zaman bütçesi yaklaşımı

| Kural | Değer |
|---|---|
| 800 MHz clock'un %1'i (±%0.5) | 6.25 ps -> **±1 mm** eşleştirme |
| DQ nokta-nokta, bit periyodunun %1'i | 625 ps × %1 = 6.25 ps -> **±0.5 mm** |
| Address ağaç topolojisi dal eşleştirme | **1 mm** içinde |
| Via gecikme bütçesi | max **20 ps** |
| 10 ps içinde eşleştirme | **1.5 mm = 60 mil** aralık |

### Fly-by topolojisi

Zincirleme, çok kısa/sıfır stub: controller -> Chip 0 -> ... -> Chip N -> VTT.
**Address, command, control, clock** fly-by; **veri (DQ/DQS) nokta-nokta**, VTT
yok (ODT kullanılır). DDR3'te CA<->DQ skew'ini **write leveling** telafi eder.
DDR3 JEDEC modüllerinde fly-by **zorunlu**. Sonlandırma zincirin **son
SDRAM'inde**, iz <= 500 mil.

## 3.7 3W kuralı ve 20H kuralı

### 3W / 4W / 5W

| Kural | Tanım | Kaynak |
|---|---|---|
| **3W** | merkez-merkez >= 3 × iz genişliği (kenar-kenar 2W) | TI USB 2.0 Guidelines (**yalnızca saat izleri için**) |
| **4W** | merkez-merkez >= 4 × W | TI SPRABI1 — **>1066 MT/s için uygun değil** |
| **5W** | diff çiftler arası >= 5 × iz genişliği | **TI SPRAAR7E, SLLA414, SPRABI1** |
| 5 × iz genişliği | USB izleri <-> ilgisiz izler | Microchip AN15.17 |
| 1.5W | diff çift <-> referans düzlem boşluğu | TI SPRAAR7E §3.2 |
| Mutlak keep-out (herhangi sinyal) | 0.762 mm | TI SPRAAR7E |
| Mutlak keep-out (saat/periyodik) | 1.27 mm | TI SPRAAR7E |

**Önemli:** TI'ın yüksek hızlı dokümanlarının hepsi **3W değil 5W** kullanıyor;
3W yalnızca saat izleri için geçiyor. "3W" endüstri folkloruna göre daha gevşek
bir kural — yüksek hızlı diferansiyel için **5W esas alınmalı**. "%70 alan
sınırlaması" iddiasının birincil kaynağı **BULUNAMADI**.

### 20H kuralı — ÇÜRÜTÜLDÜ

| Konu | Durum |
|---|---|
| Tanım | Güç düzlemi kenarı, toprak düzlemi kenarından **20 × dielektrik kalınlığı** içeri çekilir |
| Orijinal kaynak | Montrose, *PCB Design Techniques for EMC Compliance*, IEEE Press, 1996, s. 26-28 |
| Sayısal karşılık | 0.2 mm prepreg -> 4 mm; 0.36 mm -> 7.2 mm |
| **Bilimsel bulgu** | **Shim & Hubing (Clemson CVEL / IEEE EMC 2001):** *"radiated emissions directly from boards implementing the 20-H rule are actually **slightly higher** than the emissions from boards with a traditional design."* |
| Geçerli kalan kısım | *"There is no doubt that implementation of a 20-H rule can help to **contain the electric field near the edge of the board**."* |
| Sonuç | *"...it can create more problems than it solves when misapplied."* |

**Pratik öneri:** 20H'yi genel EMI azaltıcı olarak uygulamayın. Yalnızca kart
kenarına yakın kablo/muhafaza kuplajı riski varsa uygulayın.

## 3.8 I2C ve SPI

### I2C — NXP UM10204 (spesifikasyonun kendisi)

| Kural | Standard | Fast | Fm+ | Hs |
|---|---|---|---|---|
| Bit hızı (kbit/s) | 100 | 400 | 1000 | 3400 |
| **Max bus kapasitansı Cb** | **400 pF** | **400 pF** | **400 pF** | 100 pF |
| Max tr | 1000 ns | 300 ns | 120 ns | - |
| Cihaz başına pin kapasitansı | <=10 pF | <=10 pF | <=10 pF | <=10 pF |

**Pull-up boyutlandırma:** `T = 0.8473 × RC` · `Rp(max) = tr / (0.8473 × Cb)` ·
`Rp(min) = (VDD − VOL(max)) / IOL` (IOL = 3 mA). Cb <= 200 pF: basit direnç
yeterli. Cb 200-400 pF: **akım kaynağı veya anahtarlamalı direnç** gerekir.

**Pull-up direncinin KONUMU: UM10204 normatif kural İÇERMİYOR — BULUNAMADI.**
Spesifikasyonun tek kısıtı: bus başına **tek bir pull-up çifti** (paralel
pull-up'lar Rp(min) ihlali yaratır).

**İz uzunluğu (türetilmiş):** 400 pF bütçe; 8 cihaz × 10 pF = 80 pF; PCB izi
~0.5-1.5 pF/cm -> teorik metrelerce. **Kısıt iz uzunluğu değil, cihaz sayısı +
tr bütçesi.** Kaynaklı bir "max cm" değeri **BULUNAMADI**.

### SPI

**SPI için standart yerleşim toleransı YOKTUR** — SPI bir Motorola *de facto*
arayüzü, resmi spesifikasyonu yok. Kullanılabilir tek kaynaklı yaklaşım
**kritik uzunluk kuralı** (Bogatin): `BW = 0.35/RT`, `TD < RT/3`,
**`Len < 2 × RT`** (inç, ns).

| Sürücü yükselme süresi | Kritik uzunluk | mm |
|---|---|---|
| 5 ns | 10 inç | 254 |
| 2 ns | 4 inç | 102 |
| 1 ns | 2 inç | 51 |
| **0.5 ns** (tipik modern CMOS) | 1 inç | **25** |
| 0.25 ns | 0.5 inç | 12.7 |

**Belirleyici olan frekans değil yükselme süresidir.** Uyarı: Altium ve
Interference Technology bu kuralın keyfiliğini eleştiriyor (1/2, 1/3, 1/4, 1/6,
1/10, 1/20 versiyonları dolaşımda); Bogatin'in 1/3 versiyonu en iyi
gerekçelendirilmiş olanı.

## 3.9 ADC / hassas analog girişler

| Kural | Değer | Kaynak |
|---|---|---|
| HF bypass (0.1 µF) -> besleme pini | doğrudan bağlı; **< 6.35 mm** | TI SBAA113 §2.3 |
| Bulk (2.2-6.8 µF) | biraz uzakta olabilir, paylaşılabilir | TI SBAA113 |
| HF bypass GND dönüşü | **star bağlantı** | TI SBAA113 Fig.6 |
| GND pad'ine giden iz genişliği | **> 1.27 mm** | TI SBAA113 §2.4 |
| Op-amp/ADC **altında** GND + güç düzlemi | **açık (boşaltılmış)**, tüm doğrudan bağlı pad'leri kapsayacak şekilde | TI SBAA113 §2.4 |
| Referans (REFP/REFN) bypass | HF seramik <= 1.0 µF, **üst katmanda** | ADI |
| Kritik kondansatör izleri | >= 0.254 mm | ADI |
| **Empedans süreksizliği yasak bölgesi** | ADC'den **100-200 ps** içinde hiçbir süreksizlik = **20-38 mm** FR4'te; mecbursan **seri direnç** | **ADI, A Short Course in PCB Layout for High-Speed ADCs** |
| Analog <-> dijital min ayrım (mm) | **BULUNAMADI** | - |
| — türetilebilir vekil | 0.762 mm genel; 1.27 mm saat/periyodik | TI SPRAAR7E |
| Guard trace genişliği | 0.5-1.0 mm başlangıç | TI E2E (**forum, zayıf kaynak**) |
| Guard trace bağlantısı | her iki uçtan **via ile** ilgili toprağa | NXP AN10897 |
| Kelvin bağlantı sayısal kuralı | **BULUNAMADI** — sadece kavramsal | - |
| Simetri (diferansiyel ADC sürücü) | **sinyal yolu simetrisi** > komponent simetrisi | TI SBAA113 §2.1 |

**Görünürdeki çelişki, aslında bağlam farkı:** TI SBAA113 "op-amp altında GND
düzlemini aç" derken TI SPRAAR7E "yüksek hızlı sinyaller kesintisiz GND
üzerinden geçsin" diyor. SBAA113 **yüksek empedanslı analog pad'lerin parazitik
kapasitif geri beslemesini** hedefliyor (yerel boşaltma); SPRAAR7E **iletim
hattı dönüş akımını**. İkisi de doğru — hangisinin baskın olduğu düğüm
empedansına bağlı.

## 3.10 Reset ve hassas yüksek empedanslı düğümler

| Kural | Değer | Kaynak |
|---|---|---|
| NRST filtre kondansatörü | **100 nF** | ST AN2586 |
| NRST kondansatörü -> pin mesafesi | "short wires" — **mm BULUNAMADI** | ST AN2586 |
| VDD decoupling (STM32) | her VDD pininden GND düzlemine 100 nF X7R, **en kısa yol** | ST AN2586 |
| VREF stabilizasyon (FPGA) | pin başına 1 adet, 0.022-0.47 µF, en yakın | Xilinx UG483 s.36 |
| Ethernet RBIAS/ISET (yüksek Z) | pine çok yakın, iz çok kısa, **5 × iz genişliği** uzakta | Microchip DS00002054A |

**Türetilebilir kural:** Reset/VREF/RBIAS gibi yüksek empedanslı düğümler için
decoupling kuralı aynen geçerli -> **< 6.35 mm**, tercihen doğrudan bitişik.
λ/40 da uygulanabilir. Ancak **hiçbir üretici NRST için mm yayınlamıyor.**

## 3.11 Anten / RF (2.4 GHz — BLE / WiFi / Zigbee)

### Keep-out ve toprak

| Kural | Değer | Kaynak |
|---|---|---|
| Anten keep-out | **tüm katmanlarda** komponent/düzlem/vida/iz yok; alan antene bağlı | Infineon AN91445 §12 |
| Anten **altında** toprak | **kesinlikle yok** | AN91445 §12 |
| Anten konumu | **PCB köşesinde** | AN91445 §12 |
| Metal muhafaza | anten yakın alanında **yasak** | AN91445 §12 |
| Toprak düzlemi + plastik muhafaza | rezonansı **~100-200 MHz aşağı** kaydırır | AN91445 §11 |
| λ/4 @ 2.4 GHz (referans) | ~31 mm | türetilmiş |

### Chip anten (Johanson 2450AT) — kesin mm değerleri

| Kural | Değer |
|---|---|
| Anten kısa kenarlarından toprak boşluğu | **> 2 mm** |
| Toprak düzlemine en yakın kısa uçtan | **> 1 mm** |
| Anten uzun kenarından (kart kenarına monte) | **> 4 mm** |
| Dipol gibi davranması için toprak düzlemi | 3-4 cm × 1-2 cm |

### 50 Ω hat genişliği — DİKKAT: topoloji kritik

**CPWG (alt toprak düzlemli koplanar dalga kılavuzu), FR4 εr=4.3** (AN91445):

| Dielektrik kalınlığı | 50 Ω hat genişliği |
|---|---|
| 1.52 mm (60 mil) | **1.65 mm (65 mil)** |
| 1.27 mm | 1.50 mm |
| 1.02 mm | 1.32 mm |
| 0.76 mm | 1.12 mm |
| 0.51 mm | 0.84 mm |

**ÇELİŞKİ / kavram ayrımı:** Yaygın alıntılanan **"1.6 mm FR4'te 50 Ω ≈ 2.9-3.0
mm"** değeri **düz mikroşerit** içindir (yan toprak dökümü yok). AN91445'in
**1.65 mm** değeri **CPWG** içindir (izin iki yanında toprak dökümü var, gerekli
genişliği ciddi biçimde düşürür). Mikroşerit ~2.9 mm değeri birincil kaynakta
**doğrulanamadı** — hesaplayıcı sonucudur. **İki topolojiyi karıştırmayın.**

### Besleme hattı ve PCB anten boyutları

| Kural | Değer |
|---|---|
| Besleme izi < 3 mm | genişlik kritik değil |
| Besleme izi > ~1 cm | **kontrollü empedans zorunlu** |
| MIFA boyutu (1.6 mm FR4) | 7.2 × 11.1 mm, iz genişliği 0.51 mm |
| IFA boyutu (1.6 mm FR4) | 4 × 20.5 mm, iz 0.61 mm; MIFA'dan **daha verimli** |
| İyi eşleme kriteri | VSWR 1.5 iyi; **VSWR > 2.0 -> eşleme ağı gözden geçir** |

## Özet: en kritik 15 sayı

| # | Kural | Değer | Kaynak |
|---|---|---|---|
| 1 | FR4 stripline yayılım gecikmesi | **6.5 ps/mm** | Micron TN-41-13 |
| 2 | Decoupling max mesafe (kaynaklı) | **< 6.35 mm** | TI SBAA113 |
| 3 | Decoupling — frekans bağımlı | **λ/40 @ F_RIS** | Xilinx UG483 |
| 4 | BGA decoupling yoğunluğu | 0.1 µF / 2 güç topu | TI SPRABV2 |
| 5 | USB 2.0 intra-pair skew | **1.27 mm** MAX | TI SPRAAR7E |
| 6 | USB 2.0 diferansiyel empedans | 90 Ω ±%15 | USB 2.0 spec |
| 7 | USB 2.0 max iz uzunluğu | 305 mm | TI SPRAAR7E |
| 8 | Via stub / backdrill eşiği | 0.381 mm | TI SPRAAR7E |
| 9 | Diff çift <-> saat sinyali | **1.27 mm** min | TI SPRAAR7E |
| 10 | PCIe/SATA/USB3 intra-pair skew | **0.127 mm** | TI SPRAAR7E |
| 11 | Ethernet intra/inter-pair | 1.27 / 15.24 mm | Microchip DS00002054A |
| 12 | Ethernet PHY<->magnetics<->RJ45 | < 25.4 mm her biri | Microchip DS00002054A |
| 13 | DDR3 byte-lane / DQS / clock | ±0.254 / ±0.025 / ±0.025 mm | TI SPRABI1 |
| 14 | I2C max bus kapasitansı | **400 pF** | NXP UM10204 |
| 15 | Diff çift aralığı (crosstalk) | **5W** (3W değil) | TI SPRAAR7E |

## Kaynaklar

| # | Başlık | URL | Destek |
|---|---|---|---|
| 1 | TI SPRAAR7E High-Speed Interface Layout Guidelines | https://cdn.hackaday.io/files/11178478239552/spraar7e_USB.pdf | 3.3, 3.5, 3.7 |
| 2 | TI SLLA414A High-Speed Layout Guidelines for Signal Conditioners and USB Hubs | https://www.ti.com/lit/pdf/slla414 | 3.3, 3.5 |
| 3 | TI SPRABT8A AM335x/AM43xx USB Layout Guidelines | https://www.ti.com/lit/an/sprabt8a/sprabt8a.pdf | 3.3 |
| 4 | TI USB 2.0 Board Design and Layout Guidelines | https://e2echina.ti.com/cfs-file/__key/telligent-evolution-components-attachments/13-106-00-00-00-00-33-10/USB-2.0-Board-Design-and-Layout-Guidelines.pdf | 3.2, 3.3 |
| 5 | TI SPRABV2 BGA PCB design / decoupling | https://www.ti.com/lit/pdf/sprabv2 | 3.1 |
| 6 | TI SBAA113 PCB Layout for Low Distortion High-Speed ADC Drivers | https://www.ti.com/lit/pdf/sbaa113 | 3.1, 3.9 |
| 7 | TI SPRABI1 DDR3 Design Requirements for KeyStone Devices | https://www.ti.com/lit/pdf/sprabi1 | 3.6, 3.7 |
| 8 | TI SNLA079D DP83848 PHYTER Design Guide | https://www.ti.com/lit/an/snla079d/snla079d.pdf | 3.4, 3.10 |
| 9 | TI SWRA161 Antenna Selection Guide | https://www.ti.com/lit/pdf/swra161 | 3.11 |
| 10 | TI SCAA106 Troubleshooting I2C Bus Protocol | https://www.ti.com/lit/pdf/scaa106 | 3.8 |
| 11 | Xilinx/AMD UG483 7 Series FPGAs PCB Design Guide | https://www.amd.com/content/dam/xilinx/support/documents/user_guides/ug483_7Series_PCB.pdf | 3.1 (**λ/40**), 3.10 |
| 12 | NXP UM10204 I2C-bus specification | https://www.nxp.com/docs/en/user-guide/UM10204.pdf | 3.8 |
| 13 | NXP AN10897 A guide to designing for ESD and EMC | https://www.nxp.com/docs/en/application-note/AN10897.pdf | 3.2, 3.9 |
| 14 | ST AN2867 Oscillator design guide | https://www.st.com/resource/en/application_note/an2867-guidelines-for-oscillator-design-on-stm8afals-and-stm32-mcusmpus-stmicroelectronics.pdf | 3.2 (**mm YOK**) |
| 15 | ST AN2586 Getting started with STM32F10xxx hardware development | https://www.st.com/resource/en/application_note/cd00164185-getting-started-with-stm32f10xxx-hardware-development-stmicroelectronics.pdf | 3.1, 3.10 |
| 16 | Microchip AN826 Crystal Oscillator Basics and Crystal Selection | https://ww1.microchip.com/downloads/en/appnotes/00826a.pdf | 3.2 |
| 17 | Microchip DS00002054A Ethernet PCB Layout Guidelines | https://ww1.microchip.com/downloads/en/Appnotes/00002054A.pdf | 3.1, 3.2, 3.4 |
| 18 | Microchip AN15.17 USB2514 Two-Layer PCB Layout Guidelines | https://web.pa.msu.edu/people/edmunds/Disco_Kraken/Components/USB_Components/usb_microchip_an15.17_layout_guide.pdf | 3.2, 3.3 |
| 19 | Silicon Labs AN0016 Oscillator Design Considerations | https://www.silabs.com/documents/public/application-notes/an0016.1-efm32-series-1-oscillator-design-considerations.pdf | 3.2 |
| 20 | Micron TN-41-13 DDR3 Point-to-Point Design Support | https://perso.esiee.fr/~poulichp/CEM/Signal_Integrity/tn4113_ddr3_point_to_point_design.pdf | 3.0, 3.6 |
| 21 | Infineon/Cypress AN91445 Antenna Design and RF Layout Guidelines | https://www.infineon.com/dgdl/Infineon-AN91445_Antenna_Design_and_RF_Layout_Guidelines-ApplicationNotes-v09_00-EN.pdf | 3.11 |
| 22 | Johanson Technology Chip Antenna Layout Considerations | https://www.johansontechnology.com/tech-notes/chip-antenna-layout-considerations-for-ble-80211-and-24g-zigbee/ | 3.11 |
| 23 | Bogatin, The Critical Length of a Transmission Line | https://www.polarinstruments.com/support/cits/Critical_length.pdf | 3.0, 3.8 |
| 24 | Shim & Hubing, 20-H Rule Modeling and Measurements (IEEE EMC 2001) | https://cecas.clemson.edu/cvel/pdf/EMCS01-939.pdf | 3.7 (**20H çürütmesi**) |
| 25 | Montrose, PCB Design Techniques for EMC Compliance, IEEE Press 1996 | (kitap) | 3.7 (20H orijinal kaynağı) |
| 26 | ADI Schematic and Layout Guidelines for High-Speed Data Converters | https://www.analog.com/en/resources/technical-articles/schematic-and-layout-guidelines-for-highspeed-data-converters.html | 3.9 |
| 27 | ADI A Short Course in PCB Layout for High-Speed ADCs | https://www.analog.com/en/resources/technical-articles/a-short-course-in-pcb-layout-for-highspeed-adcs.html | 3.9 |
| 28 | Altium, Can We All Stop Quoting the Critical Length Rule? | https://resources.altium.com/p/can-we-all-stop-quoting-critical-length-rule | 3.8 |

## Bulunamayanlar

| Konu | Durum |
|---|---|
| Kristal -> MCU pini max mesafe (mm) | **BULUNAMADI** — 4 üretici, hiçbiri sayı vermiyor |
| Yük kondansatörü -> kristal mesafe (mm) | **BULUNAMADI** |
| USB-IF'in kendi mil/mm layout toleransları | **BULUNAMADI** — spec sadece 90 Ω ±%15 verir |
| MIPI D-PHY skew | **BULUNAMADI** — üye belgesi |
| LVDS yerleşim toleransları | **BULUNAMADI** |
| Analog <-> dijital iz min ayrım (mm) | **BULUNAMADI** — vekil: TI 30/50 mil |
| Kelvin bağlantı sayısal kuralı | **BULUNAMADI** |
| I2C pull-up konumu (normatif) | **BULUNAMADI** — UM10204 kural içermiyor |
| I2C izin verilen iz uzunluğu | **BULUNAMADI** — 400 pF'ten türetilmeli |
| SPI yerleşim toleransları | **BULUNAMADI (standart mevcut değil)** |
| NRST kondansatörü mesafesi (mm) | **BULUNAMADI** |
| 3W "%70" iddiasının birincil kaynağı | **BULUNAMADI** |
| 1.6 mm FR4 mikroşerit 50 Ω genişliği | **BULUNAMADI** (birincil) — AN91445 sadece CPWG verir |
