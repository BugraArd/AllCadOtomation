"""SOZLUK - KiCad kutuphanelerinden bilesen adlari, iki dilde.

    pcbqa sozluk                 ozet: kac onek, kac terim, kac sembol
    pcbqa sozluk --uret          sembol sozlugunu uret (data/kicad-sozluk.json.gz)
    pcbqa sozluk --ara direnc    onek/terim/sembol icinde ara

## Ne icin

Ilerideki makine ogrenimi bir bileseni ADINDAN tanimak zorunda: "C", "kondansator",
"capacitor", "Device:C_Polarized" ayni seyi soyluyor. Bu modul o esleme
tablosunu kurar - kisaltma, tam ad, Ingilizce ve Turkce.

## Uc katman, ucu de farkli guvenilirlikte

  1. DESIGNATORS - referans oneki (C, R, U...) -> tur adi. ELLE kuruldu ama
     TAHMINLE DEGIL: her onekin kutuphanedeki 22.776 sembolde gercekte hangi
     aciklamalarla kullanildigi olculdu ve ad ona gore verildi. Yanindaki
     `ornek` alani o olcumun ozetidir.
  2. TERMS - Ingilizce terim -> Turkce. Yine elle, ama secim olcume dayali:
     aciklama metinlerindeki kelime siklik listesinden bas taraf alindi.
  3. semboller - KiCad kutuphanelerinden OLCULEREK cikarilir (22.776 kayit).
     Ingilizce aciklama kutuphanenin kendisinden gelir; Turkce karsilik
     YALNIZCA TERMS'ten uretilir.

## Uydurulmayan sey

22.776 sembolun cogu parca numarasidir (STM32F103C8Tx, TPS54331). Bunlarin
"Turkcesi" yoktur ve uydurulmaz. Bir sembolun Turkce alani ancak TERMS'ten
gercek bir eslesme ciktiginda dolar; cikmazsa BOS kalir ve bu bir eksiklik
degil, dogruluk tercihidir. `kapsam()` bu oranin ne oldugunu soyler.

Paket adlari (SOT-23, LQFP, QFN) ve uretici adlari (STMicroelectronics) da
bilincli olarak cevrilmez - onlar ozel addir.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

DATA = Path(__file__).parent / "data"
SOZLUK_DOSYASI = DATA / "kicad-sozluk.json.gz"
SURUM = 1


# --------------------------------------------------------------------------
# 1) Referans onekleri
# --------------------------------------------------------------------------
#
# `ornek` alani, o onegin kutuphanedeki sembollerinde EN SIK gecen anahtar
# kelimelerdir (olculdu 2026-08-31, KiCad 10.0.4, 223 kutuphane / 22.776
# sembol). Ad vermeden once bakilan kanit budur; "C kondansatordur" diye
# ezberden yazilmadi.
#
# `adet` = o onegi kullanan sembol sayisi. Kucuk sayilar onegin nadir
# oldugunu soyler, yanlis oldugunu degil.

DESIGNATORS: dict[str, dict[str, str]] = {
    "U":    {"en": "Integrated circuit",      "tr": "Tumlesik devre",        "ornek": "arm, cortex-m, flash, voltage, output"},
    "IC":   {"en": "Integrated circuit",      "tr": "Tumlesik devre",        "ornek": "microcontroller, flash, core, ram"},
    "J":    {"en": "Connector (jack/socket)", "tr": "Konnektor (disi)",      "ornek": "connector, row, pin, generic"},
    "P":    {"en": "Connector (plug)",        "tr": "Konnektor (fis)",       "ornek": "plug, usb, iec, type-c"},
    "CN":   {"en": "Capacitor network",       "tr": "Kondansator dizisi",    "ornek": "network, capacitor, star, bussed"},
    "D":    {"en": "Diode",                   "tr": "Diyot",                 "ornek": "diode, rectifier, schottky, zener"},
    "LD":   {"en": "Laser diode",             "tr": "Lazer diyot",           "ornek": "laser, diode, opto, photodiode"},
    "Q":    {"en": "Transistor",              "tr": "Transistor",            "ornek": "mosfet, n-channel, transistor, npn"},
    "R":    {"en": "Resistor",                "tr": "Direnc",                "ornek": "resistor, light dependent, ldr, variable"},
    "RN":   {"en": "Resistor network",        "tr": "Direnc dizisi",         "ornek": "network, topology, resistor, bussed"},
    "RV":   {"en": "Variable resistor",       "tr": "Ayarli direnc",         "ornek": "resistor, variable, potentiometer"},
    "TH":   {"en": "Thermistor / RTD",        "tr": "Termistor / RTD",       "ornek": "temperature, sensor, rtd, thermistor"},
    "C":    {"en": "Capacitor",               "tr": "Kondansator",           "ornek": "capacitor, cap, polarized, trimmer"},
    "L":    {"en": "Inductor",                "tr": "Bobin",                 "ornek": "inductor, coupled, choke, coil, reactor"},
    "FB":   {"en": "Ferrite bead",            "tr": "Ferrit boncuk",         "ornek": "ferrite, bead"},
    "T":    {"en": "Transformer",             "tr": "Transformator",         "ornek": "transformer, smt, gate drive, pulse"},
    "TR":   {"en": "Transformer (RF)",        "tr": "Transformator (RF)",    "ornek": "transformer, secondary, balanced, mhz"},
    "K":    {"en": "Relay",                   "tr": "Role",                  "ornek": "relay, coil, pole, dpdt"},
    "SW":   {"en": "Switch",                  "tr": "Anahtar",               "ornek": "switch, rotary, pole, throw, dip"},
    "JP":   {"en": "Jumper",                  "tr": "Jumper (kopru)",        "ornek": "jumper, solder, bridged, spst"},
    "CB":   {"en": "Circuit breaker",         "tr": "Devre kesici",          "ornek": "pole, circuit, breaker"},
    "F":    {"en": "Fuse / protection",       "tr": "Sigorta / koruma",      "ornek": "bidirectional, protection, low capacitance"},
    "FL":   {"en": "Filter",                  "tr": "Filtre",                "ornek": "filter, pass, mhz, passive"},
    "X":    {"en": "SAW filter / resonator",  "tr": "SAW filtre / rezonator", "ornek": "filter, bandpass, saw, mhz"},
    "Y":    {"en": "Crystal / oscillator",    "tr": "Kristal / osilator",    "ornek": "oscillator, clock, crystal, mems"},
    "AE":   {"en": "Antenna",                 "tr": "Anten",                 "ornek": "antenna, dipole, loop, ceramic"},
    "M":    {"en": "Motor",                   "tr": "Motor",                 "ornek": "motor, fan, servo, tacho, pwm"},
    "LS":   {"en": "Loudspeaker / transducer", "tr": "Hoparlor / donusturucu", "ornek": "speaker, transducer, ultrasonic"},
    "MK":   {"en": "Microphone",              "tr": "Mikrofon",              "ornek": "microphone, mems, digital"},
    "BAR":  {"en": "LED bar / array",         "tr": "LED cubuk / dizi",      "ornek": "led, display, array, element"},
    "DS":   {"en": "Display",                 "tr": "Gosterge",              "ornek": "display, lcd, alphanumeric, graphics"},
    "BT":   {"en": "Battery",                 "tr": "Pil / batarya",         "ornek": "battery, cell"},
    "MES":  {"en": "Meter",                   "tr": "Olcer",                 "ornek": "ammeter, voltmeter, meter, counter"},
    "TP":   {"en": "Test point",              "tr": "Test noktasi",          "ornek": "point, test, coaxial, testpoint"},
    "TC":   {"en": "Thermocouple",            "tr": "Isil cift",             "ornek": "thermocouple, temperature, cold junction"},
    "HS":   {"en": "Heatsink",                "tr": "Sogutucu",              "ornek": "heatsink, thermal, heat"},
    "H":    {"en": "Mounting hardware",       "tr": "Montaj donanimi",       "ornek": "mounting, hole, outline"},
    "NT":   {"en": "Net tie",                 "tr": "Ag baglayici",          "ornek": "net, tie, short, tee, cross"},
    "A":    {"en": "Module / assembly",       "tr": "Modul / alt montaj",    "ornek": "microcontroller, module, arduino"},
    "V":    {"en": "Voltage source",          "tr": "Gerilim kaynagi",       "ornek": "voltage, source, simulation, noise"},
    "I":    {"en": "Current source",          "tr": "Akim kaynagi",          "ornek": "current, source, simulation"},
    # --- nadir ama net: her biri kutuphanedeki gercek sembolle dogrulandi ---
    "AFF":  {"en": "Seven-segment display",   "tr": "Yedi segmanli gosterge", "ornek": "LTS-6960HR: DISPLAY 7 SEGMENTS"},
    "BZ":   {"en": "Buzzer",                  "tr": "Buzzer (sesli uyarici)", "ornek": "Device:Buzzer"},
    "LA":   {"en": "Lamp",                    "tr": "Lamba",                 "ornek": "Device:Lamp, Lamp_Flash"},
    "NE":   {"en": "Neon lamp",               "tr": "Neon lamba",            "ornek": "Device:Lamp_Neon"},
    "LN":   {"en": "Inductor network",        "tr": "Bobin dizisi",          "ornek": "Device:L_Pack04"},
    "GD":   {"en": "Gas discharge tube",      "tr": "Gaz desarj tupu",       "ornek": "Device:GDT_2Pin"},
    "SC":   {"en": "Solar cell",              "tr": "Gunes pili",            "ornek": "Device:Solar_Cell"},
    "PE":   {"en": "Peltier element",         "tr": "Peltier elemani",       "ornek": "Device:PeltierElement"},
    "HG":   {"en": "Hall effect generator",   "tr": "Hall etkili uretec",    "ornek": "Device:HallGenerator"},
    "MR":   {"en": "Memristor",               "tr": "Memristor",             "ornek": "Device:Memristor"},
    "TJ":   {"en": "Thermal jumper",          "tr": "Isil kopru",            "ornek": "Device:Thermal_Jumper"},
    "PMT":  {"en": "Photomultiplier tube",    "tr": "Foto cogaltici tup",    "ornek": "Sensor_Optical:PMTx08Dyn"},
    "DWM":  {"en": "UWB radio module",        "tr": "UWB telsiz modulu",     "ornek": "RF_Module:DWM1000"},
    "RL":   {"en": "Relay",                   "tr": "Role",                  "ornek": "Relay:JW2 (K ile ayni sey)"},
    "FID":  {"en": "Fiducial marker",         "tr": "Fiducial (hizalama) isareti", "ornek": "Mechanical:Fiducial"},
    "DRA":  {"en": "DIN rail adapter",        "tr": "DIN ray adaptoru",      "ornek": "Mechanical:DIN_Rail_Adapter"},
    "N":    {"en": "Housing (mechanical)",    "tr": "Muhafaza (mekanik)",    "ornek": "Mechanical:Housing"},
    # SPICE benzetim sembolleri - standart SPICE harfleri
    "E":    {"en": "VCVS (SPICE)",            "tr": "Gerilim kontrollu gerilim kaynagi", "ornek": "Simulation_SPICE:ESOURCE"},
    "G":    {"en": "VCCS (SPICE)",            "tr": "Gerilim kontrollu akim kaynagi",    "ornek": "Simulation_SPICE:GSOURCE"},
    "B":    {"en": "Behavioral source (SPICE)", "tr": "Davranissal kaynak (SPICE)",      "ornek": "Simulation_SPICE:BSOURCE"},
    "S":    {"en": "Controlled switch (SPICE)", "tr": "Kontrollu anahtar (SPICE)",       "ornek": "Simulation_SPICE:SWITCH"},
    # Sanal semboller: netlist'te BILESEN olarak gorunmezler (olculdu - bkz.
    # 'netlistte-gorunmeyeni-netlistte-arama'). Sozlukte dururlar ki bir arac
    # onlari gordugunde ne olduklarini bilsin.
    "#PWR": {"en": "Power symbol (virtual)",  "tr": "Guc sembolu (sanal)",   "ornek": "global, power, label"},
    "#FLG": {"en": "Power flag (virtual)",    "tr": "Guc bayragi (sanal)",   "ornek": "power, flag"},
    "#SYM": {"en": "Graphic symbol (virtual)", "tr": "Cizim sembolu (sanal)", "ornek": "symbol, warning, arrow, logo"},
    "#GND": {"en": "Ground reference (SPICE)", "tr": "Toprak referansi (SPICE)", "ornek": "Simulation_SPICE:0"},
    "SYM":  {"en": "Graphic symbol",          "tr": "Cizim sembolu",         "ornek": "Graphic:SYM_EasterEgg"},
}

# `B` ve `S` iki farkli seyde kullanilmis: SPICE kaynagi/anahtari ve
# Mechanical:MouseBite / Mechanical_Shape. Standart olan SPICE anlamidir;
# mekanik olanlar kutuphanenin kendi tutarsizligidir. Ad SPICE'a gore verildi.


# --------------------------------------------------------------------------
# 2) Terim sozlugu
# --------------------------------------------------------------------------
#
# Secim olcume dayali: aciklama + anahtar kelime metinlerinde (266.284 kelime)
# siklik listesi cikarildi ve BILESEN TURU bildiren kelimeler alindi. Paket
# adlari (sot, soic, lqfp, qfn, dip), uretici adlari ve olcu birimleri
# BILINCLI OLARAK disarida: onlar ozel ad, cevrilmez.

TERMS: dict[str, str] = {
    # temel pasifler
    "resistor": "direnc", "resistors": "direncler", "res": "direnc",
    "capacitor": "kondansator", "capacitors": "kondansatorler", "cap": "kondansator",
    "inductor": "bobin", "inductors": "bobinler", "coil": "bobin",
    "choke": "sok bobini", "ferrite": "ferrit", "bead": "boncuk",
    "transformer": "transformator", "potentiometer": "potansiyometre",
    "varistor": "varistor", "thermistor": "termistor", "trimmer": "trimer",
    "network": "dizi", "array": "dizi",
    # yariiletken
    "diode": "diyot", "diodes": "diyotlar", "rectifier": "dogrultucu",
    "schottky": "schottky", "zener": "zener", "bridge": "kopru",
    "transistor": "transistor", "mosfet": "mosfet", "jfet": "jfet",
    "igbt": "igbt", "thyristor": "tristor", "triac": "triyak",
    "n-channel": "n-kanal", "p-channel": "p-kanal", "npn": "npn", "pnp": "pnp",
    "photodiode": "fotodiyot", "phototransistor": "fototransistor",
    "optocoupler": "optokuplor", "opto": "opto", "laser": "lazer",
    # tumlesik
    "microcontroller": "mikrodenetleyici", "mcu": "mikrodenetleyici",
    "microprocessor": "mikroislemci", "cpu": "islemci",
    "amplifier": "yukseltec", "opamp": "islemsel yukseltec",
    "comparator": "karsilastirici", "regulator": "regulator",
    "converter": "donusturucu", "inverter": "evirici", "driver": "surucu",
    "controller": "denetleyici", "oscillator": "osilator", "crystal": "kristal",
    "resonator": "rezonator", "multiplexer": "coklayici", "demultiplexer": "ayirici",
    "encoder": "kodlayici", "decoder": "kod cozucu", "counter": "sayici",
    "register": "yazmac", "latch": "mandal", "buffer": "tampon",
    "gate": "kapi", "logic": "mantik", "flip-flop": "flip-flop",
    "memory": "bellek", "eeprom": "eeprom", "flash": "flas bellek",
    "sram": "sram", "dram": "dram", "ram": "ram", "rom": "rom",
    "sensor": "algilayici", "transceiver": "alici-verici",
    "receiver": "alici", "transmitter": "verici", "modulator": "modulator",
    "filter": "filtre", "switch": "anahtar", "relay": "role", "fuse": "sigorta",
    "isolator": "yalitici", "isolated": "yalitilmis", "isolation": "yalitim",
    "reference": "referans", "monitor": "izleyici", "supervisor": "gozetleyici",
    "accelerometer": "ivmeolcer", "gyroscope": "jiroskop",
    "magnetometer": "manyetometre", "barometer": "barometre",
    # guc
    "power": "guc", "voltage": "gerilim", "current": "akim",
    "supply": "besleme", "battery": "pil", "charger": "sarj devresi",
    "ldo": "dusuk dusumlu regulator", "buck": "dusuruculu",
    "boost": "yukselticili", "step-down": "gerilim dusurucu",
    "step-up": "gerilim yukseltici", "linear": "lineer", "switching": "anahtarlamali",
    "positive": "pozitif", "negative": "negatif", "fixed": "sabit",
    "adjustable": "ayarlanabilir", "variable": "degisken",
    "dropout": "dusum", "efficiency": "verim",
    # baglanti
    "connector": "konnektor", "header": "baglanti basligi", "socket": "soket",
    "plug": "fis", "jack": "jak", "terminal": "klemens", "jumper": "jumper",
    "pin": "pin", "pins": "pin", "row": "sira", "rows": "sira",
    "male": "erkek", "female": "disi", "shield": "ekran", "shielded": "ekranli",
    "cable": "kablo", "wire": "tel",
    # gosterge / cikis
    "led": "led", "display": "gosterge", "lcd": "lcd", "oled": "oled",
    "segment": "segment", "backlight": "arka isik", "lamp": "lamba",
    "speaker": "hoparlor", "buzzer": "buzzer", "microphone": "mikrofon",
    "antenna": "anten", "motor": "motor", "servo": "servo", "fan": "fan",
    "heatsink": "sogutucu",
    # olcum / sinama
    "meter": "olcer", "ammeter": "ampermetre", "voltmeter": "voltmetre",
    "test": "test", "point": "nokta", "probe": "prob",
    "temperature": "sicaklik", "thermocouple": "isil cift",
    # sifat / nitelik
    "dual": "cift", "single": "tek", "triple": "uclu", "quad": "dortlu",
    "octal": "sekizli", "high": "yuksek", "low": "dusuk", "high-speed": "yuksek hizli",
    "generic": "genel", "polarized": "kutuplu", "unpolarized": "kutupsuz",
    "bidirectional": "cift yonlu", "unidirectional": "tek yonlu",
    "differential": "diferansiyel", "analog": "analog", "digital": "sayisal",
    "input": "giris", "output": "cikis", "protection": "koruma",
    "suppressor": "bastirici", "module": "modul", "small": "kucuk",
    "large": "buyuk", "mounting": "montaj", "hole": "delik",
    "channel": "kanal", "channels": "kanal", "package": "govde",
    # Olcum sonrasi eklenenler: ceviri orneklerinde bunlar Ingilizce kalmisti
    # ve cumleyi bozuyordu (or. "sicaklik dependent direnc").
    "dependent": "bagli", "coefficient": "katsayi", "cell": "hucre",
    "cells": "hucreler", "solar": "gunes", "button": "dugme", "push": "basmali",
    "mount": "montaj", "surface": "yuzey", "through": "delikli",
    "two": "iki", "three": "uc", "four": "dort", "eight": "sekiz",
    "general": "genel", "purpose": "amacli", "clock": "saat", "timer": "zamanlayici",
    "reset": "reset", "enable": "etkinlestirme", "ground": "toprak",
    "shunt": "sont", "bypass": "bypass", "coupling": "kuplaj",
    "decoupling": "ayirma", "termination": "sonlandirma", "pull-up": "cekme direnci",
    "pull-down": "asagi cekme", "open-drain": "acik drenaj",
    "wide": "genis", "narrow": "dar", "band": "bant", "frequency": "frekans",
    "gain": "kazanc", "noise": "gurultu", "offset": "kayma", "drift": "surukleme",
    "precision": "hassas", "accuracy": "dogruluk", "resolution": "cozunurluk",
    "programmable": "programlanabilir", "configurable": "yapilandirilabilir",
    "interface": "arayuz", "bus": "veri yolu", "serial": "seri", "parallel": "paralel",
    "wireless": "kablosuz", "radio": "telsiz", "optical": "optik",
    "magnetic": "manyetik", "thermal": "isil", "mechanical": "mekanik",
    "housing": "muhafaza", "shape": "sekil", "outline": "dis hat",
    "marker": "isaret", "adapter": "adaptor", "rail": "ray",
    "photoresistor": "foto direnc", "photocoupler": "foto kuplor",
    "varactor": "varaktor", "tvs": "tvs (asiri gerilim koruma)",
    "crystal": "kristal", "quartz": "kuvars", "ceramic": "seramik",
    "electrolytic": "elektrolitik", "tantalum": "tantal", "film": "film",
    "jack": "jak", "barrel": "varil", "ribbon": "serit",
    "potentiometer": "potansiyometre", "encoder": "kodlayici",
    "solenoid": "solenoid", "stepper": "adim motoru", "brushless": "fircasiz",
}

# Cok kelimeli kaliplar. Kelime kelime cevirmek bunlarda YANLIS okunuyor:
# olculdu - "Through hole" -> "Through delik", "Single solar cell" ->
# "tek solar cell". Kaliplar kelime degisiminden ONCE uygulanir.
PHRASES: dict[str, str] = {
    "through hole": "delikli montaj",
    "surface mount": "yuzey montaj",
    "push button": "basmali dugme",
    "solar cell": "gunes pili",
    "solar cells": "gunes pilleri",
    "general purpose": "genel amacli",
    "low dropout": "dusuk dusumlu",
    "low-dropout": "dusuk dusumlu",
    "temperature coefficient": "sicaklik katsayisi",
    "temperature dependent": "sicakliga bagli",
    "voltage dependent": "gerilime bagli",
    "light dependent": "isiga bagli",
    "operational amplifier": "islemsel yukseltec",
    "instrumentation amplifier": "enstrumantasyon yukselteci",
    "current sense": "akim algilama",
    "level shifter": "seviye donusturucu",
    "load switch": "yuk anahtari",
    "gate driver": "kapi surucusu",
    "half bridge": "yarim kopru",
    "full bridge": "tam kopru",
    "single row": "tek sira",
    "double row": "cift sira",
    "screw terminal": "vidali klemens",
    "crystal oscillator": "kristal osilator",
    "real time clock": "gercek zamanli saat",
    "watchdog timer": "bekci zamanlayici",
    "shift register": "kaydirmali yazmac",
    "power supply": "guc kaynagi",
    "step down": "gerilim dusurucu",
    "step up": "gerilim yukseltici",
}

# Bilincli olarak CEVRILMEYENLER - ozel ad ya da standart kisaltma.
# Sozlukte yer almamalari bir eksiklik degil, karar.
CEVRILMEZ = (
    "sot", "soic", "lqfp", "qfn", "dip", "tssop", "msop", "bga", "sod", "smd",
    "usb", "spi", "i2c", "uart", "can", "hdmi", "pcie", "sata", "rj",
    "arm", "cortex-m", "stm", "stmicroelectronics", "nxp", "texas", "microchip",
    "mhz", "khz", "ghz", "kicad-library-utils", "script", "generated",
)


# --------------------------------------------------------------------------
# Hasat
# --------------------------------------------------------------------------


@dataclass
class Entry:
    """Tek bir kutuphane sembolu."""

    lib_id: str
    designator: str
    en: str                       # kutuphanenin kendi aciklamasi
    keywords: str = ""
    tr: str = ""                  # TERMS'ten uretilen karsilik; yoksa bos
    category_en: str = ""
    category_tr: str = ""

    def as_dict(self) -> dict:
        d = {"id": self.lib_id, "ref": self.designator, "en": self.en}
        if self.keywords:
            d["k"] = self.keywords
        if self.tr:
            d["tr"] = self.tr
        return d


_BLOK = re.compile(r'\n\t\(symbol "')
_ALAN = re.compile(r'\(property "(Reference|Description|ki_keywords)" "((?:[^"\\]|\\.)*)"')
_KELIME = re.compile(r"[A-Za-z][A-Za-z\-]*")


def normalize_designator(ref: str) -> str:
    """`U6`, `RL2`, `MES?` -> `U`, `RL`, `MES`.

    Bunlar ayri onek DEGIL, kutuphanenin yazim tutarsizligi: bazi sembollerin
    Reference alanina ornek numarasi ya da soru isareti sizmis. Olculdu
    (KiCad 10.0.4): U1/U2/U3/U6, RL2, MES?, U? - toplam 7 varyant, 71 sembol.
    Bunlari ayri onek saymak sozlukte hayalet girdiler uretirdi.

    Kirpma YALNIZCA sonucu tanimli bir onege dusuruyorsa uygulanir; boylece
    gercekten yeni bir onek sessizce yutulmaz.
    """
    if not ref or ref in DESIGNATORS:
        return ref
    kirpilmis = ref.rstrip("?")
    while kirpilmis and kirpilmis[-1].isdigit():
        kirpilmis = kirpilmis[:-1]
    return kirpilmis if kirpilmis in DESIGNATORS else ref


def gloss(text: str) -> str:
    """Ingilizce metni TERMS ile Turkcelestirir. Eslesme yoksa BOS doner.

    Kelime kelime degistirir; bilmedigi kelimeyi OLDUGU GIBI birakir. Hicbir
    terim tutmazsa bos doner - yarim yamalak bir "ceviri" uretip onu Turkce
    diye sunmak, hic cevirmemekten kotudur.
    """
    if not text:
        return ""
    tutan = 0

    # Once cok kelimeli kaliplar - uzundan kisaya, ki "low dropout regulator"
    # icindeki "low" tek basina yakalanip kalibi bozmasin.
    sonuc = text
    for kalip in sorted(PHRASES, key=len, reverse=True):
        desen = re.compile(re.escape(kalip), re.IGNORECASE)
        if desen.search(sonuc):
            sonuc = desen.sub(PHRASES[kalip], sonuc)
            tutan += 1

    def degistir(m: re.Match) -> str:
        nonlocal tutan
        kelime = m.group(0)
        karsilik = TERMS.get(kelime.lower())
        if karsilik:
            tutan += 1
            return karsilik
        return kelime

    sonuc = _KELIME.sub(degistir, sonuc)
    return sonuc if tutan else ""


def harvest(libraries: dict[str, str] | None = None) -> list[Entry]:
    """Kurulu KiCad sembol kutuphanelerini tarar."""
    from . import symlib

    libs = libraries if libraries is not None else symlib.libraries()
    out: list[Entry] = []
    for lib_ad, yol in sorted(libs.items()):
        try:
            metin = Path(yol).read_text(encoding="utf-8")
        except OSError:
            continue
        for blok in _BLOK.split(metin)[1:]:
            ad = blok.split('"', 1)[0]
            alanlar = dict(_ALAN.findall(blok))
            ref = normalize_designator((alanlar.get("Reference") or "").strip())
            aciklama = (alanlar.get("Description") or "").strip()
            kategori = DESIGNATORS.get(ref, {})
            out.append(Entry(
                lib_id=f"{lib_ad}:{ad}",
                designator=ref,
                en=aciklama,
                keywords=(alanlar.get("ki_keywords") or "").strip(),
                tr=gloss(aciklama),
                category_en=kategori.get("en", ""),
                category_tr=kategori.get("tr", ""),
            ))
    return out


def kapsam(entries: list[Entry]) -> dict:
    """Sozlugun ne kadarini gercekten kapsadigimiz - saklanmayacak sayi."""
    toplam = len(entries)
    tr_var = sum(1 for e in entries if e.tr)
    kategori_var = sum(1 for e in entries if e.category_tr)
    bilinmeyen = sorted({e.designator for e in entries if e.designator
                         and e.designator not in DESIGNATORS})
    return {
        "sembol": toplam,
        "turkce_karsilik": tr_var,
        "turkce_oran": round(100 * tr_var / toplam, 1) if toplam else 0.0,
        "kategori_bilinen": kategori_var,
        "kategori_oran": round(100 * kategori_var / toplam, 1) if toplam else 0.0,
        "tanimsiz_onek": bilinmeyen,
    }


# --------------------------------------------------------------------------
# Uretim / okuma
# --------------------------------------------------------------------------


def build(out: Path | None = None) -> dict:
    """Sozlugu uretir ve sikistirilmis JSON olarak yazar."""
    entries = harvest()
    veri = {
        "surum": SURUM,
        "designators": DESIGNATORS,
        "terimler": TERMS,
        "cevrilmez": list(CEVRILMEZ),
        "kapsam": kapsam(entries),
        "semboller": [e.as_dict() for e in entries],
    }
    hedef = Path(out) if out else SOZLUK_DOSYASI
    hedef.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(hedef, "wt", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, separators=(",", ":"))
    return veri


def load(path: Path | None = None) -> dict:
    """Uretilmis sozlugu okur. Yoksa FileNotFoundError."""
    hedef = Path(path) if path else SOZLUK_DOSYASI
    with gzip.open(hedef, "rt", encoding="utf-8") as f:
        return json.load(f)


def lookup(term: str) -> dict:
    """Bir kisaltma ya da kelime icin bilinen her seyi doner."""
    t = term.strip()
    sonuc: dict = {"sorgu": t}
    if t.upper() in DESIGNATORS:
        sonuc["onek"] = DESIGNATORS[t.upper()]
    dusuk = t.lower()
    if dusuk in TERMS:
        sonuc["terim_tr"] = TERMS[dusuk]
    ters = [en for en, tr in TERMS.items() if tr == dusuk]
    if ters:
        sonuc["terim_en"] = ters

    # TAM KELIME arar, alt dizi degil. Olculdu: alt dizi aramasi 'C' icin 41
    # onek donduruyordu ("Capacitor", "Circuit", "Microphone"... hepsinde 'c'
    # var). Boyle bir sonuc listesi bilgi degil gurultudur.
    desen = re.compile(rf"\b{re.escape(dusuk)}\b", re.IGNORECASE)
    onekler = [k for k, v in DESIGNATORS.items()
               if desen.search(v["en"]) or desen.search(v["tr"])]
    if onekler:
        sonuc["eslesen_onekler"] = onekler

    # Uretilmis sozluk varsa sembollerde de ara (en fazla 8 ornek).
    if SOZLUK_DOSYASI.is_file():
        try:
            semboller = load()["semboller"]
        except (OSError, ValueError):
            semboller = []
        bulunan = [e["id"] for e in semboller
                   if desen.search(e.get("en", "")) or desen.search(e.get("tr", ""))]
        if bulunan:
            sonuc["sembol_sayisi"] = len(bulunan)
            sonuc["sembol_ornek"] = bulunan[:8]
    return sonuc


# --------------------------------------------------------------------------
# Komut satiri
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pcbqa.lexicon",
        description="KiCad kutuphanelerinden iki dilli bilesen sozlugu.",
    )
    ap.add_argument("--uret", action="store_true", help="Sozlugu uret ve yaz")
    ap.add_argument("--ara", metavar="TERIM", help="Kisaltma ya da kelime ara")
    ap.add_argument("--cikti", metavar="YOL", default=None, help="Uretim hedefi")
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)

    if args.ara:
        sonuc = lookup(args.ara)
        if len(sonuc) == 1:
            print(f"'{args.ara}' icin kayit yok")
            return 1
        for anahtar, deger in sonuc.items():
            print(f"  {anahtar:<16} {deger}")
        return 0

    if args.uret:
        print("sozluk uretiliyor - KiCad kutuphaneleri taraniyor...")
        veri = build(Path(args.cikti) if args.cikti else None)
        hedef = Path(args.cikti) if args.cikti else SOZLUK_DOSYASI
        k = veri["kapsam"]
        print(f"  yazildi: {hedef}  ({hedef.stat().st_size // 1024} KB)")
        print(f"  sembol            : {k['sembol']}")
        print(f"  referans oneki    : {len(DESIGNATORS)} tanimli")
        print(f"  terim             : {len(TERMS)}")
        print(f"  kategorisi bilinen: {k['kategori_bilinen']} (%{k['kategori_oran']})")
        print(f"  Turkce karsiligi  : {k['turkce_karsilik']} (%{k['turkce_oran']})")
        if k["tanimsiz_onek"]:
            print(f"  tanimsiz onek     : {', '.join(k['tanimsiz_onek'][:20])}")
        return 0

    # Ozet
    print("pcbqa sozluk")
    print(f"  referans oneki : {len(DESIGNATORS)}")
    print(f"  terim (en->tr) : {len(TERMS)}")
    if SOZLUK_DOSYASI.is_file():
        veri = load()
        k = veri.get("kapsam", {})
        print(f"  uretilmis sozluk: {k.get('sembol', '?')} sembol "
              f"({SOZLUK_DOSYASI.stat().st_size // 1024} KB)")
        print(f"    kategorisi bilinen %{k.get('kategori_oran', 0)}, "
              f"Turkce karsiligi %{k.get('turkce_oran', 0)}")
    else:
        print("  uretilmis sozluk: YOK - uretmek icin: pcbqa sozluk --uret")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
