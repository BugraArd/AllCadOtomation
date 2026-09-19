# Skorlama yol haritasi evre 1 tam metin pcbqa

> Beads kalici hafizasi (`bd recall skorlama-yol-haritasi-evre-1-tam-metin-pcbqa`). Kaynak Dolt veritabani;
> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.

Skorlama yol haritasi - DURUM (2026-08-28 sonu, 4. guncelleme)

NIHAI HEDEF: uretken tasarim. Once STM32, sonra genel CPU. Fazlama icin bkz
[evre-3-uretken-tasarim-fazlama].

EVRE 1 (agirlikli skor) BITTI. EVRE 2 (devre dogrulugu, 16 kural tipi) BITTI.
EVRE 3a (niyet + sablon + surucu) BITTI. EVRE 3b (varyant dongusu) BITTI.

SKORUN SINIRI - 3b'de OLCULDU VE ONEMLI: skor bir IHLAL SAYACIDIR, kalite
olcegi degil. Uretilen kartta DOYUYOR (40x28 ile 100x70 arasi hepsi 100.0).
Cozunurlugu yalnizca ihlal varken var (25x18 -> 24.7, 30x20 -> 74.1).
SONUC: 'en yuksek skoru sec' bir secim olcutu DEGILDIR. Uretimde secim
(skor, -hata, -uyari, -ALAN, -HPWL) ile yapiliyor - alan gercek maliyet ve
skor onu hic gormuyor. ML etiketi de ham skor OLAMAZ (hepsi 100).

SESSIZ HATA SINIFI - ON ornek. Son dordu (turev sembol birim adlari,
fp_rect courtyard, icbukey courtyard+SAT, pad acisi cift sayimi) birim
testleri DEGIL KiCad'in kendi araclari buldu (netlist ihraci mesajsiz 3
kodu, DRC, --schematic-parity). DERS: bir sey URETMEK, o seyi OLCEN katmani
denetlemenin en iyi yolu.

DURUM: 566 test. uretim kalibrasyonu medyan 95.9, ceyrekler 80.7/95.9/100.0
(dort olcum duzeltmesinden sonra ozet DEGISMEDI, tek tek kartlar duzeldi:
jetson 73.8->83.9). pic_programmer 0 bulgu - saglam kartta sessizlik ayakta.
