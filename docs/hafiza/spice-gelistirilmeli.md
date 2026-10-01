# Spice gelistirilmeli

> Beads kalici hafizasi (`bd recall spice-gelistirilmeli`). Kaynak Dolt veritabani;
> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.

GELECEK PLANI - SPICE GELISTIRILMELI (kullanici talimati, 2026-10-01, Kicad-5d6.5)

KULLANICI DEDI: SPICE'i ileride gelistirmemiz gerekecek; MOSFET, regulator
veya baska bir entegre icin uygun SPICE modeli gerekebilir. Graphify notlarina
'SPICE gelistirilmeli' diye ekle.

DURUM (ilk surum): yalnizca DC calisma noktasi (op) senaryolari. Pasifler
SPICE ilkel elemani; LDO davranissal/ideal (dusum sabit, akim siniri / termal
kapanma / gecici yanit YOK, Iq bilinmiyorsa 0); diyot varsayilan model;
MOSFET, MCU, anahtarlamali regulator ATLANIYOR (rapor 'spice-modeli' info).

YAPILACAKLAR:
 1. Uretici SPICE modelleri: MOSFET (2N7002, AO3400A...), LDO (AMS1117),
    anahtarlamali regulator, op-amp. Her model: kaynak URL, lisans (cogu
    uretici modeli yeniden dagitimi kisitlar - pcbqa'ya GOMULMEMELI, kullanici
    yolu ya da indirme ile), pin eslemesi (parca.SpiceModeli.pin_esleme) ve
    pin-esligi kontrolunden gecmeli.
 2. Gecici (tran) analiz: yuk basamagi, acilis, LDO kararliligi (cikis
    kondansatoru ESR), anahtarlama dugumleri. C/L tolerans ve sicaklik
    etkileri ancak burada gorunur (DC'de C acik, L kisa).
 3. Sinif II seramik DC bias kapasite kaybi modeli (uretici egrisi).
 4. Sicaklik: yariiletken modellerde .temp etkisi; direnclerde TCR isareti
    bilinmiyor - su an +/- kose.
 5. Monte Carlo icin ngspice yerlesik 'agauss' yerine Python ornekleme
    kullaniliyor (arka uctan bagimsiz); buyuk devrede tek oturumda alter
    sayisi buyur - performans olculmeli.
 6. XSPICE kod modelleri (KiCad lib/ngspice/*.cm) spinit olmadan
    yuklenmiyor; gerekirse isci.py 'codemodel' komutuyla yukler.
