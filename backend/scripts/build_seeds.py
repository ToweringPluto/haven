"""Build the offline seed files ``data/seed/<dataset_id>.json`` (and ``data/sql/rent_stats.sql``).

Runs every loader in ``haven.datasets.loaders``. Loaders read only local sources, so this
works with no network. Output is deterministic and a file is rewritten only when its content
changes, so running it twice is a no-op (idempotent). A loader whose raw source isn't present
(e.g. the rents CSV in ``data/raw/``, which is gitignored) is skipped and its committed seed
stays as the fallback.

Usage (from ``backend/``)::

    uv run python scripts/build_seeds.py            # (re)build every seed
    uv run python scripts/build_seeds.py lha_rates  # just one
    uv run python scripts/build_seeds.py --check    # fail if a seed is stale or invalid
"""

from __future__ import annotations

import argparse
import sys

from haven.datasets.loaders import LOADERS, LoaderSourceMissing, rents
from haven.datasets.seeds import load_seed_file, render_seed, seed_path, write_seed


def _write_sql(check: bool) -> bool:
    """Regenerate rent_stats.sql from the committed seed. Returns False if stale (check)."""
    text = rents.render_sql(load_seed_file(rents.DATASET_ID))
    path = rents.SQL_PATH
    current = path.read_text(encoding="utf-8") if path.is_file() else None
    if current == text:
        return True
    if check:
        print(f"stale: {path}", file=sys.stderr)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {path}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("datasets", nargs="*", help=f"subset of: {', '.join(LOADERS)}")
    parser.add_argument("--check", action="store_true", help="validate instead of writing")
    args = parser.parse_args(argv)
    unknown = sorted(set(args.datasets) - set(LOADERS))
    if unknown:
        parser.error(f"unknown dataset(s): {', '.join(unknown)}")
    ok = True
    for dataset_id in args.datasets or LOADERS:
        loader = LOADERS[dataset_id]
        try:
            document = loader.build()
        except LoaderSourceMissing as exc:
            load_seed_file(dataset_id)  # the committed fallback must still be valid
            print(f"skip {dataset_id}: {exc}; keeping committed seed")
            continue
        path = seed_path(dataset_id)
        if args.check:
            current = path.read_text(encoding="utf-8") if path.is_file() else None
            if current != render_seed(document):
                print(f"stale: {path} (re-run scripts/build_seeds.py)", file=sys.stderr)
                ok = False
            continue
        print(f"{'wrote' if write_seed(document) else 'unchanged'} {path}")
    if not args.datasets or rents.DATASET_ID in args.datasets:
        ok = _write_sql(args.check) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
