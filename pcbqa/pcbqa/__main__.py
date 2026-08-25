"""Komut satiri girisi:  python -m pcbqa <proje>

Akis:
  1. Proje dosyalarini bul (.kicad_pro / .kicad_sch / .kicad_pcb)
  2. kicad-cli ile netlist + ERC + DRC uret
  3. PCB'yi oku, sematik ile birlestir (model.Design)
  4. Kendi kurallarimizi calistir
  5. Hepsini tek raporda topla
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from .kicadcli import KicadCli, KicadCliError, describe_violation, load_violations
from .model import build_design
from .netlist import netlist_from_board, read_netlist
from .pcb import read_board
from .report import Report, enable_ansi, render
from .rules import Finding, RuleError, load_rules, run_rules, run_schematic_checks
from .schematic import read_schematic

# KiCad'in severity adlarini kendi adlarimiza cevir
_KICAD_SEVERITY = {
    "error": "error",
    "warning": "warning",
    "exclusion": "info",
    "info": "info",
}


class ProjectError(RuntimeError):
    pass


def discover_project(target: Path) -> tuple[str, Path | None, Path | None]:
    """Verilen klasor/dosyadan (proje adi, sematik, pcb) uclusunu bulur."""
    target = target.resolve()

    if target.is_file():
        stem, folder = target.stem, target.parent
    elif target.is_dir():
        folder = target
        pro = sorted(folder.glob("*.kicad_pro"))
        if pro:
            stem = pro[0].stem
        else:
            pcb = sorted(folder.glob("*.kicad_pcb"))
            if not pcb:
                raise ProjectError(f"{folder} icinde KiCad projesi bulunamadi")
            stem = pcb[0].stem
    else:
        raise ProjectError(f"bulunamadi: {target}")

    sch = folder / f"{stem}.kicad_sch"
    pcb = folder / f"{stem}.kicad_pcb"
    return stem, (sch if sch.exists() else None), (pcb if pcb.exists() else None)


def default_rules_path() -> Path:
    """Once calisma dizinindeki rules.yaml, yoksa paketle gelen varsayilan."""
    local = Path.cwd() / "rules.yaml"
    if local.exists():
        return local
    return Path(__file__).parent / "default_rules.yaml"


def kicad_findings(path: Path | None, source: str) -> list[Finding]:
    """ERC/DRC JSON raporunu Finding listesine cevirir."""
    out: list[Finding] = []
    for item in load_violations(path) if path else []:
        severity, code, text = describe_violation(item)
        if severity == "ignore":
            continue
        out.append(
            Finding(
                rule_id=code,
                severity=_KICAD_SEVERITY.get(severity, "warning"),
                message=text or code,
                source=source,
            )
        )
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pcbqa",
        description="KiCad tasarimlari icin salt-okunur kalite/uygunluk analizi.",
    )
    p.add_argument("project", type=Path, help="Proje klasoru veya .kicad_pro/.kicad_pcb dosyasi")
    p.add_argument("--rules", type=Path, default=None, help="YAML kural dosyasi")
    p.add_argument("--json", type=Path, default=None, help="Raporu JSON olarak da yaz")
    p.add_argument("--work-dir", type=Path, default=None, help="Ara dosyalari burada tut")
    p.add_argument("--kicad-cli", default=None, help="kicad-cli yolu")
    p.add_argument(
        "--no-kicad-checks", action="store_true", help="KiCad'in ERC/DRC kontrollerini atla"
    )
    p.add_argument("--no-color", action="store_true", help="Renkleri kapat")
    p.add_argument(
        "--fail-on",
        choices=("error", "warning", "none"),
        default="error",
        help="Hangi seviyede cikis kodu 1 dondurulsun (varsayilan: error)",
    )
    return p


def analyze(args: argparse.Namespace, work: Path) -> Report:
    name, sch, pcb = discover_project(args.project)
    if pcb is None:
        raise ProjectError(f"{name}: .kicad_pcb dosyasi yok - Asama 0 PCB konumlarina ihtiyac duyar")

    cli = KicadCli(args.kicad_cli)
    version = cli.version()
    board = read_board(pcb)

    # 1) Baglanti bilgisi: varsa sematikten (pin islev adlari + net siniflari
    #    icin daha zengin), yoksa dogrudan PCB pad'lerinden.
    if sch is not None:
        net_xml = work / "netlist.xml"
        res = cli.export_netlist(sch, net_xml)
        if not res.ok or res.output_path is None:
            raise ProjectError(f"netlist uretilemedi:\n{res.stderr or res.stdout}")
        netlist = read_netlist(net_xml)
    else:
        netlist = netlist_from_board(board)

    # 2) Konum + baglanti bilgisini birlestir
    design = build_design(board, netlist, project_name=name)

    # 3) Kendi kurallarimiz
    rules_path = args.rules or default_rules_path()
    if not rules_path.exists():
        raise ProjectError(f"kural dosyasi bulunamadi: {rules_path}")
    findings = run_rules(design, load_rules(rules_path))

    # 3b) Sematigin kendisi (Asama 4a). Okuma basarisiz olursa analiz
    #     durmaz - sematik zorunlu degil, PCB analizi kendi basina anlamli.
    schematic = None
    if sch is not None:
        try:
            schematic = read_schematic(sch)
            findings += run_schematic_checks(schematic)
        except Exception as exc:  # bozuk/desteklenmeyen sematik analizi durdurmasin
            findings.append(
                Finding(
                    rule_id="sematik-okunamadi",
                    severity="info",
                    message=f"sematik okunamadi ({type(exc).__name__}): {str(exc)[:120]}",
                    source="pcbqa-sch",
                )
            )

    # 4) KiCad'in kendi kontrolleri
    if not args.no_kicad_checks:
        if sch is not None:
            erc = cli.erc(sch, work / "erc.json")
            findings += kicad_findings(erc.output_path, "kicad-erc")
        drc = cli.drc(pcb, work / "drc.json")
        findings += kicad_findings(drc.output_path, "kicad-drc")

    order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: (order.get(f.severity, 9), f.source, f.rule_id))

    return Report(
        design=design,
        metrics=design.metrics(),
        findings=findings,
        kicad_version=version,
        schematic=schematic,
    )


def main(argv: list[str] | None = None) -> int:
    # Windows konsolu varsayilan olarak UTF-8 degil; Turkce karakterler bozulmasin.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    color = enable_ansi() and not args.no_color

    try:
        if args.work_dir:
            args.work_dir.mkdir(parents=True, exist_ok=True)
            report = analyze(args, args.work_dir)
        else:
            with tempfile.TemporaryDirectory(prefix="pcbqa-") as tmp:
                report = analyze(args, Path(tmp))
    except (ProjectError, KicadCliError, RuleError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2

    print(render(report, color=color))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"JSON rapor: {args.json}")

    if args.fail_on == "error" and report.count("error"):
        return 1
    if args.fail_on == "warning" and (report.count("error") or report.count("warning")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
