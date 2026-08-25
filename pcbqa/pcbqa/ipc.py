"""Apply placement results to a running KiCad PCB editor through IPC.

This module is intentionally thin: it knows only how to map the existing
`Placement` contract (`ref -> x_mm, y_mm, rotation_deg`) onto kicad-python's
footprint API. The optimizer and scoring model stay KiCad-independent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .placement.base import Placement

NM_PER_MM = 1_000_000.0


class IpcApplyError(RuntimeError):
    """The placement could not be applied to the active KiCad board."""


@dataclass
class IpcApplySummary:
    """Human and machine-readable result of an IPC apply attempt."""

    board_name: str
    kicad_version: str = ""
    requested: int = 0
    changed: int = 0
    unchanged: int = 0
    missing_refs: list[str] = field(default_factory=list)
    skipped_locked_refs: list[str] = field(default_factory=list)
    duplicate_refs: list[str] = field(default_factory=list)
    applied_refs: list[str] = field(default_factory=list)
    verify_errors: list[str] = field(default_factory=list)
    dry_run: bool = True
    saved: bool = False

    @property
    def ok(self) -> bool:
        return not self.duplicate_refs and not self.verify_errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "board_name": self.board_name,
            "kicad_version": self.kicad_version,
            "requested": self.requested,
            "changed": self.changed,
            "unchanged": self.unchanged,
            "missing_refs": self.missing_refs,
            "skipped_locked_refs": self.skipped_locked_refs,
            "duplicate_refs": self.duplicate_refs,
            "applied_refs": self.applied_refs,
            "verify_errors": self.verify_errors,
            "dry_run": self.dry_run,
            "saved": self.saved,
            "ok": self.ok,
        }


def _load_kipy():
    try:
        from kipy import KiCad
        from kipy.geometry import Angle, Vector2
    except ModuleNotFoundError as exc:
        raise IpcApplyError(
            "kicad-python kurulu degil. Kurulum: "
            ".\\.venv\\Scripts\\python -m pip install kicad-python"
        ) from exc
    return KiCad, Vector2, Angle


def _reference_of(footprint) -> str:
    try:
        return str(footprint.reference_field.text.value)
    except Exception as exc:  # pragma: no cover - defensive for API drift
        raise IpcApplyError("footprint referansi IPC API'den okunamadi") from exc


def _position_mm(footprint) -> tuple[float, float]:
    pos = footprint.position
    return float(pos.x) / NM_PER_MM, float(pos.y) / NM_PER_MM


def _orientation_degrees(footprint) -> float:
    try:
        return float(footprint.orientation.degrees)
    except Exception:
        return 0.0


def _angle_delta(a: float, b: float) -> float:
    return ((a - b + 180.0) % 360.0) - 180.0


def _pose_changed(footprint, x: float, y: float, rot: float, tolerance_mm: float) -> bool:
    cx, cy = _position_mm(footprint)
    crot = _orientation_degrees(footprint)
    return (
        abs(cx - x) > tolerance_mm
        or abs(cy - y) > tolerance_mm
        or abs(_angle_delta(crot, rot)) > 1e-6
    )


def _index_footprints(board) -> tuple[dict[str, Any], list[str]]:
    by_ref: dict[str, Any] = {}
    duplicates: set[str] = set()

    for fp in board.get_footprints():
        ref = _reference_of(fp)
        if ref in by_ref:
            duplicates.add(ref)
            continue
        by_ref[ref] = fp

    return by_ref, sorted(duplicates)


def _verify(board, placement: Placement, refs: list[str], tolerance_mm: float) -> list[str]:
    by_ref, _duplicates = _index_footprints(board)
    errors: list[str] = []
    for ref in refs:
        fp = by_ref.get(ref)
        if fp is None:
            errors.append(f"{ref}: uygulamadan sonra aktif kartta bulunamadi")
            continue
        x, y, rot = placement[ref]
        if _pose_changed(fp, float(x), float(y), float(rot), tolerance_mm):
            cx, cy = _position_mm(fp)
            crot = _orientation_degrees(fp)
            errors.append(
                f"{ref}: beklenen ({x:.3f}, {y:.3f}, {rot:.1f}), "
                f"okunan ({cx:.3f}, {cy:.3f}, {crot:.1f})"
            )
    return errors


def apply_placement_to_board(
    board,
    placement: Placement,
    *,
    vector2,
    angle,
    apply: bool = False,
    save: bool = False,
    locked_refs: set[str] | None = None,
    expected_board_name: str | None = None,
    allow_board_mismatch: bool = False,
    respect_kicad_locks: bool = True,
    commit_message: str = "pcbqa: apply placement",
    tolerance_mm: float = 1e-6,
) -> IpcApplySummary:
    """Apply `placement` to an already-open kicad-python Board object.

    When `apply` is false this performs a non-mutating dry-run against the
    active board. It still connects to KiCad so board/ref mismatches are caught
    before the user commits to a write.
    """

    board_name = str(getattr(board, "name", "") or "")
    if expected_board_name and board_name and board_name != expected_board_name:
        if not allow_board_mismatch:
            raise IpcApplyError(
                f"aktif KiCad karti {board_name!r}, beklenen {expected_board_name!r}. "
                "--allow-board-mismatch ile bilerek uygulayabilirsiniz."
            )

    locked_refs = locked_refs or set()
    by_ref, duplicates = _index_footprints(board)
    duplicate_targets = sorted(ref for ref in duplicates if ref in placement)
    if duplicate_targets:
        raise IpcApplyError(
            "aktif kartta tekrar eden referans var; hangi footprint'in tasinacagi belirsiz: "
            + ", ".join(duplicate_targets)
        )

    skipped_locked: list[str] = []
    missing: list[str] = []
    unchanged: list[str] = []
    planned: list[tuple[str, Any, float, float, float]] = []

    for ref in sorted(placement):
        x, y, rot = placement[ref]
        fp = by_ref.get(ref)
        if ref in locked_refs:
            skipped_locked.append(ref)
            continue
        if fp is None:
            missing.append(ref)
            continue
        if respect_kicad_locks and bool(getattr(fp, "locked", False)):
            skipped_locked.append(ref)
            continue
        x, y, rot = float(x), float(y), float(rot)
        if _pose_changed(fp, x, y, rot, tolerance_mm):
            planned.append((ref, fp, x, y, rot))
        else:
            unchanged.append(ref)

    summary = IpcApplySummary(
        board_name=board_name,
        requested=len(placement),
        changed=len(planned),
        unchanged=len(unchanged),
        missing_refs=missing,
        skipped_locked_refs=skipped_locked,
        duplicate_refs=duplicates,
        applied_refs=[ref for ref, *_ in planned],
        dry_run=not apply,
        saved=False,
    )

    if not apply or not planned:
        return summary

    commit = None
    try:
        commit = board.begin_commit()
        for _ref, fp, x, y, rot in planned:
            fp.position = vector2.from_xy_mm(x, y)
            fp.orientation = angle.from_degrees(rot)

        updated = board.update_items([fp for _ref, fp, *_ in planned])
        if updated is not None and len(updated) != len(planned):
            raise IpcApplyError(
                f"KiCad {len(planned)} footprint beklenirken {len(updated)} footprint guncelledi"
            )
        board.push_commit(commit, commit_message)
        commit = None
    except Exception as exc:
        if commit is not None:
            try:
                board.drop_commit(commit)
            except Exception:
                pass
        if isinstance(exc, IpcApplyError):
            raise
        raise IpcApplyError(f"KiCad IPC uygulamasi basarisiz: {exc}") from exc

    summary.verify_errors = _verify(board, placement, summary.applied_refs, tolerance_mm)
    if summary.verify_errors:
        raise IpcApplyError(
            "KiCad IPC uygulandi ama dogrulama basarisiz: "
            + "; ".join(summary.verify_errors[:5])
        )

    if save:
        try:
            board.save()
        except Exception as exc:
            raise IpcApplyError(f"kart uygulandi ama kaydedilemedi: {exc}") from exc
        summary.saved = True

    return summary


def apply_placement_to_running_kicad(
    placement: Placement,
    *,
    apply: bool = False,
    save: bool = False,
    locked_refs: set[str] | None = None,
    expected_board_name: str | None = None,
    allow_board_mismatch: bool = False,
    respect_kicad_locks: bool = True,
    socket_path: str | None = None,
    kicad_token: str | None = None,
    timeout_ms: int = 5000,
    client_name: str = "pcbqa",
) -> IpcApplySummary:
    """Connect to the running KiCad GUI and apply a placement."""

    KiCad, Vector2, Angle = _load_kipy()
    try:
        kicad = KiCad(
            socket_path=socket_path,
            client_name=client_name,
            kicad_token=kicad_token,
            timeout_ms=timeout_ms,
        )
    except Exception as exc:
        raise IpcApplyError(
            "KiCad IPC baglantisi kurulamadi. KiCad PCB Editor acik olmali ve "
            "Preferences > Plugins altinda IPC API etkin olmali."
        ) from exc

    try:
        try:
            board = kicad.get_board()
            if board is None:
                raise IpcApplyError("KiCad'de acik PCB bulunamadi")
            summary = apply_placement_to_board(
                board,
                placement,
                vector2=Vector2,
                angle=Angle,
                apply=apply,
                save=save,
                locked_refs=locked_refs,
                expected_board_name=expected_board_name,
                allow_board_mismatch=allow_board_mismatch,
                respect_kicad_locks=respect_kicad_locks,
            )
            try:
                summary.kicad_version = str(kicad.get_version())
            except Exception:
                summary.kicad_version = ""
            return summary
        except IpcApplyError:
            raise
        except Exception as exc:
            text = str(exc)
            if "Failed to connect" in text or "Connection refused" in text:
                raise IpcApplyError(
                    "KiCad IPC baglantisi kurulamadi. KiCad PCB Editor acik olmali ve "
                    "Preferences > Plugins altinda IPC API etkin olmali."
                ) from exc
            raise IpcApplyError(f"KiCad IPC islemi basarisiz: {exc}") from exc
    finally:
        try:
            kicad.close()
        except Exception:
            pass
