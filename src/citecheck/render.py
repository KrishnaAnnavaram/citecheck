"""Reference strings for five styles, made from a ``WorkRecord`` by fixed rules.

The styles are looked up by name in ``STYLES``. Nothing maps a style to a
row position, so two styles can never change places.

The rules cover journal articles, conference papers, chapters, reports and
books. They follow the main pattern of each style guide. They are a
simplified, documented version, not a full CSL processor:

* ``apa``       APA 7th edition reference list
* ``mla``       MLA 9th edition works cited
* ``chicago``   Chicago 17th edition, author-date reference list
* ``harvard``   Harvard (Cite Them Right pattern)
* ``vancouver`` Vancouver (ICMJE / NLM pattern)
"""
from __future__ import annotations

from typing import Callable

from .records import Author, WorkRecord

EN_DASH = "–"


def initials(given: str, with_periods: bool = True, spaced: bool = True) -> str:
    parts = [p for p in given.replace("-", " ").replace(".", " ").split() if p]
    if with_periods:
        return (" " if spaced else "").join(f"{p[0].upper()}." for p in parts)
    return "".join(p[0].upper() for p in parts)


def _pages(pages: str, dash: str = EN_DASH) -> str:
    return pages.replace("-", dash)


def _doi_url(doi: str) -> str:
    return f"https://doi.org/{doi}" if doi else ""


def _end(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "?", "!")) else text + "."


# APA 7 -----------------------------------------------------------------
def _apa_name(a: Author) -> str:
    ini = initials(a.given)
    return f"{a.family}, {ini}" if ini else a.family


def _apa_authors(authors: tuple[Author, ...]) -> str:
    names = [_apa_name(a) for a in authors]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) > 20:
        return ", ".join(names[:19]) + ", . . . " + names[-1]
    return ", ".join(names[:-1]) + ", & " + names[-1]


def apa(r: WorkRecord) -> str:
    year = f"({r.year})" if r.year else "(n.d.)"
    head = f"{_apa_authors(r.authors)} {year}." if r.authors else f"{_end(r.title)} {year}."
    title = "" if not r.authors else " " + _end(r.title)
    if r.type == "book":
        body = f"{head}{title} {r.publisher}." if r.publisher else f"{head}{title}"
    else:
        src = r.container_title
        if r.volume:
            src += f", {r.volume}"
            if r.issue:
                src += f"({r.issue})"
        if r.pages:
            src += f", {_pages(r.pages)}"
        body = f"{head}{title} {src}." if src else f"{head}{title}"
    doi = _doi_url(r.doi)
    return f"{body} {doi}".strip()


# MLA 9 -----------------------------------------------------------------
def _mla_authors(authors: tuple[Author, ...]) -> str:
    if not authors:
        return ""
    first = f"{authors[0].family}, {authors[0].given}".rstrip(", ")
    if len(authors) == 1:
        return first
    if len(authors) == 2:
        second = f"{authors[1].given} {authors[1].family}".strip()
        return f"{first}, and {second}"
    return f"{first}, et al"


def mla(r: WorkRecord) -> str:
    parts = []
    if r.authors:
        parts.append(_end(_mla_authors(r.authors)))
    if r.type == "book":
        parts.append(_end(r.title))
        tail = ", ".join(x for x in [r.publisher, str(r.year or "")] if x)
    else:
        t = _end(r.title)
        parts.append(f"“{t}”")
        bits = [r.container_title] if r.container_title else []
        if r.volume:
            bits.append(f"vol. {r.volume}")
        if r.issue:
            bits.append(f"no. {r.issue}")
        if r.year:
            bits.append(str(r.year))
        if r.pages:
            bits.append(("pp. " if "-" in r.pages else "p. ") + _pages(r.pages, "-"))
        tail = ", ".join(bits)
    if r.doi:
        tail = f"{tail}, {_doi_url(r.doi)}" if tail else _doi_url(r.doi)
    if tail:
        parts.append(_end(tail))
    return " ".join(parts)


# Chicago author-date ----------------------------------------------------
def _chicago_authors(authors: tuple[Author, ...]) -> str:
    if not authors:
        return ""
    names = [f"{authors[0].family}, {authors[0].given}".rstrip(", ")]
    names += [f"{a.given} {a.family}".strip() for a in authors[1:]]
    if len(names) > 10:
        names = names[:7] + ["et al"]
        return ", ".join(names)
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]}, and {names[1]}"
    return ", ".join(names[:-1]) + ", and " + names[-1]


def chicago(r: WorkRecord) -> str:
    year = str(r.year) if r.year else "n.d."
    head = f"{_end(_chicago_authors(r.authors))} {year}." if r.authors else f"{year}."
    if r.type == "book":
        body = f"{head} {_end(r.title)}"
        if r.publisher:
            body += f" {r.publisher}."
    else:
        body = f"{head} “{_end(r.title)}”"
        src = r.container_title
        if r.volume:
            src += f" {r.volume}"
            if r.issue:
                src += f" ({r.issue})"
        if r.pages:
            src += f": {_pages(r.pages)}"
        if src:
            body += f" {_end(src)}"
    if r.doi:
        body += f" {_doi_url(r.doi)}."
    return body


# Harvard ---------------------------------------------------------------
def _harvard_name(a: Author) -> str:
    ini = initials(a.given, spaced=False)
    return f"{a.family}, {ini}" if ini else a.family


def _harvard_authors(authors: tuple[Author, ...]) -> str:
    names = [_harvard_name(a) for a in authors]
    if not names:
        return ""
    if len(names) > 3:
        return f"{names[0]} et al."
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def harvard(r: WorkRecord) -> str:
    year = f"({r.year})" if r.year else "(no date)"
    who = _harvard_authors(r.authors)
    head = f"{who} {year}" if who else year
    if r.type == "book":
        body = f"{head} {r.title}."
        if r.publisher:
            body += f" {r.publisher}."
    else:
        body = f"{head} ‘{r.title}’"
        bits = [r.container_title] if r.container_title else []
        vol = r.volume + (f"({r.issue})" if r.issue and r.volume else "")
        if vol:
            bits.append(vol)
        if r.pages:
            bits.append(("pp. " if "-" in r.pages else "p. ") + _pages(r.pages))
        body = f"{body}, {', '.join(bits)}." if bits else f"{body}."
    if r.doi:
        body += f" Available at: {_doi_url(r.doi)}."
    return body


# Vancouver -------------------------------------------------------------
def _vancouver_authors(authors: tuple[Author, ...]) -> str:
    names = [f"{a.family} {initials(a.given, with_periods=False)}".strip() for a in authors]
    if len(names) > 6:
        return ", ".join(names[:6]) + ", et al"
    return ", ".join(names)


def vancouver(r: WorkRecord) -> str:
    parts = []
    if r.authors:
        parts.append(_end(_vancouver_authors(r.authors)))
    parts.append(_end(r.title))
    if r.type == "book":
        tail = "; ".join(x for x in [r.publisher, str(r.year or "")] if x)
        if tail:
            parts.append(_end(tail))
    else:
        if r.container_title:
            parts.append(_end(r.container_title))
        loc = str(r.year or "")
        if r.volume:
            loc += f";{r.volume}"
            if r.issue:
                loc += f"({r.issue})"
        if r.pages:
            loc += f":{r.pages}"
        if loc:
            parts.append(_end(loc))
    if r.doi:
        parts.append(f"doi:{r.doi}")
    return " ".join(parts)


STYLES: dict[str, Callable[[WorkRecord], str]] = {
    "apa": apa,
    "mla": mla,
    "chicago": chicago,
    "harvard": harvard,
    "vancouver": vancouver,
}


def render(record: WorkRecord, style: str) -> str:
    try:
        return STYLES[style](record)
    except KeyError as exc:
        raise ValueError(f"unknown style {style!r}; use one of {sorted(STYLES)}") from exc


def render_all(record: WorkRecord) -> dict[str, str]:
    return {name: fn(record) for name, fn in STYLES.items()}
