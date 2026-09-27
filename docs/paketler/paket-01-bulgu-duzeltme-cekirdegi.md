# Paket 01 — Bulgu / Düzeltme / Doğrulama Çekirdeği

**Durum:** UYGULANDI — KABUL TESTİ BEKLİYOR
**Kapsam değişikliği:** 2026-09-27 — onay/önizleme adımı kaldırıldı, bkz. §11
**Tarih:** 2026-09-26
**Hedef:** Mevcut `pcbqa` analiz motorunu, bulduğu tasarım sorunlarını güvenli biçimde düzeltebilen ilk ürün akışına dönüştürmek.

## 1. Ürün kararı

Bu paket “KiCad’in yerine geçen yeni CAD” geliştirmez. İlk ürün vaadi şudur:

> KiCad projesini tara; problemi kanıtıyla açıkla; güvenli bir düzeltme öner; kullanıcı onaylarsa uygula; KiCad ve `pcbqa` ile tekrar doğrula.

Paketin başarı ölçütü yeni bir algoritma eklemek değil, bu döngünün baştan sona güvenilir çalışmasıdır.

## 2. Neden ilk paket bu?

Mevcut projede aşağıdaki parçalar zaten vardır:

- PCB, netlist, ERC ve DRC okuyucuları
- Kural ve preset sistemi
- Yerleşim motoru ve gerileme koruması
- KiCad PCB Editor IPC bağlantısı
- Dry-run, yedek ve tek adımlı undo yaklaşımı
- Türkçe sınırlı doğal dil komut çözümleyicisi

Eksik olan merkezî ürün katmanı şudur:

```text
Finding → Evidence → Fix proposal → Preview → Approval → Apply → Verify
```

Bu katman kurulmadan yeni şablon, ML modeli veya daha fazla doğal dil desteği ürün değerini yeterince artırmaz.

## 3. Kapsam

### 3.1 Bulgu sözleşmesi

Her analiz bulgusu ortak ve sürümlü bir yapıya dönüştürülecek:

```text
Finding
  id
  rule_id
  severity
  title
  message
  source              # pcbqa / erc / drc / netlist
  affected_refs       # U1, C7 vb.
  nets
  evidence            # ölçüm, eşik, kaynak ve dosya konumu
  confidence          # high / medium / low
  auto_fixable        # true / false
```

Kuralların mevcut insan-okur mesajları korunacak; buna ek olarak makine ve arayüz tarafından kullanılabilecek kararlı alanlar eklenecek.

### 3.2 Düzeltme sözleşmesi

```text
FixProposal
  id
  finding_id
  description
  preconditions
  affected_files
  patch_summary
  risk                  # low / medium / high
  verification_plan
```

Düzeltme doğrudan dosyaya yazılmayacak. Önce önizleme üretilecek. Ön koşullar sağlanmıyorsa araç duracak ve gerekçeyi yazacak.

### 3.3 İlk düzeltme sınıfı

İlk sürümde yalnızca güvenilir ve ölçülebilir düzeltmeler ele alınacak:

1. **Decoupling mesafesi:** U1 güç pini ile uygun kondansatör arasındaki mesafe eşiği aşıldığında yerleşim adayı üretme.
2. **Kart kenarı mesafesi:** Kenara fazla yakın bileşen için güvenli içeri taşıma adayı üretme.
3. **Courtyard çakışması:** Çakışan iki parçadan hareket ettirilebilecek olan için öneri üretme.
4. **Bağlanmamış pin / netlist farkı:** İlk sürümde otomatik yazma yok; yalnızca kök neden ve insan onayı gerektiren öneri.

İlk uçtan uca otomatik uygulama için 1. madde referans alınacak. Diğerleri önce öneri veya kontrollü aday olarak kalabilir.

### 3.4 CLI ve arayüz

Mevcut `analiz` komutu korunacak. Yeni akış mevcut komutları çoğaltmak yerine ortak sonuç şemasını kullanacak:

- `analiz`: bulguları üretir ve JSON raporu yazar.
- `duzelt --finding <id>`: belirli bulgu için dry-run düzeltme adayı üretir.
- `duzelt --finding <id> --uygula`: ön koşulları tekrar doğrular, yedek alır, uygular ve tekrar tarar.
- Arayüzde ilk aşamada “Bulgular” listesi, kanıt paneli, önizleme ve “Uygula” onayı bulunur.

Doğal dil bu paketin karar vericisi olmayacak; yalnızca mevcut typed komutlara dönüştürücü olarak kalacak.

## 4. Paket dışında bırakılanlar

Bu sınırlar bilinçli olarak korunur:

- Otomatik routing
- Stabil KiCad 9/10 canlı şematik yazma
- Genel amaçlı LLM ile serbest CAD komutu
- PyTorch/CUDA veya yeni ML modeli
- Gerçek tedarikçi fiyat/stok entegrasyonu
- Farklı MCU ailelerinin toplu desteklenmesi
- STM32G0 üretim şablonunun tamamlanması; bu Paket 02'dir

## 5. Kabul kriterleri

Paket ancak aşağıdakilerin tamamı sağlanırsa tamamlanmış sayılacak:

- Aynı bulgu CLI ve GUI'de aynı `finding_id` ile görünür.
- Her bulgu en az bir ölçülebilir kanıt içerir.
- Dry-run dosyaya yazmaz ve beklenen değişikliği özetler.
- Uygulama öncesi otomatik yedek alınır.
- Uygulama netlisti değiştirmemesi gereken düzeltmelerde netlist değişmezliği ile korunur.
- Uygulama sonrası aynı kural, ERC/DRC ve ilgili doğrulamalar yeniden çalışır.
- Doğrulama başarısızsa değişiklik geri alınır veya açıkça başarısız olarak raporlanır.
- En az bir gerçek PCB üzerinde decoupling düzeltmesi uçtan uca gösterilir.
- Mevcut test paketi kırılmaz; yeni çekirdek için birim ve uçtan uca testler eklenir.
- “Skor 100” ile “üretime hazır” birbirinden ayrılır; routing tamamlanmamış kart açıkça belirtilir.

## 6. Teknik uygulama sırası

1. `Finding` ve `FixProposal` veri modellerini ekle.
2. Mevcut kural çıktısını bu modellere bağla.
3. JSON rapor şemasını sürümle.
4. İlk düzeltme üreticisini ekle.
5. Dry-run ve diff çıktısını ekle.
6. Yedekleme, uygulama ve geri alma akışını bağla.
7. Uygulama sonrası doğrulama kapısını ekle.
8. GUI bulgu listesi ve onay akışını bağla.
9. Gerçek kart kabul testi ve regresyon testi ekle.
10. Dokümantasyonu ve açık iş raporunu güncelle.

## 7. Bilinçli tasarım kararları

- Model hiçbir zaman doğrudan KiCad dosyası yazmaz.
- Her düzeltme ön koşul, risk ve doğrulama planı taşır.
- Kanıtı olmayan otomatik düzeltme yapılmaz.
- Kullanıcı onayı olmadan mevcut tasarım değiştirilmez.
- Kural skoru sıralama içindir; üretim onayı yerine geçmez.
- KiCad proje dosyası kaynak gerçeklik olarak kalır.

## 8. Paket sonunda gösterilecek demo

Bir STM32 tabanlı PCB açılacak ve şu akış gösterilecek:

1. Analiz sonucu en az bir gerçek decoupling mesafe bulgusu.
2. Bulgunun pin, net, mesafe ve eşik kanıtı.
3. Önerilen yeni konumun dry-run önizlemesi.
4. Kullanıcı onayı.
5. KiCad'e uygulanmış tek undo adımı.
6. Yeniden analizde bulgunun kapanması.
7. ERC/DRC ve netlist paritesinin korunması.

Bu demo çalışmıyorsa paket tamamlanmış sayılmayacak.

## 9. Uygulama durumu

Paketin çekirdek akışı uygulanmıştır: `Finding` kanıt sözleşmesi, kararlı
kimlik, decoupling düzeltme önerisi, dry-run, yedekli uygulama, netlist parite
kontrolü, tekrar tarama ve GUI'deki `Duzelt` sekmesi hazırdır.

Örnek `bench_bad.kicad_pcb` üzerinde uçtan uca uygulama gösterilmiştir. Ancak
STM32G0 tabanlı gerçek kullanıcı kartında kabul testi ve yönlendirilmiş kart
uygulama akışı henüz açık iştir. Bu nedenle paket kod olarak uygulanmış,
ürün kabulü ise kontrollü biçimde açık bırakılmıştır.

## 10. Onay kararı

İşleme başlamadan önce aşağıdaki üç karardan biri seçilmeli:

- **ONAY:** Kapsam aynen uygulanır.
- **ONAY + DEĞİŞİKLİK:** Kapsama yazılacak değişiklikler belirtilir.
- **RED / YENİ PAKET:** Gerekçe yazılır; kodlama başlamaz.

## 11. Kapsam değişikliği — 2026-09-27: önizleme adımı kaldırıldı

Kullanıcı talimatıyla, paketin **iki adımlı onay akışı kaldırıldı**. Yazma
yolları artık tek adımlıdır: plan üretilir, ekrana yazılır ve aynı koşumda
uygulanır.

Kaldırılan dört katman:

1. `duzelt.py` CLI'sindeki `--uygula` bayrağı ve dry-run varsayılanı
2. Arayüzdeki "Anla (kuru koşum)" düğmesi ve `kuru_imza` silahlanma kapısı
3. `Duzelt` sekmesindeki "Öneriyi önizle" adımı
4. Canlı PCB ve canlı şematik `prepare` önizlemeleri

**Gerekçe:** önizleme kapısının koruduğu şey plan bayatlamasıydı — ekranda
görülen planın yazılandan farklı olması. Plan ile yazma artık aynı iş
parçacığında zincirlendiği için bu fark yapısal olarak oluşamaz; imza
karşılaştırması korumadığı bir şeyi korumaya çalışıyordu.

**Korunanlar (kullanıcı kararı):** güvenlik önizlemeden değil yazma
kapılarından gelir ve hepsi yerinde durur — otomatik yedek, KiCad açıkken
yazma reddi, kalkan (mevcut devre değişmedi mi), netlist paritesi ve başarısız
doğrulamada yedekten geri alma. Bakır/via/zone bulunan yönlendirilmiş kartta
otomatik yerleşim yazması hâlâ reddedilir.

**İstisna:** canlı *yerleştirme* planı hâlâ iki adımlıdır; yüzlerce bileşeni
tek tıkla oynatmak geri alınabilir olsa da okunamaz.

**Bu değişiklikle geçersizleşen maddeler:** §3.2'deki "önce önizleme
üretilecek", §3.4'teki `--uygula` ayrımı ve "Uygula onayı", §5'teki "dry-run
dosyaya yazmaz" kriteri, §7'deki "kullanıcı onayı olmadan mevcut tasarım
değiştirilmez", §8'deki 3. ve 4. demo adımları. §5'in geri kalanı — yedek,
netlist değişmezliği, uygulama sonrası doğrulama, başarısızsa geri alma —
yürürlüktedir.

**Doğrulama:** 930 test, 0 hata (`unittest discover -s tests`). `test_arayuz.py`
artık kilidi değil yazma kapılarını sınar: anlaşılmayan cümle dosyaya dokunmaz,
eksik girdi iş başlatmaz, `prepare`/`apply` tek koşumda zincirlenir.
