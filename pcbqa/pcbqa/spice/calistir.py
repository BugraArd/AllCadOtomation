"""ngspice'i bulur, ayri surecte calistirir, `wrdata` ciktilarini okur.

Arka uclar (bulunma sirasiyla):
  1. PCBQA_NGSPICE ortam degiskeni -> ngspice konsol programi (exe)
  2. PATH uzerinde `ngspice` / `ngspice_con`
  3. PCBQA_NGSPICE_DLL ya da KiCad kurulumundaki ngspice.dll -> isci.py
     (paylasimli kutuphane, ayri Python sureci)

KiCad 10 Windows kurulumu ngspice.dll (ngspice-46) getiriyor ama konsol
programini getirmiyor (olculdu, 2026-10-01). Yani ek kurulum gerekmeden
3. yol calisir.

Sonuc bicimi: `set wr_vecnames` + `set wr_singlescale` ile yazilan `wrdata`
dosyasi - ilk satir vektor adlari, sonraki satirlar degerler.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


class SpiceHatasi(RuntimeError):
    pass


@dataclass
class ArkaUc:
    tur: str        # "exe" | "dll"
    yol: Path

    def aciklama(self) -> str:
        return f"ngspice {'konsol' if self.tur == 'exe' else 'paylasimli kutuphane'}: {self.yol}"


@dataclass
class SpiceCalismasi:
    ok: bool
    arka_uc: str
    gunluk: list[str] = field(default_factory=list)
    hatalar: list[str] = field(default_factory=list)


def _kicad_dll() -> Path | None:
    try:
        from ..kicadcli import find_kicad_cli

        cli = find_kicad_cli()
    except Exception:
        return None
    aday = cli.parent / ("ngspice.dll" if os.name == "nt" else "libngspice.so")
    return aday if aday.is_file() else None


def arka_uc_bul() -> ArkaUc | None:
    env = os.environ.get("PCBQA_NGSPICE")
    if env and Path(env).is_file():
        return ArkaUc("exe", Path(env))
    for ad in ("ngspice", "ngspice_con"):
        yol = shutil.which(ad)
        if yol:
            return ArkaUc("exe", Path(yol))
    env = os.environ.get("PCBQA_NGSPICE_DLL")
    if env and Path(env).is_file():
        return ArkaUc("dll", Path(env))
    dll = _kicad_dll()
    if dll is not None:
        return ArkaUc("dll", dll)
    return None


def calistir(devre: Path, arka_uc: ArkaUc, zaman_asimi: float = 120.0) -> SpiceCalismasi:
    """`devre` dosyasini (.control blogu iceren) calistirir; cwd devrenin klasoru."""
    devre = Path(devre)
    try:
        if arka_uc.tur == "exe":
            proc = subprocess.run(
                [str(arka_uc.yol), "-b", devre.name], cwd=devre.parent,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=zaman_asimi)
            gunluk = (proc.stdout + proc.stderr).splitlines()
            hatalar = [s for s in gunluk if "error" in s.lower()]
            return SpiceCalismasi(proc.returncode == 0, arka_uc.aciklama(), gunluk[-80:], hatalar)
        isci = Path(__file__).with_name("isci.py")
        proc = subprocess.run(
            [sys.executable, str(isci), "--dll", str(arka_uc.yol), str(devre)],
            cwd=devre.parent, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=zaman_asimi)
    except subprocess.TimeoutExpired as exc:
        raise SpiceHatasi(f"ngspice zaman asimi ({zaman_asimi:g} s)") from exc
    satir = (proc.stdout or "").strip().splitlines()
    if proc.returncode != 0 or not satir:
        raise SpiceHatasi(f"ngspice iscisi basarisiz (kod {proc.returncode}): {(proc.stderr or '')[-400:]}")
    try:
        veri = json.loads(satir[-1])
    except json.JSONDecodeError as exc:
        raise SpiceHatasi(f"isci ciktisi okunamadi: {satir[-1][:200]}") from exc
    ok = veri.get("kod") == 0 and not veri.get("hatalar") and veri.get("cikis") in (None, 0)
    return SpiceCalismasi(ok, arka_uc.aciklama(), veri.get("gunluk", []), veri.get("hatalar", []))


def wrdata_oku(yol: Path) -> list[dict[str, float]]:
    """wrdata dosyasi -> satir basina {vektor: deger}.

    `op` analizinde ngspice ilk sutuna bir olcek vektoru koyar; adlar
    baslik satirindan okundugu icin bu bir sorun degildir.
    """
    yol = Path(yol)
    if not yol.is_file():
        raise SpiceHatasi(f"benzetim ciktisi yok: {yol.name}")
    satirlar = [s.split() for s in yol.read_text(encoding="utf-8", errors="replace").splitlines() if s.strip()]
    if not satirlar:
        raise SpiceHatasi(f"bos benzetim ciktisi: {yol.name}")
    adlar = [a.lower() for a in satirlar[0]]
    out = []
    for s in satirlar[1:]:
        try:
            out.append({ad: float(v) for ad, v in zip(adlar, s)})
        except ValueError:
            continue
    return out
