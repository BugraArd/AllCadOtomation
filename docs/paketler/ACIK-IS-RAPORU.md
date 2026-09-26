# Açık İş Raporu

**Son güncelleme:** 2026-09-26
**Aktif paket:** Paket 01 — Bulgu / Düzeltme / Doğrulama Çekirdeği
**Durum:** Paket 01 çekirdeği uygulandı; STM32G0 kabul testi ve Paket 02 planı bekliyor

## Mevcut doğrulanmış taban

- KiCad 10.0.6 ve Python ortamı kuruldu.
- `pcbqa tani` kütüphane ve canlı PCB ortamını doğruluyor.
- 911 test başarılı, 50 test isteğe bağlı demo eksikliği nedeniyle atlanıyor.
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
| P02-01 | P0 | Kesin STM32G0 parçası ve paketinin seçilmesi | Planlandı | 02 |
| P02-02 | P0 | STM32G0 şablon ve üretim profili | Planlandı | 02 |
| P02-03 | P1 | Gerçek MPN/BOM veri kaynağı | Planlandı | 02 |
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
- Mevcut üretim şablonları STM32F103 ağırlıklıdır; STM32G0 henüz ürün profili değildir.

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
- Uçtan uca regresyon: `Ran 911 tests ... OK (skipped=50)`.
- Uygulama sonrası örnek kartta başka bulgular kaldığı için genel sonuç kodu `1` dönebilir; hedef bulgunun kapanması ve netlist paritesi ayrı doğrulama kapılarıdır.

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

Paket 01 onaylandı; bu teslimatta commit ve push yapılacaktır. Sonraki paketlerde
aynı rapor güncellenmeden üretim koduna başlanmayacaktır.
