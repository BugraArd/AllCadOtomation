"""Sematik yerlestirme kalitesi (Asama 4e).

Asama 3'te PCB icin kurulan mimari buraya oldugu gibi tasinir: yerlestirici
vekil bir maliyet uydurmaz, HAKEMIN GERCEK OLCUTUNU optimize eder ve sonuc
hicbir zaman baslangictan kotu olamaz. `refine.polish` degistirilmeden
kullanilir; degisen tek sey degerlendiricidir.

## Neden ayri bir degerlendirici?

Kalkan (`sch_verify`) her cagrida `kicad-cli` calistirir - 2-4 saniye. Yerel
arama binlerce aday dener; kalkani her adayda kosturmak imkansiz. Bu yuzden:

  * ARAMA sirasinda hizli, bellek-ici, GEOMETRIK bir olcut kullanilir
    (~mikrosaniyeler): cakisma, izgara, sayfa siniri, toplam tel uzunlugu ve
    baglanti riski.
  * YAZMA oncesi bir kez gercek netlist kalkani kosturulur (`sch_apply`).

Geometrik olcut baglanti riskini de tasir: bir sembol tasinirken pini
KENDISINE ait olmayan bir capaya (baska bir telin ucu, baska bir sembolun
pini) otururca iki net birlesir. Bu, kalkanin yakaladigi hatanin ucuz vekili
oldugu icin arama zaten oraya gitmez; kalkan son soz olarak kalir.

## Yerlestirme sozlesmesi

    SchPlacement = {sembol_uuid: (x_mm, y_mm)}

Yalnizca OTELEME. Rotasyon ve ayna desteklenmiyor (bkz. sch_move): pin
konumlari donunce tel uclari tek bir delta ile tasinamaz.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from .placement.base import Evaluation, PlacementContext
from .placement.refine import polish
from .report import MIN_COMPONENTS_FOR_SCORE, PENALTY
from .rules import Finding, run_schematic_checks
from .schematic import GRID_MM, SchSymbol, Schematic, read_schematic

# sembol UUID'si -> (x, y). Referans DEGIL: cok birimli bilesenlerin
# birimleri ayni referansi paylasir. Rotasyon yok; bkz. modul basligi.
SchPlacement = dict[str, tuple[float, float]]

# Konum esitligi toleransi (mm)
EPS = 1e-4

# Yaygin kagit boyutlari (mm, yatay). Sayfa siniri kontrolu icin.
PAPER_SIZES = {
    "A0": (1189.0, 841.0),
    "A1": (841.0, 594.0),
    "A2": (594.0, 420.0),
    "A3": (420.0, 297.0),
    "A4": (297.0, 210.0),
    "A5": (210.0, 148.0),
    "A": (279.4, 215.9),
    "B": (431.8, 279.4),
    "C": (558.8, 431.8),
    "D": (863.6, 558.8),
    "E": (1117.6, 863.6),
    "USLetter": (279.4, 215.9),
    "USLegal": (355.6, 215.9),
    "USLedger": (431.8, 279.4),
}

# Sayfa kenarinda birakilacak pay (mm) - cerceve ve yazi kutusu icin
PAGE_MARGIN = 10.0


def _same(a: float, b: float) -> bool:
    return abs(a - b) < EPS


def _key(sheet: str, x: float, y: float) -> tuple[str, float, float]:
    return (sheet, round(x, 3), round(y, 3))


@dataclass
class _SymbolInfo:
    """Bir sembol ORNEGININ tasimaya hazir on-hesaplanmis hali.

    Anahtar UUID'dir, referans DEGIL: cok birimli bir bilesenin (or. 74LS125
    dort kapili) her birimi ayri bir `symbol` dugumudur ve hepsi ayni
    referansi tasir. Referansla anahtarlamak dordunu tek girdiye cokertip
    "U2 ve U2 cakisiyor" gibi hayali bulgular uretiyordu.
    """

    uuid: str
    ref: str
    label: str
    unit: int
    sheet: str
    base: tuple[float, float]
    pin_offsets: list[tuple[float, float]]
    bbox_offset: tuple[float, float, float, float] | None
    virtual: bool


@dataclass
class _WireInfo:
    sheet: str
    a: tuple[float, float]
    b: tuple[float, float]
    # Uclarin tutundugu sembol (varsa) - tasinirken birlikte gider
    a_owner: str | None
    b_owner: str | None


@dataclass
class SchEvaluation:
    """Bir yerlestirmenin geometrik olcumu (rapor icin)."""

    score: float
    errors: int
    warnings: int
    total_wire_mm: float
    findings: list[Finding] = field(default_factory=list)


class SchematicArena:
    """Sematik uzerinde hizli yerlestirme degerlendirmesi.

    `refine.polish`in bekledigi arayuzu saglar: `evaluate`, `current`,
    `movable`, `locked`, `outline`, `extent_of`, `seed`, `time_budget_s`.
    """

    def __init__(
        self,
        schematic: Schematic,
        sheet_path: str = "/",
        *,
        locked: set[str] | None = None,
        seed: int = 0,
        time_budget_s: float = 30.0,
        allow_buses: bool = False,
    ) -> None:
        self.schematic = schematic
        self.sheet_path = sheet_path
        self.seed = seed
        self.time_budget_s = time_budget_s

        self._symbols: dict[str, _SymbolInfo] = {}
        multi = {}
        for sym in schematic.symbols:
            if sym.sheet_path == sheet_path and sym.ref:
                multi[sym.ref] = multi.get(sym.ref, 0) + 1
        for index, sym in enumerate(schematic.symbols):
            if sym.sheet_path != sheet_path or not sym.ref:
                continue
            key = sym.uuid or f"{sym.ref}#{index}"
            self._symbols[key] = _SymbolInfo(
                uuid=key,
                ref=sym.ref,
                label=f"{sym.ref}.{sym.unit}" if multi.get(sym.ref, 1) > 1 else sym.ref,
                unit=sym.unit,
                sheet=sym.sheet_path,
                base=(sym.x, sym.y),
                pin_offsets=[(round(p.x - sym.x, 4), round(p.y - sym.y, 4)) for p in sym.pins],
                bbox_offset=(
                    (
                        round(sym.bbox[0] - sym.x, 4),
                        round(sym.bbox[1] - sym.y, 4),
                        round(sym.bbox[2] - sym.x, 4),
                        round(sym.bbox[3] - sym.y, 4),
                    )
                    if sym.bbox
                    else None
                ),
                virtual=sym.is_virtual,
            )

        # Pin konumu -> o konumdaki sembol referanslari
        pin_owner: dict[tuple[str, float, float], set[str]] = {}
        for info in self._symbols.values():
            for ox, oy in info.pin_offsets:
                pin_owner.setdefault(
                    _key(info.sheet, info.base[0] + ox, info.base[1] + oy), set()
                ).add(info.uuid)

        # Dogrudan pin-pine temas eden ciftler: birlikte tasinmalari sart
        self._welded: dict[str, set[str]] = {}
        for keys in pin_owner.values():
            if len(keys) > 1:
                for key in keys:
                    self._welded.setdefault(key, set()).update(keys - {key})

        self._wires: list[_WireInfo] = []
        for wire in schematic.wires:
            if wire.sheet_path != sheet_path:
                continue
            owners = []
            for px, py in wire.endpoints:
                candidates = pin_owner.get(_key(wire.sheet_path, px, py), set())
                owners.append(next(iter(sorted(candidates))) if len(candidates) == 1 else None)
            self._wires.append(
                _WireInfo(
                    sheet=wire.sheet_path,
                    a=(wire.x1, wire.y1),
                    b=(wire.x2, wire.y2),
                    a_owner=owners[0],
                    b_owner=owners[1],
                )
            )

        # Tasinmayan capalar: junction, no_connect, etiket
        self._static_anchors: set[tuple[str, float, float]] = set()
        for point in schematic.junctions + schematic.no_connects:
            if point.sheet_path == sheet_path:
                self._static_anchors.add(_key(sheet_path, point.x, point.y))
        for label in schematic.labels:
            if label.sheet_path == sheet_path:
                self._static_anchors.add(_key(sheet_path, label.x, label.y))

        # SURUKLENEMEYEN capalar: bus'lar ve bus girisleri. Sembol tasinirken
        # pinine degen tel uclari birlikte gider, ama bus girisi YERINDE KALIR.
        # Bir sembol pini dogrudan bus girisinde duruyorsa o sembolu tasimak
        # baglantiyi koparir ve suruklenecek bir tel de yoktur.
        #
        # Olculdu: vme-wren/vme_p1_p2 sayfasinda bu kural yokken optimizasyon
        # "skor 100, 0 hata, tel %60 kisaldi" diyordu; gercek netlist kalkani
        # 257 pinin ag degistirdigini gosterip yazmayi reddetti.
        self._undraggable: set[tuple[str, float, float]] = set()
        for entry in schematic.bus_entries:
            if entry.sheet_path == sheet_path:
                self._undraggable.add(_key(sheet_path, entry.x, entry.y))
        for bus in schematic.buses:
            if bus.sheet_path == sheet_path:
                for bx, by in bus.endpoints:
                    self._undraggable.add(_key(sheet_path, bx, by))
        self._static_anchors |= self._undraggable

        # BUS ICEREN SAYFALAR VARSAYILAN OLARAK KAPALI.
        #
        # Ucuz geometrik olcut bus baglantilarini modelleyemiyor. Olculdu:
        # vme-wren/vme_p1_p2 sayfasinda (137 bus, 262 bus girisi) optimizasyon
        # "skor 100, 0 hata, tel %60 kisaldi" diyordu; gercek netlist kalkani
        # 257 pinin ag degistirdigini gosterdi ve yazma reddedildi. Sistem
        # guvenliydi ama olcut YANILTICIYDI.
        #
        # Mekanizma tam cozulmedi; cozulene kadar dogru davranis, olcutun
        # gecerli olmadigi sayfada hic tasima onermemektir. `allow_buses=True`
        # ile acilabilir - kalkan yine son soz olarak calisir.
        self.has_buses = any(
            b.sheet_path == sheet_path for b in schematic.buses
        ) or any(e.sheet_path == sheet_path for e in schematic.bus_entries)

        # Cagiran REFERANS verir; iceride UUID ile calisilir
        locked_refs = set(locked or ())
        if self.has_buses and not allow_buses:
            # Olcut bu sayfada gecerli degil: hicbir sey tasinmaz
            self.locked = set(self._symbols)
        else:
            self.locked = {
                info.uuid
                for info in self._symbols.values()
                # Sanal semboller (guc/bayrak) kendi basina tasinmaz: pinleri
                # baska sembollere kaynakli oldugu icin bagimsiz hareket
                # baglantiyi koparir
                if info.virtual or info.ref in locked_refs
            }

        page = PAPER_SIZES.get(schematic.paper, PAPER_SIZES["A4"])
        self._bounds = (PAGE_MARGIN, PAGE_MARGIN, page[0] - PAGE_MARGIN, page[1] - PAGE_MARGIN)

        # refine.polish'e alana ozgu adimlar: sematikte konumlar 1.27 mm
        # izgarasina oturmak zorunda, PCB'nin serbest mm adimlari burada her
        # denemeyi izgara disi birakip reddettiriyordu.
        self.nudge_steps = tuple(GRID_MM * n for n in (1, 2, 4, 8))
        # Rotasyon desteklenmiyor (bkz. modul basligi); denemek bosa harcanan
        # degerlendirme demek.
        self.allow_rotation = False

        self.evaluator = self.evaluate

    # -- refine.polish arayuzu -------------------------------------------

    def current(self) -> SchPlacement:
        return {info.uuid: info.base for info in self._symbols.values()}

    def movable(self) -> list[str]:
        return [ref for ref in self._symbols if ref not in self.locked]

    def outline(self) -> tuple[float, float, float, float]:
        return self._bounds

    def extent_of(self, key: str) -> float:
        info = self._symbols.get(key)
        if info is None or info.bbox_offset is None:
            return GRID_MM
        minx, miny, maxx, maxy = info.bbox_offset
        return max(maxx - minx, maxy - miny) / 2.0 or GRID_MM

    # -- olcum ------------------------------------------------------------

    def positions(self, placement) -> dict[str, tuple[float, float]]:
        """Yerlestirmeyi taban konumlarla birlestirir (eksikler yerinde kalir).

        Konumlar BURADA yuvarlanir. Arama sirasinda kullanilan koordinatlarla
        sonunda dosyaya yazilan koordinatlar ayni olmak zorunda; aksi halde
        aramanin kabul ettigi bir yerlesim yuvarlandiktan sonra baska bir
        olcum verir ve monotonluk garantisi kagit uzerinde kalir. Olculdu:
        4e-14 mm'lik yuvarlama farki bir sayfada skoru 100'den 97.4'e
        dusuruyordu.
        """
        out = {info.uuid: info.base for info in self._symbols.values()}
        for key, value in (placement or {}).items():
            if key in out and value is not None:
                out[key] = (round(float(value[0]), 4), round(float(value[1]), 4))
        return out

    def wire_length(self, positions) -> float:
        total = 0.0
        for wire in self._wires:
            ax, ay = wire.a
            bx, by = wire.b
            if wire.a_owner and wire.a_owner in positions:
                base = self._symbols[wire.a_owner].base
                new = positions[wire.a_owner]
                ax += new[0] - base[0]
                ay += new[1] - base[1]
            if wire.b_owner and wire.b_owner in positions:
                base = self._symbols[wire.b_owner].base
                new = positions[wire.b_owner]
                bx += new[0] - base[0]
                by += new[1] - base[1]
            total += math.hypot(bx - ax, by - ay)
        return total

    def _geometry_findings(self, positions) -> list[Finding]:
        """Kural motorunun gormedigi, tasimaya ozgu riskler."""
        findings: list[Finding] = []

        moved = {
            key
            for key, pos in positions.items()
            if not (
                _same(pos[0], self._symbols[key].base[0])
                and _same(pos[1], self._symbols[key].base[1])
            )
        }
        if not moved:
            return findings

        # 1) Kaynakli komsusu olmadan tasinan sembol -> baglanti kopar
        for key in moved:
            own = self._symbols[key]
            for mate_key in self._welded.get(key, set()):
                mate = self._symbols[mate_key]
                mate_pos = positions.get(mate_key)
                same_delta = (
                    mate_pos is not None
                    and _same(mate_pos[0] - mate.base[0], positions[key][0] - own.base[0])
                    and _same(mate_pos[1] - mate.base[1], positions[key][1] - own.base[1])
                )
                if not same_delta:
                    findings.append(
                        Finding(
                            rule_id="sematik-kaynakli-pin-kopuyor",
                            severity="error",
                            message=(
                                f"{own.label} tasinirsa {mate.label} ile dogrudan temasi "
                                "kopar (arada tel yok)"
                            ),
                            source="pcbqa-sch",
                            refs=[own.ref, mate.ref],
                        )
                    )

        # 1b) Pini suruklenemeyen bir capada (bus girisi) duran sembol tasinamaz
        for key in moved:
            info = self._symbols[key]
            bx, by = info.base
            for ox, oy in info.pin_offsets:
                if _key(info.sheet, bx + ox, by + oy) in self._undraggable:
                    findings.append(
                        Finding(
                            rule_id="sematik-bus-girisi-kopuyor",
                            severity="error",
                            message=(
                                f"{info.label} pini bir bus girisinde duruyor "
                                f"({bx + ox:g}, {by + oy:g}); bus girisi suruklenemez, "
                                "tasima baglantiyi koparir"
                            ),
                            source="pcbqa-sch",
                            refs=[info.ref],
                        )
                    )

        # 2) Tasinan bir pin, kendisine ait olmayan bir capaya oturuyor -> net birlesir
        occupied: dict[tuple[str, float, float], set[str]] = {}
        for key, (x, y) in positions.items():
            info = self._symbols[key]
            for ox, oy in info.pin_offsets:
                occupied.setdefault(_key(info.sheet, x + ox, y + oy), set()).add(key)

        for key in moved:
            info = self._symbols[key]
            x, y = positions[key]
            for ox, oy in info.pin_offsets:
                point = _key(info.sheet, x + ox, y + oy)
                foreign = occupied.get(point, set()) - {key} - self._welded.get(key, set())
                if foreign:
                    names = sorted(self._symbols[f].label for f in foreign)
                    findings.append(
                        Finding(
                            rule_id="sematik-pin-carpismasi",
                            severity="error",
                            message=(
                                f"{info.label} pini {', '.join(names)} pini uzerine oturuyor "
                                f"({point[1]:g}, {point[2]:g}); netler birlesir"
                            ),
                            source="pcbqa-sch",
                            refs=[info.ref, *sorted({self._symbols[f].ref for f in foreign})],
                        )
                    )
                elif point in self._static_anchors:
                    findings.append(
                        Finding(
                            rule_id="sematik-capaya-oturdu",
                            severity="error",
                            message=(
                                f"{info.label} pini serbest bir capaya (junction/etiket) "
                                f"oturuyor ({point[1]:g}, {point[2]:g}); netler birlesir"
                            ),
                            source="pcbqa-sch",
                            refs=[info.ref],
                        )
                    )

        # 3) Sayfa disina tasma
        minx, miny, maxx, maxy = self._bounds
        for key in moved:
            info = self._symbols[key]
            x, y = positions[key]
            if info.bbox_offset:
                bx1, by1, bx2, by2 = info.bbox_offset
                box = (x + bx1, y + by1, x + bx2, y + by2)
            else:
                box = (x, y, x, y)
            if box[0] < minx or box[1] < miny or box[2] > maxx or box[3] > maxy:
                findings.append(
                    Finding(
                        rule_id="sematik-sayfa-disi",
                        severity="warning",
                        message=f"{info.label} sayfa sinirinin disina tasiyor",
                        source="pcbqa-sch",
                        refs=[info.ref],
                    )
                )
        return findings

    def _moved_schematic(self, positions) -> Schematic:
        """Kural motorunun anlayacagi hafif bir Schematic goruntusu uretir.

        Yalnizca `run_schematic_checks`in okudugu alanlar doldurulur.
        """
        symbols: list[SchSymbol] = []
        for sym in self.schematic.symbols:
            if sym.sheet_path != self.sheet_path:
                symbols.append(sym)
                continue
            x, y = positions.get(sym.uuid, (sym.x, sym.y))
            dx, dy = x - sym.x, y - sym.y
            clone = SchSymbol(
                ref=sym.ref,
                lib_id=sym.lib_id,
                x=x,
                y=y,
                rotation=sym.rotation,
                mirror=sym.mirror,
                unit=sym.unit,
                uuid=sym.uuid,
                value=sym.value,
                footprint=sym.footprint,
                dnp=sym.dnp,
                sheet_path=sym.sheet_path,
                properties=sym.properties,
                bbox=(
                    (sym.bbox[0] + dx, sym.bbox[1] + dy, sym.bbox[2] + dx, sym.bbox[3] + dy)
                    if sym.bbox
                    else None
                ),
            )
            symbols.append(clone)
        return Schematic(
            root_path=self.schematic.root_path,
            paper=self.schematic.paper,
            symbols=symbols,
            sheets=self.schematic.sheets,
            files=self.schematic.files,
            file_of_sheet=self.schematic.file_of_sheet,
        )

    def evaluate(self, placement) -> Evaluation:
        """Bir yerlestirmeyi puanlar. Hizli: kicad-cli calistirmaz."""
        positions = self.positions(placement)
        findings = run_schematic_checks(self._moved_schematic(positions))
        findings += self._geometry_findings(positions)

        penalty = sum(PENALTY.get(f.severity, 0.0) for f in findings)
        size = max(len(self._symbols), MIN_COMPONENTS_FOR_SCORE)
        score = 100.0 if penalty <= 0 else round(100.0 * math.exp(-penalty / size), 1)

        return Evaluation(
            score=score,
            errors=sum(1 for f in findings if f.severity == "error"),
            warnings=sum(1 for f in findings if f.severity == "warning"),
            total_hpwl_mm=round(self.wire_length(positions), 1),
            findings=findings,
        )


def _context_for(arena: SchematicArena) -> PlacementContext:
    """`refine.polish` icin arena'yi baglam gibi gosterir.

    polish yalnizca su uyeleri kullanir: evaluator, evaluate, current,
    movable, locked, outline, extent_of, seed, time_budget_s - hepsini arena
    sagliyor. `design` alani yalnizca eski PCB yolunda okunur.
    """
    return arena  # type: ignore[return-value]


def improve(
    schematic: Schematic,
    sheet_path: str = "/",
    *,
    budget_s: float = 20.0,
    seed: int = 0,
    locked: set[str] | None = None,
    allow_buses: bool = False,
    verbose: bool = False,
) -> tuple[SchPlacement, Evaluation, Evaluation]:
    """Bir sayfanin yerlesimini iyilestirir.

    `(placement, onceki_olcum, sonraki_olcum)` dondurur. Sonuc hicbir zaman
    baslangictan kotu degildir - garanti `refine.polish`ten gelir.
    """
    arena = SchematicArena(
        schematic,
        sheet_path,
        locked=locked,
        seed=seed,
        time_budget_s=budget_s,
        allow_buses=allow_buses,
    )
    start = arena.current()
    before = arena.evaluate(start)

    # polish (x, y, rot) ucluleriyle calisir; sematikte rotasyon sabit
    seeded = {ref: (pos[0], pos[1], 0.0) for ref, pos in start.items()}
    polished = polish(seeded, _context_for(arena), budget_s=budget_s, verbose=verbose)

    placement: SchPlacement = {
        ref: (round(value[0], 4), round(value[1], 4)) for ref, value in polished.items()
    }
    return placement, before, arena.evaluate(placement)


def changed_only(schematic: Schematic, placement: SchPlacement, sheet_path: str = "/") -> SchPlacement:
    """Yalnizca gercekten yeri degisen sembol orneklerini birakir.

    Anahtar UUID'dir: cok birimli bir bilesenin birimleri ayni referansi
    paylasir, o yuzden referansla anahtarlamak birimleri birbirine karistirir.
    """
    out: SchPlacement = {}
    for sym in schematic.symbols:
        if sym.sheet_path != sheet_path or sym.uuid not in placement:
            continue
        x, y = placement[sym.uuid]
        if not (_same(x, sym.x) and _same(y, sym.y)):
            out[sym.uuid] = (x, y)
    return out


def improve_file(
    sch_path: Path | str,
    sheet_path: str = "/",
    **kwargs,
) -> tuple[Schematic, SchPlacement, Evaluation, Evaluation]:
    """`read_schematic` + `improve` kisayolu."""
    schematic = read_schematic(sch_path)
    placement, before, after = improve(schematic, sheet_path, **kwargs)
    return schematic, changed_only(schematic, placement, sheet_path), before, after
