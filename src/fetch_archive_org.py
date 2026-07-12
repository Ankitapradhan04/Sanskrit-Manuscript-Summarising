"""
Bulk-downloads public-domain Sanskrit manuscript page images from
archive.org into data/manuscripts/raw/, ready for ingest_manuscripts.py.

Why archive.org and not namami.gov.in?
---------------------------------------
namami.gov.in (National Mission for Manuscripts / Kritisampada) blocks
automated access via robots.txt, and access to individual manuscripts is
also gated behind institution-specific permissions. Writing a scraper
against it would violate their terms of service. archive.org, by
contrast, exposes a documented, ToS-compliant search + download API for
its public-domain texts, which is what this script uses.

If you have manuscript images you obtained manually (e.g. saved from
namami.gov.in's public viewer for material you've confirmed is free to
use, or your own scans), skip this script entirely and drop the image
files straight into data/manuscripts/raw/, then run ingest_manuscripts.py.

Usage:
    python -m src.fetch_archive_org --count 100
"""
import argparse
import os
import time
import requests
from tqdm import tqdm

from config import RAW_DIR, ARCHIVE_SEARCH_QUERY, ARCHIVE_TARGET_COUNT

SEARCH_URL = "https://archive.org/advancedsearch.php"
METADATA_URL = "https://archive.org/metadata/{identifier}"
DOWNLOAD_URL = "https://archive.org/download/{identifier}/{filename}"

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff")


def search_identifiers(query, rows):
    params = {
        "q": query,
        "fl[]": "identifier",
        "rows": rows,
        "page": 1,
        "output": "json",
    }
    resp = requests.get(SEARCH_URL, params=params, timeout=30)
    resp.raise_for_status()
    docs = resp.json().get("response", {}).get("docs", [])
    return [d["identifier"] for d in docs]


def first_page_image(identifier):
    """Return the filename of one representative page image for an item, if any."""
    resp = requests.get(METADATA_URL.format(identifier=identifier), timeout=30)
    if resp.status_code != 200:
        return None
    files = resp.json().get("files", [])
    images = [f["name"] for f in files if f["name"].lower().endswith(IMAGE_EXTS)]
    if not images:
        return None
    images.sort()
    return images[len(images) // 3]  # a page roughly a third of the way in tends to avoid blank covers


def download(identifier, filename, dest_dir):
    url = DOWNLOAD_URL.format(identifier=identifier, filename=filename)
    resp = requests.get(url, timeout=60, stream=True)
    if resp.status_code != 200:
        return None
    ext = os.path.splitext(filename)[1] or ".jpg"
    out_path = os.path.join(dest_dir, f"{identifier}{ext}")
    with open(out_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=ARCHIVE_TARGET_COUNT)
    parser.add_argument("--query", type=str, default=ARCHIVE_SEARCH_QUERY)
    args = parser.parse_args()

    print(f"Searching archive.org for: {args.query}")
    identifiers = search_identifiers(args.query, rows=args.count * 3)  # over-fetch; not all have usable images
    print(f"Found {len(identifiers)} candidate items.")

    saved = 0
    for ident in tqdm(identifiers, desc="Downloading manuscript pages"):
        if saved >= args.count:
            break
        try:
            fname = first_page_image(ident)
            if not fname:
                continue
            out_path = download(ident, fname, RAW_DIR)
            if out_path:
                saved += 1
            time.sleep(0.5)  # be polite to the API
        except requests.RequestException:
            continue

    print(f"Saved {saved} manuscript page images to {RAW_DIR}")
    print("Next step: python -m src.ingest_manuscripts")


if __name__ == "__main__":
    main()
