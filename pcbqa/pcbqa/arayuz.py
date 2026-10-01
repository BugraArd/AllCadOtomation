"""MASAUSTU ARAYUZU (tkinter) - islerin pencereden yurutulmesi.

    pcbqa arayuz

Yedi sekme, hepsi ustteki ayni projeyi (ve istege bagli kosullar dosyasini)
hedefler. 2026-10-02'de sadelestirildi (Kicad-5d6.11): Analiz + Dogrula tek
Kontrol sekmesinde, Ortam Canli'da, dagarcik Yap'ta.

    Yap       dogal dil komutu -> plan -> uygula; dagarcik  (`komut.py`)
    Devre     parca tablosu (ag/gerilim/akim/MPN/fiyat) + devre grafi
              (`elektrik.py`, `devre/__main__.py`)
    Kontrol   kalite skoru + seviye 1/2/3 + PCB dal akimi + 9 kontrol,
              ERC/DRC bir kez (`kontrol.py`)
    Duzelt    bulgu duzeltme (yazar) + elektriksel duzeltme onerisi (yazmaz)
              (`duzelt.py`, `duzeltme/sirala.py`)
    Deney     gercek proje deneyi: aday secimi, gerekce, envanter
              (`duzeltme/gorunum.py`, `envanter.py`, `proje.py`)
    Uret      niyet dosyasindan kart uret / kesfet, ardindan kontrol
              (`generate`, `explore`, `kontrol`)
    Canli     ortam denetimi, KiCad baglantisi, acik PCB oku/yaz/yerlestir,
              sematik komut (`app`, `canli`, `canli_pcb`, `canli_sematik`)

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

## Tek adimli yazma - guvenlik yazma kapilarinda

Kullanici talimati (2026-09-27): onizleme/kuru kosum adimi KALDIRILDI. "Uygula"
dugmeleri surekli aciktir; plan ile yazma ayni is parcaciginda zincirlenir, bu
yuzden "ekranda gordugun plan" ile "yazilan plan" zaten ayni olur ve imza
silahlanmasina gerek kalmaz.

Guvenlik onizlemeden DEGIL, yazma kapilarindan gelir ve hepsi korunur:
otomatik yedek, KiCad acikken yazma reddi, kalkan (mevcut devre degismedi mi),
netlist paritesi ve basarisiz dogrulamada yedekten geri alma.

Tek istisna: canli YERLESTIRME plani (`b_canli_uygula`) hala iki adimlidir -
yuzlerce bileseni tek tikla oynatmak geri alinabilir olsa da okunamaz.

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
        self.canli_plan = None
        self.canli_proje = None
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
        self.deney_kaynak = tk.StringVar(value=ayar.get("deney_kaynak", ""))
        self.deney_cikti = tk.StringVar(value=ayar.get("deney_cikti", ""))
        self.deney = None
        self.kosullar = tk.StringVar(value=ayar.get("kosullar", ""))
        self.kontrol_raporu = None

        self._proje_satiri()
        # Durum cubugu defterden ONCE paketlenir: sonra paketlenince genisleyen
        # defter onu pencerenin disina itiyordu (olculdu, Kosullar satiri eklenince).
        self._durum_cubugu()
        self.defter = ttk.Notebook(root)
        self.defter.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self._sekme_yap()
        self._sekme_devre()
        self._sekme_kontrol()
        self._sekme_duzelt()
        self._sekme_deney()
        self._sekme_uret()
        self._sekme_canli()
        self.proje.trace_add("write", lambda *_: self._sil_silah())

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
        # Kosullar: Devre, Kontrol (seviye 3) ve elektriksel duzeltme ortak kullanir.
        cerceve = ttk.Frame(self.root)
        cerceve.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Label(cerceve, text="Kosullar:").pack(side="left")
        ttk.Entry(cerceve, textvariable=self.kosullar).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(cerceve, text="Sec...", command=self._kosullar_sec).pack(side="left")
        ttk.Label(cerceve, text=" istege bagli (YAML/JSON): raylar, yukler, gereksinimler - "
                                "benzetim ve elektriksel duzeltme icin", foreground="#666").pack(side="left")

    def _proje_secildi(self, yol: str):
        """Proje degisti; yaninda kosullar dosyasi varsa ve alan bossa onu oner."""
        self.proje.set(yol)
        self._sil_silah()
        if not self.kosullar.get().strip():
            klasor = Path(yol) if Path(yol).is_dir() else Path(yol).parent
            for ad in ("kosullar.yaml", "kosullar.yml", "kosullar.json"):
                if (klasor / ad).is_file():
                    self.kosullar.set(str(klasor / ad))
                    break

    def _proje_sec_klasor(self):
        from tkinter import filedialog

        yol = filedialog.askdirectory(title="KiCad proje klasoru")
        if yol:
            self._proje_secildi(yol)

    def _proje_sec_dosya(self):
        from tkinter import filedialog

        yol = filedialog.askopenfilename(
            title="KiCad proje dosyasi", filetypes=[("KiCad", "*.kicad_sch *.kicad_pcb *.kicad_pro")])
        if yol:
            self._proje_secildi(yol)

    def _kosullar_sec(self):
        from tkinter import filedialog

        yol = filedialog.askopenfilename(title="Calisma kosullari",
                                         filetypes=[("Kosullar", "*.yaml *.yml *.json")])
        if yol:
            self.kosullar.set(yol)

    def _kosullar_yolu(self) -> Path | None:
        metin = self.kosullar.get().strip()
        return Path(metin) if metin else None

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
        giris.bind("<Return>", lambda _e: self._uygula())
        giris.bind("<KeyRelease>", lambda _e: self._sil_silah())
        self.b_uygula = ttk.Button(ust, text="Uygula", command=self._uygula)
        self.b_uygula.pack(side="left")
        self.dugmeler += [self.b_uygula]

        ornek = ttk.Frame(sayfa)
        ornek.pack(fill="x", padx=8)
        ttk.Label(ornek, text="ornekler:", foreground="#666").pack(side="left")
        for metin in ("10 adet kapasitor ekle",
                      "5 adet 100nF 0603 kondansator ve 3 adet 10k direnc ekle",
                      "2 polarize kapasitor 4u7 koy"):
            ttk.Button(ornek, text=metin, width=len(metin) + 2,
                       command=lambda m=metin: self._ornek(m)).pack(side="left", padx=3)
        b = ttk.Button(ornek, text="Dagarcik (anlanan turler)", command=self._dagarcik)
        b.pack(side="right")
        self.dugmeler.append(b)

        self.yap_cikti = self._metin_alani(sayfa)

    def _ornek(self, metin: str):
        self.komut.set(metin)
        self._sil_silah()

    def _sil_silah(self):
        """Proje degisti - saklanan canli plan artik bu projeye ait degil."""
        if self.canli_proje != self.proje.get().strip():
            self.canli_plan = None
            if hasattr(self, "b_canli_uygula"):
                self.b_canli_uygula.config(state="disabled")

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

    def _uygula(self):
        """Cumleyi anla ve AYNI kosumda sematige yaz.

        Ayri bir kuru kosum adimi yoktur (kullanici talimati, 2026-09-27).
        Guvenlik onizlemeden degil `sch_add`in kapilarindan gelir: kalkan
        (mevcut devre degismedi mi), yedek, KiCad kilit kontrolu ve netlist
        dogrulamasi orada korunur. Ilk engelde sonraki eylemler CALISMAZ -
        yarim uygulanmis bir cumle, hic uygulanmamis olandan zor toparlanir.
        """
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
                return yorum, None
            hedef = self._hedef_sematik(proje)
            try:
                sonuclar = uygula(yorum, hedef, apply=True)
            except KomutError as exc:
                yorum.engeller.append(str(exc))
                return yorum, None
            return yorum, sonuclar

        self._calistir("uygula", is_, self._uygula_bitti)

    def _uygula_bitti(self, s: Sonuc):
        """Yazma sonucunu dokur: ne anlasildi, ne yazildi, neresi durdu."""
        if s.hata:
            self._yaz(self.yap_cikti, f"hata: {s.hata}")
            self.durum.set("yazilamadi")
            return
        yorum, sonuclar = s.deger
        satirlar = [yorum.describe()]
        if not sonuclar:
            self._yaz(self.yap_cikti, "\n".join(satirlar))
            self.durum.set("komut uygulanmadi")
            return

        yazilan = 0
        for sonuc in sonuclar:
            satirlar += ["", sonuc.plan.describe()]
            if sonuc.diff is not None and not sonuc.diff.ok:
                satirlar.append(f"  KALKAN REDDETTI: {sonuc.diff.describe()}")
                satirlar += ["  " + r for r in sonuc.diff.details()]
            if sonuc.applied and sonuc.write is not None:
                yazilan += 1
                yedek = (f" (yedek: {sonuc.write.backup.name})"
                         if sonuc.write.backup else "")
                satirlar.append(f"  yazildi: {sonuc.write.path}{yedek}")
        if len(sonuclar) < len(yorum.eylemler):
            satirlar.append(f"  DURDURULDU: {len(yorum.eylemler) - len(sonuclar)} "
                            "eylem calistirilmadi")
        self._yaz(self.yap_cikti, "\n".join(satirlar))
        self.durum.set(f"{yazilan} eylem yazildi")

    # -- sekme: Devre (parca tablosu + devre grafi) ------------------------

    def _sekme_devre(self):
        from .elektrik import BASLIKLAR

        ttk = self.ttk
        sayfa = ttk.Frame(self.defter)
        self.defter.add(sayfa, text="Devre")

        ust = ttk.Frame(sayfa)
        ust.pack(fill="x", padx=8, pady=8)
        b = ttk.Button(ust, text="Parca tablosu", command=self._parcalar)
        b2 = ttk.Button(ust, text="CSV'ye yaz...", command=self._parcalar_csv)
        b3 = ttk.Button(ust, text="Devre grafi", command=self._devre_grafi)
        for d in (b, b2, b3):
            d.pack(side="left", padx=(0, 4))
        self.dugmeler += [b, b2, b3]
        ttk.Label(ust, text="  MPN ve fiyat SENTETIKTIR (test verisi). Bos hucre = turetilemedi. "
                            "Devre grafi: roller, sinirlar, eksik bilgi.",
                  foreground="#a33").pack(side="left")

        bolme = ttk.PanedWindow(sayfa, orient="vertical")
        bolme.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        cerceve = ttk.Frame(bolme)
        self.agac = ttk.Treeview(cerceve, columns=BASLIKLAR, show="headings", height=12)
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
        bolme.add(cerceve, weight=1)
        self.devre_cikti = self._kaydirmali_metin(bolme)
        bolme.add(self.devre_cikti.master, weight=1)

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
        from .elektrik import ag_metni

        secili = self.agac.selection()
        if not secili:
            return
        indis = self.agac.index(secili[0])
        if indis >= len(self.satirlar):
            return
        s = self.satirlar[indis]
        parcalar = [f"{s.ref}  {s.deger}  {s.lib_id}"]
        for pin, ag, volt in s.baglantilar:
            volt_metni = f"  = {volt:g} V" if volt is not None else ""
            parcalar.append(f"    pin {pin} -> {ag_metni(ag)}{volt_metni}")
        if s.gerilim_kaynak:
            parcalar.append(f"  gerilim: {s.gerilim_kaynak}")
        if s.akim_kaynak:
            parcalar.append(f"  akim: {s.akim_kaynak}")
        self._yaz(self.devre_cikti, "\n".join(parcalar))

    def _parcalar_csv(self):
        from tkinter import filedialog, messagebox

        from .elektrik import csv_yaz

        if not self.satirlar:
            messagebox.showinfo(BASLIK, "Once 'Parca tablosu' calistirin.")
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

    def _devre_grafi(self):
        """`pcbqa devre` ciktisinin aynisi (ayni fonksiyon, yakalanmis cikti)."""
        from .devre import __main__ as devre_ana

        proje = self.proje.get().strip()
        kosullar = self._kosullar_yolu()
        if not proje:
            self._yaz(self.devre_cikti, "once bir proje secin.")
            return

        def is_():
            argv = [proje] + (["--kosullar", str(kosullar)] if kosullar else [])
            kod, cikti = _yakala(devre_ana.main, argv)
            if kod:
                raise RuntimeError(cikti.strip() or f"devre grafi kurulamadi (kod {kod})")
            return cikti

        self._calistir("devre grafi", is_,
                       lambda s: self._basit_bitti(s, self.devre_cikti, "devre grafi"))

    # -- sekme: Kontrol (analiz + dogrulama tek kosuda) ---------------------

    KONTROL_RENK = {"GECTI": "#1a7f37", "KALDI": "#c62828", "UYARI": "#b26a00", "KISMEN": "#b26a00",
                    "DENETLENEMEDI": "#666", "ATLANDI": "#666"}

    def _sekme_kontrol(self):
        """Butun kontroller tek dugmede (Kicad-5d6.11). Mantik `kontrol.py`de;
        CLI `pcbqa kontrol` ile ayni rapor. ERC/DRC bir kez kosar."""
        tk, ttk = self.tk, self.ttk
        sayfa = ttk.Frame(self.defter)
        self.defter.add(sayfa, text="Kontrol")
        self.kontrol_secim = {
            "kalite": tk.BooleanVar(value=True), 1: tk.BooleanVar(value=True),
            2: tk.BooleanVar(value=True), 3: tk.BooleanVar(value=True)}
        self.kontrol_ayrinti = tk.BooleanVar(value=False)

        ust = ttk.Frame(sayfa)
        ust.pack(fill="x", padx=8, pady=8)
        self.b_kontrol = ttk.Button(ust, text="Kontrolleri calistir", command=self._kontrol)
        self.b_kontrol.pack(side="left", padx=(0, 8))
        for anahtar, metin in (("kalite", "Kalite skoru"), (1, "1 ERC/DRC/parite"),
                               (2, "2 Muhendislik"), (3, "3 Benzetim (ngspice)")):
            ttk.Checkbutton(ust, text=metin, variable=self.kontrol_secim[anahtar]).pack(side="left", padx=4)
        ttk.Checkbutton(ust, text="Ayrinti", variable=self.kontrol_ayrinti).pack(side="left", padx=(12, 4))
        b = ttk.Button(ust, text="Tam rapor", command=self._kontrol_tam_rapor)
        b.pack(side="left", padx=4)
        self.dugmeler += [self.b_kontrol, b]
        ttk.Label(sayfa, text="PCB dal akimi ve 9 kontrol her zaman kosar. ERC/DRC bir kez calisir; kalite "
                              "skoru seviye 1'in raporunu kullanir. Benzetim gereksinimleri ustteki kosullar "
                              "dosyasindan gelir. Bir satira tiklayin: bulgular asagida.",
                  foreground="#666", wraplength=1100, justify="left").pack(anchor="w", padx=8)

        bolme = ttk.PanedWindow(sayfa, orient="vertical")
        bolme.pack(fill="both", expand=True, padx=8, pady=8)
        cerceve = ttk.Frame(bolme)
        kolonlar = ("Kontrol", "Durum", "Hata", "Uyari", "Bilgi")
        self.kontrol_agac = ttk.Treeview(cerceve, columns=kolonlar, show="headings", height=12)
        for ad, gen in zip(kolonlar, (380, 140, 60, 60, 60)):
            self.kontrol_agac.heading(ad, text=ad)
            self.kontrol_agac.column(ad, width=gen, anchor="w")
        for durum, renk in self.KONTROL_RENK.items():
            self.kontrol_agac.tag_configure(durum, foreground=renk)
        kay = ttk.Scrollbar(cerceve, orient="vertical", command=self.kontrol_agac.yview)
        self.kontrol_agac.configure(yscrollcommand=kay.set)
        self.kontrol_agac.pack(side="left", fill="both", expand=True)
        kay.pack(side="right", fill="y")
        self.kontrol_agac.bind("<<TreeviewSelect>>", self._kontrol_secildi)
        bolme.add(cerceve, weight=1)
        self.kontrol_cikti = self._kaydirmali_metin(bolme)
        bolme.add(self.kontrol_cikti.master, weight=1)

    def _kontrol(self):
        from . import kontrol

        proje = self.proje.get().strip()
        kosullar = self._kosullar_yolu()
        seviyeler = {s for s in (1, 2, 3) if self.kontrol_secim[s].get()}
        kalite = self.kontrol_secim["kalite"].get()
        ayrinti = self.kontrol_ayrinti.get()
        if not proje:
            self._yaz(self.kontrol_cikti, "once bir proje secin.")
            return
        self._calistir("kontroller",
                       lambda: kontrol.calistir(Path(proje), kosullar, seviyeler, kalite=kalite, ayrinti=ayrinti),
                       self._kontrol_bitti)

    def _kontrol_bitti(self, s: Sonuc):
        self.kontrol_raporu = None
        self.kontrol_agac.delete(*self.kontrol_agac.get_children())
        if s.hata:
            self._yaz(self.kontrol_cikti, f"hata: {s.hata}\n\n{s.cikti}")
            self.durum.set("kontroller: hata")
            return
        r = s.deger
        self.kontrol_raporu = r
        for i, satir in enumerate(r.satirlar):
            etiket = satir.durum if satir.durum in self.KONTROL_RENK else ""
            self.kontrol_agac.insert("", "end", iid=str(i), tags=(etiket,),
                                     values=(satir.ad, satir.durum, satir.hata, satir.uyari, satir.bilgi))
        self._yaz(self.kontrol_cikti, r.metin)
        skor = f"skor {r.skor:g} | " if r.skor is not None else ""
        self.durum.set(f"kontroller bitti: {skor}toplam hata {r.hata_sayisi}"
                       + (" | ERC/DRC tek kosu" if r.erc_drc_tek_kosu else ""))

    def _kontrol_secildi(self, _event=None):
        secili = self.kontrol_agac.selection()
        if self.kontrol_raporu is None or not secili:
            return
        satir = self.kontrol_raporu.satirlar[int(secili[0])]
        self._yaz(self.kontrol_cikti, "\n".join([f"{satir.ad}: {satir.durum}", ""] + satir.ayrinti))

    def _kontrol_tam_rapor(self):
        if self.kontrol_raporu is not None:
            self._yaz(self.kontrol_cikti, self.kontrol_raporu.metin)

    # -- sekme: Duzelt -----------------------------------------------------

    def _sekme_duzelt(self):
        tk, ttk = self.tk, self.ttk
        sayfa = ttk.Frame(self.defter)
        self.defter.add(sayfa, text="Duzelt")
        self.duzelt_finding = tk.StringVar(value="")

        bulgu = ttk.LabelFrame(sayfa, text="Bulgu duzeltme - dosyaya yazar (yedek alinir, dogrulama "
                                           "basarisizsa geri alinir)")
        bulgu.pack(fill="x", padx=8, pady=(8, 4))
        ust = ttk.Frame(bulgu)
        ust.pack(fill="x", padx=6, pady=6)
        tara = ttk.Button(ust, text="Bulgulari tara", command=self._duzelt_liste)
        tara.pack(side="left")
        ttk.Label(ust, text="  Finding ID:").pack(side="left")
        giris = ttk.Entry(ust, textvariable=self.duzelt_finding, width=20)
        giris.pack(side="left", padx=6)
        giris.bind("<Return>", lambda _e: self._duzelt_uygula())
        self.b_duzelt_uygula = ttk.Button(ust, text="Uygula", command=self._duzelt_uygula)
        self.b_duzelt_uygula.pack(side="left")
        self.dugmeler += [tara, self.b_duzelt_uygula]

        elek = ttk.LabelFrame(sayfa, text="Elektriksel duzeltme onerisi - dosyaya YAZMAZ (rezistif bolucu "
                                          "ailesi; her aday ngspice + kural + PCB ile denenir)")
        elek.pack(fill="x", padx=8, pady=4)
        ust = ttk.Frame(elek)
        ust.pack(fill="x", padx=6, pady=6)
        self.b_devre_duzelt = ttk.Button(ust, text="Duzeltme oner", command=self._devre_duzelt)
        self.b_devre_duzelt.pack(side="left")
        self.dugmeler.append(self.b_devre_duzelt)
        ttk.Label(ust, text="  ustteki kosullar dosyasi gerekir (gereksinim penceresi). Gercek dosyada "
                            "denemek icin Deney sekmesi.", foreground="#666").pack(side="left")
        self.duzelt_cikti = self._metin_alani(sayfa)

    def _duzelt_liste(self):
        from . import duzelt

        proje = self.proje.get().strip()

        def is_():
            if not proje:
                raise RuntimeError("once bir proje secin")
            return _yakala(duzelt.main, [proje, "--liste"])

        self._calistir(
            "bulgu taramasi",
            is_,
            lambda s: self._duzelt_bitti(s, "bulgu taramasi"),
        )

    def _duzelt_uygula(self):
        """Secili bulgunun duzeltmesini dogrudan uygula.

        Onizleme adimi yoktur (kullanici talimati, 2026-09-27). `duzelt` plani
        ciktiya yazar ve ayni kosumda uygular; bakirli kart, acik KiCad ve
        bozulan netlist paritesi orada reddedilir.
        """
        from . import duzelt

        proje = self.proje.get().strip()
        finding = self.duzelt_finding.get().strip()
        if not proje or not finding:
            self._yaz(self.duzelt_cikti, "proje ve Finding ID gerekli.")
            return

        def is_():
            return _yakala(duzelt.main, [proje, "--finding", finding])

        self._calistir(
            "duzeltme uygulamasi",
            is_,
            lambda s: self._duzelt_bitti(s, "duzeltme uygulamasi"),
        )

    def _devre_duzelt(self):
        """`pcbqa devre-duzelt` - ayni fonksiyon; proje dosyalarina yazmaz."""
        from .duzeltme import sirala

        proje = self.proje.get().strip()
        kosullar = self._kosullar_yolu()
        if not proje or kosullar is None:
            self._yaz(self.duzelt_cikti, "proje ve kosullar dosyasi gerekli (ust satir).")
            return
        self._calistir("elektriksel duzeltme",
                       lambda: _yakala(sirala.main, [proje, "--kosullar", str(kosullar)]),
                       lambda s: self._duzelt_bitti(s, "elektriksel duzeltme"))

    def _duzelt_bitti(self, s: Sonuc, ad: str):
        if s.hata:
            self._yaz(self.duzelt_cikti, f"hata: {s.hata}\n\n{s.cikti}")
            self.durum.set(f"{ad}: hata")
            return
        deger = s.deger
        if isinstance(deger, tuple) and len(deger) == 2:
            _code, cikti = deger
        else:
            cikti = str(deger)
        self._yaz(self.duzelt_cikti, cikti)
        self.durum.set(f"{ad} bitti")

    # -- sekme: Deney ------------------------------------------------------

    DENEY_YOK = ("Deney kaynagi yuklenmedi - gercek proje degerlendirmesi GOSTERILMIYOR. Bir deney klasoru "
                 "(deney.jsonl) secin ya da asagidan yeni deney calistirin.")

    def _sekme_deney(self):
        """Gercek proje deneyi sonuclari (Kicad-d8k).

        Analiz kodu YOK: secim, gerekce ve envanter `duzeltme.gorunum` /
        `duzeltme.envanter` / `duzeltme.proje` fonksiyonlarindan gelir - CLI
        (`pcbqa duzeltme-proje goster`, `pcbqa duzeltme-envanter`) ile ayni."""
        from .duzeltme.aciklama import KAPSAM_NOTU

        tk, ttk = self.tk, self.ttk
        sayfa = ttk.Frame(self.defter)
        self.defter.add(sayfa, text="Deney")

        ust = ttk.Frame(sayfa)
        ust.pack(fill="x", padx=8, pady=(8, 2))
        ttk.Label(ust, text="Deney kaynagi:").pack(side="left")
        ttk.Entry(ust, textvariable=self.deney_kaynak).pack(side="left", fill="x", expand=True, padx=6)
        b1 = ttk.Button(ust, text="Klasor...", command=self._deney_klasor_sec)
        b2 = ttk.Button(ust, text="Yukle", command=self._deney_yukle)
        b3 = ttk.Button(ust, text="Envanter", command=self._deney_envanter)
        for b in (b1, b2, b3):
            b.pack(side="left", padx=(0, 4))

        alt = ttk.Frame(sayfa)
        alt.pack(fill="x", padx=8, pady=2)
        ttk.Label(alt, text="Yeni deney (temel = ustteki proje), cikti klasoru:").pack(side="left")
        ttk.Entry(alt, textvariable=self.deney_cikti).pack(side="left", fill="x", expand=True, padx=6)
        b4 = ttk.Button(alt, text="Tum adaylarla calistir", command=self._deney_calistir)
        b4.pack(side="left")
        self.dugmeler += [b1, b2, b3, b4]

        ttk.Label(sayfa, text=KAPSAM_NOTU + " Calistirma birkac dakika surer (aday basina ~6 s).",
                  foreground="#a33", wraplength=1100, justify="left").pack(anchor="w", padx=8, pady=(2, 2))
        self.deney_durum = ttk.Label(sayfa, text=self.DENEY_YOK, foreground="#444", wraplength=1100,
                                     justify="left")
        self.deney_durum.pack(anchor="w", padx=8, pady=(0, 4))

        bolme = ttk.PanedWindow(sayfa, orient="vertical")
        bolme.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        cerceve = ttk.Frame(bolme)
        kolonlar = ("Aday", "Degisiklik", "Maliyet", "Durum", "Tercih")
        self.deney_agac = ttk.Treeview(cerceve, columns=kolonlar, show="headings", height=9)
        for ad, gen in zip(kolonlar, (220, 520, 70, 90, 110)):
            self.deney_agac.heading(ad, text=ad)
            self.deney_agac.column(ad, width=gen, anchor="w")
        kay = ttk.Scrollbar(cerceve, orient="vertical", command=self.deney_agac.yview)
        self.deney_agac.configure(yscrollcommand=kay.set)
        self.deney_agac.pack(side="left", fill="both", expand=True)
        kay.pack(side="right", fill="y")
        self.deney_agac.bind("<<TreeviewSelect>>", self._deney_secildi)
        bolme.add(cerceve, weight=1)
        detay = ttk.Frame(bolme)
        self.deney_detay = tk.Text(detay, wrap="word", font=("Consolas", 10), state="disabled",
                                   background="#fbfbfb", height=14)
        dk = ttk.Scrollbar(detay, orient="vertical", command=self.deney_detay.yview)
        self.deney_detay.configure(yscrollcommand=dk.set)
        self.deney_detay.pack(side="left", fill="both", expand=True)
        dk.pack(side="right", fill="y")
        bolme.add(detay, weight=1)

    def _deney_klasor_sec(self):
        from tkinter import filedialog

        yol = filedialog.askdirectory(title="Deney klasoru (deney.jsonl)")
        if yol:
            self.deney_kaynak.set(yol)

    def _deney_temizle(self, mesaj: str):
        self.deney = None
        self.deney_agac.delete(*self.deney_agac.get_children())
        self.deney_durum.config(text=mesaj)

    def _deney_yukle(self):
        from .duzeltme.gorunum import deney_yukle

        kaynak = self.deney_kaynak.get().strip()
        if not kaynak:
            self._deney_temizle(self.DENEY_YOK)
            self._yaz(self.deney_detay, "once bir deney klasoru secin.")
            return
        self._calistir("deney yukleme", lambda: deney_yukle(Path(kaynak)), self._deney_yuklendi)

    def _deney_yuklendi(self, s: Sonuc):
        if s.hata:
            self._deney_temizle(f"{self.DENEY_YOK}\nKaynak okunamadi: {s.hata}")
            self._yaz(self.deney_detay, f"hata: {s.hata}")
            self.durum.set("deney yukleme: hata")
            return
        g = s.deger
        self.deney = g
        self.deney_agac.delete(*self.deney_agac.get_children())
        for i, r in enumerate(g.satirlar):
            self.deney_agac.insert("", "end", iid=str(i),
                                   values=(r["kimlik"], r["degisiklik"], r["maliyet"], r["durum"], r["tercih"]))
        sec = g.secim
        bas = f"Kaynak: {g.dosya} (gercek proje deneyi; {len(g.kayitlar)} kayit"
        bas += f", {len(g.bozuk)} okunamayan)" if g.bozuk else ")"
        self.deney_durum.config(text=bas + "\nSecilen: " + (sec["secilen"] or "YOK")
                                + (f" | esit maliyetli: {', '.join(sec['esit_maliyetliler'])}"
                                   if sec["esit_maliyetliler"] else ""))
        self._yaz(self.deney_detay, "\n".join(g.secim_satirlari))
        self.durum.set(f"deney yuklendi: {len(g.satirlar) - 1} aday")

    def _deney_secildi(self, _event=None):
        if self.deney is None:
            return
        secili = self.deney_agac.selection()
        if not secili:
            return
        r = self.deney.satirlar[int(secili[0])]
        satirlar = [f"{r['kimlik']}  ({r['durum']})", f"degisiklik: {r['degisiklik']}",
                    f"maliyet: {r['maliyet']}"]
        if r["tercih_nedeni"]:
            satirlar.append(f"tercih: {r['tercih_nedeni']}")
        satirlar.append("")
        satirlar += [f"[{a['kod']}] {a['metin']}" for a in r["aciklamalar"]] or ["(aciklama yok)"]
        satirlar += ["", "--- secim ---"] + self.deney.secim_satirlari
        self._yaz(self.deney_detay, "\n".join(satirlar))

    def _deney_envanter(self):
        from .duzeltme.envanter import envanter_metni

        kaynak = self.deney_kaynak.get().strip()
        if not kaynak:
            self._yaz(self.deney_detay, "once bir kaynak secin (deney klasoru ya da bellek veri klasoru).")
            return
        self._calistir("envanter", lambda: envanter_metni([Path(kaynak)])[0],
                       lambda s: self._basit_bitti(s, self.deney_detay, "envanter"))

    def _deney_calistir(self):
        """Ustteki projede tum adaylarla gercek deney. Desteklenmeyen proje
        (pcbqa-referans.json yok) hic baslatilmaz."""
        from .duzeltme import proje as P

        proje = self.proje.get().strip()
        cikti = self.deney_cikti.get().strip()
        try:
            temel = P.Proje.bul(Path(proje)) if proje else None
        except P.ProjeHatasi as exc:
            temel, neden = None, str(exc)
        else:
            neden = "once ustten bir temel proje secin" if temel is None else ""
        if temel is not None and not (temel.klasor / "pcbqa-referans.json").is_file():
            neden = (f"{temel.klasor} icinde pcbqa-referans.json yok: bu proje desteklenen kapsamda degil "
                     "(yalnizca rezistif bolucu ailesi, pcbqa duzeltme-proje referans ile uretilmis temel)")
            temel = None
        if temel is not None and not cikti:
            neden, temel = "cikti klasoru gerekli", None
        if temel is None:
            self._deney_temizle(f"{self.DENEY_YOK}\nDeney BASLATILMADI: {neden}")
            self._yaz(self.deney_detay, f"Deney baslatilmadi: {neden}")
            return

        def is_():
            from .duzeltme.gorunum import deney_yukle

            P.deney(temel.klasor, Path(cikti), hepsi=True)
            return deney_yukle(Path(cikti))

        self.deney_kaynak.set(cikti)
        self._calistir("gercek deney", is_, self._deney_yuklendi)

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
        self.uret_kontrol = self.tk.BooleanVar(value=True)
        ttk.Checkbutton(dugme, text="Ardindan kontrol et (seviye 1+2, 9 kontrol)",
                        variable=self.uret_kontrol).pack(side="left", padx=(12, 0))
        b3 = ttk.Button(dugme, text="Sablonlari listele", command=self._sablonlar)
        b3.pack(side="right")
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
        """Uret / kesfet; istenirse uretilen projede `kontrol` (Kicad-5d6.11).

        Kontrol kalite skorunu ATLAR - uretim kendi skorunu zaten yaziyor - ve
        seviye 3'u kosmaz: niyet dosyasi benzetim gereksinimi tasimiyor.
        """
        niyet, hedef, varyant = (self.niyet.get().strip(),
                                 self.hedef.get().strip(), self.varyant.get().strip())
        kontrol_et = self.uret_kontrol.get()

        def is_():
            if not niyet or not hedef:
                raise RuntimeError("niyet dosyasi ve cikti klasoru gerekli")
            argv = ["--intent", niyet, "--out", hedef]
            if kesfet:
                from . import explore as modul

                argv += ["--variants", varyant or "4"]
            else:
                from . import generate as modul
            kod, cikti = _yakala(modul.main, argv)
            if kontrol_et and kod != 2:
                from . import kontrol

                r = kontrol.calistir(Path(hedef), seviyeler={1, 2}, kalite=False)
                cikti += "\n\n" + "=" * 70 + "\nURETILEN PROJENIN KONTROLU\n" + r.metin
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
        ortam = ttk.LabelFrame(sayfa, text="Ortam ve KiCad baglantisi")
        ortam.pack(fill="x", padx=8, pady=(8, 4))
        row = ttk.Frame(ortam)
        row.pack(fill="x", padx=6, pady=4)
        for text, command in (
                ("Ortami denetle", self._tani),
                ("Baglantiyi kontrol et", self._canli_kontrol),
                ("API'yi etkinlestir", self._canli_etkinlestir),
                ("Bagimliliklari kur", self._canli_kur),
                ("PCB'yi KiCad'de ac", lambda: self._editor_ac("pcb")),
                ("Sematigi KiCad'de ac", lambda: self._editor_ac("sematik"))):
            b = ttk.Button(row, text=text, command=command)
            b.pack(side="left", padx=(0, 4))
            self.dugmeler.append(b)

        pcb = ttk.LabelFrame(sayfa, text="Canli PCB - her yazma tek Ctrl+Z ile geri alinir")
        pcb.pack(fill="x", padx=8, pady=4)
        row = ttk.Frame(pcb)
        row.pack(fill="x", padx=6, pady=4)
        b = ttk.Button(row, text="Yerlesimi onizle", command=self._canli_onizle)
        b.pack(side="left", padx=(0, 4))
        self.dugmeler.append(b)
        self.b_canli_uygula = ttk.Button(row, text="Yerlesimi uygula",
                                        command=self._canli_uygula, state="disabled")
        self.b_canli_uygula.pack(side="left", padx=(0, 12))
        read = ttk.Button(row, text="PCB'yi oku", command=self._pcb_oku)
        read.pack(side="left", padx=(0, 4))
        self.dugmeler.append(read)
        ttk.Entry(row, textvariable=self.pcb_komut).pack(side="left", fill="x", expand=True)
        self.b_pcb_uygula = ttk.Button(row, text="Canli PCB'ye yaz",
                                       command=self._pcb_uygula)
        self.b_pcb_uygula.pack(side="left", padx=4)
        self.dugmeler.append(self.b_pcb_uygula)
        ttk.Label(pcb, text="Ornek: R1 konumunu 50 30 yap; C2 5 -2.5 kaydir; U1 90 dondur; "
                  "U1 acisini 180 yap; J1 kilitle; J1 kilidini ac; R1 degerini 10k yap",
                  wraplength=1050).pack(anchor="w", padx=6, pady=4)
        sch = ttk.LabelFrame(sayfa, text="Canli sematik (KiCad nightly; degisiklik kopyada kalir, "
                                         "kaydetmek icin KiCad'de Ctrl+S)")
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
        self.b_sematik_uygula = ttk.Button(row, text="Canli sematige uygula",
                                          command=self._sematik_uygula)
        self.b_sematik_uygula.pack(side="left", padx=4)
        self.dugmeler.append(self.b_sematik_uygula)
        ttk.Label(sch, text="Ornek: R1 degerini 10k yap | 2 adet 100nF kondansator ekle ve hepsini VCC ile GND arasina bagla",
                  wraplength=1050).pack(anchor="w", padx=6, pady=4)
        self.canli_cikti = self._metin_alani(sayfa)

    def _pcb_oku(self):
        from .canli_pcb import read_live
        project = self.proje.get().strip()
        self._calistir("PCB okuma", lambda: read_live(project),
                       lambda s: self._basit_bitti(s, self.canli_cikti, "PCB okuma"))

    def _pcb_uygula(self):
        """Komutu cozumle ve acik PCB'ye AYNI kosumda yaz.

        Ayri onizleme adimi yoktur (kullanici talimati, 2026-09-27). Plan ve
        yazma ayni is parcaciginda zincirlendigi icin "ekranda gordugun plan"
        ile "yazilan plan" zaten ayni olur; imza karsilastirmasina gerek kalmaz.
        """
        from .canli_pcb import apply_edit, prepare_edit
        if self.mesgul:
            return
        signature = (self.proje.get().strip(), self.pcb_komut.get().strip())

        def is_():
            plan = prepare_edit(*signature)
            return f"{plan.description}\n\n{apply_edit(plan)}"

        self._calistir("canli PCB yazma", is_,
                       lambda s: self._basit_bitti(s, self.canli_cikti, "canli PCB yazma"))

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

    def _sematik_uygula(self):
        """Komutu cozumle ve acik sematige AYNI kosumda uygula.

        Ayri onizleme adimi yoktur (kullanici talimati, 2026-09-27); plan ile
        yazma zincirlendigi icin arada plan bayatlamasi olamaz.
        """
        from .canli_sematik import request
        if self.mesgul:
            return
        project, command = self.proje.get().strip(), self.sematik_komut.get().strip()

        def is_():
            plan = request("prepare", project, command=command)
            applied = request("apply", project, plan=plan)
            return f"{plan['description']}\n\n{applied['description']}"

        self._calistir("canli sematik", is_,
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

    # -- ortam (Canli sekmesinde) ve dagarcik (Yap sekmesinde) -------------

    def _tani(self):
        def is_():
            from .app import diagnose

            satirlar, engel = diagnose()
            return "\n".join(satirlar) + (
                f"\n\n{engel} engel var" if engel else "\n\nTemel ortam hazir; canli baglantiyi 'Baglantiyi kontrol et' ile sinayin.")

        self._calistir("tani", is_,
                       lambda s: self._basit_bitti(s, self.canli_cikti, "tani"))

    def _dagarcik(self):
        def is_():
            from . import komut

            _kod, cikti = _yakala(komut.main, ["--dagarcik"])
            return cikti

        self._calistir("dagarcik", is_,
                       lambda s: self._basit_bitti(s, self.yap_cikti, "dagarcik"))

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

    def _kaydirmali_metin(self, ana):
        """PanedWindow bolmesi icin metin alani; `.master` bolmeye eklenir."""
        tk, ttk = self.tk, self.ttk
        cerceve = ttk.Frame(ana)
        metin = tk.Text(cerceve, wrap="none", font=("Consolas", 10), state="disabled",
                        background="#fbfbfb", height=12)
        dikey = ttk.Scrollbar(cerceve, orient="vertical", command=metin.yview)
        yatay = ttk.Scrollbar(cerceve, orient="horizontal", command=metin.xview)
        metin.configure(yscrollcommand=dikey.set, xscrollcommand=yatay.set)
        yatay.pack(side="bottom", fill="x")
        dikey.pack(side="right", fill="y")
        metin.pack(side="left", fill="both", expand=True)
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
        self.b_duzelt_uygula.config(state="disabled")
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
                # Yazma dugmeleri artik surekli aciktir; silahlanma kapisi yok.
                # Yalnizca canli YERLESTIRME plani hala iki adimlidir.
                self.b_canli_uygula.config(state="normal" if self.canli_plan is not None
                    and self.canli_proje == self.proje.get().strip() else "disabled")
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
            "deney_kaynak": self.deney_kaynak.get(), "deney_cikti": self.deney_cikti.get(),
            "kosullar": self.kosullar.get(),
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
