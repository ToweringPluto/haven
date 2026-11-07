"""Runtime settings, read from ``HAVEN_*`` environment variables."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_EXAMPLES_DIR = REPO_ROOT / "contracts" / "examples"
REFERENCE_DIR = REPO_ROOT / "data" / "reference"
SEED_PATH = REPO_ROOT / "data" / "seed" / "properties.yaml"
LOCATION_CACHE_DIR = REPO_ROOT / "data" / "location_cache"
UPLOAD_DIR = REPO_ROOT / "backend" / "var" / "uploads"
UPLOAD_MAX_BYTES = 15 * 1024 * 1024


class QualityThresholds(BaseModel):
    """Image quality gate thresholds (Haven's own heuristics, not an external standard).

    Each check grades a photo ``good`` / ``limited`` / ``poor``; the worst grade wins.
    Blur is the variance of a 3x3 Laplacian on the grayscale image after scaling its longest
    side to ``blur_analysis_side_px``, so it's comparable across photo sizes.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    min_side_px_poor: int = Field(default=224, gt=0, description="Shorter side below = poor.")
    min_side_px_good: int = Field(default=640, gt=0, description="Shorter side below = limited.")
    blur_analysis_side_px: int = Field(default=1024, gt=0)
    blur_variance_poor: float = Field(default=15.0, ge=0, description="Below = poor (blurred).")
    blur_variance_good: float = Field(default=60.0, ge=0, description="Below = limited.")
    dark_level: int = Field(default=16, ge=0, le=255, description="Pixels at or below are dark.")
    bright_level: int = Field(default=240, ge=0, le=255, description="At or above = blown out.")
    clipped_share_poor: float = Field(default=0.6, gt=0, le=1, description="Above = poor.")
    clipped_share_good: float = Field(default=0.25, gt=0, le=1, description="Above = limited.")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HAVEN_", env_nested_delimiter="__", extra="ignore"
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
    upload_dir: Path = Field(
        default=UPLOAD_DIR,
        description="Where uploaded evidence is stored (HAVEN_UPLOAD_DIR); gitignored.",
    )
    quality: QualityThresholds = Field(
        default_factory=QualityThresholds,
        description="Image quality gate thresholds (HAVEN_QUALITY__<NAME>).",
    )
    upload_max_bytes: int = Field(
        default=UPLOAD_MAX_BYTES, gt=0, description="Largest accepted upload, in bytes."
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
