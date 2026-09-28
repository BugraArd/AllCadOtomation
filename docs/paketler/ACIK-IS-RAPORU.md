# Açık İş Raporu

**Son güncelleme:** 2026-09-28
**Aktif paket:** Paket 02 — STM32G0 ilk üretim profili
**Durum:** İlk STM32G0 dikey dilimi uygulandı; elektriksel kabul ve sourcing açık

## Mevcut doğrulanmış taban

- KiCad 10.0.6 ve Python ortamı kuruldu.
- `pcbqa tani` kütüphane ve canlı PCB ortamını doğruluyor.
- 935 test başarılı, 50 test isteğe bağlı demo eksikliği nedeniyle atlanıyor.
- Gerçek PCB üzerinde canlı IPC bağlantısı doğrulandı; 63 bileşenli kart okundu.
- Paket başlamadan önce Git çalışma ağacı temizdi; bu teslimatın değişiklikleri tek mantıksal commit olarak gönderilecek.
- KiCad proje dosyaları kaynak gerçeklik olarak korunuyor.

## Açık işler

| ID | Öncelik | İş | Durum | Paket |
|---|---:|---|---|---|
| P01-01 | P0 | `Finding` ortak veri modeli | Tamamlandı | 01 |
| P01-02 | P0 | `FixProposal` ve ön koşul sözleşmesi | Tamamlandı | 01 |
| P01-03 | P0 | Decoupling mesafesi için ilk otomatik düzeltme | Tamamlandı | 01 |
| P01-04 | P0 | Dry-run, diff, yedek ve tekrar doğrulama | Tamamlandı | 01 |
| P01-05 | P0 | CLI ve GUI bulgu/onay akışı | Tamamlandı | 01 |
| P01-06 | P0 | Gerçek STM32 kartı uçtan uca kabul testi | Açık — örnek kart testi tamam, STM32 testi bekliyor | 01 |
| P01-07 | P1 | Kart kenarı ve courtyard önerileri | Bekliyor | 01 |
| P01-08 | P1 | Skoru üretime hazır olma durumundan ayırma | Bekliyor | 01 |
| P02-01 | P0 | İlk STM32G0 parçası ve paketinin seçilmesi | İlk aday seçildi: STM32G031K8T6 / LQFP-32; stok ve sıcaklık sınıfı açık | 02 |
| P02-02 | P0 | STM32G0 şablon ve üretim profili | İlk dilim tamam; elektriksel kabul açık | 02 |
| P02-03 | P1 | Gerçek MPN/BOM veri kaynağı | İlk provenance kapısı tamam; canlı stok/fiyat entegrasyonu açık | 02 |
| P02-04 | P0 | Kullanıcı donanım gereksinim sözleşmesi | Açık karar kapısı eklendi; kullanıcı değerleri bekleniyor | 02 |
| P03-01 | P1 | Lisans, kök README, kurulum paketi ve CI | Planlandı | 03 |
| P03-02 | P1 | KiCad içi daha doğal panel/plugin deneyimi | Planlandı | 03 |
| P04-01 | P2 | Kabul edilmiş düzeltmelerden öğrenme verisi | Ertelendi | 04 |
| P04-02 | P2 | ML/LLM ile düzeltme adaylarını sıralama | Ertelendi | 04 |
| P05-01 | P2 | Routing entegrasyonu | Karar bekliyor | 05 |

## Bilinen ürün sınırları

- Otomatik routing yok.
- Stabil KiCad 9/10 üzerinde canlı şematik yazma yok.
- Doğal dil desteği sınırlı, deterministik bir komut sözlüğüdür.
- MPN ve fiyat verileri üretim/pazar verisi değildir.
- ML altyapısı vardır ancak üretim yerleşiminde kanıtlanmış uçtan uca kazanç yoktur.
- STM32G0 için ilk G031K8T6 profili var; gerçek BOM/sourcing ve kullanıcı elektriksel gereksinimleri henüz kilitli değildir.
- `bom` manifesti artık doğrulanmış MPN ile seçilmemiş/sentetik kalemleri ayırır; canlı distributor stok/fiyat entegrasyonu yoktur.
- `gereksinim` manifesti artık besleme, akım, arayüz, GPIO, mekanik/üretim ve sıcaklık/paket kararlarını açıkça izler; örnek sözleşme henüz `draft`tır.

## Paket tamamlanınca rapora eklenecek kanıtlar

- Çalıştırılan komutlar
- Test sayısı ve sonucu
- Kabul kartının yolu ve lisans durumu
- Önce/sonra bulgu sayıları
- Netlist/ ERC/DRC doğrulama çıktıları
- Yedekleme ve geri alma sonucu
- Bilinen başarısızlıklar ve sonraki paket ID'leri

## Paket 01 teslimat kanıtı

- `pcbqa duzelt <proje> --liste` ile kararlı finding ID ve ölçülebilir kanıt çıktısı.
- `--finding <id>` varsayılan olarak dry-run üretir; dosyaya dokunmaz.
- Bakır/via/zone içeren yönlendirilmiş kartlarda otomatik dosya yazımı güvenlik nedeniyle reddedilir.
- `bench_bad.kicad_pcb` üzerinde decoupling bulgusu kapatıldı, yedek oluşturuldu ve netlist paritesi korundu.
- Paket 01 sonrası uçtan uca regresyon: `Ran 927 tests ... OK (skipped=50)`.
- BOM provenance kapısı sonrası güncel uçtan uca regresyon: `Ran 930 tests ... OK (skipped=50)`.
- Gereksinim sözleşmesi sonrası güncel uçtan uca regresyon: `Ran 935 tests ... OK (skipped=50)`.
- Uygulama sonrası örnek kartta başka bulgular kaldığı için genel sonuç kodu `1` dönebilir; hedef bulgunun kapanması ve netlist paritesi ayrı doğrulama kapılarıdır.

## Paket 02 ilk dilim kanıtı

- KiCad sembolü `MCU_ST_STM32G0:STM32G031K8Tx` çözüldü.
- `Package_QFP:LQFP-32_7x7mm_P0.8mm` footprint’i çözüldü.
- `g031-asgari.yaml` geçici KiCad projesi üretti; 4 planlanan ağın tamamı KiCad netlist’inde doğrulandı.
- G031 profili bilinçli olarak USB/HSE üretmiyor; PA14/SWCLK ile BOOT0 çoklaması nedeniyle otomatik BOOT0 pulldown eklemiyor.
- Paket 02’ye özel 3 sözleşme testi ve runtime JSON ayrışma kontrolü geçti.
- `pcbqa bom samples\\bom\\g031-asgari.yaml --fail-on-open` üretim öncesi açık BOM kalemlerini bilinçli olarak reddeder; U1 dışındaki pasif/regülatör kalemleri henüz açık durumdadır.
- `pcbqa gereksinim samples\\gereksinimler\\g031-urun-sozlesmesi.yaml --fail-on-open` altı kullanıcı kararı açık olduğu için bilinçli olarak `1` döndürür.

## Commit politikası

Her paket tek veya mantıksal olarak bölünmüş commit'lerle teslim edilecek. Commit gövdesi şu bilgileri taşıyacak:

```text
feat(core): bulgu-düzeltme-doğrulama çekirdeği

Kapsam:
- ...

Doğrulama:
- ...

Bilinen açıklar:
- ...

Açık iş raporu:
- docs/paketler/ACIK-IS-RAPORU.md güncellendi
```

Paket 01 ve Paket 02’nin bu ilk dilimi pushlandı. Sonraki paketlerde aynı rapor
güncellenmeden üretim koduna başlanmayacaktır.
