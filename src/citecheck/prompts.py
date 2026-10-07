"""Prompt variants. Each variant gives the model a different amount of metadata.

The model must answer with one JSON object: the bibliographic fields and one
reference string for each of the five styles.
"""
from __future__ import annotations

from .records import WorkRecord
from .render import STYLES

VARIANTS = ("title_only", "title_doi", "full_metadata")

SYSTEM = (
    "You are a reference formatter. Answer with one JSON object and nothing else. Keys: "
    '"authors" (list of {"family", "given"}), "year" (integer or null), "title", "container_title", '
    '"volume", "issue", "pages", "doi", "type", and "citations" (an object with the keys '
    + ", ".join(f'"{s}"' for s in STYLES)
    + "). Use the empty string or null for a fact that you do not know. Do not invent facts."
)

STYLE_NAMES = {"apa": "APA 7th edition", "mla": "MLA 9th edition", "chicago": "Chicago 17th edition author-date",
               "harvard": "Harvard (Cite Them Right)", "vancouver": "Vancouver (NLM)"}


def user_prompt(record: WorkRecord, variant: str) -> str:
    if variant not in VARIANTS:
        raise ValueError(f"unknown prompt variant {variant!r}; use one of {VARIANTS}")
    lines = [f"Title: {record.title}"]
    if variant in ("title_doi", "full_metadata") and record.doi:
        lines.append(f"DOI: {record.doi}")
    if variant == "full_metadata":
        if record.authors:
            lines.append("Authors: " + "; ".join(f"{a.family}, {a.given}".strip(", ") for a in record.authors))
        for label, value in (("Year", record.year), ("Type", record.type), ("Container", record.container_title),
                             ("Volume", record.volume), ("Issue", record.issue), ("Pages", record.pages),
                             ("Publisher", record.publisher)):
            if value:
                lines.append(f"{label}: {value}")
    styles = ", ".join(STYLE_NAMES[s] for s in STYLES)
    return "Give the bibliographic facts and the reference in these styles: " + styles + ".\n" + "\n".join(lines)


def messages(record: WorkRecord, variant: str) -> list[dict[str, str]]:
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_prompt(record, variant)}]
