"""OGRENIM - kullanicinin kendi KiCad projelerinden ogrenen akis (iskelet).

Kullanici talimati (2026-10-02): "elle ekleyecegim sematik ve PCB cizimlerini
iceride makine ogrenimi ile ogrenecek, sonuc cikartacak ufak bir uygulama
arayuzune baslayalim; bunun icin alt dosya yolu olustur". Ayrintili sartname
ayni gun verildi (proje iceri alma -> bolum tespiti -> kosul formu -> referans
-> gercek deney -> sonuc -> veri kapsami -> gorulmemis projede model
karsilastirmasi -> LDO hazirligi). Plan Beads'te (bkz. AGENTS.md bolum 9).

Bu paket YENIDEN YAZMAZ; var olanlari baglar:
    devre/          devre grafi (bolum tespiti bunun ustunde)
    duzeltme/       bolucu ailesi, gercek proje hatti (proje.py), secim,
                    envanter, aciklama, egitim/olcut
    kontrol.py      tum kart kontrolleri (bolum sonucundan AYRI gosterilir)

Yonetilen calisma alani (kaynak projelere ASLA yazilmaz; git disi):

    <CALISMA>/
      projeler/<proje-kimligi>/
          kaynak.json        kaynak yol, dosya envanteri, sha256 ozetleri, soy
          kopya/             iceri alinan dosyalarin salt kopyasi
          bolumler.json      bulunan bolumler + destek durumu
          kosullar/<kosul-kimligi>.json   formdan gelen calisma kosullari (+ kaynak)
          deneyler/<kosu-kimligi>/        deney.jsonl, rapor.md, ozet.json
      koleksiyon.json        projeler, tasarim soyu, kaynak turu (gercek/varyant/sentetik)
      modeller/<surum>/      ayrica baslatilan, surumlu egitim; ustune yazilmaz

<CALISMA> varsayilani depo icindeki `pcbqa/calisma/`; `PCBQA_CALISMA` ortam
degiskeni ile degistirilir.
"""

from __future__ import annotations

import os
from pathlib import Path

VARSAYILAN_CALISMA = Path(__file__).resolve().parents[2] / "calisma"


def calisma_alani() -> Path:
    """Yonetilen calisma alaninin koku (olusturmaz)."""
    ortam = os.environ.get("PCBQA_CALISMA", "").strip()
    return Path(ortam) if ortam else VARSAYILAN_CALISMA
