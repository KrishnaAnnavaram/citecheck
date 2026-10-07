import json
from urllib.parse import parse_qs, urlparse

import pytest

from citecheck.sources import CrossrefSource, HTTPError, JsonClient, OpenAlexSource, parse_crossref, parse_openalex

CROSSREF_MESSAGE = {
    "DOI": "10.5555/XYZ.9", "type": "journal-article", "title": ["Learning to cite"],
    "author": [{"given": "Ana", "family": "Silva"}, {"given": "Bo", "family": "Lee"}, {"name": "A Consortium"}],
    "container-title": ["Journal of Tests"], "volume": "4", "issue": "2", "page": "10-20",
    "published-print": {"date-parts": [[2021, 5]]}, "publisher": "Test Press",
}
OPENALEX_WORK = {
    "id": "https://openalex.org/W1", "doi": "https://doi.org/10.5555/xyz.9", "title": "Learning to cite",
    "type": "article", "publication_year": 2021,
    "authorships": [{"author": {"display_name": "Ana Silva"}}, {"author": {"display_name": "Bo Lee"}}],
    "biblio": {"volume": "4", "issue": "2", "first_page": "10", "last_page": "20"},
    "primary_location": {"source": {"display_name": "Journal of Tests", "host_organization_name": "Test Press"}},
}


def test_crossref_and_openalex_give_the_same_record():
    a, b = parse_crossref(CROSSREF_MESSAGE), parse_openalex(OPENALEX_WORK)
    for r in (a, b):
        assert r.doi == "10.5555/xyz.9" and r.year == 2021 and r.pages == "10-20"
        assert [x.family for x in r.authors] == ["Silva", "Lee"] and r.container_title == "Journal of Tests"
        assert r.type == "article-journal"


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def __call__(self, url, headers, timeout):
        self.urls.append(url)
        assert "citecheck" in headers["User-Agent"]
        return self.responses.pop(0)


def test_client_caches_retries_and_raises(tmp_path):
    t = FakeTransport([(429, b""), (200, json.dumps({"message": CROSSREF_MESSAGE}).encode())])
    sleeps = []
    c = JsonClient(tmp_path, min_interval_s=0, transport=t, sleep=sleeps.append)
    src = CrossrefSource(c, mailto="me@example.org")
    assert src.lookup_doi("10.5555/xyz.9").title == "Learning to cite"
    assert sleeps == [1.0] and "mailto=me%40example.org" in t.urls[0]
    assert src.lookup_doi("10.5555/xyz.9").title == "Learning to cite"  # from the cache
    assert c.network_calls == 2
    c404 = JsonClient(None, min_interval_s=0, transport=FakeTransport([(404, b"")]), sleep=lambda s: None)
    assert CrossrefSource(c404).lookup_doi("10.5555/none") is None
    bad = JsonClient(None, min_interval_s=0, retries=1, transport=FakeTransport([(503, b""), (503, b"")]),
                     sleep=lambda s: None)
    with pytest.raises(HTTPError):
        CrossrefSource(bad).lookup_doi("10.5555/x")


def test_openalex_sample_requests_each_page_once_and_dedupes():
    page1 = {"results": [{"doi": f"https://doi.org/10.5555/{i}"} for i in range(200)]}
    page2 = {"results": [{"doi": "https://doi.org/10.5555/0"}] + [{"doi": f"https://doi.org/10.5555/{i}"}
                                                                   for i in range(200, 260)]}
    t = FakeTransport([(200, json.dumps(page1).encode()), (200, json.dumps(page2).encode())])
    src = OpenAlexSource(JsonClient(None, min_interval_s=0, transport=t, sleep=lambda s: None))
    dois = src.sample_dois(250, seed=7)
    assert len(dois) == 250 and len(set(dois)) == 250
    pages = [parse_qs(urlparse(u).query)["page"][0] for u in t.urls]
    assert pages == ["1", "2"]
    assert all(parse_qs(urlparse(u).query)["seed"] == ["7"] for u in t.urls)
