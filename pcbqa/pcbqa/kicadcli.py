"""`kicad-cli` sarmalayicisi.

Asama 0'in tamami bu arac uzerinden calisir; IPC API (kicad-python) gerekmez.
Bunun iki faydasi var:
  * KiCad'in acik olmasi gerekmez, CI/komut satirindan calisir
  * IPC bindings'in alpha olmasindan ve Python surum destegi sorunlarindan etkilenmez
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Windows'ta varsayilan kurulum kokleri (surum klasoru joker)
_WINDOWS_GLOBS = [
    r"C:\Program Files\KiCad\*\bin\kicad-cli.exe",
    r"C:\Program Files (x86)\KiCad\*\bin\kicad-cli.exe",
]
_POSIX_CANDIDATES = [
    "/usr/bin/kicad-cli",
    "/usr/local/bin/kicad-cli",
    "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
]


class KicadCliError(RuntimeError):
    pass


def find_kicad_cli(explicit: str | None = None) -> Path:
    """kicad-cli'yi bulur. Sirasiyla: parametre, ortam degiskeni, PATH, bilinen konumlar."""
    if explicit:
        p = Path(explicit)
        if p.exists():
            return p
        raise KicadCliError(f"Belirtilen kicad-cli bulunamadi: {explicit}")

    env = os.environ.get("PCBQA_KICAD_CLI")
    if env and Path(env).exists():
        return Path(env)

    on_path = shutil.which("kicad-cli")
    if on_path:
        return Path(on_path)

    matches: list[Path] = []
    for pattern in _WINDOWS_GLOBS:
        root = Path(pattern).parent.parent.parent  # C:\Program Files\KiCad
        if root.exists():
            matches.extend(root.glob("*/bin/kicad-cli.exe"))
    for cand in _POSIX_CANDIDATES:
        if Path(cand).exists():
            matches.append(Path(cand))

    if matches:
        # En yuksek surum numarasi
        return sorted(matches, key=lambda p: p.parts)[-1]

    raise KicadCliError(
        "kicad-cli bulunamadi. PCBQA_KICAD_CLI ortam degiskenini ayarlayin "
        "veya --kicad-cli ile yolunu verin."
    )


@dataclass
class CliResult:
    ok: bool
    output_path: Path | None
    stdout: str
    stderr: str
    returncode: int


class KicadCli:
    """kicad-cli cagrilarini saran ince katman."""

    def __init__(self, exe: str | Path | None = None, timeout: int = 180) -> None:
        self.exe = find_kicad_cli(str(exe) if exe else None)
        self.timeout = timeout

    def version(self) -> str:
        res = self._run(["version"])
        return res.stdout.strip()

    # ------------------------------------------------------------------ komutlar

    def export_netlist(self, schematic: Path, out: Path) -> CliResult:
        """Sematikten XML netlist. Neyin neye bagli oldugunu buradan ogreniyoruz."""
        out.parent.mkdir(parents=True, exist_ok=True)
        return self._run(
            ["sch", "export", "netlist", "--format", "kicadxml", "-o", str(out), str(schematic)],
            out,
        )

    def erc(self, schematic: Path, out: Path) -> CliResult:
        """KiCad'in kendi elektriksel kural kontrolu (JSON rapor)."""
        out.parent.mkdir(parents=True, exist_ok=True)
        return self._run(
            ["sch", "erc", "--format", "json", "--severity-all", "-o", str(out), str(schematic)],
            out,
        )

    def drc(self, board: Path, out: Path) -> CliResult:
        """KiCad'in kendi tasarim kurali kontrolu (JSON rapor)."""
        out.parent.mkdir(parents=True, exist_ok=True)
        return self._run(
            ["pcb", "drc", "--format", "json", "--severity-all", "-o", str(out), str(board)],
            out,
        )

    # ------------------------------------------------------------------ ic isler

    def _run(self, args: list[str], out: Path | None = None) -> CliResult:
        try:
            proc = subprocess.run(
                [str(self.exe), *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise KicadCliError(f"kicad-cli zaman asimi: {' '.join(args)}") from exc

        # DRC/ERC ihlal buldugunda sifir disi kod donebilir; dosya olustuysa basarili sayariz.
        produced = out is not None and out.exists()
        ok = proc.returncode == 0 or produced
        return CliResult(
            ok=ok,
            output_path=out if produced else None,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            returncode=proc.returncode,
        )


# ---------------------------------------------------------------------- raporlar


def load_violations(path: Path) -> list[dict]:
    """ERC/DRC JSON raporunu duz bir ihlal listesine cevirir.

    Iki dosyanin yapisi farkli:
      ERC : {"sheets": [{"path": "/", "violations": [...]}, ...]}
      DRC : {"violations": [...], "unconnected_items": [...], "schematic_parity": [...]}
    """
    if not path or not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    found: list[dict] = []

    for sheet in data.get("sheets", []) or []:
        for item in sheet.get("violations", []) or []:
            item = dict(item)
            item.setdefault("_sheet", sheet.get("path", ""))
            found.append(item)

    for key in ("violations", "unconnected_items", "schematic_parity"):
        for item in data.get(key, []) or []:
            item = dict(item)
            item["_group"] = key
            found.append(item)

    return found


def describe_violation(item: dict) -> tuple[str, str, str]:
    """(severity, kod, aciklama) uclusu dondurur."""
    severity = (item.get("severity") or "warning").lower()
    code = item.get("type") or item.get("_group") or "unknown"
    text = item.get("description") or ""

    items = item.get("items") or []
    parts = [i.get("description", "") for i in items if i.get("description")]
    if parts:
        text = f"{text} [{' <-> '.join(parts)}]" if text else " <-> ".join(parts)

    return severity, code, text.strip()
