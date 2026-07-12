"""
Evaluation harness.

Runs the current gloss-matching pipeline (src/gloss.py) against
data/eval/gold_sentences.csv and reports vocabulary coverage, broken
down by category and match strategy. Run this after any change to the
dictionary, stemming rules, or corpus -- it's the "did this actually
help?" check from the project roadmap, instead of eyeballing a few
example sentences.

It does NOT score translation fluency (that would need the LLM
polishing step and a proper metric like BLEU/chrF against the
reference_translation column) -- it measures what's directly
verifiable: whether each word in the gold sentences resolved to a
dictionary meaning, and by which strategy.

Usage:
    python -m src.evaluate
    python -m src.evaluate --save   # also writes a timestamped report to data/eval/reports/
"""
import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime

from config import DATA_DIR
from src.database import init_db
from src.gloss import gloss_text, coverage

GOLD_CSV = os.path.join(DATA_DIR, "eval", "gold_sentences.csv")
REPORTS_DIR = os.path.join(DATA_DIR, "eval", "reports")


def load_gold_set(path=GOLD_CSV):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def evaluate(gold_rows, verbose=True):
    per_sentence = []
    match_type_counts = Counter()
    category_coverage = defaultdict(list)

    for row in gold_rows:
        gloss = gloss_text(row["sanskrit"])
        cov = coverage(gloss)
        for g in gloss:
            match_type_counts[g["match_type"]] += 1
        category_coverage[row["category"]].append(cov)

        per_sentence.append({
            "id": row["id"],
            "category": row["category"],
            "sanskrit": row["sanskrit"],
            "reference_translation": row["reference_translation"],
            "coverage": round(cov, 2),
            "unglossed_tokens": [g["token"] for g in gloss if not g["matched"]],
        })

    overall_coverage = sum(s["coverage"] for s in per_sentence) / len(per_sentence)

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "num_sentences": len(gold_rows),
        "overall_avg_coverage": round(overall_coverage, 3),
        "coverage_by_category": {
            cat: round(sum(vals) / len(vals), 3) for cat, vals in category_coverage.items()
        },
        "match_type_breakdown": dict(match_type_counts),
        "per_sentence": per_sentence,
    }

    if verbose:
        _print_report(report)

    return report


def _print_report(report):
    print(f"Gold set: {report['num_sentences']} sentences")
    print(f"Overall average vocabulary coverage: {report['overall_avg_coverage'] * 100:.0f}%\n")

    print("By category:")
    for cat, cov in report["coverage_by_category"].items():
        print(f"  {cat:<20} {cov * 100:.0f}%")

    print("\nMatch strategy breakdown (across all tokens):")
    total = sum(report["match_type_breakdown"].values())
    for match_type, count in sorted(report["match_type_breakdown"].items(), key=lambda x: -x[1]):
        print(f"  {match_type:<10} {count:>4}  ({count / total * 100:.0f}%)")

    print("\nSentences with unglossed tokens:")
    any_gaps = False
    for s in report["per_sentence"]:
        if s["unglossed_tokens"]:
            any_gaps = True
            print(f"  #{s['id']} ({s['category']}): {', '.join(s['unglossed_tokens'])}")
    if not any_gaps:
        print("  (none)")


def save_report(report):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(REPORTS_DIR, f"eval_{timestamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nSaved report to {path}")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", action="store_true", help="Write a timestamped JSON report")
    parser.add_argument("--gold", type=str, default=GOLD_CSV, help="Path to an alternate gold CSV")
    args = parser.parse_args()

    init_db()
    gold_rows = load_gold_set(args.gold)
    report = evaluate(gold_rows)

    if args.save:
        save_report(report)


if __name__ == "__main__":
    main()
