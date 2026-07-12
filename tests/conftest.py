"""
Shared test fixtures.

Every test gets its own throwaway SQLite file (never the real
db/manuscripts.sqlite3), so running the test suite can't corrupt your
actual manuscript/vocabulary data.
"""
import os
import sys

# Make sure the project root (parent of tests/) is importable regardless
# of where pytest is invoked from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import src.database as database
from src.dictionary_loader import load_csv
from config import DICT_DIR


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """An empty, freshly-initialized database, isolated to this test."""
    db_path = tmp_path / "test_manuscripts.sqlite3"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    database.init_db()

    # src/gloss.py caches the headword list at module level; make sure
    # each test starts with a clean cache pointed at the temp DB.
    import src.gloss as gloss
    gloss.invalidate_headword_cache()

    yield database
    gloss.invalidate_headword_cache()


@pytest.fixture
def seeded_db(temp_db):
    """temp_db, pre-loaded with the real starter dictionary."""
    csv_path = os.path.join(DICT_DIR, "seed_dictionary.csv")
    load_csv(csv_path)
    import src.gloss as gloss
    gloss.invalidate_headword_cache()
    return temp_db
