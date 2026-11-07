"""Typed loader for reference data files.

Every file in ``data/reference/`` is a YAML mapping with a top-level ``meta`` block::

    meta:
      source_url: https://...      # where the figures were taken from
      retrieved: 2026-11-07        # date they were read (never in the future)
      licence: OGL v3.0            # licence of the source
      notes: How the figures were extracted, caveats.
    ...                            # the data itself

Engines load a file through :func:`load_reference` with a ``ReferenceDocument``
subclass that describes the data, so a malformed or unattributed file fails loudly
instead of feeding silent defaults into a calculation.
"""

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from haven.config import REFERENCE_DIR

SUFFIX = ".yaml"


class ReferenceDataError(Exception):
    """A reference file is missing, unreadable or fails validation."""


class ReferenceMeta(BaseModel):
    """Provenance of a reference file. All four fields are required."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_url: str = Field(
        pattern=r"^https?://\S+$", description="URL the figures were taken from."
    )
    retrieved: date = Field(description="Date the source was read; never in the future.")
    licence: str = Field(min_length=1, description="Licence of the source data.")
    notes: str = Field(min_length=1, description="Extraction method, caveats and known gaps.")

    @model_validator(mode="after")
    def _retrieved_not_in_future(self) -> Self:
        if self.retrieved > date.today():
            raise ValueError(f"retrieved date {self.retrieved} is in the future")
        return self


class ReferenceDocument(BaseModel):
    """Base for a reference file: ``meta`` plus data fields.

    The base class keeps unknown top-level keys (``extra="allow"``) so any file can be
    checked for provenance. Subclasses for specific files should set
    ``model_config = ConfigDict(frozen=True, extra="forbid")`` and declare their fields.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    meta: ReferenceMeta


def iter_reference_files(directory: Path | None = None) -> Iterator[Path]:
    """Yield every ``*.yaml`` file in ``directory`` (default ``data/reference``), sorted."""
    base = REFERENCE_DIR if directory is None else directory
    if not base.is_dir():
        return
    yield from sorted(p for p in base.glob(f"*{SUFFIX}") if p.is_file())


def _read_mapping(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ReferenceDataError(f"reference file not found: {path}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ReferenceDataError(f"{path.name}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ReferenceDataError(f"{path.name}: top level must be a mapping with a 'meta' key")
    return data


def load_reference_file[D: ReferenceDocument](path: Path, model: type[D]) -> D:
    """Load and validate one reference file against ``model``."""
    data = _read_mapping(path)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ReferenceDataError(f"{path.name}: {exc}") from exc


def load_reference[D: ReferenceDocument](
    name: str, model: type[D], *, directory: Path | None = None
) -> D:
    """Load ``<directory>/<name>.yaml`` (``name`` may include the suffix)."""
    base = REFERENCE_DIR if directory is None else directory
    filename = name if name.endswith(SUFFIX) else f"{name}{SUFFIX}"
    return load_reference_file(base / filename, model)


def load_all_references(directory: Path | None = None) -> dict[str, ReferenceDocument]:
    """Load every reference file with the generic schema, keyed by file stem."""
    return {
        path.stem: load_reference_file(path, ReferenceDocument)
        for path in iter_reference_files(directory)
    }
