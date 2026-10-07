import json
import re
import subprocess
from pathlib import Path

import pytest

from citecheck import cli, pipeline
from citecheck.config import settings_from_env
from citecheck.llm import ScriptedLLM, SimulatedLLM
from citecheck.report import BANNER, to_markdown
from citecheck.sources import FixtureSource
from citecheck.synthetic import make_records


@pytest.fixture
def small():
    recs = make_records(12, seed=1)
    src = FixtureSource(recs)
    return src, pipeline.build_truth([r.doi for r in recs] + ["10.5555/missing"], src, log=lambda s: None)


def test_build_truth_skips_unknown_dois(small):
    _, truth = small
    assert len(truth) == 12 and set(truth[0]["citations"]) == {"apa", "mla", "chicago", "harvard", "vancouver"}


def test_generate_is_resumable_and_records_failures(small, tmp_path):
    _, truth = small
    out = tmp_path / "gen.jsonl"

    class Flaky(ScriptedLLM):
        def complete(self, messages):
            self.calls.append(messages)
            if len(self.calls) == 2:
                raise TimeoutError("slow")
            return '{"title": "x"}'

    llm = Flaky([])
    rows = pipeline.generate(truth[:2], llm, ["title_only", "title_doi"], out, log=lambda s: None)
    assert len(rows) == 4 and sum(bool(r["error"]) for r in rows) == 1
    assert next(r for r in rows if r["error"])["raw"] == ""  # never a made-up answer
    pipeline.generate(truth[:2], llm, ["title_only", "title_doi"], out, log=lambda s: None)
    assert len(llm.calls) == 4  # nothing is sent again
    with pytest.raises(ValueError):
        pipeline.generate(truth, llm, ["bogus"], None)


def test_simulated_pipeline_end_to_end(small):
    src, truth = small
    llm = SimulatedLLM(pipeline.truth_records(truth), seed=0)
    rows = pipeline.evaluate(truth, pipeline.generate(truth, llm, log=lambda s: None), src)
    s = pipeline.summarize(rows)
    assert s["simulated"] and set(s["variants"]) == {"title_only", "title_doi", "full_metadata"}
    full, bare = s["variants"]["full_metadata"], s["variants"]["title_only"]
    assert full["fields"]["year"]["accuracy"]["mean"] >= bare["fields"]["year"]["accuracy"]["mean"]
    assert "full_metadata_vs_title_only" in s["comparisons"]
    assert BANNER in to_markdown(s)


def test_simulated_and_real_results_are_never_mixed(small):
    src, truth = small
    sim = pipeline.generate(truth[:2], SimulatedLLM(pipeline.truth_records(truth)), ["title_only"], log=lambda s: None)
    real = pipeline.generate(truth[:2], ScriptedLLM(["{}", "{}"], name="real-model"), ["title_only"], log=lambda s: None)
    with pytest.raises(ValueError):
        pipeline.summarize(pipeline.evaluate(truth, sim + real, src))
    report = to_markdown(pipeline.summarize(pipeline.evaluate(truth, real, src)))
    assert BANNER not in report


def test_read_dois_needs_column_and_dedupes(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text("doi\nhttps://doi.org/10.5555/A\n10.5555/a\n10.5555/b\n")
    assert pipeline.read_dois(p) == ["10.5555/a", "10.5555/b"]
    p.write_text("id\n1\n")
    with pytest.raises(ValueError):
        pipeline.read_dois(p)


def test_cli_offline_run(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    fixture = ["--source", "fixture", "--synthetic-n", "15"]
    assert cli.main(["sample", *fixture, "--n", "10", "--out", "dois.csv"]) == 0
    assert cli.main(["build-truth", *fixture, "--dois", "dois.csv", "--out", "truth.jsonl"]) == 0
    assert cli.main(["generate", "--truth", "truth.jsonl", "--provider", "simulated", "--out", "gen.jsonl"]) == 0
    assert cli.main(["evaluate", *fixture, "--truth", "truth.jsonl", "--generations", "gen.jsonl",
                     "--out", "eval.jsonl"]) == 0
    assert cli.main(["report", "--eval", "eval.jsonl", "--out", "report.md"]) == 0
    assert "SIMULATED" in (tmp_path / "report.md").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "report.json").read_text())["simulated"] is True
    assert cli.main(["demo", "--n", "12", "--out-dir", str(tmp_path / "demo")]) == 0


def test_openai_provider_needs_a_key(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CITECHECK_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        cli.make_llm("openai", settings_from_env())
    monkeypatch.setenv("OPENAI_API_KEY", "test-value")
    s = settings_from_env()
    assert s.llm_api_key == "test-value" and "test-value" not in repr(s)


KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|hf_[A-Za-z0-9]{25,}|gsk_[A-Za-z0-9]{20,}|"
                         r"AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}")


def test_no_api_key_is_committed():
    root = Path(__file__).resolve().parents[1]
    try:
        files = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        files = [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]
    for name in files:
        path = root / name
        if path.suffix in {".py", ".md", ".toml", ".yml", ".txt", ".json", ".csv", ".example", ""} and path.is_file():
            assert not KEY_PATTERN.search(path.read_text(encoding="utf-8", errors="ignore")), name
