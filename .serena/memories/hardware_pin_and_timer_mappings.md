# Donanım pin ve zamanlayıcı eşlemeleri

## Bu proje için GEÇERSİZ — uydurulmadı

Bu depoda **mikrodenetleyici pin eşlemesi, timer/PWM yapılandırması veya
periferik ataması yoktur.** Doğrulama (2026-08-27):

- C/C++/başlık dosyası sayısı: **0**
- `.ioc` (STM32CubeMX), `.ld` (linker script), `CMakeLists.txt`, `Makefile`: **yok**
- `compile_commands.json`: yok ve **gerekmiyor** (derlenen kaynak yok)
- Proje %100 Python (107 `.py`)

Bu bir **gömülü firmware projesi değil**, KiCad dosyalarını okuyup analiz eden
bir **masaüstü otomasyon aracı**. "Pin" kavramı burada çalışan bir çipin
bacağını değil, KiCad şematiğindeki bir sembol pinini / karttaki bir pad'i
ifade eder.

## Bunun yerine geçerli olan donanım kavramları

Araç aşağıdaki donanım verisini **okur** (üretmez):

| Kavram | Nerede | Anlamı |
|---|---|---|
| `PinRef` | `model.py` | Şematik pini: `ref`, `pin`, `function` (pin adı), `pintype` (power_in, output, passive...), `net`, çözülmüş `x/y` |
| `Pad` | `pcb.py` | Kart üzerindeki bakır pad: mutlak `x/y`, `size_x/size_y`, `angle`, `shape` (circle/oval/rect/roundrect) |
| `Track` / `Via` | `pcb.py` | Yönlendirilmiş bakır: genişlik, katman, uçlar / delik+pad çapı |

Pin konumu dönüşümü şematik tarafında **deneysel olarak doğrulanmıştır**
(README "Pin konumu: deneysel olarak doğrulanmış dönüşüm"); KiCad'in Y ekseni
aşağı dogru olduğu için `_rotate()` KiCad kaynağındaki `RotatePoint` ile aynı
konvansiyonu kullanır.

## Zamanlayıcı yerine: elektriksel eşik tabloları

Projede "timer" yoktur; sayısal donanım sabitleri `pcbqa/ipc2221.py` içindedir
ve hepsi standarda dayalıdır:

- IPC-2221B iz genişliği: `k = 0.048` (dış katman) / `0.024` (iç katman)
- IPC-2221B Tablo 6-1 gerilim açıklıkları (B1-B4, A5-A7 sınıfları)
- TI SLVA959B via akım tablosu (0.15 mm -> 0.20 A ... 0.41 mm -> 1.10 A)
- Şebeke creepage: temel 2.5 mm / takviyeli 5.0 mm (IEC 62368-1, PD2, Grup IIIa)

Kaynakları `docs/tasarim-kurallari/` altında, her sayının yanında yazılı.

## Bu hafıza ne zaman güncellenmeli

Depoya gerçek firmware (C/C++, .ioc, linker script) eklenirse bu dosya
tamamen yeniden yazılmalıdır. O zamana kadar içeriği "geçersiz" olarak
kalmalıdır — boş bir pin tablosu uydurmak yanlış bilgi olur.

İlgili: [[project_overview]], [[critical_technical_decisions]]
