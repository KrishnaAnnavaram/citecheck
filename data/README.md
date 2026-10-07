# Data

This repository commits no data: no DOI lists, no API responses, no model answers and no results.

## Ground truth sources

| Item | Crossref | OpenAlex |
|---|---|---|
| Source name | Crossref REST API | OpenAlex API |
| URL | https://api.crossref.org/works/{doi} | https://api.openalex.org/works/doi:{doi} and `/works?sample=N&seed=S` |
| License / terms | Bibliographic metadata is free to reuse (Crossref states no copyright on the metadata). Use the "polite" pool: set `CITECHECK_CONTACT_EMAIL` | CC0. Use the "polite" pool: set `CITECHECK_CONTACT_EMAIL` |
| Rate | `CITECHECK_MIN_INTERVAL_S` between calls (default 0.2 s), back-off on HTTP 429 and 5xx | same |

citecheck does not scrape Google Scholar. Scraping breaks its terms of service and gives
unrepeatable data. The open APIs give exact, DOI-resolved metadata.

## Files that citecheck writes

| File | Contents |
|---|---|
| `data/dois.csv` | Column `doi` (required). Written by `citecheck sample` or by you |
| `data/cache/<source>/*.json` | Cached API responses, one file per URL |
| `results/truth.jsonl` | One line per work: `source`, `record` (CSL-like fields), `citations` (five rendered styles) |
| `results/generations.jsonl` | One line per work and prompt variant: `work_id`, `variant`, `model`, `simulated`, `raw`, `error` |
| `results/eval.jsonl` | One line per answer: field statuses, author scores, DOI existence, format scores |
| `results/report.md`, `report.json` | Summary with bootstrap intervals and paired tests |

## Make a DOI sample

```bash
citecheck sample --source openalex --n 200 --seed 0 --out data/dois.csv
```

## Synthetic data

`--source fixture` uses invented records from `citecheck.synthetic.make_records`. Their DOIs use the
test prefix `10.5555`, so they never point to a real work. The demo and the tests use only this data.
