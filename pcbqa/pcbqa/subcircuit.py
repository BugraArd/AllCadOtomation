"""Alt-devre tanima: karttaki bilinen devre bloklarini topolojiden bulur.

Neden gerekli: kural on ayarlari simdiye kadar NET ADINA bakiyordu
(`net: "^(FB|VFB|VSENSE)$"`). Gercek kartlarda bu yetmiyor - KiCad geri besleme
netini `Net-(U2-FB{slash}VSET)` diye otomatik adlandiriyor ve hicbir desen
tutmuyor. Ama IC'nin PIN ADI "FB/VSET" olarak duruyor. Yani dogru yol addan
degil TOPOLOJIDEN gitmek: regulatorun FB pininden geriye izlemek.

Ayni altyapi iki yeri birden aciyor:
  * kurallarin kesinligi (hangi direnc FB bolucusu, hangi kondansator CIN)
  * uretken tasarim (once tanimak, sonra uretmek)

Su an yalnizca anahtarlamali regulator (buck) taniniyor. Imza minimal tutuldu:
SW pini + o nette bir induktor. Daha fazlasini sart kosmak gercek kartlarda
kaybettiriyor - bazi parcalarda VIN ile EN ayni nette, bazilarinda cikis
"VOS" diye adlandirilmis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import geom
from .model import Design

# Pin ADI desenleri. Kismi eslesme bilincli: gercek parcalarda pin adi
# "FB/VSET", "SW1", "PVIN" gibi bilesik olabiliyor.
_SW = re.compile(r"^(SW|PH|LX|VSW|PHASE)\b|^SW\d*$", re.IGNORECASE)
_FB = re.compile(r"^(FB|VFB|VSENSE|ADJ)", re.IGNORECASE)
_VIN = re.compile(r"^(VIN|PVIN|VCC|VDD)\b|^P?VIN\d*$", re.IGNORECASE)
_BOOT = re.compile(r"^(BOOT|BST|CB)\b", re.IGNORECASE)
_GND = re.compile(r"^(GND|PGND|AGND|VSS|EP|PAD|THERMAL)\b", re.IGNORECASE)


# KiCad sembollerinde pin adi BICIMLEME isaretlemesi tasiyabilir:
#   V_{IN}  altsimge      ~{RESET}  ustcizgi      A^{2}  ustsimge
# Gercek kartta gorildu: jetson'daki TPS564247'nin VIN pini "V_{IN}" yaziyor;
# desen tutmadigi icin giris kondansatorleri bulunamiyordu.
_MARKUP = re.compile(r"[~_^]\{|\}")


def normalize_pin_name(name: str) -> str:
    """Pin adindan bicimleme isaretlemesini atar: "V_{IN}" -> "VIN"."""
    return _MARKUP.sub("", name or "")


@dataclass
class BuckConverter:
    """Tanimis bir anahtarlamali regulator ve rolleri.

    Alanlarin bir kismi None olabilir: gercek kartlarda her rol bulunamiyor
    (ornegin cikis "VOS" pininden okunuyorsa `out_net` induktorden turetilir).
    Kural motoru None rolleri sessizce atlamalidir.
    """

    ic: str
    sw_net: str
    inductor: str | None = None
    out_net: str | None = None
    vin_net: str | None = None
    fb_net: str | None = None
    boot_net: str | None = None
    # "buck" ya da "buck-boost". Ikincisinde induktor IKI anahtarlama dugumu
    # arasindadir ve `out_net` bu yolla belirlenemez.
    topology: str = "buck"
    gnd_net: str | None = None
    # SW dugumundeki HARICI anahtarlama elemanlari (FET / diyot). Bos degilse
    # regulator AYRIKTIR ve giris sicak dongusu IC'nin dort pad'inden GECMEZ.
    external_switches: list[str] = field(default_factory=list)
    # Ayrik tasarimda anahtar rolleri - TOPOLOJIDEN, pin adindan degil.
    # Ust kol: VIN ve SW'de pad'i olan. Alt kol: SW ve GND'de pad'i olan.
    high_side: str | None = None
    low_side: str | None = None
    cin: list[str] = field(default_factory=list)
    cout: list[str] = field(default_factory=list)
    fb_resistors: list[str] = field(default_factory=list)

    def describe(self) -> str:
        parts = [f"IC={self.ic}", f"tip={self.topology}", f"SW={self.sw_net}"]
        if self.inductor:
            parts.append(f"L={self.inductor}")
        if self.vin_net:
            parts.append(f"VIN={self.vin_net}")
        if self.fb_net:
            parts.append(f"FB={self.fb_net}")
        return " ".join(parts)


def _pins_by_ref(design: Design) -> dict[str, list]:
    """ref -> o bilesenin pinleri. Net dongusunu bir kez doner."""
    out: dict[str, list] = {}
    for net_name in design.net_names():
        for pin in design.pins_on_net(net_name):
            out.setdefault(pin.ref, []).append(pin)
    return out


def _first_net(pins, pattern) -> str | None:
    for pin in pins:
        if pin.function and pattern.search(normalize_pin_name(pin.function)):
            return pin.net
    return None


def _switch_nets(pins) -> set[str]:
    """IC'nin TUM anahtarlama dugumu netleri (buck-boost'ta iki tane olur)."""
    return {
        pin.net
        for pin in pins
        if pin.function and _SW.search(normalize_pin_name(pin.function)) and pin.net
    }


def _components_on(design: Design, net: str | None, kind: str) -> list[str]:
    if not net:
        return []
    return sorted({p.ref for p in design.pins_on_net(net) if design.kind_of(p.ref) == kind})


def find_buck_converters(design: Design) -> list[BuckConverter]:
    """Karttaki anahtarlamali regulatorleri topolojiden bulur.

    Imza: bir IC'nin SW pini + o nette bir induktor. Bu iki sey bir arada
    baska bir devrede pratikte gorulmez.

    Cikis neti induktorun DIGER ucundan turetilir; IC'nin cikis pini
    ("VOS", "VOUT", "FB") parcadan parcaya degisiyor ve guvenilir degil.
    """
    pins_by_ref = _pins_by_ref(design)
    found: list[BuckConverter] = []

    for comp in design.board.components:
        if design.kind_of(comp.ref) != "ic":
            continue
        pins = pins_by_ref.get(comp.ref, [])
        sw_net = _first_net(pins, _SW)
        if not sw_net:
            continue

        inductors = _components_on(design, sw_net, "inductor")
        if not inductors:
            continue  # SW adli pin var ama anahtarlama dugumu degil

        buck = BuckConverter(ic=comp.ref, sw_net=sw_net, inductor=inductors[0])
        buck.vin_net = _first_net(pins, _VIN)
        buck.fb_net = _first_net(pins, _FB)
        buck.boot_net = _first_net(pins, _BOOT)
        buck.gnd_net = _first_net(pins, _GND)

        # Cikis: induktorun SW olmayan ucu.
        #
        # AMA once topolojiyi ayirmak gerek: BUCK-BOOST ve sarj denetleyicilerde
        # (or. TI BQ25672) induktor IKI anahtarlama dugumu ARASINDADIR. Orada
        # "diger uc" cikis degil, ikinci anahtardir. Gercek kartta gorildu -
        # One-Air-Max U5: SW1 -> L1 -> SW2 - ve out_net yanlislikla SW2 cikiyordu.
        switch_nets = _switch_nets(pins)
        ind_nets = {
            p.net for p in pins_by_ref.get(buck.inductor, []) if p.net and p.net != sw_net
        }
        other = ind_nets - switch_nets
        if ind_nets and not other:
            buck.topology = "buck-boost"
            buck.out_net = None
        else:
            buck.out_net = sorted(other)[0] if other else None

        # AYRIK MI? SW dugumunde harici FET ya da diyot varsa anahtarlama
        # IC'nin DISINDA oluyor. Diyot da sayilir: asenkron buck'ta alt kol
        # diyottur ve donus yolu yine IC'nin disindan gecer.
        buck.external_switches = sorted(
            _components_on(design, sw_net, "transistor")
            + _components_on(design, sw_net, "diode")
        )

        if buck.external_switches:
            # Roller BAGLANTIDAN cikarilir, pin adindan DEGIL: ayrik FET
            # sembollerinde pin adlari "D/G/S", "1/2/3" ya da bos olabiliyor.
            # Bootstrap diyodu bu testi gecemez - GND'de pad'i yoktur.
            def _on(ref: str, net: str | None) -> bool:
                return bool(net) and any(
                    pin.ref == ref for pin in design.pins_on_net(net)
                )

            buck.high_side = next(
                (
                    r
                    for r in buck.external_switches
                    if _on(r, buck.vin_net) and _on(r, sw_net)
                ),
                None,
            )
            buck.low_side = next(
                (
                    r
                    for r in buck.external_switches
                    if r != buck.high_side and _on(r, sw_net) and _on(r, buck.gnd_net)
                ),
                None,
            )

        buck.cin = _components_on(design, buck.vin_net, "capacitor")
        buck.cout = _components_on(design, buck.out_net, "capacitor")
        buck.fb_resistors = _components_on(design, buck.fb_net, "resistor")
        found.append(buck)

    return found


def _pad_xy(design: Design, ref: str, net: str | None):
    """Bir bilesenin belirli bir netteki pad'inin konumu."""
    if not net:
        return None
    for pin in design.pins_on_net(net):
        if pin.ref == ref and pin.placed:
            return (pin.x, pin.y)
    return None


def hot_loop_polygon(design: Design, buck: BuckConverter):
    """Giris sicak dongusunun cevreledigi dortgen - ya da None.

    TI AN-2155 bu alani OLCTU: 6 mm2'de SW spike 2.5 V ve CISPR-22 Class B
    marji 8.3 dB; 18 mm2'de 6.1 V ve 6.7 dB. Projedeki en guclu sayisal kanit.

    ENTEGRE regulatorlerde (her iki anahtar da IC icinde) dongu sudur:

        CIN.VIN  ->  IC.VIN  ->  IC.GND  ->  CIN.GND  ->  (CIN icinden geri)

    Dort pad'in cevreledigi dortgen. Anahtarlarin IC ICI baglantisini bilmeye
    gerek yok; akim IC'ye VIN'den girip GND'den cikiyor.

    AYRIK tasarimlarda (harici FET'ler) o dortgen YANLIS olur - orada dongu
    FET'lerin uzerinden geciyor. Ustelik yanlis yonde: IC'ye yakin duran dort
    pad KUCUK bir alan verir, yani sorunlu bir kart sessizce gecerdi. O yuzden
    ayrik tasarimda AKIM YOLU izlenir ve dongu bir ALTIGENDIR:

        CIN.VIN -> Qust.VIN -> Qust.SW -> Qalt.SW -> Qalt.GND -> CIN.GND

    Asenkron buck'ta alt kol diyottur; ayni altigen gecerlidir cunku donus
    yolu yine SW'den GND'ye o elemanin uzerinden gider.

    Roller cozulemezse (ornegin yalnizca ust kol harici) yine None doner -
    olcemedigimize sayi UYDURMAYIZ. `thermal`in olculen egri disina cikmayi
    reddetmesiyle ayni ilke.

    SINIR: bu altigen GERCEK bir ayrik kartta dogrulanmadi - korpusta ayrik
    regulator yok (alti regulatorun altisi entegre). Geometri analitik olarak
    sinandi (bilinen koordinatlar -> bilinen alan) ve roller topolojiden
    cikiyor, ama tanima gercek bir ayrik kartta gorulmedi.

    Alan `geom.area` (shoelace) ile hesaplanir; poligon AKIM YOLU sirasindadir.
    Kendini kesen patolojik bir yerlesimde shoelace gercek cevrelenen alandan
    kucuk verir - entegre yoldaki dortgen de ayni varsayimi tasiyor.

    En KUCUK dongulu giris kondansatoru secilir: AC akimi tasiyan odur
    (Richtek AN045 "en kucuk paket en yakina" der).
    """
    if not (buck.vin_net and buck.gnd_net and buck.cin):
        return None

    if buck.external_switches:
        if not (buck.high_side and buck.low_side):
            return None  # rol cozulemedi - kural bunu "OLCULEMEDI" diye yazar
        mid = [
            _pad_xy(design, buck.high_side, buck.vin_net),
            _pad_xy(design, buck.high_side, buck.sw_net),
            _pad_xy(design, buck.low_side, buck.sw_net),
            _pad_xy(design, buck.low_side, buck.gnd_net),
        ]
        if any(pt is None for pt in mid):
            return None
        best = None
        for ref in buck.cin:
            cap_vin = _pad_xy(design, ref, buck.vin_net)
            cap_gnd = _pad_xy(design, ref, buck.gnd_net)
            if cap_vin is None or cap_gnd is None:
                continue
            poly = [cap_vin, *mid, cap_gnd]
            a = geom.area(poly)
            if best is None or a < best[0]:
                best = (a, ref, poly)
        return None if best is None else (best[2], best[1])

    ic_vin = _pad_xy(design, buck.ic, buck.vin_net)
    ic_gnd = _pad_xy(design, buck.ic, buck.gnd_net)
    if ic_vin is None or ic_gnd is None:
        return None

    best = None
    for ref in buck.cin:
        cap_vin = _pad_xy(design, ref, buck.vin_net)
        cap_gnd = _pad_xy(design, ref, buck.gnd_net)
        if cap_vin is None or cap_gnd is None:
            continue
        poly = [ic_vin, cap_vin, cap_gnd, ic_gnd]
        area = geom.area(poly)
        if best is None or area < best[0]:
            best = (area, ref, poly)
    return None if best is None else (best[2], best[1])


def hot_loop_area_mm2(design: Design, buck: BuckConverter) -> float | None:
    """Sicak dongu alani (mm2) - olculemiyorsa None."""
    result = hot_loop_polygon(design, buck)
    return None if result is None else geom.area(result[0])


# ad -> bulucu. Ileride boost/LDO eklenirse buraya girer.
DETECTORS = {
    "buck": find_buck_converters,
}
