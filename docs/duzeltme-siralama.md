# Düzeltme adayı sıralama — makine öğrenimine geçişin ilk deneyi

> Beads: **Kicad-u4k** (plan + kararlar), **Kicad-ww0** (deney sırasında bulunan
> iki hata). Kod: `pcbqa/pcbqa/duzeltme/`. Tarih: 2026-10-01.
>
> **Takip işleri (aynı gün):**
> - **Kicad-ecd**: gerçek KiCad projelerinde doğrulama.
> - **Kicad-apg**: en az değişiklik tercihi.
> - **Kicad-7cb**: paket kapsamı.
> - Hatalar: **Kicad-duf** (uyum eşiği) ve **Kicad-es5** (parça verisi).
>
> Güncel sonuçlar belgenin sonundaki bölümlerdedir. "Gerçek değerlendirme
> sonuçları" bölümü eski yerleşim, eski parça kaydı ve eski üreteçle
> ölçüldü; tarihsel kayıttır.

## Soru

> "Bu devre ve çalışma koşullarında hangi düzeltme adayını önce denemeliyim?"

Model elektriksel doğrulamanın **yerini almaz**. Yalnızca adayların deneme
sırasını belirler. Uygulamanın gösterdiği her öneri gerçek ngspice, kural ve
PCB kontrolünden geçmiştir.

## Devre ailesi: yüklü rezistif gerilim bölücü

```
VIN --[R_üst]--+--[R_alt]-- GND
               |
              OUT --> yük (ADC girişi, referans pini) 0..I_tepe
```

**Bu ailenin seçilme nedeni.** ngspice'ta direnç ilkel elemandır: üretici
modeli gerekmez ve "ideal" işareti taşımaz. Devrenin kapalı form çözümü de
vardır: `Vout = R2 (Vin − I R1) / (R1 + R2)`. Böylece her benzetim sonucu
bağımsız bir el hesabıyla karşılaştırılabilir. Diğer ailelerin modelleri bu
güveni vermiyor (bkz. Kicad-5d6.5):

- LDO'nun modeli davranışsal, ideal işaretli.
- Diyot varsayılan modelle benzetiliyor.
- MOSFET'in modeli yok.

**En kötü durum (EVA, mühendislik seçimi).** Her direncin sapması üç katkının
toplamıdır: tolerans, TCR × ΔT_max ve 1000 saatlik ömür testi sapması. Üçü de
Yageo kalın film kaydından gelir: 100 ppm/°C ve %1. Vout her değişkende
monotondur, bu yüzden en kötü durum kutunun 16 köşesindedir. Güç ise monoton
değildir: P_R1, R1 = R2'de tepe yapar. Kutu içi gerçek en büyük güç
`bolucu._guc_ust_siniri` ile kapalı formda bulunur.

**Mevcut koda bulunan zayıflık (ölçüldü).** `seviye3`'ün `tolerans±`
senaryosu bütün dirençleri aynı yöne kaydırır; bölücü oranı değişmez. Bu
yüzden en kötü durum (R1 yukarı, R2 aşağı) hiç görülmez.
`seviye3(ek_senaryolar=...)` adlı geriye uyumlu kanca eklendi. Bölücü ailesi
16 çapraz köşeyi bu kancayla benzetime ekler. Ölçüm:
`test_capraz_kose_kancasi_tolerans_kosesinin_kacirdigini_yakalar`'da aynı
tasarım kancasız geçiyor, kancayla kalıyor.

## Akış

| Adım | Ne yapılır | Modül |
|---|---|---|
| 1. Referans | Parametre örneklenir. Kapalı form EVA geçmeli, güç oranı ≤ %50 olan en küçük paket seçilir, courtyard'lar çakışmamalı. Ardından gerçek kontrollerden geçmeli ve benzetimle el hesabı uyuşmalı; uyuşmazsa referans reddedilir. | `veri.referans_ornekle`, `referans_isle` |
| 2. Kontrollü hata | Yedi tür hata. Hatalı varyant gerçek kontrolde **kalmalı**; kalmayan "zararsız" diye sayılır ve veriye girmez. | `hatalar.py` |
| 3. Adaylar | Üreteç yalnızca hatalı tasarımı ve koşulları görür. Hata türünü ve adayın sonucunu bilmez (imza testi var). Altı operatörden sabit sırayla ~14 aday çıkar. | `adaylar.py` |
| 4. Değerlendirme | ngspice (KiCad'in DLL'i, yan süreç, 16 çapraz köşe dahil), seviye2, PCB. PCB tarafında KiCad'in kendi `.kicad_mod` geometrisiyle courtyard çakışması, kart sınırı ve bağlantı eşliği. | `degerlendir.py` |
| 5. Kayıt | Temel tasarım kimliği, koşullar, değişiklik, sürümler, durum ve yeni ihlaller. | `veri.py` |
| 6. Model | Mevcut `ml/` altyapısı: ridge ve GBT, gruplu bölme, JSON model. | `egitim.py` |
| 7. Uygulama | `pcbqa devre-duzelt` | `sirala.py` |

**Durumlar birbirine karıştırılmaz:**

- `gecerli`: zorunlu kontrollerin hepsi çalıştı ve geçti.
- `gecersiz`: en az bir zorunlu kontrol elektriksel ya da fiziksel olarak kaldı.
- `denetlenemedi`: kontrol çalışamadı. Nedenleri: ngspice yok ya da yakınsamadı, tolerans veya anma gücü eksik, bölücü tanınmadı, benzetim el hesabıyla uyuşmadı. Bu durum etikete `gecersiz` diye **girmez**.

**Öznitelikler yalnızca tahmin anında bilinen bilgiden oluşur.**

- Girenler: hatalı tasarımın değerleri, koşullar, kart geometrisi; hatalı tasarımın **gerçek** kontrol sonuçları (marjlar, güç oranları, kalan kontroller); adayın değişiklik tanımı.
- `tam` şemada ayrıca adayın kapalı form ön hesabı ve geometrik courtyard ön kontrolü vardır. Bunlar benzetim değildir, anında hesaplanır.
- Girmeyenler: adayın benzetim sonucu ve hata türü. `test_sonuc_ve_hata_turu_oznitelik_degistirmez` bunu doğrular.

## Kayıt şeması (`kayitlar.jsonl`, `tur: aday`)

```
temel     {kimlik: bolucu-0007, parametre: {...}, imza}
varyant   {kimlik, hata (yalnızca kayıtta), tasarim: {bilesenler, kosullar, bosluk_mm},
           degerlendirme (hatalı tasarımın gerçek kontrolü)}
aday      {kimlik, operator, sira, gerekce, degisiklikler: [{ref, alan, eski, yeni}],
           on_hesap: {analitik, cakisma}}
sonuc     {durum, kontroller, nedenler, ihlaller, hatalar, olcumler, analitik,
           uyum (benzetim vs el hesabı), yeni_ihlaller, simulasyon, sure_s, onbellekten}
surumler  {kayit_semasi, pcbqa_git, pcbqa_kirli, kicad, ngspice, parca_kutuphanesi
           (sha256), aile, aday_ureteci, oznitelik, python}
```

## Çalıştırılan komutlar

```bat
cd pcbqa
.venv\Scripts\python.exe -m pcbqa.duzeltme.veri --referans 80 --cikti .work/duzeltme --isci 12
.venv\Scripts\python.exe -m pcbqa.duzeltme.egitim --veri .work/duzeltme --model-cikti pcbqa/data/modeller/duzeltme-bolucu.json
.venv\Scripts\python.exe -m pcbqa.app uret --intent samples/bolucu/bolucu-hatali.yaml --out .work/bolucu-proje --budget 3
.venv\Scripts\python.exe -m pcbqa.app devre-duzelt .work/bolucu-proje --kosullar samples/bolucu/kosullar.yaml
```

## Veri kapsamı (tohum 20261001)

| | Sayı |
|---|---|
| Kabul edilen referans | 80 / 80. Örneklemede 44 parametre seti kapalı form kapısında elendi: 21 uygun paket yok, 13 courtyard, 8 pencere tutmadı, 2 değer aralığı dışı. |
| Hatalı varyant | 427 kullanıldı; 94 zararsız çıktı, 39 uygulanamadı. |
| Aday | 6000: 1658 geçerli, 4342 geçersiz, 0 denetlenemedi |
| Gerçek ngspice koşusu | 4723. Kalanlar önbellekten geldi: aynı tasarım ikinci kez benzetilmedi. Aday başına ortalama 0,58 s. |
| Benzetim ↔ el hesabı uyuşmazlığı | 0 (düzeltmeden önce 53; bkz. Kicad-ww0) |
| Toplam süre | 280 s, 12 paralel referans |

**Dağılım:**

- Vin: 3,3 / 5 / 9 / 12 / 15 / 24 V; her birinde 9 ile 17 referans.
- Direnç değerleri: 23,7 Ω – 422 kΩ.
- Paketler: 0402 62, 0603 12, 0805 2, 1206 4 → **dengesiz**.
- `paket-kucuk` hatası yalnızca 6 varyantta görüldü, çünkü referansların çoğu zaten küçük pakette.
- Kalan zorunlu kontroller: gereksinim 3752, direnç gücü 824, PCB courtyard 189.
- 37 aday kapalı formu geçti ama PCB courtyard kontrolünde kaldı.

## Gerçek değerlendirme sonuçları

`ilk öneri` ve `ilk 3`, en az bir geçerli adayı olan varyantlar üzerinden
hesaplandı: 427 varyantın 424'ü. Benzetim, ilk geçerliye kadar harcanan
ngspice koşusudur. `+az` satırları puanı 0,1'lik kovalara ayırır ve aynı
kovada az değişikliği öne alır.

### Eğitimde bulunmayan temel tasarımlar (gruplu 5 kat CV, grup = referans)

| Sıralayıcı | İlk öneri geçerli | İlk 3'te geçerli | Benzetim ort / en çok | Yeni ihlal (ilk öneri) | Yeni ihlal (çözüm) | Değişiklik |
|---|---|---|---|---|---|---|
| rastgele (beklenen) | %27,8 | %62,6 | 3,50 / 8,5 | 0,25 | 0,04 | 2,07 |
| **üreteç (model yokken uygulama)** | %64,6 | %72,4 | 3,58 / 14 | 0,20 | 0,09 | 1,52 |
| kural-elektrik (kapalı form) | %100 | %100 | 1,00 / 1 | 0,10 | 0,09 | 1,52 |
| gbt-ham (fizik verilmeden) | %92,2 | %98,3 | 1,15 / 7 | 0,08 | 0,02 | 2,13 |
| ridge-ham | %88,2 | %96,5 | 1,32 / 16 | 0,11 | 0,00 | 2,18 |
| gbt-tam | %100 | %100 | 1,00 / 1 | 0,01 | 0,01 | 2,38 |
| **ridge-tam+az (uygulamada)** | %100 | %100 | 1,00 / 1 | 0,09 | 0,08 | 1,59 |

### Dağılım dışı (eğitim Vin ≤ 12 V, test Vin ≥ 15 V; 140 varyant)

| Sıralayıcı | İlk öneri | İlk 3 | Benzetim | Değişiklik |
|---|---|---|---|---|
| üreteç | %64,3 | %70,7 | 3,80 | 1,54 |
| gbt-ham | %91,4 | %97,1 | 1,15 | 2,04 |
| ridge-tam+az | %100 | %100 | 1,00 | 1,59 |

### Görülmemiş hata türü (her tür için: o tür eğitimde yok)

| Sıralayıcı | İlk öneri | İlk 3 | Benzetim | Değişiklik |
|---|---|---|---|---|
| üreteç | %64,6 | %72,4 | 3,58 | 1,52 |
| gbt-ham | %67,2 | %86,3 | 1,86 | 2,41 |
| ridge-ham | %74,3 | %91,3 | 1,65 | 2,54 |
| ridge-tam+az | %100 | %100 | 1,00 | 1,57 |

## Sonuçların dürüst okuması

1. **Bu ailede kapalı form kuralı kusursuz sıralıyor.** El hesabının
   "geçer" dediği aday ilk sıraya alındığında, test edilen 424 varyantın
   tamamında ilk öneri geçerli çıktı. Bunun nedeni benzetimin kapalı formla
   1 µV içinde uyuşması. `tam` şemalı model bu yüzden kuralı yeniden buluyor
   ve onu geçemiyor. Bu ailede modelin katkısı, kurala göre yeni ihlali biraz
   azaltmak ve dağılım dışında aynı başarıyı korumaktan ibaret.
2. **Taşınabilir sinyal `ham` satırlarındadır.** `gbt-ham` hiçbir fizik
   formülü görmeden, gerçek kontrol etiketlerinden öğrendi: ilk öneri
   %64,6'dan %92,2'ye çıktı, gereken benzetim 3,58'den 1,15'e indi. Bu
   kazanç Vin dağılımı dışında da korundu (%91,4). Kapalı formu olmayan
   aileler (LDO, anahtarlamalı güç) için ölçülmesi gereken sayı budur.
3. **Zayıf nokta: görülmemiş hata türü.** `gbt-ham` %67,2'ye düşüyor ama
   üreteçten (3,58 benzetim) hâlâ iyi (1,86). Model bulguların
   "imzasından" genelleme yapıyor, hata türünü ezberlemiyor. Yine de
   kapsama hata türlerinin çeşitliliğine bağlı.
4. **Ölçülen yan etki ve düzeltmesi.** Etiket yalnızca geçerliliği
   ödüllendiriyor. Ham puanla sıralayan `gbt-tam`, tek direnç yeterken dört
   değişiklikli yeniden tasarımı seçti; buna paket küçültme de dahildi
   (gerçek projede görüldü). `+az` kovalı sıralama, değişiklik sayısını
   kuralın düzeyine (1,59'a karşı 1,52) indirdi. Seçim ölçütü
   benzetim → ilk öneri → değişiklik sayısı → yeni ihlal sırasıyla ilerler.

## Uygulama (`pcbqa devre-duzelt`)

Gerçek bir KiCad projesinde koşuldu: `pcbqa uret` ile ayrı çalışma kopyasına
üretildi, netlist kicad-cli'den alındı, kart gerçek dosyadan okundu.

```
Mevcut durum: GECERSIZ (... gereksinim kaldi ...)
  - /OUT 1.813 V < gereksinim 2.7 V (senaryo capraz-kose:vin-:yuk+:r1+:r2-)
Adaylar: 16; siralama: model ridge-tam (duzeltme-bolucu.json, egitim 2026-10-01)
  1. ust-yeniden-E96: GECERLI
Onerilen degisiklik:  R1 deger: 47k -> 28.7k
  /OUT tum senaryo ve capraz koselerde 2.774..3.289 V (pencere 2.7..3.3 V)
  bu sonuca 2 benzetimde ulasildi (1 mevcut durum + 1 aday)
Proje dosyalarina YAZILMADI.
```

Model aşağıdaki durumlarda kullanılmaz, uygulama üreteç sırasıyla çalışmaya
devam eder ve nedenini yazar:

- model dosyası yok,
- dosya bozuk,
- öznitelik şeması uyuşmuyor.

Üç durum da testlidir. Eksik bilgi ya da çalışmayan benzetim durumunda
`DENETLENEMEDI` yazılır ve aday üretilmez.

## Testler

- `tests/test_duzeltme.py`: 29 test, sahte benzetimle. El hesabı (veri sayfası ömür terimi dahil), ızgaraya karşı güç sınırı, **negatif Vout sınır testi** (I_yük × R_üst = Vin'in hemen altı / eşitliği / hemen üstü), durum ayrımı ve `eksik_turu`, üretecin bağımsızlığı, öznitelik sızıntısı, v1 kayıt/model reddi, ölçütler, gruplu bölme.
- `tests/test_duzeltme_tercih.py`: 16 test (Kicad-apg). Maliyet farkı, sözlüksel hedef, politikalar, uyumluluk.
- `tests/test_duzeltme_paket.py`: 15 test (Kicad-7cb). Veri sayfası sınırları, MPN kuralı, paket nedenleri, örnekleme politikası, bölme/çoğaltma.
- `tests/test_duzeltme_entegrasyon.py`: 10 test, gerçek ngspice + KiCad footprint'i + kicad-cli. Negatif Vout sınırı, yüksek empedans uyum eşiği, büyük paketin yetersiz kalması, aynı tohum → aynı kayıt.
- `tests/test_duzeltme_proje.py`: 10 test (Kicad-ecd), gerçek kicad-cli ERC/DRC/parite ve ngspice ile.

Araç bulunamazsa entegrasyon sınıfları **atlanır**; atlanan test geçti sayılmaz.

---

## Kicad-ecd — gerçek KiCad projelerinde doğrulama

Bellekteki deney, adayları KiCad okuyucularının ürettiği veri yapılarıyla kuruyordu. `duzeltme/proje.py` aynı adayları gerçek `.kicad_sch` / `.kicad_pcb` dosyalarına uygular. Her aday şu zincirden geçer:

| Adım | Ne yapılır |
|---|---|
| Kopya | Temel proje, adayın **ayrı** klasörüne kopyalanır. KiCad kilit dosyaları (`~*.lck`) ve yedekler kopyalanmaz, kilit dosyasına **dokunulmaz**. Hedef klasör varsa iş durur: bir adayın değişikliği diğerine taşınamaz. |
| Uygula | Şematikte Value / Tolerance / Footprint / MPN alanı yazılır. Kartta Value güncellenir. Footprint takası KiCad kütüphanesinin `.kicad_mod` dosyasından yapılır: footprint UUID'si, sembol yolu, konum, açı ve pad ağları korunur, iç UUID'ler deterministiktir. Footprint değiştiyse kart yeniden yönlendirilir. |
| Geri oku | Dosyalar yeniden okunur. Kontrol edilenler: değişiklik diskte mi, UUID / yol / pin-pad eşlemesi korundu mu, şematik bağlantısı değişmedi mi (`sch_verify.compare`), bastırma envanteri (PWR_FLAG, no-connect, ERC/DRC dışlaması) aynı mı. |
| KiCad | `kicad-cli` ile netlist, `sch erc` ve `pcb drc --schematic-parity` çalışır. Bakır döküm varsa `--refill-zones` eklenir, kart kaydedilmez. Komut, çıkış kodu ve JSON rapor saklanır. |
| Elektrik | **Kaydedilmiş** şematiğin kicad-cli netlist'inden devre grafı kurulur. Ardından ngspice (16 çapraz köşe), seviye2, PCB geometrisi ve iz analizi çalışır. İz analizi yol direncini, gerilim düşümünü ve darboğazı ölçer; bölücü kol akımları en kötü köşeden gelir. |
| Durum | `gecti` / `kaldi` / `veri-model-eksik` / `arac-hatasi`. Öncelik sırası: kaldı > araç hatası > veri/model eksik > geçti. Kontrol yoksa sonuç başarı sayılmaz. |
| Kayıt | `deney.jsonl` ve aday klasöründe `_pcbqa/kayit.json`. İçerik: temel ve aday kimliği, değişiklikler, maliyet, dosya SHA-256 özetleri, KiCad / ngspice / parça kütüphanesi / footprint dosyası sürümleri, koşullar, ERC/DRC ihlalleri, elektriksel ölçümler, eğitime aktarılabilirlik ve bellekteki sonuçla uyum. |
| Önbellek | Anahtar şunların özetidir: aday dosyaları, koşullar, KiCad ve ngspice sürümü, parça kütüphanesi, kullanılan footprint dosyaları, kozmetik DRC listesi ve doğrulama kodunun kendisi. Bunlardan biri değişince önbellek kendiliğinden geçersizleşir. |

**Ortak geometri.** Bellekteki tasarım (`bolucu.tasarim_kur`) ile gerçek proje aynı yerleşimi kullanır: R1 üst rayda yatay, R2 raylar arasında dikey. Yönlendirme de aynıdır: `bolucu.rayli_yonlendir`. Bu deterministik, iki raylı bir yönlendiricidir; genel amaçlı autorouter değildir. Temel kart bu yönlendirmeyle çizilmemişse (elle değiştirilmiş ya da eksik izli kart) footprint adayı `arac-hatasi` olur. Bozuk kart sessizce yeniden yönlendirilip "onarılmış" sayılmaz.

**Bastırma yok.** ERC/DRC ihlali PWR_FLAG, no-connect işareti ya da dışlama eklenerek gizlenmez. Envanter, temel ile aday arasında karşılaştırılır. Yalnızca beş kozmetik DRC türü (silk/metin) adayı kaldırmaz, ama kayda yazılır.

**Referans projeler** (`samples/bolucu/referans/`, KiCad'de açılabilir, gerçek sembol ve footprint kütüphaneleri):

- `bolucu-gecerli`: 12 V → 3,0 V, R1 28,7 kΩ ve R2 10 kΩ, %1, 0603.
- `bolucu-hatali`: aynı devre, R1 47 kΩ (kontrollü hata).

Bağımsız el hesabı: `Vout = 10k·(12 − 10 µA·28,7k)/38,7k = 3,0266 V`. Benzetim 3,026615 V verdi.

Geçerli referansta ERC, DRC, bağlanmamış öğe ve parite sayısının dördü de 0. Kartta 7 iz parçası var.

```bat
cd pcbqa
.venv\Scripts\python.exe -m pcbqa.duzeltme.proje referans --cikti samples/bolucu/referans
.venv\Scripts\python.exe -m pcbqa.duzeltme.proje deney --temel samples/bolucu/referans/bolucu-hatali --cikti .work/gercek-deney --hepsi --model pcbqa/data/modeller/duzeltme-bolucu.json
:: ya da: pcbqa duzeltme-proje deney ...
```

**Sonuç (son kod, model sırasıyla, 17 aday; `.work/gercek-deney/`).**

- Temel durum **kaldı**, yalnızca `elektrik-gereksinim` nedeniyle. Vout 1,812 – 2,243 V; pencere 2,64 – 3,36 V. ERC, DRC ve parite 0.
- Model sırasının ilk üç önerisi tek dirençli, maliyeti 1 olan adaylar. Üçü de gerçek dosyada **geçti**.

Seçilen aday `R1 değer 47k → 28.7k` (maliyet 1). Bu seçim **eski kuralla** (deneme sırasında ilk geçen) yapılmıştı; Kicad-d8k'den beri seçim kuralı değişti (aşağıda "Kicad-d8k" bölümü). Önce ve sonra:

| | Önce (temel) | Sonra (aday-01) |
|---|---|---|
| Şematik / kart R1 | `47k 1%` | `28.7k 1%` (diskte ve kicad-cli netlist'inde) |
| ERC / DRC / bağlanmamış / parite | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| Vout (16 çapraz köşe + senaryolar) | 1,812 – 2,243 V → **kaldı** | 2,774 – 3,289 V → geçti |
| En yüklü direnç | anma gücünün %2,3'ü | %3,0'ı |
| İz analizi: en büyük düşüm | 0,0045 mV | 0,0066 mV |
| Geri okuma (UUID, yol, pin-pad, bağlantı, bastırma) | — | geçti |

Toplam sonuç: 6 geçti, 11 kaldı, 0 araç hatası, 0 veri/model eksik.

- `paket-buyut-ikisi-2` adayı gerçek DRC'de `courtyards_overlap` hatasıyla kaldı.
- 17 adayın 17'sinde bellekteki sonuç gerçek dosya sonucuyla aynı çıktı.
- Temel projenin SHA-256 özetleri deneyin başında ve sonunda aynı.
- Aday başına yaklaşık 6,5 s sürüyor: 3 kicad-cli çağrısı ve 2 ngspice koşusu.

**Rapor konumları.** Gerçek ERC/DRC JSON'ları `pcbqa/.work/gercek-deney/onbellek/<anahtar>/{erc,drc}.json` ve `netlist.xml` dosyalarındadır. Aday projeleri `.work/gercek-deney/adaylar/<kimlik>/` altında, aday kaydı `_pcbqa/kayit.json`'da, deney özeti `deney.jsonl`, `ozet.json` ve `rapor.md`'dedir.

**Testler (gerçek araçlarla, `test_duzeltme_proje.py`).** Kapsananlar:

- geçerli referansın geçmesi;
- aday uygulanıp zincirden geçince değerin diskte ve kicad-cli netlist'inde `28.7k 1%` olarak görünmesi (`47k 1%` regresyonu);
- adayların yalıtımı;
- footprint takasında UUID, yol ve pad ağlarının (`/VIN`, `/OUT`) korunması ve izlerin yeni pad'e gitmesi;
- `GDN` etiket hatasının KiCad paritesinde yakalanması;
- silinen izin DRC'de bağlanmamış öğe ve iz analizinde kopukluk olarak yakalanması;
- 2,4 mm izle gerçek clearance ihlali;
- empedans /100 tasarımında direnç gücü ihlali (ERC/DRC temizken);
- kicad-cli ya da ngspice yokken `arac-hatasi` (etiket üretilmez);
- önbelleğin aynı girdide kullanılması ve koşul değişince geçersizleşmesi.

---

## Kicad-apg — "en az değişiklik" tercihi

**Tercih sırası** (kullanıcı talimatı):

1. Zorunlu elektriksel ve tasarım gereksinimleri.
2. Geçerli adaylar arasında değişiklik maliyeti.
3. Eşdeğer adaylarda ek tercih: daha az yeni ihlal.

**Değişiklik maliyeti** (`duzeltme/maliyet.py`). Maliyet, değişiklik listesinden değil, iki tasarımın **son hallerinin farkından** hesaplanır. Bu yüzden geri alınmış ya da etkisiz işlem (`4.7k` → `4700`) maliyet üretmez. Aynı bileşendeki değer ve tolerans değişimi tek parça değişimi sayılır.

Ayrı kaydedilen alanlar ve ağırlıkları (mühendislik seçimi). Ağırlıkları `kosullar.degisiklik_maliyeti` ezer.

| Alan | Ağırlık |
|---|---|
| parça (BOM kalemi değişen bileşen) | 1 |
| footprint | 1 |
| ekleme | 2 |
| silme | 1 |
| bağlantı (pin başına) | 2 |
| yerleşim (bileşen başına) | 0,5 |
| yönlendirme (ağ başına) | 0,25 |

`deger`, `tolerans` ve `mpn` sayımları bilgi amaçlıdır; toplama girmez.

**Hedef (`sozluksel-v1`, `duzeltme/tercih.py`).** Parti, aynı sorun ve aynı çalışma koşulu demektir. Parti içindeki geçerli adaylar (maliyet, yeni ihlal) anahtarıyla yoğun sıralanır ve `1 − 0,5·r/(R−1)` hedefini alır. Geçersiz adayın hedefi 0'dır. `denetlenemedi` hedefe girmez. Eşit anahtar eşit hedef alır. Hedef parti-görelidir: farklı devreler ortak bir sıraya konmaz. Geçerli adayı olmayan parti `parti_cozumsuz` olarak işaretlenir.

**Yöntem.** Noktasal regresyon, mevcut ridge ve GBT ile. Seçim nedeni: en basit uygun yöntem bu. Yeni bir öğrenici gerekmez, model dosya biçimi ve şema denetimi aynı kalır. Çıktılar sıralama puanıdır, olasılık değildir (kalibre edilmedi). Maliyet öznitelikleri tahmin anında hesaplanır, benzetim gerektirmez. Doğrulama sonuçları yalnızca hedefi üretmek için kullanılır.

**Bölme.** Gruplar temel tasarımdır. Aynı tasarım imzasını taşıyan yakın kopyalar aynı gruba düşer (`veri.kopya_gruplari`). Grupların %20'si **son test** olarak ayrılır; model seçimi yalnızca geliştirme gruplarının gruplu 5 kat CV'siyle yapılır.

**0,1'lik kova geçici sıralama kuralı olarak kaldı** (kullanıcı talimatı). Yeni modelde aynı kovada düşük maliyet öne geçer; eski modelde az değişiklik.

### Sonuçlar — dengeli veri, SON TEST (16 temel tasarım, 95 parti; seçimde kullanılmadı)

`ilk-gecerli` politikası: adaylar sırayla doğrulanır, ilk geçerlide durulur. Pişmanlık, seçilen adayın maliyeti ile partideki en düşük geçerli maliyet arasındaki farktır.

| Yöntem | İlk öneri | İlk 3 | Benzetim | Pişmanlık (ort / en çok) | En ucuz seçildi |
|---|---|---|---|---|---|
| mevcut kural (üreteç sırası) | %17,9 | %64,2 | 4,91 | 0,06 / 2,75 | %97,9 |
| kapalı form kuralı + maliyet | %91,6 | %92,6 | 1,74 | 0,00 | %100 |
| **mevcut GBT + 0,1 kova** | %100 | %100 | 1,00 | **2,12** / 3,75 | %33,7 |
| doğrudan en az (hepsi doğrulanır) | — | — | **14,87** | 0,00 | %100 |
| **yeni: soz-gbt-tam + kova** | %100 | %100 | 1,00 | **0,00** / 0,00 | %100 |
| yeni: soz-gbt-tam (ham puan, kural yok) | %100 | %100 | 1,00 | 0,00 | %100 |
| fizik görmeyen: gec-gbt-ham + kova | %93,7 | %100 | 1,06 | 1,88 | %38,9 |
| fizik görmeyen: soz-gbt-ham + kova | %90,5 | %98,9 | 1,14 | 0,39 | %85,3 |

Doğal veride (aynı bölme) mevcut GBT + kova 0,42 pişmanlık verdi, yeni model 0,011.

**Model ile kuralın katkısı ayrı ayrı ölçüldü.** Kova kuralı mevcut modelin pişmanlığını 2,53'ten 2,12'ye indiriyor. Yeni hedef ise kural olmadan bile 0,00'a indiriyor. Yani kazanç kuraldan değil hedeften geliyor. `ilk-k` politikası (ilk 3 doğrulanır, en ucuzu seçilir) mevcut modelin pişmanlığını 0,34'e indiriyor, ama her partide 3 benzetim harcıyor.

**Doğrudan seçimin bedeli.** Pişmanlık tanım gereği 0. Ama parti başına ortalama 14,9 benzetim gerekiyor; yeni model aynı sonuca 1 benzetimle ulaşıyor.

**Fayda görülmeyen ve kötüleşen durumlar.** Bunlar açıkça raporlanır:

- **Görülmemiş hata türü `paket-buyuk` (mekanik).** Yeni model ilk öneride **%0**: dengeli veride 6,4 benzetim, doğalda 3,3. Mevcut geçerlilik modeli aynı durumda %100. Neden: sözlüksel hedef ucuz adayı öne çekiyor, ama eğitimde hiç görülmemiş bir mekanik hata ucuz değer adaylarıyla düzelmiyor. Diğer 7 görülmemiş türde yeni model ≥ %93 ilk öneri ve ≤ 0,36 pişmanlık verdi.
- **Kapalı form kuralı yeni veride kusursuz değil** (%91,6). Kural courtyard, MPN ve gerilim kontrolünü görmüyor. Maliyetle birlikte kullanıldığında pişmanlığı yine 0.

---

## Kicad-7cb — paket kapsamı

### Parça verisi (kaynak: Yageo RC_L veri sayfası V.10, 2018-12-12)

Kayıt satır satır veri sayfasıyla karşılaştırıldı (Kicad-es5). Eski kayıttaki üç yanlış düzeltildi:

- 0201'in TCR'si ±200 ppm.
- 0201 125 °C'de sıfır güce iner.
- J (%5) toleransının ömür sapması ±(%3 + 50 mΩ).

Ayrıca serideki %0,1 (B) ve %0,5 (D) tolerans seçenekleri eklendi (10 Ω – 1 MΩ). Eski belgede "kütüphanede %1'den sıkı kayıt yok" yazıyordu; bu yanlıştı.

**Paket adları** EIA inç kodudur: 0402 = 1,0 × 0,5 mm (metrik 1005). KiCad footprint adı ikisini birlikte taşır, örneğin `R_0402_1005Metric`.

**MPN.** Veri sayfasının sipariş kodu kuralıyla üretilir (`RC0603FR-0728K7L`). Örnek, veri sayfasındaki `RC0402JR-07100KL` ile birebir aynı çıkar. Katalogda olmayan bileşim (yanlış aralık, %5 için E24 dışı değer) için kod **üretilmez**; alan boşaltılır ve kontrolde kalır.

### "Paket küçük" teknik tanımı

Paket boyu tek başına bir neden sayılmaz. Gecersizlik dört ayrı nedene ayrılır (`degerlendir.neden_etiketleri`):

| Neden | Kontrol |
|---|---|
| güç | `direnc-gucu`, sıcaklıkla azaltılmış anma gücüne göre |
| gerilim | `direnc-gerilimi`, azami çalışma gerilimine göre (yeni) |
| mekanik | courtyard ve kart sınırı |
| pad/footprint | `paket-uyumu`: MPN paketi footprint'ten farklı, sembolle çelişki ya da katalog dışı (yeni) |

Gerekli veri yoksa (MPN yok, sınır bilinmiyor) neden **belirsiz** kaydedilir.

Yeni hata türleri: `paket-buyuk` (mekanik) ve `mpn-paket` (BOM'da yanlış paketli parça). Yeni aday operatörleri: `mpn-paket-esle` ve `tolerans-cok-sik` (%0,1, yalnızca katalogda varsa).

### Örnekleme politikası (`duzeltme/orneklem.py`, `--politika dogal|dengeli`)

`dengeli` politikası katmanlı örnekler. Paket kotası yapılandırılabilir; varsayılan 4 × %25.

- %30 **aşırı boy** kipi: paket gerekenden büyüktür.
- %70 **güç güdümlü** kipi: paket gücün gerektirdiği en küçük pakettir. `paket-kucuk` hedefinin güç oranı bir sınır bandına oturtulur.

Bantlar (mühendislik seçimi, ±%10):

| Bant | Güç oranı |
|---|---|
| alt | < 0,9 |
| yakın | 0,9 – 1,1 |
| üst | > 1,1 |

Tolerans ve yük paketten bağımsız örneklenir. Gerilim sınırı örnekleri için Vin listesine 36 ve 48 V eklendi. Plan yalnızca **fiziksel olarak ulaşılabilir** bantları atar. Örnek: temiz bir 0402 referansından 0201'e inince güç oranı en fazla 0,5 × 0,0625/0,05 = 0,625 olur; 0402 için yalnızca alt bant mümkündür.

Rastgelelik yalnızca (tohum, referans indeksi) çiftinden gelir. Aynı ayar aynı kaydı üretir (zaman ve süre hariç; testli). `ozet.json` şunları içerir: tohum, politika, plan, şema, sürümler ve kopya tespiti.

### Önce / sonra dağılımı (tohum 20261001, aynı kod)

| | Doğal (eski politika) | Dengeli |
|---|---|---|
| Referans paketi 0402/0603/0805/1206 | **64**/9/1/6 | 20/20/20/20 |
| Referans toleransı | %1: 80 | %1: 34, %0,5: 46 |
| Vin | 3,3 – 24 V | 3,3 – 48 V |
| Kullanılan varyant (80 temelden) | 463 | 488 |
| `paket-kucuk` varyantı | 14; bant alt 7 / üst 7 | 22; alt 8 / yakın 6 / üst 8 |
| Zararsız çıkan `paket-kucuk` (küçük paket **geçerli**) | 30 | 58 |
| Gerilim nedenli varyant | 0 | 21 |
| Aday (geçerli / geçersiz) | 6840 (2351 / 4489) | 7259 (2516 / 4743) |
| Benzetim ↔ el hesabı uyuşmazlığı | 0 | 0 |
| Kopya referans / aday | 0 / 0 | 0 / 0 |

### Paket bazında değerlendirme (`paket_deney.py`, aynı model gbt, aynı yöntem; test = dengeli verinin son test grupları)

Eğitim/test sızıntısı (temel imza kesişimi) 0. Karar eşiği 0,5 bir mühendislik seçimidir; puan olasılık değildir.

| Eğitim → dengeli test (gbt-ham, fizik görmeyen) | Kaçırılan geçersiz | Yanlış uyarı | Güç kaçırma | Mekanik kaçırma | Pad/footprint kaçırma | İlk öneri |
|---|---|---|---|---|---|---|
| doğal | 133 / 939 | 73 / 474 | 42 / 157 | 15 / 84 | 9 / 37 | %91,6 |
| doğal + çoğaltma (yalnızca eğitimde, grup bütün) | 97 | 81 | 11 | 9 | 10 | %90,5 |
| **dengeli** | **60** | 74 | **4** | **0** | **5** | **%93,7** |

Pakete göre kaçırma (doğal → dengeli eğitim):

| Paket | Doğal | Dengeli |
|---|---|---|
| 0402 | 40 | 36 |
| 0603 | 23 | 8 |
| 0805 | 43 | 15 |
| 1206 | 19 | 1 |

Fizik bilgili `gbt-tam` her iki veride de neredeyse kusursuz: dengeli test için doğal veride 9 kaçırma, dengeli veride 16; her ikisinde de yanlış uyarı 0.

**Dürüst okuma.**

- Dengeli veri en çok fizik görmeyen modelde ve az temsil edilen paketlerde (0805, 1206) fark yaratıyor.
- Çoğaltma kaçırmayı azaltıyor ama yanlış uyarıyı artırıyor. Yeni bilgi üretmiyor.
- **Ters yönde** (doğal test, adayların %78'i 0402 referanslı) dengeli eğitimli model daha çok yanlış uyarı veriyor: 128'e karşı 70. Dengeli veri hata dağılımını paketlere yayıyor; bedava değil.
- Gerilim nedeni dengeli testte yalnızca **8** örnek (AZ ÖRNEK). Bu sınıfta başarı iddiası kurulmuyor.
- Dengeli testte 1206 referanslı çözülebilir parti yalnızca 5.

```bat
.venv\Scripts\python.exe -m pcbqa.duzeltme.veri --referans 80 --cikti .work/duzeltme-dogal --isci 8 --politika dogal
.venv\Scripts\python.exe -m pcbqa.duzeltme.veri --referans 80 --cikti .work/duzeltme-dengeli --isci 8 --politika dengeli
.venv\Scripts\python.exe -m pcbqa.duzeltme.envanter --veri .work/duzeltme-dogal --veri .work/duzeltme-dengeli
.venv\Scripts\python.exe -m pcbqa.duzeltme.egitim --veri .work/duzeltme-dengeli --model-cikti pcbqa/data/modeller/duzeltme-bolucu.json
.venv\Scripts\python.exe -m pcbqa.duzeltme.paket_deney --dogal .work/duzeltme-dogal --dengeli .work/duzeltme-dengeli
```

Her veri kümesi 16 çekirdekte paralel ~11 dk sürdü. Eğitim karşılaştırması 2,7 dk.

---

## Kicad-d8k — seçim kuralı, okunur gerekçe, gerçek deney envanteri ve arayüz

Gerçek deney hattının (Kicad-ecd) üç eksiği kapatıldı. ECD/APG/7CB kodu yeniden yazılmadı; seçim, açıklama ve envanter kayıtların **üstüne** eklenen katmanlardır.

### Seçim kuralı `en-dusuk-maliyet-v1` (`duzeltme/secim.py`)

| | Eski davranış | Yeni davranış |
|---|---|---|
| Seçime giren | deneme sırasında ilk `gecti` | **bütün** değerlendirilmiş `gecti` adaylar |
| Ölçüt | sıra (model ya da üreteç) | en düşük değişiklik maliyeti (`maliyet.toplam`) |
| Eşit maliyet | — (ilk gelen) | belgelenmiş ek tercih: daha az **yeni ihlal**; hâlâ eşitse kararlı üreteç kimliği (`aday.kimlik`, alfabetik) |
| Eksik / geçersiz maliyet | — | seçim dışı, **sıfır sayılmaz**, `maliyeti_eksik` altında raporlanır |
| Geçerli aday yok | `secilen` boş | `secilen` boş + geçmeyen kontrollerin sayımı |
| Kapsam | iddia yok | `tum-adaylar` / `kismi` / `bilinmiyor`; kısmi değerlendirmede küresel en düşük iddia edilmez |

- **Yeni ihlal**, adayın temel kayıtta olmayan ihlal imzalarıdır: elektrik imzası ile KiCad ERC/DRC/parite türü ve bileşenleri. Kozmetik DRC de sayılır; adayı kaldırmaz ama ek tercihe girer.
- **Kararlı kimlik** üretecin aday adıdır (`ust-yeniden-E96`). `aday-02-` ön eki sıralayıcıya göre değiştiği için anahtar değildir. Bu adım bir kalite farkı değildir: eşit maliyetli adaylar raporlanır ve "daha kötü" denmez.
- **Etiketler değişmez.** `durum` ve `egitim` yalnızca okunur. Tercih bilgisi her kayıtta ayrı bir `tercih` alanındadır (`secime_uygun`, `maliyet`, `yeni_ihlal`, `derece`, `secildi`, `esit_maliyet`, `neden`). Özet `ozet.json` → `secim`'de durur; `ilk_gecen` (eski kural) ayrı alandır.
- **Erken durdurma korundu.** `--hepsi` olmadan ilk geçende durulur; seçim o zaman "değerlendirilenler arasında" diye etiketlenir.

### Okunur gerekçe (`duzeltme/aciklama.py`)

Her geçmeyen kontrol `{kod, durum, metin}` olarak ayrı bir `aciklamalar` listesine yazılır. Ham `kontroller` olduğu gibi kalır.

- Metindeki sayılar kayıttan gelir (ölçüm, koşul, KiCad raporu). Kayıtta olmayan ölçüm ya da çözüm önerisi yazılmaz; yoksa "kayıtta yok" denir.
- Ölçüm 3 basamakta sınırla aynı görünecekse basamak artırılır (2,6395 → `2,639`).
- KiCad ihlallerinde bileşen referansları raporun kendi öğelerinden alınır. KiCad'in özgün açıklaması ve tür kodu metinde korunur.
- Bilinmeyen kod ya da KiCad türü için teknik kodu koruyan bir yedek açıklama üretilir.
- CLI çıktısı, `rapor.md`, `pcbqa duzeltme-proje goster` ve arayüz aynı `rapor_metni` / `kontrol_aciklamalari` fonksiyonlarını kullanır.

Örnek (temel proje, gerçek kayıt):

> OUT cikis gerilimi benzetim senaryolari ve capraz koselerde 1,81-2,24 V araliginda. Izin verilen aralik 2,64-3,36 V oldugu icin gerilim gereksinimi karsilanmiyor (alt sinirin altina iniyor).
>
> [kicad-drc] R1 ve R2: courtyard alanlari cakisiyor (KiCad DRC: courtyards_overlap, error). KiCad: "Courtyards overlap"

Metinler ASCII'dir (proje kuralı: kod ASCII); ondalık ayırıcı virgüldür.

### Gerçek deney envanteri (`pcbqa duzeltme-envanter`)

```bat
pcbqa duzeltme-envanter <deney klasörü | deney.jsonl> [...] [--json çıktı.json]
pcbqa duzeltme-envanter .work/duzeltme-dogal          :: bellek veri kümesi, AYRI bölüm
```

Kaynak türü otomatik belirlenir:

| Tür | Girdi | Ne olduğu |
|---|---|---|
| `gercek-proje-deneyi` | `deney.jsonl` ya da onu içeren klasör | gerçek KiCad kopyalarında değerlendirilmiş adaylar |
| `bellek-veri-kumesi` | `kayitlar.jsonl` ya da onu içeren klasör | bellekte kurulan sentetik tasarımlar |

İki tür hiçbir zaman birleştirilmez.

**Kimlik ve tekrar kuralı:**

| Kavram | Kimlik |
|---|---|
| temel tasarım | temel proje dosyalarının SHA-256 özetleri (yol ve ad hariç) |
| çalışma koşulu | temel tasarım + `kosullar.json` içeriği |
| deney koşusu | bir `deney.jsonl` |
| referans kaydı | koşu başına `gercek-temel`; benzersizi çalışma koşulu |
| aday kaydı | çalışma koşulu + üreteç kimliği + değişiklik listesi (`ref, alan, eski, yeni`) |
| tekrar koşu | çalışma koşulu ve aday anahtar kümesi önceki bir koşuyla aynı |

- Tekrar kayıtlar dağılımlara bir kez girer. Sonuçları farklıysa `celiskili_tekrar` altında raporlanır.
- Değişiklikleri farklı iki aday tek kayda inmez.
- Okunamayan ya da zorunlu alanı olmayan satırlar `bozuk` sayılır ve satır numarasıyla listelenir.
- Gerçek kayıtta olmayan isteğe bağlı alanlar "eksik alanlar" başlığında ayrıca sayılır.
- Paket ve tolerans dağılımı için her kayda `bilesenler` alanı eklendi (kopyadaki kartın değer / footprint / paket / tolerans özeti). Bu alan Kicad-d8k'den önceki kayıtlarda yoktur ve envanterde eksik görünür.

### Arayüz (Deney sekmesi)

`pcbqa arayuz` → **Deney** sekmesi:

1. **Deney kaynağı:** klasör seçilip **Yükle** ile açılır. Aday listesinde maliyet, durum ve tercih (`SECILDI` / `esit maliyet` / `daha pahali` / `maliyet eksik`) görünür.
2. **Ayrıntı:** bir satır seçilince o adayın gerekçeleri ve seçim açıklaması gösterilir.
3. **Envanter:** aynı kaynağın envanteri, CLI ile aynı metin.
4. **Tüm adaylarla çalıştır:** üstteki projede yeni deney başlatır. Projede `pcbqa-referans.json` yoksa iş hiç başlamaz ve nedeni yazılır.

Kaynak yüklenmemişken liste boştur ve "gerçek proje değerlendirmesi GÖSTERİLMİYOR" yazar. Bellek veri kümesi seçilirse aday listesi doldurulmaz. Desteklenen aile ve `pcbqa-referans.json` gereksinimi sekmede sürekli görünür. Sekme analiz kodu içermez; `gorunum.deney_yukle`, `envanter.envanter_metni` ve `proje.deney` fonksiyonlarını çağırır.

### Gerçek projede yeniden çalıştırma (`bolucu-hatali`, 2026-10-01)

| Koşu | Sıralama | Önbellek | Değerlendirilen | İlk geçen (eski kural) | Seçilen (yeni kural) | Eşit maliyetli |
|---|---|---|---|---|---|---|
| eski kod | üreteç | yok | 17/17 | aday-02 ust-yeniden-E96 | (aday-02 seçilmişti) | — |
| yeni-1 | üreteç | yok | 17/17 | aday-02 ust-yeniden-E96 | **aday-03 alt-yeniden-E96** | aday-04 ust-yeniden-E24, aday-02 ust-yeniden-E96 |
| yeni-2 | üreteç | yok | 17/17 | aynı | **aynı** | aynı |
| model | `gbt-tam` | 18/18 | 17/17 | aday-01 ust-yeniden-E96 | **alt-yeniden-E96** (aday-03) | ust-yeniden-E24, ust-yeniden-E96 |
| erken | üreteç | 3/3 | 2/17 (`kismi`) | aday-02 | aday-02 (değerlendirilenler arasında) | — |

- **Kontrol sonuçları korundu.** Eski ve yeni kodda 18 kaydın 18'inde `durum`, `kontroller`, `egitim`, `maliyet` ve dosya özetleri aynı. Durum dağılımı yine 6 geçti, 11 kaldı.
- **Seçilen adayın gerekçesi:** `R2 10k → 16.5k` (E96). Maliyet 1 (1 parça). Vout 2,70 – 3,31 V; izin 2,64 – 3,36 V. ERC/DRC/parite 0. Geçen 6 aday arasında en düşük maliyet 1'dir ve bunu üç aday paylaşır. Üçünde de yeni ihlal 0 olduğu için ek tercih eşitliği ayırmadı; seçimi kararlı kimlik sırası belirledi (`alt-…` < `ust-…`). Diğer ikisi daha kötü değildir.
- **Tekrar üretilebilirlik:** önbelleksiz iki yeni koşu, zaman / süre / klasör dışında kayıt kayıt aynı (18/18). `ozet.json` dosyaları da aynı.
- **Sıralamadan bağımsızlık:** model sırasında aday numaraları değişti (`aday-01-ust-yeniden-E96`), ama seçim yine `alt-yeniden-E96` oldu.
- **Envanter (dört koşu birlikte):** 1 temel tasarım, 1 çalışma koşulu, 4 koşu (2'si tekrar), 4 referans kaydı (1 benzersiz), 53 aday kaydı (17 benzersiz, 36 tekrar), 0 bozuk, 0 eksik alan. Sonra paket: R1/R2 0603 10, 0402 4, 0805 2, 1206 1. Gecen maliyetleri: 1 (3 aday), 4,75 (3 aday).

### Bu işin çözmediği şeyler

- **Veri dengesizliği:** gerçek envanter tek tasarım, tek koşul ve 17 aday gösteriyor. Bu bir dağılım değil, tek örnektir. Kicad-4zv ve Kicad-515 açık kalır.
- **Aileler arası genelleme:** hat yalnızca rezistif bölücüyü ve `pcbqa-referans.json` içeren temel projeleri destekler. Kicad-s0p açık kalır.
- **`pcbqa devre-duzelt` değişmedi.** Bu komut bellekte, belgelenmiş `ilk-gecerli` politikasıyla (model sırası + ilk geçerlide dur) çalışmaya devam eder.
- **Kapsam dışı metni düzeltildi.** `KAPSAM_DISI` "direnç gerilim sınırı (azami çalışma gerilimi) kontrol edilmiyor" diyordu. Oysa Kicad-7cb'den beri `direnc-gerilimi` kontrolü bunu denetliyor. Metin "aşırı yük / darbe gerilimi kontrol edilmiyor" olarak düzeltildi. Eski kayıtlarda eski metin durur.

---

## Kalan eksikler

- **Bu aile ML için hâlâ kolay.** Fizik bilgili model kapalı formu yeniden buluyor. Asıl sınav LDO (Kicad-s0p): dropout, yük geçişi, açılış ve parçaya bağlı Cout/ESR kararlılığı. Bu sınav, Kicad-5d6.5'teki üretici modelleri gelince yapılacak.
- **Görülmemiş mekanik hata.** Sözlüksel hedef ucuz adayı öne çekiyor; `paket-buyuk` eğitimde yokken ilk öneri %0.
- **Kapsam açıkları.** 0402 referansından yakın/üst güç bandına ulaşılamıyor (fizik sınırı). `tolerans-gevsek` hatası E96 değerlerde uygulanamıyor, çünkü RC_L'de %5 yalnızca E24'te var (dengeli veride 0 varyant). Gerilim nedeni testte az. Tek üretici serisi (Yageo RC_L) var; ince film yok.
- **Gerçek proje hattı yalnızca bu bölücü topolojisini yönlendirir.** Genel autorouter yok. Yerleşim değişikliği yapan aday yok; maliyetteki yerleşim alanı bu ailede hep 0.
- **Yük modeli ideal akım yutucu.** Konnektör pin akım sınırı ve direnç aşırı yük gerilimi kontrol edilmiyor (`proje.KAPSAM_DISI`).
- **Uygulama yalnızca ilk bölücüyü ele alıyor.**
- **Kicad-u4k tabloları** ("Gerçek değerlendirme sonuçları" bölümü) eski yerleşim, eski parça kaydı ve eski üreteçle ölçüldü. Tarihsel kayıttır; güncel sayılar yukarıdadır.
