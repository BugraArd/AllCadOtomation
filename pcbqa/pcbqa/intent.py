"""Niyet beyani -> bilesen/baglanti plani (Evre 3a, uretken tasarim).

Kullanici devreyi PARCA listesiyle degil NIYETLE soyler: "STM32F103 + USB +
3V3 LDO + kristal". Bu modul o beyani sablon kutuphanesinden gecirip somut
bir insa planina acar: hangi semboller, hangi degerlerle, hangi aglara.
Plani fiilen sematige donusturen surucu AYRI bir adimdir; buradaki cikti
`sch_add.add_symbols(connect=...)` cagrilarinin girdisiyle ayni dildedir
(pin = ag adi).

## Sablon (pcbqa/templates/*.yaml)

Bir sablon tek bir devre blogudur: MCU cekirdegi, LDO, kristal... Icinde
bilesenler ve pin baglantilari durur. Degerlerin KAYNAGI yorumda yazilir
(or. AN2586'nin decoupling recetesi) - kural dosyalarindaki gelenek burada
da gecerli: uydurma sayi yazilmaz, kaynaksiz olan "muhendislik secimi" diye
etiketlenir.

## Yetenek modeli (provides / requires / interfaces)

Bloklar birbirini AG ADI uzerinden bulur (3V3, HSE_IN, SWDIO...). Iki
mekanizma bunu guvenli kilar:

  * `requires` karsilanmayan blok PLANI DUSURUR - "LDO yok ama MCU 3V3
    bekliyor" sessizce bos bir ag olarak kalmaz, engel uretir.
  * `interfaces` yalnizca ISTENDIGINDE aktiflesir: MCU sablonu PD0/PD1'i
    ancak kristal blogu `hse-pinleri` istedigi zaman etiketler. Aksi halde
    her MCU pini kosulsuz etiketlenir ve kristalsiz kartta tek pinli ag
    coplugu olusurdu.

## Sessiz hata dersi (6 ornek oldu - bkz. HANDOFF)

Cozumlemeyen her sey GORUNUR: bilinmeyen sablon adi, yazim hatali param,
sembolde olmayan pin adi, kutuphanede olmayan footprint - hepsi `problems`
listesine duser ve CLI cikis kodu 1 olur. "Olmayan pini atla" yoktur.

Ana giris: `plan_from_file(niyet.yaml)`, CLI: `python -m pcbqa.intent`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .confload import ConfigError, load_config
from . import symlib

TEMPLATES_DIR = Path(__file__).parent / "templates"

# ${param} referansi
_VAR = re.compile(r"\$\{([A-Za-z0-9_]+)\}")


class IntentError(RuntimeError):
    """Niyet ya da sablon dosyasi okunamadi / bicimi bozuk.

    Bicim hatasi (yanlis anahtar, eksik alan) ile plan engeli (karsilanmayan
    gereksinim) ayridir: ilki dosya duzeltilmeden hicbir sey yapilamaz demek,
    aninda atilir; ikincisi planin icinde `problems` olarak birikir ki
    kullanici hepsini tek seferde gorsun.
    """


# --------------------------------------------------------------------------
# Sablon
# --------------------------------------------------------------------------


@dataclass
class TemplateComponent:
    """Sablondaki tek bir bilesen kalemi."""

    name: str  # sablon ici ad ("mcu", "vdd-decoupling")
    lib_id: str  # "Device:C"
    value: str  # "100nF" ya da "${load}"
    footprint: str
    count: int = 1
    # pin anahtari -> ag adi. Anahtar "#3" ise pin NUMARASI, degilse pin ADI
    # (ayni ada sahip TUM pinler baglanir - STM32'nin uc VDD pini gibi).
    connect: dict[str, str] = field(default_factory=dict)


@dataclass
class Template:
    """Tek bir devre blogu sablonu."""

    id: str
    path: Path
    description: str = ""
    provides: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    params: dict[str, str] = field(default_factory=dict)
    components: list[TemplateComponent] = field(default_factory=list)
    # arayuz adi -> {bilesen adi -> {pin anahtari -> ag}}
    interfaces: dict[str, dict[str, dict[str, str]]] = field(default_factory=dict)

    @property
    def effective_provides(self) -> list[str]:
        """Acikca beyan edilenler + arayuz adlari.

        Bir arayuz tanimlamak onu saglamak demektir; ayrica `provides`a
        yazdirmak cift kayit olurdu ve iki liste ayrisirdi.
        """
        return list(self.provides) + [i for i in self.interfaces if i not in self.provides]


_TEMPLATE_KEYS = {"version", "id", "description", "provides", "requires",
                  "params", "components", "interfaces"}
_COMPONENT_KEYS = {"name", "lib_id", "value", "footprint", "count", "connect"}


def _check_keys(data: dict, allowed: set[str], where: str) -> None:
    """Bilinmeyen anahtar = buyuk olasilikla yazim hatasi; sessizce yutulmaz."""
    unknown = set(data) - allowed
    if unknown:
        raise IntentError(
            f"{where}: bilinmeyen anahtar(lar): {', '.join(sorted(unknown))} "
            f"(gecerli: {', '.join(sorted(allowed))})"
        )


def _str_map(data, where: str) -> dict[str, str]:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise IntentError(f"{where}: eslesme (anahtar: deger) bekleniyordu")
    return {str(k): str(v) for k, v in data.items()}


def read_template(path: Path) -> Template:
    """Tek bir sablon dosyasini okur ve bicimini dogrular."""
    try:
        data, _ = load_config(path)
    except ConfigError as exc:
        raise IntentError(f"sablon okunamadi: {exc}") from exc
    if not data:
        raise IntentError(f"{path.name}: sablon bos")
    _check_keys(data, _TEMPLATE_KEYS, path.name)
    if data.get("version") != 1:
        raise IntentError(f"{path.name}: version: 1 bekleniyor ({data.get('version')!r} bulundu)")
    tpl_id = str(data.get("id") or "").strip()
    if not tpl_id:
        raise IntentError(f"{path.name}: id alani zorunlu")

    components: list[TemplateComponent] = []
    for i, raw in enumerate(data.get("components") or []):
        if not isinstance(raw, dict):
            raise IntentError(f"{path.name}: components[{i}] bir eslesme olmali")
        _check_keys(raw, _COMPONENT_KEYS, f"{path.name}: components[{i}]")
        name = str(raw.get("name") or "").strip()
        lib_id = str(raw.get("lib_id") or "").strip()
        if not name or not lib_id:
            raise IntentError(f"{path.name}: components[{i}]: name ve lib_id zorunlu")
        count = raw.get("count", 1)
        if not isinstance(count, int) or count < 1:
            raise IntentError(f"{path.name}: {name}: count pozitif tam sayi olmali")
        components.append(TemplateComponent(
            name=name,
            lib_id=lib_id,
            value=str(raw.get("value") or ""),
            footprint=str(raw.get("footprint") or ""),
            count=count,
            connect=_str_map(raw.get("connect"), f"{path.name}: {name}.connect"),
        ))
    if not components:
        raise IntentError(f"{path.name}: sablonda en az bir bilesen olmali")

    names = [c.name for c in components]
    if len(names) != len(set(names)):
        raise IntentError(f"{path.name}: bilesen adlari benzersiz olmali")

    interfaces: dict[str, dict[str, dict[str, str]]] = {}
    for iface, targets in (data.get("interfaces") or {}).items():
        if not isinstance(targets, dict):
            raise IntentError(f"{path.name}: interfaces.{iface} bir eslesme olmali")
        interfaces[str(iface)] = {}
        for comp_name, conns in targets.items():
            if str(comp_name) not in names:
                raise IntentError(
                    f"{path.name}: interfaces.{iface}: {comp_name!r} adinda bilesen yok"
                )
            interfaces[str(iface)][str(comp_name)] = _str_map(
                conns, f"{path.name}: interfaces.{iface}.{comp_name}"
            )

    return Template(
        id=tpl_id,
        path=path,
        description=str(data.get("description") or ""),
        provides=[str(p) for p in (data.get("provides") or [])],
        requires=[str(r) for r in (data.get("requires") or [])],
        params=_str_map(data.get("params"), f"{path.name}: params"),
        components=components,
        interfaces=interfaces,
    )


def load_templates(folder: Path | None = None) -> dict[str, Template]:
    """Klasordeki tum sablonlar: id -> Template."""
    folder = folder or TEMPLATES_DIR
    if not folder.is_dir():
        raise IntentError(f"sablon klasoru yok: {folder}")
    out: dict[str, Template] = {}
    for path in sorted(folder.glob("*.yaml")):
        tpl = read_template(path)
        if tpl.id in out:
            raise IntentError(
                f"sablon kimligi cakisiyor: {tpl.id!r} "
                f"({out[tpl.id].path.name} ve {path.name})"
            )
        out[tpl.id] = tpl
    if not out:
        raise IntentError(f"sablon klasoru bos: {folder}")
    return out


# --------------------------------------------------------------------------
# Niyet
# --------------------------------------------------------------------------


@dataclass
class IntentBlock:
    template: str
    params: dict[str, str] = field(default_factory=dict)


@dataclass
class Intent:
    name: str
    blocks: list[IntentBlock]
    path: Path | None = None


_INTENT_KEYS = {"version", "name", "blocks"}
_BLOCK_KEYS = {"template", "params"}


def read_intent(path: Path) -> Intent:
    """Niyet beyanini okur ve bicimini dogrular."""
    try:
        data, _ = load_config(Path(path))
    except ConfigError as exc:
        raise IntentError(f"niyet dosyasi okunamadi: {exc}") from exc
    if not data:
        raise IntentError(f"{Path(path).name}: niyet dosyasi bos")
    _check_keys(data, _INTENT_KEYS, Path(path).name)
    if data.get("version") != 1:
        raise IntentError(
            f"{Path(path).name}: version: 1 bekleniyor ({data.get('version')!r} bulundu)"
        )

    blocks: list[IntentBlock] = []
    raw_blocks = data.get("blocks")
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise IntentError(f"{Path(path).name}: blocks bos olmayan bir liste olmali")
    for i, raw in enumerate(raw_blocks):
        if isinstance(raw, str):
            # kisa bicim:  - mcu-stm32f103c8
            blocks.append(IntentBlock(template=raw.strip()))
            continue
        if not isinstance(raw, dict):
            raise IntentError(f"{Path(path).name}: blocks[{i}] ad ya da eslesme olmali")
        _check_keys(raw, _BLOCK_KEYS, f"{Path(path).name}: blocks[{i}]")
        tpl = str(raw.get("template") or "").strip()
        if not tpl:
            raise IntentError(f"{Path(path).name}: blocks[{i}]: template alani zorunlu")
        blocks.append(IntentBlock(
            template=tpl,
            params=_str_map(raw.get("params"), f"{Path(path).name}: blocks[{i}].params"),
        ))

    name = str(data.get("name") or "").strip() or Path(path).stem
    return Intent(name=name, blocks=blocks, path=Path(path))


# --------------------------------------------------------------------------
# Acilim: niyet + sablonlar -> insa plani
# --------------------------------------------------------------------------


@dataclass
class PlannedComponent:
    """Plandaki tek bir somut bilesen.

    Referans numarasi (C1, C2...) BURADA verilmez - o `sch_add`in isidir
    (numaralar mevcut sematige gore atanir). `label` yalnizca plan icinde
    konusabilmek icin: "mcu-stm32f103c8/vdd-decoupling.2".
    """

    label: str
    template_id: str
    lib_id: str
    value: str
    footprint: str
    connect: list[tuple[str, str]] = field(default_factory=list)  # (pin anahtari, ag)
    # Cozumleme sonrasi doldurulur: (pin numarasi, ag)
    pin_connect: list[tuple[str, str]] = field(default_factory=list)
    ref_prefix: str = ""


@dataclass
class BuildPlan:
    """Niyetin acilmis hali - yazilabilir, gosterilebilir, sorgulanabilir."""

    name: str
    blocks: list[str] = field(default_factory=list)
    components: list[PlannedComponent] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    resolved: bool = False

    @property
    def ok(self) -> bool:
        return not self.problems and bool(self.components)

    def nets(self) -> dict[str, list[tuple[str, str]]]:
        """Ag adi -> [(bilesen etiketi, pin anahtari)].

        Cozumlemeden once pin anahtarlari, sonra pin numaralari kullanilir -
        cozumlenmis plan sematik uretimi icin dogrudan kullanilabilir olsun.
        """
        out: dict[str, list[tuple[str, str]]] = {}
        for comp in self.components:
            pairs = comp.pin_connect if self.resolved else comp.connect
            for pin, net in pairs:
                out.setdefault(net, []).append((comp.label, pin))
        return out

    def describe(self) -> str:
        lines = [f"plan: {self.name}  ({len(self.components)} bilesen, "
                 f"{len(self.nets())} ag)"]
        lines.append("  bloklar: " + ", ".join(self.blocks))
        for comp in self.components:
            head = f"  {comp.label:<40} {comp.lib_id}"
            if comp.value:
                head += f"  [{comp.value}]"
            lines.append(head)
            pairs = comp.pin_connect if self.resolved else comp.connect
            for pin, net in pairs:
                lines.append(f"    {pin} -> {net}")
        for net, pins in sorted(self.nets().items()):
            if len(pins) < 2:
                lines.append(f"  tek pinli ag: {net} ({pins[0][0]}.{pins[0][1]})")
        for note in self.notes:
            lines.append(f"  not: {note}")
        for problem in self.problems:
            lines.append(f"  ENGEL: {problem}")
        return "\n".join(lines)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "blocks": list(self.blocks),
            "resolved": self.resolved,
            "components": [
                {
                    "label": c.label,
                    "template": c.template_id,
                    "lib_id": c.lib_id,
                    "value": c.value,
                    "footprint": c.footprint,
                    "ref_prefix": c.ref_prefix,
                    "connect": [list(p) for p in c.connect],
                    "pin_connect": [list(p) for p in c.pin_connect],
                }
                for c in self.components
            ],
            "nets": {net: [list(p) for p in pins] for net, pins in self.nets().items()},
            "notes": list(self.notes),
            "problems": list(self.problems),
        }


def _substitute(text: str, params: dict[str, str], used: set[str],
                problems: list[str], where: str) -> str:
    """${param} referanslarini cozer; bilinmeyeni engel yapar."""

    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name in params:
            used.add(name)
            return params[name]
        problems.append(f"{where}: tanimsiz parametre ${{{name}}}")
        return m.group(0)

    return _VAR.sub(repl, text)


def expand_intent(intent: Intent, templates: dict[str, Template]) -> BuildPlan:
    """Niyeti plana acar. Kutuphaneye DOKUNMAZ (onu `resolve_plan` yapar)."""
    plan = BuildPlan(name=intent.name)

    # 1) Sablonlari bul; ayni sablonun tekrarini reddet (net adlari cakisir).
    chosen: list[tuple[IntentBlock, Template]] = []
    seen: set[str] = set()
    for block in intent.blocks:
        tpl = templates.get(block.template)
        if tpl is None:
            near = ", ".join(sorted(templates))
            plan.problems.append(
                f"sablon bulunamadi: {block.template!r} (eldekiler: {near})"
            )
            continue
        if tpl.id in seen:
            plan.problems.append(
                f"sablon iki kez istenmis: {tpl.id!r} - ayni ag adlarini iki blok "
                "birden surer; simdilik desteklenmiyor"
            )
            continue
        seen.add(tpl.id)
        chosen.append((block, tpl))
        plan.blocks.append(tpl.id)

    # 2) Yetenek denetimi: her `requires` bir baska bloktan karsilanmali.
    provided: dict[str, list[str]] = {}
    for _, tpl in chosen:
        for cap in tpl.effective_provides:
            provided.setdefault(cap, []).append(tpl.id)
    for cap, sources in provided.items():
        if len(sources) > 1:
            plan.notes.append(
                f"{cap!r} yetenegini birden fazla blok sagliyor: {', '.join(sources)}"
            )
    required: set[str] = set()
    for _, tpl in chosen:
        for cap in tpl.requires:
            required.add(cap)
            if cap not in provided:
                candidates = sorted(
                    t.id for t in templates.values() if cap in t.effective_provides
                )
                plan.problems.append(
                    f"{tpl.id}: {cap!r} gereksinimi karsilanmiyor"
                    + (f" (saglayabilecek sablonlar: {', '.join(candidates)})"
                       if candidates else "")
                )

    # 3) Bilesenleri uret. Arayuz baglantilari yalnizca ISTENEN arayuzler icin.
    for block, tpl in chosen:
        params = dict(tpl.params)
        unknown = set(block.params) - set(tpl.params)
        if unknown:
            plan.problems.append(
                f"{tpl.id}: sablonda olmayan parametre(ler): "
                f"{', '.join(sorted(unknown))} (gecerli: "
                f"{', '.join(sorted(tpl.params)) or 'yok'})"
            )
        params.update({k: v for k, v in block.params.items() if k in tpl.params})
        used: set[str] = set()

        # Aktif arayuzlerin ek baglantilari, bilesen adina gore
        extra: dict[str, dict[str, str]] = {}
        for iface, targets in tpl.interfaces.items():
            if iface not in required:
                continue
            for comp_name, conns in targets.items():
                extra.setdefault(comp_name, {}).update(conns)

        for comp in tpl.components:
            conns = dict(comp.connect)
            conns.update(extra.get(comp.name, {}))
            where = f"{tpl.id}/{comp.name}"
            value = _substitute(comp.value, params, used, plan.problems, where)
            resolved_conns = [
                (pin, _substitute(net, params, used, plan.problems, f"{where}.{pin}"))
                for pin, net in conns.items()
            ]
            for i in range(comp.count):
                label = where if comp.count == 1 else f"{where}.{i + 1}"
                plan.components.append(PlannedComponent(
                    label=label,
                    template_id=tpl.id,
                    lib_id=comp.lib_id,
                    value=value,
                    footprint=comp.footprint,
                    connect=list(resolved_conns),
                ))

        # Kullanicinin gecersiz kildigi ama hicbir yerde kullanilmayan param
        # gorunur olmali - or. i2c blogu yokken `scl` vermek bosa gider.
        # Sablonun KENDI varsayilanlari icin ayni not gurultu olurdu: aktif
        # olmayan her arayuzun ag adi "kullanilmadi" diye bagirirdi.
        idle = (set(block.params) & set(tpl.params)) - used
        if idle:
            plan.notes.append(
                f"{tpl.id}: verilen parametre(ler) hicbir baglantida kullanilmadi: "
                f"{', '.join(sorted(idle))}"
            )

    return plan


# --------------------------------------------------------------------------
# Cozumleme: plan + KiCad kutuphanesi -> pin numaralari
# --------------------------------------------------------------------------


def resolve_plan(
    plan: BuildPlan,
    project_dir: Path | None = None,
    kicad_cli: str | None = None,
) -> BuildPlan:
    """Pin anahtarlarini kurulu KiCad kutuphanesine karsi cozer.

    "#3" pin numarasidir; diger her anahtar pin ADI olarak aranir ve ayni
    ada sahip TUM pinler baglanir (STM32'nin uc VDD pini tek satirla). Adi
    bulunamayan pin, olmayan footprint, baglanmamis power_in pini - hepsi
    engel. Plan yerinde guncellenir ve ayni nesne dondurulur.
    """
    cache: dict[str, symlib.LibSymbol | None] = {}
    for comp in plan.components:
        if comp.lib_id not in cache:
            try:
                cache[comp.lib_id] = symlib.get_symbol(
                    comp.lib_id, project_dir=project_dir, kicad_cli=kicad_cli
                )
            except symlib.SymLibError as exc:
                cache[comp.lib_id] = None
                plan.problems.append(f"{comp.label}: {exc}")
        symbol = cache[comp.lib_id]
        if symbol is None:
            continue
        comp.ref_prefix = symbol.reference_prefix

        by_number = {p.number: p for p in symbol.pins}
        by_name: dict[str, list[str]] = {}
        for p in symbol.pins:
            if p.name and p.name != "~":
                by_name.setdefault(p.name, []).append(p.number)

        comp.pin_connect = []
        connected: set[str] = set()
        for key, net in comp.connect:
            if key.startswith("#"):
                number = key[1:]
                if number not in by_number:
                    plan.problems.append(
                        f"{comp.label}: {comp.lib_id} sembolunde {number!r} numarali "
                        f"pin yok (pinler: {', '.join(sorted(by_number))})"
                    )
                    continue
                comp.pin_connect.append((number, net))
                connected.add(number)
            else:
                numbers = by_name.get(key)
                if not numbers:
                    near = ", ".join(sorted(by_name)[:8])
                    plan.problems.append(
                        f"{comp.label}: {comp.lib_id} sembolunde {key!r} adli pin yok"
                        + (f" (adlar: {near}...)" if near else "")
                    )
                    continue
                for number in numbers:
                    comp.pin_connect.append((number, net))
                    connected.add(number)

        # Baglanmamis guc girisi = calismayan devre. Sablon yazarken en kolay
        # kacan hata bu; kutuphane sembolu elektriksel tipi zaten biliyor.
        for p in symbol.pins:
            if p.electrical == "power_in" and p.number not in connected:
                plan.problems.append(
                    f"{comp.label}: guc girisi pini baglanmamis: "
                    f"{p.number} ({p.name or 'adsiz'})"
                )

        if comp.footprint and not symlib.footprint_exists(
            comp.footprint, project_dir, kicad_cli
        ):
            plan.problems.append(
                f"{comp.label}: footprint bulunamadi: {comp.footprint}"
            )

    plan.resolved = True
    return plan


def plan_from_file(
    intent_path: Path,
    templates_dir: Path | None = None,
    resolve: bool = True,
    project_dir: Path | None = None,
    kicad_cli: str | None = None,
) -> BuildPlan:
    """Niyet dosyasindan tek adimda plan."""
    intent = read_intent(Path(intent_path))
    plan = expand_intent(intent, load_templates(templates_dir))
    if resolve:
        resolve_plan(plan, project_dir=project_dir, kicad_cli=kicad_cli)
    return plan


# --------------------------------------------------------------------------
# Komut satiri
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pcbqa.intent",
        description="Niyet beyanini (YAML) sablon kutuphanesiyle insa planina acar.",
    )
    ap.add_argument("--intent", type=Path, default=None, help="Niyet dosyasi (YAML)")
    ap.add_argument("--templates", type=Path, default=None,
                    help=f"Sablon klasoru (varsayilan: {TEMPLATES_DIR})")
    ap.add_argument("--list", action="store_true", help="Sablonlari listele ve cik")
    ap.add_argument("--no-resolve", action="store_true",
                    help="KiCad kutuphanesine karsi pin cozumlemesini atla")
    ap.add_argument("--json", type=Path, default=None, help="Plani JSON olarak da yaz")
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    try:
        if args.list:
            templates = load_templates(args.templates)
            for tpl in templates.values():
                caps = ", ".join(tpl.effective_provides) or "-"
                needs = ", ".join(tpl.requires) or "-"
                print(f"{tpl.id:<24} {tpl.description}")
                print(f"{'':<24} saglar: {caps} | ister: {needs}")
            return 0

        if args.intent is None:
            print("hata: --intent ya da --list gerekli", file=sys.stderr)
            return 2

        plan = plan_from_file(
            args.intent, templates_dir=args.templates, resolve=not args.no_resolve
        )
    except IntentError as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2

    print(plan.describe())
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(plan.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"JSON plan: {args.json}")
    return 0 if plan.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
