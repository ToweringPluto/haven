"""Runtime settings, read from ``HAVEN_*`` environment variables."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / "backend" / ".env"
CONTRACT_EXAMPLES_DIR = REPO_ROOT / "contracts" / "examples"
REFERENCE_DIR = REPO_ROOT / "data" / "reference"
SEED_PATH = REPO_ROOT / "data" / "seed" / "properties.yaml"
LOCATION_CACHE_DIR = REPO_ROOT / "data" / "location_cache"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HAVEN_", env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

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
    location_cache_dir: Path = Field(
        default=LOCATION_CACHE_DIR,
        description="Per-property location cache directory (HAVEN_LOCATION_CACHE_DIR).",
    )
    database_url: SecretStr | None = Field(
        default=None,
        description="Postgres connection URL, e.g. the Tiger Cloud service URL "
        "(HAVEN_DATABASE_URL). Unset means no database.",
    )

    # --- Auth0 (signed-in features) -----------------------------------------------------
    auth0_domain: str = Field(
        default="",
        description="Auth0 tenant domain, e.g. haven.eu.auth0.com (HAVEN_AUTH0_DOMAIN). When "
        "empty, signed-in endpoints return 503 and the rest of the API is unaffected.",
    )
    auth0_audience: str = Field(
        default="",
        description="Identifier of the Auth0 API the access tokens are issued for "
        "(HAVEN_AUTH0_AUDIENCE).",
    )
    auth0_email_claim: str = Field(
        default="email",
        description="Access-token claim holding the user's email. Auth0 access tokens only "
        "carry email via a namespaced custom claim added by an Action, e.g. "
        "https://haven.example/email (HAVEN_AUTH0_EMAIL_CLAIM).",
    )

    # --- Limits for signed-in features --------------------------------------------------
    photo_screen_max_bytes: int = Field(
        default=5 * 1024 * 1024, gt=0, description="Largest accepted photo, in bytes."
    )
    photo_screen_rate_limit: int = Field(
        default=10, gt=0, description="Photo screenings allowed per user per window."
    )
    read_aloud_max_chars: int = Field(
        default=5000, gt=0, description="Longest text accepted for read-aloud, in characters."
    )
    read_aloud_rate_limit: int = Field(
        default=30, gt=0, description="Read-aloud requests allowed per user per window."
    )
    rate_limit_window_seconds: int = Field(
        default=3600, gt=0, description="Length of the per-user rate-limit window."
    )

    @property
    def auth_configured(self) -> bool:
        return bool(self.auth0_domain and self.auth0_audience)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
