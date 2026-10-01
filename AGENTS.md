# AGENTS.md — yapay zekâ ajanları için TEK proje dosyası

> Bu dosya, ajanların okuması gereken **kuralları, yapıyı ve hafıza özetini**
> tek yerde toplar (kullanıcı talimatı, 2026-10-01). Codex bu dosyayı doğrudan
> okur; Claude Code `CLAUDE.md` içindeki `@AGENTS.md` satırıyla içe aktarır.
> Başka bir ajan talimat dosyası açmayın — ekleme buraya yapılır.
>
> Kalıcı kayıtların **kanonik kaynağı Beads'tir** (`bd`). Bölüm 8'deki hafıza
> özeti bir dizindir: ayrıntı ve güncel metin `bd recall <anahtar>` ile okunur.
> Özet ile Beads çelişirse Beads doğrudur; özeti düzeltin.

---

## 0. Oturum açılışı (her oturumda)

```bat
bd prime                                   :: Beads bağlamı + kalıcı hafızalar
graphify explain "DevreGrafi"              :: graphify çalışıyor mu (yerel, jeton yok)
cd pcbqa && .venv\Scripts\python.exe -m pcbqa.app tani   :: ortam denetimi
```

SessionStart kancaları (`.claude/settings.json`) bunun bir kısmını kendisi
yapar: `bd prime`, `graphify-durum.py` (düğüm/kenar/yaş), `graphify-etiketle.py`
(topluluk adlarını geri uygular). Kancalar **hatırlatır, engellemez**.

---

## 1. Çalışma kuralları

### 1.1 Graphify + Beads anlaşması (kullanıcı talimatı, 2026-08-31 / 2026-09-07)

- **Serena kullanılmaz.** Proje hafızası Beads, sorgulanabilir katman
  graphify'dır. Serena MCP'yi kurmayın, önermeyin.
- **Kod sorusundan önce grafiğe sor:** `graphify explain "<kavram>"` (en
  isabetli), `graphify path "<A>" "<B>"`, `graphify query "<soru>" --budget N`.
  Bulgular gerekiyorsa kaynak koduyla doğrulanır.
- **Üç zorunlu tetik** — her biri önce Beads'e yazılır:
  1. her yeni **karar** (mimari, eşik, bağımlılık, arayüz, ürün şekli)
  2. her **hata düzeltmesi** (kök sebep + başarısız denemeler + doğrulama)
  3. her **gelecek planı** (evre, yol haritası, sıradaki iş)
- **Akış tek yönlüdür:**
  ```
  bd create / bd remember                 -> Beads (kanonik)
  python .claude/graphify-bilgilendir.py   -> beads -> docs/hafiza/*.md
                                              graphify update .  (AST, yerel)
                                              graphify-etiketle.py
  ```
  `docs/hafiza/` **üretilmiş çıktıdır, elle düzenlenmez.**
- **Sınır, dürüstçe:** aktarım betiği metni aranabilir yapar ama **kavram
  düğümü ve gerekçe kenarı üretmez**; onlar anlamsal tarama ister
  (`/graphify --update`, alt-ajan, kullanıcı onayı). "Grafik güncellendi"
  derken bu ayrımı söyleyin.
- Windows'ta `bd` bir npm shim'idir. Çok satırlı metin için `bd.cmd` ilk
  satırı keser; doğrudan `%APPDATA%\npm\node_modules\@beads\bd\bin\bd.exe` ya da
  `--body-file` kullanın.

### 1.2 Karar kayıtları

Var olan bir geçici çözüm, mimari, pin eşlemesi, bağımlılık sürümü, zamanlama
değeri ya da hata düzeltmesi değiştirilmeden önce `bd prime` çalıştırılır ve
ilgili Beads kayıtları okunur. Her anlamlı düzeltme/davranış değişikliğinden
sonra şunlar kaydedilir: sorun, karar, gerekçe, etkilenen dosya ve semboller,
başarısız yaklaşımlar, doğrulama/test sonucu, ilgili commit SHA'sı, kararın
geri alınabileceği koşullar. **Kayıtlı bir karar sessizce geri alınmaz**;
çelişki açıklanır ve kullanıcı onayı alınır.

### 1.3 Git politikası (muhafazakâr profil)

Commit, push ve Dolt uzak senkronu **yalnızca kullanıcı açıkça isterse**.
Devirde: değişen dosyalar, doğrulama ve önerilen komutlar raporlanır.

### 1.4 Kod kuralları

- **Kod ve YAML ASCII'dir**; belgeler (`.md`) tam Türkçe. Kod içi yorumlar
  Türkçe ama ASCII harflerle (`aciklik`, `genislik`).
- Yorumlar **nedeni** anlatır. Ölçülmüş sayı varsa yorumda geçer.
- Eşiklerin **kaynağı yazılır**; kaynaksız olanlar "mühendislik seçimi" diye
  etiketlenir. **Uydurma sayı yazılmaz**; bilinmeyen değer EKSİK kalır ve
  nedeni kaydedilir (bkz. `pcbqa/devre/bilgi.py`).
- Sentetik veri makinece okunur biçimde işaretlenir (`SENT-`, `MPN_Kaynak`).
- Testler davranıştan çok **sessizliği** korur: sağlam gerçek kartta
  (`samples/pic_programmer`) bakır kuralları sıfır bulgu üretmelidir.
- **Netlist değişmezliği kutsaldır**: yerleştirme bağlantıyı asla değiştirmez.
- **KiCad açıkken dosyaya yazılmaz** (`~*.lck` açık-proje koruması).
- Etkileşimsiz kabuk: `cp -f`, `mv -f`, `rm -rf`; `scp/ssh -o BatchMode=yes`.

---

## 2. Ortam ve sürümler (ölçüldü, 2026-10-01)

| Bileşen | Sürüm / yer |
|---|---|
| KiCad (kararlı) | **10.0.4** — `C:\Program Files\KiCad\10.0\` (`kicad-cli`, `pcbnew` SWIG) |
| KiCad'in Python'u | **3.11.5** — `pcbnew` var, `pyyaml` YOK, `sys.path`'i siler (`sitecustomize.py`) |
| Geliştirme ortamı | **Python 3.13.14** — `pcbqa/.venv` (`pyyaml`, `kicad-python`) |
| kicad-python (kipy) | 0.7.1 (üst düzey sarmalayıcı bozuk; ham `KiCadClient.send` kullanılır) |
| KiCad nightly (canlı şematik) | 10.99.0-3671-gbe90a7e200 — `pcbqa/.runtime/kicad-nightly`, ayrı `.venv-nightly` |
| ngspice | **ngspice-46**, KiCad'in `bin\ngspice.dll`'i (konsol programı KiCad'le gelmez) |
| graphify | 0.9.53 (`uv tool install graphifyy`) |
| Beads | `bd` (npm), Dolt veritabanı `.beads/` |

Çalışma zamanı bağımlılığı **yoktur** (stdlib). YAML kaynaklarının JSON
ikizleri `python -m pcbqa.bundle` ile üretilir; KiCad'in Python'u onları okur.
`pcbqa.bundle --check` ayrışmayı yakalar (bir test her koşuda çağırır).

---

## 3. Python proje yapısı

```
Kicad/                          depo kökü
├─ AGENTS.md                    bu dosya (tek AI dosyası)
├─ CLAUDE.md                    @AGENTS.md içe aktarımı
├─ README.md                    insanlar için genel bakış
├─ .beads/                      Beads (Dolt) - kanonik hafıza ve işler
├─ .claude/                     kancalar: graphify-bilgilendir/durum/etiketle.py,
│                               graphify-etiketler.json, agents/placer-*.md
├─ .agents/skills/beads/        Codex beads becerisi     .codex/ Codex ayarları
├─ graphify-out/                bilgi grafiği (graph.json izlenir, birleştirme sürücüsü var)
├─ docs/                        TÜM BELGELER VE HAFIZA DOSYALARI (tek klasör, Kicad-41r)
│  ├─ HAFIZA-HARITASI.md        tüm hafıza/ayar dosyalarının yeri ve nedeni
│  ├─ HANDOFF.md                tam geliştirme bağlamı
│  ├─ KURULUM.md                son kullanıcı kurulumu
│  ├─ AGENT_BRIEF.md            yerleştirici alt-ajan brifingi
│  ├─ yol-haritasi-skorlama.md, devre-modeli-ve-dogrulama.md
│  ├─ tasarim-kurallari/        eşik kaynakları
│  ├─ hafiza/                   Beads'ten ÜRETİLMİŞ (elle düzenlenmez)
│  └─ paketler/                 paket kararları ve devir raporları
├─ KicadOtomasyon1/, CanliProjeler/   kullanıcının deneme projeleri
└─ pcbqa/                       UYGULAMA
   ├─ pcbqa.cmd, pcbqa-arayuz.cmd, run.cmd, baslat.py   başlatıcılar
   ├─ README.md (ayrıntılı kullanım), requirements.txt
   ├─ samples/                  pic_programmer (sağlam gerçek kart), bench_*.kicad_pcb,
   │                            niyetler/*.yaml, bom/, uc_parca/
   ├─ tests/                    unittest (pytest DEĞİL) - bkz. bölüm 6
   └─ pcbqa/                    paket
      ├─ app.py                 tek giriş noktası (alt komutlar)
      ├─ sexpr, pcb, schematic, netlist, symlib      ayrıştırma
      ├─ model, geom            tasarım modeli (KiCad'i bilmez)
      ├─ rules, ipc2221, circuit, thermal, subcircuit, eseri, presets/   kurallar
      ├─ devre/                 ORTAK DEVRE MODELİ (graf, parça, roller, koşullar)
      ├─ dogrulama/             3 seviyeli doğrulama + 9 kontrol
      ├─ spice/                 ngspice entegrasyonu (netlist, çalıştırıcı, işçi süreç)
      ├─ duzeltme/              ML: elektriksel düzeltme adayı sıralama (bölücü ailesi) + gerçek proje hattı
      ├─ pcb_akim.py            dal akımı + yönlendirme girdisi
      ├─ placement/             yerleştiriciler (auto = üretim)
      ├─ sch_*.py, pcb_sync, connect, propose, komut   şematik/kart yazma
      ├─ intent, generate, explore, templates/   üretken tasarım
      ├─ canli*.py, ipc*.py, swig_apply, kurulum      KiCad'e bağlanma
      ├─ elektrik, mpn, bom, lexicon, arayuz         tablo, BOM, sözlük, GUI
      ├─ confload, minyaml, bundle                   YAML/JSON yükleme
      ├─ data/                  kicad-sozluk.json.gz, parcalar/*.yaml (+json)
      └─ ml/                    veri kümesi, öznitelik, eğitim, devre_veri
```

---

## 4. Özellik haritası — nerede, ne yapar

Komutlar: `pcbqa <komut>` (= `pcbqa.cmd`, KiCad'in Python'uyla) ya da
geliştirmede `.venv\Scripts\python.exe -m pcbqa.app <komut>`.

| Komut | Modül | İşlev |
|---|---|---|
| `tani` | `app.py` | Ortam denetimi: kicad-cli, kütüphaneler, JSON ikizleri, canlı mod |
| `kurulum` | `kurulum.py` | KiCad IPC sunucusunu izinle açar (yedek + atomik yazma + geri al) |
| `analiz` | `__main__.py` | Proje kalitesi: kural motoru + şematik kontroller + ERC/DRC, skor |
| `devre` | `devre/__main__.py` | **Devre grafı**: her parçanın pinleri, rolü, sınırları, PCB karşılığı, eksikleri |
| `dogrula` | `dogrulama/dogrula.py` | **Seviye 1** ERC/DRC/parite/netlist, **2** mühendislik kuralları, **3** ngspice, PCB dal akımı, **9 kontrol**, `--veri` ML satırı |
| `kontrol` | `kontrol.py` | **Tüm kontroller tek koşuda**: kalite skoru (analiz) + seviye 1/2/3 + PCB dal akımı + 9 kontrol. ERC/DRC bir kez koşar; kalite skoru seviye 1'in raporunu kullanır (parite grubu hariç), skor `analiz` ile aynı (pic_programmer 45,2 = 45,2, ölçüldü). Arayüzün Kontrol sekmesi bunu çağırır (Kicad-5d6.11) |
| `duzelt` | `duzelt.py` | Bulgu kanıtı + güvenli düzeltme + tekrar doğrulama |
| `devre-duzelt` | `duzeltme/sirala.py` | Elektriksel sorun → düzeltme adayları → model sırası (yoksa üreteç sırası) → gerçek ngspice/kural/PCB kontrolü → geçerli değişiklik + gerekçe + maliyet; dosyaya yazmaz |
| `duzeltme-proje` | `duzeltme/proje.py` | Adayları temel projenin AYRI kopyalarında gerçek dosyalara yazar → geri okuma → kicad-cli ERC/DRC/parite → kaydedilmiş şematikten ngspice + iz analizi → gecti/kaldi/veri-model-eksik/arac-hatasi; önbellekli kayıt (Kicad-ecd). Seçim: geçenler arasında en düşük maliyet, eşitlikte az yeni ihlal → kararlı kimlik; `goster` var olan deneyi okunur gerekçeyle raporlar (Kicad-d8k) |
| `duzeltme-envanter` | `duzeltme/envanter.py` | Gerçek deney (`deney.jsonl`) ve bellek veri kümesi envanteri AYRI; temel tasarım / koşu / referans / aday sayıları, tekrar ve bozuk kayıt (Kicad-d8k) |
| `arayuz` | `arayuz.py` | tkinter masaüstü arayüzü, 7 sekme (2026-10-02 sadeleştirildi, Kicad-5d6.11): Yap (+dağarcık), Devre (parça tablosu + devre grafı), Kontrol (`kontrol`), Düzelt (bulgu + elektriksel öneri), Deney, Üret (+ardından kontrol), Canlı (+ortam denetimi). Ortak satır: proje + koşullar dosyası |
| `yap` | `komut.py` | Doğal dil komutu → somut ekleme ("10 adet kapasitör ekle") |
| `parcalar` | `elektrik.py` | Parça tablosu: ağ, gerilim, akım (yalnızca türetilebilen), MPN, fiyat |
| `uret` | `generate.py` | Niyet YAML → şablonlar → KiCad projesi → pcb_sync → auto → skor |
| `kesfet` | `explore.py` | Aynı niyetten N varyant; seçim (skor, −hata, −uyarı, −ALAN, −HPWL) |
| `bagla` | `connect.py` | Var olan sembolleri telle birleştirir (`--ag` / `--oner`) |
| `sablonlar` | `intent.py` | Şablon kütüphanesi (`templates/*.yaml`) |
| `sozluk` | `lexicon.py` | İki dilli bileşen sözlüğü |
| `mpn` | `mpn.py` | **SENTETİK** MPN/fiyat alanları (test verisi, `SENT-`) |
| `bom` | `bom.py` | Kaynaklı BOM manifesti, açık kalem kapısı |
| `yerlestir` | `harness.py` | Hakem: yerleştiriciyi koşturur, öncesi/sonrası puanlar |
| `uygula` | `swig_apply.py` | Yerleşimi pcbnew (SWIG) ile uygular — API gerekmez |
| `uygula-ipc` | `ipc_apply.py` | Çalışan KiCad'e IPC ile uygular |
| `canli` / `canli-pcb` | `canli.py`, `canli_pcb.py` | Açık PCB'ye önizleme + tek Ctrl+Z işlemiyle canlı yazma |
| `canli-sematik` | `canli_sematik.py` (+ `_worker`) | Nightly KiCad ile açık şematiğe komut (kararlı 10.0.4'te şematik API yok) |
| `veri` | `ml/collect_design.py` | Niyetlerden eğitim verisi |

Kütüphane katmanları (komutu olmayanlar):

| Modül | İşlev |
|---|---|
| `rules.py` | 16 kural tipi (YAML), `Finding`, skor ağırlıkları; `default_rules.yaml`, `presets/*.rules.yaml` |
| `ipc2221.py` | IPC-2221B iz genişliği/açıklık, FAB_CLASSES, IPC-6012, via akımı (TI SLVA959B) |
| `thermal.py` | θJA eğrileri (SOT-223 Richtek AN044) → Tj |
| `circuit.py`, `eseri.py` | Değer ayrıştırma, I2C pull-up / kristal / FB bölücü hesapları, E-serisi |
| `subcircuit.py` | Topolojiden buck tanıma, sıcak döngü alanı |
| `devre/` | `graf.py` DevreGrafi, `parca.py` ParcaBilgisi + kütüphane, `roller.py`, `kosullar.py`, `bilgi.py` |
| `dogrulama/` | `seviye1.py`, `seviye2.py`, `seviye3.py`, `kontroller.py` (9 kontrol), `sonuc.py`; `seviye3(ek_senaryolar=...)` aileye özgü köşe kancası |
| `duzeltme/` | `bolucu.py` (aile: tanıma, kapalı form EVA, çapraz köşe), `tasarim.py` (kopya üzerinde değişiklik, gerçek footprint takası), `hatalar.py`, `adaylar.py` (üreteç), `degerlendir.py` (gecerli/gecersiz/denetlenemedi), `ozellik.py`, `olcut.py`, `veri.py`, `egitim.py`, `sirala.py`; `proje.py` (gerçek KiCad hattı), `maliyet.py` (değişiklik maliyeti), `tercih.py` (sözlüksel hedef, politikalar), `orneklem.py` (doğal/dengeli örnekleme), `envanter.py` (bellek + gerçek deney envanteri), `paket_deney.py`, `secim.py` (gerçek deneyde aday seçimi), `aciklama.py` (kontrol kodu → okunur gerekçe; CLI/rapor/arayüz ortak), `gorunum.py` (deney kaynağını okur: `goster` + Deney sekmesi) — ayrıntı `docs/duzeltme-siralama.md` |
| `spice/` | `netlist.py` (graf → SPICE), `calistir.py` (arka uç bulma, wrdata), `isci.py` (DLL yan süreç) |
| `pcb_akim.py` | Bakır ağı → Kirchhoff, dal akımı, darboğaz, via, darbe (Onderdonk), dV; `yonlendirme_girdisi` |
| `placement/` | `auto` (üretim), `refine`, `codex`, `force`, `anneal`, `cluster`, `learned`, `repertoire`, `base` (sözleşme) |
| `sch_verify.py` | Netlist değişmezliği kalkanı (her yazmanın bekçisi) |
| `sch_add/wire/move/place/apply/write.py` | Şematiğe sembol ekleme, tel, taşıma, yerleşim, güvenli yazma |
| `pcb_sync.py` | "Update PCB from Schematic" eşdeğeri |
| `confload.py`, `minyaml.py`, `bundle.py` | YAML okuma sırası: .json → pyyaml → minyaml → JSON ikizi |
| `ml/` | `dataset.py` (JSONL, kart bazlı bölme), `features.py`, `train.py`, `devre_veri.py` |

---

## 5. Mimari (katmanlar yalnızca altını bilir)

1. **Ayrıştırma** — `sexpr`, `pcb`, `schematic`, `netlist`, `symlib`
2. **Model** — `model.Design` (sematik + konum), `devre.DevreGrafi` (+ parça
   bilgisi, rol, koşul, PCB karşılığı). **KiCad'i bilmez.**
3. **Kurallar / doğrulama** — `rules`, `dogrulama/`, `spice/`, `pcb_akim`
4. **Yerleştirme** — `placement/` (`auto`)
5. **Yazma** — `sch_*`, `pcb_sync`, `swig_apply`, `ipc_apply`, `canli*`
6. **ML** — `ml/` (model karar vermez; 3d kapısı açık değil)

KiCad'e bağlanma yolları: (1) dosya tabanlı — KiCad kapalıyken; (2) süreç içi
SWIG (`pcbnew`) — ayar gerekmez; (3) IPC — API sunucusu varsayılan kapalı,
`pcbqa kurulum` ile açılır. Canlı PCB düzenleme 10.0.4'te çalışıyor; canlı
şematik yalnızca nightly ile. **Aynı anda tek KiCad örneği açık olsun.**

---

## 6. Test listesi

Çerçeve `unittest` (pytest kurulu değil). Komutlar `pcbqa/` içinden:

```bat
.venv\Scripts\python.exe -m unittest discover -s tests              :: 1135 test, ~9 dk
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_spice.py"   :: tek dosya
```

Son tam koşu: **2026-10-02 — 1135 test, 528,7 s, OK, 0 başarısız, 0 atlanan** (Kicad-5d6.11). Tek dosya çalıştırırken
`discover -p` kullanın; `tests/devre_ornek.py` gibi yardımcılar ancak böyle
içe aktarılır. KiCad/ngspice gerektiren testler, bunlar yoksa atlanır.

| Dosya | Test | Kapsam |
|---|---|---|
| test_app | 24 | giriş noktası, `tani`, başlatıcılar |
| test_arayuz | 32 | tkinter arayüzü: 7 sekme, Kontrol/Devre/elektriksel düzeltme/Üret+kontrol, Deney |
| **test_kontrol** | 12 | `kontrol`: birleşik skor = analiz skoru, bulgu kümesi aynı, ERC/DRC çift sayılmaz, kaynak dosya korunur, seviye 3 gerçek ngspice |
| test_bom | 3 | BOM manifesti |
| test_calibration | 9 | korpus skor kalibrasyonu |
| test_canli / _pcb / _sematik | 6 / 13 / 12 | canlı mod |
| test_circuit | 42 | değer ayrıştırma, I2C/kristal/FB hesapları |
| test_collect_design | 20 | niyet veri toplama |
| test_connect | 19 | `bagla` |
| test_copper / _rules | 6 / 38 | bakır kuralları (pic_programmer sessizliği) |
| test_courtyard | 13 | courtyard çakışması |
| test_decoupling_count | 16 | dekuplaj sayısı |
| **test_devre_graf** | 21 | devre grafı, parça bilgisi, roller, eksikler |
| **test_dogrulama_seviye1** | 3 | ERC/DRC/parite (gerçek kicad-cli) |
| **test_dogrulama_seviye2** | 16 | 5 mühendislik kuralı |
| **test_dokuz_kontrol** | 18 | 9 kontrol |
| test_duzelt | 5 | düzeltme akışı |
| **test_duzeltme** | 29 | düzeltme sıralama: el hesabı, negatif Vout sınırı, sızıntı, ölçütler, bölme, v1 model/kayıt reddi (SAHTE benzetim) |
| **test_duzeltme_tercih** | 16 | maliyet farkı, sözlüksel hedef, politikalar, eşit maliyet, çözümsüz parti, eksik analiz (Kicad-apg) |
| **test_duzeltme_paket** | 15 | Yageo RC_L veri sayfası sınırları, MPN kuralı, paket nedenleri, dengeli örnekleme, çoğaltma yalnız eğitimde (Kicad-7cb) |
| **test_duzeltme_entegrasyon** | 10 | GERÇEK ngspice + KiCad footprint: negatif Vout sınırı, yüksek empedans uyum eşiği, büyük paket yetersiz, aynı tohum aynı kayıt |
| **test_duzeltme_proje** | 10 | GERÇEK kicad-cli ERC/DRC/parite + ngspice: aday gerçek dosyada, bağlantı hatası, bağlanmamış kart, clearance, güç ihlali, araç yok, önbellek (Kicad-ecd); seçim kapsamı/eşitlik/etiket korunumu (Kicad-d8k) |
| **test_duzeltme_secim** | 20 | en ucuz geçen seçimi, eşit maliyet + ek tercih, geçerli yok, eksik maliyet ≠ 0, erken durdurma; okunur gerekçe; gerçek envanter tekrar/bozuk/kaynak türü (Kicad-d8k) |
| test_elektrik | 24 | parça tablosu |
| test_eseri | 21 | E-serisi |
| test_explore / test_generate | 13 / 23 | üretken tasarım |
| test_intent | 31 | niyet şeması |
| test_ipc2221 / test_ipc_apply | 18 / 4 | IPC hesapları, IPC uygulama |
| test_komut | 67 | doğal dil komutu |
| test_kurulum | 27 | kurulum |
| test_lexicon | 20 | sözlük |
| test_minyaml | 21 | PyYAML ile diferansiyel test |
| test_ml / **test_ml_devre_veri** | 37 / 3 | ML |
| test_mpn | 14 | sentetik MPN |
| **test_pcb_akim** | 13 | dal akımı, Kirchhoff, darboğaz, via, darbe |
| test_pcb_sync / test_pcb_versions | 16 / 7 | karta yansıtma, KiCad 5–10 kartları |
| test_placement_keep_apart, test_propose, test_refine, test_repertoire | 2 / 9 / 17 / 13 | yerleştirme |
| test_presets | 15 | kural ön ayarları |
| test_schematic, test_sch_add, _connect, _move, _place | 30 / 37 / 31 / 19 / 18 | şematik okuma/yazma |
| test_score_weights | 35 | skor ağırlıkları |
| **test_spice** | 8 | SPICE netlisti, senaryolar, gerçek ngspice (3) |
| test_stm32g0_template | 3 | STM32G0 profili |
| test_subcircuit | 40 | alt devre tanıma |
| test_swig_bridge | 14 | KiCad Python köprüsü |
| test_symlib_alternates | 9 | sembol kütüphanesi |
| test_thermal | 25 | termal |
| test_zones | 23 | bakır döküm |

---

## 7. Graphify — önemli bilgiler

- Grafik: `graphify-out/graph.json`. Son ölçüm 4809 düğüm, 10556 kenar, 226
  topluluk. Kod AST ile (yerel, bedava), belgeler anlamsal taramayla
  çıkarılır.
- **En çok bağlantılı düğümler** (çekirdek soyutlamalar): `PlacementContext`,
  `read_schematic()`, `load_design()`, `Schematic`, **`DevreGrafi`**,
  `Design`, `Finding`, `load_rules()`, `add_symbols()`, `read_board()`.
- Topluluk adları **çapa düğümüne** bağlıdır, numaraya değil
  (`.claude/graphify-etiketler.json`). Sebep: `graphify update` her koşuda
  yeniden kümeler.
- Tuzak: `graph.json` node-link biçimindedir; kenarlar `links` altındadır.
  `edges` diye okursanız sessizce 0 çıkar.
- Belgelenmiş kavram örneği: `graphify explain pcbqa_handoff_sessiz_hata_sinifi`
  komutu, HANDOFF'un dört bölümündeki altı gerçek hatayı tek kavramda bağlar.
- Kod değişince `graphify update .`. `.gitattributes` içindeki `merge=graphify`
  sürücüsü `graph.json` çakışmalarını birleştirir.

---

## 8. Kalıcı hafıza özeti (kanonik: `bd recall <anahtar>`)

| Anahtar | Özet |
|---|---|
| `calisma-anlasmasi-graphify-entegre` | Bölüm 1.1'deki anlaşma; kural üç yerde (bu dosya, Beads, kancalar) |
| `graphify-kurulumu-ve-hafiza-akisi` | Graphify kurulumu, kancalar, `docs/hafiza` aktarımı, tuzaklar |
| `serena-kaldirildi-graphify-eklendi` | Serena 2026-08-30/31'de kaldırıldı; hafıza kaybı yok (HANDOFF kopyasıydı) |
| `kicad-baglanti-yollari` | Ürün şekli BAĞIMSIZ UYGULAMA = ayrı Python gerektirmez; 3 bağlantı yolu; YAML sırası |
| `kicad-python-sys-path-silme` | KiCad Python'u PYTHONPATH'i yok sayar; betik paketin yanında ya da `sys.path.insert` |
| `canli-mod-ve-sematik-api` / `canli-pcb-duzenleme-calisiyor` | Canlı PCB 10.0.4'te çalışıyor; tek KiCad örneği |
| `sematik-canli-yazma-mumkun-degil` / `canli-sematik-nightly-dogrulandi` | Kararlı sürümde şematik API yok; nightly ile ölçüldü |
| `canli-pcb-arayuzu-ve-dogrulama` | Readback `push_commit` SONRASINDA yapılır |
| `netlistte-gorunmeyeni-netlistte-arama` | `#PWR/#FLG` netlist'te yok; güç için ağ ADINA bakılır |
| `sentetik-veri-isaretlenmeli` | Sessizce gerçekmiş gibi duran veri, hiç veri olmamasından kötüdür |
| `skorlama-yol-haritasi-evre-1-tam-metin-pcbqa` | Skor bir ihlal sayacıdır, kalite ölçeği değil; üretilen kartta doyar |
| `evre-3-uretken-tasarim-fazlama` | 3a–3c bitti; **3d kapısı açık değil** (sıralayıcı yazı-tura); ölçmeden model yazılmaz |
| `st-motor-kontrol-model-eslemesi` | ST motor kartı modeli → pcbqa feature/variant katmanı eksiği |
| `devre-modeli-ve-uc-seviyeli-dogrulama` | Devre grafı, 3 seviye, ngspice DLL yan süreç, dal akımı, 9 kontrol, ML satırı |
| `spice-gelistirilmeli` | **Gelecek planı**: üretici SPICE modelleri, geçici analiz, DC bias (Kicad-5d6.5) |
| `duzeltme-siralama-ilk-deney` | ML ilk deneyi: bölücü ailesinde düzeltme adayı sıralama; kapalı form kuralı %100, fizik görmeyen gbt-ham %92 ilk öneri (üreteç %65); `pcbqa devre-duzelt` (Kicad-u4k) |
| `duzeltme-secim-gerekce-envanter` | Kicad-d8k: gerçek deneyde seçim = geçenler arasında en düşük maliyet (eşitlik: az yeni ihlal → kararlı kimlik); okunur gerekçe katmanı; `duzeltme-envanter` gerçek/bellek ayrı; Deney sekmesi. Gerçek projede seçim aday-02 → aday-03 (eşit maliyet 1), kontrol sonuçları 18/18 aynı |
| `duzeltme-gercek-proje-tercih-paket` | Kicad-ecd/apg/7cb: gerçek proje hattı (17/17 bellekle uyumlu); sözlüksel hedef pişmanlık 2,12 → 0,00 (son test) ama görülmemiş `paket-buyuk`'ta %0; dengeli veri gbt-ham kaçırma 133 → 60; RC_L veri sayfası düzeltmeleri |

**Ölçülmüş olumsuz sonuçlar — tekrar denenmeden önce HANDOFF okunur:**
- Faz A (geniş hamle repertuarı) ve Faz E (tavlama kabulü) kazanç vermedi.
- "Yalnızca skor artışını say" daha kötü çıktı.
- `learned` yerleştiricisi sinyal öğreniyor ama uçtan uca `auto`'yu geçmiyor.
- `keep_apart` cezası zaten skoru besliyor (Kicad-ec5).

Ortak ders: **sınır aramada değil, skorun kendisinde.**

**Yol haritası:** önce skorlama (bitti), sonra üretken tasarım. Hedef önce
STM32, sonra genel CPU. Ayrıntı: `docs/yol-haritasi-skorlama.md`.

---

## 9. Açık işler

`bd ready` ve `bd list --status=open` güncel listeyi verir. Öne çıkanlar:
- Kicad-5d6.5 SPICE geliştirilmeli
- Kicad-5d6.9 parça kaydı teyidi
- Kicad-a27 3d kapısı
- Kicad-4m5 MCU pin planlayıcısı
- Kicad-mdm ERC güç sözleşmesi
- Kicad-s0p düzeltme sıralamayı kapalı formu olmayan aileye taşı (LDO, 5d6.5 sonrası)
- Kicad-515 sözlüksel hedef görülmemiş mekanik hatada zayıf (paket-küçült operatörü)
- Kicad-4zv düzeltme veri kapsamı açıkları (E24/%5, ince film, gerilim örneği)

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:6cd5cc61 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->

<!-- BEGIN BEADS CODEX SETUP: generated by bd setup codex -->
## Beads Issue Tracker

Use Beads (`bd`) for durable task tracking in repositories that include it. Use the `beads` skill at `.agents/skills/beads/SKILL.md` (project install) or `~/.agents/skills/beads/SKILL.md` (global install) for Beads workflow guidance, then use the `bd` CLI for issue operations.

### Quick Reference

```bash
bd ready                # Find available work
bd show <id>            # View issue details
bd update <id> --claim  # Claim work
bd close <id>           # Complete work
bd prime                # Refresh Beads context
```

### Rules

- Use `bd` for all task tracking; do not create markdown TODO lists.
- Run `bd prime` when Beads context is missing or stale. Codex 0.129.0+ can load Beads context automatically through native hooks; use `/hooks` to inspect or toggle them.
- Keep persistent project memory in Beads via `bd remember`; do not create ad hoc memory files.

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.
<!-- END BEADS CODEX SETUP -->

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
