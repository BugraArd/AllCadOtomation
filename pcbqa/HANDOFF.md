# Devir Promptu — KiCad Otomasyon Projesi

> Bu dosya, projeyi yeni bir oturumda (veya başka bir asistanla) kaldığı yerden
> sürdürmek için hazırlanmış tam bağlam metnidir. Olduğu gibi kopyalayıp
> yapıştırabilirsiniz.

---

## Rolün ve hedefim

KiCad üzerinde bir otomasyon sistemi geliştiriyorum. Nihai hedef: **PCB ve
şematik üzerinde otomatik bileşen yerleştirme + kalite/uygunluk testleri.**
Özellikle "doğru pinler doğru bağlanmış mı, hem de en verimli uzaklıkta mı"
sorusunu makineye sordurmak ve zamanla her şeyi kendi yerleştiren bir sisteme
dönüştürmek istiyorum.

Proje 5 aşamaya bölündü. **Hepsi bitti (0, 1, 2, 3, 4a-4e, 5).**
**KiCad 11 beklenmedi** — şematik okuma da yazma da KiCad 10 ile çalışıyor
(bkz. §10). Aşama 5 makine öğrenimi altyapısıdır (bkz. §11); altyapı hazır ve
ölçülmüş durumda, ama öğrenilmiş yerleştirici uçtan uca henüz `auto`yu
geçmiyor — üretim yerleştiricisi hâlâ `auto`.

| Aşama | Kapsam | Durum |
|---|---|---|
| 0 | Salt-okunur analiz + rapor + ölçüm | ✅ Bitti |
| 1 | Kural motoru (YAML) + KiCad ERC/DRC entegrasyonu | ✅ Bitti |
| 2 | Kazanan placement çıktısını çalışan KiCad PCB Editor'e IPC ile yaz | ✅ Bitti |
| 3 | Tam otomatik PCB yerleştirme (`auto`) + gerileme koruması | ✅ Bitti |
| 4a | Şematik okuma (hiyerarşik) + yapısal kontroller | ✅ Bitti |
| 4b | Netlist değişmezliği kalkanı | ✅ Bitti |
| 4c | Atomik yazma + açık-proje koruması | ✅ Bitti |
| 4d | Bağlantı koruyan sembol taşıma | ✅ Bitti |
| 4e | Şematik yerleştirme kalitesi + toplu uygulama | ✅ Bitti |
| 4f | Kütüphaneden sembol okuma + şematiğe **ekleme** | ✅ Bitti (§18) |
| 4f+ | Bağlama (tel/etiket), çok birim, footprint doğrulama | ✅ Bitti (§19) |
| 4g | Şematikten karta yansıtma (`pcb_sync`) | ✅ Bitti (§19) |
| 5 | Makine öğrenimi altyapısı (veri, model, ölçüm, güvenli bağlantı) | ✅ Bitti |
| 6/A | Geniş hamle repertuarı + model filtresi (yol haritası A1-A3) | ⚠️ Bitti, kazanç yok (§13) |
| 6/C | Öznitelik şeması v3: pin düzeyi geometri + bulgu bağlamı | ✅ Bitti (§14) |
| 6/E | Kabul kuralı: tavlama benzeri kaçış | ⚠️ Ölçüldü, kazanç yok (§15) |
| 6/F | `polish`e yakınsama ölçütü (skor sabrı) | ✅ Bitti (§16) |
| 6/G | `auto` bütçe bölüşümü: sert tavan + artık devri + 75/25 | ✅ Bitti (§17) |
| 7 | Devre tipine göre kural kütüphanesi + bakır okuma/kuralları | ✅ Bitti (§20) |
| 8 | Ağırlıklı skorlama, korpus kalibrasyonu, alt-devre tanıma | ✅ Bitti (§21) |

---

## 1. Lisans durumu (araştırıldı, karar verildi)

Mimariyi bu belirledi, tekrar araştırmaya gerek yok:

- KiCad kaynak kodu: **GPLv3 veya sonrası**
- `kicad-python` (resmi IPC bağlayıcıları): **MIT** — repodaki LICENSE dosyası doğrulandı
- Sembol/footprint kütüphaneleri: CC-BY-SA 4.0 **+ istisna** → kütüphaneyi kullanan
  tasarımlar ve üretilen dosyalar CC-BY-SA'ya tabi değil, ticari/kapalı olabilir
- KiCad markaları Linux Foundation'a tescilli → ürün adında "KiCad" kullanma
- Resmi PCM deposu açık kaynak zorunlu; **3. parti depoda kapalı kaynak serbest**

**Seçilen zemin:** `kicad-cli` (ayrı süreç) + IPC API/`kicad-python` (MIT, ayrı
süreç). GPL koduyla hiçbir noktada linklenmiyoruz. Kendi kodumuz istediğimiz
lisansta olabilir. Sadece `kicad-cli` binary'sini kendi kurulum paketimize
gömüp dağıtırsak GPL yükümlülüğü doğar — kullanıcının kendi KiCad'ini çağırmak
bu sorunu ortadan kaldırır.

## 2. KiCad'in teknik kısıtları (KiCad 10.0.x, doğrulandı)

| İhtiyaç | Durum |
|---|---|
| PCB okuma/footprint taşıma (IPC API) | ✅ Var (KiCad 9'dan beri) |
| **Şematik API ile okuma/değiştirme** | ❌ **Yok — KiCad 11'e planlandı** |
| Headless (GUI'siz) IPC | ❌ KiCad 11 |
| Netlist / ERC / DRC / export (`kicad-cli`) | ✅ Var |

Resmi dokümanın ifadesi: *"In KiCad 9.0, the IPC API and the new IPC plugin
system are only implemented in the PCB editor."* KiCad 10'da da değişmedi.

**Sonuç:** Otomatik yerleştirme PCB'de bugün yapılabilir; şematik yerleştirme
KiCad 11'i bekliyor.

Bilinen IPC bug'ları (Aşama 2'de karşılaşılacak): `update_items()` bazen sessizce
hiçbir şey yapmıyor; IPC üzerinden footprint döndürmek sembol bağlantısını
bozuyor ([kicad#21655](https://gitlab.com/kicad/code/kicad/-/issues/21655)).
Her yazma işleminden önce git commit, ve mutlaka `begin_commit`/`push_commit`.

## 3. Ortam

```
Proje        : C:\Users\ardaa\OneDrive\Desktop\Kicad\pcbqa\
kicad-cli    : C:\Program Files\KiCad\10.0\bin\kicad-cli.exe  (sürüm 10.0.4)
Demo projeler: C:\Program Files\KiCad\10.0\share\kicad\demos  (19 adet)
Python       : 3.13.14 (Microsoft Store), venv proje içinde .venv
Bağımlılıklar : pyyaml 6.0.3; IPC yazma için kicad-python
Platform     : Windows 11, PowerShell
```

`.kicad_pcb` dosya sürümü: `20260206`. KiCad 10'da **üst düzey net tablosu yok**
— netler pad'lerde isimle taşınır: `(net "GND")`.

## 4. Kurulan araç: `pcbqa`

Salt-okunur KiCad tasarım analizi. **Tasarıma hiçbir şey yazmaz.**

```
pcbqa/
  sexpr.py         s-expression okuyucu (bağımlılıksız, bozuk dosyalara toleranslı)
  geom.py          dışbükey kabuk, SAT çakışma testi, poligon mesafesi
  pcb.py           .kicad_pcb -> bileşen/pad/courtyard konumları, kart sınırı
  netlist.py       kicadxml VEYA doğrudan PCB -> net/pin bağlantıları
  model.py         ikisini birleştirir + ölçümler (HPWL, yoğunluk)
  rules.py         YAML kural motoru (7 kural tipi)
  kicadcli.py      kicad-cli sarmalayıcısı (netlist, ERC, DRC)
  schematic.py     .kicad_sch okuyucu (hiyerarşik, pin/bbox geometrisi çözülmüş)
  sch_verify.py    netlist değişmezliği kalkanı (yazma için ön koşul)
  sch_write.py     atomik yazma + açık-proje (lck) koruması + yedek
  sch_move.py      bağlantı koruyan sembol taşıma + komut satırı
  sch_place.py     şematik yerleştirme optimizasyonu (hızlı geometrik ölçüt)
  sch_apply.py     toplu uygulama: tek doğrulama, tek yazma + komut satırı
  ipc.py           kicad-python ile çalışan KiCad PCB Editor'e placement uygular
  ipc_apply.py     yarışmayı koşturur, kazananı seçer, IPC dry-run/apply yapar
  report.py        terminal raporu + skor
  synth.py         sentetik test kartı üreteci
  harness.py       yerleştiricileri koşturur, puanlar, kazanan kartı yazabilir
  placement/
    base.py        DONMUŞ arayüz: Placer, PlacementContext, Evaluation
    refine.py      bulgu güdümlü cila — hakemin gerçek puanını optimize eder
    auto.py        ÜRETİM yerleştiricisi: kaba + cila + gerileme tabanı
    cluster.py     kümeleme tabanlı kaba yerleşim (auto bunu kullanır)
    learned.py     auto + öğrenilmiş hamle sıralaması (Aşama 5)
    force.py / anneal.py / codex.py   yarışan diğer motorlar
    baseline.py    identity / random (hakem doğrulaması)
  ml/              Aşama 5 — makine öğrenimi altyapısı
    features.py    DONMUŞ öznitelik şeması (v3, 75 öznitelik)
    collect.py     gerçek hakemle etiketlenmiş veri kümesi (CLI)
    dataset.py     JSONL + KART BAZLI bölme
    metrics.py     regresyon + sıralama metrikleri
    model.py / linear.py / trees.py   model sözleşmesi, ridge, GBT
    train.py       eğitim/karşılaştırma CLI
    models/        eğitilmiş modeller (JSON)
  placement/repertoire.py   geniş hamle repertuarı: takas / küme / bölge (Aşama 6)
  __main__.py      komut satırı
  default_rules.yaml
samples/
  bench_good.kicad_pcb / bench_bad.kicad_pcb   (üretilmiş test tezgâhı)
  bench.rules.yaml                              (4 alanı kapsayan kural seti)
  pic_programmer/  + pic_programmer.rules.yaml  (demo kopyası)
run.cmd  README.md  requirements.txt  .gitignore
```

**Kritik mimari kararı 2 (Aşama 3'te öğrenildi):** yerleştirici, hakemin
puanladığı şeyi optimize etmeli. Motorlar vekil bir maliyet (HPWL + genel
cezalar) optimize ederken hakem YAML kurallarına bakıyordu; sentetik tezgâhta
ikisi örtüştüğü için sorun görünmedi, gerçek kartta ayrıştı ve dört motorun
üçü `pic_programmer`ı **bozdu**. Çözüm: `ctx.evaluate(placement)` ile gerçek
ölçüm yerleştiricinin eline verildi (60 bileşenli kartta ~5 ms). Yeni bir
motor yazarken vekil maliyet uydurmayın.

**Kritik mimari kararı:** `model.py` ve `rules.py` KiCad'i **hiç bilmez** —
sadece kendi veri modelini görürler. Aşama 3'ün yerleştirme motoru da aynı
modeli kullanacak; KiCad 11 şematik API'sini getirdiğinde sadece yeni bir
okuyucu eklenecek. Bu ayrımı bozma.

### Temel fikir

KiCad şematiği ile PCB'yi ayrı tutar ve **birleştirmez**. ERC "bu pin bağlı
değil" der; "bu decoupling kondansatörü 33 mm ötede" demez. `pcbqa` tam olarak
o boşluğu doldurur:

```
U2.VCC_14 için en yakın C1 33.3 mm uzakta (hedef <= 10 mm), net VCC
```

**Şematik zorunlu değil.** KiCad 9+ pad'lerde hem net adını hem pin tipini
(`power_in`, `bidirectional`…) sakladığı için kuralların neredeyse tamamı
sadece `.kicad_pcb` ile çalışır.

### Kullanım

```powershell
.\.venv\Scripts\python -m pcbqa <proje>                       # klasör veya .kicad_pcb
.\.venv\Scripts\python -m pcbqa <proje> --rules r.yaml --json rapor.json
.\.venv\Scripts\python -m pcbqa.synth --out samples           # tezgâhı yeniden üret
.\.venv\Scripts\python -m pcbqa.harness --all                 # yerleştirici yarışması
.\.venv\Scripts\python -m pcbqa.ipc_apply --board samples\bench_bad.kicad_pcb
.\.venv\Scripts\python -m pcbqa.ipc_apply --board samples\bench_bad.kicad_pcb --apply
run.cmd samples\pic_programmer                                # kısayol

# Aşama 5 — ML hattı
.\.venv\Scripts\python -m pcbqa.ml.collect --suite "<demolar>" --out .work\moves.jsonl
.\.venv\Scripts\python -m pcbqa.ml.train .work\moves.jsonl --model all --target all --cv 5
.\.venv\Scripts\python -m pcbqa.harness --placer auto --placer learned
```

Analiz bayrakları: `--rules --json --work-dir --kicad-cli --no-kicad-checks --no-color --fail-on`
Çıkış kodları: `0` temiz · `1` eşiği aşan bulgu · `2` araç hatası.

### IPC uygulama hattı (`pcbqa.ipc_apply`)

Amaç: Aşama 3 yerleştiricisinin/kazananın ham çıktısını çalışan KiCad PCB
Editor'e yazmak. Sözleşme `Placement = dict[str, tuple[float, float, float]]`,
yani `ref -> (x_mm, y_mm, rot_deg)`.

Akış:

1. `--board` üzerinden mevcut tasarım okunur ve kilitli referanslar belirlenir.
2. `--placer`/`--all` verilirse harness ile placement yarışması çalışır.
   Hiçbiri verilmezse `identity/random` dışındaki yarışmacılar çalışır.
3. Sözleşme ihlali olmayan en iyi skor seçilir.
4. Çalışan KiCad'e `kicad-python` ile bağlanır, aktif kart adı `--board`
   dosya adıyla karşılaştırılır.
5. Varsayılan dry-run'dır. `--apply` verilirse footprint `position` ve
   `orientation` değerleri `Board.begin_commit()` / `Board.update_items()` /
   `Board.push_commit()` ile tek undo adımı olarak uygulanır.
6. `--save` verilirse KiCad kartı kaydedilir; verilmezse sadece editor'de
   uygulanmış halde kalır ve kullanıcı inceleyebilir/undo yapabilir.

Önemli bayraklar:

- `--write-placement-json .work\winner-placement.json`: kazanan ham çıktıyı saklar.
- `--placement-json PATH`: yarışmayı tekrar koşturmadan aynı çıktıyı uygular.
- `--allow-board-mismatch`: aktif KiCad kart adı farklıysa yine de uygula.
- `--ignore-kicad-locks`: KiCad'de kilitli footprint'leri taşıma korumasını kapatır.

### Kural sistemi (7 tip)

| Tip | Alan | Ne kontrol eder |
|---|---|---|
| `proximity` | güç / niyet | Bir pine, aynı nette belirli bir bileşen N mm'den yakın mı |
| `require_on_net` | niyet | Ada uyan her nette belirli türde bileşen var mı (pull-up) |
| `same_net` | niyet | Belirtilen pinler aynı nette mi |
| `net_length` | sinyal | Netin tahmini uzunluğu (HPWL) bütçeyi aşıyor mu |
| `length_match` | sinyal | Bir grup netin uzunluğu birbirine yakın mı (diferansiyel çift) |
| `courtyard_overlap` | üretim | Bileşenler çakışıyor mu (gerçek poligon kesişimi) |
| `edge_clearance` | üretim | Bileşenler kart kenarından yeterince içeride mi |

Seçici alanları (`pin` / `partner`): `ref` (regex), `kind`, `value` (regex),
`pintype`, `function` (regex).
`kind` değerleri: `ic capacitor resistor inductor diode transistor crystal
connector switch fuse testpoint other` (referans önekinden türetilir).

### Skor

```
ceza = 8 × hata + 2 × uyarı
skor = 100 × e^(−ceza / max(bileşen_sayısı, 20))
```

Bileşen sayısına bölünür ki farklı büyüklükteki kartlar karşılaştırılabilsin;
üstel eğri kullanılır ki büyük kartlarda 0'a doymasın. **Aşama 3'te bu skor,
yerleştirme motorunun küçülteceği maliyet fonksiyonuna dönüşecek.**

## 5. Sentetik test tezgâhı (`pcbqa/synth.py`)

Yerleştirme motorunu geliştirmek için **kötü** bir kart gerekir — temiz kartta
optimize edilecek bir şey yoktur. Aynı devreden iki kart üretiliyor:

| Kart | Ne | Skor |
|---|---|---|
| `bench_good.kicad_pcb` | Makul yerleşim — **hedef** | 67 / 100 |
| `bench_bad.kicad_pcb` | 7 kasıtlı kusur (hepsi taşınabilir bileşende) | 2 / 100 |

Devre: USB-C → LDO regülatör → MCU (SOIC-20) + EEPROM (SOIC-8) + 12MHz kristal
+ UART header. 18 bileşen, 60×45 mm kart. Footprint'ler dosya içine gömülü
üretiliyor (kütüphane bağımlılığı yok). KiCad'in kendi DRC'si iki dosyayı da
sorunsuz ayrıştırıyor → format geçerli.

**Devrenin doğru cevabı kodda:** `spec.truth` sözlüğü hangi kondansatörün hangi
IC'ye ait olduğunu, hangi netlerin diferansiyel çift olduğunu tutuyor. Yani
kuralların doğru şeyi yakalayıp yakalamadığı kanıtlanabiliyor.

`bench_bad`'e ekilen kusurlar: 4 uzak decoupling/yük kondansatörü, 2 courtyard
çakışması (Y1/C7, R1/R2), bozuk USB çift simetrisi (R5 yanlış yerde).

Kilitli bileşenlere (J1/J2 konnektörleri) **kusur ekilmez**: yerleştirici
onları taşıyamayacağı için düzeltilemez bir ceza olur ve ulaşılabilir tavanı
düşürür. J1/J2 bu yüzden her iki kartta da aynı, yasal konumdadır.

⚠️ **`bench_good`'un 1 hatası kasıtlıdır**: `nRESET` pull-up'ı yok. Bu bir
**devre** kusuru, yerleşim kusuru değil — her iki kartta da var ve yerleştirme
motoru bunu asla düzeltemez. Bu yüzden hedef 100 değil **67**. Motorun işi
`2 → 67` mesafesini kapatmak.

⚠️ Tezgâh kartlarında **yönlendirme (track) yok**. KiCad DRC'si her neti
"bağlanmamış" sayıp 65 gürültülü ihlal üretir → yerleşim çalışmasında
**`--no-kicad-checks` kullan.**

## 6. Yol boyunca bulunan gerçek problemler (tekrar keşfetme)

**1. KiCad'in kendi demo dosyası bozuk.** `royalblue54L_feather.kicad_pcb`
içinde 349 yerde eksik açılış parantezi var (`(curved_edges no)filter_ratio 0.9)`).
`sexpr.parse()` artık toleranslı: bozuk parantezleri atlar, kalan üst düzey
düğümleri köke bağlar, sayacı raporda gösterir. O kartta 71 bileşenin tamamı
okunuyor. Katı davranış için `parse(text, strict=True)`.

**2. Zayıf kural formülasyonu.** "Aynı nette en yakın kondansatör" testi 3V3
gibi global bir rayda anlamsız: **tek bir kondansatör 10 güç pinini birden
tatmin ediyordu.** Çözüm: `proximity` kuralına `exclusive: true` seçeneği —
her partner en fazla bir hedef pine sayılır (en yakından başlayan açgözlü
eşleme). Gerçek beklenti "her güç pini kendi kondansatörünü ister" buydu.
Eski tasarımlarda çok bulgu üretir; kademeli geçiş için önce `false`.

**3. Döndürülmüş bileşenlerde yanlış alarm.** Kapladıkları alanı eksen-hizalı
sınır kutusuyla temsil etmek ciddi hata üretiyordu: stickhub demosunda `U1`
-135° dönük, gerçek courtyard'ı eğik dikdörtgen ama sınır kutusu çok daha büyük
bir kare — yakınındaki kondansatörler köşelerine düşüp "çakışıyor" görünüyordu
(26 yanlış bulgu). Çözüm: `geom.py` — dışbükey kabuk + ayırıcı eksen teoremi
(SAT) ile **gerçek poligon kesişimi**. Alan hesabı da shoelace ile poligondan.

**4. KiCad'in DRC'si her şeyi yakalamaz.** `courtyards_overlap` kontrolü proje
ayarlarından kapatılabiliyor ve stickhub demosunda **kapalı** — KiCad 0 ihlal
raporluyor. Aynı kartta gerçekten çakışan bileşenler var (`J7` ve `J8`, 7 mm
arayla yerleştirilmiş ama courtyard'ları 7.8 mm yüksek). pcbqa bu kontrolü
proje ayarlarından bağımsız yapar.

**Küçük tuzaklar:**
- SOIC'te pin 20, pin 1'in **tam karşısındadır** (ikisi de üstte), altta değil.
  Sol sütun 1→n/2 aşağı, sağ sütun n/2+1→n **yukarı** gider.
- Çift taraflı kartlarda yoğunluk: iki yüzün alanını toplamak %130 gibi anlamsız
  sonuç verir → en yoğun **yüz** üzerinden hesaplanıyor.
- Pad döndürme KiCad konvansiyonu (Y aşağı): `x' = x·cos + y·sin`,
  `y' = y·cos − x·sin`.
- Windows konsolu UTF-8 değil → `main()` içinde stdout/stderr `reconfigure`
  ediliyor.

## 7. Doğrulama durumu

- KiCad'in **19 demo projesinin 17'sinde** sorunsuz çalışıyor. Atlanan 2 tanesi
  zaten tam proje değil (`python_scripts_examples`, `simulation`) ve temiz hata
  mesajı + çıkış kodu 2 veriyorlar.
- 7 kural tipinin de hem geçen hem hata veren yolu test edildi.
- Çıkış kodları, JSON çıktısı, hata mesajları doğrulandı.
- Referans skorlar: `pic_programmer` 45, `video` 29, `ecc83` 100,
  `bench_good` 67, `bench_bad` 2.
- Aşama 2 IPC yazıcı için mock board unittestleri eklendi:
  dry-run mutasyon yapmıyor, `--apply` yalnız taşınabilir footprint'i güncelliyor,
  kazanan seçimi sözleşme ihlali olan sonucu dışarıda bırakıyor.
- Aşama 3 için 12 test daha (`tests/test_refine.py`): cila monotonluğu,
  kilitli bileşen sözleşmesi, `auto`nun iyi bir kartı bozmaması ve üç
  gerileme koruyucusunun ayrı ayrı doğrulanması. Toplam 15 test geçiyor.
- Aşama 3 regresyon paketi: 19 KiCad demo kartında `auto` (bkz. §9).
- Aşama 4a şematik okuyucu 19 demo projesinde doğrulandı: 17.088 pin,
  %98.7 örtüşme, 0 bozuk parantez, 0 okunamayan proje (bkz. §10).
- Aşama 4a/4b için 11 test daha (`tests/test_schematic.py`): dönüşüm
  doğruluğu, hiyerarşi, sanal sembol ayrımı, kalkanın doğru değişmezi
  kullanması.
- Aşama 4c/4d için 19 test daha (`tests/test_sch_move.py`): atomik yazma,
  yedek çakışması, kilit koruması, ızgara oturtmasının kaydırmayı değiştirmesi,
  doğrudan pin temasının engellenmesi, net birleştiren taşımanın kalkanla
  reddedilmesi, UUID korunması. **Toplam 64 test geçiyor.**

## 8. Bilinen sınırlar

- ~~Şematik konumları okunmuyor~~ → Aşama 4a ile çözüldü: `schematic.py`
  IPC'ye hiç dokunmadan `.kicad_sch`'i doğrudan okuyor.
- Courtyard poligonu dışbükey kabukla alınıyor; dikdörtgenler için birebir,
  nadir içbükey (L/U) courtyard'larda fazladan bulgu üretebilir.
- Dairesel courtyard'larda alan biraz küçük çıkabilir (`fp_circle`).
- `length_match` HPWL üzerinden çalışır — gerçek uzunluk eşleme kontrolü değil,
  "bu iki net çok farklı yerlerde" ön uyarısıdır.

---

## 9. Aşama 3 — TAMAMLANDI: `auto` yerleştiricisi

Kabul ölçütü hem sentetik tezgâhta hem gerçek kartlarda karşılandı.

### Ne inşa edildi

**Kök sebep:** dört yarışan motor vekil bir maliyet (HPWL + genel cezalar)
optimize ediyordu, hakem ise YAML kurallarına bakıyordu. Sentetik tezgâhta
ikisi örtüştü, gerçek kartta ayrıştı: `pic_programmer` üzerinde dört motorun
**üçü kartı bozuyordu** (codex −2.6, force −7.6, anneal −16.5).

Üç parçalı çözüm:

1. `base.py` → `ctx.evaluate(placement)` — hakemin gerçek ölçümü artık
   yerleştiricinin elinde. Geriye uyumlu (varsayılanlı alan); eski motorlar
   değişmeden çalışıyor. 60 bileşenli kartta ~5 ms, yani 30 sn'de binlerce
   deneme.
2. `refine.py` → **bulgu güdümlü cila.** Hamleler doğrudan bulgulardan
   üretilir ve yalnızca ölçüm iyileşirse kabul edilir (first-improvement
   tepe tırmanışı). Bulgunun yönü `measured`/`limit` karşılaştırmasından
   çıkarılır: `measured > limit` yaklaştır (decoupling), `measured < limit`
   uzaklaştır (courtyard çakışması). **Bu ayrım şart** — ilk sürüm çakışan
   iki bileşeni birbirine yaklaştırmaya çalışıyordu.
3. `auto.py` → üretim yerleştiricisi: `cluster` (kaba) + cila + kartın
   **mevcut hali de aday**. Son madde `auto`nun hiçbir kartı kötüleştiremeyeceğini
   tasarım gereği garanti eder.

**Gerileme koruması üç noktada:** `refine.polish` (monoton), `harness.best_result`
ve `ipc_apply.select_winner`. Skoru düşüren bir yerleştirme karta asla yazılmaz;
hiçbir motor iyileştiremezse `ipc_apply` hata verip karta dokunmaz.

### Ölçümler

Sentetik tezgâh (`bench_bad`, hedef `bench_good` = 67):

| yerleştirici | önce | sonra | hata | HPWL mm |
|---|---|---|---|---|
| **auto** | 2 | **67** | 1 | **220** |
| cluster / force / codex | 2 | 67 | 1 | 224 / 256 / 261 |
| anneal | 2 | 30 | 3 | 444 |
| identity (doğrulama) | 2 | 2 | 10 | 485 |
| random (duyarlılık) | 2 | 0 | 18 | 802 |

Cila **tek başına** (kaba yerleşim olmadan, sıfırdan): `bench_bad` 1.7 → 30.1,
hata 10 → 3, HPWL 485 → 265.

Gerçek kart (`pic_programmer`, kendi kural seti):

| yerleştirici | önce | sonra | kazanç |
|---|---|---|---|
| **auto** | 83 | **100** | **+17.3** — 0 hata, HPWL 1489 → **1203** |
| cluster | 83 | 88 | +5.4 |
| codex | 83 | 83 | +0.0 |
| force | 83 | 75 | −7.6 |
| anneal | 83 | 66 | −16.5 |

`force` ve `anneal` gerçek kartı hâlâ bozuyor — bunlar araştırma motorları
olarak duruyor, gerileme koruyucusu çıktılarının karta yazılmasını engelliyor.

`auto`, Aşama 0'dan beri duran `U2.14 → C1 33.3 mm` decoupling hatasını kapattı.

### Regresyon paketi

`--suite` ile 19 KiCad demo kartının tamamında koşuluyor. Bu, kabul ölçütünün
asıl yeri: tek kartta iyi sonuç, sentetik tezgâha aşırı uyum olabilir.

```powershell
.\.venv\Scripts\python -m pcbqa.harness --placer auto --budget 15 --suite "SUITE_PATH" --rules pcbqa\default_rules.yaml
```

Herhangi bir kartta gerileme varsa çıkış kodu `1`. 19 KiCad demo kartının **hiçbirinde gerileme yok** (çıkış kodu 0):

| Kart | önce → sonra | | Kart | önce → sonra |
|---|---|---|---|---|
| pic_programmer | 45 → **94** (+48.6) | | RoyalBlue54L-Feather | 80 → 84 (+4.6) |
| complex_hierarchy | 54 → **97** (+43.2) | | One-Air-Max | 93 → 97 (+3.7) |
| multichannel_mixer-unrouted | 70 → **100** (+29.6) | | tinytapeout-demo | 74 → 78 (+3.5) |
| sonde xilinx | 73 → **100** (+27.4) | | multichannel_mixer | 98 → 100 (+1.7) |
| interf_u | 5 → 30 (+25.3) | | ecc83-pp / ecc83-pp_v2 | 100 → 100 |
| video | 29 → 38 (+8.5) | | microwave / RoyalBlue54L-NFC | 100 → 100 |
| CM5_MINIMA_3 | 81 → 85 (+4.5) | | jetson / kit-dev / StickHub / vme-wren | değişmedi |

11 kartta iyileşme, 8 kartta değişiklik yok. Değişmeyenlerde `auto` doğru
davranıp kartın **mevcut halini** döndürüyor.

Testler: `python -m unittest discover -s tests` → 15 test, hepsi geçiyor.
Yeni testler kilitli bileşen sözleşmesini, monotonluk garantisini ve üç
gerileme koruyucusunu ayrı ayrı doğruluyor.

### Bilinen sınır

Bütçe **yumuşak**. Çok büyük kartlarda (ör. `jetson-agx-thor-baseboard`) tek
değerlendirme pahalı olduğu için `auto` verilen süreyi belirgin şekilde aşabilir.
Kesme yok; sonuç doğru, süre uzun.

---

## 10. Aşama 4 TAMAMLANDI — şematik okuma, kalkan, yazma, taşıma

### KiCad 11 beklenmiyor, çünkü gerek yok

Bu proje "şematik API'si KiCad 11'e planlandı" diye 4. aşamayı erteliyordu.
IPC'de gerçekten yok — ama `.kicad_sch` de s-expression, ve `sexpr.py` onu
zaten okuyor. Yazmanın da mümkün olduğu ölçülerek doğrulandı:

- `pic_programmer.kicad_sch` parse → `dumps()` → yeniden parse: **ağaç birebir
  aynı** (tırnaklı/tırnaksız atom ayrımı dahil), 0 bozuk parantez.
- KiCad yeniden yazılan dosyayı sorunsuz açıyor ve **netlist birebir aynı**
  çıkıyor.

### 4a — şematik okuma (`schematic.py`)

Hiyerarşik: kök dosyadaki `sheet` düğümlerini `Sheetfile` üzerinden izleyip
alt sayfalara iniyor, her öğeye sayfa yolunu (`/`, `/pic_sockets`) işliyor,
döngülere karşı ziyaret edilen dosyaları takip ediyor. `vme-wren` demosunda
**36 dosya, 1606 sembol** sorunsuz okunuyor.

**En riskli parça pin geometrisiydi** — kütüphanede Y yukarı, sayfada Y aşağı,
üstüne rotasyon ve ayna. Tahmin etmek yerine 19 demo projesinin tamamında
ölçüp seçtim:

| Hipotez | Örtüşme |
|---|---|
| `(px·cos − py·sin, −px·sin − py·cos)` | **%93.5** |
| rakip | %37.8 |
| ayna **rotasyondan sonra** | **%94.9** |
| ayna rotasyondan önce | %27.0 |

Doğrulama: 19 proje, **17.088 pin, %98.7 örtüşme** (çoğu projede %100),
**0 bozuk parantez, 0 okunamayan proje**.

> **Tekrar keşfetmeyin:** ilk ölçümüm %79 çıkmıştı ve okuyucuda hata var
> sandım. Yoktu — çapa kümem darmış. Bir pin yalnızca tel ucuna değil;
> junction'a, no-connect'e, etikete veya **doğrudan başka bir sembolün pinine**
> de değebilir. Güç sembolleri (GND/VCC) çoğunlukla telsiz, doğrudan IC pinine
> yapışır. Doğru ölçütle `pic_programmer`da oran %100.

Rapora `SEMATIK` bölümü eklendi; `rules.run_schematic_checks` dört yapısal
kontrol veriyor: eksik alt sayfa dosyası (hata), bozuk dosya (hata), ızgara
dışı sembol (uyarı), footprint'i yok (uyarı), çakışan sembol gövdeleri (uyarı).

`#` ile başlayan referanslar (`#PWR`, `#FLG`) sanal sayılır — footprint'leri
olmaz, bileşen sayımına ve footprint kontrolüne girmezler.

### 4b — netlist değişmezliği kalkanı (`sch_verify.py`)

**Şematikte bağlantı geometriktir.** PCB'de net pad'in içinde isimle yazılıdır;
şematikte tel ucu pine değiyorsa bağlıdır. Ölçüldü: `pic_programmer` üzerinde
R1 kaydırılınca pin 2 koptu, `unconnected-(R1-Pad2)` oldu — hiçbir hata, hiçbir
uyarı. **Tek ızgara adımı (1.27 mm) bile yetiyor.**

Kalkan yazma öncesi/sonrası `kicad-cli sch export netlist` koşturup karşılaştırır.
Doğru değişmez ham XML değil — **pinlerin ağlara bölünüşü**:

```
{ {(R1,1),(U1,3)},  {(R1,2),(C4,1)},  ... }
```

Net kodları her ihracatta yeniden numaralanır, otomatik net adları konuma göre
değişir; bunlar gerçek bağlantı değişikliği değildir. Bölünme aynıysa devre
elektriksel olarak aynıdır. Kalkan üç durumu doğru ayırt ediyor: yeniden
yazma (geçer), 12.7 mm kayma (yakalar), 1.27 mm kayma (yakalar).

Testler: `python -m unittest discover -s tests` → **45 test**, hepsi geçiyor.

### 4c — atomik yazma (`sch_write.py`)

IPC sematikte calismadigi icin PCB tarafindaki "calisan editore uygula, undo
ile geri al" secenegi YOK. Yazma dogrudan dosyaya, dolayisiyla:

- Gecici dosya **ayni dizine** yazilir → `fsync` → `os.replace`. Windows'ta da
  atomiktir; **ayni dizin sart** cunku farkli birimler arasinda atomiklik
  garanti edilmez.
- Yazmadan once yedek alinir (`.pcbqa-bak`, mevcut yedegin uzerine yazmaz).
- Proje KiCad'de acikken (`~<proje>.kicad_pro.lck`) yazma REDDEDILIR. Eeschema
  dosyayi bellekte tutar; kullanici kaydederse bizim degisikligimiz sessizce
  kaybolur.
- **UUID'ler asla yeniden uretilmez** — KiCad sembol orneklerini ve netlist
  yollarini onlarla izler; yenilenirse PCB ile sematik arasindaki bag kopar.
- Varsayilan dry-run.

### 4d — bağlantı koruyan taşıma (`sch_move.py`)

Sembol tasinirken ona TUTUNAN her sey birlikte tasinir: pinlerine degen tel
uclari (telin oteki ucu yerinde kalir, tel uzar/kisalir), pin konumundaki
junction ve no_connect isaretleri, etiketler, sembolun kendi property
konumlari. Hiyerarside sembol hangi alt sayfadaysa **o dosya** duzenlenir.

Izgaraya oturtma kaydirma miktarini degistirir; tel uclari AYNI miktarda
kaydirilir - yoksa pinden kopar.

**Uc katmanli koruma, uctan uca dogrulandi:**

| Katman | Ornek | Sonuc |
|---|---|---|
| Geometrik engel | `#PWR022` pini `J1.5`'e dogrudan yapisik (arada tel yok) | tasima reddedildi |
| Netlist kalkani | R1 (+12.7, −10.16) → `/VPP_ON` agi `VCC`'ye kayniyor (12→15 pin) | `--apply` verilmisken bile yazilmadi, dosya bayt bayt ayni kaldi |
| Atomik yazma | `~pic_programmer.kicad_pro.lck` var | cikis kodu 2, yazma yok |

Basarili tasima ornegi (gercek cikti):

```
R1: (78.74, 43.18) -> (81.28, 43.18)  [tel ucu 2, junction 0, ... property 5]
KALKAN: baglanti degismedi
UYGULANDI: 230,132 bayt yazildi
```

Bagimsiz dogrulama: yazilan dosyanin netlist'i orijinalle **birebir ayni**,
0 bozuk parantez, UUID'ler korunmus. Alt sayfadaki `C6` tasindiginda yalnizca
`pic_sockets.kicad_sch` degisti, kok dosya el degmedi.

Testler: `python -m unittest discover -s tests` → **64 test**, hepsi geciyor.
`kicad-cli` yoksa uctan uca testler atlanir.

### Bilinen sınırlar (4c/4d)

- **Yalnizca oteleme.** Rotasyon ve ayna desteklenmiyor: pin konumlari donunce
  tel uclarinin nasil uzatilacagi otelemedeki gibi tek bir delta degil.
- Dogrudan pin-pine temasta tasima reddediliyor; "ikisini birlikte tasi"
  secenegi henuz yok (`--force` var ama baglantiyi koparir).
- Ayni .kicad_sch birden fazla sayfada ornenmisse duzenleme TUM orneklerini
  etkiler; bu durum engel olarak isaretleniyor.
- Kalkan her tasimada iki `kicad-cli` ihracati calistirir (~2-4 sn). Toplu
  tasimalarda her adimda degil, sonunda bir kez calistirmak gerekir.
- `dumps()` dosyayi yeniden bicimlendirir; git diff sisiyor. KiCad de her
  kaydediste ayni sey yaptigi icin kabul edildi.

### 4e — şematik yerleştirme kalitesi (`sch_place.py`, `sch_apply.py`)

Aşama 3 mimarisi olduğu gibi taşındı: `refine.polish` **değiştirilmeden**
kullanılıyor, değişen tek şey değerlendirici. Monotonluk garantisi de oradan
geliyor.

**İki hızlı, bir yavaş ölçüt.** Kalkan her çağrıda `kicad-cli` çalıştırır
(2-4 sn); yerel arama binlerce aday dener. Bu yüzden arama sırasında
bellek-içi geometrik ölçüt kullanılır (**~0.4 ms**, 20 sn'de ~47.000 deneme),
netlist kalkanı yalnızca yazmadan önce **bir kez** koşar. Geometrik ölçüt
bağlantı riskini de taşır: taşınan bir pin kendisine ait olmayan bir çapaya
oturursa netler birleşir — kalkanın ucuz vekili.

`refine.py`'de iki nokta gevşetildi (Aşama 3 davranışı değişmeden):
`extent_of` ve `nudge_steps`. İkincisi şarttı — PCB'nin serbest mm adımları
(±0.5, ±1, ±2, ±4) şematikte **her denemeyi ızgara dışı** bırakıp reddettiriyor,
optimizasyon 0.7 sn'de sıfır taşımayla yakınsıyordu. Şematik adımları 1.27 mm
katları olmak zorunda.

**Sembol kimliği UUID'dir, referans değil.** Çok birimli bir bileşenin
(74LS125'in dört kapısı) her birimi ayrı `symbol` düğümüdür ve hepsi aynı
referansı taşır; referansla anahtarlamak dördünü tek girdiye çökertip
"U2 ve U2 çakışıyor" gibi hayali bulgular üretiyordu.

`sch_apply` toplu uygulayıcıdır: tüm taşımaları ağaçta uygular, kalkanı bir kez
koşar, dosyayı bir kez yazar. Bir nokta iki taşınan sembolün pinine denk gelip
deltaları farklıysa çatışma sayılır ve uygulama reddedilir.

**Ölçümler:** `pic_programmer` kök sayfası 985.5 → 976.6 mm (skor 100 sabit,
0 hata, netlist birebir aynı). Dağınık sayfalarda çok daha fazla:
`video/RAMS` %21, `vme-wren` kök %17, `sonde xilinx` %8.

### Yol boyunca bulunan gerçek hata (tekrar keşfetmeyin)

Regresyon paketi tek bir sayfada monotonluk ihlali gösterdi:
`jetson-agx-thor-baseboard /SoM_IO` skoru 100 → 97.4. `polish` yuvarlanmamış
kayan noktalarla çalışıyor (308.60999999999996), sonuç dosyaya yazılırken 4
haneye yuvarlanıyordu (308.61). Bu **4×10⁻¹⁴ mm**'lik fark, tam kenar kenara
duran iki gövdenin çakışma testini ters çeviriyordu: `_boxes_overlap` toleranssızdı,
yani kıl payı bir yüklem kayan nokta gürültüsüne bırakılmıştı. 1.27 mm
ızgarasında bitişik semboller çok yaygın olduğu için bu er geç patlardı.

İki yerden düzeltildi: `rules.OVERLAP_EPS` (tam temas çakışma sayılmaz) ve
`SchematicArena.positions` artık yuvarlamayı **arama sırasında** yapıyor, yani
aramanın gördüğü koordinatlarla dosyaya yazılan koordinatlar aynı.

### Yol boyunca bulunan ikinci gerçek hata: SAHTE KAZANÇ

Regresyon paketi `vme-wren/vme_p1_p2` sayfasında "skor 100, 0 hata, tel %60
kısaldı" dedi. Şüphelenip gerçek kalkanla uçtan uca denedim: **257 pin ağ
değiştirmişti** ve yazma reddedildi. Sistem güvenliydi (kalkan son söz), ama
ucuz ölçüt YANILTICIYDI.

Sebep: o sayfada **137 bus ve 262 bus girişi** var ve okuyucu `bus`/`bus_entry`
düğümlerini hiç tanımıyordu. İki iş yapıldı:

1. Okuyucu artık `bus` ve `bus_entry` düğümlerini okuyor; bunlar
   **sürüklenemeyen çapa** sayılıyor (`sematik-bus-girisi-kopuyor` kuralı).
2. **Mekanizma tam çözülmedi.** Bus girişi kuralı tek başına bu sayfayı
   kurtarmadı. Yarım anlaşılmış bir sezgisel kural göndermek yerine
   muhafazakâr davranıldı: **bus içeren sayfalarda optimizasyon varsayılan
   olarak kapalı** (`allow_buses=True` ile açılır, kalkan yine son söz).

Bu bilinçli bir borç. Çözmek için sıradaki adım: bus/bus_entry/label
topolojisini gerçekten modelleyen bir bağlantı grafiği kurmak — o zaman ucuz
ölçüt bus'lı sayfalarda da güvenilir olur.

### Bilinen sınırlar (4e)

- Yalnızca öteleme (4d ile aynı sınır).
- Optimizasyon **tek sayfa** üzerinde çalışır; sayfalar arası denge yok.
- Sayfa sınırı kontrolü kağıt boyutundan türetiliyor (`PAPER_SIZES`); listede
  olmayan bir boyut A4 varsayılıyor.
- Geometrik ölçüt tel **topolojisini** değiştirmez, yalnızca uçları sürükler.
  Gerçek bir yeniden çizim (wire routing) kapsam dışı.
- **Bus içeren sayfalar varsayılan olarak kapalı** (yukarıdaki nota bakın).
  Demo projelerinin önemli bir kısmı bus kullanıyor, yani 4e şu an esas olarak
  bus'sız sayfalarda iş görüyor.

---

## 11. Aşama 5 TAMAMLANDI — makine öğrenimi altyapısı

Bu aşamanın çıktısı bir **altyapı**dır: veri toplama, öznitelik çıkarımı,
model eğitimi, dürüst ölçüm ve arama motoruna güvenli bağlantı. Model
kalitesi bugün `auto`yu geçmiyor (bkz. §11.5) — ama artık geçip geçmediği
**ölçülebiliyor**, ve ölçüm hattı bir sonraki denemeyi ucuzlatıyor.

### 11.1 Neden ML, ve tam olarak neye

Aşama 3'ün dersi "yerleştirici hakemin puanladığı şeyi optimize etmeli"ydi.
Sıradaki darboğaz hakemin **maliyeti**: bir değerlendirme `bench_bad`de
2.1 ms, `pic_programmer`da 6.1 ms, `jetson`da çok daha fazla (§9'daki
"bütçe yumuşak" sınırının kök sebebi bu). Yerel arama bütçesinin neredeyse
tamamını `ctx.evaluate` çağrılarına harcıyor.

Sorulan soru: **"bu bileşeni buraya taşırsam hakemin puanı artar mı?"**
sorusunu, hakemi çağırmadan tahmin edebilir miyiz? Cevabı bilen bir model,
adayları denenme sırasına dizerek aynı bütçede daha çok iyileşme yakalatabilir.

### 11.2 Mimari kararı: **model karar vermez, sıra önerir**

Bu, tüm altyapıyı belirleyen karardır ve bozulmamalı. Model çıktısı yalnızca
`refine.polish` içindeki aday hamlelerin **sırasını** değiştirir; bir hamlenin
kabul edilip edilmeyeceğine hâlâ `ctx.evaluate` karar verir. Sonuçları:

- Monotonluk garantisi (Aşama 3) aynen duruyor — model tamamen yanılsa bile
  sonuç başlangıçtan kötü olamaz.
- Bozuk/eski model dosyası aramayı durduramaz; sıralayıcı patlarsa arama kendi
  sırasıyla devam eder.
- Model yoksa `learned` sessizce `auto` gibi davranır (depo modelsiz de çalışır).

`tests/test_ml.py::AdversarialRankerTests` bunu kasten zorluyor: **en kötü
hamleyi başa alan** sıralayıcı ve her çağrıda istisna fırlatan sıralayıcı ile
`polish` koşuluyor, ikisinde de gerileme yok.

`base.py`'ye eklenen tek şey varsayılanlı `ctx.move_ranker` alanı — Aşama 3'ün
`evaluator`ı nasıl eklendiyse aynı şekilde, geriye uyumlu.

### 11.3 Kurulan araçlar

```
pcbqa/ml/
  features.py    DONMUS sema (v1, 51 oznitelik): Design + aday hamle -> vektor
  collect.py     gercek hakemle etiketlenmis veri kumesi (CLI)
  dataset.py     JSONL depolama + KART BAZLI bolme
  metrics.py     regresyon + SIRALAMA metrikleri
  model.py       model sozlesmesi, JSON kaydet/yukle, kayit defteri
  linear.py      ridge regresyon (saf Python)
  trees.py       gradyan artirmali agaclar (saf Python, histogram tabanli)
  train.py       egitim/karsilastirma CLI
  models/move-v1.json   depoya konan egitilmis model (5 KB)
pcbqa/placement/learned.py   auto + ogrenilmis siralama
tests/test_ml.py             29 test
```

Katmanlama `model.py`/`rules.py`nin KiCad'i bilmemesiyle aynı: `features.py` ve
`collect.py` PCB'yi bilir, çekirdek bilmez. Şematik tarafı aynı çekirdeği
kullanmak isterse yalnızca yeni bir `features`/`collect` çifti gerekir.

**Bağımlılık eklenmedi.** numpy/scikit-learn yok; problem boyutu (~50 öznitelik,
~50 bin satır) saf Python için fazlasıyla küçük ve Windows Store Python'da
tekerlek/derleyici derdi açmıyor. Modeller **JSON**: git diff'i okunabilir,
sürümler arası taşınabilir, ve çalıştırılabilir kod taşımadığı için
başkasından gelen bir model dosyasını açmak güvenlik sorunu değil.

### 11.4 Öznitelikler neden yerel (ve neden test ediliyorlar)

51 özniteliğin tamamı tek bir bileşenin **kendi netleri ve yakın
komşularıyla** hesaplanır; maliyet kartın büyüklüğüne değil bileşenin
derecesine bağlıdır:

| kart | bileşen | öznitelik | tam değerlendirme | oran |
|---|---|---|---|---|
| bench_bad | 18 | 32 µs | 2.09 ms | 65x |
| pic_programmer | 63 | 72 µs | 6.12 ms | 85x |

İlk sürüm 250 µs sürüyordu; profil, sürenin %77'sinin `geom.distance`
(gerçek poligon mesafesi) içinde geçtiğini gösterdi. Çakışma testi gerçek
poligonla (SAT) kaldı — `courtyard_overlap` kuralı da öyle çalışıyor — ama
**açıklık** ölçüsü sınır kutusu boşluğuna çevrildi; ayrık kutular için SAT'a
hiç girilmiyor.

Yerel hesabın sessizce yanlış olması en tehlikeli hata sınıfı olurdu (model
sağlam veriyle eğitildiğini sanır). Bu yüzden `d_hpwl` özniteliği testlerde
**tam yeniden hesaplamayla** karşılaştırılıyor.

### 11.5 Ölçüm — ve `learned` neden hâlâ `auto`yu geçmiyor

Bakılan metrik R² değil. Yerel arama ilk iyileştiren hamleyi kabul ettiği için
asıl soru "skoru artıran hamleye kaçıncı denemede ulaşıldığı", ve tabanı
cilanın **bugün** kullandığı sıra (rastgele sıra değil — hamle üreteci zaten
yarıçap sırasına dizili, rastgeleyi taban almak modele haksız avantaj verir).

21 karttan 49.699 örnek, **kart bazlı 5 katlı** çapraz doğrulama:

| model | hedef | ikili doğruluk | skor hızlanması |
|---|---|---|---|
| mean (taban) | — | 0.500 | 1.00x |
| **ridge** | **sign** | **0.714** | **1.56x** |
| gbt | score | 0.581 | 1.53x |
| ridge | score | 0.691 | 1.51x |
| gbt | value | 0.698 | 1.36x |

Yani öğrenilecek gerçek bir sinyal var. **Ama uçtan uca yansımıyor.** Modelin
hiç görmediği kartlarda (eğitimden çıkarılarak), 5 sn bütçe:

| kart | önce | `auto` | `learned` |
|---|---|---|---|
| pic_programmer | 45 | 94 | 94 |
| complex_hierarchy | 54 | 94 | 94 |
| sonde xilinx | 73 | 100 | 100 |
| interf_u | 5 | 12–14 | 12–15 |
| jetson (1125 bileşen, 60 sn) | 93 | 93.3 | 93.3 |

19 demo kartlık tam regresyon paketinde (bütçe 15 sn) `learned` **19 kartın
19'unda `auto` ile birebir aynı** sonucu veriyor, hiçbirinde gerileme yok.
`interf_u` satırındaki oynama üç tekrarda `auto` için de aynı aralıkta çıkıyor
— duvar saati bütçesinden gelen gürültü.

Sebep: bu bütçelerde `auto` zaten doyuma ulaşıyor. Sıralamayı hızlandırmak
ulaşılabilir **tavanı** yükseltmiyor, sadece oraya daha çabuk varıyor.
`learned` bu yüzden `force`/`anneal` gibi bir **araştırma yerleştiricisi**;
üretim yerleştiricisi hâlâ `auto`.

### 11.6 Yol boyunca bulunan iki gerçek problem (tekrar keşfetmeyin)

**1. Etiket seçimi model seçiminden daha önemli.** İlk çalışan model `sign`
hedefiyle ("hakemi mutlu eder mi") eğitildi ve `complex_hierarchy`yi
94 → 81'e **düşürdü** — üstelik HPWL'i iyileştirerek (1680 → 1594 mm). Veri
kümesine bakınca sebep göründü: etiketi pozitif olan hamlelerin **%81'i skoru
hiç değiştirmiyor**, yalnızca teli birkaç mm kısaltıyor (skor 0.1 adımlarla
yuvarlanıyor, HPWL ise eşitlik bozucu). Model bunları öğrenip cilayı mikro
HPWL kazançlarına yönlendirdi; hakemin saydığı hatalar açık kaldı. Kural:
**modele neyi sıralamasını istiyorsak etiket tam olarak o olmalı**
(`--target score`). Aynı sebeple `train.py`'de kazanan, "her iyileşme"
hızlanmasına değil **skor artıran hamle** hızlanmasına göre seçiliyor.

**2. Her sıra bilgisiz değildir — modeli her yere sokmayın.** Onarım
aşamasında hamleler zaten anlamlı bir sırada üretiliyor: yarıçap artan, yani
"en küçük yer değiştirme önce". Bu muhafazakâr sıra komşu kısıtları bozmadığı
için değerlidir; modelin "tek başına en çok iyileştiren" hamlesi ise büyük
sıçramalar seçip başka bulguları açıyordu (dört model varyantının **dördü de**
`complex_hierarchy`yi 84–89'a düşürdü). Sıralayıcı bu yüzden **yalnızca ince
ayar aşamasında** devreye giriyor — orada sıra bugün zaten `rng.shuffle` ile
rastgele, yani kaybedilecek bilgi yok. Bu kısıtlamadan sonra hiçbir varyant
gerileme yapmadı.

Bir üçüncüsü daha var, küçük ama sinsi: ilk metrik sürümünde `mean` taban
çizgisi 1.07x "hızlanma" ve 0.748 ikili doğruluk gösteriyordu. Sabit tahmin
eden bir model bunları veremez — beraberlik durumu yanlış sayılıyordu. Taban
çizgisinin **tam olarak** 1.00x ve 0.500 vermesi artık test ediliyor
(`MetricTests`). Bir ML hattında ilk kurulacak şey taban çizgisidir; taban
yanlışsa üstündeki her sayı yanlıştır.

### 11.7 Bilinen sınırlar (Aşama 5)

- **Uçtan uca kazanç yok** (§11.5). Altyapı hazır, model yeterince iyi değil.
- Veri kümesi yalnızca **KiCad demo kartlarından** toplandı (21 kart). Gerçek
  bir üretim kartı havuzu çok daha çeşitli olurdu.
- Öznitelikler yalnızca **öteleme + döndürme** hamlelerini tanımlar; katman
  değiştirme, takas (swap), grup taşıma yok.
- GBT eğitimi saf Python: 50 bin satır / 60 ağaç ≈ 14 sn. Veri 10 katına
  çıkarsa eğitim dakikalara çıkar; o noktada numpy tartışması açılır.
- `--target sign` ile eğitilmiş bir modeli **onarım aşamasına** bağlarsanız
  §11.6'daki gerileme geri gelir. Sıralayıcının nereye bağlandığını
  `refine.polish` içindeki `rank=True` çağrısı belirliyor.

### 11.8 Sıradaki adım (öneri)

Kazanç, sıralamayı hızlandırmakta değil **arama uzayını genişletmekte**
görünüyor: `auto` doyuma ulaşıyor çünkü hamle repertuarı dar (tek bileşen
öteleme/döndürme). Model bir kez kurulduğuna göre, pahalı ama güçlü hamleleri
(iki bileşen takası, küme taşıma, katman değiştirme) **ucuza eleyebilecek**
bir aday üreteci olarak kullanmak daha umut verici. Yani modeli mevcut
adayları sıralamak için değil, **daha çok aday üretmeyi karşılanabilir kılmak**
için kullanın.

---

## 12. Aşama 0-5 yeniden doğrulama (2026-08-26)

Tüm aşamalar sıfırdan koşuldu.

| Ne | Sonuç |
|---|---|
| Birim testleri | **111 test, hepsi geçiyor** (52 sn) |
| Referans skorlar (0/1) | pic_programmer 45, video 29, ecc83 100, bench_good 67, bench_bad 2 — **hepsi aynı** |
| `kicad-cli` entegrasyonu (1) | 10.0.4 bulundu, ERC/DRC koştu |
| Çıkış kodları (0/1) | temiz 0, bulgulu 1, eksik proje 2 |
| IPC (2), KiCad kapalıyken | temiz hata + çıkış 2, karta dokunulmadı |
| Hakem doğrulaması (3) | `identity` kazancı +0.0 |
| Regresyon paketi (3+5) | **19 kart × 2 yerleştirici, hiçbirinde gerileme yok** |
| Şematik okuma (4a) | 15 demo projesi, 4.874 sembol, 16.154 pin, **0 bozuk parantez** |
| Netlist kalkanı (4b) | R1 (+12.7, −10.16) → `/VPP_ON` VCC'ye kaynıyor (12→15 pin), **yazma reddedildi, dosya bayt bayt aynı** |
| Atomik yazma (4c) | 230.132 bayt yazıldı + yedek; yazılan dosyanın netlist'i **birebir aynı** (111 net / 236 pin) |
| Açık-proje koruması (4c) | `~pic_programmer.kicad_pro.lck` varken çıkış 2, yazma yok |
| Bağlantı koruyan taşıma (4d) | R1 (78.74, 43.18) → (81.28, 43.18), tel ucu 2 / property 5 birlikte taşındı |
| Şematik yerleştirme (4e) | pic_programmer kök 985.5 → 976.6 mm; vme-wren `/fpga/fpga-config` 1206.5 → **1069.1 mm** (−%11.4), kalkan temiz |
| Bus koruması (4e) | bus'lı sayfalarda taşıma önerilmiyor (varsayılan) |
| ML hattı (5) | 21 karttan 49.699 örnek toplandı, 3 model × 3 hedef eğitildi ve ölçüldü |

**Doğrulama sırasında görülen tek sapma** — HANDOFF'un 4e bölümünde "video/RAMS
%21" yazıyor; o sayfada 2 bus öğesi var ve bus koruması **sonradan** eklendiği
için artık taşıma önerilmiyor. Gerileme değil, bilinçli muhafazakârlığın
sonucu. Bus'sız sayfalarda 4e ölçümleri korunuyor (yukarıdaki fpga-config
satırı).

---

## 13. Aşama 6 / Faz A — geniş hamle repertuarı + model filtresi

Yol haritasının A1–A3 adımları. **Sonuç kısmen olumsuz ve bu bölüm asıl olarak
onu kaydediyor**: altyapı çalışıyor, ölçümler net, ama Faz A'nın dayandığı
"repertuar darlığı tavanı belirliyor" varsayımı ölçüldüğünde büyük ölçüde
çürüdü. Aynı yola tekrar girilmesin diye sebepleri aşağıda.

### 13.1 Ne inşa edildi

| Parça | İş |
|---|---|
| `base.Compound` | Birleşik hamle: aynı anda birden fazla bileşen. Tek bileşenli hamle 1 elemanlı özel hali |
| `placement/repertoire.py` | `swaps` (takas), `clusters` (IC + uyduları), `regions` (boş bölgeye sıçrama) |
| `refine.polish` 3. aşama | Geniş repertuar, `keep` ile değerlendirme bütçesi sabitlenmiş |
| `features.py` v2 | Birleşik hamleleri **doğru** hesaplar + 8 birleşik öznitelik (51 → 59) |
| `metrics.recall_at_k` | Eleme riski: top-K kesiminden kaç iyileşme sağ çıkıyor |
| `collect --saturate` | Doymuş durumdan da örnekleme |
| `tests/test_repertoire.py` | 15 test |

Birleşik hamle **şart**tı: takas ancak iki bileşen aynı anda oynarsa işe yarar.
Ara adımdan gitmek (önce A, sonra B) her seferinde çakışma üretir ve hakem ara
durumu reddeder.

### 13.2 Ölçüm 1 — repertuar gerçekten iyileşme içeriyor mu? **Evet, ama HPWL'de**

Dar repertuarın tükendiği (doymuş) bir yerleşimde, adayların hakemin sıralama
anahtarını (`better_than`) iyileştirme oranı:

| üretici | pic_programmer | interf_u |
|---|---|---|
| kümе taşıma | **%28.3** | **%20.5** |
| takas | %1.8 | %3.2 |
| bölge sıçraması | %0.0 | %1.7 |

⚠️ **Bu sayıları yanlış okumayın** — ilk okuyuşta ben okudum. `better_than`
sözlükseldir ve skor eşitken **HPWL** karar verir. Aynı hamlelerin *skoru*
artırma oranı yalnızca **%0.3**. Yani geniş repertuar güçlü bir **tel uzunluğu**
optimizasyoncusu, ama kural bulgularını neredeyse hiç kapatmıyor. Skor
bulgulardan geldiği için tavan da bu yüzden yerinde duruyor.

`regions` bu ölçümle **kapatıldı**: hiçbir şey bulmuyor ama adayların üçte
birini yiyordu (`include_regions=True` ile açılır).

### 13.3 Ölçüm 2 — bütçe politikası: üç deneme, üçü de öğretici

3. aşama ilk sürümde **hiç çalışmadı**. Sebep: 1. ve 2. aşama kendiliğinden
bitmiyor. Durma şartı "bir tur gez, hiçbiri iyileşmesin"; HPWL bir eşitlik
bozucu olduğu için her zaman birkaç mikron kazandıran bir kaydırma bulunuyor.

| deneme | 19 kartlık pakette sonuç |
|---|---|
| a) Sabit %30 pay kes | **Berabere**: StickHub +1.2, video +3.3 / complex_hierarchy −2.8, interf_u −2.3 |
| b) "Durgunluk yalnızca SKOR artışında sıfırlansın" | **Daha kötü**: 2 iyi, 3 kötü (complex_hierarchy −5.5) |
| c) 1. ve 2. aşamadan zaman **çalma**, geniş aşamayı opt-in yap | Gerileme riski **sıfır** — seçilen |

(b)'nin başarısızlığı en öğretici olanı: **sadece HPWL kısaltan hamleler boşa
gitmiyor, plato aşma mekanizması onlar.** Bileşenleri yavaş yavaş yeniden
konumlandırıyorlar ve skor kazancı ancak birkaç adım sonra ulaşılabilir hale
geliyor. "Skoru artırmayan hamle zaman israfıdır" sezgisi ölçümle çürüdü.

Bu yüzden geniş aşama **varsayılan olarak kapalı**: `auto` commit edilmiş
davranışını birebir koruyor.

### 13.4 Ölçüm 3 (A3) — eleme riski ve K seçimi

`recall_at_k` ile, 21 karttan 67.511 örnek üzerinde (doymuş başlangıçlar dahil):

| K | hit (parti) | recall |
|---|---|---|
| 4 | %92.1 | %50.5 |
| **8** | **%96.8** | %72.4 |
| 12 | %96.8 | %83.8 |
| 24 | %100 | %100 |

Karar verdirici sütun `hit`: yerel arama ilk iyileşmeyi kabul edip durduğu için
top-K içinde **en az bir** iyileşmenin sağ kalması yeterli. `WIDE_KEEP = 12`
artık tahmin değil, bu eğriden geliyor (%95 eşiğini marjla karşılıyor).

### 13.5 Ölçüm 4 (A2) — model filtresi zar atmayı geçiyor mu? **Henüz hayır**

Üç kol, aynı değerlendirme bütçesi, 15 sn:

| kart | `auto` (dar) | +geniş, **zar** seçimi | +geniş, **model** seçimi |
|---|---|---|---|
| StickHub | 55.1 | **56.3** | **56.3** |
| complex_hierarchy | 91.6 | 91.6 | **94.3** |
| interf_u | 15.9 | **27.8** | 21.9 |
| video / pic_programmer / kit-dev | — | değişmedi | değişmedi |

Model, zar atmaya karşı tutarlı bir üstünlük göstermiyor. Sebebi `recall_at_k`
tablosunda görünüyor: aday havuzları zaten küçük (küme partisi ~13, takas ~20),
K = 12 ile **zar da neredeyse her şeyi tutuyor**. Filtrelemenin kazanç
üretebilmesi için havuzun K'dan çok daha büyük olması gerekir — yani
`SWAP_MAX_PARTNERS` sınırının kalkması. O sınır maliyet için konmuştu; kaldırmak
ancak aday üretimi ucuz kalırsa mantıklı.

Model tarafındaki saf sıralama ölçümü ise iyileşti (v2 şeması, doymuş veri):
`gbt:sign` skor artıran hamleyi 3.5 yerine 2.5 denemede buluyor (**1.40x**),
ikili doğruluk 0.694, taban 1.00x/0.500.

### 13.6 Bilinen sınırlar / bir sonraki adım

- Geniş repertuar **opt-in**: `ctx.allow_wide_moves = True` veya
  `polish(..., wide_keep=N)`; `Learned(wide=True)`. Şematik tarafı (4e)
  açıkça kapatır — takas/küme/bölge PCB kavramları.
- Takas ortakları 20 ile sınırlı; model filtresinin anlam kazanabilmesi için
  bu sınırın kalkması gerekir (bkz. 13.5).
- **Faz A'nın asıl dersi:** tavanı belirleyen şey repertuar darlığı değil,
  skorun **kural bulgularından** gelmesi. Bulguları kapatan hamleler
  onarım aşamasının ürettiği hamlelerdir; geniş repertuar tel uzunluğuna
  çalışıyor. Yol haritasında Faz A'dan beklenen kazanç bu yüzden gelmedi.
- Buna göre **Faz C (öznitelik şeması v3 — pin düzeyi geometri, kural tipi
  bağlamı) Faz D'den ve A'nın devamından önce gelmeli**: skor bulgulardan
  geliyorsa, modelin bulguları görmesi gerekir. Şu anki öznitelikler bulguyu
  yalnızca "bu bileşen bir bulguda geçiyor mu" düzeyinde görüyor.

---

## 14. Faz C — öznitelik şeması v3: pin düzeyi geometri + bulgu bağlamı

Faz A'nın dersi şuydu: **tavanı belirleyen repertuar darlığı değil, skorun
kural bulgularından gelmesi.** Faz C bunun doğrudan sonucu — model bulguları
görmüyorsa, skoru neyin artıracağını da göremez.

### 14.1 Kök sebep: merkez yaklaşımı tam da kuralın karar verdiği yerde yanlış

`proximity` kuralı (kural setinin en yaygın tipi) **pin-pin** mesafesi ölçer:

```python
dist = target.distance_to(partner)   # ikisi de PinRef, pad konumları çözülmüş
```

v1/v2 öznitelikleri ise bileşen **merkezleri** arasındaki mesafeyi kullanıyordu.
SOIC-20'de bir pin merkeze ~5 mm uzakta olabilir — kuralın limitiyle (6-10 mm)
**aynı mertebede**. Yani vekil, kuralın karar verdiği eşiğin tam çevresinde
sistematik olarak yanılıyordu.

### 14.2 Ne eklendi

**`rules.Finding` iki yeni alan** (ikisi de varsayılanlı, geriye uyumlu):

- `rule_type` — `proximity`, `courtyard_overlap`... `rule_id` kullanıcının
  verdiği addır ve projeden projeye değişir; **tip sabittir**. `run_rules`
  merkezî olarak dolduruyor, 18 kurulum noktası değişmedi.
- `pins` — bulguyu üreten pin kimlikleri (`["U2.14", "C1.1"]`), `refs` ile
  aynı sırada. Bu olmadan ölçümü hamleden sonra yeniden hesaplamak mümkün
  değil: yalnızca referansı bilmek pinin nerede olduğunu söylemez.

**`features.py` v3** (59 → 75 öznitelik):

| blok | ne verir |
|---|---|
| `pin_span` | Merkezden en uzak pine mesafe — merkez tabanlı özniteliklerin **ne kadar yanılabileceği** |
| `pin_partner_min_*` | Pinlerin net ortaklarının pinlerine gerçek en kısa mesafesi |
| `rule_*` (8 adet) | Açık bulgunun **tipi** — `proximity` "yaklaştır", `courtyard_overlap` "uzaklaştır" demek; model bunu göremezse iki zıt isteği aynı sinyal sanar |
| `finding_slack_before/after` | `(ölçülen − limit) / limit`; **`proximity` için hamleden sonra birebir yeniden hesaplanır** |
| `finding_closed` | Hamle bulguyu kapatıyor mu (0/1) |
| `move_toward_finding` | Hamle vektörü ile karşı pine yön vektörünün kosinüsü |

Doğrulama (`bench_bad`, `U1.20 → C2.1`, ölçülen 16.5 / limit 6.0):

| hamle | slack önce → sonra | yön |
|---|---|---|
| yerinde dur | 1.75 → 1.75 | 0.00 |
| partnerin üzerine git | 1.75 → **0.08** | +0.99 |
| 30 mm uzağa | 1.75 → 4.00 | −0.66 |

Testler yerel yeniden hesabı **kural motorunun kendi ölçümüyle** karşılaştırıyor.

### 14.3 Yol boyunca bulunan gerçek hata: yuvarlanmış "önce", tam "sonra"

İlk sürümde `finding_slack_before` bulgunun sakladığı `measured` değerinden
geliyordu — ama `rules.py` onu `round(dist, 2)` ile saklıyor. Tam hesaplanan
"sonra" ile yuvarlanmış "önce"yi karşılaştırmak, farka **~1.3×10⁻⁴'lük
sistematik bir yanlılık** sokuyordu ve model esas olarak farka bakıyor.
Çözüm: `proximity` için "önce" de yeniden hesaplanıyor, ikisi aynı zeminde.

Aynı sınıftan bir hata Aşama 4e'de de çıkmıştı (yuvarlanmamış kayan noktalar
`_boxes_overlap`'i ters çeviriyordu). **Bu projede tekrar eden bir tuzak:
aynı büyüklüğün iki farklı hassasiyetteki hâlini karşılaştırmayın.**

### 14.4 Ölçüm — v3 yardımcı oluyor, ama mütevazı

Kart bazlı 5 katlı çapraz doğrulama, aynı protokol, aynı kartlar:

| veri | model | ikili doğruluk | skor hızlanması |
|---|---|---|---|
| v2 | mean (taban) | 0.500 | 1.00x |
| v2 | ridge:sign | 0.670 | 1.29x |
| v2 | gbt:sign | 0.674 | 1.26x |
| **v3** | **ridge:sign** | **0.681** | **1.38x** |
| v3 | gbt:sign | 0.672 | 1.32x |

Eleme eğrisi belirgin biçimde iyileşti — %95 `hit` için gereken K **8 → 4**:

| K | v2 hit | v3 hit |
|---|---|---|
| 4 | %92.1 | **%95.2** |
| 8 | %96.8 | %95.2 |
| 12 | %96.8 | %97.6 |
| 24 | %100 | %100 |

Yani model aynı güvenle **yarı yarıya daha az aday** ile çalışabiliyor. Bu, Faz
A'nın tıkandığı yer için doğrudan anlamlı (havuz K'dan çok daha büyük
olduğunda filtreleme kazanmaya başlar).

Yeni öznitelikler gerçekten kullanılıyor: `finding_closed` GBT'nin en çok
böldüğü 5. öznitelik, `rule_courtyard_overlap` 6.

### 14.5 Uçtan uca: yine fark yok

Modelin hiç görmediği dört kartta (eğitimden çıkarılarak), 15 sn:

| kart | önce | `auto` | `learned` v3 |
|---|---|---|---|
| pic_programmer | 45 | 93.8 / 1379 mm | 93.8 / **1365 mm** |
| complex_hierarchy | 54 | 97.1 / 1536 mm | 97.1 / **1520 mm** |
| interf_u | 5 | 30.1 | 30.1 |
| video | 29 | 37.8 | 37.8 |

Skorlar aynı, tel uzunluğu iki kartta kıl payı daha iyi. **Aşama 5'ten beri
değişmeyen tablo:** model sıralamayı ölçülebilir biçimde iyileştiriyor, ama
`auto` bu bütçelerde zaten doyuma ulaştığı için kaliteye yansımıyor.

### 14.6 Maliyet

Öznitelik çıkarımı 72 µs → **134 µs** (pin-pin taraması yüzünden, yaklaşık iki
kat). Tam değerlendirme `pic_programmer`da 6.1 ms, yani oran 85x'ten ~45x'e
düştü. Hâlâ geniş bir marj, ama şema büyümeye devam ederse bu oran izlenmeli —
sıralamanın anlamı ucuz olmasından geliyor.

### 14.7 Değerlendirme ve sıradaki adım

Faz C hedefini tuttu: model artık bulguyu görüyor ve bunu kullanıyor; sıralama
ve özellikle **eleme** kalitesi ölçülebilir biçimde arttı. Ama uçtan uca kazanç
üç fazdır gelmiyor ve sebebi artık iyice belirginleşti:

> `auto`'nun bulduğu yerel en iyi, **arama sırasından bağımsız**. Modeli
> hızlandırmak ya da eleme kalitesini artırmak oraya daha çabuk götürüyor,
> daha iyi bir yere değil.

Buradan iki dürüst çıkış var:

1. **Kabul kuralını değiştirmek** (tepe tırmanışından çıkmak): tavlama benzeri
   bir kabul, kötüleştiren hamleleri de sınırlı ölçüde alır ve yerel en
   iyiden kaçar. Model o zaman "hangi kötüleşmeyi göze alalım" sorusunu
   cevaplar — bu, sıralamadan nitel olarak farklı ve gerçekten tavanı
   ilgilendiren bir iş. Gerileme koruması yine son sözü söyler.
2. **Faz B (veri popülasyonu)**: 21 demo kartı hâlâ tek veri kaynağı ve
   `synth.py` parametrik hâle getirilirse yüzlerce kart üretebilir.

Faz D (öğrenilmiş hakem) hâlâ en iddialı yol ama (1) olmadan onun da aynı
tavana daha hızlı varmaktan başka bir şey yapmayacağı artık ölçülmüş
görünüyor.

---

## 15. Faz E — kabul kuralı: tepe tırmanışından tavlamaya (ÖLÇÜLDÜ, OLUMSUZ)

Üç fazın ortak sonucu şuydu: model sıralamayı iyileştiriyor ama `auto`'nun
vardığı yer değişmiyor, çünkü **`auto`'nun bulduğu yerel en iyi arama
sırasından bağımsız.** Bu fazın hipotezi: sorun sıra değil **kabul kuralı**.

Sonuç: hipotez ölçüldü ve **doğrulanmadı** — ama başarısızlığın sebebi, bu
projede iki ayrı fikri arka arkaya öldüren tek bir yapısal soruna işaret
ediyor. Asıl kayıt bu.

### 15.1 Hipotez

`refine.py:312` aramanın tamamını belirliyordu:

```python
if ev.better_than(current_eval):   # yalnizca KESIN iyilesme
```

Tepe tırmanışı, hiçbir **tek** hamlenin iyileştiremediği noktada durur. Ama o
nokta kartın ulaşılabilir en iyisi değil. Klasik tuzak: `C1`'i `U2.14`'ün
yanına götürmek gerekiyor ama orada `R5` var. `C1`'i taşımak çakışma üretir
(reddedilir), `R5`'i çekmek `R5`'in kendi kuralını bozar (reddedilir). İki
adımlık dizinin **sonu** iyi, **ilk adımı** kötü — tepe tırmanışı ilk adımı
asla atmaz.

### 15.2 Ne inşa edildi

- `Evaluation.gain_over(other)` — sözlüksel sıralamayı tek sayıya indirir.
  `key` karşılaştırmaya yeter ama `exp(−|Δ|/T)` skaler ister.
  **`ml/collect.label_of` artık bunu çağırıyor**: eğitim etiketi ile tavlama
  enerjisinin ayrışmaması önemli, ikisi de aynı büyüklük.
- `refine.Metropolis` — kötüleşen hamleyi `exp(−|Δ|/T)` ile kabul eder.
  Sıcaklık **kendini ölçer**: ilk 25 reddin medyanı × `heat`. Sabit bir T
  kartlar arası anlamsız olurdu (skor cezası bileşen sayısına bölünüyor).
- `polish(accept=...)` — **gezinen durum ile kayıt ayrıldı**: `current`
  kötüleşebilir, `best` asla. `polish` her zaman `best`'i döndürür, yani
  Aşama 3'ün monotonluk garantisi olduğu gibi duruyor (teste bağlandı:
  kasten "her kötüleşmeyi kabul et" ayarıyla bile çıktı başlangıçtan kötü
  değil).

### 15.3 Ölçüm — üç deneme

**(a) Kabul kuralını baştan gevşet** (medyan sıcaklık, tasma yok):

| kart | tepe | tavlama |
|---|---|---|
| tinytapeout | 80.3 | **81.2** |
| video | 29.3 / 25e | **31.2 / 23e** |
| kit-dev | 89.4 | 89.4 |
| pic_programmer | 93.8 | 90.9 |
| **interf_u** | 25.7 | **6.1** ⟵ çöküş |

`interf_u`'da kötü hamlelerin **%38'i** kabul edilmiş: arama tırmanmak yerine
gezinmiş ve iyi bölgeye hiç ulaşamamış.

**(b) Soğuk başlangıç (heat=0.15) + tasma (leash=2.0)** — felaket önlendi:

| kart | tepe | tavlama |
|---|---|---|
| kit-dev | 89.4 | **91.6** |
| interf_u | 25.7 | 21.9 |
| pic_programmer | 93.8 | 90.9 |
| tinytapeout | 80.3 | 79.4 |

Hâlâ net negatif. Desen her iki ölçümde de aynı: **tavlama, tırmanışın
gerçekten tıkandığı kartlarda kazandırıyor, hâlâ verimli olduğu kartlarda
kaybettiriyor.** Faz A'daki kuralın aynısı — üretken aşamadan zaman çalma.

**(c) Kaçış aşaması: yalnızca ARTAN bütçe** (4. aşama, `accept` verilirse):

7 kartın 7'sinde **hiç ateşlenmedi** (kabul/görülen = 0/0). Çünkü artan bütçe
diye bir şey yok.

### 15.4 Asıl bulgu: `polish` "yakınsadım" diyemiyor

(c)'nin hiç çalışmaması tesadüf değil. 1. ve 2. aşamanın durma şartı "bir tur
gez, hiçbiri iyileşmesin" — ama HPWL sözlüksel anahtarda eşitlik bozucu
olduğu için **bir yerlerde her zaman birkaç mikron kazandıran bir kaydırma
bulunuyor.** Aşamalar bu yüzden pratikte hiç bitmiyor.

Bu tek olgu artık **iki ayrı fikri** öldürdü:

| fikir | nasıl öldü |
|---|---|
| Faz A: geniş repertuar (takas/küme) | 3. aşamaya hiç sıra gelmedi; pay kesince de üretken aşamadan çalmış olduk |
| Faz E: kaçış aşaması | Artan bütçe hiç oluşmadı |

Ve "yalnızca skor artışını say" şeklindeki bariz çözüm Faz A'da ölçüldü,
**daha kötü** çıktı: sadece HPWL kısaltan hamleler boşa gitmiyor, plato aşma
mekanizması onlar.

Yani eksik olan şey, ikisinin arasında bir yerde: **azalan getiri testi.**
2. aşama, HPWL iyileşme *oranı* anlamsızlaşınca durmalı; sıfırlanınca değil.
Şu an "0.001 mm de bir iyileşmedir" diyor ve bu yüzden hiçbir zaman
devretmiyor.

### 15.5 Durum ve öneri

Kod depoda ve **varsayılan olarak kapalı**: `accept=None` bugünkü davranışın
birebir aynısı, gerileme riski sıfır. Ölçüm altyapısı (`gain_over`,
`Metropolis`, gezinen/kayıt ayrımı, kaçış aşaması) kurulu ve testli; hipotez
yeniden denenmek istendiğinde sıfırdan yazılmayacak.

**Sıradaki doğru iş, ML değil:** `polish`'e bir yakınsama ölçütü koymak.

    2. asama, son N denemede elde edilen toplam `gain_over` iyilesmesi
    baslangictaki tipik iyilesmenin %X'inin altina duserse dursun.

Bu tek değişiklik hem Faz A'nın hem Faz E'nin önünü açıyor; ikisi de o kapı
açılmadan ölçülemez durumda. Öncelik sırası bu yüzden değişti:

1. **Yakınsama ölçütü** (yukarıdaki) — her şeyin ön koşulu
2. Faz E'yi (kaçış) yeniden ölç — artık gerçekten çalışacağı için
3. Faz B (veri popülasyonu: `synth.py`'yi parametrik yap)
4. Faz D (öğrenilmiş hakem)

---

## 16. Faz F — `polish`'e yakınsama ölçütü

§15'in bulgusu şuydu: `polish`'in aşamaları hiç bitmiyor, bu yüzden Faz A
(geniş repertuar) ve Faz E (kaçış) ölçülemez durumda. Bu faz o kapıyı açıyor.

### 16.1 Dört ölçüt denendi, üçü çalışmadı

| ölçüt | sonuç |
|---|---|
| **a)** "Bir tur gez, hiçbiri iyileşmesin" (mevcut) | Hiç ateşlenmiyor: HPWL eşitlik bozucu olduğu için bir yerlerde her zaman birkaç mikron kazandıran bir kaydırma var |
| **b)** "Yalnızca skor artışını say, hemen dur" | Faz A'da ölçüldü, **daha kötü**: 2 iyi / 3 kötü, `complex_hierarchy` −5.5. HPWL hamleleri boşa gitmiyor — **plato aşma mekanizması onlar** |
| **c)** Azalan getiri (fazın kendi başındaki tipik getiriye oran) | Hiç ateşlenmedi. Ölçüldü: faz 2'de getiriler **azalmıyor**, baştan tekdüze önemsiz — `pic_programmer`da referans 1.2×10⁻⁴, kuyruk 2–7×10⁻⁵, hep referansın ~%30'u. Azalma yok ki azalan getiri ölçülsün |
| **d)** **Skor sabrı** — seçilen | Çalışıyor: `pic_programmer`da faz 2, 525 değerlendirme sonra devrediyor |

**Çalışan ölçüt (`_Convergence`):** kayıttaki **skor** son `patience`
değerlendirmedir artmadıysa aşama devreder. Birim olarak "değerlendirme"
seçildi çünkü bütçeyi gerçekten yiyen o; bileşen saymak kart büyüklüğüne göre
anlamını değiştiriyor. (b)'den farkı sabrın **cömert** olması (varsayılan 400):
HPWL hamlelerine plato aşmak için bol yer bırakıyor ama sonunda pes ediyor.

### 16.2 Varsayılan davranış neden değişmiyor

Kontrol `handoff` kapısının arkasında:

```python
handoff = wide_keep > 0 or accept is not None
```

Devredilecek bir aşama yoksa erken durmak bütçeyi boşa harcamak olurdu —
mikron kazançları küçük ama sıfırdan büyük. Varsayılan yapılandırmada
(`wide_keep=0`, `accept=None`) yakınsama hiç sorgulanmaz.

### 16.3 Ölçüm: kapı açıldı, ama `auto` içinde işe yaramıyor

**Çıplak `polish` ile, 20 sn tek koşu** (8 kart): yakınsama + geniş repertuar
4 kartta kazandırıyor, hiçbirinde kaybettirmiyor — toplam skor 521.1 → **531.4**
(`StickHub` +1.2, `pic_programmer` +2.9, `interf_u` +4.1, `complex_hier` +2.1).
Kaçış aşaması eklemek bunu 530.2'ye **düşürüyor**.

**19 kartlık pakette `auto` ile, bütçe 15 sn**: tablo tersine dönüyor —
2 iyi / 4 kötü, toplam 1632.0 → 1624.5.

⚠️ **Buradaki fark benim ölçüm hatamdı ve kaydedilmeye değer:** ilk
karşılaştırmayı çıplak `polish` üzerinde yapıp `auto`ya genelledim. `auto` ise
kaba yerleşim + **iki ayrı cila koşusu** + `keep_best` demek; her `polish`
çağrısına toplam bütçenin ancak üçte biri düşüyor (15 sn → ~5 sn → ~800
değerlendirme). O pencerede skor sabri ya **çok erken** ateşleniyor (400
değerlendirme, faz 2'nin ortası) ya da hiç ateşlenmiyor. Yani ölçüt doğru,
ama `auto`'nun bütçe bölüşümü ona yer bırakmıyor.

Bu yüzden geniş repertuar **varsayılan olarak kapalı kalıyor**; yakınsama
ölçütü de onunla birlikte uykuda.

### 16.4 Durum

- `_Convergence` kurulu, testli, belgeli. Faz A ve Faz E artık **ölçülebilir**
  — ikisi de bu ölçüt olmadan çalıştırılamıyordu.
- Tek koşuluk ölçümlerde `complex_hierarchy`, `interf_u`,
  `multichannel_mixer-unrouted` gibi kartların **koşudan koşuya oynaklığı
  yüksek** (aynı kod, aynı tohum: `interf_u` 20–30 arasında geziniyor). Duvar
  saati bütçesi ve makine yükü belirleyici. Küçük farkları tek koşuya bakarak
  yorumlamayın; bu bölümdeki ±2 puanlık farklar gürültü bandının içinde.

### 16.5 Sıradaki adım — 1. madde YAPILDI, bkz. §17

Yakınsama ölçütünün işe yarayabilmesi için **tek bir cila koşusuna yeterli
bütçe** gerekiyor. İki yol var:

1. **`auto`'nun bütçe bölüşümünü gözden geçirmek.** Dört aday (mevcut, kaba,
   cilalı-kaba, cilalı-mevcut) bütçeyi dörde bölüyor. Bu bölüşüm Aşama 3'te
   ölçülmüştü ama o zaman devredilecek bir aşama yoktu; şimdi var.
2. **Uzun bütçeli tek koşu kipini ölçmek** (`polish` doğrudan, 20 sn+).
   Ölçümler orada tutarlı biçimde olumlu.

`patience` bir parametre (`polish(..., patience=N)`); süpürülmesi gereken
sonraki ayar o.

---

## 17. Faz G — `auto`'nun bütçe bölüşümü (2026-08-27)

§16.5'in 1. maddesi. Soru şuydu: dört aday bütçeyi nasıl paylaşıyor ve bu
paylaşım ölçülmüş mü? Cevap: paylaşım Aşama 3'ten kalmaydı ve **üç ayrı
yerde sızdırıyordu**.

### 17.1 Ölçüm — bütçe gerçekte nereye gidiyor

19 kart, bütçe 15 sn, tohum 0. Her faz sarmalanıp payı/harcaması/değerlendirme
sayısı kaydedildi (baz koşu iki kez tekrarlandı, totaller birebir aynı çıktı).

| kart | n | toplam/15s | kaba (pay 6.75) | cila-kaba | cila-mevcut | ms/değerlendirme |
|---|---|---|---|---|---|---|
| pic_programmer | 63 | 15.1 | 6.1 | 5.3 (351 d) | 3.6 (242 d) | 15 |
| video | 189 | 16.2 | 8.3 | 4.1 (33 d) | 2.8 (23 d) | 124 |
| ecc83-pp | 15 | **9.7** | 6.0 | 1.3 (506 d) | 2.5 (1099 d) | 2.5 |
| jetson | 1125 | **82.1** | **77.9** | 0.5 (1 d) | 0.4 (1 d) | 465 |
| vme-wren | 1508 | **167.7** | **141.2** | 3.1 (1 d) | 1.9 (1 d) | 3118 |

Bulgular:

1. **Kaba fazın sert tavanı yoktu.** `cluster` son tarihe yalnızca deneme
   sonunda ve `(it & 255)` aralıklarıyla bakıyordu; açgözlü rötuş turu ise
   tur BAŞINDA. jetson'da tek bir `_attempt` 40 sn sürüyor (payı 5.9 sn).
   Sonuç: 15 sn'lik iş 82–168 sn, cila fazlarına **1 değerlendirme** kalıyor
   ve o kartlarda kaba aday zaten mevcuttan kötü (jetson 89.4 < 93.3).
2. **Seçim maliyeti bütçe dışıydı.** `keep_best` dört adayı yeniden
   puanlıyordu; vme-wren'de 21,5 sn (bütçenin kendisi 15 sn).
3. **Paylar saniye cinsinden, asıl kaynak değerlendirme.** Maliyet 0,4 ms ile
   3118 ms arasında — ~8000×. Aynı %60'lık pay bir kartta 807, başkasında 33
   değerlendirme demek. §16.3'ün teşhisi böylece sayısallaştı: 400
   değerlendirmelik skor sabri 19 kartın 16'sında **ateşlenemiyor**.
4. **Artık devredilmiyordu.** 60/40 önden hesaplanıyordu; birinci cila erken
   tükenince (ecc83: payının dörtte biri) kalan zaman kimseye geçmiyordu.
5. **60/40 ölçüldü ve suboptimaldi.** Cila(mevcut) dalı DOYUYOR: payını
   %40'tan %100'e çıkarmak 17 kartın yalnızca 3'ünde bir şey değiştiriyor
   (toplam +23). Kaba dalı ise hâlâ tırmanıyor.
6. **Kaba payının kendisi (0,45) doğru.** Kaba fazı kaldırmak toplamı
   **60,4 puan düşürüyor** (complex_hierarchy −24,0, mixer-unrouted −15,6,
   video −11,8, sonde −7,7); 0,30'a çekmek gürültü bandında (+4,9, tamamı iki
   oynak karttan). Ham `kaba` adayı hiçbir kartta tek başına kazanmıyor —
   değeri yalnızca cilaya tohum olmak.

### 17.2 Ne değişti

- `cluster.py`: son tarih payı aşamıyor (`min(pay, max(2, pay*0.88))`);
  tavlama kontrolleri 256 → 16 iterasyon; açgözlü rötuşta **her bileşende**
  saat okunuyor.
- `refine.py`: `polish` → `polish_scored` (sonucun `Evaluation`'ını da
  döndürür, `start_eval` ile başlangıcı yeniden puanlamaz). Eski `polish`
  ince bir sarmalayıcı — `sch_place`, `ml.collect` ve testler etkilenmedi.
  `keep_best(..., known=...)` bilinen puanları kabul eder.
- `auto.py`: `POLISH_SPLIT = 0.75` (eskiden gömülü 0,60); ikinci cilanın payı
  **duvar saatinden** yeniden hesaplanır; `keep_best` bütçe dışında hiç
  değerlendirme yapmaz. `COARSE_SHARE` 0,45'te kaldı (bkz. 17.1/6).
- `learned.py`: aynı politikayı `auto`'dan içe aktarır. İki kolun tek farkı
  SIRALAYICI olmalı; bölüşüm de ayrışırsa §13'teki karşılaştırma anlamını
  yitirir.

### 17.3 Ölçüm — önce/sonra (`--suite`, 19 kart, 15 sn, tohum 0)

| kart | önce | HEAD | yeni | fark | süre HEAD → yeni |
|---|---|---|---|---|---|
| video | 29 | 41.1 | **52.4** | +11.3 | 15.7 → 15.0 |
| interf_u | 5 | 17.2 | **27.8** | +10.6 | 15.1 → 15.0 |
| multichannel_mixer | 98 | 100.0 | 98.3 | −1.7 | 15.1 → 15.0 |
| jetson | 93 | 93.3 | 93.3 | +0.0 | **79.8 → 15.1** |
| vme-wren | 92 | 92.4 | 92.4 | +0.0 | **163.4 → 15.6** |
| diğer 14 kart | | | | +0.0 | ~15 → ~15 |
| **TOPLAM** | | **1616.2** | **1636.4** | **+20.2** | 463 sn → **248 sn** |

- **Bütçe aşımı 215,8 sn → 0,9 sn.** Yumuşak bütçe sözleşmesi geri geldi.
- Hiçbir kartta gerileme yok (iki koşuda da çıkış kodu 0); 134 birim testi
  geçiyor.

`multichannel_mixer` −1,7 dürüst notu: bu kart eşiğin üstünde. Aynı kodla,
aynı tohumla 98,3 ile 100,0 arasında gidip geliyor (yeni kodda
`POLISH_SPLIT=0.60` → 98,3, `0.75` → 100,0; pakette 0,75 ile 98,3). Sistematik
kayıp değil, §16.4'teki oynaklık. Kalan +21,9 puan iki karttan geliyor ve
ikisi de tekrarlanabilir.

### 17.4 Açık kalan

**Payları değerlendirme cinsinden ifade etmek** (17.1/3). Zemin artık hazır:
kaba faz taşmadığı için cila dilimleri öngörülebilir. `patience` süpürmesi
(§16.5) ancak bundan sonra anlamlı — bugün hâlâ kartın büyüklüğüne göre
tamamen farklı sayıda değerlendirme görüyor.

---

## 18. Aşama 4f — kütüphaneden sembol okuma ve şematiğe ekleme (2026-08-27)

Soru şuydu: "şematiğe 5 adet direnç ekle" desem yapabiliyor mu? **Hayır** —
4a–4e var olan sembolleri okuyup taşıyabiliyordu, ama:

- harici `.kicad_sym` kütüphaneleri hiç okunmuyordu (yalnızca dosyanın kendi
  `lib_symbols` bölümü),
- yeni sembol ekleyecek bir yol yoktu,
- netlist kalkanı "hiçbir şey değişmesin" diyordu, yani ekleme yapısal olarak
  her zaman reddedilirdi.

Üçü de kapatıldı.

### 18.1 `symlib.py` — kütüphane okuma

`Device:R` gibi bir kimliği KiCad'in kendi zinciriyle çözer:

    proje/sym-lib-table  ->  %APPDATA%/kicad/<sürüm>/sym-lib-table
                             (type "Table") satırları izlenir

URI'lerdeki `${KICAD10_SYMBOL_DIR}` değişkenleri `os.environ` ->
`kicad_common.json` -> kurulumdan türetilen varsayılan sırasıyla çözülür.
Tablo eski sürüm adını taşıyorsa (`KICAD9_...`) aynı türden değişkene
**düşürülür** — KiCad güncellemesinden sonra sık görülen durum.

Bu makinede 223 kütüphane çözülüyor. `(extends "...")` taşıyan türevler ana
sembolle birleştirilir (özellikler türevin, pin/grafik üstünündür).

### 18.2 `sch_add.py` — ekleme

Üç iş bir arada: kütüphaneden **oku**, tanımı dosyanın `lib_symbols`
bölümüne **birleştir** (yoksa; KiCad dosyayı kendi kendine yeter tutar),
sayfaya örnek **ekle**.

- **Referans**: tüm şematikteki en küçük boş numara (`R1` ve `R3` doluysa
  sıradaki `R2`) — KiCad'in annotation aracıyla aynı davranış.
- **Konum**: sayfada boş hücre taraması (mevcut gövdeler + teller +
  2.54 mm tampon), 1.27 mm ızgarasına oturmuş. `--at` verilirse o kullanılır
  ama yine ızgaraya oturtulur ve **bu bir not olarak bildirilir** — ızgara
  dışı sembolün pinleri tellere denk gelmez.
- **`instances` bloğu**: KiCad 10'da referans sembolün içinde değil bu
  blokta durur. Blok aynı dosyadaki mevcut bir sembolden kopyalanır; böylece
  hiyerarşide birden çok kez örneklenen sayfalarda her örnek doğru referansı
  alır. Eksik olsa Eeschema sembolü `R?` gösterirdi.
- **Güvenlik**: `sch_move` ile aynı boru hattı — varsayılan DRY-RUN, kum
  havuzunda kalkan, yedek, kilit kontrolü, atomik yazma. UUID yalnızca yeni
  düğümler için üretilir.

```powershell
.\.venv\Scripts\python -m pcbqa.sch_add --sch proje\x.kicad_sch `
    --lib-id Device:R --count 5 --value 10k `
    --footprint "Resistor_SMD:R_0805_2012Metric" --apply
```

### 18.3 Kalkanın ekleme sürümü ve orada bulunan gerçek açık

`compare_additive` (bkz. `sch_verify.py`) dört şey ister: (1) var olan
pinlerin bölünüşü aynı kalmalı, (2) **yeni pinler var olan bir ağa
katılmamalı**, (3) hiçbir bileşen/pin kaybolmamalı, (4) eklenenler tam olarak
beklenenler olmalı.

⚠️ **(2) maddesi ölçümle eklendi ve kaydedilmeye değer.** İlk sürümde yalnızca
(1) vardı ve testte açık verdi: yeni sembol var olan bir tele değdiğinde eski
pinlerin **birbirine göre** bölünüşü değişmiyor —

    N1 = {R1.1, U1.3}  ->  N1 = {R1.1, U1.3, R2.1}

— yani sessiz bağlantı kalkandan geçiyordu. Tam da yakalaması gereken şey.
Bilinçli bağlamak isteyen `allow_connections=True` der.

Canlı doğrulama (`pic_programmer` kopyası): R22 kasıtlı olarak J1 pin 1'in
noktasına konduğunda kalkan reddetti (`R22.2 -> /PC-CLOCK-OUT`), dosyaya
yazılmadı, çıkış kodu 1.

### 18.4 Doğrulama

`pic_programmer` kopyasına 5 direnç (`Device:R`, 10k, 0805):

| kontrol | sonuç |
|---|---|
| pcbqa geri okuma | R22–R26, `Device:R`, 10k, 2 pin, ızgarada |
| KiCad netlist | 63 → 68 bileşen, `R?` yok, yeni pinler serbest |
| KiCad ERC | önce 0 ihlal → sonra 10 ihlal, **hepsi** `pin_not_connected` (5 × 2 pin) |
| mevcut devre | 111 ağın bölünüşü değişmedi |
| birim testi | 33 yeni test (toplam 167) geçiyor |

### 18.5 Yol boyunca bulunan gerçek hata

`kicad-cli` bir projeyi açtığında `~<proje>.kicad_pro.lck` bırakıyor ve
**temizlemiyor**. Kalkan "önce" ölçümünü kullanıcının klasöründe alırsa,
hemen ardından gelen yazma kendi bıraktığımız kilidi görüp *"proje KiCad'de
açık"* diye reddediyor. Çözüm: kalkan artık **iki** kum havuzu kopyası
kullanır (önce/sonra); kullanıcının klasöründe hiç `kicad-cli`
çalıştırılmaz. `sch_move` hâlâ eski yolu kullanıyor — aynı düzeltme oraya da
uygulanmalı.

### 18.6 Bilinen sınırlar

- Sembol **tellere bağlanmıyor**: eklenen parçalar serbest durur. Bağlama
  (tel çekme, etiket koyma) bir sonraki adım.
- Çok birimli semboller (74LS125 gibi) her zaman 1. birimle eklenir.
- Footprint kimliği doğrulanmıyor (kütüphanede var mı diye bakılmıyor).
- PCB tarafına yansıtma yok: yeni bileşen karta `Update PCB from Schematic`
  ile gider.

---

## 19. Aşama 4f/4g — §18.6'daki dört sınırın kaldırılması (2026-08-27)

§18 "ekleyebiliyor ama bağlayamıyor" durumundaydı. Dört sınırın dördü de
kapatıldı.

### 19.1 Bağlama (`sch_wire.py` + `--connect`)

İki yol, ikisi de KiCad'in kendi geometrik bağlantı kuralıyla:

- **`--connect 1=VCC`** — pinin tam üstüne yerel etiket konur. Ad eşleşmesi
  mesafeden bağımsız çalışır; uzaktaki bir ağa bağlanmanın en sağlam yolu.
- **`--connect 2=R1.1`** — iki pin arasına L biçimli dik yol çizilir. İki aday
  (önce yatay / önce dikey) arasından, **üzerinden başka bir pin ya da tel ucu
  geçmeyeni** seçilir: KiCad'de bir telin ortasına değen uç o telle bağlanır,
  yani yanlış aday sessiz bağlantı üretir. Kesişme (X) sorun değildir —
  junction olmadan kesişen teller bağlanmaz. Temiz aday yoksa iş yapılmaz ve
  engel bildirilir (yarım bağlantı yazmaktansa hiç yazmamak).
- Yolun ucu mevcut bir telin **ortasına** düşüyorsa junction eklenir.

### 19.2 Kalkan: "bağlandı mı" da denetleniyor

`compare_additive` artık `expected_joins` alıyor: hangi yeni pinin hangi
mevcut pinle **aynı ağa girmesi gerektiği**. Üç şey birden kontrol ediliyor:

1. beklenen bağlantı gerçekten kuruldu mu (kurulmadıysa reddedilir —
   *tel çizip bağlanmadığını fark etmemek, hiç bağlamamaktan kötüdür*),
2. beklenmeyen bir bağlantı doğdu mu (sessiz bağlantı),
3. mevcut devrenin bölünüşü değişti mi.

### 19.3 Çok birimli semboller

`allocate_units`: bir referans bütün birimleri taşır (U7A, U7B...), yani
`--count 6` = "6 kapı" ve bu iki referansa dağılır. `--unit 3` verilirse her
örnek 3. birimi alır ve kendi referansını. Birimler eksik kalırsa plan
uyarıyor — KiCad ERC'si bunu `missing_unit` diye bildiriyor.

### 19.4 Footprint doğrulama

`symlib` artık `fp-lib-table`'ı da okuyor (bu makinede 155 kütüphane).
`--footprint` kimliği `.pretty` klasöründe aranıyor; yoksa plan engel üretiyor
ve benzer adları öneriyor. `--no-check-footprint` ile atlanabilir.

### 19.5 `pcb_sync.py` — şematikten karta yansıtma

`kicad-cli pcb` alt komutları drc/export/import/render/upgrade ile sınırlı;
"Update PCB from Schematic" **yalnızca GUI'de var**. Bu yüzden kendimiz
yapıyoruz: netlist'ten bileşen ve ağ bilgisi, kütüphaneden `.kicad_mod`, karta
`(path)` bağıyla + pad ağlarıyla ekleme. Eşleme **referansla değil UUID
yoluyla**. Var olan bileşenlere dokunulmuyor; yeniler kartın sağına diziliyor
(düzgün yerleştirme `auto`nun işi).

### 19.6 Uçtan uca doğrulama (KiCad'in kendi araçlarıyla)

`pic_programmer` kopyası: 5 direnç (VCC/GND'ye etiketle bağlı) + 2 kapı
74LS125, sonra karta yansıtma:

| kontrol | sonuç |
|---|---|
| `sch erc` | 0 ihlal (bağlı dirençler); bağlanmamış kapılar için beklenen uyarılar |
| `pcb drc` | **0 ihlal** |
| `pcb drc --schematic-parity` | **0 fark** |
| bağlanmamış bakır | 10 (5 direnç × 2 pad — yol henüz çizilmedi, beklenen) |
| pad ağları | 6/6 bileşen geri okundu, şematikle birebir |
| birim testi | 214 test (61 yeni) geçiyor |

### 19.7 Uçtan uca kontrolde bulunan iki gerçek hata

Bu iki hatayı **birim testleri değil, KiCad'in kendi parite kontrolü** ortaya
çıkardı — bu yüzden kaydedilmeye değer:

1. **Çok birimli parça karta iki kez gidiyordu.** U7A ve U7B şematikte iki
   ayrı sembol düğümü ama kartta **tek fiziksel paket**. Yansıtma referansa
   göre gruplanmıyordu. Düzeltildi; ayrıca `(units (unit (name "A") (pins ...)))`
   eşlemesi de yazılıyor.

2. **`unconnected-(U7-Pad1)` adlarını "yer tutucu" sanıp elemek yanlıştı.**
   Sezgi "boş pad'in ağı olmaz" diyordu; KiCad'in kendisi örnek kartta bu
   adlardan **77 tane** yazıyor. Elediğimizde parite "Ped, şematik tarafından
   verilen ağdan yoksun" diye altı uyarı verdi. Netlist ne diyorsa o yazılır.

Ayrıca `ki_keywords`/`ki_fp_filters` gibi alanlar sembol **örneğine**
yazılmamalı (kütüphane tanımına aittir) ama `Description`/`Datasheet`
footprint'e **taşınmalı** — ikisi de parite uyarısıyla bulundu.

### 19.8 Kalan sınırlar

- Bağlama yalnızca **eklenen** semboller için (`sch_add --connect`). İki mevcut
  pini birbirine bağlayan bağımsız bir komut yok.
- Kartta **yol (track) çizilmiyor**: pad'ler doğru ağda ama bakır bağlantı
  yok. Otomatik yönlendirme kapsam dışı.
- Yansıtma yalnızca **ekler**: şematikten silinen bileşen karttan silinmez,
  footprint değişikliği karta yansımaz.
- `sch_move` hâlâ "önce" ölçümünü kullanıcının klasöründe alıyor (§18.5'teki
  kilit sorunu); `sch_add`/`pcb_sync` iki kum havuzu kullanıyor.
## 20. Aşama 7 — devre tipine göre kural kütüphanesi (2026-08-27)

### 20.1 Neden

Kural motorundaki eşikler (10 mm decoupling, 120 mm HPWL bütçesi) **uydurmaydı**
— makul ama kaynaksız. Oysa gerçek sınır sistemden sisteme değişiyor: bir buck
converter'ın giriş kondansatörü 3 mm'de olmalı, bir LDO'nunki 5 mm yeter, bir
sıcaklık sensörünün pull-up direnci ise **10 mm'den uzak** durmalı.

Dört araştırma ajanı internetten üretici app-note'u ve standart topladı
(~90 kaynak, büyük çoğunluğu birincil). Sonuç `docs/tasarim-kurallari/` altında,
her sayının yanında kaynağıyla.

### 20.2 Araştırmanın asıl bulgusu: çoğu tavsiyenin sayısı yok

Beklenen çıktı bir eşik tablosuydu; çıkan sonuç şu oldu:

> **Birinci sınıf kaynakların çoğu mm cinsinden sayı vermez.** TI, ADI, Richtek,
> ST, Microchip, NXP, Bosch, Sensirion — hepsi "as close as possible" der.

Bosch bunu açıkça gerekçelendiriyor: *"a 'reasonable distance' depends on many
customer specific variables and must therefore be [determined by the customer]"*.

Sayı veren birkaç kaynak bu yüzden orantısız ağırlık taşıyor: **ROHM 66AN015E**
(anahtarlamalı regülatör için sistematik sayısal kontrol listesi — bu alanda
tek örneği), **TI SLVA959B**, **TI SNOA986A**, **TI AN-2155** (sıcak döngünün
EMI'ye etkisinin ölçülmüş verisi), **IPC-2221B / IPC-7351B**.

### 20.3 Kaynaklar çelişiyor — ve çelişkiler gizlenmedi

| Konu | Yayılım | Karar |
|---|---|---|
| USB 2.0 intra-pair | TI'ın 4 dokümanı 2 / 50 / 100 / 150 mil — **75 kat**, biri kendi içinde tutarsız | 50 mil |
| İz genişliği yöntemi | 3 A için 0.90 – 3.00 mm arası — **3.3 kat** | `method:` seçilebilir |
| IPC-2152 daha mı gevşek? | Çıplak temel eğrisi IPC-2221'den **daha muhafazakâr** | IPC-2221B, ΔT parametre |
| Via akım kapasitesi | 0.30 mm: TI 0.84 A, IPC-2221 1.45–1.69 A — **2 kat** | TI (muhafazakâr) |
| 3W mu 5W mu | Folklor 3W; TI'ın tüm HS dokümanları **5W** | 5W |
| 20H kuralı | **Shim & Hubing (IEEE EMC 2001) ölçümle çürüttü** — radyasyon hafifçe artıyor | Genel EMI kuralı olarak kullanma |

İki ajan IPC-2152 konusunda ters şey söyledi; hesap yapılıp Jouppi'nin makalesi
okununca ikisinin de kısmen haklı olduğu görüldü (çıplak eğri vs çarpanlı) —
bu, `ipc2221.py`'nin docstring'ine ve dokümana yazıldı.

### 20.4 Eklenen: bakır okuma

Proje o güne kadar **bakırı hiç okumuyordu** — yalnızca footprint ve pad
konumu. `pcb.py` genişletildi:

- `Track` (net, genişlik, katman, uçlar, `is_outer`, `length_mm`) — `segment`
  ve `arc` düğümleri
- `Via` (net, konum, size, drill, layers)
- `Pad.size_x/size_y/angle/shape` + **`copper_shape()`**

`copper_shape()` gelişmenin en öğretici parçası. Pad'i önce çevreleyen daireye,
sonra kareye yuvarladım; **ikisi de sağlam bir kartta hayali açıklık ihlali
üretti** (0.5 mm ve 0.03 mm). TO-92'nin 1.27 mm köşegen aralıktaki iki yuvarlak
pad'i kare kabul edilince köşeleri çakışıyor. Doğru çözüm şekli **tam**
modellemek:

| Şekil | Gösterim | Doğruluk |
|---|---|---|
| circle | tek nokta + yarıçap | kusursuz |
| oval | uzun eksen boyunca parça + kısa yarım genişlik (stadyum) | kusursuz |
| rect/roundrect | dönmüş dörtgen | roundrect'te küçük fazla tahmin |

Üç şekil de aynı `(noktalar, şişme_yarıçapı)` gösterimine indiği için açıklık
ölçümü tek ifade: `shape_distance(A, B) - rA - rB`.

`geom.segment_distance()` da eklendi: mevcut `_segment_distance` yalnızca uç
noktaları deniyordu ve **birbirini kesen** iki parça için pozitif sayı
döndürüyordu — açıklık kuralında sessiz bir kaçak olurdu.

### 20.5 Eklenen: dört kural tipi

| Tip | Ne ölçer |
|---|---|
| `trace_width` | İz genişliği ≥ akımın gerektirdiği (IPC-2221B ya da ROHM mm/A) |
| `via_current` | Netteki via'ların toplam akım kapasitesi (TI SLVA959B Tablo 3-1) |
| `clearance_voltage` | İki net arası bakır açıklığı ≥ gerilim farkının gerektirdiği |
| `keep_apart` | İki bileşen kümesi arası **minimum** mesafe |

**`keep_apart` beklenmedik biçimde en önemlisi.** Araştırmadaki kuralların
şaşırtıcı bir kısmı "yaklaştır" değil **"uzaklaştır"** diyor: FB izi →
indüktör ≥ 10 mm, I2C pull-up → sıcaklık sensörü ≥ 10 mm (öz-ısınma),
CIN GND ↔ COUT GND ≥ 10 mm (giriş gürültüsü GND üzerinden çıkışa taşınmasın).

Bu, **yerleştiriciyi doğrudan ilgilendiriyor**: `auto` yalnızca HPWL küçültmeye
çalışıyor, yani bu kısıtları sistematik olarak ihlal eder. Skor fonksiyonuna
`keep_apart` cezası eklemek Aşama 8'in ilk adayı.

Bakır kuralları **yönlendirilmemiş kartta sessizce atlanır** — yerleştirme
aşamasında kartta bakır yok, ve orada bulgu üretmek gürültüden ibaret olurdu.

### 20.6 Eklenen: ön ayar kütüphanesi + `include`

`pcbqa/presets/` altında dört YAML (28 kural), her eşiğin yanında kaynağı.
`load_rules` artık `include:` destekliyor (yollar dahil eden dosyaya göre;
dairesel include ve tekrar eden `id` hata verir).

`uretim.rules.yaml` devre tipinden bağımsız ve **sağlam bir gerçek kartta sıfır
bulgu** üretiyor — bu bir testle korunuyor. Diğer üçü ref/net desenlerinin
tasarıma uyarlanmasını gerektiriyor ve dosya başlıklarında öyle yazıyor.

### 20.7 Ölçüldü: yöntem seçimi gerçekten fark ediyor

`pic_programmer` kartının VCC izi 0.8 mm:

| Yöntem | 2 A için gereken | Sonuç |
|---|---|---|
| IPC-2221B, ΔT=10 °C | 0.781 mm | **geçer** |
| ROHM 1 mm/A | 2.000 mm | **kalır** |

Aynı iz, aynı akım, iki savunulabilir kaynak, ters sonuç. Bu yüzden motor tek
bir "doğru sayı" iddia etmiyor; `method`, `delta_t_c`, `copper_oz` parametre.

`clearance_voltage` de doğru ayrım yapıyor: VPP 5 V'ta sessiz, 60 V'ta 0.6 mm
eşiğiyle bulgu, 400 V'ta ayrıca "creepage gerekir" uyarısı.

### 20.8 Kalan sınırlar

Sayısal değeri araştırmada **bulunan** ama ölçülemeyen kurallar; her ön ayar
dosyasının sonunda kendi listesi var. Ortak eksik:

| Gereken veri | Açtığı kurallar |
|---|---|
| **Bakır döküm (zone) okuma** | Sıcak döngü alanı (6 mm² iyi / 18 mm² kötü — TI'ın ölçtüğü), SW bakır alanı ≤ 100 mm², indüktör altında bakır olmaması, termal bakır alanı (1 W → ~20 cm²) |
| İz topolojisi | Stub uzunluğu, ESD izi endüktansı (52 nH → TVS tamamen işlevsiz), Kelvin bağlantı |
| Katman yığını | Via stub/backdrill, gerçek bakır kalınlığı, empedans |
| 3B / yükseklik | Elektrolitik vent boşluğu (Nichicon 2/3/5 mm), konnektör keep-out |
| İç Edge.Cuts | Creepage slot genişliği (PD1 0.25 / PD2 1.0 / PD3 1.5 mm) |

**Zone okuma en yüksek getirili olan:** tek başına anahtarlamalı güç
kaynaklarının en kritik üç kuralını ölçülebilir hale getirir.

Ayrıca: `clearance_voltage` **clearance** ölçer, **creepage değil** — şebeke
izolasyonuna yetmez. İz genişliği hesabı **nominal** bakır kullanır; iç katman
1 oz gerçekte ~25 µm olduğu için iç katman güç izlerinde hesap **~%25
iyimser**.

### 20.9 Testler

`python -m unittest discover -s tests` → **277 test**, hepsi geçiyor
(önceki 214 + `test_copper` 6 + `test_ipc2221` 15 + `test_copper_rules` 30 +
`test_presets` 12).

En değerli olanlar davranışı değil **sessizliği** koruyanlar:
`test_sound_board_at_logic_voltage_is_silent` ve
`test_manufacturing_preset_is_silent_on_sound_board` — ikisi de geliştirme
sırasında gerçekten kırıldı ve pad şekli hatasını yakaladı.
## 21. Aşama 8 — ağırlıklı skorlama, kalibrasyon, alt-devre tanıma (2026-08-28)

### 21.1 Neden

Skor `8 × hata + 2 × uyarı` idi: **yalnızca severity sayılıyordu.** Ölçülmüş
etkisi olan bir kural (TI AN-2155'in sıcak döngü deneyi) ile kaynaksız bir
mühendislik seçimi aynı 8 puanı yiyordu. Ayrıca ceza **ikiliydi** — 0.01 mm dar
bir iz ile 2 mm dar bir iz eşitti.

Nihai hedef üretken tasarım: sistemin kendi bileşenini ekleyip bağlayıp PCB
üretmesi. Zincirin mekaniği zaten var (`sch_add`, `sch_wire`, `pcb_sync`,
`auto`); eksik olan **karar**. Skor bunun uygunluk fonksiyonudur —
yargılayamadığımızı üretemeyiz. Bu yüzden önce skor.

Yol haritası: `docs/yol-haritasi-skorlama.md`.

### 21.2 Evre 1 — ağırlıklı skor (dört faz)

| Faz | Ne | Sonuç |
|---|---|---|
| 1a | `Rule.weight` / `Finding.weight`, `report.penalty_of()` | Geriye uyumlu; ağırlıksız dosya birebir eski skoru üretir |
| 1b | Orantılı ceza: `çarpan = min(1 + \|m−l\|/\|l\|, scale_max)` | Opt-in; gerileme koşumu yapıldı, **gerileme yok** |
| 1c | 28 ön ayar kuralına kanıt gücüne göre ağırlık | Her ağırlığın yanında kaynağı; testle korunuyor |
| 1d | Korpus kalibrasyonu (`harness --score-only`) | **İki gerçek kusur yakalandı** |

**1b'nin gerileme koşumu neden önemsizdi:** ölçekleme *monotondur* — aynı bulgu
kümesi için skor karşılaştırmasının işaretini değiştirmez. Risk gerçekti ama
yapısal olarak hafif çıktı.

**1c'de benimsenen ilke:** kaynak belirsizliği ağırlığı **düşürür**.
`hs-usb-cift-eslestirme` 8 aldı çünkü TI'ın dört dokümanı aynı eşik için 75 kat
farklı değer veriyor.

### 21.3 Kalibrasyonun yakaladığı iki kusur

> Sahaya çıkmış bir karta skorumuz düşük veriyorsa **yanlış olan skordur.**

19 KiCad demo kartı, `uretim` ön ayarıyla:

| Ölçüm | İlk koşum | Sonra |
|---|---|---|
| Medyan | 88.9 | **95.9** |
| Çeyrekler | 40.6/88.9/100 | **80.7/95.9/100** |

**1) Pad katmanları okunmuyordu.** `interf_u`'da `BUS1.29` (VCC) ve `BUS1.60`
(/PC-A2) aynı koordinatta, aralarında **0.000 mm** açıklık ölçülüyordu — gerçek
bir kartta kısa devre demek. Sebep: kart-kenarı konnektörü, pad'ler ön ve arka
yüzde. `Pad.copper_layers` eklendi. Kartın skoru **1.6 → 72.6**.

**2) Ön ayar projenin kendi kararından sapmıştı.** `courtyard` kuralı
`error`/16 yazılmıştı; `default_rules.yaml` **warning** diyor ve gerekçesini
yazmış (StickHub'ı adıyla anarak). Korpus sayısallaştırdı: 19 kartın 5'inde
(%26) çakışma var. Düşük kesinlikli kural ağır ağırlık taşımamalı → `warning`/6.

### 21.4 Zone okuma — tahmin fazla iyimserdi

`Zone`/`ZoneFill` + `Board.copper_area_mm2()` + `copper_area` kuralı eklendi.
"Zone okuma üç kritik kuralı birden açar" demiştim; gerçekte:

| Hedef | Sonuç |
|---|---|
| SW bakır alanı ≤ 100 mm² | ✅ açıldı |
| Termal bakır alanı | ⚠️ kural yazılabilir, eşik güç dissipasyonu beyanı istiyor |
| Sıcak döngü alanı | ❌ hâlâ kapalı — netin alanı değil, **akım yolunun çevrelediği** alan |
| İndüktör altında bakır | ❌ zone ∩ courtyard kesişimi gerek |

**Ders:** alan ölçmek ile geometrik ilişki ölçmek farklı şeyler.

### 21.5 Evre 2 — devre doğruluğu (`circuit.py`)

Motorun ilk **değer** kuralları. `parse_value` (IEC 60062 RKM: `4k7` = 4.7k) +
`i2c_pullup` (NXP UM10204) + `crystal_load` (Microchip AN826) + `fb_divider`
(Richtek AN033) + yeni kural tipi `component_value`.

**Bağımsız doğrulama:** formüller kaynağın kendi sonucunu üretti. 400 pF
fast-mode'da `Rp(min)` = 967 Ω > `Rp(max)` = 885 Ω — düz dirençle çözüm yok.
UM10204 tam bunu söylüyor. Kural bunu "kabul aralığı **boş**" diye bildirir.

İki farklı "eksik" bilinçli ayrıldı: bileşenin değeri çözülemiyorsa **sessizce
atlanır** (tasarım özelliği), kuralın beyanı eksikse **hata** verilir
(yapılandırma hatası).

### 21.6 Sessiz hata: pin adları hiç okunmuyordu

`netlist_from_board` `pinfunction`'ı boş bırakıyordu ve docstring'i "yalnızca
şematikten gelir" diyordu. **Yanlıştı** — 19 demo kartın hepsinde pad'lerde
pinfunction var (vme-wren'de 6828 tane).

Etkisi sessizdi: `function:` seçicisini kullanan **tüm** kurallar hiçbir zaman
eşleşmiyordu ve bu "temiz kart" gibi görünüyordu.

**Nasıl bulundu:** alt-devre tanıma için korpusta buck converter aranırken
hiçbiri bulunamadı. Önce "demolarda buck yok" sandım; taramayı gevşetince pin
adlarının tamamen boş olduğu ortaya çıktı. Yani bir varsayımı sınamak başka bir
hatayı açtı.

### 21.7 Alt-devre tanıma — ad değil topoloji

`subcircuit.py`: imza = bir IC'nin SW pini + o nette bir indüktör. Roller
çıkarılır (CIN, COUT, indüktör, FB dirençleri). Üç gerçek kartta **altı
regülatör** doğrulandı.

Gerçek veri iki kusuru gösterdi; ikisi de sentetik kartta görünmezdi:

- **Pin adında biçimleme:** jetson'daki TPS564247'nin VIN pini `V_{IN}` yazıyor.
  Desen tutmuyordu, CIN listesi boş kalıyordu. `normalize_pin_name()` eklendi;
  jetson'da CIN **0 → 16**.
- **Buck-boost buck sanıldı:** One-Air-Max U5 (BQ25672) indüktörü **iki**
  anahtarlama düğümü arasında. "Diğer uç çıkıştır" varsayımı orada yanlış.

`buck_layout` kuralı ROHM'un listesini bu rollere karşı çalıştırır:

| kart | ad desenli | topolojik |
|---|---|---|
| CM5_MINIMA_3 | 19 bulgu, 19.0 | **1 bulgu, 85.2** |
| One-Air-Max | 32 bulgu, 20.4 | **4 bulgu, 70.3** |
| jetson | — | **0 bulgu, 100.0** |

Buck ön ayarı 9 kuraldan 4'e indi ve yerleşim kuralları için **artık uyarlama
gerektirmiyor.**

### 21.8 ROHM'un kontrol listesi kendi içinde çelişiyor (kanıtlandı)

```
#4-2       FB direnci IC'nin FB pinine  <= 4 mm
Öncelik 2  İndüktör  IC'nin SW pinine   <= 4 mm
=>  üçgen eşitsizliği:  FB<->L  <=  4 + (IC içi SW-FB pin ayrımı) + 4
```

Ölçüldü: One-Air-Max U6'da pin ayrımı 1.20 mm → **üst sınır 9.20 mm**. Yani
#4-1'in istediği "≥ 10 mm" **matematiksel olarak sağlanamaz**. Üç gerçek kartın
üçünde de, sekiz FB direncinin sekizinde de ihlal çıkıyordu.

Bu yüzden `fb_inductor_min_mm` ön ayarda **verilmedi**; gerekçe hem YAML'a hem
teste yazıldı.

### 21.9 Kalan sınırlar

- **Sıcak döngü alanı** hâlâ ölçülemiyor. Zone okuma ve alt-devre tanıma
  eklendi ama yetmedi: anahtarların **IC içi** bağlantısını bilmek gerekiyor.
  Bead: `Kicad-*` (akım yolu topolojisi).
- **Yönlendirme** kapsam dışı; gerçekçi yol dış bir otomatik yönlendiriciyi
  çağırıp çıktısını bizim bakır kurallarımızla denetlemek.
- **`learned` hâlâ `auto`yu geçmiyor** — bu kez gerçekten ölçüldü (§21.11).

### 21.10 ML ölçümü ve içinden çıkan sessiz hata

Skor zenginleştiği için `learned` vs `auto` ölçümü tekrarlandı. **Sonuç
değişmedi** — ama yol boyunca iki hipotez çürüdü ve bir hata bulundu.

**Çürüyen hipotez 1:** "Skor zenginleşince `auto` zorlanır, o zaman sıralamanın
değeri artar." Hayır — zenginleşen skor `auto`yu zorlamadı, **taktı**: zengin
kural kümesiyle `pic_programmer`da sıfır bileşen oynadı. Ve nedeni gradyan
değil **maliyet**ti: `clearance_voltage` tek başına değerlendirmeyi 8.9 ms'den
467 ms'ye çıkarıyordu, 8 s'lik bütçe ~900 denemeden ~17'ye düşüyordu.

Bu, iki gerçek düzeltmeye yol açtı (§21.12).

**Çürüyen hipotez 2:** "`learned`in değeri, değerlendirmenin pahalı olduğu büyük
kartlarda görünür." Hayır. `vme-wren`de (1508 bileşen) tek ölçüm **2983 ms**;
45 s bütçede ~15 deneme kalıyor ve o kadar denemede ne `auto` ne `learned` bir
şey yapabiliyor.

**Bulunan sessiz hata:** `learned`in `DEFAULT_MODEL_PATH`'i `move-v2.json`
diyordu; diskteki tek model `move-v3.json`. Model bulunamayınca sınıf —
belgelendiği gibi — sessizce `auto` gibi davranıyor. Yani **Faz C'den beri
`learned` hiçbir model kullanmıyordu.**

Fark edilmemesinin sebebi öğretici: beklenen sonuç zaten "learned ≈ auto"
olduğu için **hata kendi kamuflajını yaptı.** Bu oturumda ölçümü üç kez yapıp
üçünde de `+0.0` gördüm ve her seferinde "demek ki sıralamanın değeri yok" diye
yorumladım. Dördüncüde "birebir *aynı* olması şüpheli" deyip modele baktım.

> Beklediğin sonucu doğrulayan bir ölçüm, ölçümün kendisinin bozuk olduğunu
> gizleyebilir. "Sonuç beklendiği gibi çıktı" bir doğrulama değil, bir uyarıdır.

Düzeltme: yol artık öznitelik **sürümünden** türetiliyor
(`move-v{FEATURE_VERSION}.json`). Şema değişince yol da değişir ve model
eğitilmemişse boşluk sessiz değil görünür olur.

Gerçek ölçüm (model yüklenmiş, `ModelRanker` 8 s'de 31 kez çağrılıyor):
`bench_bad` 16.5=16.5 · `pic_programmer` 3.0=3.0 · `jetson` 64.3=64.3 ·
`vme-wren` 86.7=86.7. HANDOFF §11'in sonucu **doğru çıktı**, ama artık
artefaktla değil gerçek ölçümle destekleniyor.

### 21.11 İki performans/anlam düzeltmesi

**1) Yerleştirme yönlendirmeyi geçersiz kılar — ama etmiyordu.**
`apply_placement` yalnızca bileşenleri taşıyordu; izler, via'lar ve dökümler
yerinde kalıyordu. Yani bakır kuralları **taşınmış pad'lerle sabit izleri**
karşılaştırıyordu — fiziksel olarak anlamsız. Artık bir bileşen gerçekten
oynadıysa bakır temizleniyor ve kart "yönlendirilmemiş" duruma düşüyor; bakır
kuralları zaten "iz yoksa sessizce atla" diye yazılmıştı.

**2) `clearance_voltage` 6.2× hızlandı.** Sınır kutusu ön filtresi: kutular
şişme yarıçapı kadar büyütülür; iki kutu arasındaki mesafe gereken açıklıktan
büyükse gerçek şekil mesafesi de büyüktür, yani atlamak **güvenli**.
467 ms → 74.8 ms, skor değişmedi. Profil, kalan maliyetin ön filtrenin
*kendisi* olduğunu gösterdi (81 bin kutu karşılaştırması, yalnızca 2.3 bin
gerçek şekil hesabı) — yani filtre işini yapıyor.

### 21.12 Termal: eşik yerine hesap

`copper_area`'nın termal varyantı ön ayarda **yorum satırında** duruyordu ve
sebebi haklıydı: sabit bir "en az N mm²" eşiği savunulamaz. Aynı 1 W'lık
regülatör 25 °C ortamda ~148 mm² ile, 70 °C ortamda ~1885 mm² ile aynı
jonksiyon sıcaklığına ulaşır. Tek bir sayı ikisine birden uyamaz.

Çözüm eşiği düzeltmek değil, **eşiği kaldırmak** oldu. `pcbqa/thermal.py`
Richtek AN044'ün SOT-223 için ölçülmüş θJA eğrisini taşıyor (16 mm² → 135 °C/W,
100 → 107, 2500 → 50, 3600 → 45) ve yeni `thermal` kuralı `Tj = TA + P·θJA`
hesaplıyor. `measured` artık **sıcaklık**, `limit` ise `tj_max_c`.

Ara değerler `log10(alan)` üzerinde doğrusal: dört nokta on yıllık bir alan
aralığına yayılıyor ve aralarındaki eğim decade başına neredeyse sabit
(−35, −41, −32 °C/W). Doğrusal alan üzerinde ara değer almak 100–2500 arasını
aşırı iyimser gösterirdi. Eğri ölçülen noktalardan **tam** geçiyor; yeni bir
fonksiyon uydurulmadı.

Bağımsız doğrulama: 16 mm²'lik standart footprint'te 0.741 W, TA=25 °C'de tam
olarak Tj=125 °C veriyor — AN044'ün kendi PD değeri. Belgedeki iki serbest
hesap da tutuyor: 1 W @ 25 °C → 148 mm² (belge "~120–150"), 1 W @ 70 °C →
1885 mm² (belge "~2000–2200", elle okuma).

**Modül ölçülen aralığın dışına çıkmayı reddediyor.** SOT-223'te 85 °C ortamda
1 W için gereken θJA 40 °C/W'tır — ölçülen en iyi değerin (3600 mm²'de 45)
*altında*. Kural o koşulda "çözüm bakır değil paket/soğutucu" der ve bir alan
**önermez**; öneriyi destekleyen ölçüm yok. Aynı sebeple SOT-23 / SO-8 / DFN-8
tek noktalı verilerle (MaxLinear ANP-02) tutuluyor ama onlarda kural asla
"bakır ekleyin" demiyor — alan bağımlılıkları ölçülmemiş.

**Termal pad seçimi** beyan gerektirmiyor: bileşenin en büyük pad'i alınıyor.
SOT-223, DPAK, D2PAK gibi paketlerde ısıyı taşıyan tab zaten açık ara en büyük
pad. Gerçek kartta doğrulandı — `tiny_tapeout` demosundaki TLV1117LV33'ün
tab'ı (pin 2 → +3V3, 101 mm²) söylenmeden bulunuyor.

Tersi de doğrulandı: `pic_programmer`'ın 7805'inde (TO-220 tabdown) en büyük
pad tab'dır ama **netliste bağlı değildir**. Termal yol tanımsız, kural susuyor.
İkinci büyük pad'e düşmek yanlış olurdu — o VI pini.

Üç bilinçli yanlılık, üçü de **iyimser** yönde, yani gerçek kart daha sıcaktır:
alan ölçümü üst üste binen bakırı iki kez sayar; hesap tek ısı kaynağı varsayar;
eğri tek katlı JESD51 kartında ölçüldü. Bu yüzden bulgu "Tj **EN AZ** …" diyor.

Kural ön ayarda yine **kapalı** — ama artık sebebi farklı: `power_w`,
`ambient_c`, `tj_max_c` tasarım dosyasında yoktur ve beyan edilmeden kural
hata verir. Bu bilinçli: sessizce geçmek kuralı görünmez biçimde etkisiz
bırakırdı (bkz. §21.6, §21.10 — bu projede aynı hata iki kez oldu).

### 21.13 Decoupling: mesafe değil ADET

`circuit.decoupling_counts()` (TI SPRABV2) yazılmış ve test edilmişti ama
**hiçbir kural onu çağırmıyordu** — grep ile doğrulandı. Yol haritasının Evre 2
tablosundaki son doldurulmamış satır buydu ve bu projede aynı sınıf hata
üçüncü kez ortaya çıktı (bkz. §21.6 pin adları, §21.10 bayat model yolu):
yazılmış ama bağlanmamış kod sessizce etkisizdir.

Yeni kural `decoupling_count`, `hs-decoupling-mesafesi`nin kardeşi. O mesafe
sorar, bu adet sorar. Aradaki fark somut: 20 güç pinli bir parçanın tek
kondansatörü 2 mm ötede olabilir — mesafe kuralı **susar**, TI ise 10 adet
ister.

**Seramik IC başına, bulk NET başına.** Ayrım kaynaktan geliyor: seramik
yüksek frekansta çalışır ve ancak yakınsa (6.35 mm, TI SBAA113) iş görür, yani
her yongaya kendi kondansatörü gerekir; bulk bir *rayı* besler, kart genelinde
paylaşılır ve TI onun için mesafe **vermez** — biz de aramıyoruz. İlk sürüm
bulk'u IC başına sayıyordu ve aynı ray üzerindeki üç yonga için aynı eksiği üç
kez bildiriyordu.

**Kaynağın birimi altına inilmedi.** `ceil(n/10)` matematiksel olarak tek güç
pininde bile 1 bulk ister, ama TI'ın birimi "~10 güç topu"dur; o sayı kaynağın
değil tavan fonksiyonunun ürünü. Korpus bunu sayısallaştırdı: eşiksiz hâl
19 kartın 9'unda ateşliyordu (%47) — 1d'nin "çoğunlukta ateşleyen kural
şüphelidir" ölçütünü ihlal ediyordu. `bulk_min_power_pins: 10` ile %11'e
düştü ve kalan iki bulgu da sağlam çıktı: kit-dev-coldfire'ın 29 güç pinli
3.3 V rayında 2 bulk var, 3 gerekiyor; video'nun 63 güç pinli 5 V rayında
2 var, 7 gerekiyor. Bu, `thermal`ın ölçülen eğri dışına çıkmayı reddetmesiyle
aynı ilke.

**Çözülemeyen değer her iki kovaya sayılır.** İlk sürüm yalnızca seramiğe
sayıyordu; pic_programmer'ın `22uF/25V` yazan C3'ü bunu çürüttü — gerçek bir
bulk kondansatörü, ayrıştırılamıyor, ve yalnızca seramiğe sayılsaydı **uydurma
bir bulk eksiği** üretirdi. Yani yanlılık yön değiştiriyordu. Şimdi üç
yanlılığın üçü de iyimser.

Bunun ölçülmüş bedeli var ve gizlenmiyor: `jetson-agx-thor-baseboard` değer
alanına `C_100n_0402` yazıyor — 100 nF seramikler bulk sayılıyor ve o kartta
bulk denetimi etkisiz kalıyor. Alternatif (değer alanından paket adı
ayrıştırmak) yanlış tahminde gerçek bulk'u yok sayardı.

Toprak pinleri `ignore_nets` ile eleniyor: `GND` de `power_in` taşır ve
sayılsaydı gereken adet **iki katına** çıkardı. TI güç *toplarını* sayıyor.

`uretim` ön ayarı etkilenmedi — kural `yuksek-hiz`e eklendi ve 1d kalibrasyonu
birebir aynı: medyan 95.9, çeyrekler 80.7/95.9/100.0.

### 21.14 Ayrık regülatör: yanlış ölçmektense ölçmemek

§21.13'ün sonunda yaptığım tarama, "yazılmış ama bağlanmamış" başka bir kod
bulmadı (`current_capacity_a` `trace_width_mm`'in kullanılmayan tersi,
`hot_loop_area_mm2` test tarafı sarmalayıcı, `i2c_needs_current_source` boş
aralık yolu tarafından zaten kapsanıyor). Ama Kicad-z1d'nin açık bıraktığı
kısım aynı ailenin dördüncü üyesiydi — bu kez **sessizce yanlış ölçüm**.

Sıcak döngü dörtgeni `CIN.VIN -> IC.VIN -> IC.GND -> CIN.GND` **entegre**
regülatör varsayar. Harici FET'li ayrık tasarımda döngü FET'lerin üzerinden
dolaşır ve bu dört pad onu temsil etmez. Kritik olan, hatanın **yönü**: IC'ye
bitişik dört pad **küçük** bir alan verir, yani ayrık ve sorunlu bir kart
TI'ın 6 mm² eşiğini rahatça geçip temiz görünürdü.

Artık `find_buck_converters` SW düğümündeki harici anahtarlama elemanlarını
(`BuckConverter.external_switches`) buluyor ve doluysa `hot_loop_polygon`
**None** dönüyor. Diyot da sayılıyor: asenkron buck'ta alt kol diyottur ve
dönüş yolu yine IC'nin dışından geçer.

Susmak tek başına yeterli olmazdı — görünmez bir boşluk yine sessiz hatadır.
Kural bu durumda `info` seviyesinde "giriş sıcak döngüsü ÖLÇÜLEMEDİ" yazıyor;
cezası sıfır (kapsam dışılık bir ihlal değil), ama raporda görünüyor.

**Korpusta ayrık regülatör yok** — altı regülatörün altısı da entegre, yani
gerçek ölçüm hâlâ yapılamıyor. Test bu yüzden gerçek bir kartın (One-Air-Max
U6) üzerine tek bir sentetik FET ekliyor: taban kart gerçek, yalnızca o bileşen
uydurma. Hem tanıma hem reddetme böyle sınanıyor, ayrıca taban kartta yanlış
pozitif olmadığı ve entegre ölçümün bozulmadığı korunuyor.

Kalan iş değişmedi: ayrık döngüyü gerçekten ölçmek akım yolu topolojisi
(CIN → üst FET → alt FET → CIN) ve test edilecek gerçek bir ayrık kart ister.

### 21.15 Ayrık döngü: reddetmekten ölçmeye

§21.14 ayrık tasarımda ölçmeyi **reddediyordu**. Bu adım onu ölçüyor.

Önce blokajı sınadım: sistemde ayrık regülatörlü kart var mı? Yok — KiCad
demoları (19 kart, 6 regülatör, altısı da entegre) ve deponun kendi örnekleri
dışında `.kicad_pcb` yok. Yani blokaj gerçek, ama **kısmi**: engellediği şey
uygulama değil, tanıyıcının gerçek kartta doğrulanması.

**Roller addan değil topolojiden çıkarılıyor** — ayrık FET sembollerinde pin
adları "D/G/S", "1/2/3" ya da boş olabiliyor:

    üst kol  = VIN ve SW'de pad'i olan
    alt kol  = SW ve GND'de pad'i olan

Bootstrap diyodu bu testi geçemez, çünkü GND'de pad'i yoktur — SW'de olması
onu alt kol yapmıyor. Test bunu ayrıca koruyor.

Döngü artık bir **altıgen**, akım yolu sırasında:

    CIN.VIN -> Qüst.VIN -> Qüst.SW -> Qalt.SW -> Qalt.GND -> CIN.GND

Asenkron buck'ta alt kol diyottur; aynı altıgen geçerli, çünkü dönüş yolu yine
SW'den GND'ye o elemanın üzerinden gider.

Roller çözülemezse (örneğin yalnızca üst kol harici) hâlâ **None** dönüyor ve
`info` düşüyor — mesaj artık hangi kolun çözülemediğini de söylüyor.

**Doğrulama analitik.** Gerçek karta FET eklemek alanı öngörülemez yapıyordu
(CIN'in konumu sabit). Bu yüzden koordinatları biz seçen sentetik bir kart var:
altı pad bir 4×3 dikdörtgen çevreliyor, beklenen alan **12 mm²** elle
hesaplanıyor ve `hot_loop_area_mm2` tam onu veriyor. Ayrı bir test poligonun
nokta sırasını sabitliyor — sıra yanlış olsaydı shoelace başka (küçük) bir alan
verirdi, ki bu tam da §21.14'te düzeltilen hatanın biçimi.

Altı gerçek entegre regülatörün ölçümü **birebir değişmedi** (0.73 / 0.79 /
0.81 / 0.85 / 1.13 mm², U5 hâlâ ölçülemiyor).

**Kicad-z1d hâlâ açık.** Kalan iş uygulama değil doğrulama: gerçek bir ayrık
(harici FET'li) referans kart bulunup tanımanın orada da çalıştığının
görülmesi. Sentetik kartla eşik doğrulamak 1d'nin "korpusa uydurma" yasağına
girerdi.

### 21.16 İki P0: dosya sürümü körlüğü ve sayısal iz netleri

Ayrık buck referans kartı ararken (Kicad-xpi) indirilen gerçek bir kart
(LM5116, KiCad 5.1) iki P0 hata buldu — doğrulama işi, doğrulamaya
başlayamadan ayrıştırıcıyı düzeltti.

**1) KiCad 5 kartları sessizce boş okunuyordu.** KiCad 5 footprint düğümüne
`(module ...)` der ve referansı `(fp_text reference U1 ...)` içinde tutar;
ayrıştırıcı yalnızca `footprint` + `property` tanıyordu. 43 modüllü gerçek
kart **0 bileşenle** okunuyor, `parse_warnings` 0 kalıyor ve `uretim` ön ayarı
**skor 100.0** veriyordu — "kartınız kusursuz". Sessiz hata sınıfının beşinci
ve en geniş örneği. Düzeltme: `module` düğümleri de okunuyor, `fp_text`
geri düşümü eklendi, ve **gürültülü başarısızlık**: dosyada footprint var ama
hiçbiri okunamadıysa `BoardParseError` — sessiz boş kart olmaz.

**2) İz ve via netleri numara olarak okunuyordu — KiCad 9'da da.** Segment ve
via düğümleri neti yalnızca numarayla taşır (`(net 2)`); ad kökteki tabloda.
`_node_net` son elemanı aldığı için iz netleri `"2"` oluyordu. Ölçüldü
(video.kicad_pcb, 7932 iz): iz ve via netlerinin **%100'ü** sayısaldı. Sonuç:
`trace_width` ve `via_current` **hiçbir gerçek kartta hiç çalışmamıştı** ve
`copper_area`'nın track kaynağı hep 0 dönüyordu. Düzeltme: kökteki
`(net N "AD")` tablosu okunuyor, sayısal referans oradan çözülüyor.

**Düzeltme kalibrasyonu değiştirdi ve 1d ilkesi hemen çalıştı.**
`uretim-min-iz-genisligi` ilk kez gerçekten koşunca üç profesyonel kartı
çökertti (CM5_MINIMA 80.7→1.4, jetson 88→50.5, Feather 71→3.5): 0.13 mm
izler DPHY/HDMI/Ethernet **empedans kontrollü çiftleri**, üretim hatası değil.
Korpusla ölçüldü: dört profesyonel kart 0.10–0.13 kullanıyor, hiçbiri 0.10'un
altına inmiyor. Eşik 0.15 → **0.10** (yaygın ucuz sınıfın gerçek sınırı, ön
ayarın kendi yorumundaki değer). Kalibrasyon eski hâline döndü: medyan 95.9,
çeyrekler 80.7/95.9/100.0.

### 21.17 Gerçek ayrık kart: FET'ler "U" referanslı olabilir

LM5116 kartında MOSFET'ler (Si7850) **U2/U3** referansı taşıyor —
`ref_kind` onlara "ic" der, `external_switches`'in tür filtresi
(transistor+diode) onları kaçırırdı. Düzeltme: SW düğümündeki, denetleyici
olmayan ve anahtar gibi **bağlanan** (VIN∧SW ya da SW∧GND) IC'ler de aday.
Tür genişlemesi yalnızca "ic" — snubber kondansatörü de SW+GND koşulunu
sağlar, tür filtresi onu dışarıda tutmaya devam ediyor. Altı entegre
regülatörde yanlış pozitif yok, ölçümler birebir aynı.

Kalan sınır (Kicad-xpi hâlâ açık): KiCad 5 pad'lerinde `pinfunction` yok —
tanıma SW pinini pin adından bulduğu için bu kartta hiç başlayamıyor. Kartın
lisansı da yok, korpusa eklenemez. Pin adı olmayan kartta net adına
(`SW`/`HO`/`LO`) geri düşmek bir seçenek ama net-adı-güvenilmez kararıyla
çelişmeden tasarlanmalı; xpi'de not olarak duruyor.

### 21.18 Testler

`python -m unittest discover -s tests` → **485 test**, hepsi geçiyor
(oturum başında 214). KiCad demolarına bağlı testler kurulum yoksa atlanır.
## 22. Evre 3a — niyet şeması ve STM32 şablon kütüphanesi (2026-08-28)

### 22.1 Ne ve neden

Üretken tasarımın ilk deterministik adımı: kullanıcı devreyi parça listesiyle
değil **niyetle** söyler ("STM32F103 + USB + 3V3 LDO + kristal"), sistem bunu
şablon kütüphanesinden geçirip somut bir **inşa planına** açar — hangi
semboller, hangi değerlerle, hangi ağlara. ML yok; skorun yargılayabildiği
bir üretim zinciri kurmak önce gelir (bkz. `bd memories evre-3`).

Yeni dosyalar:

| Dosya | Ne |
|---|---|
| `pcbqa/intent.py` | Niyet YAML şeması, şablon yükleme, açılım, symlib ile pin çözümleme, CLI |
| `pcbqa/templates/*.yaml` | 6 şablon: `mcu-stm32f103c8`, `ldo-ams1117-3v3`, `crystal-hse`, `usb-micro-b`, `swd-header`, `guc-girisi-header` |
| `samples/ornek-niyet.yaml` | 18 bileşen / 11 ağlı örnek F103 kartı niyeti |
| `tests/test_intent.py` | 31 test |

CLI: `python -m pcbqa.intent --intent samples/ornek-niyet.yaml` (`--list`
şablonları döker, `--json` planı yazar, engel varsa çıkış kodu 1).

### 22.2 Tasarım kararları

- **Yetenek modeli (`provides`/`requires`/`interfaces`).** Bloklar birbirini
  ağ adıyla bulur (3V3, HSE_IN...). Karşılanmayan `requires` plan engelidir ve
  mesaj hangi şablonun sağlayabileceğini söyler. `interfaces` yalnızca istendiğinde
  aktifleşir: MCU'nun PD0/PD1'i ancak kristal bloğu `hse-pinleri` istediğinde
  etiketlenir — yoksa kristalsiz kartta tek pinli ağ çöplüğü oluşurdu.
- **Pin ADI ile bağlama.** `VDD: "${vdd}"` aynı ada sahip **tüm** pinleri bağlar
  (STM32'nin üç VDD pini tek satır). `#3` pin numarasıdır (adsız pasifler için).
  Çözümleme kurulu KiCad kütüphanesine karşı yapılır; sembolde olmayan ad,
  olmayan footprint, **bağlanmamış `power_in` pini** — hepsi engel (sessiz
  hata dersinin şablonlara uygulanışı).
- **Referans numarası planda YOK** — o `sch_add`'in işi (mevcut şematiğe göre
  atanır). Plan bileşenleri şablon-yerel etiketle konuşur
  (`mcu-stm32f103c8/vdd-decoupling.2`).
- **Değerlerin kaynağı şablon yorumunda**: AN2586 (VDD pini başına 100 nF +
  4.7 µF bulk, VDDA 10 nF + 1 µF, NRST 100 nF, BOOT0 10k), AN2867 (yük
  kondansatörü 2×(CL−Cs); 15 pF varsayılanı CL=12.5/Cs=5 varsayımıyla),
  AMS1117 veri sayfası (çıkış ≥ 22 µF), F103'te dahili D+ pull-up olmadığı
  için 1.5k harici. Kaynaksız seçimler "mühendislik seçimi" etiketli.
- **Aynı şablon iki kez → engel** (ağ adları çakışır; param ile ayrıştırma
  ileriye bırakıldı). İki `guc-vbus` kaynağı (USB + güç header'ı) → not,
  engel değil (gerçek kartlarda meşru).

### 22.3 Testin koruduğu şey

`test_every_bundled_template_resolves_cleanly` paketteki **her** şablonu
gerçek kütüphaneden geçirir — "şablon yazıldı ama kütüphaneyle hiç sınanmadı"
durumu kalıcı olarak kapalı. `test_vdd_decoupling_count_matches_symbol`
şablondaki `count: 3`'ü sembolün gerçek VDD pin sayısına bağlar: kütüphane
değişirse test bağırır.

### 22.4 Kalan işler (3a devamı)

- **Sürücü yok**: plan → gerçek `.kicad_sch` üretimi (boş proje iskeleti +
  `sch_add(connect=...)` döngüsü) → `pcb_sync` → `auto` → skor. Plan çıktısı
  `sch_add`'in diliyle bire bir (pin = ağ adı) tasarlandı.
- Şablonlar tek MCU'yu tanıyor; ikinci paket (F103RC, F4) eklenince MCU
  şablonundan aile şablonuna geçilecek.
- ERC "unconnected pin" gürültüsü: kullanılmayan GPIO'lara no-connect
  bayrağı üretimi sürücünün işi.

### 22.5 Testler

`python -m unittest discover -s tests` → **516 test** (485 + 31), hepsi geçiyor.
## 23. Evre 3a sürücüsü — plandan gerçek KiCad projesine (2026-08-28)

### 23.1 Zincir kapandı

`intent.py` bir plan üretiyordu ama plan bir **veri yapısıydı**. `generate.py`
zinciri kapatır:

    niyet.yaml --intent--> plan --generate--> .kicad_sch
                                          --pcb_sync--> .kicad_pcb
                                          --auto------> yerleşim
                                          --run_rules--> skor

CLI: `python -m pcbqa.generate --intent samples/ornek-niyet.yaml --out <klasör>`

Örnek F103 kartında ölçülen sonuç:

| adım | sonuç |
|---|---|
| şematik | 18 bileşen, A4, 55 etiket |
| **kalkan** | **11 planlanan ağın tamamı KiCad netlist'inde birebir doğrulandı** |
| kart | 50 × 35 mm, 18/18 bileşen yansıtıldı, pad ağları geri okundu |
| yerleşim | 1.2 → **100.0** (kendi kurallarımız: 0 hata / 0 uyarı) |
| `sch erc` | **0 ihlal** (`--no-connect-unused` ile) |
| `pcb drc --schematic-parity` | **0 fark** |
| kalan DRC | 52 bağlanmamış bakır (yönlendirme yok — bilinen sınır), ipek çakışması (Kicad-ywm) |

### 23.2 Tasarım kararları

- **`sch_add` döngüsü değil, tek geçiş.** `add_symbols` her çağrıda netlist
  kalkanını iki kez koşturur (~4 s × 2); 18 bileşen iki dakikadan fazla eder.
  Üstelik kalkanın sorusu burada yanlış: "mevcut devre bozulmasın" der, oysa
  mevcut devre yoktur. Semboller `sch_add`'in düğüm üreticileriyle tek geçişte
  kurulur, sonunda **daha güçlü** bir soru sorulur: *KiCad'in kendi netlist'i
  planın kurmak istediği ağların aynısını mı okuyor?* Üç sessiz hata sınıfı
  ayrı ayrı aranır — eksik pin (etiket tutmamış), bölünmüş ağ, fazla pin
  (sessiz kısa devre).
- **Bağlantı hep etiketle.** Plan zaten pin → ağ adı dilinde; etiket tam olarak
  bunu ifade eder ve mesafeden bağımsızdır.
- **Kilitli bileşen yok.** `harness.locked_refs` konnektörleri sabit sayar;
  üretilen kartta böyle bir mekanik kısıt henüz yoktur ve kilitli sayılsalardı
  `pcb_sync`'in bıraktığı ara konumda (sınırın dışında) donup kalırlardı.
- **Kart sınırı tahmin değil ölçüm.** Önce bileşenler karta yansıtılır, sonra
  gerçek courtyard alanları okunup %25 yoğunluk hedefiyle Edge.Cuts çizilir.
- **Yığılmış güç pinleri.** STM32F103C8Tx'in üç VSS pini aynı noktada durur
  (KiCad'in kendi geleneği). Doğru değişmez "çakışma olmasın" değil,
  **"çakışanlar aynı ağda olsun"**; etiket noktaya bir kez yazılır.

### 23.3 Üretim koşumunun bulduğu DÖRT gerçek hata

Hepsi sessizdi ve hiçbiri birim testleriyle değil, **KiCad'in kendi araçlarıyla**
bulundu — §19.7'deki dersin tekrarı.

**1) Türev sembollerin birim adları (`symlib.resolve_definition`).**
`extends` çözülürken gövde üst sembolden kopyalanıyor ama birim düğümlerinin
adı üstte kalıyordu: `STM32F103C8Tx` adlı sembolün içinde
`STM32F103C_8-B_Tx_0_1`. `kicad-cli` böyle bir dosyayı **hiçbir mesaj vermeden
3 koduyla** reddediyor. Yani `sch_add` bugüne kadar türev sembol kullanan her
eklemede (STM32, AMS1117…) **KiCad'de açılamayan dosya üretiyordu.**

**2) `fp_rect` courtyard'lar düşüyordu (`pcb._local_points`).**
Şekil iki köşegen köşesini saklar; okuyucu iki noktayı poligon sayamayıp
atıyordu. Etkilenen: **0603/0805 gibi en yaygın pasifler** — yani hemen her
kartın bileşenlerinin çoğu courtyard'sız görülüyordu. `courtyard_overlap`,
`edge_clearance` ve yoğunluk ölçümü onlarda sessizce susuyordu.

**3) İçbükey courtyard + SAT (`pcb._read_courtyard_local`, `geom.overlap`).**
Courtyard'lar dışbükey kabuğa çevrilip SAT ile sınanıyordu; ikisi de L biçimli
bir konnektörün **boşluğunu dolu sayar**. (2) düzeltilince `pic_programmer`da
P3'ün L'sinin boşluğuna oturan C7 "çakışıyor" çıktı — KiCad aynı kartta sıfır
ihlal buluyor. Çözüm: parçaları uç uca **zincirleyerek** gerçek (içbükey
olabilen) poligonu kurmak, ve `overlap`'i kenar kesişimi + içerme testine
çevirmek (her basit poligonda kesin; dışbükeyde SAT ile aynı cevap).

**4) Pad açısı çift sayılıyordu (`pcb._read_footprint`, `harness.write_board`).**
Okuyucu `footprint_dönmesi + kayıtlı_açı` hesaplıyordu; KiCad dönmeyi zaten her
pad'in açısına işliyor. Dikdörtgen pad'ler 180° simetrik olduğu için hata
**90/270 dönmüş bileşenlerde** görünür hale gelir. Ölçüldü: `jetson` kartı
73.8 → **83.9** (üç yanlış açıklık hatası kalktı). Yazma tarafı da eksikti —
`write_board` gövdeyi döndürüp içindeki metin ve pad açılarını olduğu gibi
bırakıyordu; KiCad üretilen kartta 12 bileşeni "kütüphanedeki kopyasıyla
eşleşmiyor" diye işaretledi ve **o 12 bileşen dönmüş olanların tam olarak
kendisiydi**. Düzeltince `lib_footprint_mismatch` **0**'a indi.

### 23.4 Kalibrasyon: net etki YOK

Dört düzeltmeden sonra 19 kartlık korpus (`uretim` ön ayarı):

| ölçüm | kayıtlı (§21) | şimdi |
|---|---|---|
| medyan | 95.9 | **95.9** |
| çeyrekler | 80.7/95.9/100.0 | **80.7/95.9/100.0** |

Özet aynı ama **tek tek kartlar artık doğru ölçülüyor**: courtyard körlüğü
skorları yukarı, pad açısı hatası aşağı çekiyordu ve toplamda birbirlerini
götürüyorlardı. Courtyard çakışması 5 → 6 kartta ateşliyor; §21.3'te adı geçen
üç kartın sayıları **birebir aynı** kaldı (StickHub 25, tinytapeout 14,
Feather 4), yani düzeltmeler yanlış alarm eklemedi. Yeni ateşleyen
`vme-wren`de KiCad'in kendi DRC'si 22, biz 25 diyoruz. `pic_programmer` yine
**0 bulgu** — "sağlam kartta sessizlik" testi ayakta.

### 23.5 Kalan sınırlar

- **Yönlendirme yok** (Evre 3b öncesi verilecek karar): bakır kuralları susuyor,
  skor yarım konuşuyor. Üretilen kartın 52 bağlanmamış bakır kalemi bundan.
- **Mikron seviyesi değme** (Kicad-4ro): CM5 demosunda 0.005–0.006 mm'lik
  ortüşmeler "çakışma" sayılıyor. Tasarımcı bunları `.kicad_pro`da DRC
  muafiyetine almış — yani KiCad de görüyor, kabul etmiş. Eşik **uydurulmadı**;
  kaynak (IPC-7351B toleransı ya da üretici verisi) bulunana kadar kural
  yapılandırıldığı gibi davranıyor (`clearance_mm: 0.0`).
- **İpek baskı çakışması** (Kicad-ywm): yerleştirici referans metinlerini
  görmüyor; %25 yoğunlukta 18 + 12 uyarı çıkıyor.
- **Çok birimli semboller** üretilemiyor (birimlerin sayfaya dağıtılması ayrı
  bir karar); plan bunu engel olarak bildirir, sessizce atlamaz.

### 23.6 Testler

`python -m unittest discover -s tests` → **553 test**, hepsi geçiyor
(oturum başında 485). Yeni: `test_intent` 31, `test_generate` 23,
`test_courtyard` 13, `test_sch_add` +1 (türev sembol birim adları).
## 24. Evre 3b — üretim-değerlendirme döngüsü (2026-08-28)

### 24.1 Önce kapatılan karar: yönlendirme (Kicad-805)

**Karar: dış autorouter entegre edilmeyecek.** Gerekçe ölçüm:
`kicad-cli`'de Specctra **DSN dışa aktarımı yok**, ve `pcb import` yalnızca
pads/altium/eagle/cadstar/fabmaster/pcad/solidworks tanıyor — **SES yok**.
Yani freerouting turu KiCad 10'da GUI'ye özel; entegrasyon sıfırdan bir DSN
yazıcı **ve** SES okuyucu yazmak demek.

Peki bu 3b'yi engelliyor mu? **Hayır.** Aynı niyetten üretilen bütün
varyantlar aynı netlist'e sahip ve hepsi yönlendirilmemiş — bakır körlüğü
**sabit bir kayma**, karşılaştırmayı bozmaz. Bozduğu şey **mutlak sayı**:
100 "kusursuz kart" değil, "yerleşimde ihlal yok" demektir. `explore` bunu
her raporda açıkça yazar.

### 24.2 Ölçüm: skor tek başına varyantları sıralayamıyor

Üretilen 18 bileşenlik F103 kartında skor **doyuyor**:

| kart | skor |
|---|---|
| 40 × 28 mm | 100.0 |
| 50 × 35 mm | 100.0 |
| 70 × 50 mm | 100.0 |
| 100 × 70 mm | 100.0 |

Skor bir **ihlal sayacıdır**; ihlal kalmadığı anda ayrım gücü biter. "En
yüksek skorlu varyantı seç" demek bu dördünü eşit görmek demektir.

İki ölçüm tıkanıklığı açtı:

1. **Tohum gerçek fark yaratıyor.** Sabit 50×35'te altı tohum HPWL'i
   174.5 – 216.2 mm arasına dağıttı — en iyisi en kötüsünden **%19.3** iyi.
2. **Skorun çözünürlüğü dar kartta var.** 25×18 → **24.7** (4 uyarı),
   30×20 → **74.1** (1 uyarı), 35×25 → **100.0**. Yani 35×25 skoru tam
   tutturan **en küçük** karttır ve 50×35'in yarı alanıdır.

İkincisi asıl kazançtır: aynı kalite, yarı kart alanı. **Kart alanı gerçek
bir üretim maliyetidir ve skor onu hiç görmez** — bu yüzden seçim ölçütüne
ayrıca konur.

### 24.3 Seçim ölçütü

Sözlüksel, büyük olan kazanır:

    (skor, -hata, -uyarı, -alan, -HPWL)

Skor önce gelir: kaliteden ödün verilmez. Eşit kalite katmanında **en küçük
kart** yeğlenir (para). Alan da eşitse HPWL ayırır. Bu, `Evaluation.key`
sözleşmesinin alan eklenmiş hâli — yeni bir ölçüt icat edilmedi.

### 24.4 `explore.py` — ölçülen kazanç

Şematik **bir kez** üretilir (netlist her varyantta aynıdır); değişen yalnızca
kart sınırı ve yerleştiricinin tohumu. Kart her denemede taze bir kopyadan
kurulur ve sınır **dosyaya yazılmadan** modele konur — varyant başına dosya
yazıp okumak bütçenin önemli kısmını diske harcardı.

Arama sırası bilinçli: **önce boyut, sonra tohum.** Boyut kart alanını
(parayı) değiştirir; tohum yalnızca aynı kart içinde daha iyi bir yerleşim
arar. Yani önce geniş, sonra derin.

`--variants 6 --budget 10` ile ölçülen koşum:

| # | yoğunluk | boyut | alan | tohum | skor | HPWL |
|---|---|---|---|---|---|---|
| 1 | %40 | 40×30 | 1200 | 0 | 100.0 | 221.6 |
| 2 | %32 | 45×30 | 1350 | 0 | 100.0 | 177.9 |
| 3 | %25 | 50×35 | 1750 | 0 | 100.0 | 174.5 |
| 4 | %18 | 55×40 | 2200 | 0 | 100.0 | 200.0 |
| **5** | **%40** | **40×30** | **1200** | **1** | **100.0** | **148.9** |
| 6 | %32 | 45×30 | 1350 | 1 | 100.0 | 189.8 |

Kazanan **40×30 mm**: en büyük adaydan **%45**, tek atışlık `generate`'in
seçtiği 50×35'ten **%31 küçük**, üstelik altısının **en kısa** teli
(148.9 mm, 174.5'e karşı **%15** iyi). Aynı boyutta tohum 0 → 221.6,
tohum 1 → 148.9: tohum ekseni tek başına **%33** fark.

Yazılan kart doğrulandı: `--schematic-parity` **0 fark**, kendi kurallarımız
**0 bulgu**, tek `Edge.Cuts` dikdörtgeni.

### 24.5 Bunun 3c/3d için anlamı

Skorun doyması **ML katmanını doğrudan ilgilendiriyor**: eğitim etiketi olarak
ham skor kullanılamaz — üretilen kartların hepsi 100 alır, yani etiket sabittir
ve model hiçbir şey öğrenemez. 3c'de toplanan veri **etiketi `Variant.key`
üzerinden** (ya da doğrudan HPWL/alan üzerinden) taşımalı. Bu, `learned`
yerleştirici dersinin (§21.10) tekrarını önler: sinyal ölçülebilir olmadan
model terfi etmez.

### 24.6 Kalan sınırlar

- Varyant ekseni **yalnızca boyut ve tohum**. Devre topolojisi (alternatif
  şablon, farklı LDO, farklı paket) henüz varyant üretmiyor — şablon
  kütüphanesi büyüdükçe doğal genişleme yolu bu.
- **En-boy oranı sabit** (`BOARD_ASPECT = 1.4`). Kare ya da uzun kart bazı
  tasarımlarda daha iyi olabilir; ölçülmedi.
- Bütçe varyant sayısıyla **doğrusal** çarpılıyor (`N × budget`). Paralel
  koşum yok.

### 24.7 Testler

`python -m unittest discover -s tests` → **566 test**, hepsi geçiyor
(3b öncesi 553). Yeni `test_explore` 13: seçim ölçütünün sözlüksel sırası
(skor > hata > alan > HPWL), arama sırası (önce boyut sonra tohum), ve uçtan
uca kazanan kartın gerçekten yazıldığı.
## 25. Evre 3c — tasarım seviyesi veri toplama (2026-08-28)

### 25.1 Ne toplanıyor

`ml/collect.py` **hamle** seviyesinde topluyordu (bir yerleştirme aramasındaki
aday hamleler). `ml/collect_design.py` bir üst katmanda toplar: bir **niyetten**
üretilen kart **varyantları**. İkisi aynı biçimi (`ml/dataset.py`) paylaşır,
yani mevcut eğitici (`ml/train.py`) ve sıralama metrikleri (`ml/metrics.py`)
ikisinde de çalışır — bu doğrulandı.

    grup  = niyetin adı        -> bölme buna göre (model niyeti ezberlemesin)
    parti = tek keşif koşumu   -> sıralama parti içinde ölçülür

`samples/niyetler/` altında **7 niyet** var (4 – 18 bileşen): tam donanımlı
F103'ten MCU'suz güç modülüne kadar. Veri çeşitliliği buradan geliyor.

    python -m pcbqa.ml.collect_design --intents samples/niyetler \
        --out .work/tasarim.jsonl --variants 8 --budget 6

### 25.2 İki tasarım kararı

**Etiket HPWL üzerinden.** Üretilen kartta skor doyuyor (§24.2), yani ham skoru
etiket yapmak bütün örnekleri aynı etiketle işaretlemek olurdu. Etiket
`collect.py`'nin sözleşmesini koruyarak parti **medyanına** göre yazılır:

    etiket = d_skor + 0.05 × clamp(−d_HPWL / medyan_HPWL, −1, +1)

Skorlar eşitken (olağan durum) geriye bağıl HPWL iyileşmesi kalır. Ölçek küçük
ama sıralama metrikleri yalnızca **sırayı** umursar.

**Tohum bilerek öznitelik değil.** Tohum bir tasarım kararı değil, aramanın
rastgeleliğidir; özniteliğe koymak modeli gürültüyü ezberlemeye davet ederdi.
Dışarıda bırakınca aynı öznitelik vektörü farklı etiketlerle birden fazla kez
görünür — bu bir kusur değil, **gürültü tabanının ölçülebilir hale gelmesidir.**

**Lisans zorunlu.** Her kayıt kaynağını taşır; üretilen kartlarda
`lisans: "uretilmis"`. Dışarıdan gelen bir kayıt lisanssız eklenemez — LM5116
emsali (§1): lisansı olmayan kart korpusa alınamamıştı.

### 25.3 Ölçüm: öğrenilebilir sinyal zayıf

Bu, 3d'nin kapısıdır ve **model yazılmadan önce** ölçüldü.

**Varyans ayrımı** (F103 kartı, 4 yoğunluk × 5 tohum):

| kaynak | varyans |
|---|---|
| yoğunluklar arası (öğrenilebilir) | 87.7 |
| tohum, yoğunluk içi (indirgenemez) | 321.5 |
| **açıklanan oran** | **%21.4** |

**Bütçe artırmak yardım etmiyor.** Aynı yoğunlukta 5 tohum:

| bütçe | ort | en iyi | en kötü | std |
|---|---|---|---|---|
| 6 sn | 174.4 | 166.1 | 200.4 | 13.0 |
| 20 sn | 181.8 | 158.5 | 228.5 | **25.3** |

Yayılım azalmadı, arttı. Yani tohum gürültüsü "yakınsamamış arama" değil,
`auto`'nun kendi doğası: arama yolu bütçeyle tamamen değişiyor ve `auto`'nun
gerileme garantisi yalnızca **başlangıç kartına** göre, daha kısa bir koşuma
göre değil.

**Toplanan veri kümesinde gürültü tabanı** (7 niyet × 8 varyant = 56 örnek):
24 ayrık öznitelik vektörünün 24'ü tekrarlı; **açıklanabilir üst sınır %31.4**.

### 25.4 İlk eğitim koşumu: hiçbir model temel çizgiyi geçmiyor

`python -m pcbqa.ml.train .work/tasarim.jsonl --cv 3` (grup bazlı 3 kat):

| model | spearman | ikili doğruluk |
|---|---|---|
| mean (temel çizgi) | 0.000 | 0.500 |
| ridge | **−0.214** | **0.422** |
| gbt | **−0.103** | **0.495** |

İkili doğruluk 0.5 = yazı tura. **Varyant sıralayıcı şu hâliyle öğrenmiyor.**
Bu bir başarısızlık değil ölçülmüş bir sonuçtur ve `learned` yerleştirici
dersinin (§21.10) birebir tekrarıdır: *model kazanç ölçülmeden terfi etmez.*

Neden sinyal yok, üç aday sebep — hepsi test edilebilir:

1. **Gürültü baskın**: varyansın ~%69'u tohum. Model tek koşumu tahmin etmeye
   çalışıyor; oysa tahmin edilebilir olan **koşulun ortalamasıdır**. Etiketi
   tohumlar üzerinden ortalayarak denemek en umut verici sonraki adım.
2. **Veri küçük**: 7 grup, 56 örnek. Grup bazlı 3 katta her kat 2 – 3 niyet.
3. **Topoloji tekdüze**: yedi niyetin altısı aynı MCU'yu kullanıyor, yani
   topoloji öznitelikleri neredeyse yalnızca bileşen sayısıyla değişiyor.
   Şablon kütüphanesi büyümeden çeşitlilik gelmez.

### 25.5 Bulunan yan hata: `meta` başlığı sessizce eziyordu

`Dataset.save` başlığı `{"kind": ..., **self.meta}` diye yazıyordu. `meta`
içinde `kind` olan bir veri kümesi **sorunsuz yazılıyor**, sonra `load`
"pcbqa veri kümesi değil" diye reddediyor ve sebebi hiçbir yerde yazmıyor.
Bu hataya bu oturumda bizzat düşüldü. `save` artık ayrılmış adları (`kind`,
`feature_version`, `features`, `count`) gürültülü biçimde reddediyor.

### 25.6 Sıradaki (3d) için hazır olan / olmayan

**Hazır:** veri şeması, toplama CLI'si, 7 niyetlik kütüphane, gürültü tabanı
ölçümü, ve mevcut eğitici/metriklerin bu veriyi doğrudan tükettiği doğrulaması.

**Hazır değil:** öğrenilebilir bir sinyal. 3d'ye geçmeden önce 25.4'teki üç
adaydan en az birinin denenmesi gerekir; aksi halde eğitilecek model, ölçümün
şimdiden "yazı tura" dediği bir işi yapmaya çalışacaktır.

### 25.7 Testler

`python -m unittest discover -s tests` → **586 test**. Yeni `test_collect_design`
20: öznitelik şeması, tohumun öznitelik OLMADIĞI, etiket sırası (skor > HPWL),
lisans zorunluluğu, gürültü tabanı hesabı ve ayrılmış `meta` adı tuzağı.
## 26. API'siz bağlantı — KiCad'in kendi Python'u (2026-08-28)

### 26.1 Neden gerekti

`ipc.py` çalışan KiCad'e **IPC API sunucusu** üzerinden bağlanıyor. Ölçüldü:
o sunucu KiCad 10'da **varsayılan olarak kapalı** —
`%APPDATA%\kicad\10.0\kicad_common.json` → `"api": {"enable_server": false}`.
Yani dağıtılacak bir uygulama ya da eklenti her kullanıcıdan Tercihler'e girip
bir ayarı açmasını isterdi. Kabul edilemez bir kurulum adımı.

İkinci yol zaten yarı yarıya vardı ama görülmüyordu:

| yol | KiCad ayarı gerekir mi | ne yapar |
|---|---|---|
| **dosya tabanlı** (`generate`, `explore`, `pcb_sync`) | hayır | `.kicad_sch`/`.kicad_pcb` yazar, kullanıcı sonra açar |
| **süreç-içi** (`swig_apply`, YENİ) | hayır | KiCad'in içinde `pcbnew` ile açık kartı yerinde taşır |
| IPC (`ipc.py`) | **evet** | dışarıdan çalışan editöre bağlanır |

### 26.2 Önündeki tek engel: yorumlayıcı ayrımı

| | KiCad 10.0 python 3.11.5 | proje `.venv` python 3.13 |
|---|---|---|
| `pcbnew` (SWIG, süreç-içi) | ✅ 10.0.4 | ❌ |
| `pyyaml` | ❌ | ✅ |

`import yaml` modül düzeyinde durduğu sürece `pcbqa` KiCad'in içinde **hiç
import edilemiyordu.** Bağımlılık yüzeyi darmış: yalnızca `rules.py` ve
`intent.py`, toplam üç çağrı.

### 26.3 Çözüm: YAML kaynak, JSON çalışma zamanı kopyası

`confload.py` sırayla bakar: dosya `.json` ise stdlib → pyyaml varsa YAML →
yanında `.json` eşi varsa o → hiçbiri yoksa **sebebini söyleyen hata**.

**YAML neden atılmadı:** kural ve şablon dosyalarındaki *yorumlar* bu projenin
belkemiği — her eşiğin kaynağı orada ("Kaynak: ST AN2586 Bölüm 3.4"). JSON
yorum taşımaz. Bu yüzden YAML insan için kalır, JSON yalnızca çalışma zamanı
kopyasıdır. `python -m pcbqa.bundle` üretir (11 dosya), `--check` ayrışmayı
yakalar ve bir test her koşumda çağırır — çünkü YAML düzeltilip JSON eski
kalırsa **KiCad'in içinde eski kural koşar, hem de sessizce.**

Kullanıcının kendi kural dosyası da çevrilebilir:
`python -m pcbqa.bundle benim.rules.yaml`.

### 26.4 `swig_apply.py` — sözleşme `ipc.py` ile aynı

Aynı `Placement` girer, aynı özet çıkar: varsayılan **dry-run**, KiCad'de
kilitli footprint'e dokunulmaz, tekrar eden referansta durulur, yazdıktan
sonra kart **geri okunup doğrulanır**. İki yol arasında davranış farkı olsaydı
hangisinin kullanıldığı sonuca karışırdı.

**GUI gerekmiyor:** `pcbnew.LoadBoard()` başsız çalışıyor (ölçüldü: 63
footprint). Yani bu yol baştan sona test edilebilir — ve ediliyor.

### 26.5 Uçtan uca ölçüm (KiCad'in kendi Python'unda, API kapalı)

    pyyaml var mı: False        -> kurallar JSON kopyasından okundu
    1) açık kartın skoru   : 54.9  (0 hata, 2 uyarı)
    2) yerleştirme sonrası : 100.0 (0 hata, 0 uyarı)
    3) dry-run             : 18 değişecek, 0 zaten yerinde
       uygulandı           : 18 | doğrulama hatası: 0 | kaydedildi: True
    4) diskten geri okunan : 100.0  (beklenen 100.0)

### 26.6 Testler

`tests/test_swig_bridge.py` 14 test. Beşi **alt süreç olarak KiCad'in
yorumlayıcısını çağırıp orada koşar** — başka türlü bu yol hiç sınanmaz,
çünkü bizim `.venv`'imizde `pcbnew` yoktur. Korunanlar: pyyaml olmadan kural
ve şablon okuma, dry-run'ın dosyaya dokunmaması, taşımanın diske yansıması,
kilitli footprint'in atlanması, ve kopyaların ayrışmaması.

### 26.7 Kalan iş (dağıtım)

Bu bölüm **bağlantıyı** çözdü, **paketlemeyi** değil. Ürün şekli hâlâ açık:

- **Bağımsız uygulama**: kendi Python'unu taşır, dosya tabanlı çalışır, KiCad
  kapalıyken kullanılır. Bugün hazır, ek iş yok.
- **KiCad eklentisi (PCM/"DLC")**: `metadata.json` + `plugins/` düzeni, KiCad
  araç çubuğunda bir düğme. `swig_apply` bunun çalışan çekirdeği; eksik olan
  paket sarmalayıcı ve PCM metadata'sı.
## 27. Bağımsız uygulama (2026-08-28)

### 27.1 "Bağımsız" ne demek, ne demek değil

**Ayrı bir Python kurulumu gerektirmez.** "KiCad'siz çalışır" **değil** — o
mümkün de değil: netlist/ERC/DRC için `kicad-cli`, bileşenler için sembol ve
footprint kütüphaneleri KiCad'den geliyor.

KiCad zaten kurulu olmak zorunda olduğuna ve kendi Python'unu (3.11.5)
getirdiğine göre, ikinci bir yorumlayıcı gömmek ya da PyInstaller ile
paketlemek daha büyük, daha kırılgan ve virüs tarayıcılarını rahatsız eden bir
çıktı verir; kazancı sıfırdır. Dağıtım = **bu klasör + `pcbqa.cmd`**.

Bunu mümkün kılan §26'daki iş: paketin çalışma zamanı bağımlılığı kaldırıldı.

### 27.2 Yeni parçalar

| dosya | ne yapar |
|---|---|
| `pcbqa/app.py` | tek giriş noktası; alt komutlar mevcut modüllerin `main()`ini çağırır |
| `pcbqa.cmd` | başlatıcı: KiCad'in Python'unu kendi bulur (yeni sürümden eskiye) |
| `pcbqa/minyaml.py` | bağımlılıksız YAML okuyucu |
| `KURULUM.md` | son kullanıcı belgesi |

`pcbqa tani` tek komutta ortamı denetliyor: yorumlayıcı, `kicad-cli`, sembol
ve footprint kütüphaneleri, çalışma zamanı kopyaları, `pcbnew`, şablonlar.
Engel varsa `!!` ile işaretlenip çıkış kodu 1 dönüyor.

### 27.3 Ortaya çıkan gerçek açık: kullanıcının kendi YAML'ı

`bundle.py`'nin ürettiği JSON kopyaları **paketin kendi** dosyalarını
kurtarıyordu. Ama başlatıcıyla ilk gerçek denemede şu çıktı:

    pcbqa uret --intent samples\niyetler\f103-asgari.yaml
    hata: niyet dosyasi okunamadi: pyyaml kurulu degil ve calisma zamani
          kopyasi (f103-asgari.json) yok

Kullanıcının **kendi niyet ve kural dosyaları** YAML'dır ve "önce JSON'a
çevir" kabul edilemez bir kullanım adımıdır.

### 27.4 `minyaml.py` — ve neden kendi yazıldı

Önce kullanımımız ölçüldü (21 YAML dosyası taranarak):

| yapı | satır |
|---|---|
| iç içe blok eşleşme | 490 |
| blok liste (`-`) | 105 |
| satır içi liste `[a, b]` | 23 |
| satır içi eşleşme `{a: 1}` | 16 |
| tırnaklı anahtar | 9 |
| **çapa / çok satırlı / etiket / belge ayracı** | **0** |

Gerçekten dar bir altküme. `sexpr.py` de aynı gerekçeyle sıfırdan yazılmıştı.

**Tehlike ve karşılığı:** böyle bir okuyucunun tek gerçek riski *sessizce
yanlış okumak*. İki önlem alındı:

1. **Anlamadığını reddeder.** Çapa (`&`/`*`), etiket (`!`), çok satırlı skaler
   (`|`/`>`), belge ayracı (`---`), girintide sekme → satır numarasıyla hata.
2. **PyYAML ile diferansiyel test.** Depodaki her YAML iki okuyucudan geçer ve
   sonuçlar birebir eşit olmalıdır: **21/21 aynı.**

### 27.5 Diferansiyel testin bulduğu iki gerçek ayrışma

Test yazılır yazılmaz iki hata yakaladı — kendi kendine yazılmış bir okuyucuya
neden güvenilmeyeceğinin kanıtı:

1. **`1e3`**: PyYAML bunu **metin** sayıyor (YAML 1.1'de üs için işaret
   zorunlu); bizimki float yapıyordu.
2. **`%50`**: PyYAML hata veriyor, bizimki kabul ediyordu (korpustan çıkarıldı;
   geçerli YAML değil).

Sonrasında PyYAML'ın çözümleyici düzenli ifadeleri **birebir** alındı, çünkü
YAML 1.1'in sayı kuralları tuzaklı ve sezgiyle yazmak yanlış olur:

    1e3    -> metin        012  -> 10    (sekizlik!)
    1.0e3  -> metin        0603 -> 387   (yine sekizlik)
    1.0e+3 -> 1000.0       0805 -> metin (8 sekizlik değil)
    1:30   -> 90 (altmışlık)      1_000 -> 1000

Bu tutarsızlıkları "düzeltmek" bizim işimiz değil: amaç **aynı ağacı**
üretmek, yoksa aynı dosya iki ortamda iki farklı kural yükler. Ölçüm: 26/26
skaler birebir aynı.

### 27.6 Okuma sırası değişti

    1. .json dosyası    -> stdlib json
    2. pyyaml varsa     -> yaml
    3. minyaml          -> yaml   (KAYNAĞI okur)
    4. .json eşi varsa  -> json   (3 takılırsa emniyet ağı)
    5. hiçbiri          -> sebebini söyleyen hata

3'ün 4'ten önce gelmesi bilinçli: JSON kopyası **üretilmiş** bir şeydir ve
bayat olabilir; kendi okuyucumuz dosyanın kendisini okur.

### 27.7 Kapatılan yan açık: karta yazmada kilit koruması yoktu

Şematik tarafında açık-proje koruması baştan beri vardı (`sch_write`), **kart
tarafında yoktu**. Dağıtılan bir uygulamada bu gerçek bir tehlike: KiCad kartı
bellekte tutar, biz yazarken kullanıcı kaydederse bir taraf sessizce kaybolur.
`harness.write_board` artık kilidi görünce reddediyor — bu tek nokta
`generate`, `explore` ve `yerlestir`'i birden koruyor.

### 27.8 Ölçülen uçtan uca (sanal ortam yok, pyyaml yok)

    > pcbqa tani            -> Python 3.11.5 (KiCad'in kendi yorumlayıcısı), her şey yerinde
    > pcbqa uret  ...       -> 13 bileşen, 5/5 ağ doğrulandı, skor 2.7 -> 100.0
    > pcbqa uygula --apply  -> skor 54.9 -> 100.0, 18 footprint, kart kaydedildi

### 27.9 Testler

**638 test** (önceki 600). Yeni: `test_minyaml` 21 (diferansiyel + reddetme),
`test_app` 17 (komut tablosu tutarlılığı, `tani`, ve **başlatıcının gerçekten
alt süreç olarak koşturulması** — geliştirici ortam değişkenleri silinerek,
son kullanıcının göreceği hâliyle).
## 28. Canlı mod — kurulumda izinle alınan API (2026-08-29)

### 28.1 İhtiyaç

Kullanıcı KiCad açıkken değişiklik yapılabilmesini istedi; gerekçesi şu:
**eş zamanlı çalışırken kendi hatama müdahale edebilmeli.** Ama "her seferinde
Tercihler'den API'yi aç" demek yeni kullanıcı için zorlayıcı. Doğru yer
**kurulum**: izni bir kez, açıkça alıp orada halletmek.

### 28.2 Önce düzeltilen bir yanılgı

İlk incelemede "KiCad 10'da şematik API'si yok" demiştim. Daha derin bakınca
**yanıldığım** ortaya çıktı ve bunu kaydetmek önemli:

`schematic_commands_pb2` diye ayrı bir dosya **yok** — ama gerek de yok, çünkü
`common/commands/editor_commands` **belge türünden bağımsız**:

    CreateItems, UpdateItems, DeleteItems, GetItems
    ParseAndCreateItemsFromString      <- s-expression metnini doğrudan alır
    BeginCommit / EndCommit            <- tek, GERİ ALINABİLİR işlem
    RefreshEditor, SaveDocument, RevertDocument

Ve `DOCTYPE_SCHEMATIC = 1` protokolde tanımlı. `BeginCommit`/`EndCommit`
tam olarak kullanıcının istediği şeyi verir: aracın yaptığı değişiklik
KiCad'in kendi geri alma yığınına girer, `Ctrl+Z` ile geri alınır.

**Sınır:** kipy 0.7.1'in üst düzey `schematic` sarmalayıcısı bozuk (kendi
protobuf'unda `BusEntryType` yok) — ama `KiCadClient.send()` ham bir kanal,
sarmalayıcı atlanabilir. 0.7.1 en güncel sürüm.

**Henüz doğrulanmadı:** KiCad 10.0.4'ün *sunucusunun* bu komutları şematik
için gerçekten uygulayıp uygulamadığı. Sonda hazır
(`scratchpad/sonda_canli.py`); API açılır açılmaz dört şeyi ölçecek: bağlantı,
açık şematik belgesi, öğe okuma, ve boş bir commit ile yazma yolu.

### 28.3 `pcbqa kurulum`

    pcbqa kurulum              ne değişeceğini gösterir (YAZMAZ)
    pcbqa kurulum --uygula     onaylayıp uygular
    pcbqa kurulum --geri-al    eski hâline döndürür

**İzin = `--uygula` bayrağı.** Önce tam olarak ne değişeceği gösterilir
(`api.enable_server` → `true`, dosya yolu dahil), sonra kullanıcı bilerek
onaylar. Sessiz bir yapılandırma değişikliği yok.

Güvenlik kuralları — bu, projenin **kullanıcının kendi yapılandırmasına
dokunan tek yeri**:

- **KiCad çalışıyorsa yazılmaz.** Sebep somut: KiCad ayarları bellekte tutar ve
  *çıkarken* dosyanın üzerine yazar; şimdi yazarsak değişikliğimiz kaybolur.
  Süreç adı ve pid söylenerek reddedilir (`--kicad-acikken` ile bilerek
  geçilebilir).
- **Yalnızca tek alan** değişir; tema, kütüphane yolları, pencere konumları,
  Türkçe anahtarlar aynen kalır (test bunu `assertEqual` ile bütün sözlük
  üzerinden koruyor).
- Yedek alınır, atomik yazılır, sonra **geri okunup doğrulanır**.
- Her şey geri alınabilir.

### 28.4 İki mod, ikisi de geçerli

| | API'siz mod (varsayılan) | Canlı mod |
|---|---|---|
| kurulum adımı | yok | bir kez, izinle |
| KiCad açıkken | dosyaya yazmaz | çalışan belgeye dokunur |
| geri alma | dosya yedeği | KiCad'in kendi `Ctrl+Z`'si |
| şematiğe canlı müdahale | hayır | evet |

Bağımsız uygulamanın dağıtım hikâyesi **değişmedi**: API'siz mod hâlâ sıfır
ayarla çalışıyor. Canlı mod, isteyen için bir üst basamak.

`pcbqa tani` artık hangi modun açık olduğunu da bildiriyor.

### 28.5 Ölçülen durum

    KiCad süreci     : kicad.exe (pid 12316), başlık "*KicadOtomasyon1 — Şematik"
    api.enable_server: false  -> IPC bağlantısı: Connection refused
    kurulum --uygula : REDDEDİLDİ (KiCad çalışıyor), ayar dosyasına dokunulmadı

Baştaki `*` işareti kullanıcının üç bileşeninin **kaydedilmemiş** olduğunu
gösteriyor — diskteki şematik hâlâ 230 bayt ve 0 sembol.

### 28.6 Testler

**656 test** (önceki 638). Yeni `test_kurulum` 18: tek alanın değiştiği
(sözlüğün tamamı karşılaştırılarak), Türkçe anahtarların hayatta kaldığı,
yedeğin eski hâli taşıdığı, bozuk JSON'da hiç yazılmadığı, KiCad çalışırken
reddedildiği ve reddedilen isteğin dosyaya dokunmadığı.

## 29. Kurulum uygulandı — ve başlatıcıda bulunan gerçek hata (2026-08-30)

### 29.1 `kurulum --uygula` çalıştı

KiCad kapatılmıştı, komut kabul edildi:

    guncellendi: C:\Users\ardaa\AppData\Roaming\kicad\10.0\kicad_common.json

Yedekle karşılaştırma, değişimin gerçekten tek alanla sınırlı kaldığını
gösteriyor — **1092 alandan 1 tanesi**:

    api.enable_server: False -> True

Kullanıcının şematiği bu arada kaydedilmiş: `KicadOtomasyon1.kicad_sch`
11699 bayt, üç sembol — `power:+10V`, `Device:R`, `Device:C`.

`pcbqa tani` artık `ok canli mod (IPC) acik` diyor.

### 29.2 Başlatıcı yalnızca kendi klasöründen çalışıyormuş

`tani`'yi başka bir dizinden çağırınca çıktı:

    No module named pcbqa

Kök sebep KiCad'in kendi `sitecustomize.py`'sinde
(`bin\Lib\site-packages\sitecustomize.py`):

```python
in_venv = sys.prefix != sys.base_prefix
if not in_venv:
    sys.path = []
```

Site aşamasında `sys.path` **komple siliniyor** ve yeniden kuruluyor. Silinenler
arasında `PYTHONPATH` girdileri de var. Ölçüm:

    set PYTHONPATH=...\pcbqa
    python.exe -c "import sys; print(sys.path)"
    -> ['', DLLs, Lib, site-packages, 3rdparty]        # pcbqa YOK

Yani `pcbqa.cmd`'nin kurduğu `PYTHONPATH` hiçbir zaman işe yaramıyormuş.
Başlatıcı yalnızca `-m`'in çalışma dizinini site'dan **sonra** eklemesi
sayesinde ayakta duruyordu — yani yalnızca kullanıcı paket klasöründeyken.

Testler bunu göremedi çünkü `LauncherTests._run` her zaman `cwd=PROJECT`
veriyordu. İki katmanlı bir körlük: hem geliştirme ortamı `.venv` kullandığı
için silme hiç tetiklenmiyor (`in_venv` doğru), hem de test çalışma dizinini
paket klasörü seçiyordu.

### 29.3 Çözüm: `baslat.py`

`pcbqa.cmd` artık `-m pcbqa.app` değil, paketin **yanında** duran
`baslat.py`'yi çalıştırıyor. CPython betiğin klasörünü site'dan sonra
`sys.path[0]`'a koyduğu için o girdi silmeden kurtuluyor; `baslat.py` ayrıca
kendi klasörünü açıkça ekliyor — sıraya değil, bildiğimiz yola güveniyoruz.

Ölçüm, dört ayrı dizinden:

    C:\Windows                          -> 0
    C:\Users                            -> 0
    ...\Kicad          (proje kökü)     -> 0
    ...\Kicad\pcbqa    (paket klasörü)  -> 0

### 29.4 Aynı kök sebep ikinci yerde

`tests/test_swig_bridge.py` içindeki `run_in_kicad` da KiCad'in Python'una
`env={"PYTHONPATH": PROJECT}` veriyordu. O da hiç işe yaramıyormuş; testler
yalnızca çalışma dizini paket klasörü olduğu için geçiyordu. Artık yol betiğin
önsözünde ekleniyor ve `cwd` bilerek `PROJECT.parent` yapıldı — böylece test
çalışma dizinine **yaslanmadığını kendisi kanıtlıyor**.

### 29.5 Yeni testler

`test_app` 17 -> 20:

- `test_launcher_runs_from_an_unrelated_directory` — cwd'yi elinden alır
- `test_pythonpath_alone_is_not_relied_upon` — KiCad'in Python'unun
  `PYTHONPATH`'i hâlâ yok saydığını doğrular; bir gün sayarsa test düşer ve
  `baslat.py`'nin gerekçesini gözden geçirmemizi söyler
- `test_bootstrap_sits_next_to_the_package`

Bead: `Kicad-i6z` (kapatıldı). Hafıza: `kicad-python-sys-path-silme`.

## 30. Karar katmanı ve canlı düzenlemenin gerçek sınırı (2026-08-30)

### 30.1 İki yeni modül

Kullanıcının sorusu şuydu: *"bu bağlantıyı yaparken kendi zihnini de kullandın
mı yoksa uygulama mı tüm işi yaptı"*. Dürüst cevap: **topoloji kararı bendeydi**,
uygulamada onu verecek bir katman yoktu. Bu bölüm o boşluğu kapatıyor.

- **`propose.py`** — sayfaya bakıp bağlantı **önerir**. Dosyada niyet yazmaz ama
  **yerleşim yazar**: iki pin tam aynı hizadaysa bu tesadüf değil.
  - `hizalama` — iki boş pin aynı x ya da y'de, aralarında engel yok, **ve
    birbirinin en yakın hizalı komşusu**. Karşılıklılık şartı bilinçli: tek
    yönlü yakınlık, hangisinin doğru olduğunu bilmediğimiz bir seçim demek.
  - `guc-inisi` — güç sembolünün boş pini, bir tel parçasının **ortasına** dik
    iniyorsa.
  - Kanıtı olmayan hiçbir şey önerilmez ve **atlanan pin adıyla söylenir**;
    sessizce atlanan bir pin, kullanıcının fark etmediği eksik bağlantıdır.

- **`connect.py`** (`pcbqa bagla`) — kararı yürütür. İki giriş: `--ag` (beyan)
  ve `--oner` (çıkarım). Yolu `sch_wire.route` çıkarır, junction'ı KiCad'in
  kendi kuralıyla sayar, `sch_write` yazar, sonra **`kicad-cli` netlist'i
  hakemdir**.

### 30.2 Ölçüm iki gerçek hata buldu

**Kısa devre.** İlk sürümde öneri `R1.1 - R1.2` diyordu — yani direncin kendi
iki ucunu birleştiriyordu. Sebep: en yakın hizalı komşu R1 için R1.2 (7.62 mm),
C1.1 değil (15.24 mm). Kural eklendi: **aynı sembolün pinleri asla eşleşmez** —
o hizalama sembolün *geometrisinden* gelir, kullanıcının yerleşiminden değil,
yani hiçbir niyet taşımaz. Testle korunuyor.

**Hakemin yanlış aradığı şey.** `#PWR01.1 R1.1 C1.1` ağı doğru tellenmişti ama
hakem reddetti. Sebep: KiCad netlist'inde **güç sembolleri düğüm olarak hiç
görünmez** — ağ `+10V → C1.1, R1.1` diyor, `#PWR01.1` listede yok. Hakem
sağlanamayacak bir şey arıyordu. Düzeltme: güç için ağın **adına** bakılıyor
(KiCad ağı güç sembolünün değeriyle adlandırır). `NetCheck.power_name`.

### 30.3 Sonuç: uygulama aynı kararı verdi

Aynı üç parça üzerinde `--oner`, elle verdiğim kararın **aynısını** üretti —
üç tel, aynı koordinatlar, `(39.37, 45.72)`'de aynı junction — ve her birinin
gerekçesiyle. `kicad-cli` netlist'i onayladı.

Kalan sınır dürüstçe duruyor: sayfada yalnızca R ve C varsa seri mi paralel mi
olacağı **dosyada yazmıyor**. Burada eksik olan yetenek değil bilgi; uygulama
öneri üretmez ve nedenini söyler.

### 30.4 Canlı düzenleme: şematikte yok, PCB'de VAR

Şematik tarafı kapandı (§29, `Kicad-5be`): `GetItems` handler'ı yok, ve
`BeginCommit` mesajının **hiç alanı yok** — belgeye bağlanamıyor, yönlendirilemiyor.
Sondalama KiCad'i iki kez çökertti (dosya her ikisinde de sağlam kaldı).

Ama PCB tarafı ölçüldü ve **çalışıyor**:

    GetItems(KOT_PCB_FOOTPRINT)              -> 18 oge okundu
    begin_commit + update_items + push_commit -> kabul; J1 8.000 -> 9.000 mm
    pcbqa uygula-ipc --apply                  -> 16 footprint CANLI tasindi,
                                                 kilitli J1/J2 atlandi,
                                                 undo gecmisine TEK islem

Yani kullanıcının istediği *"ben bakarken araç çalışsın, hatasına `Ctrl+Z` ile
müdahale edeyim"* akışı **PCB tarafında zaten gerçekleşiyor** — `ipc_apply`
yazılmıştı ama API kapalı olduğu için hiç doğrulanmamıştı.

### 30.5 Düzelen bir tespit

"Bağımsız editör API sunucusuna kaydolmuyor" demiştim — **yanlış**. Tek başına
çalışan `pcbnew.exe` soketi kendisi barındırıyor. Önceki `eeschema` denemesinde
`kicad.exe` soketi zaten tutuyordu; o bir çakışmaydı. Kural: canlı çalışırken
**aynı anda tek KiCad örneği**.

kipy notu: `Vector2(x=..., y=...)` yok; `Vector2.from_xy()` / `from_xy_mm()`.

### 30.6 Testler

`test_propose` 9 + `test_connect` 19. Örnek eklendi: `samples/uc_parca/` —
üç bağlantısız sembol (`power:+10V`, `R1`, `C1`), öneri katmanının sabit sınavı.

## 31. Serena çıktı, graphify girdi — bilgi grafiği hafızası (2026-08-31)

### 31.1 Serena kaldırıldı

MCP sunucusu kullanıcı kapsamından silindi, `.serena/` hem diskten hem git
indeksinden kaldırıldı (10 dosya). İçeriği kaybolmadı: `.serena/memories/`
dosyaları zaten *"Hepsi HANDOFF.md / README.md'de gerekçesiyle birlikte
kayıtlı"* diyordu. Projenin hafıza sistemi zaten `bd`; Serena ikinci ve
gereksiz bir kayıt yeriydi. Belgelerdeki tek sarkan atıf düzeltildi.

### 31.2 Beads bilgisi dosyaya aktarıldı

Beads bir Dolt veritabanında duruyor, yani **hiçbir dosya tarayıcısı onu
göremiyor** — oysa projenin ölçülmüş bilgisinin çoğu orada. 8 hafıza + 32 kayıt
`pcbqa/docs/hafiza/` altına yazıldı; her hafıza **ayrı dosya**, çünkü grafikte
her biri kendi düğümü olsun istiyoruz.

Tazeleme mantığı: `bd recall <anahtar>` + `bd list --status open,closed --json`.
Not: `bd` bir npm shim'i; Windows'ta `subprocess` uzantısız adı bulamıyor,
`bd.cmd` vermek gerekiyor.

### 31.3 Grafik

    3423 dugum, 7350 kenar, 174 topluluk
      3006 AST      tree-sitter, YEREL, 0 jeton, LLM yok
       417 anlamsal 4 alt-ajan, 664.798 jeton
       417/417 anlamsal dugum GEREKCE tasiyor

Kimlik çakışması **0** — alt-ajanlara verilen düğüm-kimliği kuralı AST'nin
ürettiğiyle birebir uyuştu. Sağlık: 336 sarkan uçlu, 480 çökmüş kenar; bunlar
AST'nin grafik dışı sembollere (stdlib, üçüncü parti) referansları.

Asıl kazanç kod haritası değil **gerekçe haritası**. Örnek: `graphify explain
pcbqa_handoff_sessiz_hata_sinifi` çağrısı, HANDOFF'un dört ayrı bölümündeki
altı gerçek hatayı (`pinfunction` hiç okunmuyordu, bayat `move-v2.json` yolu,
`decoupling_counts()` çağrılmıyordu, KiCad 5 körlüğü, iz/via netleri numara
okunuyordu) **tek kavram altında** bağlıyor. Böyle bir liste hiçbir dosyada
yok; grafik onu kendisi kurdu.

### 31.4 Her oturumda açık — dört katman

| katman | ne yapar |
|---|---|
| `CLAUDE.md` `## graphify` bölümü | her oturumda yüklenir |
| `PreToolUse` kancaları | `Bash\|Grep` ve `Read\|Glob` öncesi hatırlatma **enjekte eder** (engellemez — ölçüldü, çıkış 0) |
| `SessionStart` kancası | `.claude/graphify-durum.py` — düğüm/kenar/topluluk, yaş, commit edilmemiş `.py` sayısı |
| `graphify hook install` | post-commit / post-checkout otomatik tazeleme |

Üçüncüsünü biz yazdık. Sebep: graphify'ın kendi kurulumu grafiğin *var
olduğunu* söylüyor ama **ne kadar bayat olduğunu** söylemiyor. Bayat grafik,
güvenle sorgulanan yanlış bir haritadır.

### 31.5 Tuzaklar

- `graph.json` **node-link** biçiminde: kenarlar `links` altında, `edges`
  altında **değil**. `edges` diye okuyunca sessizce `0` çıkıyor (bu bize oldu).
- Kümeleme her yeniden kurulumda baştan koşuyor (174 → 165 ölçüldü);
  **topluluk numaraları değişiyor** ve elle verilen adlar **siliniyor** —
  yerine en yüksek dereceli düğümün adı geçiyor (`Design`, `load_design`,
  `parse_with_stats`). Yani post-commit kancasını kurup bırakırsak grafik her
  commit'te biraz daha okunmaz hale gelir, sessizce.

  Çözüm: adlar topluluk numarasına değil **çapa düğümüne** bağlandı
  (`.claude/graphify-etiketler.json`). Çapa kimlikleri dosya yolundan türediği
  için yeniden kümelemede değişmiyor. `.claude/graphify-etiketle.py` her oturum
  başında adları geri uyguluyor; çapası olmayan topluluklar graphify'ın kendi
  türettiği adla kalıyor — uydurma ad vermek yerine. Bir çapa kaybolursa
  betik bunu **söylüyor**, sessizce atlamıyor.
- `graphify claude install --project`, projenin **sürüm kontrolündeki**
  `CLAUDE.md`'sine yazar. `graphify-out/graph.json` bilinçli olarak
  `.gitignore` dışında bırakıldı: `graphify hook install` onun için bir
  birleştirme sürücüsü kaydediyor, yani izlenmesi bekleniyor.

### 31.6 Çalışma anlaşması — graphify entegre (2026-08-31)

Kullanıcının kalıcı talimatı: her karar, her hata düzeltmesi ve her gelecek
planı graphify'a işlenecek, ve bu her oturumda hatırlanacak.

Bir söz olarak bırakılmadı, **mekanizma** kuruldu — çünkü davranış kuralları
unutulur, oturum başında koşan bir kanca unutulmaz:

```
bd create / bd remember              beads = KANONİK kaynak
python .claude/graphify-bilgilendir.py
        beads → pcbqa/docs/hafiza/*.md
        graphify update .
        .claude/graphify-etiketle.py
```

`pcbqa/docs/hafiza/` **üretilmiş çıktıdır, elle düzenlenmez.** Betik beads'ten
silinen bir hafızanın dosyasını da siler — yoksa grafik artık geçerli olmayan
bir kararı doğruymuş gibi taşırdı.

Kural üç yerde birden duruyor (`CLAUDE.md` §Çalışma Anlaşması, beads hafızası
`calisma-anlasmasi-graphify-entegre`, ajanın kendi dosya hafızası) ve ayrıca
`SessionStart` çıktısında her oturum görünüyor.

**Betiğin sınırı çıktıda söyleniyor, saklanmıyor:** yeni kaydın *metnini*
dosyaya düşürür ve aranabilir yapar, ama **kavram düğümü ve gerekçe kenarları
oluşturmaz** — onlar anlamsal tarama ister (`/graphify --update`, alt-ajan
gerektirir, kullanıcı onayı ile).

Çapa çakışmaları da sessiz geçmiyor: iki çapa aynı kümeye düşerse betik bunu
yazıyor (`Varyant kesfi -> Niyetten kart uretimi`). İki ayrı kavramın tek kümeye
düşmesi, kümelemenin kaydığını ve adlandırmanın gözden geçirilmesi gerektiğini
söyler.

## 32. İki dilli bileşen sözlüğü (2026-08-31)

`lexicon.py` — KiCad'in açık kaynak kütüphanelerinden bileşen adlarını
çıkarır: kısaltma, tam ad, İngilizce ve Türkçe. Amaç ileriki makine
öğrenimi: bir bileşeni *adından* tanımak. `C`, `kondansator`, `capacitor` ve
`Device:C_Polarized` aynı şeyi söylüyor; model bunu bilmiyorsa öğrenemez.

### 32.1 Üç katman, üçü de farklı güvenilirlikte

| katman | nasıl kuruldu | büyüklük |
|---|---|---|
| `DESIGNATORS` | elle, **ama ölçümle** | 67 önek |
| `TERMS` + `PHRASES` | elle, seçim ölçüme dayalı | 252 + 31 |
| `semboller` | KiCad kütüphanelerinden çıkarıldı | 22.776 |

**Önek adları ezberden yazılmadı.** Her önek için, o öneki kullanan
sembollerin açıklamalarında en sık geçen kelimeler ölçüldü ve ad ona göre
verildi. Tablodaki `ornek` alanı o ölçümün izidir — `TR` gerçekten
"transformer, secondary, balanced, mhz" diye kullanılıyor, biz öyle
sandığımız için değil.

**Terim seçimi de ölçüme dayalı:** 45.187 açıklama alanında 266.284 kelime
sayıldı, sıklık listesinin başı alındı.

### 32.2 Uydurulmayan şey

22.776 sembolün çoğu parça numarasıdır (`STM32F103C8Tx`, `TPS54331`).
Bunların "Türkçesi" yoktur. Bir sembolün Türkçe alanı **ancak `TERMS`'ten
gerçek bir eşleşme çıktığında** dolar; çıkmazsa boş kalır. `kapsam()` bu
oranı söyler ve test `%100`'ü **şüpheli** sayar — parça numaralarının
Türkçesi olmamalı.

Ölçülen kapsam: kategorisi bilinen **%100.0**, Türkçe karşılığı **%94.6**.

Paket adları (SOT-223, LQFP, QFN) ve üretici adları (STMicroelectronics)
bilinçli olarak çevrilmez; `CEVRILMEZ` listesi bunu belgeler ve bir test
o kelimelerin `TERMS`'e sızmadığını korur.

### 32.3 Ölçümün bulduğu iki şey

**Kelime kelime çeviri bozuyordu.** `Through hole` → `Through delik`,
`Single solar cell` → `tek solar cell`. Çözüm: `PHRASES` — çok kelimeli
kalıplar, uzundan kısaya, kelime değişiminden **önce** uygulanıyor.

**`U6`, `RL2`, `MES?` ayrı önek değil.** Bazı sembollerin `Reference`
alanına örnek numarası ya da soru işareti sızmış (7 varyant, 71 sembol).
`normalize_designator()` bunları kırpıyor — ama **yalnızca sonuç tanımlı bir
öneke düşüyorsa**, yoksa gerçekten yeni bir önek sessizce yutulurdu.
Bu düzeltmeyle kategori kapsaması %99.5 → %100.

### 32.4 Kullanım

```
pcbqa sozluk                 özet
pcbqa sozluk --uret          sözlüğü üret (data/kicad-sozluk.json.gz, 424 KB)
pcbqa sozluk --ara direnc    iki dilde ara
```

Arama **tam kelime** eşler, alt dizi değil: ölçüldü, alt dizi araması `C`
için 41 önek döndürüyordu (`Capacitor`, `Circuit`, `Microphone`… hepsinde
`c` var) ve bu bilgi değil gürültüdür.

Üretilen dosya izleniyor (424 KB): ML için sabit bir sözcük dağarcığı sürümü
olması, yeniden üretilebilir olmasından daha değerli. KiCad sürümü değişince
`--uret` ile tazelenir.

Testler: `test_lexicon` 20.

## 33. Sentetik MPN ve fiyat alanları (2026-08-31)

`mpn.py` — bileşenlere parça numarası ve fiyat alanı yazar. Kullanıcı açıkça
*"gerçekçi bir şekilde fiyat ya da mpn numarası göstermesi gerekmiyor, şu
anlık test için"* dedi; sınanan şey **alan yazma yolu**, tedarik verisinin
doğruluğu değil.

### 33.1 Uydurma veri uydurma görünmeli

Bu modülün en büyük riski teknik değil: birinin bu fiyatları gerçek sanması.
Üç koruma:

- Her MPN `SENT-` ile başlar.
- Her sembole `MPN_Kaynak = sentetik-test` alanı yazılır. Gerçek bir tedarikçi
  bağlandığında bu işareti taşıyan her kayıt **güvenle** üzerine yazılabilir.
- Üretici adları uydurmadır (`SentCo`, `TestParts`, `MockElec`, `DemoComp`) —
  uydurma bir fiyatın yanına gerçek bir marka yazmak yanlış izlenim bırakır.
  Bir test bu adların gerçek firma adlarına benzemediğini korur.

### 33.2 Süsleme, istenen değişmezi bozdu

İlk iki sürümde fiyata "gerçekçi dursun" diye deterministik bir sapma
ekliyordum (±%2). Ölçüm gösterdi ki üst kademelerde adımlar küçülüyor
(40 µF → 45 µF yalnızca %0.4) ve sapma **sıralamayı ters çeviriyordu**:
C10 (45 µF), C9'dan (40 µF) ucuz çıktı.

Kullanıcının istediği tam olarak sıralamaydı ("en ucuzdan pahalıya"). Görsel
bir süslemenin istenen değişmezi bozmasına izin verilmez — sapma **kaldırıldı**.
Fiyat artık saf bir `(değer, paket)` fonksiyonu; bir test on değeri sırayla
karşılaştırıp monotonluğu koruyor.

Aynı hikâyenin ikinci yarısı: `_base_price` değeri okunamayan bileşene `0.10`
sabiti veriyordu, yani `Device:C`'nin varsayılan `"C"` değeri de fiyat
alıyordu — hakkında hiçbir şey bilinmeyen parçaya güvenle fiyat yazmak.
Artık `None` dönüyor ve o bileşen **engel olarak raporlanıyor**, sessizce
atlanmıyor.

### 33.3 Ölçülen sonuç

`KicadOtomasyon1` üzerinde 10 kondansatöre uygulandı, 40 alan yazıldı:

```
C2   5uF  SENT-C9783-0402  $0.5559      <- en ucuz
...
C11 50uF  SENT-C2973-0402  $0.6359      <- en pahali
C1  (deger 'C' okunamadi)  -> fiyat atanmadi
```

Sıralama istisnasız. KiCad'in kendi netlist'i alanları `MPN` / `Price` /
`Manufacturer` / `MPN_Kaynak` olarak geri okuyor.

Yeni alanlar **gizli** yazılıyor (`hide yes`): şematikte görünseler sayfa
okunmaz hale gelirdi, ama KiCad BOM'da yine görüyor.

Testler: `test_mpn` 14.

## 34. Doğal dil komutu — `pcbqa yap` (2026-09-03)

Kullanıcı şunu istedi: *"ben şu anki modelimize 10 adet kapasitör koy dedim,
bunu anlayacak ve uygulayacak hale getirmeliyiz"*.

Altta duran her şey **zaten hazırdı**: `sch_add.add_symbols` sembolü
kütüphaneden getiriyor, sayfada boş yer buluyor, netlist kalkanını
çalıştırıyor, yedek alıyor, atomik yazıyor. Eksik olan tek şey **cümleyi o
çağrıya çeviren katmandı**. `komut.py` yalnızca onu yapar; hiçbir dosyayı
kendisi yazmaz.

### 34.1 Neden modelsiz

Üç kısıt, üçü de ölçülmüş bir gerçeğe dayanıyor:

1. `pcbqa`nın **çalışma zamanı bağımlılığı yok** ve KiCad'in kendi
   Python'unda koşuyor (§27). Bir model istemcisi bunu bozardı.
2. Testler sessizliği korur — aynı cümle her koşuda **aynı** planı üretmeli.
3. "Basit görev" dağarcığı **kapalı** bir küme: fiil, adet, tür, değer,
   paket. Kapalı küme için çözümleyici hem daha doğru hem hesapsız.

Yine de çıktı **tipli bir sözleşmedir**:

```
anla(metin) -> Yorum{ eylemler: [Eylem], notlar, engeller }
uygula(yorum, sch) -> [sch_add.AddResult]
```

İleride bir model cümleyi doğrudan `Eylem` listesine çevirebilir;
uygulayıcı, kalkan ve testler değişmez. Kapı açık, bağımlılık yok.

### 34.2 Anlaşılmayan görünür

Projenin geri kalanıyla aynı doktrin:

| durum | sonuç |
|---|---|
| bilinmeyen fiil | ENGEL, bilinen fiiller listelenir |
| bilinmeyen bileşen | ENGEL, bilinen türler listelenir |
| belirsiz sözcük (`transistör`) | ENGEL + adaylar (NPN mi PNP mi MOSFET mi) |
| tanımsız paket (`1206 bobin`) | ENGEL |
| eşleşmeyen kelime | NOT olarak dökülür, yutulmaz |
| değer verilmemiş | NOT — **uydurulmaz**, kütüphanedeki değer kullanılır |

İlk sürüm yalnızca **ekliyordu**; `bağla` §34.6'da geldi. `sil` / `taşı` /
`değiştir` hâlâ tanınır ama reddedilir: *"anlamadım"* ile *"henüz
yapmıyorum"* ayrı şeylerdir.

### 34.3 Dört gerçek hata — üçünü test yakaladı

- **`"on"` dolgu kelimesi sanıldı.** İngilizce edat diye `DOLGU`ya konmuştu;
  Türkçe *"on adet kapasitör"* komutundaki **10 sessizce 1'e düştü**. Artık
  bir nöbetçi test `DOLGU ∩ SAYILAR = ∅` olduğunu koruyor.
- **`Device:Ferrite_Bead` diye bir sembol yok** — KiCad'de adı
  `Device:FerriteBead`. `test_every_lib_id_resolves` ilk koşuda yakaladı.
  Tablodaki her `lib_id` ve her footprint gerçek kütüphaneye karşı sınanıyor;
  uydurma sembol adı yazılamaz.
- **Değer sadeleştirilmiş kelimeden okunuyordu**, yani `10M` (mega) ile
  `10m` (mili) aynı şeye düşüyordu — 10 megaohm'luk direnç şematiğe 10
  miliohm diye yazılırdı. Değer artık **ham** kelimeden okunur, tür sözcüğü
  sadeleştirilmişten.
- **Virgül koşulsuz ayraçtı.** Türkçe ondalık ayracı da virgüldür; `4,7k`
  ikiye bölünüp değer kayboluyordu. Ayraç artık `(?<!\d)[,;](?!\d)`.

### 34.4 Türkçe iki yerde ısırıyor

- `"İ".lower()` ayrı bir birleştirici nokta (U+0307) bırakır ve tablo
  eşleşmesi kaçar. Bu yüzden **önce** büyük Türkçe harfler ASCII küçüğe
  çevrilir, **sonra** `lower()` çalışır.
- Türkçe eklemelidir: `kapasitör`, `kapasitörler`, `kapasitörü`,
  `kapasitörden` aynı sözcüktür. Hepsini tabloya yazmak tabloyu okunmaz
  ederdi. Kırpma kuralı `lexicon.normalize_designator` ile **aynı**: kırpma
  yalnızca sonucu tabloda **tanımlı** bir sözcüğe düşürüyorsa kabul edilir —
  böylece gerçekten bilmediğimiz bir kelime sessizce bir bileşene bağlanmaz.
  (`zımbırtı` engel olarak kalır.)

### 34.5 Ölçülen sonuç

```
> pcbqa yap "şu anki modelimize 10 adet kapasitör koy" --sch ..\KicadOtomasyon1
anlasilan: "şu anki modelimize 10 adet kapasitör koy"
  10 x Kondansator (Device:C)
  not: deger verilmedi - kutuphanedeki deger kullanilacak
  C12 @ (15.24, 16.51) ... C21 @ (129.54, 16.51)
  kalkan: mevcut devre degismedi, yalnizca yeni bilesenler eklendi
  (dry-run - yazmak icin --uygula)
```

Çok istekli cümle de tek geçişte:

```
pcbqa yap "5 adet 100nF 0603 kondansatör ve 3 adet 10k direnç ekle" --uygula
  -> C8..C13 (footprint doğrulandı: C_0603_1608Metric), sonra R22..R24
```

İkinci eylem birincinin **yazılmış** halini okur; yoksa iki plan da aynı
referansları verirdi. Bir eylem engele takılırsa sonrakiler **çalışmaz** —
yarım uygulanmış bir cümle, hiç uygulanmamış olandan zor toparlanır.

Testler: `test_komut` 41 (çözümleme testleri KiCad'siz koşar; kütüphane ve
uçtan uca testleri KiCad kuruluysa).

### 34.6 Bağlama fiili — eklenen sembol artık bağlantısız değil (2026-09-04)

`Kicad-d8f`in ilk maddesi. Ölçülen eksik şuydu: `pcbqa yap "10 kapasitör
ekle"` sayfaya **on tane bağlantısız sembol** bırakıyordu; kullanıcının
gerçekten istediği cümle *"…ve hepsini VCC-GND arasına bağla"*ydı.

Alt katman yine hazırdı: `sch_add.add_symbols(connect=["1=VCC", "2=GND"])`
etiketi/telleri çiziyor, `_expected_joins` ile kalkana *"bu pin şu pinlerle
aynı ağa girmeli"* diyor. Eksik olan tek şey **kalıbı o çağrıya çeviren
katmandı**.

```
pcbqa yap "6 adet 100nF kondansatör ekle ve hepsini VCC ile GND arasına bağla"
  6 x Kondansator (Device:C)  deger=100nF  bagla: 1=VCC, 2=GND
  C8 @ (15.24, 16.51) ... C14 @ (78.74, 16.51)
  baglanti: C8.1 -> VCC (etiket)   ... 12 bağlantı
  kalkan: mevcut devre degismedi, yalnizca yeni bilesenler eklendi
```

Ölçü şematikteki etiket değil, KiCad'in çıkardığı **netlist**tir: uçtan uca
test altı kapasitörün ikişer pinini `net_of` üzerinden `VCC` ve `GND`de
doğrular ve **eski her pinin ağının değişmediğini** ayrıca ölçer.

**Kalıp cümleden EN BAŞTA ayrılır**, ekleme çözümlemesinden önce. İki
ölçülmüş sebep:

1. Ayraç `"ve"`dir. `"VCC ve GND arasına"` cümlenin ortasında kalırsa
   `_AYRAC` onu ikiye böler ve iki yarım istek çıkar.
2. `"toprak"` hem bir **ağ adı** hem bir **bileşen türü**dür (`power:GND`).
   Kalıp ayrılmazsa `"VCC ile toprak arasına bağla"` sayfaya istenmeyen bir
   toprak sembolü de eklerdi.

#### İki gerçek hata

- **Yapı sözcüğü ağ adı sanıldı.** Ayraç `" ve "` olduğu ve regex en soldan
  eşleştiği için `"2 diyot ekle ve VCC-GND arasına bağla"` cümlesinde
  hedefler `("ekle", "VCC-GND")` diye okundu — iki diyotun katoduna `ekle`
  adında bir ağ yazılacaktı. Hedef artık yapı sözcüğü (fiil, dolgu, kapsam,
  sayı) olamaz; **bileşen sözcükleri bu listeye girmez**, çünkü `LED` ya da
  `CLOCK` gerçek ağ adlarıdır. Reddedilen eşleşmeden sonra tarama hedefin
  **sonundan** devam eder: başından devam edince `"ekle"` bu kez `"kle"`
  diye eşleşti.
- **`uygula` aşamasındaki notlar hiç basılmıyordu.** `main()` önce
  `yorum.describe()` yazıyor, sonra `uygula`yı çağırıyordu; `uygula`nın
  eklediği notlar — *"VCCC diye bir ağ YOK"* uyarısı ve daha eski olan
  dry-run numaralama notu — ekrana **hiç** çıkmıyordu. Artık `uygula`dan
  sonra yeni notlar basılıyor (hata yolunda da).

#### Ağ adının yazımı tahmin edilmez, şematiğe sorulur

KiCad'de ağ adları büyük/küçük harfe **duyarlıdır**: `"vcc"` yazan kullanıcı
`VCC` ağına bağlanmış olmaz, on kapasitör boş bir `vcc` adasında kalır.
**Netlist kalkanı bunu yakalamaz** — yeni bir ağ oluşturmak da geçerli bir
işlemdir ve kalkan yalnızca *eski* devrenin değişmediğini ölçer. Bu yüzden
`uygula` hedefleri şematikteki gerçek yazımla eşler:

| durum | sonuç |
|---|---|
| `VCC` (birebir var) | aynen kullanılır |
| `vcc` (yalnız harf farkı) | `VCC` yapılır + NOT |
| `VCCC` (hiç yok) | **UYARI** + mevcut adlar listelenir |
| `toprak` / `ground` | `GND` okunur + NOT (`AG_ADLARI`) |

#### Reddedilenler

| cümle | sonuç |
|---|---|
| `... ekle ve bağla` | ENGEL — kalıp yok; bağlantısız sembol bırakmaktansa hiç eklememek |
| `C5 ile C6 arasına bağla` | ENGEL — bu katman yalnızca **eklerken** bağlar |
| `... hepsini C5 ile GND arasına` | ENGEL — `C5` bir referans, ağ adı değil |
| `5 direnç ve 5 kapasitör ekle ve VCC-GND arasına` | ENGEL — hangi gruba ait belirsiz, `"hepsini"` gerek |
| `3 toprak ekle ve VCC-GND arasına` | ENGEL — `power:GND` tek uçlu |

Kutuplu bileşende (diyot, LED, polarize kondansatör) yön **elektriksel bir
karardır** ve cümle onu söylemez: seçilen yön NOT olarak yazılır, sessizce
seçilmez. `TURLER`deki uç numaraları ve kutup adları kütüphaneye karşı
sınanır (`test_declared_pins_exist`,
`test_polarity_names_match_the_library`) — KiCad diyot pin sırasını
değiştirirse not sessizce yanlışlaşmasın.

Testler: `test_komut` 41 → **67**.

Sonraki adımlar `Kicad-d8f`de: silme (`compare_subtractive` gerekir),
örneğe referansla konuşma (`C5`, `son eklediklerim` — var olan bir pine
bağlama da bunu bekliyor), dağarcığı `lexicon`in ölçülmüş 22.776
sembolünden türetme.

## 35. Masaüstü arayüzü ve parça tablosu (2026-09-03)

Kullanıcı: *"kullanabileceğim bir python arayüzü yaz, işlerimi o arayüz
üzerinden de gerçekleştirebileyim"* + *"MPN bilgisi, fiyat ve üstünden geçen
amperi voltajı tablo olarak göstersin her parça için"*.

İki yeni modül: `arayuz.py` (`pcbqa arayuz`) ve `elektrik.py`
(`pcbqa parcalar`). Arayüz CLI'nin **yerine geçmez, üstüne biner**: her sekme
aynı modülün aynı fonksiyonunu çağırır, ikinci bir mantık yazılmaz.

### 35.1 Ölçülen kısıt: KiCad'in Python'unda tkinter yok

```
"C:\Program Files\KiCad\10.0\bin\python.exe" -c "import tkinter"
-> ModuleNotFoundError: No module named '_tkinter'
```

Bu §27'yi doğrudan etkiliyor: `pcbqa.cmd` yorumlayıcı olarak **önce KiCad'in
Python'unu** seçer, yani arayüz başlatıcının varsayılan yorumlayıcısıyla
açılamaz. Karşılık, sessiz olmayan bir geri çekilme:

- `arayuz.main()` tkinter'ı bulamazsa **çıkmaz**; `py` / `python` /
  `python3` arasında tkinter'ı olanı arar, `baslat.py` üzerinden oradan
  açılır ve **ne yaptığını yazar**. Ölçüldü: KiCad'in Python'undan
  `tkinterli_python()` → `python3`.
- Hiçbiri yoksa ne yapılacağını söyler (`PCBQA_PYTHON`) ve CLI'ye yönlendirir.

Kullanıcıya üç seçenek sunuldu (tarayıcı arayüzü / tkinter / yalnız API);
tkinter **bilinerek** seçildi, bu kısıt bilinerek kabul edildi.

### 35.2 İki adımlı güvenlik, düğmeye çevrildi

CLI'de yazmak için `--uygula` yazmak zorundasınız. Arayüzde bunun karşılığı:
**"Uygula" kapalı başlar**, yalnızca *aynı cümle* + *aynı proje* için bir kuru
koşum geçtikten sonra açılır, cümle/proje değişince ve yazdıktan sonra tekrar
kapanır. `_uygula()` düğmenin görünümüne **güvenmez**, imzayı kendisi de
doğrular — testlerden biri tam olarak bunu, düğmeyi hiç kullanmadan sınar.

### 35.3 `elektrik.py` — asıl soru "neyi bilmiyoruz"

SPICE yok; akım genel halde türetilemez. Kural: her sayının yanında **nereden
bilindiği** yazılır, türetilemeyen **boş** kalır. Gerçekten türetilebilen üç şey:

1. **Ray gerilimi, net ADINDAN.** `+3V3`→3.3, `+1V8`→1.8, `-12V`→-12;
   GND ailesi 0 V (referans düğümü *tanımı*); `VBUS` 5 V (USB 2.0 spec 7.2.1).
   Ad bir kanıttır. Buna karşılık **`VCC` / `VDD` / `VIN` hiçbir şey
   söylemez** ve boş bırakılır — "VCC 5V'tur" varsayımı 3.3 V'luk bir kartta
   yanlış akım hesaplatırdı. Bir test tam olarak bu suskunluğu korur.
2. **Direnç akımı**: iki ucun gerilimi biliniyorsa `I = |ΔV| / R`.
3. **Kondansatör**: kararlı halde DC akım ≈ 0 — tahmin değil, elemanın tanımı.

Gerisi ("benzetim gerekir") boş kalır. Bir LED'in akımı seri direncinden
hesaplanabilirdi ama Vf parçaya özgüdür ve kütüphanede yazmaz; Vf uydurmak
tabloyu kirletirdi. KiCad'in `unconnected-(R2-Pad1)` adları **ağ değildir**,
tabloda "(bagli degil)" görünür ve sebep olarak yazılır.

### 35.4 Üç gerçek hata — üçü de ölçümle çıktı

- **`mpn.py` çöküyordu.** `_base_price` değeri 0 olan parçada
  `math.log10(0)` → `ValueError`. Ölçüldü: `samples/pic_programmer` C4'ün
  değeri `"0"`, yani `pcbqa mpn` o kartta çöküyordu. §33'teki karar ("değeri
  okunamayan parçaya fiyat yazılmaz") sıfırı kapsamıyordu; düzeltme o kararın
  **uzantısı**, tersi değil — 0 Ω'luk bir köprünün fiyatı büyüklükten zaten
  türetilemez.
- **tkinter iş parçacığı güvenli değil.** İlk sürümde arka plan işi
  `self.proje.get()` çağırıyordu; dört test `main thread is not in main loop`
  ile düştü. Artık her Tk değeri **ana iş parçacığında** okunup fotoğrafı
  arka plana geçiriliyor.
- **Kapanışta bekleyen `after`.** Pencere yok edildikten sonra zamanlayıcı
  ateş edip Tcl'de `invalid command name` üretiyordu; testte bir Tk
  yorumlayıcısını test başına kurup yıkmak ise
  `Tcl_AsyncDelete: async handler deleted by the wrong thread` ile yıkıyordu.
  Çözüm: zamanlayıcı kimliği saklanıp kapanışta iptal ediliyor, testler tek
  Tk yorumlayıcısı altında `Toplevel` kullanıyor.

### 35.5 Ölçülen sonuç

```
> pcbqa parcalar samples\pic_programmer\pic_programmer.kicad_sch
C1   100µF  Kondansator  1:VCC, 2:GND         2:0V    ~0   -        kararli halde DC akim gecmez
R1   10k    Direnc       1:+3V3, 2:GND        3.3 V   330 uA        Ohm yasasi: |3.3 V| / 10k
D8   RED-LED Diyot       1:GND, 2:Net-(D8-A)  1:0V    -             ag gerilimi bilinmiyor
J1   DB9    Konnektor    1:(bagli degil), ... 5:0V    -             baglanmamis pin: 1, 2, 6, 9
```

Testler: `test_elektrik` 24, `test_arayuz` 15 (Tk açılamayan ortamda atlanır).

## 36. Arayüz kısayolu ve ayrı başlatıcısı (2026-09-04)

Kullanıcı: *"açılması için kısayolu klasöre koy"*. İki dosya:
`pcbqa/pcbqa-arayuz.cmd` (kısayolun hedefi) ve klasördeki
`pcbqa Arayuz.lnk`. Kısayollar makineye özeldir — içinde mutlak yol gömülü —
bu yüzden `.gitignore`'a `*.lnk` eklendi; nasıl yeniden yapılacağı
`KURULUM.md`'de yazıyor.

### 36.1 Neden ayrı bir başlatıcı

§35.1'in doğrudan sonucu: `pcbqa.cmd` yorumlayıcı olarak **önce KiCad'inkini**
seçer ve KiCad Python'unu Tk olmadan paketler. Arayüz o yorumlayıcıyla
açılamaz. `pcbqa-arayuz.cmd` tkinter'ı **gerçekten** olan bir Python arar —
varsaymaz, her adayı çalıştırıp sınar — ve konsol penceresi açılmasın diye
onun **kendi** `pythonw.exe`'siyle başlatır. Aday sırası: `PCBQA_PYTHON`,
proje `.venv`'i, `py`, `python`, `python3`.

`--nerede` hangi çiftin seçildiğini yazar; kısayol çalışmadığında ilk
sorulacak soru bu olduğu için kalıcı bir bayrak.

### 36.2 Üç gerçek hata — üçü de sessizdi

- **Yanlış kurulumun `pythonw`'su.** İlk sürüm `pythonw`'yu PATH'ten
  alıyordu. Ölçüldü: bu makinede PATH'teki `pythonw`, Microsoft Store takma
  adı — tkinter'ı sınadığımız `.venv`'den **başka bir kurulum**. `start` onu
  çalıştıramadığı için **arayüz sessizce hiç açılmıyor**, başlatıcı yine de
  `0` dönüyordu. En kötü hata türü: başarı gibi görünen başarısızlık.
  Konsolsuz ikiz artık **yalnızca** seçilen yorumlayıcının kendi klasöründen
  alınır; bulunamazsa konsollu açılır ve bunu söyler.
- **`for /f "usebackq"` içindeki iç içe tırnaklar** cmd'de çözümlenmiyordu;
  `pythonw` yolunu üreten döngü **hiç sonuç üretmedi**, sessizce. Yol artık
  ara dosyaya yazılıp `set /p` ile okunuyor.
- **`if exist` yetmiyor.** Store takma adının `sys.executable`'ı
  `C:\Program Files\WindowsApps\...` altını gösterir ve o klasörün ACL'si
  yüzünden `if exist` **yanlış olarak** "yok" der. Hem tkinter hem `pythonw`
  denetimi artık adayı **çalıştırıp** çıkış koduna bakarak yapılıyor.

Ek olarak `baslat.py`: belge dizgesindeki `...\pcbqa`, Python 3.12+
tarafından geçersiz kaçış dizisi sayılıp **her çalıştırmada**
`SyntaxWarning` bastırıyordu — kullanıcının gördüğü ilk şey oydu. Dizge ham
(`r"""`) yapıldı.

### 36.3 Ölçülen sonuç ve ölçümün sınırı

Kısayoldan açılınca:

```
"...\.venv\Scripts\pythonw.exe"  "...\baslat.py" arayuz     (artık cmd penceresi: 0)
```

Pencerenin gerçekten haritalandığı **uygulamanın kendisine sorularak**
doğrulandı (`pythonw` altında, `sys.stdout is None` iken):

```
winfo_ismapped=1  viewable=1  1180x760
sekmeler: ['Yap','Parcalar','Analiz','Uret','Ortam']   Uygula: disabled
```

`EnumWindows` ile doğrulanamadı: bu oturumdan `pythonw` pencereleri
görünmüyor — **çıplak Tk de** aynı şekilde görünmüyor, yani bu uygulamanın
değil ölçümün sınırı. Bir yöntem iki farklı şeyi ayırt edemiyorsa kanıt
üretmiyordur; ayırt edebilen yöntem (uygulamaya sormak) kullanıldı.

Testler: `test_app` içinde `ArayuzLauncherTests` 4 test. Biri yazılırken
düştü ve **testin kendisi yanlıştı**: seçilen yorumlayıcıyı yol metninde
`kicad\` aramakla eliyordum, ama kullanıcının proje klasörünün adı da
`Kicad`. Denetim artık KiCad'in gerçek yorumlayıcı dosyasıyla karşılaştırıyor.
