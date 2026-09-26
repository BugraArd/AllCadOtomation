"""Acik PCB'yi canli okuma ve sinirli komutlarla canli yazma.

Okuma kaydedilmemis hali IPC'den alir. Yazma sematik tarafindaki akisin
aynisidir: onizle -> SHA256 ile eski plani reddet -> tek commit (tek Ctrl+Z)
-> commit SONRASI geri okuyup dogrula. Baglanti (ag/pad) hic degistirilmez;
yalnizca konum, aci, kilit ve deger alani yazilir.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field, replace
from pathlib import Path
import re
import tempfile

from .canli import board_identity, check_target, connection, fingerprint, project_file, snapshot
from .ipc import IpcApplyError, _angle_delta, _load_kipy, _orientation_degrees, _position_mm, _reference_of

# Konum karsilastirmasi: KiCad nm tamsayi tutar; 1 nm'den kucuk fark yuvarlamadir.
TOLERANS_MM = 1e-6

ORNEKLER = ("R1 konumunu 50 30 yap", "C2 5 -2.5 kaydir", "U1 90 dondur",
            "U1 acisini 180 yap", "J1 kilitle", "J1 kilidini ac", "R1 degerini 10k yap")


@dataclass
class FpState:
    ref: str
    x: float
    y: float
    rot: float
    locked: bool
    value: str
    footprint: str = ""
    side: str = ""

    def key(self) -> tuple:
        return (round(self.x, 6), round(self.y, 6), round(self.rot % 360.0, 6) % 360.0,
                self.locked, self.value)


@dataclass
class Edit:
    ref: str
    kind: str  # tasi | kaydir | dondur | aci | kilitle | kilit_ac | deger
    args: tuple = ()
    text: str = ""


@dataclass
class PcbEditPlan:
    target: Path
    identity: tuple[str, str]
    fingerprint: str
    command: str
    before: dict[str, FpState]
    after: dict[str, FpState]
    description: str
    warnings: list[str] = field(default_factory=list)

    @property
    def changed(self) -> list[str]:
        return sorted(r for r in self.after if self.after[r].key() != self.before[r].key())


# -- okuma -------------------------------------------------------------------

def _side(fp) -> str:
    layer = getattr(fp, "layer", None)
    try:
        from kipy.proto.board.board_types_pb2 import BoardLayer
        name = BoardLayer.Name(layer)
    except Exception:
        return ""
    return {"BL_F_Cu": "on", "BL_B_Cu": "arka"}.get(name, name)


def _field_text(fp, name: str) -> str:
    try:
        return str(getattr(fp, name).text.value)
    except Exception:
        return ""


def state_of(fp) -> FpState:
    x, y = _position_mm(fp)
    lib = ""
    try:
        lib = str(fp.definition.id)
    except Exception:
        pass
    return FpState(_reference_of(fp), x, y, _orientation_degrees(fp), bool(getattr(fp, "locked", False)),
                   _field_text(fp, "value_field"), lib, _side(fp))


def index(board) -> dict[str, object]:
    found: dict[str, object] = {}
    duplicates = set()
    for fp in board.get_footprints():
        ref = _reference_of(fp)
        if ref in found:
            duplicates.add(ref)
        found[ref] = fp
    if duplicates:
        # Hangi footprint'e yazilacagi belirsizse hic yazmayiz.
        raise IpcApplyError("PCB'de tekrar eden referans var: " + ", ".join(sorted(duplicates)))
    return found


def states(board) -> dict[str, FpState]:
    return {ref: state_of(fp) for ref, fp in index(board).items()}


def _ref_key(ref: str):
    m = re.fullmatch(r"(\D*)(\d+)(.*)", ref)
    return (m.group(1), int(m.group(2)), m.group(3)) if m else (ref, 0, "")


def _count(board, getter: str) -> str:
    fn = getattr(board, getter, None)
    if fn is None:
        return "?"
    try:
        return str(len(fn()))
    except Exception:
        return "?"


def format_table(rows: dict[str, FpState]) -> str:
    lines = [f"{'Ref':<8} {'Deger':<14} {'X mm':>9} {'Y mm':>9} {'Aci':>7} {'Yuz':<5} Kilit  Footprint"]
    for ref in sorted(rows, key=_ref_key):
        s = rows[ref]
        lines.append(f"{s.ref:<8} {s.value[:14]:<14} {s.x:>9.3f} {s.y:>9.3f} {s.rot:>7.1f} "
                     f"{s.side:<5} {'evet ' if s.locked else '-    '}  {s.footprint}")
    return "\n".join(lines)


def read_live(project: str | Path, *, socket_path=None) -> str:
    expected = project_file(project, ".kicad_pcb")
    with connection(socket_path) as kicad:
        board = kicad.get_board()
        check_target(board, expected)
        rows = states(board)
        summary = (f"Canli PCB: {expected}\n{len(rows)} bilesen, {_count(board, 'get_tracks')} iz, "
                   f"{_count(board, 'get_vias')} via, {_count(board, 'get_zones')} bakir dokum, "
                   f"{_count(board, 'get_nets')} ag.\n"
                   "Okunan hal KiCad'deki kaydedilmemis degisiklikleri de icerir.\n\n")
        return summary + format_table(rows)


# -- komut ayristirma --------------------------------------------------------

_TR = str.maketrans("ıİğĞşŞüÜöÖçÇ",
                    "iIgGsSuUoOcC")
_SAYI = r"([-+]?\d+(?:[.,]\d+)?)(?:\s*mm)?"
_REF = r"([A-Za-z]+\d+[A-Za-z]?)(?:'[a-z]+)?"
_KALIPLAR = (
    ("tasi", rf"{_REF}\s+(?:konumunu\s+)?{_SAYI}\s+{_SAYI}\s+(?:konumuna\s+)?(?:yap|tasi)"),
    ("tasi", rf"{_REF}\s+tasi\s+{_SAYI}\s+{_SAYI}"),
    ("kaydir", rf"{_REF}\s+{_SAYI}\s+{_SAYI}\s+kaydir"),
    ("kaydir", rf"{_REF}\s+kaydir\s+{_SAYI}\s+{_SAYI}"),
    ("aci", rf"{_REF}\s+acisini\s+{_SAYI}\s+(?:derece\s+)?yap"),
    ("dondur", rf"{_REF}\s+{_SAYI}\s+(?:derece\s+)?dondur"),
    ("dondur", rf"{_REF}\s+dondur\s+{_SAYI}(?:\s+derece)?"),
    ("kilit_ac", rf"{_REF}\s+kilidini\s+(?:ac|kaldir)"),
    ("kilitle", rf"{_REF}\s+kilitle"),
    ("deger", rf"{_REF}\s+degerini\s+(\S+)\s+(?:yap|degistir)"),
)


def _number(text: str) -> float:
    return float(text.replace(",", "."))


def parse_commands(command: str) -> list[Edit]:
    """';' veya satir sonuyla ayrilmis komutlari sirasiyla ayristirir.

    Anlasilmayan tek parca butun komutu reddeder: yarim plan uygulanmaz.
    """
    edits: list[Edit] = []
    parts = [p.strip() for p in re.split(r"[;\n]+", command) if p.strip()]
    if not parts:
        raise IpcApplyError("PCB komutu bos. Ornek: " + " | ".join(ORNEKLER[:3]))
    for part in parts:
        normal = part.translate(_TR).lower().rstrip(".")
        for kind, pattern in _KALIPLAR:
            m = re.fullmatch(pattern, normal)
            if not m:
                continue
            ref = m.group(1).upper()
            if kind == "deger":
                # Deger buyuk/kucuk harf tasir (10k, 4.7uF); orijinal metinden al.
                raw = re.fullmatch(rf"(?i)\S+\s+\S+\s+(\S+)\s+\S+", part.strip().rstrip("."))
                args = (raw.group(1) if raw else m.group(2),)
            else:
                args = tuple(_number(g) for g in m.groups()[1:])
            edits.append(Edit(ref, kind, args, part))
            break
        else:
            raise IpcApplyError(f"Anlasilmadi: '{part}'. Ornekler: " + " | ".join(ORNEKLER))
    return edits


def plan_states(before: dict[str, FpState], edits: list[Edit]) -> tuple[dict[str, FpState], list[str]]:
    """Duzenlemeleri kopyada sirayla uygular; kilitli parcaya dokunmaz."""
    after = {ref: replace(s) for ref, s in before.items()}
    warnings: list[str] = []
    for e in edits:
        s = after.get(e.ref)
        if s is None:
            raise IpcApplyError(f"{e.ref}: canli PCB'de yok. Once 'PCB'yi oku' ile referanslari gorun.")
        if s.locked and e.kind not in ("kilit_ac", "kilitle"):
            raise IpcApplyError(f"{e.ref} kilitli; once '{e.ref} kilidini ac' komutunu ekleyin.")
        if e.kind == "tasi":
            s.x, s.y = e.args
        elif e.kind == "kaydir":
            s.x, s.y = s.x + e.args[0], s.y + e.args[1]
        elif e.kind == "aci":
            s.rot = e.args[0]
        elif e.kind == "dondur":
            s.rot = s.rot + e.args[0]
        elif e.kind == "kilitle":
            s.locked = True
        elif e.kind == "kilit_ac":
            s.locked = False
        elif e.kind == "deger":
            s.value = e.args[0]
            warnings.append(f"{e.ref}: deger yalnizca PCB'de degisir. Sematik degismezse KiCad F8 "
                            "(Sematikten PCB'yi guncelle) eski degeri geri yazar; sematigi de guncelleyin.")
        # KiCad footprint acisini -180..180 araliginda tutar.
        s.rot = ((s.rot + 180.0) % 360.0) - 180.0
        if s.rot == -180.0:
            s.rot = 180.0
    return after, warnings


def describe_plan(target: Path, before: dict[str, FpState], after: dict[str, FpState],
                  warnings: list[str]) -> str:
    lines = [f"PCB: {target}", "Canli PCB onizlemesi:"]
    for ref in sorted(after, key=_ref_key):
        a, b = before[ref], after[ref]
        if a.key() == b.key():
            continue
        parts = []
        if (round(a.x, 6), round(a.y, 6)) != (round(b.x, 6), round(b.y, 6)):
            parts.append(f"konum ({a.x:.3f}, {a.y:.3f}) -> ({b.x:.3f}, {b.y:.3f}) mm")
        if abs(_angle_delta(a.rot, b.rot)) > 1e-9:
            parts.append(f"aci {a.rot:.1f} -> {b.rot:.1f}")
        if a.locked != b.locked:
            parts.append("kilitlenecek" if b.locked else "kilidi acilacak")
        if a.value != b.value:
            parts.append(f"deger {a.value} -> {b.value}")
        lines.append(f"  {ref}: " + "; ".join(parts))
    if len(lines) == 2:
        raise IpcApplyError("Komut PCB'de hicbir seyi degistirmiyor.")
    lines += [f"UYARI: {w}" for w in warnings]
    lines.append("Aglar ve pad baglantilari degismez. Tek Ctrl+Z ile geri alinir; dosya otomatik kaydedilmez.")
    return "\n".join(lines)


# -- yazma -------------------------------------------------------------------

def prepare_edit(project: str | Path, command: str, *, socket_path=None) -> PcbEditPlan:
    expected = project_file(project, ".kicad_pcb")
    edits = parse_commands(command)
    with connection(socket_path) as kicad, tempfile.TemporaryDirectory(prefix="pcbqa-live-") as tmp:
        board = kicad.get_board()
        check_target(board, expected)
        digest = fingerprint(snapshot(board, Path(tmp)))
        before = states(board)
        after, warnings = plan_states(before, edits)
        description = describe_plan(expected, before, after, warnings)
        return PcbEditPlan(expected, board_identity(board), digest, command, before, after,
                           description, warnings)


def _mismatch(expected: FpState, actual: FpState) -> str:
    if (abs(expected.x - actual.x) > TOLERANS_MM or abs(expected.y - actual.y) > TOLERANS_MM
            or abs(_angle_delta(expected.rot, actual.rot)) > 1e-6
            or expected.locked != actual.locked or expected.value != actual.value):
        return (f"{expected.ref}: beklenen ({expected.x:.3f}, {expected.y:.3f}, {expected.rot:.1f}, "
                f"kilit={expected.locked}, {expected.value}), okunan ({actual.x:.3f}, {actual.y:.3f}, "
                f"{actual.rot:.1f}, kilit={actual.locked}, {actual.value})")
    return ""


def apply_edit(plan: PcbEditPlan, *, socket_path=None) -> str:
    changed = plan.changed
    if not changed:
        raise IpcApplyError("Planda degisiklik yok.")
    _, vector, angle = _load_kipy()
    with connection(socket_path) as kicad, tempfile.TemporaryDirectory(prefix="pcbqa-live-") as tmp:
        board = kicad.get_board()
        check_target(board, plan.target)
        if board_identity(board) != plan.identity or fingerprint(snapshot(board, Path(tmp))) != plan.fingerprint:
            raise IpcApplyError("PCB onizlemeden sonra degisti. Yeni onizleme alin; eski plan uygulanmadi.")
        by_ref = index(board)
        items = []
        for ref in changed:
            fp, target = by_ref[ref], plan.after[ref]
            fp.position = vector.from_xy_mm(target.x, target.y)
            fp.orientation = angle.from_degrees(target.rot)
            fp.locked = target.locked
            if target.value != plan.before[ref].value:
                fp.value_field.text.value = target.value
            items.append(fp)
        commit = board.begin_commit()
        try:
            updated = board.update_items(items)
            if updated is not None and len(updated) != len(items):
                raise IpcApplyError(f"KiCad {len(items)} footprint beklenirken {len(updated)} guncelledi.")
            board.push_commit(commit, "pcbqa: " + plan.command[:120])
        except Exception as exc:
            try:
                board.drop_commit(commit)
            except Exception:
                pass
            if isinstance(exc, IpcApplyError):
                raise
            raise IpcApplyError(f"KiCad canli PCB yazmasi basarisiz: {exc}") from exc
        # KiCad 10.0.4 commit ONCESI GetItems'a eski konumu verir; dogrulama sonra.
        try:
            current = states(board)
            errors = [f"{ref}: yazmadan sonra bulunamadi" for ref in plan.after if ref not in current]
            errors += [f"beklenmeyen yeni footprint: {ref}" for ref in current if ref not in plan.after]
            errors += [m for ref, s in plan.after.items() if ref in current
                       for m in [_mismatch(s, current[ref])] if m]
        except IpcApplyError as exc:
            errors = [str(exc)]
        if errors:
            raise IpcApplyError("Canli PCB yazildi ama dogrulama basarisiz; KiCad'de Ctrl+Z ile geri alin: "
                                + "; ".join(errors[:5]))
    return (f"Canli PCB dogrulandi: {len(changed)} bilesen yazildi ({', '.join(changed)}).\n"
            "KiCad'de Ctrl+Z ile geri alabilir, Ctrl+S ile kaydedebilirsiniz.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Canli PCB okuma ve komutla yazma")
    parser.add_argument("project")
    parser.add_argument("--komut", help="ornek: 'R1 konumunu 50 30 yap; U1 90 dondur'")
    parser.add_argument("--uygula", action="store_true")
    parser.add_argument("--socket")
    args = parser.parse_args(argv)
    try:
        if args.komut:
            plan = prepare_edit(args.project, args.komut, socket_path=args.socket)
            print(plan.description)
            if args.uygula:
                print(apply_edit(plan, socket_path=args.socket))
        elif args.uygula:
            raise IpcApplyError("--uygula icin --komut gerekli.")
        else:
            print(read_live(args.project, socket_path=args.socket))
    except (IpcApplyError, OSError, ValueError) as exc:
        print(f"hata: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
