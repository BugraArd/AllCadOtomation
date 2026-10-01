"""Dal akimina gore iz analizi ve yonlendirme girdisi.

Iki soru, iki asama - SIRASI ONEMLI:

1. YONLENDIRMEDEN ONCE (`yonlendirme_girdisi`): yerlesim ve kisitlar.
   Otomatik yol cizmenin girdisi yalnizca iki padin konumu olmamali. Once
   kritik baglantilar (dekuplaj, regulator kondansatoru) yerlesimde
   saglanmali, uretim sinirlari bilinmeli, sonra her agin DAL akimlari
   ve bu akimlarin istedigi genislik/uzunluk butcesi cikarilmali.

2. YONLENDIRMEDEN SONRA (`iz_analizi`): gercek bakir uzerinde dugum analizi.
   Bir aga TEK akim atanmaz. Agin bakiri (iz parcalari, vialar, padler) bir
   direnc agina cevrilir, yuklerin cektigi akim pinlerine, kaynagin verdigi
   akim kaynak pinine yazilir ve Kirchhoff akim yasasi cozulur. Boylece ana
   kol toplam yuku, her dal yalnizca kendi yukunu tasir.

Temel hesaplar:
    R  = rho * L / (w * t)       iz parcasi direnci
    dV = I * R                   gerilim dusumu
    P  = I^2 * R                 kayip

Kullanilan girdiler: surekli/RMS akim, tepe akim + darbe suresi, bakir
kalinligi, ic/dis katman, izin verilen sicaklik artisi, iz uzunlugu ve izin
verilen gerilim dusumu, pad cikislari, darbogazlar, vialar, konnektorler.

Kaynaklar:
  rho = 1.7241e-8 ohm.m  IEC 60028 (tavlanmis bakir, 20 C)
  alfa = 0.00393 1/C     bakirin direnc sicaklik katsayisi (IEC 60028)
  1 oz = 35 um           ipc2221.MIL_PER_OZ ile ayni
  genislik <-> akim      IPC-2221B (ipc2221.trace_width_mm)
  via akimi              TI SLVA959B (ipc2221.via_current_a)
  darbe                  Onderdonk erime denklemi (kisa sureli, adyabatik)
Muhendislik secimleri:
  DARBE_PAYI = 0.5       tepe akim, Onderdonk erime akiminin yarisini asmasin
  YAKINLIK_MM            ipc2221.DECOUPLING_MAX_MM (TI SBAA113, 6.35 mm)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from . import ipc2221
from .devre.graf import BilesenDugumu, DevreGrafi
from .devre.kosullar import ag_anahtari
from .pcb import Board, Pad

RHO_CU = 1.7241e-8          # ohm*m, IEC 60028, 20 C
ALFA_CU = 0.00393           # 1/C
MM_PER_OZ = 0.035
ONDERDONK_TM_C = 1083.0     # bakirin erime noktasi
CMIL_MM2 = 5.067e-4         # 1 dairesel mil = 5.067e-4 mm2
DARBE_PAYI = 0.5
_EPS = 1e-3


# --------------------------------------------------------------------------
# Temel hesaplar
# --------------------------------------------------------------------------


def iz_direnci_ohm(uzunluk_mm: float, genislik_mm: float, kalinlik_mm: float,
                   sicaklik_c: float = 20.0) -> float:
    """R = rho L / (w t), sicaklikla duzeltilmis."""
    if genislik_mm <= 0 or kalinlik_mm <= 0:
        raise ValueError("genislik ve kalinlik pozitif olmali")
    rho = RHO_CU * (1 + ALFA_CU * (sicaklik_c - 20.0))
    return rho * (uzunluk_mm * 1e-3) / ((genislik_mm * 1e-3) * (kalinlik_mm * 1e-3))


def via_direnci_ohm(delik_mm: float, boy_mm: float, kaplama_mm: float) -> float:
    """Via namlusu: ince cidarli silindir, kesit ~ pi * d * t."""
    if delik_mm <= 0 or kaplama_mm <= 0:
        raise ValueError("delik ve kaplama pozitif olmali")
    alan = math.pi * (delik_mm + kaplama_mm) * kaplama_mm * 1e-6
    return RHO_CU * (boy_mm * 1e-3) / alan


def sicaklik_artisi_c(akim_a: float, genislik_mm: float, bakir_oz: float, dis: bool) -> float:
    """IPC-2221B'nin tersi: bu genislik bu akimla kac derece isinir."""
    if akim_a <= 0:
        return 0.0
    k = ipc2221.K_OUTER if dis else ipc2221.K_INNER
    alan_mil2 = (genislik_mm / ipc2221.MM_PER_MIL) * bakir_oz * ipc2221.MIL_PER_OZ
    return (akim_a / (k * alan_mil2 ** 0.725)) ** (1 / 0.44)


def onderdonk_erime_a(kesit_mm2: float, sure_s: float, ortam_c: float = 25.0) -> float:
    """Onderdonk: I = A * sqrt(log10(1 + (Tm - Ta)/(234 + Ta)) / (33 t)).

    A dairesel mil, t saniye. Kisa sureli (adyabatik) darbe icindir; ~10 s
    ustunde gecerli degildir, orada surekli akim hesabi kullanilir.
    """
    if sure_s <= 0 or kesit_mm2 <= 0:
        raise ValueError("kesit ve sure pozitif olmali")
    a_cmil = kesit_mm2 / CMIL_MM2
    return a_cmil * math.sqrt(math.log10(1 + (ONDERDONK_TM_C - ortam_c) / (234 + ortam_c)) / (33 * sure_s))


def _kalinlik_mm(kosullar_pcb: dict, dis: bool) -> float:
    oz = kosullar_pcb.get("bakir_oz" if dis else "ic_bakir_oz") or 1.0
    return float(oz) * MM_PER_OZ


# --------------------------------------------------------------------------
# Akim noktalari: hangi pin ne kadar akim veriyor / cekiyor
# --------------------------------------------------------------------------


@dataclass
class AkimNoktasi:
    pin: str            # "U1.2"
    surekli_a: float    # + kaynak (aga akim verir), - yuk (agdan ceker)
    tepe_a: float
    darbe_s: float | None = None


@dataclass
class AgAkimlari:
    ag: str
    noktalar: list[AkimNoktasi] = field(default_factory=list)
    notlar: list[str] = field(default_factory=list)

    @property
    def toplam_a(self) -> float:
        return sum(-n.surekli_a for n in self.noktalar if n.surekli_a < 0)


def _kaynak_pinleri(g: DevreGrafi, ag: str) -> list[str]:
    """Bu agi BESLEYEN pinler: regulator cikisi, guc-girisi konnektoru."""
    out = []
    for b, rol in g.rolle("regulator"):
        if ag_anahtari(rol.aglar.get("cikis", "")) == ag_anahtari(ag):
            out += [p.tam for p in b.pinler.values() if p.ag == rol.aglar["cikis"]]
    for b, rol in g.rolle("guc-girisi"):
        if ag_anahtari(rol.aglar.get("ray", "")) == ag_anahtari(ag):
            out += [p.tam for p in b.pinler.values() if p.ag == rol.aglar["ray"]]
    return out


def _gnd_pini(b: BilesenDugumu, g: DevreGrafi) -> str | None:
    for p in sorted(b.pinler.values(), key=lambda p: p.numara):
        if p.ag and g.toprak_mi(p.ag):
            return p.tam
    return None


def akim_dagilimi(g: DevreGrafi) -> dict[str, AgAkimlari]:
    """Beyan edilen yuklerden her agin akim noktalari.

    Dogrusal regulatorun GIRIS akimi = cikis yukleri + Iq; bu yuk regulatorun
    giris pinine yazilir (zincir halinde yayilir). Donus akimi: yukun toprak
    pininden kaynagin toprak pinine.
    """
    sonuc: dict[str, AgAkimlari] = {}

    def ag_kaydi(ag: str) -> AgAkimlari:
        a = g.ag(ag)
        ad = a.ad if a else ag
        return sonuc.setdefault(ad, AgAkimlari(ad))

    # (ag, pin, surekli, tepe, darbe, ref)
    yukler: list[tuple[str, str | None, float, float, float | None, str | None]] = []
    for y in g.kosullar.yukler:
        a = g.ag(y.ag)
        if a is None:
            continue
        pinler: list[str] = []
        if y.ref and y.pin:
            pinler = [f"{y.ref}.{y.pin}"]
        elif y.ref:
            pinler = [p.tam for p in a.pinler if p.ref == y.ref]
        else:
            adaylar = [p.tam for p in a.pinler if p.islev == "guc-giris" or p.tip == "power_in"]
            kaynaklar = set(_kaynak_pinleri(g, a.ad))
            adaylar = [p for p in adaylar if p not in kaynaklar]
            if not adaylar:
                # Kart disi yuk: rayi disari veren konnektor pini
                adaylar = [p.tam for p in a.pinler
                           if g.bilesenler[p.ref].tur == "connector" and p.tam not in kaynaklar]
            if len(adaylar) == 1:
                pinler = adaylar
            else:
                ag_kaydi(a.ad).notlar.append(
                    f"{y.akim_a:g} A yukun hangi pinde cekildigi belirtilmedi (ref/pin); "
                    "dal analizi bu yuku iceremez")
                continue
        for pin in pinler:
            pay = 1.0 / len(pinler)
            yukler.append((a.ad, pin, y.akim_a * pay, y.tepe * pay, y.darbe_s, pin.split(".")[0]))

    # Dogrusal regulator zinciri: cikis yuklerini girise tasi (en fazla 5 kat)
    for _ in range(5):
        degisti = False
        for b, rol in g.rolle("regulator"):
            if b.parca.kategori != "ldo":
                continue
            cikis, giris = rol.aglar.get("cikis"), rol.aglar.get("giris")
            if not (cikis and giris):
                continue
            surekli = sum(s for ag, _p, s, _t, _d, _r in yukler if ag == cikis)
            tepe = sum(t for ag, _p, _s, t, _d, _r in yukler if ag == cikis)
            pin = next((p.tam for p in b.pinler.values() if p.ag == giris), None)
            mevcut = [i for i, y in enumerate(yukler) if y[1] == pin and y[0] == giris]
            iq = b.parca.sinir("iq")
            iq_a = iq.onerilen_max if iq and iq.onerilen_max else 0.0
            yeni = (giris, pin, surekli + iq_a, tepe + iq_a, None, b.ref)
            if surekli <= 0 or pin is None:
                continue
            if mevcut:
                if abs(yukler[mevcut[0]][2] - yeni[2]) > 1e-12:
                    yukler[mevcut[0]] = yeni
                    degisti = True
            else:
                yukler.append(yeni)
                degisti = True
                if iq is None:
                    ag_kaydi(giris).notlar.append(f"{b.ref} Iq bilinmiyor; giris akimi = cikis akimi alindi")
        if not degisti:
            break

    for ag, pin, s, t, d, ref in yukler:
        ag_kaydi(ag).noktalar.append(AkimNoktasi(pin, -s, -t, d))

    # Kaynaklar: her agin toplam yukunu besleyen pin(ler)
    for ad, kayit in list(sonuc.items()):
        toplam = kayit.toplam_a
        tepe = sum(-n.tepe_a for n in kayit.noktalar if n.tepe_a < 0)
        kaynaklar = _kaynak_pinleri(g, ad)
        if not kaynaklar:
            kayit.notlar.append("agi besleyen pin bulunamadi (regulator cikisi / guc-girisi konnektoru)")
            continue
        if len(kaynaklar) > 1:
            kayit.notlar.append(f"birden fazla kaynak pini ({', '.join(kaynaklar)}); akim esit bolundu - YAKLASIK")
        for kp in kaynaklar:
            kayit.noktalar.append(AkimNoktasi(kp, toplam / len(kaynaklar), tepe / len(kaynaklar)))

    # Donus yolu (toprak): yuk refinin toprak pininden kaynagin toprak pinine
    for ad, kayit in list(sonuc.items()):
        if g.toprak_mi(ad):
            continue
        kaynak_refleri = {n.pin.split(".")[0] for n in kayit.noktalar if n.surekli_a > 0}
        donus_kaynak = [_gnd_pini(g.bilesenler[r], g) for r in kaynak_refleri if r in g.bilesenler]
        donus_kaynak = [p for p in donus_kaynak if p]
        for n in kayit.noktalar:
            if n.surekli_a >= 0:
                continue
            ref = n.pin.split(".")[0]
            b = g.bilesenler.get(ref)
            gp = _gnd_pini(b, g) if b else None
            if b is not None and b.rol("regulator"):
                continue  # regulatorun giris akimi topraga degil cikisa gider
            if gp is None or not donus_kaynak:
                continue
            gnd_ag = g.pin(ref, gp.split(".")[1]).ag
            gk = ag_kaydi(gnd_ag)
            gk.noktalar.append(AkimNoktasi(gp, -n.surekli_a, -n.tepe_a, n.darbe_s))
            for kp in donus_kaynak:
                gk.noktalar.append(AkimNoktasi(kp, n.surekli_a / len(donus_kaynak),
                                               n.tepe_a / len(donus_kaynak), n.darbe_s))
    # Ayni pine dusen donus noktalarini birlestir
    for kayit in sonuc.values():
        birlesik: dict[str, AkimNoktasi] = {}
        for n in kayit.noktalar:
            if n.pin in birlesik:
                m = birlesik[n.pin]
                m.surekli_a += n.surekli_a
                m.tepe_a += n.tepe_a
                if n.darbe_s is not None:
                    m.darbe_s = n.darbe_s if m.darbe_s is None else min(m.darbe_s, n.darbe_s)
            else:
                birlesik[n.pin] = AkimNoktasi(n.pin, n.surekli_a, n.tepe_a, n.darbe_s)
        kayit.noktalar = list(birlesik.values())
    return sonuc


# --------------------------------------------------------------------------
# Bakir agi: iz parcalari + vialar + padler -> direnc agi
# --------------------------------------------------------------------------


@dataclass
class Kenar:
    tur: str            # iz | via
    a: int
    b: int
    direnc: float
    genislik: float = 0.0
    uzunluk: float = 0.0
    katman: str = ""
    dis: bool = True
    delik: float = 0.0
    x: float = 0.0
    y: float = 0.0
    pad_cikisi: str = ""  # bu iz bir pad'e degiyorsa "U1.2"


@dataclass
class BakirAgi:
    ag: str
    dugum_sayisi: int = 0
    kenarlar: list[Kenar] = field(default_factory=list)
    pad_dugumu: dict[str, int] = field(default_factory=dict)  # "U1.2" -> dugum
    notlar: list[str] = field(default_factory=list)


class _BirlesimKumesi:
    def __init__(self) -> None:
        self.ust: list[int] = []

    def yeni(self) -> int:
        self.ust.append(len(self.ust))
        return len(self.ust) - 1

    def bul(self, x: int) -> int:
        while self.ust[x] != x:
            self.ust[x] = self.ust[self.ust[x]]
            x = self.ust[x]
        return x

    def birlestir(self, a: int, b: int) -> None:
        ra, rb = self.bul(a), self.bul(b)
        if ra != rb:
            self.ust[rb] = ra


def _pad_icinde(pad: Pad, x: float, y: float, katman: str) -> bool:
    if not pad.on_all_layers and katman not in pad.copper_layers:
        return False
    aci = math.radians(-pad.angle)
    dx, dy = x - pad.x, y - pad.y
    lx = dx * math.cos(aci) - dy * math.sin(aci)
    ly = dx * math.sin(aci) + dy * math.cos(aci)
    return abs(lx) <= pad.size_x / 2 + _EPS and abs(ly) <= pad.size_y / 2 + _EPS


def _nokta_parcada(px, py, x1, y1, x2, y2, tol) -> float | None:
    """Nokta parcanin IC kisminda mi? Evetse parametre t (0..1)."""
    vx, vy = x2 - x1, y2 - y1
    L2 = vx * vx + vy * vy
    if L2 < 1e-12:
        return None
    t = ((px - x1) * vx + (py - y1) * vy) / L2
    if t <= 1e-6 or t >= 1 - 1e-6:
        return None
    qx, qy = x1 + t * vx, y1 + t * vy
    return t if math.hypot(px - qx, py - qy) <= tol else None


def bakir_agi_kur(board: Board, ag: str, pcb_kosul: dict, sicaklik_c: float = 20.0) -> BakirAgi:
    agi = BakirAgi(ag)
    uf = _BirlesimKumesi()
    noktalar: dict[tuple[float, float, str], int] = {}

    def nokta(x, y, katman):
        k = (round(x, 3), round(y, 3), katman)
        if k not in noktalar:
            noktalar[k] = uf.yeni()
        return noktalar[k]

    izler = [t for t in board.tracks if t.net == ag]
    # T birlesimleri: bir izin ucu ya da bir padin merkezi baska bir izin
    # ORTASINA degiyorsa o iz orada bolunur (iz padin ustunden geciyor).
    uclar = [(t.x1, t.y1, t.layer) for t in izler] + [(t.x2, t.y2, t.layer) for t in izler]
    for comp in board.components:
        for pad in comp.pads:
            if pad.net == ag:
                for kat in ({t.layer for t in izler} if pad.on_all_layers else pad.copper_layers):
                    uclar.append((pad.x, pad.y, kat))
    parcalar = []
    for t in izler:
        kesimler = sorted({tt for (px, py, kat) in uclar if kat == t.layer
                           for tt in [_nokta_parcada(px, py, t.x1, t.y1, t.x2, t.y2, t.width / 2)]
                           if tt is not None})
        ts = [0.0, *kesimler, 1.0]
        for t0, t1 in zip(ts, ts[1:]):
            parcalar.append((t.x1 + (t.x2 - t.x1) * t0, t.y1 + (t.y2 - t.y1) * t0,
                             t.x1 + (t.x2 - t.x1) * t1, t.y1 + (t.y2 - t.y1) * t1, t.width, t.layer))

    kenar_ham = []
    for x1, y1, x2, y2, w, kat in parcalar:
        a, b = nokta(x1, y1, kat), nokta(x2, y2, kat)
        L = math.hypot(x2 - x1, y2 - y1)
        dis = kat in ("F.Cu", "B.Cu")
        if L < 1e-9:
            uf.birlestir(a, b)
            continue
        r = iz_direnci_ohm(L, w, _kalinlik_mm(pcb_kosul, dis), sicaklik_c)
        kenar_ham.append(Kenar("iz", a, b, r, w, L, kat, dis, x=(x1 + x2) / 2, y=(y1 + y2) / 2))

    # Padler: her pad bir dugum; icine dusen iz uclari pad'e birlesir
    for comp in board.components:
        for pad in comp.pads:
            if pad.net != ag or not pad.number:
                continue
            anahtar = f"{comp.ref}.{pad.number}"
            dn = agi.pad_dugumu.get(anahtar)
            if dn is None:
                dn = uf.yeni()
                agi.pad_dugumu[anahtar] = dn
            for (x, y, kat), n in list(noktalar.items()):
                if _pad_icinde(pad, x, y, kat):
                    uf.birlestir(dn, n)
                    for k in kenar_ham:
                        if k.a == n or k.b == n:
                            k.pad_cikisi = k.pad_cikisi or anahtar

    # Vialar: katmanlar arasi; her katman ayagi R_via/2 (yildiz - YAKLASIK)
    boy = float(pcb_kosul.get("kart_kalinligi_mm") or 1.6)
    kaplama = float(pcb_kosul.get("kaplama_um") or 20.0) * 1e-3
    for v in board.vias:
        if v.net != ag:
            continue
        merkez = uf.yeni()
        r_via = via_direnci_ohm(v.drill, boy, kaplama)
        katmanlar = {kat for (x, y, kat) in noktalar if math.hypot(x - v.x, y - v.y) <= v.size / 2 + _EPS}
        for kat in sorted(katmanlar):
            n = nokta(v.x, v.y, kat)
            for (x, y, k2), m in list(noktalar.items()):
                if k2 == kat and math.hypot(x - v.x, y - v.y) <= v.size / 2 + _EPS:
                    uf.birlestir(n, m)
            kenar_ham.append(Kenar("via", merkez, n, r_via / 2, katman=kat, delik=v.drill, x=v.x, y=v.y))

    # Delikli padler tum katmanlari birlestirir (pad dugumu zaten tek)
    # Birlesimleri uygula ve dugumleri yeniden numarala
    kok_no: dict[int, int] = {}

    def no(x: int) -> int:
        r = uf.bul(x)
        if r not in kok_no:
            kok_no[r] = len(kok_no)
        return kok_no[r]

    for k in kenar_ham:
        k.a, k.b = no(k.a), no(k.b)
        if k.a != k.b:
            agi.kenarlar.append(k)
    agi.pad_dugumu = {p: no(n) for p, n in agi.pad_dugumu.items()}
    agi.dugum_sayisi = len(kok_no)
    if any(z.net == ag for z in board.zones):
        agi.notlar.append("agda bakir dokum var: dokum akimi paylasir, burada MODELLENMEDI - "
                          "iz akimlari FAZLA tahmin (guvenli yon), dusum fazla tahmin")
    return agi


def _coz(n: int, kenarlar: list[Kenar], enjeksiyon: dict[int, float], referans: int) -> list[float] | None:
    """Dugum analizi: G v = i (referans dugum 0 V). Gauss eliminasyonu."""
    idx = [i for i in range(n) if i != referans]
    yer = {d: k for k, d in enumerate(idx)}
    m = len(idx)
    G = [[0.0] * m for _ in range(m)]
    I = [0.0] * m
    for k in kenarlar:
        gk = 1.0 / max(k.direnc, 1e-12)
        for u, v in ((k.a, k.b), (k.b, k.a)):
            if u in yer:
                G[yer[u]][yer[u]] += gk
                if v in yer:
                    G[yer[u]][yer[v]] -= gk
    for d, akim in enjeksiyon.items():
        if d in yer:
            I[yer[d]] += akim
    # kismi pivotlu eliminasyon
    for c in range(m):
        p = max(range(c, m), key=lambda r: abs(G[r][c]))
        if abs(G[p][c]) < 1e-15:
            return None
        G[c], G[p] = G[p], G[c]
        I[c], I[p] = I[p], I[c]
        for r in range(c + 1, m):
            f = G[r][c] / G[c][c]
            if f:
                for cc in range(c, m):
                    G[r][cc] -= f * G[c][cc]
                I[r] -= f * I[c]
    v = [0.0] * m
    for r in range(m - 1, -1, -1):
        v[r] = (I[r] - sum(G[r][cc] * v[cc] for cc in range(r + 1, m))) / G[r][r]
    out = [0.0] * n
    for d, k in yer.items():
        out[d] = v[k]
    return out


def _bagli_bilesen(n: int, kenarlar: list[Kenar], baslangic: int) -> set[int]:
    komsu: dict[int, list[int]] = {}
    for k in kenarlar:
        komsu.setdefault(k.a, []).append(k.b)
        komsu.setdefault(k.b, []).append(k.a)
    gorulen = {baslangic}
    yigin = [baslangic]
    while yigin:
        u = yigin.pop()
        for v in komsu.get(u, []):
            if v not in gorulen:
                gorulen.add(v)
                yigin.append(v)
    return gorulen


# --------------------------------------------------------------------------
# Analiz
# --------------------------------------------------------------------------


@dataclass
class KenarSonucu:
    kenar: Kenar
    surekli_a: float
    tepe_a: float
    gereken_genislik_mm: float = 0.0
    sicaklik_artisi_c: float = 0.0
    kayip_w: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        k = self.kenar
        return {"tur": k.tur, "katman": k.katman, "x": round(k.x, 3), "y": round(k.y, 3),
                "genislik_mm": k.genislik, "uzunluk_mm": round(k.uzunluk, 3), "delik_mm": k.delik,
                "direnc_mohm": round(k.direnc * 1e3, 4), "surekli_a": round(self.surekli_a, 5),
                "tepe_a": round(self.tepe_a, 5), "gereken_genislik_mm": round(self.gereken_genislik_mm, 4),
                "sicaklik_artisi_c": round(self.sicaklik_artisi_c, 2), "kayip_mw": round(self.kayip_w * 1e3, 4),
                "pad_cikisi": k.pad_cikisi}


def iz_analizi(g: DevreGrafi, akimlar: dict[str, AgAkimlari] | None = None):
    """Yonlendirilmis kart uzerinde dal akimi analizi -> SeviyeSonucu.

    `akimlar` verilirse aglarin akim noktalari beyan edilen yuklerden
    (`akim_dagilimi`) TURETILMEZ, bu sozlukten alinir. Neden: `akim_dagilimi`
    yalnizca yuk / regulator / guc girisi bilir; pasif kol akimlarini (bolucu
    direncleri) bilmez. Bolucu ailesi (Kicad-ecd) kol akimlarini kendi en kotu
    kose hesabindan verir."""
    from .dogrulama.sonuc import SeviyeSonucu, bulgu, eksik_bulgu

    KAYNAK = "pcbqa-pcb"
    sonuc = SeviyeSonucu(4, "PCB dal akimi ve iz genisligi")
    if g.board is None:
        sonuc.calisti = False
        sonuc.atlanma_nedeni = "kart yok"
        return sonuc
    if not g.board.tracks:
        sonuc.calisti = False
        sonuc.atlanma_nedeni = "kart yonlendirilmemis - once yonlendirme girdisine bakin (yonlendirme_girdisi)"
        return sonuc
    if akimlar is None and not g.kosullar.yukler:
        sonuc.calisti = False
        sonuc.atlanma_nedeni = "yuk akimi beyan edilmedi (kosullar.yukler) - aglara akim atanamaz"
        return sonuc

    pcb = g.kosullar.pcb
    dT = float(pcb.get("dT_c") or ipc2221.DEFAULT_DELTA_T)
    izin_dv = pcb.get("izin_dV_yuzde")
    ortam = g.kosullar.ortam_c if g.kosullar.ortam_c is not None else 25.0
    ag_ozet: dict[str, Any] = {}
    dagilim = akimlar if akimlar is not None else akim_dagilimi(g)
    for ad, akimlar in sorted(dagilim.items()):
        for n in akimlar.notlar:
            sonuc.bulgular.append(eksik_bulgu("dal-akimi", f"{ad}: {n}", source=KAYNAK))
        if not any(n.surekli_a > 0 for n in akimlar.noktalar):
            continue
        agi = bakir_agi_kur(g.board, ad, pcb, sicaklik_c=ortam + dT)
        for n in agi.notlar:
            sonuc.bulgular.append(bulgu("dal-akimi-not", "info", f"{ad}: {n}", source=KAYNAK))
        kaynak_n = next((n for n in akimlar.noktalar if n.surekli_a > 0), None)
        ref_dugum = agi.pad_dugumu.get(kaynak_n.pin) if kaynak_n else None
        if ref_dugum is None:
            sonuc.bulgular.append(eksik_bulgu("dal-akimi", f"{ad}: kaynak pini kartta bulunamadi", source=KAYNAK))
            continue
        bagli = _bagli_bilesen(agi.dugum_sayisi, agi.kenarlar, ref_dugum)
        kopuk = [n.pin for n in akimlar.noktalar if agi.pad_dugumu.get(n.pin) not in bagli]
        if kopuk:
            sonuc.bulgular.append(bulgu("dal-akimi-kopuk", "warning",
                                        f"{ad}: {', '.join(kopuk)} kaynaga iz ile baglanmiyor "
                                        "(dokum ya da eksik yonlendirme) - bu pinler analiz disi",
                                        source=KAYNAK))
        kenarlar = [k for k in agi.kenarlar if k.a in bagli and k.b in bagli]
        cozumler = {}
        for alan in ("surekli_a", "tepe_a"):
            enj: dict[int, float] = {}
            for n in akimlar.noktalar:
                d = agi.pad_dugumu.get(n.pin)
                if d in bagli:
                    enj[d] = enj.get(d, 0.0) + getattr(n, alan)
            # Kirchhoff: toplam sifir olmali; kaynak (referans) fazlayi alir
            cozumler[alan] = _coz(agi.dugum_sayisi, kenarlar, enj, ref_dugum)
        if cozumler["surekli_a"] is None:
            sonuc.bulgular.append(eksik_bulgu("dal-akimi", f"{ad}: bakir agi cozulemedi (tekil matris)",
                                              source=KAYNAK))
            continue
        vs, vt = cozumler["surekli_a"], cozumler["tepe_a"] or cozumler["surekli_a"]
        darbe = min((n.darbe_s for n in akimlar.noktalar if n.darbe_s), default=None)
        sonuclar: list[KenarSonucu] = []
        for k in kenarlar:
            i_s = abs(vs[k.a] - vs[k.b]) / k.direnc
            i_t = abs(vt[k.a] - vt[k.b]) / k.direnc
            ks = KenarSonucu(k, i_s, max(i_t, i_s), kayip_w=i_s * i_s * k.direnc)
            if k.tur == "iz":
                oz = float(pcb.get("bakir_oz" if k.dis else "ic_bakir_oz") or 1.0)
                ks.gereken_genislik_mm = ipc2221.trace_width_mm(i_s, dT, oz, k.dis)
                ks.sicaklik_artisi_c = sicaklik_artisi_c(i_s, k.genislik, oz, k.dis)
            sonuclar.append(ks)

        ray = g.gerilim(ad)
        dusumler = {n.pin: abs(vs[agi.pad_dugumu[n.pin]]) for n in akimlar.noktalar
                    if n.surekli_a < 0 and agi.pad_dugumu.get(n.pin) in bagli}
        toplam_kayip = sum(s.kayip_w for s in sonuclar)
        ana = max(sonuclar, key=lambda s: s.surekli_a, default=None)
        ag_ozet[ad] = {
            "toplam_a": akimlar.toplam_a,
            "kenar": len(sonuclar),
            "en_yuklu_kol_a": round(ana.surekli_a, 5) if ana else 0.0,
            "kayip_mw": round(toplam_kayip * 1e3, 4),
            "dusumler_mv": {p: round(v * 1e3, 4) for p, v in dusumler.items()},
            "kenarlar": [s.as_dict() for s in sorted(sonuclar, key=lambda s: -s.surekli_a)[:40]],
        }

        for s in sonuclar:
            k = s.kenar
            yer = f"({k.x:.2f}, {k.y:.2f}) {k.katman}"
            if k.tur == "iz" and s.surekli_a > 0 and k.genislik + 1e-9 < s.gereken_genislik_mm:
                tur = "pad-cikisi" if k.pad_cikisi else "darbogaz"
                sonuc.bulgular.append(bulgu(
                    f"iz-{tur}", "error",
                    f"{ad} {yer}: {k.genislik:.3f} mm iz {s.surekli_a:.3f} A tasiyor; IPC-2221B "
                    f"dT={dT:g} C icin {s.gereken_genislik_mm:.3f} mm gerekir (isinma ~{s.sicaklik_artisi_c:.0f} C)"
                    + (f"; {k.pad_cikisi} pad cikisi" if k.pad_cikisi else ""),
                    source=KAYNAK, measured=k.genislik, limit=round(s.gereken_genislik_mm, 4)))
            if k.tur == "via":
                kap = ipc2221.via_current_a(k.delik)
                if s.surekli_a > kap:
                    sonuc.bulgular.append(bulgu(
                        "via-akimi", "error",
                        f"{ad} via ({k.x:.2f}, {k.y:.2f}) {k.delik:.2f} mm: {s.surekli_a:.3f} A > {kap:.2f} A "
                        "(TI SLVA959B, 10 C) - paralel via ekleyin",
                        source=KAYNAK, measured=s.surekli_a, limit=kap))
            if k.tur == "iz" and darbe and s.tepe_a > s.surekli_a:
                kesit = k.genislik * _kalinlik_mm(pcb, k.dis)
                erime = onderdonk_erime_a(kesit, darbe, ortam)
                if s.tepe_a > DARBE_PAYI * erime:
                    sonuc.bulgular.append(bulgu(
                        "iz-darbe", "error",
                        f"{ad} {yer}: {s.tepe_a:.2f} A x {darbe * 1e3:g} ms darbe; Onderdonk erime "
                        f"{erime:.1f} A, pay %{DARBE_PAYI * 100:.0f} asiliyor",
                        source=KAYNAK, measured=s.tepe_a, limit=DARBE_PAYI * erime))

        if izin_dv is not None and ray.bilinen and float(ray.deger):
            sinir = abs(float(ray.deger)) * float(izin_dv) / 100.0
            for pin, dv in dusumler.items():
                if dv > sinir:
                    sonuc.bulgular.append(bulgu(
                        "iz-gerilim-dusumu", "error",
                        f"{ad}: kaynaktan {pin}'e dusum {dv * 1e3:.1f} mV > %{float(izin_dv):g} "
                        f"({sinir * 1e3:.1f} mV)", source=KAYNAK, pins=[pin], measured=dv, limit=sinir))
        elif izin_dv is None:
            sonuc.bulgular.append(eksik_bulgu("iz-gerilim-dusumu",
                                              f"{ad}: izin verilen dusum beyan edilmedi (pcb.izin_dV_yuzde); "
                                              f"olculen en buyuk dusum {max(dusumler.values(), default=0) * 1e3:.1f} mV",
                                              source=KAYNAK))

        # Konnektor pin akimi
        for n in akimlar.noktalar:
            ref = n.pin.split(".")[0]
            b = g.bilesenler.get(ref)
            if b is None or b.tur != "connector":
                continue
            s_akim = b.parca.sinir("akim")
            if s_akim is None or s_akim.onerilen_max is None:
                sonuc.bulgular.append(eksik_bulgu("konnektor-akimi",
                                                  f"{n.pin} {abs(n.surekli_a):.3f} A tasiyor; pin akim siniri bilinmiyor",
                                                  source=KAYNAK, refs=[ref]))
            elif abs(n.surekli_a) > s_akim.onerilen_max:
                sonuc.bulgular.append(bulgu("konnektor-akimi", "error",
                                            f"{n.pin} {abs(n.surekli_a):.3f} A > pin siniri {s_akim.onerilen_max:g} A",
                                            source=KAYNAK, refs=[ref], measured=abs(n.surekli_a),
                                            limit=s_akim.onerilen_max))
    sonuc.ekler["aglar"] = ag_ozet
    return sonuc


# --------------------------------------------------------------------------
# Yonlendirmeden ONCE: yerlesim kisitlari -> uretim sinirlari -> dal butcesi
# --------------------------------------------------------------------------


def _pin_xy(g: DevreGrafi, tam: str) -> tuple[float, float] | None:
    ref, _, no = tam.partition(".")
    p = g.pin(ref, no)
    if p is None or not p.padler:
        return None
    return p.padler[0].x, p.padler[0].y


def _manhattan(a, b) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def yonlendirme_girdisi(g: DevreGrafi) -> dict[str, Any]:
    """Yol cizicinin girdisi: once kisitlar, sonra dal akimlari ve genislikler.

    Dal topolojisi kaynak pinden baslayan dogrusal (Manhattan) en kucuk
    kapsayan agactir - yonlendirilmemis kartta gercek yolun en iyi tahmini.
    Her agac kenari, kaynaktan uzak tarafindaki yuklerin TOPLAMINI tasir.
    """
    pcb = g.kosullar.pcb
    fab = ipc2221.FAB_CLASSES.get(str(pcb.get("uretici") or "standart"), ipc2221.FAB_CLASSES["standart"])
    dT = float(pcb.get("dT_c") or ipc2221.DEFAULT_DELTA_T)
    oz = float(pcb.get("bakir_oz") or 1.0)
    izin_dv = pcb.get("izin_dV_yuzde")

    # 1) yerlesim kisitlari: kritik baglantilar
    kisitlar = []
    for rol_adi in ("dekuplaj", "regulator-giris-kond", "regulator-cikis-kond"):
        for b, rol in g.rolle(rol_adi):
            ray = rol.aglar.get("ray")
            c_pin = next((p.tam for p in b.pinler.values() if p.ag == ray), None)
            hedef_pinler = rol.hedefler if rol_adi == "dekuplaj" else [
                p.tam for h in rol.hedefler if h in g.bilesenler
                for p in g.bilesenler[h].pinler.values() if p.ag == ray]
            for hp in hedef_pinler:
                a, c = _pin_xy(g, hp), _pin_xy(g, c_pin) if c_pin else None
                mesafe = math.hypot(a[0] - c[0], a[1] - c[1]) if a and c else None
                kisitlar.append({
                    "tur": rol_adi, "bilesen": b.ref, "hedef": hp,
                    "azami_mm": ipc2221.DECOUPLING_MAX_MM,
                    "kaynak": "TI SBAA113 (6.35 mm ust sinir)",
                    "mevcut_mm": round(mesafe, 3) if mesafe is not None else None,
                    "saglaniyor": (mesafe <= ipc2221.DECOUPLING_MAX_MM) if mesafe is not None else None,
                })

    # 2) uretim sinirlari
    uretim = {"profil": fab.name, "min_iz_mm": fab.min_track_mm, "min_aciklik_mm": fab.min_clearance_mm,
              "min_delik_mm": fab.min_drill_mm, "min_halka_mm": fab.min_annular_ring_mm,
              "min_kenar_mm": fab.min_edge_clearance_mm, "kaynak": "docs/tasarim-kurallari 2.6/2.7"}

    # 3) dal butcesi
    aglar = {}
    for ad, akimlar in sorted(akim_dagilimi(g).items()):
        kaynaklar = [n for n in akimlar.noktalar if n.surekli_a > 0]
        yukler = [n for n in akimlar.noktalar if n.surekli_a < 0]
        if not kaynaklar or not yukler:
            if akimlar.notlar:
                aglar[ad] = {"notlar": akimlar.notlar}
            continue
        kok = kaynaklar[0].pin
        konum = {n.pin: _pin_xy(g, n.pin) for n in akimlar.noktalar}
        if any(v is None for v in konum.values()):
            aglar[ad] = {"notlar": akimlar.notlar + ["bazi pinlerin kartta konumu yok (yerlestirilmemis)"]}
            continue
        # Prim: kaynaktan buyuyen Manhattan agaci
        agacta = {kok}
        ebeveyn: dict[str, str] = {}
        kalan = {n.pin for n in akimlar.noktalar} - agacta
        while kalan:
            u, v = min(((u, v) for u in agacta for v in kalan),
                       key=lambda uv: _manhattan(konum[uv[0]], konum[uv[1]]))
            ebeveyn[v] = u
            agacta.add(v)
            kalan.discard(v)
        # Agac kenarinin akimi = kenarin altindaki alt agacin NET enjeksiyonu
        # (Kirchhoff). Isaretli toplanir; toprak agi (cok kaynakli donus) da
        # boylece dogru cikar.
        akim = {n.pin: n.surekli_a for n in akimlar.noktalar}
        tepe = {n.pin: n.tepe_a for n in akimlar.noktalar}
        alt_toplam: dict[str, tuple[float, float]] = {}

        def alt(p):
            if p in alt_toplam:
                return alt_toplam[p]
            s, t = akim.get(p, 0.0), tepe.get(p, 0.0)
            for c, e in ebeveyn.items():
                if e == p:
                    cs, ct = alt(c)
                    s, t = s + cs, t + ct
            alt_toplam[p] = (s, t)
            return alt_toplam[p]

        ray = g.gerilim(ad)
        dallar = []
        for cocuk, e in ebeveyn.items():
            s, t = (abs(x) for x in alt(cocuk))
            L = _manhattan(konum[e], konum[cocuk])
            w_ipc = ipc2221.trace_width_mm(s, dT, oz, True)
            w = max(w_ipc, fab.min_track_mm)
            r = iz_direnci_ohm(max(L, 1e-6), w, oz * MM_PER_OZ) if L > 0 else 0.0
            dal = {"den": e, "e": cocuk, "surekli_a": round(s, 5), "tepe_a": round(t, 5),
                   "tahmini_uzunluk_mm": round(L, 3), "gereken_genislik_mm": round(w_ipc, 4),
                   "onerilen_genislik_mm": round(w, 4), "tahmini_dusum_mv": round(s * r * 1e3, 4)}
            if izin_dv is not None and ray.bilinen and float(ray.deger) and s > 0:
                dv_izin = abs(float(ray.deger)) * float(izin_dv) / 100.0
                # Bu genislikte izin verilen dusume ulasan uzunluk (tek dal icin)
                r_per_mm = iz_direnci_ohm(1.0, w, oz * MM_PER_OZ)
                dal["azami_uzunluk_mm"] = round(dv_izin / (s * r_per_mm), 1)
            dallar.append(dal)
        aglar[ad] = {"kaynak": kok, "toplam_a": round(akimlar.toplam_a, 5),
                     "dallar": sorted(dallar, key=lambda d: -d["surekli_a"]), "notlar": akimlar.notlar}

    return {
        "sira": ["1-yerlesim-kisitlari", "2-uretim-sinirlari", "3-dal-akimlari-ve-genislik"],
        "yerlesim_kisitlari": kisitlar,
        "uretim_sinirlari": uretim,
        "parametreler": {"dT_c": dT, "bakir_oz": oz, "izin_dV_yuzde": izin_dv},
        "aglar": aglar,
    }
