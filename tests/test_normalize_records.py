import pytest
from pydantic import ValidationError

from citecheck.normalize import normalize_doi, normalize_family, normalize_pages, normalize_title, title_similarity, token_f1
from citecheck.records import WorkRecord, record_from_dict
from citecheck.synthetic import make_records


def test_titles_lose_result_tags_and_accents():
    assert normalize_title("[PDF][HTML] Deep Learning: A Révïew!") == "deep learning a review"
    assert title_similarity("[BOOK] Machine learning", "Machine Learning.") == 1.0


def test_doi_forms():
    for raw in ("https://doi.org/10.1000/ABC", "doi:10.1000/abc", "http://dx.doi.org/10.1000/abc.", "10.1000/abc"):
        assert normalize_doi(raw) == "10.1000/abc"


def test_pages_and_names():
    assert normalize_pages("123 – 9") == "123-129"
    assert normalize_pages("e1002") == "e1002"
    assert normalize_family("Müller-Lüdenscheidt") == "mullerludenscheidt"


def test_token_f1_ignores_order_and_markup():
    assert token_f1("*Nature*, 12(3)", "Nature 12 3") == 1.0
    assert token_f1("", "") == 1.0 and token_f1("a", "b") == 0.0


def test_record_validation():
    with pytest.raises(ValidationError):
        WorkRecord(id="x", title="t", doi="not-a-doi")
    with pytest.raises(ValidationError):
        WorkRecord(id="x", title="t", year=3020)
    with pytest.raises(ValidationError):
        WorkRecord(id="x", title="t", unknown="y")
    assert WorkRecord(id="x", title="t", pages="12 — 19").pages == "12-19"


def test_loose_model_output_is_cleaned():
    r = record_from_dict({"title": "T", "authors": ["Smith, Ann", {"family": "Lee", "given": "Bo"}, {"given": "x"}],
                          "year": "2019a", "doi": "https://doi.org/10.1/x", "type": "journal", "extra": 1}, "w")
    assert [a.family for a in r.authors] == ["Smith", "Lee"] and r.year == 2019
    assert r.doi == "" and r.type == "other"  # "10.1/x" has too few prefix digits
    assert record_from_dict({"year": "unknown"}, "w").year is None


def test_synthetic_records_are_unique_and_seeded():
    a, b = make_records(100, 3), make_records(100, 3)
    assert a == b
    assert len({r.title.lower() for r in a}) == 100
    assert all(r.doi.startswith("10.5555/") for r in a)
