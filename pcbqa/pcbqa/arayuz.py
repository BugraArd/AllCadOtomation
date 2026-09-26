"""MASAUSTU ARAYUZU (tkinter) - islerin pencereden yurutulmesi.

    pcbqa arayuz

Alti sekme, hepsi ayni projeyi hedefler:

    Yap       dogal dil komutu -> plan -> uygula        (`komut.py`)
    Parcalar  ag / gerilim / akim / MPN / fiyat tablosu (`elektrik.py`)
    Analiz    kalite raporu ve skor                     (`__main__.py`)
    Uret      niyet dosyasindan kart uret / kesfet      (`generate`, `explore`)
    Canli     acik PCB oku/yaz, yerlestir; sematik komut (`canli`, `canli_pcb`,
              `canli_sematik`)
    Ortam     ortam denetimi + arayuzun dagarcigi       (`app`, `komut`)

## Olculmus kisit: KiCad'in Python'unda tkinter YOK

    "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" -c "import tkinter"
    -> ModuleNotFoundError: No module named '_tkinter'

Bu onemli, cunku `pcbqa.cmd` yorumlayici olarak ONCE KiCad'inkini secer
(bkz. `app.py`: ayri bir Python gomulmemesinin gerekcesi). Yani arayuz,
baslaticinin varsayilan yorumlayicisiyla ACILAMAZ. Iki karsilik:

  * `main()` tkinter'i bulamazsa CIKMAZ; tkinter'i OLAN bir Python arar
    (`py -3`, PATH'teki `python`) ve arayuzu onunla yeniden baslatir. Ne
    yaptigini yazar - sessizce baska bir yorumlayiciya gecmez.
  * Hicbiri yoksa ne yapilacagini soyler ve CLI'ye yonlendirir. Arayuz
    CLI'nin yerine gecmez, ustune biner: her sekme ayni modulun ayni
    fonksiyonunu cagirir, ikinci bir mantik yazilmaz.

## Iki adimli guvenlik korunur

CLI'de varsayilan dry-run'dir ve yazmak icin `--uygula` gerekir. Arayuzde
bunun karsiligi: "Uygula" dugmesi BASLANGICTA KAPALIDIR ve yalnizca AYNI
cumle + AYNI proje icin bir kuru kosum gectikten sonra acilir. Cumle ya da
proje degisirse tekrar kapanir - ekranda gordugunuz planla yazilan planin
ayni olmasi bu sekilde garanti edilir.

Uzun suren isler (netlist, ERC, yerlestirme) ayri bir is parcaciginda kosar;
pencere donmaz, ama ayni anda tek is calisir (dugmeler kilitlenir).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import queue
import subprocess
import sys
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path

AYAR_DOSYASI = Path.home() / ".pcbqa" / "arayuz.json"
BASLIK = "pcbqa"


# --------------------------------------------------------------------------
# Ayarlar - yalnizca kolaylik; kaybolursa hicbir sey bozulmaz
# --------------------------------------------------------------------------


def ayar_oku() -> dict:
    try:
        return json.loads(AYAR_DOSYASI.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def ayar_yaz(veri: dict) -> None:
    try:
        AYAR_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
        AYAR_DOSYASI.write_text(json.dumps(veri, indent=2, ensure_ascii=False),
                                encoding="utf-8")
    except OSError:
        pass  # ayar yazilamamasi isi durdurmaz


# --------------------------------------------------------------------------
# Arka plan isi
# --------------------------------------------------------------------------


@dataclass
class Sonuc:
    ad: str
    deger: object = None
    hata: BaseException | None = None
    cikti: str = ""


def _yakala(fn, *args, **kwargs) -> tuple[object, str]:
    """Fonksiyonu calistirir ve stdout'una yazdigini da toplar.

    Alt komutlarin cogu (`analiz`, `uret`) sonucunu YAZDIRARAK verir. Ayni
    metni arayuzde gostermek icin ikinci bir bicimlendirici yazmak, iki
    ciktinin zamanla ayrismasi demekti - o yuzden dogrudan yakalaniyor.
    Ayni anda tek is kostugu icin (dugmeler kilitli) bu guvenli.
    """
    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon), contextlib.redirect_stderr(tampon):
        deger = fn(*args, **kwargs)
    return deger, tampon.getvalue()


# --------------------------------------------------------------------------
# Pencere
# --------------------------------------------------------------------------


class Arayuz:
    def __init__(self, root, proje: str = ""):
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self.root = root
        self.kuyruk: queue.Queue[Sonuc] = queue.Queue()
        self.mesgul = False
        self.dugmeler: list = []
        # (cumle, proje) - "Uygula"nin acik olabilecegi tek durum
        self.kuru_imza: tuple[str, str] | None = None
        self.kuru_yorum = None
        self.canli_plan = None
        self.canli_proje = None
        self.sematik_plan = None
        self.sematik_imza = None
        self.pcb_plan = None
        self.pcb_imza = None
        self.satirlar: list = []

        ayar = ayar_oku()
        root.title(BASLIK)
        root.geometry("1180x760")
        root.minsize(900, 600)

        self.proje = tk.StringVar(value=proje or ayar.get("proje", ""))
        self.niyet = tk.StringVar(value=ayar.get("niyet", ""))
        self.hedef = tk.StringVar(value=ayar.get("hedef", ""))
        self.varyant = tk.StringVar(value=str(ayar.get("varyant", 4)))
        self.komut = tk.StringVar(value="")
        self.sematik_komut = tk.StringVar(value="2 adet 100nF kondansator ekle")
        self.pcb_komut = tk.StringVar(value="R1 konumunu 50 30 yap")
        self.durum = tk.StringVar(value="hazir")

        self._proje_satiri()
        self.defter = ttk.Notebook(root)
        self.defter.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self._sekme_yap()
        self._sekme_parcalar()
        self._sekme_analiz()
        self._sekme_uret()
        self._sekme_canli()
        self.sematik_komut.trace_add("write", lambda *_: self._sematik_sifirla())
        self.proje.trace_add("write", lambda *_: self._sematik_sifirla())
        self.pcb_komut.trace_add("write", lambda *_: self._pcb_sifirla())
        self.proje.trace_add("write", lambda *_: self._pcb_sifirla())
        self._sekme_ortam()
        self._durum_cubugu()

        root.protocol("WM_DELETE_WINDOW", self._kapat)
        # Zamanlayici kimligi SAKLANIR: pencere kapandiktan sonra bekleyen bir
        # `after` cagrisi Tcl'de `invalid command name` uretiyordu (olculdu).
        self.zamanlayici = root.after(100, self._kuyrugu_isle)

    # -- ust satir ---------------------------------------------------------

    def _proje_satiri(self):
        tk, ttk = self.tk, self.ttk
        cerceve = ttk.Frame(self.root)
        cerceve.pack(fill="x", padx=8, pady=8)
        ttk.Label(cerceve, text="Proje:").pack(side="left")
        giris = ttk.Entry(cerceve, textvariable=self.proje)
        giris.pack(side="left", fill="x", expand=True, padx=6)
        giris.bind("<KeyRelease>", lambda _e: self._sil_silah())
        ttk.Button(cerceve, text="Klasor...", command=self._proje_sec_klasor
                   ).pack(side="left")
        ttk.Button(cerceve, text="Dosya...", command=self._proje_sec_dosya
                   ).pack(side="left", padx=(4, 0))

    def _proje_sec_klasor(self):
        from tkinter import filedialog

        yol = filedialog.askdirectory(title="KiCad proje klasoru")
        if yol:
            self.proje.set(yol)
            self._sil_silah()

    def _proje_sec_dosya(self):
        from tkinter import filedialog

        yol = filedialog.askopenfilename(
            title="KiCad proje dosyasi", filetypes=[("KiCad", "*.kicad_sch *.kicad_pcb *.kicad_pro")])
        if yol:
            self.proje.set(yol)
            self._sil_silah()

    # -- sekme: Yap --------------------------------------------------------

    def _sekme_yap(self):
        ttk = self.ttk
        sayfa = ttk.Frame(self.defter)
        self.defter.add(sayfa, text="Yap")

        ust = ttk.Frame(sayfa)
        ust.pack(fill="x", padx=8, pady=8)
        ttk.Label(ust, text="Komut:").pack(side="left")
        giris = ttk.Entry(ust, textvariable=self.komut, font=("Segoe UI", 11))
        giris.pack(side="left", fill="x", expand=True, padx=6)
        giris.bind("<Return>", lambda _e: self._anla())
        giris.bind("<KeyRelease>", lambda _e: self._sil_silah())
        self.b_anla = ttk.Button(ust, text="Anla (kuru kosum)", command=self._anla)
        self.b_anla.pack(side="left")
        self.b_uygula = ttk.Button(ust, text="Uygula", command=self._uygula,
                                   state="disabled")
        self.b_uygula.pack(side="left", padx=(4, 0))
        self.dugmeler += [self.b_anla, self.b_uygula]

        ornek = ttk.Frame(sayfa)
        ornek.pack(fill="x", padx=8)
        ttk.Label(ornek, text="ornekler:", foreground="#666").pack(side="left")
        for metin in ("10 adet kapasitor ekle",
                      "5 adet 100nF 0603 kondansator ve 3 adet 10k direnc ekle",
                      "2 polarize kapasitor 4u7 koy"):
            ttk.Button(ornek, text=metin, width=len(metin) + 2,
                       command=lambda m=metin: self._ornek(m)).pack(side="left", padx=3)

        self.yap_cikti = self._metin_alani(sayfa)

    def _ornek(self, metin: str):
        self.komut.set(metin)
        self._sil_silah()

    def _sil_silah(self):
        """Cumle ya da proje degisti - gosterilen plan artik gecerli degil."""
        if self.canli_proje != self.proje.get().strip():
            self.canli_plan = None
            if hasattr(self, "b_canli_uygula"):
                self.b_canli_uygula.config(state="disabled")
        if self.kuru_imza != (self.komut.get().strip(), self.proje.get().strip()):
            self.kuru_imza = None
            self.kuru_yorum = None
            if not self.mesgul:
                self.b_uygula.config(state="disabled")

    def _hedef_sematik(self, proje_metni: str):
        """Proje metninden kok sematik. Metin ARGUMANDIR, Tk degiskeni degil.

        tkinter is parcacigi guvenli DEGILDIR: bir `StringVar.get()`i arka
        plandan cagirmak "main thread is not in main loop" ile patlar
        (olculdu - arayuzun ilk surumunde dort test bu yuzden dustu). Bu
        yuzden her Tk degeri ANA IS PARCACIGINDA okunup fotografi arka plana
        gecirilir.
        """
        from .komut import kok_sematik

        metin = (proje_metni or "").strip()
        if metin and Path(metin).suffix in (".kicad_pcb", ".kicad_pro"):
            metin = str(Path(metin).with_suffix(".kicad_sch"))
        return kok_sematik(Path(metin) if metin else None)

    def _anla(self):
        from .komut import anla, uygula

        metin = self.komut.get().strip()
        proje = self.proje.get()          # ANA is parcaciginda okunur
        if not metin:
            self._yaz(self.yap_cikti, "bir komut cumlesi yazin.")
            return

        def is_():
            from .komut import KomutError

            yorum = anla(metin)
            if not yorum.ok:
                return yorum, None, None
            hedef = self._hedef_sematik(proje)
            try:
                sonuclar = uygula(yorum, hedef, apply=False)
            except KomutError as exc:
                yorum.engeller.append(str(exc))
                return yorum, hedef, None
            return yorum, hedef, sonuclar

        self._calistir("anla", is_, self._anla_bitti)

    def _anla_bitti(self, s: Sonuc):
        if s.hata:
            self._yaz(self.yap_cikti, f"hata: {s.hata}")
            return
        yorum, hedef, sonuclar = s.deger
        satirlar = [yorum.describe()]
        if hedef is not None:
            satirlar.append(f"  hedef: {hedef}")
        gecti = bool(sonuclar)
        for sonuc in sonuclar or []:
            satirlar += ["", sonuc.plan.describe()]
            if sonuc.diff is not None:
                if sonuc.diff.ok:
                    satirlar.append("  kalkan: mevcut devre degismedi, "
                                    "yalnizca yeni bilesenler eklendi")
                else:
                    satirlar.append(f"  KALKAN REDDETTI: {sonuc.diff.describe()}")
                    satirlar += ["  " + r for r in sonuc.diff.details()]
                    gecti = False
            if not sonuc.plan.ok:
                gecti = False
        if sonuclar and len(sonuclar) < len(yorum.eylemler):
            satirlar.append(f"  DURDURULDU: {len(yorum.eylemler) - len(sonuclar)} "
                            "eylem calistirilmadi")
            gecti = False

        if gecti:
            self.kuru_imza = (self.komut.get().strip(), self.proje.get().strip())
            self.kuru_yorum = yorum
            self.b_uygula.config(state="normal")
            satirlar += ["", "  kuru kosum gecti - yazmak icin 'Uygula'."]
            self.durum.set("kuru kosum gecti - 'Uygula' acildi")
        else:
            self.kuru_imza = None
            self.b_uygula.config(state="disabled")
            self.durum.set("kuru kosum gecmedi - yazma kapali")
        self._yaz(self.yap_cikti, "\n".join(satirlar))

    def _uygula(self):
        from tkinter import messagebox

        from .komut import uygula

        imza = (self.komut.get().strip(), self.proje.get().strip())
        if self.kuru_imza != imza or self.kuru_yorum is None:
            messagebox.showwarning(
                BASLIK,
                "Gosterilen plan bu cumleye ait degil. Once 'Anla' calistirin.")
            self.b_uygula.config(state="disabled")
            return
        eylemler = "\n".join("  " + e.describe() for e in self.kuru_yorum.eylemler)
        if not messagebox.askokcancel(
                BASLIK, f"Sematige YAZILACAK:\n\n{eylemler}\n\n"
                        f"Hedef: {imza[1] or 'bulundugun klasor'}\n\n"
                        "Yedek alinir; KiCad acikken yazma reddedilir."):
            return

        yorum = self.kuru_yorum
        proje = self.proje.get()

        def is_():
            return uygula(yorum, self._hedef_sematik(proje), apply=True)

        self._calistir("uygula", is_, self._uygula_bitti)

    def _uygula_bitti(self, s: Sonuc):
        if s.hata:
            self._yaz(self.yap_cikti, f"hata: {s.hata}")
            self.durum.set("yazilamadi")
            return
        satirlar = []
        yazilan = 0
        for sonuc in s.deger:
            satirlar += [sonuc.plan.describe()]
            if sonuc.applied and sonuc.write is not None:
                yazilan += 1
                yedek = (f" (yedek: {sonuc.write.backup.name})"
                         if sonuc.write.backup else "")
                satirlar.append(f"  yazildi: {sonuc.write.path}{yedek}")
            satirlar.append("")
        self._yaz(self.yap_cikti, "\n".join(satirlar))
        self.durum.set(f"{yazilan} eylem yazildi")
        # Yazildi: ayni cumleyi yanlislikla ikinci kez uygulamayi engelle.
        self.kuru_imza = None
        self.kuru_yorum = None
        self.b_uygula.config(state="disabled")

    # -- sekme: Parcalar ---------------------------------------------------

    def _sekme_parcalar(self):
        from .elektrik import BASLIKLAR

        ttk = self.ttk
        sayfa = ttk.Frame(self.defter)
        self.defter.add(sayfa, text="Parcalar")

        ust = ttk.Frame(sayfa)
        ust.pack(fill="x", padx=8, pady=8)
        b = ttk.Button(ust, text="Tabloyu cikar", command=self._parcalar)
        b.pack(side="left")
        b2 = ttk.Button(ust, text="CSV'ye yaz...", command=self._parcalar_csv)
        b2.pack(side="left", padx=4)
        self.dugmeler += [b, b2]
        ttk.Label(ust, text="  MPN ve fiyat SENTETIKTIR (test verisi). "
                            "Bos hucre = turetilemedi.",
                  foreground="#a33").pack(side="left")

        cerceve = ttk.Frame(sayfa)
        cerceve.pack(fill="both", expand=True, padx=8)
        self.agac = ttk.Treeview(cerceve, columns=BASLIKLAR, show="headings")
        genislikler = {"Ref": 60, "Deger": 90, "Tur": 130, "Aglar": 260,
                       "Gerilim": 110, "Akim": 80, "MPN": 180, "Fiyat": 70,
                       "Nasil bilindi": 300}
        for ad in BASLIKLAR:
            self.agac.heading(ad, text=ad)
            self.agac.column(ad, width=genislikler.get(ad, 120), anchor="w")
        kaydirma = ttk.Scrollbar(cerceve, orient="vertical",
                                 command=self.agac.yview)
        self.agac.configure(yscrollcommand=kaydirma.set)
        self.agac.pack(side="left", fill="both", expand=True)
        kaydirma.pack(side="right", fill="y")
        self.agac.bind("<<TreeviewSelect>>", self._parca_secildi)

        self.parca_detay = ttk.Label(sayfa, text="", foreground="#444",
                                     wraplength=1100, justify="left")
        self.parca_detay.pack(fill="x", padx=8, pady=(4, 8))

    def _parcalar(self):
        from .elektrik import ozet, tablo

        proje = self.proje.get()

        def is_():
            satirlar = tablo(self._hedef_sematik(proje))
            return satirlar, ozet(satirlar)

        self._calistir("parcalar", is_, self._parcalar_bitti)

    def _parcalar_bitti(self, s: Sonuc):
        from tkinter import messagebox

        from .elektrik import satir_hucreleri

        if s.hata:
            messagebox.showerror(BASLIK, str(s.hata))
            self.durum.set("tablo cikarilamadi")
            return
        self.satirlar, o = s.deger
        self.agac.delete(*self.agac.get_children())
        for satir in self.satirlar:
            self.agac.insert("", "end", values=satir_hucreleri(satir))
        self.durum.set(
            f"{o['parca']} parca | gerilimi bilinen {o['gerilimi_bilinen']} | "
            f"akimi turetilebilen {o['akimi_turetilebilen']} | "
            f"fiyati olan {o['fiyati_olan']} (toplam ${o['toplam_fiyat']:.4f})")

    def _parca_secildi(self, _event=None):
        secili = self.agac.selection()
        if not secili:
            return
        indis = self.agac.index(secili[0])
        if indis >= len(self.satirlar):
            return
        s = self.satirlar[indis]
        parcalar = [f"{s.ref}  {s.deger}  {s.lib_id}"]
        for pin, ag, volt in s.baglantilar:
            from .elektrik import ag_metni

            volt_metni = f"  = {volt:g} V" if volt is not None else ""
            parcalar.append(f"    pin {pin} -> {ag_metni(ag)}{volt_metni}")
        if s.gerilim_kaynak:
            parcalar.append(f"  gerilim: {s.gerilim_kaynak}")
        if s.akim_kaynak:
            parcalar.append(f"  akim: {s.akim_kaynak}")
        self.parca_detay.config(text="\n".join(parcalar))

    def _parcalar_csv(self):
        from tkinter import filedialog, messagebox

        from .elektrik import csv_yaz

        if not self.satirlar:
            messagebox.showinfo(BASLIK, "Once 'Tabloyu cikar' calistirin.")
            return
        yol = filedialog.asksaveasfilename(
            title="CSV olarak yaz", defaultextension=".csv",
            filetypes=[("CSV", "*.csv")])
        if not yol:
            return
        try:
            hedef = csv_yaz(self.satirlar, Path(yol))
        except OSError as exc:
            messagebox.showerror(BASLIK, str(exc))
            return
        self.durum.set(f"CSV yazildi: {hedef}")

    # -- sekme: Analiz -----------------------------------------------------

    def _sekme_analiz(self):
        ttk = self.ttk
        sayfa = ttk.Frame(self.defter)
        self.defter.add(sayfa, text="Analiz")
        ust = ttk.Frame(sayfa)
        ust.pack(fill="x", padx=8, pady=8)
        b = ttk.Button(ust, text="Kaliteyi olc", command=self._analiz)
        b.pack(side="left")
        self.dugmeler.append(b)
        ttk.Label(ust, text="  netlist + ERC + DRC calistirilir, birkac saniye "
                            "surebilir", foreground="#666").pack(side="left")
        self.analiz_cikti = self._metin_alani(sayfa)

    def _analiz(self):
        proje = self.proje.get().strip()

        def is_():
            from . import __main__ as ana

            if not proje:
                raise RuntimeError("once bir proje secin")
            _kod, cikti = _yakala(ana.main, [proje, "--no-color"])
            return cikti

        self._calistir("analiz", is_,
                       lambda s: self._basit_bitti(s, self.analiz_cikti, "analiz"))

    # -- sekme: Uret -------------------------------------------------------

    def _sekme_uret(self):
        ttk = self.ttk
        sayfa = ttk.Frame(self.defter)
        self.defter.add(sayfa, text="Uret")

        izgara = ttk.Frame(sayfa)
        izgara.pack(fill="x", padx=8, pady=8)
        ttk.Label(izgara, text="Niyet (YAML):").grid(row=0, column=0, sticky="w")
        ttk.Entry(izgara, textvariable=self.niyet, width=70).grid(
            row=0, column=1, sticky="we", padx=6)
        ttk.Button(izgara, text="Sec...", command=self._niyet_sec).grid(row=0, column=2)
        ttk.Label(izgara, text="Cikti klasoru:").grid(row=1, column=0, sticky="w",
                                                      pady=(6, 0))
        ttk.Entry(izgara, textvariable=self.hedef, width=70).grid(
            row=1, column=1, sticky="we", padx=6, pady=(6, 0))
        ttk.Button(izgara, text="Sec...", command=self._hedef_sec).grid(
            row=1, column=2, pady=(6, 0))
        izgara.columnconfigure(1, weight=1)

        dugme = ttk.Frame(sayfa)
        dugme.pack(fill="x", padx=8)
        b1 = ttk.Button(dugme, text="Uret", command=lambda: self._uret(False))
        b1.pack(side="left")
        b2 = ttk.Button(dugme, text="Kesfet", command=lambda: self._uret(True))
        b2.pack(side="left", padx=4)
        ttk.Label(dugme, text="varyant:").pack(side="left", padx=(12, 4))
        ttk.Entry(dugme, textvariable=self.varyant, width=5).pack(side="left")
        b3 = ttk.Button(dugme, text="Sablonlari listele", command=self._sablonlar)
        b3.pack(side="left", padx=12)
        self.dugmeler += [b1, b2, b3]

        self.uret_cikti = self._metin_alani(sayfa)

    def _niyet_sec(self):
        from tkinter import filedialog

        yol = filedialog.askopenfilename(title="Niyet dosyasi",
                                         filetypes=[("YAML", "*.yaml *.yml")])
        if yol:
            self.niyet.set(yol)

    def _hedef_sec(self):
        from tkinter import filedialog

        yol = filedialog.askdirectory(title="Cikti klasoru")
        if yol:
            self.hedef.set(yol)

    def _uret(self, kesfet: bool):
        niyet, hedef, varyant = (self.niyet.get().strip(),
                                 self.hedef.get().strip(), self.varyant.get().strip())

        def is_():
            if not niyet or not hedef:
                raise RuntimeError("niyet dosyasi ve cikti klasoru gerekli")
            argv = ["--intent", niyet, "--out", hedef]
            if kesfet:
                from . import explore as modul

                argv += ["--variants", varyant or "4"]
            else:
                from . import generate as modul
            _kod, cikti = _yakala(modul.main, argv)
            return cikti

        self._calistir("kesfet" if kesfet else "uret", is_,
                       lambda s: self._basit_bitti(s, self.uret_cikti, "uretim"))

    def _sablonlar(self):
        def is_():
            from . import intent

            _kod, cikti = _yakala(intent.main, ["--list"])
            return cikti

        self._calistir("sablonlar", is_,
                       lambda s: self._basit_bitti(s, self.uret_cikti, "sablonlar"))

    # -- sekme: Canli ------------------------------------------------------

    def _sekme_canli(self):
        ttk = self.ttk
        sayfa = ttk.Frame(self.defter)
        self.defter.add(sayfa, text="Canli")
        ttk.Label(sayfa, text="PCB: acik karti okuyun, komutla yazin veya otomatik yerlestirin; "
                  "her yazma tek Ctrl+Z ile geri alinir.\n"
                  "Sematik: asagidan ayri KiCad nightly ile canli proje kopyasi acin. "
                  "Degisiklikler kopyada kalir; kaydetmek icin KiCad'de Ctrl+S kullanin.", wraplength=1000).pack(
                      fill="x", padx=8, pady=8)
        ust = ttk.Frame(sayfa)
        ust.pack(fill="x", padx=8)
        for text, command in (
                ("PCB'yi ac", lambda: self._editor_ac("pcb")),
                ("Sematik (stabil)", lambda: self._editor_ac("sematik")),
                ("Baglantiyi kontrol et", self._canli_kontrol),
                ("API'yi etkinlestir", self._canli_etkinlestir),
                ("Bagimliliklari kur", self._canli_kur),
                ("Yerlesimi onizle", self._canli_onizle)):
            b = ttk.Button(ust, text=text, command=command)
            b.pack(side="left", padx=(0, 4))
            self.dugmeler.append(b)
        self.b_canli_uygula = ttk.Button(sayfa, text="Canli PCB'ye uygula",
                                        command=self._canli_uygula, state="disabled")
        self.b_canli_uygula.pack(anchor="w", padx=8, pady=8)
        pcb = ttk.LabelFrame(sayfa, text="Canli PCB okuma ve yazma")
        pcb.pack(fill="x", padx=8, pady=4)
        row = ttk.Frame(pcb)
        row.pack(fill="x", padx=6, pady=4)
        read = ttk.Button(row, text="PCB'yi oku", command=self._pcb_oku)
        read.pack(side="left", padx=(0, 4))
        self.dugmeler.append(read)
        ttk.Entry(row, textvariable=self.pcb_komut).pack(side="left", fill="x", expand=True)
        preview = ttk.Button(row, text="PCB komutunu onizle", command=self._pcb_onizle)
        preview.pack(side="left", padx=4)
        self.dugmeler.append(preview)
        self.b_pcb_uygula = ttk.Button(row, text="Canli PCB'ye yaz", state="disabled",
                                       command=self._pcb_uygula)
        self.b_pcb_uygula.pack(side="left")
        ttk.Label(pcb, text="Ornek: R1 konumunu 50 30 yap; C2 5 -2.5 kaydir; U1 90 dondur; "
                  "U1 acisini 180 yap; J1 kilitle; J1 kilidini ac; R1 degerini 10k yap",
                  wraplength=1050).pack(anchor="w", padx=6, pady=4)
        sch = ttk.LabelFrame(sayfa, text="Canli sematik (gelistirme surumu)")
        sch.pack(fill="x", padx=8, pady=4)
        row = ttk.Frame(sch)
        row.pack(fill="x", padx=6, pady=4)
        for label, command in (("Canli sematik kopyasini ac", self._sematik_ac),
                               ("Sematik baglantisini kontrol et", self._sematik_kontrol)):
            button = ttk.Button(row, text=label, command=command)
            button.pack(side="left", padx=3)
            self.dugmeler.append(button)
        row = ttk.Frame(sch)
        row.pack(fill="x", padx=6, pady=4)
        ttk.Entry(row, textvariable=self.sematik_komut).pack(side="left", fill="x", expand=True)
        preview = ttk.Button(row, text="Sematik komutunu onizle", command=self._sematik_onizle)
        preview.pack(side="left", padx=4)
        self.dugmeler.append(preview)
        self.b_sematik_uygula = ttk.Button(row, text="Canli sematige uygula", state="disabled",
                                          command=self._sematik_uygula)
        self.b_sematik_uygula.pack(side="left")
        ttk.Label(sch, text="Ornek: R1 degerini 10k yap | 2 adet 100nF kondansator ekle ve hepsini VCC ile GND arasina bagla",
                  wraplength=1050).pack(anchor="w", padx=6, pady=4)
        self.canli_cikti = self._metin_alani(sayfa)

    def _pcb_sifirla(self):
        self.pcb_plan = self.pcb_imza = None
        if hasattr(self, "b_pcb_uygula"):
            self.b_pcb_uygula.config(state="disabled")

    def _pcb_oku(self):
        from .canli_pcb import read_live
        project = self.proje.get().strip()
        self._calistir("PCB okuma", lambda: read_live(project),
                       lambda s: self._basit_bitti(s, self.canli_cikti, "PCB okuma"))

    def _pcb_onizle(self):
        from .canli_pcb import prepare_edit
        if self.mesgul:
            return
        self._pcb_sifirla()
        signature = (self.proje.get().strip(), self.pcb_komut.get().strip())

        def finished(s):
            if s.hata:
                self._basit_bitti(s, self.canli_cikti, "PCB onizleme")
            elif signature != (self.proje.get().strip(), self.pcb_komut.get().strip()):
                self._yaz(self.canli_cikti, "Proje veya komut degisti; yeni onizleme alin.")
            else:
                self.pcb_plan, self.pcb_imza = s.deger, signature
                self.b_pcb_uygula.config(state="normal")
                self._yaz(self.canli_cikti, s.deger.description)
                self.durum.set("Canli PCB onizlemesi hazir")

        self._calistir("PCB onizleme", lambda: prepare_edit(*signature), finished)

    def _pcb_uygula(self):
        from tkinter import messagebox
        from .canli_pcb import apply_edit
        if self.mesgul:
            return
        signature = (self.proje.get().strip(), self.pcb_komut.get().strip())
        if self.pcb_plan is None or self.pcb_imza != signature:
            messagebox.showwarning(BASLIK, "Once bu proje ve komut icin PCB onizlemesi alin.")
            return
        plan = self.pcb_plan
        if not messagebox.askokcancel(BASLIK, plan.description + "\n\nAcik PCB'ye yazilsin mi?"):
            return
        self._pcb_sifirla()
        self._calistir("canli PCB yazma", lambda: apply_edit(plan),
                       lambda s: self._basit_bitti(s, self.canli_cikti, "canli PCB yazma"))

    def _sematik_sifirla(self):
        self.sematik_plan = self.sematik_imza = None
        self.b_sematik_uygula.config(state="disabled")

    def _sematik_ac(self):
        from .canli_sematik import open_copy
        project = self.proje.get().strip()

        def finished(s):
            if s.hata:
                self._basit_bitti(s, self.canli_cikti, "canli sematik")
                return
            self.proje.set(s.deger["project"])
            self._sil_silah()
            self._yaz(self.canli_cikti, s.deger["description"])
            self.durum.set("Canli sematik kopyasi aciliyor")

        self._calistir("sematik kopyasi", lambda: open_copy(project), finished)

    def _sematik_kontrol(self):
        from .canli_sematik import request
        project = self.proje.get().strip()
        self._calistir("sematik baglantisi", lambda: request("check", project)["description"],
                       lambda s: self._basit_bitti(s, self.canli_cikti, "sematik baglantisi"))

    def _sematik_onizle(self):
        from .canli_sematik import request
        if self.mesgul:
            return
        self._sematik_sifirla()
        signature = (self.proje.get().strip(), self.sematik_komut.get().strip())

        def finished(s):
            if s.hata:
                self._basit_bitti(s, self.canli_cikti, "sematik onizleme")
            elif signature != (self.proje.get().strip(), self.sematik_komut.get().strip()):
                self._yaz(self.canli_cikti, "Proje veya komut degisti; yeni onizleme alin.")
            else:
                self.sematik_plan, self.sematik_imza = s.deger, signature
                self.b_sematik_uygula.config(state="normal")
                self._yaz(self.canli_cikti, s.deger["description"])
                self.durum.set("Canli sematik onizlemesi hazir")

        self._calistir("sematik onizleme", lambda: request("prepare", signature[0], command=signature[1]), finished)

    def _sematik_uygula(self):
        from tkinter import messagebox
        from .canli_sematik import request
        if self.mesgul:
            return
        signature = (self.proje.get().strip(), self.sematik_komut.get().strip())
        if self.sematik_plan is None or self.sematik_imza != signature:
            messagebox.showwarning(BASLIK, "Once bu proje ve komut icin sematik onizlemesi alin.")
            return
        plan = self.sematik_plan
        if not messagebox.askokcancel(BASLIK, plan["description"] + "\n\nAcik sematige uygulansin mi?"):
            return
        self._sematik_sifirla()
        self._calistir("canli sematik", lambda: request("apply", signature[0], plan=plan)["description"],
                       lambda s: self._basit_bitti(s, self.canli_cikti, "canli sematik"))

    def _editor_ac(self, kind):
        from .canli import open_editor
        project = self.proje.get().strip()
        self._calistir("editor", lambda: open_editor(project, kind),
                       lambda s: self._basit_bitti(s, self.canli_cikti, "editor"))

    def _canli_kontrol(self):
        from .canli import describe_connection
        from .kurulum import live_deps_details
        project = self.proje.get().strip()

        def work():
            deps = live_deps_details(Path(sys.executable))
            errors = [f"{n}: {v['error']}" for n, v in deps.items() if v["ok"] is not True]
            if errors:
                raise RuntimeError("Arayuzun baglanti kutuphaneleri:\n" + "\n".join(errors))
            return describe_connection(project)

        self._calistir("baglanti", work,
                       lambda s: self._basit_bitti(s, self.canli_cikti, "baglanti"))

    def _canli_kur(self):
        from .kurulum import install_live_deps

        def work():
            lines = []
            install_live_deps(Path(sys.executable), echo=lines.append)
            return "\n".join(lines) + "\nArayuz bagimliliklari dogrulandi."

        self._calistir("bagimliliklar", work,
                       lambda s: self._basit_bitti(s, self.canli_cikti, "kurulum"))

    def _canli_etkinlestir(self):
        from .kurulum import apply

        def work():
            changed = apply(True)
            if changed:
                return "API etkinlestirildi. KiCad'i yeniden acin."
            return "API zaten etkin. Baglantiyi kontrol et dugmesini kullanin."

        self._calistir("API kurulumu", work,
                       lambda s: self._basit_bitti(s, self.canli_cikti, "kurulum"))

    def _canli_onizle(self):
        from .canli import prepare
        if self.mesgul:
            return
        project = self.proje.get().strip()
        self.canli_plan = None
        self.b_canli_uygula.config(state="disabled")

        def finished(s):
            if s.hata:
                self._basit_bitti(s, self.canli_cikti, "onizleme")
                return
            if project != self.proje.get().strip():
                self._yaz(self.canli_cikti, "Proje degisti. Yeni onizleme alin.")
                return
            self.canli_plan, self.canli_proje = s.deger, project
            self._yaz(self.canli_cikti, s.deger.description)
            self.b_canli_uygula.config(state="normal")
            self.durum.set("Canli onizleme hazir")

        self._calistir("canli onizleme", lambda: prepare(project), finished)

    def _canli_uygula(self):
        from tkinter import messagebox
        from .canli import apply_plan
        if self.mesgul:
            return
        if self.canli_plan is None or self.canli_proje != self.proje.get().strip():
            messagebox.showwarning(BASLIK, "Once secili proje icin canli onizleme alin.")
            return
        plan = self.canli_plan
        if not messagebox.askokcancel(BASLIK, plan.description + "\n\nCanli PCB'ye uygulansin mi?"):
            return
        self.canli_plan = None
        self.b_canli_uygula.config(state="disabled")

        def work():
            summary = apply_plan(plan)
            return (f"Canli PCB'de {summary.changed} bilesen tasindi.\n"
                    "KiCad'de Ctrl+Z ile geri alabilirsiniz. Dosya otomatik kaydedilmedi.")

        self._calistir("canli uygulama", work,
                       lambda s: self._basit_bitti(s, self.canli_cikti, "canli uygulama"))

    # -- sekme: Ortam ------------------------------------------------------

    def _sekme_ortam(self):
        ttk = self.ttk
        sayfa = ttk.Frame(self.defter)
        self.defter.add(sayfa, text="Ortam")
        ust = ttk.Frame(sayfa)
        ust.pack(fill="x", padx=8, pady=8)
        b1 = ttk.Button(ust, text="Ortami denetle", command=self._tani)
        b1.pack(side="left")
        b2 = ttk.Button(ust, text="Dagarcik (anlanan turler)", command=self._dagarcik)
        b2.pack(side="left", padx=4)
        self.dugmeler += [b1, b2]
        self.ortam_cikti = self._metin_alani(sayfa)

    def _tani(self):
        def is_():
            from .app import diagnose

            satirlar, engel = diagnose()
            return "\n".join(satirlar) + (
                f"\n\n{engel} engel var" if engel else "\n\nTemel ortam hazir; canli baglantiyi Canli sekmesinden sinayin.")

        self._calistir("tani", is_,
                       lambda s: self._basit_bitti(s, self.ortam_cikti, "tani"))

    def _dagarcik(self):
        def is_():
            from . import komut

            _kod, cikti = _yakala(komut.main, ["--dagarcik"])
            return cikti

        self._calistir("dagarcik", is_,
                       lambda s: self._basit_bitti(s, self.ortam_cikti, "dagarcik"))

    # -- ortak -------------------------------------------------------------

    def _metin_alani(self, ana):
        tk, ttk = self.tk, self.ttk
        cerceve = ttk.Frame(ana)
        cerceve.pack(fill="both", expand=True, padx=8, pady=8)
        metin = tk.Text(cerceve, wrap="none", font=("Consolas", 10),
                        state="disabled", background="#fbfbfb")
        dikey = ttk.Scrollbar(cerceve, orient="vertical", command=metin.yview)
        yatay = ttk.Scrollbar(ana, orient="horizontal", command=metin.xview)
        metin.configure(yscrollcommand=dikey.set, xscrollcommand=yatay.set)
        metin.pack(side="left", fill="both", expand=True)
        dikey.pack(side="right", fill="y")
        yatay.pack(fill="x", padx=8, pady=(0, 6))
        return metin

    def _yaz(self, alan, metin: str):
        alan.config(state="normal")
        alan.delete("1.0", "end")
        alan.insert("1.0", metin)
        alan.config(state="disabled")

    def _basit_bitti(self, s: Sonuc, alan, ad: str):
        if s.hata:
            self._yaz(alan, f"hata: {s.hata}\n\n{s.cikti}")
            self.durum.set(f"{ad}: hata")
            return
        self._yaz(alan, str(s.deger) or "(cikti yok)")
        self.durum.set(f"{ad} bitti")

    def _durum_cubugu(self):
        ttk = self.ttk
        cubuk = ttk.Frame(self.root)
        cubuk.pack(fill="x", side="bottom")
        ttk.Separator(cubuk, orient="horizontal").pack(fill="x")
        ttk.Label(cubuk, textvariable=self.durum, anchor="w").pack(
            fill="x", padx=10, pady=4)

    def _calistir(self, ad: str, fn, bitince):
        if self.mesgul:
            return
        self.mesgul = True
        for d in self.dugmeler:
            d.config(state="disabled")
        self.b_uygula.config(state="disabled")
        self.b_canli_uygula.config(state="disabled")
        self.durum.set(f"{ad} calisiyor...")
        self.b_sematik_uygula.config(state="disabled")
        self.b_pcb_uygula.config(state="disabled")
        self._bitince = bitince

        def sarmal():
            try:
                deger, cikti = _yakala(fn)
                self.kuyruk.put(Sonuc(ad=ad, deger=deger, cikti=cikti))
            except BaseException as exc:  # noqa: BLE001 - arayuz cokmemeli
                self.kuyruk.put(Sonuc(ad=ad, hata=exc,
                                      cikti=traceback.format_exc()))

        threading.Thread(target=sarmal, daemon=True).start()

    def _kuyrugu_isle(self):
        self.zamanlayici = None
        try:
            if not self.root.winfo_exists():
                return
        except Exception:  # noqa: BLE001 - pencere zaten yok edilmis
            return
        try:
            while True:
                sonuc = self.kuyruk.get_nowait()
                self.mesgul = False
                for d in self.dugmeler:
                    d.config(state="normal")
                self.b_uygula.config(state="disabled")
                self.b_canli_uygula.config(state="normal" if self.canli_plan is not None
                    and self.canli_proje == self.proje.get().strip() else "disabled")
                self.b_sematik_uygula.config(state="normal" if self.sematik_plan is not None
                    and self.sematik_imza == (self.proje.get().strip(), self.sematik_komut.get().strip()) else "disabled")
                self.b_pcb_uygula.config(state="normal" if self.pcb_plan is not None
                    and self.pcb_imza == (self.proje.get().strip(), self.pcb_komut.get().strip()) else "disabled")
                geri = getattr(self, "_bitince", None)
                if geri:
                    try:
                        geri(sonuc)
                    except Exception:  # noqa: BLE001
                        self.durum.set("arayuz hatasi - ayrinti konsolda")
                        traceback.print_exc()
        except queue.Empty:
            pass
        self.zamanlayici = self.root.after(100, self._kuyrugu_isle)

    def durdur(self):
        """Zamanlayiciyi iptal eder. Pencereyi YOK ETMEZ."""
        if self.zamanlayici is not None:
            try:
                self.root.after_cancel(self.zamanlayici)
            except Exception:  # noqa: BLE001
                pass
            self.zamanlayici = None

    def _kapat(self):
        ayar_yaz({
            "proje": self.proje.get(), "niyet": self.niyet.get(),
            "hedef": self.hedef.get(), "varyant": self.varyant.get(),
        })
        self.durdur()
        self.root.destroy()


# --------------------------------------------------------------------------
# Yorumlayici secimi
# --------------------------------------------------------------------------


def tkinter_var(python: str | None = None) -> bool:
    """Bu (ya da verilen) Python tkinter'i getiriyor mu?"""
    if python is None:
        try:
            import tkinter  # noqa: F401

            return True
        except Exception:  # noqa: BLE001 - Tk yoksa ImportError disi hata da olur
            return False
    try:
        return subprocess.run([python, "-c", "import tkinter"],
                              capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def tkinterli_python() -> str | None:
    """tkinter'i olan bir yorumlayici ara. Bulamazsa None.

    KiCad'inki elenir - onda `_tkinter` yok (olculdu, KiCad 10.0.4).
    """
    for aday in ("py", "python", "python3"):
        if tkinter_var(aday):
            return aday
    return None


_YARDIM = """\
Bu Python tkinter getirmiyor, arayuz acilamaz.

Sebep olculdu: KiCad kendi Python'unu getiriyor ama icinde `_tkinter` YOK
(KiCad 10.0.4). `pcbqa.cmd` yorumlayici olarak once KiCad'inkini secer.

Cozum - tkinter'i olan bir Python gosterin:

    set PCBQA_PYTHON=C:\\Python313\\python.exe
    pcbqa arayuz

Arayuz olmadan ayni isler komut satirindan yapilabilir:

    pcbqa yap "10 adet kapasitor ekle"
    pcbqa parcalar <sematik>
    pcbqa analiz <proje>
"""


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pcbqa.arayuz", description="pcbqa masaustu arayuzu (tkinter).")
    ap.add_argument("--proje", default="", help="Acilista secili proje")
    ap.add_argument("--no-yeniden-baslat", action="store_true",
                    help="tkinter yoksa baska yorumlayici ARAMA")
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)

    if not tkinter_var():
        if args.no_yeniden_baslat or os.environ.get("PCBQA_ARAYUZ_TEKRAR"):
            print(_YARDIM, file=sys.stderr)
            return 2
        baska = tkinterli_python()
        if baska is None:
            print(_YARDIM, file=sys.stderr)
            return 2
        # Paketi bulduran onyukleyici (bkz. baslat.py): KiCad'in Python'u
        # PYTHONPATH'i yok sayiyor, o yuzden yol degil DOSYA calistiriyoruz.
        baslatici = Path(__file__).resolve().parent.parent / "baslat.py"
        komut = [baska, str(baslatici), "arayuz"] + (
            ["--proje", args.proje] if args.proje else [])
        print(f"bu Python'da tkinter yok; arayuz {baska} ile aciliyor")
        ortam = dict(os.environ, PCBQA_ARAYUZ_TEKRAR="1")
        try:
            return subprocess.call(komut, env=ortam)
        except OSError as exc:
            print(f"hata: {baska} calistirilamadi: {exc}", file=sys.stderr)
            print(_YARDIM, file=sys.stderr)
            return 2

    import tkinter as tk

    root = tk.Tk()
    Arayuz(root, proje=args.proje)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
