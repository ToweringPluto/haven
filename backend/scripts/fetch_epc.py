"""Download and extract the Scottish Government domestic EPC dataset into ``data/raw/epc/``.

The dataset page on data.gov.scot has a single 7z resource. Its download link redirects to a
short-lived signed S3 URL, so the stable URL recorded in ``docs/DATA_SOURCES.md`` is the
data.gov.scot ``.../resource/<id>/download`` link. The publisher replaces the archive every
quarter under the same dataset slug, so the sha256 identifies which release was used.

Usage (from ``backend/``)::

    uv run python scripts/fetch_epc.py             # download if missing, then extract
    uv run python scripts/fetch_epc.py --force     # re-download even if the archive exists
    uv run python scripts/fetch_epc.py --check     # verify the archive hash and the CSVs

Raw files live in ``data/raw/epc/`` (gitignored) and are never committed. Licence: OGL v3.0 for
non-address fields; address fields (ADDRESS1, ADDRESS2, POSTTOWN, POSTCODE) are Royal Mail
copyright. Haven only uses aggregates and never stores addresses.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import httpx
import py7zr

from haven.config import REPO_ROOT

RAW_DIR = REPO_ROOT / "data" / "raw" / "epc"
ARCHIVE = RAW_DIR / "epc_download.7z"
EXTRACT_DIR = RAW_DIR / "extracted"
DATASET_URL = (
    "https://data.gov.scot/dataset/domestic_energy_performance_certificates___dataset_to_q1_2026"
)
DOWNLOAD_URL = f"{DATASET_URL}/resource/5ebad3f5-c40e-4f80-b508-2c69712f0d25/download"
# The release downloaded on 2026-11-07 ("Dataset to Q3 2026", last updated 4 Nov 2026).
EXPECTED_SHA256 = "e6127d8aad4817faf5b0f581bac060c3cbe5dbf7fc6ef95115890d37fd8ebd76"
USER_AGENT = "haven-prototype"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    headers = {"User-Agent": USER_AGENT}
    with httpx.stream(
        "GET", DOWNLOAD_URL, headers=headers, follow_redirects=True, timeout=120
    ) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in resp.iter_bytes(1 << 20):
                fh.write(chunk)
    tmp.replace(dest)


def extract(archive: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with py7zr.SevenZipFile(archive, mode="r") as zf:
        for name in zf.getnames():
            target = (out_dir / name).resolve()
            if not target.is_relative_to(out_dir.resolve()):
                raise SystemExit(f"refusing to extract {name!r}: path escapes {out_dir}")
        zf.extractall(path=out_dir)
    return sorted(out_dir.rglob("*.csv"))


def check() -> int:
    if not ARCHIVE.is_file():
        print(f"missing {ARCHIVE}; run without --check to download", file=sys.stderr)
        return 1
    actual = sha256(ARCHIVE)
    if actual != EXPECTED_SHA256:
        print(
            f"sha256 mismatch for {ARCHIVE.name}: {actual} (expected {EXPECTED_SHA256}). "
            "A new quarterly release? Update EXPECTED_SHA256 and docs/DATA_SOURCES.md.",
            file=sys.stderr,
        )
        return 1
    csvs = sorted(EXTRACT_DIR.rglob("*.csv"))
    if not csvs:
        print(f"no CSVs under {EXTRACT_DIR}; run without --check to extract", file=sys.stderr)
        return 1
    print(f"ok: {ARCHIVE.name} sha256 matches; {len(csvs)} CSV file(s) extracted")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-download the archive")
    parser.add_argument("--check", action="store_true", help="verify only, no network")
    args = parser.parse_args(argv)

    if args.check:
        return check()
    if args.force or not ARCHIVE.is_file():
        print(f"downloading {DOWNLOAD_URL}")
        download(ARCHIVE)
    size = ARCHIVE.stat().st_size
    digest = sha256(ARCHIVE)
    print(f"{ARCHIVE.name}: {size} bytes, sha256 {digest}")
    if digest != EXPECTED_SHA256:
        print("note: sha256 differs from EXPECTED_SHA256 (new release?)", file=sys.stderr)
    for csv in extract(ARCHIVE, EXTRACT_DIR):
        print(f"extracted {csv.relative_to(RAW_DIR)} ({csv.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
