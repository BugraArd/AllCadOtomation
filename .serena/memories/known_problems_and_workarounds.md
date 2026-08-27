# Bilinen sorunlar ve geçici çözümler

## Ortam

### `pytest` yok — unittest kullanın
`python -m pytest` "No module named pytest" verir. Doğru komut:
`.venv\Scripts\python.exe -m unittest discover -s tests`

### Sistem Python'ı çalışmaz
Bağımlılıklar yalnızca `pcbqa/.venv` içinde. Her zaman
`.venv\Scripts\python.exe` kullanın.

### Uzun heredoc'lar Git Bash'te kesiliyor
Bash aracına çok uzun `<<'EOF'` bloğu verildiğinde komut kesiliyor ve
"unexpected EOF while looking for matching `''" hatası çıkıyor — dosya hiç
yazılmıyor. **Geçici çözüm:** uzun içerik için Write aracını kullanın, ya da
yamayı bir `.py` dosyasına yazıp çalıştırın.

### Serena dil sunucusu `uvx` ister (2026-08-27 giderildi)
Serena'nın Python dil sunucusu (Pyright) `uvx` üzerinden başlar. `uv`/`uvx`
PATH'te yoksa MCP bağlantısı "Connected" görünse bile **sembol araçları
çalışmaz**. Çözüm: `uv.exe` ve `uvx.exe` `C:\Users\ardaa\.local\bin` altına
kopyalandı (bu dizin makine PATH'inde).

## KiCad tarafı

### IPC API bug'ları (HANDOFF §2)
- `update_items()` bazen **sessizce hiçbir şey yapmıyor**.
- IPC üzerinden footprint döndürmek sembol bağlantısını bozuyor
  ([kicad#21655](https://gitlab.com/kicad/code/kicad/-/issues/21655)).

### Bozuk KiCad dosyaları gerçek
KiCad 10.0.4 ile gelen `royalblue54L_feather` demosunda teardrop ayarlarında
açılış parantezi eksik. `sexpr.parse()` bu yüzden **varsayılan olarak
toleranslıdır**; atlanan parantez sayısını `parse_warnings` ile raporlar.
`strict=True` istenirse hata fırlatır.

### KiCad açıkken yazmayın
Açık-proje koruması var (`.lck` dosyası kontrolü). Atlanırsa dosya bozulabilir.

### `unconnected-(U7-Pad1)` adları gerçek ağlardır
"Boş pad'in ağı olmaz" sezgisi yanlıştı; KiCad örnek kartta bu adlardan **77
tane** yazıyor. Elenirse parite "Ped, şematik tarafından verilen ağdan yoksun"
uyarısı veriyor. Netlist ne diyorsa o yazılır.

### `ki_keywords`/`ki_fp_filters` sembol örneğine yazılmamalı
Kütüphane tanımına aittir. Buna karşılık `Description`/`Datasheet` footprint'e
**taşınmalıdır**.

## Kural motoru

### Ölçülemeyen kurallar (sayısal değeri var, veri yok)
`docs/tasarim-kurallari/README.md` ve her ön ayar dosyasının sonunda liste var.
En yüksek getirili eksik: **bakır döküm (zone) okuma** — tek başına sıcak döngü
alanı, SW bakır alanı ve termal bakır alanı kurallarını açar.

### `clearance_voltage` creepage ölçmez
Yalnızca **clearance** (hava aralığı, IPC-2221B Tablo 6-1). Şebeke izolasyonuna
yetmez; 250 V üstünde bulguya uyarı ekler ama yüzey mesafesini hesaplamaz.

### İz genişliği hesabı iç katmanda ~%25 iyimser
Nominal bakır kalınlığı kullanılır. Gerçekte iç katman 1 oz ≈ 25 µm (nominalin
%71'i), dış katman ≈ 48-60 µm (kaplama ekler). İç katman güç izlerinde
`copper_oz` değerini düşürün.

### `keep_apart` bileşen merkezini ölçer
İz güzergâhını değil. "FB izi indüktörden 10 mm uzak" kuralı bu yüzden bir
**yaklaşımdır**.

## Yerleştirme

### `polish` aşamaları hiç bitmiyordu (Faz F ile giderildi)
Yakınsama ölçütü (skor sabrı) eklendi; `_Convergence` kurulu ve testli.

### `auto` yalnızca HPWL küçültür — `keep_apart` kısıtlarını ihlal eder
Araştırmadaki kuralların şaşırtıcı bir kısmı "uzaklaştır" der (FB→indüktör
≥10 mm, pull-up→sensör ≥10 mm). Skor fonksiyonuna `keep_apart` cezası eklemek
bir sonraki adımın ilk adayı. **Bu bilinen ve kabul edilmiş bir boşluktur.**

### `sch_move` "önce" ölçümünü kullanıcının klasöründe alıyor
`sch_add`/`pcb_sync` iki kum havuzu kullanıyor; `sch_move` henüz değil
(HANDOFF §18.5 kilit sorunu).

## Kapsam dışı (eksik değil, bilinçli)

- Otomatik **yönlendirme (routing)** yok — pad'ler doğru ağda ama bakır yol
  çizilmiyor.
- Yansıtma yalnızca **ekler**: şematikten silinen bileşen karttan silinmez,
  footprint değişikliği karta yansımaz.
- Bağlama yalnızca eklenen semboller için (`sch_add --connect`).

İlgili: [[critical_technical_decisions]], [[build_and_test_commands]]
