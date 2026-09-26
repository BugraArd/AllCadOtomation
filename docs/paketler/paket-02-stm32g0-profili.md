# Paket 02 — STM32G0 ilk üretim profili

**Durum:** İLK DİLİM UYGULANDI — ELEKTRİKSEL KABUL BEKLİYOR
**Tarih:** 2026-09-26

## Karar

İlk profil `STM32G031K8T6` olacaktır. Tasarım dosyalarında KiCad’in ortak
sembol kimliği `MCU_ST_STM32G0:STM32G031K8Tx`, paket ise
`Package_QFP:LQFP-32_7x7mm_P0.8mm` olarak kullanılır.

Bu seçim ilk dikey dilim için dengelidir: ST’nin resmi ürün sayfası 64 KB
Flash, 8 KB RAM, 1.7–3.6 V çalışma aralığı, 64 MHz Cortex-M0+ ve SWD desteğini
belirtir. KiCad 10 kurulumunda sembol ve footprint doğrulanmıştır. T6/T3/T7
ve bant/ambalaj seçimi satın alma aşamasında ayrıca stok ve sıcaklık sınıfıyla
kontrol edilecektir; bu dosya gerçek BOM/sourcing garantisi değildir.

## Uygulanan ilk dilim

`pcbqa/pcbqa/templates/mcu-stm32g031k8.yaml` şunları üretir:

- U1: STM32G031K8T6, LQFP-32
- VDD/VSS: `3V3` / `GND`
- PF2-NRST: `NRST`
- 1 × 100 nF VDD decoupling
- 1 × 4.7 uF bulk kapasite
- 1 × 100 nF NRST kapasitesi
- opsiyonel SWD, I2C1, USART2 ve LSE pin eşlemeleri

## Bilinçli sınırlar

- Bu LQFP-32 profilinde USB ve HSE pini varsayılmaz.
- PA14, SWCLK ile BOOT0 işlevini paylaşır; otomatik BOOT0 pulldown eklenmez.
  Boot/option-byte politikası ayrı bir blokta ele alınacaktır.
- Üretilen kart yönlendirilmez; bu paket yalnızca doğru şematik niyet,
  gerçek sembol/footprint ve net bağlantı sözleşmesini kurar.
- AMS1117 bloğu mevcut örnek altyapıyla uyumluluk içindir; üretim BOM’u için
  regülatör seçimi ve termal/akım gereksinimi ayrıca doğrulanacaktır.

## Kabul kriterleri

- YAML ve runtime JSON kopyası ayrışmamalı.
- Gerçek KiCad sembolü ve footprint’i çözülmeli.
- `g031-asgari.yaml` plansız pin veya eksik sağlayıcı üretmemeli.
- KiCad netlist doğrulaması geçen geçici bir proje üretilebilmeli.
- Gerçek kartta güç, reset, SWD ve seçilen çevre birimleri kullanıcı
  gereksinimiyle onaylanmadan profil “üretime hazır” sayılmamalı.

## Kaynaklar

- ST STM32G031K8 ürün sayfası: https://www.st.com/en/microcontrollers-microprocessors/stm32g031k8.html
- ST DS12992 datasheet: https://www.st.com/resource/en/datasheet/stm32g031k8.pdf
- ST AN5096 hardware development: https://www.st.com/resource/en/application_note/dm00443870-getting-started-with-stm32g0-series-hardware-development-stmicroelectronics.pdf
