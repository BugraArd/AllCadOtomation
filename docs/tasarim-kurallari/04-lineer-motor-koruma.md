# 4. Lineer regülatör, motor sürücü, koruma, sensör, HV, mekanik

> **Kaynak etiketleri:** işaretsiz satırlar üretici app-note'undan birebir;
> **HESAP** = kaynaktaki formülden türetildi; **İKİNCİL** = blog/DFM kaynaklı,
> standart değil.

## 4.0 En önemli bulgu: "yakın olmalı" tavsiyelerinin sayısallaştırılması

Bu tablo, üretici kaynaklarında **gerçekten sayı geçen** tüm yerleşim
mesafelerini toplar. Kural motoruna eşik koyarken dayanabileceğimiz liste bu —
gerisi niteliksel.

| # | Kural | Sayı | Kaynak |
|---|---|---|---|
| 1 | Bypass kondansatörü -> IC besleme pini | **< 5 mm** (0.2 in) | TI SLVA959B §5.3.1 |
| 2 | 0.1 µF bypass -> sıcaklık sensörü (garanti şartı) | **<= 5 mm** | TI SNOA986A §3 |
| 3 | I2C pull-up direnci -> sıcaklık sensörü | **>= 10 mm** | TI SNOA986A §3, §11 |
| 4 | Gate izi genişliği (motor sürücü, 1 oz) | **>= 0.508 mm** | TI SLVA959B §4 |
| 5 | Güç izi genişliği | **>= 0.381 mm/A** | TI SNVA021C §5 |
| 6 | Güç için via sayısı | **1 via / 200 mA** | TI SNVA021C §5 |
| 7 | Via akım kapasitesi (10 °C, 1 oz) | 0.15 mm 0.2 A · 0.20 mm 0.55 A · 0.25 mm 0.81 A · 0.41 mm 1.1 A | TI SLVA959B Tablo 3-1 |
| 8 | Termal via boyutu | 0.20 mm delik / 0.51 mm çap -> 5.73 °C/W | TI SLVA959B §2.5-2.6 |
| 9 | Termal via sayısı | >=4-6 ped altında; ~10 °C/W için **10+** | TI SLPA015 §2 |
| 10 | Bypass kondansatörü ped en/boy oranı | **<= 3:1** | TI SLVA959B §5.3.1 |
| 11 | Gate surge koruma -> SiC MOSFET | **<= ~20 mm** | ROHM 67AN006E §4 |
| 12 | TVS parazitik endüktans bütçesi | **0.25 nH -> +10 V** @8 kV; hedef ~1 nH | TI SLVA680A §2.1 |
| 13 | TVS izi 50 mm x 0.5 mm | **52 nH -> clamp tamamen başarısız (3.4 kV)** | ROHM 66AN067E |
| 14 | TVS stub uzunluğu | **0 mm (yasak)** | TI SLVA680A §2.1 |
| 15 | Konnektör-TVS arasında via | **0 adet** | TI SLVA680A §2.3 |
| 16 | ESD izi köşe açısı | **<= 45°** | TI SLVA680A §2.2 |
| 17 | Bakır döküm faydalı yarıçapı | **~25 mm**, doygunluk 4.5 in²/yüzey | TI SLPA015 §2 |
| 18 | 1 W termal alan | 1 in² 2 oz -> 100 °C; 1 oz -> 125 °C | TI SLPA015 |
| 19 | SOT-223 θJA | 16 mm² 135 · 100 mm² 107 · 2500 mm² 50 °C/W | Richtek AN044 |
| 20 | Bileşen gövdeleri arası min. boşluk | 0.2 / **0.5** / 1.0 mm | IPC-7351B |
| 21 | HV creepage slot genişliği | PD1 **0.25** / PD2 **1.0** / PD3 **1.5** mm | IEC 60664-1 §6.2 |
| 22 | Elektrolitik vent üstü boşluk | Ø6.3-16 **2 mm** · Ø18-35 **3 mm** · Ø>=40 **5 mm** | Nichicon CAT.8101E |
| 23 | Sensör metal kapağı üstü boşluk (BME280) | **>= 0.1 mm** | Bosch BST-BME280-HS006 |
| 24 | Sıcaklık sensörü kart kalınlığı (hava ölçümü) | **0.8 mm** | TI SNOA967A §2.6 |
| 25 | Manyetometre -> 1 A güç izi (20 µT için) | **>= 10 mm** (HESAP) | NXP AN4247 |
| 26 | Via etrafı açık bakır (alt düzlemde) | 0.05 mm | TI SLVA959B Şekil 3-1 |
| 27 | Havada ark yarıçapı @7 kV | ~2.6 mm | TI SLVA680A §2.2 |

**Sayısı BULUNAMADI** (birincil kaynak yalnızca "yakın" diyor): LDO
CIN/COUT/NR-SS/FB direnç mesafesi · gate sürücü <-> FET mesafesi · TVS <->
konnektör mm değeri · konnektör kart kenarı mesafesi · sensör <-> ısı kaynağı mm
· nem sensörü keep-out mm · röle keep-out · IMU manyetik keep-out mm.

## 4.1 LDO / lineer regülatör

**Kritik bulgu:** TI, ADI ve MaxLinear'ın LDO datasheet/app-note'larının
**hiçbiri giriş/çıkış kondansatörü için mm cinsinden üst sınır vermiyor** —
hepsi "as close as practical" diyor. Bağlayıcı tek sayı TI'ın motor sürücü ve
sıcaklık sensörü notlarından geliyor ve genel IC bypass kuralı olarak
kullanılabilir.

| Kural | Sıkı | Tipik | Gevşek | Kaynak |
|---|---|---|---|---|
| Genel IC bypass -> besleme pini | 2 mm | 3-5 mm | **5 mm** | TI SLVA959B §5.3.1 |
| 0.1 µF bypass -> IC (garanti) | - | - | **5 mm** | TI SNOA986A §3 |
| Bypass pedi en/boy oranı | - | <=3:1 | 3:1 | TI SLVA959B |
| CIN/COUT ile IC arasına via | **yasak** | - | - | TI SBVS295A §10.1 |
| Küçük değerli kondansatör önce | zorunlu | - | - | TI SLVA959B |
| NR/SS kondansatörü mesafesi | **BULUNAMADI** (layout şeklinde pine bitişik çizili) | | | TI SBVS295A |
| ADJ/FB bölücü mesafesi | **BULUNAMADI** (mm) | | | - |
| CFF (feed-forward) -> FB pini | "as close as possible" — mm yok | | | TI SNVA021C §3 |
| FB izi yönlendirme | indüktör/gürültülü izlerden uzak, doğrudan ve kalın; tercihen indüktörün ters yüzünde, arada GND | | | TI SNVA021C §2 |

**Yorum:** "CIN'i VIN'e yakın koy" tavsiyesinin tek savunulabilir
sayısallaştırması **<= 5 mm**. 2-3 mm hedefleyin, 5 mm'yi aşmayın.

## 4.2 Termal: güç dissipasyonu <-> bakır alanı

### TI'ın "peçete arkası" kuralı (SLPA015)

| Kural | Değer |
|---|---|
| 1 W -> 1 in² **2 oz** bakır | **100 °C** artış |
| 1 W -> 1 in² **1 oz** bakır | **125 °C** artış |
| PCB üst<->alt yüzey termal empedansı | 10 °C/W |
| Tek termal via | ~100 °C/W |
| Termal ped altı via | 4-6 (sığdığı kadar); ~10 °C/W için 10+ |
| Bakır dökümünün doygunluğu | IC'den **~25 mm** yarıçaptan sonra kazanç yok |
| Pratik üst sınır | 4.5 in² (29 cm²)/yüzey, toplam 9 in² (58 cm²) |
| **HESAP:** 1 W'ta 40 °C artış için 2 oz alan | 2.5 in² ≈ **16 cm²** |
| **HESAP:** 1 W'ta 40 °C artış için 1 oz alan | 3.1 in² ≈ **20 cm²** |

### SOT-223 — ölçülmüş θJA vs bakır alanı (Richtek AN044, JESD51)

| Bakır alanı | θJA | PD @ TA=25 °C, TJ=125 °C |
|---|---|---|
| 16 mm² (standart footprint) | **135 °C/W** | 0.741 W |
| 100 mm² | **107 °C/W** | ~0.93 W (HESAP) |
| 2500 mm² | **50 °C/W** | 2.0 W (HESAP) |
| 3600 mm² | ~45 °C/W | ~2.2 W |
| θJC | 15 °C/W | - |

**HESAP — "1 W için kaç cm²?"** (SOT-223, tek kat, JESD51 kartı):
- TA=25 °C, TJ<=125 °C -> θJA <= 100 °C/W -> **~120-150 mm² (1.2-1.5 cm²)**
- TA=70 °C, TJ<=125 °C -> θJA <= 55 °C/W -> **~2000-2200 mm² (20-22 cm²)**

Yani "1 W için 1 cm²" ancak oda sıcaklığında ve TJ=125 °C'de doğru; gerçek
ortamda **~20 cm²** gerekiyor.

### Diğer paketler ve kat sayısı

| Kural | Değer | Kaynak |
|---|---|---|
| 1 oz düzlem, 1x1 cm yanal | 71.4 °C/W | TI SLVA959B §2.3 |
| 2 oz düzlem, 1x1 cm yanal | 35.7 °C/W | TI SLVA959B §2.3 |
| Termal via (0.51 mm çap / 0.20 mm delik, 1.561 mm FR4) | 5.73 °C/W | TI SLVA959B §2.5 |
| 2 kat (1/1 oz), 2 in² GND | 43.4 °C/W | TI SNVA183 |
| 4 kat (2/1/1/2 oz), 9 in² | **25.0 °C/W** | TI SNVA183 |
| Solder mask'i termal alandan kaldırma | 26.3 -> 25.0 (%5) | TI SNVA183 |
| SOT-23 / SO-8 / DFN-8 (4-kat JEDEC) | 220 / 128.4 / **59** °C/W | MaxLinear ANP-02 |
| JESD51-7 (1S2P) vs 51-3 (1S0P) | 1S2P ~**%50 daha düşük** θJA | JEDEC |

**DPAK için ayrık θJA-vs-alan tablosu BULUNAMADI.**

## 4.3 Motor sürücü / H-köprü / gate driver

| Kural | Değer | Kaynak |
|---|---|---|
| Bypass -> IC besleme pini | sıkı 2 · tipik 3 · **gevşek 5 mm** | TI SLVA959B §5.3.1 |
| Bypass ile IC arasına via | **yasak** | TI SLVA959B |
| Bulk kondansatör | güç girişi yanında, çoklu via; >10 µF düşük ESR | TI SLVA959B §5.1 |
| Güç katı seramik bypass | <10 µF, FET ve motora en yakın | TI SLVA959B §5.3.2-3 |
| CSA (sense) pin dekuplajı | ~1 nF, sense pinlerine en yakın | TI SLVA959B §5.3.4 |
| **Gate izi genişliği** | **0.508 mm (20 mil)** @1 oz | TI SLVA959B §4 |
| HS gate izi <-> switch-node izi | yakın/paralel (loop alanı min.) | TI SLVA959B §4 |
| Gate sürücü <-> FET mesafesi | "as close as possible" — **mm yok** | Infineon gate driver AN |
| **Gate surge koruma -> SiC MOSFET** | **<= ~20 mm** | ROHM 67AN006E §4 |
| SiC gate koruma önceliği | 1) aktif miller clamp 2) negatif surge clamp 3) pozitif surge clamp 4) G-S kondansatörü | ROHM 67AN006E |
| Yüksek akım izi | **>= 0.381 mm/A** mutlak minimum | TI SNVA021C §5 |
| Katlar arası via | 1 via / **200 mA** | TI SNVA021C §5 |
| **Sense direnci Kelvin bağlantısı** | sense sinyalleri **diferansiyel çift**, şönt'ten CSA girişine paralel ve sıkı eşleşmiş | TI SLVA959B §7.6 |
| Sense direnci yerleşimi | güç katıyla in-line, CSA'ya yakın | TI SLVA959B §7.5 |
| CAD zorlaması | şönt ile IC arasına **Net Tie** koy | TI SLVA959B §7.7 |
| VDRAIN Kelvin sense | tek iz, doğrudan FET drain'ine; drain'e yakın Net Tie | TI SLVA959B §6.3.3 |
| İz köşeleri | 90° **yasak**; <=45° veya geniş yay | TI SLVA959B §4 |
| Sense/CSA çevresi | kondansatör/direnç çiftleri yan yana, kaydırılmış yerleşim yasak | TI SLVA959B §4 |

## 4.4 ESD / TVS koruma

| Kural | Değer | Kaynak |
|---|---|---|
| TVS -> konnektör | tasarım kurallarının izin verdiği **en yakın** | TI SLVA680A §2.1 |
| Sayısallaştırma | < 5 mm | **İKİNCİL** (blog) |
| Korunan IC <-> TVS | TVS-konnektör mesafesinden **çok daha büyük** (L4 >> L1) | TI SLVA680A §2.1 |
| **Stub (TVS sapması)** | **0 mm — yasak** | TI SLVA680A §2.1 |
| Konnektör-TVS arasında via | **0 adet** | TI SLVA680A §2.3 |
| TVS anot -> GND | en kısa/geniş, **çoklu via** | TI SLVA680A §2.4 |
| Konnektör-TVS arası bölge | korumasız izler için **keep-out** | TI SLVA680A §2.2 |
| İz köşeleri | <=45° | TI SLVA680A §2.2 |
| **Parazitik endüktans etkisi** | 8 kV IEC 61000-4-2 -> dI/dt = 4e10 A/s; **0.25 nH -> +10 V** | TI SLVA680A §2.1 |
| **İz uzunluğu -> endüktans** | 50 mm x 0.5 mm = **52 nH**; 80 mm x 0.5 mm = **91 nH** | ROHM 66AN067E |
| Sonucu (8 kV) | 52+91 nH ile 1. tepe **3.4 kV** (TVS hiç çalışmıyor); ~1 nH ile **107 V** | ROHM 66AN067E |
| Via endüktansı | `L = 0.2·h·(ln(4h/d)+1)` nH -> tipik 0.5-1.5 nH | ROHM 66AN067E Eq.3 |

**Çelişki:** TI SLVA680A "IC'yi TVS'ten kasten uzağa (kart ortasına) koy, L4>>L1
olsun" derken ON/Littelfuse AND8232/D "ayrımı büyütmek loop alanını ve RF
duyarlılığını artırır" uyarısı yapıyor. Uzlaşma: TVS'i konnektöre yapıştır,
IC'yi makul mesafede tut, ama sürekli GND düzlemi ile sinyal+dönüş kuplajını
sıkı tut.

**Kural motoru için ders:** ESD'de asıl büyüklük mesafe değil **endüktans**
(yani iz uzunluğu × genişlik). 52 nH'lik bir iz TVS'i tamamen işlevsiz
bırakıyor — bu, "mesafe eşiği" tipi bir kuralın yakalayamayacağı bir hata.

## 4.5 Konnektörler

**Kritik bulgu:** Konnektör yerleşimi için mm cinsinden değer veren **birincil
kaynak bulunamadı.** Aşağıdakiler IPC-7351B (standart) + DFM/blog (ikincil).

| Kural | Sıkı | Tipik | Gevşek | Kaynak |
|---|---|---|---|---|
| Courtyard excess | 0.1 | **0.25** | 0.5 mm | IPC-7351B |
| Gövdeler arası min. boşluk | 0.2 | **0.5** | 1.0 mm | IPC-7351B |
| Üst üste binen parça açıklığı | - | >0.2 mm | - | İKİNCİL: JLCPCB |
| Min. IC pin aralığı (montaj) | 0.35 | 0.4 mm | - | İKİNCİL: JLCPCB |
| USB-C konnektör -> kart kenarı | 3 | 3-5 | 5 mm | İKİNCİL |
| ESD/CMC -> USB konnektörü | - | <=1.5 mm | - | İKİNCİL |
| Konnektör keep-out kapsamı | eşleşen gövde + mandal hareketi + kablo bükülme yarıçapı + NPTH pimleri + shield ayakları | | | İKİNCİL |
| Konnektör altında bakır/keep-out | **BULUNAMADI** (birincil) | | | - |

## 4.6 Sensörler

### Sıcaklık sensörü (sayısal değer veren nadir kaynak)

| Kural | Değer | Kaynak |
|---|---|---|
| **0.1 µF bypass -> sensör** | **<= 5 mm** | TI SNOA986A §3 |
| **I2C pull-up -> sensör** (öz-ısınma) | **>= 10 mm** | TI SNOA986A §3, §11 |
| Pull-up direnç değeri | > 5 kΩ | TI SNOA986A |
| Isı kaynağından mesafe | kart köşesine, ısı üreten IC'lerden mümkün olduğunca uzak (**mm yok**) | TI SNOA967A §2.2 |
| **Termal izolasyon slot'u** | sensör etrafına kısmi router izi ("isolation island") | TI SNOA967A §2.3 |
| Slot genişliği (mm) | **BULUNAMADI** | - |
| GND düzlemi | diğer IC'lerin düzlemi sensöre uzatılmaz; ana bölgede hatched GND | TI SNOA967A §2.1 |
| PCB kalınlığı (hava ölçümü) | **0.8 mm** (1.6 yerine) | TI SNOA967A §2.6 |
| Bakır vs FR4 iletkenlik | bakır ~FR4'ün **1500 katı** | TI SNOA967A |

### Nem / basınç sensörü

| Kural | Değer | Kaynak |
|---|---|---|
| Isı kaynağından mesafe | **SAYI YOK — kasten verilmiyor** | Sensirion Design Guide §3.1 |
| Termal izolasyon | frezelenmiş yarıklar; metal bağlantıları mümkün olduğunca ince | Sensirion §3.1 |
| Bosch BME280 | *"a 'reasonable distance' depends on many customer specific variables"* — Bosch sayı vermeyi açıkça reddediyor | Bosch BST-BME280-HS006 §5.3 |
| BME280 metal kapak üstü boşluk | **>= 0.1 mm** | Bosch §5.8 |
| BME280 keep-out | buton kontağı altına/yanına, kart kenarına yakın, vida noktasına yakın **koyma** | Bosch §5.3-5.7 |

### Manyetik keep-out (IMU / manyetometre / hall)

Sayısal keep-out yok ama **formül var**:

```
B(r) = µ0·I / (2π·r) = 0.2e-6 · I / r      [T, r metre]
```

| Durum | Değer | Kaynak |
|---|---|---|
| 1 A güç izi, 1 mm mesafede | **200 µT** | NXP AN4247 §6 |
| 1 A güç izi, 10 mm mesafede | **20 µT** | NXP AN4247 §6 |
| Hedef pusula hatası 3° | ölçüm hatası <= **0.5 µT** | AN4247 §2 |
| **HESAP:** 1 A izden 0.5 µT'ye inmek | r = **400 mm** -> pratikte imkânsız, kalibrasyon zorunlu | AN4247 Eq.4 |
| **HESAP:** 1 A izden 20 µT'ye inmek | **10 mm** — makul minimum keep-out | AN4247 Eq.4 |
| Yer manyetik alanı (referans) | 22-67 µT | AN4247 §2 |
| Hard/soft iron girişimi | **>1000 µT** olabilir, sensörü doyurur | AN4247 §1.2 |
| **Yasak malzemeler** | demir, kobalt, **nikel** ve alaşımları (hoparlör mıknatısı, vibratör, çelik shield, batarya) | AN4247 §8 |
| **Güvenli malzemeler** | pirinç, alüminyum, bakır, altın, gümüş, titanyum | AN4247 §8 |
| **Ekranlama** | **yapmayın** — alüminyum manyetik alana şeffaf, çelik shield ek soft-iron girişimi yaratır | AN4247 §7 |

## 4.7 Sigorta / güç girişi / ters polarite koruma

**Sıralama:** giriş -> **sigorta/PTC** -> **TVS** -> **ters polarite koruma** ->
giriş kondansatörü -> DC/DC & yük.

| Kural | Değer | Kaynak |
|---|---|---|
| TVS tipi seçimi | tek yönlü TVS, ters polarite korumasından **önce** konursa ters polaritede iletime geçer -> o konumda **çift yönlü** kullan | TI E2E |
| Neden TVS Schottky'den önce | surge akımını en kısa yoldan toprağa gönderip Schottky'den geçirmemek | EE Times (İKİNCİL) |
| Sigorta-TVS koordinasyonu | TVS'in tekrarlı clamp akımı sigortanın I²t'siyle koordine edilmeli | TI E2E |
| **mm cinsinden mesafe** | **BULUNAMADI** — hiçbir birincil kaynak sayısal mesafe vermiyor | - |

## 4.8 Yüksek gerilim / şebeke (AC-DC)

### PCB slot (bakır kaldırma) — creepage artırma

| Kirlilik derecesi | **Minimum slot genişliği** |
|---|---|
| PD1 | **0.25 mm** |
| PD2 (lab/ofis/kapalı kabin) | **1.0 mm** |
| PD3 (endüstriyel) | **1.5 mm** |

Kaynak: IEC 60664-1 §6.2, TI SLUP419 Tablo 7. Slot **sadece creepage'ı**
artırır, **clearance'ı etkilemez**.

Optokuplör altı uygulama örneği: 2.00 mm slot + iki yanda 3.30 mm -> toplam
creepage 8.60 mm (İKİNCİL: In Compliance Magazine). Toshiba SO6 TLP2355 gövdesi
kendi başına min. 5 mm creepage/clearance garanti eder.

### Creepage — IEC 60664-1 Tablo F.4 (alt küme)

| Çalışma gerilimi (V_RMS) | PD1 | PD2 Grup I | PD2 Grup II | PD2 Grup IIIa |
|---|---|---|---|---|
| 63 V | 0.2 | 0.63 | 0.9 | 1.25 |
| 400 V | 1.0 | **2.0** | 2.8 | **4.0** |
| 800 V | 2.4 | 4.0 | 5.6 | 8.0 |
| 1000 V | 3.2 | 5.0 | 7.1 | 10.0 |

**Reinforced = basic'in 2 katı creepage.** Creepage, clearance'tan küçük olamaz.

### Clearance — IEC 60664-1 Tablo F.2 (parantez: IEC 62368-1, daha sıkı)

| Impuls dayanımı | PD1 | PD2 | PD3 |
|---|---|---|---|
| 0.5 kV | 0.04 | 0.2 | 0.8 |
| 1.5 kV | - | **0.5** (62368: 0.76) | 0.8 |
| 2.5 kV | - | **1.5** (62368: 1.8) | - |
| 4.0 kV | - | **3.0** (62368: 3.8) | - |
| 6.0 kV | - | **5.5** (62368: 7.9) | - |

**İmpuls gerilimi seçimi** (IEC 60664-1 Tablo F.1):

| Hat-nötr | OVC I | OVC II | OVC III | OVC IV |
|---|---|---|---|---|
| 50 V | 330 | 500 | 800 | 1500 V |
| 150 V (120 VAC ABD) | 800 | 1500 | 2500 | 4000 V |
| 300 V (230 VAC AB) | 1500 | **2500** | 4000 | 6000 V |
| 600 V (endüstriyel motor) | 2500 | 4000 | 6000 | 8000 V |

- Reinforced için Tablo F.1'de **bir kademe yukarı** çık.
- AC transientine maruz değilse: gerekli impuls = nominal L-N + 1200 V.
- Rakım > 2000 m -> IEC 60664-1 Tablo A.2 çarpanı.
- **HiPOT:** 2 × V_çalışma + 1000 V; 265 VAC -> 1530 V, yaygın test 1.5 kV.

### Mains <-> SELV bölge ayrımı

| Taraflar | Gereken izolasyon |
|---|---|
| SELV <-> SELV | functional |
| Primary / hazardous <-> **topraklanmış** SELV | basic |
| Primary / hazardous <-> **topraklanmamış** SELV | **reinforced** |
| ES3 (>120 V) <-> kullanıcı | **reinforced** |

TI SLUP419 notu: IEC 60664-1 Tablo F.4'ün ilk iki sütunu ile IPC-2221B Tablo
6-1'in kaplamasız dış katman değerleri **birbirine çok yakın**; IPC-9592B,
IPC-2221B'den daha muhafazakâr.

## 4.9 Röle / elektrolitik / kristal — yükseklik ve mekanik

### Alüminyum elektrolitik kondansatör (Nichicon CAT.8101E)

| Kural | Değer |
|---|---|
| **Basınç tahliye venti üstünde boşluk** — Ø6.3-16 mm | **>= 2 mm** |
| Ø18-35 mm | **>= 3 mm** |
| Ø >= 40 mm | **>= 5 mm** |
| Vent üstünde iz/pattern | **yasak** |
| Vent PCB'ye bakıyorsa | PCB'ye vent konumuna denk **delik** aç |
| End-seal altında iz | **yasak** — elektrolit iletkendir, patlarsa kısa devre/yangın |
| Isı üreten bileşenler | elektrolitiğin yanına veya ters yüzde altına **koyma** |
| Ömür | her +10 °C -> ömür yarıya (İKİNCİL, Arrhenius) |

**Çelişki:** bazı bloglar vent üstü boşluk için 4 mm diyor; Nichicon (birincil)
Ø<=16 mm için 2 mm der. Üretici datasheet'i esastır.

### Kristal / osilatör (ST AN2867)

| Kural | Değer |
|---|---|
| İz uzunluğu | "as much as possible" azalt — **mm yok** |
| Guard ring | kristal etrafına; **hemen altındaki katta lokal** ground plane (tüm kartta değil) |
| VSS yolları | CL1/CL2 altında biten VSS yolları quartz altındaki ground shield'e **değmemeli** |
| Yüksek frekanslı sinyal | osilatör devresi yakınında bulunmamalı |
| Dekuplaj | her VDD yolu ile **en yakın** VSS yolu arasına |
| CL yük kondansatörü mesafesi (mm) | **BULUNAMADI** |

### Röle

**BULUNAMADI** — sayısal PCB keep-out/yükseklik kuralı veren birincil kaynak
yok. Dolaylı uygulanabilir: IPC-7351B courtyard, bobin akımı için 0.381 mm/A,
kontak tarafı için IEC 60664-1 clearance/creepage, manyetik sensör varsa
NXP AN4247 keep-out.

## Çelişkiler ve uyarılar

1. **TVS <-> korunan IC mesafesi:** TI "uzağa koy", ON/Littelfuse "uzaklaştırma
   loop alanını artırır". -> Sürekli GND düzlemi ile çözülür.
2. **"1 W = 1 in² 2 oz -> 100 °C" doğrusal değil.** TI kuralına göre 2500 mm²
   için ~25.6 °C/W çıkar; Richtek'in **ölçtüğü** SOT-223 değeri **50 °C/W** —
   yaklaşık **2x iyimser**. Sadece ilk yaklaşım; gerçek θJA datasheet'ten.
3. **JEDEC θJA uygulama tahmini için geçersiz.** ROHM 65AN114E: *"θJA is neither
   intended nor able to predict package performance in application-specific
   environments"* — yalnızca paket karşılaştırması içindir.
4. **Sensör üreticileri bilerek sayı vermiyor** (Bosch, Sensirion). Buna karşılık
   TI sıcaklık sensörü için net 5 mm / 10 mm veriyor. TI'ın 10 mm'sini nem
   sensörüne taşımak makul ama **kaynaklı değildir**.
5. **Elektrolitik vent boşluğu:** Nichicon 2 mm, bloglar 4 mm. Üretici esas.
6. **IPC-2221 != IEC 60664-1 != IEC 62368-1.** IEC 62368-1 clearance'ları
   60664-1'den sistematik olarak daha sıkı (6 kV: 5.5 vs 7.9 mm). Ürün
   standardınızın tablosunu kullanın.
7. **Manyetometre keep-out fiziksel olarak imkânsız:** 1 A izden 0.5 µT hedefine
   400 mm gerekir -> yazılım kalibrasyonu zorunlu, yerleşimle çözülemez.

## Kaynaklar

| # | Doküman | URL | Destek |
|---|---|---|---|
| 1 | TI SNVA021C (AN-1149) Layout Guidelines for Switching Power Supplies | https://www.ti.com/lit/pdf/snva021 | 4.1, 4.3 (0.381 mm/A, 1 via/200 mA) |
| 2 | TI SBVS295A TPS7A52 datasheet §10 | https://www.ti.com/lit/ds/symlink/tps7a52.pdf | 4.1 (sayı yokluğunun kanıtı) |
| 3 | TI SLVA959B Best Practices for Board Layout of Motor Drivers | https://www.ti.com/lit/pdf/slva959 | 4.1, 4.2, 4.3 |
| 4 | TI SLPA015 Accurate Thermal Calculations on the Back of a Napkin | https://www.ti.com/lit/pdf/slpa015 | 4.2 |
| 5 | TI SNVA183 (AN-1520) Guide to Board Layout for Best Thermal Resistance | https://www.ti.com/lit/pdf/snva183 | 4.2 |
| 6 | Richtek AN044 Thermal Characteristic of SOT-223 | https://www.richtek.com/Design%20Support/Technical%20Document/AN044 | 4.2 (ölçülmüş θJA) |
| 7 | ROHM 65AN114E θJA and ψJT | https://fscdn.rohm.com/en/products/databook/applinote/common/theta_ja_and_psi_jt_an-e.pdf | 4.2 (θJA'nın geçersizliği) |
| 8 | MaxLinear ANP-02 Thermal Considerations for Linear Regulators | https://www.maxlinear.com/appnote/anp-02.pdf | 4.1, 4.2 |
| 9 | TI SLVA680A ESD Protection Layout Guide | https://www.ti.com/lit/pdf/slva680 | 4.4 |
| 10 | ROHM 66AN067E PCB Layout for TVS Diodes | https://fscdn.rohm.com/en/products/databook/applinote/discrete/diodes/pcb_layout_for_tvs_diodes_an-e.pdf | 4.4 (52/91 nH) |
| 11 | ON/Littelfuse AND8232/D TVS PCB Design Guidelines | https://www.littelfuse.com/ | 4.4 (çelişki) — tam metne erişilemedi |
| 12 | Infineon PCB layout guidelines for MOSFET gate driver | https://www.infineon.com/ | 4.3 |
| 13 | ROHM 67AN006E SiC MOSFET Layout Design Considerations | https://fscdn.rohm.com/en/products/databook/applinote/discrete/sic/mosfet/sic_mosfet_layout_design_considerations_an-e.pdf | 4.3 (<=20 mm) |
| 14 | TI SNOA967A Temperature sensors: PCB guidelines for SMD | https://www.ti.com/lit/an/snoa967a/snoa967a.pdf | 4.6 |
| 15 | TI SNOA986A Precise Temperature Measurements With TMP116/117 | https://www.ti.com/lit/pdf/snoa986a | 4.6 (**5 mm / 10 mm**) |
| 16 | Sensirion Design Guide for Humidity and Temperature Sensors | https://sensirion.com/media/documents/FC5BED84/662B494D/Sensirion_Humidity_Temperature_Design_Guide.pdf | 4.6 |
| 17 | Bosch BST-BME280-HS006 Handling, soldering & mounting | https://www.bosch-sensortec.com/media/boschsensortec/downloads/handling_soldering_mounting_instructions/bst-bme280-hs006.pdf | 4.6 |
| 18 | NXP AN4247 Layout Recommendations for PCBs Using a Magnetometer | https://www.nxp.com/docs/en/application-note/AN4247.pdf | 4.6 (B formülü) |
| 19 | TI SLUP419 Demystifying Clearance and Creepage Distance | https://www.ti.com/lit/pdf/slup419 | 4.8 (slot 0.25/1.0/1.5 mm, IEC tabloları) |
| 20 | ST AN2867 Oscillator design guide for STM8/STM32 §7 | https://www.st.com/resource/en/application_note/an2867-oscillator-design-guide-for-stm8afals-stm32-mcus-and-mpus-stmicroelectronics.pdf | 4.9 |
| 21 | Nichicon Application Guidelines for Aluminum Electrolytic Capacitors CAT.8101E | https://www.nichicon.co.jp/english/products/pdf/aluminum-e.pdf | 4.9 (vent 2/3/5 mm) |
| 22 | JEDEC JESD51-7 High Effective Thermal Conductivity Test Board | https://www.jedec.org/standards-documents/docs/jesd-51-7 | 4.2 |
| 23 | IPC-7351B (özet) | https://www.protoexpress.com/blog/features-of-ipc-7351-standards-to-design-pcb-component-footprint/ | 4.5 |
| 24 | Toshiba Photocoupler Application Note 1 | https://toshiba.semicon-storage.com/info/docget.jsp?did=61477 | 4.8 |
| 25 | In Compliance — Creepage Distance of an Optocoupler | https://incompliancemag.com/creepage-distance-of-an-optocoupler/ | 4.8 — İKİNCİL |
| 26 | EE Times — Reliable Power-Path Design | https://www.eetimes.com/reliable-power-path-design-integrating-mosfets-diodes-tvs-devices-and-capacitors/ | 4.7 — İKİNCİL |
| 27 | JLCPCB PCB Assembly Capabilities | https://jlcpcb.com/capabilities/pcb-assembly-capabilities | 4.5 — İKİNCİL |
| 28 | Allegro Hall Effect Sensor Applications Guide | https://www.allegromicro.com/en/insights-and-innovations/technical-documents/hall-effect-ic-publications/hall-effect-ic-applications-guide | 4.6 |

**22 birincil (üretici app-note / standart) + 6 ikincil kaynak.**

## Erişilemeyen kaynaklar

TDK InvenSense AN-000393/AN-000262 (IMU PCB kuralları), ON/Littelfuse AND8232/D
tam metni, ADI LT3045/ADP7118 datasheet layout bölümleri — sunucular 403/404
döndürdü. Bunlar 4.5 (konnektör), 4.6 (IMU keep-out) ve 4.1 (LDO mm)
boşluklarını kapatabilir.
