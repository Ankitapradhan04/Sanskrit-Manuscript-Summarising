"""
Central configuration for the Sanskrit Manuscript Summarizer project.
Edit thresholds here rather than hunting through the codebase.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---- Folders -----------------------------------------------------------
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "manuscripts", "raw")        # freshly downloaded/uploaded scans
GOOD_DIR = os.path.join(DATA_DIR, "manuscripts", "good")      # scans that passed the quality filter
REJECTED_DIR = os.path.join(DATA_DIR, "manuscripts", "rejected")
DICT_DIR = os.path.join(DATA_DIR, "dictionary")
DB_PATH = os.path.join(BASE_DIR, "db", "manuscripts.sqlite3")
SCHEMA_PATH = os.path.join(BASE_DIR, "db", "schema.sql")

UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")  # files a user submits via the web app for translation

for d in (RAW_DIR, GOOD_DIR, REJECTED_DIR, DICT_DIR, UPLOAD_DIR, os.path.dirname(DB_PATH)):
    os.makedirs(d, exist_ok=True)

# ---- Tesseract -----------------------------------------------------------
# Point this at the tesseract binary if it isn't on PATH (Windows users especially).
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", None)
OCR_LANG = "san"  # Devanagari-Sanskrit trained data (falls back to "hin" if "san" isn't installed)
OCR_LANG_FALLBACK = "hin"

# ---- Quality-filter thresholds --------------------------------------------
# A manuscript page is kept ("good") only if it clears ALL of these.
MIN_OCR_CONFIDENCE = 55.0        # average Tesseract word confidence (0-100)
MIN_DEVANAGARI_RATIO = 0.75      # fraction of non-space characters that are Devanagari
MIN_TEXT_LENGTH = 40             # minimum number of extracted characters
MAX_GARBAGE_RATIO = 0.15         # fraction of tokens that look like OCR noise (very short/odd tokens)

# ---- Reference builder -----------------------------------------------------
MIN_WORD_FREQ_FOR_GRAMMAR_PATTERN = 3  # how often a suffix must repeat to be logged as a pattern

# ---- archive.org bulk fetch -------------------------------------------------
ARCHIVE_SEARCH_QUERY = 'subject:"sanskrit manuscript" AND mediatype:texts'
ARCHIVE_TARGET_COUNT = 100
