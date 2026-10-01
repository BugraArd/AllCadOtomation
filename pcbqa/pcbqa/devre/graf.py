"""Devre grafi: bilesen -> pin -> ag dugumleri, her birinin PCB karsiligiyla.

Okuyucular ayri ayri tek bir soruyu cevapliyordu: netlist "neye bagli",
kart "nerede", sematik "hangi alanlar". Bu modul ucunu, parca bilgisini ve
calisma kosullarini tek bir yapida birlestirir, boylece

    "R1 = 10k"  yerine
    "R1 (10 kohm, tolerans bilinmiyor, 0603 -> 0.1 W paket-tipik) U2.PA5 ile
     +3V3 arasinda PULL-UP; kartta (31.2, 14.0) F.Cu; uzerindeki guc
     0.33 mW (Ohm yasasi)"

cumlesi kurulabilir. Kurallar (dogrulama/), benzetim (spice/), iz analizi
(pcb_akim.py) ve ML (ml/devre_veri.py) bu grafigi okur.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from ..model import ref_kind
from ..netlist import Netlist, netlist_from_board
from ..pcb import Board
from .bilgi import Bilgi, bilinen, eksik
from .kosullar import Kosullar, ag_anahtari
from .parca import Kutuphane, ParcaBilgisi, PinBilgisi, parca_bilgisi, varsayilan_kutuphane

# Toprak ag adlari (elektrik.TOPRAK ile ayni kume; dongusel ice aktarimi
# onlemek icin burada da tutulur, test esitligi korur).
TOPRAK_ADLARI = {"GND", "GNDA", "GNDD", "GNDPWR", "GNDREF", "AGND", "DGND", "PGND",
                 "VSS", "VSSA", "EARTH", "0V"}


@dataclass
class PadKarsiligi:
    numara: str
    x: float
    y: float
    ag: str
    katmanlar: tuple[str, ...] = ()
    boyut: tuple[float, float] = (0.0, 0.0)
    delik: float = 0.0
    tur: str = "smd"

    def as_dict(self) -> dict[str, Any]:
        return {"numara": self.numara, "x": round(self.x, 4), "y": round(self.y, 4),
                "ag": self.ag, "katmanlar": list(self.katmanlar),
                "boyut": [round(v, 4) for v in self.boyut], "delik": self.delik, "tur": self.tur}


@dataclass
class PinDugumu:
    ref: str
    numara: str
    ad: str = ""
    tip: str = ""            # KiCad elektriksel tipi (input, power_in, passive...)
    ag: str = ""             # sematik agi (yoksa PCB agi)
    padler: list[PadKarsiligi] = field(default_factory=list)
    bilgi: PinBilgisi | None = None

    @property
    def tam(self) -> str:
        return f"{self.ref}.{self.numara}"

    @property
    def gorunen(self) -> str:
        return f"{self.ref}.{self.ad or self.numara}"

    @property
    def islev(self) -> str:
        """Parca bilgisindeki islev; yoksa KiCad tipinden turetilir."""
        if self.bilgi and self.bilgi.islev:
            return self.bilgi.islev
        return {
            "input": "giris", "output": "cikis", "bidirectional": "iki-yonlu",
            "tri_state": "cikis", "power_in": "guc-giris", "power_out": "guc-cikis",
            "open_collector": "acik-kolektor", "open_emitter": "cikis",
            "passive": "pasif", "no_connect": "nc", "free": "pasif",
            "unspecified": "",
        }.get(self.tip, "")

    def as_dict(self) -> dict[str, Any]:
        return {
            "numara": self.numara, "ad": self.ad, "tip": self.tip, "islev": self.islev,
            "ag": self.ag, "padler": [p.as_dict() for p in self.padler],
            "sinirlar": ({k: s.as_dict() for k, s in self.bilgi.sinirlar.items()}
                         if self.bilgi else {}),
        }


@dataclass
class PcbKarsiligi:
    footprint: str
    x: float
    y: float
    aci: float
    katman: str
    alan_mm2: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {"footprint": self.footprint, "x": round(self.x, 4), "y": round(self.y, 4),
                "aci": self.aci, "katman": self.katman, "alan_mm2": round(self.alan_mm2, 3)}


@dataclass
class Rol:
    """Bir bilesenin devredeki gorevi ve neden o goreve atandigi."""

    ad: str
    hedefler: list[str] = field(default_factory=list)   # ilgili ref / pinler
    aglar: dict[str, str] = field(default_factory=dict)  # gorev adi -> ag
    gerekce: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"ad": self.ad, "hedefler": list(self.hedefler), "aglar": dict(self.aglar),
                "gerekce": self.gerekce}


@dataclass
class BilesenDugumu:
    ref: str
    deger: str = ""
    lib_id: str = ""
    footprint: str = ""
    tur: str = "other"
    alanlar: dict[str, str] = field(default_factory=dict)
    datasheet: str = ""
    parca: ParcaBilgisi = field(default_factory=ParcaBilgisi)
    pinler: dict[str, PinDugumu] = field(default_factory=dict)
    pcb: PcbKarsiligi | None = None
    roller: list[Rol] = field(default_factory=list)
    sematikte: bool = True
    dnp: bool = False

    def rol(self, ad: str) -> Rol | None:
        for r in self.roller:
            if r.ad == ad:
                return r
        return None

    def rol_adlari(self) -> list[str]:
        return [r.ad for r in self.roller]

    def aglar(self) -> list[str]:
        return [p.ag for p in self.pinler.values() if p.ag]

    def pin_islevle(self, *islevler: str) -> list[PinDugumu]:
        return [p for p in self.pinler.values() if p.islev in islevler]

    def eksikler(self) -> list[str]:
        out = list(self.parca.eksikler())
        if self.pcb is None:
            out.append("PCB karsiligi yok (karta yerlestirilmemis ya da kart okunmadi)")
        else:
            padsiz = sorted(p.numara for p in self.pinler.values() if not p.padler)
            if padsiz:
                out.append(f"footprint'te karsiligi olmayan sembol pinleri: {', '.join(padsiz)}")
        if not self.sematikte:
            out.append("sematikte yok (yalnizca PCB'de)")
        return out

    def as_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref, "deger": self.deger, "lib_id": self.lib_id,
            "footprint": self.footprint, "tur": self.tur, "dnp": self.dnp,
            "alanlar": dict(self.alanlar), "datasheet": self.datasheet,
            "parca": self.parca.as_dict(),
            "pinler": {k: p.as_dict() for k, p in self.pinler.items()},
            "pcb": self.pcb.as_dict() if self.pcb else None,
            "roller": [r.as_dict() for r in self.roller],
            "eksikler": self.eksikler(),
        }


@dataclass
class AgDugumu:
    ad: str
    sinif: str = "Default"
    pinler: list[PinDugumu] = field(default_factory=list)
    gerilim: Bilgi = field(default_factory=lambda: eksik("ag adi gerilim soylemiyor, beyan yok"))
    toprak: bool = False
    # PCB tarafi (kart okunduysa)
    iz_uzunlugu_mm: float = 0.0
    min_iz_genisligi_mm: float | None = None
    via_sayisi: int = 0
    dokum_alani_mm2: float = 0.0

    @property
    def refler(self) -> set[str]:
        return {p.ref for p in self.pinler}

    def as_dict(self) -> dict[str, Any]:
        return {
            "ad": self.ad, "sinif": self.sinif, "toprak": self.toprak,
            "gerilim": self.gerilim.as_dict(),
            "pinler": [p.tam for p in self.pinler],
            "pcb": {"iz_uzunlugu_mm": round(self.iz_uzunlugu_mm, 3),
                    "min_iz_genisligi_mm": self.min_iz_genisligi_mm,
                    "via_sayisi": self.via_sayisi,
                    "dokum_alani_mm2": round(self.dokum_alani_mm2, 2)},
        }


@dataclass
class DevreGrafi:
    proje: str = ""
    bilesenler: dict[str, BilesenDugumu] = field(default_factory=dict)
    aglar: dict[str, AgDugumu] = field(default_factory=dict)
    kosullar: Kosullar = field(default_factory=Kosullar)
    board: Board | None = None
    # Hangi okuyucular katkida bulundu ("netlist", "kart", "sematik", "kosullar")
    kaynaklar: list[str] = field(default_factory=list)

    # ------------------------------------------------------------ sorgular

    def bilesen(self, ref: str) -> BilesenDugumu | None:
        return self.bilesenler.get(ref)

    def ag(self, ad: str) -> AgDugumu | None:
        if ad in self.aglar:
            return self.aglar[ad]
        anahtar = ag_anahtari(ad)
        for a in self.aglar.values():
            if ag_anahtari(a.ad) == anahtar:
                return a
        return None

    def pin(self, ref: str, numara: str) -> PinDugumu | None:
        b = self.bilesenler.get(ref)
        return b.pinler.get(numara) if b else None

    def gerilim(self, ag: str) -> Bilgi:
        a = self.ag(ag)
        return a.gerilim if a else eksik(f"ag yok: {ag}")

    def toprak_mi(self, ag: str) -> bool:
        a = self.ag(ag)
        return bool(a and a.toprak)

    def ray_mi(self, ag: str) -> bool:
        """Gerilimi bilinen, topraktan farkli bir besleme agi mi?"""
        a = self.ag(ag)
        if a is None or a.toprak:
            return False
        if a.gerilim.bilinen:
            return True
        return any(p.tip in ("power_in", "power_out") for p in a.pinler)

    def bilesenler_on(self, ag: str, tur: str | None = None) -> list[BilesenDugumu]:
        a = self.ag(ag)
        if a is None:
            return []
        out = []
        for ref in sorted(a.refler):
            b = self.bilesenler.get(ref)
            if b and (tur is None or b.tur == tur):
                out.append(b)
        return out

    def rolle(self, ad: str) -> list[tuple[BilesenDugumu, Rol]]:
        return [(b, r) for b in self.bilesenler.values() for r in b.roller if r.ad == ad]

    def kategoride(self, *kategoriler: str) -> list[BilesenDugumu]:
        return [b for b in self.bilesenler.values() if b.parca.kategori in kategoriler]

    def iki_uc(self, b: BilesenDugumu) -> tuple[str, str] | None:
        """Iki uclu bilesenin (pin1 agi, pin2 agi). Numara sirasiyla."""
        pins = sorted(b.pinler.values(), key=lambda p: p.numara)
        if len(pins) != 2:
            return None
        return pins[0].ag, pins[1].ag

    # ------------------------------------------------------------ rapor

    def eksik_raporu(self) -> dict[str, list[str]]:
        return {ref: b.eksikler() for ref, b in sorted(self.bilesenler.items()) if b.eksikler()}

    def ozet(self) -> dict[str, Any]:
        n = len(self.bilesenler)
        eksiksiz = sum(1 for b in self.bilesenler.values() if not b.eksikler())
        gerilimli = sum(1 for a in self.aglar.values() if a.gerilim.bilinen)
        rollu = sum(1 for b in self.bilesenler.values() if b.roller)
        return {
            "bilesen": n,
            "ag": len(self.aglar),
            "gerilimi_bilinen_ag": gerilimli,
            "rolu_bilinen_bilesen": rollu,
            "eksiksiz_bilesen": eksiksiz,
            "pcb_karsiligi_olan": sum(1 for b in self.bilesenler.values() if b.pcb),
            "kaynaklar": list(self.kaynaklar),
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "proje": self.proje,
            "ozet": self.ozet(),
            "kosullar": self.kosullar.as_dict(),
            "bilesenler": {k: b.as_dict() for k, b in sorted(self.bilesenler.items())},
            "aglar": {k: a.as_dict() for k, a in sorted(self.aglar.items())},
        }

    def bilesen_cumlesi(self, ref: str) -> str:
        """Tek satirlik insan okunur ozet ("R1 = 10k" yerine)."""
        b = self.bilesenler.get(ref)
        if b is None:
            return f"{ref}: yok"
        baglar = ", ".join(f"{p.numara}:{p.ag or '-'}" for p in
                           sorted(b.pinler.values(), key=lambda p: p.numara))
        roller = ", ".join(r.ad for r in b.roller) or "rol bilinmiyor"
        guc = b.parca.sinir("guc")
        guc_m = f"{guc.onerilen_max:g} W ({guc.guven or 'beyan'})" if guc and guc.onerilen_max else "guc siniri bilinmiyor"
        yer = (f"kartta ({b.pcb.x:.2f}, {b.pcb.y:.2f}) {b.pcb.katman}" if b.pcb else "kartta yok")
        return f"{ref} [{b.deger}] {baglar} | {roller} | {guc_m} | {yer}"


# --------------------------------------------------------------------------
# Kurulum
# --------------------------------------------------------------------------

_SONEK = re.compile(r"^(.*)_(\w+)$")


def _pin_adi(pinfunction: str, numara: str) -> str:
    """KiCad 10 netlist'i "VO_2" yazar; numara sonekini atar."""
    m = _SONEK.match(pinfunction or "")
    if m and m.group(2) == numara:
        return m.group(1)
    return pinfunction or ""


def _ad_toprak_mi(ad: str) -> bool:
    return ag_anahtari(ad) in TOPRAK_ADLARI


def graf_kur(
    *,
    netlist: Netlist | None = None,
    board: Board | None = None,
    kosullar: Kosullar | None = None,
    kutuphane: Kutuphane | None = None,
    sematik=None,
    proje: str = "",
) -> DevreGrafi:
    """Okuyuculardan devre grafini kurar.

    En az biri gerekir: `netlist` (sematikten) ya da `board`. Yalnizca kart
    verilirse baglanti kartin pad aglarindan okunur (netlist_from_board).
    """
    if netlist is None and board is None:
        raise ValueError("graf_kur: netlist ya da board gerekli")
    kutuphane = kutuphane if kutuphane is not None else varsayilan_kutuphane()
    kosullar = kosullar if kosullar is not None else Kosullar()
    g = DevreGrafi(proje=proje, kosullar=kosullar, board=board)

    sematik_var = netlist is not None
    if netlist is None:
        netlist = netlist_from_board(board)
        g.kaynaklar.append("kart (baglanti pad aglarindan)")
    else:
        g.kaynaklar.append("netlist")
    if board is not None:
        g.kaynaklar.append("kart")
    if sematik is not None:
        g.kaynaklar.append("sematik")
    if kosullar.yol is not None or kosullar.raylar or kosullar.yukler:
        g.kaynaklar.append("kosullar")

    by_ref_pcb = {c.ref: c for c in board.components} if board is not None else {}
    sem_sym = {s.ref: s for s in sematik.real_symbols} if sematik is not None else {}

    # --- bilesenler ---------------------------------------------------
    refs = set(netlist.components)
    if board is not None:
        refs |= set(by_ref_pcb)
    for ref in sorted(refs):
        sc = netlist.components.get(ref)
        comp = by_ref_pcb.get(ref)
        sym = sem_sym.get(ref)
        alanlar: dict[str, str] = {}
        if sc is not None:
            alanlar.update(sc.fields)
        if sym is not None:
            for k, v in sym.properties.items():
                alanlar.setdefault(k, v)
        deger = (sc.value if sc and sc.value else (comp.value if comp else ""))
        footprint = (sc.footprint if sc and sc.footprint else (comp.footprint_id if comp else ""))
        lib_id = f"{sc.lib}:{sc.libpart}" if sc and sc.libpart else (sym.lib_id if sym else "")
        tur = ref_kind(ref)
        b = BilesenDugumu(
            ref=ref, deger=deger, lib_id=lib_id, footprint=footprint, tur=tur,
            alanlar=alanlar, datasheet=(sc.datasheet if sc else ""),
            sematikte=(sc is not None) if sematik_var else True,
            dnp=bool(sym.dnp) if sym is not None else False,
        )
        b.parca = parca_bilgisi(
            tur=tur, deger=deger, footprint=footprint,
            libpart=(sc.libpart if sc else ""), lib_id=lib_id,
            alanlar=alanlar, kutuphane=kutuphane,
        )
        if comp is not None:
            b.pcb = PcbKarsiligi(comp.footprint_id, comp.x, comp.y, comp.rotation,
                                 comp.layer, comp.area_mm2)
        # Pin listesi: once kutuphane sembolu (bagli olmayanlar dahil TAM liste)
        for lp in netlist.lib_pins_of(ref):
            b.pinler[lp.number] = PinDugumu(ref=ref, numara=lp.number, ad=lp.name, tip=lp.type)
        g.bilesenler[ref] = b

    # --- aglar --------------------------------------------------------
    for net in netlist.nets:
        a = g.aglar.setdefault(net.name, AgDugumu(ad=net.name, sinif=net.netclass))
        for node in net.nodes:
            b = g.bilesenler.get(node.ref)
            if b is None:
                continue
            pin = b.pinler.get(node.pin)
            if pin is None:
                pin = PinDugumu(ref=node.ref, numara=node.pin,
                                ad=_pin_adi(node.pinfunction, node.pin), tip=node.pintype)
                b.pinler[node.pin] = pin
            if not pin.tip:
                pin.tip = node.pintype
            if not pin.ad:
                pin.ad = _pin_adi(node.pinfunction, node.pin)
            pin.ag = net.name
            a.pinler.append(pin)

    # --- PCB pad karsiliklari ----------------------------------------------
    for ref, comp in by_ref_pcb.items():
        b = g.bilesenler[ref]
        for pad in comp.pads:
            if not pad.number:
                continue  # numarasiz mekanik pad
            pk = PadKarsiligi(pad.number, pad.x, pad.y, pad.net, pad.copper_layers,
                              (pad.size_x, pad.size_y), pad.drill, pad.kind)
            pin = b.pinler.get(pad.number)
            if pin is None:
                # Sembolde olmayan numarali pad (montaj tabi, EP). Netlist
                # yoksa pin listesi zaten padlerden kurulur.
                if sematik_var and b.sematikte:
                    continue
                pin = PinDugumu(ref=ref, numara=pad.number, ad=pad.function,
                                tip=pad.pintype, ag=pad.net)
                b.pinler[pad.number] = pin
            pin.padler.append(pk)

    # --- pin parca bilgisi ---------------------------------------------
    for b in g.bilesenler.values():
        for pin in b.pinler.values():
            pin.bilgi = b.parca.pin_bilgisi(pin.numara, pin.ad)

    # --- PCB ag istatistikleri -------------------------------------------
    if board is not None:
        for tr in board.tracks:
            a = g.aglar.get(tr.net)
            if a is None:
                continue
            a.iz_uzunlugu_mm += tr.length_mm
            a.min_iz_genisligi_mm = (tr.width if a.min_iz_genisligi_mm is None
                                     else min(a.min_iz_genisligi_mm, tr.width))
        for v in board.vias:
            if v.net in g.aglar:
                g.aglar[v.net].via_sayisi += 1
        for z in board.zones:
            if z.net in g.aglar:
                g.aglar[z.net].dokum_alani_mm2 += z.area_mm2

    _gerilimleri_coz(g)
    from .roller import rolleri_cikar  # dongusel ice aktarim yok: roller graf'i kullanir

    rolleri_cikar(g)
    _regulator_cikislari(g)  # roller regulatoru tanidiktan sonra cikis gerilimi
    return g


def _gerilimleri_coz(g: DevreGrafi) -> None:
    """Ag gerilimi: beyan > ag adi. Regulator cikisi rollerden sonra eklenir."""
    from ..elektrik import ray_gerilimi

    for a in g.aglar.values():
        a.toprak = _ad_toprak_mi(a.ad)
        ray = g.kosullar.ray(a.ad)
        if ray is not None:
            a.gerilim = bilinen(ray.nom, f"kosullar beyani ({ray.ad})", "beyan")
            if ray.nom == 0.0:
                a.toprak = True
            continue
        if a.toprak:
            a.gerilim = bilinen(0.0, "referans dugumu (toprak tanimi)", "turetilmis")
            continue
        volt, nereden = ray_gerilimi(a.ad)
        if volt is not None:
            a.gerilim = bilinen(volt, nereden, "turetilmis")
        else:
            a.gerilim = eksik(nereden or f"{a.ad!r} adi gerilim soylemiyor ve beyan yok")


def regulator_cikis_gerilimi(b: BilesenDugumu) -> Bilgi:
    """Sabit cikisli regulatorun nominal cikisi - parca bilgisinden."""
    s = b.parca.sinir("vout")
    if s and s.onerilen_min is not None and s.onerilen_max is not None:
        return bilinen(round((s.onerilen_min + s.onerilen_max) / 2.0, 6),
                       f"{b.ref} ({b.deger}) cikisi: {s.kaynak}", s.guven or "dogrulanmamis")
    if b.parca.spice and "vnom" in b.parca.spice.parametreler:
        return bilinen(float(b.parca.spice.parametreler["vnom"]),
                       f"{b.ref} ({b.deger}) cikisi: {b.parca.spice.kaynak}", "dogrulanmamis")
    return eksik(f"{b.ref} cikis gerilimi parca bilgisinde yok")


def _regulator_cikislari(g: DevreGrafi) -> None:
    for b, rol in g.rolle("regulator"):
        cikis = rol.aglar.get("cikis")
        a = g.ag(cikis) if cikis else None
        if a is None or a.gerilim.bilinen:
            continue  # beyan ya da ad zaten soyluyor; beyan her zaman kazanir
        v = regulator_cikis_gerilimi(b)
        if v.bilinen:
            a.gerilim = v


def tum_pinler(g: DevreGrafi) -> Iterable[PinDugumu]:
    for b in g.bilesenler.values():
        yield from b.pinler.values()
