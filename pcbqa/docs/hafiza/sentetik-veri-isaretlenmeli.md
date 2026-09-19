# Sentetik veri isaretlenmeli

> Beads kalici hafizasi (`bd recall sentetik-veri-isaretlenmeli`). Kaynak Dolt veritabani;
> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.

SENTETIK VERI ISARETLENMELI (2026-08-31)

pcbqa/mpn.py sematige TEDARIK VERISI yaziyor ve o veri UYDURMA. Asil risk
teknik degil: birinin bu fiyatlari GERCEK sanmasi.

UC KORUMA:
  * her MPN 'SENT-' ile baslar
  * her sembole MPN_Kaynak=sentetik-test alani yazilir -> gercek tedarikci
    baglandiginda bu isaretli her kayit GUVENLE uzerine yazilabilir
  * uretici adlari uydurma (SentCo/TestParts/MockElec/DemoComp); uydurma bir
    fiyatin yanina gercek marka yazmak yanlis izlenim birakir

KURAL: sessizce gercekmis gibi duran veri, hic veri olmamasindan KOTUDUR.
Test verisi uretirken her zaman makine tarafindan okunabilir bir kaynak
isareti birak.

AYRICA - GORSEL SUSLEME ISTENEN DEGISMEZI BOZAMAZ:
Fiyata 'gercekci dursun' diye deterministik bir sapma (+-%2) eklemistim.
Ust kademelerde adim kuculunce (40uF -> 45uF yalnizca %0.4) sapma siralamayi
TERS CEVIRDI: C10 (45uF), C9'dan (40uF) ucuz cikti. Kullanicinin istedigi tam
olarak siralamaydi. Sapma kaldirildi, fiyat saf bir (deger, paket) fonksiyonu.

VE - BILINMEYENE VARSAYILAN ATAMA:
_base_price, degeri okunamayan bilesene 0.10 sabiti veriyordu; Device:C'nin
varsayilan 'C' degeri de fiyat aliyordu. Hakkinda hicbir sey bilinmeyen parcaya
guvenle fiyat yazmak. Artik None doner ve bilesen ENGEL olarak raporlanir.
