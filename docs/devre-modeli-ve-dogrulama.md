# Ortak devre modeli ve üç seviyeli doğrulama

Bu belge, `pcbqa devre` ve `pcbqa dogrula` komutlarının arkasındaki yapıyı
anlatır. Beads kaydı: **Kicad-5d6** (alt işler .1–.8).

## 1. Devre grafı (`pcbqa/devre/`)

Okuyucular eskiden tek tek soru cevaplıyordu: netlist "neye bağlı", kart
"nerede", şematik "hangi alanlar". Devre grafı bunları, parça bilgisini ve
çalışma koşullarını **tek yapıda** birleştirir:

```
R1 [4k7] 1:3V3, 2:SDA | pull-up | 0.1 W (paket-tipik) | kartta (44.00, 40.00) F.Cu
```

| Katman | Dosya | Ne taşır |
|---|---|---|
| Bilgi/eksik | `devre/bilgi.py` | Her değer kaynağıyla **ya da** neden bilinmediğiyle |
| Parça bilgisi | `devre/parca.py` | Değer, tolerans, üretici, MPN, pin işlevleri, önerilen + mutlak sınırlar, termal, SOA, SPICE modeli + kaynağı + pin eşlemesi, sıcaklık katsayısı, yaşlanma |
| Parça kütüphanesi | `data/parcalar/temel.yaml` | Kaynaklı kayıtlar (AMS1117, 78xx, STM32G031, 2N7002, AO3400A, 1N4007, 1N5819, SMBJ, genel direnç/kondansatör) |
| Graf | `devre/graf.py` | Bileşen → pin → ağ; her birinin PCB karşılığı |
| Roller | `devre/roller.py` | Regülatör, dekuplaj, pull-up, bölücü, LED direnci, MOSFET anahtar, endüktif yük, serbest geçiş diyotu, sigorta, TVS, güç girişi, programlama |
| Koşullar | `devre/kosullar.py` | Ray gerilimleri, kaynaklar, yükler, gereksinimler, PCB parametreleri |

**Bilgi kaynak sırası:** sembol alanları (MPN, Manufacturer, Tolerance,
Voltage, Power, Current) → MPN ile tam eşleşen kütüphane kaydı → değer /
sembol adı deseni → genel paket kaydı → **eksik** (nedeniyle).

**Güven seviyeleri:** `parcaya-ozel`, `beyan`, `turetilmis`, `paket-tipik`,
`dogrulanmamis`, `sentetik`. Kütüphanedeki kayıtların çoğu
`dogrulanmamis`: veri sayfasından elle aktarıldı, sayfa numarasıyla teyit
edilmedi. Üretim kararından önce teyit edin.

**Ağ gerilimi sırası:** koşullar beyanı → regülatör çıkışı (parça bilgisi)
→ ağ adı (`+3V3`, `5V`) → eksik. `VCC`, `VDD` gibi adlar gerilim
**söylemez**.

## 2. Doğrulama seviyeleri (`pcbqa/dogrulama/`)

| Seviye | Dosya | Ne yapar |
|---|---|---|
| 1 | `seviye1.py` | `kicad-cli` ile ERC, PCB DRC + **şematik paritesi**, netlist dışa aktarımı |
| 2 | `seviye2.py` | Giriş pinine aşırı gerilim; regülatör giriş/çıkış/yük/kayıp/Tj; MOSFET gate sürme; pull-up / dekuplaj / regülatör kondansatörü / endüktif yük koruması; direnç gücü ve kondansatör gerilimi |
| 3 | `seviye3.py` + `pcbqa/spice/` | ngspice benzetimi: netlist, test koşulları, çalıştırma, okuma, gereksinimle karşılaştırma |

Seviye 2 kuralları **parçaya** (sınırlar) ve **amaca** (roller + koşullar)
bağlıdır. Gerekli bilgi yoksa kural sessizce geçmez, "denetlenemedi" bulgusu
bırakır.

### Seviye 3: ngspice

- **Yan uygulama:** KiCad 10 kendi `ngspice.dll`'ini (ngspice-46) getiriyor.
  pcbqa bu kütüphaneyi **ayrı bir süreçte** (`spice/isci.py`) yükler.
  ngspice çökerse ana uygulama etkilenmez, zaman aşımıyla kesilir.
  `PCBQA_NGSPICE` ile konsol programı da verilebilir.
- **Lisans:** ngspice'in ana lisansı değiştirilmiş (3 maddeli) BSD'dir.
  pcbqa ngspice'i **dağıtmaz**, kullanıcının KiCad kurulumundakini çağırır.
  MATLAB benzeri bir araç (GNU Octave, GPL-3) eklenmedi; son işlemeyi
  Python zaten yapıyor ve ek bağımlılık gerekmiyor.
- **Senaryolar:**
  - `nominal`
  - giriş köşeleri (`giris-min`, `giris-max`)
  - `tepe-yuk`
  - tolerans köşeleri (`tolerans+/-`) ve Monte Carlo (sabit tohum)
  - sıcaklık (TCR sınırıyla ± yönde)
  - yaşlanma (veri sayfası ömür testi sapması; **daha uzun süreye
    ekstrapolasyon yapılmaz**)
  - `termal-en-kotu` (en yüksek giriş + en sıcak ortam + sürekli yük)
- **Modeller:**
  - Pasifler SPICE'ın kendi elemanlarıyla girer.
  - LDO **davranışsal/ideal** modelle girer ve raporda öyle yazar.
  - MOSFET, MCU ve diğer entegreler atlanır; atlanan her parça nedeniyle
    kaydedilir.

**Örnek (kullanıcının verdiği):** varsayımsal bir LDO 12 V'u 3,3 V'a indirip
300 mA verirse:
- Benzetim 3V3'ü gereksinim içinde bulur.
- Kayıp (12,6 − 3,3) × 0,3 = **2,79 W** olur.
- SOT-223'te θJA ≈ 135 °C/W ile Tj yüzlerce °C'ye çıkar.

ERC bu durumu göremez; benzetim kaybı ölçer, termal model Tj'yi verir.

> **SPICE geliştirilmeli (Kicad-5d6.5):** MOSFET, regülatör ve diğer
> entegreler için üretici SPICE modelleri gerekli. Her model kaynağı,
> lisansı ve sembol pin eşlemesiyle eklenmeli. Geçici (transient) analiz,
> kondansatör/bobin etkileri ve DC bias da bu işin kapsamında.

## 3. PCB: önce yerleşim ve kısıtlar (`pcbqa/pcb_akim.py`)

**Yönlendirmeden önce** `yonlendirme_girdisi()` çalışır. Sıra şöyledir:

1. **Yerleşim kısıtları:** dekuplaj ve regülatör kondansatörü → hedef pin
   mesafesi (TI SBAA113, 6,35 mm).
2. **Üretim sınırları:** üretici profili (iz, açıklık, delik, halka, kenar).
3. **Dal akımları:**
   - Kaynak pinden başlayan Manhattan ağacı kurulur.
   - Her kenar, altındaki yüklerin **toplamını** taşır.
   - Her kenar için IPC-2221B genişliği ve izin verilen düşüme göre azami
     uzunluk hesaplanır.

**Yönlendirmeden sonra** `iz_analizi()` çalışır:

- Ağın bakırı (iz parçaları, vialar, padler) bir direnç ağına çevrilir.
- Kirchhoff düğüm analiziyle her parçanın gerçek akımı çözülür.
- **Bir ağa tek akım atanmaz:** ana kol toplamı taşır, dallar kendi yükünü.

```
R = ρ·L / (w·t)      ΔV = I·R      P = I²·R
```

Kullanılan girdiler:
- sürekli/RMS akım, tepe akım ve darbe süresi (Onderdonk)
- bakır kalınlığı, iç/dış katman, izin verilen sıcaklık artışı
- yol uzunluğu ve izin verilen gerilim düşümü
- pad çıkışları, darboğazlar, vialar (TI SLVA959B) ve konnektör pin sınırı

## 4. Dokuz kontrol (`dogrulama/kontroller.py`)

| Kontrol | Amaç |
|---|---|
| Şematik–PCB bağlantı eşleşmesi | PCB'nin hedef devreyle aynı bağlantıları taşıması |
| Sembol–footprint–model pin eşleşmesi | Pin numarası veya model bağlantısı hatalarını bulmak |
| Bileşen yüklenmesi | Güç, gerilim, akım ve çalışma sınırları |
| Termal değerlendirme | Regülatör Tj ve bakır ısınması |
| Koruma koordinasyonu | Sigorta / TVS ile korunan parçanın uyumu |
| Dönüş yolu ve kritik döngüler | Toprak düzlemi kapsaması, dekuplaj döngüsü, dönüş bağlantısı |
| Üretilebilirlik | Üreticinin iz, boşluk, delik, halka ve kenar sınırları |
| Mekanik ve montaj | Kart sınırı, montaj delikleri, konnektör erişimi, çakışmalar |
| Test edilebilirlik | Ölçüm noktaları ve programlama bağlantıları |

Durumlar `gecti`, `uyari`, `kaldi`, `kismen` ve `denetlenemedi`'dir.
**`kismen` ve `denetlenemedi` "geçti" demek değildir**; nedeni raporda yazar.

## 5. ML bağlantısı (`pcbqa/ml/devre_veri.py`)

`pcbqa dogrula ... --veri devre.jsonl` her koşuyu `ml/dataset.py` biçiminde
(grup = proje) bir örnek olarak ekler. Öznitelikler:

- graf özeti (gerilimi/rolü bilinen oranı, eksik bilgi ortalaması, sentetik
  ve doğrulanmamış kaynak oranı)
- seviye hata sayıları
- LDO kaybı ve Tj marjı
- gerilim marjı
- iz kaybı
- kontrol durumları ve yerleşim kısıtı ihlali

Etiket seçenekleri `gecti`, `tj_marj` ve `hata_sayisi`'dır. Ölçülemeyen
öznitelik sıfırla gizlenmez; ayrı bir `_var` bayrağı taşır.

## Kullanım

```bat
pcbqa devre   <proje> [--kosullar k.yaml] [--ref U1] [--json graf.json]
pcbqa dogrula <proje> --kosullar k.yaml [--seviye 1,2,3] [--ayrinti]
              [--json rapor.json] [--graf-json graf.json] [--veri devre.jsonl]
```

Örnek koşullar dosyası:

```yaml
version: 1
ortam_c: 40
raylar:
  VBUS: {nom: 12, min: 11.4, max: 12.6}
kaynaklar: [VBUS]
yukler:
  - {ag: 3V3, akim_a: 0.3, tepe_a: 0.45, darbe_s: 0.002, ref: U2, pin: "1"}
gereksinimler:
  - {ag: 3V3, min_v: 3.2, max_v: 3.4}
pcb:
  izin_dV_yuzde: 2
  uretici: standart
analiz:
  monte_carlo: 30
  sicakliklar: [-40, 85]
  yaslanma_saat: 50000
```

## Mühendislik seçimleri (kaynaksız, ayarlanabilir sabitler)

| Sabit | Değer | Yer |
|---|---|---|
| CMOS giriş payı | VDD + 0,3 V (pin sınırı yoksa; 5 V toleranslı pinde yanlış alarm verebilir) | `seviye2.py` |
| Kondansatör gerilim oranı | %80 | `seviye2.py` |
| Direnç güç oranı | %50 | `seviye2.py` |
| Dekuplaj/toplu ayrımı | 1 µF | `roller.py` |
| Sıcaklık köşeleri (beyan yoksa) | −40 / 85 °C | `seviye3.py` |
| Darbe payı | Onderdonk erime akımının %50'si | `pcb_akim.py` |
| Konnektör kenar mesafesi | 5 mm | `kontroller.py` |
| Toprak düzlemi kapsama | %50 | `kontroller.py` |
| Dekuplaj döngüsü | 2 × 6,35 mm | `kontroller.py` |
