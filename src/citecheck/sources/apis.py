"""Ground-truth sources: Crossref and OpenAlex (open APIs), and a fixture source for offline runs.

A source has two methods:

* ``lookup_doi(doi)``: the ``WorkRecord`` of a DOI, or ``None`` if the DOI does not exist.
* ``sample_dois(n, seed)``: a seeded sample of DOIs (OpenAlex and fixture only).
"""
from __future__ import annotations

import urllib.parse
from typing import Protocol

from ..normalize import normalize_doi
from ..records import Author, WorkRecord
from .http import JsonClient

CROSSREF_TYPES = {"journal-article": "article-journal", "proceedings-article": "paper-conference",
                  "book": "book", "monograph": "book", "edited-book": "book", "book-chapter": "chapter",
                  "report": "report"}
OPENALEX_TYPES = {"article": "article-journal", "book": "book", "book-chapter": "chapter", "report": "report"}


class Source(Protocol):
    name: str

    def lookup_doi(self, doi: str) -> WorkRecord | None:  # pragma: no cover - protocol
        ...


def parse_crossref(message: dict) -> WorkRecord:
    """Make a record from the ``message`` object of ``GET /works/{doi}``."""
    authors = tuple(Author(family=a["family"], given=a.get("given", ""))
                    for a in message.get("author", []) if a.get("family"))
    year = None
    for key in ("published-print", "published-online", "issued", "published"):
        parts = (message.get(key) or {}).get("date-parts") or [[None]]
        if parts and parts[0] and parts[0][0]:
            year = int(parts[0][0])
            break
    title = (message.get("title") or [""])[0]
    container = (message.get("container-title") or [""])[0] if message.get("container-title") else ""
    return WorkRecord(
        id=normalize_doi(message.get("DOI", "")) or title[:40],
        type=CROSSREF_TYPES.get(message.get("type", ""), "other"),
        title=title or "(no title)",
        authors=authors,
        year=year,
        container_title=container,
        volume=str(message.get("volume", "") or ""),
        issue=str(message.get("issue", "") or ""),
        pages=str(message.get("page", "") or ""),
        doi=message.get("DOI", ""),
        publisher=str(message.get("publisher", "") or ""),
    )


def _split_name(display: str) -> Author | None:
    parts = display.strip().split()
    if not parts:
        return None
    return Author(family=parts[-1], given=" ".join(parts[:-1]))


def parse_openalex(work: dict) -> WorkRecord:
    """Make a record from one OpenAlex ``Work`` object. OpenAlex gives display names, so the family name is the last word."""
    authors = tuple(a for a in (_split_name((x.get("author") or {}).get("display_name", ""))
                                for x in work.get("authorships", [])) if a)
    biblio = work.get("biblio") or {}
    first, last = biblio.get("first_page") or "", biblio.get("last_page") or ""
    pages = f"{first}-{last}" if first and last and first != last else first
    source = ((work.get("primary_location") or {}).get("source") or {})
    doi = normalize_doi(work.get("doi") or "")
    return WorkRecord(
        id=doi or str(work.get("id", "work")),
        type=OPENALEX_TYPES.get(work.get("type", ""), "other"),
        title=work.get("title") or work.get("display_name") or "(no title)",
        authors=authors,
        year=work.get("publication_year"),
        container_title=source.get("display_name") or "",
        volume=str(biblio.get("volume") or ""),
        issue=str(biblio.get("issue") or ""),
        pages=pages,
        doi=doi,
        publisher=source.get("host_organization_name") or "",
    )


class CrossrefSource:
    name = "crossref"
    base = "https://api.crossref.org"

    def __init__(self, client: JsonClient, mailto: str | None = None) -> None:
        self.client = client
        self.mailto = mailto

    def lookup_doi(self, doi: str) -> WorkRecord | None:
        url = f"{self.base}/works/{urllib.parse.quote(normalize_doi(doi), safe='/')}"
        if self.mailto:
            url += "?mailto=" + urllib.parse.quote(self.mailto)
        body = self.client.get(url)
        return None if body is None else parse_crossref(body["message"])


class OpenAlexSource:
    name = "openalex"
    base = "https://api.openalex.org"

    def __init__(self, client: JsonClient, mailto: str | None = None) -> None:
        self.client = client
        self.mailto = mailto

    def _q(self, params: dict) -> str:
        if self.mailto:
            params = {**params, "mailto": self.mailto}
        return urllib.parse.urlencode(params)

    def lookup_doi(self, doi: str) -> WorkRecord | None:
        body = self.client.get(f"{self.base}/works/doi:{normalize_doi(doi)}?{self._q({})}")
        return None if body is None else parse_openalex(body)

    def sample_dois(self, n: int, seed: int, filters: str = "type:article,has_doi:true") -> list[str]:
        """A seeded random sample. OpenAlex pages a sample with ``page``; each page is a new request."""
        dois: list[str] = []
        page = 1
        while len(dois) < n:
            per = min(200, n - len(dois)) if page == 1 else 200
            body = self.client.get(f"{self.base}/works?" + self._q({"sample": n, "seed": seed, "filter": filters,
                                                                    "per-page": per, "page": page}))
            results = (body or {}).get("results") or []
            if not results:
                break
            for w in results:
                d = normalize_doi(w.get("doi") or "")
                if d and d not in dois:
                    dois.append(d)
            page += 1
        return dois[:n]


class FixtureSource:
    """In-memory source for offline runs and tests."""

    name = "fixture"

    def __init__(self, records: list[WorkRecord]) -> None:
        self.by_doi = {r.doi: r for r in records if r.doi}

    def lookup_doi(self, doi: str) -> WorkRecord | None:
        return self.by_doi.get(normalize_doi(doi))

    def sample_dois(self, n: int, seed: int) -> list[str]:
        import numpy as np

        keys = sorted(self.by_doi)
        idx = np.random.default_rng(seed).permutation(len(keys))[:n]
        return [keys[i] for i in idx]
