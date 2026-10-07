"""Field-level, existence and format metrics for one work.

Each field gets one status:

* ``correct``: the model gives the true value (after normalisation)
* ``wrong``:   the model gives a value, and the value is false (a hallucination)
* ``missing``: the model gives no value although the truth has one
* ``n/a``:     the truth has no value, so the field does not count
"""
from __future__ import annotations

from .normalize import fold, normalize_doi, normalize_family, normalize_pages, title_similarity, token_f1
from .records import FIELDS, WorkRecord
from .render import STYLES
from .sources import Source

TITLE_MATCH = 0.9


def _status(pred_value, truth_value, same) -> str:
    if truth_value in (None, "", ()):
        return "n/a"
    if pred_value in (None, "", ()):
        return "missing"
    return "correct" if same(pred_value, truth_value) else "wrong"


def author_scores(pred: WorkRecord, truth: WorkRecord) -> dict[str, float]:
    p = [normalize_family(a.family) for a in pred.authors]
    t = [normalize_family(a.family) for a in truth.authors]
    if not t:
        return {"author_precision": 1.0, "author_recall": 1.0, "author_f1": 1.0, "first_author_correct": 1.0}
    common = len(set(p) & set(t))
    prec = common / len(p) if p else 0.0
    rec = common / len(t)
    f1 = 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec)
    return {"author_precision": prec, "author_recall": rec, "author_f1": f1,
            "first_author_correct": float(bool(p) and p[0] == t[0])}


def field_statuses(pred: WorkRecord | None, truth: WorkRecord) -> dict[str, str]:
    if pred is None:
        return {f: ("n/a" if getattr(truth, f) in (None, "", ()) else "missing") for f in FIELDS}
    fam = lambda r: [normalize_family(a.family) for a in r.authors]  # noqa: E731
    return {
        "authors": _status(fam(pred) or None, fam(truth) or None, lambda a, b: a == b),
        "year": _status(pred.year, truth.year, lambda a, b: a == b),
        "title": _status(pred.title if pred.title != "(no title)" else "", truth.title,
                         lambda a, b: title_similarity(a, b) >= TITLE_MATCH),
        "container_title": _status(pred.container_title, truth.container_title,
                                   lambda a, b: fold(a) == fold(b) or token_f1(a, b) >= TITLE_MATCH),
        "volume": _status(pred.volume, truth.volume, lambda a, b: fold(a) == fold(b)),
        "issue": _status(pred.issue, truth.issue, lambda a, b: fold(a) == fold(b)),
        "pages": _status(pred.pages, truth.pages, lambda a, b: normalize_pages(a) == normalize_pages(b)),
        "doi": _status(pred.doi, truth.doi, lambda a, b: normalize_doi(a) == normalize_doi(b)),
    }


def existence(pred: WorkRecord | None, truth: WorkRecord, source: Source) -> str:
    """What the predicted DOI points to: ``no_doi``, ``same_work``, ``other_work`` or ``not_found``."""
    if pred is None or not pred.doi:
        return "no_doi"
    if normalize_doi(pred.doi) == normalize_doi(truth.doi):
        return "same_work"
    found = source.lookup_doi(pred.doi)
    if found is None:
        return "not_found"
    return "same_work" if title_similarity(found.title, truth.title) >= TITLE_MATCH else "other_work"


def canonical(text: str) -> str:
    """Fold case, quotes, dashes and spaces. Keeps punctuation, because punctuation is part of a style."""
    return fold(text).replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")


def format_scores(pred_cites: dict[str, str], truth_cites: dict[str, str]) -> dict[str, dict[str, float]]:
    out = {}
    for style in STYLES:
        p, t = pred_cites.get(style, ""), truth_cites[style]
        out[style] = {"exact": float(bool(p) and canonical(p) == canonical(t)), "token_f1": token_f1(p, t),
                      "present": float(bool(p))}
    return out
