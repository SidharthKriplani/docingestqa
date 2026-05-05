from __future__ import annotations

import hashlib
import math
import re
import string
import unicodedata
from collections import Counter

_WORD_RE = re.compile(r"\w+", flags=re.UNICODE)
_REPEATED_CHAR_RE = re.compile(r"(.)\1{7,}")
_SENTENCE_END_RE = re.compile(r"[.!?…\"\'»)\]]+\s*$")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Mojibake: UTF-8 bytes 0x80–0xBF decoded as latin-1 produce U+0080–U+00BF.
# Common patterns: Ã© = é, Â© = ©, â€™ = ', â€œ = "
_MOJIBAKE_RE = re.compile(
    r"Ã[\x80-\xbf]"      # é → Ã©, à → Ãà, etc.
    r"|Â[\x80-\xbf]"     # © → Â©, ® → Â®, etc.
    r"|â\x80[\x90-\x9f]" # smart quotes/dashes: ' → â€™, " → â€œ, – → â€"
)


def normalize_text(text: str) -> str:
    return " ".join(text.lower().strip().split())


def stable_hash(text: str) -> str:
    return hashlib.sha1(normalize_text(text).encode("utf-8")).hexdigest()


def token_ngrams(text: str, n: int = 5) -> set[tuple[str, ...]]:
    tokens = _WORD_RE.findall(text.lower())
    if len(tokens) < n:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def jaccard(a: set[tuple[str, ...]], b: set[tuple[str, ...]]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def printable_noise_ratio(text: str) -> float:
    if not text:
        return 0.0
    useful = set(string.ascii_letters + string.digits + string.punctuation + string.whitespace)
    return sum(1 for ch in text if ch not in useful) / len(text)


def char_entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    n = len(text)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def has_repeated_char_run(text: str) -> bool:
    return _REPEATED_CHAR_RE.search(text) is not None


def replacement_char_count(text: str) -> int:
    return text.count("�")


def null_byte_count(text: str) -> int:
    return text.count("\x00")


def control_char_count(text: str) -> int:
    return len(_CONTROL_CHAR_RE.findall(text))


def bom_detected(text: str) -> bool:
    return text.startswith("﻿")


def mojibake_count(text: str) -> int:
    return len(_MOJIBAKE_RE.findall(text))


def starts_mid_sentence(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped:
        return False
    if re.match(r"^[a-z]", stripped) and not re.match(r"^\d+[.)]\s", stripped):
        return True
    if re.match(r"^(and|or|but|so|yet|nor|for|because|since|although|however|therefore)\s", stripped, re.I):
        return True
    return False


def ends_mid_sentence(text: str) -> bool:
    stripped = text.rstrip()
    if not stripped:
        return False
    if stripped.endswith(":"):
        return False
    return not _SENTENCE_END_RE.search(stripped)


def is_navigation_fragment(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) >= 60:
        return False
    if re.match(r"^\d+$", stripped):
        return True
    if re.match(r"^(page\s+\d+|chapter\s+\d+|\d+\s+of\s+\d+)$", stripped, re.I):
        return True
    if re.match(r"^(table of contents|contents|index|bibliography|references|appendix)$", stripped, re.I):
        return True
    return False
