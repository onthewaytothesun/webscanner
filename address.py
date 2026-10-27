"""
Addresses from the device's Identity.

Routers are named «<тип>_<Адрес>», for example CP_Natashi_Kovshovoy_29 or
S_Varshavskoe_sh_128k1 (V / CP / CPL / R / S before the address); antennas are named
«<CPE|AP>_<адрес антенны>-><адрес ответной антенны>», for example
AP_Varshavskoe_sh_128k1->Kavkazskiy_b_r_59s2. The addresses are written in Latin
letters; this module turns them back into Russian:

    CP_Natashi_Kovshovoy_29                    -> Наташи Ковшовой 29
    CPE_Dorozhnaya_1k5s3->Dnepropetrovskaya_1  -> Дорожная 1к5с3  (ответная: Днепропетровская 1)

Everything before the address is dropped, as is a «(2)» at the end (it only tells
the routers on one address apart). Latin letters do not say everything (ь, ё, э are
lost), so a small dictionary of common words is built in, and the operator can add
their own in mt_config.json, section "translit": {"ulyanova": "Ульянова"} (a whole
word in lower case -> how it is written; used by both programs).

No Tk here: this is unit tested headlessly.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

# what stands before the address in an Identity
PREFIXES = {"V", "CP", "CPL", "R", "S", "CPE", "AP"}

_DIGRAPHS = (("shch", "щ"), ("sch", "щ"), ("zh", "ж"), ("kh", "х"), ("ts", "ц"), ("ch", "ч"),
             ("sh", "ш"), ("yu", "ю"), ("ya", "я"), ("yo", "ё"), ("ye", "е"), ("ju", "ю"), ("ja", "я"))
_LETTERS = {
    "a": "а", "b": "б", "v": "в", "g": "г", "d": "д", "e": "е", "z": "з", "i": "и", "k": "к",
    "l": "л", "m": "м", "n": "н", "o": "о", "p": "п", "r": "р", "s": "с", "t": "т", "u": "у",
    "f": "ф", "h": "х", "c": "ц", "j": "й", "x": "кс", "w": "в", "q": "к",
}
_VOWELS = set("aeiou")

# abbreviations written as separate words, and words whose spelling cannot be rebuilt
# from the Latin letters (the soft sign, э instead of е)
BUILTIN_WORDS: Dict[str, str] = {
    "sh": "ш.", "pr": "пр-т", "ul": "ул.", "per": "пер.", "pl": "пл.", "nab": "наб.", "al": "ал.",
    "tup": "туп.", "mkr": "мкр.", "d": "д.", "dom": "д.", "korp": "корп.", "str": "стр.", "g": "г.",
    "pos": "пос.", "bulvar": "бульвар", "proezd": "проезд", "shosse": "шоссе",
    "ploshchad": "площадь", "ploschad": "площадь",
    "bolshaya": "Большая", "bolshoy": "Большой", "bolshoe": "Большое", "bolshie": "Большие",
    "ulyanova": "Ульянова", "ulyanovskaya": "Ульяновская", "ilyicha": "Ильича",
    "kuzminki": "Кузьминки", "kuzminskaya": "Кузьминская", "gorkogo": "Горького",
    "pyatnitskaya": "Пятницкая", "kuznetskiy": "Кузнецкий", "kuznetskaya": "Кузнецкая",
}
# two words that are one abbreviation: b_r -> б-р
COMBOS: Dict[Tuple[str, str], str] = {
    ("b", "r"): "б-р", ("pr", "t"): "пр-т", ("pr", "d"): "пр-д", ("pr", "kt"): "пр-кт",
}
# a word that starts like this starts with э, not е
_E_STEMS = ("elektr", "energ", "entuz", "ekspr", "ekonom", "eksper", "estonsk", "ekolog", "ehr")
# where the Latin spelling hides a soft sign («'» below) or a «тс» that is not «ц»:
# Shkolnaya -> Школьная, Podolsk -> Подольск, Oktyabrskaya -> Октябрьская,
# Ilyinskaya -> Ильинская, Vasilyevskaya -> Васильевская, Sovetskaya -> Советская
_CONSONANT = "bcdfghjklmnpqrstvwxz"
_SPELLING = (
    (re.compile(r"lsk"), "l'sk"),
    (re.compile(r"brsk"), "br'sk"),
    (re.compile(r"ln(aya|yaya|yy|yi|yj|iy|oe|ye|ie|ogo|oy|ykh|ikh|aja)$"), r"l'n\1"),
    (re.compile(rf"(?<=[{_CONSONANT}])yi"), "'i"),
    (re.compile(rf"(?<=[{_CONSONANT}])ye"), "'ye"),
    (re.compile(r"tsk"), "t\x00sk"),
)
_HOUSE = re.compile(r"^\d")      # a token that starts with a digit is a house number: 128k1, 59s2, 1k5s3
_TRAIL = re.compile(r"\s*\(\s*\d+\s*\)\s*$")
_ARROW = re.compile(r"\s*(?:->|→|=>)\s*")


def _word(token: str) -> str:
    """One Latin word -> Russian, with a capital letter."""
    low = token.lower()
    out: List[str] = []
    i = 0
    if low.startswith(_E_STEMS):
        out.append("э")
        i = 1
    for pattern, repl in _SPELLING:
        low = pattern.sub(repl, low)
    while i < len(low):
        for latin, cyr in _DIGRAPHS:
            if low.startswith(latin, i):
                out.append(cyr)
                i += len(latin)
                break
        else:
            ch = low[i]
            if ch == "y":
                prev = low[i - 1] if i else ""
                out.append("й" if prev in _VOWELS or prev == "y" or not prev else "ы")
            elif ch == "'":
                out.append("ь")
            elif ch == "\x00":       # only splits a digraph: t|s
                pass
            elif ch in _LETTERS:
                out.append(_LETTERS[ch])
            else:
                out.append(ch)      # digits, hyphens and the like stay as they are
            i += 1
    text = "".join(out)
    return text[:1].upper() + text[1:]


def _house(token: str) -> str:
    """128k1 -> 128к1, 1k5s3 -> 1к5с3: the letters of a house number are single letters."""
    return "".join(_LETTERS.get(ch, ch) if ch.isalpha() else ch for ch in token.lower())


def strip_prefix(tokens: List[str]) -> List[str]:
    """Drop the type before the address: V / CP / CPL / R / S / CPE / AP, and any other
    short word in capitals (the address itself is written Like_This)."""
    tokens = list(tokens)
    while len(tokens) > 1 and (tokens[0].upper() in PREFIXES or (
            tokens[0].isalpha() and tokens[0].isupper() and len(tokens[0]) <= 4)):
        tokens.pop(0)
    return tokens


def to_russian(tokens: List[str], words: Optional[Dict[str, str]] = None) -> str:
    """The words of one address (without the prefix) in Russian."""
    words = {**BUILTIN_WORDS, **{k.lower(): v for k, v in (words or {}).items()}}
    out: List[str] = []
    i = 0
    while i < len(tokens):
        low = tokens[i].lower()
        if i + 1 < len(tokens) and (low, tokens[i + 1].lower()) in COMBOS:
            out.append(COMBOS[(low, tokens[i + 1].lower())])
            i += 2
            continue
        if low in words:
            out.append(words[low])
        elif _HOUSE.match(low):
            out.append(_house(low))
        else:
            out.append(_word(tokens[i]))
        i += 1
    return " ".join(out)


def _one(text: str, words) -> str:
    tokens = [t for t in re.split(r"[_\s]+", text.strip()) if t]
    return to_russian(strip_prefix(tokens), words) if tokens else ""


def parse_identity(identity: str, words: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    """(address of the device, address of the opposite antenna) in Russian.
    The second one is empty for routers and for antennas named without «->»."""
    text = _TRAIL.sub("", (identity or "").strip())
    parts = _ARROW.split(text, maxsplit=1)
    own = _one(parts[0], words)
    remote = _one(parts[1], words) if len(parts) > 1 else ""
    return own, remote
