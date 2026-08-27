"""Yerlestirici, "uzaklastir" tipi kisitlara nasil tepki veriyor?

Arka plan (bead Kicad-ec5): arastirmadaki kurallarin sasirtici bir kismi
"yaklastir" degil UZAKLASTIR diyor (FB izi -> induktor >= 10 mm, I2C pull-up ->
sicaklik sensoru >= 10 mm). `auto` yalnizca HPWL kucultuyor gibi gorundugu icin
bu kisitlari sistematik ihlal ettigi VARSAYILDI ve skora ayri bir ceza eklemek
gerektigi dusunuldu.

Olcum bunun YANLIS oldugunu gosterdi: `evaluate_design` kural dosyasindaki TUM
kurallari calistirir, yani keep_apart bulgulari zaten skoru besliyor. Eksik olan
sey mekanizma degildi - hicbir kural dosyasinda keep_apart kurali YOKTU, yani
yetenek hic denenmemisti.

Bu iki test o olcumu kalici hale getirir. Ikisi de gercek bir davranisi korur:

  1. Karsilanabilir bir kisit -> auto onu SAGLAR.
  2. Baska (daha guclu) bir kisitla catisan bir kisit -> auto onun pesine dusup
     kartin geri kalanini BOZMAZ.

Ikincisi ozellikle onemli: birisi "auto keep_apart'i ihlal ediyor" diye bakip
yerlestiriciyi kisiti korukorune saglamaya zorlarsa bu test kirilir.
"""

from __future__ import annotations

import copy
import math
import tempfile
import unittest
from pathlib import Path

from pcbqa.harness import (
    apply_placement,
    evaluate_design,
    load_design,
    locked_refs,
    make_evaluator,
)
from pcbqa.placement import get as get_placer
from pcbqa.placement.base import PlacementContext
from pcbqa.rules import load_rules

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "samples" / "bench_bad.kicad_pcb"
BENCH_RULES = ROOT / "samples" / "bench.rules.yaml"

# Olculdu: 3 s butce bu kartta kisiti saglamaya yetiyor (6 s ile ayni sonuc).
BUDGET = 3.0
SEED = 1

# C8 (22pF kristal yuk kondansatoru) ve R2 (4k7 pull-up) ORTAK NET TASIMIYOR,
# dolayisiyla ayirmak HPWL'i neredeyse hic etkilemez - "ucuz" kisit budur.
CHEAP_A, CHEAP_B = "C8", "R2"
CHEAP_MIN_MM = 11.1


def rules_with(tmp: Path, body: str):
    """bench kurallari + ek bir kural iceren gecici kural dosyasi."""
    path = tmp / "kural.yaml"
    path.write_text(
        f"version: 1\ninclude:\n  - {BENCH_RULES.as_posix()}\nrules:\n{body}",
        encoding="utf-8",
    )
    return load_rules(path)


def run_auto(rules):
    design = load_design(BOARD)
    ctx = PlacementContext(
        design=design,
        evaluator=make_evaluator(design, rules),
        locked=locked_refs(design),
        seed=SEED,
        time_budget_s=BUDGET,
    )
    placement = get_placer("auto").run(ctx)
    placed = apply_placement(copy.deepcopy(load_design(BOARD)), placement)
    return placed, evaluate_design(placed, rules)


def gap(design, ref_a: str, ref_b: str) -> float:
    a, b = design.component(ref_a), design.component(ref_b)
    return math.hypot(a.x - b.x, a.y - b.y)


class KeepApartPlacementTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_auto_satisfies_an_affordable_keep_apart(self):
        """Ucuz bir kisit skora girince auto onu saglar.

        Bu, keep_apart'in ucu uca calistiginin kaniti: kural motoru olcuyor,
        skor cezalandiriyor, yerlestirici tepki veriyor. Ayri bir ceza terimi
        GEREKMIYOR.
        """
        rules = rules_with(
            self.tmp,
            f"  - id: ucuz-ayrim\n"
            f"    type: keep_apart\n"
            f"    severity: error\n"
            f'    description: "Deney: {CHEAP_A} ile {CHEAP_B} ayri dursun"\n'
            f'    a: {{ ref: "^{CHEAP_A}$" }}\n'
            f'    b: {{ ref: "^{CHEAP_B}$" }}\n'
            f"    min_distance_mm: {CHEAP_MIN_MM}\n",
        )
        placed, _ = run_auto(rules)
        self.assertGreaterEqual(
            gap(placed, CHEAP_A, CHEAP_B),
            CHEAP_MIN_MM,
            f"{CHEAP_A}<->{CHEAP_B} kisiti karsilanabilir olmasina ragmen saglanmadi",
        )

    def test_auto_does_not_wreck_the_board_for_an_infeasible_constraint(self):
        """Catisan bir kisit pesinde kartin geri kalani bozulmamali.

        Kristali USB konnektorunden 30 mm uzaga tasimak, onu MCU'dan ve yuk
        kondansatorlerinden koparir - o da kaynakli bir kural. Olculdu: kisiti
        saglayan EN IYI konum bile skoru 44.9'dan 13.5'e dusuruyor (hata 2->5).
        Yani auto'nun kisiti reddetmesi DOGRU davranistir.
        """
        infeasible = rules_with(
            self.tmp,
            "  - id: imkansiz-ayrim\n"
            "    type: keep_apart\n"
            "    severity: error\n"
            '    description: "Deney: kristal konnektorden 30 mm uzak"\n'
            '    a: { kind: crystal }\n'
            '    b: { ref: "^J1$" }\n'
            "    min_distance_mm: 30.0\n",
        )
        constrained, ev_constrained = run_auto(infeasible)

        baseline_rules = load_rules(BENCH_RULES)
        baseline, ev_baseline = run_auto(baseline_rules)

        # Imkansiz kisidin kendi bulgusu haric, kart en az baseline kadar iyi
        # olmali: auto kovalamaca ugruna baska kurallari bozmamali.
        other_errors = sum(
            1
            for f in ev_constrained.findings
            if f.severity == "error" and f.rule_id != "imkansiz-ayrim"
        )
        self.assertLessEqual(
            other_errors,
            ev_baseline.errors,
            "imkansiz kisit pesinde baska kurallar bozuldu",
        )
        self.assertLessEqual(
            ev_constrained.total_hpwl_mm,
            ev_baseline.total_hpwl_mm * 1.10,
            "imkansiz kisit HPWL'i %10'dan fazla kotulestirdi",
        )


if __name__ == "__main__":
    unittest.main()
