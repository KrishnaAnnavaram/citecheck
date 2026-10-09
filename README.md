<div align="center">

# citecheck — Field-Level Accuracy Of LLM References In Five Styles

**citecheck is a benchmark tool that measures how accurately a language model writes academic references. It takes a seeded DOI sample through these steps to per-field hallucination rates with confidence intervals:**

`sample DOIs` → `build truth` → `generate` → `evaluate` → `report`.

![Styles](https://img.shields.io/badge/Styles-APA_%7C_MLA_%7C_Chicago_%7C_Harvard_%7C_Vancouver-1F3864?style=for-the-badge)
![Truth](https://img.shields.io/badge/Ground_truth-Crossref_%7C_OpenAlex-2E5FD9?style=for-the-badge)
![Prompt variants](https://img.shields.io/badge/Prompt_variants-3-6E86E8?style=for-the-badge)
![Tests](https://img.shields.io/badge/Tests-29_passing-3DA35B?style=for-the-badge)
![Offline demo](https://img.shields.io/badge/Offline_demo-Yes-F5C542?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-A0399B?style=for-the-badge)

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![SciPy](https://img.shields.io/badge/SciPy-McNemar_test-8CAAE6?style=flat-square&logo=scipy&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-record_schema-E92063?style=flat-square&logo=pydantic&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI--compatible-any_endpoint-412991?style=flat-square&logo=openai&logoColor=white)
![Docs](https://img.shields.io/badge/Docs-ASD--STE100-5D6D7E?style=flat-square)

**[Summary](#1-summary)** ·
**[Workflow](#4-the-end-to-end-workflow)** ·
**[Run it](#10-how-to-run-citecheck)** ·
**[Configuration](#104-environment-variables)** ·
**[Known problems](#13-known-problems)** ·
**[Glossary](#15-glossary)**

</div>

> [!NOTE]
> This README uses ASD-STE100 Simplified Technical English. The writing rules and the project
> vocabulary are in [`docs/ste-style-guide.md`](docs/ste-style-guide.md). Each term in the
> [Glossary](#15-glossary) has only one meaning.

---

citecheck asks a model for the bibliographic fields and the five reference strings of a work. It compares each field with DOI-resolved metadata from Crossref or OpenAlex. A false value is a hallucination. A missing value is an omission. citecheck counts the two apart and checks if a given DOI points to the same work. Paired tests compare prompt variants on the same works.

This README is the **one location that explains all of citecheck**. It gives these topics:

- the general design
- each component and its procedure, step by step
- the decision rules
- the data map
- the runbook
- the validation results and the known problems

| If you are… | Read |
|---|---|
| A manager or reviewer | [1](#1-summary), [3](#3-design-rules), [4](#4-the-end-to-end-workflow), [12](#12-validation-results), [14](#14-key-points) |
| A developer who joins the project | All sections, in sequence. Keep [10](#10-how-to-run-citecheck) and [13](#13-known-problems) open while you work |
| An operator who runs citecheck | [10](#10-how-to-run-citecheck), then the section for the component that you use |

---

## Table of contents

1. 🧭 [Summary](#1-summary)
2. 🏗️ [How citecheck is built](#2-how-citecheck-is-built)
   - 2.1 [Components](#21-components)
   - 2.2 [System context](#22-system-context)
   - 2.3 [Repository layout](#23-repository-layout)
3. 🛡️ [Design rules](#3-design-rules)
4. 🔄 [The end-to-end workflow](#4-the-end-to-end-workflow)
   - 4.1 [Full flow](#41-full-flow)
   - 4.2 [The life cycle of one work](#42-the-life-cycle-of-one-work)
   - 4.3 [Who does which step](#43-who-does-which-step)
5. 🔵 [Truth set and renderer](#5-truth-set-and-renderer)
6. 🟢 [Prompt variants and models](#6-prompt-variants-and-models)
7. 🟣 [Evaluation](#7-evaluation)
8. ⚖️ [The scoring and statistics rules](#8-the-scoring-and-statistics-rules)
9. 🗂️ [Data and file map](#9-data-and-file-map)
10. ▶️ [How to run citecheck](#10-how-to-run-citecheck)
    - 10.1 [Prerequisites](#101-prerequisites) · 10.2 [Installation](#102-installation) · 10.3 [Run citecheck](#103-run-citecheck) · 10.4 [Environment variables](#104-environment-variables)
11. 🧩 [How to extend citecheck](#11-how-to-extend-citecheck)
12. ✅ [Validation results](#12-validation-results)
13. ⚠️ [Known problems](#13-known-problems)
14. 📌 [Key points](#14-key-points)
15. 📖 [Glossary](#15-glossary)
16. 📄 [License](#16-license)

---

## 1. Summary

**The problem.** A whole-string similarity between two references mixes two different failures: a false fact and a different punctuation. The difficult questions are:

- Which fields does the model make up, and which fields does it leave out?
- Does a DOI from the model point to the work, to another work or to nothing?
- How much does the answer improve when the prompt gives the DOI or the full metadata?
- Is a difference between two prompts larger than chance on the same works?

citecheck gives each question its own metric and a paired test.

| Item | Value |
|---|---|
| Input | A CSV file of DOIs (`doi` column), or a seeded OpenAlex sample |
| Output | `truth.jsonl`, `generations.jsonl`, `eval.jsonl`, `report.md` and `report.json` |
| Components | **6**: sources, renderer, prompts and models, parser, metrics, statistics |
| Providers | Crossref and OpenAlex (truth), any OpenAI-compatible endpoint (model under test) |
| Offline mode | Synthetic records, the fixture source and the seeded simulated model |
| Safety | Keys come from the environment only. A test scans the repository for key patterns |
| Tests | **29** unit tests (`pytest`), all offline |

```mermaid
flowchart LR
    IN["DOI list"] --> A["truth set (Crossref / OpenAlex)"] --> B["model answers (3 prompt variants)"] --> C["field statuses + DOI check + format scores"] --> OUT["report with intervals"]
```

---

## 2. How citecheck is built

### 2.1 Components

| Component | Module | Purpose |
|---|---|---|
| Records | `src/citecheck/records.py` | `WorkRecord` schema (CSL-like fields), loose-input cleaning |
| Normalisation | `src/citecheck/normalize.py` | Title, DOI, name and page folding, token F1 |
| Sources | `src/citecheck/sources/` | Crossref and OpenAlex parsers, cached HTTP client, fixture source |
| Renderer | `src/citecheck/render.py` | Reference strings for the five styles, looked up by name |
| Prompts | `src/citecheck/prompts.py` | The three prompt variants and the JSON answer contract |
| Models | `src/citecheck/llm.py` | OpenAI-compatible client, simulated model, scripted model |
| Parser | `src/citecheck/parse.py` | JSON extraction and record building from an answer |
| Metrics | `src/citecheck/metrics.py` | Field statuses, author scores, existence check, format scores |
| Statistics | `src/citecheck/stats.py` | Bootstrap intervals, paired bootstrap, exact McNemar test |
| Pipeline | `src/citecheck/pipeline.py` | Truth, generation (resumable), evaluation, summary |
| Report | `src/citecheck/report.py` | Markdown report, with a banner for simulated results |
| Synthetic data | `src/citecheck/synthetic.py` | Invented records with test-prefix DOIs |
| CLI | `src/citecheck/cli.py` | The `citecheck` command |

The component map shows which module calls which module. An arrow points from the caller to the module that it uses.

```mermaid
flowchart TB
    subgraph ENTRY["Entry point"]
        CLI["cli.py<br/>citecheck command"]
        CFG["config.py<br/>Settings, load_dotenv"]
    end
    subgraph TRUTH["Truth"]
        SRC["sources/apis.py<br/>Crossref, OpenAlex, Fixture"]
        HTTP["sources/http.py<br/>JsonClient"]
        SYN["synthetic.py<br/>make_records"]
        REN["render.py<br/>STYLES, render_all"]
    end
    subgraph GEN["Generation"]
        PRM["prompts.py<br/>VARIANTS, messages"]
        LLM["llm.py<br/>OpenAICompatibleLLM, SimulatedLLM"]
    end
    subgraph SCORE["Evaluation"]
        PAR["parse.py<br/>parse_answer"]
        MET["metrics.py<br/>field_statuses, existence, format_scores"]
        STA["stats.py<br/>bootstrap_ci, mcnemar"]
        REP["report.py<br/>to_markdown"]
    end
    PIPE["pipeline.py<br/>build_truth, generate, evaluate, summarize"]
    REC["records.py, normalize.py<br/>WorkRecord, folding"]

    CLI --> CFG
    CLI --> SRC
    CLI --> SYN
    CLI --> LLM
    CLI --> PIPE
    CLI --> REN
    CLI --> REP
    SRC --> HTTP
    SRC --> REC
    PIPE --> SRC
    PIPE --> REN
    PIPE --> PRM
    PIPE --> LLM
    PIPE --> PAR
    PIPE --> MET
    PIPE --> STA
    MET --> SRC
    LLM --> REN
    PAR --> REC
```

### 2.2 System context

```mermaid
flowchart TB
    U["researcher"] --> CLI["citecheck CLI"]
    CLI --> CR["Crossref API"]
    CLI --> OA["OpenAlex API"]
    CLI --> M["model under test (OpenAI-compatible)"]
    CLI --> SIM["simulated model (offline)"]
    CLI --> CACHE["data/cache (API responses)"]
    CLI --> RES["results/*.jsonl, report.md"]
```

### 2.3 Repository layout

```
citecheck/
├── data/README.md            sources, terms, file schema (no data is committed)
├── docs/ste-style-guide.md   writing rules and project vocabulary
├── src/citecheck/
│   ├── records.py normalize.py render.py prompts.py
│   ├── llm.py parse.py metrics.py stats.py
│   ├── pipeline.py report.py synthetic.py config.py
│   ├── sources/              http.py (cache, rate, retry), apis.py (Crossref, OpenAlex, fixture)
│   └── cli.py                the citecheck command
├── tests/                    pytest suite (offline)
└── pyproject.toml            package and the console script
```

---

## 3. Design rules

### 3.1 Truth from open APIs, not from scraping
The truth set comes from Crossref or OpenAlex by DOI. The renderer makes the five reference strings from these records. citecheck never scrapes a search engine.

### 3.2 Styles by name
`render.STYLES` maps each style name to its renderer. No code maps a style to a row position, so APA and MLA can never change places. A test checks a typical pattern of each style.

### 3.3 Field-level scoring
Each field gets the status `correct`, `wrong`, `missing` or `n/a`. A wrong value is a hallucination. A missing value is an omission. The two rates are separate.

### 3.4 Real tests, not a test against 1.0
Every rate has a 95% bootstrap interval. Two prompt variants are compared on the same works with the exact McNemar test and a paired bootstrap interval.

### 3.5 No made-up results
A failed model call is saved with its error and an empty answer. The simulated model marks every row as `simulated`. `summarize` refuses a file that mixes simulated and real rows, and the report shows a banner for simulated results.

```mermaid
flowchart TD
    GEN["generate: each row gets<br/>simulated = llm.simulated"] --> EVR[/"eval.jsonl rows"/]
    FAIL["Failed model call"] --> ROW["Row with the error text<br/>and an empty raw field"]
    ROW --> EVR
    EVR --> MIX{"summarize: simulated and<br/>real rows in one file?"}
    MIX -- "yes" --> STOP[/"ValueError: evaluate them apart"/]
    MIX -- "no" --> SIM{"Rows simulated?"}
    SIM -- "yes" --> BAN[/"report.md with the<br/>SIMULATED RESULTS banner"/]
    SIM -- "no" --> REP[/"report.md with the model name"/]
```

### 3.6 Keys from the environment only
The model key comes from `CITECHECK_LLM_API_KEY` or `OPENAI_API_KEY`. The settings object hides the key in its text form. A test scans all tracked files for key patterns.

### 3.7 Polite, repeatable data collection
The HTTP client caches each response on disk, waits `CITECHECK_MIN_INTERVAL_S` between calls and retries HTTP 429 and 5xx with back-off. An error stops the run. It never becomes an "N/A" row.

```mermaid
flowchart TD
    URL[/"API URL"/] --> C{"Cache file for the URL<br/>in data/cache?"}
    C -- "yes" --> CB[/"Cached body"/]
    C -- "no" --> W["Wait until CITECHECK_MIN_INTERVAL_S<br/>has passed since the last call"]
    W --> GET["GET with the User-Agent<br/>and the mailto address"]
    GET --> S{"HTTP status"}
    S -- "200" --> B["JSON body"]
    S -- "404" --> N["None: the DOI does not exist"]
    S -- "429, 500, 502, 503, 504<br/>and a retry is left" --> BO["Back-off: 1, 2, 4 s"]
    BO --> W
    S -- "other status,<br/>or no retry left" --> ERR[/"HTTPError: the run stops"/]
    B --> SAVE["Write the cache file:<br/>url and body"]
    N --> SAVE
    SAVE --> OUT[/"Body, or None"/]
```

---

## 4. The end-to-end workflow

### 4.1 Full flow

```mermaid
flowchart TD
    SQ{"sample --source"} -- "openalex" --> SAMP["OpenAlexSource.sample_dois<br/>seeded, type:article,has_doi:true"]
    SQ -- "fixture" --> FIX["FixtureSource.sample_dois<br/>synthetic records"]
    OWN[/"Your CSV with a doi column"/] --> DOIS
    SAMP --> DOIS[("data/dois.csv")]
    FIX --> DOIS
    DOIS --> READ["read_dois: normalize, remove duplicates"]
    READ --> BT["build_truth: lookup_doi for each DOI"]
    API[("Crossref or OpenAlex<br/>cached in data/cache")] --> BT
    BT --> SKIP{"Found, with authors<br/>and a year?"}
    SKIP -- "no" --> LOG[/"skip message"/]
    SKIP -- "yes" --> REN["render_all: 5 reference strings"]
    REN --> TRUTH[("results/truth.jsonl")]
    KEY{{"OPERATOR<br/>select the provider and the model,<br/>put the key in .env"}} --> GEN
    TRUTH --> GEN["generate: 3 prompt variants for each work,<br/>done triples skipped"]
    GEN --> GENS[("results/generations.jsonl")]
    GENS --> EVAL["evaluate: parse_answer, field_statuses,<br/>author_scores, existence, format_scores"]
    TRUTH --> EVAL
    EVAL --> EVF[("results/eval.jsonl")]
    EVF --> SUM["summarize: bootstrap intervals,<br/>McNemar against title_only"]
    SUM --> OUT[/"report.md + report.json"/]
    OUT --> HUMAN{{"HUMAN<br/>read the banner and the known problems<br/>before you publish"}}

    classDef human fill:#fff3cd,stroke:#b8901f,color:#3d2f00,font-weight:bold
    class KEY,HUMAN human
```

### 4.2 The life cycle of one work

```mermaid
stateDiagram-v2
    state "DOI in dois.csv" as Listed
    state "Skipped by build-truth" as Skipped
    state "Truth row with 5 strings" as Truth
    state "Answer saved" as Answer
    state "Call error saved" as CallError
    state "Parsed record" as Parsed
    state "Parse failed" as ParseFailed
    state "Evaluation row" as Scored
    state "In the summary" as Summarized
    [*] --> Listed: sample, or your CSV
    Listed --> Skipped: not found, or no authors or no year
    Listed --> Truth: lookup_doi, render_all
    Truth --> Answer: generate, one row for each variant
    Truth --> CallError: the model call raised an error
    Answer --> Parsed: parse_answer ok
    Answer --> ParseFailed: no JSON object or invalid fields
    Parsed --> Scored: field_statuses, existence, format_scores
    ParseFailed --> Scored: fields missing or n/a, no_doi
    CallError --> Scored: fields missing or n/a, no_doi
    Scored --> Summarized: summarize
    Skipped --> [*]
    Summarized --> [*]
```

1. `sample` puts the DOI of the work in `data/dois.csv`.
2. `build-truth` gets the record from the source and renders the five reference strings.
3. `build-truth` skips the work if the source has no authors or no year for it.
4. `generate` sends three prompts: title only, title and DOI, full metadata.
5. The model returns one JSON object with the fields and five reference strings.
6. `parse_answer` reads the JSON object. A parse failure or a call error counts every field as missing. A field with no truth value stays `n/a`.
7. `field_statuses` compares each field with the truth after normalisation.
8. `existence` gets the DOI of the answer from the source and compares the titles.
9. `format_scores` compares each reference string with the rendered truth.
10. `summarize` puts the work into the rates and the paired tests of each variant.

### 4.3 Who does which step

```mermaid
sequenceDiagram
    autonumber
    actor R as Researcher
    participant CLI as citecheck CLI
    participant PIPE as pipeline.py
    participant HTTP as JsonClient and data/cache
    participant API as Crossref or OpenAlex
    participant LLM as Model under test
    participant FS as data/ and results/ files

    R->>CLI: citecheck sample --source openalex --n 200
    CLI->>HTTP: get works sample, one page at a time
    HTTP->>API: GET /works with sample, seed and filter
    API-->>HTTP: page of works
    CLI->>FS: write data/dois.csv
    R->>CLI: citecheck build-truth --source crossref
    CLI->>PIPE: build_truth(dois, source)
    PIPE->>HTTP: lookup_doi for each DOI
    HTTP->>API: GET /works/DOI, on a cache miss only
    API-->>HTTP: metadata, or HTTP 404
    HTTP-->>PIPE: WorkRecord, or None
    PIPE->>PIPE: render_all, 5 styles
    CLI->>FS: write results/truth.jsonl
    R->>CLI: citecheck generate --provider openai
    CLI->>PIPE: generate(truth, llm, variants, out)
    loop each work and variant not in the file
        PIPE->>LLM: POST /chat/completions, temperature 0, JSON mode
        LLM-->>PIPE: JSON answer, or an error
        PIPE->>FS: append one row to generations.jsonl
    end
    R->>CLI: citecheck evaluate --source crossref
    CLI->>PIPE: evaluate(truth, generations, source)
    PIPE->>PIPE: parse_answer, field_statuses, format_scores
    PIPE->>HTTP: lookup_doi of a DOI that differs from the truth
    CLI->>FS: write results/eval.jsonl
    R->>CLI: citecheck report
    CLI->>PIPE: summarize(rows)
    PIPE-->>CLI: summary with intervals and McNemar tests
    CLI->>FS: write report.json and report.md
    CLI-->>R: paths of the written files
```

---

## 5. Truth set and renderer

**Purpose.** Make exact, repeatable ground truth for each work and each style.

```mermaid
flowchart TD
    IN[/"DOIs and --source"/] --> NORM["normalize_doi: remove doi.org and doi:,<br/>lower case"]
    NORM --> SRC{"Source"}
    SRC -- "crossref" --> CR["CrossrefSource.lookup_doi<br/>GET /works/DOI"]
    SRC -- "openalex" --> OA["OpenAlexSource.lookup_doi<br/>GET /works/doi:DOI"]
    SRC -- "fixture" --> FX["FixtureSource.lookup_doi<br/>synthetic records in memory"]
    CR -- "200" --> PC["parse_crossref: first date part,<br/>CROSSREF_TYPES"]
    OA -- "200" --> PO["parse_openalex: family name is the last word,<br/>OPENALEX_TYPES"]
    CR -- "404" --> NF[/"skip: not found"/]
    OA -- "404" --> NF
    FX -- "unknown DOI" --> NF
    PC --> AY{"Authors and a year?"}
    PO --> AY
    FX -- "known DOI" --> AY
    AY -- "no" --> NA[/"skip: no authors or no year"/]
    AY -- "yes" --> RA["render_all: the five styles by name"]
    RA --> OUT[/"truth.jsonl row:<br/>source, record, citations"/]
```

| Input | Output |
|---|---|
| DOIs and a source (`crossref`, `openalex` or `fixture`) | `truth.jsonl`: `source`, `record`, `citations` |

**Procedure**

1. Normalise each DOI (remove `https://doi.org/` and `doi:`, fold case).
2. Get the record. A 404 answer means that the DOI does not exist.
3. Map the source type to `article-journal`, `paper-conference`, `book`, `chapter`, `report` or `other`.
4. Render the five reference strings.

**Rules of the renderer**

```mermaid
flowchart LR
    REC[/"WorkRecord"/] --> ALL["render_all: each name in STYLES"]
    ALL --> AUTH["Author list by the rule<br/>of the style"]
    AUTH --> YR["Year, or n.d.<br/>or no date"]
    YR --> TY{"type is book?"}
    TY -- "yes" --> BK["Title, publisher"]
    TY -- "no" --> CT["Title, container, volume,<br/>issue, pages"]
    BK --> DOI["DOI as https://doi.org/<br/>or doi: for Vancouver"]
    CT --> DOI
    DOI --> OUT[/"citations: apa, mla, chicago,<br/>harvard, vancouver"/]
```

| Style | Authors | Pattern for a journal article |
|---|---|---|
| `apa` | `Family, I. I.`, `&` before the last, up to 20, then `. . .` and the last | `Authors (Year). Title. Journal, Volume(Issue), pages. https://doi.org/DOI` |
| `mla` | first `Family, Given`, two with `and`, three or more `et al.` | `Authors. “Title.” Journal, vol. V, no. I, Year, pp. P, https://doi.org/DOI.` |
| `chicago` | first inverted, others `Given Family`, up to 10 | `Authors. Year. “Title.” Journal Volume (Issue): pages. https://doi.org/DOI.` |
| `harvard` | `Family, I.I.`, `and` before the last, more than 3 `et al.` | `Authors (Year) ‘Title’, Journal, Volume(Issue), pp. pages. Available at: https://doi.org/DOI.` |
| `vancouver` | `Family II`, up to 6, then `et al.` | `Authors. Title. Journal. Year;Volume(Issue):pages. doi:DOI` |

The renderer follows the main pattern of each style guide. It is a simplified version, not a full CSL processor. Section 13 lists the limits.

---

## 6. Prompt variants and models

**Purpose.** Ask the model for the same facts with three amounts of input.

```mermaid
flowchart LR
    REC[/"Truth record and variant"/] --> CHK{"variant in VARIANTS?"}
    CHK -- "no" --> ERR[/"ValueError"/]
    CHK -- "yes" --> T["Title line"]
    T --> D{"title_doi or full_metadata,<br/>and the DOI is known?"}
    D -- "yes" --> DL["Add the DOI line"]
    D -- "no" --> F{"full_metadata?"}
    DL --> F
    F -- "yes" --> ML["Add Authors, Year, Type, Container,<br/>Volume, Issue, Pages, Publisher<br/>when they have a value"]
    F -- "no" --> MSG["messages: SYSTEM prompt<br/>and the user prompt with 5 style names"]
    ML --> MSG
    MSG --> OUT[/"Chat messages"/]
```

| Variant | The prompt gives |
|---|---|
| `title_only` | The title |
| `title_doi` | The title and the DOI |
| `full_metadata` | The title, the DOI, the authors, the year, the type, the container, the volume, the issue, the pages, the publisher |

The system prompt asks for one JSON object with `authors`, `year`, `title`, `container_title`, `volume`, `issue`, `pages`, `doi`, `type` and `citations` (one string for each style). It tells the model to leave unknown facts empty.

| Model | Module | Use |
|---|---|---|
| `OpenAICompatibleLLM` | `llm.py` | Real runs. Temperature 0, JSON mode, `https` base URL (or `localhost`) |
| `SimulatedLLM` | `llm.py` | Offline runs. Seeded errors with fixed rates for each variant. Every row is marked `simulated` |
| `ScriptedLLM` | `llm.py` | Tests. Fixed answers |

```mermaid
flowchart TD
    TR[/"truth.jsonl"/] --> PROV{"--provider or<br/>CITECHECK_LLM_PROVIDER"}
    PROV -- "simulated" --> SIM["SimulatedLLM<br/>truth records and seed"]
    PROV -- "openai" --> KEYQ{"Key set, or a base URL<br/>that is not https?"}
    KEYQ -- "no" --> EXIT[/"Exit: set CITECHECK_LLM_API_KEY"/]
    KEYQ -- "yes" --> URLQ{"Base URL is https,<br/>or localhost?"}
    URLQ -- "no" --> VE[/"ValueError"/]
    URLQ -- "yes" --> OAI["OpenAICompatibleLLM<br/>temperature 0, JSON mode"]
    SIM --> LOOP["For each work and each variant"]
    OAI --> LOOP
    LOOP --> DONE{"Work, variant and model<br/>in the output file?"}
    DONE -- "yes" --> SKIP["Skip"]
    DONE -- "no" --> CALL["llm.complete(messages)"]
    CALL --> OKQ{"Error?"}
    OKQ -- "yes" --> EROW["raw empty, error text"]
    OKQ -- "no" --> AROW["raw answer, error empty"]
    EROW --> APP[/"Append to generations.jsonl<br/>with the simulated flag"/]
    AROW --> APP
```

The simulated model makes its errors from fixed rates, so a correct pipeline must find these rates again.

```mermaid
flowchart TD
    P[/"Chat messages"/] --> T["Read the Title line,<br/>find the truth record by title"]
    T --> F{"Title in the catalogue?"}
    F -- "no" --> E[/"JSON with the title only"/]
    F -- "yes" --> V["Variant from the prompt:<br/>Authors line, DOI line, or title only"]
    V --> R["Seeded generator:<br/>seed, work ID, variant"]
    R --> L["For each field: error with<br/>the ERROR_RATES of the variant"]
    L --> K{"Error?"}
    K -- "no" --> KEEP["Keep the true value"]
    K -- "yes, OMIT_SHARE 0.4" --> OM["Omission: empty value"]
    K -- "yes, other errors" --> WR["Wrong value: other year,<br/>other venue, invented or other DOI"]
    KEEP --> RA["render_all of the answer record"]
    OM --> RA
    WR --> RA
    RA --> SL["Each string: STYLE_SLIP 0.25<br/>chance of one format slip"]
    SL --> OUT[/"JSON answer,<br/>model name simulated-seedN"/]
```

**Rules**

- Generation is resumable. A (work, variant, model) triple in the output file is not sent again.
- A failed call is saved with `error` and an empty `raw` field.

---

## 7. Evaluation

**Purpose.** Give each answer field statuses, a DOI result and format scores.

```mermaid
flowchart LR
    G[/"generations row"/] --> TQ{"work_id in<br/>the truth set?"}
    TQ -- "no" --> SK["Skip"]
    TQ -- "yes" --> EQ{"Call error?"}
    EQ -- "yes" --> NP["No record"]
    EQ -- "no" --> PA["parse_answer"]
    PA -- "parse failed" --> NP
    PA -- "ok" --> FS["field_statuses"]
    NP --> FS
    FS --> AU["author_scores<br/>0 with no record"]
    AU --> EX["existence"]
    EX --> FM["format_scores<br/>for the 5 styles"]
    FM --> OUT[/"eval.jsonl row"/]
```

`parse_answer` reads one answer as follows:

```mermaid
flowchart TD
    RAW[/"Raw answer text"/] --> FJ["first_json_object: first balanced block,<br/>braces in strings ignored"]
    FJ --> B{"Block found?"}
    B -- "no" --> E1[/"ok false: no JSON object"/]
    B -- "yes" --> J{"Valid JSON,<br/>and an object?"}
    J -- "no" --> E2[/"ok false: invalid JSON,<br/>or not an object"/]
    J -- "yes" --> RD["record_from_dict: drop unknown keys,<br/>years outside 1000 to 2100, invalid DOIs"]
    RD --> V{"Validation error?"}
    V -- "yes" --> E3[/"ok false: invalid fields"/]
    V -- "no" --> C["Keep the citations<br/>with a known style name"]
    C --> OK[/"ok true: record and citations"/]
```

| Input | Output |
|---|---|
| `truth.jsonl`, `generations.jsonl`, a source | `eval.jsonl`: one row per answer |

**Procedure**

1. Read the first balanced JSON object of the answer. Ignore code fences and text around it.
2. Build a record. Drop unknown keys, invalid years and invalid DOIs.
3. Give each field a status (section 8).
4. Compute author precision, recall, F1 and first-author match on normalised family names.
5. Run the existence check on the DOI of the answer.
6. Compute exact match and token F1 for each of the five reference strings.

---

## 8. The scoring and statistics rules

**Field statuses.**

| Field | `correct` when |
|---|---|
| `authors` | The normalised family names are equal, in the same order |
| `year` | The years are equal |
| `title` | Token F1 of the normalised titles is at least 0.9 |
| `container_title` | Equal after folding, or token F1 at least 0.9 |
| `volume`, `issue` | Equal after folding |
| `pages` | Equal after normalisation (`123-9` becomes `123-129`) |
| `doi` | Equal after normalisation |

A field is `n/a` when the truth has no value. It is `missing` when the answer has no value. Otherwise it is `wrong`.

```mermaid
flowchart TD
    IN[/"Answer value and truth value<br/>of one field"/] --> T{"Truth value empty?"}
    T -- "yes" --> NA[/"n/a: the field does not count"/]
    T -- "no" --> P{"Answer value empty?"}
    P -- "yes" --> MI[/"missing: an omission"/]
    P -- "no" --> S{"Same after the rule of the field?<br/>title F1 ≥ 0.9, pages expanded,<br/>DOI normalised"}
    S -- "yes" --> CO[/"correct"/]
    S -- "no" --> WR[/"wrong: a hallucination"/]
```

**Existence check.**

| Result | Meaning |
|---|---|
| `same_work` | The DOI equals the true DOI, or it points to a record with a title match |
| `other_work` | The DOI points to a real record of another work |
| `not_found` | The source does not know the DOI |
| `no_doi` | The answer has no DOI |

```mermaid
flowchart TD
    A[/"Answer record and truth record"/] --> D{"Answer has a DOI?"}
    D -- "no" --> ND[/"no_doi"/]
    D -- "yes" --> EQ{"Same DOI as the truth<br/>after normalize_doi?"}
    EQ -- "yes" --> SW[/"same_work"/]
    EQ -- "no" --> LK["source.lookup_doi<br/>of the answer DOI"]
    LK --> F{"Record found?"}
    F -- "no" --> NF[/"not_found"/]
    F -- "yes" --> TS{"title_similarity<br/>≥ 0.9?"}
    TS -- "yes" --> SW
    TS -- "no" --> OW[/"other_work"/]
```

**Format scores.** Exact match folds case, quotes, dashes and spaces, but keeps punctuation, because punctuation is part of a style. Token F1 compares the words only. A high token F1 with a low exact match means correct facts in a wrong format.

**Statistics.** Each rate has a 95% percentile bootstrap interval (2000 resamples, seed 0). citecheck compares each prompt variant with `title_only` on the same works. It uses the exact McNemar test for each field and a paired bootstrap interval of the accuracy difference.

```mermaid
flowchart TD
    R[/"eval.jsonl rows"/] --> E{"No rows?"}
    E -- "yes" --> ERR[/"ValueError"/]
    E -- "no" --> M{"Simulated and real<br/>rows mixed?"}
    M -- "yes" --> ERR
    M -- "no" --> V["For each variant and field:<br/>accuracy, hallucination, omission,<br/>n/a rows left out"]
    V --> BS["bootstrap_ci: 2000 resamples,<br/>seed 0, 95 % percentile interval"]
    BS --> X["Existence shares, author F1,<br/>exact match and token F1 for each style"]
    X --> B{"title_only rows exist?"}
    B -- "no" --> OUT[/"summary: report.json,<br/>to_markdown gives report.md"/]
    B -- "yes" --> PAIR["Pair each variant with title_only<br/>on the same work and model"]
    PAIR --> MC["mcnemar for each field:<br/>exact binomial test"]
    PAIR --> PB["paired_bootstrap: accuracy difference,<br/>APA token F1 difference"]
    MC --> OUT
    PB --> OUT
```

---

## 9. Data and file map

| Path | Committed? | Contents |
|---|---|---|
| `data/README.md` | Yes | Sources, terms and file schema |
| `data/dois.csv` | No (git ignores it) | The DOI sample |
| `data/cache/` | No (git ignores it) | API responses |
| `results/truth.jsonl` | No (git ignores it) | Truth set |
| `results/generations.jsonl` | No (git ignores it) | Model answers |
| `results/eval.jsonl` | No (git ignores it) | Evaluation rows |
| `results/report.md`, `report.json` | No (git ignores it) | Summary |
| `.env` | No (git ignores it) | Local settings and the key |
| `.env.example` | Yes | Names of the environment variables |

---

## 10. How to run citecheck

### 10.1 Prerequisites

| Need | For |
|---|---|
| Python 3.11+ | All components |
| Network access | `sample`, `build-truth` and `evaluate` with `crossref` or `openalex`, and real model runs |
| A key for an OpenAI-compatible endpoint | Real model runs only |

### 10.2 Installation

```bash
git clone https://github.com/KrishnaAnnavaram/citecheck.git
cd citecheck
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 10.3 Run citecheck

```mermaid
flowchart LR
    A["citecheck sample"] --> B[("data/dois.csv")]
    B --> C["citecheck build-truth"]
    C --> D[("results/truth.jsonl")]
    D --> E["citecheck generate"]
    E --> F[("results/generations.jsonl")]
    F --> G["citecheck evaluate"]
    G --> H[("results/eval.jsonl")]
    H --> I["citecheck report"]
    I --> J[/"report.md + report.json"/]
    DEMO["citecheck demo<br/>fixture source and SimulatedLLM"] --> T[/"Temporary folder or --out-dir:<br/>generations.jsonl, summary.json, report.md"/]
```

```bash
# offline demo: 60 synthetic works, the simulated model, all stages
citecheck demo

# real run (network): sample, truth, answers, evaluation, report
citecheck sample --source openalex --n 200 --seed 0 --out data/dois.csv
citecheck build-truth --source crossref --dois data/dois.csv --out results/truth.jsonl
citecheck generate --provider openai --truth results/truth.jsonl --out results/generations.jsonl
citecheck evaluate --source crossref --truth results/truth.jsonl --generations results/generations.jsonl --out results/eval.jsonl
citecheck report --eval results/eval.jsonl --out results/report.md

# show the five reference strings of one DOI
citecheck render 10.1038/nature14539 --source crossref
```

### 10.4 Environment variables

| Variable | Used by | Meaning |
|---|---|---|
| `CITECHECK_DATA_DIR` | Settings only | Data folder. Default `data`. The CLI does not read it. Use `--dois` and `--out` to change the paths |
| `CITECHECK_RESULTS_DIR` | Settings only | Results folder. Default `results`. The CLI does not read it. Use `--out` to change the paths |
| `CITECHECK_CACHE_DIR` | sources | API cache. Default `data/cache` |
| `CITECHECK_CONTACT_EMAIL` | sources | Sent as `mailto` to Crossref and OpenAlex (polite pool) |
| `CITECHECK_MIN_INTERVAL_S` | sources | Seconds between API calls. Default `0.2` |
| `CITECHECK_LLM_PROVIDER` | `generate` | `simulated` (default) or `openai` |
| `CITECHECK_LLM_BASE_URL` | `generate` | Default `https://api.openai.com/v1` |
| `CITECHECK_LLM_MODEL` | `generate` | Default `gpt-4o-mini` |
| `CITECHECK_LLM_API_KEY` | `generate` | Model key. `OPENAI_API_KEY` is also read |
| `CITECHECK_LLM_TIMEOUT_S` | `generate` | Default `60` |

Credentials are only in a local `.env` file. Git ignores this file. Do not print or commit credentials.

---

## 11. How to extend citecheck

| You want to… | Do this | Code change? |
|---|---|---|
| Test another model | Set `CITECHECK_LLM_BASE_URL` and `CITECHECK_LLM_MODEL`, then run `generate` again into a new file | No |
| Use your own DOI list | Write a CSV with a `doi` column and pass it to `build-truth` | No |
| Add a style | Add a renderer to `STYLES` in `render.py` and a test of its pattern | Small |
| Use official CSL styles | Replace the renderer with a CSL processor (for example `citeproc-py`) behind the same `render` function | Yes |
| Add a prompt variant | Add it to `VARIANTS` and to `user_prompt` | Small |
| Add a source | Write a class with `name` and `lookup_doi(doi)` | Small |

---

## 12. Validation results

| Validation | Result | Command |
|---|---|---|
| Unit tests | **29 passed** (all offline, the same in CI) | `pytest -q` |
| Pipeline check with the simulated model | See below | `citecheck demo --n 200` |

**Pipeline check (SIMULATED).** The simulated model has fixed error rates (`ERROR_RATES` in `llm.py`). A correct pipeline must find these rates again. With 200 synthetic works and seed 0, the `full_metadata` variant has a set year-error rate of 2%. The measured year accuracy is 96.5% [93.5%, 99.0%], with 2.0% hallucination and 1.5% omission. The `title_doi` variant has a set DOI-error rate of 5%. The measured DOI accuracy is 94.0% [90.5%, 97.0%], and the existence check finds the same work for 94.0% of answers.

| Prompt variant (simulated) | Year accuracy | DOI accuracy | DOI points to another real work | APA exact match | APA token F1 |
|---|---|---|---|---|---|
| `title_only` | 46.0% | 23.0% | 16.0% | 0.5% | 0.725 |
| `title_doi` | 50.5% | 94.0% | 0.0% | 4.5% | 0.840 |
| `full_metadata` | 96.5% | 99.5% | 0.0% | 65.0% | 0.988 |

These numbers describe the simulator, not a real model. They show that the statuses, the existence check, the intervals and the McNemar tests work together. No real-model result is in this repository. The prototype reported only `SequenceMatcher` similarities on a duplicated sample. Those numbers are not reproduced here.

---

## 13. Known problems

Read these problems before you publish a result from citecheck.

| # | Area | Problem | Impact and action |
|---|---|---|---|
| 1 | Results | No real-model result is in the repository or in CI | Run the real pipeline with your own key and report the model version and the date |
| 2 | Renderer | The renderer is a simplified version of each style. It has no italics, no editors, no conference locations, no title-case rules | Exact match can count a correct reference as different. Read token F1 and the field rates first |
| 3 | Truth | Crossref and OpenAlex metadata can be incomplete or wrong (for example a missing issue) | A field with no truth value is `n/a`. A wrong truth value counts against the model |
| 4 | Authors | OpenAlex gives display names, so the family name is the last word | Names such as "van der Berg" can split wrongly. Prefer Crossref for the truth set |
| 5 | Title match | A title match uses token F1 ≥ 0.9 | Two works with almost the same title can count as the same work |
| 6 | Scope | The sample filter is `type:article,has_doi:true` by default | Books and works without a DOI are not in the default sample |
| 7 | Prototype data | The earlier data from search-result pages is not used | Old and new numbers are not comparable |

---

## 14. Key points

1. **Hallucination and omission are different.** citecheck counts a false value and a missing value apart, for each field.
2. **A DOI must point to the same work.** The existence check separates a correct DOI, a real but different work and an invented DOI.
3. **Truth is exact and legal.** Open APIs by DOI, rendered by fixed rules, and no scraping.
4. **Comparisons are paired.** McNemar tests and bootstrap intervals on the same works, not a test against 1.0.
5. **Simulated numbers stay apart.** The pipeline refuses to mix them with real results and marks them in the report.

---

## 15. Glossary

| Term | Meaning |
|---|---|
| **work** | One publication that has a DOI |
| **record** | The bibliographic fields of one work |
| **field** | One part of a record, for example `year` or `doi` |
| **source** | The ground-truth service: `crossref`, `openalex` or `fixture` |
| **truth set** | The records and their reference strings in `truth.jsonl` |
| **style** | One reference format: `apa`, `mla`, `chicago`, `harvard`, `vancouver` |
| **reference string** | The text of one reference in one style |
| **prompt variant** | `title_only`, `title_doi` or `full_metadata` |
| **answer** | The raw text of the model for one work and one variant |
| **status** | `correct`, `wrong`, `missing` or `n/a` for one field |
| **hallucination** | A field with a false value |
| **omission** | A field with no value although the truth has one |
| **existence check** | The result for the DOI of an answer: `same_work`, `other_work`, `not_found`, `no_doi` |
| **token F1** | The F1 score of the word tokens of two strings |
| **simulated model** | The seeded error model for offline runs |

---

## 16. License

[MIT](LICENSE) © 2026 Krishna Annavaram
