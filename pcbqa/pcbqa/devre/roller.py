"""Rol cikarimi: bir bilesenin devredeki GOREVI topolojiden.

Kurallar parcaya ve devrenin amacina bagli olmali: "bu direnc 4k7" bilgisi
tek basina hicbir kurali tetiklemez; "bu direnc PA5'in I2C pull-up'i" ise
pull-up hesabini, "bu kondansator U1'in VI dekuplaji" ise yakinlik ve
gerilim kurallarini acar.

Roller ve imzalari (hepsi agdan, ad tahmini yok - yalnizca pin ADI ve
parca kategorisi kullanilir):

  regulator              kategori ldo/regulator ya da lib Regulator_*;
                         giris/cikis aglari pin islevinden (guc-giris/cikis)
  regulator-giris-kond   C: bir ucu regulator girisinde, digeri toprakta
  regulator-cikis-kond   C: bir ucu regulator cikisinda, digeri toprakta
  dekuplaj               C: ray-toprak arasinda, rayda bir IC guc pini var
  toplu-kond             C: ray-toprak arasinda, IC guc pini yok
  pull-up / pull-down    R: bir ucu ray/toprak, digeri sinyal agi (IC pini)
  bolucu                 iki R ayni orta dugumde, uclari ray ve toprak
  led-seri-direnci       R: bir ucu bir LED'in pini
  gate-direnci           R: bir ucu bir MOSFET gate'i
  anahtar                MOSFET; aglar: gate/drain/source
  enduktif-yuk           L / role (K) / motor (M): bir ucu anahtar drain'inde
  serbest-gecis-diyotu   D: enduktif yukun iki ucuna ters paralel
  led, tvs, sigorta, konnektor, guc-girisi, kristal, test-noktasi, mcu
"""

from __future__ import annotations

import re

from .graf import BilesenDugumu, DevreGrafi, Rol

_REG_LIB = re.compile(r"^Regulator_", re.IGNORECASE)
_LED = re.compile(r"(^|[:_])LED|^LED", re.IGNORECASE)
_TVS = re.compile(r"TVS|ESD|^SM[AB]J|^P6KE|^PESD|^SMF", re.IGNORECASE)
_FET_LIB = re.compile(r"Transistor_FET|MOSFET", re.IGNORECASE)
_MCU_LIB = re.compile(r"^MCU_", re.IGNORECASE)
_VIN_AD = re.compile(r"^(VIN|VI|IN|PVIN|VCC)\d*$", re.IGNORECASE)
_VOUT_AD = re.compile(r"^(VOUT|VO|OUT)\d*$", re.IGNORECASE)
_GATE_AD = re.compile(r"^G(ATE)?$", re.IGNORECASE)
_DRAIN_AD = re.compile(r"^D(RAIN)?$", re.IGNORECASE)
_SOURCE_AD = re.compile(r"^S(OURCE)?$", re.IGNORECASE)
_SWD = re.compile(r"SWDIO|SWCLK|SWD|NRST|TCK|TMS|TDI|TDO|BOOT0|UPDI|PDI", re.IGNORECASE)


# Muhendislik secimi: 1 uF ustu ray kondansatoru TOPLU (bulk) sayilir;
# dekuplaj kondansatorleri tipik olarak 10 nF - 1 uF araligindadir.
DEKUPLAJ_UST_F = 1e-6


def _en_yakin(g: DevreGrafi, c: BilesenDugumu, ray: str, hedefler: list[str]) -> list[str]:
    """Kart varsa kondansatoru EN YAKIN IC guc pinine atar; yoksa hepsi."""
    c_pin = next((p for p in c.pinler.values() if p.ag == ray and p.padler), None)
    if c_pin is None:
        return hedefler
    cx, cy = c_pin.padler[0].x, c_pin.padler[0].y
    mesafeler = []
    for h in hedefler:
        ref, _, no = h.partition(".")
        p = g.pin(ref, no)
        if p is not None and p.padler:
            mesafeler.append(((p.padler[0].x - cx) ** 2 + (p.padler[0].y - cy) ** 2, h))
    return [min(mesafeler)[1]] if mesafeler else hedefler


def _ekle(b: BilesenDugumu, rol: Rol) -> None:
    if b.rol(rol.ad) is None:
        b.roller.append(rol)


def _kategori_duzelt(g: DevreGrafi) -> None:
    """Kutuphane kaydi olmayan bilesenlere kutuphane adindan kategori."""
    for b in g.bilesenler.values():
        k = b.parca.kategori
        if k not in ("genel", "entegre"):
            continue
        if b.tur == "ic" and _REG_LIB.search(b.lib_id):
            b.parca.kategori = "regulator"
        elif b.tur == "ic" and _MCU_LIB.search(b.lib_id):
            b.parca.kategori = "mcu"
        elif b.tur == "transistor" and (_FET_LIB.search(b.lib_id) or
                                        {p.ad.upper() for p in b.pinler.values()} >= {"G", "D", "S"}):
            b.parca.kategori = "mosfet-p" if "P-CH" in b.lib_id.upper() or "PMOS" in b.lib_id.upper() \
                else "mosfet-n"
        elif b.tur == "diode" and (_LED.search(b.lib_id) or _LED.search(b.deger)):
            b.parca.kategori = "led"
        elif b.tur == "diode" and (_TVS.search(b.lib_id) or _TVS.search(b.deger)):
            b.parca.kategori = "tvs"
        elif b.tur == "diode":
            b.parca.kategori = "diyot"
        elif b.tur == "ic":
            b.parca.kategori = "entegre"
        elif b.ref.upper().startswith("K"):
            b.parca.kategori = "role"


def _pin_agi(b: BilesenDugumu, *, islev: tuple[str, ...] = (), ad: re.Pattern | None = None) -> str | None:
    for p in sorted(b.pinler.values(), key=lambda p: p.numara):
        if islev and p.islev in islev and p.ag:
            return p.ag
        if ad and p.ad and ad.match(p.ad) and p.ag:
            return p.ag
    return None


def _ic_guc_pinleri(g: DevreGrafi, ag: str, haric: set[str]) -> list[str]:
    a = g.ag(ag)
    if a is None:
        return []
    return sorted({
        p.tam for p in a.pinler
        if p.ref not in haric
        and g.bilesenler[p.ref].tur == "ic"
        and (p.islev in ("guc-giris",) or p.tip == "power_in")
    })


def _ic_sinyal_pinleri(g: DevreGrafi, ag: str) -> list[str]:
    a = g.ag(ag)
    if a is None:
        return []
    return sorted({
        p.tam for p in a.pinler
        if g.bilesenler[p.ref].tur in ("ic", "connector", "transistor")
        and p.islev not in ("guc-giris", "guc-cikis", "gnd")
    })


def rolleri_cikar(g: DevreGrafi) -> None:
    _kategori_duzelt(g)

    # --- regulatorler ---------------------------------------------------
    reg_giris: dict[str, str] = {}
    reg_cikis: dict[str, str] = {}
    for b in g.bilesenler.values():
        if b.parca.kategori not in ("ldo", "regulator"):
            continue
        giris = _pin_agi(b, islev=("guc-giris",)) or _pin_agi(b, ad=_VIN_AD)
        cikis = _pin_agi(b, islev=("guc-cikis",)) or _pin_agi(b, ad=_VOUT_AD)
        rol = Rol("regulator", aglar={k: v for k, v in (("giris", giris), ("cikis", cikis)) if v},
                  gerekce="parca kategorisi " + b.parca.kategori)
        _ekle(b, rol)
        if giris:
            reg_giris[giris] = b.ref
        if cikis:
            reg_cikis[cikis] = b.ref

    # --- MOSFET anahtarlar ------------------------------------------------
    drainler: dict[str, str] = {}
    gateler: dict[str, str] = {}
    for b in g.bilesenler.values():
        if b.parca.kategori not in ("mosfet-n", "mosfet-p"):
            continue
        gate = _pin_agi(b, islev=("gate",)) or _pin_agi(b, ad=_GATE_AD)
        drain = _pin_agi(b, islev=("drain",)) or _pin_agi(b, ad=_DRAIN_AD)
        source = _pin_agi(b, islev=("source",)) or _pin_agi(b, ad=_SOURCE_AD)
        aglar = {k: v for k, v in (("gate", gate), ("drain", drain), ("source", source)) if v}
        surucu = _ic_sinyal_pinleri(g, gate) if gate else []
        _ekle(b, Rol("anahtar", hedefler=[s for s in surucu if not s.startswith(b.ref + ".")],
                     aglar=aglar, gerekce="MOSFET; gate surucusu = gate agindaki IC pini"))
        if drain:
            drainler[drain] = b.ref
        if gate:
            gateler[gate] = b.ref

    # --- iki uclu pasifler ve diyotlar -------------------------------------
    for b in g.bilesenler.values():
        uclar = g.iki_uc(b)
        k = b.parca.kategori

        if k == "led":
            _ekle(b, Rol("led", gerekce="LED"))
        if k == "tvs":
            _ekle(b, Rol("tvs", aglar=dict(zip(("a", "b"), uclar or ())), gerekce="TVS/ESD"))
        if k == "sigorta" or b.tur == "fuse":
            _ekle(b, Rol("sigorta", aglar=dict(zip(("giris", "cikis"), uclar or ())),
                         gerekce="F oneki / kategori"))
        if b.tur == "crystal":
            _ekle(b, Rol("kristal"))
        if b.tur == "testpoint":
            _ekle(b, Rol("test-noktasi", aglar={"ag": a for a in b.aglar()[:1]}))
        if k == "mcu":
            _ekle(b, Rol("mcu"))

        if uclar is None or not all(uclar):
            continue
        a1, a2 = uclar

        if b.tur == "capacitor":
            toprak = [a for a in (a1, a2) if g.toprak_mi(a)]
            ray = [a for a in (a1, a2) if g.ray_mi(a)]
            if len(toprak) == 1 and ray:
                r = ray[0]
                if r in reg_giris:
                    _ekle(b, Rol("regulator-giris-kond", [reg_giris[r]], {"ray": r},
                                 f"{reg_giris[r]} girisi ile toprak arasinda"))
                if r in reg_cikis:
                    _ekle(b, Rol("regulator-cikis-kond", [reg_cikis[r]], {"ray": r},
                                 f"{reg_cikis[r]} cikisi ile toprak arasinda"))
                hedef = _ic_guc_pinleri(g, r, haric=set(reg_giris.values()) | set(reg_cikis.values()))
                deger = b.parca.deger.deger if b.parca.deger.bilinen else None
                toplu = isinstance(deger, float) and deger > DEKUPLAJ_UST_F
                if hedef and not toplu:
                    hedef = _en_yakin(g, b, r, hedef)
                    _ekle(b, Rol("dekuplaj", hedef, {"ray": r},
                                 "ray-toprak arasinda, rayda IC guc pini var"
                                 + ("; hedef en yakin guc pini" if len(hedef) == 1 else "")))
                elif r not in reg_giris and r not in reg_cikis:
                    _ekle(b, Rol("toplu-kond", [], {"ray": r},
                                 f"ray-toprak arasinda{' ve > 1 uF' if toplu else ''}"))

        elif b.tur == "resistor":
            ray = [a for a in (a1, a2) if g.ray_mi(a)]
            toprak = [a for a in (a1, a2) if g.toprak_mi(a)]
            diger = [a for a in (a1, a2) if not g.ray_mi(a) and not g.toprak_mi(a)]
            # LED / gate direnci once: bir ucu bir LED'e ya da gate'e degiyorsa.
            # Ortak ag ray ya da toprak OLMAMALI: toprakta bir LED katodu
            # olmasi, topraga giden her direnci "LED direnci" yapmaz.
            for a in (a1, a2):
                if g.toprak_mi(a) or g.ray_mi(a):
                    continue
                for c in g.bilesenler_on(a):
                    if c.ref != b.ref and c.parca.kategori == "led":
                        _ekle(b, Rol("led-seri-direnci", [c.ref], {"ag": a}, f"{c.ref} LED'i ile seri"))
                if a in gateler:
                    _ekle(b, Rol("gate-direnci", [gateler[a]], {"gate": a},
                                 f"{gateler[a]} gate'ine bagli"))
            if len(diger) == 1 and (ray or toprak):
                hedef = _ic_sinyal_pinleri(g, diger[0])
                if hedef and diger[0] not in gateler:
                    ad = "pull-up" if ray else "pull-down"
                    _ekle(b, Rol(ad, hedef, {"sinyal": diger[0], "ray": (ray or toprak)[0]},
                                 f"sinyal agi {diger[0]} ile {(ray or toprak)[0]} arasinda"))

        elif k in ("diyot", "zener", "tvs") or b.tur == "diode":
            pass  # serbest gecis diyotu asagida, yuk bilindikten sonra

    _bolucu_bul(g)
    _enduktif_yukler(g, drainler)
    _konnektorler(g)


def _bolucu_bul(g: DevreGrafi) -> None:
    """Iki direnc ortak bir orta dugumde, uclari ray ve toprakta."""
    for a in g.aglar.values():
        if a.toprak or g.ray_mi(a.ad):
            continue
        rs = [b for b in g.bilesenler_on(a.ad, "resistor") if g.iki_uc(b)]
        ust = [r for r in rs if any(g.ray_mi(x) for x in g.iki_uc(r) if x != a.ad)]
        alt = [r for r in rs if any(g.toprak_mi(x) for x in g.iki_uc(r) if x != a.ad)]
        if ust and alt:
            hedef = _ic_sinyal_pinleri(g, a.ad)
            for r in ust:
                _ekle(r, Rol("bolucu", [alt[0].ref] + hedef, {"orta": a.ad, "konum": "ust"},
                             f"orta dugum {a.ad}"))
                r.roller = [x for x in r.roller if x.ad != "pull-up"]
            for r in alt:
                _ekle(r, Rol("bolucu", [ust[0].ref] + hedef, {"orta": a.ad, "konum": "alt"},
                             f"orta dugum {a.ad}"))
                r.roller = [x for x in r.roller if x.ad != "pull-down"]


def _enduktif_yukler(g: DevreGrafi, drainler: dict[str, str]) -> None:
    for drain, fet in drainler.items():
        for c in g.bilesenler_on(drain):
            if c.ref == fet:
                continue
            enduktif = c.tur == "inductor" or c.parca.kategori == "role" or \
                c.ref.upper().startswith(("K", "M")) and c.tur == "other"
            if not enduktif:
                continue
            uclar = g.iki_uc(c) or tuple(sorted(set(c.aglar())))[:2]
            diger = [a for a in uclar if a != drain]
            _ekle(c, Rol("enduktif-yuk", [fet], {"drain": drain, "besleme": diger[0] if diger else ""},
                         f"{fet} drain'i tarafindan anahtarlaniyor"))
            # Ters paralel diyot: bir ucu drain, digeri besleme
            for d in g.bilesenler_on(drain):
                if d.parca.kategori not in ("diyot", "zener", "tvs") and d.tur != "diode":
                    continue
                d_uclar = set(d.aglar())
                if diger and {drain, diger[0]} <= d_uclar:
                    _ekle(d, Rol("serbest-gecis-diyotu", [c.ref, fet], {"drain": drain},
                                 f"{c.ref} enduktif yukune paralel"))


def _konnektorler(g: DevreGrafi) -> None:
    for b in g.bilesenler.values():
        if b.tur != "connector":
            continue
        aglar = set(b.aglar())
        _ekle(b, Rol("konnektor", aglar={str(i): a for i, a in enumerate(sorted(aglar))}))
        raylar = [a for a in aglar if g.ray_mi(a)]
        toprak = [a for a in aglar if g.toprak_mi(a)]
        if raylar and toprak:
            # Rayi besleyen bir guc-cikis pini yoksa ya da beyan kaynak diyorsa
            for r in raylar:
                a = g.ag(r)
                # Rayi kart ICINDE suren bir sey varsa (guc-cikis pini,
                # transistor, regulator, diyot, bobin) konnektor guc girisi
                # degil, o rayin tuketicisidir (ornek: programlama soketi).
                def surer(p) -> bool:
                    c = g.bilesenler[p.ref]
                    reg = c.rol("regulator")
                    if reg is not None:
                        return reg.aglar.get("cikis") == r  # girisi tuketicidir
                    return p.islev == "guc-cikis" or c.tur in ("transistor", "diode", "inductor")

                besleyen = a is not None and any(surer(p) for p in a.pinler)
                if g.kosullar.kaynak_mi(r) or not besleyen:
                    _ekle(b, Rol("guc-girisi", aglar={"ray": r, "toprak": toprak[0]},
                                 gerekce="konnektor ray ve topraga bagli, rayi baska kaynak beslemiyor"))
                    break
        if any(_SWD.search(a.lstrip("/")) for a in aglar):
            _ekle(b, Rol("programlama", aglar={a: a for a in aglar if _SWD.search(a.lstrip("/"))},
                         gerekce="SWD/JTAG ag adlari"))
