"""Kural motoru: "dogru pinler dogru baglanmis mi, hem de dogru mesafede mi?"

KiCad'in ERC'si "bu pin bagli degil" der; "bu kondansator yanlis yerde" demez.
Bu modul tam olarak o bosluğu doldurur: sematik NIYETI ile PCB FIZIGINI ayni
kuralda birlestirir.

Kurallar YAML ile tanimlanir, kod degistirmeden genisletilebilir.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


from . import circuit, geom, ipc2221, subcircuit, thermal
from .confload import ConfigError, load_config
from .model import Design, PinRef

SEVERITIES = ("error", "warning", "info")
DEFAULT_MAX_FINDINGS = 25

# Orantili cezada carpanin varsayilan tavani. 3.0 secildi: bir ihlalin en fazla
# uc kat agirlikta sayilmasi, "cok kotu" ile "biraz kotu"yu ayirmaya yetiyor
# ama tek bir uc ornegin skoru yutmasina izin vermiyor.
DEFAULT_SCALE_MAX = 3.0


class RuleError(ValueError):
    """Hatali kural tanimi."""


@dataclass
class Finding:
    """Tek bir bulgu."""

    rule_id: str
    severity: str
    message: str
    source: str = "pcbqa"
    refs: list[str] = field(default_factory=list)
    measured: float | None = None
    limit: float | None = None
    # Kural TIPI (`proximity`, `courtyard_overlap`...). `rule_id` kullanicinin
    # verdigi addir ve projeden projeye degisir; tip sabittir. `run_rules`
    # merkezi olarak doldurur, tek tek kontroller ugrasmaz.
    rule_type: str = ""
    # Bulguyu ureten PINLER ("U2.14", "C1.1") - `refs` ile ayni sirada.
    # `proximity` pin-pin mesafesi olcer; yalnizca referanslari bilmek olcumu
    # yeniden hesaplamaya yetmez, cunku SOIC-20'de bir pin merkeze 5 mm
    # uzakta olabilir - kuralin siniriyla ayni mertebede.
    pins: list[str] = field(default_factory=list)
    # Bu bulgunun skora yazacagi ceza. None ise `report.PENALTY` uzerinden
    # severity'den turetilir - yani agirlik BELIRTMEYEN kurallar ve disaridan
    # gelen bulgular (KiCad ERC/DRC, sematik kontrolleri) eski davranisi korur.
    # `run_rules` merkezi olarak doldurur, tek tek kontroller ugrasmaz.
    weight: float | None = None
    # Orantili ceza aciksa carpanin TAVANI; kapaliysa None. Iki bilgiyi tek
    # alanda tutmak, "acik mi" ile "ne kadar" arasinda tutarsizligi imkansiz
    # kilar. `run_rules` doldurur.
    scale_max: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_type": self.rule_type,
            "severity": self.severity,
            "message": self.message,
            "source": self.source,
            "refs": self.refs,
            "pins": self.pins,
            "measured": self.measured,
            "limit": self.limit,
            "weight": self.weight,
            "scale_max": self.scale_max,
        }


# --------------------------------------------------------------------- seciciler


def _rx(pattern: str | None):
    if not pattern:
        return None
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise RuleError(f"gecersiz duzenli ifade: {pattern!r} ({exc})") from exc


class Selector:
    """Bilesen/pin secici. Verilen tum alanlar AND ile birlestirilir."""

    def __init__(self, spec: dict[str, Any] | None) -> None:
        spec = spec or {}
        unknown = set(spec) - {"ref", "kind", "value", "pintype", "function"}
        if unknown:
            raise RuleError(f"bilinmeyen secici alani: {sorted(unknown)}")
        self.ref = _rx(spec.get("ref"))
        self.value = _rx(spec.get("value"))
        self.function = _rx(spec.get("function"))
        self.kind = spec.get("kind")
        self.pintype = spec.get("pintype")

    def describe(self) -> str:
        """Hata mesajlarinda kullanilacak kisa insan okunur tanim."""
        parts = []
        if self.kind:
            parts.append(str(self.kind))
        if self.ref:
            parts.append(f"ref~{self.ref.pattern}")
        if self.value:
            parts.append(f"deger~{self.value.pattern}")
        return " ".join(parts) or "bilesen"

    def matches_component(self, design: Design, ref: str) -> bool:
        if self.ref and not self.ref.search(ref):
            return False
        if self.kind and design.kind_of(ref) != self.kind:
            return False
        if self.value and not self.value.search(design.value_of(ref)):
            return False
        return True

    def matches_pin(self, design: Design, pin: PinRef) -> bool:
        if not self.matches_component(design, pin.ref):
            return False
        if self.pintype and pin.pintype != self.pintype:
            return False
        if self.function and not self.function.search(pin.function or pin.pin):
            return False
        return True


# ------------------------------------------------------------------ kural tipleri


@dataclass
class Rule:
    id: str
    type: str
    severity: str = "warning"
    description: str = ""
    spec: dict[str, Any] = field(default_factory=dict)
    ignore_nets: list[str] = field(default_factory=list)
    max_findings: int = DEFAULT_MAX_FINDINGS
    # Bu kuraldan cikan her bulgunun skora yazacagi ceza (bkz. Finding.weight).
    # None ise severity'den turetilir; boylece agirlik kullanmayan mevcut kural
    # dosyalari birebir eski skoru uretir.
    #
    # Neden gerekli: severity tek basina "olculmus etkisi olan bir kural" ile
    # "kaynaksiz bir muhendislik secimi"ni ayirt edemiyor - ikisi de 8 puan
    # yiyordu. Bkz. docs/yol-haritasi-skorlama.md
    weight: float | None = None
    # Ceza ihlalin BUYUKLUGUNE gore olceklensin mi? Varsayilan kapali, cunku
    # bu skor manzarasini degistirir ve yerlestirici o manzarayi optimize eder.
    scale: bool = False
    # Olcekleme carpaninin tavani. Tavan sart: `via_current`'ta kapasite sifira
    # yaklasirsa oran patlar ve tek bulgu butun skoru yutar.
    scale_max: float = DEFAULT_SCALE_MAX

    def net_ignored(self, net_name: str) -> bool:
        return any(re.fullmatch(p, net_name, re.IGNORECASE) for p in self.ignore_nets)


def _check_proximity(design: Design, rule: Rule) -> list[Finding]:
    """Bir pine, ayni netteki belirli bir bilesen turu N mm'den yakin olmali.

    Klasik kullanim: her IC guc pininin yaninda decoupling kondansatoru.

    `exclusive: true` onemli bir fark yaratir. Kapali oldugunda, 3V3 gibi genis
    bir rayda TEK bir kondansator butun guc pinlerini "tatmin eder" - oysa
    gercek beklenti her guc pininin KENDI kondansatorune sahip olmasidir.
    Acikken her partner en fazla bir hedef pine sayilir (en yakindan baslayarak
    esleme yapilir), yani eksik kondansatorler ortaya cikar.
    """
    pin_sel = Selector(rule.spec.get("pin"))
    partner_sel = Selector(rule.spec.get("partner"))
    max_mm = float(rule.spec.get("max_distance_mm", 10.0))
    require_partner = bool(rule.spec.get("require_partner", True))
    exclusive = bool(rule.spec.get("exclusive", False))

    findings: list[Finding] = []
    claimed: set[str] = set()  # exclusive modda kullanilmis partner referanslari

    for net_name in design.net_names():
        if rule.net_ignored(net_name):
            continue
        pins = design.pins_on_net(net_name)

        targets = [p for p in pins if pin_sel.matches_pin(design, p) and p.placed]
        if not targets:
            continue
        partners = [p for p in pins if partner_sel.matches_component(design, p.ref)]

        if not partners:
            if require_partner:
                for target in targets:
                    findings.append(
                        Finding(
                            rule_id=rule.id,
                            severity=rule.severity,
                            message=(
                                f"{target} ({net_name}) ayni nette uygun bir "
                                f"bilesen bulunamadi"
                            ),
                            refs=[target.ref],
                        )
                    )
            continue

        # Tum (hedef, partner) mesafelerini hesapla, en yakindan basla.
        # exclusive modda bu "aciozlu en yakin eslesme" (greedy matching) olur.
        pairs: list[tuple[float, PinRef, PinRef]] = []
        for target in targets:
            for partner in partners:
                if partner.ref == target.ref:
                    continue
                dist = target.distance_to(partner)
                if dist is not None:
                    pairs.append((dist, target, partner))
        pairs.sort(key=lambda t: t[0])

        matched: dict[str, tuple[float, PinRef]] = {}  # hedef anahtari -> (mesafe, partner)
        used: set[str] = set()
        for dist, target, partner in pairs:
            key = f"{target.ref}.{target.pin}"
            if key in matched:
                continue
            if exclusive and (partner.ref in claimed or partner.ref in used):
                continue
            matched[key] = (dist, partner)
            used.add(partner.ref)
        claimed |= used

        for target in targets:
            key = f"{target.ref}.{target.pin}"
            hit = matched.get(key)
            if hit is None:
                # exclusive modda partner'lar tukendi -> eksik bilesen
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        severity=rule.severity,
                        message=(
                            f"{target} icin ayri bir {partner_sel.describe()} yok "
                            f"(net {net_name}, mevcut olanlar baska pinlere atandi)"
                        ),
                        refs=[target.ref],
                    )
                )
                continue

            dist, partner = hit
            if dist > max_mm:
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        severity=rule.severity,
                        message=(
                            f"{target} icin en yakin {partner.ref} "
                            f"{dist:.1f} mm uzakta (hedef <= {max_mm:g} mm), net {net_name}"
                        ),
                        refs=[target.ref, partner.ref],
                        pins=[f"{target.ref}.{target.pin}", f"{partner.ref}.{partner.pin}"],
                        measured=round(dist, 2),
                        limit=max_mm,
                    )
                )

    return findings


def _check_courtyard_overlap(design: Design, rule: Rule) -> list[Finding]:
    """Iki bilesenin kapladigi alan cakismamali (uretilebilirlik).

    Ayni yuzdeki bilesenler karsilastirilir. Sinir kutusu yerine GERCEK
    poligon kullanilir: dondurulmus bilesenlerde sinir kutusu cok buyuk kalir
    ve yanlis alarm uretir (bkz. geom.py). Once ucuz bir sinir kutusu on
    elemesi yapilir, sonra kesin test.
    """
    clearance = float(rule.spec.get("clearance_mm", 0.0))
    ignore_refs = [_rx(p) for p in (rule.spec.get("ignore_refs") or [])]
    comps = [c for c in design.board.components if c.courtyard_poly]

    def ignored(ref: str) -> bool:
        return any(rx.search(ref) for rx in ignore_refs if rx)

    findings: list[Finding] = []
    for i, a in enumerate(comps):
        if ignored(a.ref):
            continue
        ax1, ay1, ax2, ay2 = a.courtyard
        for b in comps[i + 1 :]:
            if ignored(b.ref):
                continue
            if (a.layer.startswith("B.")) != (b.layer.startswith("B.")):
                continue  # farkli yuzler cakismaz

            # Ucuz on eleme: sinir kutulari bile yeterince uzaksa gec
            bx1, by1, bx2, by2 = b.courtyard
            if max(max(bx1 - ax2, ax1 - bx2), max(by1 - ay2, ay1 - by2)) >= clearance:
                continue

            if geom.overlap(a.courtyard_poly, b.courtyard_poly):
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        severity=rule.severity,
                        message=f"{a.ref} ve {b.ref} cakisiyor",
                        refs=[a.ref, b.ref],
                        measured=0.0,
                        limit=clearance,
                    )
                )
                continue

            gap = geom.distance(a.courtyard_poly, b.courtyard_poly)
            if gap < clearance:
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        severity=rule.severity,
                        message=(
                            f"{a.ref} ve {b.ref} arasinda sadece {gap:.2f} mm var "
                            f"(gereken >= {clearance:g} mm)"
                        ),
                        refs=[a.ref, b.ref],
                        measured=round(gap, 3),
                        limit=clearance,
                    )
                )
    findings.sort(key=lambda f: f.measured if f.measured is not None else 0)
    return findings


def _check_edge_clearance(design: Design, rule: Rule) -> list[Finding]:
    """Bilesenler kart kenarindan en az N mm iceride olmali (uretilebilirlik)."""
    min_mm = float(rule.spec.get("min_distance_mm", 1.0))
    ignore_refs = [_rx(p) for p in (rule.spec.get("ignore_refs") or [])]
    outline = design.board.outline
    if not outline:
        return []
    bx1, by1, bx2, by2 = outline

    findings: list[Finding] = []
    for comp in design.board.components:
        if not comp.courtyard:
            continue
        if any(rx.search(comp.ref) for rx in ignore_refs if rx):
            continue
        cx1, cy1, cx2, cy2 = comp.courtyard
        margin = min(cx1 - bx1, cy1 - by1, bx2 - cx2, by2 - cy2)
        if margin < min_mm:
            state = "kart disina tasiyor" if margin < 0 else f"kenara {margin:.2f} mm mesafede"
            findings.append(
                Finding(
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=f"{comp.ref} {state} (gereken >= {min_mm:g} mm)",
                    refs=[comp.ref],
                    measured=round(margin, 3),
                    limit=min_mm,
                )
            )
    findings.sort(key=lambda f: f.measured if f.measured is not None else 0)
    return findings


def _check_length_match(design: Design, rule: Rule) -> list[Finding]:
    """Bir grup netin tahmini uzunlugu birbirine yakin olmali.

    Diferansiyel ciftler ve paralel veri yollari icin. HPWL uzerinden calisir,
    yani yonlendirme oncesi bir on uyaridir - kesin uzunluk esleme kontrolu
    degil, "bu iki net cok farkli yerlerde duruyor" uyarisidir.
    """
    tolerance = float(rule.spec.get("tolerance_mm", 5.0))
    groups = rule.spec.get("groups") or []
    if not groups:
        raise RuleError(f"{rule.id}: 'groups' gerekli, or. [['USB_DP','USB_DM']]")

    findings: list[Finding] = []
    known = set(design.net_names())

    for group in groups:
        if not isinstance(group, list) or len(group) < 2:
            raise RuleError(f"{rule.id}: her grup en az iki net adi icermeli")

        missing = [n for n in group if n not in known]
        if missing:
            findings.append(
                Finding(
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=f"net bulunamadi: {', '.join(missing)}",
                )
            )
            continue

        lengths = {n: design.hpwl(n) for n in group}
        spread = max(lengths.values()) - min(lengths.values())
        if spread > tolerance:
            detail = ", ".join(f"{n}={v:.1f}mm" for n, v in lengths.items())
            findings.append(
                Finding(
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=(
                        f"uzunluk farki {spread:.1f} mm (tolerans {tolerance:g} mm): {detail}"
                    ),
                    measured=round(spread, 2),
                    limit=tolerance,
                )
            )
    return findings


def _check_require_on_net(design: Design, rule: Rule) -> list[Finding]:
    """Ada uyan her nette, belirli turde bir bilesen bulunmali (or. pull-up)."""
    net_rx = _rx(rule.spec.get("net", ".*"))
    partner_sel = Selector(rule.spec.get("partner"))

    findings: list[Finding] = []
    for net_name in design.net_names():
        if rule.net_ignored(net_name) or not net_rx.search(net_name):
            continue
        pins = design.pins_on_net(net_name)
        if not pins:
            continue
        if any(partner_sel.matches_component(design, p.ref) for p in pins):
            continue
        findings.append(
            Finding(
                rule_id=rule.id,
                severity=rule.severity,
                message=f"{net_name} netinde beklenen bilesen yok",
                refs=sorted({p.ref for p in pins}),
            )
        )
    return findings


def _check_net_length(design: Design, rule: Rule) -> list[Finding]:
    """Netin tahmini uzunlugu (HPWL) butceyi asmamali."""
    net_rx = _rx(rule.spec.get("net", ".*"))
    max_mm = float(rule.spec.get("max_hpwl_mm", 100.0))

    findings: list[Finding] = []
    for net_name in design.net_names():
        if rule.net_ignored(net_name) or not net_rx.search(net_name):
            continue
        length = design.hpwl(net_name)
        if length > max_mm:
            findings.append(
                Finding(
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=f"{net_name} tahmini uzunluk {length:.1f} mm (butce {max_mm:g} mm)",
                    refs=sorted({p.ref for p in design.pins_on_net(net_name)}),
                    measured=round(length, 2),
                    limit=max_mm,
                )
            )
    findings.sort(key=lambda f: f.measured or 0, reverse=True)
    return findings


def _check_same_net(design: Design, rule: Rule) -> list[Finding]:
    """Acikca belirtilen pinler ayni nette olmali. Dogrudan "niyet" kontrolu."""
    pins_spec = rule.spec.get("pins") or []
    if len(pins_spec) < 2:
        raise RuleError(f"{rule.id}: 'pins' en az iki pin icermeli (or. ['U1.8','U5.14'])")

    resolved: dict[str, str | None] = {}
    for item in pins_spec:
        if "." not in str(item):
            raise RuleError(f"{rule.id}: pin bicimi 'REF.PIN' olmali, gelen: {item!r}")
        ref, pin = str(item).split(".", 1)
        net = design.netlist.net_of(ref, pin)
        resolved[str(item)] = net.name if net else None

    missing = [k for k, v in resolved.items() if v is None]
    if missing:
        return [
            Finding(
                rule_id=rule.id,
                severity=rule.severity,
                message=f"pin bulunamadi veya bagli degil: {', '.join(missing)}",
                refs=[k.split(".")[0] for k in missing],
            )
        ]

    distinct = set(resolved.values())
    if len(distinct) > 1:
        detail = ", ".join(f"{k} -> {v}" for k, v in resolved.items())
        return [
            Finding(
                rule_id=rule.id,
                severity=rule.severity,
                message=f"pinler farkli netlerde: {detail}",
                refs=[k.split(".")[0] for k in resolved],
            )
        ]
    return []


def _net_matcher(rule: Rule, key: str = "net"):
    """Kuraldaki net secicisini derler."""
    return _rx(rule.spec.get(key, ".*"))


def _check_trace_width(design: Design, rule: Rule) -> list[Finding]:
    """Yonlendirilmis izler, netin tasidigi akim icin yeterince genis mi?

    Iki yontem: `ipc2221` (varsayilan, standardin formulu) ve `mm_per_amp`
    (ROHM 60AN066E'nin pratik kurali - kendi olcum egrisinden ~4x
    muhafazakar, ama ortam sicakligi ve komsu bilesen isisi icin marj birakir).

    YONLENDIRILMEMIS KART SESSIZCE ATLANIR. Bu bilincli: pcbqa'nin asil isi
    yerlestirme ve o asamada kartta hic bakir olmaz. Kartta hic iz yoksa kural
    hicbir bulgu uretmez; kart yonlendirilmis ama SECILEN net yonlendirilmemisse
    "info" verir - o gercekten anlamli bir bosluktur.
    """
    net_rx = _net_matcher(rule)
    current_a = float(rule.spec.get("current_a", 0.0))
    if current_a <= 0:
        raise RuleError(f"{rule.id}: 'current_a' pozitif olmali")

    delta_t = float(rule.spec.get("delta_t_c", ipc2221.DEFAULT_DELTA_T))
    copper_oz = float(rule.spec.get("copper_oz", ipc2221.DEFAULT_COPPER_OZ))
    method = rule.spec.get("method", "ipc2221")
    if method not in ("ipc2221", "mm_per_amp"):
        raise RuleError(f"{rule.id}: 'method' ipc2221 ya da mm_per_amp olmali")
    floor_mm = float(rule.spec.get("min_width_mm", 0.0))

    if not design.board.tracks:
        return []  # kart yonlendirilmemis - olculecek bakir yok

    findings: list[Finding] = []
    for net_name in design.net_names():
        if rule.net_ignored(net_name) or not net_rx.search(net_name):
            continue
        tracks = [t for t in design.board.tracks if t.net == net_name]
        if not tracks:
            # Tek pinli net (bagli olmayan pad) yonlendirilemez zaten - onu
            # "eksik" diye raporlamak yalnizca gurultu uretir.
            pins = design.pins_on_net(net_name)
            if len(pins) >= 2:
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        severity="info",
                        message=f"{net_name} netinde yonlendirilmis iz yok",
                        refs=sorted({p.ref for p in pins}),
                    )
                )
            continue

        narrowest = min(tracks, key=lambda t: t.width)
        if method == "mm_per_amp":
            required = ipc2221.rohm_width_mm(current_a, copper_oz)
        else:
            required = ipc2221.trace_width_mm(
                current_a, delta_t, copper_oz, outer=narrowest.is_outer
            )
        required = max(required, floor_mm)

        if narrowest.width + 1e-9 < required:
            layer_note = "dis" if narrowest.is_outer else "ic"
            findings.append(
                Finding(
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=(
                        f"{net_name}: en dar iz {narrowest.width:.3f} mm, "
                        f"{current_a:g} A icin {required:.3f} mm gerekiyor "
                        f"({layer_note} katman {narrowest.layer}, {method})"
                    ),
                    refs=sorted({p.ref for p in design.pins_on_net(net_name)}),
                    measured=round(narrowest.width, 3),
                    limit=round(required, 3),
                )
            )
    findings.sort(key=lambda f: (f.limit or 0) - (f.measured or 0), reverse=True)
    return findings


def _check_via_current(design: Design, rule: Rule) -> list[Finding]:
    """Netteki via'lar toplu olarak akimi tasiyabiliyor mu?

    Via basina kapasite TI SLVA959B Tablo 3-1'den gelir; IPC-2221'in namlu
    kesiti hesabindan ~2 kat muhafazakardir (bkz. dokuman 1.8).
    """
    net_rx = _net_matcher(rule)
    current_a = float(rule.spec.get("current_a", 0.0))
    if current_a <= 0:
        raise RuleError(f"{rule.id}: 'current_a' pozitif olmali")

    if not design.board.tracks and not design.board.vias:
        return []  # yonlendirilmemis

    findings: list[Finding] = []
    for net_name in design.net_names():
        if rule.net_ignored(net_name) or not net_rx.search(net_name):
            continue
        vias = [v for v in design.board.vias if v.net == net_name]
        if not vias:
            continue  # net katman degistirmiyorsa via kurali uygulanmaz
        capacity = sum(ipc2221.via_current_a(v.drill) for v in vias)
        if capacity + 1e-9 < current_a:
            findings.append(
                Finding(
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=(
                        f"{net_name}: {len(vias)} via toplam {capacity:.2f} A tasiyor, "
                        f"{current_a:g} A gerekiyor"
                    ),
                    refs=sorted({p.ref for p in design.pins_on_net(net_name)}),
                    measured=round(capacity, 2),
                    limit=current_a,
                )
            )
    return findings


def _check_keep_apart(design: Design, rule: Rule) -> list[Finding]:
    """Iki bilesen kumesi birbirinden EN AZ N mm uzak olmali.

    `proximity`nin tersi. Arastirmadaki sasirtici sayida kural bu bicimde:
    FB izi -> induktor >= 10 mm (ROHM 66AN015E), I2C pull-up -> sicaklik
    sensoru >= 10 mm (TI SNOA986A), CIN GND -> COUT GND >= 10 mm (ROHM),
    Ethernet on ucu -> diger yuksek hizli izler >= 7.62 mm (Microchip).

    Bu kural olmadan yerlestirici yalnizca "her seyi yaklastir" yonunde calisir
    ve bu kisitlari sessizce ihlal eder.
    """
    a_sel = Selector(rule.spec.get("a"))
    b_sel = Selector(rule.spec.get("b"))
    min_mm = float(rule.spec.get("min_distance_mm", 0.0))
    if min_mm <= 0:
        raise RuleError(f"{rule.id}: 'min_distance_mm' pozitif olmali")

    # Net filtresi kesinlik icin SART. "FB bolucu induktorden uzak dursun"
    # kurali `a: {kind: resistor}` ile yazilinca KARTTAKI HER DIRENCI her
    # induktorle karsilastiriyor. Gercek bir kartta (One-Air-Max) bu tek
    # basina 10 yanlis bulgu uretti; kastedilen yalnizca FB netindeki
    # direnclerdi.
    a_on = _refs_on_nets(design, rule, _rx(rule.spec.get("a_on_net")))
    b_on = _refs_on_nets(design, rule, _rx(rule.spec.get("b_on_net")))

    a_refs = [
        c.ref
        for c in design.board.components
        if a_sel.matches_component(design, c.ref) and (a_on is None or c.ref in a_on)
    ]
    b_refs = [
        c.ref
        for c in design.board.components
        if b_sel.matches_component(design, c.ref) and (b_on is None or c.ref in b_on)
    ]
    if not a_refs or not b_refs:
        return []

    findings: list[Finding] = []
    seen: set[tuple[str, str]] = set()
    for ref_a in a_refs:
        comp_a = design.component(ref_a)
        if comp_a is None:
            continue
        for ref_b in b_refs:
            if ref_a == ref_b:
                continue
            key = (ref_a, ref_b) if ref_a < ref_b else (ref_b, ref_a)
            if key in seen:
                continue
            seen.add(key)
            comp_b = design.component(ref_b)
            if comp_b is None:
                continue
            gap = math.hypot(comp_a.x - comp_b.x, comp_a.y - comp_b.y)
            if gap + 1e-9 < min_mm:
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        severity=rule.severity,
                        message=(
                            f"{ref_a} ile {ref_b} arasi {gap:.2f} mm, "
                            f"en az {min_mm:g} mm olmali"
                        ),
                        refs=[ref_a, ref_b],
                        measured=round(gap, 2),
                        limit=min_mm,
                    )
                )
    findings.sort(key=lambda f: f.measured or 0)
    return findings


def _pin_xy(design: Design, ref: str, net: str | None):
    """Bir bilesenin BELIRLI bir netteki pininin konumu.

    Bilesen merkezini kullanmak yaniltici olurdu: SOIC-16'da bir pin merkeze
    5 mm uzakta olabilir ve ROHM'un esikleri 3-4 mm mertebesinde.
    """
    if not net:
        return None
    for pin in design.pins_on_net(net):
        if pin.ref == ref and pin.placed:
            return (pin.x, pin.y)
    return None


def _pin_gap(design: Design, ref_a: str, ref_b: str, net: str | None) -> float | None:
    """Iki bilesenin AYNI netteki pinleri arasindaki mesafe."""
    a = _pin_xy(design, ref_a, net)
    b = _pin_xy(design, ref_b, net)
    if a is None or b is None:
        return None
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _check_buck_layout(design: Design, rule: Rule) -> list[Finding]:
    """Anahtarlamali regulator yerlesimi - ROHM 66AN015E kontrol listesi.

    Diger kurallardan farki: bilesenleri NET ADINDAN degil TOPOLOJIDEN buluyor
    (bkz. `pcbqa/subcircuit.py`). Gercek kartlarda FB neti
    "Net-(U2-FB{slash}VSET)" diye adlandirilmis olabiliyor ve hicbir ad deseni
    tutmuyor; ama IC'nin FB pini duruyor.

    Her esik istege baglidir. Verilmeyen esik olculmez; tespit edilemeyen rol
    de SESSIZCE atlanir - "bu kartta CIN bulunamadi" diye bulgu uretmek,
    tanimanin sinirlarini tasarimin hatasi gibi gosterirdi.

    TEK ISTISNA sicak dongudur: AYRIK tasarimda (SW dugumunde harici FET/diyot)
    roller cozulemezse `info` yazilir. Sebep, orada sessizligin YANILTICI
    olmasi - eskiden IC'nin dort pad'i olculuyor ve sonuc yanlis YONDE kucuk
    cikiyordu, yani sorunlu kart temiz gorunuyordu. Diger rollerde boyle bir
    risk yok: rol bulunamazsa hicbir sey olculmuyor.
    """
    limits = {
        "cin_max_mm": rule.spec.get("cin_max_mm"),
        "sw_max_mm": rule.spec.get("sw_max_mm"),
        "cout_max_mm": rule.spec.get("cout_max_mm"),
        "fb_max_mm": rule.spec.get("fb_max_mm"),
        "fb_inductor_min_mm": rule.spec.get("fb_inductor_min_mm"),
        "sw_area_max_mm2": rule.spec.get("sw_area_max_mm2"),
        "hot_loop_max_mm2": rule.spec.get("hot_loop_max_mm2"),
    }
    if all(v is None for v in limits.values()):
        raise RuleError(
            f"{rule.id}: en az bir esik verilmeli "
            f"({', '.join(sorted(limits))})"
        )

    findings: list[Finding] = []

    def add(msg: str, refs: list[str], measured: float, limit: float) -> None:
        findings.append(
            Finding(
                rule_id=rule.id,
                severity=rule.severity,
                message=msg,
                refs=refs,
                measured=round(measured, 2),
                limit=float(limit),
            )
        )

    for buck in subcircuit.find_buck_converters(design):
        tag = f"{buck.ic} ({buck.topology})"

        # Oncelik 1 - giris kondansatoru VIN pinine yakin
        limit = limits["cin_max_mm"]
        if limit is not None and buck.cin:
            gaps = [
                (g, ref)
                for ref in buck.cin
                if (g := _pin_gap(design, buck.ic, ref, buck.vin_net)) is not None
            ]
            if gaps:
                best, ref = min(gaps)
                if best > float(limit):
                    add(
                        f"{tag}: en yakin giris kondansatoru {ref} "
                        f"{best:.2f} mm uzakta (ROHM: <= {float(limit):g} mm)",
                        [buck.ic, ref],
                        best,
                        limit,
                    )

        # Oncelik 2 - IC'den induktore SW izi kisa
        limit = limits["sw_max_mm"]
        if limit is not None and buck.inductor:
            gap = _pin_gap(design, buck.ic, buck.inductor, buck.sw_net)
            if gap is not None and gap > float(limit):
                add(
                    f"{tag}: induktor {buck.inductor} SW pininden {gap:.2f} mm "
                    f"uzakta (ROHM: <= {float(limit):g} mm)",
                    [buck.ic, buck.inductor],
                    gap,
                    limit,
                )

        # Oncelik 3 - cikis kondansatoru induktore yakin
        limit = limits["cout_max_mm"]
        if limit is not None and buck.inductor and buck.cout:
            gaps = [
                (g, ref)
                for ref in buck.cout
                if (g := _pin_gap(design, buck.inductor, ref, buck.out_net)) is not None
            ]
            if gaps:
                best, ref = min(gaps)
                if best > float(limit):
                    add(
                        f"{tag}: en yakin cikis kondansatoru {ref} induktorden "
                        f"{best:.2f} mm uzakta (ROHM: <= {float(limit):g} mm)",
                        [buck.inductor, ref],
                        best,
                        limit,
                    )

        # #4-2 - FB bolucu FB pinine yakin
        limit = limits["fb_max_mm"]
        if limit is not None and buck.fb_resistors:
            gaps = [
                (g, ref)
                for ref in buck.fb_resistors
                if (g := _pin_gap(design, buck.ic, ref, buck.fb_net)) is not None
            ]
            if gaps:
                best, ref = min(gaps)
                if best > float(limit):
                    add(
                        f"{tag}: FB bolucu {ref} FB pininden {best:.2f} mm "
                        f"uzakta (ROHM: <= {float(limit):g} mm)",
                        [buck.ic, ref],
                        best,
                        limit,
                    )

        # #4-1 - FB bilesenleri induktorden UZAK
        limit = limits["fb_inductor_min_mm"]
        if limit is not None and buck.inductor and buck.fb_resistors:
            ind = design.component(buck.inductor)
            for ref in buck.fb_resistors:
                comp = design.component(ref)
                if ind is None or comp is None:
                    continue
                gap = math.hypot(ind.x - comp.x, ind.y - comp.y)
                if gap < float(limit):
                    add(
                        f"{tag}: FB bileseni {ref} induktore {gap:.2f} mm "
                        f"yakinlikta (ROHM: >= {float(limit):g} mm)",
                        [ref, buck.inductor],
                        gap,
                        limit,
                    )

        # Oncelik 2 - SW bakir alani
        limit = limits["sw_area_max_mm2"]
        if limit is not None:
            area = design.board.copper_area_mm2(buck.sw_net)
            if area > float(limit):
                add(
                    f"{tag}: SW bakir alani {area:.1f} mm2 "
                    f"(ROHM: <= {float(limit):g} mm2)",
                    [buck.ic],
                    area,
                    limit,
                )

        # TI AN-2155'in OLCTUGU buyukluk: 6 mm2 iyi, 18 mm2 kotu
        limit = limits["hot_loop_max_mm2"]
        if limit is not None:
            loop = subcircuit.hot_loop_polygon(design, buck)
            if loop is None and buck.external_switches:
                # Ayrik tasarim ama roller cozulemedi. Eskiden burada IC'nin
                # dort pad'i olculuyor ve sonuc yanlis YONDE kucuk cikiyordu -
                # sorunlu kart sessizce temiz gorunurdu. Artik olcemedigimizi
                # SOYLUYORUZ. `info` cunku bu bir ihlal degil kapsam disiligi;
                # ceza 0, ama raporda gorunur.
                eksik = "ust kol" if not buck.high_side else "alt kol"
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        severity="info",
                        message=(
                            f"{tag}: giris sicak dongusu OLCULEMEDI - SW "
                            f"dugumunde harici anahtarlama elemani var "
                            f"({', '.join(buck.external_switches)}) ama "
                            f"{eksik} topolojiden cozulemedi. Ayrik tasarimda "
                            f"dongu bu elemanlarin uzerinden geciyor; IC "
                            f"pad'lerinden hesaplanan alan yaniltici olurdu"
                        ),
                        refs=[buck.ic, *buck.external_switches],
                    )
                )
            elif loop is not None:
                poly, cap = loop
                area = geom.area(poly)
                if area > float(limit):
                    if buck.external_switches:
                        yol = f"{cap} + {buck.high_side}/{buck.low_side} uzerinden, ayrik"
                        refs = [buck.ic, cap, buck.high_side, buck.low_side]
                    else:
                        yol = f"{cap} uzerinden"
                        refs = [buck.ic, cap]
                    add(
                        f"{tag}: giris sicak dongusu {area:.1f} mm2 "
                        f"({yol}; TI AN-2155: <= {float(limit):g} mm2)",
                        refs,
                        area,
                        limit,
                    )

    return findings


def _refs_on_nets(design: Design, rule: Rule, pattern) -> set[str] | None:
    """Ada uyan netlere bagli bilesen referanslari. Desen yoksa None (=hepsi)."""
    if pattern is None:
        return None
    refs: set[str] = set()
    for net_name in design.net_names():
        if rule.net_ignored(net_name) or not pattern.search(net_name):
            continue
        refs.update(p.ref for p in design.pins_on_net(net_name))
    return refs


def _bound(raw, name: str, rule_id: str) -> float | None:
    """Sinir degeri: ya duz sayi (SI taban birimi) ya da "4k7" gibi bir metin."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    parsed = circuit.parse_value(str(raw))
    if parsed is None:
        raise RuleError(f"{rule_id}: '{name}' cozulemedi: {raw!r}")
    return parsed


def _check_component_value(design: Design, rule: Rule) -> list[Finding]:
    """Bilesen DEGERI hesaplanan araliga uyuyor mu?

    Sinir iki bicimde verilebilir:
      * dogrudan  -> `min: "1k"`, `max: "10k"`
      * hesaplanmis -> `check: i2c_pullup` + `params: {...}`

    Hesaplar `pcbqa/circuit.py` icinde ve hepsi kaynakli (NXP UM10204,
    Microchip AN826, Richtek AN033).

    IKI FARKLI "EKSIK" AYRILIR:
      * Bilesenin degeri COZULEMIYORSA sessizce atlanir. Deger alanina serbest
        metin yazmak yaygin; bunu hata saymak gurultu uretir.
      * Kuralin kendisi eksikse (params'ta gereken beyan yok) HATA verilir.
        O bir yapilandirma hatasidir, tasarim ozelligi degil - sessiz gecmek
        kurali gorunmez bicimde etkisiz birakirdi.
    """
    select = Selector(rule.spec.get("select"))
    on_net = _rx(rule.spec.get("on_net"))

    check_name = rule.spec.get("check")
    if check_name is not None:
        if check_name not in circuit.CHECKS:
            raise RuleError(
                f"{rule.id}: bilinmeyen 'check' {check_name!r}; "
                f"gecerli: {', '.join(sorted(circuit.CHECKS))}"
            )
        params = rule.spec.get("params") or {}
        try:
            value_range = circuit.CHECKS[check_name](params)
        except KeyError as exc:
            raise RuleError(
                f"{rule.id}: '{check_name}' hesabi icin {exc} beyani gerekiyor "
                "(params altinda verin)"
            ) from None
        except ValueError as exc:
            raise RuleError(f"{rule.id}: '{check_name}' hesabi basarisiz: {exc}") from None
    else:
        low = _bound(rule.spec.get("min"), "min", rule.id)
        high = _bound(rule.spec.get("max"), "max", rule.id)
        if low is None and high is None:
            raise RuleError(f"{rule.id}: 'min'/'max' ya da 'check' verilmeli")
        value_range = circuit.ValueRange(low=low, high=high, source="kuralda verildi")

    if value_range.low is not None and value_range.high is not None:
        if value_range.low > value_range.high:
            # Bu bazen GERCEK bir bulgudur: UM10204'e gore 400 pF fast-mode'da
            # duz direncle cozum YOKTUR. Kurali sessizce gecmek yerine soyle.
            return [
                Finding(
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=(
                        f"kabul araligi BOS: alt sinir {value_range.low:.4g} > "
                        f"ust sinir {value_range.high:.4g} ({value_range.source}). "
                        "Bu degerlerle cozum yok - devre topolojisi degismeli."
                    ),
                )
            ]

    # Netle sinirlandirma: bilesenin pinlerinden biri o nete bagli mi?
    allowed: set[str] | None = None
    if on_net is not None:
        allowed = set()
        for net_name in design.net_names():
            if rule.net_ignored(net_name) or not on_net.search(net_name):
                continue
            allowed.update(p.ref for p in design.pins_on_net(net_name))

    findings: list[Finding] = []
    for comp in design.board.components:
        if allowed is not None and comp.ref not in allowed:
            continue
        if not select.matches_component(design, comp.ref):
            continue
        value = circuit.parse_value(design.value_of(comp.ref))
        if value is None:
            continue  # deger okunamadi - sessiz
        if value_range.contains(value):
            continue

        if value_range.low is not None and value < value_range.low:
            limit, yon = value_range.low, "en az"
        else:
            limit, yon = value_range.high, "en fazla"
        findings.append(
            Finding(
                rule_id=rule.id,
                severity=rule.severity,
                message=(
                    f"{comp.ref} degeri {design.value_of(comp.ref)!r} "
                    f"({value:.4g}); {yon} {limit:.4g} olmali ({value_range.source})"
                ),
                refs=[comp.ref],
                measured=value,
                limit=limit,
            )
        )
    return findings


def _check_decoupling_count(design: Design, rule: Rule) -> list[Finding]:
    """IC'nin guc pini SAYISINA gore yeterli decoupling kondansatoru var mi.

    NEDEN AYRI BIR KURAL: `proximity` (hs-decoupling-mesafesi) MESAFE sorar -
    "kondansator yeterince yakin mi". ADET sormaz. 20 guc pinli bir FPGA'nin
    tek kondansatoru 2 mm otede olabilir ve mesafe kurali SUSAR; TI SPRABV2
    ise o kart icin 10 adet 0.1 uF ister. Iki kural birbirini tamamlar.

    SERAMIK PER IC, BULK PER NET - bu ayrim kaynagin kendisinden geliyor:
      * Seramik (0.1 uF) yuksek frekansta calisir ve ancak YAKINSA is gorur,
        yani her yongaya kendi kondansatoru gerekir. TI SBAA113'un 6.35 mm
        siniri icinde, IC BASINA sayilir.
      * Bulk (>= 15 uF) dusuk frekansta calisir, bir RAYI besler ve kart
        genelinde paylasilir. NET BASINA, mesafe siniri ARANMADAN sayilir -
        TI bulk icin mesafe VERMIYOR, uydurmuyoruz.
      Bulk'u IC basina saymak ayni ray uzerindeki uc yonga icin ayni eksigi uc
      kez bildirirdi ve tek pinli her yongaya ayrik bulk dayatirdi; ikisi de
      kaynagin soyledigi sey degil.
      Bulk ayrica `bulk_min_power_pins` (varsayilan 10) ALTINDA hic sorulmaz:
      TI'in birimi "~10 guc topu"dur ve ceil(n/10) tek pinde bile 1 bulk
      isterdi - o sayi kaynagin degil tavan fonksiyonunun urunu.

    UC BILINCLI YANLILIK, ucu de IYIMSER (yani gercek kart daha kotudur) -
    cunku bu projede yanlis alarm, kacirilan bulgudan pahalidir:
      1. Degeri COZULEMEYEN kondansator HER IKI kovaya da sayilir. KiCad deger
         alanlari duzensizdir: pic_programmer'da "22uF/25V" cozulemiyor ve o
         gercek bir bulk kondansatorudur. Yalnizca seramige saysaydik ayni
         parca bulk eksigi uydururdu - yani yanlilik yon degistirirdi.
      2. Bir kondansator birden fazla guc netinde sayilabilir (ayrik degil).
      3. Guc pini `pintype` ile bulunur; pintype yoksa bilesen SESSIZCE atlanir.

    OLCULMUS SINIR (1. yanliligin bedeli): jetson-agx-thor-baseboard deger
    alanina "C_100n_0402" yaziyor - bir 100 nF seramik, ama `parse_value`
    cozemiyor, yani bulk da sayiliyor. O kartta bulk denetimi seramiklerle
    doluyor ve etkisiz kaliyor. Bilincli kabul: alternatif, deger alanindan
    paket adi ayristirmaya calismakti ve yanlis tahmin gercek bir bulk
    kondansatorunu yok sayip UYDURMA bir eksik uretirdi.

    TOPRAK PINLERI `ignore_nets` ile disarida kalmali - toprak pinleri de
    `power_in` tasir ve sayilsalardi gereken adet iki katina cikardi. On
    ayarlarin defaults blogu GND/AGND/DGND'yi zaten eliyor.

    Beyan gerektirmez: guc pinleri de kondansator degerleri de tasarim
    dosyasindadir. `thermal`dan farki bu - orada beyan yoktu, burada var.
    """
    select = Selector(rule.spec.get("select"))
    pin_sel = Selector(rule.spec.get("pin") or {"pintype": "power_in"})
    partner_sel = Selector(rule.spec.get("partner") or {"kind": "capacitor"})
    max_mm = float(rule.spec.get("max_distance_mm", 6.35))
    bulk_min_uf = float(rule.spec.get("bulk_min_uf", 15.0))
    if bulk_min_uf <= 0:
        raise RuleError(f"{rule.id}: 'bulk_min_uf' pozitif olmali (gelen {bulk_min_uf})")
    check_bulk = bool(rule.spec.get("check_bulk", True))
    bulk_min_f = bulk_min_uf * 1e-6
    # TI'in bulk birimi "~10 guc topu". ceil(n/10) matematiksel olarak 1 guc
    # pininde bile 1 bulk ister - ama kaynak bunu SOYLEMIYOR; o sayi tavan
    # fonksiyonunun artifakti. Korpusta olculdu: esiksiz hali 19 kartin
    # 9'unda atesliyordu (%47), esikle 2'sinde. Kaynagin konustugu yerin
    # altina inmiyoruz - `thermal`in olculen egri disina cikmayi reddetmesiyle
    # ayni ilke.
    bulk_floor = int(rule.spec.get("bulk_min_power_pins", circuit.DECOUPLING_POWER_PINS_PER_BULK))

    def buckets(net_name: str, near_to: list[PinRef]) -> tuple[set[str], set[str]]:
        """(o nette 6.35 mm icindeki seramikler, nette HERHANGI bir yerdeki bulk)."""
        ceramic: set[str] = set()
        bulk: set[str] = set()
        for cand in design.pins_on_net(net_name):
            if not partner_sel.matches_component(design, cand.ref):
                continue
            farads = circuit.parse_value(design.value_of(cand.ref))
            if farads is None or farads >= bulk_min_f:
                bulk.add(cand.ref)
                if farads is not None:
                    continue  # kesin bulk; seramik kovasina girmez
            if not cand.placed:
                continue
            if any(
                (d := cand.distance_to(t)) is not None and d <= max_mm for t in near_to
            ):
                ceramic.add(cand.ref)
        return ceramic, bulk

    findings: list[Finding] = []
    net_pins: dict[str, int] = {}       # net -> o nete bagli guc pini sayisi
    net_refs: dict[str, set[str]] = {}  # net -> o nete bagli IC'ler

    for comp in design.board.components:
        if not select.matches_component(design, comp.ref):
            continue
        power_pins = [
            p
            for p in design.pins_of(comp.ref)
            if pin_sel.matches_pin(design, p)
            and p.placed
            and p.net
            and not rule.net_ignored(p.net)
        ]
        if not power_pins:
            continue  # guc pini isaretlenmemis - sessiz (yukaridaki yanlilik 3)

        ceramic: set[str] = set()
        for net_name in {p.net for p in power_pins}:
            on_net = [p for p in power_pins if p.net == net_name]
            net_pins[net_name] = net_pins.get(net_name, 0) + len(on_net)
            net_refs.setdefault(net_name, set()).add(comp.ref)
            ceramic |= buckets(net_name, on_net)[0]

        need_ceramic, _ = circuit.decoupling_counts(len(power_pins))
        if len(ceramic) < need_ceramic:
            nets_txt = ", ".join(sorted({p.net for p in power_pins}))
            findings.append(
                Finding(
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=(
                        f"{comp.ref}: {len(power_pins)} guc pini ({nets_txt}) icin "
                        f"{need_ceramic} adet seramik decoupling gerekiyor, "
                        f"{max_mm:g} mm icinde {len(ceramic)} adet var "
                        f"(TI SPRABV2 6: 2 guc pinine 1 x 0.1 uF)"
                    ),
                    refs=[comp.ref],
                    measured=len(ceramic),
                    limit=need_ceramic,
                )
            )

    if check_bulk:
        for net_name in sorted(net_pins):
            if net_pins[net_name] < bulk_floor:
                continue  # kaynagin birimi altinda - sessiz, uydurmuyoruz
            _, need_bulk = circuit.decoupling_counts(net_pins[net_name])
            have = len(buckets(net_name, [])[1])
            if have >= need_bulk:
                continue
            refs = sorted(net_refs[net_name])
            findings.append(
                Finding(
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=(
                        f"{net_name}: rayda {net_pins[net_name]} IC guc pini var "
                        f"({', '.join(refs)}), {need_bulk} adet bulk "
                        f"(>= {bulk_min_uf:g} uF) gerekiyor, {have} adet bulundu "
                        f"(TI SPRABV2 6: ~10 guc pinine 1 x bulk)"
                    ),
                    refs=refs,
                    measured=have,
                    limit=need_bulk,
                )
            )

    findings.sort(key=lambda f: (f.limit or 0) - (f.measured or 0), reverse=True)
    return findings


def _check_thermal(design: Design, rule: Rule) -> list[Finding]:
    """Termal bakir alanindan jonksiyon sicakligini hesaplar (Richtek AN044).

    NEDEN ESIK DEGIL HESAP: sabit bir "en az N mm2" esigi savunulamaz. Ayni
    1 W'lik regulator 25 C ortamda ~150 mm2 ile, 70 C ortamda ~1885 mm2 ile
    ayni jonksiyon sicakligina ulasir. Bu yuzden kural alan degil SICAKLIK
    olcer: measured = Tj, limit = tj_max_c.

    Termal pad'in secimi: aksi belirtilmedikce bilesenin EN BUYUK pad'i.
    SOT-223, DPAK, D2PAK gibi paketlerde isiyi tasiyan tab zaten acik ara en
    buyuk pad'dir. `thermal_pin` ile acikca verilebilir.

    UC AYRI "EKSIK" AYRILIR:
      * Beyan eksikse (power_w / ambient_c / tj_max_c) HATA - yapilandirma
        hatasidir, sessiz gecmek kurali gorunmez bicimde etkisiz birakir.
      * Bilesen eslesmiyorsa, termal pad'in neti yoksa ya da o nette olculebilir
        bakir yoksa SESSIZ - dokum yapilmamis kartta yanlis alarm uretmemeli.
      * Paketin alan bagimliligi olculmemisse (SOT-23, SO-8, DFN-8) sicaklik
        yine hesaplanir ama bulgu "bakir ekleyin" DEMEZ; o oneriyi destekleyen
        olcum yok.

    UC BILINCLI YANLILIK, ucu de IYIMSER yonde (yani gercek kart daha
    sicaktir):
      1. `copper_area_mm2` ustuste binen bakiri iki kez sayar, yani alani fazla
         tahmin eder.
      2. Hesap tek isi kaynagi varsayar; komsu bilesenlerin isitmasi girmez.
      3. Egri tek katli JESD51 kartinda olculdu; cok katli kartta ve termal
         via'lar varsa gercek theta_JA daha iyi olabilir.
    Bu yuzden bulgu bir ALT SINIRDIR ve bulgu metninde boyle yazar.
    """
    select = Selector(rule.spec.get("select"))

    package = rule.spec.get("package")
    if package is None:
        raise RuleError(
            f"{rule.id}: 'package' verilmeli; gecerli: "
            f"{', '.join(sorted(thermal.THETA_JA_CURVES))}"
        )
    package = str(package).lower()
    if package not in thermal.THETA_JA_CURVES:
        raise RuleError(
            f"{rule.id}: '{package}' icin olculmus theta_JA verisi yok; gecerli: "
            f"{', '.join(sorted(thermal.THETA_JA_CURVES))}"
        )

    missing = [k for k in ("power_w", "ambient_c", "tj_max_c") if rule.spec.get(k) is None]
    if missing:
        raise RuleError(
            f"{rule.id}: {', '.join(missing)} beyan edilmeli - "
            "bu degerler tasarim dosyasinda YOKTUR, varsayilani uydurulmaz"
        )
    power_w = float(rule.spec["power_w"])
    ambient_c = float(rule.spec["ambient_c"])
    tj_max_c = float(rule.spec["tj_max_c"])
    if power_w <= 0:
        raise RuleError(f"{rule.id}: 'power_w' pozitif olmali (gelen {power_w})")
    if tj_max_c <= ambient_c:
        raise RuleError(
            f"{rule.id}: 'tj_max_c' ({tj_max_c:g}) ortam sicakligindan "
            f"({ambient_c:g}) buyuk olmali - aksi halde butce negatif"
        )

    thermal_pin = rule.spec.get("thermal_pin")
    thermal_pin = str(thermal_pin) if thermal_pin is not None else None
    sources = tuple(rule.spec.get("sources") or ("zone", "track", "pad"))
    unknown = set(sources) - {"zone", "track", "pad"}
    if unknown:
        raise RuleError(f"{rule.id}: bilinmeyen 'sources' degeri: {sorted(unknown)}")
    layer_spec = rule.spec.get("layer")

    source_note = thermal.SOURCES.get(package, package)
    findings: list[Finding] = []
    # `thermal_pin` yazim hatasi kurali SESSIZCE etkisiz birakmasin (bkz.
    # docstring): secilen hicbir bilesende o pad yoksa bu bir yapilandirma
    # hatasidir. Bir bilesende bulunup digerinde bulunmamasi normaldir -
    # heterojen bir secici (or. ^U) 2 pinli bir parcayi da kapsayabilir.
    selected_any = False
    thermal_pin_seen = False
    for comp in design.board.components:
        if not select.matches_component(design, comp.ref):
            continue
        selected_any = True

        if thermal_pin is not None:
            pads = [p for p in comp.pads if p.number == thermal_pin or p.function == thermal_pin]
            if pads:
                thermal_pin_seen = True
        else:
            # En buyuk pad = tab. Esitlik durumunda pad numarasi belirleyici
            # olsun ki sonuc kartin okunma sirasindan bagimsiz olsun.
            pads = sorted(comp.pads, key=lambda p: (-p.area_mm2, p.number))[:1]
        pad = next((p for p in pads if p.net), None)
        if pad is None:
            continue  # termal pad bulunamadi ya da nete bagli degil - sessiz
        if rule.net_ignored(pad.net):
            continue

        # Katman: pad tek bakir katmandaysa ONUN katmani. Richtek egrisi tek
        # katli kartta olculdu; tum katmanlari toplamak, isinin via'sizca
        # yayildigini varsaymak olurdu.
        layer = layer_spec
        if layer is None and len(pad.copper_layers) == 1:
            layer = pad.copper_layers[0]

        area = design.board.copper_area_mm2(pad.net, layer=layer, sources=sources)
        if area <= 0:
            continue  # dokum yapilmamis / yonlendirilmemis kart - sessiz

        theta = thermal.theta_ja_c_per_w(package, area)
        tj = thermal.junction_temp_c(package, area, power_w, ambient_c)
        if tj <= tj_max_c:
            continue

        hint = ""
        if thermal.is_area_dependent(package):
            need = thermal.required_area_mm2(package, power_w, ambient_c, tj_max_c)
            if need is None:
                hint = (
                    "; olculen en buyuk alanda bile yetmiyor - cozum bakir degil "
                    "paket/soguturucu"
                )
            else:
                hint = f"; gereken alan ~{need:.0f} mm2"

        findings.append(
            Finding(
                rule_id=rule.id,
                severity=rule.severity,
                message=(
                    f"{comp.ref} ({package}, pad {pad.number} -> {pad.net}): "
                    f"termal bakir {area:.0f} mm2 -> theta_JA ~{theta:.0f} C/W; "
                    f"{power_w:g} W ve {ambient_c:g} C ortamda Tj EN AZ {tj:.0f} C, "
                    f"sinir {tj_max_c:g} C ({source_note}){hint}"
                ),
                refs=[comp.ref],
                measured=round(tj, 1),
                limit=tj_max_c,
            )
        )
    if thermal_pin is not None and selected_any and not thermal_pin_seen:
        raise RuleError(
            f"{rule.id}: 'thermal_pin' {thermal_pin!r} secilen hicbir bilesende "
            "yok - pad numarasi ya da pin adi olmali (or. '2'). Sessiz gecmek "
            "kurali gorunmez bicimde etkisiz birakirdi"
        )
    findings.sort(key=lambda f: (f.measured or 0) - (f.limit or 0), reverse=True)
    return findings


def _check_copper_area(design: Design, rule: Rule) -> list[Finding]:
    """Bir netin bakir alani belirtilen araliktan cikmamali.

    Iki kaynakli kurali birden karsilar:
      * SW bakir alani <= 100 mm2 (ROHM 66AN015E Oncelik 2) - EMI icin ust sinir
      * termal bakir alani >= X (Richtek AN044 SOT-223 olcum egrisi) - alt sinir

    Zone okunmayan/dokum yapilmamis kartlarda alan yalnizca iz ve pad'lerden
    gelir; bu dogru ama eksiktir. `min_mm2` kullanan kural bu yuzden dokum
    OLMAYAN kartlarda yanlis alarm verebilir - kart doldurulmus olmali.
    """
    net_rx = _net_matcher(rule)
    max_mm2 = rule.spec.get("max_mm2")
    min_mm2 = rule.spec.get("min_mm2")
    if max_mm2 is None and min_mm2 is None:
        raise RuleError(f"{rule.id}: 'max_mm2' ya da 'min_mm2' verilmeli")
    max_mm2 = float(max_mm2) if max_mm2 is not None else None
    min_mm2 = float(min_mm2) if min_mm2 is not None else None
    if max_mm2 is not None and min_mm2 is not None and min_mm2 > max_mm2:
        raise RuleError(f"{rule.id}: 'min_mm2' > 'max_mm2' - bu aralik bos")

    layer = rule.spec.get("layer")
    sources = tuple(rule.spec.get("sources") or ("zone", "track", "pad"))
    unknown = set(sources) - {"zone", "track", "pad"}
    if unknown:
        raise RuleError(f"{rule.id}: bilinmeyen 'sources' degeri: {sorted(unknown)}")

    findings: list[Finding] = []
    for net_name in design.net_names():
        if rule.net_ignored(net_name) or not net_rx.search(net_name):
            continue
        area = design.board.copper_area_mm2(net_name, layer=layer, sources=sources)
        if area <= 0:
            continue  # bu nette olculebilir bakir yok - sessiz
        refs = sorted({p.ref for p in design.pins_on_net(net_name)})
        where = f" ({layer})" if layer else ""
        if max_mm2 is not None and area > max_mm2:
            findings.append(
                Finding(
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=(
                        f"{net_name}{where}: bakir alani {area:.1f} mm2, "
                        f"en fazla {max_mm2:g} mm2 olmali"
                    ),
                    refs=refs,
                    measured=round(area, 2),
                    limit=max_mm2,
                )
            )
        elif min_mm2 is not None and area < min_mm2:
            findings.append(
                Finding(
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=(
                        f"{net_name}{where}: bakir alani {area:.1f} mm2, "
                        f"en az {min_mm2:g} mm2 olmali"
                    ),
                    refs=refs,
                    measured=round(area, 2),
                    limit=min_mm2,
                )
            )
    findings.sort(key=lambda f: abs((f.measured or 0) - (f.limit or 0)), reverse=True)
    return findings


def _copper_items_by_net(design: Design) -> dict[str, list]:
    """TUM bakir parcalarini tek gecisle net'e gore gruplar.

    Her parca (noktalar, sisme_yaricapi, katmanlar) uclusudur ve uc sekil de
    ayni ifadeyle olculur:  aciklik = shape_distance(A, B) - rA - rB

      * iz  -> merkez cizgisi (2 nokta) + yarim genislik, kendi katmani
      * via -> tek nokta + yaricap, katman None (= hepsi). Delikli via tum
               katmanlari deler; kor/gomulu via nadir ve bu varsayim onlarda
               MUHAFAZAKAR yonde (fazladan karsilastirma).
      * pad -> sekline gore (bkz. Pad.copper_shape): daire -> nokta + r,
               oval -> parca + r, dortgen -> 4 kose

    Pad'i once cevreleyen daireye, sonra kareye yuvarlamak gercek kartta yanlis
    alarm uretiyordu; her iki yuvarlama da olculen acikligi bilesen ayak izi
    mertebesinde (0.5 mm) kuculttugu icin saglam kartlar ihlalli gorunuyordu.
    Daire ve oval artik TAM modelleniyor.

    Tek gecis olmasinin nedeni: onceki hal net BASINA cagriliyor ve her cagrida
    butun izleri, via'lari, pad'leri bastan tariyordu - 33 netli bir kartta 33
    kat gereksiz is.
    """
    out: dict[str, list] = {}
    for track in design.board.tracks:
        if track.net:
            out.setdefault(track.net, []).append(
                (
                    [(track.x1, track.y1), (track.x2, track.y2)],
                    track.width / 2.0,
                    frozenset({track.layer}),
                )
            )
    for via in design.board.vias:
        if via.net:
            out.setdefault(via.net, []).append(([(via.x, via.y)], via.size / 2.0, None))
    for comp in design.board.components:
        for pad in comp.pads:
            if not pad.net:
                continue
            pts, radius = pad.copper_shape()
            layers = None if pad.on_all_layers else frozenset(pad.copper_layers)
            out.setdefault(pad.net, []).append((pts, radius, layers))
    return out


def _layers_can_touch(a, b) -> bool:
    """Iki bakir parcasi ayni katmanda bulunabilir mi? None = tum katmanlar."""
    if a is None or b is None:
        return True
    return bool(a & b)


def _check_clearance_voltage(design: Design, rule: Rule) -> list[Finding]:
    """Gerilim farkina gore minimum bakir acikligi (IPC-2221B Tablo 6-1).

    `voltages` ile net adi desenlerine gerilim atanir; olculen aciklik, iki net
    arasindaki gerilim FARKI icin gereken degerle karsilastirilir.

    SINIRLAR (bilincli, gizlenmiyor):
      - Daire ve oval pad'ler tam, roundrect/custom pad'ler dortgen olarak
        alinir -> son ikisinde olcum bir miktar muhafazakar kalir.
      - Pad'ler kendi bakir katmanlarinda karsilastirilir (delikli pad tum
        katmanlarda). Bu ayrim sart: kart kenari konnektorlerinde on ve arka
        yuzdeki pad'ler ayni x/y'dedir ve farkli netlere baglidir.
      - Via'lar tum katmanlarda varsayilir (kor/gomulu via'da muhafazakar).
      - Poligon dokum (zone) okunmaz -> GND dokumu bu olcume girmez.
      - Bu CLEARANCE'tir, CREEPAGE degil. Sebeke izolasyonuna yetmez; kural
        250 V ustunde bulgu metnine ayrica uyari koyar.
    """
    voltages_spec = rule.spec.get("voltages") or {}
    if not voltages_spec:
        raise RuleError(f"{rule.id}: 'voltages' bos olamaz (net deseni -> gerilim)")
    klass = rule.spec.get("class", "B2")
    default_v = float(rule.spec.get("default_voltage", 0.0))

    compiled = [(_rx(pattern), float(v)) for pattern, v in voltages_spec.items()]

    def voltage_of(net_name: str) -> float:
        for pattern, volts in compiled:
            if pattern and pattern.search(net_name):
                return volts
        return default_v

    net_names = [n for n in design.net_names() if not rule.net_ignored(n)]
    declared = {n: voltage_of(n) for n in net_names}
    # Yalnizca gerilim BEYAN EDILMIS netlerden basariz; aksi halde her net
    # ciftini denemek buyuk kartlarda karesel patlar.
    sources = [n for n in net_names if declared[n] != default_v]
    if not sources:
        return []

    grouped = _copper_items_by_net(design)
    copper = {n: grouped.get(n, []) for n in net_names}

    # SINIR KUTUSU ON FILTRESI - performans icin sart, dogruluk icin degil.
    #
    # Olculdu (pic_programmer, 370 iz + 247 pad): filtresiz bu kural TEK BASINA
    # 459 ms suruyordu, geri kalan 21 kural toplam 9 ms. Yerlestirici hakemi
    # her hamlede cagirdigi icin 8 s'lik butce ~900 denemeden ~17'ye dusuyor ve
    # HICBIR bilesen oynamiyordu.
    #
    # Kutular her parcanin sisme yaricapi kadar buyutulur; iki kutu arasindaki
    # mesafe gereken acikliktan buyukse gercek sekil mesafesi de buyuktur, yani
    # atlamak GUVENLIDIR (kutu her zaman sekli icerir).
    boxes: dict[str, list[tuple[float, float, float, float]]] = {}
    for name, items in copper.items():
        rows = []
        for pts, radius, _layers in items:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            rows.append(
                (min(xs) - radius, min(ys) - radius, max(xs) + radius, max(ys) + radius)
            )
        boxes[name] = rows

    def box_gap(a, b) -> float:
        """Iki eksen-hizali kutu arasindaki en kisa mesafe (cakisiyorsa 0)."""
        dx = max(a[0] - b[2], b[0] - a[2], 0.0)
        dy = max(a[1] - b[3], b[1] - a[3], 0.0)
        return math.hypot(dx, dy)

    findings: list[Finding] = []
    checked: set[tuple[str, str]] = set()

    for net_a in sources:
        for net_b in net_names:
            if net_a == net_b:
                continue
            key = (net_a, net_b) if net_a < net_b else (net_b, net_a)
            if key in checked:
                continue
            checked.add(key)

            delta_v = abs(declared[net_a] - declared[net_b])
            if delta_v <= 0:
                continue
            required = ipc2221.clearance_mm(delta_v, klass)

            best = math.inf
            items_a = copper[net_a]
            items_b = copper[net_b]
            boxes_a = boxes[net_a]
            boxes_b = boxes[net_b]
            for i, (pts_a, r1, layers_a) in enumerate(items_a):
                box_a = boxes_a[i]
                for j, (pts_b, r2, layers_b) in enumerate(items_b):
                    if not _layers_can_touch(layers_a, layers_b):
                        continue
                    # Kaba eleme: kutular zaten yeterince uzaksa sekil mesafesi
                    # de uzaktir. Simdiye kadarki en iyiyi de asamayacaksa bak.
                    coarse = box_gap(box_a, boxes_b[j])
                    if coarse >= required and coarse >= best:
                        continue
                    gap = geom.shape_distance(pts_a, pts_b) - r1 - r2
                    if gap < best:
                        best = gap
                        if best <= 0:
                            break
                if best <= 0:
                    break
            if best is math.inf:
                continue

            if best + 1e-9 < required:
                note = ""
                if delta_v > 250:
                    note = " (DIKKAT: sebeke gerilimi - creepage ayrica gerekir)"
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        severity=rule.severity,
                        message=(
                            f"{net_a} <-> {net_b}: aciklik {best:.3f} mm, "
                            f"{delta_v:g} V icin {required:g} mm gerekiyor "
                            f"(sinif {klass}){note}"
                        ),
                        measured=round(best, 3),
                        limit=required,
                    )
                )
    findings.sort(key=lambda f: (f.limit or 0) - (f.measured or 0), reverse=True)
    return findings


CHECKS: dict[str, Callable[[Design, Rule], list[Finding]]] = {
    # baglanti niyeti + guc butunlugu
    "proximity": _check_proximity,
    "require_on_net": _check_require_on_net,
    "same_net": _check_same_net,
    # sinyal butunlugu
    "net_length": _check_net_length,
    "length_match": _check_length_match,
    # yerlesim kisitlari
    "keep_apart": _check_keep_apart,
    # uretilebilirlik
    "courtyard_overlap": _check_courtyard_overlap,
    "edge_clearance": _check_edge_clearance,
    # bakir: akim tasima ve gerilim acikligi (yalnizca yonlendirilmis kartlarda)
    "trace_width": _check_trace_width,
    "via_current": _check_via_current,
    "clearance_voltage": _check_clearance_voltage,
    "copper_area": _check_copper_area,
    # termal: bakir alani -> theta_JA -> jonksiyon sicakligi
    "thermal": _check_thermal,
    # devre dogrulugu (bilesen DEGERI)
    "component_value": _check_component_value,
    # decoupling ADEDI (mesafe degil): TI SPRABV2
    "decoupling_count": _check_decoupling_count,
    # alt-devre farkindalikli yerlesim (net adina DEGIL topolojiye bakar)
    "buck_layout": _check_buck_layout,
}


# ---------------------------------------------------------------------- yukleme


def load_rules(path: str | Path) -> list[Rule]:
    """YAML kural dosyasini okur ve dogrular.

    `include:` ile baska kural dosyalari dahil edilebilir (yollar dahil eden
    dosyaya GORE cozulur). On ayar kutuphanesi (pcbqa/presets/) boylece
    kopyala-yapistir olmadan kullanilir:

        include:
          - presets/buck.rules.yaml
        rules:
          - id: kendi-kuralim
            ...

    Dahil edilen kurallar once gelir; ayni `id` iki kez taniminca hata verir -
    bu bilincli, cunku sessizce ezilen bir kural fark edilmeyen bir bosluktur.
    """
    return _load_rules(Path(path), seen_files=set(), seen_ids=set())


def _load_rules(path: Path, seen_files: set[Path], seen_ids: set[str]) -> list[Rule]:
    resolved = path.resolve()
    if resolved in seen_files:
        raise RuleError(f"dairesel include: {path}")
    seen_files.add(resolved)

    try:
        data, _ = load_config(path)
    except ConfigError as exc:
        raise RuleError(f"kural dosyasi okunamadi: {exc}") from exc

    defaults = data.get("defaults") or {}
    default_severity = defaults.get("severity", "warning")
    global_ignore = list(defaults.get("ignore_nets") or [])

    rules: list[Rule] = []
    seen = seen_ids

    includes = data.get("include") or []
    if isinstance(includes, str):
        includes = [includes]
    for item in includes:
        rules.extend(_load_rules(path.parent / str(item), seen_files, seen))

    for raw in data.get("rules") or []:
        if not isinstance(raw, dict):
            raise RuleError(f"kural bir sozluk olmali, gelen: {type(raw).__name__}")

        rule_id = raw.get("id")
        if not rule_id:
            raise RuleError("her kuralin bir 'id' alani olmali")
        if rule_id in seen:
            raise RuleError(f"tekrar eden kural id: {rule_id}")
        seen.add(rule_id)

        rtype = raw.get("type")
        if rtype not in CHECKS:
            raise RuleError(
                f"{rule_id}: bilinmeyen kural tipi {rtype!r}. "
                f"Gecerli tipler: {', '.join(sorted(CHECKS))}"
            )

        severity = raw.get("severity", default_severity)
        if severity not in SEVERITIES:
            raise RuleError(f"{rule_id}: gecersiz severity {severity!r}")

        spec = {
            k: v
            for k, v in raw.items()
            if k
            not in {
                "id",
                "type",
                "severity",
                "description",
                "ignore_nets",
                "max_findings",
                "weight",
                "scale",
                "scale_max",
            }
        }

        weight = raw.get("weight")
        if weight is not None:
            try:
                weight = float(weight)
            except (TypeError, ValueError):
                raise RuleError(f"{rule_id}: 'weight' sayi olmali, gelen: {weight!r}") from None
            if weight < 0:
                raise RuleError(f"{rule_id}: 'weight' negatif olamaz (gelen {weight})")

        scale = raw.get("scale", False)
        if not isinstance(scale, bool):
            raise RuleError(f"{rule_id}: 'scale' true/false olmali, gelen: {scale!r}")

        scale_max = raw.get("scale_max", DEFAULT_SCALE_MAX)
        try:
            scale_max = float(scale_max)
        except (TypeError, ValueError):
            raise RuleError(
                f"{rule_id}: 'scale_max' sayi olmali, gelen: {scale_max!r}"
            ) from None
        if scale_max < 1.0:
            raise RuleError(
                f"{rule_id}: 'scale_max' 1.0'dan kucuk olamaz (gelen {scale_max}); "
                "carpan cezayi azaltmak icin degil, buyutmek icindir"
            )

        rules.append(
            Rule(
                id=rule_id,
                type=rtype,
                severity=severity,
                description=raw.get("description", ""),
                spec=spec,
                ignore_nets=global_ignore + list(raw.get("ignore_nets") or []),
                max_findings=int(raw.get("max_findings", DEFAULT_MAX_FINDINGS)),
                weight=weight,
                scale=scale,
                scale_max=scale_max,
            )
        )

    if not rules:
        raise RuleError(f"{path}: hic kural tanimlanmamis")
    return rules


def run_rules(design: Design, rules: list[Rule]) -> list[Finding]:
    """Tum kurallari calistirir ve bulgulari dondurur."""
    findings: list[Finding] = []

    for rule in rules:
        produced = CHECKS[rule.type](design, rule)
        for finding in produced:
            finding.rule_type = rule.type
            finding.weight = rule.weight
            finding.scale_max = rule.scale_max if rule.scale else None
        if len(produced) > rule.max_findings:
            extra = len(produced) - rule.max_findings
            produced = produced[: rule.max_findings]
            produced.append(
                Finding(
                    rule_id=rule.id,
                    severity="info",
                    message=f"...ve {extra} benzer bulgu daha (max_findings ile sinirlandi)",
                )
            )
        findings.extend(produced)

    order = {s: i for i, s in enumerate(SEVERITIES)}
    findings.sort(key=lambda f: (order.get(f.severity, 9), f.rule_id))
    return findings


# --------------------------------------------------------------------------
# Sematik kontrolleri (Asama 4a)
#
# YAML kural motorundan ayridir: bunlar sematigin YAPISAL saglamligini
# olcer, tasarimcinin kendi esiklerini degil. `Schematic` bizim kendi veri
# modelimizdir - bu fonksiyon da KiCad'i bilmez.
# --------------------------------------------------------------------------

# Sematik izgarasi disindaki sembol, tel ucuyla ortusmeyebilir -> sessiz kopukluk
SCH_GRID_MM = 1.27


# Cakisma testinde kullanilan tolerans (mm). Sematikte semboller 1.27 mm
# izgarasinda cogu zaman TAM kenar kenara durur; toleranssiz bir yuklem bu
# durumu kayan nokta gurultusune birakir ve ayni yerlesim bir hesapta
# "cakisiyor", digerinde "cakismiyor" cikar. Olculdu: 4e-14 mm'lik bir fark
# jetson-agx-thor-baseboard/SoM_IO sayfasinda skoru 100'den 97.4'e dusuruyordu.
OVERLAP_EPS = 1e-6


def _boxes_overlap(a, b, margin: float = 0.0) -> bool:
    """Iki sinir kutusu ust uste biniyor mu? Tam temas cakisma SAYILMAZ."""
    gap = margin - OVERLAP_EPS
    return not (
        a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1]
    )


def run_schematic_checks(schematic) -> list[Finding]:
    """Sematigin yapisal saglamligini kontrol eder.

    `schematic` bir `pcbqa.schematic.Schematic` ornegidir.
    """
    findings: list[Finding] = []

    if schematic.stray_parens:
        findings.append(
            Finding(
                rule_id="sematik-bozuk-dosya",
                severity="error",
                message=(
                    f"sematik dosyasinda {schematic.stray_parens} bozuk parantez var; "
                    "okuma toleransli yapildi ama dosya kusurlu"
                ),
                source="pcbqa-sch",
                measured=float(schematic.stray_parens),
                limit=0.0,
            )
        )

    for sheet in schematic.sheets:
        if sheet.missing:
            findings.append(
                Finding(
                    rule_id="sematik-eksik-sayfa",
                    severity="error",
                    message=(
                        f"'{sheet.name}' alt sayfasinin dosyasi bulunamadi: {sheet.filename}"
                    ),
                    source="pcbqa-sch",
                )
            )

    off_grid = [s for s in schematic.real_symbols if not s.on_grid(SCH_GRID_MM)]
    for sym in off_grid:
        findings.append(
            Finding(
                rule_id="sematik-izgara-disi",
                severity="warning",
                message=(
                    f"{sym.ref} {SCH_GRID_MM} mm izgarasinin disinda "
                    f"({sym.x:g}, {sym.y:g}); tel uclari pine denk gelmeyebilir"
                ),
                source="pcbqa-sch",
                refs=[sym.ref],
            )
        )

    missing_fp = [
        s for s in schematic.real_symbols if not s.footprint.strip() and not s.dnp
    ]
    for sym in missing_fp:
        findings.append(
            Finding(
                rule_id="sematik-footprint-yok",
                severity="warning",
                message=f"{sym.ref} ({sym.value}) icin footprint atanmamis; PCB'ye aktarilamaz",
                source="pcbqa-sch",
                refs=[sym.ref],
            )
        )

    # Ayni sayfada govdesi cakisan semboller
    by_sheet: dict[str, list] = {}
    for sym in schematic.real_symbols:
        if sym.bbox:
            by_sheet.setdefault(sym.sheet_path, []).append(sym)
    for sheet_path, symbols in by_sheet.items():
        for i, a in enumerate(symbols):
            for b in symbols[i + 1 :]:
                if _boxes_overlap(a.bbox, b.bbox):
                    findings.append(
                        Finding(
                            rule_id="sematik-cakisan-sembol",
                            severity="warning",
                            message=(
                                f"{a.ref} ve {b.ref} sembol govdeleri cakisiyor"
                                f"{'' if sheet_path == '/' else f' (sayfa {sheet_path})'}"
                            ),
                            source="pcbqa-sch",
                            refs=[a.ref, b.ref],
                        )
                    )

    order = {s: i for i, s in enumerate(SEVERITIES)}
    findings.sort(key=lambda f: (order.get(f.severity, 9), f.rule_id))
    return findings
