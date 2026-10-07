"""Command line interface: ``citecheck <command> ...``."""
from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path

from . import pipeline
from .config import Settings, load_dotenv, settings_from_env
from .llm import OpenAICompatibleLLM, SimulatedLLM
from .prompts import VARIANTS
from .render import STYLES, render
from .report import to_markdown
from .sources import CrossrefSource, FixtureSource, JsonClient, OpenAlexSource
from .synthetic import make_records


def make_source(name: str, s: Settings, synthetic_n: int = 60, synthetic_seed: int = 0):
    if name == "fixture":
        return FixtureSource(make_records(synthetic_n, synthetic_seed))
    client = JsonClient(cache_dir=s.cache_dir / name, min_interval_s=s.min_interval_s,
                        user_agent=f"citecheck/0.1 (mailto:{s.contact_email})" if s.contact_email else "citecheck/0.1")
    if name == "crossref":
        return CrossrefSource(client, s.contact_email)
    if name == "openalex":
        return OpenAlexSource(client, s.contact_email)
    raise ValueError(f"unknown source {name!r}")


def make_llm(provider: str, s: Settings, catalogue=None, seed: int = 0):
    if provider == "simulated":
        if catalogue is None:
            raise ValueError("the simulated model needs the truth records")
        return SimulatedLLM(catalogue, seed)
    if provider == "openai":
        if not s.llm_api_key and s.llm_base_url.startswith("https://"):
            sys.exit("set CITECHECK_LLM_API_KEY (or OPENAI_API_KEY) in the environment or in .env")
        return OpenAICompatibleLLM(s.llm_base_url, s.llm_model, s.llm_api_key, s.llm_timeout_s)
    raise ValueError(f"unknown provider {provider!r}; use 'simulated' or 'openai'")


def _write_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {path}")


def _write_jsonl(rows, path: Path) -> None:
    if path.exists():
        path.unlink()
    pipeline.append_jsonl(path, rows)
    print(f"wrote {path} ({len(rows)} rows)")


def cmd_sample(a) -> None:
    s = settings_from_env()
    src = make_source(a.source, s, a.synthetic_n, a.synthetic_seed)
    if not hasattr(src, "sample_dois"):
        sys.exit(f"source {a.source} cannot sample; use openalex or fixture")
    dois = src.sample_dois(a.n, a.seed)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["doi"])
        w.writerows([d] for d in dois)
    print(f"wrote {out} ({len(dois)} DOIs)")


def cmd_build_truth(a) -> None:
    s = settings_from_env()
    src = make_source(a.source, s, a.synthetic_n, a.synthetic_seed)
    rows = pipeline.build_truth(pipeline.read_dois(a.dois), src)
    _write_jsonl(rows, Path(a.out))


def cmd_generate(a) -> None:
    s = settings_from_env()
    truth = pipeline.read_jsonl(a.truth)
    llm = make_llm(a.provider or s.llm_provider, s, pipeline.truth_records(truth), a.seed)
    pipeline.generate(truth, llm, a.variants, a.out)


def cmd_evaluate(a) -> None:
    s = settings_from_env()
    truth = pipeline.read_jsonl(a.truth)
    rows = pipeline.evaluate(truth, pipeline.read_jsonl(a.generations),
                             make_source(a.source, s, a.synthetic_n, a.synthetic_seed))
    _write_jsonl(rows, Path(a.out))


def cmd_report(a) -> None:
    summary = pipeline.summarize(pipeline.read_jsonl(a.eval))
    out = Path(a.out)
    _write_json(summary, out.with_suffix(".json"))
    out.write_text(to_markdown(summary), encoding="utf-8")
    print(f"wrote {out}")


def cmd_render(a) -> None:
    s = settings_from_env()
    rec = make_source(a.source, s).lookup_doi(a.doi)
    if rec is None:
        sys.exit(f"{a.doi} not found in {a.source}")
    for style in (a.style,) if a.style else STYLES:
        print(f"{style:10s} {render(rec, style)}")


def cmd_demo(a) -> None:
    """Offline demo: synthetic records, the fixture source and the simulated model."""
    s = settings_from_env()
    work = Path(a.out_dir) if a.out_dir else Path(tempfile.mkdtemp(prefix="citecheck_demo_"))
    src = make_source("fixture", s, a.n, a.seed)
    truth = pipeline.build_truth(src.sample_dois(a.n, a.seed), src)
    llm = SimulatedLLM(pipeline.truth_records(truth), a.seed)
    gens = pipeline.generate(truth, llm, VARIANTS, work / "generations.jsonl")
    rows = pipeline.evaluate(truth, gens, src)
    summary = pipeline.summarize(rows)
    _write_json(summary, work / "summary.json")
    md = to_markdown(summary)
    (work / "report.md").write_text(md, encoding="utf-8")
    print(md)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="citecheck", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    def source_args(sp, default="crossref"):
        sp.add_argument("--source", choices=["crossref", "openalex", "fixture"], default=default)
        sp.add_argument("--synthetic-n", type=int, default=60, help="fixture source: number of synthetic records")
        sp.add_argument("--synthetic-seed", type=int, default=0)

    sa = sub.add_parser("sample", help="seeded sample of DOIs (openalex or fixture)")
    source_args(sa, "openalex")
    sa.add_argument("--n", type=int, default=100)
    sa.add_argument("--seed", type=int, default=0)
    sa.add_argument("--out", default="data/dois.csv")
    sa.set_defaults(func=cmd_sample)

    bt = sub.add_parser("build-truth", help="look up each DOI and render the five reference styles")
    source_args(bt)
    bt.add_argument("--dois", default="data/dois.csv")
    bt.add_argument("--out", default="results/truth.jsonl")
    bt.set_defaults(func=cmd_build_truth)

    g = sub.add_parser("generate", help="ask the model for each work and prompt variant (resumable)")
    g.add_argument("--truth", default="results/truth.jsonl")
    g.add_argument("--provider", choices=["simulated", "openai"])
    g.add_argument("--variants", nargs="+", choices=list(VARIANTS), default=list(VARIANTS))
    g.add_argument("--seed", type=int, default=0, help="seed of the simulated model")
    g.add_argument("--out", default="results/generations.jsonl")
    g.set_defaults(func=cmd_generate)

    e = sub.add_parser("evaluate", help="field, existence and format metrics for each answer")
    source_args(e)
    e.add_argument("--truth", default="results/truth.jsonl")
    e.add_argument("--generations", default="results/generations.jsonl")
    e.add_argument("--out", default="results/eval.jsonl")
    e.set_defaults(func=cmd_evaluate)

    r = sub.add_parser("report", help="summary with bootstrap intervals and paired tests")
    r.add_argument("--eval", default="results/eval.jsonl")
    r.add_argument("--out", default="results/report.md")
    r.set_defaults(func=cmd_report)

    rd = sub.add_parser("render", help="show the reference strings of one DOI")
    rd.add_argument("doi")
    rd.add_argument("--source", choices=["crossref", "openalex"], default="crossref")
    rd.add_argument("--style", choices=list(STYLES))
    rd.set_defaults(func=cmd_render)

    d = sub.add_parser("demo", help="offline demo with synthetic records and the simulated model")
    d.add_argument("--n", type=int, default=60)
    d.add_argument("--seed", type=int, default=0)
    d.add_argument("--out-dir")
    d.set_defaults(func=cmd_demo)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
