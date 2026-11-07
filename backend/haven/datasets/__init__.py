"""Data layer: the dataset registry (``data/datasets.yml``) and the offline seed files.

- :mod:`haven.datasets.registry` loads and validates the registry, one entry per dataset.
- :mod:`haven.datasets.seeds` reads and writes ``data/seed/<dataset_id>.json``, the
  network-free fallback every loader produces. Every record carries ``is_sample``.
- :mod:`haven.datasets.loaders` holds one loader per P0 dataset; ``scripts/build_seeds.py``
  runs them.
"""

from haven.datasets.registry import (
    DatasetEntry,
    Integration,
    Priority,
    Registry,
    RegistryError,
    load_registry,
)
from haven.datasets.seeds import SeedDocument, SeedError, load_seed_file, render_seed

__all__ = [
    "DatasetEntry",
    "Integration",
    "Priority",
    "Registry",
    "RegistryError",
    "SeedDocument",
    "SeedError",
    "load_registry",
    "load_seed_file",
    "render_seed",
]
