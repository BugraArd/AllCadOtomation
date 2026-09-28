"""Donanim gereksinim sozlesmesi ve acik karar kapisi.

Bu modul elektriksel veya mekanik deger tahmin etmez. Kullanici kararlarini
tek bir manifestte toplar; ``decided`` olmayan kararlar raporda acik kalir ve
``--fail-on-open`` ile uretim oncesi kapisi olarak kullanilabilir.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .confload import ConfigError, load_config


class RequirementsError(ValueError):
    """Gereksinim sozlesmesi bicim veya kabul kurallarina uymuyor."""


CONTRACT_STATUSES = {"draft", "review", "accepted"}
DECISION_STATUSES = {"open", "decided", "not_applicable", "blocked"}

# Bu liste, devir raporunda kullanicidan beklenen P0 kararlarinin makinece
# izlenebilir karsiligidir. Yeni bir karar eklemek bilincli bir sema degisikligi
# olmali; yazim hatasi sessizce kabul edilmemelidir.
REQUIRED_DECISIONS = (
    "input_supply",
    "current_budget",
    "interfaces",
    "gpio_and_peripherals",
    "mechanical_and_manufacturing",
    "temperature_and_package",
)

DECISION_LABELS = {
    "input_supply": "Giris beslemesi",
    "current_budget": "Akım bütçesi",
    "interfaces": "Zorunlu arayüzler",
    "gpio_and_peripherals": "GPIO ve çevre birimleri",
    "mechanical_and_manufacturing": "Mekanik ve üretim",
    "temperature_and_package": "Sıcaklık ve MCU paketi",
}

ROOT_KEYS = {"version", "profile", "status", "decisions", "notes"}
DECISION_KEYS = {"id", "status", "value", "source", "evidence", "notes"}


@dataclass(frozen=True)
class RequirementDecision:
    decision_id: str
    status: str
    value: Any = None
    source: str | None = None
    evidence: str | None = None
    notes: str | None = None

    @property
    def label(self) -> str:
        return DECISION_LABELS.get(self.decision_id, self.decision_id)

    @property
    def closed(self) -> bool:
        return self.status in {"decided", "not_applicable"}

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["label"] = self.label
        data["closed"] = self.closed
        return data


@dataclass(frozen=True)
class RequirementsContract:
    version: int
    profile: str
    status: str
    decisions: tuple[RequirementDecision, ...] = field(default_factory=tuple)
    notes: str | None = None

    @property
    def open_decisions(self) -> tuple[RequirementDecision, ...]:
        return tuple(decision for decision in self.decisions if not decision.closed)

    @property
    def accepted(self) -> bool:
        return self.status == "accepted" and not self.open_decisions

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "profile": self.profile,
            "status": self.status,
            "notes": self.notes,
            "decisions": [decision.as_dict() for decision in self.decisions],
            "summary": {
                "total": len(self.decisions),
                "closed": len(self.decisions) - len(self.open_decisions),
                "open": len(self.open_decisions),
            },
        }


def _check_keys(data: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise RequirementsError(
            f"{where}: bilinmeyen anahtar(lar): {', '.join(sorted(unknown))}"
        )


def _text(data: dict[str, Any], key: str, *, required: bool = True) -> str | None:
    value = data.get(key)
    if value is None or str(value).strip() == "":
        if required:
            raise RequirementsError(f"{key} alani zorunlu")
        return None
    return str(value).strip()


def _has_value(value: Any) -> bool:
    """False gibi gecerli karar degerlerini bos degerden ayirir."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def load_contract(path: Path) -> RequirementsContract:
    try:
        data, _runtime = load_config(Path(path))
    except ConfigError as exc:
        raise RequirementsError(f"gereksinim dosyasi okunamadi: {exc}") from exc
    if not isinstance(data, dict):
        raise RequirementsError("gereksinim kok nesnesi bir mapping olmali")
    _check_keys(data, ROOT_KEYS, Path(path).name)
    if data.get("version") != 1:
        raise RequirementsError(
            f"version: 1 bekleniyor ({data.get('version')!r} bulundu)"
        )

    profile = _text(data, "profile")
    status = _text(data, "status")
    assert profile is not None
    assert status is not None
    if status not in CONTRACT_STATUSES:
        raise RequirementsError(f"gecersiz sozlesme durumu: {status!r}")

    raw_decisions = data.get("decisions")
    if not isinstance(raw_decisions, list) or not raw_decisions:
        raise RequirementsError("decisions bos olmayan bir liste olmali")

    decisions: list[RequirementDecision] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_decisions):
        if not isinstance(raw, dict):
            raise RequirementsError(f"decisions[{index}] bir mapping olmali")
        where = f"decisions[{index}]"
        _check_keys(raw, DECISION_KEYS, where)
        decision_id = _text(raw, "id")
        decision_status = _text(raw, "status")
        assert decision_id is not None
        assert decision_status is not None
        if decision_id not in REQUIRED_DECISIONS:
            raise RequirementsError(f"{where}.id bilinmiyor: {decision_id!r}")
        if decision_id in seen:
            raise RequirementsError(f"tekrar eden karar: {decision_id}")
        seen.add(decision_id)
        if decision_status not in DECISION_STATUSES:
            raise RequirementsError(
                f"{where}.status gecersiz: {decision_status!r}"
            )

        value = raw.get("value")
        notes = _text(raw, "notes", required=False)
        if decision_status == "decided" and not _has_value(value):
            raise RequirementsError(
                f"{where}: decided ise value bos olamaz"
            )
        if decision_status in {"blocked", "not_applicable"} and not notes:
            raise RequirementsError(
                f"{where}: {decision_status} karari icin notes zorunlu"
            )
        decisions.append(RequirementDecision(
            decision_id=decision_id,
            status=decision_status,
            value=value,
            source=_text(raw, "source", required=False),
            evidence=_text(raw, "evidence", required=False),
            notes=notes,
        ))

    missing = [key for key in REQUIRED_DECISIONS if key not in seen]
    if missing:
        raise RequirementsError(
            "eksik zorunlu karar(lar): " + ", ".join(missing)
        )
    if status == "accepted" and any(not decision.closed for decision in decisions):
        raise RequirementsError(
            "accepted sozlesmede open veya blocked karar kalamaz"
        )

    return RequirementsContract(
        version=1,
        profile=profile,
        status=status,
        decisions=tuple(decisions),
        notes=_text(data, "notes", required=False),
    )


def _display_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def render(contract: RequirementsContract) -> str:
    lines = [
        "DONANIM GEREKSINIM SOZLESMESI",
        "-----------------------------",
        f"profil : {contract.profile}",
        f"durum  : {contract.status}",
        f"karar  : {len(contract.decisions)} toplam / "
        f"{len(contract.open_decisions)} acik",
        "",
        "ID | DURUM | DEGER",
        "-" * 72,
    ]
    for decision in contract.decisions:
        lines.append(
            f"{decision.decision_id} | {decision.status} | "
            f"{_display_value(decision.value)}"
        )
        if decision.notes:
            lines.append(f"  not: {decision.notes}")
    if contract.notes:
        lines.append(f"not: {contract.notes}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pcbqa.gereksinim",
        description="Donanim gereksinim sozlesmesini raporla ve acik karar kapisini denetle",
    )
    parser.add_argument("contract", type=Path, help="Gereksinim manifesti (YAML veya JSON)")
    parser.add_argument("--json", type=Path, default=None, help="Rapor JSON yolu")
    parser.add_argument(
        "--fail-on-open",
        action="store_true",
        help="decided olmayan karar varsa 1 don",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        contract = load_contract(args.contract)
        print(render(contract))
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(
                json.dumps(contract.as_dict(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"JSON rapor: {args.json}")
        if args.fail_on_open and contract.open_decisions:
            print(
                f"hata: {len(contract.open_decisions)} gereksinim karari acik",
                file=sys.stderr,
            )
            return 1
        return 0
    except (RequirementsError, ConfigError, OSError, ValueError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
