# pcbqa — KiCad tasarım kalite analizi ve otomatik yerleştirme

KiCad projelerini **salt-okunur** analiz eden bir araç. Tasarımınızda hiçbir
değişiklik yapmaz — sadece okur, ölçer ve rapor eder.

## Ne yapar?

KiCad şematiği ile PCB'yi ayrı ayrı bilir ama **ikisini birleştirmez**. ERC size
"bu pin bağlı değil" der; "bu decoupling kondansatörü 33 mm ötede" demez.
`pcbqa` tam olarak o boşluğu doldurur:

```
U2.VCC_14 için en yakın C1 33.3 mm uzakta (hedef <= 20 mm), net VCC
```

Üç kaynağı tek raporda birleştirir:

| Kaynak | Ne verir |
|---|---|
| `kicad-cli sch export netlist` | Hangi pin hangi nette, pin işlevleri ve tipleri |
| `.kicad_pcb` | Bileşenlerin ve pad'lerin fiziksel konumu, courtyard, kart sınırı |
| `kicad-cli sch erc` / `pcb drc` | KiCad'in kendi kontrolleri |

**Şematik zorunlu değil.** KiCad 9+ pad'lerde hem net adını hem pin tipini
sakladığı için kuralların neredeyse tamamı sadece `.kicad_pcb` ile çalışır.
Şematik varsa ek olarak pin işlev adları (`VCC_8`) ve net sınıfları gelir.

## Kurulum

Gereksinim: KiCad 9 veya üzeri (`kicad-cli` için) ve Python 3.10+.
IPC ile çalışan KiCad'e placement yazmak için ayrıca `kicad-python` kurulur.

```powershell
cd C:\Users\ardaa\OneDrive\Desktop\Kicad\pcbqa
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

`kicad-cli` otomatik bulunur (PATH → `C:\Program Files\KiCad\*\bin`). Gerekirse:

```powershell
$env:PCBQA_KICAD_CLI = "C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
```

## Kullanım

```powershell
# Demo proje üzerinde
.\.venv\Scripts\python -m pcbqa samples\pic_programmer

# Kendi projeniz + kendi kurallarınız + JSON çıktı
.\.venv\Scripts\python -m pcbqa C:\yol\projem --rules rules.yaml --json rapor.json
```

Ya da kısayol: `run.cmd samples\pic_programmer`

## Aşama 5: makine öğrenimi altyapısı

Aşama 3'ün dersi "yerleştirici, hakemin puanladığı şeyi optimize etmeli"ydi.
Aşama 5 sıradaki soruyu sorar: hakemin ölçümü **doğru ama pahalı** (60
bileşenli kartta 2 ms, `pic_programmer`da 6 ms, `jetson` gibi kartlarda çok
daha fazla — `auto`nun süre bütçesini aşmasının sebebi bu). Yerel arama saniyede
binlerce aday dener; bunların hangisinin denemeye değer olduğunu **öğrenilmiş
bir model** söyleyebilir mi?

```powershell
# 1) Gerçek hakemle etiketlenmiş veri topla
.\.venv\Scripts\python -m pcbqa.ml.collect --suite "C:\Program Files\KiCad\10.0\share\kicad\demos" `
    --board samples\bench_bad.kicad_pcb --rules pcbqa\default_rules.yaml `
    --out .work\moves.jsonl --budget 25

# 2) Modelleri eğit ve KARŞILAŞTIR (mean = taban çizgisi, identity'nin ML karşılığı)
.\.venv\Scripts\python -m pcbqa.ml.train .work\moves.jsonl --model all --target all --cv 5 `
    --out pcbqa\ml\models\move-v1.json

# 3) Öğrenilmiş sıralamayla yerleştir
.\.venv\Scripts\python -m pcbqa.harness --placer auto --placer learned --board samples\bench_bad.kicad_pcb
```

### Model karar vermez, sıra önerir

Bu ayrım altyapının tamamını belirledi. Model yalnızca aday hamleleri
**denenme sırasına** dizer; bir hamlenin kabul edilip edilmeyeceğine hâlâ
`ctx.evaluate` (gerçek hakem) karar verir. Sonuçları:

- Model iyi çalışırsa aynı bütçede daha çok iyileşme yakalanır.
- Model **tamamen yanılırsa** sonuç sadece biraz yavaşlar; skor düşemez.
- Bozuk/eski bir model dosyası aramayı durduramaz — sıralayıcı patlarsa
  arama kendi sırasıyla devam eder.

Testlerde bu bilerek zorlanıyor: kasten **en kötü hamleyi başa alan** bir
sıralayıcıyla ve her çağrıda istisna fırlatan bir sıralayıcıyla `polish`
koşturuluyor; ikisinde de sonuç başlangıçtan kötü çıkmıyor.

### Ölçülen şey: kaç değerlendirmede ilk iyileşmeyi buluyoruz

R² değil. Yerel arama ilk iyileştiren hamleyi kabul ettiği için asıl soru
"skoru artıran hamleye kaçıncı denemede ulaşıldığı". Taban, cilanın **bugün**
kullandığı sıra. 21 karttan toplanan 49.699 örnekte, kart bazlı 5 katlı çapraz
doğrulama:

| model | hedef | ikili doğruluk | skor hızlanması |
|---|---|---|---|
| mean (taban) | — | 0.500 | 1.00x |
| ridge | sign | **0.714** | **1.56x** |
| gbt | score | 0.581 | 1.53x |
| ridge | score | 0.691 | 1.51x |
| gbt | value | 0.698 | 1.36x |
| ridge | value | 0.695 | 1.34x |

Yani öğrenilecek gerçek bir sinyal var: model, skoru artıran hamleyi ortalama
2.8 yerine ~1.4 denemede buluyor.

### Uçtan uca sonuç: `learned` şu an `auto`yu geçmiyor

Dürüst tablo şu: sıralama kazancı yerleştirme **kalitesine** yansımıyor.
Modelin hiç görmediği dört kartta (eğitim kümesinden çıkarılarak), 5 sn bütçe:

| kart | önce | `auto` | `learned` |
|---|---|---|---|
| pic_programmer | 45 | 94 | 94 |
| complex_hierarchy | 54 | 94 | 94 |
| sonde xilinx | 73 | 100 | 100 |
| interf_u | 5 | 12–14 | 12–15 |
| jetson (1125 bileşen, 60 sn) | 93 | 93.3 | 93.3 |

`interf_u` satırındaki oynama üç tekrarda `auto` için de aynı aralıkta çıkıyor
— duvar saati bütçesinden gelen gürültü, model etkisi değil. Sebep basit:
bu bütçelerde `auto` zaten doyuma ulaşıyor, sıralamayı hızlandırmak
ulaşılabilir tavanı yükseltmiyor. `learned` bu yüzden `force`/`anneal` gibi bir
**araştırma yerleştiricisi** olarak duruyor; üretim yerleştiricisi hâlâ `auto`.

### Yol boyunca bulunan iki gerçek problem

**1. Etiket seçimi model seçiminden daha önemli.** İlk model `sign` hedefiyle
(“hakemi mutlu eder mi”) eğitildi ve `complex_hierarchy`yi 94 → 81 **düşürdü**
— üstelik HPWL'i iyileştirerek (1680 → 1594). Sebep veri kümesinde görünüyor:
etiketi pozitif olan hamlelerin **%81'i skoru hiç değiştirmiyor**, yalnızca
teli birkaç mm kısaltıyor. Model bunları öğrenip cilayı mikro HPWL
kazançlarına yönlendirdi, hakemin saydığı hatalar açık kaldı. Kural: modele
neyi sıralamasını istiyorsak etiket **tam olarak o** olmalı (`--target score`).

**2. Her sıra bilgisiz değildir.** Onarım aşamasında hamleler zaten anlamlı bir
sırada üretiliyor: yarıçap artan, yani "en küçük yer değiştirme önce". Bu
muhafazakâr sıra komşu kısıtları bozmadığı için değerlidir; modelin "tek başına
en çok iyileştiren" hamlesi ise büyük sıçramalar seçip başka bulguları
açıyordu. Sıralayıcı bu yüzden **yalnızca ince ayar aşamasında** devreye
giriyor — orada sıra bugün zaten `rng.shuffle` ile rastgele, yani kaybedilecek
bilgi yok. Bu kısıtlamadan sonra dört model varyantının hiçbiri gerileme
yapmadı.

### Öznitelikler neden yerel

75 öznitelik var (şema v3) ve hepsi tek bir bileşenin **kendi netleri ve yakın
komşularıyla** hesaplanıyor; maliyet kartın büyüklüğüne değil bileşenin
derecesine bağlı. Ölçüldü:

| kart | bileşen | öznitelik | tam değerlendirme | oran |
|---|---|---|---|---|
| bench_bad | 18 | 32 µs | 2.09 ms | 65x |
| pic_programmer | 63 | 72 µs (v1) · 134 µs (v3) | 6.12 ms | 85x · 45x |

Şema v3 bulgunun **kendisini** de taşıyor: kural tipi, `(ölçülen − limit)/limit`
boşluğu ve — `proximity` için — hamleden sonraki ölçümün **birebir yeniden
hesabı**. `proximity` pin-pin mesafesi ölçtüğü için bileşen merkezi yaklaşımı
tam da kuralın karar verdiği eşiğin çevresinde yanılıyordu (SOIC-20'de bir pin
merkeze 5 mm uzakta olabilir). Ayrıntı: HANDOFF §14.

Yerel hesabın sessizce yanlış olmaması kritik — model o zaman sağlam veriyle
eğitildiğini sanır. Bu yüzden `d_hpwl` özniteliği testlerde **tam yeniden
hesaplamayla** karşılaştırılıyor.

### Bağımlılık yok

`numpy`/`scikit-learn` eklenmedi. Ridge regresyon (normal denklemler +
Cholesky) ve gradyan artırmalı ağaçlar (histogram tabanlı) saf Python;
problem boyutu (~50 öznitelik, ~50 bin satır) bunun için fazlasıyla küçük ve
proje `sexpr.py`den beri bağımlılıksız kalmayı tercih ediyor. Modeller
**JSON** olarak saklanıyor: git diff'i okunabilir, Python sürümleri arasında
taşınabilir, ve içinde çalıştırılabilir kod olmadığı için başkasından gelen bir
model dosyasını açmak güvenlik sorunu değil.

## Aşama 4a/4b: şematik okuma ve netlist kalkanı

KiCad 10'da IPC API'si yalnızca PCB editöründe var. Ama şematiği **okumak**
için IPC'ye gerek yok: `.kicad_sch` da s-expression. `pcbqa.schematic` onu
doğrudan okur — hiyerarşik alt sayfalar dahil.

```python
from pcbqa.schematic import read_schematic

sch = read_schematic("proje/proje.kicad_sch")   # alt sayfalara kendi iner
sch.stats()          # {'dosya': 2, 'sayfa': 2, 'sembol': 124, ...}
r1 = sch.by_ref("R1")
r1.pins              # sayfa koordinatına çözülmüş pinler
r1.bbox              # gövde sınır kutusu
```

Analiz raporuna `SEMATIK` bölümü olarak da yansır (`python -m pcbqa <proje>`)
ve dört yapısal kontrol ekler: eksik alt sayfa dosyası, ızgara dışı sembol,
footprint'i atanmamış bileşen, gövdeleri çakışan semboller.

### Pin konumu: deneysel olarak doğrulanmış dönüşüm

Kütüphane sembolünde Y **yukarı**, sayfada Y **aşağı** bakar; sembol ayrıca
döndürülmüş ve aynalanmış olabilir. Doğru dönüşüm tahminle değil, KiCad'in 19
demo projesinin tamamında ölçülerek seçildi:

| | örtüşme |
|---|---|
| `(px·cos − py·sin, −px·sin − py·cos)` | **%93.5** |
| rakip hipotez | %37.8 |
| ayna **rotasyondan sonra** | **%94.9** |
| ayna rotasyondan önce | %27.0 |

Okuyucu 19 projede, **17.088 pin** üzerinde doğrulandı: pinlerin **%98.7'si**
bir çapaya oturuyor, projelerin çoğunda %100, bozuk parantez 0.

> Çapa yalnızca tel ucu değildir. Bir pin junction'a, no-connect'e, etikete
> veya **doğrudan başka bir sembolün pinine** de değebilir — güç sembolleri
> (GND, VCC) çoğu zaman telsiz, doğrudan IC pinine yapışır. Dar bir ölçüt
> bunları "kaçan pin" sanar.

### Netlist değişmezliği kalkanı

Şematikte bağlantı **geometriktir**: tel ucu pine değiyorsa bağlıdır. PCB'de
durum farklı — orada net, pad'in içinde ismiyle yazılıdır. Sonuç: bir sembolü
şematikte kaydırmak bağlantıyı **sessizce** koparır.

Ölçüldü: `pic_programmer` üzerinde R1 kaydırıldığında pin 2 koptu ve netlist'te
`unconnected-(R1-Pad2)` olarak belirdi. Hiçbir hata, hiçbir uyarı. **Tek ızgara
adımı (1.27 mm) bile yetiyor.**

```python
from pcbqa.sch_verify import verify_unchanged

diff = verify_unchanged(onceki_sch, sonraki_sch)
if not diff.ok:
    print(diff.describe())    # "BAGLANTI DEGISTI: 7 pin baska aga tasindi"
    for satir in diff.details():
        print(satir)
```

Doğru değişmez, ham XML değil **pinlerin ağlara bölünüşüdür**. Net kodları her
ihracatta yeniden numaralanır ve otomatik net adları (`Net-(R1-Pad1)`)
konuma göre değişir; bunlar gerçek bağlantı değişikliği değildir. Bölünme aynı
kaldığı sürece devre elektriksel olarak aynıdır.

Bu kalkan, şematiğe yazma (Aşama 4c/4d) için ön koşuldur: yazma öncesi/sonrası
karşılaştırılır, `ok=False` ise yazma reddedilir.

## Aşama 4e: şematik yerleştirme kalitesi

Aşama 3'te PCB için kurulan mimari şematiğe olduğu gibi taşındı: yerleştirici
vekil bir maliyet uydurmaz, **hakemin gerçek ölçütünü** optimize eder ve sonuç
hiçbir zaman başlangıçtan kötü olamaz. `refine.polish` değiştirilmeden
kullanılır; değişen tek şey değerlendiricidir.

```powershell
# Bir sayfayı iyileştir (dry-run), sonra uygula
.\.venv\Scripts\python -m pcbqa.sch_apply --sch proje\proje.kicad_sch --budget 20
.\.venv\Scripts\python -m pcbqa.sch_apply --sch proje\proje.kicad_sch --budget 20 --apply

# Alt sayfa
.\.venv\Scripts\python -m pcbqa.sch_apply --sch proje\proje.kicad_sch --sheet /guc --apply
```

### İki hızlı, bir yavaş ölçüt

Kalkan her çağrıda `kicad-cli` çalıştırır (2-4 sn); yerel arama binlerce aday
dener. Bu yüzden ölçüt ikiye ayrıldı:

| | ne zaman | ne kadar sürer |
|---|---|---|
| Geometrik ölçüt (bellek-içi) | her adayda | **~0.4 ms** → 20 sn'de ~47.000 deneme |
| Netlist kalkanı | yalnızca yazmadan önce, **bir kez** | 2-4 sn |

Geometrik ölçüt bağlantı riskini de taşır: taşınan bir pin **kendisine ait
olmayan** bir çapaya (başka bir telin ucu, başka bir sembolün pini) oturursa
iki net birleşir. Bu, kalkanın yakaladığı hatanın ucuz vekili olduğu için arama
zaten oraya gitmez; kalkan son söz olarak kalır.

Ölçülen: `pic_programmer` kök sayfası 985.5 → 976.6 mm, skor 100'de sabit,
0 hata. Daha dağınık sayfalarda kazanç çok daha büyük (`video/RAMS` %21,
`vme-wren` kök sayfası %17).

### Bus içeren sayfalar: varsayılan olarak kapalı

Ucuz ölçüt bus bağlantılarını modelleyemiyor. `vme-wren/vme_p1_p2` sayfasında
(137 bus, 262 bus girişi) optimizasyon "skor 100, 0 hata, tel %60 kısaldı"
dedi; gerçek kalkan **257 pinin ağ değiştirdiğini** gösterdi ve yazma
reddedildi. Sistem güvenliydi ama ölçüm yanıltıcıydı.

Bu yüzden bus içeren sayfalarda optimizasyon kapalıdır. `allow_buses=True`
ile açılabilir — kalkan yine son söz olarak çalışır.

### Toplu uygulama

`sch_move` tek sembol taşır ve her çağrıda kalkanı çalıştırır — 30 sembol için
dakikalar. `sch_apply` tersini yapar: **tüm** taşımaları ağaç üzerinde uygular,
kalkanı **bir kez** çalıştırır, dosyayı **bir kez** yazar.

Bir nokta iki taşınan sembolün pinine denk gelip deltaları farklıysa, o noktayı
nereye götüreceğimiz belirsizdir — çatışma sayılır ve uygulama reddedilir.

### Sembol kimliği: UUID, referans değil

Çok birimli bir bileşenin (ör. 74LS125'in dört kapısı) her birimi ayrı bir
`symbol` düğümüdür ve **hepsi aynı referansı taşır**. Referansla anahtarlamak
dördünü tek girdiye çökertip "U2 ve U2 çakışıyor" gibi hayali bulgular
üretiyordu. Yerleştirme sözleşmesi bu yüzden `{sembol_uuid: (x, y)}`.

Yalnızca **öteleme**. Rotasyon ve ayna desteklenmiyor: pin konumları dönünce
tel uçları tek bir delta ile taşınamaz.

## Aşama 4c/4d: şematiğe yazma ve bağlantı koruyan taşıma

Bir sembolü kaydırıp bırakmak, pinlerine değen tel uçlarını yerinde bırakır ve
bağlantı **sessizce** kopar. `pcbqa.sch_move` sembolü taşırken ona tutunan her
şeyi birlikte taşır: tel uçları, junction ve no-connect işaretleri, etiketler,
sembolün kendi metin alanları.

```powershell
# Dry-run (varsayılan): ne olacağını söyler, dosyaya dokunmaz
.\.venv\Scripts\python -m pcbqa.sch_move --sch proje\proje.kicad_sch --ref R1 --dx 2.54 --dy 0

# Gerçekten yaz
.\.venv\Scripts\python -m pcbqa.sch_move --sch proje\proje.kicad_sch --ref R1 --dx 2.54 --dy 0 --apply
```

Çıktı:

```
  R1: (78.74, 43.18) -> (81.28, 43.18)  [tel ucu 2, junction 0, no-connect 0, etiket 0, property 5]
  KALKAN: baglanti degismedi
  UYGULANDI: 230,132 bayt yazildi
  yedek: pic_programmer.kicad_sch.pcbqa-bak
```

Hiyerarşide sembol hangi alt sayfadaysa **o dosya** düzenlenir; kök dosyaya
dokunulmaz.

### Üç katmanlı koruma

**1. Geometrik engel.** İki sembolün pini araya tel girmeden birbirine
değiyorsa (güç sembolleri çoğunlukla böyle bağlanır), uzatılacak tel yoktur ve
taşıma reddedilir:

```
  ENGEL: #PWR022 pini J1.5 ile dogrudan temas halinde (43.18, 101.6);
         arada tel yok, tasima baglantiyi koparir
```

**2. Netlist kalkanı.** Geometri her şeyi göremez. Taşınan bir tel ucu başka
bir netin üstüne oturabilir. Değişiklik önce bir kum havuzunda uygulanır ve
netlist karşılaştırılır:

```
  KALKAN: BAGLANTI DEGISTI: 15 pin baska aga tasindi
    J1.3: '/VPP_ON' (3 pin) -> 'VCC' (15 pin)
  tasima yapilmadi - baglanti bozulurdu
```

Bu örnek gerçek: `--apply` verilmiş olmasına rağmen dosyaya dokunulmadı.

**3. Atomik yazma.** IPC şematikte çalışmadığı için "editöre uygula, undo ile
geri al" seçeneği yok — yazma doğrudan dosyaya. Bu yüzden:

- geçici dosya **aynı dizine** yazılır → `fsync` → `os.replace` (Windows'ta da
  atomik; ayrı birimler arasında atomiklik garanti edilmez, o yüzden aynı dizin)
- yazmadan önce **yedek** alınır
- proje KiCad'de açıksa (`~<proje>.kicad_pro.lck`) yazma **reddedilir** —
  Eeschema dosyayı bellekte tutar, kullanıcı kaydederse değişikliğimiz kaybolur
- **UUID'ler asla yeniden üretilmez**; KiCad sembol örneklerini ve netlist
  yollarını onlarla izler

### Bayraklar

| Bayrak | Açıklama |
|---|---|
| `--apply` | Gerçekten yaz (varsayılan dry-run) |
| `--sheet` | Sembol birden fazla sayfadaysa sayfa yolu |
| `--no-snap` | 1.27 mm ızgaraya oturtma |
| `--no-verify` | Netlist kalkanını atla (**önerilmez**) |
| `--no-backup` | Yedek alma |
| `--force` | Engelleri ve kalkan reddini yok say |
| `--allow-open-project` | KiCad açıkken de yaz |

Izgaraya oturtma kaydırma miktarını değiştirir; tel uçları **aynı** miktarda
kaydırılır, yoksa pinden kopar.

Çıkış kodları: `0` başarılı · `1` engel/kalkan reddi · `2` araç hatası.

## Aşama 3: otomatik yerleştirme (`auto`)

`auto` üretim yerleştiricisidir. Üç katmandan oluşur:

1. **Kaba yerleşim** — `cluster` ile sıfırdan bir aday üretilir.
2. **Cila** — `refine.polish` hakemin **gerçek puanını** optimize eder.
   Hamleler doğrudan bulgulardan üretilir: "C1, U2.14'ten 33 mm uzakta"
   bulgusu, C1'i U2 çevresinde limitin içindeki halkalara taşımayı dener ve
   yalnızca ölçüm iyileşirse kabul eder.
3. **Gerileme tabanı** — kartın **mevcut hali** de bir aday olarak yarışır.

3. madde tasarım gereğidir: `auto` hiçbir kartı mevcut halinden kötü yapamaz.
Aynı koruma hakemde (`best_result`) ve IPC yazma yolunda (`select_winner`) da
vardır — skoru düşüren bir yerleştirme karta **hiçbir zaman** yazılmaz;
böyle bir durumda araç hata verip karta dokunmaz.

```powershell
# Tek kartta
.\.venv\Scripts\python -m pcbqa.harness --placer auto

# Yarışma: auto'yu diğer motorlarla karşılaştır
.\.venv\Scripts\python -m pcbqa.harness --all

# Regresyon paketi: bir klasördeki TÜM kartlarda koştur
.\.venv\Scripts\python -m pcbqa.harness --placer auto --budget 15 `
  --suite "C:\Program Files\KiCad\10.0\share\kicad\demos" `
  --rules pcbqa\default_rules.yaml
```

`--suite` herhangi bir kartta gerileme bulursa çıkış kodu `1` verir; tek kartta
iyi sonuç almak yetmez, sentetik tezgâha aşırı uyum tam olarak böyle yakalanır.

### Kendi yerleştiricinizi yazarken

`ctx.evaluate(placement)` hakemin gerçek ölçümünü döndürür (60 bileşenli kartta
~5 ms, yani 30 saniyelik bütçede binlerce deneme). Vekil bir maliyet
fonksiyonu uydurmak yerine bunu optimize edin — Aşama 3'te gerçek kartlardaki
gerilemelerin sebebi tam olarak bu ikisinin ayrışmasıydı.

## Aşama 2: IPC ile KiCad'e placement uygulama

Yerleştirme motorları `ref -> (x_mm, y_mm, rot_deg)` sözleşmesiyle ham placement
üretir. `pcbqa.ipc_apply` bu çıktıyı çalışan KiCad PCB Editor oturumuna yazar.
Varsayılan mod **dry-run**'dır; KiCad'e gerçek yazma için `--apply` açıkça
verilmelidir.

Önce KiCad'de aynı `.kicad_pcb` dosyasını açın ve Preferences > Plugins altında
IPC API'nin etkin olduğundan emin olun.

```powershell
# Yarışmayı çalıştır, kazananı seç, aktif KiCad kartına yazmadan doğrula
.\.venv\Scripts\python -m pcbqa.ipc_apply --board samples\bench_bad.kicad_pcb --no-color

# Kazanan placement'ı tek undo adımı olarak çalışan KiCad'e uygula
.\.venv\Scripts\python -m pcbqa.ipc_apply --board samples\bench_bad.kicad_pcb --apply --no-color

# Uygulamadan sonra KiCad kartını da kaydet
.\.venv\Scripts\python -m pcbqa.ipc_apply --board samples\bench_bad.kicad_pcb --apply --save

# Kazanan ham placement çıktısını kaydet; sonra aynı çıktıyı tekrar uygula
.\.venv\Scripts\python -m pcbqa.ipc_apply --write-placement-json .work\winner-placement.json
.\.venv\Scripts\python -m pcbqa.ipc_apply --placement-json .work\winner-placement.json --apply
```

Güvenlik davranışı:

- aktif KiCad kart adı `--board` dosya adıyla uyuşmazsa durur;
  bilinçli uygulama için `--allow-board-mismatch` gerekir.
- harness'in kilitli saydığı konnektör/montaj deliği referanslarını taşımaz.
- KiCad'de kilitli footprint'leri de taşımaz; gerekirse `--ignore-kicad-locks`.
- değişiklikleri `begin_commit` / `push_commit` ile tek undo adımı yapar.

### Seçenekler

| Bayrak | Açıklama |
|---|---|
| `--rules PATH` | YAML kural dosyası (varsayılan: cwd'deki `rules.yaml`, yoksa paketle gelen) |
| `--json PATH` | Raporu JSON olarak da yazar (CI / ileri işleme için) |
| `--no-kicad-checks` | ERC/DRC'yi atlar, sadece kendi kurallarımız çalışır (daha hızlı) |
| `--work-dir PATH` | Ara dosyaları (netlist.xml, erc.json, drc.json) saklar |
| `--fail-on` | `error` (varsayılan) / `warning` / `none` — çıkış kodunu belirler |
| `--kicad-cli PATH` | kicad-cli yolunu elle verir |

Çıkış kodları: `0` temiz · `1` eşiği aşan bulgu var · `2` araç hatası.

## Kurallar

Kurallar YAML ile tanımlanır, kod değiştirmek gerekmez. On dört tip var:

| Tip | Alan | Ne kontrol eder |
|---|---|---|
| `proximity` | güç / niyet | Bir pine, aynı nette belirli bir bileşen N mm'den yakın mı |
| `require_on_net` | niyet | Ada uyan her nette belirli türde bir bileşen var mı |
| `same_net` | niyet | Belirtilen pinler aynı nette mi |
| `net_length` | sinyal | Netin tahmini uzunluğu (HPWL) bütçeyi aşıyor mu |
| `length_match` | sinyal | Bir grup netin uzunluğu birbirine yakın mı (diferansiyel çift) |
| `keep_apart` | yerleşim | İki bileşen kümesi arasında **en az** N mm var mı |
| `courtyard_overlap` | üretim | Bileşenler çakışıyor mu, aralarında montaj boşluğu var mı |
| `edge_clearance` | üretim | Bileşenler kart kenarından yeterince içeride mi |
| `trace_width` | bakır | İz genişliği akımı taşımaya yetiyor mu (IPC-2221B) |
| `via_current` | bakır | Netteki via'lar akımı taşıyabiliyor mu |
| `clearance_voltage` | bakır | İki net arası açıklık gerilim farkına yetiyor mu |
| `copper_area` | bakır | Bir netin toplam bakır alanı aralıkta mı (SW alanı, termal) |
| `component_value` | devre | Bileşen **değeri** hesaplanan aralıkta mı |
| `buck_layout` | alt-devre | Regülatör yerleşimi — bileşenleri **topolojiden** bulur |

`trace_width` / `via_current` / `clearance_voltage` **yalnızca yönlendirilmiş
kartlarda** çalışır; yerleştirme aşamasında (kartta bakır yokken) sessizce
atlanırlar.

### `buck_layout` — ad değil topoloji

Diğer kurallar bileşeni **net adından** bulur (`net: "^(FB|VFB)$"`). Gerçek
kartlarda bu yetmiyor: KiCad geri besleme netini `Net-(U2-FB{slash}VSET)` diye
otomatik adlandırıyor ve hiçbir desen tutmuyor. Ama IC'nin **pin adı** "FB/VSET"
olarak duruyor.

`pcbqa/subcircuit.py` regülatörü topolojiden bulur — imza: bir IC'nin SW pini +
o nette bir indüktör — ve rolleri çıkarır (CIN, COUT, indüktör, FB dirençleri).
`buck_layout` ROHM'un kontrol listesini bu rollere karşı çalıştırır.

Gerçek KiCad demo kartlarında ölçüldü:

| kart | ad desenli | topolojik |
|---|---|---|
| CM5_MINIMA_3 | 19 bulgu, skor 19.0 | **1 bulgu, 85.2** |
| One-Air-Max | 32 bulgu, skor 20.4 | **4 bulgu, 70.3** |
| jetson | — | **0 bulgu, 100.0** |

Bulgular parçayı adıyla söylüyor: *"U702 (buck): indüktör L701 SW pininden
4.32 mm uzakta (ROHM: <= 4 mm)"*.

`keep_apart`, `proximity`nin tersidir ve gerçek bir boşluğu kapatır: üretici
kurallarının şaşırtıcı bir kısmı "yaklaştır" değil **"uzaklaştır"** der —
FB izi → indüktör ≥ 10 mm (ROHM), I2C pull-up → sıcaklık sensörü ≥ 10 mm (TI).
Yalnızca mesafe küçültmeye çalışan bir yerleştirici bunları sessizce ihlal eder.

```yaml
rules:
  - id: decoupling-mesafe
    type: proximity
    severity: error
    pin:     { kind: ic, pintype: power_in }
    partner: { kind: capacitor }
    max_distance_mm: 10
    exclusive: true        # her kondansatör en fazla bir pine sayılır

  - id: veri-hatti-pullup
    type: require_on_net
    net: "(SDA|SCL)"
    partner: { kind: resistor }

  - id: guc-raylari-ortak
    type: same_net
    severity: error
    pins: ["U1.8", "U5.14", "U6.1"]

  - id: usb-cift
    type: length_match
    groups: [["USB_DP", "USB_DM"]]
    tolerance_mm: 3

  - id: courtyard-cakisma
    type: courtyard_overlap
    clearance_mm: 0.2

  - id: kart-kenari
    type: edge_clearance
    min_distance_mm: 2.0
    ignore_refs: ["^J", "^MH"]   # konnektörler kasten kenardadır

  - id: guc-izi-genisligi
    type: trace_width
    net: "^(VIN|VBUS|VOUT)$"
    current_a: 2.0
    delta_t_c: 10                # varsayılan 10 °C sıcaklık artışı
    copper_oz: 1.0
    method: ipc2221              # ya da mm_per_amp (ROHM'un 1 mm/A kuralı)

  - id: guc-via-sayisi
    type: via_current
    net: "^VBUS$"
    current_a: 2.0

  - id: gerilim-acikligi
    type: clearance_voltage
    class: B2                    # B1 iç / B2 dış kaplamasız / B4 kaplamalı
    voltages:
      "^HV_": 400
      "^VBUS$": 5

  - id: pullup-sensorden-uzak
    type: keep_apart
    a: { kind: resistor }
    b: { kind: ic, ref: "^TMP" }
    min_distance_mm: 10.0
```

### Hazır kural kütüphanesi ve `include`

`pcbqa/presets/` altında, üretici app-note'larından ve IPC/IEC standartlarından
toplanmış eşikleri taşıyan dört ön ayar var. Kendi kural dosyanızdan dahil edin:

```yaml
include:
  - presets/uretim.rules.yaml      # her tasarımda geçerli, uyarlama gerekmez
  - presets/buck.rules.yaml        # tasarımda buck converter varsa
rules:
  - id: kendi-kuralim
    ...
```

| Ön ayar | İçerik |
|---|---|
| `uretim.rules.yaml` | courtyard (IPC-7351B), kart kenarı, fab min. iz, gerilim açıklığı |
| `buck.rules.yaml` | CIN/SW/FB/COUT mesafeleri, güç izi genişliği, via sayısı |
| `lineer-koruma.rules.yaml` | LDO, motor sürücü, ESD/TVS, sensör |
| `yuksek-hiz.rules.yaml` | decoupling (λ/40), kristal, I2C, diferansiyel çiftler |

Yollar dahil eden dosyaya göre çözülür; dairesel `include` ve tekrar eden kural
`id`'si hata verir. `uretim` ön ayarı devre tipinden bağımsızdır ve sağlam bir
gerçek kartta sıfır bulgu üretir (testle korunuyor).

Eşiklerin **hepsinin kaynağı yazılı**, kaynağı olmayanlar "mühendislik seçimi"
diye etiketli. Ayrıntı, çelişkiler ve ölçülemeyenler:
[docs/tasarim-kurallari/](docs/tasarim-kurallari/README.md).

### `exclusive` neden önemli?

`proximity` kuralında `exclusive: false` (varsayılan) iken 3V3 gibi geniş bir
rayda **tek bir kondansatör bütün güç pinlerini "tatmin eder"** — eksik
decoupling görünmez olur. `exclusive: true` ile her kondansatör en fazla bir
pine sayılır (en yakından başlayarak eşleme yapılır), yani "her güç pininin
kendi kondansatörü olmalı" beklentisi gerçekten test edilir.

Mevcut tasarımlarda çok bulgu üretebilir; kademeli geçiş için önce `false`
ile deneyin.

**Seçici alanları** (`pin` / `partner`):

- `ref` — referans üzerinde düzenli ifade (`"^U"`)
- `kind` — `ic`, `capacitor`, `resistor`, `inductor`, `diode`, `transistor`,
  `crystal`, `connector`, `switch`, `fuse`, `testpoint`, `other`
- `value` — değer üzerinde düzenli ifade (`"100n"`)
- `pintype` — KiCad pin tipi: `power_in`, `input`, `output`, `bidirectional`, `passive`…
- `function` — pin adı üzerinde düzenli ifade (`"V(CC|DD)"`)

`defaults.ignore_nets` ile toprak/güç netleri tüm kurallarda atlanır (poligon
döküm yapılan netlerde mesafe ölçümü anlamsızdır).

## HPWL nedir?

*Half-Perimeter Wire Length* — bir netin tüm pinlerini saran en küçük
dikdörtgenin genişlik + yükseklik toplamı. Yönlendirme yapılmadan önce gerçek
bakır uzunluğunu tahmin etmenin endüstri standardı yoludur: hızlı ve yeterince
doğru. **Aşama 3'teki otomatik yerleştirme motorunun küçülteceği ana büyüklük
budur.**

## Skor nasıl hesaplanır?

```
ceza  = Σ bulgu_cezası
skor  = 100 × e^(−ceza / bileşen_sayısı)
```

Bir bulgunun cezası, kuralı `weight` belirtmişse odur; belirtmemişse
severity'den türetilir — **hata 8, uyarı 2, bilgi 0**.

Ceza bileşen sayısına bölündüğü için 40 bileşenli bir kartla 400 bileşenli bir
kartın skorları karşılaştırılabilir. Üstel eğri sayesinde skor tam 0'a doymaz —
25 hatalı kart ile 60 hatalı kart hâlâ ayırt edilebilir.

### Kural bazlı ağırlık

```yaml
- id: sicak-dongu-alani
  type: keep_apart
  severity: error
  weight: 24.0        # bu kuralın her bulgusu 24 puan yer
```

**Neden gerekli:** severity tek başına yeterli değil. Ölçülmüş etkisi olan bir
kural (TI AN-2155'in sıcak döngü deneyi: 6 → 18 mm² alanda EMI marjı 1.6 dB
kayıp) ile kaynaksız bir mühendislik seçimi aynı 8 puanı yiyordu.

- `weight` **verilmezse** eski davranış birebir korunur; ağırlık kullanmayan
  kural dosyaları aynı skoru üretir.
- `weight: 0` → kural raporda görünür ama skoru etkilemez.
- Yüksek ağırlıklı bir **uyarı**, varsayılan bir **hatayı** geçebilir. Bu
  bilinçlidir: severity "ne kadar acil", ağırlık "ne kadar önemli" demektir.
- `info` bulguları **her zaman** sıfırdır, kuralın ağırlığı ne olursa olsun.
  Somut nedeni: `max_findings` sınırına takılan kural sentetik bir bilgi
  bulgusu üretir, `trace_width` de yönlendirilmemiş net için bilgi verir —
  ağırlık bunlara uygulansaydı ağırlığı 24 olan bir kural hiçbir ihlal olmadan
  24 puan yazdırırdı.

### Orantılı ceza

İhlalin *ne kadar* büyük olduğu da cezaya yansıyabilir:

```yaml
- id: guc-izi-genisligi
  type: trace_width
  weight: 12.0
  scale: true       # varsayılan false
  scale_max: 3.0    # çarpan tavanı, varsayılan 3.0
```

```
aşım   = |measured − limit| / |limit|
çarpan = min(1 + aşım, scale_max)
ceza   = weight × çarpan
```

Mutlak değer bilinçli: bazı kurallarda ihlal `measured > limit` (net uzunluğu),
bazılarında `measured < limit` (iz genişliği). Tek ifade ikisini de doğru ölçer.

Üç durumda ölçekleme **yapılmaz** (çarpan 1.0):

- kural `scale` istememiş,
- bulgu `measured`/`limit` taşımıyor — `require_on_net` ve `same_net` ikili
  kurallardır, "ne kadar ihlal" diye bir şey yoktur; `scale: true` verilse bile
  sessizce sabit ağırlığa düşer,
- `limit == 0` — `courtyard_overlap`'te `clearance_mm: 0.0` yaygındır.

**Tavan neden şart:** `via_current`'ta kapasite sıfıra yaklaşırsa oran patlar ve
tek bir bulgu bütün skoru yutar.

**Ölçüldü (2026-08-28):** Tezgah kartlarında ve `pic_programmer`da tüm kurallar
`scale: true` yapılıp `auto` yeniden koşuldu; **yerleştirmede gerileme yok**,
sonuçlar birebir aynı. Beklenen bir sonuç: ölçekleme *monotondur* — aynı bulgu
kümesi için skor karşılaştırmasının işaretini değiştirmez, yalnızca büyüklüğünü.
Sıralama ancak farklı bulgu kümeleri karşılaştırılırken (sayı ile büyüklük takas
edilirken) değişir.

Ağırlıkların kanıt gücüne göre nasıl seçileceği ve sıradaki adımlar:
[docs/yol-haritasi-skorlama.md](docs/yol-haritasi-skorlama.md).

Bu skor bilinçli olarak geçicidir. Aşama 3'te otomatik yerleştirme motorunun
küçülteceği **maliyet fonksiyonuna** dönüşecek; o yüzden ürettiği ara değerler
(HPWL, mesafe ihlalleri) ölçülebilir tutuluyor.

## Sentetik test tezgâhı

Yerleştirme motorunu (Aşama 3) geliştirmek için **kötü** bir karta ihtiyaç var —
temiz bir kartta optimize edilecek bir şey yoktur. `pcbqa.synth` aynı devreden
iki kart üretir:

```powershell
.\.venv\Scripts\python -m pcbqa.synth --out samples
```

| Kart | Ne | Skor |
|---|---|---|
| `bench_good.kicad_pcb` | Makul yerleşim — **hedef** | 67 / 100 |
| `bench_bad.kicad_pcb` | Kasıtlı kusurlu yerleşim — motorun düzelteceği kart | 2 / 100 |

Devre küçük bir MCU kartı: regülatör + MCU + EEPROM + kristal + USB. Devrenin
"doğru cevabı" `synth.py` içinde tanımlı — hangi kondansatörün hangi IC'ye ait
olduğunu, hangi netlerin diferansiyel çift olduğunu kod belirliyor. Yani
kuralların gerçekten doğru şeyi yakalayıp yakalamadığı kanıtlanabiliyor.

`bench_bad`'e ekilen 7 kusurun tamamı **taşınabilir** bileşenlerde: 4 uzak
decoupling/yük kondansatörü, 2 courtyard çakışması, bozuk USB çift simetrisi.
Kilitli bileşenlere (J1/J2 konnektörleri) kusur ekilmez — yerleştirici onları
taşıyamayacağı için düzeltilemez bir ceza olur ve ulaşılabilir tavanı
düşürürdü. Bu yüzden J1/J2 iki kartta da aynı, yasal konumda durur.

`bench_good`'un 1 hatası kasıtlıdır: `nRESET` pull-up'ı yok. Bu bir **devre**
kusuru, yerleşim kusuru değil — her iki kartta da var ve yerleştirme motoru
bunu asla düzeltemez. Motorun işi `2 → 67` mesafesini kapatmak.

```powershell
.\.venv\Scripts\python -m pcbqa samples\bench_bad.kicad_pcb --rules samples\bench.rules.yaml --no-kicad-checks
```

`--no-kicad-checks` önemli: tezgâh kartlarında **yönlendirme (track) yok**,
sadece yerleşim var. KiCad'in DRC'si o yüzden her neti "bağlanmamış" sayıp
onlarca gürültülü ihlal üretir (65 hata). Yerleşim çalışmasında bizi
ilgilendiren pcbqa'nın kendi kurallarıdır.

## Mimari

```
pcbqa/
  sexpr.py         s-expression okuyucu (bağımlılıksız, hatalı dosyalara toleranslı)
  geom.py          dışbükey kabuk, SAT çakışma testi, poligon mesafesi
  pcb.py           .kicad_pcb  -> bileşen/pad/courtyard konumları
  netlist.py       kicadxml veya doğrudan PCB -> net/pin bağlantıları
  model.py         ikisini birleştirir + ölçümler (HPWL, yoğunluk)
  rules.py         YAML kural motoru (7 kural tipi)
  kicadcli.py      kicad-cli sarmalayıcısı (netlist, ERC, DRC)
  ipc.py           kicad-python ile çalışan KiCad PCB Editor'e placement yazar
  ipc_apply.py     kazanan yerleştiriciyi seçip IPC uygulamasını koşturan CLI
  report.py        terminal raporu + skor
  synth.py         sentetik test kartı üreteci
  harness.py       yerleştiricileri koşturur, puanlar, kazanan kartı yazabilir
  schematic.py     .kicad_sch okuyucu (hiyerarşik, pin/bbox geometrisi çözülmüş)
  sch_verify.py    netlist değişmezliği kalkanı
  sch_write.py     atomik yazma + açık-proje koruması + yedek
  sch_move.py      bağlantı koruyan sembol taşıma
  sch_place.py     şematik yerleştirme optimizasyonu
  sch_apply.py     toplu uygulama (tek doğrulama, tek yazma)
  __main__.py      komut satırı
  placement/
    base.py        DONMUŞ arayüz: Placer, PlacementContext, Evaluation
    refine.py      bulgu güdümlü cila — hakemin gerçek puanını optimize eder
    auto.py        ÜRETİM yerleştiricisi: kaba + cila + gerileme tabanı
    learned.py     auto + öğrenilmiş hamle sıralaması (Aşama 5)
    repertoire.py  geniş hamle repertuarı: takas / küme taşıma (Aşama 6, opt-in)
    cluster.py / force.py / anneal.py / codex.py   yarışan motorlar
    baseline.py    identity / random (hakem doğrulaması)
  ml/              Aşama 5 — makine öğrenimi altyapısı
    features.py    DONMUŞ öznitelik şeması: tasarım + aday hamle -> vektör
    collect.py     gerçek hakemle etiketlenmiş veri kümesi üretir
    dataset.py     JSONL depolama + KART BAZLI bölme
    metrics.py     regresyon + sıralama metrikleri
    model.py       model sözleşmesi, JSON kaydet/yükle, kayıt defteri
    linear.py      ridge regresyon (saf Python)
    trees.py       gradyan artırmalı ağaçlar (saf Python)
    train.py       eğitim/karşılaştırma komut satırı
    models/        eğitilmiş modeller (JSON)
```

`ml/` içinde de aynı katmanlama var: `features.py` ve `collect.py` PCB'yi bilir,
geri kalanı bilmez. Şematik tarafı (Aşama 4e) aynı çekirdeği kullanmak
istediğinde yalnızca yeni bir `features`/`collect` çifti yazmak yetecek.

`model.py` ve `rules.py` KiCad'i **hiç bilmez** — sadece kendi veri modelini
görürler. Bu ayrım bilinçli: Aşama 3'ün yerleştirme motoru da aynı modeli
kullanacak, ve KiCad 11 şematik API'sini getirdiğinde sadece yeni bir okuyucu
eklenecek.

## Neden Aşama 0/1'de IPC API (kicad-python) değil?

Aşama 0/1'in tamamı `kicad-cli` ile çalışır. Bunun sonucu:

- KiCad'in açık olması gerekmez → CI'da / komut satırında çalışır
- IPC bindings'in alpha olmasından ve Python sürüm desteği sorunlarından etkilenmez
- Yazma işlemi olmadığı için tasarımı bozma riski sıfır

Aşama 2'de IPC sadece seçilmiş placement çıktısını çalışan PCB Editor'e
uygulamak için kullanılır; analiz ve skor modeli hâlâ KiCad'den bağımsızdır.

## Dayanıklılık

KiCad 10.0.4 ile gelen `royalblue54L_feather` demosunun `.kicad_pcb` dosyasında
349 yerde bozuk s-expression var (`(curved_edges no)filter_ratio 0.9)` — açılış
parantezi eksik). Okuyucu bu tür bozukluklarda çökmez: hatalı parantezleri
atlar, kalan üst düzey düğümleri köke bağlar ve raporda uyarı gösterir. O
dosyada 71 bileşenin tamamı yine de okunabiliyor. Katı davranış isterseniz
`sexpr.parse(text, strict=True)`.

**Döndürülmüş bileşenler.** Kapladıkları alanı eksen-hizalı sınır kutusuyla
temsil etmek ciddi yanlış alarm üretir: stickhub demosunda `U1` -135° dönük,
gerçek courtyard'ı eğik bir dikdörtgen ama sınır kutusu çok daha büyük bir kare
— yakınındaki kondansatörler o karenin köşelerine düşüyor ve "çakışıyor" gibi
görünüyorlardı. Çakışma testleri artık gerçek poligon üzerinden yapılıyor
(dışbükey kabuk + ayırıcı eksen teoremi), bu yanlış alarmlar ortadan kalktı.

**KiCad'in DRC'si her şeyi yakalamaz.** `courtyards_overlap` kontrolü proje
ayarlarından kapatılabiliyor — stickhub demosunda kapalı, o yüzden KiCad 0 ihlal
raporluyor. Aynı kartta gerçekten çakışan bileşenler var (örn. `J7` ve `J8`,
7 mm arayla yerleştirilmiş ama courtyard'ları 7.8 mm yüksek). pcbqa bu kontrolü
proje ayarlarından bağımsız yapar.

Doğrulama: KiCad'in 19 demo projesinin 17'sinde sorunsuz çalışıyor. Atlanan 2
tanesi zaten tam proje değil (PCB'si yok) ve temiz hata mesajı veriyorlar.

## Sınırlar

- Şematik **konumları** okunmuyor (KiCad 10'da IPC şematik desteği yok);
  şematikten sadece bağlantı bilgisi alınıyor.
- Courtyard poligonu **dışbükey kabuk** ile alınıyor. Dikdörtgen courtyard'lar
  için birebir doğru; nadir görülen içbükey (L/U şekilli) courtyard'larda
  güvenli tarafta kalır, yani fazladan bulgu üretebilir.
- Dairesel courtyard'larda alan bir miktar küçük çıkabilir (`fp_circle` için
  merkez + çevre noktası kullanılıyor).
- `length_match` HPWL üzerinden çalışır; gerçek uzunluk eşleme kontrolü değil,
  "bu iki net çok farklı yerlerde duruyor" ön uyarısıdır.
- Yoğunluk en yoğun **yüz** üzerinden hesaplanır (çift taraflı kartlarda iki
  yüzün alanını toplamak %100'ü aşan anlamsız sonuçlar verirdi).
- HPWL bir tahmindir; gerçek bakır uzunluğu değil. Yönlendirme öncesi
  karşılaştırma için tasarlanmıştır.
- **Geniş hamle repertuarı (`repertoire.py`) varsayılan olarak kapalı.**
  Takas/küme taşıma tel uzunluğunu iyi kısaltıyor (doymuş yerleşimde küme
  hamlelerinin %28'i hakemin sıralama anahtarını iyileştiriyor) ama kural
  bulgularını neredeyse hiç kapatmıyor (%0.3), yani skoru yükseltmiyor.
  Açmak için `ctx.allow_wide_moves = True`. Ayrıntılı ölçüm: HANDOFF §13.
- **Öğrenilmiş sıralayıcı (`learned`) uçtan uca henüz kazanç vermiyor.**
  Model sıralamayı ölçülebilir şekilde iyileştiriyor (çapraz doğrulamada
  1.56x) ama bu bütçelerde `auto` zaten doyuma ulaştığı için yerleştirme
  kalitesi değişmiyor. Üretim yerleştiricisi `auto`.
