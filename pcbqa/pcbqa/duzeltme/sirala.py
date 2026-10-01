"""`pcbqa devre-duzelt` - bulgu -> adaylar -> model sirasi -> GERCEK kontrol.

    pcbqa devre-duzelt <proje> --kosullar kosullar.yaml [--model yol] [--en-fazla 8] [--json rapor.json]

Akis (kullanici talimati, 2026-10-01):
  1. Mevcut kontroller sorunu bulur (ngspice + seviye2 + PCB).
  2. Ureteci duzeltme adaylarini cikarir.
  3. Model adaylari SIRALAR. Model dosyasi yoksa, okunamazsa ya da semasi
     uyusmazsa ureteci sirasi kullanilir - akis DURMAZ.
  4. Adaylar o sirayla gercek kontrollerden gecirilir; ilk GECERLI adayda
     durulur (en fazla --en-fazla benzetim).
  5. Gecerli degisiklik ve gerekcesi gosterilir.

Modelin tahmini elektriksel dogrulamanin yerini ALMAZ: gosterilen her
oneri ngspice ve kurallardan gecmistir; model yalnizca iyi adaya daha erken
ulasmayi saglar. Proje dosyalarina YAZILMAZ - adaylar bellekteki bir
kopyada denenir (KiCad acik olsa da guvenli).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..dogrulama.seviye3 import seviye3
from .adaylar import Aday, adaylari_uret
from .bolucu import Bolucu, yonlendirici_kur
from .degerlendir import Degerlendirme, degerlendir, yeni_ihlaller
from .egitim import VARSAYILAN_MODEL
from .maliyet import maliyet
from .tercih import HEDEFLER, kova_anahtari
from .ozellik import OZNITELIK_SURUMU, SEMALAR, on_hesap, ozellikler, tasarim_ozeti
from .tasarim import Tasarim


@dataclass
class Siralayici:
    model: Any = None
    sema: str | None = None
    kaynak: str = "ureteci sirasi"

    def sirala(self, kayitlar: list[dict[str, Any]]) -> list[int]:
        """Model puani (OLASILIK DEGIL) + gecici 0.1 kova kurali: ayni kovada
        dusuk maliyet (sozluksel model) ya da az degisiklik (eski model) once."""
        sira = list(range(len(kayitlar)))
        if self.model is None:
            return sira
        puan = [self.model.predict(ozellikler(k, self.sema)) for k in kayitlar]
        kova = self.model.meta.get("kova")
        ikincil = self.model.meta.get("kova_ikincil", "n_degisiklik")

        def ikinci(k):
            if ikincil == "maliyet":
                return float(k["aday"]["maliyet"]["toplam"])
            return float(len(k["aday"]["degisiklikler"]))
        return sorted(sira, key=lambda i: kova_anahtari(puan[i], ikinci(kayitlar[i]), kayitlar[i]["aday"]["sira"],
                                                        kova))


def siralayici_yukle(yol: Path | None) -> Siralayici:
    """Model yoksa / bozuksa / semasi uyusmazsa ureteci sirasi - nedeniyle."""
    yol = Path(yol) if yol else VARSAYILAN_MODEL
    if not yol.is_file():
        return Siralayici(kaynak=f"ureteci sirasi (model yok: {yol.name})")
    try:
        from ..ml.model import load

        m = load(yol)
        sema = m.meta.get("sema")
        if sema not in SEMALAR:
            raise ValueError(f"bilinmeyen sema {sema!r}")
        m.check_schema(SEMALAR[sema], OZNITELIK_SURUMU)
        # Hedef ACIKCA bilinmeli: eski (Kicad-u4k) dosyada alan yok -> gecerlilik
        # modeli sayilir; bilinmeyen hedef reddedilir (sessizce yorumlanmaz).
        hedef = m.meta.get("hedef", "gecerlilik")
        if hedef not in HEDEFLER:
            raise ValueError(f"bilinmeyen hedef {hedef!r}")
        if m.meta.get("kova_ikincil", "n_degisiklik") not in ("n_degisiklik", "maliyet"):
            raise ValueError(f"bilinmeyen kova kurali {m.meta.get('kova_ikincil')!r}")
    except Exception as exc:  # model bir hizlandiricidir; yoklugu akisi durdurmaz
        return Siralayici(kaynak=f"ureteci sirasi (model kullanilamadi: {exc})")
    return Siralayici(m, sema, f"model {m.kind}-{sema} ({yol.name}, egitim {m.meta.get('egitim_tarihi', '?')})")


@dataclass
class Deneme:
    aday: Aday
    sonuc: Degerlendirme
    yeni_ihlaller: list[str]


@dataclass
class DuzeltSonucu:
    durum: str                  # sorun-yok | duzeltildi | bulunamadi | denetlenemedi
    once: Degerlendirme
    siralama: str = ""
    aday_sayisi: int = 0
    denemeler: list[Deneme] = field(default_factory=list)

    @property
    def secilen(self) -> Deneme | None:
        return next((d for d in self.denemeler if d.sonuc.durum == "gecerli"), None)

    @property
    def benzetim(self) -> int:
        return self.once.simulasyon + sum(d.sonuc.simulasyon for d in self.denemeler)

    def as_dict(self) -> dict[str, Any]:
        return {
            "durum": self.durum, "siralama": self.siralama, "aday_sayisi": self.aday_sayisi,
            "benzetim": self.benzetim, "once": self.once.as_dict(),
            "denemeler": [{"aday": d.aday.as_dict(), "sonuc": d.sonuc.as_dict(),
                           "yeni_ihlaller": d.yeni_ihlaller} for d in self.denemeler],
            "secilen": self.secilen.aday.as_dict() if self.secilen else None,
        }


def duzelt(t: Tasarim, siralayici: Siralayici, *, en_fazla: int = 8,
           benzetim: Callable[..., Any] = seviye3) -> DuzeltSonucu:
    once = degerlendir(t, benzetim=benzetim)
    if once.durum == "gecerli":
        return DuzeltSonucu("sorun-yok", once, siralayici.kaynak)
    if once.durum == "denetlenemedi":
        # Eksik bilgi / calismayan benzetim elektriksel hata DEGIL: aday uretilmez.
        return DuzeltSonucu("denetlenemedi", once, siralayici.kaynak)
    b = Bolucu(**once.bolucu)
    # Kart bu ailenin rayli yonlendirmesiyle cizilmisse footprint adayi izleri
    # yeniden uretir (maliyete yonlendirme degisimi girer; egitimle ayni).
    yonlendirici_kur(t, b)
    adaylar = adaylari_uret(t, b)
    varyant = {"tasarim": tasarim_ozeti(t, b), "degerlendirme": once.as_dict()}
    kayitlar = []
    for a in adaylar:
        ta = t.uygula(a.degisiklikler)
        # Maliyet degisiklik tanimi + kart geometrisinden ANINDA (benzetim yok)
        kayitlar.append({"varyant": varyant, "aday": {**a.as_dict(), "on_hesap": on_hesap(ta, b),
                                                      "maliyet": maliyet(t, ta)}})
    sonuc = DuzeltSonucu("bulunamadi", once, siralayici.kaynak, len(adaylar))
    for i in siralayici.sirala(kayitlar)[:en_fazla]:
        a = adaylar[i]
        a.ek["maliyet"] = kayitlar[i]["aday"]["maliyet"]
        d = degerlendir(t.uygula(a.degisiklikler), benzetim=benzetim, bolucu=b)
        sonuc.denemeler.append(Deneme(a, d, yeni_ihlaller(once, d)))
        if d.durum == "gecerli":
            sonuc.durum = "duzeltildi"
            break
    return sonuc


# --------------------------------------------------------------------------
# Projeden tasarim (gercek KiCad dosyalari, salt okunur)
# --------------------------------------------------------------------------


def projeden_tasarim(proje: Path, kosullar_yolu: Path) -> Tasarim:
    from ..confload import load_config
    from ..devre.yukle import ProjeHatasi, proje_bul
    from ..kicadcli import KicadCli
    from ..netlist import read_netlist
    from ..pcb import read_board

    dosyalar = proje_bul(proje)
    if dosyalar.sematik is None:
        raise ProjeHatasi(f"{dosyalar.ad}: sematik yok - degerler sematikten okunur")
    hedef = Path(tempfile.mkdtemp(prefix="pcbqa-duzelt-")) / "netlist.xml"
    res = KicadCli().export_netlist(dosyalar.sematik, hedef)
    if not res.ok or res.output_path is None:
        raise ProjeHatasi(f"netlist uretilemedi: {res.stderr or res.stdout}")
    kosullar, _ = load_config(Path(kosullar_yolu))
    board = read_board(dosyalar.kart) if dosyalar.kart is not None else None
    return Tasarim(read_netlist(res.output_path), board, dict(kosullar), proje=dosyalar.ad)


def _kontrol_satiri(d: Degerlendirme) -> str:
    return ", ".join(f"{k} {v}" for k, v in d.kontroller.items())


def metin(s: DuzeltSonucu) -> str:
    o = s.once
    a = o.analitik
    out = []
    if o.bolucu:
        b = o.bolucu
        out.append(f"Bolucu: {b['ust']} ({b['giris']}) / {b['alt']} ({b['toprak']}) -> {b['cikis']}, "
                   f"gereksinim {a.get('pencere_min')}..{a.get('pencere_max')} V")
    out.append(f"Mevcut durum: {o.durum.upper()} ({_kontrol_satiri(o)})")
    for h in o.hatalar[:5]:
        out.append(f"  - {h}")
    for n in o.nedenler:
        out.append(f"  ! {n}")
    if s.durum == "sorun-yok":
        out.append("Zorunlu kontrollerin hepsi geciyor - duzeltme gerekmiyor.")
        return "\n".join(out)
    if s.durum == "denetlenemedi":
        out.append("DENETLENEMEDI: bu elektriksel bir hata degil; eksik bilgi tamamlanmadan aday uretilmez.")
        return "\n".join(out)
    out.append(f"Adaylar: {s.aday_sayisi}; siralama: {s.siralama}")
    out.append("Denenenler (her biri gercek ngspice + kural + PCB kontrolu):")
    for j, d in enumerate(s.denemeler, 1):
        yi = f", yeni ihlal: {', '.join(d.yeni_ihlaller)}" if d.yeni_ihlaller else ""
        out.append(f"  {j}. {d.aday.kimlik}: {d.sonuc.durum.upper()} ({_kontrol_satiri(d.sonuc)}){yi}")
    sec = s.secilen
    if sec is None:
        out.append(f"Gecerli duzeltme bulunamadi ({len(s.denemeler)} aday denendi).")
        return "\n".join(out)
    ol, an = sec.sonuc.olcumler, sec.sonuc.analitik
    out.append("Onerilen degisiklik:")
    for dg in sec.aday.degisiklikler:
        out.append(f"  {dg.metin()}")
    m = sec.aday.ek.get("maliyet")
    if m:
        alan = ", ".join(f"{k} {v}" for k, v in m["alanlar"].items() if v and k in m["agirliklar"])
        out.append(f"  degisiklik maliyeti {m['toplam']:g} ({alan})")
    out.append("Gerekce:")
    out.append(f"  {sec.aday.gerekce}")
    out.append(f"  {o.bolucu['cikis']} tum senaryo ve capraz koselerde {ol['vout_min']:.4g}..{ol['vout_max']:.4g} V "
               f"(pencere {an['pencere_min']:g}..{an['pencere_max']:g} V; marj alt "
               f"{(ol['vout_min'] - an['pencere_min']) * 1e3:.1f} mV, ust {(an['pencere_max'] - ol['vout_max']) * 1e3:.1f} mV)")
    oranlar = [x for x in (ol.get("p_ust_oran"), ol.get("p_alt_oran")) if x is not None]
    if oranlar:
        out.append(f"  en yuklu direnc anma gucunun %{max(oranlar) * 100:.1f}'i (benzetim)")
    out.append("  PCB: courtyard cakismasi yok, kart siniri icinde, baglanti esligi korunuyor")
    out.append(f"  yeni ihlal: {', '.join(sec.yeni_ihlaller) if sec.yeni_ihlaller else 'yok'}")
    out.append(f"  bu sonuca {s.benzetim} benzetimde ulasildi (1 mevcut durum + {len(s.denemeler)} aday)")
    out.append("Not: siralama yalnizca deneme sirasini belirler; oneri ngspice + kurallardan gecti.")
    out.append("Proje dosyalarina YAZILMADI.")
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="pcbqa devre-duzelt", description=__doc__.splitlines()[0])
    ap.add_argument("proje", type=Path, help="KiCad proje klasoru ya da dosyasi")
    ap.add_argument("--kosullar", type=Path, required=True, help="calisma kosullari / gereksinimler (YAML)")
    ap.add_argument("--model", type=Path, default=None, help=f"siralama modeli (varsayilan {VARSAYILAN_MODEL.name})")
    ap.add_argument("--en-fazla", type=int, default=8, help="denenecek en fazla aday (benzetim butcesi)")
    ap.add_argument("--json", type=Path, default=None)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        t = projeden_tasarim(args.proje, args.kosullar)
    except Exception as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 2
    s = duzelt(t, siralayici_yukle(args.model), en_fazla=args.en_fazla)
    print(f"pcbqa devre-duzelt: {t.proje}")
    print(metin(s))
    if args.json:
        args.json.write_text(json.dumps(s.as_dict(), ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return {"sorun-yok": 0, "duzeltildi": 0, "bulunamadi": 1, "denetlenemedi": 2}[s.durum]


if __name__ == "__main__":
    sys.exit(main())
