import numpy as np
import pytest

from citecheck.metrics import existence, field_statuses, format_scores
from citecheck.parse import first_json_object, parse_answer
from citecheck.records import Author, WorkRecord
from citecheck.render import render_all
from citecheck.sources import FixtureSource
from citecheck.stats import bootstrap_ci, mcnemar, paired_bootstrap

TRUTH = WorkRecord(id="t", title="Learning to cite", year=2021, container_title="Journal of Tests", volume="4",
                   issue="", pages="10-20", doi="10.5555/t.1", authors=(Author(family="Silva", given="Ana"),))
OTHER = WorkRecord(id="o", title="Another paper entirely", year=2001, doi="10.5555/o.1")


def test_first_json_object_ignores_fences_and_braces_in_strings():
    raw = 'Here:\n```json\n{"title": "A {b} c", "x": {"y": 1}}\n```\nDone {not json}'
    assert first_json_object(raw) == '{"title": "A {b} c", "x": {"y": 1}}'
    assert first_json_object("no object") is None


def test_parse_answer_errors_and_success():
    assert not parse_answer("nothing", "w").ok
    assert "invalid JSON" in parse_answer("{'a': 1}", "w").error
    p = parse_answer('{"title": "T", "year": 2020, "citations": {"APA": "x", "ieee": "y", "mla": ""}}', "w")
    assert p.ok and p.record.year == 2020 and p.citations == {"apa": "x"}


def test_field_statuses_separate_wrong_from_missing():
    pred = TRUTH.model_copy(update={"year": 2019, "volume": "", "pages": "10–20", "doi": "10.5555/T.1"})
    s = field_statuses(pred, TRUTH)
    assert s["year"] == "wrong" and s["volume"] == "missing" and s["issue"] == "n/a"
    assert s["pages"] == "correct" and s["doi"] == "correct" and s["authors"] == "correct"
    assert set(field_statuses(None, TRUTH).values()) <= {"missing", "n/a"}


def test_existence_categories():
    src = FixtureSource([TRUTH, OTHER])
    assert existence(None, TRUTH, src) == "no_doi"
    assert existence(TRUTH, TRUTH, src) == "same_work"
    assert existence(TRUTH.model_copy(update={"doi": "10.5555/o.1"}), TRUTH, src) == "other_work"
    assert existence(TRUTH.model_copy(update={"doi": "10.9999/fake"}), TRUTH, src) == "not_found"


def test_format_scores():
    truth = render_all(TRUTH)
    out = format_scores({"apa": truth["apa"].upper(), "mla": truth["mla"].replace("“", "")}, truth)
    assert out["apa"]["exact"] == 1.0  # case does not count
    assert out["mla"]["exact"] == 0.0 and out["mla"]["token_f1"] == 1.0  # punctuation counts for exact only
    assert out["vancouver"]["present"] == 0.0 and out["vancouver"]["token_f1"] == 0.0


def test_stats():
    ci = bootstrap_ci(np.r_[np.ones(80), np.zeros(20)])
    assert ci["mean"] == 0.8 and ci["ci_low"] < 0.8 < ci["ci_high"]
    assert np.isnan(bootstrap_ci([])["mean"])
    m = mcnemar([1, 1, 1, 0, 1], [0, 0, 1, 0, 1])
    assert (m["only_a"], m["only_b"]) == (2, 0) and 0 < m["p_value"] <= 1
    assert mcnemar([1, 0], [1, 0])["p_value"] == 1.0
    with pytest.raises(ValueError):
        paired_bootstrap([1, 2], [1])
