"""Terminal raporu ve skor.

Skor su an basit bir agirlikli ceza toplami. Asama 3'te (otomatik yerlestirme)
bu skor, motorun kuculttugu MALIYET FONKSIYONUNA donusecek; o yuzden burada
uretilen sayilar (HPWL, mesafe ihlalleri) bilerek olculebilir tutuluyor.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass

from .model import Design, Metrics
from .rules import Finding

# Bulgu basina ceza agirligi
PENALTY = {"error": 8.0, "warning": 2.0, "info": 0.0}

# Skor normalizasyonu: kucuk kartlarda tek bir hatanin skoru ucurmamasi icin
# bilesen sayisi bu degerin altina dusmus gibi islenmez.
MIN_COMPONENTS_FOR_SCORE = 20


def penalty_of(finding: Finding) -> float:
    """Bir bulgunun skora yazacagi ceza.

    Kural kendi `weight` degerini verdiyse o gecerlidir; vermediyse severity'den
    turetilir (eski davranis). Boylece agirlik kullanmayan kural dosyalari ve
    disaridan gelen bulgular (KiCad ERC/DRC, sematik kontrolleri) birebir ayni
    skoru uretir.

    `info` HER ZAMAN sifirdir, kuralin agirligi ne olursa olsun. Bunun somut bir
    nedeni var: `max_findings` sinirina takilan kural sentetik bir "...ve N
    benzer bulgu daha" bilgisi uretir ve `trace_width` yonlendirilmemis net icin
    bilgi verir. Agirlik bunlara da uygulansaydi, agirligi 24 olan bir kural
    hicbir ihlal olmadan 24 puan yazdirabilirdi.
    """
    if finding.severity == "info":
        return 0.0
    base = finding.weight if finding.weight is not None else PENALTY.get(finding.severity, 0.0)
    return base * overshoot_factor(finding)


def overshoot_factor(finding: Finding) -> float:
    """Ihlalin BUYUKLUGUNE gore ceza carpani (Faz 1b).

        asim   = |measured - limit| / |limit|
        carpan = min(1 + asim, scale_max)

    Mutlak deger bilincli: bazi kurallarda ihlal `measured > limit` (net
    uzunlugu), bazilarinda `measured < limit` (iz genisligi). Tek ifade ikisini
    de dogru olcer.

    Uc durumda 1.0 doner (yani olcekleme yok):
      * kural `scale` istememis
      * bulgu `measured`/`limit` tasimiyor - `require_on_net` ve `same_net`
        ikili kurallardir, "ne kadar ihlal" diye bir sey yoktur. `scale: true`
        verilse bile sessizce sabit agirliga duser; hata degil.
      * `limit == 0` - `courtyard_overlap`'te `clearance_mm: 0.0` yaygindir ve
        sifira bolmek NaN uretirdi.
    """
    if finding.scale_max is None:
        return 1.0
    if finding.measured is None or finding.limit is None:
        return 1.0
    if finding.limit == 0:
        return 1.0
    overshoot = abs(finding.measured - finding.limit) / abs(finding.limit)
    return min(1.0 + overshoot, finding.scale_max)

_MARK = {"error": "HATA ", "warning": "UYARI", "info": "BILGI"}
_COLOR = {"error": "\033[31m", "warning": "\033[33m", "info": "\033[36m"}
_RESET = "\033[0m"
_DIM = "\033[2m"
_BOLD = "\033[1m"


def enable_ansi() -> bool:
    """Windows konsolunda ANSI renklerini acar. Basarisizsa renkler kapatilir."""
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        # -11 = STD_OUTPUT_HANDLE, 0x4 = ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return bool(kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7))
    except Exception:
        return False


@dataclass
class Report:
    design: Design
    metrics: Metrics
    findings: list[Finding]
    kicad_version: str = ""
    # Asama 4a: sematik okunabildiyse (pcbqa.schematic.Schematic), yoksa None
    schematic: object | None = None

    def count(self, severity: str) -> int:
        return sum(1 for f in self.findings if f.severity == severity)

    @property
    def score(self) -> float:
        """0-100 arasi kalite skoru.

        Ceza, bilesen sayisina bolunerek normalize edilir; boylece 40 bilesenli
        bir kart ile 400 bilesenli bir kartin skorlari karsilastirilabilir olur.
        Ustel egri kullanilir: skor hicbir zaman tam 0'a doymaz, yani 25 hatali
        bir kart ile 60 hatali bir kart hala ayirt edilebilir.
        """
        penalty = sum(penalty_of(f) for f in self.findings)
        if penalty <= 0:
            return 100.0
        size = max(self.metrics.component_count, MIN_COMPONENTS_FOR_SCORE)
        return round(100.0 * math.exp(-penalty / size), 1)

    def as_dict(self) -> dict:
        m = self.metrics
        return {
            "project": self.design.project_name,
            "kicad_version": self.kicad_version,
            "score": round(self.score, 1),
            "counts": {s: self.count(s) for s in ("error", "warning", "info")},
            "metrics": {
                "component_count": m.component_count,
                "placed_count": m.placed_count,
                "net_count": m.net_count,
                "total_hpwl_mm": round(m.total_hpwl_mm, 1),
                "board_area_mm2": round(m.board_area_mm2, 1) if m.board_area_mm2 else None,
                "density_pct": round(m.density_pct, 1) if m.density_pct else None,
                "area_by_side": {k: round(v, 1) for k, v in m.area_by_side.items()},
                "parse_warnings": m.parse_warnings,
                "longest_nets": [[n, round(v, 1)] for n, v in m.longest_nets],
            },
            "findings": [f.as_dict() for f in self.findings],
        }


class Renderer:
    def __init__(self, color: bool = True, width: int = 78) -> None:
        self.color = color
        self.width = width
        self.lines: list[str] = []

    def c(self, text: str, code: str) -> str:
        return f"{code}{text}{_RESET}" if self.color else text

    def rule(self, char: str = "-") -> None:
        self.lines.append(char * self.width)

    def heading(self, text: str) -> None:
        self.lines.append("")
        self.lines.append(self.c(text, _BOLD))
        self.rule()

    def kv(self, key: str, val: str) -> None:
        self.lines.append(f"  {key:<28} {val}")

    def render(self, report: Report) -> str:
        self.lines = []
        d, m = report.design, report.metrics

        self.rule("=")
        self.lines.append(self.c(f"  pcbqa - tasarim kalite raporu", _BOLD))
        self.lines.append(f"  proje       : {d.project_name}")
        self.lines.append(f"  kart        : {d.board.path.name}")
        if report.kicad_version:
            self.lines.append(self.c(f"  kicad-cli   : {report.kicad_version}", _DIM))
        self.rule("=")

        # ------------------------------------------------------------ olcumler
        self.heading("OLCUMLER")
        self.kv("Bilesen (sematik / PCB)", f"{m.component_count} / {m.placed_count}")
        self.kv("Net sayisi", str(m.net_count))
        self.kv("Toplam tahmini tel (HPWL)", f"{m.total_hpwl_mm:,.0f} mm")
        if m.board_area_mm2:
            self.kv("Kart alani", f"{m.board_area_mm2:,.0f} mm2")
        if m.density_pct is not None:
            sides = "/".join(f"{s}:{v:,.0f}" for s, v in sorted(m.area_by_side.items()))
            self.kv("Yerlesim yogunlugu", f"%{m.density_pct:.1f}  (yuz alanlari {sides} mm2)")

        if m.parse_warnings:
            self.lines.append("")
            self.lines.append(
                self.c(
                    f"  DIKKAT: .kicad_pcb dosyasinda {m.parse_warnings} bozuk parantez "
                    "atlandi; sonuclar eksik olabilir.",
                    _COLOR["warning"],
                )
            )

        if m.longest_nets:
            self.lines.append("")
            self.lines.append("  En uzun netler:")
            for name, length in m.longest_nets:
                self.lines.append(f"    {length:8.1f} mm   {name}")

        unplaced = d.unplaced_refs()
        orphans = d.orphan_refs()
        if unplaced:
            self.lines.append("")
            self.lines.append(
                self.c(f"  PCB'ye yerlestirilmemis: {', '.join(unplaced[:12])}", _COLOR["warning"])
            )
        if orphans:
            self.lines.append(
                self.c(f"  Sematikte olmayan: {', '.join(orphans[:12])}", _COLOR["warning"])
            )

        # -------------------------------------------------------------- sematik
        sch = report.schematic
        if sch is not None:
            self.heading("SEMATIK")
            stats = sch.stats()
            self.kv("Dosya / sayfa", f"{stats['dosya']} dosya, {stats['sayfa']} sayfa")
            self.kv(
                "Sembol",
                f"{stats['gercek_bilesen']} bilesen + {stats['sanal_sembol']} sanal "
                f"(#PWR/#FLG)",
            )
            self.kv("Baglanti ogeleri", f"{stats['tel']} tel, {stats['junction']} junction, "
                                        f"{stats['no_connect']} no-connect, {stats['etiket']} etiket")
            if stats["alt_sayfa"]:
                names = ", ".join(sh.name for sh in sch.sheets[:6] if sh.name)
                self.kv("Alt sayfalar", names or str(stats["alt_sayfa"]))
            if sch.paper:
                self.kv("Kagit", sch.paper)

        # ------------------------------------------------------------- bulgular
        self.heading("BULGULAR")
        if not report.findings:
            self.lines.append(self.c("  Temiz - hicbir kural ihlali bulunamadi.", "\033[32m"))
        else:
            for severity in ("error", "warning", "info"):
                group = [f for f in report.findings if f.severity == severity]
                if not group:
                    continue
                label = self.c(f"[{_MARK[severity]}]", _COLOR[severity])
                self.lines.append("")
                self.lines.append(f"  {label} {len(group)} adet")
                for f in group:
                    tag = self.c(f"({f.source}:{f.rule_id})", _DIM)
                    self.lines.append(f"    - {f.message} {tag}")

        # --------------------------------------------------------------- sonuc
        self.heading("SONUC")
        score = report.score
        score_color = "\033[32m" if score >= 85 else _COLOR["warning"] if score >= 60 else _COLOR["error"]
        self.kv(
            "Bulgular",
            f"{report.count('error')} hata / {report.count('warning')} uyari / "
            f"{report.count('info')} bilgi",
        )
        self.kv("Skor", self.c(f"{score:.0f} / 100", score_color))
        self.lines.append("")
        self.lines.append(
            self.c(
                "  Not: bu arac salt-okunurdur; tasariminizda hicbir degisiklik yapmaz.",
                _DIM,
            )
        )
        self.lines.append("")

        return "\n".join(self.lines)


def render(report: Report, color: bool = True) -> str:
    return Renderer(color=color).render(report)
