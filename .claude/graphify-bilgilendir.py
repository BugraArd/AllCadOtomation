"""GRAPHIFY'I BILGILENDIR - her karar, her hata duzeltmesi, her plan sonrasi.

    python .claude/graphify-bilgilendir.py

## Neden bir betik, neden bir soz degil

"Her kararda graphify'i guncelle" bir davranis kurali; kurallar unutulur.
Bu betik onu tek komuta indiriyor, boylece unutmanin bedeli kalmiyor.

## Ne yapar (sirayla)

  1. Beads bilgisini markdown'a aktarir. Beads bir Dolt veritabaninda duruyor
     ve HICBIR dosya tarayicisi onu goremez - graphify dahil. Her hafiza ayri
     dosya olur ki bilgi grafiginde her biri kendi dugumu olsun.
  2. `graphify update .` ile kod grafigini tazeler (AST, yerel, jeton yok).
  3. Elle verilen topluluk adlarini geri uygular - `graphify update` onlari
     siliyor (bkz. graphify-etiketle.py).

## Ne YAPMAZ

Belge (markdown/yaml) icerigini yeniden TARAMAZ; o anlamsal tarama istiyor ve
alt-ajan gerektiriyor. Yani yeni bir beads kaydinin METNI dosyaya duser ve
aranabilir olur, ama kavram dugumu ve gerekce kenarlari ancak
`/graphify --update` ile olusur. Betik bunu cikti olarak SOYLER; sessizce
"guncellendi" demez.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
HEDEF = KOK / "pcbqa" / "docs" / "hafiza"
# `bd` bir npm shim'i; Windows'ta subprocess uzantisiz adi bulamiyor.
BD = str(Path.home() / "AppData" / "Roaming" / "npm" / "bd.cmd")


def kabuk(args: list[str], **kw) -> str:
    args = [BD if a == "bd" else a for a in args]
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(KOK), **kw)
    if proc.returncode != 0:
        raise RuntimeError(f"{args[0]} basarisiz: {(proc.stderr or proc.stdout)[:300]}")
    return proc.stdout


# --------------------------------------------------------------------------
# 1) Beads -> markdown
# --------------------------------------------------------------------------


def hafiza_anahtarlari() -> list[str]:
    metin = kabuk(["bd", "memories"])
    return [m.group(1) for m in re.finditer(r"^  ([a-z0-9][a-z0-9-]+)$", metin, re.M)]


def yaz_hafizalar() -> int:
    HEDEF.mkdir(parents=True, exist_ok=True)
    guncel: set[str] = set()
    for anahtar in hafiza_anahtarlari():
        govde = kabuk(["bd", "recall", anahtar]).strip()
        dosya = HEDEF / f"{anahtar}.md"
        icerik = (
            f"# {anahtar.replace('-', ' ').capitalize()}\n\n"
            f"> Beads kalici hafizasi (`bd recall {anahtar}`). Kaynak Dolt veritabani;\n"
            f"> bu dosya graphify gorebilsin diye disa aktarilmis kopyasidir.\n\n"
            f"{govde}\n"
        )
        # Degismediyse dokunma: dosya zaman damgasi graphify'in bayatlik
        # olcumunu yanlis tetiklemesin.
        if not dosya.is_file() or dosya.read_text(encoding="utf-8") != icerik:
            dosya.write_text(icerik, encoding="utf-8")
        guncel.add(dosya.name)

    # Silinen bir hafiza dosyada kalmamali - yoksa grafik olmayan bir karari
    # dogruymus gibi tasir.
    for eski in HEDEF.glob("*.md"):
        if eski.name.startswith("beads-") or eski.name in guncel:
            continue
        eski.unlink()
        print(f"  silindi (artik beads'te yok): {eski.name}")
    return len(guncel)


def yaz_kayitlar() -> tuple[int, int]:
    veri = json.loads(kabuk(["bd", "list", "--status", "open,closed", "--json"]))
    acik = [i for i in veri if i.get("status") != "closed"]
    kapali = [i for i in veri if i.get("status") == "closed"]

    def blok(kayitlar: list[dict], baslik: str, dosya: str) -> None:
        satirlar = [f"# {baslik}", "",
                    "> Beads kayitlari (`bd list --json`). Her kayit bir kararin ya da",
                    "> olcumun gerekcesini tasir; kod bunlari anlatmaz.", ""]
        for k in sorted(kayitlar, key=lambda x: (x.get("priority", 9), x.get("id", ""))):
            satirlar += [f"## {k.get('id')} - {k.get('title')}", "",
                         f"- oncelik: P{k.get('priority')}  |  durum: {k.get('status')}"
                         f"  |  tur: {k.get('issue_type', '?')}"]
            if k.get("closed_at"):
                satirlar.append(f"- kapanis: {k['closed_at']}")
            satirlar.append("")
            aciklama = (k.get("description") or "").strip()
            if aciklama:
                satirlar += [aciklama, ""]
        yol = HEDEF / dosya
        yeni = "\n".join(satirlar)
        if not yol.is_file() or yol.read_text(encoding="utf-8") != yeni:
            yol.write_text(yeni, encoding="utf-8")

    blok(acik, "Acik beads kayitlari", "beads-acik-kayitlar.md")
    blok(kapali, "Kapali beads kayitlari", "beads-kapali-kayitlar.md")
    return len(acik), len(kapali)


# --------------------------------------------------------------------------
# 2-3) Grafigi tazele, adlari geri uygula
# --------------------------------------------------------------------------


def graphify_tazele() -> str:
    graphify = Path.home() / ".local" / "bin" / "graphify.EXE"
    if not graphify.is_file():
        return "graphify bulunamadi - atlandi"
    try:
        cikti = kabuk([str(graphify), "update", "."])
    except RuntimeError as exc:
        return f"tazeleme basarisiz: {exc}"
    for satir in cikti.splitlines():
        if "Rebuilt" in satir or "nodes" in satir:
            return satir.strip()
    return "tazelendi"


def main() -> int:
    print("graphify bilgilendirmesi")
    try:
        n = yaz_hafizalar()
        acik, kapali = yaz_kayitlar()
    except RuntimeError as exc:
        print(f"  hata: {exc}", file=sys.stderr)
        return 2
    print(f"  beads -> dosya : {n} hafiza, {acik} acik + {kapali} kapali kayit")
    print(f"  grafik         : {graphify_tazele()}")

    sys.stdout.flush()   # alt surec dogrudan yaziyor; sira karismasin
    etiketle = Path(__file__).with_name("graphify-etiketle.py")
    if etiketle.is_file():
        subprocess.run([sys.executable, str(etiketle)], cwd=str(KOK))

    print()
    print("  NOT: belge METNI guncellendi ve aranabilir. Yeni KAVRAM dugumleri ve")
    print("       gerekce kenarlari icin anlamsal tarama gerekiyor: /graphify --update")
    return 0


if __name__ == "__main__":
    sys.exit(main())
