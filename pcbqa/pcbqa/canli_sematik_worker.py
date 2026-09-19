"""Yalnizca eslesen nightly istemcisinde calisan sematik isleri.

GUI'nin stabil kipy ortamina protokol yuklenmez. JSON stdin/stdout kullanilir.
"""
from __future__ import annotations

import base64
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tempfile

from .canli import project_file
from .ipc import IpcApplyError


def connect(config):
    from kipy import KiCad
    # Nightly ayni klasorde eski soket bulursa PID eki kullanabilir.
    socket_dir = Path(config["temp"]) / "kicad"
    sockets = [socket_dir / "api.sock"] + sorted(socket_dir.glob("api-*.sock"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    errors = []
    for path in sockets:
        k = KiCad(socket_path="ipc://" + str(path), timeout_ms=4000)
        try:
            version = k.get_version()
            if version.full_version != config["version"]:
                raise IpcApplyError(f"Eslesmeyen KiCad: {version.full_version}")
            k.get_schematic()
            return k
        except Exception as exc:
            errors.append(str(exc))
            k.close()
    raise IpcApplyError("Canli sematik hazir degil. Canli kopyayi acin ve KiCad diyaloglarini tamamlayin. "
                        + "; ".join(errors[-2:]))


def check_target(schematic, project):
    expected = project_file(project, ".kicad_sch")
    doc = schematic.document
    if not doc.project.path or (Path(doc.project.path) / schematic.name).resolve() != expected:
        raise IpcApplyError("Acik sematik ile secilen proje farkli; hicbir degisiklik yapilmadi.")
    return expected


def snapshot(schematic, folder, name):
    from .sexpr import children, parse_with_stats
    path = folder / name
    schematic.save_as(str(path), overwrite=True, include_project=False)
    root, _ = parse_with_stats(path.read_text(encoding="utf-8"))
    if list(children(root, "sheet")):
        raise IpcApplyError("Canli komutlar su an tek sayfali sematikleri destekliyor.")
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def items(schematic):
    # Bos tur listesi 'hepsi' anlamina gelmiyor (10.99 gercek olcum).
    return list(schematic.get_symbols()) + list(schematic.get_lines()) + list(
        schematic.get_labels()) + list(schematic.get_junctions())


def encode(item):
    return {"type": item.proto.DESCRIPTOR.full_name,
            "data": base64.b64encode(item.proto.SerializeToString(deterministic=True)).decode()}


def decode(data):
    from google.protobuf import descriptor_pool, message_factory
    from kipy.schematic_types import unwrap
    from kipy.util import pack_any
    cls = message_factory.GetMessageClass(descriptor_pool.Default().FindMessageTypeByName(data["type"]))
    message = cls.FromString(base64.b64decode(data["data"], validate=True))
    return unwrap(pack_any(message))


def net_signature(path, cli):
    from .kicadcli import KicadCli
    from .netlist import read_netlist
    out = path.with_suffix(".xml")
    result = KicadCli(cli).export_netlist(path, out)
    if not result.ok:
        raise IpcApplyError("KiCad netlist dogrulamasi basarisiz: " + result.stderr)
    net = read_netlist(out)
    # API ayni kutuphane sembolunu eklerken C -> C_1/C_2 yerel tanim adi
    # uretebilir. Elektriksel kimlik ref/deger/footprint ve pin aglaridir.
    data = {"components": sorted((c.ref, c.value, c.footprint) for c in net.components.values()),
            "nets": sorted((n.name, sorted((x.ref, x.pin) for x in n.nodes)) for n in net.nets)}
    return json.loads(json.dumps(data))


def write_checked(schematic, changes, create):
    from kipy.proto.common.commands import editor_commands_pb2 as commands
    from kipy.util import pack_any
    command = commands.CreateItems() if create else commands.UpdateItems()
    command.header.document.CopyFrom(schematic.document)
    command.items.extend(pack_any(x.proto) for x in changes)
    response = schematic.client.send(command, commands.CreateItemsResponse if create else commands.UpdateItemsResponse)
    results = response.created_items if create else response.updated_items
    if len(results) != len(changes) or any(x.status.code != commands.ISC_OK for x in results):
        errors = "; ".join(x.status.error_message for x in results if x.status.code != commands.ISC_OK)
        raise IpcApplyError("KiCad oge islemini reddetti: " + errors)


def prepare(k, project, command, config):
    from kipy import KiCad
    from .komut import anla, uygula
    s = k.get_schematic()
    target = check_target(s, project)
    with tempfile.TemporaryDirectory(prefix="pcbqa-sch-preview-") as tmp:
        folder = Path(tmp)
        path = snapshot(s, folder, target.name)
        before = digest(path)
        original = {x.id.value: encode(x) for x in items(s)}
        # Mevcut deger degisikligi acik ve sinirli bir kaliptir.
        normalized = command.translate(str.maketrans("\u0131\u0130\u011f\u011e\u015f\u015e", "iIgGsS"))
        match = re.fullmatch(r"([A-Za-z]+\d+)\s+degerini\s+(\S+)\s+(?:yap|degistir)", normalized.strip(), re.I)
        if match:
            ref, value = match.group(1).upper(), match.group(2)
            selected = [x for x in s.get_symbols() if x.reference_field.text.value == ref]
            if len(selected) != 1 or selected[0].locked:
                raise IpcApplyError("Tek ve kilitsiz bir sembol secilmeli: " + ref)
            symbol = selected[0]
            old = symbol.value_field.text.value
            if old == value:
                raise IpcApplyError("Sembol degeri zaten " + value)
            symbol.value_field.text.value = value
            creates, updates = [], [encode(symbol)]
            signature = net_signature(path, config["cli"])
            for component in signature["components"]:
                if component[0] == ref:
                    component[1] = value
            description = f"{ref}: {old} -> {value}"
        else:
            parsed = anla(command)
            if not parsed.ok:
                raise IpcApplyError("Komut anlasilmadi. Ornek: 2 adet 100nF kondansator ekle; R1 degerini 10k yap.")
            results = uygula(parsed, path, apply=True, backup=False, kicad_cli=config["cli"])
            if len(results) != len(parsed.eylemler) or not all(
                    x.applied and x.plan.ok and x.diff is not None and x.diff.ok for x in results):
                raise IpcApplyError("Ekleme plani netlist korumasindan gecmedi.")
            signature = net_signature(path, config["cli"])
            with KiCad(headless=True, kicad_cli_path=config["cli"], file_path=str(path), timeout_ms=10000) as reader:
                planned = {x.id.value: encode(x) for x in items(reader.get_schematic())}
            # Dosya okuyucusunun mevcut sembolleri yeniden serilestirmesi alanlari
            # normalize edebilir; yalnizca yeni UUID'ler aktarilir, eskilere yazilmaz.
            if not original.keys() <= planned.keys():
                raise IpcApplyError("Plan mevcut sematik ogelerini kaldiriyor; reddedildi.")
            creates = [v for key, v in planned.items() if key not in original]
            updates = []
            if not creates:
                raise IpcApplyError("Eklenecek sematik ogesi yok.")
            description = "\n".join(x.plan.describe() for x in results)
            description += "\n" + "\n".join(parsed.notlar)
        return dict(target=str(target), fingerprint=before, command=command,
                    creates=creates, updates=updates, originals=original, signature=signature,
                    description=description + "\nTek Ctrl+Z ile geri alinir. Dosya otomatik kaydedilmez.")


def apply(k, project, plan, config):
    s = k.get_schematic()
    target = check_target(s, project)
    if str(target) != plan["target"]:
        raise IpcApplyError("Plan baska bir sematige ait.")
    with tempfile.TemporaryDirectory(prefix="pcbqa-sch-apply-") as tmp:
        folder = Path(tmp)
        if digest(snapshot(s, folder, target.name)) != plan["fingerprint"]:
            raise IpcApplyError("Sematik onizlemeden sonra degisti. Yeni onizleme alin.")
        created = [decode(x) for x in plan["creates"]]
        updated = [decode(x) for x in plan["updates"]]
        transaction = s.begin_commit()
        try:
            if created:
                write_checked(s, created, True)
            if updated:
                write_checked(s, updated, False)
            s.push_commit(transaction, "pcbqa: " + plan["command"][:120])
        except Exception:
            s.drop_commit(transaction)
            raise
        # KiCad degisiklikleri commit sonrasinda okuma API'sine yansitir.
        try:
            current = {x.id.value: x for x in items(s)}
            changed_ids = {x.id.value for x in updated}
            for key, old in plan["originals"].items():
                if key not in changed_ids and (key not in current or encode(current[key]) != old):
                    raise IpcApplyError("Mevcut bir sematik ogesi beklenmedik sekilde degisti.")
            for x in created + updated:
                if x.id.value not in current:
                    raise IpcApplyError("Yazilan oge geri okunamadi.")
                if hasattr(x, "position") and current[x.id.value].position != x.position:
                    raise IpcApplyError("Yazilan oge konumu dogrulanamadi.")
            for x in updated:
                if current[x.id.value].value_field.text.value != x.value_field.text.value:
                    raise IpcApplyError("Sembol degeri dogrulanamadi.")
            actual = snapshot(s, folder, target.name)
            if plan["signature"] is not None and net_signature(actual, config["cli"]) != plan["signature"]:
                raise IpcApplyError("Canli netlist hazirlanan baglantilarla eslesmiyor.")
        except Exception as exc:
            raise IpcApplyError(f"Canli islem yapildi ancak dogrulama basarisiz: {exc}. KiCad'de Ctrl+Z ile geri alin.") from exc
        return {"description": f"Canli sematik dogrulandi: {len(created)} yeni oge, {len(updated)} deger degisikligi.\n"
                "KiCad acik; Ctrl+Z ile geri alabilir, Ctrl+S ile kaydedebilirsiniz.",
                "created": len(created), "updated": len(updated)}


def dispatch(payload):
    config = payload["config"]
    with connect(config) as k:
        action = payload["action"]
        if action == "prepare":
            return prepare(k, payload["project"], payload["command"], config)
        if action == "apply":
            return apply(k, payload["project"], payload["plan"], config)
        if action != "check":
            raise IpcApplyError("Bilinmeyen canli sematik islemi.")
        s = k.get_schematic()
        target = check_target(s, payload["project"])
        return {"description": f"Canli sematik hazir: {target}\nKiCad {k.get_version()}\n"
                f"{len(s.get_symbols())} sembol, {len(s.get_lines())} tel/cizgi.\n"
                "Parca ekleme, yeni parcalari aglara baglama ve deger degistirme kullanilabilir."}


def main():
    try:
        payload = json.load(sys.stdin)
        with redirect_stdout(io.StringIO()):
            result = dispatch(payload)
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=True))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
