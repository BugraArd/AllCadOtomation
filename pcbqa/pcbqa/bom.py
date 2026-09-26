"""Kaynakli BOM manifesti ve uretim oncesi acik kalem kapisi.

Bu modul fiyat/stok uydurmaz. Bir MPN ancak kaynagi ve ureticisiyle birlikte
``verified`` olarak isaretlenebilir; diger kalemler acik olarak raporlanir.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .confload import ConfigError, load_config


class BomError(ValueError):
    """BOM manifesti sozlesmeye uymuyor."""


ITEM_STATUSES = {"verified", "needs_selection", "blocked", "synthetic"}
MANIFEST_STATUSES = {"draft", "review", "accepted"}


@dataclass(frozen=True)
class BomItem:
    item_id: str
    template: str
    value: str
    footprint: str
    status: str
    mpn: str | None = None
    manufacturer: str | None = None
    source: str | None = None
    evidence: str | None = None
    notes: str | None = None

    @property
    def verified(self) -> bool:
        return self.status == "verified"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["verified"] = self.verified
        return data


@dataclass(frozen=True)
class BomManifest:
    version: int
    profile: str
    status: str
    items: tuple[BomItem, ...] = field(default_factory=tuple)

    @property
    def open_items(self) -> tuple[BomItem, ...]:
        return tuple(item for item in self.items if not item.verified)

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "profile": self.profile,
            "status": self.status,
            "items": [item.as_dict() for item in self.items],
            "summary": {
                "total": len(self.items),
                "verified": len(self.items) - len(self.open_items),
                "open": len(self.open_items),
            },
        }


def _text(data: dict[str, Any], key: str, *, required: bool = True) -> str | None:
    value = data.get(key)
    if value is None or str(value).strip() == "":
        if required:
            raise BomError(f"{key} alani zorunlu")
        return None
    return str(value).strip()


def load_manifest(path: Path) -> BomManifest:
    try:
        data, _runtime = load_config(Path(path))
    except ConfigError as exc:
        raise BomError(f"BOM okunamadi: {exc}") from exc
    if not isinstance(data, dict):
        raise BomError("BOM kok nesnesi bir mapping olmali")
    if data.get("version") != 1:
        raise BomError(f"BOM version: 1 bekleniyor ({data.get('version')!r})")

    profile = _text(data, "profile")
    status = _text(data, "status")
    if status not in MANIFEST_STATUSES:
        raise BomError(f"gecersiz BOM durumu: {status!r}")

    raw_items = data.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise BomError("items bos olmayan bir liste olmali")

    items: list[BomItem] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            raise BomError(f"items[{index}] bir mapping olmali")
        prefix = f"items[{index}]"
        item_id = _text(raw, "id")
        assert item_id is not None
        if item_id in seen:
            raise BomError(f"tekrar eden BOM kalemi: {item_id}")
        seen.add(item_id)
        template = _text(raw, "template")
        value = _text(raw, "value")
        footprint = _text(raw, "footprint")
        item_status = _text(raw, "status")
        assert template is not None
        assert value is not None
        assert footprint is not None
        assert item_status is not None
        if item_status not in ITEM_STATUSES:
            raise BomError(f"{prefix}.status gecersiz: {item_status!r}")

        mpn = _text(raw, "mpn", required=False)
        manufacturer = _text(raw, "manufacturer", required=False)
        source = _text(raw, "source", required=False)
        evidence = _text(raw, "evidence", required=False)
        notes = _text(raw, "notes", required=False)
        if item_status == "verified" and not all((mpn, manufacturer, source)):
            raise BomError(
                f"{prefix} verified ise mpn, manufacturer ve source zorunlu"
            )
        items.append(BomItem(
            item_id=item_id,
            template=template,
            value=value,
            footprint=footprint,
            status=item_status,
            mpn=mpn,
            manufacturer=manufacturer,
            source=source,
            evidence=evidence,
            notes=notes,
        ))

    return BomManifest(1, profile, status, tuple(items))


def render(manifest: BomManifest) -> str:
    lines = [
        "BOM KAYNAK RAPORU",
        "-----------------",
        f"profil : {manifest.profile}",
        f"durum  : {manifest.status}",
        f"kalem  : {len(manifest.items)} toplam / "
        f"{len(manifest.open_items)} acik",
        "",
        "ID | DURUM | DEGER | MPN | KAYNAK",
        "-" * 88,
    ]
    for item in manifest.items:
        lines.append(
            f"{item.item_id} | {item.status} | {item.value} | "
            f"{item.mpn or '-'} | {item.source or '-'}"
        )
        if item.notes:
            lines.append(f"  not: {item.notes}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pcbqa.bom",
        description="Kaynakli BOM raporu; sentetik ve secilmemis kalemleri ayirir",
    )
    parser.add_argument("manifest", type=Path, help="BOM manifesti (YAML veya JSON)")
    parser.add_argument("--json", type=Path, default=None, help="Rapor JSON yolu")
    parser.add_argument(
        "--fail-on-open",
        action="store_true",
        help="verified olmayan kalem varsa 1 don",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        print(render(manifest))
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(
                json.dumps(manifest.as_dict(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"JSON rapor: {args.json}")
        if args.fail_on_open and manifest.open_items:
            print(
                f"hata: {len(manifest.open_items)} BOM kalemi verified degil",
                file=sys.stderr,
            )
            return 1
        return 0
    except (BomError, ConfigError, OSError, ValueError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
