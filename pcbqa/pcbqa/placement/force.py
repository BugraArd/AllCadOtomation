"""Kuvvet tabanli (force-directed) yerlestirme.

Fikir: netler yay, bilesenler dugum. Her net kendi pinlerini birbirine ceker,
kaplama alanlari (courtyard) cakisan bilesenler birbirini iter. Sistem dengeye
yaklastirilir, sonra cakismalar cozulup izgaraya oturtulur.

Klasik EDA akisi uc fazdir ve bu modul de o sirayi izler:

  1. GLOBAL YERLESIM  (`_global_place`)
     Surekli uzayda kaba konum. Her hareketli bilesen icin "denge noktasi"
     analitik olarak cozulur: bagli oldugu her netin merkezine, o netin yay
     sabitiyle agirliklandirilmis ortalama. Buna ek olarak kural kaynakli
     "es yaylar" (decoupling kondansatoru <-> IC guc pini, yuk kondansatoru
     <-> kristal) cok yuksek sabitle eklenir - asil kazanc oradadir. Her
     adimda ayrica bir yayilma (repulsion) itmesi ve kart siniri baskisi
     uygulanir.

  2. LEGALIZASYON  (`_legalize`)
     Global fazin biraktigi cakismalar en az nufuz eden eksen boyunca ayrilir,
     bilesenler kart icine cekilir, konumlar 0.05 mm izgarasina oturtulur.

  3. INCE AYAR  (`_anneal`)
     Kucuk tasi / buyuk sicrama / 90 derece dondur / iki bileseni takasla
     hareketleriyle tavlama (simulated annealing), ardindan acgozlu inis.
     Maliyet fonksiyonu yerlesim kurallarini dogrudan modeller (asagi bak).

Maliyet fonksiyonu, yerlesimle duzeltilebilen klasik PCB kurallarinin
surekli bir gevsetmesidir:

    Cost = 0.03 * toplam HPWL
         + 8 * (ihlal edilen hata kurali sayisi)  + gradyan terimi
         + 2 * (ihlal edilen uyari kurali sayisi) + gradyan terimi

Kurallar tasarimdan turetilir (pin tipi / bilesen turu / deger), tek bir karta
gomulu degildir: IC guc pinlerinin kendi decoupling kondansatoru, regulator
giris/cikis kondansatorleri, kristal net uzunlugu ve yuk kondansatorleri,
diferansiyel cift dengesi, guc rayi ve sinyal uzunluk butceleri, courtyard
bosluğu ve kart kenari mesafesi.

Rastgelelik yalnizca `ctx.seed`den beslenir; ayni tohum ayni sonucu verir.
"""

from __future__ import annotations

import math
import random
import time

from .base import Placement, PlacementContext

# --------------------------------------------------------------------- ayarlar

_ROTS = (0.0, 90.0, 180.0, 270.0)
_GRID = 0.05                 # KiCad'de rahat okunan konum izgarasi (mm)

# Uretilebilirlik
_CLEARANCE = 0.2             # courtyard'lar arasi zorunlu bosluk (mm)
_CLEARANCE_AIM = 0.45        # optimize ederken hedeflenen bosluk (izgara payi)
_EDGE_MIN = 2.0              # kart kenarindan zorunlu mesafe (mm)
_EDGE_AIM = 2.25

# Kural esikleri (klasik EDA varsayilanlari)
_DECOUPLE_MM = 6.0           # IC guc pini <-> kendi decoupling kondansatoru
_REGCAP_MM = 8.0             # regulator <-> giris/cikis kondansatoru
_XTAL_CAP_MM = 6.0           # kristal <-> yuk kondansatoru
_XTAL_NET_MM = 12.0          # XIN / XOUT net uzunlugu
_RAIL_MM = 60.0              # guc rayi HPWL butcesi
_SIGNAL_MM = 45.0            # sinyal net HPWL butcesi
_DIFF_TOL_MM = 3.0           # diferansiyel cift uzunluk farki

# Maliyet agirliklari (report.py'deki ceza tablosuyla ayni oran: hata 8, uyari 2)
_W_ERR = 8.0
_W_WARN = 2.0
_W_HPWL = 0.03

_GROUND_NAMES = {"GND", "AGND", "DGND", "VSS", "VSSA", "GNDA", "NC", "N/C"}
_POWER_TYPES = {"power_in", "power_out"}

# Is miktari. Saatten degil `ctx.time_budget_s`den turetilir ki ayni tohum +
# ayni butce her calistirmada ayni sonucu versin (hakem bunu boyle karsilastiriyor).
_RESTARTS = 8                 # farkli baslangictan kuvvet cozumu
_ANNEAL_PER_SECOND = 6500     # saniye butcesi basina toplam tavlama adimi
_DESCENT_PASSES = 8           # her yeniden baslatmadan sonra acgozlu inis turu
_FINAL_PASSES = 30            # kazanan aday uzerinde uzun inis


def _rotate(dx: float, dy: float, degrees: float) -> tuple[float, float]:
    """KiCad donme konvansiyonu (Y ekseni asagi) - pcb.py ile ayni."""
    if not degrees:
        return dx, dy
    th = math.radians(degrees)
    cos, sin = math.cos(th), math.sin(th)
    return dx * cos + dy * sin, dy * cos - dx * sin


def _snap(v: float) -> float:
    return round(v / _GRID) * _GRID


# ------------------------------------------------------------------ veri yapisi


class _Item:
    """Yerlestiricinin ic bilesen temsili: donme basina onceden hesaplanmis
    pad ofsetleri ve courtyard sinir kutusu."""

    __slots__ = ("idx", "ref", "kind", "value", "movable", "nets", "types", "off", "box")

    def __init__(self, idx, ref, kind, value, movable, nets, types, off, box):
        self.idx = idx
        self.ref = ref
        self.kind = kind
        self.value = value
        self.movable = movable
        self.nets = nets      # pad basina net adi
        self.types = types    # pad basina pintype
        self.off = off        # 4 donme x pad -> (dx, dy)
        self.box = box        # 4 donme -> (dx1, dy1, dx2, dy2) courtyard ofseti


class _Group:
    """Bir yakinlik (proximity) kuralinin tek bir netteki hali."""

    __slots__ = ("targets", "partners")

    def __init__(self, targets, partners):
        self.targets = targets      # [(item, pad, key)]
        self.partners = partners    # [(item, pad, ref)]


def _is_ground(net: str) -> bool:
    return net.upper() in _GROUND_NAMES


def _diff_partner(name: str) -> str | None:
    """`USB_DP` <-> `USB_DM` gibi diferansiyel cift esini dondurur."""
    for a, b in (("DP", "DM"), ("_P", "_M"), ("+", "-")):
        if a in name:
            return name.replace(a, b, 1)
    return None


# ------------------------------------------------------------------- model


class _Model:
    """Tasarimin yerlestirme icin sadelestirilmis, hizli degerlendirilebilir hali."""

    def __init__(self, ctx: PlacementContext) -> None:
        design = ctx.design
        self.minx, self.miny, self.maxx, self.maxy = ctx.outline()

        self.items: list[_Item] = []
        for idx, comp in enumerate(design.board.components):
            nets = tuple(p.net for p in comp.pads)
            types = tuple(p.pintype for p in comp.pads)
            off, box = [], []
            for rot in _ROTS:
                off.append(tuple(_rotate(p.dx, p.dy, rot) for p in comp.pads))
                poly = [_rotate(lx, ly, rot) for lx, ly in comp.courtyard_local]
                if not poly:
                    poly = [_rotate(p.dx, p.dy, rot) for p in comp.pads] or [(0.0, 0.0)]
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                box.append((min(xs), min(ys), max(xs), max(ys)))
            self.items.append(
                _Item(
                    idx,
                    comp.ref,
                    design.kind_of(comp.ref),
                    design.value_of(comp.ref),
                    comp.ref not in ctx.locked,
                    nets,
                    types,
                    tuple(off),
                    tuple(box),
                )
            )

        self.start = [
            (c.x, c.y, _ROTS.index(c.rotation % 360.0) if (c.rotation % 360.0) in _ROTS else 0)
            for c in design.board.components
        ]
        self.movable = [it.idx for it in self.items if it.movable]

        # net adi -> [(item, pad)]  (netlist.py ile ayni sira: ada gore sirali)
        members: dict[str, list[tuple[int, int]]] = {}
        for it in self.items:
            for p, net in enumerate(it.nets):
                if net:
                    members.setdefault(net, []).append((it.idx, p))
        self.nets = [(n, tuple(members[n])) for n in sorted(members)]
        self.net_index = {n: i for i, (n, _) in enumerate(self.nets)}

        self._build_rules()
        self._build_weights()

    # -------------------------------------------------------------- kural kurulum

    def _build_rules(self) -> None:
        items = self.items

        # Regulator: power_out pad'i olan IC.
        regs = {
            it.ref
            for it in items
            if it.kind == "ic" and any(t == "power_out" for t in it.types)
        }

        self.decouple: list[_Group] = []   # IC guc pini <- kendi kondansatoru
        self.regcap: list[_Group] = []     # regulator <- uF kondansatoru
        self.xtalcap: list[_Group] = []    # kristal <- pF yuk kondansatoru

        xtal_nets: set[str] = set()
        rail_nets: set[str] = set()

        for net, mem in self.nets:
            if _is_ground(net):
                continue
            caps = [(i, p, items[i].ref) for i, p in mem if items[i].kind == "capacitor"]

            pwr = [
                (i, p, f"{items[i].ref}.{p}")
                for i, p in mem
                if items[i].kind == "ic" and items[i].types[p] == "power_in"
            ]
            if pwr and caps:
                self.decouple.append(_Group(pwr, caps))

            reg_pins = [(i, p, f"{items[i].ref}.{p}") for i, p in mem if items[i].ref in regs]
            bulk = [c for c in caps if "uf" in items[c[0]].value.lower()]
            if reg_pins and bulk:
                self.regcap.append(_Group(reg_pins, bulk))

            xt = [(i, p, f"{items[i].ref}.{p}") for i, p in mem if items[i].kind == "crystal"]
            if xt:
                xtal_nets.add(net)
                load = [c for c in caps if "pf" in items[c[0]].value.lower()]
                if load:
                    self.xtalcap.append(_Group(xt, load))

            if any(items[i].types[p] in _POWER_TYPES for i, p in mem):
                rail_nets.add(net)

        # Net uzunluk butceleri: (net adi, limit, hata mi)
        self.len_rules: list[tuple[str, float, bool]] = []
        for net, mem in self.nets:
            if _is_ground(net) or len(mem) < 2:
                continue
            if net in xtal_nets:
                self.len_rules.append((net, _XTAL_NET_MM, True))
            elif net in rail_nets:
                self.len_rules.append((net, _RAIL_MM, False))
            else:
                self.len_rules.append((net, _SIGNAL_MM, False))

        # Diferansiyel ciftler: ada gore eslesen netler
        seen: set[str] = set()
        self.diff_pairs: list[tuple[str, str]] = []
        for net, _ in self.nets:
            if net in seen or _is_ground(net):
                continue
            mate = _diff_partner(net)
            if mate and mate != net and mate in self.net_index:
                self.diff_pairs.append((net, mate))
                seen.add(net)
                seen.add(mate)

    def _build_weights(self) -> None:
        """Yay sabitleri: kritik netler daha sert ceker."""
        xtal = {n for n, _, err in self.len_rules if err}
        diff = {n for pair in self.diff_pairs for n in pair}
        crit_caps = {g for grp in (self.decouple, self.xtalcap, self.regcap) for g in grp}
        cap_nets: set[str] = set()
        for net, mem in self.nets:
            for g in crit_caps:
                if any((i, p) in mem for i, p, _ in g.partners):
                    cap_nets.add(net)

        self.netw: dict[str, float] = {}
        for net, mem in self.nets:
            if len(mem) < 2:
                continue
            if _is_ground(net):
                w = 0.06                      # her seyi baglar; sert olursa kart cokerdi
            elif net in xtal:
                w = 6.0
            elif net in diff:
                w = 2.0
            elif net in cap_nets:
                w = 0.9                       # guc rayi: es yaylar zaten isi goruyor
            else:
                w = 1.6
            self.netw[net] = w

    # ------------------------------------------------------------- degerlendirme

    def pads(self, state) -> list[tuple[tuple[float, float], ...]]:
        out = []
        for it, (x, y, r) in zip(self.items, state):
            out.append(tuple((x + dx, y + dy) for dx, dy in it.off[r]))
        return out

    def boxes(self, state) -> list[tuple[float, float, float, float]]:
        out = []
        for it, (x, y, r) in zip(self.items, state):
            a, b, c, d = it.box[r]
            out.append((x + a, y + b, x + c, y + d))
        return out

    def net_boxes(self, pads) -> list[tuple[float, float, float, float] | None]:
        out = []
        for _, mem in self.nets:
            if len(mem) < 2:
                out.append(None)
                continue
            xs = [pads[i][p][0] for i, p in mem]
            ys = [pads[i][p][1] for i, p in mem]
            out.append((min(xs), min(ys), max(xs), max(ys)))
        return out

    def match(self, group_list: list[_Group], pads, exclusive: bool):
        """rules.py'deki `proximity` eslemesinin birebir aynisi: tum (hedef,
        partner) ciftleri mesafeye gore siralanir, en yakindan baslanarak
        acgozlu eslesme yapilir. `exclusive` acikken bir partner en fazla bir
        hedefe sayilir."""
        claimed: set[str] = set()
        result: list[tuple[str, float | None, int, int, int, int]] = []
        for grp in group_list:
            pairs = []
            for ti, tp, key in grp.targets:
                tx, ty = pads[ti][tp]
                for pi, pp, pref in grp.partners:
                    if pref == self.items[ti].ref:
                        continue
                    px, py = pads[pi][pp]
                    pairs.append((math.hypot(tx - px, ty - py), key, pref, ti, tp, pi, pp))
            pairs.sort(key=lambda t: t[0])
            matched: dict[str, tuple] = {}
            used: set[str] = set()
            for rec in pairs:
                if rec[1] in matched:
                    continue
                if exclusive and (rec[2] in claimed or rec[2] in used):
                    continue
                matched[rec[1]] = rec
                used.add(rec[2])
            claimed |= used
            for ti, tp, key in grp.targets:
                hit = matched.get(key)
                if hit is None:
                    result.append((key, None, ti, tp, -1, -1))
                else:
                    result.append((key, hit[0], hit[3], hit[4], hit[5], hit[6]))
        return result

    def cost(self, state) -> float:
        pads = self.pads(state)
        nb = self.net_boxes(pads)
        total = 0.0

        # --- tel uzunlugu (rapordaki toplam HPWL ile ayni tanim)
        hpwl = [0.0 if b is None else (b[2] - b[0]) + (b[3] - b[1]) for b in nb]
        total += _W_HPWL * math.fsum(hpwl)

        # --- net uzunluk butceleri
        for net, limit, is_err in self.len_rules:
            length = hpwl[self.net_index[net]]
            if length > limit:
                total += (_W_ERR if is_err else _W_WARN) + 0.6 * (length - limit)
            else:
                total += 0.04 * max(0.0, length - 0.85 * limit)

        # --- yakinlik kurallari
        total += self._prox_cost(self.decouple, pads, _DECOUPLE_MM, True)
        total += self._prox_cost(self.xtalcap, pads, _XTAL_CAP_MM, True)
        total += self._prox_cost(self.regcap, pads, _REGCAP_MM, False)

        # --- diferansiyel cift dengesi
        for a, b in self.diff_pairs:
            spread = abs(hpwl[self.net_index[a]] - hpwl[self.net_index[b]])
            if spread > _DIFF_TOL_MM:
                total += _W_ERR + 1.5 * (spread - _DIFF_TOL_MM)
            else:
                total += 0.15 * spread

        # --- uretilebilirlik
        total += self._geom_cost(state)
        return total

    def _prox_cost(self, groups, pads, limit: float, exclusive: bool) -> float:
        total = 0.0
        for _key, dist, *_ in self.match(groups, pads, exclusive):
            if dist is None:
                total += _W_ERR * 2.0      # partner tukendi - yerlesimle cozulemez
            elif dist > limit:
                total += _W_ERR + 1.4 * (dist - limit)
            else:
                total += 0.12 * max(0.0, dist - 0.6 * limit)
        return total

    def _geom_cost(self, state) -> float:
        boxes = self.boxes(state)
        total = 0.0
        n = len(boxes)
        for i in range(n):
            ax1, ay1, ax2, ay2 = boxes[i]
            for j in range(i + 1, n):
                if not (self.items[i].movable or self.items[j].movable):
                    continue
                bx1, by1, bx2, by2 = boxes[j]
                gap = max(max(bx1 - ax2, ax1 - bx2), max(by1 - ay2, ay1 - by2))
                if gap < _CLEARANCE:
                    total += _W_ERR + 3.0 * (_CLEARANCE_AIM - gap)
                elif gap < _CLEARANCE_AIM:
                    total += 1.5 * (_CLEARANCE_AIM - gap)

        for idx in self.movable:
            x1, y1, x2, y2 = boxes[idx]
            margin = min(x1 - self.minx, y1 - self.miny, self.maxx - x2, self.maxy - y2)
            if margin < _EDGE_MIN:
                total += _W_ERR + 3.0 * (_EDGE_AIM - margin)
            elif margin < _EDGE_AIM:
                total += 1.5 * (_EDGE_AIM - margin)
        return total

    def total_hpwl(self, state) -> float:
        nb = self.net_boxes(self.pads(state))
        return math.fsum(0.0 if b is None else (b[2] - b[0]) + (b[3] - b[1]) for b in nb)


# ------------------------------------------------------------------ yerlestirici


class ForcePlacer:
    """Kuvvet tabanli global yerlesim + legalizasyon + tavlamali ince ayar."""

    name = "force"

    def run(self, ctx: PlacementContext) -> Placement:
        model = _Model(ctx)
        if not model.movable:
            return {}

        # Is miktari SURE degil BUTCE degerinden turetilir: ayni tohum + ayni
        # butce her makinede ayni sonucu verir. Saat yalnizca acil fren.
        restarts = _RESTARTS
        anneal_iters = max(
            400, int(_ANNEAL_PER_SECOND * ctx.time_budget_s / restarts)
        )
        deadline = time.perf_counter() + max(1.0, ctx.time_budget_s * 0.95)
        rng = random.Random(ctx.seed)

        best = [tuple(s) for s in model.start]
        best_cost = model.cost(best)

        for attempt in range(restarts):
            state = self._seed_state(model, rng, attempt)
            self._global_place(model, state, iters=180)
            self._legalize(model, state, iters=140)
            self._snap_state(model, state)

            state, cost = self._anneal(model, state, rng, anneal_iters, deadline)
            state, cost = self._descend(model, state, cost, _DESCENT_PASSES, deadline)

            if cost < best_cost - 1e-9:
                best, best_cost = state, cost

            if time.perf_counter() >= deadline:
                break

        # Kazanan aday uzerinde uzun acgozlu inis (detayli iyilestirme)
        best, best_cost = self._descend(model, best, best_cost, _FINAL_PASSES, deadline)

        # Son guvenlik: legalizasyon + izgara, yalnizca iyilestiriyorsa kabul et
        polished = [tuple(s) for s in best]
        self._legalize(model, polished, iters=200)
        self._snap_state(model, polished)
        if model.cost(polished) <= best_cost:
            best = polished

        return {
            model.items[i].ref: (round(best[i][0], 4), round(best[i][1], 4), _ROTS[best[i][2]])
            for i in model.movable
        }

    # ---------------------------------------------------------------- baslangic

    def _seed_state(self, model: _Model, rng: random.Random, attempt: int) -> list:
        """Ilk deneme mevcut yerlesimden, sonrakiler dagitilmis baslangictan.

        Farkli baslangiclar kuvvet sisteminin farkli yerel dengelerine dusmesini
        saglar; en iyisi maliyete gore secilir.
        """
        state = [tuple(s) for s in model.start]
        if attempt == 0:
            return state
        cx = (model.minx + model.maxx) / 2.0
        cy = (model.miny + model.maxy) / 2.0
        span = 0.25 * min(model.maxx - model.minx, model.maxy - model.miny)
        for idx in model.movable:
            _, _, r = state[idx]
            state[idx] = (
                cx + rng.uniform(-span, span),
                cy + rng.uniform(-span, span),
                r if attempt < 4 else rng.randrange(4),
            )
        return state

    # ------------------------------------------------------- 1. global yerlesim

    def _global_place(self, model: _Model, state: list, iters: int) -> None:
        """Denge cozumu: her bilesen bagli oldugu yaylarin agirlikli
        ortalamasina cekilir, ustune yayilma itmesi uygulanir."""
        items = model.items
        for step in range(iters):
            pads = model.pads(state)
            nb = model.net_boxes(pads)
            centers = [
                None if b is None else ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0) for b in nb
            ]

            numx = [0.0] * len(items)
            numy = [0.0] * len(items)
            den = [0.0] * len(items)

            # net yaylari (yildiz modeli)
            for idx in model.movable:
                it = items[idx]
                offs = it.off[state[idx][2]]
                for p, net in enumerate(it.nets):
                    w = model.netw.get(net, 0.0)
                    if w <= 0.0:
                        continue
                    c = centers[model.net_index[net]]
                    if c is None:
                        continue
                    numx[idx] += w * (c[0] - offs[p][0])
                    numy[idx] += w * (c[1] - offs[p][1])
                    den[idx] += w

            # kural yaylari: eslesen kondansator <-> hedef pin (asil kazanc)
            for groups, limit, excl, k in (
                (model.decouple, _DECOUPLE_MM, True, 14.0),
                (model.xtalcap, _XTAL_CAP_MM, True, 16.0),
                (model.regcap, _REGCAP_MM, False, 8.0),
            ):
                rest = 0.45 * limit
                for _key, dist, ti, tp, pi, pp in model.match(groups, pads, excl):
                    if dist is None:
                        continue
                    tx, ty = pads[ti][tp]
                    for who, wpad in ((pi, pp), (ti, tp)):
                        if not items[who].movable:
                            continue
                        px, py = pads[who][wpad]
                        ax, ay = (tx, ty) if who == pi else pads[pi][pp]
                        dx, dy = px - ax, py - ay
                        norm = math.hypot(dx, dy)
                        if norm < 1e-6:
                            dx, dy, norm = 1.0, 0.0, 1.0
                        ix, iy = ax + dx / norm * rest, ay + dy / norm * rest
                        offs = items[who].off[state[who][2]]
                        numx[who] += k * (ix - offs[wpad][0])
                        numy[who] += k * (iy - offs[wpad][1])
                        den[who] += k

            alpha = 0.85 * (1.0 - 0.55 * step / max(1, iters))
            for idx in model.movable:
                if den[idx] <= 0.0:
                    continue
                x, y, r = state[idx]
                state[idx] = (
                    x + alpha * (numx[idx] / den[idx] - x),
                    y + alpha * (numy[idx] / den[idx] - y),
                    r,
                )

            self._spread(model, state, strength=0.55)
            self._confine(model, state)

    def _spread(self, model: _Model, state: list, strength: float) -> None:
        """Yayilma kuvveti: cakisan courtyard'lar en az nufuz eden eksen boyunca
        birbirini iter. Kilitli bilesen itilmez, itmeyi karsi taraf yuklenir."""
        boxes = model.boxes(state)
        n = len(boxes)
        for i in range(n):
            ax1, ay1, ax2, ay2 = boxes[i]
            for j in range(i + 1, n):
                mi, mj = model.items[i].movable, model.items[j].movable
                if not (mi or mj):
                    continue
                bx1, by1, bx2, by2 = boxes[j]
                ox = min(ax2, bx2) - max(ax1, bx1) + _CLEARANCE_AIM
                oy = min(ay2, by2) - max(ay1, by1) + _CLEARANCE_AIM
                if ox <= 0.0 or oy <= 0.0:
                    continue
                if ox < oy:
                    push = ox * strength
                    sign = 1.0 if (ax1 + ax2) <= (bx1 + bx2) else -1.0
                    dxi, dyi, dxj, dyj = -sign * push, 0.0, sign * push, 0.0
                else:
                    push = oy * strength
                    sign = 1.0 if (ay1 + ay2) <= (by1 + by2) else -1.0
                    dxi, dyi, dxj, dyj = 0.0, -sign * push, 0.0, sign * push
                if mi and mj:
                    dxi, dyi, dxj, dyj = dxi / 2, dyi / 2, dxj / 2, dyj / 2
                if mi:
                    x, y, r = state[i]
                    state[i] = (x + dxi, y + dyi, r)
                    boxes[i] = (ax1 + dxi, ay1 + dyi, ax2 + dxi, ay2 + dyi)
                    ax1, ay1, ax2, ay2 = boxes[i]
                if mj:
                    x, y, r = state[j]
                    state[j] = (x + dxj, y + dyj, r)
                    boxes[j] = (bx1 + dxj, by1 + dyj, bx2 + dxj, by2 + dyj)

    def _confine(self, model: _Model, state: list) -> None:
        """Kart siniri: courtyard kenardan _EDGE_AIM kadar iceride kalsin."""
        for idx in model.movable:
            x, y, r = state[idx]
            a, b, c, d = model.items[idx].box[r]
            lo_x, hi_x = model.minx + _EDGE_AIM - a, model.maxx - _EDGE_AIM - c
            lo_y, hi_y = model.miny + _EDGE_AIM - b, model.maxy - _EDGE_AIM - d
            nx = min(max(x, lo_x), hi_x) if lo_x <= hi_x else (lo_x + hi_x) / 2.0
            ny = min(max(y, lo_y), hi_y) if lo_y <= hi_y else (lo_y + hi_y) / 2.0
            state[idx] = (nx, ny, r)

    # ---------------------------------------------------------- 2. legalizasyon

    def _legalize(self, model: _Model, state: list, iters: int) -> None:
        for k in range(iters):
            self._spread(model, state, strength=1.0 if k < iters // 2 else 0.6)
            self._confine(model, state)
            if self._legal(model, state):
                return

    def _legal(self, model: _Model, state: list) -> bool:
        boxes = model.boxes(state)
        n = len(boxes)
        for i in range(n):
            ax1, ay1, ax2, ay2 = boxes[i]
            for j in range(i + 1, n):
                if not (model.items[i].movable or model.items[j].movable):
                    continue
                bx1, by1, bx2, by2 = boxes[j]
                if max(max(bx1 - ax2, ax1 - bx2), max(by1 - ay2, ay1 - by2)) < _CLEARANCE:
                    return False
        for idx in model.movable:
            x1, y1, x2, y2 = boxes[idx]
            if min(x1 - model.minx, y1 - model.miny,
                   model.maxx - x2, model.maxy - y2) < _EDGE_MIN:
                return False
        return True

    def _snap_state(self, model: _Model, state: list) -> None:
        for idx in model.movable:
            x, y, r = state[idx]
            state[idx] = (_snap(x), _snap(y), r)

    # ------------------------------------------------------------ 3. ince ayar

    def _anneal(self, model: _Model, state: list, rng: random.Random, iters: int, until: float):
        cur = [tuple(s) for s in state]
        cur_cost = model.cost(cur)
        best, best_cost = [tuple(s) for s in cur], cur_cost

        span_x = model.maxx - model.minx
        span_y = model.maxy - model.miny
        temp0 = 3.0

        for it in range(iters):
            if it % 512 == 0 and it and time.perf_counter() >= until:
                break
            frac = it / iters
            temp = max(0.02, temp0 * math.exp(-4.2 * frac))
            sigma = max(0.15, 5.0 * (1.0 - 0.92 * frac))

            trial = list(cur)
            idx = rng.choice(model.movable)
            x, y, r = trial[idx]
            roll = rng.random()
            if roll < 0.55:
                trial[idx] = (_snap(x + rng.gauss(0, sigma)), _snap(y + rng.gauss(0, sigma)), r)
            elif roll < 0.70:
                trial[idx] = (
                    _snap(model.minx + rng.random() * span_x),
                    _snap(model.miny + rng.random() * span_y),
                    r,
                )
            elif roll < 0.85:
                trial[idx] = (x, y, rng.randrange(4))
            else:
                other = rng.choice(model.movable)
                if other == idx:
                    continue
                ox, oy, orr = trial[other]
                trial[idx] = (ox, oy, r)
                trial[other] = (x, y, orr)

            cost = model.cost(trial)
            delta = cost - cur_cost
            if delta <= 0.0 or rng.random() < math.exp(-delta / temp):
                cur, cur_cost = trial, cost
                if cur_cost < best_cost:
                    best, best_cost = list(cur), cur_cost

        return best, best_cost

    def _descend(self, model: _Model, state: list, cost: float, passes: int, until: float):
        """Acgozlu inis: kucuk eksen hizali adimlar, kabul yalnizca iyilesirse."""
        cur = list(state)
        cur_cost = cost
        steps = (2.0, 1.0, 0.4, 0.15, _GRID)
        for _ in range(passes):
            improved = False
            for idx in model.movable:
                x, y, r = cur[idx]
                for s in steps:
                    for dx, dy in ((s, 0.0), (-s, 0.0), (0.0, s), (0.0, -s),
                                   (s, s), (s, -s), (-s, s), (-s, -s)):
                        trial = list(cur)
                        trial[idx] = (_snap(x + dx), _snap(y + dy), r)
                        c = model.cost(trial)
                        if c < cur_cost - 1e-9:
                            cur, cur_cost = trial, c
                            x, y, _ = cur[idx]
                            improved = True
                for rr in range(4):
                    if rr == r:
                        continue
                    trial = list(cur)
                    trial[idx] = (cur[idx][0], cur[idx][1], rr)
                    c = model.cost(trial)
                    if c < cur_cost - 1e-9:
                        cur, cur_cost = trial, c
                        improved = True
                if time.perf_counter() >= until:
                    break
            if not improved:
                break
        return cur, cur_cost
