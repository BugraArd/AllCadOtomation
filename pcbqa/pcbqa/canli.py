"""Acik PCB'den onizleme ve tek undo islemiyle canli yerlestirme.

KiCad 9/10 sematik API yazmasi desteklemez. Canli PCB'nin kaydedilmemis
halini SaveCopyOfDocument ile okuruz; diskteki eski karttan plan yapilmaz.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

from .ipc import IpcApplyError, _load_kipy, apply_placement_to_board


@contextmanager
def connection(socket_path=None):
    KiCad, _, _ = _load_kipy()
    try:
        kicad = KiCad(socket_path=socket_path, client_name="pcbqa", timeout_ms=3000)
    except Exception as exc:
        raise IpcApplyError(f"KiCad istemcisi baslatilamadi: {exc}") from exc
    try:
        yield kicad
    except IpcApplyError:
        raise
    except Exception as exc:
        raise IpcApplyError(
            f"KiCad baglantisi: {exc}. PCB editorunu acin; "
            "Tercihler > Eklentiler bolumunde API sunucusu etkin olmali."
        ) from exc
    finally:
        # 0.7.1'de KiCad.close yok; istemcinin NNG baglantisi var.
        close = getattr(kicad, "close", None)
        if close:
            close()
        else:
            client = getattr(kicad, "_client", None)
            conn = getattr(client, "_conn", None)
            if conn is not None:
                conn.close()


def project_file(project: str | Path, suffix: str) -> Path:
    if not str(project).strip():
        raise IpcApplyError("Once bir proje secin.")
    path = Path(project).resolve()
    if path.is_dir():
        candidates = list(path.glob("*" + suffix))
        if len(candidates) != 1:
            raise IpcApplyError(f"{path}: tek bir {suffix} secilemiyor; dosyayi secin.")
        return candidates[0]
    candidate = path.with_suffix(suffix)
    if not candidate.is_file():
        raise IpcApplyError(f"Dosya bulunamadi: {candidate}")
    return candidate


def open_editor(project: str | Path, kind: str) -> str:
    """Secilen dosyayi gorunur editorle acar; acik editoru kapatmaz."""
    from .kicadcli import find_kicad_cli
    from .kurulum import running_kicad

    exe_name, suffix = (("pcbnew", ".kicad_pcb") if kind == "pcb"
                        else ("eeschema", ".kicad_sch"))
    path = project_file(project, suffix)
    running = running_kicad()
    if any(name.lower().startswith("kicad.exe ") for name in running):
        raise IpcApplyError("KiCad proje yoneticisi acik. Editoru o pencereden acin; "
                            "ayri KiCad ornekleri ayni API soketini paylasamaz.")
    if any(exe_name in name.lower() for name in running):
        raise IpcApplyError(
            f"{exe_name} zaten acik. Acik pencereden bu projeyi secin: {path}")
    exe = Path(find_kicad_cli()).with_name(exe_name + (".exe" if os.name == "nt" else ""))
    subprocess.Popen([str(exe), str(path)])
    return f"Aciliyor: {path}"


def board_identity(board) -> tuple[str, str]:
    return board.name, str(board.document.project.path)


def check_target(board, expected: Path) -> None:
    name, folder = board_identity(board)
    if not folder or (Path(folder) / name).resolve() != expected.resolve():
        raise IpcApplyError(f"Acik PCB {folder}/{name}; secilen PCB {expected}. Karta dokunulmadi.")


def snapshot(board, folder: Path) -> Path:
    path = folder / "snapshot.kicad_pcb"
    board.save_as(str(path), overwrite=True, include_project=False)
    if not path.is_file():
        raise IpcApplyError("KiCad canli kartin kopyasini olusturamadi.")
    return path


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class LivePlan:
    target: Path
    identity: tuple[str, str]
    fingerprint: str
    placement: dict
    locked: set[str]
    description: str


def prepare(project: str | Path, *, budget: float = 10.0, socket_path=None) -> LivePlan:
    from .harness import load_design, locked_refs, run_one
    from .ipc_apply import Candidate, select_winner
    from .rules import load_rules

    expected = project_file(project, ".kicad_pcb")
    with connection(socket_path) as kicad, tempfile.TemporaryDirectory(prefix="pcbqa-live-") as tmp:
        board = kicad.get_board()
        check_target(board, expected)
        path = snapshot(board, Path(tmp))
        digest = fingerprint(path)
        design = load_design(path)
        if not design.board.components:
            raise IpcApplyError("PCB bos: once sematikten PCB'ye bilesenleri aktarin (KiCad F8).")
        # Canli bakiri ayirmamak icin yonlendirilmis karti otomatik tasimayiz.
        if design.board.tracks or design.board.vias:
            raise IpcApplyError("PCB'de bakir yollar/vialar var. Canli otomatik yerlestirme "
                                "yalnizca henuz yonlendirilmemis kartta kullanilir.")
        own_rules = expected.with_suffix(".rules.yaml")
        rules_path = own_rules if own_rules.is_file() else Path(__file__).parent / "presets/uretim.rules.yaml"
        rules = load_rules(rules_path)
        result, placement = run_one("auto", design, rules, seed=0, budget=budget)
        winner = select_winner([Candidate("auto", result, placement)])
        _, vector, angle = _load_kipy()
        summary = apply_placement_to_board(board, winner.placement, vector2=vector,
                                           angle=angle, locked_refs=locked_refs(design))
        details = (f"PCB: {expected}\nCanli onizleme: {summary.changed} bilesen tasinacak; "
                   f"{len(summary.skipped_locked_refs)} kilitli bilesen korunacak.\n"
                   f"Kural skoru: {result.before.score:.1f} -> {result.after.score:.1f}\n"
                   f"Kurallar: {rules_path.name}\n"
                   "Bu skor yonlendirme veya uretime hazirlik garantisi degildir.\n"
                   "Uygulama tek Ctrl+Z ile geri alinir. Dosya otomatik kaydedilmez.")
        return LivePlan(expected, board_identity(board), digest, winner.placement,
                        locked_refs(design), details)


def apply_plan(plan: LivePlan, *, socket_path=None):
    with connection(socket_path) as kicad, tempfile.TemporaryDirectory(prefix="pcbqa-live-") as tmp:
        board = kicad.get_board()
        check_target(board, plan.target)
        if board_identity(board) != plan.identity or fingerprint(snapshot(board, Path(tmp))) != plan.fingerprint:
            raise IpcApplyError("PCB onizlemeden sonra degisti. Yeni onizleme alin; eski plan uygulanmadi.")
        _, vector, angle = _load_kipy()
        return apply_placement_to_board(board, plan.placement, vector2=vector, angle=angle,
                                        apply=True, locked_refs=plan.locked,
                                        expected_board_name=plan.target.name)


def describe_connection(project: str | Path = "", *, socket_path=None) -> str:
    with connection(socket_path) as kicad:
        version = kicad.get_version()
        board = kicad.get_board()
        if project:
            check_target(board, project_file(project, ".kicad_pcb"))
        count = len(board.get_footprints())
        return (f"KiCad {version}\nPCB baglantisi: hazir ({board.name}, {count} bilesen)\n"
                "Sematik: Canli sekmesinin sematik bolumunden ayri nightly kopyasini acin; "
                "stabil KiCad 9/10 sematik yazmasini desteklemez.\n"
                "Sematikteki degisiklikler PCB'ye kendiliginden aktarilmaz; KiCad'de F8 kullanin.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="KiCad canli PCB baglantisi ve yerlestirme")
    parser.add_argument("project", nargs="?", default="")
    parser.add_argument("--yerlestir", action="store_true")
    parser.add_argument("--uygula", action="store_true")
    parser.add_argument("--ac", choices=("pcb", "sematik"))
    parser.add_argument("--socket")
    args = parser.parse_args(argv)
    try:
        if args.ac:
            print(open_editor(args.project, args.ac))
        elif args.yerlestir:
            plan = prepare(args.project, socket_path=args.socket)
            print(plan.description)
            if args.uygula:
                summary = apply_plan(plan, socket_path=args.socket)
                print(f"Uygulandi: {summary.changed} bilesen; dosya kaydedilmedi.")
        elif args.uygula:
            raise IpcApplyError("--uygula icin --yerlestir gerekli.")
        else:
            print(describe_connection(args.project, socket_path=args.socket))
    except (IpcApplyError, OSError, ValueError) as exc:
        print(f"hata: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
