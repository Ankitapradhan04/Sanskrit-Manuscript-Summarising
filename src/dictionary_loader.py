"""
Loads a dictionary CSV into the `vocabulary` table.

By default loads the bundled seed dictionary
(data/dictionary/seed_dictionary.csv, 152 hand-verified entries) with
source='dictionary_seed'. This gives the reference set a reliable
linguistic backbone which build_reference.py then supplements with
frequency statistics mined from your own manuscript corpus.

Want a bigger dictionary? src/import_monier_williams.py converts the
full, scholarly Monier-Williams dictionary (31,821 entries) from the
C-SALT Cologne project into this same CSV format -- see that script's
docstring for how to fetch the source data. Load the result with:

    python -m src.dictionary_loader --csv data/dictionary/monier_williams_full.csv --source-tag mw_import

Loading both is fine and expected: hand-verified seed entries get a
small trust boost (see below) so they're preferred over the much larger
but algorithmically-extracted MW import when both define the same word,
while MW fills in everything the 152-word seed set doesn't cover.

Usage:
    python -m src.dictionary_loader
    python -m src.dictionary_loader --csv path/to/bigger_dictionary.csv --source-tag mw_import
"""
import argparse
import csv
import os

from config import DICT_DIR
from src.database import init_db, upsert_vocab

DEFAULT_CSV = os.path.join(DICT_DIR, "seed_dictionary.csv")

# Hand-verified entries start with a small frequency head start so they
# win lookup_word() ties against unreviewed bulk-imported entries for
# the same headword+meaning combination, rather than ordering being
# arbitrary insertion order.
TRUSTED_SOURCES = {"dictionary_seed"}
TRUST_BOOST = 1


def load_csv(path, source_tag="dictionary_seed"):
    count = 0
    freq_increment = TRUST_BOOST if source_tag in TRUSTED_SOURCES else 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            headword = row["headword"].strip()
            meaning = row["meaning_en"].strip()
            if not headword or not meaning:
                continue
            upsert_vocab(
                headword=headword,
                transliteration=row.get("transliteration", "").strip(),
                meaning_en=meaning,
                part_of_speech=row.get("part_of_speech", "").strip(),
                source=source_tag,
                freq_increment=freq_increment,
            )
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=str, default=DEFAULT_CSV)
    parser.add_argument("--source-tag", type=str, default="dictionary_seed",
                         help="Provenance tag stored on each loaded entry, e.g. 'mw_import'")
    args = parser.parse_args()

    init_db()
    n = load_csv(args.csv, source_tag=args.source_tag)
    print(f"Loaded {n} dictionary entries from {args.csv} (source='{args.source_tag}')")


if __name__ == "__main__":
    main()
