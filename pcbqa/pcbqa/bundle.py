"""Calisma zamani kopyalarini uretir: YAML -> JSON.

    python -m pcbqa.bundle            # uret
    python -m pcbqa.bundle --check    # ayrisma var mi diye bak (yazmaz)

## Neden

`pcbqa`nin tek ucuncu parti calisma zamani bagimliligi pyyaml'di ve KiCad'in
kendi Python'unda (3.11.5) o paket YOK. Yani eklenti - yani API'siz baglanti -
YAML'a bagli kaldigi surece mumkun degildi.

Cozum: YAML **kaynak**, JSON **calisma zamani kopyasi**. Ikisi de pakette
durur. Insan YAML'i okur (butun esik kaynaklari orada yorum olarak yaziyor -
"Kaynak: ST AN2586 Bolum 3.4"); calisma zamani JSON'u okur ve stdlib disinda
hicbir seye ihtiyac duymaz.

## Ayrisma riski ve karsiligi

Iki dosyanin ayrismasi gercek bir tehlike: birileri YAML'i duzeltir, JSON eski
kalir ve KiCad ICINDE eski kural kosar - hem de sessizce. `--check` bunu
yakalar ve bir test her kosumda cagirir.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .confload import RUNTIME_SUFFIX, ConfigError, load_config, runtime_twin, yaml_available

PACKAGE_ROOT = Path(__file__).parent

# Calisma zamaninda okunan YAML tasiyan klasorler
BUNDLED_DIRS = ("presets", "templates")


def yaml_sources(root: Path | None = None) -> list[Path]:
    """Paketle birlikte dagitilan YAML dosyalari."""
    root = Path(root) if root else PACKAGE_ROOT
    found: list[Path] = []
    for name in BUNDLED_DIRS:
        folder = root / name
        if folder.is_dir():
            found.extend(sorted(folder.glob("*.yaml")))
    # Varsayilan kural dosyasi klasorde degil, kokte duruyor
    default_rules = root / "default_rules.yaml"
    if default_rules.is_file():
        found.append(default_rules)
    return found


def render(data: dict) -> str:
    """JSON metni - bicimi SABIT olmali ki `--check` gurultu uretmesin."""
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def build(
    root: Path | None = None,
    write: bool = True,
    sources: list[Path] | None = None,
) -> tuple[list[Path], list[Path]]:
    """Kopyalari uretir/denetler. Doner: (guncel olanlar, ayrisan olanlar).

    `sources` verilirse yalnizca o dosyalar cevrilir - kullanicinin KENDI
    kural dosyasi da KiCad'in icinde okunabilsin diye. Paketle gelmeyen bir
    YAML'in JSON esi yoktur ve eklenti onu okuyamaz; bu, o bosluğun kapisi.
    """
    if not yaml_available():
        raise ConfigError(
            "pyyaml kurulu degil - kopyalari uretmek KAYNAGI okumayi gerektirir. "
            "Bu komut gelistirici ortaminda calistirilir, KiCad'in Python'unda degil."
        )
    fresh: list[Path] = []
    stale: list[Path] = []
    for source in (sources if sources is not None else yaml_sources(root)):
        data, _ = load_config(source)
        text = render(data)
        target = runtime_twin(source)
        current = target.read_text(encoding="utf-8") if target.is_file() else None
        if current == text:
            fresh.append(target)
            continue
        stale.append(target)
        if write:
            target.write_text(text, encoding="utf-8")
    return fresh, stale


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pcbqa.bundle",
        description="Kural ve sablon dosyalarinin calisma zamani JSON kopyalarini uretir.",
    )
    ap.add_argument("--check", action="store_true",
                    help="Yazma; yalnizca ayrisma var mi diye bak (cikis kodu 1)")
    ap.add_argument("--root", type=Path, default=None, help="Paket koku (test icin)")
    ap.add_argument("files", type=Path, nargs="*",
                    help="Belirli YAML dosyalari (bos birakilirsa paketle gelenler). "
                         "Kendi kural dosyanizi KiCad icinde okutmak icin kullanin.")
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    try:
        fresh, stale = build(args.root, write=not args.check,
                             sources=[Path(f) for f in args.files] or None)
    except ConfigError as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2

    if args.check:
        if stale:
            print(f"{len(stale)} calisma zamani kopyasi AYRISMIS:", file=sys.stderr)
            for path in stale:
                print(f"  {path.name}", file=sys.stderr)
            print("uretmek icin: python -m pcbqa.bundle", file=sys.stderr)
            return 1
        print(f"{len(fresh)} kopya guncel")
        return 0

    for path in stale:
        try:
            gosterim = path.relative_to(PACKAGE_ROOT)
        except ValueError:
            gosterim = path  # paket disindaki kullanici dosyasi
        print(f"  yazildi: {gosterim}")
    print(f"{len(stale)} kopya yazildi, {len(fresh)} zaten guncel"
          f"  (toplam {len(fresh) + len(stale)}{RUNTIME_SUFFIX})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
