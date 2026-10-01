"""Degisiklik maliyeti - ozgun tasarim ile aday arasindaki FARK (Kicad-apg).

Maliyet degisiklik LISTESINDEN degil, iki tasarimin SON HALLERININ farkindan
hesaplanir. Boylece:
  * geri alinmis islem (10k -> 4.7k -> 10k) ve etkisiz islem ("4.7k" ->
    "4700") maliyet uretmez,
  * ayni bilesendeki deger + tolerans degisimi TEK parca degisimidir (BOM'da
    tek kalem degisir; iki kez sayilmaz).

Alanlar (her biri ayri kaydedilir):

  parca        BOM kalemi degisen bilesen sayisi (deger, tolerans ya da MPN
               farkli; ayni ref bir kez)
  deger, tolerans, mpn   bilgi icin ayri sayimlar (toplama GIRMEZ - parca'nin
               alt kirilimi; aksi halde ayni refi iki kez sayardik)
  footprint    land pattern'i degisen bilesen (parca'ya EK: kart duzeni de degisir)
  ekleme, silme  eklenen / silinen bilesen
  baglanti     agi degisen pin (eklenen/silinen bilesenin pinleri haric)
  yerlesim     konumu ya da acisi degisen bilesen (eklenen/silinen haric)
  yonlendirme  bakiri (iz parcalari) degisen ag

Agirliklar MUHENDISLIK SECIMIDIR (kaynak yok); proje tercihi
`kosullar.degisiklik_maliyeti` ile ezilir:

  parca 1.0       bir BOM kalemi degisimi = birim
  footprint 1.0   ek yeniden yerlesim/montaj kontrolu; parca ile birlikte 2
  ekleme 2.0      yeni kalem + yerlesim + baglanti
  silme 1.0
  baglanti 2.0    pin basina; sematik topolojisi degisimi en riskli islem
  yerlesim 0.5    bilesen basina
  yonlendirme 0.25  ag basina (iz yeniden cizimi; footprint degisiminin
                  dogal sonucu oldugu icin dusuk)
"""

from __future__ import annotations

from typing import Any

from ..circuit import parse_value
from ..devre.kosullar import ag_anahtari
from ..devre.parca import tolerans_metinden
from .tasarim import TOLERANS_ALANI, Tasarim

MALIYET_SURUMU = 1
VARSAYILAN_AGIRLIKLAR: dict[str, float] = {
    "parca": 1.0, "footprint": 1.0, "ekleme": 2.0, "silme": 1.0,
    "baglanti": 2.0, "yerlesim": 0.5, "yonlendirme": 0.25,
}
ALANLAR = ("parca", "deger", "tolerans", "mpn", "footprint", "ekleme", "silme", "baglanti", "yerlesim",
           "yonlendirme")
MPN_ALANLARI = ("MPN", "Manufacturer_Part_Number", "mpn")
_KONUM_TOL_MM = 1e-4
_ACI_TOL = 1e-3


def agirliklar(kosullar: dict[str, Any] | None = None, ek: dict[str, float] | None = None) -> dict[str, float]:
    """Varsayilan <- proje tercihi (kosullar.degisiklik_maliyeti) <- cagiran."""
    w = dict(VARSAYILAN_AGIRLIKLAR)
    proje = (kosullar or {}).get("degisiklik_maliyeti") or {}
    for kaynak in (proje, ek or {}):
        for k, v in kaynak.items():
            if k not in VARSAYILAN_AGIRLIKLAR:
                raise ValueError(f"bilinmeyen maliyet alani: {k!r} (gecerli: {sorted(VARSAYILAN_AGIRLIKLAR)})")
            w[k] = float(v)
    return w


def _deger(metin: str) -> float | str:
    ilk = (metin or "").split()[0] if (metin or "").split() else ""
    v = parse_value(ilk)
    return v if v is not None else ilk


def _tolerans(c) -> float | None:
    metin = c.fields.get(TOLERANS_ALANI) or next((p for p in c.value.split()[1:] if p.endswith("%")), "")
    return tolerans_metinden(metin) if metin else None


def _mpn(c) -> str:
    return next((str(c.fields[k]) for k in MPN_ALANLARI if c.fields.get(k)), "")


def _ayni_sayi(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= 1e-9 * max(abs(a), abs(b), 1e-30)
    return a == b


def _pin_aglari(t: Tasarim) -> dict[tuple[str, str], str]:
    return {(n.ref, n.pin): ag_anahtari(net.name) for net in t.netlist.nets for n in net.nodes}


def _bakir(t: Tasarim) -> dict[str, list]:
    out: dict[str, list] = {}
    if t.board is not None:
        for tr in t.board.tracks:
            out.setdefault(ag_anahtari(tr.net), []).append(
                (tr.layer, round(tr.width, 6), *sorted([(round(tr.x1, 4), round(tr.y1, 4)),
                                                        (round(tr.x2, 4), round(tr.y2, 4))])))
    return {k: sorted(v) for k, v in out.items()}


def fark(once: Tasarim, sonra: Tasarim) -> dict[str, Any]:
    """Iki tasarimin bilesen / baglanti / kart farki (sayimlar + hangi refler)."""
    a, b = once.netlist.components, sonra.netlist.components
    sayim = {k: 0 for k in ALANLAR}
    refler: dict[str, list[str]] = {}
    eklenen, silinen = sorted(set(b) - set(a)), sorted(set(a) - set(b))
    sayim["ekleme"], sayim["silme"] = len(eklenen), len(silinen)
    for ref in eklenen:
        refler[ref] = ["ekleme"]
    for ref in silinen:
        refler[ref] = ["silme"]
    for ref in sorted(set(a) & set(b)):
        ca, cb = a[ref], b[ref]
        alanlar = []
        if not _ayni_sayi(_deger(ca.value), _deger(cb.value)):
            alanlar.append("deger")
        if not _ayni_sayi(_tolerans(ca), _tolerans(cb)):
            alanlar.append("tolerans")
        if _mpn(ca) != _mpn(cb):
            alanlar.append("mpn")
        if alanlar:
            sayim["parca"] += 1
            for x in alanlar:
                sayim[x] += 1
        if ca.footprint != cb.footprint:
            alanlar.append("footprint")
            sayim["footprint"] += 1
        if alanlar:
            refler[ref] = alanlar
    # Baglanti: yalnizca iki tasarimda da var olan bilesenlerin pinleri
    pa, pb = _pin_aglari(once), _pin_aglari(sonra)
    ortak = set(a) & set(b)
    degisen_pin = sorted(f"{r}.{p}" for (r, p) in (set(pa) | set(pb))
                         if r in ortak and pa.get((r, p)) != pb.get((r, p)))
    sayim["baglanti"] = len(degisen_pin)
    if once.board is not None and sonra.board is not None:
        ka = {c.ref: c for c in once.board.components}
        kb = {c.ref: c for c in sonra.board.components}
        for ref in sorted(set(ka) & set(kb)):
            x, y = ka[ref], kb[ref]
            if (abs(x.x - y.x) > _KONUM_TOL_MM or abs(x.y - y.y) > _KONUM_TOL_MM
                    or abs((x.rotation - y.rotation + 180) % 360 - 180) > _ACI_TOL):
                sayim["yerlesim"] += 1
                refler.setdefault(ref, []).append("yerlesim")
        ba, bb = _bakir(once), _bakir(sonra)
        degisen_ag = sorted(k for k in set(ba) | set(bb) if ba.get(k) != bb.get(k))
        sayim["yonlendirme"] = len(degisen_ag)
    else:
        degisen_ag = []
    return {"sayim": sayim, "refler": refler, "pinler": degisen_pin, "aglar": degisen_ag}


def maliyet(once: Tasarim, sonra: Tasarim, w: dict[str, float] | None = None) -> dict[str, Any]:
    """Fark + agirlikli toplam. `toplam` yalnizca VARSAYILAN_AGIRLIKLAR
    alanlarindan; deger/tolerans/mpn parca'nin kirilimidir, toplama girmez."""
    w = w or agirliklar(once.kosullar)
    f = fark(once, sonra)
    toplam = sum(w[k] * f["sayim"][k] for k in VARSAYILAN_AGIRLIKLAR)
    return {"surum": MALIYET_SURUMU, "toplam": round(toplam, 6), "alanlar": f["sayim"],
            "refler": f["refler"], "agirliklar": w, "aglar": f["aglar"], "pinler": f["pinler"]}
