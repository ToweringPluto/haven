"""Offline seed files: ``data/seed/<dataset_id>.json``.

Each loader writes one seed file so the app runs with no network. The format is::

    {
      "as_of": "2026-04-01",
      "dataset_id": "lha_rates",
      "generated_by": "backend/scripts/build_seeds.py",
      "licence_note": "...",
      "records": [{"...": "...", "is_sample": false}],
      "retrieved_at": "2026-11-07",
      "source_url": "https://..."
    }

Files are rendered deterministically (sorted keys, 2-space indent, LF, no generation
timestamp), so re-running a loader on the same source rewrites nothing: seeding is idempotent.
Every record must carry a boolean ``is_sample`` (``true`` for invented data).
"""

import json
from datetime import date
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from haven.config import SEED_DIR

GENERATED_BY = "backend/scripts/build_seeds.py"


class SeedError(Exception):
    """A seed file is missing, unreadable or fails validation."""


class SeedDocument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    generated_by: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https?://\S+$")
    as_of: date
    retrieved_at: date
    licence_note: str = Field(min_length=1)
    records: list[dict[str, Any]] = Field(min_length=1)

    @model_validator(mode="after")
    def _every_record_flags_sample(self) -> Self:
        for i, record in enumerate(self.records):
            if not isinstance(record.get("is_sample"), bool):
                raise ValueError(f"record {i} lacks a boolean is_sample")
        return self


def seed_path(dataset_id: str, directory: Path | None = None) -> Path:
    return (SEED_DIR if directory is None else directory) / f"{dataset_id}.json"


def render_seed(document: SeedDocument) -> str:
    """Deterministic JSON text for a seed document."""
    data = document.model_dump(mode="json")
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_seed(document: SeedDocument, directory: Path | None = None) -> bool:
    """Write the seed file if its content changed. Returns ``True`` when it wrote."""
    path = seed_path(document.dataset_id, directory)
    text = render_seed(document)
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def load_seed_file(dataset_id: str, directory: Path | None = None) -> SeedDocument:
    """Load and validate ``data/seed/<dataset_id>.json``."""
    path = seed_path(dataset_id, directory)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SeedError(f"seed file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SeedError(f"{path.name}: invalid JSON: {exc}") from exc
    try:
        return SeedDocument.model_validate(data)
    except ValidationError as exc:
        raise SeedError(f"{path.name}: {exc}") from exc


def seed_document(
    dataset_id: str,
    *,
    source_url: str,
    as_of: date,
    retrieved_at: date,
    licence_note: str,
    records: list[dict[str, Any]],
) -> SeedDocument:
    return SeedDocument(
        dataset_id=dataset_id,
        generated_by=GENERATED_BY,
        source_url=source_url,
        as_of=as_of,
        retrieved_at=retrieved_at,
        licence_note=licence_note,
        records=records,
    )
