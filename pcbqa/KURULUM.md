# pcbqa — kurulum ve kullanım

## Ne gerekiyor

**Yalnızca KiCad.** Ayrı bir Python kurmanız gerekmez.

Bunun sebebi iki ölçüme dayanıyor: KiCad kendi Python'unu (3.11.5) getiriyor,
ve `pcbqa`'nın **çalışma zamanı bağımlılığı yok** — yalnızca standart kütüphane
kullanıyor. İkinci bir Python gömmek ya da PyInstaller ile paketlemek daha
büyük, daha kırılgan ve virüs tarayıcılarını rahatsız eden bir çıktı verirdi;
kazancı ise sıfır olurdu.

KiCad zaten zorunlu: netlist/ERC/DRC için `kicad-cli`, bileşenler için sembol
ve footprint kütüphaneleri oradan geliyor. Yani "bağımsız" burada **"ayrı bir
Python kurulumu gerektirmez"** demek, "KiCad'siz çalışır" demek değil.

## Kurulum

1. KiCad 10 (ya da 8/9) kurulu olsun.
2. Bu klasörü istediğiniz yere kopyalayın.
3. İlk komut her zaman şu olsun:

```
pcbqa tani
```

Beklenen çıktı:

```
pcbqa - ortam denetimi

  ok yorumlayici               Python 3.11.5
  -- yorumlayici yolu          C:\Program Files\KiCad\10.0\bin\python.exe
  ok kicad-cli                 10.0.4  (C:\Program Files\KiCad\10.0\bin\kicad-cli.exe)
  ok sembol kutuphanesi        223 kutuphane
  ok footprint kutuphanesi     155 kutuphane
  ok calisma zamani kopyalari  11 dosya tam
  -- pyyaml                    yok - JSON kopyalari kullanilacak (normal)
  ok pcbnew (surec-ici)        10.0.4
  ok sablon kutuphanesi        6 sablon

Temel ortam hazir. Canli baglanti ve istege bagli ozelliklerin durumuna yukaridan bakin.
```

`!!` ile işaretli satır varsa program ne eksik olduğunu ve ne yapmanız
gerektiğini söyler. `pyyaml: yok` satırı **normaldir**, bir eksiklik değil.

KiCad'i olağandışı bir yere kurduysanız yorumlayıcıyı elle gösterin:

```
set PCBQA_PYTHON=D:\KiCad\10.0\bin\python.exe
```

## İki çalışma modu

| | API'siz mod (varsayılan) | Canlı mod |
|---|---|---|
| kurulum adımı | yok | `pcbqa kurulum --uygula` (bir kez) |
| KiCad açıkken | dosyaya yazmaz | çalışan PCB belgesine dokunur |
| geri alma | dosya yedeği | **KiCad'in kendi `Ctrl+Z`'si** |
| şematiğe canlı müdahale | hayır | KiCad 9/10'da desteklenmiyor |

Çoğu iş için API'siz mod yeter ve hiçbir ayar istemez. **Canlı mod**, siz
KiCad'de bakarken aracın açık PCB üzerinde çalışmasını sağlar. Şematikte
KiCad 10.0.4'ün sunucusu gerekli komutları uygulamaz; Python paketlerini
kurmak bu desteği eklemez. Şematik düzenlemesi için ilgili projeyi/editörü
kapatın, **Yap** sekmesinde düzenleyin ve şematiği yeniden açın. Proje
yöneticisi kilidi sürüyorsa onu da kapatın.

### Canlı modu açmak

```
pcbqa kurulum              ne değişeceğini gösterir (yazmaz)
pcbqa kurulum --uygula     onaylayıp uygular
pcbqa kurulum --geri-al    eski hâline döndürür
```

Değiştirilen **tek alan**: KiCad'in `kicad_common.json` dosyasındaki
`api.enable_server` → `true`. Temanız, kütüphane yollarınız, pencere
ayarlarınız aynen kalır. Yazmadan önce yedek alınır.

İki koşul var:

- **KiCad kapalı olmalı.** KiCad ayarları bellekte tutar ve çıkarken dosyanın
  üzerine yazar; açıkken değiştirirsek değişikliğimiz kaybolur. Program bunu
  kendisi denetler ve açıkken yazmayı reddeder.
- **Sonra KiCad'i yeniden başlatın** — sunucu açılışta bağlanıyor.

## Komutlar

```
pcbqa tani                       ortamı denetle
pcbqa kurulum                    canlı modu aç (bir kez, izinle)
pcbqa canli                      açık PCB bağlantısını kontrol et
pcbqa arayuz                     masaüstü arayüzünü aç (pencere)
pcbqa analiz  <proje>            kaliteyi ölç ve raporla
pcbqa yap     "<cümle>"          doğal dil komutunu anla ve uygula
pcbqa parcalar <şematik>         ağ / gerilim / akım / MPN / fiyat tablosu
pcbqa uret    <niyet.yaml>       niyetten çalışır bir kart üret
pcbqa kesfet  <niyet.yaml>       N varyant üret, en iyisini seç
pcbqa bagla   <şematik>          var olan sembolleri telle birleştir
pcbqa sozluk                     bileşen adları sözlüğü (kısaltma, EN/TR)
pcbqa mpn     <şematik>          parça numarası + fiyat alanları (sentetik)
pcbqa sablonlar                  şablon kütüphanesini listele
pcbqa yerlestir <kart>           var olan bir kartı yerleştir ve puanla
pcbqa uygula  <kart>             yerleştirip pcbnew ile uygula (API gerekmez)
```

Her komutun kendi yardımı var: `pcbqa <komut> --help`

## Arayüz

```
pcbqa arayuz
```

Beş sekme, hepsi aynı projeyi hedefler: **Yap** (doğal dil komutu),
**Parçalar** (ağ / gerilim / akım / MPN / fiyat tablosu), **Analiz**,
**Üret** (niyetten kart), **Ortam** (tanı + sözcük dağarcığı).

Komut satırındaki iki adımlı güvenlik arayüzde de aynen geçerli: **"Uygula"
düğmesi kapalı başlar** ve yalnızca *aynı cümle* + *aynı proje* için bir
kuru koşum geçtikten sonra açılır. Cümleyi ya da projeyi değiştirirseniz
tekrar kapanır — ekranda gördüğünüz planla yazılan plan hep aynıdır.
Yazmadan önce ayrıca onay sorulur.

### Kısayol

Çift tıklamayla açmak için proje klasöründe **`pcbqa Arayuz`** kısayolu var;
hedefi `pcbqa\pcbqa-arayuz.cmd`. Masaüstüne ya da Başlat'a sürükleyebilirsiniz.

Kısayol kaybolursa yenisi PowerShell'de bir satırda yapılır:

```powershell
$w=New-Object -ComObject WScript.Shell; $k=$w.CreateShortcut("$PWD\pcbqa Arayuz.lnk")
$k.TargetPath="$PWD\pcbqa\pcbqa-arayuz.cmd"; $k.WorkingDirectory="$PWD\pcbqa"
$k.WindowStyle=7; $k.Save()
```

Kısayollar makineye özeldir (içlerinde mutlak yol gömülüdür), bu yüzden
sürüm kontrolüne girmez.

### Arayüz neden ayrı bir başlatıcı kullanıyor

**KiCad'in kendi Python'unda `tkinter` yoktur** (ölçüldü, KiCad 10.0.4) ve
`pcbqa.cmd` yorumlayıcı olarak önce onu seçer — yani arayüz normal
başlatıcıyla açılamaz. `pcbqa-arayuz.cmd` bu yüzden var: `tkinter`'ı
**gerçekten** olan bir Python arar (varsaymaz, her adayı çalıştırıp sınar) ve
konsol penceresi açılmasın diye onun **kendi** `pythonw.exe`'siyle başlatır.

Hangi yorumlayıcıyı seçtiğini sorabilirsiniz:

```
pcbqa\pcbqa-arayuz.cmd --nerede
```

Hiçbiri bulunamazsa ne yapacağınızı söyler; sabitlemek için:
`set PCBQA_PYTHON=C:\Python313\python.exe`

## Örnek: var olan bir karta bileşen eklemek

Cümleyi olduğu gibi yazın; araç ne anladığını **önce gösterir**, yazmaz:

```
> pcbqa yap "şu anki modelimize 10 adet kapasitör koy"
anlasilan: "şu anki modelimize 10 adet kapasitör koy"
  10 x Kondansator (Device:C)
  not: Kondansator: deger verilmedi - kutuphanedeki deger kullanilacak
  hedef: ...\kartim.kicad_sch
  C8 @ (15.24, 16.51) ... C18 @ (129.54, 16.51)
  (dry-run - yazmak icin --uygula)
```

Değer, paket ve birden fazla istek aynı cümlede olabilir:

```
pcbqa yap "5 adet 100nF 0603 kondansatör ve 3 adet 10k direnç ekle" --uygula
```

Anlaşılmayan hiçbir şey sessizce geçilmez: bilinmeyen bir kelime, tanımsız
bir paket ya da tek başına yetmeyen bir istek (`transistör` — NPN mi PNP mi?)
**engel** olur ve adaylarıyla birlikte yazılır. Değer verilmezse
uydurulmaz. Anlaşılan bileşen türlerini `pcbqa yap --dagarcik` listeler.

Bu sürüm yalnızca **ekler**; `sil`, `taşı`, `bağla` tanınır ama reddedilir
(bağlamak için `pcbqa bagla`).

## Örnek: parça tablosu

```
pcbqa parcalar KicadOtomasyon1\KicadOtomasyon1.kicad_sch --csv tablo.csv
```

Her parça için ağlar, gerilim, akım, MPN ve fiyat. **Boş hücre "bilmiyoruz"
demektir** ve son sütun neyi neden bilmediğimizi yazar. Gerçekten
türetilebilen üç şey var:

| ne | nereden |
|---|---|
| ray gerilimi | net **adından**: `+3V3`→3.3 V, `+1V8`→1.8 V, `GND` ailesi 0 V (referans düğümü), `VBUS` 5 V (USB 2.0 spec 7.2.1) |
| direnç akımı | iki ucunun gerilimi biliniyorsa Ohm yasası, `I = \|ΔV\| / R` |
| kondansatör akımı | kararlı halde DC akım geçmez — tahmin değil, elemanın tanımı |

`VCC`, `VDD`, `VIN` gibi adlar **hiçbir şey söylemez** (1.8 V da olabilir
24 V da) ve boş bırakılır: "VCC 5V'tur" varsayımı 3.3 V'luk bir kartta
yanlış akım hesaplatırdı. Entegre, diyot, LED ve transistörler için
"benzetim gerekir" yazar — bir LED'in akımı seri direncinden hesaplanabilirdi
ama ileri gerilimi (Vf) parçaya özgüdür ve kütüphanede yazmaz.

**MPN ve fiyat sentetiktir** (test verisi): her MPN `SENT-` ile başlar,
şematiğe yazılmamış olanlar `(oneri)` diye işaretlenir.

## Örnek: sıfırdan bir kart

```
pcbqa kesfet --intent samples\niyetler\f103-asgari.yaml --out C:\isler\kartim --variants 4
```

Çıktı, dört aday arasından en küçük ve en kısa telli olanı seçer ve
`C:\isler\kartim` altına açılabilir bir KiCad projesi bırakır.

## Kendi niyetinizi yazmak

`samples\niyetler\` altındaki dosyaları örnek alın. Kullanabileceğiniz
blokları `pcbqa sablonlar` listeler:

```yaml
version: 1
name: kartim
blocks:
  - mcu-stm32f103c8
  - ldo-ams1117-3v3
  - usb-micro-b
  - template: crystal-hse
    params:
      freq: 8MHz
```

## KiCad açıkken

Dosyaya yazan komutlar (`uret`, `kesfet`, `yerlestir`, `uygula --apply`)
proje KiCad'de **açıkken çalışmayı reddeder**. Bu bilinçli bir korumadır:
KiCad dosyayı bellekte tutar, biz yazarken siz kaydederseniz iki taraftan
birinin değişikliği sessizce kaybolur. Projeyi kapatın ve tekrar deneyin.

## Bilinen sınırlar

- **Üretilen kart yönlendirilmez** (bakır yol çizilmez). Bileşenler doğru
  ağlarda ve düzgün yerleştirilmiş olarak gelir; yönlendirmeyi KiCad'de siz
  yaparsınız. Bu yüzden skor yalnızca yerleşimi yargılar.
- **Şablon kütüphanesi şimdilik STM32F103 ailesi** ve temel güç/bağlantı
  blokları. `pcbqa sablonlar` güncel listeyi verir.
- Üretilen kartta **referans yazıları çakışabilir** (ipek baskı); yerleştirici
  metinleri hesaba katmıyor.

### Canlı mod ne yapar, ne yapmaz

Ölçüldü (stabil KiCad 10.0.4 ve ayrı nightly 10.99.0-3671-gbe90a7e200):

| | canlı düzenleme |
|---|---|
| **PCB** (pcbnew açıkken) | **evet** — **Canlı** sekmesinden önizleme ve uygulama; değişiklik KiCad'in geri alma geçmişine tek işlem olarak girer (`Ctrl+Z`) |
| **Şematik** (Eeschema açıkken) | **hayır** — Eeschema öğe komutlarını uygulamıyor (`GetItems` → "no handler available"). Şematik için editör kapalıyken dosyaya yazılır. |
| **Şematik, ayrı nightly** | **evet** — Canlı sekmesinden parça ekleme, yeni parçaları ağlara bağlama ve değer değiştirme; tek `Ctrl+Z`, kaydetmek için `Ctrl+S`. |

Canlı modun istemci kütüphanesi KiCad'in Python'unda kurulu gelmez; bir kez:

```
pcbqa kurulum --canli-bagimliliklar
```

Bu, `kicad-python` ve bağımlılıklarını KiCad'in **kendi eklenti klasörüne**
kurar (`Belgeler\KiCad\<sürüm>\3rdparty\...`). KiCad açıkken de
çalışır — ayara değil, ayrı bir sürece paket kuruyor.

Arayüz farklı Python kullanır. **Canlı → Bağımlılıkları kur**, arayüzün
kullandığı ortama kurar; komut satırındaki kurulum KiCad'in Python'unu
hedefler. Denetim gerçek `import` işlemleriyle yapılır. **DENETLENEMEDİ**,
yorumlayıcıya erişilemediği anlamına gelir; üç paketin eksik olduğu anlamına
gelmez.

**Canlı PCB akışı:** Projeyi seçin → **PCB'yi aç** → **Bağlantıyı kontrol et**
→ **Yerleşimi önizle** → **Canlı PCB'ye uygula**. API kapalıysa KiCad'i
kapatıp **API'yi etkinleştir** düğmesini kullanın, ardından PCB'yi açın.
Önizleme açık PCB'nin kaydedilmemiş hâlinden alınır. Kart önizlemeden sonra
değişirse uygulama reddedilir; yeniden önizleme gerekir. Dosya otomatik
kaydedilmez. Boş kartta önce KiCad'de **F8** ile şematikten aktarım yapın.
Bakır yolları/viaları olan kart otomatik taşınmaz; bu akış yönlendirme öncesi
yerleşim içindir. Şematik değişiklikleri PCB'ye kendiliğinden aktarılmaz.

Komut satırında aynı akış:

```
pcbqa canli "C:\projeler\kart.kicad_pcb"
pcbqa canli "C:\projeler\kart.kicad_pcb" --yerlestir
pcbqa canli "C:\projeler\kart.kicad_pcb" --yerlestir --uygula
```

Şematik API desteği KiCad'in geliştirme dalında bulunmaktadır; mevcut
kararlı kurulumda etkin değildir. Kaynaklar:
[KiCad 10.0 şematik sunucusu](https://gitlab.com/kicad/code/kicad/-/blob/10.0/eeschema/api/api_handler_sch.cpp),
[resmî Python istemcisinin sürüm notları](https://gitlab.com/kicad/code/kicad-python/-/blob/main/README.md).

**Stabil PCB bağlantısı için aynı anda tek KiCad örneği açık olsun.** IPC soketini ilk açılan örnek
barındırır; ikinci bir örnek (ör. proje yöneticisi açıkken ayrıca açılan
bağımsız bir editör) sunucuya katılmaz ve API onu görmez.

### Canlı şematik

Bu bilgisayarda ayrı **KiCad 10.99.0-3671-gbe90a7e200** ve ona eşleşen Python
istemcisi hazırlandı. Mevcut KiCad 10.0.4 kurulumu korunur. Nightly şematik
dosyalarını yeni biçimde kaydedebilir; çalışma bu yüzden **CanliProjeler**
klasöründeki proje kopyasında yapılır. Kopyayı eski KiCad sürümünde
açabileceğinizi varsaymayın.

1. Uygulamada projeyi seçin; kaynak KiCad'de açıksa kaydedip kapatın.
2. **Canlı → Canlı şematik kopyasını aç** düğmesine basın. Üstteki proje
   yolu oluşturulan kopyaya geçer. İlk açılışta KiCad bir diyalog gösterirse tamamlayın.
3. **Şematik bağlantısını kontrol et** düğmesi açık şematikteki sembolleri okur.
4. Komutu yazıp **Şematik komutunu önizle** düğmesine basın.
5. Planı inceleyip **Canlı şematiğe uygula** düğmesini kullanın.

Örnekler:

```
2 adet 100nF kondansator ekle
2 adet 100nF kondansator ekle ve hepsini VCC ile GND arasina bagla
R1 degerini 10k yap
```

Mevcut olmayan bir ağ adı kullanılırsa önizleme bunu bildirir. Oluşturulan
etiketler yalnızca aynı adlı ağları bağlar; güç kaynağı oluşturmaz.
Şematikte yaptığınız değişiklikleri **KiCad'de Ctrl+S** ile kaydedin.
İşlemin tamamı **Ctrl+Z** ile geri alınır. Daha sonra aynı canlı kopyayı seçip
açma düğmesine bastığınızda o kopyaya devam edilir.

Önizleme açık şematiğin kaydedilmemiş hâlinden hazırlanır. Uygulamadan önce
tam dosya yolu ve içerik özeti tekrar denetlenir; arada değişiklik olduysa
yeni önizleme gerekir. Yeni parçalar önce geçici dosyada hazırlanır ve
KiCad netlist kontrolünden geçirilir; açık şematiğe yalnızca yeni öğeler
aktarılır. Her API öğesinin kabul durumu kontrol edilir, işlem sonrası
bağlantılar tekrar karşılaştırılır. İşlem sonrası doğrulama hata bildirirse
KiCad'de Ctrl+Z kullanın; uygulama böyle bir durumda başarı bildirmez.

Şimdilik **tek sayfalı şematik**, mevcut komut sözlüğündeki eklemeler ve
`R1 degerini 10k yap` biçimindeki değer değişiklikleri desteklenir.
Serbest metinle her KiCad işlemini yapmaz; var olan parçaları otomatik
silme/taşıma ve çok sayfalı şematik otomasyonu bu akışın kapsamı dışındadır.
PCB'ye aktarım ayrıca KiCad'de yapılır; otomatik eşitleme yoktur.

Geliştirici için: `pcbqa/.runtime/sematik.json` yerel KiCad/Python yollarını
tutar. Nightly `.runtime/kicad-nightly`, istemci `.venv-nightly` içindedir;
stabil istemci sürümü değiştirilmez. İşçi JSON üzerinden ayrı süreçte
çalışır. Görünür editör, arka plan okuyucusu ve stabil KiCad ayrı profillere
sahiptir; şematik soketi de ayrıdır. Bu kurulum şu anda bu bilgisayara
özgüdür; başka bilgisayara yalnızca kaynak klasörünü kopyalamak yeterli değildir.

Doğrulanan istemci, [resmî Python kaynağı](https://gitlab.com/kicad/code/kicad-python)
ve [nightly ile aynı protokol sürümünden](https://gitlab.com/kicad/code/kicad/-/tree/be90a7e200/api/proto)
üretilmiştir. `.runtime` içindeki yerel wheel eşleşen istemciyi saklar.

Komut satırı karşılığı:

```
pcbqa canli-sematik "C:\projeler\kart\kart.kicad_sch" --ac-kopya
pcbqa canli-sematik "C:\...\CanliProjeler\kart-...\kart.kicad_sch"
pcbqa canli-sematik "C:\...\CanliProjeler\kart-...\kart.kicad_sch" --komut "R1 degerini 10k yap"
```

Son komut yalnızca önizler; gerçek uygulama için `--uygula` eklenir.

## Sorun giderme

| belirti | sebep / çözüm |
|---|---|
| `calistirilacak bir Python bulunamadi` | KiCad kurulu değil ya da olağandışı bir yerde — `PCBQA_PYTHON` ayarlayın |
| `kicad-cli bulunamadi` | KiCad kurulumu eksik — `PCBQA_KICAD_CLI` ile yolunu verin |
| `proje KiCad'de acik gorunuyor` | Projeyi KiCad'de kapatın |
| `calisma zamani kopyasi yok` | Paket eksik kopyalanmış — `python -m pcbqa.bundle` çalıştırın |
| YAML dosyanız okunamıyor | Çapa (`&`), çok satırlı metin (`|`) gibi ileri YAML yapıları desteklenmiyor; sadeleştirin |
