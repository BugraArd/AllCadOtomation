"""KiCad sembol kutuphanelerini okuma (.kicad_sym + sym-lib-table).

Bugune kadar sematik tarafi yalnizca dosyanin KENDI icindeki `lib_symbols`
bolumunu taniyordu - yani var olan sembolleri okuyup tasiyabiliyor, ama yeni
bir sembol EKLEYEMIYORDU. Ekleme icin sembolun tanimini bir yerden getirmek
gerekir; o yer kutuphanelerdir.

## Cozumleme zinciri (KiCad'in kendi sirasi)

    Device:R
    ^^^^^^ takma ad          -> sym-lib-table'da aranir
           ^ sembol adi      -> .kicad_sym dosyasinda aranir

Tablolar iki katmanlidir ve KiCad ikisini de okur:

  1. PROJE tablosu   <proje>/sym-lib-table          (varsa oncelikli)
  2. GENEL tablo     %APPDATA%/kicad/<surum>/sym-lib-table
                     ~/.config/kicad/<surum>/sym-lib-table  (Linux/mac)

Genel tablo `(type "Table")` satiriyla BASKA bir tabloyu isaret edebilir -
KiCad kurulumundaki varsayilan kutuphane listesi boyle gelir. Zincir izlenir.

## Ortam degiskenleri

URI'ler `${KICAD10_SYMBOL_DIR}` gibi degiskenler icerir. KiCad bunlari
`kicad_common.json`dan ya da kendi varsayilanlarindan cozer; burada da ayni
sira uygulanir:

    os.environ  ->  kicad_common.json  ->  kurulumdan turetilen varsayilan

`KIPRJMOD` her zaman projenin kendi klasorudur.

## Neden ayri modul

`schematic.py` PCB/sematik DOSYASINI bilir, kutuphane sistemini bilmez.
Bu modul yalnizca s-expr ve dosya sistemi bilir; ekleme mantigi
(`sch_add.py`) ikisini birlestirir. Katmanlama `rules.py`/`model.py`
ayrimiyla ayni.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .kicadcli import find_kicad_cli
from .sexpr import child, children, head, parse_with_stats

# ${...} bicimindeki degisken referansi
_VAR = re.compile(r"\$\{([A-Za-z0-9_]+)\}")
# Surum numarasi tasiyan degiskenler: KICAD10_SYMBOL_DIR, KICAD9_SYMBOL_DIR...
_VERSIONED = re.compile(r"^KICAD(\d+)_(SYMBOL|FOOTPRINT|3DMODEL|TEMPLATE)_DIR$")


class SymLibError(RuntimeError):
    """Kutuphane ya da sembol bulunamadi / okunamadi."""


@dataclass
class LibPin:
    """Kutuphane uzayinda bir sembol pini."""

    number: str
    name: str
    electrical: str = "unspecified"
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    length: float = 0.0
    unit: int = 1


@dataclass
class LibSymbol:
    """Kutuphaneden okunmus bir sembol tanimi."""

    lib_id: str  # "Device:R"
    name: str  # "R"
    library: str  # "Device"
    path: Path  # kaynak .kicad_sym
    node: list  # ham s-expr dugumu (lib_symbols'a kopyalanacak)
    properties: dict[str, str] = field(default_factory=dict)
    pins: list[LibPin] = field(default_factory=list)
    extends: str | None = None

    @property
    def reference_prefix(self) -> str:
        """Referans on eki: "R", "C", "U"...

        Kutuphanedeki `Reference` ozelligi zaten on ektir (KiCad sembolu
        yerlestirirken sonuna numara ekler). Bos ise "U" makul bir varsayilan.
        """
        raw = (self.properties.get("Reference") or "U").strip()
        # "R?" gibi eski bicimleri de temizle
        return raw.rstrip("?0123456789") or "U"

    @property
    def unit_count(self) -> int:
        """Sembolun birim sayisi (or. 74LS125 -> 4 kapi + guc birimi)."""
        units = set()
        for sub in children(self.node, "symbol"):
            name = head_atom(sub)
            parsed = _unit_of(name)
            if parsed is not None:
                units.add(parsed)
        return max(units) if units else 1


def head_atom(node) -> str:
    """Dugumun ilk argumani (genelde ad)."""
    return str(node[1]).strip('"') if len(node) > 1 and not isinstance(node[1], list) else ""


def _unit_of(sub_name: str) -> int | None:
    """"R_0_1" -> 0, "74LS125_1_1" -> 1. Ad cozulemezse None."""
    parts = sub_name.rsplit("_", 2)
    if len(parts) == 3 and parts[1].isdigit():
        return int(parts[1])
    return None


# --------------------------------------------------------------------------
# Ortam degiskenleri
# --------------------------------------------------------------------------


def kicad_config_dirs() -> list[Path]:
    """KiCad kullanici yapilandirma klasorleri, yeni surum once."""
    roots: list[Path] = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        roots.append(Path(appdata) / "kicad")
    home = Path.home()
    roots.extend([home / ".config" / "kicad",
                  home / "Library" / "Preferences" / "kicad"])

    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        versions = [p for p in root.iterdir() if p.is_dir() and p.name[:1].isdigit()]
        found.extend(sorted(versions, key=_version_key, reverse=True))
    return found


def _version_key(path: Path) -> tuple:
    return tuple(int(p) if p.isdigit() else 0 for p in path.name.split("."))


def kicad_install_root(kicad_cli: str | None = None) -> Path | None:
    """KiCad kurulum koku (`share/kicad`in ustu). Bulunamazsa None."""
    try:
        cli = find_kicad_cli(kicad_cli)
    except Exception:
        return None
    return cli.parent.parent  # <root>/bin/kicad-cli.exe -> <root>


def environment(project_dir: Path | None = None, kicad_cli: str | None = None) -> dict[str, str]:
    """URI'lerde kullanilan degiskenler; KiCad'in cozme sirasiyla.

    En dusuk oncelikten en yuksege: kurulumdan turetilenler, kullanicinin
    `kicad_common.json`i, sonra gercek ortam degiskenleri. `KIPRJMOD`
    her zaman projenin klasorudur.
    """
    env: dict[str, str] = {}

    root = kicad_install_root(kicad_cli)
    if root is not None:
        share = root / "share" / "kicad"
        # Surum on ekini kurulum klasorunden al: ...\KiCad\10.0 -> 10
        major = root.name.split(".")[0]
        if major.isdigit():
            env[f"KICAD{major}_SYMBOL_DIR"] = str(share / "symbols")
            env[f"KICAD{major}_FOOTPRINT_DIR"] = str(share / "footprints")
            env[f"KICAD{major}_3DMODEL_DIR"] = str(share / "3dmodels")
            env[f"KICAD{major}_TEMPLATE_DIR"] = str(share / "template")

    for cfg in kicad_config_dirs():
        common = cfg / "kicad_common.json"
        if not common.is_file():
            continue
        try:
            data = json.loads(common.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        for name, value in ((data.get("environment") or {}).get("vars") or {}).items():
            env[name] = value
        break

    for name, value in os.environ.items():
        if name.startswith("KICAD") or name == "KIPRJMOD":
            env[name] = value

    if project_dir is not None:
        env["KIPRJMOD"] = str(project_dir)
    return env


def expand(uri: str, env: dict[str, str]) -> str:
    """URI'deki `${DEGISKEN}` referanslarini cozer.

    Cozulemeyen bir surumlu degisken (or. `${KICAD9_SYMBOL_DIR}` ama kurulu
    olan 10) elde bulunan ayni turden degiskene DUSURULUR - kutuphane
    tablosu KiCad guncellemesinden sonra eski adi tasiyabiliyor.
    """

    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name in env:
            return env[name]
        versioned = _VERSIONED.match(name)
        if versioned:
            kind = versioned.group(2)
            for key, value in env.items():
                other = _VERSIONED.match(key)
                if other and other.group(2) == kind:
                    return value
        return m.group(0)

    return _VAR.sub(repl, uri)


# --------------------------------------------------------------------------
# sym-lib-table
# --------------------------------------------------------------------------


@dataclass
class LibEntry:
    nickname: str
    uri: str
    kind: str = "KiCad"
    source: Path | None = None


def read_lib_table(path: Path) -> list[LibEntry]:
    """Tek bir `sym-lib-table` dosyasini okur (zinciri IZLEMEZ)."""
    try:
        root, _ = parse_with_stats(path.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        raise SymLibError(f"kutuphane tablosu okunamadi: {path} ({exc})") from exc

    entries: list[LibEntry] = []
    for lib in children(root, "lib"):
        name = _field(lib, "name")
        uri = _field(lib, "uri")
        if name and uri:
            entries.append(LibEntry(nickname=name, uri=uri,
                                    kind=_field(lib, "type") or "KiCad", source=path))
    return entries


def _field(node, name: str) -> str:
    sub = child(node, name)
    if not sub or len(sub) < 2:
        return ""
    return str(sub[1]).strip('"')


def lib_tables(project_dir: Path | None = None,
               filename: str = "sym-lib-table") -> list[Path]:
    """Okunacak tablolar: once proje, sonra genel.

    `filename` ile footprint tablosu da okunur (`fp-lib-table`) - iki dosya
    ayni s-expr bicimini paylasir.
    """
    tables: list[Path] = []
    if project_dir is not None:
        local = Path(project_dir) / filename
        if local.is_file():
            tables.append(local)
    for cfg in kicad_config_dirs():
        table = cfg / filename
        if table.is_file():
            tables.append(table)
            break
    return tables


def libraries(project_dir: Path | None = None, kicad_cli: str | None = None) -> dict[str, Path]:
    """Takma ad -> .kicad_sym yolu. Proje tablosu genel tabloyu EZER.

    `(type "Table")` satirlari izlenir; KiCad kurulumunun varsayilan
    kutuphane listesi bu sekilde baglidir.
    """
    env = environment(project_dir, kicad_cli)
    result: dict[str, Path] = {}

    # Sonra okunan EZMESIN diye ters sirada gez: genel once, proje sonra.
    for table in reversed(lib_tables(project_dir)):
        for entry in _flatten(table, env, seen=set()):
            path = Path(expand(entry.uri, env))
            if path.suffix.lower() == ".kicad_sym":
                result[entry.nickname] = path
    return result


def _flatten(table: Path, env: dict[str, str], seen: set[Path]) -> list[LibEntry]:
    """Tablo zincirini duzlestirir (dongulere karsi `seen` tutulur)."""
    table = table.resolve()
    if table in seen:
        return []
    seen.add(table)

    out: list[LibEntry] = []
    for entry in read_lib_table(table):
        if entry.kind.lower() == "table":
            nested = Path(expand(entry.uri, env))
            if nested.is_file():
                out.extend(_flatten(nested, env, seen))
        else:
            out.append(entry)
    return out


def footprint_libraries(project_dir: Path | None = None,
                        kicad_cli: str | None = None) -> dict[str, Path]:
    """Takma ad -> `.pretty` klasoru. Sembol tarafiyla ayni cozumleme."""
    env = environment(project_dir, kicad_cli)
    result: dict[str, Path] = {}
    for table in reversed(lib_tables(project_dir, "fp-lib-table")):
        for entry in _flatten(table, env, seen=set()):
            result[entry.nickname] = Path(expand(entry.uri, env))
    return result


def footprint_path(
    fp_id: str,
    project_dir: Path | None = None,
    kicad_cli: str | None = None,
) -> Path:
    """`Resistor_SMD:R_0805_2012Metric` -> .kicad_mod dosyasi.

    Bulunamazsa `SymLibError` atar - sebebi adiyla soyler. Footprint kimligi
    yanlis yazilmis bir sembol, karta gecerken sessizce "footprint yok"
    olarak dusuyordu; kontrol bu yuzden var.
    """
    if ":" not in fp_id:
        raise SymLibError(f"footprint kimligi 'Kutuphane:Ad' olmali: {fp_id!r}")
    nickname, name = fp_id.split(":", 1)

    index = footprint_libraries(project_dir, kicad_cli)
    folder = index.get(nickname)
    if folder is None:
        near = ", ".join(sorted(n for n in index
                                if n.lower().startswith(nickname[:3].lower()))[:6])
        raise SymLibError(
            f"footprint kutuphanesi bulunamadi: {nickname!r}"
            + (f" (benzerleri: {near})" if near else "")
        )
    path = folder / f"{name}.kicad_mod"
    if not path.is_file():
        available = sorted(p.stem for p in folder.glob(f"{name[:4]}*.kicad_mod"))[:6]             if folder.is_dir() else []
        raise SymLibError(
            f"footprint bulunamadi: {name!r} ({folder})"
            + (f" (benzerleri: {', '.join(available)})" if available else "")
        )
    return path


def footprint_exists(fp_id: str, project_dir: Path | None = None,
                     kicad_cli: str | None = None) -> bool:
    try:
        footprint_path(fp_id, project_dir, kicad_cli)
        return True
    except SymLibError:
        return False


# --------------------------------------------------------------------------
# .kicad_sym
# --------------------------------------------------------------------------


def load_library(path: Path) -> dict[str, list]:
    """Bir `.kicad_sym` dosyasindaki sembolleri ad -> dugum olarak dondurur."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise SymLibError(f"kutuphane okunamadi: {path} ({exc})") from exc

    root, stray = parse_with_stats(text)
    if stray:
        raise SymLibError(f"{Path(path).name} bozuk gorunuyor ({stray} kacak parantez)")
    if head(root) != "kicad_symbol_lib":
        raise SymLibError(f"{Path(path).name} bir sembol kutuphanesi degil")

    out: dict[str, list] = {}
    for node in children(root, "symbol"):
        name = head_atom(node)
        if name:
            out[name] = node
    return out


def _properties_of(node) -> dict[str, str]:
    props: dict[str, str] = {}
    for prop in children(node, "property"):
        if len(prop) >= 3:
            props[str(prop[1]).strip('"')] = str(prop[2]).strip('"')
    return props


def _pins_of(node) -> list[LibPin]:
    """Sembolun butun birimlerindeki pinler.

    Pinler alt `(symbol "AD_<birim>_<govde>")` dugumlerinde durur; birim
    numarasi addan cozulur.
    """
    pins: list[LibPin] = []
    for sub in children(node, "symbol"):
        unit = _unit_of(head_atom(sub)) or 1
        for pin in children(sub, "pin"):
            at = child(pin, "at")
            number = child(pin, "number")
            name = child(pin, "name")
            pins.append(
                LibPin(
                    number=str(number[1]).strip('"') if number and len(number) > 1 else "",
                    name=str(name[1]).strip('"') if name and len(name) > 1 else "",
                    electrical=str(pin[1]).strip('"') if len(pin) > 1 else "unspecified",
                    x=float(at[1]) if at and len(at) > 1 else 0.0,
                    y=float(at[2]) if at and len(at) > 2 else 0.0,
                    rotation=float(at[3]) if at and len(at) > 3 else 0.0,
                    length=float(child(pin, "length")[1]) if child(pin, "length") else 0.0,
                    unit=unit,
                )
            )
    return pins


def get_symbol(
    lib_id: str,
    project_dir: Path | None = None,
    kicad_cli: str | None = None,
    extra_libs: dict[str, Path] | None = None,
) -> LibSymbol:
    """`Device:R` gibi bir kimligi cozup sembol tanimini dondurur.

    `(extends "R")` tasiyan turevler (or. `R_Small`) ust sembolle
    BIRLESTIRILIR: ozellikler turevin, pin/grafik ustunundur - KiCad'in
    kendi davranisi budur.
    """
    if ":" not in lib_id:
        raise SymLibError(f"kutuphane kimligi 'Kutuphane:Sembol' olmali: {lib_id!r}")
    nickname, name = lib_id.split(":", 1)

    index = dict(libraries(project_dir, kicad_cli))
    if extra_libs:
        index.update({k: Path(v) for k, v in extra_libs.items()})

    path = index.get(nickname)
    if path is None:
        near = ", ".join(sorted(n for n in index if n.lower().startswith(nickname[:3].lower()))[:6])
        raise SymLibError(
            f"kutuphane bulunamadi: {nickname!r}"
            + (f" (benzerleri: {near})" if near else "")
            + f" - {len(index)} kutuphane tarandi"
        )
    if not path.is_file():
        raise SymLibError(f"kutuphane dosyasi yok: {path} ({nickname})")

    symbols = load_library(path)
    node = symbols.get(name)
    if node is None:
        near = ", ".join(sorted(n for n in symbols if n.lower().startswith(name[:2].lower()))[:6])
        raise SymLibError(
            f"sembol bulunamadi: {name!r} ({path.name})"
            + (f" (benzerleri: {near})" if near else "")
        )

    extends_node = child(node, "extends")
    extends = str(extends_node[1]).strip('"') if extends_node and len(extends_node) > 1 else None

    props = _properties_of(node)
    pins = _pins_of(node)
    if extends:
        parent = symbols.get(extends)
        if parent is None:
            raise SymLibError(f"{name} sembolu {extends!r} sembolunu genisletiyor ama o yok")
        parent_props = _properties_of(parent)
        parent_props.update(props)  # turevin ozellikleri ustun
        props = parent_props
        pins = _pins_of(parent)  # pin/grafik ustunden gelir

    return LibSymbol(
        lib_id=lib_id,
        name=name,
        library=nickname,
        path=path,
        node=node,
        properties=props,
        pins=pins,
        extends=extends,
    )


def resolve_definition(symbol: LibSymbol) -> list:
    """`lib_symbols` bolumune konacak tam tanim.

    KiCad dosya icine yazarken sembolu `Kutuphane:Ad` adiyla ve `extends`
    COZULMUS halde saklar - dosyanin kutuphaneye bagimli kalmamasi icin.
    """
    node = _deep_copy(symbol.node)
    if symbol.extends:
        parent = load_library(symbol.path).get(symbol.extends)
        if parent is None:
            raise SymLibError(f"{symbol.name}: ust sembol {symbol.extends!r} bulunamadi")
        merged = _deep_copy(parent)
        merged[1] = f'"{symbol.library}:{symbol.name}"'
        # Turevin ozellikleri ust sembolun ozelliklerini ezer
        own = {k: v for k, v in _properties_of(symbol.node).items()}
        merged = [n for n in merged
                  if not (isinstance(n, list) and head(n) == "property"
                          and str(n[1]).strip('"') in own)]
        merged.extend(_deep_copy(p) for p in children(symbol.node, "property"))
        return merged

    node[1] = f'"{symbol.library}:{symbol.name}"'
    return [n for n in node if not (isinstance(n, list) and head(n) == "extends")]


def _deep_copy(node):
    if isinstance(node, list):
        return [_deep_copy(n) for n in node]
    return node
