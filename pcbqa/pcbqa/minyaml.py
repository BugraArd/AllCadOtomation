"""Bagimliliksiz YAML okuyucu - PROJENIN KULLANDIGI ALTKUME.

## Neden var

Bagimsiz uygulama KiCad'in kendi Python'unda kosuyor ve orada pyyaml YOK.
Kural ve sablon dosyalari icin JSON kopyalari yeterliydi (`bundle.py`), ama
KULLANICININ KENDI niyet ve kural dosyalari YAML'dir ve "once JSON'a cevir"
demek kabul edilemez bir kullanim adimidir.

`sexpr.py` de ayni gerekceyle sifirdan yazilmisti: girdi bicimi bizim
tanimladigimiz bir sey ve tek bir ucuncu parti paket icin tasinabilirlikten
vazgecmek pahali.

## Desteklenen altkume (21 YAML dosyasi tarandi, olculdu)

    ic ice blok eslesme     490 satir
    blok liste (-)          105
    satir ici liste [a, b]   23
    satir ici eslesme {a: 1} 16
    tirnakli anahtar          9
    capa/cok satirli/etiket   0   <- HIC KULLANILMIYOR

## Anlamadigini SESSIZCE GECMEZ

Bu okuyucunun tehlikeli olabilecegi tek yol, desteklemedigi bir yapiyi
yanlis yorumlamasidir. Bu yuzden capa (`&`/`*`), etiket (`!!`), cok satirli
skaler (`|`/`>`), belge ayraci (`---`) ve girintide sekme gorunce HATA atar.
Kullanici o zaman ne oldugunu bilir; sessizce yanlis kural yuklenmez.

Dogrulugu `tests/test_minyaml.py` PYYAML ILE KARSILASTIRARAK korur: depodaki
her YAML dosyasi iki okuyucudan gecirilir ve sonuclar birebir esit olmalidir.
"""

from __future__ import annotations

import re
from typing import Any

# Girinti icinde sekme YAML'de yasak; sessizce bosluga cevirmek hizalamayi
# bozar ve bambaska bir agac uretir.
_TAB_IN_INDENT = re.compile(r"^[ ]*\t")

_UNSUPPORTED = (
    ("---", "belge ayraci"),
    ("...", "belge sonu"),
)


class MiniYamlError(RuntimeError):
    """YAML okunamadi ya da desteklenmeyen bir yapi iceriyor."""


def _fail(line_no: int, message: str) -> None:
    raise MiniYamlError(f"satir {line_no}: {message}")


# --------------------------------------------------------------------------
# Skaler cozumleme
# --------------------------------------------------------------------------

# Asagidaki desenler PyYAML'in cozumleyicisinden BIREBIR alindi. Sezgiyle
# yazmak yanlis olurdu, cunku YAML 1.1'in sayi kurallari tuzakli - olculdu:
#
#     1e3     -> METIN   (us icin isaret zorunlu)
#     1.0e3   -> METIN
#     1.0e+3  -> 1000.0
#     012     -> 10      (SEKIZLIK!)
#     0603    -> 387     (yine sekizlik)
#     0805    -> METIN   (8 sekizlik degil)
#     1:30    -> 90      (altmislik)
#     1_000   -> 1000
#
# Bu tutarsizliklari "duzeltmek" bizim isimiz degil: amac pyyaml ile AYNI
# agaci uretmek, yoksa ayni dosya iki ortamda iki farkli kural yukler.
_BOOL_TRUE = {"yes", "true", "on"}
_BOOL_FALSE = {"no", "false", "off"}
_NULL = {"", "~", "null"}

_INT = re.compile(
    r"^(?:[-+]?0b[0-1_]+"
    r"|[-+]?0[0-7_]+"
    r"|[-+]?(?:0|[1-9][0-9_]*)"
    r"|[-+]?0x[0-9a-fA-F_]+"
    r"|[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+)$"
)
_FLOAT = re.compile(
    r"^(?:[-+]?(?:[0-9][0-9_]*)\.[0-9_]*(?:[eE][-+][0-9]+)?"
    r"|\.[0-9_]+(?:[eE][-+][0-9]+)?"
    r"|[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\.[0-9_]*"
    r"|[-+]?\.(?:inf|Inf|INF)"
    r"|\.(?:nan|NaN|NAN))$"
)


def _to_int(text: str) -> int:
    """YAML 1.1 tam sayisi: ikilik, sekizlik, onalti, altmislik ve `_` ayraci."""
    sign = 1
    if text and text[0] in "+-":
        sign = -1 if text[0] == "-" else 1
        text = text[1:]
    text = text.replace("_", "")
    if text.startswith("0b"):
        return sign * int(text[2:], 2)
    if text.startswith("0x"):
        return sign * int(text[2:], 16)
    if ":" in text:
        total = 0
        for part in text.split(":"):
            total = total * 60 + int(part)
        return sign * total
    if text.startswith("0") and len(text) > 1:
        return sign * int(text, 8)
    return sign * int(text)


def _to_float(text: str) -> float:
    sign = 1.0
    if text and text[0] in "+-":
        sign = -1.0 if text[0] == "-" else 1.0
        text = text[1:]
    text = text.replace("_", "")
    lowered = text.lower()
    if lowered == ".inf":
        return sign * float("inf")
    if lowered == ".nan":
        return float("nan")
    if ":" in text:
        total = 0.0
        for part in text.split(":"):
            total = total * 60.0 + float(part)
        return sign * total
    return sign * float(text)


def _unquote(text: str, line_no: int) -> str:
    quote = text[0]
    if len(text) < 2 or text[-1] != quote:
        _fail(line_no, f"kapanmamis tirnak: {text[:40]}")
    body = text[1:-1]
    if quote == "'":
        return body.replace("''", "'")
    out: list[str] = []
    i = 0
    escapes = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "/": "/", "0": "\0"}
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            out.append(escapes.get(nxt, nxt))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def parse_scalar(text: str, line_no: int = 0) -> Any:
    """Tek bir skaleri Python degerine cevirir (PyYAML safe_load ile ayni)."""
    text = text.strip()
    if text and text[0] in "\"'":
        return _unquote(text, line_no)
    if text.startswith(("&", "*")):
        _fail(line_no, "capa/atif (&, *) desteklenmiyor")
    if text.startswith("!"):
        _fail(line_no, "etiket (!) desteklenmiyor")
    low = text.lower()
    if low in _NULL:
        return None
    if low in _BOOL_TRUE:
        return True
    if low in _BOOL_FALSE:
        return False
    if _INT.match(text):
        return _to_int(text)
    if _FLOAT.match(text):
        return _to_float(text)
    return text


# --------------------------------------------------------------------------
# Satir ici (flow) bicim: [a, b]  ve  {a: 1}
# --------------------------------------------------------------------------


def _split_flow(body: str, line_no: int) -> list[str]:
    """Virgulle ayirir ama tirnak ve ic ice parantezleri sayar."""
    parts: list[str] = []
    depth = 0
    quote = ""
    current: list[str] = []
    for ch in body:
        if quote:
            current.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            current.append(ch)
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
            if depth < 0:
                _fail(line_no, "fazladan kapanis parantezi")
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)
    if quote:
        _fail(line_no, "kapanmamis tirnak")
    if depth:
        _fail(line_no, "kapanmamis parantez")
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return [p.strip() for p in parts if p.strip()]


def _split_key(text: str, line_no: int) -> tuple[str, str] | None:
    """`anahtar: deger` ayrimi; tirnak ve parantez icindeki iki nokta sayilmaz."""
    depth = 0
    quote = ""
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == ":" and depth == 0:
            after = text[i + 1:]
            if after and not after[0].isspace():
                continue  # "a:b" bir anahtar degil, duz metin
            return text[:i].strip(), after.strip()
    return None


def parse_flow(text: str, line_no: int = 0) -> Any:
    """`[a, b]` ya da `{a: 1, b: 2}` cozumler."""
    text = text.strip()
    if text.startswith("["):
        if not text.endswith("]"):
            _fail(line_no, "kapanmamis [")
        return [parse_flow(p, line_no) for p in _split_flow(text[1:-1], line_no)]
    if text.startswith("{"):
        if not text.endswith("}"):
            _fail(line_no, "kapanmamis {")
        out: dict[str, Any] = {}
        for part in _split_flow(text[1:-1], line_no):
            split = _split_key(part, line_no)
            if split is None:
                _fail(line_no, f"eslesme ogesi 'anahtar: deger' olmali: {part}")
            key, value = split
            out[str(parse_scalar(key, line_no))] = parse_flow(value, line_no)
        return out
    return parse_scalar(text, line_no)


# --------------------------------------------------------------------------
# Satir hazirligi
# --------------------------------------------------------------------------


def _strip_comment(line: str, line_no: int) -> str:
    """Tirnak disindaki `#` ve sonrasini atar."""
    quote = ""
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            continue
        if ch == "#" and (i == 0 or line[i - 1].isspace()):
            return line[:i].rstrip()
    return line.rstrip()


def _lines(text: str) -> list[tuple[int, int, str]]:
    """(satir_no, girinti, icerik) - bos ve yorum satirlari elenmis."""
    out: list[tuple[int, int, str]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if _TAB_IN_INDENT.match(raw):
            _fail(number, "girintide sekme var (YAML sekmeye izin vermez)")
        stripped = _strip_comment(raw, number)
        if not stripped.strip():
            continue
        content = stripped.strip()
        for token, name in _UNSUPPORTED:
            if content == token:
                _fail(number, f"{name} ({token}) desteklenmiyor")
        if content[:1] in "|>" or content.endswith((": |", ": >")):
            _fail(number, "cok satirli skaler (| ya da >) desteklenmiyor")
        out.append((number, len(stripped) - len(stripped.lstrip(" ")), content))
    return out


# --------------------------------------------------------------------------
# Blok cozumleme
# --------------------------------------------------------------------------


def _parse_block(rows: list[tuple[int, int, str]], start: int, indent: int) -> tuple[Any, int]:
    """`rows[start:]` icinden `indent` girintisindeki blogu okur."""
    if start >= len(rows):
        return None, start
    if rows[start][2].startswith("- "):
        return _parse_list(rows, start, indent)
    if rows[start][2] == "-":
        return _parse_list(rows, start, indent)
    return _parse_map(rows, start, indent)


def _parse_list(rows, start: int, indent: int) -> tuple[list, int]:
    items: list[Any] = []
    i = start
    while i < len(rows):
        line_no, level, content = rows[i]
        if level < indent:
            break
        if level > indent:
            _fail(line_no, "beklenmeyen girinti (liste ogesi hizasi bozuk)")
        if not (content == "-" or content.startswith("- ")):
            break
        rest = content[1:].strip()
        i += 1
        if not rest:
            value, i = _parse_block(rows, i, indent + 1) if i < len(rows) and rows[i][1] > indent else (None, i)
            items.append(value)
            continue
        # "- anahtar: deger" -> ogenin kendisi bir eslesme
        split = _split_key(rest, line_no)
        if split is not None and not rest.startswith(("[", "{")):
            key, value_text = split
            child_indent = indent + 2
            entry: dict[str, Any] = {}
            entry[str(parse_scalar(key, line_no))], i = _value_of(
                value_text, rows, i, child_indent, line_no
            )
            while i < len(rows) and rows[i][1] > indent and not rows[i][2].startswith("- "):
                more, i = _parse_map(rows, i, rows[i][1])
                entry.update(more)
            items.append(entry)
            continue
        items.append(parse_flow(rest, line_no))
    return items, i


def _parse_map(rows, start: int, indent: int) -> tuple[dict, int]:
    out: dict[str, Any] = {}
    i = start
    while i < len(rows):
        line_no, level, content = rows[i]
        if level < indent:
            break
        if level > indent:
            _fail(line_no, "beklenmeyen girinti (eslesme hizasi bozuk)")
        if content.startswith("- "):
            break
        split = _split_key(content, line_no)
        if split is None:
            _fail(line_no, f"'anahtar: deger' bekleniyordu: {content[:60]}")
        key, value_text = split
        i += 1
        out[str(parse_scalar(key, line_no))], i = _value_of(
            value_text, rows, i, indent, line_no
        )
    return out, i


def _value_of(value_text: str, rows, i: int, indent: int, line_no: int) -> tuple[Any, int]:
    """Anahtarin degeri: ayni satirda ya da altinda girintili blok."""
    if value_text:
        return parse_flow(value_text, line_no), i
    if i < len(rows) and rows[i][1] > indent:
        return _parse_block(rows, i, rows[i][1])
    return None, i


def safe_load(text: str) -> Any:
    """Metni Python degerine cevirir. `yaml.safe_load` ile ayni sonuc.

    Desteklenmeyen bir yapi gorunce `MiniYamlError` atar - sessizce yanlis
    yorumlamaz.
    """
    rows = _lines(text)
    if not rows:
        return None
    value, consumed = _parse_block(rows, 0, rows[0][1])
    if consumed < len(rows):
        _fail(rows[consumed][0], "cozumlenemeyen satir (girinti hizasi bozuk olabilir)")
    return value
