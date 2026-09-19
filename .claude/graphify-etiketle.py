"""Elle verilen topluluk adlarini graph.json'a geri uygular.

## Neden gerekiyor

`graphify update` (ve post-commit kancasi) her kosuda YENIDEN KUMELIYOR.
Olculdu: 174 -> 165 topluluk. Bu iki sey yapiyor:

  * topluluk NUMARALARI kayiyor,
  * elle verilen adlar siliniyor; yerine en yuksek dereceli dugumun adi
    geciyor ("Design", "load_design", "parse_with_stats"...).

Yani kancayi kurup birakirsak grafik her commit'te biraz daha okunmaz hale
gelir - sessizce. Bu betik adlari topluluk numarasina degil CAPA DUGUMUNE
bagliyor: capa kimlikleri dosya yolundan turedigi icin yeniden kumelemede
degismiyor.

Bir topluluk ilk eslesen capadan adini alir; capasi olmayan topluluklar
graphify'in kendi turettigi adla kalir - uydurma ad vermek yerine.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
GRAF = KOK / "graphify-out" / "graph.json"
CAPALAR = Path(__file__).resolve().parent / "graphify-etiketler.json"


def uygula() -> tuple[int, list[str], list[str]]:
    """Doner: (adlandirilan topluluk, bulunamayan capalar, birlesen adlar)."""
    veri = json.loads(GRAF.read_text(encoding="utf-8"))
    capalar = json.loads(CAPALAR.read_text(encoding="utf-8"))["capalar"]

    topluluk_of = {n["id"]: n.get("community") for n in veri["nodes"]}
    ad_of: dict[int, str] = {}
    eksik: list[str] = []
    # Iki capa ayni topluluga duserse ilk gelen kazanir - ama bu SESSIZ
    # gecmemeli: iki ayri kavramin tek kumeye dusmesi, kumelemenin degistigini
    # ve adlandirmanin gozden gecirilmesi gerektigini soyler.
    birlesen: list[str] = []
    for dugum_id, ad in capalar:
        cid = topluluk_of.get(dugum_id)
        if cid is None:
            eksik.append(ad)
            continue
        if cid in ad_of:
            birlesen.append(f"{ad} -> {ad_of[cid]}")
            continue
        ad_of[cid] = ad

    for n in veri["nodes"]:
        yeni = ad_of.get(n.get("community"))
        if yeni:
            n["community_name"] = yeni

    GRAF.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
    return len(ad_of), eksik, birlesen


def main() -> int:
    if not GRAF.is_file() or not CAPALAR.is_file():
        print("graphify: etiket uygulanamadi (graph.json ya da capa dosyasi yok)")
        return 0
    try:
        adlandirilan, eksik, birlesen = uygula()
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"graphify: etiket uygulanamadi ({exc})")
        return 0
    print(f"  graphify: {adlandirilan} toplulugun adi geri uygulandi")
    for ad in eksik:
        print(f"    capa dugumu GRAFIKTE YOK: {ad} - capayi yenileyin")
    for cift in birlesen:
        print(f"    ayni kumeye dustu: {cift}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
