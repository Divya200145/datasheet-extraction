# datasheet-extraction

Layout-aware, deterministic-first extraction of equipment datasheet fields (tag, service, design pressure, design temperature, material, power) from PDFs, with unit normalisation, validation, provenance and a human-review queue.

**Read this first: what this is and is not**

- It is a small, working reference implementation of an approach: parse the page layout, map vendor-specific labels to one schema, normalise units, validate, and send anything uncertain to review instead of guessing.
- It was evaluated on **synthetic** datasheets that I generated myself in four invented vendor layouts (`src/datasheet_extraction/synth.py`). Because I wrote both the documents and the parser, the near-perfect scores below only show the pipeline does what it was designed to do on those layouts. **They are not an accuracy estimate for real vendor documents.**
- It does **not** handle scanned documents (no OCR), P&ID drawings or symbols, or multi-item schedule tables. No real vendor data, no expert-labelled golden set and no deployment are included.
- The LLM fallback is only an interface (`llm.py`) with a unit test using a fake model. No real model is wired in or evaluated.

## How it works

```
PDF page -> words + boxes (pdfplumber)
         -> visual lines -> cells (split on wide horizontal gaps)
         -> label/value pairs: inline "Label: value" | same row | value below label
         -> label vocabulary (exact match, templates.py) -> canonical field
         -> unit parsing to barg / degC / kW (normalize.py), range checks
         -> schema validation (pydantic), tag regex, pattern-scan fallback for tags
         -> status ok | needs_review, with review_reasons, warnings, provenance
```

Design decisions worth knowing:

- **Deterministic path first.** No model is called unless you pass an `LLMFallback`. The same PDF always yields byte-identical canonical JSON (checked 10x per document in the evaluation).
- **Never guess.** A label that is not in the vocabulary leaves the field empty and the record goes to `needs_review`. Layout D in the evaluation exists to demonstrate exactly this.
- **Fallback can only fill gaps.** If an LLM fallback is supplied, it is asked only for missing fields, cannot override a deterministic value, goes through the same unit parsing and range checks, and its values are marked in `provenance` with a warning to verify.
- **Provenance everywhere.** Each value records the method, the label it came from, the raw text and the bounding box.
- **Assumptions are explicit.** `bar` is treated as gauge with a warning; `MPa`/`kPa` are treated as gauge.

## Quick start

```bash
pip install -r requirements.txt
make test                      # 31 unit/integration tests
make eval                      # generates synthetic PDFs, runs the pipeline, writes results/
python -m datasheet_extraction extract samples/A_000.pdf samples/B_000.pdf samples/C_000.pdf samples/D_000.pdf
```

## Layout of the repo

```
src/datasheet_extraction/
  layout.py      words -> lines -> cells -> label/value pairs
  templates.py   label vocabulary (vendor synonyms -> canonical fields)
  normalize.py   unit parsing + material normalisation + plausibility limits
  schema.py      pydantic record, tag validation
  pipeline.py    orchestration, review routing, canonical JSON
  llm.py         optional fallback protocol (no implementation)
  synth.py       synthetic vendor datasheet generator with ground truth
scripts/evaluate.py   evaluation + determinism check
tests/                pytest suite
samples/              a few generated PDFs
results/              metrics.json and results.md from the last run
```

## Results on the synthetic set (seed 7, 40 documents per layout)

| Layout | What it is | OK | Needs review | All fields correct | OK but wrong |
|---|---|---|---|---|---|
| A | table, metric units | 40 | 0 | 40 | 0 |
| B | label-above-value grid, psig / degF / hp | 40 | 0 | 40 | 0 |
| C | free `Label: value` text, MPa | 40 | 0 | 40 | 0 |
| D | labels outside the vocabulary (held out on purpose) | 0 | 40 | 0 | 0 |

Determinism: 160 documents x 10 runs, 0 differing outputs. Full tables are in `results/results.md`.

The result I care about is the last column: the pipeline did not produce a confident wrong answer on the layout it did not know. The perfect scores on A-C are expected for self-generated data and should not be quoted as accuracy.

## Real public PDFs: a negative result

I also tried the unmodified pipeline on real, freely downloadable PDFs (INOXPA, KSB, Alfa Laval, Goulds, Spirax Sarco). Of 11 files only two were relevant equipment documents, and both are product-series datasheets, not tagged per-item datasheets. The pipeline extracted none of the required fields from them (everything went to `needs_review`) and made a wrong tag guess on several INOXPA pages (a material code, `GG-22`). There is therefore **no real-world accuracy figure**. Details are in [`real_data/FINDINGS.md`](real_data/FINDINGS.md); `scripts/try_real_pdfs.py` reproduces the run on any folder of PDFs.

## Known limitations / next steps

- Real documents are messier than the synthetic ones (skew, scans, merged cells, multi-page items, vendor-specific abbreviations). The vocabulary in `templates.py` is hand-built and does not yet cover real vendor labels.
- Real catalogue datasheets describe a product series with ranges, which the "one tagged item per page" schema does not model.
- Tag pattern-scan can pick up tag-shaped identifiers that are not equipment tags (seen on real data: a material code); the stop-list is not exhaustive.
- Next steps I would take: build a small hand-labelled set of real per-item datasheets, extend the vocabulary from it (and evaluate on separate documents), add a series-datasheet mode, add OCR for scans, and add multi-row schedule table support.
