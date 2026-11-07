"""Text helpers that work for Arabic and English."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_ARABIC = re.compile(r"[؀-ۿ]")

# Very common words that carry little meaning when matching questions.
STOPWORDS = {
    "the", "a", "an", "is", "are", "what", "whats", "who", "how", "do", "does", "you",
    "me", "my", "of", "to", "in", "on", "and", "please", "jarvis", "can", "i",
    "ما", "ماهو", "ماهي", "هو", "هي", "من", "في", "على", "عن", "الى", "هل", "يا",
    "جارفيس", "انت", "لو", "سمحت", "وش", "ايش", "شو", "كيف", "متى", "اين", "وين",
}


def is_arabic(text: str) -> bool:
    return bool(_ARABIC.search(text or ""))


def normalize(text: str) -> str:
    """Lower-case, strip diacritics/punctuation and unify Arabic letter forms."""
    t = (text or "").strip().lower()
    t = _DIACRITICS.sub("", t)
    t = re.sub("[إأآٱ]", "ا", t)
    t = t.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    t = t.replace("؟", " ").replace("،", " ")
    t = _PUNCT.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def keywords(text: str) -> set[str]:
    words = set()
    for w in normalize(text).split():
        if w.startswith("ال") and len(w) > 4:   # drop the Arabic article "al-"
            w = w[2:]
        if w not in STOPWORDS and len(w) > 1:
            words.add(w)
    return words


def similarity(a: str, b: str) -> float:
    """0..1 score mixing character similarity and keyword overlap."""
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    char = SequenceMatcher(None, na, nb).ratio()
    ka, kb = keywords(a), keywords(b)
    jac = len(ka & kb) / len(ka | kb) if (ka or kb) else 0.0
    return 0.55 * char + 0.45 * jac


def utf8_console() -> None:
    """Make print() safe for Arabic/emoji on any console (Windows pipes default to cp1252)."""
    import sys
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
