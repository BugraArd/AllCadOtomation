# Yol haritası: ağırlıklı skorlama (Evre 1)

> **Amaç:** Skoru "kaç hata var" olmaktan çıkarıp "ne kadar önemli hatalar var"
> haline getirmek. Bu, hem denetimin doğruluğu hem de ileride üretken tasarımın
> uygunluk fonksiyonu için ön koşul — yargılayamadığımız şeyi üretemeyiz.

## Neden bu iş

Bugünkü skor `report.py`'da tek satır:

```python
PENALTY = {"error": 8.0, "warning": 2.0, "info": 0.0}
penalty = sum(PENALTY.get(f.severity, 0.0) for f in self.findings)
score   = 100 * exp(-penalty / max(component_count, 20))
```

**Yalnızca `severity` sayılıyor.** Sonuçları:

| Bulgu | Bugünkü ağırlık | Olması gereken |
|---|---|---|
| Sıcak döngü 18 mm² (TI AN-2155: EMI marjı −1.6 dB, **ölçülmüş**) | 8 | yüksek |
| Eksik I2C pull-up (bus çalışmaz) | 8 | yüksek |
| Decoupling 6.35 mm yerine 6.6 mm | 8 | düşük |
| Kristal regülatörden 15 mm uzak (**mühendislik seçimi**, kaynaksız) | 8 | çok düşük |

İkinci sorun: ceza **ikili**. 0.01 mm dar bir iz ile 2 mm dar bir iz aynı 8 puanı
yiyor. Oysa bulgular `measured` ve `limit` alanlarını zaten taşıyor.

## Ölçülen zemin (2026-08-28)

11 kural tipinden **9'u** `measured`/`limit` dolduruyor:

| Kural | measured var mı | Ceza ölçeklenebilir mi |
|---|---|---|
| `proximity` | ✅ | ✅ |
| `net_length` | ✅ | ✅ |
| `length_match` | ✅ | ✅ |
| `keep_apart` | ✅ | ✅ |
| `courtyard_overlap` | ✅ | ✅ |
| `edge_clearance` | ✅ | ✅ |
| `trace_width` | ✅ | ✅ |
| `via_current` | ✅ | ✅ |
| `clearance_voltage` | ✅ | ✅ |
| `require_on_net` | ❌ | ❌ — ikili (var/yok) |
| `same_net` | ❌ | ❌ — ikili |

Doldurmayan ikisi zaten doğası gereği ikili; orantılı ceza onlara **uygulanmaz**,
sabit ağırlık alırlar. Yani veri modeli bu işe hazır.

---

## Faz 1a — Ağırlık mekanizması (geriye uyumlu)

**Ne:** Her kural kendi ağırlığını taşısın.

```yaml
- id: sicak-dongu-alani
  type: keep_apart
  severity: error
  weight: 24.0        # yeni; verilmezse severity'den türetilir
```

**Nasıl:**

1. `rules.py` — `Rule` sınıfına `weight: float | None`; `load_rules` bunu
   `spec`ten değil doğrudan üst düzey alandan okusun (`id`/`type`/`severity`
   ile aynı seviyede; `spec`e sızmaması için ayrıştırma listesine eklenmeli).
2. `Finding` sınıfına `weight: float = 0.0`. **`run_rules` merkezî olarak
   doldursun** — `rule_type` için zaten yapılan şey bu; tek tek kontroller
   uğraşmasın.
3. `report.py` — `PENALTY[severity]` yerine `f.weight` kullansın.
4. Geriye uyum: `weight` verilmemişse `PENALTY[severity]` (8/2/0).
   `max_findings` sınırından doğan sentetik "…ve N benzer bulgu daha" bulgusu
   `info` olduğu için 0 ağırlık alır — davranış değişmez.

**Kabul ölçütü:**
- Mevcut **279 test değişmeden geçmeli** (hiçbir kural dosyasında `weight` yok).
- `weight: 16` verilen bir kuralın tek bulgusu, `severity: error` varsayılanının
  iki katı ceza üretmeli.
- `weight: 0` verilen kural skoru hiç etkilememeli (raporda yine görünmeli).

**Dokunulacak dosyalar:** `pcbqa/rules.py`, `pcbqa/report.py`,
`tests/test_score_weights.py` (yeni).

**Risk:** Düşük. Varsayılan yol birebir eski davranış.

---

## Faz 1b — Orantılı ceza (ihlal büyüklüğüne göre)

**Ne:** İhlalin *ne kadar* büyük olduğu cezaya yansısın.

```yaml
- id: guc-izi-genisligi
  type: trace_width
  weight: 12.0
  scale: true         # yeni; varsayılan false
  scale_max: 3.0      # tavan çarpan
```

**Nasıl:**

```
asim  = |measured - limit| / limit          # bulgu zaten ikisini de taşıyor
carpan = clamp(1.0 + asim, 1.0, scale_max)
ceza   = weight * carpan
```

**Tasarım kararları ve gerekçeleri:**

- **Yön yok, mutlak değer var.** Bazı kurallarda ihlal `measured > limit`
  (net uzunluğu), bazılarında `measured < limit` (iz genişliği). `|fark|/limit`
  ikisini de doğru ölçer.
- **`limit == 0` koruması** — `courtyard_overlap`'te `clearance_mm: 0.0`
  yaygın. O durumda ölçekleme atlanır, sabit ağırlık kullanılır.
- **Tavan şart.** `via_current`'ta kapasite 0'a yakınsa oran patlar; tek bulgu
  bütün skoru yutar. `scale_max` varsayılanı **3.0**.
- **Opt-in.** Varsayılan `false`, çünkü bu skor manzarasını değiştirir.

**Kabul ölçütü:**
- 0.01 mm ihlal, 2 mm ihlalden **belirgin biçimde az** ceza almalı.
- `scale: true` verilmeyen kurallarda skor birebir aynı kalmalı.
- `measured`/`limit` taşımayan bulgularda (`require_on_net`, `same_net`)
  `scale: true` verilse bile sabit ağırlık uygulanmalı — hata değil, sessiz
  geri düşüş.

**Dokunulacak dosyalar:** `pcbqa/report.py`, `pcbqa/rules.py` (spec doğrulama),
`tests/test_score_weights.py`.

**⚠ İki gerçek risk — bunlar atlanırsa iş yarım kalır:**

1. **Yerleştirici bu skoru optimize ediyor.** Skor manzarası değişince `auto`
   farklı davranabilir. `python -m pcbqa.harness --all --suite <klasör>`
   koşumu zaten "GERİLEME" işaretliyor — **değişiklikten önce ve sonra
   çalıştırılıp karşılaştırılmalı.**
2. **ML eğitim verisi skora bağlı.** `ml/collect.py` örnekleri
   `d_score = after.score - current.score` ile etiketliyor. Skor değişirse
   `.work/moves*.jsonl` içindeki 49.699 örnek **bayatlar**. Yeniden toplanması
   gerekir; bu bir kayıp değil ama planlanmalı.

---

## Faz 1c — Kaynaklı ağırlıklar

**Ne:** `presets/` altındaki 28 kurala gerçek ağırlık ver.

**İlke — kanıt gücü ağırlığı belirler:**

| Kanıt sınıfı | Örnek | Ağırlık bandı |
|---|---|---|
| **Ölçülmüş etki** | TI AN-2155 sıcak döngü (6/12/18 mm² → EMI marjı) | yüksek (16–24) |
| **Standart / sayısal app-note** | IPC-2221B Tablo 6-1, ROHM 66AN015E'nin mm'leri | orta-yüksek (8–16) |
| **Kaynaklı ama nitel** | "as close as possible" tavsiyesinin sayılaştırılması | orta (4–8) |
| **Mühendislik seçimi** | `hs-kristal-regulatorden-uzak` 15 mm | düşük (1–2) |
| **Güvenlik** | `clearance_voltage` şebeke gerilimlerinde | en yüksek |

**Kabul ölçütü:** Her `weight` satırının yanında **kaynağı yazılı**. Kaynaksız
ağırlık yok — dokümanlardaki "uydurma sayı yazılmaz" kuralı burada da geçerli.

**Dokunulacak dosyalar:** `pcbqa/presets/*.yaml`,
`docs/tasarim-kurallari/README.md` (ağırlık tablosu eklenir).

---

## Faz 1d — Korpus kalibrasyonu

**Ne:** Skorun gerçek kartlarda mantıklı davrandığını sınamak.

> Sahaya çıkmış, profesyonelce üretilmiş bir karta skorumuz 40 veriyorsa,
> **yanlış olan kart değil skorumuzdur.**

**Nasıl:**

1. `harness.py`'a *yerleştirme yapmadan yalnızca skorlayan* bir kip
   (`--score-only`). `discover_boards()` ve `run_suite()` iskeleti zaten var.
2. Rapor: skor dağılımı (histogram/çeyreklikler) + **kural bazlı ateşleme
   oranı**.
3. Yorum kuralı: bir kural gerçek kartların **çoğunda** ateşleniyorsa o kural
   ya da eşiği yanlıştır.

**Kabul ölçütü:** En az 10 gerçek kart üzerinde rapor üretilebilmeli;
`uretim.rules.yaml` (üretilebilirlik) ön ayarının medyan skoru **yüksek**
çıkmalı — bu ön ayar devre tipinden bağımsız ve sağlam kartta sıfır bulgu
üretmesi zaten testle korunuyor.

**Referans nokta (ölçüldü):** KiCad'in `pic_programmer` demosu, kendi kural
dosyasıyla **82.7** (1 hata, 2 uyarı). Kalibrasyonun çapası bu tür kartlar.

**Lisans notu:** Korpus büyütülürken her kartın lisansı kaydedilmeli. Proje
lisans konusunda net bir duruş aldı (HANDOFF §1); korpus bunu bozmamalı.

---

## Sıra ve bağımlılıklar

```
1a (mekanizma)  ->  1b (orantılı ceza)  ->  1c (kaynaklı ağırlıklar)
                                                      |
                                                      v
                                            1d (korpus kalibrasyonu)
```

1a bittiğinde sistem kullanılabilir durumdadır; 1b ve 1c artımlıdır.
1d, 1c'nin doğruluğunu sınadığı için sonda.

**Her fazdan sonra:** `python -m unittest discover -s tests` + kararı beads'e
kaydet (CLAUDE.md'deki karar kaydı kuralı).

---

## Evre 2 için devir promptu

Aşağıdaki metin, ağırlıklı skorlama bittikten sonra **olduğu gibi** yeni bir
oturuma verilebilir.

---

> **Görev: devre doğruluğu kural ailesi (Evre 2)**
>
> Bağlam: `pcbqa` projesinde ağırlıklı skorlama (Evre 1, bkz.
> `docs/yol-haritasi-skorlama.md`) tamamlandı. Sıradaki hedef, kural motorunun
> **geometriyi değil devrenin kendisini** yargılayabilmesi.
>
> **Neden:** Nihai hedef üretken tasarım — sistemin kendi bileşenini ekleyip
> bağlayıp PCB üretmesi. Üretim zincirinin mekaniği zaten var (`sch_add.py`
> sembol ekler, `sch_wire.py` bağlar, `pcb_sync.py` karta yansıtır, `auto`
> yerleştirir). Eksik olan **karar**: hangi bileşen, hangi değer, neden.
> Skor bunun uygunluk fonksiyonudur — yargılayamadığımızı üretemeyiz.
>
> **Boşluk:** Mevcut 11 kural tipi geometri (`proximity`, `keep_apart`,
> `net_length`...), bakır (`trace_width`, `via_current`, `clearance_voltage`)
> ve kısmen topoloji (`require_on_net`, `same_net`) yargılıyor. Hiçbiri
> **bileşen değerini hesaplamıyor.** `Selector.value` yalnızca eşleştirme yapar;
> "bu pull-up 4k7, 400 pF bus için doğru mu?" sorusunu soramaz.
>
> **Yapılacak:** `pcbqa/circuit.py` adında yeni bir hesap modülü — `ipc2221.py`
> ile birebir aynı deseni izle (saf fonksiyonlar, KiCad bilmez, her sabitin
> yanında kaynağı, testler beklenen değerleri dokümandan alır).
>
> Kaynaklı ve hesaplanabilir kurallar (hepsi
> `docs/tasarim-kurallari/` altında belgeli):
>
> | Kural | Formül / değer | Kaynak |
> |---|---|---|
> | I2C pull-up | `Rp(max) = tr / (0.8473 × Cb)`, `Rp(min) = (VDD − VOL)/IOL` (IOL = 3 mA), `Cb ≤ 400 pF` | NXP UM10204 (3.8) |
> | I2C bus kapasitansı | cihaz başına ≤ 10 pF; 200–400 pF arası direnç yetmez, akım kaynağı gerekir | NXP UM10204 |
> | Kristal yük kondansatörü | stray C 2–5 pF, C0 3–7 pF | Microchip AN826 (3.2) |
> | FB bölücü akımı | FB bias akımının ≥ 100 katı | Richtek AN033 (1.4) |
> | Decoupling adedi | her 2 güç topu için 1 × 0.1 µF; her ~10 güç topu için 1 × bulk ≥ 15 µF | TI SPRABV2 (3.1) |
> | Termal bakır alanı | SOT-223 ölçülmüş θJA eğrisi: 16 mm² → 135 °C/W, 100 mm² → 107, 2500 mm² → 50 | Richtek AN044 (4.2) |
> | Via akımı | zaten `ipc2221.via_current_a` içinde | TI SLVA959B |
>
> **Yeni kural tipi:** `component_value` — bir seçiciyle bileşen bulur, değerini
> ayrıştırır (`4k7`, `100n`, `22p`, `10uF` biçimleri) ve hesaplanan aralıkla
> karşılaştırır. Değer ayrıştırıcı ayrı ve test edilebilir olmalı; KiCad değer
> alanları düzensizdir (`4k7`, `4.7k`, `4700`, `4K7 1%`).
>
> **Kabul ölçütleri:**
> - Sağlam gerçek kartta (`samples/pic_programmer`) yanlış alarm **yok** —
>   bu projenin en önemli test ölçütü sessizliktir.
> - Her eşiğin kaynağı kod yorumunda yazılı; kaynaksız olan "mühendislik
>   seçimi" diye etiketli.
> - Değer ayrıştırıcı en az şu biçimleri geçmeli: `4k7`, `4.7k`, `4700`,
>   `100n`, `0.1uF`, `22p`, `10uF`, `1R0`, boş/`DNP`.
> - Faz 1c'deki kanıt sınıfı tablosuna göre ağırlık atanmalı.
>
> **Dikkat — bu kuralların çoğu ek bilgi ister** ve tasarım dosyasında yoktur:
> bus kapasitansı, besleme gerilimi, FB bias akımı, güç dissipasyonu. Bunlar
> kural YAML'ında **beyan edilmeli** (`clearance_voltage`'ın `voltages:`
> alanındaki desen gibi). Beyan yoksa kural **sessizce atlanmalı**, varsayılan
> uydurulmamalı.
>
> Başlamadan `bd prime` çalıştır ve `docs/tasarim-kurallari/` altındaki ilgili
> bölümleri oku. Bitince kararı beads'e kaydet.

---

## Kayıtlar

- Beads: Evre 1 fazları ve Evre 2 devir promptu bead olarak kayıtlı.
- Serena hafızası: `scoring_roadmap`.
