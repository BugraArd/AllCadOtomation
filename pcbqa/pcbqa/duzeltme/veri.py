"""Egitim verisi uretimi: referans -> kontrollu hata -> adaylar -> GERCEK kontroller.

    python -m pcbqa.duzeltme.veri --referans 80 --cikti .work/duzeltme

Akis (her referans icin, bagimsiz ve paralel):

  1. Parametre ornekle; KAPALI FORM en kotu durum (EVA) gecmeli, guc
     orani <= %50 olan en kucuk paket secilir, courtyard'lar cakismamali.
  2. Referansi gercek kontrollerden gecir (ngspice + seviye2 + PCB). Gecerli
     DEGILSE ya da benzetim el hesabiyla uyusmuyorsa referans REDDEDILIR.
     Boylece her referans iki bagimsiz hesapla dogrulanmis olur.
  3. Her hata turunu uygula; varyant gercek kontrolde KALMALI. Kalmazsa
     (hata bu tasarimda zararsiz) ya da denetlenemezse veri kumesine girmez;
     sayisi ozete yazilir.
  4. Ureteci adaylari cikarir; HER aday gercek kontrollerden gecer.
  5. Her aday bir kayit: temel tasarim kimligi, kosullar, degisiklik, surumler,
     dogrulama durumu, yeni ihlaller.

Ciktilar (cikti klasorunde):
  kayitlar.jsonl   tum kayitlar (tur: referans | varyant | aday)
  veri-ham.jsonl   ml.dataset bicimi, ham oznitelikler (grup = temel tasarim)
  veri-tam.jsonl   ayni ornekler, tam oznitelikler
  ozet.json        sayimlar, sureler, surumler
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from ..ml.dataset import Dataset, Sample
from . import adaylar as adaylar_mod
from .adaylar import adaylari_uret
from .bolucu import AILE, AILE_SURUMU, Bolucu
from .degerlendir import Degerlendirme, degerlendir, yeni_ihlaller
from .envanter import aday_paketleri, neden_metni
from .hatalar import HATA_TURLERI, hata_degisiklikleri
from .maliyet import maliyet
from .ozellik import OZNITELIK_SURUMU, SEMALAR, on_hesap, ozellikler, tasarim_ozeti
from .orneklem import POLITIKALAR, Politika, PlanSatiri, plan, referans_bul
from .tasarim import Tasarim

# 2: aday kaydina degisiklik maliyeti (maliyet.py) ve yonlendirilmis kart
# geometrisi eklendi (Kicad-apg / Kicad-ecd). v1 kayitlari bu surumle
# egitilmez - egitim acik hatayla reddeder (bkz. egitim.veri_yukle).
KAYIT_SEMASI = 2
VARSAYILAN_TOHUM = 20261001


# --------------------------------------------------------------------------
# Surumler
# --------------------------------------------------------------------------

_SURUMLER: dict[str, Any] | None = None


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, timeout=20,
                              cwd=Path(__file__).resolve().parents[3]).stdout.strip()
    except Exception:
        return ""


def ngspice_surumu() -> str:
    from ..spice import arka_uc_bul, calistir

    arka = arka_uc_bul()
    if arka is None:
        return "yok"
    with tempfile.TemporaryDirectory(prefix="pcbqa-surum-") as d:
        yol = Path(d) / "surum.cir"
        yol.write_text("* surum\nR1 1 0 1\nV1 1 0 1\n.control\nversion -s\n.endc\n.end\n", encoding="utf-8")
        try:
            cal = calistir(yol, arka, 60)
        except Exception as exc:
            return f"okunamadi ({exc})"
    satir = next((s for s in cal.gunluk if "ngspice-" in s.lower()), "")
    return f"{satir.split('stdout')[-1].strip() or 'bilinmiyor'} ({arka.aciklama()})"


def surumler() -> dict[str, Any]:
    global _SURUMLER
    if _SURUMLER is None:
        from ..kicadcli import KicadCli

        try:
            kicad = KicadCli().version()
        except Exception as exc:
            kicad = f"bulunamadi ({exc})"
        kutuphane = Path(__file__).resolve().parents[1] / "data" / "parcalar" / "temel.json"
        _SURUMLER = {
            "kayit_semasi": KAYIT_SEMASI,
            "pcbqa_git": _git("rev-parse", "--short", "HEAD"),
            "pcbqa_kirli": bool(_git("status", "--porcelain")),
            "kicad": kicad,
            "ngspice": ngspice_surumu(),
            "parca_kutuphanesi": hashlib.sha256(kutuphane.read_bytes()).hexdigest()[:12]
            if kutuphane.is_file() else "yok",
            "aile": f"{AILE}-v{AILE_SURUMU}",
            "aday_ureteci": adaylar_mod.URETEC_SURUMU,
            "oznitelik": OZNITELIK_SURUMU,
            "python": platform.python_version(),
        }
    return _SURUMLER


# --------------------------------------------------------------------------
# Referans ornekleme (kapali form kapisi)
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# Kayitlar
# --------------------------------------------------------------------------


def referans_isle(i: int, tohum: int, calisma_kok: Path | None = None, politika: Politika = POLITIKALAR["dogal"],
                  satir: PlanSatiri | None = None) -> list[dict[str, Any]]:
    """Bir referans + hatalari + adaylari. Rastgelelik YALNIZCA (tohum, i)'den:
    ayni ayarlar ayni kayitlari uretir (zaman ve sure alanlari haric)."""
    rng = random.Random(tohum * 100003 + i)
    kimlik = f"bolucu-{i:04d}"
    p, t, reddedilen, orneklem = referans_bul(rng, kimlik, politika, satir)
    zaman = time.strftime("%Y-%m-%dT%H:%M:%S")
    surum = surumler()
    pol = {"politika": politika.ad, "plan": satir.as_dict() if satir else None, "orneklem": orneklem}
    if p is None:
        return [{"tur": "referans", "kimlik": kimlik, "kabul": False, "neden": "ornekleme tukendi",
                 "ornekleme_reddi": reddedilen, "surumler": surum, "zaman": zaman, **pol}]
    b = Bolucu("R1", "R2", "VIN", "OUT", "GND")
    onbellek: dict[str, Degerlendirme] = {}

    def degerle(td: Tasarim) -> tuple[Degerlendirme, bool]:
        anahtar = td.imza()
        if anahtar in onbellek:
            return onbellek[anahtar], True
        d = degerlendir(td, calisma_kok=calisma_kok, bolucu=b)
        onbellek[anahtar] = d
        return d, False

    ref_d, _ = degerle(t)
    ref_kayit = {"tur": "referans", "kimlik": kimlik, "parametre": p.as_dict(),
                 "tasarim": tasarim_ozeti(t, b), "degerlendirme": ref_d.as_dict(),
                 "ornekleme_reddi": reddedilen, "surumler": surum, "zaman": zaman, **pol}
    uyumlu = bool(ref_d.uyum.get("uyumlu"))
    ref_kayit["kabul"] = ref_d.durum == "gecerli" and uyumlu
    if not ref_kayit["kabul"]:
        ref_kayit["neden"] = (f"gercek kontrol: {ref_d.durum}" if ref_d.durum != "gecerli"
                              else "benzetim el hesabiyla uyusmadi")
        return [ref_kayit]
    kayitlar = [ref_kayit]
    temel = {"kimlik": kimlik, "parametre": p.as_dict(), "imza": t.imza()}

    for tur in HATA_TURLERI:
        h = hata_degisiklikleri(t, b.ust, b.alt, tur, rng, hedef_paket=orneklem.get("hedef_paket"))
        vkim = f"{kimlik}/{tur}"
        if h is None:
            kayitlar.append({"tur": "varyant", "kimlik": vkim, "temel": temel, "hata": {"tur": tur},
                             "kullanildi": False, "neden": "bu tasarimda uygulanamadi"})
            continue
        degs, hmeta = h
        tv = t.uygula(degs)
        dv, _ = degerle(tv)
        varyant = {"kimlik": vkim, "hata": {"tur": tur, "degisiklikler": [d.as_dict() for d in degs], **hmeta},
                   "tasarim": tasarim_ozeti(tv, b), "degerlendirme": dv.as_dict()}
        kullan = dv.durum == "gecersiz"
        kayitlar.append({"tur": "varyant", "kimlik": vkim, "temel": temel, **{k: v for k, v in varyant.items()
                                                                            if k != "kimlik"},
                         "kullanildi": kullan,
                         "neden": "" if kullan else ("hata zararsiz cikti (gecerli)" if dv.durum == "gecerli"
                                                     else "hatali tasarim denetlenemedi")})
        if not kullan:
            continue
        for a in adaylari_uret(tv, b):
            ta = tv.uygula(a.degisiklikler)
            oh = on_hesap(ta, b)
            da, onb = degerle(ta)
            kayitlar.append({
                "tur": "aday", "kimlik": f"{vkim}/{a.kimlik}", "temel": temel, "varyant": varyant,
                "aday": {**a.as_dict(), "on_hesap": oh, "maliyet": maliyet(tv, ta)},
                "sonuc": {**da.as_dict(), "yeni_ihlaller": yeni_ihlaller(dv, da), "onbellekten": onb},
                "surumler": surum, "zaman": zaman,
            })
    return kayitlar


def _paketler(k: dict[str, Any]) -> dict[str, str]:
    """Paket bazli raporlama icin (Kicad-7cb): referansin ve hatali varyantin paketleri."""
    from ..devre.parca import paket_kodu

    bol = k["varyant"]["degerlendirme"]["bolucu"] or {}
    bil = k["varyant"]["tasarim"]["bilesenler"]
    par = k["temel"]["parametre"]
    return {"ref_paket_ust": par.get("paket_ust", ""), "ref_paket_alt": par.get("paket_alt", ""),
            "paket_ust": paket_kodu(bil[bol["ust"]]["footprint"]) if bol.get("ust") in bil else "",
            "paket_alt": paket_kodu(bil[bol["alt"]]["footprint"]) if bol.get("alt") in bil else ""}


def kopya_gruplari(kayitlar: list[dict[str, Any]]) -> dict[str, str]:
    """Temel kimligi -> bolme grubu. Ayni tasarim imzasini tasiyan (yakin
    kopya) temeller AYNI gruba duser: biri egitimde digeri testte olamaz."""
    ilk: dict[str, str] = {}
    out: dict[str, str] = {}
    for k in kayitlar:
        if k.get("tur") != "aday":
            continue
        t = k["temel"]
        out[t["kimlik"]] = ilk.setdefault(t["imza"], t["kimlik"])
    return out


def veri_kumesi(kayitlar: list[dict[str, Any]], sema: str) -> Dataset:
    from .tercih import HEDEF_ADI, hedefleri_ekle

    ds = Dataset(feature_names=list(SEMALAR[sema]), feature_version=OZNITELIK_SURUMU,
                 meta={"aile": AILE, "sema": sema, "etiket": "gecerli=1, gecersiz=0, denetlenemedi=-1",
                       "kayit_semasi": KAYIT_SEMASI, "tercih_hedefi": HEDEF_ADI})
    grup = kopya_gruplari(kayitlar)
    for k in kayitlar:
        if k.get("tur") != "aday":
            continue
        s = k["sonuc"]
        etiket = {"gecerli": 1.0, "gecersiz": 0.0}.get(s["durum"], -1.0)
        m = k["aday"]["maliyet"]
        ds.add(Sample(
            features=ozellikler(k, sema), label=etiket, group=grup[k["temel"]["kimlik"]],
            batch=k["varyant"]["kimlik"],
            extra={"durum": s["durum"], "sira": k["aday"]["sira"], "operator": k["aday"]["operator"],
                   "yeni_ihlal": len(s["yeni_ihlaller"]), "n_degisiklik": len(k["aday"]["degisiklikler"]),
                   "vin_nom": k["temel"]["parametre"]["vin_nom"], "hata": k["varyant"]["hata"]["tur"],
                   "a_gecer": bool(k["aday"]["on_hesap"]["analitik"].get("gecer")),
                   "g_cakisma": bool(k["aday"]["on_hesap"]["cakisma"]),
                   "maliyet": m["toplam"], "m_alanlar": {a: v for a, v in m["alanlar"].items() if v},
                   "temel": k["temel"]["kimlik"], "temel_imza": k["temel"]["imza"], **_paketler(k),
                   "aday_paket_ust": aday_paketleri(k)[0], "aday_paket_alt": aday_paketleri(k)[1],
                   "neden": neden_metni(s)},
        ))
    hedefleri_ekle(ds.samples)
    return ds


def ozet(kayitlar: list[dict[str, Any]], sure_s: float) -> dict[str, Any]:
    refs = [k for k in kayitlar if k["tur"] == "referans"]
    vars_ = [k for k in kayitlar if k["tur"] == "varyant"]
    ads = [k for k in kayitlar if k["tur"] == "aday"]
    sayac: dict[str, Any] = {}

    def say(anahtar, deger):
        d = sayac.setdefault(anahtar, {})
        d[deger] = d.get(deger, 0) + 1

    for r in refs:
        say("referans", "kabul" if r.get("kabul") else f"red: {r.get('neden')}")
        for neden, n in (r.get("ornekleme_reddi") or {}).items():
            sayac.setdefault("ornekleme_reddi", {})[neden] = sayac.get("ornekleme_reddi", {}).get(neden, 0) + n
    for v in vars_:
        say("varyant", "kullanildi" if v.get("kullanildi") else v.get("neden"))
        if v.get("kullanildi"):
            say("varyant_hata_turu", v["hata"]["tur"])
    for a in ads:
        say("aday_durumu", a["sonuc"]["durum"])
        say("aday_operator_gecerli", f"{a['aday']['operator']}:{a['sonuc']['durum']}")
    uyumsuz = sum(1 for a in ads if a["sonuc"].get("uyum", {}).get("karsilastirildi")
                  and not a["sonuc"]["uyum"].get("uyumlu"))
    sim = sum(1 for a in ads if not a["sonuc"].get("onbellekten") and a["sonuc"].get("simulasyon"))
    return {"sayilar": sayac, "aday": len(ads), "benzetim_kosusu_aday": sim,
            "el_hesabi_uyumsuz_aday": uyumsuz, "sure_s": round(sure_s, 1),
            "surumler": surumler()}


def uret(n: int, tohum: int, cikti: Path, isci: int = 8, politika: str | Politika = "dogal") -> dict[str, Any]:
    pol = POLITIKALAR[politika] if isinstance(politika, str) else politika
    cikti = Path(cikti)
    cikti.mkdir(parents=True, exist_ok=True)
    surumler()  # once ana is parcaciginda (ngspice/kicad-cli yoklamasi)
    bas = time.perf_counter()
    satirlar = plan(n, tohum, pol)
    sonuclar: dict[int, list[dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=isci) as havuz:
        isler = {havuz.submit(referans_isle, i, tohum, None, pol, satirlar[i]): i for i in range(n)}
        for is_ in as_completed(isler):
            i = isler[is_]
            sonuclar[i] = is_.result()
            aday = sum(1 for k in sonuclar[i] if k["tur"] == "aday")
            print(f"  [{len(sonuclar)}/{n}] bolucu-{i:04d}: {aday} aday "
                  f"({time.perf_counter() - bas:.0f} s)", flush=True)
    kayitlar = [k for i in sorted(sonuclar) for k in sonuclar[i]]
    with (cikti / "kayitlar.jsonl").open("w", encoding="utf-8") as f:
        for k in kayitlar:
            f.write(json.dumps(k, ensure_ascii=False, default=str) + "\n")
    for sema in SEMALAR:
        veri_kumesi(kayitlar, sema).save(cikti / f"veri-{sema}.jsonl")
    oz = ozet(kayitlar, time.perf_counter() - bas)
    oz["tohum"], oz["referans_istenen"] = tohum, n
    oz["politika"] = pol.as_dict()
    oz["kayit_semasi"] = KAYIT_SEMASI
    from .envanter import kopyalar
    oz["kopyalar"] = kopyalar(kayitlar)
    (cikti / "ozet.json").write_text(json.dumps(oz, ensure_ascii=False, indent=1), encoding="utf-8")
    return oz


def kayitlari_oku(yol: Path) -> list[dict[str, Any]]:
    return [json.loads(s) for s in Path(yol).read_text(encoding="utf-8").splitlines() if s.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pcbqa.duzeltme.veri", description=__doc__.splitlines()[0])
    ap.add_argument("--referans", type=int, default=80, help="referans tasarim sayisi")
    ap.add_argument("--tohum", type=int, default=VARSAYILAN_TOHUM)
    ap.add_argument("--cikti", type=Path, default=Path(".work/duzeltme"))
    ap.add_argument("--isci", type=int, default=8, help="paralel referans sayisi")
    ap.add_argument("--politika", choices=sorted(POLITIKALAR), default="dogal",
                    help="referans ornekleme politikasi (Kicad-7cb: dengeli = paket kotasi + sinir bantlari)")
    ap.add_argument("--yeniden-kur", action="store_true",
                    help="benzetim YAPMADAN kayitlar.jsonl'den veri-*.jsonl'i yeniden kur (sema/oznitelik degisince)")
    args = ap.parse_args(argv)
    if args.yeniden_kur:
        kayitlar = kayitlari_oku(args.cikti / "kayitlar.jsonl")
        for sema in SEMALAR:
            veri_kumesi(kayitlar, sema).save(args.cikti / f"veri-{sema}.jsonl")
        print(f"{len(kayitlar)} kayittan veri kumeleri yeniden kuruldu: {args.cikti}")
        return 0
    oz = uret(args.referans, args.tohum, args.cikti, args.isci, args.politika)
    print(json.dumps(oz, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
