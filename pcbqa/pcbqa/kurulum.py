"""KURULUM - canli mod icin KiCad'in IPC sunucusunu IZINLE acar.

    pcbqa kurulum              ne yapilacagini goster (YAZMAZ)
    pcbqa kurulum --uygula     onayla ve uygula
    pcbqa kurulum --geri-al    eski haline dondur

## Iki mod var, ikisi de gecerli

    API'SIZ MOD  (varsayilan, sifir ayar)
        uret / kesfet / yerlestir  -> dosyaya yazar
        uygula                     -> pcbnew ile surec-ici uygular
        Tek kisit: KiCad ACIKKEN dosyaya yazilmaz.

    CANLI MOD  (bu kurulum adimini ister)
        KiCad ACIKKEN calisan belgeye dokunulabilir; degisiklik KiCad'in
        kendi GERI ALMA yiginina girer, yani kullanici Ctrl+Z ile
        mudahale edebilir. KiCad 9/10'da bu yol PCB icindir; acik sematige
        yazma destegi yoktur. Paket kurmak sunucuya bu yetenegi eklemez.

## Neden bir kurulum adimi gerekiyor

KiCad'in IPC sunucusu VARSAYILAN OLARAK KAPALI:

    %APPDATA%\\kicad\\<surum>\\kicad_common.json  ->  api.enable_server = false

Her kullanicidan Tercihler'i acip bir kutu isaretlemesini beklemek yeni
kullanici icin zorlayici. Onun yerine kurulum bir kez, ACIKCA IZIN ALARAK
yapar. Izin `--uygula` bayragidir: once ne degisecegi gosterilir, sonra
kullanici bilerek onaylar.

## Guvenlik kurallari

  * KiCad CALISIYORSA yazilmaz. Sebep somut: KiCad ayarlari bellekte tutar
    ve CIKARKEN dosyanin uzerine yazar - bizim degisikligimiz sessizce
    kaybolurdu.
  * Yazmadan once yedek alinir.
  * Yalnizca `api.enable_server` alanina dokunulur; dosyanin geri kalani
    (temalar, kutuphane yollari, pencere konumlari) aynen korunur.
  * Yazdiktan sonra dosya GERI OKUNUP dogrulanir.
  * Her sey geri alinabilir: `--geri-al`.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .sch_write import atomic_write_text, backup_file

# Ayarin dosyadaki yeri
API_SECTION = "api"
API_FLAG = "enable_server"

# KiCad'in surece verdigi adlar (Windows). Calisiyorsa yazmayiz.
PROCESS_NAMES = ("kicad", "kicad-cli", "eeschema", "pcbnew", "kicad-cmd")


class SetupError(RuntimeError):
    """Kurulum yapilamadi."""


@dataclass
class ConfigFile:
    """Tek bir KiCad surumunun ayar dosyasi."""

    path: Path
    version: str
    enabled: bool


@dataclass
class SetupStatus:
    configs: list[ConfigFile] = field(default_factory=list)
    running: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def any_enabled(self) -> bool:
        return any(c.enabled for c in self.configs)

    @property
    def all_enabled(self) -> bool:
        return bool(self.configs) and all(c.enabled for c in self.configs)


# --------------------------------------------------------------------------
# Kesif
# --------------------------------------------------------------------------


def config_files() -> list[ConfigFile]:
    """Bulunan butun KiCad surumlerinin `kicad_common.json` dosyalari."""
    from .symlib import kicad_config_dirs

    found: list[ConfigFile] = []
    for folder in kicad_config_dirs():
        path = folder / "kicad_common.json"
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        enabled = bool((data.get(API_SECTION) or {}).get(API_FLAG, False))
        found.append(ConfigFile(path=path, version=folder.name, enabled=enabled))
    return found


def running_kicad() -> list[str]:
    """Calisan KiCad surecleri ("ad (pid)"). Bulunamazsa bos liste."""
    if sys.platform != "win32":
        return []
    try:
        proc = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return []  # sayamadiysak engellemeyiz; asil koruma yedek + geri alma
    out: list[str] = []
    for line in proc.stdout.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) < 2:
            continue
        name = parts[0].lower().removesuffix(".exe")
        if name in PROCESS_NAMES:
            out.append(f"{parts[0]} (pid {parts[1]})")
    return out


def status() -> SetupStatus:
    result = SetupStatus(configs=config_files(), running=running_kicad())
    if not result.configs:
        result.notes.append(
            "KiCad ayar dosyasi bulunamadi - KiCad'i bir kez calistirip kapatin, "
            "ayarlarini o zaman olusturuyor"
        )
    return result


# --------------------------------------------------------------------------
# Uygulama
# --------------------------------------------------------------------------


def set_api_enabled(path: Path, enabled: bool, backup: bool = True) -> bool:
    """Tek bir ayar dosyasinda bayragi degistirir. Doner: degisti mi.

    Dosyanin geri kalanina DOKUNULMAZ: JSON okunur, tek alan degistirilir,
    anahtar sirasi korunarak geri yazilir.
    """
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except OSError as exc:
        raise SetupError(f"ayar dosyasi okunamadi: {path} ({exc})") from exc
    except json.JSONDecodeError as exc:
        raise SetupError(f"ayar dosyasi bozuk: {path} ({exc})") from exc

    section = data.get(API_SECTION)
    if not isinstance(section, dict):
        section = {}
        data[API_SECTION] = section
    if bool(section.get(API_FLAG, False)) == enabled:
        return False

    section[API_FLAG] = enabled
    if backup:
        backup_file(path, suffix=".pcbqa-bak")
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    # Geri oku: yazdigimizi gormek zorundayiz.
    check = json.loads(path.read_text(encoding="utf-8"))
    if bool((check.get(API_SECTION) or {}).get(API_FLAG, False)) != enabled:
        raise SetupError(f"{path.name}: ayar yazildi ama geri okunamadi")
    return True


def apply(enabled: bool, allow_running: bool = False) -> list[Path]:
    """Butun bulunan ayar dosyalarinda bayragi ayarlar. Doner: degisenler."""
    state = status()
    if not state.configs:
        raise SetupError(
            "KiCad ayar dosyasi bulunamadi - KiCad'i bir kez calistirip kapatin"
        )
    if all(config.enabled == enabled for config in state.configs):
        return []
    if state.running and not allow_running:
        raise SetupError(
            "KiCad su an calisiyor (" + ", ".join(state.running) + "). "
            "KiCad ayarlari bellekte tutar ve CIKARKEN dosyanin uzerine yazar; "
            "simdi degistirirsek degisiklik kaybolur. Once KiCad'i kapatin."
        )
    changed: list[Path] = []
    for config in state.configs:
        if set_api_enabled(config.path, enabled):
            changed.append(config.path)
    return changed


# --------------------------------------------------------------------------
# Canli modun ISTEMCI tarafi
# --------------------------------------------------------------------------
#
# `--uygula` KiCad'in SUNUCUSUNU aciyor. Ama bizim tarafimizda da bir istemci
# gerekiyor ve o KiCad'in Python'unda KURULU GELMIYOR. Olcum (KiCad 10.0.4):
#
#     python.exe -c "import kipy"          -> ModuleNotFoundError
#     google.protobuf / pynng / nng        -> hicbiri yok
#
# API'siz mod bundan etkilenmiyor - onun hicbir calisma zamani bagimliligi yok.
# Yalnizca canli mod bu adimi ister.
#
# Nereye kuruluyor: KiCad'in KENDI eklenti klasoru. `sitecustomize.py`
# `PYTHONUSERBASE`i `<Belgeler>\KiCad\<surum>\3rdparty\` yapiyor, yani
# `pip install --user` tam KiCad'in aradigi yere dusuyor. Sistem Python'una ya
# da KiCad'in `bin\Lib\site-packages` klasorune DOKUNULMUYOR: ikincisi Program
# Files altinda ve KiCad guncellemesinde silinir.

# Surum sabitlenmis: 0.7.1 ile olculdu. Ust duzey sematik sarmalayicisi bu
# surumde BOZUK (kendi protobuf'unda BusEntryType yok), ama biz onu kullanmiyoruz
# - ham `KiCadClient.send()` kanalindan gidiyoruz. Yeni surume gecmeden once
# sondayi tekrar kosun.
LIVE_PACKAGES = ("kicad-python==0.7.1",)

# Ne import edilebiliyor: (modul, ne ise yaradigi)
LIVE_IMPORTS = (
    ("kipy", "IPC istemcisi"),
    ("google.protobuf", "komut kodlamasi"),
    ("pynng", "tasima katmani"),
)


def kicad_python() -> Path | None:
    """Canli modun kosacagi yorumlayici - KiCad'in kendi `python.exe`si."""
    try:
        import pcbnew  # noqa: F401  # zaten KiCad'in Python'undayiz
        return Path(sys.executable)
    except ModuleNotFoundError:
        pass

    explicit = os.environ.get("PCBQA_PYTHON")
    if explicit and Path(explicit).is_file():
        return Path(explicit)

    # kicad-cli'yi zaten ariyoruz; python.exe onun yanindadir.
    try:
        from .kicadcli import find_kicad_cli

        candidate = Path(find_kicad_cli()).parent / "python.exe"
        if candidate.is_file():
            return candidate
    except Exception:
        pass
    return None


def live_deps_details(python: Path | None = None) -> dict[str, dict]:
    """Gercek import; bulunamayan paket ile calistirilmayan denetimi ayirir."""
    python = python or kicad_python()
    if python is None:
        return {name: {"ok": False, "error": "yorumlayici bulunamadi"}
                for name, _ in LIVE_IMPORTS}
    if python.name.lower() == "pythonw.exe":
        python = python.with_name("python.exe")
    # find_spec('google.protobuf') google yoksa tum donguyu dusuruyordu.
    # Her import ayri sinanir; DLL/protobuf uyumsuzlugu da gorunur olur.
    script = "import importlib, json\nresult = {}\n"
    script += "for name in " + repr([n for n, _ in LIVE_IMPORTS]) + ":\n"
    script += (
        " try:\n"
        "  importlib.import_module(name)\n"
        "  result[name] = {'ok': True, 'error': ''}\n"
        " except Exception as exc:\n"
        "  result[name] = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}\n"
        "print(json.dumps(result))\n"
    )
    try:
        proc = subprocess.run([str(python), "-c", script],
                              capture_output=True, text=True, timeout=15,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if proc.returncode:
            raise SetupError(proc.stderr.strip() or f"yorumlayici cikis kodu {proc.returncode}")
        result = json.loads(proc.stdout)
        for name, _ in LIVE_IMPORTS:
            if result[name]["ok"] not in (True, False):
                raise ValueError("gecersiz denetim cevabi")
        return result
    except (OSError, subprocess.SubprocessError, SetupError, ValueError, KeyError, TypeError) as exc:
        return {name: {"ok": None, "error": str(exc)} for name, _ in LIVE_IMPORTS}


def live_deps(python: Path | None = None) -> dict[str, bool | None]:
    """True: import edildi; False: kullanilamiyor; None: denetlenemedi."""
    return {name: item["ok"] for name, item in live_deps_details(python).items()}


def install_live_deps(python: Path | None = None, dry_run: bool = False,
                      echo=print) -> int:
    """`pip install --user` ile canli mod bagimliliklarini kurar.

    KiCad'in ACIK olmasi sorun DEGIL: ayri bir surece paket kuruyoruz, KiCad'in
    yapilandirmasina dokunmuyoruz. (`--uygula` ise ayara yazdigi icin kapali
    olmasini ister.)
    """
    python = python or kicad_python()
    if python is None:
        raise SetupError(
            "KiCad'in Python'u bulunamadi - KiCad kurulu mu? "
            "Gerekirse PCBQA_PYTHON ile yolunu verin."
        )
    if python.name.lower() == "pythonw.exe":
        python = python.with_name("python.exe")

    command = [str(python), "-m", "pip", "install", "--no-input", "--disable-pip-version-check"]
    # Arayuzun venv'inde --user kullanilamaz. KiCad'de kullanici eklenti
    # klasoru secilir; Program Files altina paket yazilmaz.
    if not (python.parent.parent / "pyvenv.cfg").is_file():
        command.append("--user")
    command.extend(LIVE_PACKAGES)
    if dry_run:
        command.insert(command.index("install") + 1, "--dry-run")

    echo(f"  yorumlayici: {python}")
    echo("  komut      : " + " ".join(command[1:]))
    echo("")
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=900,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError) as exc:
        raise SetupError(f"paket kurulumu calistirilamadi: {exc}") from exc
    for line in (proc.stdout + proc.stderr).splitlines():
        if line.strip():
            echo("    " + line.rstrip())
    if proc.returncode != 0:
        raise SetupError(f"pip basarisiz oldu (kod {proc.returncode})")

    if dry_run:
        return 0

    # Kurulum "basarili" demis olabilir ama asil sorumuz import edilebiliyor mu.
    eksik = [name for name, ok in live_deps(python).items() if not ok]
    if eksik:
        raise SetupError(
            "pip bitti ama su modul(ler) hala import edilemiyor: "
            + ", ".join(eksik)
        )
    return 0


# --------------------------------------------------------------------------
# Rapor
# --------------------------------------------------------------------------


def describe(state: SetupStatus) -> str:
    lines = ["pcbqa - canli mod kurulumu", ""]
    lines.append("Iki mod var:")
    lines.append("  API'siz mod : sifir ayar. Dosyaya yazar, pcbnew ile uygular.")
    lines.append("                KiCad ACIKKEN dosyaya yazmaz.")
    lines.append("  Canli mod   : KiCad ACIKKEN calisan belgeye dokunur. Degisiklik")
    lines.append("                KiCad'in geri alma yiginina girer (Ctrl+Z ile geri alinir).")
    lines.append("  Sematik     : KiCad 9/10'da canli yazma desteklenmiyor.")
    lines.append("                Editor kapaliyken dosya duzenlenir, sonra yeniden acilir.")
    lines.append("")

    if not state.configs:
        lines.append("  ayar dosyasi bulunamadi")
    for config in state.configs:
        durum = "ACIK" if config.enabled else "kapali"
        lines.append(f"  KiCad {config.version:<6} IPC sunucusu: {durum}")
        lines.append(f"  {'':<13}{config.path}")
    lines.append("")

    if state.running:
        lines.append("  UYARI: KiCad su an calisiyor - " + ", ".join(state.running))
        lines.append("         Ayar degistirmek icin once kapatilmali.")
        lines.append("")

    for note in state.notes:
        lines.append(f"  not: {note}")

    # Sunucu acik olsa bile ISTEMCI tarafi eksik olabilir - iki ayri sey.
    deps = live_deps()
    eksik = [name for name, ok in deps.items() if ok is False]
    belirsiz = [name for name, ok in deps.items() if ok is None]
    aciklama = dict(LIVE_IMPORTS)
    if eksik:
        lines.append("  Canli mod bagimliliklari EKSIK:")
        for name in eksik:
            lines.append(f"    - {name:<16}{aciklama[name]}")
        lines.append("    kurmak icin: pcbqa kurulum --canli-bagimliliklar")
        lines.append("    (KiCad'in kendi eklenti klasorune kurulur; ACIK olmasi sorun degil)")
    elif not belirsiz:
        lines.append("  Canli mod bagimliliklari: tam")
    if belirsiz:
        lines.append("  Canli mod bagimliliklari DENETLENEMEDI: " + ", ".join(belirsiz))
        lines.append("    Yorumlayici erisimini kontrol edin; bu sonuc paketlerin eksik oldugu anlamina gelmez.")
    lines.append("")

    if state.all_enabled:
        lines.append("  IPC sunucusu ACIK. Ayar icin baska bir sey yapmaniza gerek yok.")
    elif state.configs:
        lines.append("  IPC sunucusunu acmak icin:  pcbqa kurulum --uygula")
        lines.append("  Degistirilecek tek alan: api.enable_server -> true")
        lines.append("  (yedek alinir, 'pcbqa kurulum --geri-al' ile donulebilir)")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Komut satiri
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pcbqa.kurulum",
        description="Canli mod icin KiCad'in IPC sunucusunu acar (izinle).",
    )
    grup = ap.add_mutually_exclusive_group()
    grup.add_argument("--uygula", action="store_true", help="Canli modu ac")
    grup.add_argument("--geri-al", dest="geri_al", action="store_true",
                      help="Canli modu kapat, eski haline don")
    grup.add_argument("--canli-bagimliliklar", dest="bagimliliklar",
                      action="store_true",
                      help="Canli modun istemci kutuphanelerini KiCad'in eklenti "
                           "klasorune kur (KiCad acik olabilir)")
    ap.add_argument("--kicad-acikken", dest="acikken", action="store_true",
                    help="KiCad calisirken de yaz (ONERILMEZ - degisiklik kaybolabilir)")
    ap.add_argument("--kuru", action="store_true",
                    help="--canli-bagimliliklar ile: ne kurulacagini goster, kurma")
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)

    if args.bagimliliklar:
        print("pcbqa - canli mod bagimliliklari")
        print()
        try:
            install_live_deps(dry_run=args.kuru)
        except SetupError as exc:
            print(f"hata: {exc}", file=sys.stderr)
            return 2
        print()
        if args.kuru:
            print("kuru calisma - hicbir sey kurulmadi")
        else:
            print("bagimliliklar kuruldu ve import edilebildigi dogrulandi")
            print("Dogrulamak icin: pcbqa tani")
        return 0

    if not args.uygula and not args.geri_al:
        print(describe(status()))
        return 0

    hedef = bool(args.uygula)
    try:
        changed = apply(hedef, allow_running=args.acikken)
    except SetupError as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2

    if not changed:
        print("degisiklik gerekmedi - ayar zaten istenen durumda "
              f"({'acik' if hedef else 'kapali'})")
        return 0

    for path in changed:
        print(f"  guncellendi: {path}")
    print()
    if hedef:
        print("Canli mod acildi. KiCad'i YENIDEN BASLATIN - sunucu acilista baglanir.")
        print("Dogrulamak icin: pcbqa tani")
    else:
        print("Canli mod kapatildi. KiCad'i yeniden baslatin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
