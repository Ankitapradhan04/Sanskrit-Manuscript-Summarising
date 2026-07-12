"""
Step 2 of the pipeline.

Builds the "grammar and vocabulary reference" from the manuscripts that
passed quality filtering in Step 1:

  - Tokenizes every 'good' manuscript's OCR text
  - Counts word frequency and bumps corpus_freq on matching vocabulary
    entries (so common, real words rise to the top of future lookups)
  - Adds any frequent-but-unknown tokens to the vocabulary table as
    'corpus_derived' entries (meaning left blank, flagged for review) --
    this is exactly how a growing reference corpus is meant to work:
    each new digitized manuscript makes future translations better.
  - Detects common case-suffix patterns among unknown tokens and logs
    them into grammar_patterns, building a lightweight, data-driven
    grammar sketch (not a substitute for a real grammar, but useful
    scaffolding).

Run this after ingest_manuscripts.py and dictionary_loader.py.

Usage:
    python -m src.build_reference
"""
from collections import Counter

from config import MIN_WORD_FREQ_FOR_GRAMMAR_PATTERN
from src.database import (
    init_db, get_good_manuscripts, lookup_word, upsert_vocab, upsert_pattern,
)
from src.sandhi_utils import tokenize, guess_case_suffix
from src.gloss import invalidate_headword_cache


def main():
    init_db()
    manuscripts = get_good_manuscripts()
    if not manuscripts:
        print("No 'good' manuscripts in the database yet. Run ingest_manuscripts.py first.")
        return

    word_counts = Counter()
    for m in manuscripts:
        for tok in tokenize(m["raw_ocr_text"] or ""):
            if tok:
                word_counts[tok] += 1

    print(f"Found {len(word_counts)} distinct word forms across {len(manuscripts)} good manuscripts.")

    known, unknown = 0, 0
    for word, freq in word_counts.items():
        matches = lookup_word(word)
        if matches:
            # bump the frequency of the existing entry so common real words rank higher
            upsert_vocab(
                headword=word,
                transliteration=matches[0]["transliteration"],
                meaning_en=matches[0]["meaning_en"],
                part_of_speech=matches[0]["part_of_speech"],
                source=matches[0]["source"],
                freq_increment=freq,
            )
            known += 1
        else:
            unknown += 1
            # Log it as an unglossed corpus-derived entry so a human (or a
            # later dictionary import) can fill in the meaning; it's still
            # useful for the grammar-pattern mining below.
            upsert_vocab(
                headword=word,
                transliteration=None,
                meaning_en="(unglossed -- add meaning manually or via a fuller dictionary import)",
                part_of_speech=None,
                source="corpus_derived",
                freq_increment=freq,
            )

            case = guess_case_suffix(word)
            if case and freq >= MIN_WORD_FREQ_FOR_GRAMMAR_PATTERN:
                suffix, desc = case
                upsert_pattern(
                    pattern_type="case_suffix",
                    pattern=suffix,
                    description=desc,
                    example_word=word,
                )

    invalidate_headword_cache()

    print(f"Matched {known} known word forms; logged {unknown} unglossed forms for future review.")
    print("Grammar-pattern mining complete (see the grammar_patterns table).")
    print("\nNext step: python -m src.translate_summarize --text \"...\"  (or run app.py)")


if __name__ == "__main__":
    main()
