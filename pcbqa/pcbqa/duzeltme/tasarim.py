"""Duzenlenebilir tasarim: netlist + kart + kosullar uclusu ve degisiklikler.

Duzeltme adayi bir DEGISIKLIK listesidir ("R1 degeri 10k -> 4.99k", "R2
footprint'i 0603 -> 1206"). Aday denenirken kullanicinin dosyasina YAZILMAZ:
degisiklik bu uclunun bir KOPYASINA uygulanir ve kopyadan devre grafi
kurulur. Boylece KiCad acik olsa da (kilit dosyasi) aday degerlendirmek
guvenlidir; yazma ayri, kullanici onayli bir adimdir.

Footprint degisikligi kartta gercek geometriyle yapilir: yeni footprint
KiCad'in kendi kutuphanesinden (`.kicad_mod`) `pcb_sync.build_footprint_node`
ile okunur, eski bilesenin konumuna ve acisina konur, pad aglari pad
numarasiyla tasinir. Courtyard ve pad olculeri boylece uydurma degil,
kutuphanedeki dosyanin kendisidir.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from ..devre.graf import DevreGrafi, graf_kur
from ..devre.kosullar import kosullari_ayristir
from ..netlist import Netlist
from ..pcb import Board, Component

TOLERANS_ALANI = "Tolerance"
MPN_ALANI = "MPN"
# MPN bu modulce uretici kuralindan turetildiyse (Kicad-7cb) deger / tolerans /
# footprint degisiminde YENIDEN turetilir: BOM ile tasarim tutarli kalir. Bu
# isaret yoksa MPN'e dokunulmaz (kullanicinin MPN'i elle secilmistir).
MPN_KAYNAK_ALANI = "MPN_Kaynak"
MPN_KURAL = "kural:yageo-rc-l-v10"


@dataclass(frozen=True)
class Degisiklik:
    ref: str
    alan: str        # "deger" | "tolerans" | "footprint"
    eski: str
    yeni: str

    def as_dict(self) -> dict[str, str]:
        return {"ref": self.ref, "alan": self.alan, "eski": self.eski, "yeni": self.yeni}

    @classmethod
    def from_dict(cls, ham: dict[str, str]) -> "Degisiklik":
        return cls(str(ham["ref"]), str(ham["alan"]), str(ham["eski"]), str(ham["yeni"]))

    def metin(self) -> str:
        return f"{self.ref} {self.alan}: {self.eski} -> {self.yeni}"


def deger_metni(ohm: float) -> str:
    """4990 -> "4.99k", 1e6 -> "1M", 330 -> "330" (KiCad deger alani bicimi)."""
    if ohm >= 1e6:
        return f"{ohm / 1e6:.3g}M"
    if ohm >= 1e3:
        return f"{ohm / 1e3:.3g}k"
    return f"{ohm:.3g}"


def tolerans_metni(oran: float) -> str:
    return f"{oran * 100:g}%"


# --------------------------------------------------------------------------
# Footprint geometrisi (KiCad kutuphanesinden, onbellekli)
# --------------------------------------------------------------------------

_FP_ONBELLEK: dict[str, Component] = {}


def kutuphane_bileseni(footprint_id: str) -> Component:
    """Kutuphanedeki footprint'i (0, 0)'da, donmemis Component olarak okur."""
    if footprint_id not in _FP_ONBELLEK:
        from ..pcb import _read_footprint
        from ..pcb_sync import NewFootprint, build_footprint_node

        node = build_footprint_node(NewFootprint("X", footprint_id, "", "/0/0"), "kutuphane.kicad_sch")
        comp = _read_footprint(node)
        if comp is None:
            raise ValueError(f"footprint okunamadi: {footprint_id}")
        _FP_ONBELLEK[footprint_id] = comp
    return copy.deepcopy(_FP_ONBELLEK[footprint_id])


def footprint_degistir(eski: Component, footprint_id: str) -> Component:
    """`eski` bilesenin yerine ayni konum/aci/aglarla yeni footprint koyar."""
    yeni = kutuphane_bileseni(footprint_id)
    aglar = {p.number: p.net for p in eski.pads if p.number}
    yeni.ref, yeni.value, yeni.layer = eski.ref, eski.value, eski.layer
    for p in yeni.pads:
        p.net = aglar.get(p.number, "")
    yeni.place(eski.x, eski.y, eski.rotation)
    return yeni


def mpn_esitle(c) -> None:
    """Kuralla turetilmis MPN'i bilesenin guncel paket/tolerans/degerine esitler.
    Katalogda yoksa MPN alani BOSALTILIR ve kaynak "katalog-disi" olur:
    olmayan parca numarasi uydurulmaz (parca bilgisi eksik kalir)."""
    from ..circuit import parse_value
    from ..devre.parca import paket_kodu, rc_l_siparis_kodu, tolerans_metinden

    if c.fields.get(MPN_KAYNAK_ALANI) not in (MPN_KURAL, MPN_KURAL + ":katalog-disi"):
        return
    tol_metin = c.fields.get(TOLERANS_ALANI) or next((p for p in c.value.split()[1:] if p.endswith("%")), "")
    tol = tolerans_metinden(tol_metin) if tol_metin else None
    r = parse_value(c.value.split()[0]) if c.value.split() else None
    kod = rc_l_siparis_kodu(paket_kodu(c.footprint), tol, r) if tol is not None and r else None
    if kod:
        c.fields[MPN_ALANI] = kod
        c.fields[MPN_KAYNAK_ALANI] = MPN_KURAL
    else:
        c.fields.pop(MPN_ALANI, None)
        c.fields[MPN_KAYNAK_ALANI] = MPN_KURAL + ":katalog-disi"


# --------------------------------------------------------------------------
# Tasarim
# --------------------------------------------------------------------------


@dataclass
class Tasarim:
    netlist: Netlist
    board: Board | None
    kosullar: dict[str, Any]           # ham beyan (kayda aynen yazilir)
    proje: str = ""
    degisiklikler: list[Degisiklik] = field(default_factory=list)  # temelden bu yana
    # Kart yonlendirilmisse footprint degisiminden sonra izleri yeniden ureten
    # islev (board -> izler). Yoksa izlere dokunulmaz (Kicad-ecd).
    yonlendirici: Callable[[Board], list] | None = None

    def graf(self) -> DevreGrafi:
        return graf_kur(netlist=self.netlist, board=self.board,
                        kosullar=kosullari_ayristir(self.kosullar), proje=self.proje)

    def bilesen_ozeti(self, refler: Iterable[str]) -> dict[str, dict[str, str]]:
        out = {}
        for ref in refler:
            c = self.netlist.components[ref]
            # Tolerans alanda ya da deger metninde ("47k 1%") durabilir.
            tol = c.fields.get(TOLERANS_ALANI) or next(
                (p for p in c.value.split()[1:] if p.endswith("%")), "")
            out[ref] = {"deger": c.value, "tolerans": tol, "footprint": c.footprint}
            if c.fields.get(MPN_ALANI) or c.fields.get(MPN_KAYNAK_ALANI):
                out[ref]["mpn"] = c.fields.get(MPN_ALANI, "")
        return out

    def imza(self) -> str:
        """Elektriksel+geometrik icerigin ozeti: ayni tasarimi iki kez
        degerlendirmemek icin (onbellek anahtari)."""
        parcalar = sorted((r, c.value, c.footprint, sorted(c.fields.items()))
                          for r, c in self.netlist.components.items())
        # Kart geometrisi de anahtara girer: ayni degerler farkli yerlesimde
        # farkli PCB sonucu verir (Kicad-ecd; ilk surumde yalnizca deger vardi).
        kart = None
        if self.board is not None:
            kart = [sorted((c.ref, c.footprint_id, round(c.x, 4), round(c.y, 4), round(c.rotation, 2))
                           for c in self.board.components),
                    sorted((t.net, t.layer, t.width, t.x1, t.y1, t.x2, t.y2) for t in self.board.tracks),
                    self.board.outline]
        ham = json.dumps([parcalar, self.kosullar, kart], sort_keys=True, default=str)
        return hashlib.sha256(ham.encode("utf-8")).hexdigest()[:16]

    def uygula(self, degisiklikler: Iterable[Degisiklik]) -> "Tasarim":
        yeni = Tasarim(copy.deepcopy(self.netlist), copy.deepcopy(self.board),
                       copy.deepcopy(self.kosullar), self.proje, list(self.degisiklikler),
                       self.yonlendirici)
        footprint_degisti = False
        for d in degisiklikler:
            c = yeni.netlist.components.get(d.ref)
            if c is None:
                raise KeyError(f"tasarimda yok: {d.ref}")
            if d.alan == "deger":
                # Deger metnindeki ek bilgiler (tolerans, paket) korunur.
                kalan = c.value.split()[1:]
                c.value = " ".join([d.yeni, *kalan])
                if yeni.board is not None:
                    for comp in yeni.board.components:
                        if comp.ref == d.ref:
                            comp.value = c.value
            elif d.alan == "tolerans":
                c.fields[TOLERANS_ALANI] = d.yeni
                # Deger metninde de tolerans yaziyorsa celismesin
                c.value = " ".join(p for p in c.value.split() if not p.endswith("%"))
            elif d.alan == "mpn":
                # BOM'daki parca numarasi - kendi basina (footprint degismez)
                c.fields[MPN_ALANI] = d.yeni
                yeni.degisiklikler.append(d)
                continue
            elif d.alan == "footprint":
                c.footprint = d.yeni
                footprint_degisti = True
                if yeni.board is not None:
                    yeni.board.components = [
                        footprint_degistir(comp, d.yeni) if comp.ref == d.ref else comp
                        for comp in yeni.board.components
                    ]
            else:
                raise ValueError(f"bilinmeyen degisiklik alani: {d.alan}")
            mpn_esitle(c)
            yeni.degisiklikler.append(d)
        if footprint_degisti and yeni.board is not None and yeni.board.tracks and yeni.yonlendirici:
            # Pad'ler yer degistirdi: eski izler yeni pad'lere gitmez.
            yeni.board.tracks = yeni.yonlendirici(yeni.board)
        return yeni
