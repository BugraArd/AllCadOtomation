# Skorlama yol haritasi (Evre 1) ve Evre 2 devri

Tam metin: `pcbqa/docs/yol-haritasi-skorlama.md`. Bu hafiza ozet + karar
gerekceleridir; ayrinti dokumanda.

## Nihai hedef (kullanicinin koydugu)

Uretken tasarim: sistem kendi bilesenini ekleyip baglayip PCB uretsin.
Sonrasinda binlerce gercek PCB/sematikle egitim, KiCad uzerinden test,
birden fazla model. Uzmanlasma hedefi once **STM32**, sonra genel CPU devreleri.

**Uretim zincirinin mekanigi ZATEN VAR:** `sch_add.py` sembol ekler,
`sch_wire.py` baglar, `pcb_sync.py` karta yansitir, `auto` yerlestirir.
Eksik olan iki uc: (1) niyet -> topoloji karari, (2) yonlendirme (kapsam disi).

**Skor, uretimin uygunluk fonksiyonudur** - yargilayamadigimizi uretemeyiz.
Bu yuzden "once skor" karari iki hedefe birden hizmet ediyor.

## Neden agirlikli skor

`report.py`: `PENALTY = {error: 8.0, warning: 2.0, info: 0.0}`,
`MIN_COMPONENTS_FOR_SCORE = 20`, `score = 100*exp(-penalty/max(n,20))`.

Yalnizca severity sayiliyor. Olculmus etkisi olan bir kural (TI AN-2155 sicak
dongu) ile kaynaksiz bir muhendislik secimi ayni 8 puani yiyor. Ayrica ceza
IKILI: 0.01 mm ihlal ile 2 mm ihlal esit.

## Olculen zemin (2026-08-28)

11 kural tipinden **9'u** `measured`/`limit` dolduruyor. Doldurmayan ikisi
(`require_on_net`, `same_net`) zaten ikili kurallar - orantili ceza onlara
uygulanmaz, sabit agirlik alirlar. Veri modeli bu ise hazir.

## Fazlar

- **1a** Agirlik mekanizmasi: `Rule.weight`, `Finding.weight`, `run_rules`
  merkezi doldurur (rule_type gibi), `report.score` kullanir. Verilmezse
  severity'den turetilir -> 279 test degismeden gecmeli.
- **1b** Orantili ceza: `asim = |measured-limit|/limit`,
  `carpan = clamp(1+asim, 1, scale_max)`, varsayilan tavan 3.0. Opt-in
  (`scale: true`). `limit == 0` korumasi sart (courtyard_overlap'te yaygin).
- **1c** Kaynakli agirliklar: kanit gucu agirligi belirler. Olculmus etki
  (16-24) > standart/sayisal app-note (8-16) > kaynakli ama nitel (4-8) >
  muhendislik secimi (1-2). Guvenlik (clearance_voltage, sebeke) en yuksek.
- **1d** Korpus kalibrasyonu: `harness.py`'a `--score-only` kipi.
  Ilke: sahaya cikmis bir karta skorumuz dusuk veriyorsa yanlis olan SKORDUR.
  Capa olcumu: KiCad pic_programmer demosu kendi kuraliyla **82.7**.

## IKI GERCEK RISK (1b'de)

1. **Yerlestirici bu skoru optimize ediyor.** Manzara degisince `auto` farkli
   davranabilir. `harness --all --suite` zaten "GERILEME" isaretliyor -
   degisiklikten ONCE ve SONRA kosulup karsilastirilmali.
2. **ML egitim verisi skora bagli.** `ml/collect.py` ornekleri
   `d_score = after.score - current.score` ile etiketliyor. Skor degisirse
   `.work/moves*.jsonl` icindeki 49.699 ornek BAYATLAR, yeniden toplanmali.

## Evre 2 (skorlamadan sonra)

`pcbqa/circuit.py` - devre DOGRULUGU kural ailesi. `ipc2221.py` deseni.
Kaynakli hesaplanabilir kurallar: I2C pull-up boyutlandirma (NXP UM10204),
kristal yuk kondansatoru (Microchip AN826), FB bolucu akimi (Richtek AN033),
decoupling adedi (TI SPRABV2), termal bakir alani (Richtek AN044).
Yeni kural tipi `component_value` + ayri test edilebilir deger ayristirici
(`4k7`, `4.7k`, `100n`, `10uF`, `1R0`, `DNP`).

Dikkat: bu kurallarin cogu tasarim dosyasinda OLMAYAN bilgi ister (bus
kapasitansi, besleme gerilimi, FB bias akimi). Kural YAML'inda beyan edilmeli;
beyan yoksa kural SESSIZCE atlanmali, varsayilan uydurulmamali.

Tam devir promptu dokumanin sonunda.
