# 2. Üretilebilirlik ve elektriksel sınırlar (IPC + fab)

> Kaynaklardan toplanmış sayısal veri. Bölüm sonunda kaynak listesi var.
> Çelişkiler gizlenmedi; hangi değeri neden seçtiğimiz yazıyor.

## 2.1 IPC-2221B iz genişliği formülü

```
A [mil²] = ( I / (k · ΔT^0.44) )^(1/0.725)
W [mil]  = A / (kalınlık[oz] × 1.378)

k = 0.048  -> DIŞ katman
k = 0.024  -> İÇ katman
1 oz bakır = 1.378 mil = 35 µm (nominal)
```

**İç/dış farkı:** Aynı akım için iç katman izi, dış katmandan `2^(1/0.725) = 2.601x`
daha geniş olmalı. Sık duyulan "iki katı" ezberi yanlıştır.

## 2.2 IPC-2152 ile farkı

IPC-2221 1950'lerin eğri uydurmasına dayanır ve bakır alanın/plane'in soğutma
etkisini yok sayar. IPC-2152 (2009) yüzlerce gerçek ölçüme dayanır.

| Akım | IPC-2221 | IPC-2152 | Fark |
|---|---|---|---|
| 1 A | 10 mil | 8 mil | %20 dar |
| 3 A | 50 mil | 42 mil | %16 dar |
| 5 A | 110 mil | 95 mil | %14 dar |
| 10 A | 330 mil | 290 mil | %12 dar |

**DİKKAT - bu tablo eksik bir doğru.** Bağımsız ikinci bir araştırma, IPC-2152'nin
**çıplak temel eğrisinin** (Figure 5-1/5-2) aslında IPC-2221 dış katmanından
**daha muhafazakâr** olduğunu gösterdi: 3 A / 1 oz / 10 °C -> IPC-2221 dış
1.37 mm, IPC-2152 evrensel eğri **2.10 mm**. Yukarıdaki "%12-20 daha dar"
karşılaştırması yalnızca **çarpanlar uygulanmış** (düzlem yakınlığı, kart
kalınlığı, malzeme, ortam) tipik kart için geçerli. Ayrıntı ve Jouppi'nin
IPC-2221 grafiklerinin kökenine dair açıklaması:
[01-anahtarlamali-guc.md](01-anahtarlamali-guc.md) §1.7.

**Karar:** kural motorunda IPC-2221B kullanıyoruz — formülü açık ve telifsiz
erişilebilir, IPC-2152 ham tabloları telifli. İki standardın hangisinin daha
gevşek olduğu duruma bağlı olduğu için, tek bir "doğru" sayı iddiası da
edilmiyor: kural motoru ΔT ve bakır ağırlığını parametre olarak alır.

## 2.3 İz genişliği tabloları (IPC-2221B, mm)

Formülden doğrudan hesaplandı (ara yuvarlama yok), yayınlanmış tablolarla
çapraz doğrulandı.

### DIŞ katman, 1 oz (35 µm)

| Akım | ΔT = 10 °C | ΔT = 20 °C |
|---|---|---|
| 0.1 A | 0.013 | 0.008 |
| 0.25 A | 0.044 | 0.029 |
| 0.5 A | 0.115 | 0.076 |
| 1 A | 0.300 | 0.197 |
| 2 A | 0.781 | 0.513 |
| 3 A | 1.367 | 0.898 |
| 5 A | 2.765 | 1.816 |
| 8 A | 5.288 | 3.472 |
| 10 A | 7.194 | 4.724 |
| 15 A | 12.585 | 8.264 |
| 20 A | 18.715 | 12.288 |

### DIŞ katman, 2 oz (70 µm)

| Akım | ΔT = 10 °C | ΔT = 20 °C |
|---|---|---|
| 0.5 A | 0.058 | 0.038 |
| 1 A | 0.150 | 0.099 |
| 2 A | 0.391 | 0.257 |
| 3 A | 0.683 | 0.449 |
| 5 A | 1.383 | 0.908 |
| 10 A | 3.597 | 2.362 |
| 20 A | 9.357 | 6.144 |

### İÇ katman, 1 oz (35 µm)

| Akım | ΔT = 10 °C | ΔT = 20 °C |
|---|---|---|
| 0.5 A | 0.300 | 0.197 |
| 1 A | 0.781 | 0.513 |
| 2 A | 2.033 | 1.335 |
| 3 A | 3.556 | 2.335 |
| 5 A | 7.194 | 4.724 |
| 10 A | 18.715 | 12.288 |

### İÇ katman, 2 oz (70 µm)

| Akım | ΔT = 10 °C | ΔT = 20 °C |
|---|---|---|
| 0.5 A | 0.150 | 0.099 |
| 1 A | 0.391 | 0.257 |
| 2 A | 1.016 | 0.667 |
| 3 A | 1.778 | 1.167 |
| 5 A | 3.597 | 2.362 |
| 10 A | 9.357 | 6.144 |

**Pratik uyarı:** 10 A üzerindeki değerler (12-48 mm iz!) IPC-2221'in aşırı
muhafazakârlığını gösterir. O akımlarda pratikte polygon pour / bara kullanılır;
kural motoru bu yüzden yüksek akımda yumuşak davranmalı.

## 2.4 Gerilime göre minimum iletken açıklığı (IPC-2221B Tablo 6-1, mm)

Sınıflar: **B1** iç katman · **B2** dış, kaplamasız, <=3050 m · **B3** dış,
kaplamasız, >3050 m · **B4** dış, polimer kaplamalı · **A5/A6/A7** montajlı kart.

| Gerilim (DC / AC tepe) | B1 | B2 | B3 | B4 | A5 | A6 | A7 |
|---|---|---|---|---|---|---|---|
| 0-15 V | 0.05 | 0.10 | 0.10 | 0.05 | 0.13 | 0.13 | 0.13 |
| 16-30 V | 0.05 | 0.10 | 0.10 | 0.05 | 0.13 | 0.25 | 0.13 |
| 31-50 V | 0.10 | 0.60 | 0.60 | 0.13 | 0.13 | 0.40 | 0.13 |
| 51-100 V | 0.10 | 0.60 | 1.50 | 0.13 | 0.13 | 0.50 | 0.13 |
| 101-150 V | 0.20 | 0.60 | 3.20 | 0.40 | 0.40 | 0.80 | 0.40 |
| 151-170 V | 0.20 | 1.25 | 3.20 | 0.40 | 0.40 | 0.80 | 0.40 |
| 171-250 V | 0.20 | 1.25 | 6.40 | 0.40 | 0.40 | 0.80 | 0.40 |
| 251-300 V | 0.20 | 1.25 | 12.50 | 0.40 | 0.40 | 0.80 | 0.80 |
| 301-500 V | 0.25 | 2.50 | 12.50 | 0.80 | 0.80 | 1.50 | 0.80 |
| >500 V (V başına ek) | +0.0025 | +0.005 | +0.025 | +0.00305 | +0.00305 | +0.00305 | +0.00305 |

500 V üstü: 301-500 V satırındaki tabana, 500 V üzerindeki her volt için ek
eklenir. Örnek (B1, 580 V): `0.25 + (580 - 500) x 0.0025 = 0.45 mm`.

**Çelişki:** Sierra Circuits sayfası B3 @151-170 V için 6.4 (diğer iki kaynak
3.2) ve 500 V üstü B1/B4 için 0.025 mm/V (diğerleri 0.0025) veriyor. EMA + SF
Circuits birebir aynı, Altium'un örnek hesabı 0.0025'i teyit ediyor ->
**tabloda çoğunluk değerleri var, Sierra'daki iki hücre dizgi hatası.**

**Kritik:** Bu tablo **clearance (hava aralığı)** verir, **creepage değildir.**
Şebeke izolasyonu için 2.5'e bakın.

## 2.5 Creepage - IEC 60664-1 / IEC 62368-1 (mm)

| RMS | PCB PD1 | PCB PD2 | PD2 Grup I | PD2 Grup II | PD2 Grup IIIa/b | PD3 Grup IIIa/b |
|---|---|---|---|---|---|---|
| 25 V | 0.025 | 0.04 | 0.5 | 0.5 | 0.5 | 1.25 |
| 50 V | 0.025 | 0.04 | 0.6 | 0.85 | 1.2 | 1.9 |
| 100 V | 0.1 | 0.16 | 0.71 | 1.0 | 1.4 | 2.2 |
| 125 V | 0.16 | 0.25 | 0.75 | 1.05 | 1.5 | 2.4 |
| 160 V | 0.25 | 0.4 | 0.8 | 1.1 | 1.6 | 2.5 |
| 200 V | 0.4 | 0.63 | 1.0 | 1.4 | 2.0 | 3.2 |
| **250 V** | 0.56 | 1.0 | 1.25 | 1.8 | **2.5** | 4.0 |
| 320 V | 0.75 | 1.6 | 1.6 | 2.2 | 3.2 | 5.0 |
| 400 V | 1.0 | 2.0 | 2.0 | 2.8 | 4.0 | 6.3 |
| 500 V | 1.3 | 2.5 | 2.5 | 3.6 | 5.0 | 8.0 |
| 630 V | 1.8 | 3.2 | 3.2 | 4.5 | 6.3 | 10.0 |
| 800 V | 2.4 | 4.0 | 4.0 | 5.6 | 8.0 | 12.5 |
| 1000 V | 3.2 | 5.0 | 5.0 | 7.1 | 10.0 | 16.0 |

Malzeme grubu (CTI): I >= 600 · II 400-600 · IIIa 175-400 · IIIb 100-175.
**Standart FR-4 tipik olarak IIIa.**
Kirlilik derecesi: PD1 iletken değil · PD2 yoğuşmayla geçici iletken (tipik
kapalı ekipman) · PD3 normalde iletken ortam.

### 230 VAC şebeke bariyeri (PD2, Grup IIIa)

| İzolasyon | Creepage |
|---|---|
| Temel (basic) | **2.5 mm** |
| Takviyeli (reinforced) | **5.0 mm** |

Kural: takviyeli izolasyon creepage'i **2x yapar**; clearance için ise darbe
gerilimi serisinde **bir kademe yukarı** çıkılır (2x değil).

**Çelişki / uyarı:** Sahada sık duyulan "230 V -> 3.2 mm basic / 6.4 mm
reinforced" değerleri IEC 62368-1 Tablo 28'in düz creepage satırından gelmez;
eski UL/IEC 60950 şebeke ek gereklilikleri ve daha yüksek aşırı gerilim
kategorisi varsayımından gelir. **Ürün tasarımında güvenlik uzmanına teyit
ettirilmeden kullanılmamalı** - sadece 250 V satırını okumak yetmez.

## 2.6 PCB üreticisi minimumları

### JLCPCB

| Parametre | 2 katman (1 oz) | 4+ katman (1 oz) |
|---|---|---|
| Min. iz genişliği | 0.10 mm | 0.09 mm |
| Min. açıklık | 0.10 mm | 0.09 mm |
| Min. delik | 0.15 mm | 0.15 mm |
| Min. via (delik/pad) | 0.15 / 0.25 mm | 0.15 / 0.25 mm |
| Annular ring | önerilen >=0.25, min. 0.18 mm | önerilen >=0.20, min. 0.15 mm |
| Via delik-delik | 0.20 mm | 0.20 mm |
| PTH pad delik-delik | 0.45 mm | 0.45 mm |
| Via-iz | 0.20 mm | 0.20 mm |
| İç katman via delik-bakır | - | 0.20 mm |
| Min. maske köprüsü | 0.10 mm | 0.10 mm |
| Bakır-kart kenarı (routed) | >=0.20 mm | >=0.20 mm |

### PCBWay

| Parametre | Değer |
|---|---|
| Min. iz / açıklık | 0.10 mm |
| Min. annular ring | 0.15 mm |
| Bitmiş delik | 0.20-6.2 mm, tolerans ±0.08 mm |
| Dış bakır | 1 / 2 / 3 oz |

### OSH Park (2 katman)

| Parametre | Değer |
|---|---|
| Min. iz / açıklık | 6 mil (0.1524 mm) |
| Min. delik | 10 mil (0.254 mm) |
| Min. annular ring | 5 mil (0.127 mm) |
| Kart kenarı keepout | 15 mil (0.381 mm) |

**Özet sınıflar:** standart havuz 0.15 mm iz/açıklık + 0.30 mm delik (her yerde
ücretsiz) · yaygın ucuz sınıf 0.10/0.10 mm + 0.20 mm delik · gelişmiş
0.09/0.09 mm + 0.15 mm delik (fiyat sınıfı yükseltir).

**Eurocircuits sınıf tablosu BULUNAMADI** (yalnızca gömülü görsel olarak
yayınlanıyor). Elde edilen kural: IPI (bağlantısız delik kenarı -> en yakın
bakır) = `IAR + 0.075 mm`, minimum 0.200 mm.

## 2.7 Kart kenarı açıklığı

| Durum | Min. bakır-kenar |
|---|---|
| Frezelenmiş profil, dış katman (Eurocircuits) | 0.25 mm |
| Frezelenmiş profil, iç katman (Eurocircuits) | 0.40 mm |
| V-cut / V-scoring (Eurocircuits) | 0.45 mm |
| JLCPCB (routed) | >=0.20 mm |
| OSH Park | 0.381 mm |
| V-score (MADPCB) | ~0.51 mm |
| Delik -> kart kenarı | >=0.50 mm |

**Çelişki:** V-scoring için 0.40 / 0.45 / 0.51 mm; routing için 0.13-0.381 mm.
**Seçim: routing 0.3 mm, V-score 0.5 mm** - çoğu üreticiyi karşılar.

Yüksek gerilimde kenar açıklığı 2.5'teki creepage değerinden küçük olmamalı ve
kenar **kaplamasız (B2/B3)** kabul edilmeli - kesme işlemi bakırı açığa çıkarır,
reçineyi çatlatabilir. Bu konuda tek sayısal üretici standardı BULUNAMADI.

## 2.8 Montaj boşlukları (IPC-7351B courtyard excess)

| Yoğunluk | Excess | Bileşenler arası fiili boşluk | Kullanım |
|---|---|---|---|
| Level L (Least) | 0.10 mm | 0.20 mm | Yüksek yoğunluk, taşınabilir |
| **Level N (Nominal)** | **0.25 mm** | **0.50 mm** | Standart üretim - varsayılan |
| Level M (Most) | 0.50 mm | 1.00 mm | Ruggedized, yüksek güvenilirlik |

**Önemli:** IPC-7352 courtyard excess'i yalnızca **SMD** ve **delikli (TH)**
diye ikiye ayırır. Chip/SOIC/QFP/BGA/elektrolitik/konnektör bazında ayrı resmi
tablo **BULUNAMADI** - firmalar kendi iç standardını geliştiriyor. Dolayısıyla
"bileşen tipine göre courtyard" kuralı standarda dayanamaz; sadece yoğunluk
seviyesi seçimi dayanabilir.

Dalga lehim için bileşenler arası sayısal minimum **BULUNAMADI** (IPC-7351
reflow içindir; dalga lehim gölgelemesi EMS'e özgüdür).

## 2.9 Delik-bakır ve via-via

| Parametre | Değer |
|---|---|
| PTH delik -> bakır, dış | 0.20 mm standart (uç süreç 0.127) |
| PTH delik -> bakır, iç | 0.15 mm |
| NPTH delik -> bakır | >=0.40 mm |
| Montaj/vida deliği -> bakır | >=1.0 mm (vida kenarından) |
| Delik -> kart kenarı | >=0.50 mm |
| Via delik -> delik (JLCPCB) | 0.20 mm |
| PTH pad delik -> delik | 0.45 mm |

**Via-via:** tek bir IPC minimumu yok; üretim sınırı ~0.20 mm. "IPC 0.6 mm"
diye dolaşan değer aslında **gerilim kaynaklı** (Tablo 6-1 B2, 51-100 V);
ikisini karıştırmayın.

**Etch payı:** Etch kompanzasyonu ve bakır wicking efektif açıklığı 1-2 mil
azaltabilir -> IPC minimumunun üzerine **en az %20 tasarım payı** önerilir.

## 2.10 "1 oz bakır" gerçekte ne kadar?

Bu, iz genişliği hesabını doğrudan etkiliyor.

| Katman | Nominal | Gerçek bitmiş (Class 2 min.) |
|---|---|---|
| İç, 1 oz (35 µm) | 35 µm | **24.9 µm** (%71) |
| Dış, 1 oz (35 µm) | 35 µm | **47.9 µm** (kaplama ekler) |
| İç, 2 oz (70 µm) | 70 µm | 55.7 µm |
| Dış, 2 oz (70 µm) | 70 µm | 78.7 µm |

**Sonuç - iki hata ters yönde:**
- **İç katman 1 oz gerçekte ~25 µm** -> 2.3'teki iç katman tabloları
  **iyimser**, gerçek kapasite ~%25 düşük. İç katmanda ek pay bırakın.
- **Dış katman 1 oz gerçekte ~48-60 µm** (galvanik kaplama bakır ekler) ->
  dış katman tabloları **muhafazakâr**, gerçek kapasite daha yüksek.

"1 oz bakır" garantili tek bir bitmiş kalınlık değildir (NCAB).

## Kaynaklar

| # | Başlık | URL | Destek |
|---|---|---|---|
| 1 | PCB Trace Width Calculator (IPC-2221) | https://tracewidthcalculator.com/ | 2.1 formül, k katsayıları |
| 2 | IPC-2221 vs IPC-2152 | https://tracewidthcalculator.com/blog/ipc-2221-vs-ipc-2152-pcb-standards | 2.2 sayısal fark, 2.3 doğrulama |
| 3 | PCB Trace Width Guide (Schemalyzer) | https://www.schemalyzer.com/en/blog/pcb-design/basics/pcb-trace-width-guide | 2.3 (çelişkili, işaretlendi) |
| 4 | PCB Clearance and Creepage Distance Table (EMA) | https://www.ema-eda.com/ema-resources/blog/pcb-clearance-and-creepage-distance-table/ | 2.4 Tablo 6-1, 2.5 IEC 62368-1 |
| 5 | PCB Line Spacing, Clearance & Creepage (SF Circuits) | https://www.sfcircuits.com/pcb-school/pcb-line-spacing-clearance-creepage | 2.4 bağımsız doğrulama |
| 6 | Applying IPC-2221 Standards (Sierra Circuits) | https://www.protoexpress.com/blog/ipc-2221-circuit-board-design/ | 2.4 üçüncü kaynak (2 dizgi hatası) |
| 7 | IPC-2221 Calculator for High Voltage (Altium) | https://resources.altium.com/p/using-an-ipc-2221-calculator-for-high-voltage-design | 2.4 500 V üstü hesabı |
| 8 | IPC-2221B Trace Spacing by Voltage (SMPS Power Supply) | https://www.smpspowersupply.com/ipc2221pcbclearance.html | 2.4 B2 500 V üstü formülü |
| 9 | Creepage & Clearance Calculator IEC 60664-1 | https://standardclarity.com/calculators/creepage-clearance/ | 2.5 reinforced=2x kuralı |
| 10 | JLCPCB Capabilities | https://jlcpcb.com/capabilities/pcb-capabilities | 2.6, 2.7, 2.9 |
| 11 | PCBWay Capabilities | https://m.pcbway.com/capabilities.html | 2.6 |
| 12 | OSH Park Two Layer Docs | https://docs.oshpark.com/services/two-layer/ | 2.6, 2.7 |
| 13 | Copper and the Board Edge (Eurocircuits) | https://www.eurocircuits.com/copper-and-the-board-edge/ | 2.7 |
| 14 | PCB Classification (Eurocircuits) | https://www.eurocircuits.com/pcb-classification-drill-class/ | 2.6 IPI kuralı |
| 15 | Tolerances on Copper Thickness (Eurocircuits) | https://www.eurocircuits.com/technical-guidelines/understanding-manufacturing-tolerances-on-a-pcb/tolerances-on-copper-thickness/ | 2.10 |
| 16 | How much finished copper? (NCAB) | https://www.ncabgroup.com/faq/how-much-finished-copper-can-be-expected/ | 2.10 |
| 17 | Placement Courtyard Excess (PCB Libraries) | https://www.pcblibraries.com/forum/placement-courtyard-excess_topic3372.html | 2.8 |
| 18 | IPC-7351 Footprint Standards (Sierra Circuits) | https://www.protoexpress.com/blog/features-of-ipc-7351-standards-to-design-pcb-component-footprint/ | 2.8 Level L/N/M |
| 19 | PCB Hole to Copper Distance (PCBMaster) | https://www.pcbmaster.com/news/pcb-hole-to-copper-distance.html | 2.9 |
| 20 | V-scoring (MADPCB) | https://madpcb.com/v-scoring/ | 2.7 |
| 21 | IPC-2221C (NextPCB) | https://www.nextpcb.com/blog/ipc-2221 | 2.9 etch payı |

## Bulunamayanlar

1. Eurocircuits pattern/drill class sayısal tablosu (yalnızca görsel).
2. Bileşen tipi bazında courtyard excess (standartta yok - teyit edildi).
3. Dalga lehim için bileşenler arası sayısal minimum (EMS'e özgü).
4. Yüksek gerilim için sayısal kart kenarı açıklığı standardı.
5. IPC-2152 ham tablo değerleri (telifli; yalnızca karşılaştırmalı örnekler).
