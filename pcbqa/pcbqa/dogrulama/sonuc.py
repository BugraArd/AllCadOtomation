"""Seviye sonucu ve bulgu yardimcilari."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..rules import Finding


@dataclass
class SeviyeSonucu:
    seviye: int
    ad: str
    bulgular: list[Finding] = field(default_factory=list)
    calisti: bool = True
    atlanma_nedeni: str = ""
    # Seviyeye ozgu ek bilgi: dosya yollari, olcumler, benzetim sonuclari
    ekler: dict[str, Any] = field(default_factory=dict)

    def sayi(self, severity: str) -> int:
        return sum(1 for f in self.bulgular if f.severity == severity)

    @property
    def gecti(self) -> bool | None:
        """Hata yoksa True; calismadiysa None (gecti DEMEK DEGIL)."""
        if not self.calisti:
            return None
        return self.sayi("error") == 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "seviye": self.seviye,
            "ad": self.ad,
            "calisti": self.calisti,
            "atlanma_nedeni": self.atlanma_nedeni,
            "gecti": self.gecti,
            "sayilar": {s: self.sayi(s) for s in ("error", "warning", "info")},
            "bulgular": [f.as_dict() for f in self.bulgular],
            "ekler": self.ekler,
        }


def bulgu(
    rule_id: str,
    severity: str,
    message: str,
    *,
    source: str,
    refs: list[str] | None = None,
    pins: list[str] | None = None,
    measured: float | None = None,
    limit: float | None = None,
    rule_type: str = "",
) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        message=message,
        source=source,
        refs=list(refs or []),
        pins=list(pins or []),
        measured=measured,
        limit=limit,
        rule_type=rule_type or rule_id,
    )


def eksik_bulgu(kontrol: str, neden: str, *, source: str, refs: list[str] | None = None) -> Finding:
    """Bir kontrolun bilgi eksikligi yuzunden YAPILAMADIGINI bildirir.

    'Sorun yok' ile 'bakilamadi' ayni sey degildir; ikincisi sessiz kalirsa
    kullanici gecti sanar.
    """
    return bulgu(f"{kontrol}-eksik-bilgi", "info",
                 f"{kontrol}: denetlenemedi - {neden}", source=source, refs=refs,
                 rule_type="eksik-bilgi")
