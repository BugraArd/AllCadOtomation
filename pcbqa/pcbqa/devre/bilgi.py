"""Bir bilginin degeri, KAYNAGI ve guveni - ya da neden bilinmedigi.

Devre grafindaki her sayi bu kalibi tasir. Uc durum vardir ve karistirilmaz:

  * bilinen     : deger + kaynak ("AMS1117 veri sayfasi", "sembol alani MPN")
  * eksik       : deger yok + NEDEN ("tolerans alani yok, deger metninde de yok")
  * guven       : bilinen degerin ne kadar parcaya ozgu oldugu

Guven seviyeleri (yuksekten dusuge):
  parcaya-ozel   tam parca numarasinin veri sayfasindan
  beyan          kullanicinin kosullar dosyasinda yazdigi
  turetilmis     baska bilinenlerden hesaplandi (Ohm yasasi, ray adi)
  paket-tipik    ayni paket/aile icin tipik veri sayfasi degeri; tam parca
                 bilinmiyor
  dogrulanmamis  veri sayfasindan elle aktarildi ama sayfa referansiyla
                 teyit edilmedi
  sentetik       test verisi (mpn.py) - GERCEK SANILMAMALI
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

GUVENLER = (
    "parcaya-ozel",
    "beyan",
    "turetilmis",
    "paket-tipik",
    "dogrulanmamis",
    "sentetik",
)


@dataclass(frozen=True)
class Bilgi:
    deger: Any = None
    kaynak: str = ""
    eksik_neden: str = ""
    guven: str = ""

    @property
    def bilinen(self) -> bool:
        return self.deger is not None

    def veya(self, diger: "Bilgi") -> "Bilgi":
        """Bu bilinmiyorsa digeri; ikisi de eksikse nedenler birlesir."""
        if self.bilinen:
            return self
        if diger.bilinen:
            return diger
        nedenler = [n for n in (self.eksik_neden, diger.eksik_neden) if n]
        return Bilgi(eksik_neden="; ".join(dict.fromkeys(nedenler)))

    def metin(self, birim: str = "") -> str:
        if not self.bilinen:
            return "-"
        if isinstance(self.deger, float):
            return f"{self.deger:g}{(' ' + birim) if birim else ''}"
        return f"{self.deger}{(' ' + birim) if birim else ''}"

    def as_dict(self) -> dict[str, Any]:
        if self.bilinen:
            out: dict[str, Any] = {"deger": self.deger, "kaynak": self.kaynak}
            if self.guven:
                out["guven"] = self.guven
            return out
        return {"deger": None, "eksik": self.eksik_neden or "bilinmiyor"}


def bilinen(deger: Any, kaynak: str, guven: str = "parcaya-ozel") -> Bilgi:
    if deger is None:
        raise ValueError("bilinen() None alamaz; eksik() kullanin")
    if guven and guven not in GUVENLER:
        raise ValueError(f"bilinmeyen guven seviyesi: {guven!r}")
    return Bilgi(deger=deger, kaynak=kaynak, guven=guven)


def eksik(neden: str) -> Bilgi:
    return Bilgi(eksik_neden=neden)
