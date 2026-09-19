"""DOGAL DIL KOMUTU -> somut ekleme islemi (Asama 4g).

    pcbqa yap "10 adet kapasitor ekle"
    pcbqa yap "5 tane 100nF 0603 kondansator ve 3 direnc koy" --uygula
    pcbqa yap "10 adet 100nF kapasitor ekle ve hepsini VCC-GND arasina bagla"

## Neden ayri bir katman

Alt katmanlarin hepsi hazirdi: `sch_add.add_symbols(sch, "Device:C", 10)`
sembolu kutuphaneden getirir, sayfada bos yer bulur, netlist kalkanini
calistirir, yedek alir, atomik yazar. Eksik olan tek sey CUMLEYI o cagriya
cevirmekti. Bu modul yalnizca onu yapar; hicbir dosyayi kendisi yazmaz.

## Neden modelsiz (regex + sozluk), LLM degil

Uc olculmus kisit:

  * `pcbqa`nin calisma zamani bagimliligi YOKTUR (bkz. `confload.py`) ve
    KiCad'in kendi Python'unda kosar. Bir model istemcisi bunu bozardi.
  * Testler sessizligi korur; ayni cumle her kosuda ayni plani uretmeli.
  * "Basit gorev" dagarcigi KAPALI bir kume: fiil, adet, bilesen turu,
    deger, paket. Kapali kume icin cozumleyici hem daha dogru hem hesapsiz.

Yine de cikti (`Yorum`) TIPLI bir sozlesmedir: ileride bir model cumleyi
dogrudan `Eylem` listesine cevirebilir, asagidaki uygulayici degismez.

## Anlasilmayan sey GORUNUR

Projenin geri kalaninda oldugu gibi burada da sessiz tahmin yok:

  * bilinmeyen fiil        -> ENGEL (bu surum ekler ve eklerken baglar)
  * bilesen turu yoksa     -> ENGEL ("neyi ekleyecegimi anlamadim")
  * belirsiz sozcuk        -> ENGEL, adaylariyla ("transistor": NPN mi PNP mi)
  * eslesmeyen kelimeler   -> NOT olarak dokulur, yutulmaz
  * "bagla" var ama kalip  -> ENGEL (baglantisiz sembol birakmaktansa hic
    yoksa                      eklememek yeglenir)

Deger verilmezse UYDURULMAZ: sembol kutuphanedeki degeriyle eklenir ve bu
bir not olarak yazilir. "Kondansator = 100nF" gibi bir varsayilan, kaynagi
olmadigi icin bu projede kabul edilmez.

## Baglama EKLEME ile ayni cumlede

"... ve hepsini VCC-GND arasina bagla" kalibi `sch_add`in `connect=`
parametresine (PIN=HEDEF) cevrilir ve EKLENEN HER sembole uygulanir. Once
yazilan hedef 1. uca, sonraki 2. uca gider. Kutuplu bilesende (diyot, LED)
bu yon NOT olarak yazilir: cumle yonu SOYLEMEZ, biz de sessizce secmeyiz.
Iki ucu olmayan bir bilesende (toprak sembolu) istek ENGEL'dir - hangi
pinin nereye gidecegi uydurulmaz.

Kalip cumleden EN BASTA ayrilir, ekleme cozumlemesinden once. Iki olculmus
sebep: (1) ayrac "ve"dir, kalip cumlede kalirsa bolucu onu ikiye boler;
(2) "toprak" hem bir AG adi hem bir BILESEN turudur - "VCC ile toprak
arasina" cumlesi sayfaya istenmeyen bir toprak sembolu de eklerdi.

Cumlede birden fazla ekleme varsa "hepsini" gibi bir kapsam sozcugu
SARTTIR: baglamanin hangi gruba ait oldugu tahmin edilmez.

## Ag adinin yazimi tahmin edilmez, SEMATIGE sorulur

Baglanti bir ETIKET yazilarak kurulur ve KiCad'de ag adlari buyuk/kucuk
harfe duyarlidir. "vcc" yazan kullanici "VCC" agina baglanmis olmaz; on
kapasitor bos bir "vcc" adasinda kalir. Netlist kalkani bunu YAKALAMAZ -
yeni bir ag olusturmak da gecerli bir islemdir ve kalkan yalnizca ESKI
devrenin degismedigini olcer. Bu yuzden `uygula` asamasinda hedef adlari
sematikteki gercek yazimla eslenir; eslesmiyorsa acikca uyarilir.

Bu katman yalnizca EKLERKEN baglar. Sayfada zaten duran sembolleri
birbirine baglamak once onlara REFERANSLA konusabilmeyi ister (`C5`,
"son eklediklerim") - ayri bir is, bkz. Kicad-d8f.

Ana giris: `anla(metin)` -> `Yorum`, `uygula(yorum, sch)`.
CLI: `python -m pcbqa.komut`.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import symlib
from .sch_add import AddResult, SchAddError, add_symbols
from .sch_write import SchWriteError
from .schematic import Schematic, read_schematic


class KomutError(RuntimeError):
    """Komut calistirilamadi (hedef sematik bulunamadi gibi)."""


# --------------------------------------------------------------------------
# 1) Dagarcik
# --------------------------------------------------------------------------
#
# TURLER'in `lib_id` alanlari UYDURULMAZ: hepsi KiCad'in standart
# kutuphanesindeki gercek sembollerdir ve `uygula()` her birini calistirma
# aninda `symlib.get_symbol` ile dogrular - kutuphane kurulu degilse ya da
# sembol adi degismisse sessizce yanlis sey eklenmez, engel uretilir.
#
# `paketler` icindeki footprint kimlikleri de ayni bicimde dogrulanir
# (`plan_add` footprint'i arar, bulamazsa ENGEL yazar).

# `uclar`: baglamada kullanilan iki ucun pin NUMARALARIDIR ve SIRASI
# anlamlidir - cumlede ONCE yazilan hedef birinci uca gider. `uc_adlari`
# yalnizca KUTUPLU bilesenlerde doludur; yonu NOT olarak yazdirmaya yarar,
# secimi degistirmez. Iki ucu olmayan tur (toprak sembolu) baglamada ENGEL
# uretir. Numaralar `KutuphaneTests.test_declared_pins_exist` ile gercek
# sembole karsi sinanir; kutupluluk `test_polarity_names_match_the_library`
# ile - KiCad diyot pin sirasini degistirirse NOT sessizce yanlislasmasin.

TURLER: dict[str, dict] = {
    "kapasitor": {
        "ad": "Kondansator",
        "lib_id": "Device:C",
        "uclar": ("1", "2"),
        "paketler": {
            "0402": "Capacitor_SMD:C_0402_1005Metric",
            "0603": "Capacitor_SMD:C_0603_1608Metric",
            "0805": "Capacitor_SMD:C_0805_2012Metric",
            "1206": "Capacitor_SMD:C_1206_3216Metric",
        },
    },
    "kapasitor-polarize": {
        "ad": "Polarize kondansator",
        "lib_id": "Device:C_Polarized",
        "uclar": ("1", "2"),
        # Kutuphane bu sembolde pin ADI vermez (ikisi de bos); isaret govde
        # cizimindedir. KiCad'de pin 1 arti uctur (bkz. Device.kicad_sym).
        "uc_adlari": ("arti (+)", "eksi (-)"),
        "paketler": {},
    },
    "direnc": {
        "ad": "Direnc",
        "lib_id": "Device:R",
        "uclar": ("1", "2"),
        "paketler": {
            "0402": "Resistor_SMD:R_0402_1005Metric",
            "0603": "Resistor_SMD:R_0603_1608Metric",
            "0805": "Resistor_SMD:R_0805_2012Metric",
            "1206": "Resistor_SMD:R_1206_3216Metric",
        },
    },
    "bobin": {"ad": "Bobin", "lib_id": "Device:L",
              "uclar": ("1", "2"), "paketler": {}},
    "diyot": {"ad": "Diyot", "lib_id": "Device:D",
              "uclar": ("1", "2"), "uc_adlari": ("katot (K)", "anot (A)"),
              "paketler": {}},
    "led": {"ad": "LED", "lib_id": "Device:LED",
            "uclar": ("1", "2"), "uc_adlari": ("katot (K)", "anot (A)"),
            "paketler": {}},
    "kristal": {"ad": "Kristal", "lib_id": "Device:Crystal",
                "uclar": ("1", "2"), "paketler": {}},
    "ferrit": {"ad": "Ferrit boncuk", "lib_id": "Device:FerriteBead",
               "uclar": ("1", "2"), "paketler": {}},
    "buton": {"ad": "Buton", "lib_id": "Switch:SW_Push",
              "uclar": ("1", "2"), "paketler": {}},
    # Tek pinli: "arasina" diye bir yeri yok, baglamada ENGEL uretir.
    "toprak": {"ad": "Toprak sembolu", "lib_id": "power:GND",
               "uclar": (), "paketler": {}},
}

# Sozcuk -> tur anahtari. Sol taraf SADELESTIRILMIS bicimdedir (bkz.
# `sadelestir`): "kapasitor" de "KAPASITOR" de buraya "kapasitor" diye duser.
SOZCUKLER: dict[str, str] = {
    "kapasitor": "kapasitor", "kondansator": "kapasitor", "kondansor": "kapasitor",
    "kapasite": "kapasitor", "capacitor": "kapasitor", "cap": "kapasitor",
    "caps": "kapasitor", "kapasitorler": "kapasitor", "kondansatorler": "kapasitor",
    "direnc": "direnc", "direncler": "direnc", "rezistans": "direnc",
    "resistor": "direnc", "resistors": "direnc",
    "bobin": "bobin", "bobinler": "bobin", "induktor": "bobin",
    "inductor": "bobin", "coil": "bobin",
    "diyot": "diyot", "diyotlar": "diyot", "diode": "diyot", "diodes": "diyot",
    "led": "led", "ledler": "led", "leds": "led",
    "kristal": "kristal", "crystal": "kristal", "xtal": "kristal",
    "ferrit": "ferrit", "ferrite": "ferrit", "boncuk": "ferrit",
    "buton": "buton", "butonlar": "buton", "dugme": "buton",
    "switch": "buton", "anahtar": "buton", "button": "buton",
    "gnd": "toprak", "toprak": "toprak", "ground": "toprak",
}

# Turu DEGISTIREN sifatlar: "polarize kapasitor" -> Device:C_Polarized
NITELEYICILER: dict[str, dict[str, str]] = {
    "polarize": {"kapasitor": "kapasitor-polarize"},
    "elektrolitik": {"kapasitor": "kapasitor-polarize"},
    "electrolytic": {"kapasitor": "kapasitor-polarize"},
    "polarized": {"kapasitor": "kapasitor-polarize"},
}

# Tanidigimiz ama TEK BASINA yetmeyen sozcukler. Sessizce bir sembole
# baglamak yerine adaylari sayip soruyoruz - "transistor" deyince NPN mi
# PNP mi MOSFET mi bilinmez ve yanlis secim sematige yazilir.
BELIRSIZ: dict[str, str] = {
    "transistor": "Device:Q_NPN_BCE, Device:Q_PNP_BCE, Device:Q_NMOS_GDS ...",
    "mosfet": "Device:Q_NMOS_GDS, Device:Q_PMOS_GDS ...",
    "konnektor": "Connector_Generic:Conn_01x02, Conn_01x04 ... (kac pin?)",
    "connector": "Connector_Generic:Conn_01x02, Conn_01x04 ... (kac pin?)",
    "header": "Connector_Generic:Conn_01x02, Conn_01x04 ... (kac pin?)",
    "regulator": "Regulator_Linear:AMS1117-3.3 ... (hangi parca?)",
    "mcu": "MCU_ST_STM32F1:STM32F103C8Tx ... (hangi parca?)",
    "islemci": "MCU_ST_STM32F1:STM32F103C8Tx ... (hangi parca?)",
}

# Fiiller. Bu surum EKLER ve eklerken BAGLAR; digerleri taninir ama
# reddedilir ki kullanici "anlamadi" ile "henuz yapmiyorum" arasindaki farki
# gorsun.
EKLE_FIILLERI = {
    "ekle", "ekler", "ekleyelim", "ekleyin", "ekliyelim", "koy", "koyalim",
    "koyun", "yerlestir", "yerlestirelim", "at", "add", "place", "put", "insert",
}
# Baglama fiili TEK BASINA yetmez: bu katman yalnizca EKLERKEN baglar, cunku
# baglanacak sembolleri kendisi uretir. Sayfada zaten duran iki sembolu
# baglamak, once onlara REFERANSLA konusabilmeyi ister (ayri is).
BAGLA_FIILLERI = {
    "bagla", "baglar", "baglayalim", "baglayin", "baglansin", "baglanacak",
    "baglanir", "baglanti", "baglantisi", "connect", "connected", "tie", "tied",
}
# Baglamanin TUM eklenenlere ait oldugunu soyleyen sozcukler. Cumlede birden
# fazla ekleme varsa bunlardan biri SART: hangi gruba ait oldugu tahmin
# edilmez.
KAPSAM_SOZCUKLERI = {
    "hepsini", "hepsi", "hepsine", "tumunu", "tumu", "tamamini", "her birini",
    "herbirini", "ikisini", "all", "each", "both", "them",
}
HENUZ_YOK: dict[str, str] = {
    "sil": "silme", "kaldir": "silme", "delete": "silme", "remove": "silme",
    "tasi": "tasima (bkz. sch_move modulu)",
    "move": "tasima (bkz. sch_move modulu)",
    "degistir": "degistirme", "replace": "degistirme",
}
# Ag adi olmayan ama ag adina cevrilmesi tek anlamli olan sozcukler. Kisa
# tutulur: "besleme" gibi bir sozcugun karsiligi karta gore degisir ve
# uydurulmaz.
AG_ADLARI: dict[str, str] = {"toprak": "GND", "ground": "GND",
                             "sase": "GND", "gnd": "GND"}

# Sayi sozcukleri. Bilesik sayi ("on iki") YOK: kapali kume kucuk kalsin,
# eksigi rakamla yazmak zaten daha kolay.
SAYILAR: dict[str, int] = {
    "bir": 1, "iki": 2, "uc": 3, "dort": 4, "bes": 5, "alti": 6, "yedi": 7,
    "sekiz": 8, "dokuz": 9, "on": 10, "yirmi": 20, "otuz": 30, "kirk": 40,
    "elli": 50, "yuz": 100,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twenty": 20,
}

# Anlam tasimayan ama cumlede bulunmasi dogal olan sozcukler. Bunlar
# "anlasilmadi" listesine dusmez; geri kalan her kelime duser.
# DIKKAT: "on" buraya YAZILMAZ. Ingilizce edat diye eklemek, Turkce'de
# "on adet kapasitor" cumlesindeki SAYIYI yutar - kazanci kaybindan kucuk.
DOLGU = {
    "adet", "tane", "lik", "luk", "adetlik", "ve", "and", "of", "a", "an",
    "the", "su", "suanki", "anki", "simdiki", "mevcut", "current", "bu", "o",
    "model", "modele", "modelimize", "modelimiz", "modeline", "proje", "projeye",
    "projemize", "sema", "semaya", "semada", "sematik", "sematige", "kart",
    "karta", "kartimiza", "devre", "devreye", "board", "schematic", "sheet",
    "sayfaya", "lutfen", "please", "daha", "de", "da", "ile", "with", "to",
    "into", "in", "birer",
}

# --------------------------------------------------------------------------
# 2) Sadelestirme ve bolme
# --------------------------------------------------------------------------
#
# Turkce'nin buyuk/kucuk harf kurali Python'un `lower()`ina uymaz: bizde
# "I" -> "i" degildir ve buyuk noktali I'nin `lower()`i ayri bir
# birlestirici nokta (U+0307) birakir. Bu yuzden once BUYUK Turkce harfler
# ASCII kucuge cevrilir, sonra `lower()` calistirilir.

_BUYUK = str.maketrans({"I": "i", "İ": "i", "Ğ": "g", "Ü": "u",
                        "Ş": "s", "Ö": "o", "Ç": "c"})
_KUCUK = str.maketrans({"ı": "i", "ğ": "g", "ü": "u",
                        "ş": "s", "ö": "o", "ç": "c",
                        "â": "a", "î": "i", "û": "u",
                        "µ": "u", "μ": "u", "̇": ""})


def sadelestir(text: str) -> str:
    """Turkce metni ASCII kucuk harfe indirger (kod ve tablolar ASCII'dir)."""
    return text.translate(_BUYUK).lower().translate(_KUCUK)


# Cumleyi bagimsiz isteklere bolen ayraclar. "5 direnc VE 3 kapasitor ekle"
# tek fiille iki ayri ekleme demektir. Virgul yalnizca SAYILAR ARASINDA
# DEGILSE ayractir: Turkce ondalik ayraci da virguldur ve "4,7k" bolunurse
# geriye anlamsiz iki parca kalir.
_AYRAC = re.compile(
    r"\s+ve\s+|\s+and\s+|\s+arti\s+|\s*(?<!\d)[,;](?!\d)\s*|\s*\+\s*",
    re.IGNORECASE,
)
_KELIME = re.compile(r"\S+")
_TEMIZ = re.compile(r"^[\"'(\[]+|[\"')\].!?:,;]+$")


# Turkce eklemeli bir dildir: "kapasitor", "kapasitorler", "kapasitoru",
# "kapasitorden" hepsi ayni sozcuktur ve hepsini tabloya yazmak tabloyu
# okunmaz eder. Kirpma kurali `lexicon.normalize_designator` ile AYNI: kirpma
# YALNIZCA sonucu tabloda TANIMLI bir sozcuge dusuruyorsa kabul edilir,
# boylece gercekten bilmedigimiz bir kelime sessizce bir bilesene baglanmaz.
_EKLER = ("lerini", "larini", "leri", "lari", "ler", "lar", "den", "dan",
          "nin", "nun", "in", "un", "yi", "yu", "de", "da", "es", "s",
          "i", "u", "e", "a")


def _kok(sade: str, tablo) -> str:
    """Sozcugun tabloda karsiligi olan kokunu doner; yoksa bos dizge."""
    if sade in tablo:
        return sade
    for ek in _EKLER:
        if len(sade) > len(ek) + 2 and sade.endswith(ek):
            govde = sade[: -len(ek)]
            if govde in tablo:
                return govde
    return ""


def _kelimeler(parca: str) -> list[tuple[str, str]]:
    """(ham, sade) ciftleri. Ham gerekli: "10M" ile "10m" ayri seylerdir."""
    out: list[tuple[str, str]] = []
    for kelime in _KELIME.findall(parca):
        ham = _TEMIZ.sub("", kelime)
        if ham:
            out.append((ham, sadelestir(ham)))
    return out


# --------------------------------------------------------------------------
# 2b) Baglama kalibinin cumleden ayrilmasi
# --------------------------------------------------------------------------
#
# Baglama kalibi cumleden ONCE ayrilir, ekleme cozumlemesinden once. Iki
# olculmus sebep:
#
#   * Ayrac "ve"dir: "VCC ve GND arasina" cumlenin ortasinda kalirsa
#     `_AYRAC` onu ikiye boler ve iki yarim istek ortaya cikar.
#   * "toprak" hem bir AG adi hem de bir BILESEN turudur (power:GND).
#     "VCC ile toprak arasina bagla" cumlesinde kalip ayrilmazsa sayfaya
#     istenmeyen bir toprak sembolu de eklenir.
#
# Hedefler HAM metinden alinir: ag adlari buyuk/kucuk harfe duyarlidir,
# KiCad'de "VCC" ile "vcc" ayri iki agdir.


def _kelime_deseni(kelimeler) -> re.Pattern:
    """Sozcuk kumesinden tek bir sinir-duyarli desen (tek kaynak, tek tablo)."""
    parcalar = sorted(
        (re.escape(k).replace(r"\ ", r"\s+") for k in kelimeler),
        key=len, reverse=True,
    )
    return re.compile(r"\b(?:" + "|".join(parcalar) + r")\b")


_BAGLA_FIIL = _kelime_deseni(BAGLA_FIILLERI)
_KAPSAM = _kelime_deseni(KAPSAM_SOZCUKLERI)
_BAGLA_ARTIK = _kelime_deseni(BAGLA_FIILLERI | KAPSAM_SOZCUKLERI)

# "<A> ile <B> arasina" / "<A>-<B> arasinda" / "between <A> and <B>".
# `[^\s,;]+` bir hedefi bosluga kadar alir; tire ayraci yalnizca baska turlu
# eslesme olmadiginda kullanilir (regex acgozludur), boylece "CLOCK-RB6 ile
# DATA-RB7 arasina" cumlesinde ag adlarindaki tireler bolunmez.
# Turkce iki harf koda ASCII kacisiyla girer (kural: kod ASCII'dir).
_NOKTASIZ_I = "\u0131"   # "arasina" TR klavyede "aras" + noktasiz i + "na"
_TIRNAKLAR = "'\u2019"  # duz ve egri kesme isareti

_HEDEF = r"[^\s,;]+"
_ARASINA = re.compile(
    rf"(?P<a>{_HEDEF})"
    r"(?P<ayrac>\s+(?:ile|ve|and|with)\s+|\s*[-/]\s*)"
    rf"(?P<b>{_HEDEF})\s+aras[i{_NOKTASIZ_I}]n(?:a|da)\b"
)
_BETWEEN = re.compile(
    rf"\bbetween\s+(?P<a>{_HEDEF})"
    r"(?P<ayrac>\s+(?:and|ve)\s+|\s*[-/]\s*)"
    rf"(?P<b>{_HEDEF})"
)

# Bir bilesen referansi ("C5", "R1.2") ag adi DEGILDIR. Sessizce "C5" adinda
# bir etiket yazmak, kullanicinin kastettigi seyin tam tersidir.
_REFERANS = re.compile(r"^[A-Za-z]{1,3}\d+(?:\.\w+)?$")
# KiCad ag adlarinda gecen isaretler: +3V3, VCC_PIC, 3.3V, /BUS/CLK, ~RESET.
_AG_ADI = re.compile(r"^[A-Za-z0-9_+\-./~{}]+$")

# Uzunlugu KORUYAN sadelestirme icin: `_KUCUK`un birlestirici-nokta SILEN
# girdisi burada yoktur, cunku eslesme indisleri ham metne uymalidir.
_HIZALI = str.maketrans({"ı": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o",
                         "ç": "c", "â": "a", "î": "i", "û": "u",
                         "µ": "u", "μ": "u"})


def _hizali_sade(metin: str) -> str:
    """Sadelestirilmis ama HAM metinle ayni uzunlukta kopya.

    Kalip aramasi sadelestirilmis metinde yapilir ("ARASINA", "arasina"
    ve noktasiz i'li yazim ayni seydir), ama hedef adlari HAM metinden
    kesilir. Bunun icin indislerin kaymamasi sarttir; kaydigi ender durumda
    ham metne dusuruz (kalip yine de cogu yazimda tutar).
    """
    sade = metin.translate(_BUYUK).lower().translate(_HIZALI)
    return sade if len(sade) == len(metin) else metin


def _spanlari_cikar(metin: str, spans: list[tuple[int, int]]) -> str:
    """Verilen araliklari metinden atar, kalani tek boslukla birlestirir."""
    birlesik: list[list[int]] = []
    for bas, son in sorted(spans):
        if birlesik and bas <= birlesik[-1][1]:
            birlesik[-1][1] = max(birlesik[-1][1], son)
        else:
            birlesik.append([bas, son])
    parcalar: list[str] = []
    imlec = 0
    for bas, son in birlesik:
        parcalar.append(metin[imlec:bas])
        imlec = son
    parcalar.append(metin[imlec:])
    kalan = " ".join(p.strip() for p in parcalar if p.strip())
    # Kalip cikinca ortada asili kalan ayraclar ("... ekle ve", "..., ")
    # bolucuye takilip bos istek uretmesin.
    kalan = re.sub(r"(?:\s|[,;+]|\bve\b|\band\b|\barti\b)+$", "", kalan)
    return re.sub(r"^(?:\s|[,;+]|\bve\b|\band\b)+", "", kalan).strip()


# Cumlenin YAPI sozcukleri hedef olamaz. Olculmus hata: "2 diyot ekle ve
# VCC-GND arasina bagla" cumlesinde ayrac " ve " oldugu icin kalip en soldan
# eslesti ve hedefler ("ekle", "VCC-GND") diye okundu - iki diyotun ucuna
# "ekle" adinda bir ag yazilacakti. Bilesen sozcukleri BURAYA GIRMEZ: "LED",
# "CLOCK" gibi adlar gercek ag adlaridir.
_HEDEF_OLMAZ = (EKLE_FIILLERI | BAGLA_FIILLERI | KAPSAM_SOZCUKLERI
                | DOLGU | set(SAYILAR) | set(HENUZ_YOK))


def _hedef_olabilir(sade_hedef: str) -> bool:
    ad = sade_hedef.strip("\"'()[].,;:!?")
    return bool(ad) and ad not in _HEDEF_OLMAZ and not ad.isdigit()


def _kalip_bul(sade: str) -> "re.Match | None":
    """Ilk MAKUL baglama kalibi. Yapi sozcugune denk gelen eslesme atlanir."""
    for desen in (_ARASINA, _BETWEEN):
        bas = 0
        while True:
            eslesme = desen.search(sade, bas)
            if eslesme is None:
                break
            if all(_hedef_olabilir(eslesme.group(ad)) for ad in ("a", "b")):
                return eslesme
            # Reddedilen hedefin SONUNDAN devam: basindan devam edersek ayni
            # kelimenin kuyrugu ("ekle" -> "kle") gecerli bir ad gibi gorunur.
            bas = max(eslesme.end("a"), bas + 1)
    return None


def _hedef_temizle(ham: str) -> str:
    """Hedef sozcugunun etrafindaki noktalama ve Turkce ekleri atar."""
    ad = ham.strip().strip("\"'()[]")
    ad = re.sub(r"[.,;:!?]+$", "", ad)
    # "VPP'ye" -> "VPP": ag adinda kesme isareti olmaz, Turkce ekte olur.
    return re.split(f"[{_TIRNAKLAR}]", ad, maxsplit=1)[0] or ad


@dataclass
class Baglama:
    """Cumleden okunan tek baglama istegi: iki hedef ve kapsami."""

    hedefler: tuple[str, str]
    kapsam: bool  # cumle "hepsini" diyor mu
    kaynak: str


def _baglama_ayir(metin: str, yorum: Yorum) -> tuple[str, "Baglama | None", bool]:
    """(baglamasiz kalan metin, istek, cumlede baglama fiili var mi).

    Kalip bulunamazsa istek `None`dir. Baglama fiili VARSA bu bir ENGEL'dir:
    "bagla" deyip de baglanmamis sembol birakmaktansa hic eklememek yeglenir.
    """
    sade = _hizali_sade(metin)
    fiil_var = bool(_BAGLA_FIIL.search(sade))
    eslesme = _kalip_bul(sade)
    if eslesme is None:
        if fiil_var:
            yorum.engeller.append(
                "baglama istendi ama neyin nereye baglanacagi anlasilmadi - "
                "kalip: \"... ekle ve hepsini VCC ile GND arasina bagla\""
            )
        return metin, None, fiil_var

    hedefler = tuple(
        _hedef_temizle(metin[eslesme.start(ad):eslesme.end(ad)]) for ad in ("a", "b")
    )
    kapsam = bool(_KAPSAM.search(sade))
    artiklar = [e.span() for e in _BAGLA_ARTIK.finditer(sade)]
    kalan = _spanlari_cikar(metin, [eslesme.span()] + artiklar)

    once = len(yorum.engeller)
    for hedef in hedefler:
        if not hedef:
            yorum.engeller.append("baglama hedeflerinden biri bos")
        elif _REFERANS.match(hedef):
            yorum.engeller.append(
                f"{hedef!r} bir bilesen referansina benziyor; bu surum yalnizca "
                "AG ADINA baglar (or. VCC, GND, +3V3). Var olan bir bilesenin "
                "pinine baglama henuz yok."
            )
        elif not _AG_ADI.match(hedef):
            yorum.engeller.append(f"{hedef!r} bir ag adina benzemiyor")
    if len(yorum.engeller) > once:
        return kalan, None, fiil_var

    if "-" in eslesme.group("ayrac"):
        yorum.notlar.append(
            f"{hedefler[0]}-{hedefler[1]}: iki ag adi diye okundu - tek bir ag "
            "adiysa \"X ile Y arasina\" yazin"
        )
    cevrilmis = []
    for hedef in hedefler:
        karsilik = AG_ADLARI.get(sadelestir(hedef))
        if karsilik and karsilik != hedef:
            yorum.notlar.append(f"{hedef!r} -> {karsilik!r} ag adi olarak okundu")
            cevrilmis.append(karsilik)
        else:
            cevrilmis.append(hedef)

    return kalan, Baglama(hedefler=(cevrilmis[0], cevrilmis[1]), kapsam=kapsam,
                          kaynak=eslesme.group(0).strip()), fiil_var


# --------------------------------------------------------------------------
# 3) Deger cozumleme
# --------------------------------------------------------------------------
#
# Deger HAM kelimeden okunur, sadelestirilmisten degil: SI oneklerinde
# buyuk/kucuk harf anlam tasir. "10M" mega, "10m" milidir; sadelestirseydik
# ikisi ayni sey olurdu ve 10 megaohm'luk direnc sematige 10 miliohm diye
# yazilirdi.

_ONEK = {"p": "p", "n": "n", "u": "u", "µ": "u", "μ": "u",
         "m": "m", "k": "k", "K": "k", "M": "M", "G": "G", "R": "R", "r": "R"}
_BIRIM = {"f": "F", "F": "F", "h": "H", "H": "H", "r": "", "R": "",
          "ohm": "", "OHM": "", "Ω": ""}

# 100nF, 4.7k, 22p, 1uF, 10ohm
_DEGER_DUZ = re.compile(
    r"^(\d+(?:\.\d+)?)\s*([pnuµμmkKMGRr])?\s*(F|f|H|h|R|r|ohm|OHM|Ω)?$"
)
# 4u7, 4k7, 4R7 - onek ondalik ayraci yerine gecer (IEC 60062)
_DEGER_HARFLI = re.compile(r"^(\d+)([pnuµμmkKMGRr])(\d+)$")


def deger_coz(ham: str) -> str | None:
    """"100nf" -> "100nF", "4u7" -> "4u7", "10" -> None (o bir SAYI).

    Onek ya da birim tasimayan sayi deger DEGILDIR; adet olarak okunur.
    Boyle olmasaydi "10 kapasitor" cumlesi "10 farad kapasitor" diye
    anlasilirdi.
    """
    m = _DEGER_HARFLI.match(ham)
    if m:
        return f"{m.group(1)}{_ONEK[m.group(2)]}{m.group(3)}"
    m = _DEGER_DUZ.match(ham)
    if not m:
        return None
    sayi, onek, birim = m.group(1), m.group(2), m.group(3)
    if not onek and not birim:
        return None  # cippe sayi -> adet
    onek_s = _ONEK[onek] if onek else ""
    birim_s = _BIRIM[birim] if birim else ""
    if onek_s == "R" and not birim_s:
        return f"{sayi}R"  # "10R" = 10 ohm
    if not onek_s and birim is not None:
        return f"{sayi}R" if birim_s == "" else f"{sayi}{birim_s}"
    return f"{sayi}{onek_s}{birim_s}"


# --------------------------------------------------------------------------
# 4) Yorum
# --------------------------------------------------------------------------


@dataclass
class Eylem:
    """Tek bir somut ekleme istegi - `add_symbols` cagrisinin girdisi."""

    fiil: str = "ekle"
    adet: int = 1
    tur: str = ""
    lib_id: str = ""
    ad: str = ""
    deger: str = ""
    footprint: str = ""
    kaynak: str = ""  # cumlenin bu eylemi ureten parcasi (izlenebilirlik)
    # "PIN=HEDEF" bicimi dogrudan `sch_add.add_symbols(connect=...)` girdisidir;
    # EKLENEN HER sembole ayni sekilde uygulanir (10 kapasitorun onu da).
    baglar: list[str] = field(default_factory=list)

    def describe(self) -> str:
        parca = f"{self.adet} x {self.ad} ({self.lib_id})"
        if self.deger:
            parca += f"  deger={self.deger}"
        if self.footprint:
            parca += f"  footprint={self.footprint}"
        if self.baglar:
            parca += "  bagla: " + ", ".join(self.baglar)
        return parca


@dataclass
class Yorum:
    """Cumlenin anlasilan hali. Dosyaya DOKUNMAZ; once gosterilir."""

    metin: str
    eylemler: list[Eylem] = field(default_factory=list)
    notlar: list[str] = field(default_factory=list)
    engeller: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.engeller and bool(self.eylemler)

    def describe(self) -> str:
        lines = [f'anlasilan: "{self.metin}"']
        for eylem in self.eylemler:
            lines.append(f"  {eylem.describe()}")
        for note in self.notlar:
            lines.append(f"  not: {note}")
        for engel in self.engeller:
            lines.append(f"  ENGEL: {engel}")
        if not self.eylemler and not self.engeller:
            lines.append("  ENGEL: cumlede yapilacak bir is bulunamadi")
        return "\n".join(lines)

    def as_dict(self) -> dict:
        return {
            "metin": self.metin,
            "eylemler": [
                {"fiil": e.fiil, "adet": e.adet, "lib_id": e.lib_id,
                 "deger": e.deger, "footprint": e.footprint,
                 "baglar": list(e.baglar), "kaynak": e.kaynak}
                for e in self.eylemler
            ],
            "notlar": list(self.notlar),
            "engeller": list(self.engeller),
        }


def _fiil_bul(sade_kelimeler: list[str], yorum: Yorum,
              baglama_var: bool = False) -> str:
    """Cumlenin fiili. Bilinmeyen fiil sessizce "ekle" sayilmaz."""
    for kelime in sade_kelimeler:
        if kelime in EKLE_FIILLERI:
            return "ekle"
    if baglama_var:
        # Baglama tek basina bir is degil: bu katman baglanacak sembolleri
        # kendisi uretir. Var olan iki sembolu baglamak once onlara
        # REFERANSLA konusabilmeyi ister; o ayri bir is.
        yorum.engeller.append(
            "bu surum yalnizca EKLERKEN baglar, cumlede bir ekleme fiili yok "
            '(or. "10 adet 100nF kapasitor ekle ve hepsini VCC ile GND '
            'arasina bagla")'
        )
        return ""
    for kelime in sade_kelimeler:
        if kelime in HENUZ_YOK:
            yorum.engeller.append(
                f"{kelime!r} = {HENUZ_YOK[kelime]} - bu surum EKLER ve "
                "eklerken BAGLAR, baskasini yapmaz"
            )
            return ""
    yorum.engeller.append(
        "cumlede bilinen bir fiil yok (or. ekle, koy, yerlestir / add, place)"
    )
    return ""


def anla(metin: str) -> Yorum:
    """Dogal dil cumlesini eylem listesine cevirir. KUTUPHANEYE DOKUNMAZ.

    Cozumleme saf tutulur ki testler KiCad kurulu olmadan da kosabilsin;
    `lib_id`lerin gercekten var olup olmadigi `uygula()` asamasinda
    dogrulanir.
    """
    yorum = Yorum(metin=metin.strip())
    if not yorum.metin:
        yorum.engeller.append("bos komut")
        return yorum

    tum = _kelimeler(metin)
    # Baglama kalibi ONCE ayrilir: icindeki "ve" bolucuyu, icindeki "toprak"
    # da bilesen tablosunu yaniltir (bkz. 2b).
    kalan, istek, bagla_fiili = _baglama_ayir(metin, yorum)
    if yorum.engeller:
        return yorum  # kalip anlasilmadi; yarim is planlanmaz
    fiil = _fiil_bul([s for _, s in tum], yorum,
                     baglama_var=istek is not None or bagla_fiili)
    if not fiil:
        return yorum

    parcalar = [p for p in _AYRAC.split(kalan) if p and p.strip()]
    anlasilmayan: list[str] = []

    for parca in parcalar:
        kelimeler = _kelimeler(parca)
        tur = ""
        adet: int | None = None
        deger = ""
        paket = ""
        nitelik: list[str] = []
        artik: list[str] = []
        belirsizler: list[str] = []

        for ham, sade in kelimeler:
            if sade in EKLE_FIILLERI or sade in DOLGU:
                continue
            kok = _kok(sade, SOZCUKLER)
            if kok:
                yeni = SOZCUKLER[kok]
                if tur and tur != yeni:
                    yorum.engeller.append(
                        f"{parca.strip()!r}: tek istekte iki bilesen turu var "
                        f"({TURLER[tur]['ad']} ve {TURLER[yeni]['ad']}) - "
                        "'ve' ile ayirin"
                    )
                tur = yeni
                continue
            kok = _kok(sade, NITELEYICILER)
            if kok:
                nitelik.append(kok)
                continue
            kok = _kok(sade, BELIRSIZ)
            if kok:
                belirsizler.append(kok)
                continue
            if sade in SAYILAR:
                adet = SAYILAR[sade] if adet is None else adet
                continue
            carpim = re.fullmatch(r"(\d+)x|x(\d+)", sade)
            if carpim:
                sayi = int(carpim.group(1) or carpim.group(2))
                adet = sayi if adet is None else adet
                continue
            # Paket kodu sayidan ONCE denenir: "0603" bir adet degil, boyuttur.
            if re.fullmatch(r"\d{4}", sade):
                paket = sade
                continue
            bulunan = deger_coz(ham)
            if bulunan:
                deger = bulunan
                continue
            if sade.isdigit():
                adet = int(sade) if adet is None else adet
                continue
            artik.append(ham)

        for kelime in belirsizler:
            yorum.engeller.append(
                f"{kelime!r} tek basina yetmiyor - adaylar: {BELIRSIZ[kelime]}"
            )

        if not tur:
            if not belirsizler and (artik or adet is not None or deger or paket):
                yorum.engeller.append(
                    f"{parca.strip()!r}: hangi bilesen istendigi anlasilmadi"
                    + (f" (tanimadigim kelimeler: {', '.join(artik)})" if artik else "")
                    + f" - bilinen turler: {', '.join(sorted(TURLER))}"
                )
            continue

        for kelime in nitelik:
            hedef = NITELEYICILER[kelime].get(tur)
            if hedef:
                tur = hedef
            else:
                artik.append(kelime)

        bilgi = TURLER[tur]
        footprint = ""
        if paket:
            footprint = bilgi["paketler"].get(paket, "")
            if not footprint:
                yorum.engeller.append(
                    f"{bilgi['ad']} icin {paket!r} paketi tanimli degil"
                    + (f" (bilinenler: {', '.join(sorted(bilgi['paketler']))})"
                       if bilgi["paketler"] else " - bu tur icin paket tablosu yok")
                )

        if artik:
            anlasilmayan.extend(artik)

        yorum.eylemler.append(Eylem(
            fiil=fiil,
            adet=adet if adet is not None else 1,
            tur=tur,
            lib_id=bilgi["lib_id"],
            ad=bilgi["ad"],
            deger=deger,
            footprint=footprint,
            kaynak=parca.strip(),
        ))

    if istek is not None:
        _baglantilari_dagit(yorum, istek)

    if anlasilmayan:
        yorum.notlar.append(
            "yok sayilan kelime(ler): " + ", ".join(dict.fromkeys(anlasilmayan))
        )
    for eylem in yorum.eylemler:
        if not eylem.deger:
            yorum.notlar.append(
                f"{eylem.ad}: deger verilmedi - kutuphanedeki deger kullanilacak "
                "(varsayilan bir deger uydurulmaz)"
            )
    return yorum


def _baglantilari_dagit(yorum: Yorum, istek: Baglama) -> None:
    """Okunan baglama istegini eylemlere `PIN=HEDEF` olarak yazar.

    Cumlede birden fazla ekleme varsa ve "hepsini" gibi bir kapsam sozcugu
    YOKSA baglamanin hangisine ait oldugu tahmin edilmez: yanlis bilesenin
    ucuna etiket koymak, hic koymamaktan kotudur.
    """
    if not yorum.eylemler:
        if not yorum.engeller:
            yorum.engeller.append(
                "baglama istendi ama eklenecek bir bilesen bulunamadi"
            )
        return
    if len(yorum.eylemler) > 1 and not istek.kapsam:
        yorum.engeller.append(
            f"cumlede {len(yorum.eylemler)} ayri ekleme var; baglamanin "
            'hangisine ait oldugu belirsiz - "hepsini" deyin ya da istekleri '
            "ayri cumlelere bolun"
        )
        return

    once, sonra = istek.hedefler
    for eylem in yorum.eylemler:
        uclar = TURLER[eylem.tur]["uclar"]
        if len(uclar) != 2:
            yorum.engeller.append(
                f"{eylem.ad} iki uclu degil - hangi pininin nereye gidecegi "
                "uydurulmaz"
            )
            continue
        eylem.baglar = [f"{uclar[0]}={once}", f"{uclar[1]}={sonra}"]
        adlar = TURLER[eylem.tur].get("uc_adlari")
        if adlar:
            # Kutuplu bilesende yon ELEKTRIKSEL bir karardir ve cumle onu
            # soylemez. Sectigimizi yazariz; sessizce secmeyiz.
            yorum.notlar.append(
                f"{eylem.ad} kutupludur: {once} -> {adlar[0]}, "
                f"{sonra} -> {adlar[1]}. Cumle yonu soylemiyor; tersi "
                "isteniyorsa hedefleri ters sirada yazin."
            )


# --------------------------------------------------------------------------
# 5) Hedef sematik
# --------------------------------------------------------------------------


def kok_sematik(hedef: Path | None = None) -> Path:
    """"Su anki modelimiz" = hedefteki TEK proje.

    Birden fazla aday varsa secim yapilmaz: yanlis dosyaya yazmak, hic
    yazmamaktan kotudur.
    """
    yol = Path(hedef) if hedef else Path.cwd()
    if yol.is_file():
        if yol.suffix != ".kicad_sch":
            raise KomutError(f"sematik dosyasi bekleniyordu: {yol}")
        return yol
    if not yol.is_dir():
        raise KomutError(f"bulunamadi: {yol}")

    projeler = sorted(yol.glob("*.kicad_pro"))
    if len(projeler) == 1:
        aday = projeler[0].with_suffix(".kicad_sch")
        if aday.is_file():
            return aday
    semalar = sorted(yol.glob("*.kicad_sch"))
    if len(semalar) == 1:
        return semalar[0]
    if not semalar:
        raise KomutError(f"{yol} icinde .kicad_sch yok - hedefi --sch ile verin")
    raise KomutError(
        f"{yol} icinde {len(semalar)} sematik var, hangisi belli degil "
        f"({', '.join(s.name for s in semalar[:5])}) - --sch ile secin"
    )


# --------------------------------------------------------------------------
# 6) Uygulama
# --------------------------------------------------------------------------


def mevcut_aglar(schematic: Schematic) -> set[str]:
    """Sematikte BUGUN duran ag adlari (etiketler + guc sembolleri).

    Netlist'ten degil sematikten okunur: bu bilgi `kicad-cli` kosmadan da
    gerekli ve yalnizca "boyle bir ad var mi" sorusuna cevap veriyor.
    """
    adlar = {etiket.text.strip().lstrip("/") for etiket in schematic.labels}
    adlar |= {sym.value.strip() for sym in schematic.symbols if sym.is_power}
    return {ad for ad in adlar if ad}


def _aglari_coz(yorum: Yorum, schematic: Schematic) -> None:
    """Hedef ag adlarini sematikteki GERCEK yazimla esler.

    Neden gerekli: baglanti bir ETIKET yazilarak kurulur ve KiCad'de ag
    adlari buyuk/kucuk harfe duyarlidir. "vcc" yazan kullanici "VCC" agina
    baglanmis olmaz - on kapasitor de sayfada bos bir "vcc" adasinda kalir.
    Netlist kalkani bunu YAKALAMAZ: yeni bir ag olusturmak da gecerli bir
    islemdir, kalkan yalnizca ESKI devrenin degismedigini olcer. O yuzden
    burada yazim duzeltilir, duzeltilemiyorsa ACIKCA uyarilir.
    """
    mevcut = mevcut_aglar(schematic)
    kucuk: dict[str, list[str]] = {}
    for ad in mevcut:
        kucuk.setdefault(ad.lower(), []).append(ad)

    soylenen: set[str] = set()

    def not_ver(mesaj: str) -> None:
        if mesaj not in soylenen:
            soylenen.add(mesaj)
            yorum.notlar.append(mesaj)

    for eylem in yorum.eylemler:
        yeni: list[str] = []
        for parca in eylem.baglar:
            pin, _, hedef = parca.partition("=")
            adaylar = sorted(kucuk.get(hedef.lower(), []))
            if hedef in mevcut:
                yeni.append(parca)
            elif len(adaylar) == 1:
                not_ver(f"{hedef!r} -> {adaylar[0]!r} (sematikteki yazim)")
                yeni.append(f"{pin}={adaylar[0]}")
            elif adaylar:
                not_ver(
                    f"{hedef!r} icin yalnizca buyuk/kucuk harfte ayrilan "
                    f"{len(adaylar)} ag var ({', '.join(adaylar)}) - yazdiginiz "
                    "ad aynen kullanildi"
                )
                yeni.append(parca)
            else:
                not_ver(
                    f"UYARI: {hedef!r} adinda bir ag sematikte YOK - yeni ve bos "
                    "bir ag olusturulur; ad yanlissa eklenen bilesenler "
                    "baglantisiz kalir (mevcut adlar: "
                    + ", ".join(sorted(mevcut)[:10]) + ")"
                )
                yeni.append(parca)
        eylem.baglar = yeni


def uygula(
    yorum: Yorum,
    sch_path: Path,
    *,
    apply: bool = False,
    verify: bool = True,
    backup: bool = True,
    allow_open_project: bool = False,
    kicad_cli: str | None = None,
) -> list[AddResult]:
    """Eylemleri sirayla `sch_add.add_symbols`a verir.

    Kalkan, yedek, kilit kontrolu ve dry-run varsayilani `sch_add`in
    isidir - burada tekrarlanmaz. Bir eylem engele takilirsa sonrakiler
    CALISTIRILMAZ: yarim uygulanmis bir cumle, hic uygulanmamis olandan
    daha zor toparlanir.
    """
    if not yorum.ok:
        raise KomutError("anlasilmayan komut uygulanmaz")

    if any(eylem.baglar for eylem in yorum.eylemler):
        _aglari_coz(yorum, read_schematic(sch_path))

    sonuclar: list[AddResult] = []
    for eylem in yorum.eylemler:
        sonuc = add_symbols(
            sch_path,
            eylem.lib_id,
            eylem.adet,
            value=eylem.deger or None,
            footprint=eylem.footprint or None,
            connect=eylem.baglar or None,
            apply=apply,
            verify=verify,
            backup=backup,
            allow_open_project=allow_open_project,
            kicad_cli=kicad_cli,
        )
        sonuclar.append(sonuc)
        if not sonuc.plan.ok or (sonuc.diff is not None and not sonuc.diff.ok):
            break
        if apply and not sonuc.applied:
            break

    # DRY-RUN'da hicbir eylem dosyaya yazilmadigi icin her eylem AYNI bos
    # numaralardan baslar: iki kez kapasitor isteyen bir cumlede iki plan da
    # "C1..C5" der. Gercek uygulamada boyle olmaz (her adim yazilmis dosyayi
    # yeniden okur) - ama plani okuyan kisi bunu bilmezse cakisma sanir.
    if not apply and len({s.plan.lib_id for s in sonuclar}) < len(sonuclar):
        yorum.notlar.append(
            "dry-run: ayni turden birden fazla istek var; asagidaki referans "
            "numaralari her plan icin ayni baslangictan sayilir. --uygula ile "
            "her adim bir oncekinin ustune numaralanir."
        )
    return sonuclar


# --------------------------------------------------------------------------
# Komut satiri
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pcbqa.komut",
        description="Dogal dil komutunu anlar ve uygular "
                    '(or. "10 adet 100nF kapasitor ekle").',
        epilog='baglama ayni cumlede olur: "10 adet 100nF kapasitor ekle ve '
               'hepsini VCC ile GND arasina bagla"',
    )
    ap.add_argument("metin", nargs="*", help="Komut cumlesi")
    ap.add_argument("--sch", type=Path, default=None,
                    help="Hedef .kicad_sch ya da proje klasoru "
                         "(varsayilan: bulundugun klasor)")
    ap.add_argument("--uygula", action="store_true", help="Dosyaya gercekten yaz")
    ap.add_argument("--sadece-anla", action="store_true",
                    help="Yalnizca cumleyi cozumle, sematige bakma")
    ap.add_argument("--dagarcik", action="store_true",
                    help="Anlasilan bilesen turlerini listele ve cik")
    ap.add_argument("--no-verify", action="store_true",
                    help="Netlist kalkanini atla (onerilmez)")
    ap.add_argument("--no-backup", action="store_true", help="Yedek alma")
    ap.add_argument("--allow-open-project", action="store_true",
                    help="KiCad acikken de yaz")
    ap.add_argument("--kicad-cli", default=None)
    return ap


def _dagarcik() -> int:
    print("pcbqa yap - anlasilan bilesen turleri")
    print()
    for anahtar, bilgi in TURLER.items():
        sozler = sorted(k for k, v in SOZCUKLER.items() if v == anahtar)
        uclar = bilgi["uclar"]
        uc_metni = ("pin " + "/".join(uclar)) if uclar else "TEK UCLU - baglanamaz"
        print(f"  {bilgi['ad']:<22} {bilgi['lib_id']}")
        if sozler:
            print(f"  {'':<22} sozcukler: {', '.join(sozler)}")
        if bilgi["paketler"]:
            print(f"  {'':<22} paketler : {', '.join(sorted(bilgi['paketler']))}")
        print(f"  {'':<22} uclar    : {uc_metni}"
              + (f"  ({' / '.join(bilgi['uc_adlari'])})"
                 if bilgi.get("uc_adlari") else ""))
    print()
    print("  fiiller: " + ", ".join(sorted(EKLE_FIILLERI)))
    print("  bagla  : " + ", ".join(sorted(BAGLA_FIILLERI)))
    print("  kalip  : \"<A> ile <B> arasina\", \"<A>-<B> arasina\", "
          "\"between <A> and <B>\"")
    print("  kapsam : " + ", ".join(sorted(KAPSAM_SOZCUKLERI))
          + "  (birden fazla ekleme varsa SART)")
    print("  deger  : 100nF, 4u7, 10k, 4.7uF, 10R (onek/birim yoksa ADET sayilir)")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    if args.dagarcik:
        return _dagarcik()
    if not args.metin:
        print("hata: bir komut cumlesi verin, or.\n"
              '       pcbqa yap "10 adet kapasitor ekle"\n'
              "       (turleri gormek icin: pcbqa yap --dagarcik)", file=sys.stderr)
        return 2

    yorum = anla(" ".join(args.metin))
    print(yorum.describe())
    if not yorum.ok:
        return 1
    if args.sadece_anla:
        return 0

    try:
        hedef = kok_sematik(args.sch)
    except KomutError as exc:
        print(f"hata: {exc}", file=sys.stderr)
        return 2
    print(f"  hedef: {hedef}")

    # `uygula` cozumleme sirasinda BILINEMEYEN seyleri not eder (ag adinin
    # sematikteki gercek yazimi, dry-run numaralama uyarisi). Bunlar
    # `describe()` basildiktan SONRA olusur; basilmazlarsa "vcc diye bir ag
    # yok" uyarisi hic gorunmez ve kullanici bos bir adaya baglanir.
    onceki = len(yorum.notlar)

    def yeni_notlar() -> None:
        for metin in yorum.notlar[onceki:]:
            print(f"  not: {metin}")

    try:
        sonuclar = uygula(
            yorum, hedef,
            apply=args.uygula, verify=not args.no_verify,
            backup=not args.no_backup,
            allow_open_project=args.allow_open_project,
            kicad_cli=args.kicad_cli,
        )
    except (KomutError, SchAddError, SchWriteError, symlib.SymLibError) as exc:
        yeni_notlar()
        print(f"hata: {exc}", file=sys.stderr)
        return 1
    yeni_notlar()

    basarili = True
    for sonuc in sonuclar:
        print()
        print(sonuc.plan.describe())
        if sonuc.diff is not None:
            if sonuc.diff.ok:
                print("  kalkan: mevcut devre degismedi, yalnizca yeni "
                      "bilesenler eklendi")
            else:
                print(f"  KALKAN REDDETTI: {sonuc.diff.describe()}")
                for satir in sonuc.diff.details():
                    print("  " + satir)
                basarili = False
        if not sonuc.plan.ok:
            basarili = False
        if sonuc.write is not None and sonuc.applied:
            print(f"  yazildi: {sonuc.write.path}"
                  + (f" (yedek: {sonuc.write.backup.name})"
                     if sonuc.write.backup else ""))

    if len(sonuclar) < len(yorum.eylemler):
        print()
        print(f"  DURDURULDU: {len(yorum.eylemler) - len(sonuclar)} eylem "
              "calistirilmadi (onceki adim gecmedi)")
        basarili = False
    if not args.uygula:
        print()
        print("  (dry-run - yazmak icin --uygula)")
    return 0 if basarili else 1


if __name__ == "__main__":
    raise SystemExit(main())
