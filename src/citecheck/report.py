"""A Markdown report from a summary."""
from __future__ import annotations

from .records import FIELDS
from .render import STYLES

BANNER = ("> **SIMULATED RESULTS.** These numbers come from the seeded error model `SimulatedLLM`. "
          "They show that the pipeline works. They are not a measurement of any real language model.")


def _ci(d: dict, pct: bool = True) -> str:
    if d.get("n", 0) == 0:
        return "n/a"
    f = (lambda x: f"{100 * x:.1f}%") if pct else (lambda x: f"{x:.3f}")
    return f"{f(d['mean'])} [{f(d['ci_low'])}, {f(d['ci_high'])}]"


def to_markdown(summary: dict) -> str:
    lines = [f"# citecheck report: {', '.join(summary['models'])}", ""]
    if summary["simulated"]:
        lines += [BANNER, ""]
    for v, s in summary["variants"].items():
        lines += [f"## Prompt variant `{v}` ({s['works']} works)", "",
                  f"Parsed answers: {_ci(s['parse_ok'])}. Author F1: {_ci(s['author_f1'], pct=False)}.", "",
                  "| Field | Accuracy | Hallucination (wrong value) | Omission |", "|---|---|---|---|"]
        for f in FIELDS:
            x = s["fields"][f]
            lines.append(f"| `{f}` | {_ci(x['accuracy'])} | {_ci(x['hallucination'])} | {_ci(x['omission'])} |")
        e = s["existence"]
        lines += ["", "| DOI points to the same work | another real work | nothing | no DOI given |", "|---|---|---|---|",
                  f"| {100 * e['same_work']:.1f}% | {100 * e['other_work']:.1f}% | {100 * e['not_found']:.1f}% | "
                  f"{100 * e['no_doi']:.1f}% |", "",
                  "| Style | Exact match | Token F1 |", "|---|---|---|"]
        for st in STYLES:
            x = s["styles"][st]
            lines.append(f"| {st} | {_ci(x['exact'])} | {_ci(x['token_f1'], pct=False)} |")
        lines.append("")
    for name, comp in summary["comparisons"].items():
        lines += [f"## Paired comparison `{name}`", "", "| Field | Accuracy difference | McNemar p |", "|---|---|---|"]
        for f in FIELDS:
            c = comp[f]
            lines.append(f"| `{f}` | {_ci(c['accuracy_diff'])} | {c['p_value']:.3g} |")
        lines.append("")
    return "\n".join(lines)
