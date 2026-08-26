"""CILA - hakemin gercek puanini dogrudan optimize eden yerel arama.

Asama 3'te ogrenilen sey: yerlestiriciler vekil bir maliyet (HPWL + genel
cezalar) optimize ediyordu, hakem ise YAML kurallarina bakiyordu. Sentetik
tezgahta ikisi ortusuyor, gercek kartta ortusmuyor - bu yuzden dort
yerlestiricinin ucu `pic_programmer`i BOZUYORDU.

Buradaki cila katmani araya girer: bir baslangic yerlesimi alir, hakemin
kendi olcutuyle (`ctx.evaluate`) kucuk yerel hamleler dener ve YALNIZCA
olcumu iyilestiren hamleyi kabul eder. Iki sonucu var:

  1. Cikti hicbir zaman baslangictan kotu olamaz (monoton garanti).
  2. Kural sinirlarina "kil payi" takilan hatalar kapanir - hamleler
     bulgulardan uretildigi icin dogrudan hataya nisan alir.

Ana giris: `polish(start, ctx, budget_s)`.
"""

from __future__ import annotations

import math
import random
import time
from typing import Any, Callable, Iterable

from .base import Compound, Evaluation, Move, Placement, PlacementContext
from .repertoire import Repertoire

# Bulgu kaynakli hamlelerde denenen yaricap kesirleri (limitin katlari)
_RADIUS_FRACTIONS = (0.35, 0.55, 0.75)
# Bir hedefin cevresinde denenen aci sayisi
_ANGLE_STEPS = 8
# Ince ayar hamlelerinde denenen kaydirmalar (mm)
_NUDGES = (0.5, 1.0, 2.0, 4.0)
Acceptance = Callable[["Evaluation", "Evaluation", float, random.Random], bool]

# Genis repertuar asamasinda bilesen basina kac aday gercek hakeme gider.
# Aday uretimi ucuz, DEGERLENDIRME pahali (2-6 ms); butceyi bu sayi belirler.
WIDE_KEEP = 12
# Genis repertuara ayrilan butce payi. 3. asama VARSAYILAN OLARAK KAPALI
# (`ctx.allow_wide_moves` veya `wide_keep` ile acilir); acildiginda toplam
# butcenin bu kadari 1. ve 2. asamadan kesilir.
#
# ## Neden varsayilan kapali - olculdu, tahmin degil
#
# 1. ve 2. asama bu payi vermeden 3. asamaya hic sira birakmiyor: durma sarti
# "bir tur gez, hicbir sey iyilesmesin", ama HPWL bir esitlik bozucu oldugu
# icin her zaman birkac mikron kazandiran bir kaydirma bulunuyor.
#
# Ilk cozum sabit pay kesmekti. 19 kartlik pakette sonuc BERABERE: 2 kart
# iyilesti (StickHub +1.2, video +3.3), 2 kart kotulesti (complex_hierarchy
# -2.8, interf_u -2.3).
#
# Ikinci cozum "durgunluk sayaci yalnizca SKOR artisinda sifirlansin" idi -
# yani asama, skor uretmeyi birakinca devretsin. DAHA KOTU cikti (2 iyi,
# 3 kotu; complex_hierarchy -5.5). Sebebi ogretici: sadece HPWL kisaltan
# hamleler BOSA GITMIYOR, plato asma mekanizmasi onlar. Bilesenleri yavas
# yavas yeniden konumlandiriyorlar ve skor kazanci ancak birkac adim sonra
# ulasilabilir hale geliyor. "Skoru artirmayan hamle zaman israfidir"
# sezgisi yanlisti.
#
# Uctuncu ve gecerli olan karar: 1. ve 2. asamadan zaman CALMA. Genis
# repertuar yalnizca acikca istendiginde calisir; boylece `auto` commit
# edilmis davranisini birebir korur ve gerileme riski sifirdir.
WIDE_SHARE = 0.2


def _refs_of(finding: Any) -> list[str]:
    return list(getattr(finding, "refs", None) or [])


def _limit_of(finding: Any, fallback: float) -> float:
    limit = getattr(finding, "limit", None)
    return float(limit) if isinstance(limit, (int, float)) and limit > 0 else fallback


def _inside(outline: tuple[float, float, float, float], x: float, y: float) -> bool:
    minx, miny, maxx, maxy = outline
    return minx <= x <= maxx and miny <= y <= maxy


def _with(placement: Placement, ref: str, xyr: tuple[float, float, float]) -> Placement:
    """Tek bileseni degistirilmis YENI bir yerlestirme sozlugu."""
    out = dict(placement)
    out[ref] = xyr
    return out


def _with_all(placement: Placement, compound: Compound) -> Placement:
    """BIRLESIK hamleyi uygulanmis YENI bir yerlestirme sozlugu.

    Butun atomlar ayni anda uygulanir; ara adim diye bir sey yoktur. Takasin
    calisabilmesinin sarti bu - A'yi once tasiyip sonra B'yi tasimak arada
    kesin bir cakisma uretir ve hakem o ara durumu reddeder.
    """
    out = dict(placement)
    for ref, xyr in compound:
        out[ref] = xyr
    return out


def _as_compounds(moves: Iterable[Move]) -> list[Compound]:
    """Tek bilesenli hamleleri 1 elemanli birlesige sarar."""
    return [(m,) for m in moves]


def _ring(cx: float, cy: float, radius: float) -> Iterable[tuple[float, float]]:
    for i in range(_ANGLE_STEPS):
        a = 2.0 * math.pi * i / _ANGLE_STEPS
        yield cx + radius * math.cos(a), cy + radius * math.sin(a)


def _extent_of(ref: str, ctx: PlacementContext) -> float:
    """Bilesenin kaba yaricapi (courtyard kutusunun yarisi).

    Baglam kendi `extent_of` yontemini sunuyorsa o kullanilir; boylece bu
    cila motoru PCB disindaki alanlarda da (or. sematik, Asama 4e) courtyard
    kavrami olmadan calisabilir.
    """
    own = getattr(ctx, "extent_of", None)
    if callable(own):
        return own(ref)

    comp = ctx.design.component(ref)
    poly = getattr(comp, "courtyard_local", None) if comp else None
    if not poly:
        return 1.0
    xs = [px for px, _ in poly]
    ys = [py for _, py in poly]
    return max(max(xs) - min(xs), max(ys) - min(ys)) / 2.0 or 1.0


def _centroid(refs: list[str], placement: Placement) -> tuple[float, float] | None:
    pts = [placement[r][:2] for r in refs if r in placement]
    if not pts:
        return None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def _finding_moves(
    finding: Any,
    placement: Placement,
    ctx: PlacementContext,
) -> list[tuple[str, tuple[float, float, float]]]:
    """Bir bulgudan somut hamleler uretir.

    Kural iki yonde de ihlal edilebilir, hamle yonu buna gore secilir:

      * olcum > limit  -> BIRBIRINE YAKLASTIR (decoupling mesafesi, net
        uzunlugu, yuk kondansatoru...)
      * olcum < limit  -> BIRBIRINDEN UZAKLASTIR (courtyard cakismasi,
        asgari aciklik...)

    Bu ayrimi kacirmak, cakisan iki bileseni ust uste bindirmeye calismak
    demektir - limit orada "en az bu kadar acik olsun" anlamina gelir.
    """
    refs = [r for r in _refs_of(finding) if r in placement]
    if len(refs) < 2:
        return []

    measured = getattr(finding, "measured", None)
    limit = getattr(finding, "limit", None)
    if not isinstance(limit, (int, float)) or limit <= 0:
        limit = 10.0
    push_apart = isinstance(measured, (int, float)) and measured < limit

    moves: list[tuple[str, tuple[float, float, float]]] = []
    outline = ctx.outline()

    for mover in refs:
        if mover in ctx.locked:
            continue
        others = [r for r in refs if r != mover]
        anchor = _centroid(others, placement)
        if anchor is None:
            continue
        ax, ay = anchor
        mx, my, rot = placement[mover]

        if push_apart:
            # Cakismayi acmak icin gereken en kucuk yaricap
            gap = _extent_of(mover, ctx) + max(_extent_of(r, ctx) for r in others) + limit
            radii = [gap * f for f in (1.0, 1.35, 1.8)]
        else:
            # Limitin guvenli ic tarafina yerlestir
            radii = [limit * f for f in _RADIUS_FRACTIONS]

        for radius in radii:
            for nx, ny in _ring(ax, ay, radius):
                if _inside(outline, nx, ny) and (abs(nx - mx) > 1e-9 or abs(ny - my) > 1e-9):
                    moves.append((mover, (nx, ny, rot)))
    return moves


def _nudge_moves(
    ref: str,
    placement: Placement,
    ctx: PlacementContext,
    rng: random.Random,
) -> list[tuple[str, tuple[float, float, float]]]:
    """Tek bilesen icin kucuk kaydirma ve 90 derece donme denemeleri.

    Adim boyutlari alana gore degisir. PCB'de serbest mm adimlari makuldur;
    SEMATIKTE ise konumlar 1.27 mm izgarasina oturmak ZORUNDADIR - izgara
    disi bir adim kural ihlali uretir ve her deneme reddedilir. Baglam kendi
    `nudge_steps` degerini sunuyorsa o kullanilir.
    """
    x, y, rot = placement[ref]
    outline = ctx.outline()
    steps = getattr(ctx, "nudge_steps", None) or _NUDGES
    moves = []
    for step in steps:
        for dx, dy in ((step, 0.0), (-step, 0.0), (0.0, step), (0.0, -step)):
            if _inside(outline, x + dx, y + dy):
                moves.append((ref, (x + dx, y + dy, rot)))
    if getattr(ctx, "allow_rotation", True):
        for turn in (90.0, 180.0, 270.0):
            moves.append((ref, (x, y, (rot + turn) % 360.0)))
    rng.shuffle(moves)
    return moves



class Metropolis:
    """TAVLAMA BENZERI KABUL - yerel en iyiden kacmak icin.

    `polish` bugun yalnizca iyilestiren hamleyi kabul ediyor (tepe tirmanisi),
    o yuzden hicbir TEK hamlenin iyilestiremedigi noktada duruyor. Ama o nokta
    kartin ulasilabilir en iyisi degil; yalnizca "tek hamlelik komsulugunda
    daha iyisi olmayan" bir nokta.

    Somut tuzak: C1'i U2.14'un yanina goturmek gerekiyor ama orada R5 duruyor.
    C1'i tasimak cakisma uretir (reddedilir); R5'i cekmek R5'in kendi kuralini
    bozar (reddedilir). Iki adimlik dizinin SONU iyi, ILK ADIMI kotu - tepe
    tirmanisi ilk adimi asla atmaz.

    Metropolis kurali kotulestiren hamleyi de exp(-|delta| / T) olasiligiyla
    kabul eder; T butce boyunca duser (basta cesur, sonda muhafazakar).

    ## Sicaklik neden kendini olcuyor

    Sabit bir T yazmak kartlar arasi anlamsiz olurdu: skor cezasi bilesen
    sayisina bolunuyor, yani tipik bir reddin buyuklugu karttan karta degisir.
    Bunun yerine ilk `warmup` reddin medyani T0 kabul edilir - o zaman
    baslangicta tipik bir kotulesme ~%37 olasilikla kabul edilir. Buyu sabiti
    yok, olcum var.

    ## Monotonluk garantisi neden bozulmuyor

    Bu sinif YALNIZCA `polish`in gezinen durumunu etkiler. `polish` gezinen
    durumu degil GORULEN EN IYIYI dondurur, ve baslangic da o kaydin ilk
    adayidir. Yani cikti hala baslangictan kotu olamaz - Asama 3'un garantisi
    oldugu gibi durur.
    """

    def __init__(
        self,
        cooling: float = 100.0,
        warmup: int = 25,
        heat: float = 0.15,
        leash: float | None = None,
    ) -> None:
        self.cooling = cooling
        self.warmup = warmup
        # T0 = medyan reddin `heat` kati. 1.0 (medyan) OLCULDU ve cok sicak
        # cikti: interf_u'da kotu hamlelerin %38'i kabul edildi, arama
        # tirmanmak yerine gezindi ve skor 25.7 -> 6.1'e coktu.
        self.heat = heat
        # "Tasma": mevcut durum en iyiden bu kadar geri kalirsa arama en
        # iyiye geri atlar. Klasik tavlamada bu yok cunku orada milyonlarca
        # adim var; burada butce ~birkac bin degerlendirme, o yuzden basibos
        # gezinmenin geri donusu yok.
        self.leash = leash
        self.t0: float | None = None
        self._losses: list[float] = []
        self.taken_worse = 0
        self.seen_worse = 0
        self.restarts = 0

    def __call__(
        self,
        candidate: Evaluation,
        current: Evaluation,
        progress: float,
        rng: random.Random,
    ) -> bool:
        gain = candidate.gain_over(current)
        if gain > 0.0:
            return True
        loss = -gain
        if loss <= 1e-12:
            return False  # tam esit: gezinmenin anlami yok, degerlendirme israfi
        self.seen_worse += 1
        if self.t0 is None:
            self._losses.append(loss)
            if len(self._losses) < self.warmup:
                return False
            ordered = sorted(self._losses)
            self.t0 = max(ordered[len(ordered) // 2] * self.heat, 1e-6)
        temperature = self.t0 * (1.0 / self.cooling) ** max(0.0, min(1.0, progress))
        if temperature <= 1e-12:
            return False
        if rng.random() < math.exp(-loss / temperature):
            self.taken_worse += 1
            return True
        return False


def polish(
    start: Placement,
    ctx: PlacementContext,
    budget_s: float | None = None,
    *,
    verbose: bool = False,
    wide_keep: int | None = None,
    accept: "Acceptance | None" = None,
) -> Placement:
    """Baslangic yerlesimini hakem olcutuyle iyilestirir.

    Hicbir zaman baslangictan kotu bir sonuc dondurmez. `ctx.evaluate`
    yoksa (eski cagri yolu) girdiyi oldugu gibi geri verir.

    `accept`: KACIS asamasinin kabul yuklemi. None ise (varsayilan) o asama
    hic calismaz ve davranis bugunkuyle birebir aynidir. `Metropolis()`
    verilirse, tepe tirmanisi tukenip butce ARTARSA arama kotulesen hamleleri
    de sinirli olasilikla kabul edip gezinir. Dondurulen sonuc her durumda
    GORULEN EN IYIDIR, yani monotonluk garantisi bozulmaz.

    `wide_keep`: genis repertuar asamasinda (3) bilesen basina kac aday
    gercek hakeme gonderilir. 0 verilirse o asama hic calismaz - sematik
    tarafi (Asama 4e) takas/kume kavramlarina sahip olmadigi icin kendi
    baglaminda 0 gecer. Varsayilan `WIDE_KEEP`.
    """
    if ctx.evaluator is None:
        return dict(start)

    deadline = time.perf_counter() + (budget_s if budget_s is not None else ctx.time_budget_s)
    full_deadline = deadline  # asamalar arasinda `deadline` daraltilip geri acilir
    rng = random.Random(ctx.seed)
    if wide_keep is None:
        wide_keep = WIDE_KEEP if getattr(ctx, "allow_wide_moves", False) else 0
    if wide_keep > 0:
        # 3. asamaya bir TABAN pay ayrilir. Asil devretme mekanizmasi bu degil
        # (o, asagidaki "yalnizca skor artisi sayilir" kurali); bu yalnizca
        # 1. ve 2. asamanin skor uretmeye devam ettigi kartlarda genis
        # repertuarin hic denenmeden kalmamasini garanti eder.
        #
        # Ilk surumde tek mekanizma sabit pay kesmekti ve 19 kartlik pakette
        # sonuc BERABEREYDI: 2 kart iyilesti (StickHub +1.2, video +3.3),
        # 2 kart kotulesti (complex_hierarchy -2.8, interf_u -2.3). Sebep
        # acikti - hala ilerleyen kartlardan zaman calmak.
        deadline = time.perf_counter() + (full_deadline - time.perf_counter()) * (
            1.0 - WIDE_SHARE
        )

    # Asama 5 kancasi: baglam bir siralayici sunuyorsa adaylar once ona
    # gosterilir. Siralayici YALNIZCA denenme sirasini degistirir - kabul
    # karari asagida yine `ctx.evaluate` ile verilir, yani monotonluk
    # garantisi siralayici tamamen yanilsa bile bozulmaz.
    #
    # Siralayici SADECE (2) ince ayar asamasinda devreye girer. Olculdu:
    # (1) onarim asamasinda hamleler zaten anlamli bir sirada gelir - yaricap
    # artan, yani "en kucuk yer degistirme once". Bu muhafazakar sira komsu
    # kisitlari bozmadigi icin degerlidir; modelin "tek basina en cok
    # iyilestiren" hamlesi ise buyuk siçramalar secip baska bulgulari
    # aciyordu (`complex_hierarchy` 94 -> 84...89, dort model varyantinda da).
    # (2) ince ayar asamasinin sirasi ise BUGUN RASTGELE (`rng.shuffle`),
    # yani orada kaybedilecek bir bilgi yok.
    ranker = getattr(ctx, "move_ranker", None)

    # GEZINEN durum ile KAYIT ayri tutulur. Tepe tirmanisinda ikisi hep
    # ayni; tavlamada `current` kotulesebilir, `best` asla. `polish` her
    # zaman `best`i dondurur - monotonluk garantisi buradan geliyor.
    current = dict(start)
    current_eval = ctx.evaluate(current)
    if current_eval is None:
        return current
    best, best_eval = dict(current), current_eval

    started_at = time.perf_counter()
    # Kabul yuklemi asamaya gore degisir: 1-3 her zaman TEPE TIRMANISI,
    # yalnizca 4. asama gezinir (bkz. asagisi).
    active_accept: "Acceptance | None" = None

    def progress() -> float:
        span = full_deadline - started_at
        return (time.perf_counter() - started_at) / span if span > 1e-9 else 1.0

    def try_moves(moves, rank: bool = False, keep: int | None = None) -> bool:
        """Ilk iyilestiren BIRLESIK hamleyi kabul eder (first-improvement).

        `rank` YALNIZCA ince ayar ve genis repertuar asamalarinda acilir -
        sebebi asagida (2).

        `keep` verilirse aday listesi o sayiya indirilir. Bu, genis
        repertuarin (takas O(n^2) aday uretir) degerlendirme butcesini
        sinirlamak icin sart. ADALET NOKTASI: siralayici varsa en iyi `keep`
        tanesi, yoksa RASTGELE `keep` tanesi denenir - yani `auto` ile
        `learned` ayni sayida gercek degerlendirme yapar ve aradaki fark
        yalnizca SECIMDEN gelir.
        """
        nonlocal current, current_eval, best, best_eval
        moves = list(moves)
        if not moves:
            return False
        if rank and ranker is not None:
            try:
                moves = list(ranker(current, current_eval, moves))
            except Exception:
                pass  # siralayici patlarsa arama kendi sirasiyla devam eder
        if keep is not None and len(moves) > keep:
            # Siralayici zaten en iyileri basa aldiysa bastan kes; almadiysa
            # rastgele orneklem al (bir uctan kesmek konum onyargisi yaratir).
            moves = moves[:keep] if (rank and ranker is not None) else rng.sample(moves, keep)
        for compound in moves:
            if time.perf_counter() > deadline:
                return False
            cand = _with_all(current, compound)
            ev = ctx.evaluate(cand)
            if ev is None:
                continue
            taken = (
                ev.better_than(current_eval)
                if active_accept is None
                else active_accept(ev, current_eval, progress(), rng)
            )
            if not taken:
                continue
            current, current_eval = cand, ev
            # Kayit yalnizca GERCEKTEN daha iyi oldugunda guncellenir.
            if ev.better_than(best_eval):
                best, best_eval = cand, ev
            else:
                # TASMA: gezinme en iyiden cok uzaklastiysa geri cek. Klasik
                # tavlamada boyle bir sey yok - orada milyonlarca adim var ve
                # arama geri donebilir. Burada butce birkac bin degerlendirme,
                # yani basibos gezinmenin geri donusu YOK: olculdu, interf_u
                # 25.7 -> 6.1'e coktu.
                leash = getattr(active_accept, "leash", None)
                if leash is not None and best_eval.gain_over(current_eval) > leash:
                    current, current_eval = dict(best), best_eval
                    active_accept.restarts = getattr(active_accept, "restarts", 0) + 1
            return True
        return False

    # 1) Bulgu gudumlu onarim: hakemin saydigi hatalara dogrudan nisan al.
    #
    # Her tur, o anki bulgu listesinin tamamini SIRAYLA gezer. Ilk iyilesmede
    # bastan baslamak, kucuk kazanclar veren tek bir bulgunun butun butceyi
    # yemesine yol aciyordu - bu yuzden iyilesme olsa da sonraki bulguya
    # gecilir; liste ancak tur sonunda tazelenir.
    improved = True
    while improved and time.perf_counter() < deadline:
        improved = False
        findings = list(current_eval.findings)
        errors = [f for f in findings if getattr(f, "severity", "") == "error"]
        warnings = [f for f in findings if getattr(f, "severity", "") == "warning"]
        for finding in errors + warnings:
            if time.perf_counter() > deadline:
                break
            if try_moves(_as_compounds(_finding_moves(finding, current, ctx))):
                improved = True
                if verbose:
                    print(f"    onarim: {getattr(finding, 'rule_id', '?')} -> {current_eval.score:.1f} (en iyi {best_eval.score:.1f})")

    # 2) Genel ince ayar: kalan butceyi bilesenleri tek tek kaydirmaya harca.
    movable = [r for r in ctx.movable() if r in current]
    rng.shuffle(movable)
    idx = 0
    stagnant = 0
    while time.perf_counter() < deadline and movable and stagnant < len(movable):
        ref = movable[idx % len(movable)]
        idx += 1
        if try_moves(_as_compounds(_nudge_moves(ref, current, ctx, rng)), rank=True):
            stagnant = 0
            if verbose:
                print(f"    ince ayar: {ref} -> {current_eval.score:.1f} (en iyi {best_eval.score:.1f})")
        else:
            stagnant += 1

    # 3) GENIS REPERTUAR (Asama 6): takas, kume tasima, bolge sicramasi.
    #
    # (1) ve (2) tukendiginde arama tek-bilesen hamleleriyle ulasilabilen bir
    # yerel en iyide durur. Regresyon paketinde 19 kartin 8'inde `auto`nun hic
    # iyilestirme bulamamasinin sebebi buydu: iyilestiren hamle repertuarda
    # YOKTU. Bu asama tavani yukseltmeyi hedefler.
    #
    # Aday sayisi burada patlar (takas O(n^2)); `keep` ile degerlendirme
    # butcesi sabitlenir ve secimi ya model ya da zar yapar.
    deadline = full_deadline
    if wide_keep > 0:
        repertoire = Repertoire(ctx, rng)
        rng.shuffle(movable)
        idx = 0
        stagnant = 0
        while time.perf_counter() < deadline and movable and stagnant < len(movable):
            ref = movable[idx % len(movable)]
            idx += 1
            hit = False
            # Partiler ZENGINDEN FAKIRE sirali (bkz. `wide_batches`); her biri
            # kendi `keep` butcesiyle denenir, boylece fakir bir uretici zengin
            # olani sulandiramaz.
            for label, moves in repertoire.wide_batches(ref, current):
                if try_moves(moves, rank=True, keep=wide_keep):
                    hit = True
                    if verbose:
                        print(f"    genis/{label}: {ref} -> {current_eval.score:.1f} (en iyi {best_eval.score:.1f})")
                    break
            if hit:
                stagnant = 0
            else:
                stagnant += 1

    # 4) KACIS (istege bagli): tepe tirmanisi tukendiyse ve butce kaldiysa,
    # kabul kuralini gevseterek yerel en iyiden cikmayi dene.
    #
    # ## Neden yalnizca ARTAN butceyle
    #
    # Ilk deneme kabul kuralini bastan gevsetmekti: 6 kartta 2 iyi, 2 kotu ve
    # bir felaket (interf_u 25.7 -> 6.1). Sebep butce: klasik tavlama 10^5-10^6
    # adim ister, burada bir degerlendirme 2-6 ms, yani 20 saniyede ancak
    # birkac bin adim var. Gezinmek icin harcanan her degerlendirme,
    # tirmanmaktan calinmis oluyor - ve tirmanis hala urettigi surece bu
    # kotu bir takas.
    #
    # Sogutulmus baslangic (heat=0.15) + tasma felaketi onledi ama tabloyu
    # cevirmedi: kit-dev +2.2, digerlerinde es veya geri.
    #
    # Desen her iki olcumde de ayni: tavlama, tirmanisin GERCEKTEN TIKANDIGI
    # kartlarda kazandiriyor, hala verimli oldugu kartlarda kaybettiriyor.
    # Bu, Faz A'da ogrenilen kuralin aynisi - uretken asamadan zaman calma.
    # Bu yuzden kacis asamasi yalnizca ARTAN butceyi kullanir; tirmanis
    # butun butceyi yediyse hic calismaz ve davranis bugunkuyle birebir ayni
    # kalir.
    if accept is not None and time.perf_counter() < full_deadline:
        active_accept = accept
        deadline = full_deadline
        movable = [r for r in ctx.movable() if r in current]
        rng.shuffle(movable)
        idx = 0
        while time.perf_counter() < deadline and movable:
            ref = movable[idx % len(movable)]
            idx += 1
            if try_moves(_as_compounds(_nudge_moves(ref, current, ctx, rng))) and verbose:
                print(
                    f"    kacis: {ref} -> {current_eval.score:.1f} "
                    f"(en iyi {best_eval.score:.1f})"
                )

    return best


# --------------------------------------------------------------- disa acilan
#
# Asama 5 (ML) veri toplayicisi ve ogrenilmis yerlestirici, aramanin GERCEKTEN
# gordugu aday dagilimiyla calismak zorunda. Baska bir yerde ikinci bir hamle
# ureteci yazmak yerine ayni fonksiyonlar disa aciliyor - tek kaynak.

finding_moves = _finding_moves
nudge_moves = _nudge_moves
with_move = _with
with_moves = _with_all
as_compounds = _as_compounds


def keep_best(
    candidates: dict[str, Placement],
    ctx: PlacementContext,
) -> tuple[str, Placement, Evaluation | None]:
    """Adaylar arasindan hakem olcutune gore en iyisini secer.

    `candidates` icine kartin mevcut halini de koyun ki sonuc asla
    baslangictan kotu olmasin.
    """
    best_name, best_pl, best_ev = "", {}, None
    for name, pl in candidates.items():
        ev = ctx.evaluate(pl)
        if ev is None:
            if not best_name:
                best_name, best_pl = name, pl
            continue
        if ev.better_than(best_ev):
            best_name, best_pl, best_ev = name, pl, ev
    return best_name, best_pl, best_ev
