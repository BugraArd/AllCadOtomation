"""Bulgu kanıtı, güvenli düzeltme önerisi ve tekrar doğrulama akışı.

Paket 01'in ürün kapısıdır. Kural motoru bulguyu üretir; bu modül bulguyu
doğrudan dosyaya yazmaz. Önce mevcut tasarım üzerinde adayları dener, hedef
bulgunun kapandığını ve hakem puanının kötüleşmediğini ölçer. Kullanıcı
`--uygula` demedikçe yalnızca plan ve dry-run çıktısı üretir.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from . import __main__ as analyzer
from .harness import apply_placement, locked_refs, make_evaluator, write_board
from .placement.base import Placement, PlacementContext
from .placement.refine import candidate_moves_for_finding
from .rules import Finding, RuleError, load_rules, run_rules
from .sch_write import SchWriteError, atomic_write_text, backup_file, lock_files


class FixError(RuntimeError):
    """Güvenli düzeltme üretilemedi veya doğrulama başarısız oldu."""


@dataclass
class FixProposal:
    """Kullanıcı onayından önce gösterilen, uygulanabilir düzeltme planı."""

    proposal_id: str
    finding: Finding
    description: str
    placement: Placement
    changes: list[dict[str, Any]]
    preconditions: list[str] = field(default_factory=list)
    risk: str = "low"
    verification_plan: list[str] = field(default_factory=list)
    board_has_copper: bool = False

    @property
    def finding_id(self) -> str:
        return self.finding.finding_id

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "proposal_id": self.proposal_id,
            "finding": self.finding.as_dict(),
            "description": self.description,
            "placement": {
                ref: [round(x, 4), round(y, 4), round(rot, 4)]
                for ref, (x, y, rot) in sorted(self.placement.items())
            },
            "changes": self.changes,
            "preconditions": self.preconditions,
            "risk": self.risk,
            "verification_plan": self.verification_plan,
            "board_has_copper": self.board_has_copper,
        }


def _args_for_scan(
    project: Path,
    rules: Path | None,
    kicad_cli: str | None,
    no_kicad_checks: bool,
) -> SimpleNamespace:
    return SimpleNamespace(
        project=project,
        rules=rules,
        kicad_cli=kicad_cli,
        no_kicad_checks=no_kicad_checks,
    )


def scan_project(
    project: Path,
    *,
    rules: Path | None = None,
    kicad_cli: str | None = None,
    no_kicad_checks: bool = False,
):
    """Analizörü geçici çalışma alanıyla çalıştırır."""
    args = _args_for_scan(project, rules, kicad_cli, no_kicad_checks)
    with tempfile.TemporaryDirectory(prefix="pcbqa-duzelt-") as tmp:
        return analyzer.analyze(args, Path(tmp))


def _same_finding(candidate: Finding, target: Finding) -> bool:
    """Hedef ihlalin hâlâ aynı fiziksel ilişkiyle mevcut olup olmadığını ölçer."""
    return (
        candidate.source == target.source
        and candidate.rule_id == target.rule_id
        and candidate.rule_type == target.rule_type
        and candidate.refs == target.refs
        and candidate.pins == target.pins
    )


def _net_signature(netlist) -> tuple:
    """Net isimlerini ve pin bölünüşünü net kodlarından bağımsız karşılaştırır."""
    nets = []
    for net in netlist.nets:
        nodes = tuple(sorted(
            (node.ref, node.pin, node.pinfunction, node.pintype)
            for node in net.nodes
        ))
        nets.append((net.name, net.netclass, nodes))
    return tuple(sorted(nets))


def _board_has_copper(design) -> bool:
    board = design.board
    return bool(board.tracks or board.vias or board.zones)


def _placement(design) -> Placement:
    return {
        comp.ref: (comp.x, comp.y, comp.rotation)
        for comp in design.board.components
    }


def _changed_components(before: Placement, after: Placement) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for ref in sorted(set(before) | set(after)):
        if ref not in before or ref not in after:
            continue
        old, new = before[ref], after[ref]
        if all(abs(a - b) <= 1e-6 for a, b in zip(old, new)):
            continue
        changes.append({
            "ref": ref,
            "before": [round(v, 4) for v in old],
            "after": [round(v, 4) for v in new],
        })
    return changes


def propose(report, finding: Finding, rules) -> FixProposal:
    """Hedef bulgu için hakemden geçmiş ilk uygulanabilir planı üretir."""
    if not finding.auto_fixable:
        raise FixError(
            f"{finding.finding_id} otomatik düzeltmeye uygun değil; "
            "kanıtlı öneri var ama bu sürüm dosyaya güvenli yazamıyor"
        )

    design = report.design
    before = _placement(design)
    context = PlacementContext(
        design=design,
        locked=locked_refs(design),
    )
    candidates = candidate_moves_for_finding(finding, before, context)
    if not candidates:
        raise FixError(
            f"{finding.finding_id} için kart sınırları ve kilitli parçalar içinde aday konum bulunamadı"
        )

    evaluator = make_evaluator(design, rules)
    baseline = evaluator(before)
    best: tuple[tuple, Placement, Any] | None = None

    for ref, position in candidates:
        candidate = dict(before)
        candidate[ref] = position
        after_design = apply_placement(design, candidate)
        after_findings = run_rules(after_design, rules)
        if any(_same_finding(item, finding) for item in after_findings):
            continue
        evaluation = evaluator(candidate)
        if evaluation is None or not evaluation.better_than(baseline):
            continue
        key = evaluation.key
        if best is None or key > best[0]:
            best = (key, candidate, evaluation)

    if best is None:
        raise FixError(
            f"{finding.finding_id} için hedef bulguyu kapatan ve kartı kötüleştirmeyen "
            "bir konum bulunamadı"
        )

    _key, placement, evaluation = best
    changes = _changed_components(before, placement)
    if not changes:
        raise FixError(f"{finding.finding_id} için gerçek bir konum değişikliği üretilemedi")

    changed_refs = ", ".join(change["ref"] for change in changes)
    copper = _board_has_copper(design)
    preconditions = [
        f"hedef bulgu mevcut: {finding.finding_id}",
        "netlist pin/ağ bölünüşü değişmemeli",
        "uygulama sonrası aynı kural tekrar çalıştırılmalı",
    ]
    if copper:
        preconditions.append(
            "kartta mevcut bakır/via/zone var; otomatik dosya uygulaması kapalı "
            "(routing güvenliği için)"
        )

    return FixProposal(
        proposal_id=f"P-{finding.finding_id[2:]}",
        finding=finding,
        description=(
            f"{changed_refs} bileşenini {finding.message.split(' (')[0]} "
            "bulgusunu kapatacak güvenli konuma taşı"
        ),
        placement=placement,
        changes=changes,
        preconditions=preconditions,
        risk="medium" if copper else "low",
        verification_plan=[
            f"{finding.rule_id} bulgusu aynı pin/ref çifti için kapanmalı",
            "netlist isimleri ve pin bölünüşü değişmemeli",
            "KiCad ERC/DRC tekrar çalıştırılmalı",
            f"hakem puanı kötüleşmemeli (aday sonrası {evaluation.score:.1f})",
        ],
        board_has_copper=copper,
    )


def _write_json(path: Path | None, value: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"JSON plan: {path}")


def _render_findings(findings: list[Finding]) -> str:
    if not findings:
        return "Bulgular: temiz"
    lines = ["BULGULAR", "--------"]
    for finding in findings:
        flag = "DUZELTILEBILIR" if finding.auto_fixable else "ONERI"
        lines.append(
            f"{finding.finding_id} [{finding.severity}] [{flag}] "
            f"{finding.rule_id}: {finding.message}"
        )
        lines.append(f"  kanit: {json.dumps(finding.evidence, ensure_ascii=False)}")
    return "\n".join(lines)


def _render_proposal(proposal: FixProposal) -> str:
    lines = [
        "DUZELTME ONIZLEMESI",
        "-------------------",
        f"proposal : {proposal.proposal_id}",
        f"bulgu    : {proposal.finding_id}",
        f"risk     : {proposal.risk}",
        f"aciklama : {proposal.description}",
        "",
        "DEGISIKLIKLER",
    ]
    for change in proposal.changes:
        lines.append(
            f"  {change['ref']}: {change['before']} -> {change['after']}"
        )
    lines += ["", "ON KOSULLAR"]
    lines.extend(f"  - {item}" for item in proposal.preconditions)
    lines += ["", "UYGULAMA SONRASI DOGRULAMA"]
    lines.extend(f"  - {item}" for item in proposal.verification_plan)
    return "\n".join(lines)


def _apply_proposal(source: Path, proposal: FixProposal, target: Path) -> Path | None:
    """Öneriyi atomik yaz ve varsa eski dosyayı yedekle."""
    source = source.resolve()
    target = target.resolve()
    if proposal.board_has_copper:
        raise FixError(
            "kartta mevcut bakır/via/zone bulunduğu için otomatik yerleşim yazılmadı; "
            "önce yönlendirme koruma akışı tasarlanmalı"
        )

    locks = lock_files(source if target == source else target)
    if locks:
        names = ", ".join(path.name for path in locks[:3])
        raise FixError(f"KiCad projesi açık ({names}); önce kapatın")

    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    backup: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{target.stem}.pcbqa-fix-",
            suffix=".kicad_pcb",
            dir=target.parent,
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)

        write_board(source, proposal.placement, temp_path)
        text = temp_path.read_text(encoding="utf-8")
        if target.exists():
            backup = backup_file(target)
        atomic_write_text(target, text)
        return backup
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _find_by_id(findings: list[Finding], finding_id: str) -> Finding:
    for finding in findings:
        if finding.finding_id == finding_id:
            return finding
    available = ", ".join(f.finding_id for f in findings[:12]) or "yok"
    raise FixError(f"bulgu bulunamadı: {finding_id}; mevcut bulgular: {available}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pcbqa.duzelt",
        description="Bulgu için kanıtlı düzeltme öner, onayla ve tekrar doğrula",
    )
    parser.add_argument("project", type=Path, help="Proje klasörü veya .kicad_pcb/.kicad_pro")
    parser.add_argument("--finding", help="Finding ID; örn. F-123456789abc")
    parser.add_argument("--liste", action="store_true", help="Bulguları kimlikleriyle listele")
    parser.add_argument("--rules", type=Path, default=None)
    parser.add_argument("--kicad-cli", default=None)
    parser.add_argument("--out", type=Path, default=None,
                        help="Uygulama hedefi; verilmezse kaynak PCB güvenli yedekle değiştirilir")
    parser.add_argument("--uygula", action="store_true", help="Dry-run yerine yaz ve tekrar doğrula")
    parser.add_argument("--json", type=Path, default=None, help="Rapor/öneri JSON yolu")
    parser.add_argument("--no-kicad-checks", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    try:
        report = scan_project(
            args.project,
            rules=args.rules,
            kicad_cli=args.kicad_cli,
            no_kicad_checks=args.no_kicad_checks,
        )
        if args.liste:
            print(_render_findings(report.findings))
            _write_json(args.json, report.as_dict())
            return 1 if report.count("error") else 0
        if not args.finding:
            raise FixError("--finding gerekli; önce --liste ile bulgu kimliklerini alın")

        finding = _find_by_id(report.findings, args.finding)
        rules = load_rules(args.rules or analyzer.default_rules_path())
        proposal = propose(report, finding, rules)
        print(_render_proposal(proposal))
        _write_json(args.json, proposal.as_dict())

        if not args.uygula:
            print("\nDRY-RUN: dosyaya dokunulmadı. Gerçek yazma için --uygula verin.")
            return 0

        source = report.design.board.path.resolve()
        target = (args.out or source).resolve()
        backup: Path | None = None
        try:
            backup = _apply_proposal(source, proposal, target)

            verify_project = target
            verified = scan_project(
                verify_project,
                rules=args.rules,
                kicad_cli=args.kicad_cli,
                no_kicad_checks=args.no_kicad_checks,
            )
            remaining = [f for f in verified.findings if _same_finding(f, finding)]
            if remaining:
                raise FixError(
                    f"uygulama sonrası hedef bulgu hâlâ mevcut: {remaining[0].message}"
                )
            if _net_signature(report.design.netlist) != _net_signature(verified.design.netlist):
                raise FixError("uygulama sonrası netlist değişti; güvenlik kapısı reddetti")
        except FixError as exc:
            if backup and target == source and backup.exists():
                atomic_write_text(target, backup.read_text(encoding="utf-8"))
                raise FixError(f"{exc}; kaynak dosya yedekten geri alındı") from exc
            raise

        print(f"\nUYGULANDI: {target}")
        if backup:
            print(f"yedek: {backup}")
        print("doğrulama: hedef bulgu kapandı, netlist paritesi korundu")
        print(
            f"sonuç: {verified.count('error')} hata / "
            f"{verified.count('warning')} uyarı / skor {verified.score:.1f}"
        )
        return 1 if verified.count("error") else 0
    except (FixError, RuleError, SchWriteError, OSError, ValueError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
