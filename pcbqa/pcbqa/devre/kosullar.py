"""Calisma kosullari ve tasarim gereksinimleri beyani.

Bir devrenin dogru olup olmadigi, NE ICIN tasarlandigina baglidir: ayni
AMS1117, 5 V girisle 100 mA'de serin calisir, 12 V girisle 300 mA'de
yanar. Bu bilgiler tasarim dosyasinda YOKTUR - kullanici beyan eder.

    version: 1
    ortam_c: 25
    raylar:                    # ag adi -> gerilim (V) ya da {nom, min, max}
      VBUS: {nom: 12, min: 11.4, max: 12.6}
    kaynaklar: [VBUS]          # benzetimde gerilim kaynagi olan aglar
    yukler:
      - ag: 3V3
        akim_a: 0.3            # surekli / RMS
        tepe_a: 0.5            # istege bagli
        darbe_s: 0.002         # tepe akimin suresi
        ref: U2                # istege bagli: akimi ceken pin
        pin: "1"
    gereksinimler:
      - {ag: 3V3, min_v: 3.2, max_v: 3.4}
      - {ref: U1, tj_max_c: 110}
    pcb:
      bakir_oz: 1.0            # dis katman
      ic_bakir_oz: 0.5
      dT_c: 10                 # izin verilen iz sicaklik artisi
      izin_dV_yuzde: 2.0       # rayin yuzdesi olarak izin verilen iz dusumu
      kart_kalinligi_mm: 1.6
      kaplama_um: 20           # via namlu kaplamasi
      uretici: standart        # ipc2221.FAB_CLASSES anahtari
    analiz:
      monte_carlo: 50
      sicakliklar: [-40, 25, 85]
      yaslanma_saat: 50000

Beyan edilmeyen alan None kalir; ona ihtiyac duyan kontrol bunu "eksik
beyan" diye raporlar, varsayilan uydurmaz. Tek istisna `pcb` blogundaki
uretim varsayilanlari: bunlar ipc2221.py'nin zaten kullandigi, kaynagi yazili
degerlerdir (1 oz, 10 C) ve raporda "varsayilan" diye isaretlenir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..confload import ConfigError, load_config


class KosulHatasi(ValueError):
    """Kosullar dosyasi sozlesmeye uymuyor."""


def ag_anahtari(ad: str) -> str:
    """Ag adlarini karsilastirilabilir yapar: "/3V3" == "3V3" == "+3v3"?

    Yalnizca hiyerarsi oneki ve buyuk/kucuk harf normalize edilir. "+3V3"
    ile "3V3" FARKLI kalir - KiCad'de ikisi ayri ag olabilir.
    """
    return (ad or "").strip().lstrip("/").upper()


@dataclass(frozen=True)
class Ray:
    ad: str
    nom: float
    min: float | None = None
    max: float | None = None

    @property
    def en_yuksek(self) -> float:
        return self.max if self.max is not None else self.nom

    @property
    def en_dusuk(self) -> float:
        return self.min if self.min is not None else self.nom


@dataclass(frozen=True)
class Yuk:
    ag: str
    akim_a: float
    tepe_a: float | None = None
    darbe_s: float | None = None
    ref: str | None = None
    pin: str | None = None

    @property
    def tepe(self) -> float:
        return self.tepe_a if self.tepe_a is not None else self.akim_a


@dataclass(frozen=True)
class Gereksinim:
    ag: str | None = None
    ref: str | None = None
    min_v: float | None = None
    max_v: float | None = None
    tj_max_c: float | None = None
    dalgalanma_mv: float | None = None


# ipc2221.py'nin kendi varsayilanlari; raporda "varsayilan" diye gosterilir.
PCB_VARSAYILAN: dict[str, Any] = {
    "bakir_oz": 1.0,
    "ic_bakir_oz": 0.5,
    "dT_c": 10.0,
    "izin_dV_yuzde": None,      # beyan yoksa dV kontrolu yapilmaz
    "kart_kalinligi_mm": 1.6,   # standart FR-4 kalinligi
    # IPC-6012 Class 2: delik duvari ortalama en az 20 um bakir
    "kaplama_um": 20.0,
    "uretici": "standart",
}


@dataclass
class Kosullar:
    ortam_c: float | None = None
    raylar: dict[str, Ray] = field(default_factory=dict)
    kaynaklar: list[str] = field(default_factory=list)
    yukler: list[Yuk] = field(default_factory=list)
    gereksinimler: list[Gereksinim] = field(default_factory=list)
    pcb: dict[str, Any] = field(default_factory=lambda: dict(PCB_VARSAYILAN))
    # Kullanicinin acikca yazdigi pcb anahtarlari (varsayilandan ayirmak icin)
    pcb_beyan: set[str] = field(default_factory=set)
    analiz: dict[str, Any] = field(default_factory=dict)
    yol: Path | None = None

    def ray(self, ag: str) -> Ray | None:
        anahtar = ag_anahtari(ag)
        for ad, ray in self.raylar.items():
            if ag_anahtari(ad) == anahtar:
                return ray
        return None

    def kaynak_mi(self, ag: str) -> bool:
        anahtar = ag_anahtari(ag)
        return any(ag_anahtari(k) == anahtar for k in self.kaynaklar)

    def yukler_on(self, ag: str) -> list[Yuk]:
        anahtar = ag_anahtari(ag)
        return [y for y in self.yukler if ag_anahtari(y.ag) == anahtar]

    def gereksinim_ag(self, ag: str) -> Gereksinim | None:
        anahtar = ag_anahtari(ag)
        for g in self.gereksinimler:
            if g.ag and ag_anahtari(g.ag) == anahtar:
                return g
        return None

    def gereksinim_ref(self, ref: str) -> Gereksinim | None:
        for g in self.gereksinimler:
            if g.ref == ref:
                return g
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ortam_c": self.ortam_c,
            "raylar": {k: vars(v) for k, v in self.raylar.items()},
            "kaynaklar": list(self.kaynaklar),
            "yukler": [vars(y) for y in self.yukler],
            "gereksinimler": [vars(g) for g in self.gereksinimler],
            "pcb": dict(self.pcb),
            "pcb_beyan": sorted(self.pcb_beyan),
            "analiz": dict(self.analiz),
        }


def _sayi(deger: Any, yer: str) -> float:
    try:
        return float(deger)
    except (TypeError, ValueError) as exc:
        raise KosulHatasi(f"{yer}: sayi bekleniyordu ({deger!r})") from exc


def _sayi_veya_none(deger: Any, yer: str) -> float | None:
    return None if deger is None else _sayi(deger, yer)


def kosullari_ayristir(data: dict[str, Any], yol: Path | None = None) -> Kosullar:
    if not isinstance(data, dict):
        raise KosulHatasi("kosullar kok nesnesi bir mapping olmali")
    if data.get("version", 1) != 1:
        raise KosulHatasi(f"version: 1 bekleniyor ({data.get('version')!r})")

    k = Kosullar(yol=yol)
    k.ortam_c = _sayi_veya_none(data.get("ortam_c"), "ortam_c")

    for ad, ham in (data.get("raylar") or {}).items():
        yer = f"raylar.{ad}"
        if isinstance(ham, dict):
            if "nom" not in ham:
                raise KosulHatasi(f"{yer}: nom zorunlu")
            ray = Ray(str(ad), _sayi(ham["nom"], yer),
                      _sayi_veya_none(ham.get("min"), yer),
                      _sayi_veya_none(ham.get("max"), yer))
        else:
            ray = Ray(str(ad), _sayi(ham, yer))
        if ray.min is not None and ray.max is not None and ray.min > ray.max:
            raise KosulHatasi(f"{yer}: min > max")
        k.raylar[str(ad)] = ray

    k.kaynaklar = [str(a) for a in (data.get("kaynaklar") or [])]

    for i, ham in enumerate(data.get("yukler") or []):
        yer = f"yukler[{i}]"
        if not isinstance(ham, dict) or "ag" not in ham or "akim_a" not in ham:
            raise KosulHatasi(f"{yer}: ag ve akim_a zorunlu")
        yuk = Yuk(
            ag=str(ham["ag"]),
            akim_a=_sayi(ham["akim_a"], yer),
            tepe_a=_sayi_veya_none(ham.get("tepe_a"), yer),
            darbe_s=_sayi_veya_none(ham.get("darbe_s"), yer),
            ref=str(ham["ref"]) if ham.get("ref") is not None else None,
            pin=str(ham["pin"]) if ham.get("pin") is not None else None,
        )
        if yuk.akim_a < 0:
            raise KosulHatasi(f"{yer}: akim_a negatif olamaz")
        k.yukler.append(yuk)

    for i, ham in enumerate(data.get("gereksinimler") or []):
        yer = f"gereksinimler[{i}]"
        if not isinstance(ham, dict):
            raise KosulHatasi(f"{yer}: mapping bekleniyordu")
        k.gereksinimler.append(Gereksinim(
            ag=str(ham["ag"]) if ham.get("ag") is not None else None,
            ref=str(ham["ref"]) if ham.get("ref") is not None else None,
            min_v=_sayi_veya_none(ham.get("min_v"), yer),
            max_v=_sayi_veya_none(ham.get("max_v"), yer),
            tj_max_c=_sayi_veya_none(ham.get("tj_max_c"), yer),
            dalgalanma_mv=_sayi_veya_none(ham.get("dalgalanma_mv"), yer),
        ))

    pcb = data.get("pcb") or {}
    bilinmeyen = set(pcb) - set(PCB_VARSAYILAN)
    if bilinmeyen:
        raise KosulHatasi(f"pcb: bilinmeyen alan(lar) {sorted(bilinmeyen)}")
    for anahtar, deger in pcb.items():
        k.pcb[anahtar] = deger if anahtar == "uretici" else _sayi_veya_none(deger, f"pcb.{anahtar}")
        k.pcb_beyan.add(anahtar)

    k.analiz = dict(data.get("analiz") or {})
    return k


def kosullari_oku(yol: Path | str) -> Kosullar:
    yol = Path(yol)
    try:
        data, _ = load_config(yol)
    except ConfigError as exc:
        raise KosulHatasi(f"kosullar okunamadi: {exc}") from exc
    return kosullari_ayristir(data, yol)
