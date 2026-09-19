"""Oturum basi graphify durumu - bilgi grafigi acik mi, guncel mi.

Neden var: `graphify claude install` CLAUDE.md'ye kural yaziyor ve her
Read/Grep oncesi hatirlatma enjekte ediyor, ama grafigin GERCEKTEN var olup
olmadigini ve ne kadar bayat oldugunu soylemiyor. Bayat bir grafik, guvenle
sorgulanan yanlis bir haritadir; oturumun basinda gorunmesi gerekiyor.

Yalnizca standart kutuphane kullanir - hangi Python'la calisirsa calissin.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
GRAF = KOK / "graphify-out" / "graph.json"


def degisen_kod_dosyalari() -> int:
    """Grafik yazildigindan beri kac kod dosyasi degisti (git'e gore)."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(KOK), "status", "--porcelain", "--", "*.py"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return -1
    if proc.returncode != 0:
        return -1
    return sum(1 for satir in proc.stdout.splitlines() if satir.strip())


def main() -> int:
    if not GRAF.is_file():
        print("graphify: bilgi grafigi YOK - kurmak icin: /graphify .")
        return 0

    try:
        veri = json.loads(GRAF.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"graphify: graph.json okunamadi ({exc}) - /graphify . ile yeniden kurun")
        return 0

    dugum = len(veri.get("nodes", []))
    # node-link bicimi kenarlari "links" altinda tutar, "edges" altinda degil;
    # "edges" diye okuyunca sessizce 0 cikiyordu.
    kenar = len(veri.get("links", []))
    topluluk = len({n.get("community") for n in veri.get("nodes", [])
                    if n.get("community") is not None})

    yas = datetime.now(timezone.utc) - datetime.fromtimestamp(
        GRAF.stat().st_mtime, tz=timezone.utc)
    saat = yas.total_seconds() / 3600
    tazelik = f"{saat:.0f} saat" if saat < 48 else f"{saat / 24:.0f} gun"

    print(f"graphify: {dugum} dugum, {kenar} kenar, {topluluk} topluluk "
          f"(guncelleme {tazelik} once)")
    print("  Kod sorusu sorulmadan once: graphify explain \"<kavram>\" "
          "| graphify path \"<A>\" \"<B>\" | graphify query \"<soru>\" --budget N")
    # Kullanicinin kalici talimati (2026-08-31). Kuralin kendisi de her oturumda
    # gorunmeli; yalnizca CLAUDE.md'ye yazmak yetmiyor - orada bir bolum arasinda
    # kayboluyor. Ayrinti: CLAUDE.md '## Calisma Anlasmasi'.
    print("  ANLASMA: her KARAR, her HATA DUZELTMESI, her GELECEK PLANI once "
          "bd'ye yazilir,")
    print("           sonra: python .claude/graphify-bilgilendir.py")

    kirli = degisen_kod_dosyalari()
    if kirli > 0:
        print(f"  UYARI: {kirli} .py dosyasi commit edilmemis - grafik bu "
              "degisiklikleri BILMIYOR. Tazelemek icin: graphify update .")
    return 0


if __name__ == "__main__":
    sys.exit(main())
