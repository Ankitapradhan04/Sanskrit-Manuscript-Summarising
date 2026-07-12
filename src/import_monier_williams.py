"""
Converts the full Monier-Williams Sanskrit-English Dictionary (31,821
entries, TEI-P5 XML, SLP1 transliteration) from the C-SALT Cologne
digital dictionary project into the same 4-column CSV format used by
data/dictionary/seed_dictionary.csv, so it can be loaded with
dictionary_loader.py.

Getting the source data
------------------------
This script does NOT download anything itself -- clone the data first:

    git clone --depth 1 https://github.com/cceh/c-salt_sanskrit_data.git
    python -m src.import_monier_williams --source c-salt_sanskrit_data/sa_en/mw/split --out data/dictionary/monier_williams_full.csv

The source repo publishes the dictionary as TEI-XML under a permissive
license for reuse (see the repo's LICENSE and the CCeH/Cologne project
pages) -- this script only reformats it.

What gets extracted
--------------------
Only top-level <entry> elements are converted (31,821 of them, matching
the dictionary's documented entry count) -- nested <re> sub-entries
(~160,000 of them, mostly compounds and minor derived forms) are
skipped to keep the resulting dictionary a manageable size and close to
the "one entry per headword" shape the rest of this project expects.
Headwords are transliterated from SLP1 to Devanagari + IAST. Definition
text has bibliographic <note> references stripped and is truncated to
the first clause, matching the short-gloss style used elsewhere in this
project (this is a lossy simplification of what are often much richer,
multi-sense dictionary entries -- see the original TEI for full detail).

Usage:
    python -m src.import_monier_williams --source path/to/split --out data/dictionary/monier_williams_full.csv
    python -m src.import_monier_williams --source path/to/split --out ... --limit 500   # quick test run
"""
import argparse
import copy
import csv
import glob
import os
import re
import xml.etree.ElementTree as ET

from indic_transliteration import sanscript

TEI_NS = "{http://www.tei-c.org/ns/1.0}"
MAX_MEANING_LENGTH = 150


LEADING_POS_RE = re.compile(r"^(mfn|mf|m|f|n|ind|w)\.\s+")
LEADING_VERB_CLASS_RE = re.compile(
    r"^cl\.\d+\.?\s*(?:[PAU1]\.?\s*)*[A-Za-zĀĪŪṚṜḶḸṂḤŚṢÑṄṆṬḌāīūṛṝḷḹṃḥśṣñṅṇṭḍ0-9/]+,\s*"
)


def _clean_meaning(sense_elem):
    """
    Strip <note> (page refs, cross-references) from a copy of the sense
    element, flatten remaining text, drop a couple of very common
    leading citation patterns (verb conjugation-class examples, a
    redundant part-of-speech abbreviation), and cut to the first clause
    so the result reads like a short dictionary gloss rather than a
    full lexicographic entry with citations.

    This is a deliberately simple cleanup, not a full MW parser -- real
    entries mix definitions with citations, cross-references, and
    etymology in ways that need linguistic judgment to fully untangle.
    Treat the output as a useful, imperfect, auto-generated starting
    point (consistent with how the rest of this project's vocabulary
    reference is meant to grow), not an authoritative gloss.
    """
    sense_copy = copy.deepcopy(sense_elem)
    for note in sense_copy.findall(f"{TEI_NS}note"):
        sense_copy.remove(note)

    text = "".join(sense_copy.itertext())
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip(" ,;:()")

    text = LEADING_VERB_CLASS_RE.sub("", text)
    text = LEADING_POS_RE.sub("", text)
    text = text.strip(" ,;:()")

    # Cut at the first clause boundary within a reasonable length so
    # glosses stay short; fall back to a hard truncation if no good
    # boundary is found.
    for boundary in (";", ". ", ","):
        idx = text.find(boundary)
        if 3 < idx <= MAX_MEANING_LENGTH:
            return text[:idx].strip()
    return text[:MAX_MEANING_LENGTH].strip()


def _part_of_speech(entry_elem):
    gram = entry_elem.find(f".//{TEI_NS}gramGrp/{TEI_NS}gram[@ana='lex']")
    return gram.text.strip() if gram is not None and gram.text else ""


def parse_file(path):
    """Yields (headword_slp1, part_of_speech, meaning) for each top-level entry in one .tei file."""
    tree = ET.parse(path)
    root = tree.getroot()
    body = root.find(f".//{TEI_NS}body")
    if body is None:
        return

    for entry in body.findall(f"{TEI_NS}entry"):
        orth = entry.find(f"{TEI_NS}form/{TEI_NS}orth[@ana='key1']")
        if orth is None or not orth.text:
            continue
        headword_slp1 = orth.text.strip()

        sense = entry.find(f"{TEI_NS}sense")
        if sense is None:
            continue
        meaning = _clean_meaning(sense)
        if not meaning:
            continue

        pos = _part_of_speech(entry)
        yield headword_slp1, pos, meaning


def transliterate(slp1_word):
    devanagari = sanscript.transliterate(slp1_word, sanscript.SLP1, sanscript.DEVANAGARI)
    iast = sanscript.transliterate(slp1_word, sanscript.SLP1, sanscript.IAST)
    return devanagari, iast


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Directory of .tei files (e.g. c-salt_sanskrit_data/sa_en/mw/split)")
    parser.add_argument("--out", required=True, help="Output CSV path")
    parser.add_argument("--limit", type=int, default=None, help="Stop after N entries (for a quick test run)")
    args = parser.parse_args()

    tei_files = sorted(glob.glob(os.path.join(args.source, "*.tei")))
    if not tei_files:
        raise SystemExit(f"No .tei files found in {args.source}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    count, skipped = 0, 0

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["headword", "transliteration", "meaning_en", "part_of_speech"])

        for path in tei_files:
            for headword_slp1, pos, meaning in parse_file(path):
                if args.limit and count >= args.limit:
                    break
                try:
                    devanagari, iast = transliterate(headword_slp1)
                except Exception:
                    skipped += 1
                    continue
                if not devanagari:
                    skipped += 1
                    continue
                writer.writerow([devanagari, iast, meaning, pos])
                count += 1
            if args.limit and count >= args.limit:
                break

    print(f"Wrote {count} entries to {args.out} ({skipped} skipped due to transliteration issues)")


if __name__ == "__main__":
    main()
