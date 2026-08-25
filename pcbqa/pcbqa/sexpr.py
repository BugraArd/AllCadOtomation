"""Kucuk, bagimliliksiz bir s-expression okuyucu.

KiCad'in .kicad_pcb / .kicad_sch dosyalari s-expression formatinda tutulur:

    (footprint "Lib:Ad" (layer "F.Cu") (at 110.49 78.867 180) ...)

Bu modul o metni ic ice gecmis Python listelerine cevirir:

    ['footprint', 'Lib:Ad', ['layer', 'F.Cu'], ['at', '110.49', '78.867', '180'], ...]

Ozyineleme yerine yigin (stack) kullanir; cok derin dosyalarda bile guvenlidir.
"""

from __future__ import annotations

_WS = " \t\r\n"
_DELIM = _WS + '()"'
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r"}

SExpr = list  # ic ice listeler; atomlar str


class QuotedStr(str):
    """Dosyada tirnak icinde yazilmis bir atom.

    Ayrimi korumak sart: `(at 110.49 78.867 180)` icindeki sayilar tirnaksiz,
    `(layer "F.Cu")` icindeki deger tirnaklidir. Ayrim kaybolursa dosyayi geri
    yazarken ya sayilar tirnaklanir ya da bosluklu metinler bozulur - iki
    durumda da KiCad dosyayi reddeder.
    """

    __slots__ = ()


class SExprError(ValueError):
    """Bozuk s-expression."""


def parse(text: str, strict: bool = False) -> SExpr:
    """Metni tek bir kok ifadeye cevirir.

    Gercek dunyada KiCad dosyalari bazen bozuk olabiliyor (or. KiCad 10.0.4 ile
    gelen royalblue54L_feather demosunda teardrop ayarlarinda acilis parantezi
    eksik). Varsayilan olarak bu arac toleransli davranir: fazladan ')' atlanir
    ve kok erken kapanirsa kalan ust duzey dugumler koke eklenir; boylece
    dosyanin buyuk kismi yine de okunabilir.

    strict=True verilirse bozuk girdide SExprError firlatilir.
    """
    return parse_with_stats(text, strict=strict)[0]


def parse_with_stats(text: str, strict: bool = False) -> tuple[SExpr, int]:
    """parse() ile ayni, ama atlanan bozuk parantez sayisini da dondurur."""
    pos, n = 0, len(text)
    stack: list[list] = []
    tops: list[SExpr] = []
    stray = 0

    while pos < n:
        ch = text[pos]

        if ch in _WS:
            pos += 1

        elif ch == "(":
            node: list = []
            if stack:
                stack[-1].append(node)
            stack.append(node)
            pos += 1

        elif ch == ")":
            if not stack:
                if strict:
                    raise SExprError(f"fazladan ')' (konum {pos})")
                stray += 1
                pos += 1
                continue
            node = stack.pop()
            if not stack:
                tops.append(node)
            pos += 1

        elif ch == '"':
            pos += 1
            buf: list[str] = []
            while pos < n:
                c = text[pos]
                if c == "\\" and pos + 1 < n:
                    nxt = text[pos + 1]
                    buf.append(_ESCAPES.get(nxt, nxt))
                    pos += 2
                elif c == '"':
                    pos += 1
                    break
                else:
                    buf.append(c)
                    pos += 1
            else:
                raise SExprError("kapanmamis tirnak")
            if stack:
                stack[-1].append(QuotedStr("".join(buf)))

        else:
            start = pos
            while pos < n and text[pos] not in _DELIM:
                pos += 1
            if stack:
                stack[-1].append(text[start:pos])

    if stack:
        if strict:
            raise SExprError("kapanmamis parantez")
        # Kapanmamis dugumleri de kurtar (en distaki koktur)
        tops.append(stack[0])
        stray += len(stack)

    if not tops:
        raise SExprError("okunabilir s-expression bulunamadi")

    root = tops[0]
    # Kok erken kapandiysa geri kalan ust duzey dugumler onun altina alinir,
    # boylece children(root, "footprint") gibi taramalar calismaya devam eder.
    for extra in tops[1:]:
        root.append(extra)
    return root, stray


def _quote(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def dumps(node, indent: int = 0) -> str:
    """Ayristirilmis agaci tekrar .kicad_pcb metnine cevirir.

    Bicimlendirme KiCad'inkiyle bayt bayt ayni degildir ama gecerlidir ve
    KiCad dosyayi sorunsuz acar. Alt dugumu olmayan kisa ifadeler tek satirda
    yazilir (`(at 10 20)`), digerleri girintili coklu satir olur.
    """
    if isinstance(node, QuotedStr):
        return _quote(node)
    if isinstance(node, str):
        return node
    if not isinstance(node, list):
        return _quote(str(node))

    pad = "\t" * indent
    if not node:
        return pad + "()"

    has_list_child = any(isinstance(c, list) for c in node)
    if not has_list_child:
        inner = " ".join(dumps(c) for c in node)
        return f"{pad}({inner})"

    lines = [f"{pad}({dumps(node[0])}"]
    inline: list[str] = []
    for child in node[1:]:
        if isinstance(child, list):
            if inline:
                lines[-1] += " " + " ".join(inline)
                inline = []
            lines.append(dumps(child, indent + 1))
        else:
            inline.append(dumps(child))
    if inline:
        lines[-1] += " " + " ".join(inline)
    lines.append(f"{pad})")
    return "\n".join(lines)


def head(node) -> str | None:
    """Dugumun etiketi: ['at','1','2'] -> 'at'."""
    if isinstance(node, list) and node and isinstance(node[0], str):
        return node[0]
    return None


def children(node, name: str):
    """Dogrudan alt dugumlerden etiketi `name` olanlar."""
    if not isinstance(node, list):
        return
    for c in node:
        if isinstance(c, list) and c and c[0] == name:
            yield c


def child(node, name: str):
    """Etiketi `name` olan ilk alt dugum, yoksa None."""
    return next(children(node, name), None)


def value(node, name: str, index: int = 1, default=None):
    """(name v0 v1 ...) dugumunun `index`. degeri."""
    c = child(node, name)
    if c is None or len(c) <= index:
        return default
    return c[index]


def as_float(x, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default
