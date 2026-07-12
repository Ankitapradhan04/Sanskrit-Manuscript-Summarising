# Sanskrit Manuscript Summarizer

An end-to-end pipeline that:

1. **Ingests manuscript page images, OCRs them, and separates readable
   ("good") pages from noisy/unreadable ones**, storing the good ones in a
   SQLite database.
2. **Builds a grammar & vocabulary reference set** from those good
   manuscripts, seeded with a real Sanskrit-English dictionary and
   grown by word-frequency statistics mined from your corpus.
3. **Translates and summarizes** a user-requested manuscript (image or
   pasted text) into English, using that reference set, via a small
   Flask web app or the command line.

---

## Important note on data sources (please read before Step 1)

You asked for the dataset to come from the **namami.gov.in** (National
Mission for Manuscripts / Kritisampada) website. I checked it directly:
**its `robots.txt` disallows automated crawling/scraping**, and
individual manuscript images are also gated behind per-institution
usage terms rather than a bulk-download API. Writing a scraper against
it would break their terms of service, so this project does not do that.

Instead:

- **`src/fetch_archive_org.py`** automatically downloads ~100 public-domain
  Sanskrit manuscript page images from **archive.org**, which does
  provide a documented, ToS-compliant search/download API. This is the
  "automated 100 manuscripts" step.
- **If you specifically want namami.gov.in material**, you can manually
  browse `https://www.namami.gov.in/digital-manuscripts-library`,
  save individual page images you've confirmed are free to use, and
  drop them into `data/manuscripts/raw/` yourself. The rest of the
  pipeline (OCR, quality filtering, database, reference building,
  translation) works identically regardless of where the images came
  from — it's all keyed off image files in that folder.

---

## Project layout

```
sanskrit-manuscript-summarizer/
├── app.py                       # Flask web app (Step 3 UI)
├── config.py                    # all thresholds & paths in one place
├── requirements.txt
├── pytest.ini
├── db/
│   └── schema.sql               # manuscripts / vocabulary / grammar_patterns / translations tables
├── data/
│   ├── dictionary/
│   │   ├── seed_dictionary.csv          # 152 hand-verified entries (high trust)
│   │   └── monier_williams_full.csv     # 31,773 entries, auto-converted from the full MW dictionary
│   ├── eval/
│   │   ├── gold_sentences.csv           # 25 hand-written test sentences
│   │   └── reports/                     # timestamped coverage reports from src/evaluate.py
│   └── manuscripts/{raw,good,rejected}/ # manuscript images move through these folders
├── src/
│   ├── database.py               # SQLite helper layer
│   ├── ocr_utils.py              # image preprocessing + Tesseract OCR
│   ├── quality_scorer.py         # good/rejected classification logic
│   ├── fetch_archive_org.py      # Step 1a: bulk-download sample manuscripts
│   ├── ingest_manuscripts.py     # Step 1b: OCR + filter + store in DB
│   ├── dictionary_loader.py      # loads a dictionary CSV into the vocabulary table
│   ├── import_monier_williams.py # converts the full MW TEI-XML dictionary to CSV
│   ├── sandhi_utils.py           # tokenization + stemming heuristics (verb/case/sandhi endings)
│   ├── sandhi_parser.py          # wraps the sanskrit_parser library for real sandhi/compound splitting
│   ├── gloss.py                  # word-by-word glossing: exact -> stemmed -> sandhi -> fuzzy -> none
│   ├── build_reference.py        # Step 2: builds vocab/grammar reference from good corpus
│   ├── translate_summarize.py    # Step 3: gloss -> fluent translation -> summary
│   └── evaluate.py               # runs the gold set, reports coverage by category/match-type
├── tests/                        # 63 pytest tests, isolated temp DB per test
└── templates/                    # Flask HTML templates
```

---

## 1. Setup

**Prerequisites:**
- Python 3.10+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed on your system, with the
  Sanskrit (`san`) or at minimum Hindi (`hin`) trained-data files.
  - Ubuntu/Debian: `sudo apt install tesseract-ocr tesseract-ocr-san tesseract-ocr-hin`
  - macOS: `brew install tesseract tesseract-lang`
  - Windows: install from the [UB-Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki), then set
    `TESSERACT_CMD` in `config.py` (or as an environment variable) to the `tesseract.exe` path.

```bash
cd sanskrit-manuscript-summarizer
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`sanskrit_parser` (real sandhi/compound splitting) is a normal
dependency in `requirements.txt` and installs cleanly via pip on
Linux/macOS/most Windows setups. If it fails to install on your
machine for any reason, everything still works: `src/gloss.py` detects
its absence automatically and falls back to the smaller heuristic
splitter in `sandhi_utils.py`.

The first time you run the translation step with the language-model
polishing option enabled, `transformers` will download the small
`google/flan-t5-base` model (~1GB) — this needs an internet connection
once, then it's cached locally.

---

## 2. Step 1 — Build the manuscript dataset

```bash
# Option A: automatically pull ~100 sample pages from archive.org
python -m src.fetch_archive_org --count 100

# Option B: (or in addition) manually copy your own manuscript images into:
#   data/manuscripts/raw/

# Then run OCR + quality filtering on everything in raw/:
python -m src.ingest_manuscripts
```

This OCRs every image, scores it on:
- Tesseract's average word confidence
- the fraction of characters that are actually Devanagari
- a garbage-token ratio (catches OCR gibberish)
- minimum text length

and moves each file into `data/manuscripts/good/` or
`data/manuscripts/rejected/`, recording everything (including the
rejection reason) in the `manuscripts` table so you can see exactly why
a page was excluded.

Tune the thresholds in `config.py` (`MIN_OCR_CONFIDENCE`,
`MIN_DEVANAGARI_RATIO`, etc.) if too much or too little is passing.

---

## 3. Step 2 — Build the grammar & vocabulary reference

```bash
python -m src.dictionary_loader
python -m src.dictionary_loader --csv data/dictionary/monier_williams_full.csv --source-tag mw_import
python -m src.build_reference
```

**Two dictionaries ship with this project, and loading both is the
normal setup:**

- `data/dictionary/seed_dictionary.csv` — 152 hand-verified common
  words, verbs, and pronouns. Loaded with `source='dictionary_seed'`
  and a small trust boost, so it wins lookup ties.
- `data/dictionary/monier_williams_full.csv` — **31,773 entries**,
  auto-converted from the full scholarly Monier-Williams dictionary
  published as open TEI-XML data by the
  [C-SALT Cologne project](https://github.com/cceh/c-salt_sanskrit_data).
  Loaded with `source='mw_import'`. This conversion (`src/import_monier_williams.py`)
  extracts only top-level entries, strips bibliographic citations, and
  truncates to the first clause to keep glosses short — it's a lossy,
  automated simplification of much richer dictionary entries, not a
  scholarly-grade rendering. Treat it as a large, imperfect,
  auto-generated supplement to the hand-verified seed set, not a
  replacement for it. Want to regenerate or extend it?

  ```bash
  git clone --depth 1 https://github.com/cceh/c-salt_sanskrit_data.git
  python -m src.import_monier_williams --source c-salt_sanskrit_data/sa_en/mw/split --out data/dictionary/monier_williams_full.csv
  ```

`build_reference.py` then:
- tokenizes every good manuscript
- increments frequency counts on vocabulary words it recognizes
- logs frequent-but-unrecognized words as `corpus_derived` entries
  (flagged `(unglossed)`, ready for a human to fill in later)
- detects common case-ending patterns (e.g. `-स्य` = genitive singular)
  among those unrecognized words and logs them to `grammar_patterns`

Every manuscript you add and re-run this on makes the reference set a
little better — that's the intended growth loop.

---

## 4. Step 3 — Translate & summarize

**Command line:**
```bash
python -m src.translate_summarize --text "अहं गच्छामि"
python -m src.translate_summarize --image path/to/page.jpg
python -m src.translate_summarize --manuscript-id 3
python -m src.translate_summarize --text "..." --no-llm   # gloss only, skips model download
```

**Web app:**
```bash
python app.py
```
Then open `http://127.0.0.1:5000`. You can browse manuscripts already in
the database, or go to "Translate" to paste text, upload a new
manuscript image, or reference a manuscript by ID.

Each translation shows:
- the word-by-word gloss (with unmatched words clearly flagged, not
  silently guessed)
- a vocabulary coverage percentage
- a fluent English rewrite (via a small instruction-tuned language
  model smoothing the literal gloss into grammatical English)
- a short summary

---

## Tracking quality over time (the gold evaluation set)

`data/eval/gold_sentences.csv` is a hand-written set of 25 Sanskrit
sentences with reference English translations, across seven categories
of increasing difficulty (`constructed_simple`, `constructed_case`,
`traditional_maxim`, `harder_compound`, `harder_verb_class`,
`harder_case`, `harder_sandhi`). Run it after any change to the
dictionary, stemming rules, or corpus:

```bash
python -m src.evaluate          # print a coverage report
python -m src.evaluate --save   # also save a timestamped JSON report to data/eval/reports/
```

It reports vocabulary coverage overall and by category, a breakdown of
which match strategy resolved each token (exact/stemmed/sandhi/fuzzy),
and exactly which tokens in which sentences are still unglossed --
so improvements are measured, not eyeballed.

**How coverage moved over the course of building this** (each step
verified by re-running the eval, not eyeballed):

| Change | Overall coverage |
|---|---|
| Starter dictionary (150 words), naive sandhi only | 91% |
| + stemming (verb/case endings, anusvara, visarga sandhi) | 94% |
| + real sandhi parser (`sanskrit_parser`), neuter-case fix | 98% |
| + bare-imperative-stem recovery | 99% |
| + full Monier-Williams dictionary (31,773 entries) | 100% (on the original 20-sentence set) |
| 5 harder sentences added (compounds, dual verbs, vowel sandhi) | 97% (25-sentence set) |

**Known remaining gaps** in the current 25-sentence set, intentionally
left in as the next roadmap items rather than special-cased away:
- dual-number verb forms (only singular/plural person endings are
  handled in `VERB_PERSON_ENDINGS`)
- vowel sandhi (e.g. `तथा + एव` → `तथैव`) -- covered by neither the
  heuristic pattern list nor consistently by the real parser
- instrumental plural noun case (`-भिः`) isn't in `NOUN_CASE_ENDINGS`
- compound-member stems (the first half of a compound often has no
  case ending at all, which the stemmer doesn't specifically model)

## Running the tests

```bash
python -m pytest tests/ -v
```

The test suite (63 tests, `tests/`) covers the parts of the pipeline
that don't require OCR/ML dependencies to be installed: quality
scoring, tokenization/sandhi/stemming heuristics, the database layer,
the full gloss-matching priority chain (exact → stemmed → sandhi →
fuzzy → unglossed), the real sandhi parser integration (skipped
automatically if `sanskrit_parser` isn't installed), the evaluation
harness, and the Monier-Williams TEI importer (against a small
synthetic fixture, not the full 178MB source repo). Each test gets its
own throwaway SQLite database (`tests/conftest.py`), so running the
suite never touches your real `db/manuscripts.sqlite3`.

---

## Word-lookup strategy (how gloss matching actually works)

`src/gloss.py` tries several strategies in order and tags every result
with which one fired, so the UI never presents a guess as a certainty:

1. **exact** — surface form is directly in the vocabulary table
2. **stemmed** — one or more transformations (chained up to 2 deep) are
   tried to recover a citation form: verb-person endings (`-ामि`,
   `-न्ति`, ...), noun case endings tried against both masculine and
   neuter nominative reconstructions (`-स्य`, `-ेन`, `-े`, ...),
   anusvara/visarga-sandhi normalization, or a bare stem treated as an
   imperative and matched against the present-tense citation form
   (e.g. `गच्छामि` "I go" → `गच्छति` "he/she/it goes"; `गुरुं` needs two
   chained steps to reach `गुरुः`)
3. **sandhi** — real sandhi/compound splitting via the `sanskrit_parser`
   library when installed (falls back to a small heuristic pattern list
   otherwise); a split is only accepted if a resulting piece actually
   resolves to a dictionary meaning
4. **fuzzy** — closest dictionary headword by edit distance, only above
   an 80% similarity floor, for recovering minor OCR errors (e.g.
   `गुरः` → `गुरुः`); always flagged with a similarity score in the note
5. **none** — reported as `(unglossed)`, never fabricated

---

## Honest limitations (please read)

- **This is not a trained Sanskrit machine-translation model.** There
  is no large parallel Sanskrit-English corpus available from ~100
  manuscripts to train one. The translation is **dictionary-grounded
  word-by-word glossing**, smoothed into readable English by a
  general-purpose language model. This is traceable and debuggable
  (you can see exactly which words came from the reference set, by
  which strategy, and which didn't resolve at all) but it will make
  mistakes on forms and words the reference set hasn't seen -- those
  are flagged as `(unglossed)` rather than silently invented. If you
  want a real trained MT model, the
  [ITIHASA dataset](https://github.com/rahular/itihasa) (~93,000
  Sanskrit-English sentence pairs from the Ramayana/Mahabharata) and
  [AI4Bharat's IndicTrans2](https://github.com/AI4Bharat/IndicTrans2)
  (a pretrained model that already supports Sanskrit→English) are the
  right next things to evaluate -- worth benchmarking IndicTrans2
  directly before investing in fine-tuning, and worth keeping this
  project's dictionary-gloss layer either way as an explainability
  feature ("here's what each word means") alongside whichever model
  produces the fluent translation.
- **Sandhi splitting** uses the real `sanskrit_parser` library when
  installed (proper rule-based splitting + word-list lookup), with a
  small heuristic pattern list as fallback. Neither is a complete
  sandhi analyzer -- vowel sandhi in particular isn't reliably covered
  yet (see the gold-set gaps above).
- **OCR quality on handwritten/archaic manuscripts will vary a lot.**
  Tesseract's Sanskrit model works reasonably on clean printed
  Devanagari; handwritten manuscript scans are much harder and will
  push more pages into `rejected/`. That's by design — better to
  reject a noisy page than silently corrupt your reference set with
  garbage.
- **Automated collection is from archive.org, not namami.gov.in**, per
  the ToS note above. Swap in your own manually-collected images at any
  time — the pipeline doesn't care about provenance beyond the
  `source` field it logs.
