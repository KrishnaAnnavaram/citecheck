"""The work record: a small subset of CSL-JSON with schema validation."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

WORK_TYPES = ("article-journal", "paper-conference", "book", "chapter", "report", "other")
FIELDS = ("authors", "year", "title", "container_title", "volume", "issue", "pages", "doi")


class Author(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    family: str = Field(min_length=1)
    given: str = ""


class WorkRecord(BaseModel):
    """Bibliographic facts of one work. Every field except ``title`` can be empty."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1)
    type: Literal["article-journal", "paper-conference", "book", "chapter", "report", "other"] = "article-journal"
    title: str = Field(min_length=1)
    authors: tuple[Author, ...] = ()
    year: int | None = Field(default=None, ge=1000, le=2100)
    container_title: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    doi: str = ""
    publisher: str = ""
    url: str = ""

    @field_validator("doi")
    @classmethod
    def _doi(cls, v: str) -> str:
        from .normalize import normalize_doi

        v = normalize_doi(v)
        if v and not re.match(r"^10\.\d{4,9}/\S+$", v):
            raise ValueError(f"not a DOI: {v!r}")
        return v

    @field_validator("pages")
    @classmethod
    def _pages(cls, v: str) -> str:
        return re.sub(r"\s*[-‐-―]+\s*", "-", v.strip())


def record_from_dict(data: dict, default_id: str = "work") -> WorkRecord:
    """Build a record from loose input (for example model output). Unknown keys are dropped."""
    authors = []
    for a in data.get("authors") or []:
        if isinstance(a, dict) and str(a.get("family", "")).strip():
            authors.append(Author(family=str(a["family"]).strip(), given=str(a.get("given", "") or "").strip()))
        elif isinstance(a, str) and a.strip():
            parts = [p.strip() for p in a.split(",", 1)]
            authors.append(Author(family=parts[0], given=parts[1] if len(parts) > 1 else ""))
    year = data.get("year")
    try:
        year = int(str(year)[:4]) if year not in (None, "") else None
        if year is not None and not (1000 <= year <= 2100):
            year = None
    except ValueError:
        year = None
    doi = str(data.get("doi") or "")
    from .normalize import normalize_doi

    doi = normalize_doi(doi)
    if doi and not re.match(r"^10\.\d{4,9}/\S+$", doi):
        doi = ""
    wtype = data.get("type") if data.get("type") in WORK_TYPES else "other"
    return WorkRecord(
        id=str(data.get("id") or default_id),
        type=wtype,
        title=str(data.get("title") or "").strip() or "(no title)",
        authors=tuple(authors),
        year=year,
        container_title=str(data.get("container_title") or "").strip(),
        volume=str(data.get("volume") or "").strip(),
        issue=str(data.get("issue") or "").strip(),
        pages=str(data.get("pages") or "").strip(),
        doi=doi,
        publisher=str(data.get("publisher") or "").strip(),
    )
