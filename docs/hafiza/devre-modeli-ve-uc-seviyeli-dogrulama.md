# Devre modeli ve uc seviyeli dogrulama

> Beads kalici hafizasi (`bd recall devre-modeli-ve-uc-seviyeli-dogrulama`). Kaynak Dolt veritabani;
> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.

ORTAK DEVRE MODELI + UC SEVIYELI DOGRULAMA (2026-10-01, Kicad-5d6)

KULLANICI ISTEGI: okuyuculari ortak devre modeline bagla; R1=10k yetmez, pinleri,
gorevi, guc siniri, PCB karsiligi bilinmeli; eksik bilgi ACIKCA kaydedilmeli.
Sonra 3 seviyeli dogrulama (KiCad ERC/DRC/netlist, muhendislik kurallari,
ngspice), PCB'de once yerlesim/kisit sonra dal akimina gore iz, 9 kontrol, ML.

MIMARI KARARLAR:
 * pcbqa/devre/: bilgi.py (Bilgi = deger+kaynak+guven YA DA eksik_neden),
   parca.py (ParcaBilgisi + kutuphane), graf.py (Bilesen->Pin->Ag + PCB
   karsiligi), roller.py (topolojiden gorev), kosullar.py (beyan YAML),
   yukle.py (projeden graf). CLI: pcbqa devre.
 * Parca kutuphanesi pcbqa/data/parcalar/temel.yaml (+JSON ikiz, bundle.py
   BUNDLED_DIRS'e eklendi). Kaynak alani ZORUNLU (kod reddeder). Kayitlarin
   cogu guven=dogrulanmamis (elle aktarildi, sayfa teyidi yok). Iq gibi
   teyit edilmemis sayilar BILEREK yazilmadi.
 * Bilgi sirasi: sembol alani > MPN tam eslesme > desen > genel paket > eksik.
   Desenle eslesen kaydin MPN'i sematigin MPN'i SAYILMAZ (AMS1117 cok ureticili).
 * Ag gerilimi sirasi: kosullar beyani > regulator cikisi (parca) > ag adi.
 * Addan sinir: 78xx -> vout (son iki hane), SMBJxx -> VR. Ureticinin
   adlandirma kurali, tahmin degil. 78xx dusumu teyitsiz -> SPICE modeli EKSIK.
 * pcbqa/dogrulama/: seviye1 (kicad-cli ERC + DRC --schematic-parity +
   netlist), seviye2 (5 muhendislik kurali), seviye3 (ngspice), kontroller
   (9 kontrol), dogrula.py CLI 'pcbqa dogrula'. Bulgular rules.Finding;
   tekrar eden bulgu finding_id ile tekillesir.
 * Durumlar: gecti/uyari/kaldi/kismen/denetlenemedi. kismen ve denetlenemedi
   GECTI DEGIL.
 * ngspice: KiCad 10 ngspice.dll (ngspice-46) getiriyor, konsol exe yok
   (olculdu). spice/isci.py dll'i AYRI SURECTE ctypes ile yukler (yan uygulama;
   cokme/askida kalma ana sureci etkilemez). isci.py stdlib-only cunku KiCad
   python sys.path'i siler. Senaryolar tek oturumda alter+op+wrdata.
   wr_singlescale+wr_vecnames basligi okunur. Lisans: ngspice BSD-3 ana
   lisans, pcbqa DAGITMAZ. Octave (GPL-3) eklenmedi, gerek yok.
 * LDO davranissal model: B kaynagi Vout=min(Vnom, Vin-dusum), giris akimi =
   I(sense)+Iq; ideal diye isaretli. MOSFET/MCU atlanir ve kaydedilir.
 * Termal en kotu senaryo: giris max + en sicak ortam + SUREKLI yuk. Tepe yuk
   termalde KULLANILMAZ (ilk surumde kullaniliyordu; 3.9 W yanlis en kotu
   cikti - duzeltildi).
 * Yaslanma: veri sayfasi omur testi sapmasi (1000 h); daha uzun sureye
   EKSTRAPOLASYON YOK, raporda not.
 * pcb_akim.py: yonlendirme_girdisi (sira: yerlesim kisitlari -> uretim
   sinirlari -> Manhattan agaci dal akimlari) ve iz_analizi (bakir agi ->
   Kirchhoff dugum analizi, saf Python Gauss). Iz ucu ya da pad merkezi
   baska izin ortasindaysa iz bolunur (T birlesimi). Dokum MODELLENMEDI ->
   not. rho 1.7241e-8 IEC 60028, Onderdonk darbe, TI SLVA959B via.
 * Agac kenari akimi = alt agacin NET (isaretli) enjeksiyonu; ilk surum
   yalniz negatifleri topluyordu, toprak aginda yanlisti.
 * ML: pcbqa/ml/devre_veri.py, 'dogrula --veri' -> dataset.py JSONL;
   olculemeyen oznitelik _var bayragiyla, eksik orani extra'da.

GERCEK KARTTA YAKALANAN ROL HATALARI (pic_programmer, duzeltildi):
 * ortak ag GND iken GND'deki LED katodu her topraga giden direnci LED
   direnci yapiyordu -> ray/toprak aglari LED aramasindan cikarildi.
 * raydaki her kondansator raydaki TUM IC'lere dekuplaj sayiliyordu -> en
   yakin guc pinine atanir; >1 uF toplu (muhendislik secimi).
 * VCC_PIC'i transistor suren programlama soketleri guc-girisi sayiliyordu ->
   rayi kart icinde suren (guc-cikis, transistor, diyot, bobin, regulator
   CIKISI) varsa konnektor tuketicidir.
 * kenar konnektorlerinin courtyard tasmasi hata sayiliyordu -> yalniz pad
   disaridaysa hata; konnektor govdesi tasmasi info.

DOGRULAMA: yeni 82 test (graf 21, seviye1 3, seviye2 16, spice 8 [3'u gercek
ngspice], pcb_akim 13+1, dokuz kontrol 18, ml 3). Kullanici ornegi gercek
kosuda: AMS1117 12V->3.3V 300mA: 3V3 gereksinim icinde (100 mV marj), kayip
2.79 W, Tj ~417-447 C > 125 C -> HATA. pic_programmer dogrula 6 s.
