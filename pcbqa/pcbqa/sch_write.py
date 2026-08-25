"""Sematige guvenli yazma (Asama 4c).

KiCad 10'da IPC sematikte calismaz, yani PCB tarafindaki gibi "calisan
editore uygula, undo ile geri al" secenegi YOKTUR. Yazma dogrudan dosyaya
yapilir. Bu da su korumalari zorunlu kilar:

1. ATOMIK YAZMA. Yarim yazilmis bir .kicad_sch, kullanicinin tasarimini
   kaybetmesi demektir. Once ayni dizine gecici dosya yazilir, `fsync` ile
   diske indirilir, sonra `os.replace` ile yerine gecirilir. `os.replace`
   Windows'ta da atomiktir; ayni dizin sart cunku farkli birimler arasinda
   atomiklik garanti edilmez.

2. KICAD ACIKSA YAZMA. Eeschema dosyayi bellekte tutar; biz yazarken
   kullanici kaydederse bizim degisikligimiz sessizce kaybolur (ya da tam
   tersi). KiCad proje acikken `~<proje>.kicad_pro.lck` olusturur; onu
   goruyorsak yazmayi reddederiz.

3. YEDEK. Yazmadan once dosyanin bir kopyasi alinir. Git commit'in yerini
   tutmaz ama en azindan tek adimlik geri donus verir.

UUID'ler ASLA yeniden uretilmez: KiCad sembol orneklerini ve netlist yollarini
UUID uzerinden izler; yenilenirse PCB ile sematik arasindaki bag kopar.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .sexpr import dumps


class SchWriteError(RuntimeError):
    """Yazma reddedildi veya basarisiz oldu."""


@dataclass
class WriteResult:
    path: Path
    written: bool
    backup: Path | None = None
    bytes_written: int = 0
    notes: list[str] = field(default_factory=list)


def lock_files(sch_path: Path) -> list[Path]:
    """Proje KiCad'de acik mi? Acan kilit dosyalarini dondurur.

    KiCad bir proje acikken `~<ad>.kicad_pro.lck` (ve bazi surumlerde
    `~<ad>.kicad_sch.lck`) olusturur. Bos liste "acik degil" demektir.
    """
    sch_path = Path(sch_path)
    folder = sch_path.parent
    candidates = [
        folder / f"~{sch_path.stem}.kicad_pro.lck",
        folder / f"~{sch_path.stem}.kicad_sch.lck",
        folder / f"~{sch_path.name}.lck",
    ]
    found = [c for c in candidates if c.exists()]
    # Proje adi sematik adindan farkli olabilir; klasordeki tum kilitlere bak
    found.extend(p for p in folder.glob("~*.lck") if p not in found)
    return found


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> int:
    """Metni atomik olarak yazar. Yazilan bayt sayisini dondurur.

    Gecici dosya HEDEFLE AYNI DIZINDE olusturulur; `os.replace` yalnizca ayni
    dosya sisteminde atomiktir.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.stem}-", suffix=".tmp", dir=str(path.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        data = text.encode(encoding)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        return len(data)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def backup_file(path: Path, suffix: str = ".pcbqa-bak") -> Path:
    """Dosyanin yanina zaman damgali bir yedek birakir."""
    path = Path(path)
    target = path.with_name(path.name + suffix)
    counter = 1
    while target.exists():
        target = path.with_name(f"{path.name}{suffix}.{counter}")
        counter += 1
    shutil.copy2(path, target)
    return target


def write_tree(
    path: Path,
    root,
    *,
    apply: bool = False,
    backup: bool = True,
    allow_open_project: bool = False,
) -> WriteResult:
    """Ayristirilmis s-expression agacini bir .kicad_sch dosyasina yazar.

    Varsayilan DRY-RUN'dir: `apply=True` verilmedikce hicbir sey yazilmaz.
    """
    path = Path(path)
    notes: list[str] = []

    locks = lock_files(path)
    if locks and not allow_open_project:
        names = ", ".join(p.name for p in locks[:3])
        raise SchWriteError(
            f"proje KiCad'de acik gorunuyor ({names}); once kapatin. "
            "Bilincli devam etmek icin allow_open_project=True."
        )
    if locks:
        notes.append(f"UYARI: kilit dosyasi var ({locks[0].name}), yine de yaziliyor")

    text = dumps(root) + "\n"

    if not apply:
        notes.append("dry-run: dosyaya dokunulmadi")
        return WriteResult(path=path, written=False, bytes_written=len(text.encode("utf-8")), notes=notes)

    made_backup = backup_file(path) if (backup and path.exists()) else None
    written = atomic_write_text(path, text)
    return WriteResult(path=path, written=True, backup=made_backup, bytes_written=written, notes=notes)
