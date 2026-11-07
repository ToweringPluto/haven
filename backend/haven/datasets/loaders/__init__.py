"""One loader per seeded dataset.

Each module exposes ``DATASET_ID`` and ``build() -> SeedDocument``. ``build`` reads only
local sources (committed reference YAML, editable config, constants transcribed from the
official page, or a raw download in ``data/raw/``), never the network, so
``scripts/build_seeds.py`` can run offline. A loader whose raw source is missing raises
:class:`LoaderSourceMissing`; the committed seed then stays as the fallback.
"""

from types import ModuleType

from haven.datasets.loaders import (
    council_tax,
    epc,
    landlord_register,
    lha,
    ofgem_cap,
    rents,
    sample_flats,
)
from haven.datasets.loaders.common import LoaderSourceMissing

LOADERS: dict[str, ModuleType] = {
    m.DATASET_ID: m
    for m in (rents, lha, council_tax, ofgem_cap, epc, sample_flats, landlord_register)
}

__all__ = ["LOADERS", "LoaderSourceMissing"]
