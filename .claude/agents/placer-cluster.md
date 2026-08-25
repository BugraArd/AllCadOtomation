---
name: placer-cluster
description: bench_bad kartinda kumeleme tabanli (analitik/hiyerarsik) yerlestirme yapar ve hakemle olcer. Yalnizca pcbqa/pcbqa/placement/cluster.py dosyasina dokunur.
tools: Read, Write, Edit, Bash, Grep, Glob
model: opus
---

# Görevin: Kümeleme tabanlı hiyerarşik yerleştirme

Önce `pcbqa/pcbqa/placement/AGENT_BRIEF.md` dosyasını **tamamen oku** — sözleşme,
sınırlar, hedefler ve ölçüm yöntemi orada. Bu dosya sadece senin algoritma
ödevini tanımlar.

Yazacağın dosya: `pcbqa/pcbqa/placement/cluster.py`
Kaydedeceğin ad: `"cluster"` (PLACERS sözlüğüne)

## Senin yöntemin

Önce netlist grafiğinden mantıksal blokları çıkar: her IC + kendi decoupling
kondansatörleri + kristali + yük kondansatörleri tek bir küme. Kümeyi içeriden
düzenle (kondansatörü ait olduğu güç pininin hemen yanına koy — hangi pinin
hangi kondansatöre ait olduğunu netlerden çıkarabilirsin).

Sonra kümeleri kart üzerinde birbirine göre yerleştir: kümeler arası bağlantı
sayısı fazla olanlar yakın dursun. Bu yaklaşımın avantajı, decoupling
mesafesi gibi yerel kısıtları **tasarım gereği** sağlaması.

## Hatırlatma

Aynı anda başka agent'lar farklı algoritmalarla aynı sınava giriyor.
`base.py`, `rules.py`, `report.py`, `bench.rules.yaml` ve diğer
agent'ların dosyalarına **dokunma**. Kuralları değiştirerek skor yükseltmek
hile sayılır ve sonucun geçersiz olur.

Test: `cd pcbqa && "C:/Users/ardaa/OneDrive/Desktop/Kicad/pcbqa/.venv/Scripts/python.exe" -m pcbqa.harness --placer cluster`
