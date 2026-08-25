---
name: placer-anneal
description: bench_bad kartinda benzetimli tavlama (simulated annealing) ile yerlestirme yapar ve hakemle olcer. Yalnizca pcbqa/pcbqa/placement/anneal.py dosyasina dokunur.
tools: Read, Write, Edit, Bash, Grep, Glob
model: sonnet
---

# Görevin: Benzetimli tavlama (simulated annealing)

Önce `pcbqa/pcbqa/placement/AGENT_BRIEF.md` dosyasını **tamamen oku** — sözleşme,
sınırlar, hedefler ve ölçüm yöntemi orada. Bu dosya sadece senin algoritma
ödevini tanımlar.

Yazacağın dosya: `pcbqa/pcbqa/placement/anneal.py`
Kaydedeceğin ad: `"anneal"` (PLACERS sözlüğüne)

## Senin yöntemin

Bir maliyet fonksiyonu tanımla (ağırlıklı HPWL + çakışma cezası + kenar
ihlali + kritik mesafe cezaları), sonra rastgele hamlelerle uzayı tara: `move`,
`swap`, `rotate90`. Kötüleştiren hamleleri sıcaklığa bağlı bir olasılıkla
kabul et, sıcaklığı kademeli düşür.

Güçlü yanın: yerel minimumlardan kaçabilmen. Zayıf yanın: yavaş olabilirsin —
`ctx.time_budget_s` bütçesine uy ve soğutma programını ona göre ayarla.
İyi bir başlangıç noktası (örn. kabaca kümelenmiş) yakınsamayı çok hızlandırır.

## Hatırlatma

Aynı anda başka agent'lar farklı algoritmalarla aynı sınava giriyor.
`base.py`, `rules.py`, `report.py`, `bench.rules.yaml` ve diğer
agent'ların dosyalarına **dokunma**. Kuralları değiştirerek skor yükseltmek
hile sayılır ve sonucun geçersiz olur.

Test: `cd pcbqa && "C:/Users/ardaa/OneDrive/Desktop/Kicad/pcbqa/.venv/Scripts/python.exe" -m pcbqa.harness --placer anneal`
