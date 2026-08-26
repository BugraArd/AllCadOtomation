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
| 5 | Makine öğrenimi altyapısı (veri, model, ölçüm, güvenli bağlantı) | ✅ Bitti |
| 6/A | Geniş hamle repertuarı + model filtresi (yol haritası A1-A3) | ⚠️ Bitti, kazanç yok (§13) |

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
    features.py    DONMUŞ öznitelik şeması (v1, 51 öznitelik)
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
