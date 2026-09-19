"""BAGIMSIZ UYGULAMA - tek giris noktasi.

    pcbqa tani                       ortami denetle
    pcbqa analiz  <proje>            kaliteyi olc ve raporla
    pcbqa uret    <niyet.yaml>       niyetten calisir bir kart uret
    pcbqa kesfet  <niyet.yaml>       N varyant uret, en iyisini sec
    pcbqa bagla   <sematik>          var olan sembolleri telle birlestir
    pcbqa sozluk                     bilesen adlari sozlugu (EN/TR)
    pcbqa mpn     <sematik>          parca numarasi + fiyat alanlari (sentetik)
    pcbqa sablonlar                  sablon kutuphanesini listele
    pcbqa uygula  <kart.kicad_pcb>   acik KiCad'e yerlesim uygula (API'siz)

## Neden ayri bir Python gomulmuyor

"Bagimsiz" burada "KiCad'siz" DEMEK DEGIL - olamaz da: netlist/ERC/DRC icin
`kicad-cli`, sembol ve footprint icin KiCad'in kutuphaneleri gerekiyor. KiCad
zaten kurulu olmak zorunda.

KiCad kendi Python'unu (3.11.5) getiriyor ve `pcbqa`nin CALISMA ZAMANI
BAGIMLILIGI YOK (bkz. `confload.py`) - yani o yorumlayici bu uygulamayi
oldugu gibi kosturabiliyor. Ikinci bir Python gomer ya da PyInstaller ile
paketlersek elimizde daha buyuk, daha kirilgan ve virus tarayicilarini
rahatsiz eden bir cikti olur; kazanci ise sifir. Bu yuzden dagitim = bu
klasor + `pcbqa.cmd` baslatici.

Alt komutlar mevcut modullerin `main()`ini cagirir; ayri bir CLI yazilmaz,
yoksa iki arayuz ayrisir.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

APP_NAME = "pcbqa"

# (komut, modul yolu, tek satirlik aciklama)
COMMANDS: list[tuple[str, str, str]] = [
    ("tani", "", "Ortami denetle: KiCad, kutuphaneler, calisma zamani kopyalari"),
    ("kurulum", "pcbqa.kurulum", "Canli mod icin KiCad IPC sunucusunu ac (izinle)"),
    ("canli", "pcbqa.canli", "Acik PCB'ye baglan, onizle ve geri alinabilir yerlestirme uygula"),
    ("canli-sematik", "pcbqa.canli_sematik", "Ayri KiCad nightly ile acik sematige komut uygula"),
    ("analiz", "pcbqa.__main__", "Bir KiCad projesinin kalitesini olc ve raporla"),
    ("arayuz", "pcbqa.arayuz", "Masaustu arayuzunu ac (tkinter)"),
    ("yap", "pcbqa.komut", 'Dogal dil komutunu anla ve uygula ("10 adet kapasitor ekle")'),
    ("parcalar", "pcbqa.elektrik", "Her parca icin ag, gerilim, akim, MPN ve fiyat tablosu"),
    ("uret", "pcbqa.generate", "Niyet beyanindan calisir bir kart uret"),
    ("kesfet", "pcbqa.explore", "Ayni niyetten N varyant uret, en iyisini sec"),
    ("bagla", "pcbqa.connect", "Var olan sembolleri telle birlestir (--ag ya da --oner)"),
    ("sablonlar", "pcbqa.intent", "Sablon kutuphanesini listele"),
    ("sozluk", "pcbqa.lexicon", "Iki dilli bilesen sozlugu (kisaltma, ad, EN/TR)"),
    ("mpn", "pcbqa.mpn", "Bilesenlere SENTETIK parca numarasi ve fiyat alani yaz"),
    ("yerlestir", "pcbqa.harness", "Var olan bir karti yerlestir ve puanla"),
    ("uygula", "pcbqa.swig_apply", "Karti yerlestirip pcbnew ile uygula (API GEREKMEZ)"),
    ("uygula-ipc", "pcbqa.ipc_apply", "Calisan KiCad'e IPC ile uygula (API sunucusu acik olmali)"),
    ("veri", "pcbqa.ml.collect_design", "Niyetlerden egitim verisi topla"),
]

# `sablonlar` icin alt komutun kendi bayragi zorunlu
FORCED_ARGS = {"sablonlar": ["--list"]}


def usage() -> str:
    lines = [f"{APP_NAME} <komut> [secenekler]", "", "Komutlar:"]
    for name, _module, help_text in COMMANDS:
        lines.append(f"  {name:<15}{help_text}")
    lines += [
        "",
        f"Her komutun kendi yardimi vardir:  {APP_NAME} <komut> --help",
        "",
        "Not: KiCad kurulu olmalidir (netlist/ERC/DRC ve sembol kutuphaneleri).",
        f"     Once '{APP_NAME} tani' calistirin.",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# tani - ortam denetimi
# --------------------------------------------------------------------------


def _line(ok: bool | None, label: str, detail: str) -> str:
    mark = "  ok " if ok else ("  -- " if ok is None else "  !! ")
    return f"{mark}{label:<26}{detail}"


def diagnose() -> tuple[list[str], int]:
    """Ortami denetler. Doner: (satirlar, engel_sayisi)."""
    lines: list[str] = []
    problems = 0

    lines.append(_line(True, "yorumlayici", f"Python {sys.version.split()[0]}"))
    lines.append(_line(None, "yorumlayici yolu", sys.executable))

    # --- kicad-cli ---
    try:
        from .kicadcli import KicadCli, KicadCliError, find_kicad_cli

        cli_path = find_kicad_cli()
        version = KicadCli(str(cli_path)).version()
        lines.append(_line(True, "kicad-cli", f"{version}  ({cli_path})"))
    except Exception as exc:  # KicadCliError ya da calistirma hatasi
        problems += 1
        lines.append(_line(False, "kicad-cli", f"BULUNAMADI - {exc}"))
        lines.append(_line(None, "", "KiCad'i kurun ya da PCBQA_KICAD_CLI ayarlayin"))

    # --- kutuphaneler ---
    try:
        from . import symlib

        symbols = symlib.libraries()
        footprints = symlib.footprint_libraries()
        ok_sym = len(symbols) > 0
        problems += 0 if ok_sym else 1
        lines.append(_line(ok_sym, "sembol kutuphanesi", f"{len(symbols)} kutuphane"))
        ok_fp = len(footprints) > 0
        problems += 0 if ok_fp else 1
        lines.append(_line(ok_fp, "footprint kutuphanesi", f"{len(footprints)} kutuphane"))
    except Exception as exc:
        problems += 1
        lines.append(_line(False, "kutuphaneler", f"okunamadi - {exc}"))

    # --- calisma zamani kopyalari (pyyaml yoksa hayat memat meselesi) ---
    from .confload import runtime_twin, yaml_available
    from .bundle import yaml_sources

    sources = yaml_sources()
    missing = [s.name for s in sources if not runtime_twin(s).is_file()]
    if missing:
        problems += 1
        lines.append(_line(False, "calisma zamani kopyalari",
                           f"{len(missing)} eksik: {', '.join(missing[:4])}"))
        lines.append(_line(None, "", "uretmek icin: python -m pcbqa.bundle"))
    else:
        lines.append(_line(True, "calisma zamani kopyalari", f"{len(sources)} dosya tam"))

    lines.append(_line(None, "pyyaml", "var (YAML kaynaklari okunabilir)"
                       if yaml_available() else
                       "yok - JSON kopyalari kullanilacak (normal)"))

    # --- canli mod (IPC sunucusu) ---
    try:
        from .kurulum import status as setup_status

        state = setup_status()
        if state.all_enabled:
            lines.append(_line(True, "canli mod (IPC)", "acik"))
        elif state.configs:
            lines.append(_line(None, "canli mod (IPC)",
                               "kapali - acmak icin: pcbqa kurulum --uygula"))
        else:
            lines.append(_line(None, "canli mod (IPC)", "KiCad ayar dosyasi yok"))
    except Exception as exc:
        lines.append(_line(None, "canli mod (IPC)", f"denetlenemedi - {exc}"))

    # Sunucunun acik olmasi yetmez; ISTEMCI kutuphaneleri de gerekiyor ve
    # KiCad'in Python'unda kurulu GELMIYOR (bkz. kurulum.py).
    try:
        from .kurulum import live_deps

        deps = live_deps()
        eksik = [name for name, ok in deps.items() if ok is False]
        belirsiz = [name for name, ok in deps.items() if ok is None]
        if eksik:
            lines.append(_line(None, "canli mod kutuphaneleri",
                               f"{len(eksik)} eksik: {', '.join(eksik)}"))
            lines.append(_line(None, "", "kurmak icin: pcbqa kurulum --canli-bagimliliklar"))
        elif not belirsiz:
            lines.append(_line(True, "canli mod kutuphaneleri", "tam"))
        if belirsiz:
            lines.append(_line(None, "canli mod kutuphaneleri",
                               "DENETLENEMEDI - yorumlayici erisimi; paket eksikligi dogrulanmadi"))
    except Exception as exc:
        lines.append(_line(None, "canli mod kutuphaneleri", f"denetlenemedi - {exc}"))

    lines.append(_line(None, "canli PCB baglantisi", "sinamak icin: pcbqa canli"))
    from .canli_sematik import CONFIG
    lines.append(_line(None, "canli sematik", "ayri nightly ortami hazir; Canli sekmesinden kopyayi acin"
                       if CONFIG.is_file() else "stabil KiCad 9/10 desteklemiyor; ayri nightly ortami gerekir"))

    # --- surec-ici kopru (API'siz) ---
    try:
        import pcbnew  # type: ignore

        lines.append(_line(True, "pcbnew (surec-ici)", f"{pcbnew.GetBuildVersion()}"))
    except ModuleNotFoundError:
        lines.append(_line(None, "pcbnew (surec-ici)",
                           "yok - 'uygula' yalnizca IPC ile calisir"))

    # --- sablonlar ---
    try:
        from .intent import load_templates

        lines.append(_line(True, "sablon kutuphanesi", f"{len(load_templates())} sablon"))
    except Exception as exc:
        problems += 1
        lines.append(_line(False, "sablon kutuphanesi", f"okunamadi - {exc}"))

    return lines, problems


def run_diagnose() -> int:
    lines, problems = diagnose()
    print(f"{APP_NAME} - ortam denetimi")
    print()
    for line in lines:
        print(line)
    print()
    if problems:
        print(f"{problems} engel var - yukaridaki '!!' satirlarina bakin")
        return 1
    print("Temel ortam hazir. Canli baglanti ve istege bagli ozelliklerin durumuna yukaridan bakin.")
    return 0


# --------------------------------------------------------------------------
# Dagitim
# --------------------------------------------------------------------------


def _dispatch(command: str, argv: list[str]) -> int:
    module_name = dict((c, m) for c, m, _ in COMMANDS)[command]
    forced = FORCED_ARGS.get(command, [])

    from importlib import import_module

    module = import_module(module_name)
    main = getattr(module, "main", None)
    if main is None:  # pragma: no cover - COMMANDS elle bakiliyor
        print(f"hata: {module_name} bir CLI sunmuyor", file=sys.stderr)
        return 2
    return int(main(forced + argv) or 0)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help", "yardim"):
        print(usage())
        return 0
    if args[0] in ("-V", "--version", "surum"):
        print(f"{APP_NAME} (Python {sys.version.split()[0]})")
        return 0

    command, rest = args[0], args[1:]
    known = {c for c, _, _ in COMMANDS}
    if command not in known:
        near = ", ".join(sorted(n for n in known if n.startswith(command[:2])))
        print(f"hata: bilinmeyen komut: {command}"
              + (f" (benzerleri: {near})" if near else ""), file=sys.stderr)
        print(file=sys.stderr)
        print(usage(), file=sys.stderr)
        return 2

    if command == "tani":
        return run_diagnose()
    return _dispatch(command, rest)


if __name__ == "__main__":
    raise SystemExit(main())
