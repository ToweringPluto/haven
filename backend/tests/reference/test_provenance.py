"""Every committed reference file carries complete, plausible provenance."""

from datetime import date

import yaml

from haven.config import REFERENCE_DIR
from haven.reference import ReferenceMeta, iter_reference_files

REQUIRED_META = set(ReferenceMeta.model_fields)


def test_reference_dir_exists() -> None:
    assert REFERENCE_DIR.is_dir(), f"missing {REFERENCE_DIR}"


def test_no_yml_files() -> None:
    # The loader only reads *.yaml; a .yml file would be silently ignored.
    assert not list(REFERENCE_DIR.glob("*.yml"))


def test_every_reference_file_has_meta() -> None:
    problems: list[str] = []
    for path in iter_reference_files():
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        meta = data.get("meta") if isinstance(data, dict) else None
        if not isinstance(meta, dict):
            problems.append(f"{path.name}: no top-level 'meta' mapping")
            continue
        missing = REQUIRED_META - meta.keys()
        if missing:
            problems.append(f"{path.name}: meta lacks {sorted(missing)}")
        empty = [k for k in REQUIRED_META & meta.keys() if meta[k] in (None, "")]
        if empty:
            problems.append(f"{path.name}: meta has empty {sorted(empty)}")
        retrieved = meta.get("retrieved")
        if not isinstance(retrieved, date):
            problems.append(f"{path.name}: retrieved must be a YYYY-MM-DD date")
        elif retrieved > date.today():
            problems.append(f"{path.name}: retrieved {retrieved} is in the future")
        try:
            ReferenceMeta.model_validate(meta)
        except ValueError as exc:
            problems.append(f"{path.name}: {exc}")
    assert not problems, "\n".join(problems)
