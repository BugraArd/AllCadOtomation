# Devre tipine göre PCB tasarım kuralları — kaynaklı derleme

Bu dizin, "bir buck converter'ın güç izi kaç mm olmalı?" gibi soruların
**üretici app-note'larından ve standartlardan toplanmış** sayısal cevaplarını
tutar. Amaç, kural motorundaki eşiklerin nereden geldiğinin izlenebilir olması.

| Dosya | Kapsam |
|---|---|
| [01-anahtarlamali-guc.md](01-anahtarlamali-guc.md) | Buck / boost / buck-boost: CIN mesafesi, sıcak döngü, SW alanı, FB, bootstrap, via akımı, frekans etkisi, termal ped |
| [02-uretilebilirlik-ipc.md](02-uretilebilirlik-ipc.md) | IPC-2221B iz genişliği ve açıklık tabloları, IEC creepage, fab minimumları, courtyard, bakır kalınlığı |
| [03-yuksek-hiz-sinyal.md](03-yuksek-hiz-sinyal.md) | Decoupling (λ/40), kristal, USB, Ethernet, PCIe/HDMI, DDR3, 3W/20H, I2C/SPI, ADC, RF |
| [04-lineer-motor-koruma.md](04-lineer-motor-koruma.md) | LDO, termal bakır alanı, motor sürücü, ESD/TVS, konnektör, sensör, mains izolasyon, elektrolitik/kristal mekanik |

Toplam ~90 kaynak; büyük çoğunluğu birincil (üretici app-note'u veya standart).
İkincil (blog/DFM) olanlar **İKİNCİL** diye işaretlendi.

## En önemli bulgu: çoğu tavsiyenin sayısı yok

Araştırmanın asıl sonucu bir tablo değil, bir gözlem:

> **Birinci sınıf kaynakların çoğu mm cinsinden sayı vermez.** TI, ADI, Richtek,
> ST, Microchip, NXP, Bosch, Sensirion — hepsi "as close as possible",
> "as short as practical", "reasonable distance" der.

Bosch bunu açıkça gerekçelendiriyor: *"a 'reasonable distance' depends on many
customer specific variables and must therefore be [determined by the
customer]"*.

Sayısal kriter veren birkaç kaynak bu yüzden orantısız ağırlık taşıyor:

| Kaynak | Neden önemli |
|---|---|
| **ROHM 66AN015E** | Anahtarlamalı regülatör için sistematik sayısal kontrol listesi — bu alanda tek örneği |
| **TI SLVA959B** | Bypass < 5 mm, gate izi 0.508 mm, via akım tablosu |
| **TI SNOA986A** | Sıcaklık sensörü: bypass ≤ 5 mm, pull-up ≥ 10 mm |
| **TI AN-2155 (SNVA638A)** | Sıcak döngü alanının EMI'ye etkisinin **ölçülmüş** verisi |
| **IPC-2221B / IPC-7351B** | İz genişliği, açıklık, courtyard — formülü açık standartlar |

Bu yüzden `pcbqa/presets/` altındaki eşiklerin her birinin yanında kaynağı
yazılı, ve kaynağı olmayanlar ("mühendislik seçimi") açıkça öyle etiketli.

## Kaynaklar birbiriyle çelişiyor — çelişkiler gizlenmedi

Derlemede saklanmayan başlıca çelişkiler:

| Konu | Çelişki | Karar |
|---|---|---|
| USB 2.0 intra-pair tolerans | TI'ın 4 dokümanı 2 / 50 / 100 / 150 mil diyor — **75 kat** yayılım, biri kendi içinde tutarsız | 50 mil (UI'nin %0.4'ü) |
| İz genişliği yöntemi | 3 A için ROHM 3.00 mm · IPC-2152 2.10 mm · IPC-2221/10 °C 1.37 mm · IPC-2221/20 °C 0.90 mm — **3.3 kat** | Yöntem seçilebilir (`method:`) |
| IPC-2152 daha mı gevşek? | Çıplak temel eğrisi IPC-2221'den **daha muhafazakâr**; gevşeme ancak düzlem çarpanlarıyla geliyor | IPC-2221B, ΔT parametre |
| Via akım kapasitesi | 0.30 mm delik: TI 0.84 A · IPC-2221 namlu hesabı 1.45–1.69 A — **2 kat** | TI (muhafazakâr) |
| 3W mu 5W mu | Endüstri folkloru 3W; TI'ın tüm yüksek hızlı dokümanları **5W** | 5W |
| 20H kuralı | Montrose (1996) öneriyor; **Shim & Hubing (IEEE EMC 2001) ölçümle radyasyonun hafifçe ARTTIĞINI gösterdi** | Genel EMI kuralı olarak kullanma |
| 230 V creepage | IEC 62368-1 tablosu 2.5/5.0 mm; sahada dolaşan 3.2/6.4 mm | Tablo değeri; ürün için uzmana teyit |
| Elektrolitik vent boşluğu | Nichicon 2 mm; bloglar 4 mm | Üretici datasheet'i |

## Kural motoruna nasıl bağlanıyor

Araştırmadan çıkan eşikler `pcbqa/presets/` altındaki dört YAML'da:

```yaml
# kendi rules.yaml dosyanızda
include:
  - presets/uretim.rules.yaml      # her tasarımda geçerli
  - presets/buck.rules.yaml        # tasarımda buck converter varsa
rules:
  - id: kendi-kuralim
    ...
```

| Ön ayar | İçerik | Uyarlama gerekir mi? |
|---|---|---|
| `uretim.rules.yaml` | courtyard, kart kenarı, fab min. iz, gerilim açıklığı | Hayır — devre tipinden bağımsız |
| `buck.rules.yaml` | CIN/SW/FB/COUT mesafeleri, güç izi genişliği, via sayısı | **Evet** — ref/net desenleri ve `current_a` |
| `lineer-koruma.rules.yaml` | LDO, motor sürücü, ESD/TVS, sensör | **Evet** — ref desenleri |
| `yuksek-hiz.rules.yaml` | decoupling, kristal, I2C, diferansiyel çiftler | **Evet** — net adları |

`uretim` ön ayarı, sağlam bir gerçek kartta (KiCad'in `pic_programmer` demosu)
**sıfır bulgu** üretir; bu bir testle korunuyor (`tests/test_presets.py`).

### Ağırlıklar — kanıt gücüne göre

Her ön ayar kuralı bir `weight` taşır: o kuralın bulgusunun skora yazacağı ceza.
Değeri **kanıtın gücü** belirler, kuralın ne kadar "ciddi hissettirdiği" değil.

| Kanıt sınıfı | Bant | Örnek |
|---|---|---|
| **Güvenlik** | 24 | `uretim-gerilim-acikligi` (IPC-2221B Tablo 6-1) |
| **Ölçülmüş etki** | 16–20 | `buck-giris-kondansatoru` — TI AN-2155: sıcak döngü 6→18 mm²'de SW spike 2.4×, EMI marjı −1.6 dB |
| **Standart / sayısal app-note** | 8–16 | `buck-sw-induktor` (ROHM 66AN015E Öncelik 2), `sensor-pullup-uzak-dursun` (TI SNOA986A) |
| **Kaynaklı ama nitel** | 4–8 | `ldo-giris-kondansatoru` — LDO app-note'ları mm **vermiyor**; 5 mm TI'ın genel bypass kuralından |
| **Mühendislik seçimi** | 1–2 | `hs-kristal-regulatorden-uzak` — kaynakta sayı **yok** |

İki ayarın gerekçesi ayrıca not edilmeli:

- `hs-usb-cift-eslestirme` **8** aldı, 12 değil: TI'ın dört dokümanı bu eşik için
  **75 kat** farklı değer veriyor (2 / 50 / 100 / 150 mil) ve biri kendi içinde
  tutarsız. Belirsizlik ağırlığı düşürür.
- `esd-tvs-konnektore-yakin` **14** aldı: *önemi* ölçülmüş (ROHM 66AN067E —
  52 nH'lik bir iz TVS'i tamamen işlevsiz bırakıyor, ilk tepe 3.4 kV yerine
  107 V olmalıydı) ama *eşiği* ikincil kaynaktan. Önem yukarı, eşik belirsizliği
  aşağı çekiyor.

### Ölçekleme — yalnızca formül varsa

`scale: true` yalnızca altı kuralda açık: `buck-guc-izi-genisligi`,
`buck-guc-via-sayisi`, `motor-gate-izi-genisligi`, `motor-guc-izi`,
`uretim-gerilim-acikligi`, `uretim-min-iz-genisligi`.

Ortak yanları: hepsinin kaynağı **sürekli bir ilişki** (IPC-2221B formülü, TI'ın
via akım tablosu). Orada "iki kat dar" fiziksel olarak anlamlıdır.

Mesafe kurallarında ölçekleme **kapalı**, çünkü kaynaklar bir *eşik* veriyor,
bir *eğri* değil: TI decoupling için 6.35 mm der ama 12.7 mm'nin tam iki kat
kötü olduğunu **söylemez**. Ölçeklemek uydurma olurdu. Bu ayrım testle
korunuyor (`test_scaling_only_where_the_source_is_a_formula`).

### Eklenen kural tipleri

| Tip | Ne ölçer | Kaynak |
|---|---|---|
| `trace_width` | İz genişliği ≥ akımın gerektirdiği (IPC-2221B veya ROHM mm/A) | 02 §2.1, 01 §1.7 |
| `via_current` | Netteki via'ların toplam akım kapasitesi | 01 §1.8 (TI SLVA959B) |
| `clearance_voltage` | İki net arası bakır açıklığı ≥ gerilim farkının gerektirdiği | 02 §2.4 (IPC-2221B Tablo 6-1) |
| `keep_apart` | İki bileşen kümesi arası **minimum** mesafe | 01 §1.4, 04 §4.0 |

`keep_apart`, araştırmanın ortaya çıkardığı bir boşluğu kapatıyor: kaynaklardaki
kuralların şaşırtıcı bir kısmı "yaklaştır" değil **"uzaklaştır"** diyor —
FB izi → indüktör ≥ 10 mm, I2C pull-up → sıcaklık sensörü ≥ 10 mm,
CIN GND ↔ COUT GND ≥ 10 mm. Yalnızca mesafe küçültmeye çalışan bir yerleştirici
bunları sessizce ihlal eder.

## Ölçülemeyenler

Sayısal değeri araştırmada **bulunan** ama mevcut veri modeliyle
**ölçülemeyen** kurallar. Her ön ayar dosyasının sonunda kendi listesi var;
ortak eksik şu:

| Gereken veri | Açtığı kurallar |
|---|---|
| **Bakır döküm (zone) okuma** | Sıcak döngü alanı (6 mm² iyi / 18 mm² kötü), SW bakır alanı ≤ 100 mm², indüktör altında bakır olmaması, termal bakır alanı (1 W → ~20 cm²), referans düzlem sürekliliği |
| **İz topolojisi analizi** | Stub uzunluğu, ESD izi endüktansı (52 nH → TVS işlevsiz), Kelvin bağlantı, fly-by sırası |
| **Katman yığını (stackup)** | Via stub / backdrill, iç/dış katman gerçek bakır kalınlığı, empedans |
| **3B / yükseklik** | Elektrolitik vent boşluğu, konnektör keep-out, muhafaza açıklığı |
| **Kart kesikleri (iç Edge.Cuts)** | Creepage slot genişliği (PD1 0.25 / PD2 1.0 / PD3 1.5 mm), termal izolasyon yarığı |

Bunlardan **zone okuma** en yüksek getirili olan: tek başına anahtarlamalı
güç kaynaklarının en kritik üç kuralını (sıcak döngü, SW alanı, termal bakır)
ölçülebilir hale getirir.

## Kapsam uyarısı

- `clearance_voltage` **clearance** (hava aralığı) ölçer, **creepage değil.**
  Şebeke izolasyonu için yetmez; kural 250 V üstünde bulguya uyarı koyar ama
  yüzey mesafesini hesaplamaz.
- İz genişliği hesabı **nominal** bakır kalınlığı kullanır. Gerçekte iç katman
  1 oz ≈ 25 µm (nominalin %71'i), dış katman ≈ 48–60 µm (kaplama ekler). İç
  katman güç izlerinde hesap **~%25 iyimser**.
- Bu derleme mühendislik kararının yerine geçmez; özellikle **güvenlik
  (mains izolasyon, creepage)** konularında ürün standardınıza ve bir uzmana
  başvurun.
