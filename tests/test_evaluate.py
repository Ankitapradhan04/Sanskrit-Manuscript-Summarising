from src.evaluate import evaluate


GOLD_SUBSET = [
    {
        "id": "1", "category": "constructed_simple",
        "sanskrit": "गुरुः शिष्यः वनम्",
        "reference_translation": "teacher, student, forest",
    },
    {
        "id": "2", "category": "constructed_case",
        "sanskrit": "अहं गच्छामि",
        "reference_translation": "I go",
    },
]


def test_evaluate_reports_full_coverage_on_known_vocabulary(seeded_db):
    report = evaluate(GOLD_SUBSET, verbose=False)
    assert report["num_sentences"] == 2
    assert report["overall_avg_coverage"] == 1.0
    assert report["coverage_by_category"]["constructed_simple"] == 1.0
    assert report["coverage_by_category"]["constructed_case"] == 1.0


def test_evaluate_flags_unglossed_tokens(seeded_db):
    gold = [{
        "id": "1", "category": "test",
        "sanskrit": "गुरुः झझझझझ",
        "reference_translation": "teacher, (nonsense)",
    }]
    report = evaluate(gold, verbose=False)
    assert report["overall_avg_coverage"] == 0.5
    assert report["per_sentence"][0]["unglossed_tokens"] == ["झझझझझ"]


def test_evaluate_match_type_breakdown_sums_to_total_tokens(seeded_db):
    report = evaluate(GOLD_SUBSET, verbose=False)
    total_tokens = sum(report["match_type_breakdown"].values())
    expected_tokens = sum(len(s["sanskrit"].split()) for s in GOLD_SUBSET)
    assert total_tokens == expected_tokens
