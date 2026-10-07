import pytest

from citecheck.records import Author, WorkRecord
from citecheck.render import STYLES, initials, render, render_all

ART = WorkRecord(id="a", title="Deep learning for weather", year=2016, container_title="Journal of Tests",
                 volume="12", issue="3", pages="770-778", doi="10.5555/abc.1",
                 authors=(Author(family="He", given="Kai Ming"), Author(family="Zhang", given="Xiang"),
                          Author(family="Ren", given="Shao")))
BOOK = WorkRecord(id="b", type="book", title="Pattern methods", year=2006, publisher="Harbour Press",
                  authors=(Author(family="Bishop", given="Chris M."),))


def test_styles_are_looked_up_by_name_and_differ():
    out = render_all(ART)
    assert list(out) == ["apa", "mla", "chicago", "harvard", "vancouver"]
    assert out["apa"].startswith("He, K. M., Zhang, X., & Ren, S. (2016). Deep learning for weather.")
    assert "Journal of Tests, 12(3), 770–778. https://doi.org/10.5555/abc.1" in out["apa"]
    assert out["mla"].startswith("He, Kai Ming, et al. “Deep learning for weather.”")
    assert "vol. 12, no. 3, 2016, pp. 770-778" in out["mla"]
    assert "2016. “Deep learning for weather.” Journal of Tests 12 (3): 770–778." in out["chicago"]
    assert out["harvard"].startswith("He, K.M., Zhang, X. and Ren, S. (2016) ‘Deep learning for weather’")
    assert out["harvard"].endswith("Available at: https://doi.org/10.5555/abc.1.")
    assert out["vancouver"] == ("He KM, Zhang X, Ren S. Deep learning for weather. Journal of Tests. "
                                "2016;12(3):770-778. doi:10.5555/abc.1")
    assert len(set(out.values())) == 5


def test_books():
    out = render_all(BOOK)
    assert out["apa"] == "Bishop, C. M. (2006). Pattern methods. Harbour Press."
    assert out["mla"] == "Bishop, Chris M. Pattern methods. Harbour Press, 2006."
    assert out["vancouver"] == "Bishop CM. Pattern methods. Harbour Press; 2006."


def test_author_list_rules():
    many = ART.model_copy(update={"authors": tuple(Author(family=f"F{i}", given="Ann") for i in range(22))})
    apa = render(many, "apa")
    assert ", . . . F21, A." in apa and "F19" not in apa
    assert render(many, "vancouver").startswith("F0 A, F1 A, F2 A, F3 A, F4 A, F5 A, et al.")
    assert render(many, "harvard").startswith("F0, A. et al. (2016)")
    two = ART.model_copy(update={"authors": ART.authors[:2]})
    assert render(two, "mla").startswith("He, Kai Ming, and Xiang Zhang.")


def test_missing_year_and_unknown_style():
    r = ART.model_copy(update={"year": None})
    assert "(n.d.)" in render(r, "apa") and "(no date)" in render(r, "harvard")
    with pytest.raises(ValueError):
        render(ART, "ieee")


def test_initials():
    assert initials("Anna-Maria") == "A. M." and initials("J.R.R.", with_periods=False) == "JRR"
    assert set(STYLES) == {"apa", "mla", "chicago", "harvard", "vancouver"}
