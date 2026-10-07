"""The four stages: build the truth set, generate, evaluate and summarise.

Every stage reads and writes JSON Lines files, so each stage can run again
alone. Generation is resumable: a (work, variant, model) triple that is in the
output file already is not sent to the model again.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np

from .llm import LLM
from .metrics import author_scores, existence, field_statuses, format_scores
from .normalize import normalize_doi
from .parse import parse_answer
from .prompts import VARIANTS, messages
from .records import FIELDS, WorkRecord
from .render import STYLES, render_all
from .sources import Source
from .stats import bootstrap_ci, mcnemar, paired_bootstrap


def read_jsonl(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: str | Path, rows: Iterable[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_dois(path: str | Path) -> list[str]:
    """Read the ``doi`` column of a CSV file. Duplicates are removed, and the order stays."""
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if "doi" not in (reader.fieldnames or []):
            raise ValueError(f"{path} needs a 'doi' column")
        seen, out = set(), []
        for row in reader:
            d = normalize_doi(row["doi"])
            if d and d not in seen:
                seen.add(d)
                out.append(d)
    return out


# 1. truth ---------------------------------------------------------------
def build_truth(dois: Sequence[str], source: Source, log: Callable[[str], None] = print) -> list[dict]:
    rows = []
    for doi in dois:
        rec = source.lookup_doi(doi)
        if rec is None:
            log(f"skip {doi}: not found in {source.name}")
            continue
        if not rec.authors or not rec.year:
            log(f"skip {doi}: no authors or no year in {source.name}")
            continue
        rows.append({"source": source.name, "record": rec.model_dump(mode="json"), "citations": render_all(rec)})
    return rows


def truth_records(truth_rows: list[dict]) -> list[WorkRecord]:
    return [WorkRecord.model_validate(r["record"]) for r in truth_rows]


# 2. generate ------------------------------------------------------------
def generate(truth_rows: list[dict], llm: LLM, variants: Sequence[str] = VARIANTS, out_path: str | Path | None = None,
             log: Callable[[str], None] = print) -> list[dict]:
    for v in variants:
        if v not in VARIANTS:
            raise ValueError(f"unknown variant {v!r}")
    done = {(r["work_id"], r["variant"], r["model"]) for r in read_jsonl(out_path)} if out_path else set()
    new = []
    for rec in truth_records(truth_rows):
        for v in variants:
            key = (rec.id, v, llm.name)
            if key in done:
                continue
            try:
                raw, err = llm.complete(messages(rec, v)), ""
            except Exception as exc:  # a failed call is recorded, never replaced by a made-up answer
                raw, err = "", f"{type(exc).__name__}: {exc}"
            row = {"work_id": rec.id, "variant": v, "model": llm.name, "simulated": llm.simulated, "raw": raw,
                   "error": err}
            new.append(row)
            if out_path:
                append_jsonl(out_path, [row])
    log(f"generated {len(new)} new answers with {llm.name}")
    return read_jsonl(out_path) if out_path else new


# 3. evaluate ------------------------------------------------------------
def evaluate(truth_rows: list[dict], generations: list[dict], source: Source) -> list[dict]:
    truth = {r["record"]["id"]: r for r in truth_rows}
    rows = []
    for g in generations:
        t = truth.get(g["work_id"])
        if t is None:
            continue
        trec = WorkRecord.model_validate(t["record"])
        parsed = parse_answer(g["raw"], g["work_id"]) if not g.get("error") else None
        pred = parsed.record if parsed and parsed.ok else None
        row = {
            "work_id": g["work_id"], "variant": g["variant"], "model": g["model"], "simulated": g["simulated"],
            "parse_ok": bool(parsed and parsed.ok), "call_error": g.get("error", ""),
            "fields": field_statuses(pred, trec),
            "existence": existence(pred, trec, source),
            "formats": format_scores(parsed.citations if parsed and parsed.ok else {}, t["citations"]),
        }
        row.update(author_scores(pred, trec) if pred else
                   {"author_precision": 0.0, "author_recall": 0.0, "author_f1": 0.0, "first_author_correct": 0.0})
        rows.append(row)
    return rows


# 4. summarise -----------------------------------------------------------
EXISTENCE = ("same_work", "other_work", "not_found", "no_doi")


def _rate(rows: list[dict], field: str, status: str) -> dict:
    applicable = [r for r in rows if r["fields"][field] != "n/a"]
    return bootstrap_ci([r["fields"][field] == status for r in applicable])


def summarize(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("no evaluation rows")
    models = sorted({r["model"] for r in rows})
    sims = {r["simulated"] for r in rows}
    if len(sims) > 1:
        raise ValueError("simulated and real results are in one file; evaluate them apart")
    out: dict = {"models": models, "simulated": sims.pop(), "variants": {}, "comparisons": {}}
    by_variant = {v: [r for r in rows if r["variant"] == v] for v in VARIANTS if any(r["variant"] == v for r in rows)}
    for v, vrows in by_variant.items():
        out["variants"][v] = {
            "works": len(vrows),
            "parse_ok": bootstrap_ci([r["parse_ok"] for r in vrows]),
            "fields": {f: {"accuracy": _rate(vrows, f, "correct"), "hallucination": _rate(vrows, f, "wrong"),
                           "omission": _rate(vrows, f, "missing")} for f in FIELDS},
            "author_f1": bootstrap_ci([r["author_f1"] for r in vrows]),
            "first_author_correct": bootstrap_ci([r["first_author_correct"] for r in vrows]),
            "existence": {e: float(np.mean([r["existence"] == e for r in vrows])) for e in EXISTENCE},
            "styles": {s: {"exact": bootstrap_ci([r["formats"][s]["exact"] for r in vrows]),
                           "token_f1": bootstrap_ci([r["formats"][s]["token_f1"] for r in vrows])} for s in STYLES},
        }
    base = "title_only"
    if base in by_variant:
        bmap = {(r["work_id"], r["model"]): r for r in by_variant[base]}
        for v, vrows in by_variant.items():
            if v == base:
                continue
            pairs = [(r, bmap[(r["work_id"], r["model"])]) for r in vrows if (r["work_id"], r["model"]) in bmap]
            comp = {}
            for f in FIELDS:
                ok = [(a, b) for a, b in pairs if a["fields"][f] != "n/a"]
                comp[f] = mcnemar([a["fields"][f] == "correct" for a, _ in ok], [b["fields"][f] == "correct" for _, b in ok])
                comp[f]["accuracy_diff"] = paired_bootstrap([a["fields"][f] == "correct" for a, _ in ok],
                                                            [b["fields"][f] == "correct" for _, b in ok])
            comp["apa_token_f1_diff"] = paired_bootstrap([a["formats"]["apa"]["token_f1"] for a, _ in pairs],
                                                         [b["formats"]["apa"]["token_f1"] for _, b in pairs])
            out["comparisons"][f"{v}_vs_{base}"] = comp
    return out
