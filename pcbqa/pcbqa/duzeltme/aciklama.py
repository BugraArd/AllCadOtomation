"""Kontrol sonuclarinin OKUNUR aciklamasi - CLI, rapor.md ve arayuzun ortak
katmani (Kicad-d8k).

Ham kontrol kodlari (`kontroller`: "elektrik-gereksinim" -> "kaldi") makine
icin oldugu gibi kalir; aciklama ayri bir listede dondurulur:

    {"kod": "elektrik-gereksinim", "durum": "kaldi", "metin": "OUT cikis gerilimi ..."}

Kurallar:
  * Metindeki her sayi kayittan gelir (olcum, kosul, KiCad raporu). Kayitta
    olmayan olcum ya da cozum onerisi UYDURULMAZ; yoksa "kayitta yok" denir.
  * KiCad ihlallerinde bilesen referanslari raporun kendi ogelerinden
    alinir; KiCad'in ozgun aciklamasi ve tur kodu metinde korunur.
  * Bilinmeyen kod icin teknik kodu koruyan yedek aciklama uretilir.

Kod ASCII'dir (proje kurali); metinler Turkce ama ASCII harflerle. Sayilar
Turkce ondalik virgulle yazilir.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable

from .secim import kararli_kimlik, maliyet_degeri, refler, sec

DURUM_METNI = {
    "kaldi": "kaldi",
    "arac-hatasi": "calistirilamadi (arac hatasi; basari sayilmadi)",
    "veri-model-eksik": "denetlenemedi (veri/model eksik; basari sayilmadi)",
}

KAPSAM_NOTU = ("Desteklenen kapsam: yalnizca rezistif gerilim bolucu ailesi; temel proje klasorunde "
               "pcbqa-referans.json bulunmali (pcbqa duzeltme-proje referans ile uretilir).")


def sayi(x: float, basamak: int = 3) -> str:
    return f"{x:.{basamak}g}".replace(".", ",")


def _ag(ad: Any) -> str:
    return str(ad or "?").lstrip("/")


def _e(k: dict[str, Any]) -> dict[str, Any]:
    e = k.get("elektrik")
    return e if isinstance(e, dict) else {}


def _elektrik_refler(k: dict[str, Any], kural: str) -> list[str]:
    out: list[str] = []
    for imza in _e(k).get("ihlaller") or []:
        parca = str(imza).split("|")
        if parca[0] == kural and len(parca) > 1 and parca[1]:
            out += [r for r in parca[1].split(",") if r not in out]
    return out


def _ve(adlar: list[str]) -> str:
    return adlar[0] if len(adlar) == 1 else ", ".join(adlar[:-1]) + " ve " + adlar[-1]


def _durumsuz(k: dict[str, Any], kod: str, durum: str, ad: str) -> str:
    """Kalmadi ama calismadi: nedeni kayittan (elektrik nedenleri, KiCad notlari)."""
    e = _e(k)
    nedenler = list(e.get("nedenler") or [])
    if e.get("hata"):
        nedenler.append(str(e["hata"]))
    if kod.startswith("kicad-"):
        nedenler += list((k.get("kicad") or {}).get("notlar") or [])
    neden = "; ".join(str(n) for n in nedenler if n) or "kayitta neden yok"
    return f"{ad} {DURUM_METNI.get(durum, durum)}: {neden}."


# --------------------------------------------------------------------------
# Kontrol bazinda aciklayicilar: (kayit, kod, durum) -> metin
# --------------------------------------------------------------------------


def _gereksinim(k, kod, durum):
    if durum != "kaldi":
        return _durumsuz(k, kod, durum, "Cikis gerilimi gereksinimi")
    e = _e(k)
    ol, an = e.get("olcumler") or {}, e.get("analitik") or {}
    ag = _ag((e.get("bolucu") or {}).get("cikis"))
    vmin, vmax = ol.get("vout_min"), ol.get("vout_max")
    pmin, pmax = an.get("pencere_min"), an.get("pencere_max")
    if None in (pmin, pmax):
        ger = next((g for g in (k.get("kosullar") or {}).get("gereksinimler") or []
                    if _ag(g.get("ag")) == ag), {})
        pmin, pmax = ger.get("min_v", pmin), ger.get("max_v", pmax)
    if None in (vmin, vmax, pmin, pmax):
        return (f"{ag} cikis gerilimi gereksinimi karsilanmiyor; olculen aralik ya da izin verilen aralik "
                f"kayitta yok (kod {kod}).")
    yon = []
    if vmin < pmin:
        yon.append("alt sinirin altina iniyor")
    if vmax > pmax:
        yon.append("ust siniri asiyor")
    # Sinira cok yakin olcum 3 basamakta sinirla ayni gorunmesin (2,6395 -> "2,64")
    b = 3
    while b < 6 and (sayi(vmin, b) == sayi(pmin, b) or sayi(vmax, b) == sayi(pmax, b)):
        b += 1
    return (f"{ag} cikis gerilimi benzetim senaryolari ve capraz koselerde {sayi(vmin, b)}-{sayi(vmax, b)} V "
            f"araliginda. Izin verilen aralik {sayi(pmin)}-{sayi(pmax)} V oldugu icin gerilim gereksinimi "
            f"karsilanmiyor ({' ve '.join(yon) or 'sinir disi'}).")


def _direnc_gucu(k, kod, durum):
    if durum != "kaldi":
        return _durumsuz(k, kod, durum, "Direnc guc kontrolu")
    e = _e(k)
    ol, an, b = e.get("olcumler") or {}, e.get("analitik") or {}, e.get("bolucu") or {}
    parcalar = []
    for rol in ("ust", "alt"):
        p, sinir, oran = ol.get(f"p_{rol}_w"), an.get(f"p_{rol}_siniri"), ol.get(f"p_{rol}_oran")
        if p is not None and sinir and oran is not None and oran > 1.0:
            parcalar.append(f"{b.get(rol, rol)} en kotu kosede {sayi(p)} W harciyor; sicakliga gore azaltilmis "
                            f"anma gucu {sayi(sinir)} W (oran %{sayi(oran * 100)})")
    if parcalar:
        return "; ".join(parcalar) + ". Guc dayanimi asiliyor."
    hatalar = [h for h in e.get("hatalar") or [] if "guc" in str(h).lower()]
    return ("Direnc guc kontrolu kaldi" + (f": {'; '.join(hatalar)}" if hatalar else
                                           "; asilan olcum kayitta ayrica yok") + f" (kod {kod}).")


def _direnc_gerilimi(k, kod, durum):
    if durum != "kaldi":
        return _durumsuz(k, kod, durum, "Direnc gerilim kontrolu")
    e = _e(k)
    an, b = e.get("analitik") or {}, e.get("bolucu") or {}
    parcalar = []
    for rol in ("ust", "alt"):
        v, sinir = an.get(f"v_{rol}_max"), an.get(f"v_{rol}_siniri")
        if v is not None and sinir and v > sinir:
            parcalar.append(f"{b.get(rol, rol)} uclari arasinda en kotu {sayi(v)} V; azami calisma gerilimi "
                            f"{sayi(sinir)} V")
    if parcalar:
        return "; ".join(parcalar) + ". Gerilim siniri asiliyor."
    return f"Direnc gerilim kontrolu kaldi; asilan olcum kayitta ayrica yok (kod {kod})."


def _pcb_cakisma(k, kod, durum):
    if durum != "kaldi":
        return _durumsuz(k, kod, durum, "Courtyard kontrolu")
    r = _elektrik_refler(k, "cakisma")
    if len(r) >= 2:
        return f"{_ve(r)} courtyard alanlari cakisiyor (pcbqa mekanik kontrolu, gercek footprint geometrisi)."
    return f"Courtyard cakismasi var; ilgili bilesen kayitta yok (kod {kod})."


def _pcb_sinir(k, kod, durum):
    if durum != "kaldi":
        return _durumsuz(k, kod, durum, "Kart siniri kontrolu")
    r = _elektrik_refler(k, "mekanik-sinir")
    return (f"{_ve(r)} pad ya da courtyard'i kart sinirinin disina tasiyor." if r
            else f"Bir bilesen kart sinirinin disina tasiyor; bilesen kayitta yok (kod {kod}).")


def _elektrik_parite(k, kod, durum):
    if durum != "kaldi":
        return _durumsuz(k, kod, durum, "Baglanti esligi")
    return "Kart, sematik netlistiyle ayni baglantiyi tasimiyor (pcbqa baglanti esligi)."


def _paket_uyumu(k, kod, durum):
    sorunlar = (_e(k).get("olcumler") or {}).get("paket_uyumu") or []
    if durum != "kaldi":
        return _durumsuz(k, kod, durum, "Paket/MPN uyumu")
    return ("Pad/footprint ya da MPN uyumsuz: " + "; ".join(map(str, sorunlar)) + "." if sorunlar
            else f"Paket/MPN uyumu kaldi; ayrinti kayitta yok (kod {kod}).")


def _pcb_iz(k, kod, durum):
    if durum != "kaldi":
        return _durumsuz(k, kod, durum, "Bakir iz analizi")
    bilinen = ("gereksinim-gerilim", "cakisma", "mekanik-sinir", "montaj-deligi")
    imzalar = [i for i in _e(k).get("ihlaller") or [] if str(i).split("|")[0] not in bilinen]
    return ("Bakir iz analizi kaldi (yol direnci / akim / baglanti): " + ", ".join(imzalar) + "."
            if imzalar else f"Bakir iz analizi kaldi; ihlal ayrintisi kayitta yok (kod {kod}).")


def _el_hesabi(k, kod, durum):
    if durum == "gecti":
        return ""
    return ("ngspice sonucu ile kapali form el hesabi uyusmadi; hangisinin yanlis oldugu bilinmedigi icin "
            "aday basarili sayilmadi ve egitime girmez.")


def _benzetim(k, kod, durum):
    return _durumsuz(k, kod, durum, "ngspice benzetimi")


def _analiz(k, kod, durum):
    return _durumsuz(k, kod, durum, "Elektriksel analiz")


_KICAD_TUR = {
    "courtyards_overlap": "courtyard alanlari cakisiyor",
    "clearance": "bakir aciklik (clearance) ihlali",
    "unconnected_items": "baglanti tamamlanmamis (bakir iz eksik)",
    "shorting_items": "farkli aglar kisa devre",
    "edge_clearance": "kart kenarina aciklik ihlali",
    "copper_edge_clearance": "kart kenarina bakir aciklik ihlali",
    "track_width": "iz genisligi kural disi",
    "hole_clearance": "delik acikligi ihlali",
    "missing_footprint": "sematikteki sembolun kartta footprint'i yok",
    "extra_footprint": "kartta sematikte olmayan footprint var",
    "net_conflict": "kart ve sematikte ag uyusmazligi",
    "footprint_symbol_mismatch": "footprint sembolle eslesmiyor",
    "lib_footprint_mismatch": "footprint kutuphanedekinden farkli",
    "pin_not_connected": "pin bagli degil",
    "power_pin_not_driven": "guc pini surulmuyor",
    "pin_not_driven": "giris pini surulmuyor",
    "label_dangling": "etiket bosta",
    "wire_dangling": "tel bosta",
    "multiple_net_names": "bir agda birden fazla ad",
    "similar_labels": "birbirine benzeyen etiketler",
}
_KICAD_GRUP = {"erc": ("kicad-erc", "KiCad ERC"), "violations": ("kicad-drc", "KiCad DRC"),
               "unconnected_items": ("kicad-drc", "KiCad DRC"), "schematic_parity": ("kicad-parite",
                                                                                    "KiCad sematik paritesi")}


def kicad_ihlal_metni(v: dict[str, Any]) -> str:
    _, kaynak = _KICAD_GRUP.get(v.get("grup"), ("", f"KiCad {v.get('grup')}"))
    tur = str(v.get("tur") or "?")
    r = refler(v.get("ogeler"))
    kim = f"{_ve(r)}: " if r else ""
    ozgun = f" KiCad: \"{v.get('aciklama')}\"" if v.get("aciklama") else ""
    if tur in _KICAD_TUR:
        return f"{kim}{_KICAD_TUR[tur]} ({kaynak}: {tur}, {v.get('siddet')}).{ozgun}"
    # Bilinmeyen tur: teknik kod ve KiCad'in ozgun metni korunur
    ogeler = "" if r else (" Ogeler: " + "; ".join(map(str, v.get("ogeler") or [])) if v.get("ogeler") else "")
    return f"{kim}{kaynak} ihlali '{tur}' ({v.get('siddet')}).{ozgun}{ogeler}"


def _kicad(k, kod, durum):
    if durum != "kaldi":
        return _durumsuz(k, kod, durum, {"kicad-erc": "KiCad ERC", "kicad-drc": "KiCad DRC",
                                         "kicad-parite": "KiCad sematik paritesi"}.get(kod, "KiCad netlist"))
    ihl = [v for v in (k.get("kicad") or {}).get("ihlaller") or []
           if _KICAD_GRUP.get(v.get("grup"), ("",))[0] == kod and v.get("siddet") in ("error", "warning")]
    if not ihl:
        return f"{kod} kaldi; ihlal ayrintisi kayitta yok."
    return " ".join(kicad_ihlal_metni(v) for v in ihl)


def _yazma(k, kod, durum):
    hata = [str(x) for x in k.get("yazma") or [] if str(x).startswith("HATA")]
    return f"Degisiklik proje kopyasina yazilamadi: {'; '.join(hata) or 'kayitta neden yok'}."


def _geri_okuma(k, kod, durum):
    s = (k.get("geri_okuma") or {}).get("sorunlar") or []
    return ("Yazilan dosya geri okundugunda tutarsizlik: " + "; ".join(map(str, s)) + "." if s
            else f"Geri okuma {DURUM_METNI.get(durum, durum)}; ayrinti kayitta yok.")


ACIKLAYICILAR: dict[str, Callable[[dict, str, str], str]] = {
    "elektrik-gereksinim": _gereksinim, "elektrik-direnc-gucu": _direnc_gucu,
    "elektrik-direnc-gerilimi": _direnc_gerilimi, "elektrik-pcb-cakisma": _pcb_cakisma,
    "elektrik-pcb-sinir": _pcb_sinir, "elektrik-parite": _elektrik_parite, "elektrik-paket-uyumu": _paket_uyumu,
    "elektrik-pcb-iz": _pcb_iz, "elektrik-benzetim-el-hesabi": _el_hesabi, "elektrik-benzetim": _benzetim,
    "elektrik-analiz": _analiz, "kicad-erc": _kicad, "kicad-drc": _kicad, "kicad-parite": _kicad,
    "kicad-netlist": _kicad, "yazma": _yazma, "geri-okuma": _geri_okuma,
}


def yedek_aciklama(kod: str, durum: str) -> str:
    return (f"'{kod}' kontrolu {DURUM_METNI.get(durum, durum)}. Bu kod icin ayrintili aciklama tanimli degil; "
            "teknik kod korunmustur.")


def kontrol_aciklamalari(k: dict[str, Any]) -> list[dict[str, str]]:
    """Gecmeyen her kontrol icin {kod, durum, metin}. Ham kod degismez."""
    out = []
    for kod, durum in (k.get("kontroller") or {}).items():
        if durum == "gecti":
            continue
        fn = ACIKLAYICILAR.get(kod)
        metin = fn(k, kod, durum) if fn else yedek_aciklama(kod, durum)
        out.append({"kod": kod, "durum": durum, "metin": metin or yedek_aciklama(kod, durum)})
    return out


def gecti_ozeti(k: dict[str, Any]) -> str:
    """Gecen kaydin olculen degerlerle ozeti (yalnizca kayittakiler)."""
    kk = (k.get("kicad") or {}).get("sayilar") or {}
    e = _e(k)
    ol, an = e.get("olcumler") or {}, e.get("analitik") or {}
    parca = [f"ERC {kk.get('erc', '-')}, DRC {kk.get('drc', '-')}, parite {kk.get('parite', '-')}"]
    if None not in (ol.get("vout_min"), ol.get("vout_max"), an.get("pencere_min"), an.get("pencere_max")):
        parca.append(f"{_ag((e.get('bolucu') or {}).get('cikis'))} {sayi(ol['vout_min'])}-{sayi(ol['vout_max'])} V "
                     f"(izin {sayi(an['pencere_min'])}-{sayi(an['pencere_max'])} V)")
    oran = [x for x in (ol.get("p_ust_oran"), ol.get("p_alt_oran")) if x is not None]
    if oran:
        parca.append(f"en yuklu direnc anma gucunun %{sayi(max(oran) * 100, 2)}'i")
    return "Zorunlu kontrollerin hepsi gecti: " + "; ".join(parca) + "."


def degisiklik_metni(k: dict[str, Any]) -> str:
    return "; ".join(f"{d['ref']} {d['alan']} {d['eski']} -> {d['yeni']}"
                     for d in (k.get("aday") or {}).get("degisiklikler", [])) or "-"


def maliyet_metni(k: dict[str, Any]) -> str:
    m, neden = maliyet_degeri(k)
    if m is None:
        return f"maliyet yok ({neden})"
    ham = k["maliyet"]
    w = ham.get("agirliklar") or {}
    alan = ", ".join(f"{a} {v}" for a, v in (ham.get("alanlar") or {}).items() if v and a in w)
    return f"{m:g}" + (f" ({alan})" if alan else "")


# --------------------------------------------------------------------------
# Secim aciklamasi
# --------------------------------------------------------------------------


def secim_metni(s: dict[str, Any], kayitlar: list[dict[str, Any]]) -> list[str]:
    by = {k.get("kimlik"): k for k in kayitlar}
    out: list[str] = []
    toplam = s["toplam_aday"]
    if s["kapsam"] == "tum-adaylar":
        out.append(f"Degerlendirme: {toplam} adayin hepsi gercek dosyada denendi.")
    elif s["kapsam"] == "kismi":
        out.append(f"Degerlendirme: {toplam} adaydan yalnizca {s['degerlendirilen']} tanesi denendi (ilk gecende durma "
                   "ya da --en-fazla). Secim DEGERLENDIRILENLER arasindadir; butun adaylar arasinda en dusuk "
                   "maliyetli oldugu iddia edilmez.")
    else:
        out.append(f"Degerlendirme: {s['degerlendirilen']} aday kaydi var; uretilen aday sayisi bilinmiyor "
                   "(ozet.json yok). Kuresel en dusuk iddia edilmez.")
    if s["gecerli_yok"]:
        if s["gecen_sayisi"]:
            out.append(f"Secilen aday: YOK. {s['gecen_sayisi']} aday gecti ama hepsinin maliyeti eksik/gecersiz: "
                       f"{', '.join(s['maliyeti_eksik'])}. Eksik maliyet sifir sayilmadi.")
        else:
            out.append(f"Secilen aday: YOK - gecerli aday bulunamadi (durumlar: "
                       f"{', '.join(f'{d} {n}' for d, n in s['durumlar'].items()) or 'aday yok'}).")
            kalan = Counter(kod for k in kayitlar if k.get("tur") == "gercek-aday"
                            for kod, v in (k.get("kontroller") or {}).items() if v != "gecti")
            if kalan:
                out.append("Gecmeyen kontroller (aday sayisi): " + ", ".join(f"{kod} {n}" for kod, n in
                                                                            kalan.most_common()) + ".")
        return out
    sec_k = by[s["secilen"]]
    out.append(f"Secilen aday: {s['secilen']} - {degisiklik_metni(sec_k)}; degisiklik maliyeti "
               f"{maliyet_metni(sec_k)}.")
    n = len(s["gecen_sirasi"])
    gerekce = (f"Gerekce: zorunlu kontrollerin hepsini gecen {n} aday arasinda en dusuk degisiklik maliyeti "
               f"({s['secilen_maliyet']:g})." if n > 1 else
               f"Gerekce: degerlendirilenler icinde zorunlu kontrollerin hepsini gecen tek aday (maliyet "
               f"{s['secilen_maliyet']:g}).")
    if s["kuresel_en_dusuk"]:
        gerekce += " Butun adaylar degerlendirildigi icin bu, gecen adaylar icinde kuresel en dusuktur."
    out.append(gerekce)
    if s["esit_maliyetliler"]:
        out.append("Ayni maliyetli diger gecen adaylar: " + ", ".join(
            f"{x} ({degisiklik_metni(by[x])})" for x in s["esit_maliyetliler"]) + ".")
        if s["esitlik_cozumu"] == "kararli-kimlik":
            out.append("Esitlik belgelenmis ek tercihle (daha az yeni ihlal) ayrilmadi; kararli ureteci kimligi "
                       f"sirasiyla cozuldu ({kararli_kimlik(sec_k)} once). Bu adaylar daha kotu degildir, ayni "
                       "maliyetle esdeger alternatiflerdir.")
        else:
            out.append("Esitlik belgelenmis ek tercihle (daha az yeni ihlal) cozuldu; ayrinti tercih "
                       "sutununda.")
    if s["maliyeti_eksik"]:
        out.append(f"Gecen ama maliyeti eksik/gecersiz (secim disi, sifir sayilmadi): "
                   f"{', '.join(s['maliyeti_eksik'])}. Bu yuzden kuresel en dusuk iddia edilmez.")
    if s["ilk_gecen"] and s["ilk_gecen"] != s["secilen"]:
        out.append(f"Eski kural (deneme sirasinda ilk gecen) {s['ilk_gecen']} adayini secerdi "
                   f"(maliyet {maliyet_metni(by[s['ilk_gecen']])}).")
    elif s["ilk_gecen"]:
        out.append("Eski kural (ilk gecen) da ayni adayi secerdi.")
    if not s["temel_kaydi"]:
        out.append("Temel kayit yok: yeni ihlal hesaplanamadi, ek tercih uygulanamadi.")
    return out


def tercih_hucresi(t: dict[str, Any] | None) -> str:
    if not t:
        return "-"
    if t["secildi"]:
        return "SECILDI"
    if t["esit_maliyet"]:
        return "esit maliyet"
    if t["secime_uygun"]:
        return "daha pahali"
    if t["maliyet"] is None and t["neden"].startswith("gecti"):
        return "maliyet eksik"
    return "-"


# --------------------------------------------------------------------------
# Rapor (CLI ciktisi + rapor.md + arayuz ayni metni kullanir)
# --------------------------------------------------------------------------


def rapor_metni(kayitlar: list[dict[str, Any]], rapor: dict[str, Any]) -> str:
    s = sec(kayitlar, aday_sayisi=rapor.get("adaylar"))
    temel = next((k for k in kayitlar if k.get("tur") == "gercek-temel"), None)
    out = [f"# Gercek proje deneyi: {rapor.get('temel', '?')}", "", KAPSAM_NOTU, ""]
    if temel is not None:
        out.append(f"Temel durum: **{temel.get('durum')}**")
        for a in kontrol_aciklamalari(temel):
            out.append(f"- [{a['kod']}] {a['metin']}")
    out += ["", f"Aday {rapor.get('adaylar', '?')}, denenen {s['degerlendirilen']}, siralama "
                f"{rapor.get('siralama', '-')}; temel proje degismedi: {rapor.get('temel_degismedi', '?')}", ""]
    if temel is not None and temel.get("durum") == "gecti":
        out.append("Temel proje zorunlu kontrollerin hepsini geciyor - duzeltme gerekmiyor.")
    elif temel is not None and not s["degerlendirilen"]:
        out.append("Aday uretilmedi: temel durum 'kaldi' degil ya da bolucu taninmadi.")
    else:
        out += ["## Secim", ""] + [f"- {x}" for x in secim_metni(s, kayitlar)]
    adaylar = [k for k in kayitlar if k.get("tur") == "gercek-aday"]
    if adaylar:
        out += ["", "## Adaylar", "", "| kimlik | degisiklik | maliyet | durum | tercih | gecmeyen kontroller (ham) |",
                "|---|---|---|---|---|---|"]
        for k in adaylar:
            m, _ = maliyet_degeri(k)
            kalan = ", ".join(f"{a}={v}" for a, v in (k.get("kontroller") or {}).items() if v != "gecti") or "-"
            out.append(f"| {k['kimlik']} | {degisiklik_metni(k)} | {'-' if m is None else f'{m:g}'} | "
                       f"{k.get('durum')} | {tercih_hucresi(s['tercih'].get(k['kimlik']))} | {kalan} |")
        out += ["", "## Gerekceler", ""]
        for k in adaylar:
            out.append(f"**{k['kimlik']}** ({k.get('durum')}; tercih: {s['tercih'][k['kimlik']]['neden']})")
            if k.get("durum") == "gecti":
                out.append(f"- {gecti_ozeti(k)}")
            for a in kontrol_aciklamalari(k):
                out.append(f"- [{a['kod']}] {a['metin']}")
            out.append("")
    if temel is not None and temel.get("kapsam_disi"):
        out += ["## Modellenmeyenler (kapsam disi)", ""] + [f"- {x}" for x in temel["kapsam_disi"]]
    return "\n".join(out).rstrip()
