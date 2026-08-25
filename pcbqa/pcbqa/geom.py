"""Kucuk geometri yardimcilari: dısbukey kabuk, cakisma ve mesafe.

Neden gerekli: bilesenlerin kapladigi alani eksen-hizali sinir kutusu (AABB)
ile temsil etmek dondurulmus bilesenlerde ciddi yanlis alarm uretir. Ornek:
KiCad'in stickhub demosunda U1 -135 derece donuk; gercek courtyard'i egik bir
dikdortgen, ama AABB'si cok daha buyuk bir kare. Yakinindaki kondansatorler o
karenin koselerine dusuyor ve "cakisiyor" gibi gorunuyorlar - oysa KiCad'in
kendi DRC'si (gercek poligon kesisimi kullanir) hicbir ihlal bulmuyor.

Bu modul gercek poligon uzerinden calisir:
  * convex_hull  - courtyard noktalarindan dısbukey kabuk (dikdortgenler icin birebir)
  * overlap      - ayirici eksen teoremi (SAT) ile kesin cakisma testi
  * distance     - cakismayan iki poligon arasindaki en kisa mesafe
"""

from __future__ import annotations

import math

Point = tuple[float, float]
Polygon = list[Point]


def convex_hull(points: list[Point]) -> Polygon:
    """Andrew monotone chain. Noktalar sirali gelmek zorunda degil.

    Courtyard'lar dosyada bazen tek bir fp_poly, bazen dort ayri fp_line olarak
    saklanir; ikinci durumda nokta sirasi belirsizdir. Dısbukey kabuk her iki
    durumda da dogru sonuc verir (courtyard'lar pratikte dısbukeydir).
    """
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o: Point, a: Point, b: Point) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: Polygon = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper: Polygon = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    return lower[:-1] + upper[:-1]


def bbox(poly: Polygon) -> tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def area(poly: Polygon) -> float:
    """Shoelace formulu ile alan (isaretten bagimsiz)."""
    if len(poly) < 3:
        return 0.0
    total = 0.0
    for i, (x1, y1) in enumerate(poly):
        x2, y2 = poly[(i + 1) % len(poly)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def _axes(poly: Polygon):
    """Poligon kenarlarinin normalleri (SAT icin aday ayirici eksenler)."""
    for i, (x1, y1) in enumerate(poly):
        x2, y2 = poly[(i + 1) % len(poly)]
        ex, ey = x2 - x1, y2 - y1
        length = math.hypot(ex, ey)
        if length > 1e-12:
            yield (-ey / length, ex / length)


def _project(poly: Polygon, axis: Point) -> tuple[float, float]:
    dots = [p[0] * axis[0] + p[1] * axis[1] for p in poly]
    return min(dots), max(dots)


def overlap(a: Polygon, b: Polygon) -> bool:
    """Iki dısbukey poligon kesisiyor mu? (Ayirici Eksen Teoremi)"""
    if len(a) < 3 or len(b) < 3:
        return False
    for axis in (*_axes(a), *_axes(b)):
        amin, amax = _project(a, axis)
        bmin, bmax = _project(b, axis)
        if amax < bmin or bmax < amin:
            return False  # ayirici eksen bulundu -> kesismiyorlar
    return True


def _segment_distance(p1: Point, p2: Point, q1: Point, q2: Point) -> float:
    """Iki dogru parcasi arasindaki en kisa mesafe."""

    def point_seg(p: Point, a: Point, b: Point) -> float:
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        denom = dx * dx + dy * dy
        if denom < 1e-12:
            return math.hypot(p[0] - ax, p[1] - ay)
        t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / denom))
        return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))

    return min(
        point_seg(p1, q1, q2),
        point_seg(p2, q1, q2),
        point_seg(q1, p1, p2),
        point_seg(q2, p1, p2),
    )


def distance(a: Polygon, b: Polygon) -> float:
    """Iki poligon arasindaki en kisa mesafe. Kesisiyorlarsa 0.0 (negatif degil).

    Kesisme durumunu ayirt etmek icin once overlap() cagirin.
    """
    if overlap(a, b):
        return 0.0
    best = math.inf
    for i in range(len(a)):
        p1, p2 = a[i], a[(i + 1) % len(a)]
        for j in range(len(b)):
            q1, q2 = b[j], b[(j + 1) % len(b)]
            best = min(best, _segment_distance(p1, p2, q1, q2))
    return best if best is not math.inf else 0.0
