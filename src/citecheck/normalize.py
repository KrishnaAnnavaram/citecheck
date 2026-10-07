"""Normalisation used for joins and comparisons."""
from __future__ import annotations

import re
import unicodedata

SCHOLAR_TAGS = re.compile(r"^\s*(\[(?:pdf|html|book|b|citation|c|doc)\]\s*)+", re.I)


def fold(text: str) -> str:
    """NFKC, case fold, straight quotes, single spaces."""
    t = unicodedata.normalize("NFKC", text or "")
    t = t.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    t = re.sub(r"[‐-―]", "-", t)
    return re.sub(r"\s+", " ", t).strip().casefold()


def normalize_title(title: str) -> str:
    """Remove result tags such as ``[PDF]``, accents and punctuation, then fold."""
    t = SCHOLAR_TAGS.sub("", title or "")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = fold(t)
    return " ".join(re.sub(r"[^\w\s]", " ", t).split())


def normalize_doi(doi: str) -> str:
    d = (doi or "").strip()
    d = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", d, flags=re.I)
    d = re.sub(r"^doi:\s*", "", d, flags=re.I)
    return d.rstrip(".").lower()


def normalize_family(name: str) -> str:
    n = unicodedata.normalize("NFKD", name or "")
    n = "".join(ch for ch in n if not unicodedata.combining(ch))
    return re.sub(r"[^a-z]", "", n.casefold())


def normalize_pages(pages: str) -> str:
    p = re.sub(r"\s*[-‐-―]+\s*", "-", (pages or "").strip())
    m = re.match(r"^(\d+)-(\d+)$", p)
    if m and len(m.group(2)) < len(m.group(1)):  # "123-9" -> "123-129"
        start, end = m.group(1), m.group(2)
        p = f"{start}-{start[: len(start) - len(end)]}{end}"
    return p.lower()


def tokens(text: str) -> list[str]:
    return re.findall(r"\w+", fold(text))


def token_f1(pred: str, truth: str) -> float:
    """F1 of the multiset of word tokens. Order, punctuation and markup do not count."""
    from collections import Counter

    p, t = Counter(tokens(pred)), Counter(tokens(truth))
    if not p and not t:
        return 1.0
    common = sum((p & t).values())
    if common == 0:
        return 0.0
    prec, rec = common / sum(p.values()), common / sum(t.values())
    return 2 * prec * rec / (prec + rec)


def title_similarity(a: str, b: str) -> float:
    return token_f1(normalize_title(a), normalize_title(b))
