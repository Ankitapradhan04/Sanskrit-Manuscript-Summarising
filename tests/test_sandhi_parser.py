import pytest

from src.sandhi_parser import real_sandhi_split, SANSKRIT_PARSER_AVAILABLE

pytestmark = pytest.mark.skipif(
    not SANSKRIT_PARSER_AVAILABLE,
    reason="sanskrit_parser is an optional dependency and isn't installed",
)


def test_splits_avagraha_sandhi():
    pieces = real_sandhi_split("रामोऽब्रवीत्")
    assert pieces is not None
    assert len(pieces) == 2


def test_splits_compound_into_known_pieces():
    pieces = real_sandhi_split("गुरुशिष्यौ")
    assert pieces is not None
    assert len(pieces) == 2


def test_returns_none_for_single_word_with_no_junction():
    # "च" is a single indeclinable with nothing to split
    assert real_sandhi_split("च") is None


def test_returns_none_rather_than_raising_on_garbage_input():
    # Should degrade gracefully, not crash the pipeline over bad OCR input
    result = real_sandhi_split("१२३४५")
    assert result is None or isinstance(result, tuple)


def test_results_are_cached(monkeypatch):
    real_sandhi_split.cache_clear()
    real_sandhi_split("रामोऽब्रवीत्")
    info_after_first = real_sandhi_split.cache_info()
    real_sandhi_split("रामोऽब्रवीत्")
    info_after_second = real_sandhi_split.cache_info()
    assert info_after_second.hits == info_after_first.hits + 1
