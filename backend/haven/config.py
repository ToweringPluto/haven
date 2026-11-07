"""Runtime settings, read from ``HAVEN_*`` environment variables."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_EXAMPLES_DIR = REPO_ROOT / "contracts" / "examples"
REFERENCE_DIR = REPO_ROOT / "data" / "reference"
SEED_PATH = REPO_ROOT / "data" / "seed" / "properties.yaml"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HAVEN_", extra="ignore")

    cors_origins: str = Field(
        default="",
        description="Comma-separated list of allowed CORS origins (HAVEN_CORS_ORIGINS).",
    )
    backend: Literal["engines", "fixtures"] = Field(
        default="engines",
        description="'engines' (default) serves each endpoint from its real engine where one "
        "exists and from the fixtures otherwise; 'fixtures' serves only the illustrative "
        "persona fixtures (HAVEN_BACKEND).",
    )
    fixtures_dir: Path = Field(
        default=CONTRACT_EXAMPLES_DIR,
        description="Directory the fixture backend reads persona examples from.",
    )
    reference_dir: Path = Field(
        default=REFERENCE_DIR,
        description="Directory holding the reference data YAML files (HAVEN_REFERENCE_DIR).",
    )
    seed_path: Path = Field(
        default=SEED_PATH,
        description="Seed properties file served by the engine backend (HAVEN_SEED_PATH).",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
