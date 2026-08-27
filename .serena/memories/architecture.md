# Mimari

Katmanlar aşağıdan yukarı; **her katman yalnızca altındakini bilir**.

## 1. Ayrıştırma (KiCad'i bilir, bizim modelimizi bilmez)

| Modül | Sorumluluk |
|---|---|
| `sexpr.py` | Bağımlılıksız s-expression okuyucu/yazıcı. Yığın tabanlı (özyineleme yok). Bozuk dosyalara toleranslı; atlanan parantez sayısını raporlar. `QuotedStr` ile tırnak ayrımını korur — kaybolursa KiCad dosyayı reddeder. |
| `pcb.py` | `.kicad_pcb` okur: `Component`, `Pad`, `Track`, `Via`, `Board`. Courtyard poligonu, pad şekli (circle/oval/rect), bakır izler. |
| `schematic.py` | `.kicad_sch` okur (hiyerarşik). |
| `netlist.py` | Karttan/şematikten net listesi kurar. |
| `symlib.py` | Sembol kütüphanesi okur. |

## 2. Model (KiCad'i BİLMEZ)

`model.py` — `Design`, `PinRef`, `Metrics`. Şematik niyetini PCB fiziğiyle
birleştirir: her netin pinleri, pad konumlarıyla eşleştirilmiş halde.
`geom.py` saf geometri (dışbükey kabuk, poligon çakışma/mesafe, parça mesafesi).

## 3. Kurallar

`rules.py` — YAML ile tanımlı 11 kural tipi, `CHECKS` sözlüğünde kayıtlı:

- Niyet: `proximity`, `require_on_net`, `same_net`
- Sinyal: `net_length` (HPWL), `length_match`
- Yerleşim: `keep_apart` (minimum mesafe — `proximity`'nin tersi)
- Üretim: `courtyard_overlap`, `edge_clearance`
- Bakır: `trace_width`, `via_current`, `clearance_voltage`

`ipc2221.py` — IPC-2221B hesapları (iz genişliği, Tablo 6-1 açıklık), TI via
akım tablosu, λ/40 decoupling. Kural motorunun sayısal çekirdeği.

`load_rules()` `include:` destekler; ön ayarlar `pcbqa/presets/` altında.

## 4. Yerleştirme

`placement/` — `base.py` (bağlam), `auto.py` (üretim yerleştiricisi),
`refine.py` (polish), `anneal.py`, `cluster.py`, `force.py`, `repertoire.py`,
`learned.py`. Hepsi `PlacementContext` üzerinden skor alır.

## 5. Yazma

`ipc_apply.py` (IPC ile karta), `sch_write.py`/`sch_add.py`/`sch_move.py`
(şematiğe), `pcb_sync.py` (şematikten karta yansıtma). Atomik yazma + açık-proje
koruması + netlist değişmezliği kalkanı.

## 6. ML

`ml/` — `collect.py` (veri), `features.py`, `linear.py`/`trees.py`, `train.py`,
`metrics.py`. Model **karar vermez, sıra önerir** (hangi hamle önce denensin).

## Giriş noktaları

`__main__.py` → `python -m pcbqa` (kısayol: `run.cmd`). `harness.py` test/ölçüm
tezgahı, `synth.py` sentetik kart üretici.

## Tasarım kuralı

Bir katman kendi altındakinden fazlasını bilmez; `model.py` KiCad'i bilmediği
için kural motoru ve yerleştirici KiCad sürümünden bağımsızdır.

İlgili: [[project_overview]], [[critical_technical_decisions]]
