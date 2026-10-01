"""Parca bilgisi: deger, tolerans, uretici/MPN, pin islevleri, sinirlar,
termal veri, SOA, SPICE modeli, yaslanma - ve EKSIK olanlarin listesi.

Kaynak sirasi (yukseginden dusugune):
  1. Sembolun kendi alanlari (MPN, Manufacturer, Tolerance, Voltage, Power)
  2. Kutuphanede MPN ile TAM eslesen kayit           -> parcaya-ozel
  3. Kutuphanede deger/sembol adi deseniyle eslesen   -> kaydin guveni
  4. Genel paket kaydi (0603 direnc gibi)             -> paket-tipik
  5. Hicbiri: alan EKSIK kalir ve nedeni yazilir

Kutuphane `pcbqa/data/parcalar/*.yaml` dosyalarindadir (JSON calisma zamani
kopyalariyla; bkz. bundle.py). Kayitlarin cogu "dogrulanmamis" isaretlidir:
veri sayfasindan elle aktarildi, sayfa numarasiyla teyit edilmedi. Bu isaret
raporlara tasinir - gercek bir uretim kararindan once teyit edilmelidir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..circuit import parse_value
from ..confload import ConfigError, load_config
from .bilgi import Bilgi, bilinen, eksik

KUTUPHANE_KLASORU = Path(__file__).resolve().parent.parent / "data" / "parcalar"

KATEGORILER = (
    "direnc", "kondansator", "induktor", "ldo", "regulator", "mosfet-n",
    "mosfet-p", "bjt-npn", "bjt-pnp", "diyot", "led", "tvs", "zener", "mcu",
    "konnektor", "sigorta", "kristal", "role", "test-noktasi", "entegre",
    "genel",
)

# Sembol alanlarinin olasi adlari. Kutuphaneler tutarsiz; en yaygin bicimler.
_ALAN_MPN = ("MPN", "Manufacturer_Part_Number", "Manufacturer Part Number",
             "PartNumber", "Part Number", "MFR_PN", "MPN1")
_ALAN_URETICI = ("Manufacturer", "MFR", "Mfr", "Manufacturer_Name", "Uretici")
_ALAN_TOLERANS = ("Tolerance", "Tolerans", "TOL")
_ALAN_GERILIM = ("Voltage", "Rated Voltage", "Rated_Voltage", "Gerilim", "V")
_ALAN_GUC = ("Power", "Rated Power", "Power_Rating", "Guc", "P")
_ALAN_AKIM = ("Current", "Rated Current", "Akim", "I")


@dataclass(frozen=True)
class Sinir:
    """Bir buyuklugun onerilen calisma araligi ve mutlak maksimumu."""

    ad: str
    birim: str = ""
    onerilen_min: float | None = None
    onerilen_max: float | None = None
    mutlak_min: float | None = None
    mutlak_max: float | None = None
    kosul: str = ""
    kaynak: str = ""
    guven: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in vars(self).items() if v not in (None, "")}


@dataclass
class PinBilgisi:
    numara: str
    ad: str = ""
    # giris | cikis | iki-yonlu | guc-giris | guc-cikis | gnd | pasif |
    # gate | drain | source | anot | katot | acik-kolektor | nc
    islev: str = ""
    sinirlar: dict[str, Sinir] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "numara": self.numara,
            "ad": self.ad,
            "islev": self.islev,
            "sinirlar": {k: s.as_dict() for k, s in self.sinirlar.items()},
        }


@dataclass
class SpiceModeli:
    """Bir parcanin benzetim modeli ve sembol pinleriyle eslesmesi.

    `tur`:
      primitif    - R/C/L gibi SPICE'in kendi elemani (tam)
      altdevre    - ureticinin .subckt modeli (`metin` icinde)
      davranissal - pcbqa'nin ureticisiz yaklasik modeli; `ideal` True'dur ve
                    raporda acikca "ideal model" yazar (bkz. Kicad-5d6.5)
    """

    tur: str
    ad: str = ""
    metin: str = ""
    # Modelin dugum SIRASI (".subckt AD n1 n2 n3")
    dugumler: list[str] = field(default_factory=list)
    # sembol pin numarasi -> model dugum adi
    pin_esleme: dict[str, str] = field(default_factory=dict)
    # davranissal sablon parametreleri (vnom, dusum, ...)
    parametreler: dict[str, Any] = field(default_factory=dict)
    kaynak: str = ""
    lisans: str = ""
    ideal: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "tur": self.tur,
            "ad": self.ad,
            "dugumler": list(self.dugumler),
            "pin_esleme": dict(self.pin_esleme),
            "parametreler": dict(self.parametreler),
            "kaynak": self.kaynak,
            "lisans": self.lisans,
            "ideal": self.ideal,
        }


@dataclass
class ParcaBilgisi:
    """Bir bilesen ornegi icin toplanmis parca bilgisi."""

    kategori: str = "genel"
    kutuphane_kaydi: str = ""          # eslesen kaydin anahtari ("" = yok)
    deger: Bilgi = field(default_factory=lambda: eksik("deger yok"))
    tolerans: Bilgi = field(default_factory=lambda: eksik("tolerans bilinmiyor"))
    uretici: Bilgi = field(default_factory=lambda: eksik("uretici bilinmiyor"))
    mpn: Bilgi = field(default_factory=lambda: eksik("tam parca numarasi (MPN) yok"))
    paket: str = ""
    pinler: dict[str, PinBilgisi] = field(default_factory=dict)
    sinirlar: dict[str, Sinir] = field(default_factory=dict)
    termal: dict[str, Bilgi] = field(default_factory=dict)
    soa: Bilgi = field(default_factory=lambda: eksik("guvenli calisma alani (SOA) verisi yok"))
    spice: SpiceModeli | None = None
    spice_eksik: str = "SPICE modeli yok"
    sicaklik_katsayisi: Bilgi = field(default_factory=lambda: eksik("sicaklik katsayisi bilinmiyor"))
    yaslanma: Bilgi = field(default_factory=lambda: eksik("yaslanma verisi yok"))
    dogrulama: str = ""                # kutuphane kaydinin durumu
    notlar: list[str] = field(default_factory=list)
    # Pin numarasi pakete gore degisen parcalar (MCU) icin ADA gore kurallar:
    # [(desen, islev, {ad: Sinir})]
    pin_ad_kurallari: list[tuple[re.Pattern, str, dict[str, Sinir]]] = field(default_factory=list)
    # MPN uretici adlandirma kuralindan cozulduyse: {paket, tolerans, deger,
    # tolerans_kodu} (Kicad-7cb). Footprint paketiyle karsilastirma bunun uzerinden.
    mpn_cozumu: dict[str, Any] | None = None
    # Sembol alanlari ile MPN'in soyledigi celisirse (deger, tolerans)
    celiskiler: list[str] = field(default_factory=list)
    # Deger / tolerans / paket ureticinin katalog araliginda degilse nedeni
    katalog_disi: str = ""

    def sinir(self, ad: str) -> Sinir | None:
        return self.sinirlar.get(ad)

    def pin_bilgisi(self, numara: str, ad: str = "") -> PinBilgisi | None:
        """Numarayla kayitli pin; yoksa pin ADINA uyan kural."""
        if numara in self.pinler:
            return self.pinler[numara]
        for desen, islev, sinirlar in self.pin_ad_kurallari:
            if ad and desen.search(ad):
                return PinBilgisi(numara=numara, ad=ad, islev=islev, sinirlar=dict(sinirlar))
        return None

    def eksikler(self) -> list[str]:
        """Bu parca hakkinda bilinmeyenler, okunur cumleler halinde."""
        out: list[str] = []
        alanlar = [("deger", self.deger), ("uretici", self.uretici), ("MPN", self.mpn)]
        # Tolerans yalnizca degeri devreyi belirleyen parcalarda anlamli; bir
        # konnektorun ya da entegrenin "toleransi" sorulmaz (sinirlari sorulur).
        if self.kategori in ("direnc", "kondansator", "induktor", "kristal"):
            alanlar.insert(1, ("tolerans", self.tolerans))
        for ad, alan in alanlar:
            if not alan.bilinen:
                out.append(f"{ad}: {alan.eksik_neden or 'bilinmiyor'}")
        if self.kategori == "kondansator" and "gerilim" not in self.sinirlar:
            out.append("anma gerilimi: sembol alani (Voltage) ya da deger metni ('100nF 50V') yok")
        if self.kategori == "direnc" and "guc" not in self.sinirlar:
            out.append("anma gucu: paket kodu cozulemedi ve sembol alani (Power) yok")
        if self.kategori == "konnektor" and "akim" not in self.sinirlar:
            out.append("pin akim siniri: sembol alani (Current) ya da kutuphane kaydi yok")
        if self.kategori == "sigorta" and "akim" not in self.sinirlar:
            out.append("sigorta anma akimi: deger ('500mA') ya da Current alani yok")
        if self.kategori in ("ldo", "regulator", "mosfet-n", "mosfet-p", "diyot",
                             "led", "tvs", "zener", "mcu", "entegre", "bjt-npn",
                             "bjt-pnp") and not self.sinirlar:
            out.append("sinirlar: onerilen calisma ve mutlak maksimum degerler yok")
        if self.kategori not in ("konnektor", "test-noktasi", "genel", "direnc",
                                 "kondansator", "induktor") \
                and not self.pinler and not self.pin_ad_kurallari:
            out.append("pin islevleri: kutuphane kaydi yok")
        if self.kategori in ("ldo", "regulator", "mosfet-n", "mosfet-p", "diyot",
                             "led", "tvs", "zener", "entegre", "mcu") and \
                not self.termal.get("tj_max", Bilgi()).bilinen:
            out.append("termal: azami jonksiyon sicakligi bilinmiyor")
        if self.kategori in ("mosfet-n", "mosfet-p", "bjt-npn", "bjt-pnp") and not self.soa.bilinen:
            out.append(f"SOA: {self.soa.eksik_neden}")
        if self.spice is None and self.kategori not in ("konnektor", "test-noktasi", "genel"):
            out.append(f"SPICE: {self.spice_eksik}")
        elif self.spice is not None and self.spice.ideal:
            out.append("SPICE: yalnizca davranissal/ideal model - uretici modeli gerekli")
        if self.kategori in ("direnc", "kondansator") and not self.sicaklik_katsayisi.bilinen:
            out.append(f"sicaklik katsayisi: {self.sicaklik_katsayisi.eksik_neden}")
        if self.kategori in ("direnc", "kondansator", "ldo", "regulator") and not self.yaslanma.bilinen:
            out.append(f"yaslanma: {self.yaslanma.eksik_neden}")
        return out

    def as_dict(self) -> dict[str, Any]:
        return {
            "kategori": self.kategori,
            "kutuphane_kaydi": self.kutuphane_kaydi,
            "dogrulama": self.dogrulama,
            "deger": self.deger.as_dict(),
            "tolerans": self.tolerans.as_dict(),
            "uretici": self.uretici.as_dict(),
            "mpn": self.mpn.as_dict(),
            "paket": self.paket,
            "pinler": {k: p.as_dict() for k, p in self.pinler.items()},
            "sinirlar": {k: s.as_dict() for k, s in self.sinirlar.items()},
            "termal": {k: b.as_dict() for k, b in self.termal.items()},
            "soa": self.soa.as_dict(),
            "spice": self.spice.as_dict() if self.spice else {"eksik": self.spice_eksik},
            "sicaklik_katsayisi": self.sicaklik_katsayisi.as_dict(),
            "yaslanma": self.yaslanma.as_dict(),
            "eksikler": self.eksikler(),
            "notlar": list(self.notlar),
        }


# --------------------------------------------------------------------------
# Deger metninden ek bilgiler: "100nF 50V X7R 10%", "4k7 1% 0603"
# --------------------------------------------------------------------------

_TOL_RE = re.compile(r"(?<![\w.])[±+-]?(\d+(?:\.\d+)?)\s*%")
_GERILIM_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*V(?:DC)?\b", re.IGNORECASE)
_GUC_RE = re.compile(r"(?<![\w.])(?:(\d+)/(\d+)|(\d+(?:\.\d+)?)(m?))\s*W\b")
_DIELEKTRIK_RE = re.compile(r"\b(X7R|X5R|X6S|X7S|X8R|C0G|NP0|Y5V|Z5U)\b", re.IGNORECASE)
# Footprint adindan paket kodu: R_0603_1608Metric -> 0603
_PAKET_RE = re.compile(r"(?:^|[_:])(0201|0402|0603|0805|1206|1210|1812|2010|2512)(?:_|$)")


def tolerans_metinden(metin: str) -> float | None:
    m = _TOL_RE.search(metin or "")
    return float(m.group(1)) / 100.0 if m else None


def gerilim_metinden(metin: str) -> float | None:
    """"100nF 50V" -> 50. Yalnizca deger ALANININ ILK parcasi disinda arar;
    "3V3" gibi ray adlarini gerilim derecelendirmesi sanmamak icin RKM
    bicimi (sayi-V-sayi) eslesmez."""
    parcalar = (metin or "").split()
    for parca in parcalar[1:] if len(parcalar) > 1 else []:
        m = _GERILIM_RE.fullmatch(parca)
        if m:
            return float(m.group(1))
    return None


def guc_metinden(metin: str) -> float | None:
    for parca in (metin or "").split()[1:]:
        m = _GUC_RE.fullmatch(parca)
        if not m:
            continue
        if m.group(1):
            return float(m.group(1)) / float(m.group(2))
        sayi = float(m.group(3))
        return sayi / 1000.0 if m.group(4) else sayi
    return None


# EIA RS-198 sinif II kodu: alt sicaklik harfi, ust sicaklik rakami, degisim
# harfi. Bu bir TANIMDIR (kodun kendisi araligi soyler), tahmin degil.
_EIA_ALT = {"X": -55.0, "Y": -30.0, "Z": 10.0}
_EIA_UST = {"5": 85.0, "6": 105.0, "7": 125.0, "8": 150.0}
_EIA_DEGISIM = {"R": (-15.0, 15.0), "S": (-22.0, 22.0), "U": (-56.0, 22.0), "V": (-82.0, 22.0)}


def dielektrik_sicaklik(kod: str) -> dict[str, float] | None:
    """X7R -> {min_c: -55, max_c: 125, degisim_min_yuzde: -15, ...}.

    C0G/NP0 sinif I: 0 +-30 ppm/C, -55..125 C.
    """
    kod = (kod or "").upper()
    if kod in ("C0G", "NP0"):
        return {"min_c": -55.0, "max_c": 125.0, "ppm_c": 30.0}
    if len(kod) == 3 and kod[0] in _EIA_ALT and kod[1] in _EIA_UST and kod[2] in _EIA_DEGISIM:
        lo, hi = _EIA_DEGISIM[kod[2]]
        return {"min_c": _EIA_ALT[kod[0]], "max_c": _EIA_UST[kod[1]],
                "degisim_min_yuzde": lo, "degisim_max_yuzde": hi}
    return None


_AKIM_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(m?)A\b")


def akim_metinden(metin: str) -> float | None:
    """"500mA" -> 0.5, "1.5A" -> 1.5 (sigorta degeri, Current alani)."""
    m = _AKIM_RE.search(metin or "")
    if not m:
        return None
    sayi = float(m.group(1))
    return sayi / 1000.0 if m.group(2) else sayi


def paket_kodu(footprint: str) -> str:
    m = _PAKET_RE.search(footprint or "")
    return m.group(1) if m else ""


def _alan(alanlar: dict[str, str], adlar: tuple[str, ...]) -> tuple[str, str] | None:
    lower = {k.lower(): (k, v) for k, v in alanlar.items()}
    for ad in adlar:
        hit = lower.get(ad.lower())
        if hit and str(hit[1]).strip() and str(hit[1]).strip() not in ("~", "-"):
            return hit[0], str(hit[1]).strip()
    return None


# --------------------------------------------------------------------------
# Kutuphane
# --------------------------------------------------------------------------


class KutuphaneHatasi(ValueError):
    pass


def _sinir(ad: str, ham: dict[str, Any], kaynak: str, guven: str) -> Sinir:
    izinli = {"birim", "onerilen_min", "onerilen_max", "mutlak_min", "mutlak_max", "kosul", "kaynak"}
    fazla = set(ham) - izinli
    if fazla:
        raise KutuphaneHatasi(f"sinir {ad}: bilinmeyen alan(lar) {sorted(fazla)}")

    def f(k):
        v = ham.get(k)
        return None if v is None else float(v)

    return Sinir(
        ad=ad, birim=str(ham.get("birim", "")),
        onerilen_min=f("onerilen_min"), onerilen_max=f("onerilen_max"),
        mutlak_min=f("mutlak_min"), mutlak_max=f("mutlak_max"),
        kosul=str(ham.get("kosul", "")),
        kaynak=str(ham.get("kaynak") or kaynak), guven=guven,
    )


@dataclass
class KutuphaneKaydi:
    anahtar: str
    kategori: str
    ham: dict[str, Any]
    kaynak: str
    guven: str
    mpn: str = ""
    desenler: list[re.Pattern] = field(default_factory=list)
    tur: str = ""          # genel eslesme icin model.ref_kind degeri
    dosya: Path | None = None
    mpn_desen: re.Pattern | None = None   # uretici siparis kodu deseni (Kicad-7cb)

    def eslesir_mi(self, deger: str, libpart: str, lib_id: str) -> bool:
        return any(d.search(t) for d in self.desenler for t in (deger, libpart, lib_id) if t)


@dataclass
class Kutuphane:
    kayitlar: list[KutuphaneKaydi] = field(default_factory=list)

    def mpn_ile(self, mpn: str) -> KutuphaneKaydi | None:
        hedef = (mpn or "").strip().upper()
        for k in self.kayitlar:
            if k.mpn and k.mpn.upper() == hedef:
                return k
        return None

    def desen_ile(self, deger: str, libpart: str, lib_id: str) -> KutuphaneKaydi | None:
        for k in self.kayitlar:
            if k.desenler and k.eslesir_mi(deger, libpart, lib_id):
                return k
        return None

    def mpn_deseni_ile(self, mpn: str) -> tuple[KutuphaneKaydi, re.Match] | None:
        for k in self.kayitlar:
            if k.mpn_desen is not None:
                m = k.mpn_desen.match((mpn or "").strip().upper())
                if m:
                    return k, m
        return None

    def genel(self, tur: str) -> KutuphaneKaydi | None:
        for k in self.kayitlar:
            if k.tur and k.tur == tur:
                return k
        return None


def kutuphane_ayristir(data: dict[str, Any], dosya: Path | None = None) -> list[KutuphaneKaydi]:
    if data.get("version") != 1:
        raise KutuphaneHatasi(f"{dosya}: version: 1 bekleniyor")
    out: list[KutuphaneKaydi] = []
    for i, ham in enumerate(data.get("parcalar") or []):
        yer = f"{dosya}: parcalar[{i}]"
        if not isinstance(ham, dict) or not ham.get("anahtar") or not ham.get("kategori"):
            raise KutuphaneHatasi(f"{yer}: anahtar ve kategori zorunlu")
        if ham["kategori"] not in KATEGORILER:
            raise KutuphaneHatasi(f"{yer}: bilinmeyen kategori {ham['kategori']!r}")
        if not ham.get("kaynak"):
            # Kaynaksiz sayi yazilmaz (proje kurali).
            raise KutuphaneHatasi(f"{yer}: kaynak zorunlu")
        guven = str(ham.get("guven", "dogrulanmamis"))
        eslesme = ham.get("eslesme") or {}
        desenler = [re.compile(p, re.IGNORECASE) for p in (eslesme.get("desenler") or [])]
        out.append(KutuphaneKaydi(
            anahtar=str(ham["anahtar"]),
            kategori=str(ham["kategori"]),
            ham=ham,
            kaynak=str(ham["kaynak"]),
            guven=guven,
            mpn=str(ham.get("mpn") or ""),
            desenler=desenler,
            tur=str(eslesme.get("tur") or ""),
            dosya=dosya,
            mpn_desen=re.compile(str(eslesme["mpn_desen"])) if eslesme.get("mpn_desen") else None,
        ))
    return out


def kutuphane_oku(klasor: Path | None = None) -> Kutuphane:
    klasor = Path(klasor) if klasor else KUTUPHANE_KLASORU
    kayitlar: list[KutuphaneKaydi] = []
    if not klasor.is_dir():
        return Kutuphane()
    # YAML kaynak, JSON calisma zamani kopyasi; ayni kok adini iki kez okuma.
    kokler = sorted({p.with_suffix("") for p in klasor.glob("*.yaml")}
                    | {p.with_suffix("") for p in klasor.glob("*.json")})
    for kok in kokler:
        yol = kok.with_suffix(".yaml")
        if not yol.is_file():
            yol = kok.with_suffix(".json")
        try:
            data, _ = load_config(yol)
        except ConfigError as exc:
            raise KutuphaneHatasi(f"{yol}: {exc}") from exc
        kayitlar.extend(kutuphane_ayristir(data, yol))
    anahtarlar = [k.anahtar for k in kayitlar]
    tekrar = {a for a in anahtarlar if anahtarlar.count(a) > 1}
    if tekrar:
        raise KutuphaneHatasi(f"tekrar eden parca anahtari: {sorted(tekrar)}")
    return Kutuphane(kayitlar)


_VARSAYILAN: Kutuphane | None = None


def varsayilan_kutuphane() -> Kutuphane:
    global _VARSAYILAN
    if _VARSAYILAN is None:
        _VARSAYILAN = kutuphane_oku()
    return _VARSAYILAN


# --------------------------------------------------------------------------
# Kayittan ParcaBilgisi'ne
# --------------------------------------------------------------------------

# model.ref_kind -> kategori (kutuphane kaydi yoksa)
_TUR_KATEGORI = {
    "resistor": "direnc",
    "capacitor": "kondansator",
    "inductor": "induktor",
    "connector": "konnektor",
    "fuse": "sigorta",
    "crystal": "kristal",
    "testpoint": "test-noktasi",
}


# Paket tablosu satirinda sinir OLMAYAN anahtarlar (Kicad-7cb)
_PAKET_OZEL = ("tcr", "termal", "araliklar")


def _paket_ozel_uygula(pb: ParcaBilgisi, kayit: KutuphaneKaydi, satir: dict[str, Any], g: str, paket: str) -> None:
    """Pakete ve degere bagli TCR; katalog araligi denetimi."""
    r = pb.deger.deger if pb.deger.bilinen and isinstance(pb.deger.deger, float) else None
    tcr = satir.get("tcr")
    if tcr and r is not None:
        ppm = next((float(p) for ust, p in tcr if r <= float(ust)), None)
        if ppm is None:
            pb.sicaklik_katsayisi = eksik(f"{r:g} ohm {kayit.anahtar} TCR tablosunun disinda")
        else:
            pb.sicaklik_katsayisi = bilinen({"ppm_c": ppm, "kosul": f"{r:g} ohm, paket {paket}"},
                                            kayit.kaynak, g)
    elif tcr:
        pb.sicaklik_katsayisi = eksik("deger bilinmiyor - TCR degere bagli")
    araliklar = satir.get("araliklar") or {}
    tol = pb.tolerans.deger if pb.tolerans.bilinen else None
    if araliklar and r is not None and tol is not None:
        anahtar = next((k for k in araliklar if abs(float(k) - float(tol)) < 1e-12), None)
        if anahtar is None:
            pb.katalog_disi = f"%{float(tol) * 100:g} tolerans {kayit.anahtar} {paket} katalogunda yok"
        else:
            lo, hi = (float(x) for x in araliklar[anahtar])
            if not lo <= r <= hi:
                pb.katalog_disi = (f"{r:g} ohm %{float(tol) * 100:g} {paket} katalog araligi disinda "
                                   f"({lo:g}..{hi:g} ohm)")
            elif abs(float(tol) - 0.05) < 1e-12 and not e_serisinde(r, "E24"):
                # Tablo 2: %5 yalnizca E24; %1 ve altinda E24/E96
                pb.katalog_disi = f"{r:g} ohm %5 icin E24 degeri degil (RC_L %5 yalnizca E24)"
            elif not (e_serisinde(r, "E24") or e_serisinde(r, "E96")):
                pb.katalog_disi = f"{r:g} ohm E24/E96 degeri degil"
    if pb.katalog_disi:
        pb.notlar.append(f"KATALOG DISI: {pb.katalog_disi}")


def _tolerans_sinifi_uygula(pb: ParcaBilgisi, kayit: KutuphaneKaydi, g: str) -> None:
    """Omur testi sapmasi tolerans sinifina baglidir (RC_L Tablo 8: F %1, J %3)."""
    tol = pb.tolerans.deger if pb.tolerans.bilinen else None
    if tol is None:
        pb.yaslanma = eksik("tolerans bilinmiyor - omur sapmasi tolerans sinifina bagli")
        return
    sinif = next((c for c in kayit.ham["tolerans_siniflari"] if abs(float(c["tolerans"]) - float(tol)) < 1e-12),
                 None)
    if sinif is None:
        pb.yaslanma = eksik(f"%{float(tol) * 100:g} tolerans sinifi {kayit.anahtar} kaydinda yok")
        if not pb.katalog_disi:
            pb.katalog_disi = f"%{float(tol) * 100:g} tolerans {kayit.anahtar} serisinde yok"
            pb.notlar.append(f"KATALOG DISI: {pb.katalog_disi}")
        return
    pb.yaslanma = bilinen(dict(sinif["yaslanma"]), kayit.kaynak, g)


def _kayit_uygula(pb: ParcaBilgisi, kayit: KutuphaneKaydi, paket: str) -> None:
    ham = kayit.ham
    pb.kategori = kayit.kategori
    pb.kutuphane_kaydi = kayit.anahtar
    pb.dogrulama = kayit.guven
    g = kayit.guven

    if ham.get("uretici") and not pb.uretici.bilinen:
        pb.uretici = bilinen(str(ham["uretici"]), kayit.kaynak, g)
    if kayit.mpn and not pb.mpn.bilinen:
        # Desenle eslesen bir kaydin MPN'i, sematikteki parcanin MPN'i DEGILDIR
        # (AMS1117-3.3 birden cok ureticide var). Yalnizca bilgi olarak yazilir.
        pb.notlar.append(f"kutuphane kaydi MPN'i {kayit.mpn}; sematikte MPN alani yok")

    for no, p in (ham.get("pinler") or {}).items():
        pin = PinBilgisi(numara=str(no), ad=str(p.get("ad", "")), islev=str(p.get("islev", "")))
        for sad, sham in (p.get("sinirlar") or {}).items():
            pin.sinirlar[sad] = _sinir(sad, sham, kayit.kaynak, g)
        pb.pinler[pin.numara] = pin

    for kural in ham.get("pin_adlari") or []:
        sinirlar = {sad: _sinir(sad, sham, kayit.kaynak, g)
                    for sad, sham in (kural.get("sinirlar") or {}).items()}
        pb.pin_ad_kurallari.append(
            (re.compile(str(kural["desen"]), re.IGNORECASE), str(kural.get("islev", "")), sinirlar))

    for sad, sham in (ham.get("sinirlar") or {}).items():
        pb.sinirlar[sad] = _sinir(sad, sham, kayit.kaynak, g)

    # Parca ADINDAN okunan sinir: "SMBJ5.0A" -> VR = 5.0 V. Ureticinin
    # adlandirma kuralidir (seri veri sayfasinda tanimli), tahmin degil.
    for kural in ham.get("addan_sinirlar") or []:
        hedef = pb.deger.deger if isinstance(pb.deger.deger, str) else ""
        m = re.search(str(kural["desen"]), hedef, re.IGNORECASE)
        if m:
            sayi = float(m.group(1)) * float(kural.get("carpan", 1.0))
            # tur: nominal -> deger hem alt hem ust (sabit cikis gerilimi gibi)
            alt = sayi if kural.get("tur") == "nominal" else None
            pb.sinirlar[str(kural["sinir"])] = Sinir(
                str(kural["sinir"]), str(kural.get("birim", "")),
                onerilen_min=alt, onerilen_max=sayi, kosul=str(kural.get("kosul", "")),
                kaynak=f"{kayit.kaynak} (parca adindan)", guven=g)

    # Paket tablosu: genel kayitlar (0603 direnc) sinirlari pakete gore verir.
    tablo = ham.get("paket_tablosu") or {}
    if tablo:
        satir = tablo.get(paket)
        if satir is None:
            pb.notlar.append(
                f"paket {paket or '?'} genel kaydin tablosunda yok ({kayit.anahtar})")
        else:
            paket_guven = g if pb.mpn_cozumu else "paket-tipik"
            for sad, sham in satir.items():
                if sad in _PAKET_OZEL:
                    continue
                pb.sinirlar[sad] = _sinir(sad, sham, kayit.kaynak, paket_guven)

    termal = dict(ham.get("termal") or {})
    if tablo and tablo.get(paket):
        termal.update(tablo[paket].get("termal") or {})
    for tad, tdeger in termal.items():
        pb.termal[tad] = bilinen(tdeger, kayit.kaynak, g)
    if tablo and tablo.get(paket):
        _paket_ozel_uygula(pb, kayit, tablo[paket], g, paket)
    if ham.get("tolerans_siniflari"):
        _tolerans_sinifi_uygula(pb, kayit, g)

    if ham.get("soa"):
        pb.soa = bilinen(ham["soa"], kayit.kaynak, g)
    if ham.get("sicaklik_katsayisi") is not None:
        pb.sicaklik_katsayisi = bilinen(ham["sicaklik_katsayisi"], kayit.kaynak, g)
    if ham.get("yaslanma") is not None:
        pb.yaslanma = bilinen(ham["yaslanma"], kayit.kaynak, g)
    for not_ in ham.get("notlar") or []:
        pb.notlar.append(str(not_))

    sp = ham.get("spice")
    if sp:
        # "@ad" parametresi parcanin siniri ile cozulur (@vout -> vout orta
        # degeri). Cozulemeyen parametre modeli EKSIK yapar - uydurulmaz.
        parametreler: dict[str, Any] = {}
        for pad, pdeger in (sp.get("parametreler") or {}).items():
            if isinstance(pdeger, str) and pdeger.startswith("@"):
                s = pb.sinirlar.get(pdeger[1:])
                if s is None or (s.onerilen_max is None and s.onerilen_min is None):
                    pb.spice_eksik = f"SPICE modeli parametresi {pad} icin {pdeger[1:]} bilinmiyor"
                    return
                degerler = [v for v in (s.onerilen_min, s.onerilen_max) if v is not None]
                parametreler[pad] = sum(degerler) / len(degerler)
            else:
                parametreler[pad] = pdeger
        sp = dict(sp, parametreler=parametreler)
        pb.spice = SpiceModeli(
            tur=str(sp.get("tur", "davranissal")),
            ad=str(sp.get("ad", "")),
            metin=str(sp.get("metin", "")),
            dugumler=[str(d) for d in sp.get("dugumler") or []],
            pin_esleme={str(k): str(v) for k, v in (sp.get("pin_esleme") or {}).items()},
            parametreler=dict(sp.get("parametreler") or {}),
            kaynak=str(sp.get("kaynak") or kayit.kaynak),
            lisans=str(sp.get("lisans", "")),
            ideal=bool(sp.get("ideal", sp.get("tur") == "davranissal")),
        )
    elif ham.get("spice_eksik"):
        pb.spice_eksik = str(ham["spice_eksik"])


_MPN_DEGER_RE = re.compile(r"^([0-9]+)([RKM]?)([0-9]*)$")
_CARPAN = {"R": 1.0, "K": 1e3, "M": 1e6, "": 1.0}


def mpn_deger_kodu(kod: str) -> float | None:
    """RC_L deger kodu: '97R6' 97.6, '9K76' 9760, '1M' 1e6, '100R' 100, '10K' 1e4."""
    m = _MPN_DEGER_RE.match(kod)
    if not m:
        return None
    tam, harf, kesir = m.groups()
    return float(f"{tam}.{kesir or 0}") * _CARPAN[harf]


RC_L_TOLERANS_KODU = {0.001: "B", 0.005: "D", 0.01: "F", 0.05: "J"}
RC_L_PAKETLER = ("0201", "0402", "0603", "0805", "1206", "1210", "2010", "2512")


def e_serisinde(r: float, seri: str) -> bool:
    from .. import eseri

    return abs(eseri.nearest(r, seri) - r) <= 1e-6 * r


def rc_l_siparis_kodu(paket: str, tolerans: float, ohm: float) -> str | None:
    """Yageo RC_L "GLOBAL PART NUMBER" kurali (V.10, s.2): RC + boyut +
    tolerans + ambalaj + '-' + makara + deger + 'L'. Ambalaj: 0201-1210 kagit
    (R), 2010/2512 kabartmali (K) - Tablo 3'te yalnizca bu ambalajlar var.
    Deger kodu: harf ondalik noktadir (9K76 = 9760 ohm). Katalogda olmayan
    (tolerans/paket/E serisi) birlesim icin None - kod UYDURULMAZ; aralik ve
    E serisi denetimi parca_bilgisi'nde (katalog_disi)."""
    kod = next((k for t, k in RC_L_TOLERANS_KODU.items() if abs(t - tolerans) < 1e-12), None)
    if kod is None or paket not in RC_L_PAKETLER or ohm <= 0:
        return None
    if kod == "J" and not e_serisinde(ohm, "E24"):
        return None
    if kod != "J" and not (e_serisinde(ohm, "E24") or e_serisinde(ohm, "E96")):
        return None
    for carpan, harf in ((1e6, "M"), (1e3, "K"), (1.0, "R")):
        if ohm >= carpan or harf == "R":
            v = f"{ohm / carpan:.3g}"
            if "e" in v:
                return None
            tam, _, kesir = v.partition(".")
            deger = f"{tam}{harf}{kesir}" if kesir else (f"{tam}{harf}")
            break
    ambalaj = "K" if paket in ("2010", "2512") else "R"
    return f"RC{paket}{kod}{ambalaj}-07{deger}L"


def _mpn_coz(pb: ParcaBilgisi, kayit: KutuphaneKaydi, m: re.Match, sayisal: float | None) -> None:
    """Siparis kodundan paket / tolerans / deger; sembol alanlariyla celiski."""
    paket, tkod, _ambalaj, _makara, dkod = m.groups()
    sinif = next((c for c in kayit.ham.get("tolerans_siniflari") or [] if c.get("kod") == tkod), None)
    tol = float(sinif["tolerans"]) if sinif else None
    r = mpn_deger_kodu(dkod)
    pb.mpn_cozumu = {"paket": paket, "tolerans_kodu": tkod, "tolerans": tol, "deger": r, "kayit": kayit.anahtar}
    if tol is not None:
        if pb.tolerans.bilinen and abs(float(pb.tolerans.deger) - tol) > 1e-12:
            pb.celiskiler.append(f"tolerans: sembolde %{float(pb.tolerans.deger) * 100:g}, MPN'de %{tol * 100:g}")
        elif not pb.tolerans.bilinen:
            pb.tolerans = bilinen(tol, f"MPN tolerans kodu {tkod} ({kayit.kaynak})", kayit.guven)
    if r is not None and sayisal is not None and abs(r - sayisal) > 1e-9 * max(r, sayisal):
        pb.celiskiler.append(f"deger: sembolde {sayisal:g}, MPN'de {r:g} ohm")
    for c in pb.celiskiler:
        pb.notlar.append(f"MPN CELISKISI: {c}")


def parca_bilgisi(
    *,
    tur: str,
    deger: str,
    footprint: str = "",
    libpart: str = "",
    lib_id: str = "",
    alanlar: dict[str, str] | None = None,
    kutuphane: Kutuphane | None = None,
) -> ParcaBilgisi:
    """Bir bilesen ornegi icin parca bilgisini toplar.

    `tur` model.ref_kind degeridir ("resistor", "ic"...). `alanlar` sembolun
    alanlari (netlist <fields> ya da sematik ozellikleri).
    """
    kutuphane = kutuphane if kutuphane is not None else varsayilan_kutuphane()
    alanlar = dict(alanlar or {})
    paket = paket_kodu(footprint)
    pb = ParcaBilgisi(kategori=_TUR_KATEGORI.get(tur, "genel"), paket=paket)

    sentetik = (alanlar.get("MPN_Kaynak") or "").lower().startswith("sentetik")

    # 1) Sembol alanlari
    hit = _alan(alanlar, _ALAN_MPN)
    if hit:
        pb.mpn = bilinen(hit[1], f"sembol alani {hit[0]}",
                         "sentetik" if sentetik or hit[1].upper().startswith("SENT-") else "beyan")
    hit = _alan(alanlar, _ALAN_URETICI)
    if hit:
        pb.uretici = bilinen(hit[1], f"sembol alani {hit[0]}", "sentetik" if sentetik else "beyan")
    hit = _alan(alanlar, _ALAN_TOLERANS)
    if hit:
        tol = tolerans_metinden(hit[1] if "%" in hit[1] else hit[1] + "%")
        if tol is not None:
            pb.tolerans = bilinen(tol, f"sembol alani {hit[0]}", "beyan")
    if not pb.tolerans.bilinen:
        tol = tolerans_metinden(" ".join(deger.split()[1:]))
        if tol is not None:
            pb.tolerans = bilinen(tol, "deger metni", "beyan")
        else:
            pb.tolerans = eksik("tolerans alani yok, deger metninde de yazmiyor")

    sayisal = parse_value(deger)
    if sayisal is not None and tur in ("resistor", "capacitor", "inductor"):
        pb.deger = bilinen(sayisal, "deger alani", "beyan")
    elif deger:
        pb.deger = bilinen(deger, "deger alani", "beyan")

    # Derecelendirmeler: sembol alani ya da deger metni ("100nF 50V")
    hit = _alan(alanlar, _ALAN_GERILIM)
    v_ham = parse_value(hit[1].rstrip("Vv")) if hit else gerilim_metinden(deger)
    if v_ham is not None:
        nereden = f"sembol alani {hit[0]}" if hit else "deger metni"
        pb.sinirlar["gerilim"] = Sinir("gerilim", "V", onerilen_max=v_ham, mutlak_max=v_ham,
                                        kosul="parcanin anma gerilimi", kaynak=nereden, guven="beyan")
    hit = _alan(alanlar, _ALAN_GUC)
    p_ham = guc_metinden("x " + hit[1]) if hit else guc_metinden(deger)
    if p_ham is not None:
        nereden = f"sembol alani {hit[0]}" if hit else "deger metni"
        pb.sinirlar["guc"] = Sinir("guc", "W", onerilen_max=p_ham, mutlak_max=p_ham,
                                    kosul="anma gucu", kaynak=nereden, guven="beyan")

    hit = _alan(alanlar, _ALAN_AKIM)
    a_ham = akim_metinden(hit[1]) if hit else (akim_metinden(deger) if tur == "fuse" else None)
    if a_ham is not None:
        nereden = f"sembol alani {hit[0]}" if hit else "deger metni"
        pb.sinirlar["akim"] = Sinir("akim", "A", onerilen_max=a_ham, kosul="anma akimi",
                                     kaynak=nereden, guven="beyan")

    m = _DIELEKTRIK_RE.search(deger)
    if m:
        kod = m.group(1).upper()
        pb.notlar.append(f"dielektrik {kod} (deger metninden)")
        tk = dielektrik_sicaklik(kod)
        if tk is not None:
            pb.sicaklik_katsayisi = bilinen(tk, f"EIA RS-198 dielektrik kodu {kod}", "turetilmis")

    # 2-4) Kutuphane
    kayit = None
    if pb.mpn.bilinen and pb.mpn.guven != "sentetik":
        kayit = kutuphane.mpn_ile(str(pb.mpn.deger))
        if kayit is not None:
            # MPN ile TAM eslesme: kaydin verisi bu parcanindir.
            _kayit_uygula(pb, kayit, paket)
            pb.dogrulama = kayit.guven
    if kayit is None and pb.mpn.bilinen and pb.mpn.guven != "sentetik":
        bulunan = kutuphane.mpn_deseni_ile(str(pb.mpn.deger))
        if bulunan is not None:
            kayit, m = bulunan
            _mpn_coz(pb, kayit, m, sayisal)
            _kayit_uygula(pb, kayit, pb.mpn_cozumu["paket"])
            pb.dogrulama = kayit.guven
    if kayit is None:
        kayit = kutuphane.desen_ile(deger, libpart, lib_id)
        if kayit is not None:
            # Kullanicinin yazdigi sinirlar (sembol alani) kaydi ezmesin
            beyan = dict(pb.sinirlar)
            _kayit_uygula(pb, kayit, paket)
            pb.sinirlar.update(beyan)
    if kayit is None:
        kayit = kutuphane.genel(tur)
        if kayit is not None:
            beyan = dict(pb.sinirlar)
            _kayit_uygula(pb, kayit, paket)
            pb.sinirlar.update(beyan)
            # Genel eslesme: gercek parca bu seri olmayabilir
            if kayit.ham.get("guven_genel"):
                pb.dogrulama = str(kayit.ham["guven_genel"])

    # Pasiflerin SPICE modeli SPICE'in kendisidir - eksik degil.
    if pb.spice is None and pb.kategori in ("direnc", "kondansator", "induktor") \
            and pb.deger.bilinen and isinstance(pb.deger.deger, float):
        harf = {"direnc": "R", "kondansator": "C", "induktor": "L"}[pb.kategori]
        pb.spice = SpiceModeli(tur="primitif", ad=harf, pin_esleme={"1": "1", "2": "2"},
                               dugumler=["1", "2"], kaynak="SPICE ilkel eleman",
                               lisans="-", ideal=False)
    return pb
