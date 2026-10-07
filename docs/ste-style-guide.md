# The writing standard: ASD-STE100 Simplified Technical English

The README of citecheck and this file obey these rules. Section 3 gives the project vocabulary: the technical names and the technical verbs of citecheck.

## 1. The writing rules

### Words

1. Use one word for one meaning, and one meaning for one word. Do not use synonyms for variety.
2. Use a word only as one part of speech. For example, `test` is a noun or a verb, `check` is a verb.
3. Do not use phrasal verbs (`set up`, `carry out`, `find out`, `pick up`, `look up`, `come up with`).
   Use one verb: `prepare`, `do`, `find`, `get`, `make`.
4. Do not use an `-ing` form as a noun or an adjective (`the running job`, `after indexing`).
   Exception: a technical name, a file name, a command or a status value.
5. Do not use contractions (`don't`, `it's`, `can't`). Do not use slang or idioms
   (`out of the box`, `under the hood`, `at a glance`, `gotcha`, `bells and whistles`).
6. Do not use `and/or`. Write `A, B or both`.
7. Do not use `should`, `could`, `would` or `may` for instructions. Use `must` for a rule, the
   imperative for a step and `can` for a possibility.
8. Keep the articles `a`, `an` and `the` in sentences.
9. Do not make a noun cluster of more than three words. A technical name is one word.

### Sentences

1. A procedural sentence (an instruction) has a maximum of **20 words**.
2. A descriptive sentence has a maximum of **25 words**.
3. Write one instruction in one sentence.
4. Use the imperative for an instruction: `Run the tests.` Not `The tests should be run.`
5. Use the active voice. Use the passive voice only when the agent of the action is not important.
6. Use only the simple present, the simple past and the simple future.
7. Put a condition before the instruction: `If the index is stale, build it again.`
8. Do not use semicolons in sentences. Write two sentences.

### Paragraphs, notes and warnings

1. A paragraph has one topic and a maximum of **6 sentences**. Start with the topic sentence.
2. A warning or a caution starts with a clear command. Then it gives the reason.
3. A note gives information. It does not give an instruction.
4. Use a vertical list for a sequence or a set of conditions. Each item of a numbered procedure is one step.

### Tables, headings and diagrams

1. A table cell can be a short phrase. If a cell has a sentence, the sentence obeys the rules.
2. A heading is a noun phrase (`The cost model`) or an imperative (`Run the demo`).
   Do not start a heading with an `-ing` form.
3. A diagram label is a short phrase. Use the same terms as the text.

### What STE does not change

Code, commands, file names, paths, field names, environment variables, status values, enum values,
product names and URLs stay exactly as they are. They are technical names. Put them in backticks.

## 2. General words to replace

| Do not use | Use |
|---|---|
| utilize, leverage | use |
| in order to | to |
| set up | prepare, install, configure |
| carry out, perform | do |
| make sure, ensure | make sure (allowed), or `check that` |
| a lot of, lots of | many, much |
| e.g., i.e. | for example, that is |
| should (instruction) | must (rule) / imperative (step) |
| might, may (possibility) | can |
| very, really, just, simply, easily | (delete) |
| seamless, robust, powerful, blazing | (delete or give a measured fact) |

## 3. Project vocabulary

These terms have one meaning in the citecheck documentation. Code names are in backticks.

### 3.1 Technical names (nouns)

| Term | Meaning | Do not use |
|---|---|---|
| **work** | One publication that has a DOI. | paper (for all types), item, entry |
| **record** | The bibliographic fields of one work (`WorkRecord`). | metadata (alone), CSL entry |
| **field** | One part of a record: `authors`, `year`, `title`, `container_title`, `volume`, `issue`, `pages`, `doi`. | attribute, element |
| **source** | The ground-truth service: `crossref`, `openalex` or `fixture`. | provider (for this), database |
| **truth set** | The file `truth.jsonl`: the records and their reference strings. | gold set, ground truth file |
| **style** | One reference format: `apa`, `mla`, `chicago`, `harvard`, `vancouver`. | format (alone), citation type |
| **reference string** | The text of one reference in one style. | citation (for the text), bibliography entry |
| **renderer** | The function that makes a reference string from a record. | formatter, template |
| **model** | The language model under test. | LLM (in prose), AI, chatbot |
| **simulated model** | `SimulatedLLM`, the seeded error model for offline runs. | fake model, mock |
| **prompt variant** | The amount of input facts: `title_only`, `title_doi`, `full_metadata`. | prompt type, setting |
| **answer** | The raw text that the model returns for one work and one prompt variant. | response, output |
| **status** | The result for one field: `correct`, `wrong`, `missing` or `n/a`. | label, score |
| **hallucination** | A field with a value that is false (status `wrong`). | fabrication, error (alone) |
| **omission** | A field without a value although the truth has one (status `missing`). | gap, blank |
| **existence check** | The lookup of the DOI in an answer: `same_work`, `other_work`, `not_found`, `no_doi`. | DOI check, resolution test |
| **exact match** | Two reference strings that are equal after case, quote, dash and space folding. | string match |
| **token F1** | The F1 score of the word tokens of two reference strings. | similarity, fuzzy score |
| **paired comparison** | Two prompt variants on the same works, with McNemar tests and bootstrap intervals. | A/B test |

### 3.2 Technical verbs

| Verb | Meaning |
|---|---|
| **sample** | Get a seeded set of DOIs from OpenAlex or from the fixture source. |
| **get** | Read the record of one DOI from a source (`lookup_doi`). |
| **render** | Make a reference string from a record. |
| **generate** | Send the prompt of one work and one variant to the model and keep the answer. |
| **parse** | Read an answer into a record and five reference strings. |
| **evaluate** | Give each field a status and compute the existence check and the format scores. |
| **summarise** | Compute rates, bootstrap intervals and paired tests from the evaluation rows. |
| **normalise** | Fold case, accents, quotes, dashes and spaces before a comparison. |
