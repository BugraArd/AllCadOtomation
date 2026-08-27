# Kritik teknik kararlar

Hepsi HANDOFF.md / README.md'de gerekçesiyle birlikte kayıtlı. **Bunları
değiştirmeden önce ilgili bölümü okuyun.**

## 1. Lisans: GPL koduyla asla linklenme (HANDOFF §1)

KiCad kaynağı GPLv3. Seçilen zemin: `kicad-cli` (ayrı süreç) + IPC API /
`kicad-python` (MIT, ayrı süreç). Böylece kendi kodumuz istediğimiz lisansta
olabilir. **Kicad-cli binary'sini kendi kurulum paketimize gömersek GPL
yükümlülüğü doğar** — kullanıcının kendi KiCad'ini çağırmak bunu ortadan
kaldırır. Mimariyi bu belirledi; tekrar araştırmaya gerek yok.

## 2. Şematik için IPC değil, dosya ayrıştırma (HANDOFF §2)

KiCad 10'da IPC API yalnızca PCB editöründe var; şematik KiCad 11'e planlı.
Bu yüzden şematik okuma/yazma `sexpr.py` ile dosya düzeyinde yapılıyor.
KiCad 11 beklenmedi.

## 3. Aşama 0/1'de IPC API değil, dosya okuma (README)

Salt-okunur analiz için IPC gereksiz bir bağımlılık ve çalışan bir KiCad
gerektirir. Dosya okumak hem CI'da hem KiCad kapalıyken çalışır.

## 4. Kural motoru IPC-2221B kullanır, IPC-2152 değil (`ipc2221.py`)

IPC-2152 gerçek ölçümlere dayanır ama **ham tabloları teliflidir ve açık bir
formülü yoktur**. Ayrıca "IPC-2152 hep daha gevşek" yaygın inanışı yanlış:
çıplak temel eğrisi IPC-2221 dış katmanından daha muhafazakârdır (3 A/1 oz/
10 °C: 1.37 mm vs 2.10 mm); gevşeme ancak düzlem yakınlığı gibi çarpanlarla
gelir. Formülü açık olan IPC-2221B seçildi; ΔT ve bakır ağırlığı **parametre**
olarak alınır — tek bir "doğru sayı" iddia edilmez.

## 5. Bakır kuralları yönlendirilmemiş kartta sessizce atlanır

`trace_width` / `via_current` / `clearance_voltage`, `board.tracks` boşsa hiç
bulgu üretmez. Gerekçe: aracın asıl işi yerleştirme ve o aşamada kartta bakır
yoktur; orada bulgu üretmek saf gürültüdür.

## 6. Pad şekli TAM modellenir (2026-08-27, ölçülmüş hata)

Açıklık ölçümünde pad'i önce çevreleyen daireye, sonra kareye yuvarlamak
**sağlam bir kartta hayali ihlal üretti** (sırasıyla 0.5 mm ve 0.03 mm).
TO-92'nin 1.27 mm köşegen aralıktaki iki yuvarlak pad'i kare kabul edilince
köşeleri çakışıyor. Çözüm: `Pad.copper_shape()` üç şekli de doğru gösterir —
daire = nokta + yarıçap, oval = parça + yarıçap (stadyum), dörtgen = 4 köşe.
Üçü de `(noktalar, şişme_yarıçapı)` gösterimine indiği için açıklık tek
ifadeyle ölçülür: `shape_distance(A,B) - rA - rB`.

**Bu kararı geri almayın**: `tests/test_copper_rules.py` içindeki
`test_sound_board_at_logic_voltage_is_silent` bunu koruyor.

## 7. `exclusive: true` decoupling kuralında önemli (README)

`proximity` kuralında `exclusive: false` iken 3V3 gibi geniş bir rayda TEK bir
kondansatör bütün güç pinlerini "tatmin eder" ve eksik decoupling görünmez olur.

## 8. Netlist değişmezliği kalkanı (Aşama 4b)

Şematiğe/karta yazan her işlem, netlist'in değişmediğini doğrular. Yerleştirme
bağlantıyı asla değiştirmemeli. Ayrıca atomik yazma + açık-proje koruması var
(KiCad açıkken yazmak dosyayı bozar).

## 9. Sembol kimliği UUID'dir, referans değil (Aşama 4e)

Referanslar yeniden numaralanabilir; UUID kalıcıdır.

## 10. Yerleştirmede ölçülmüş OLUMSUZ sonuçlar (tekrar denemeyin)

- **Faz A** (geniş hamle repertuarı): kazanç yok. Ders: tavanı belirleyen
  repertuar darlığı değil, **skorun kendisi**.
- **Faz E** (tavlama benzeri kabul kuralı): ölçüldü, kazanç yok.
- "Yalnızca skor artışını say, hemen dur": **daha kötü** (2 iyi / 3 kötü).
  HPWL hamleleri boşa gitmiyor — **plato aşma mekanizması onlar**.
- `learned` yerleştirici uçtan uca hâlâ `auto`yu geçmiyor; üretim
  yerleştiricisi `auto`.

İlgili: [[known_problems_and_workarounds]], [[architecture]]
