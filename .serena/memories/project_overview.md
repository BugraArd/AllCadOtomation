# Proje genel bakışı

## Ne bu?

KiCad üzerinde çalışan bir **PCB/şematik otomasyon ve kalite denetim sistemi**.
Depo kökü `C:\Users\ardaa\OneDrive\Desktop\Kicad`, asıl paket `pcbqa/` altında.

Hedef (HANDOFF.md'den): PCB ve şematik üzerinde **otomatik bileşen yerleştirme +
kalite/uygunluk testleri** — "doğru pinler doğru bağlanmış mı, hem de en verimli
uzaklıkta mı" sorusunu makineye sordurmak.

## Dil ve teknoloji

- **Saf Python** (107 .py dosyası). C/C++/STM32 kaynağı **yoktur** — bu bir
  gömülü yazılım projesi değildir.
- Bağımlılıklar minimal: `pyyaml` (zorunlu), `kicad-python` (yalnızca Aşama 2
  IPC yazımı için). `requirements.txt` iki satır.
- Sanal ortam: `pcbqa/.venv` (Python 3.13).
- KiCad ile iki ayrı süreç üzerinden konuşur: `kicad-cli` (CLI) ve IPC API.
  GPL kodla hiçbir noktada linklenmez (lisans kararı HANDOFF.md §1'de).

## Aşamalar (hepsi tamamlanmış)

| Aşama | Kapsam |
|---|---|
| 0 | Salt-okunur analiz + rapor + ölçüm |
| 1 | Kural motoru (YAML) + KiCad ERC/DRC entegrasyonu |
| 2 | Placement çıktısını çalışan KiCad PCB Editor'e IPC ile yazma |
| 3 | Tam otomatik PCB yerleştirme (`auto`) + gerileme koruması |
| 4a-4g | Şematik okuma/yazma, netlist kalkanı, sembol ekleme, karta yansıtma |
| 5 | Makine öğrenimi altyapısı |
| 6/A-G | Yerleştirme iyileştirme denemeleri (bir kısmı ölçüldü, kazanç yok) |
| 7 | Devre tipine göre kural kütüphanesi + bakır okuma/kuralları |

## Önemli kısıt

KiCad 10'da **şematik IPC API'si yok** (KiCad 11'e planlı). Şematik okuma/yazma
bu yüzden dosya düzeyinde s-expression ayrıştırmasıyla yapılıyor
(`pcbqa/sexpr.py`), PCB tarafı ise IPC kullanabiliyor.

## Girdi dosyaları

`samples/` altında iki test kartı: `bench_good`/`bench_bad` (sentetik,
**yönlendirilmemiş**) ve `pic_programmer` (KiCad'in kendi demosu, **370 iz +
6 via ile yönlendirilmiş**). Bakır kuralları yalnızca ikincisinde ölçüm yapar.

İlgili: [[architecture]], [[build_and_test_commands]]
