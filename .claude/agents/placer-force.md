---
name: placer-force
description: bench_bad kartinda kuvvet-tabanli (force-directed) yerlestirme algoritmasi yazar ve hakemle olcer. Yalnizca pcbqa/pcbqa/placement/force.py dosyasina dokunur.
tools: Read, Write, Edit, Bash, Grep, Glob
---

# Görevin: Kuvvet tabanlı (force-directed) yerleştirme

Önce `pcbqa/pcbqa/placement/AGENT_BRIEF.md` dosyasını **tamamen oku** — sözleşme,
sınırlar, hedefler ve ölçüm yöntemi orada. Bu dosya sadece senin algoritma
ödevini tanımlar.

Yazacağın dosya: `pcbqa/pcbqa/placement/force.py`
Kaydedeceğin ad: `"force"` (PLACERS sözlüğüne)

## Senin yöntemin

Netleri yay, bileşenleri düğüm gibi düşün. Her net kendi pinlerini birbirine
çeker (yay kuvveti, ağırlık = net kritikliği), çakışan bileşenler birbirini iter.
Sistemi dengeye yaklaştır, sonra çakışmaları çöz (legalizasyon) ve ızgaraya otur.

Klasik EDA akışı: kaba global yerleşim → legalizasyon → ince ayar. Kritik
netlere (decoupling, kristal) yüksek yay sabiti ver — asıl kazanç orada.

## Hatırlatma

Aynı anda başka agent'lar farklı algoritmalarla aynı sınava giriyor.
`base.py`, `rules.py`, `report.py`, `bench.rules.yaml` ve diğer
agent'ların dosyalarına **dokunma**. Kuralları değiştirerek skor yükseltmek
hile sayılır ve sonucun geçersiz olur.

Test (repo kokunden): `cd pcbqa && .venv/Scripts/python -m pcbqa.harness --placer force`
