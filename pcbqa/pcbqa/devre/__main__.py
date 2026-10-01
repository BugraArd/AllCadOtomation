"""`pcbqa devre` - devre grafini okunur bicimde dok.

    pcbqa devre <proje> [--kosullar k.yaml] [--json graf.json] [--ref R1]

Her bilesen icin: deger, pinler -> aglar, rol(ler), guc siniri, kart
konumu; ardindan EKSIK bilgi listesi (neyin bilinmedigi ve neden).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..kicadcli import KicadCliError
from .kosullar import KosulHatasi
from .yukle import ProjeHatasi, projeden_graf


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="pcbqa.devre", description="Devre grafini olustur ve goster")
    ap.add_argument("proje", type=Path)
    ap.add_argument("--kosullar", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--ref", action="append", default=[], help="Yalnizca bu bilesen(ler)in ayrintisi")
    args = ap.parse_args(argv)
    try:
        graf, dosyalar = projeden_graf(args.proje, kosullar_yolu=args.kosullar)
    except (ProjeHatasi, KosulHatasi, KicadCliError, OSError) as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2

    o = graf.ozet()
    print(f"DEVRE GRAFI - {dosyalar.ad}")
    print(f"  {o['bilesen']} bilesen, {o['ag']} ag; gerilimi bilinen ag {o['gerilimi_bilinen_ag']}, "
          f"rolu bilinen bilesen {o['rolu_bilinen_bilesen']}, eksiksiz {o['eksiksiz_bilesen']}")
    print(f"  kaynaklar: {', '.join(o['kaynaklar'])}")
    print()
    refs = args.ref or sorted(graf.bilesenler)
    for ref in refs:
        print("  " + graf.bilesen_cumlesi(ref))
        if args.ref:
            print(json.dumps(graf.bilesenler[ref].as_dict(), indent=2, ensure_ascii=False, default=str))
    print()
    print("AGLAR")
    for a in sorted(graf.aglar.values(), key=lambda a: a.ad):
        g = a.gerilim
        print(f"  {a.ad:<24} {g.metin('V') if g.bilinen else '?':<10} "
              f"{(g.kaynak if g.bilinen else g.eksik_neden)[:70]}")
    print()
    print("EKSIK BILGI")
    for ref, liste in graf.eksik_raporu().items():
        if args.ref and ref not in args.ref:
            continue
        print(f"  {ref}:")
        for satir in liste:
            print(f"     - {satir}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(graf.as_dict(), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"\nJSON: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
