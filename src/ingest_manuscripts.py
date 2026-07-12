"""
Step 1 of the pipeline.

Walks data/manuscripts/raw/, OCRs every image, scores its quality, and:
  - moves + records 'good' pages into data/manuscripts/good/ and the DB
  - moves + records 'rejected' pages into data/manuscripts/rejected/ and the DB

Run this after populating data/manuscripts/raw/ either via
fetch_archive_org.py or by manually copying image files there.

Usage:
    python -m src.ingest_manuscripts
"""
import os
import shutil
from tqdm import tqdm

from config import RAW_DIR, GOOD_DIR, REJECTED_DIR
from src.database import init_db, insert_manuscript, counts_by_status
from src.ocr_utils import extract_text
from src.quality_scorer import score_manuscript

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp")


def iter_raw_images():
    for fname in sorted(os.listdir(RAW_DIR)):
        if fname.lower().endswith(IMAGE_EXTS):
            yield os.path.join(RAW_DIR, fname)


def ingest_one(path, source="manual_or_archive"):
    text, avg_conf = extract_text(path)
    verdict = score_manuscript(text, avg_conf)

    dest_dir = GOOD_DIR if verdict["status"] == "good" else REJECTED_DIR
    dest_path = os.path.join(dest_dir, os.path.basename(path))
    shutil.move(path, dest_path)

    insert_manuscript(
        source=source,
        source_id=os.path.basename(path),
        file_path=dest_path,
        raw_ocr_text=text,
        avg_confidence=verdict["avg_confidence"],
        devanagari_ratio=verdict["devanagari_ratio"],
        garbage_ratio=verdict["garbage_ratio"],
        char_count=verdict["char_count"],
        status=verdict["status"],
        reject_reason=verdict["reject_reason"],
    )
    return verdict["status"]


def main():
    init_db()
    paths = list(iter_raw_images())
    if not paths:
        print(f"No images found in {RAW_DIR}. Run fetch_archive_org.py or copy scans there first.")
        return

    print(f"Ingesting {len(paths)} manuscript page(s)...")
    for path in tqdm(paths, desc="OCR + quality scoring"):
        try:
            ingest_one(path)
        except Exception as e:
            print(f"  ! Failed on {path}: {e}")

    counts = counts_by_status()
    print("\nIngestion complete.")
    print(f"  good:     {counts.get('good', 0)}")
    print(f"  rejected: {counts.get('rejected', 0)}")
    print("\nNext step: python -m src.build_reference")


if __name__ == "__main__":
    main()
