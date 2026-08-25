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

Proje 4 aşamaya bölündü. **Aşama 0 ve 1 bitti**, Aşama 2-3'e geçilecek.

| Aşama | Kapsam | Durum |
|---|---|---|
| 0 | Salt-okunur analiz + rapor + ölçüm | ✅ Bitti |
| 1 | Kural motoru (YAML) + KiCad ERC/DRC entegrasyonu | ✅ Bitti |
| 2 | Yerleştirme **önerisi** üret, görselleştir, kullanıcı onaylar | ⬜ Sırada |
| 3 | Tam otomatik PCB yerleştirme | ⬜ |
| 4 | KiCad 11 ile şematik API'si + headless | ⬜ (KiCad'e bağlı) |

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
Tek bağımlılık: pyyaml 6.0.3
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
  report.py        terminal raporu + skor
  synth.py         sentetik test kartı üreteci
  __main__.py      komut satırı
  default_rules.yaml
samples/
  bench_good.kicad_pcb / bench_bad.kicad_pcb   (üretilmiş test tezgâhı)
  bench.rules.yaml                              (4 alanı kapsayan kural seti)
  pic_programmer/  + pic_programmer.rules.yaml  (demo kopyası)
run.cmd  README.md  requirements.txt  .gitignore
```

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
run.cmd samples\pic_programmer                                # kısayol
```

Bayraklar: `--rules --json --work-dir --kicad-cli --no-kicad-checks --no-color --fail-on`
Çıkış kodları: `0` temiz · `1` eşiği aşan bulgu · `2` araç hatası.

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
| `bench_bad.kicad_pcb` | 9 kasıtlı kusur | 1 / 100 |

Devre: USB-C → LDO regülatör → MCU (SOIC-20) + EEPROM (SOIC-8) + 12MHz kristal
+ UART header. 18 bileşen, 60×45 mm kart. Footprint'ler dosya içine gömülü
üretiliyor (kütüphane bağımlılığı yok). KiCad'in kendi DRC'si iki dosyayı da
sorunsuz ayrıştırıyor → format geçerli.

**Devrenin doğru cevabı kodda:** `spec.truth` sözlüğü hangi kondansatörün hangi
IC'ye ait olduğunu, hangi netlerin diferansiyel çift olduğunu tutuyor. Yani
kuralların doğru şeyi yakalayıp yakalamadığı kanıtlanabiliyor.

`bench_bad`'e ekilen kusurlar: 4 uzak decoupling/yük kondansatörü, 2 courtyard
çakışması (Y1/C7, R1/R2), 2 kart kenarı ihlali (J1, J2), bozuk USB çift
simetrisi (R5 yanlış yerde).

⚠️ **`bench_good`'un 1 hatası kasıtlıdır**: `nRESET` pull-up'ı yok. Bu bir
**devre** kusuru, yerleşim kusuru değil — her iki kartta da var ve yerleştirme
motoru bunu asla düzeltemez. Bu yüzden hedef 100 değil **67**. Motorun işi
`1 → 67` mesafesini kapatmak.

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
  `bench_good` 67, `bench_bad` 1.

## 8. Bilinen sınırlar

- Şematik **konumları** okunmuyor (KiCad 10'da IPC şematik desteği yok).
- Courtyard poligonu dışbükey kabukla alınıyor; dikdörtgenler için birebir,
  nadir içbükey (L/U) courtyard'larda fazladan bulgu üretebilir.
- Dairesel courtyard'larda alan biraz küçük çıkabilir (`fp_circle`).
- `length_match` HPWL üzerinden çalışır — gerçek uzunluk eşleme kontrolü değil,
  "bu iki net çok farklı yerlerde" ön uyarısıdır.

---

## 9. SIRADAKİ ADIM — Aşama 2/3: yerleştirme motoru

`bench_bad`'i alıp skorunu `bench_good` seviyesine (1 → 67) çıkaracak motor.
**Önce KiCad'e hiç dokunmadan**: sadece koordinat optimizasyonu + öncesi/sonrası
skor karşılaştırması. IPC ile karta yazma en sona bırakılacak (bindings alpha).

Planlanan maliyet fonksiyonu:

```
Cost = Σ_net w(net)·HPWL(net)              # ana terim, model.hpwl() hazır
     + λ₁·Σ courtyard çakışma alanı         # sert kısıt, geom.overlap() hazır
     + λ₂·Σ kart sınırı ihlali              # geom + board.outline hazır
     + λ₃·Σ_kritik (dist(cap, ic_pin) − hedef)²
     + λ₄·rotasyon cezası
```

Planlanan 4 fazlı akış (klasik EDA sırası — atlanırsa 200 bileşende saatlerce
dönüp kötü sonuç verir):

1. **Kümeleme** — netlist grafiğinden her IC + kendi decoupling'leri tek blok
2. **Global yerleştirme** — force-directed, sürekli uzayda kaba konum
3. **Legalizasyon** — courtyard çakışmalarını çöz, ızgaraya oturt
4. **Detaylı iyileştirme** — simulated annealing (`move`, `swap`, `rotate90`)

Başarı kriteri: `bench_bad` üzerinde skor 1 → 67'ye yaklaşmalı, ekilen 9
yerleşim kusurunun tamamı kapanmalı, `nRESET` bulgusu (devre kusuru) kalmalı.
