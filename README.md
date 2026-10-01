# AllCadOtomation — pcbqa

KiCad üzerinde çalışan bir **devre tasarımı otomasyonu ve kalite denetimi**
aracı. Saf Python'dur (çalışma zamanı bağımlılığı yok) ve KiCad'in kendi
Python'uyla çalışır.

Yaptıkları:

- **Analiz:** `.kicad_sch` + `.kicad_pcb` okunur, kaynaklı kural kütüphanesiyle
  (IPC-2221B, üretici uygulama notları) denetlenir ve skorlanır.
- **Devre grafı:** her parçanın pinleri, devredeki rolü, güç/gerilim sınırları,
  PCB karşılığı ve **eksik bilgileri** tek modelde toplanır.
- **Üç seviyeli doğrulama:**
  1. KiCad ERC / DRC / şematik paritesi
  2. parçaya ve amaca bağlı mühendislik kuralları
  3. **ngspice** benzetimi (tolerans, sıcaklık, yaşlanma)
- **PCB:** önce yerleşim ve kısıtlar, sonra dal akımına göre iz genişliği.
  Kirchhoff çözümüyle her iz parçasının gerçek akımı, darboğazlar, vialar ve
  gerilim düşümü hesaplanır.
- **Üretken tasarım:** niyet YAML'ından şematik + kart üretimi, otomatik
  yerleştirme, varyant keşfi (önce STM32).
- **KiCad'e bağlanma:** dosya, `pcbnew` (SWIG) ya da IPC. Açık PCB'de canlı
  düzenleme tek Ctrl+Z ile geri alınabilir.
- **ML veri hattı:** doğrulama ve yerleştirme sonuçları veri kümesine yazılır.

## Gereksinimler

| | Sürüm |
|---|---|
| KiCad | **10.0.4** (kicad-cli, sembol/footprint kütüphaneleri, `ngspice.dll`) |
| KiCad'in Python'u | 3.11.5 — dağıtımda bunu kullanır (`pcbqa.cmd`) |
| Geliştirme | Python 3.13 + `pcbqa/.venv` (`pyyaml`, `kicad-python`) |
| Benzetim | ngspice-46 (KiCad ile gelir; ek kurulum gerekmez) |
| İsteğe bağlı | KiCad nightly 10.99 (yalnızca canlı şematik için, `pcbqa/.runtime/`) |

## Hızlı başlangıç

```bat
cd pcbqa
pcbqa tani                                     :: ortam denetimi
pcbqa analiz samples\pic_programmer            :: kalite raporu
pcbqa devre  <proje>                           :: devre grafı ve eksikler
pcbqa dogrula <proje> --kosullar k.yaml        :: ERC/DRC + mühendislik + ngspice + PCB + 9 kontrol
pcbqa kontrol <proje> --kosullar k.yaml        :: hepsi tek koşuda: kalite skoru + doğrulama (ERC/DRC bir kez)
pcbqa uret --intent samples\niyetler\g031-asgari.yaml --out cikti\g031
pcbqa arayuz                                   :: masaüstü arayüzü (Yap, Devre, Kontrol, Düzelt, Deney, Üret, Canlı)
```

Kurulum ayrıntısı: `docs/KURULUM.md`. Tüm komutlar: `pcbqa --help`.

## Klasör yapısı

```
Kicad/
├─ pcbqa/                  uygulama
│  ├─ pcbqa/               Python paketi
│  │  ├─ app.py            tek giriş noktası (alt komutlar)
│  │  ├─ devre/            ortak devre modeli (graf, parça bilgisi, roller, koşullar)
│  │  ├─ dogrulama/        seviye 1-2-3 + dokuz kontrol
│  │  ├─ spice/            ngspice entegrasyonu
│  │  ├─ pcb_akim.py       dal akımı ve yönlendirme girdisi
│  │  ├─ rules.py, ipc2221.py, thermal.py, circuit.py   kural motoru ve hesaplar
│  │  ├─ placement/        yerleştiriciler (auto = üretim)
│  │  ├─ sch_*.py, pcb_sync.py   şematik/kart yazma (netlist kalkanıyla)
│  │  ├─ intent.py, generate.py, explore.py, templates/   üretken tasarım
│  │  ├─ canli*.py, ipc*.py, swig_apply.py   KiCad bağlantısı
│  │  ├─ data/parcalar/    kaynaklı parça bilgi kütüphanesi
│  │  └─ ml/               veri kümesi ve modeller
│  ├─ tests/               1035 unittest
│  └─ samples/             örnek projeler ve niyetler
├─ docs/                   TÜM belgeler: HANDOFF, KURULUM, tasarım kuralları,
│                          yol haritası, devre modeli, hafiza/ (Beads'ten üretilir), paketler/
├─ graphify-out/           bilgi grafiği
├─ .beads/                 iş takibi ve kalıcı hafıza (Beads)
├─ AGENTS.md               yapay zekâ ajanları için tek dosya (kurallar + yapı + hafıza)
└─ CLAUDE.md               AGENTS.md'yi içe aktarır
```

Özelliklerin tam haritası (hangi komut hangi modülde, ne yapar) `AGENTS.md`
bölüm 4'te.

## Testler

```bat
cd pcbqa
.venv\Scripts\python.exe -m unittest discover -s tests          :: 1035 test, ~5 dk
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_spice.py"
```

Son koşu 2026-10-01'de yapıldı: 1035 test, hepsi geçti. Dosya bazında liste
`AGENTS.md` bölüm 6'da.

## Belgeler

| Belge | İçerik |
|---|---|
| `pcbqa/README.md` | Uygulamanın ayrıntılı kullanımı |
| `docs/HAFIZA-HARITASI.md` | Tüm hafıza, ayar ve belge dosyaları: nerede, neden orada |
| `docs/KURULUM.md` | Kurulum, kısayol, canlı mod |
| `docs/HANDOFF.md` | Tam geliştirme bağlamı ve ölçülmüş kararlar |
| `docs/devre-modeli-ve-dogrulama.md` | Devre grafı, 3 seviyeli doğrulama, PCB dal akımı |
| `docs/tasarim-kurallari/` | Kural eşiklerinin kaynakları |
| `docs/yol-haritasi-skorlama.md` | Yol haritası |
| `docs/duzeltme-siralama.md` | ML ilk deneyi: düzeltme adayı sıralama, sonuçlar ve eksikler |

## Proje hafızası

İşler ve kalıcı kararlar **Beads**'te tutulur (`bd ready`, `bd recall <anahtar>`).
Kod ve belge ilişkileri **graphify** bilgi grafiğinde sorgulanır
(`graphify explain "<kavram>"`). Serena kullanılmaz.
