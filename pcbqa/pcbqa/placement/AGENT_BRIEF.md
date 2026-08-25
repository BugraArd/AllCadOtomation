# Yerleştirme Agent'ı Brifingi

Bu dosyayı **işe başlamadan önce tamamen oku.** Sana verilen görev, aynı anda
çalışan başka agent'larla **yarışan** bir yerleştirme algoritması yazmak.

## Önce oku

| Dosya | Neden |
|---|---|
| `pcbqa/HANDOFF.md` | Projenin tüm bağlamı, alınan kararlar, bulunmuş tuzaklar |
| `pcbqa/pcbqa/placement/base.py` | **Donmuş arayüz** — uymak zorunda olduğun sözleşme |
| `pcbqa/pcbqa/model.py` | Elindeki veri modeli (`Design`, `PinRef`, `hpwl()`) |
| `pcbqa/README.md` | Aracın genel işleyişi, kural tipleri |

## Görev

`bench_bad.kicad_pcb` kartındaki bileşenleri yeniden yerleştirerek skoru
yükselt. Referans noktaları:

| Kart | Skor | Toplam HPWL |
|---|---|---|
| `bench_bad` (başlangıç) | 1 / 100 | 524 mm |
| `bench_good` (**hedef**) | 67 / 100 | 329 mm |

Hedef 100 değil **67** — `bench_good`'da da 1 hata var (`nRESET` pull-up'ı yok).
O bir **devre** kusuru, yerleşimle düzeltilemez. Peşine düşme.

## Sınırların — bunlar pazarlık dışı

✅ **Sadece şu iki dosyaya dokun:**
- `pcbqa/pcbqa/placement/<senin_adın>.py` — senin algoritman
- `pcbqa/pcbqa/placement/__init__.py` — sadece `PLACERS` sözlüğüne kendi satırını ekle

❌ **Asla dokunma:**
- `pcbqa/pcbqa/placement/base.py` — donmuş arayüz. Değişirse diğer agent'ların çıktısı
  uyumsuz hale gelir ve karşılaştırma imkânsızlaşır.
- `pcbqa/pcbqa/placement/` altındaki **diğer agent'ların dosyaları**
- `pcbqa/pcbqa/rules.py`, `pcbqa/samples/bench.rules.yaml`, `pcbqa/pcbqa/report.py` —
  **kuralları veya skor fonksiyonunu değiştirmek hile sayılır.** Sınavı
  kolaylaştırarak değil, daha iyi yerleştirerek kazan.
- `pcbqa/pcbqa/synth.py`, `pcbqa/samples/bench_*.kicad_pcb` — test kartları sabit

Bu kısıt teknik değil, yöntemsel: üç agent aynı sınava giriyor. Sınavı
değiştiren agent'ın sonucu geçersizdir.

## Arayüz

```python
from pcbqa.placement.base import Placement, PlacementContext

class MyPlacer:
    name = "benim-adim"

    def run(self, ctx: PlacementContext) -> Placement:
        # ref -> (x, y, rotation)
        return {...}
```

`ctx` üzerinden elindekiler:

```python
ctx.movable()                  # taşıyabileceğin referanslar
ctx.locked                     # DOKUNMA (bench_bad'de J1, J2)
ctx.outline()                  # (minx, miny, maxx, maxy) kart sınırı
ctx.seed                       # rastgelelik kullanıyorsan BUNU kullan
ctx.time_budget_s              # yumuşak süre bütçesi (varsayılan 30 sn)

ctx.design.board.components    # x, y, rotation, pads, courtyard_poly, courtyard_local
ctx.design.net_names()
ctx.design.pins_on_net(ad)     # konumu çözülmüş pinler (.x, .y, .ref, .pin, .pintype)
ctx.design.hpwl(ad)            # netin yarı-çevre tel uzunluğu
ctx.design.kind_of(ref)        # 'ic' | 'capacitor' | 'resistor' | 'crystal' | ...
```

Yardımcı geometri (`pcbqa/pcbqa/geom.py`): `overlap(a, b)` (ayırıcı eksen teoremi),
`distance(a, b)`, `convex_hull(pts)`, `area(poly)`.

Bir bileşenin yeni konumdaki courtyard'ını hesaplamak için
`Component.place(x, y, rot)` var — ama `ctx.design`'ı **değiştirme**, kopya al.

## Kendini nasıl ölçersin

Komutlar `pcbqa/` klasöründen çalışır (senin çalışma dizinin repo köküdür):

```bash
cd pcbqa
.venv/Scripts/python -m pcbqa.harness --placer benim-adim
.venv/Scripts/python -m pcbqa.harness --all              # rakiplerle karşılaştır
.venv/Scripts/python -m pcbqa.harness --placer benim-adim --write .work/sonuc.kicad_pcb
```

Hakem hem skoru hem **toplam HPWL**'i gösterir. Skor alt uçta sıkışıktır
(1 → 0 arası dar), bu yüzden geliştirme sırasında **HPWL'e bak**: 524'ten
329'a doğru inmeli. Hata sayısı da (12 → 1) net bir sinyal.

İki alt sınır referansı zaten kayıtlı:
- `identity` → kazanç **+0.0** olmalı (hakemin doğruluk testi)
- `random` → kazanç **negatif** olmalı (skorun duyarlılık testi)

Senin sonucun bu ikisinin belirgin şekilde üstünde olmalı.

## Neyi optimize ediyorsun

Skoru yükselten şeyler, ağırlık sırasına göre:

1. **Decoupling mesafesi** — her IC güç pininin ≤6 mm yakınında kendi
   kondansatörü (`exclusive` eşleme: bir kondansatör bir pine sayılır)
2. **Kristal** — `XIN`/`XOUT` netleri ≤12 mm; yük kondansatörleri kristale ≤6 mm
3. **Courtyard çakışması** — bileşenler arasında ≥0.2 mm boşluk
4. **Kart kenarı** — bileşenler kenardan ≥2 mm içeride (J1/J2 kilitli, muaf)
5. **USB diferansiyel çifti** — `USB_DP`/`USB_DM` uzunluk farkı ≤3 mm
6. **Regülatör kondansatörleri** — U2'ye ≤8 mm
7. **Güç rayı uzunluğu** — `3V3` ≤60 mm

Tam liste: `pcbqa/samples/bench.rules.yaml` (oku, ama **değiştirme**).

## Beklenen çalışma şekli

1. Brifingi ve `base.py`'yi oku
2. Algoritmanı yaz, `PLACERS`'a kaydet
3. Hakemi çalıştır, sonucu gör
4. İyileştir, tekrarla
5. Bitirdiğinde: en iyi skorunu, HPWL'ini, kalan hataları ve algoritmanın
   nasıl çalıştığını **kısa** bir özetle raporla

Deterministik ol: aynı `seed` ile aynı sonucu üret. Hakem karşılaştırmayı buna
göre yapıyor.
