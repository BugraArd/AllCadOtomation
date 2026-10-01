# Duzeltme siralama ilk deney

> Beads kalici hafizasi (`bd recall duzeltme-siralama-ilk-deney`). Kaynak Dolt veritabani;
> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.

DUZELTME SIRALAMA - ML ILK DENEYI (2026-10-01, Kicad-u4k; hatalar Kicad-ww0)
Ayrinti: docs/duzeltme-siralama.md. Kod: pcbqa/pcbqa/duzeltme/. Komut: pcbqa devre-duzelt.

GOREV: 'bu devre ve kosullarda hangi duzeltme adayini once denemeliyim?'
Model dogrulamanin yerini ALMAZ; yalnizca deneme sirasini belirler.

AILE: yuklu rezistif bolucu (ngspice'ta R ilkel, kapali form var). EVA:
tol + TCR*dTmax + omur sapmasi, 16 capraz kose. seviye3'e geri uyumlu
ek_senaryolar kancasi (tolerans+/- ayni yonde kaydiriyor, bolucu oranini
goremiyordu - olculdu).

VERI (tohum 20261001): 80 referans (hepsi kapali form + gercek ngspice ile
dogrulandi), 427 hatali varyant, 6000 aday (1658 gecerli / 4342 gecersiz /
0 denetlenemedi), 4723 gercek ngspice kosusu, 280 s, benzetim-el hesabi
uyusmazligi 0. Durumlar: gecerli / gecersiz / denetlenemedi KARISTIRILMAZ.

SONUC (gruplu CV, grup = temel tasarim; 424 cozulebilir varyant):
  ureteci (model yokken): ilk oneri %64.6, ilk3 %72.4, 3.58 benzetim
  kapali form kurali:     %100 / %100 / 1.00  -> bu ailede kural KUSURSUZ
  gbt-ham (fizik yok):    %92.2 / %98.3 / 1.15  (Vin>=15 disi: %91.4)
  gorulmemis hata turu:   gbt-ham %67.2 / 1.86 benzetim (zayif nokta)
  uygulamada: ridge-tam+az %100 / 1.00, degisiklik 1.59 (kural 1.52)
DERSLER:
  * etiket yalnizca gecerlilik -> ham puanla gbt-tam 4 degisiklikli yeniden
    tasarim secti (tek direnc yeterken). Cozum: 0.1 puan kovasi icinde az
    degisiklik once (+az). Sonraki surum: sozluksel etiket.
  * benzetim-el hesabi uyum kapisi kendi turetme hatami yakaladi (guc
    siniri varsayimi; Kicad-ww0) - kapi kaldirilmamali.
  * bu ailede ML kurali GECEMEZ; tasinabilir sinyal 'ham' satirinda.
    Asil sinav kapali formu olmayan aile (LDO, Kicad-5d6.5 sonrasi).
