# pcbqa — KiCad tasarım kalite analizi (Aşama 0)

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

```powershell
cd C:\Users\ardaa\OneDrive\Desktop\Kicad\pcbqa
python -m venv .venv
.\.venv\Scripts\python -m pip install pyyaml
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

Kurallar YAML ile tanımlanır, kod değiştirmek gerekmez. Yedi tip var:

| Tip | Alan | Ne kontrol eder |
|---|---|---|
| `proximity` | güç / niyet | Bir pine, aynı nette belirli bir bileşen N mm'den yakın mı |
| `require_on_net` | niyet | Ada uyan her nette belirli türde bir bileşen var mı |
| `same_net` | niyet | Belirtilen pinler aynı nette mi |
| `net_length` | sinyal | Netin tahmini uzunluğu (HPWL) bütçeyi aşıyor mu |
| `length_match` | sinyal | Bir grup netin uzunluğu birbirine yakın mı (diferansiyel çift) |
| `courtyard_overlap` | üretim | Bileşenler çakışıyor mu, aralarında montaj boşluğu var mı |
| `edge_clearance` | üretim | Bileşenler kart kenarından yeterince içeride mi |

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
```

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
ceza  = 8 × hata + 2 × uyarı
skor  = 100 × e^(−ceza / bileşen_sayısı)
```

Ceza bileşen sayısına bölündüğü için 40 bileşenli bir kartla 400 bileşenli bir
kartın skorları karşılaştırılabilir. Üstel eğri sayesinde skor tam 0'a doymaz —
25 hatalı kart ile 60 hatalı kart hâlâ ayırt edilebilir.

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
  report.py        terminal raporu + skor
  synth.py         sentetik test kartı üreteci
  __main__.py      komut satırı
```

`model.py` ve `rules.py` KiCad'i **hiç bilmez** — sadece kendi veri modelini
görürler. Bu ayrım bilinçli: Aşama 3'ün yerleştirme motoru da aynı modeli
kullanacak, ve KiCad 11 şematik API'sini getirdiğinde sadece yeni bir okuyucu
eklenecek.

## Neden IPC API (kicad-python) değil?

Aşama 0'ın tamamı `kicad-cli` ile çalışır. Bunun sonucu:

- KiCad'in açık olması gerekmez → CI'da / komut satırında çalışır
- IPC bindings'in alpha olmasından ve Python sürüm desteği sorunlarından etkilenmez
- Yazma işlemi olmadığı için tasarımı bozma riski sıfır

IPC API'ye Aşama 2'de (yerleştirme önerilerini karta uygulamak için) geçilecek.

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
