# Duzeltme gercek proje tercih paket

> Beads kalici hafizasi (`bd recall duzeltme-gercek-proje-tercih-paket`). Kaynak Dolt veritabani;
> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.

DUZELTME SIRALAMA - GERCEK PROJE + EN AZ DEGISIKLIK + PAKET KAPSAMI (2026-10-01; Kicad-ecd, Kicad-apg, Kicad-7cb; hatalar Kicad-duf, Kicad-es5)
Ayrinti: docs/duzeltme-siralama.md (son bolumler). Kod: pcbqa/pcbqa/duzeltme/{proje,maliyet,tercih,orneklem,envanter,paket_deney}.py.

ECD: aday -> temel projenin AYRI kopyasi -> sematik+karta yazma (footprint takasi UUID/yol/pad agi korur, deterministik UUID) -> geri okuma -> kicad-cli ERC/DRC/parite -> KAYDEDILMIS sematikten ngspice + iz analizi. Durumlar gecti/kaldi/veri-model-eksik/arac-hatasi. Bellek ile gercek proje AYNI yerlesim + rayli yonlendirme (bolucu.yerlesim/rayli_yonlendir; autorouter degil). Sonuc: 17 aday, 17/17 bellekle ayni, temel degismedi. Komut pcbqa duzeltme-proje.
APG: maliyet = son hallerin farki; hedef sozluksel-v1 (gecerlilik > maliyet > yeni ihlal, parti-goreli). Son test: mevcut GBT+0.1 kova pismanlik 2.12 -> yeni 0.00 (kazanc HEDEFTEN, kural degil). Dogrudan en az 14.9 benzetim. ZAYIF: gorulmemis paket-buyuk ilk oneri %0 (Kicad-515). 0.1 kova gecici kural.
7CB: 'paket kucuk' = guc / gerilim / mekanik / pad-footprint ayri nedenler, veri yoksa belirsiz. Dengeli ornekleme (kota + asiri-boy + guc bantlari, yalniz fiziksel ulasilabilir) 64/9/1/6 -> 20/20/20/20; gbt-ham kacirma 133 -> 60, ama dogal testte yanlis uyari artar. Cogaltma yeni bilgi uretmez.
PARCA VERISI: Yageo RC_L V.10 Tablo 2/8 - 0201 +-200 ppm ve 125 C; J omur +-(3%+50 mohm); %0.1/%0.5 VAR. MPN kuralla, katalog disi icin uretilmez.
DERSLER: uyum kapisi esigi ag empedansiyla olceklenmeli (1 Tohm sizinti, Kicad-duf); eski 'kutuphanede %1'den siki yok' notu yanlisti - veri sayfasi okunmadan parca notu yazilmaz.
