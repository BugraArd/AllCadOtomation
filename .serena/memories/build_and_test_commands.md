# Derleme ve test komutları

**Derleme adımı yoktur** — saf Python, paketleme yapılandırması (setup.py /
pyproject.toml) da yok. Depo kökünden `python -m pcbqa` ile çalıştırılır.

Tüm komutlar `C:\Users\ardaa\OneDrive\Desktop\Kicad\pcbqa` dizininden çalışır.

## Python yorumlayıcısı

Sanal ortam: `pcbqa/.venv` (Python 3.13).

```
.venv\Scripts\python.exe
```

**Sistem `python` KULLANMAYIN**: bağımlılıklar (`pyyaml`, `kicad-python`)
yalnızca `.venv` içinde. Sistem Python'da `import yaml` başarısız olur.

## Test

```
.venv\Scripts\python.exe -m unittest discover -s tests
```

- Çerçeve **unittest**'tir, pytest DEĞİL. `pytest` kurulu değil;
  `python -m pytest` "No module named pytest" verir.
- 2026-08-27 itibarıyla **277 test**, hepsi geçiyor.
- Tam paket ~110-195 saniye sürer (yerleştirme testleri gerçek bütçeyle çalışır).

Tek modül:

```
.venv\Scripts\python.exe -m unittest tests.test_copper_rules
.venv\Scripts\python.exe -m unittest tests.test_ipc2221 -v
```

## Çalıştırma

```
run.cmd <proje> [secenekler]
```

`run.cmd` yalnızca `.venv\Scripts\python.exe -m pcbqa %*` çağırır.

## Bağımlılık kurulumu

```
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Test dosyaları

`tests/` altında 13 dosya. Bakır/kural tarafı: `test_copper.py` (6),
`test_ipc2221.py` (15), `test_copper_rules.py` (30), `test_presets.py` (12).

Testlerin bir kısmı KiCad kurulumuna bağlıdır (`kicad_cli_available()`,
`device_library_available()` ile atlanabilir yapılmış) — KiCad yoksa o testler
atlanır, paket yine geçer.

## Kural dosyası doğrulama

Bir YAML kural dosyasının yüklenip yüklenmediğini hızlı kontrol:

```
.venv\Scripts\python.exe -c "from pcbqa.rules import load_rules; print(len(load_rules('pcbqa/presets/uretim.rules.yaml')))"
```

İlgili: [[project_overview]], [[known_problems_and_workarounds]]
