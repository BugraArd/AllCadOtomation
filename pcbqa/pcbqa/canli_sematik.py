"""Canli sematik icin ayri, surumu eslesen KiCad/Python ortami."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from .canli import project_file
from .ipc import IpcApplyError

BASE = Path(__file__).resolve().parent.parent
CONFIG = BASE / ".runtime/sematik.json"
PROJECTS = BASE.parent / "CanliProjeler"


def configuration():
    if not CONFIG.is_file():
        raise IpcApplyError("Canli sematik ortami kurulu degil. KURULUM.md: Canli sematik.")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    for key in ("python", "cli"):
        if not Path(config[key]).is_file():
            raise IpcApplyError(f"Canli sematik {key} bulunamadi: {config[key]}")
    return config


def environment(config):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["KICAD_CONFIG_HOME"] = config["profile"]
    env["TEMP"] = env["TMP"] = config["temp"]
    for version in (9, 10, 11):
        for kind, folder in (("SYMBOL", "symbols"), ("FOOTPRINT", "footprints"),
                             ("3DMODEL", "3dmodels"), ("TEMPLATE", "template")):
            env[f"KICAD{version}_{kind}_DIR"] = str(Path(config["stock"]) / folder)
    return env


def request(action, project="", **kwargs):
    config = configuration()
    Path(config["temp"]).mkdir(parents=True, exist_ok=True)
    payload = dict(action=action, project=str(project), config=config, **kwargs)
    env = environment(config)
    env["KICAD_CONFIG_HOME"] = config["profile"] + "-worker"
    result = subprocess.run(
        [config["python"], "-m", "pcbqa.canli_sematik_worker"],
        input=json.dumps(payload), text=True, encoding="utf-8", capture_output=True,
        cwd=BASE, env=env, timeout=120,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        response = json.loads(result.stdout)
    except ValueError as exc:
        raise IpcApplyError("Canli sematik yaniti okunamadi: " + result.stderr[-1500:]) from exc
    if result.returncode or not response.get("ok"):
        raise IpcApplyError(response.get("error", "Canli sematik islemi basarisiz."))
    return response["result"]


def open_copy(project):
    """Deneysel dosya bicimini kullanicinin asil projesinden ayirir."""
    config = configuration()
    source = project_file(project, ".kicad_sch")
    # Acik editorun kaydedilmemis halini disk kopyasi diye sunmayiz.
    if list(source.parent.glob("~*.lck")):
        raise IpcApplyError("Kaynak proje acik. Once KiCad'de kaydedip kapatin; sonra canli kopyayi acin.")
    existing_copy = PROJECTS.resolve() in source.parents and (source.parent / ".pcbqa-canli.json").is_file()
    dest = source.parent if existing_copy else PROJECTS / (source.stem + "-" + uuid.uuid4().hex[:8])
    if source.parent == BASE or source.parent in dest.parents:
        raise IpcApplyError("Projenin kendi klasorundeki .kicad_sch dosyasini secin.")
    session = BASE / ".runtime/sematik-session.json"
    if session.exists():
        from .kurulum import running_kicad
        previous = json.loads(session.read_text(encoding="utf-8"))
        if any(f"(pid {previous['pid']})" in x for x in running_kicad()):
            raise IpcApplyError("Canli sematik penceresi zaten acik; once o pencereyi kapatin.")
        try:
            request("check", json.loads(session.read_text(encoding="utf-8"))["project"])
        except (IpcApplyError, OSError, ValueError):
            pass
        else:
            raise IpcApplyError("Canli sematik zaten acik; once mevcut canli pencereyi kapatin.")
    if not existing_copy:
        shutil.copytree(source.parent, dest, ignore=shutil.ignore_patterns("~*.lck", "*-backups", "*.kicad_prl"))
        (dest / ".pcbqa-canli.json").write_text(json.dumps({"source": str(source), "version": config["version"]}), encoding="utf-8")
    profile = Path(config["profile"]) / "10.99"
    if not profile.exists():
        profile.mkdir(parents=True)
        stable = Path(os.environ.get("APPDATA", "")) / "kicad/10.0"
        for name in ("kicad_common.json", "eeschema.json", "sym-lib-table", "fp-lib-table"):
            if (stable / name).is_file():
                shutil.copy2(stable / name, profile / name)
    # Headless okuyucu da profili olusturabilir; klasorun varligi API'nin
    # acik oldugunu gostermez. Bu profil yalnizca bizim ayri editorumuzundur.
    path = profile / "kicad_common.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data.setdefault("api", {})["enable_server"] = True
    data["api"]["interpreter_path"] = str(Path(config["python"]).with_name("pythonw.exe"))
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    Path(config["temp"]).mkdir(parents=True, exist_ok=True)
    target = dest / source.name
    process = subprocess.Popen([str(Path(config["cli"]).with_name("eeschema.exe")), str(target)],
                               env=environment(config))
    session.write_text(json.dumps(dict(project=str(target), pid=process.pid)), encoding="utf-8")
    return {"project": str(target), "description":
            f"Canli sematik kopyasi aciliyor: {target}\nDegisiklikleri bu kopyada Ctrl+S ile kaydedin."}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Canli KiCad sematik baglantisi")
    parser.add_argument("project")
    parser.add_argument("--ac-kopya", action="store_true")
    parser.add_argument("--komut")
    parser.add_argument("--uygula", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.ac_kopya:
            result = open_copy(args.project)
        elif args.komut:
            result = request("prepare", args.project, command=args.komut)
            print(result["description"])
            if not args.uygula:
                return 0
            result = request("apply", args.project, plan=result)
        elif args.uygula:
            raise IpcApplyError("--uygula icin --komut gerekli.")
        else:
            result = request("check", args.project)
        print(result["description"])
        return 0
    except (IpcApplyError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"hata: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
