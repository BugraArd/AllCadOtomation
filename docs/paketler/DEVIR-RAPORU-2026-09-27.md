# AllCadOtomation — Güncel Devir Raporu

**Tarih:** 2026-09-27
**Dal:** `main`
**Son bilinen taban:** Paket 02 ilk STM32G0 profili
**Amaç:** Başka bir AI’ın bu dosyayı okuyup projeyi tekrar keşfetmeden sürdürmesi.

## 1. Mevcut durum

- Paket 01 pushlandı: `78610a5` — bulgu/düzeltme/doğrulama çekirdeği.
- Paket 02 ilk dilimi pushlandı: `0d07694` — `STM32G031K8T6` LQFP-32 profili.
- Bu çalışma turunda P02-03 için provenance-aware BOM kapısı eklendi ve bu raporla birlikte commit/pushlandı.
- KiCad 10.0.6, Python 3.13.15 ve proje sanal ortamı çalışıyor.
- Güncel tam regresyon: **930 test OK, 50 skipped**.
- Çalışma ağacı push sonrasında temiz olmalıdır; doğrulama komutu aşağıda verilmiştir.

## 2. Bu turda yapılan iş

Yeni `pcbqa bom` komutu, MPN/fiyat/stok uydurmak yerine BOM kalemlerinin kaynağını zorunlu kılar.

```powershell
pcbqa bom samples\bom\g031-asgari.yaml
pcbqa bom samples\bom\g031-asgari.yaml --fail-on-open
```

Manifest kalem durumları:

- `verified`: MPN + üretici + kaynak zorunlu.
- `needs_selection`: değer/footprint bilinir, gerçek üretici/MPN seçilmemiştir.
- `blocked`: dış karar veya veri bekler.
- `synthetic`: test amaçlıdır, üretim kabulü değildir.

Mevcut G031 manifestinde yalnızca `STM32G031K8T6` doğrulanmıştır. 100 nF,
4.7 uF, NRST kondansatörü, LDO ve güç header’ı açık kalemdir. Bu bilerek
uygulanmıştır; sahte fiyat veya stok yazılmayacaktır.

## 3. Kritik donanım kararı

İlk MCU profili:

- Parça: `STM32G031K8T6`
- KiCad sembolü: `MCU_ST_STM32G0:STM32G031K8Tx`
- Footprint: `Package_QFP:LQFP-32_7x7mm_P0.8mm`
- Profil: `pcbqa/pcbqa/templates/mcu-stm32g031k8.yaml`
- Örnek niyet: `pcbqa/samples/niyetler/g031-asgari.yaml`

Bilinçli sınırlar:

- LQFP-32 profili USB/HSE varsaymaz.
- PA14, SWCLK/BOOT0 çoklaması nedeniyle otomatik BOOT0 pulldown yoktur.
- AMS1117-3.3 yalnızca mevcut örnek altyapıyla uyumluluk placeholder’ıdır.
- Üretilen PCB yönlendirilmez.
- Gerçek ürün BOM’u, stok, sıcaklık sınıfı ve elektriksel gereksinimler henüz kilitli değildir.

## 4. Sonraki işler — öncelik sırasıyla

### P0 — Kullanıcıdan alınması gereken elektriksel sözleşme

Kod yazmadan önce şu kararlar netleştirilmeli:

1. Giriş beslemesi: 5 V header mı, USB mi, başka aralık mı?
2. Maksimum giriş/çıkış akımı ve regülatör ısıl sınırı.
3. Gerekli çevre birimleri: SWD zorunlu; I2C/USART/LSE gerçekten gerekiyor mu?
4. GPIO sayısı, ADC/PWM/timer ihtiyacı ve pin çakışma öncelikleri.
5. Ürün mekanik sınırı, kart katman sayısı, üretici minimumları ve hedef adet.
6. Çalışma sıcaklığı/sınıfı ve MCU paket alternatifi.

Bu cevaplar gelmeden AMS1117, pasif MPN veya connector seçimi üretim kararı
olarak işaretlenmemeli.

### P0 — BOM/sourcing’i gerçek veriye bağlama

- Önce kullanıcı ülkesini ve tercih edilen distributorleri belirle.
- MCU için T6/T3/T7 ve TR/tepsi farkını stok/sıcaklık sınıfıyla doğrula.
- Pasifler için üretici, dielektrik, gerilim, tolerans, paket ve MPN seç.
- LDO’yu akım/ısı/giriş aralığına göre yeniden seç; AMS1117’yi varsayılan
  üretim parçası kabul etme.
- `g031-asgari.yaml` içindeki `needs_selection` kalemlerini yalnızca kaynak
  URL’si ve MPN doğrulandıktan sonra `verified` yap.

### P0 — G031 elektriksel kabul

- SWD header’lı bir G031 niyeti ekle.
- Kullanıcı isterse I2C1 veya USART2 bloklarını ekle; pin çakışmasını test et.
- LSE istenirse ayrı LSE kristal bloğu ekle; mevcut `crystal-hse` bloğunu
  G031 LQFP-32 ile kullanma.
- Geçici proje üret, KiCad netlist/ERC kapısını çalıştır.
- Gerçek/routed kullanıcı PCB’si gelmeden `P01-06` tamamlandı denmemeli.

### P1 — Ürünleşme

- P01-07 kart kenarı/courtyard düzeltme önerileri.
- P01-08 skor ile “üretime hazır” durumunu ayıran açık kabul raporu.
- Lisans, kök README, kurulum paketi ve CI.
- KiCad içi plugin/panel deneyimi.

### P2 — Şimdilik dokunma

- PyTorch/CUDA/ML modeli.
- Otomatik routing.
- Serbest LLM ile CAD dosyası yazma.

## 5. Doğrulama komutları

`pcbqa` klasöründe çalıştır:

```powershell
$env:PCBQA_KICAD_CLI='C:\Users\ismai\AppData\Local\Programs\KiCad\10.0\bin\kicad-cli.exe'
$env:KICAD10_SYMBOL_DIR='C:\Users\ismai\AppData\Local\Programs\KiCad\10.0\share\kicad\symbols'
$env:KICAD10_FOOTPRINT_DIR='C:\Users\ismai\AppData\Local\Programs\KiCad\10.0\share\kicad\footprints'
$env:KICAD10_3DMODEL_DIR='C:\Users\ismai\AppData\Local\Programs\KiCad\10.0\share\kicad\3dmodels'

\.venv\Scripts\python.exe -m pcbqa.bundle --check
\.venv\Scripts\python.exe -m unittest discover -s tests
pcbqa bom samples\bom\g031-asgari.yaml
pcbqa bom samples\bom\g031-asgari.yaml --fail-on-open  # 1 beklenir
```

## 6. Devir kuralları

- Kullanıcının elektriksel gereksinimlerini tahmin etme.
- Kaynaksız MPN, üretici, fiyat veya stok yazma.
- `verified` yalnızca gerçek kaynak ve MPN ile kullanılmalı.
- KiCad dosyasına yazmadan önce dry-run/netlist/backup kapılarını koru.
- Her anlamlı paketi ayrı commit yap; commit gövdesine kapsam, test ve açıkları yaz.
- Push öncesi `git status --short --branch` ve `git diff --check` çalıştır.
