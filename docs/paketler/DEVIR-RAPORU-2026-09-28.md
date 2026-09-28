# AllCadOtomation — Güncel Devir Raporu

**Tarih:** 2026-09-28
**Dal:** `main`
**Önceki taban:** `e6991db` — BOM kapısı ve devir raporu
**Bu turun amacı:** P0 donanım kararlarını tahmin etmeden makinece izlenebilir bir kabul sözleşmesi eklemek.

## 1. Bu turda yapılan iş

Yeni `pcbqa gereksinim` komutu, G031 profilinin üretime hazır sayılabilmesi
için gerekli kullanıcı kararlarını tek manifestte toplar:

- `input_supply`: giriş beslemesi
- `current_budget`: akım bütçesi ve regülatör sınırı
- `interfaces`: SWD/I2C/USART/LSE seçimi
- `gpio_and_peripherals`: GPIO, ADC, PWM ve timer ihtiyacı
- `mechanical_and_manufacturing`: ölçü, katman, üretici sınırı ve adet
- `temperature_and_package`: sıcaklık sınıfı ve MCU paket tercihi

Örnek manifest bilerek `draft` ve altı karar da `open` durumundadır:

```powershell
pcbqa gereksinim samples\gereksinimler\g031-urun-sozlesmesi.yaml
pcbqa gereksinim samples\gereksinimler\g031-urun-sozlesmesi.yaml --fail-on-open
```

İkinci komutun `1` dönmesi beklenir. Bu hata değil, kullanıcı sözleşmesi
doldurulmadan üretim kabulünün engellendiğine dair kanıttır.

## 2. Kabul kuralları

- `decided` kararın boş olmayan bir `value` alanı olmalı.
- `not_applicable` ve `blocked` kararlar gerekçe olarak `notes` taşımalı.
- Altı zorunlu kararın tamamı manifestte bulunmalı; bilinmeyen/yanlış yazılmış
  karar ID’si reddedilmeli.
- Manifest `accepted` ise açık veya bloklu karar kalamaz.
- Bu dilim hiçbir gerilim, akım, pin veya mekanik değer uydurmaz.

## 3. Doğrulama

- Hedefli gereksinim testleri: 5 test geçti.
- Önceki tam regresyon tabanı: 930 test OK, 50 skipped.
- Bu tur sonrası tam regresyon: **935 test OK, 50 skipped**.

## 4. Kullanıcıdan beklenen sonraki kararlar

Başka AI veya geliştirici şu altı alanı kullanıcıdan netleştirmeden G031 BOM’unu
`accepted` yapmamalı:

1. Giriş beslemesi ve gerilim aralığı.
2. Maksimum akım ve LDO ısıl sınırı.
3. SWD dışında gerekli arayüzler.
4. GPIO/ADC/PWM/timer bütçesi.
5. Kart ölçüsü, katman, üretici minimumları ve hedef adet.
6. Sıcaklık sınıfı ve MCU paket alternatifi.

Bu cevaplar geldikten sonra sıradaki teknik iş, G031 SWD + seçilen çevre
birimleri niyetini üretmek, KiCad netlist/ERC kapısından geçirmek ve BOM’daki
`needs_selection` kalemlerini gerçek kaynak/MPN ile kapatmaktır.

## 5. Devir kuralları

- Kullanıcının elektriksel gereksinimlerini tahmin etme.
- Kaynaksız MPN, üretici, fiyat veya stok yazma.
- `accepted` yalnızca altı karar kapandıktan sonra kullanılmalı.
- KiCad dosyasına yazmadan önce dry-run/netlist/backup kapılarını koru.
- Push öncesi tam regresyon ve `git diff --check` çalıştır.
