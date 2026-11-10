# Trying the pipeline on real public PDFs (negative result)

I downloaded 11 freely available PDFs to see how the pipeline behaves on real documents. This note reports what happened, including the failures. **There is no accuracy figure here, because the set does not contain enough suitable documents to compute a meaningful one.**

## What the 11 files turned out to be

| Document | Source | What it is | Usable for evaluation? |
|---|---|---|---|
| INOXPA DIN-FOOD datasheet FT 01.110.33.01 (EN, ES, FR, RU) | INOXPA centrifugal pump downloads page | 3-page product-series datasheet; the same document in 4 languages | Only as one document (the other 3 are translations) |
| KSB KWP-Bloc type series booklet (28 pages) | KSB, via Lenntech data-sheets library | Series booklet covering many pump sizes | Partly: series-level limits only, no per-item values |
| Goulds Pump Selection Chart | ITT Goulds, via Lenntech | One-page catalog selection chart | No (not a datasheet) |
| Alfa Laval Centrifugal Pump Application Data Sheet | Alfa Laval, via Ferguson Industrial | Blank request form | No (no values to extract) |
| Spirax Sarco "Controls and Instrumentation" (2 brochures) | Spirax Sarco control valves page | Overview brochures | No (not datasheets) |
| FUNSD paper, DocILE paper | arXiv | Research papers about benchmarks | No (not equipment documents) |

So the set contains essentially **two** relevant documents, and neither is a per-item datasheet with an equipment tag.

## What the unmodified pipeline did

Run on the English, Spanish, French and Russian INOXPA datasheets (page 2), two pages of the KSB booklet, and the Alfa Laval form:

- Required fields found (tag, design pressure, design temperature): **none**.
- All pages were routed to `needs_review`, which is the intended behaviour when nothing is recognised.
- The INOXPA page does contain the values ("Max.operating pressure 10 bar", "Max.working temperature -10 to +120 degC"), but the labels are not in the vocabulary in `templates.py`, so they were not read. This is the designed "never guess" behaviour, but it also shows the vocabulary does not generalise.
- **A wrong value, repeatedly:** on the INOXPA materials page (page 1 of the English and Spanish versions, and page 2 of the Russian one) the tag pattern-scan returned `GG-22`, which is a material designation (cast iron grade), not an equipment tag. These records were still flagged `needs_review`, but the tag value itself is wrong. The stop-list in `schema.py` does not cover material codes.
- The INOXPA PDFs contain a rotated margin sidebar that extracts as reversed text (e.g. "etisbew ruo tlusnoc"). It is harmless here but would pollute a naive text-based approach.

## What this means

- The synthetic results in the main README only show the pipeline works on layouts I wrote it for.
- Real catalogue documents describe a product series with ranges, not one tagged item, so the "one equipment item per page" assumption of the schema does not fit them.
- Possible next steps: add a series-datasheet mode, extend the label vocabulary from real documents, filter material codes out of the tag scan, and build a hand-labelled set of real per-item datasheets. Tuning the vocabulary on these same two documents and then reporting success on them would be training on the test set, so I have not done it.

## Reproduce

```
python scripts/try_real_pdfs.py path/to/folder_of_pdfs
```
