"""Runtime settings, read from ``HAVEN_*`` environment variables."""

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
# Local secrets file (gitignored). HAVEN_ENV_FILE overrides it; tests point it at nothing so
# a developer's backend/.env never changes test behaviour.
ENV_FILE = Path(os.environ.get("HAVEN_ENV_FILE") or REPO_ROOT / "backend" / ".env")
CONTRACT_EXAMPLES_DIR = REPO_ROOT / "contracts" / "examples"
REFERENCE_DIR = REPO_ROOT / "data" / "reference"
SEED_DIR = REPO_ROOT / "data" / "seed"
SEED_PATH = SEED_DIR / "properties.yaml"
DATASETS_REGISTRY_PATH = REPO_ROOT / "data" / "datasets.yml"
REFERENCE_JSON_DIR = REPO_ROOT / "data" / "reference_json"
CACHE_DIR = REPO_ROOT / "data" / "cache"
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
        env_prefix="HAVEN_",
        env_nested_delimiter="__",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
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
    datasets_registry_path: Path = Field(
        default=DATASETS_REGISTRY_PATH,
        description="Dataset registry served by GET /v1/data-sources "
        "(HAVEN_DATASETS_REGISTRY_PATH).",
    )
    location_cache_dir: Path = Field(
        default=LOCATION_CACHE_DIR,
        description="Per-property location cache directory (HAVEN_LOCATION_CACHE_DIR).",
    )
    upload_dir: Path = Field(
        default=UPLOAD_DIR,
        description="Where uploaded evidence is stored (HAVEN_UPLOAD_DIR); gitignored.",
    )
    tesseract_cmd: str | None = Field(
        default=None,
        description="Path to the tesseract executable for OCR (HAVEN_TESSERACT_CMD); unset = "
        "look on PATH and in the default Windows install folder.",
    )
    vision_provider: str | None = Field(
        default=None,
        description="Photo screening model provider (HAVEN_VISION_PROVIDER): 'gemini', or "
        "unset for no model (every signal is insufficient_evidence).",
    )
    gemini_api_key: SecretStr | None = Field(
        default=None,
        description="Google Gemini API key (HAVEN_GEMINI_API_KEY), from Google AI Studio. "
        "Needed for HAVEN_VISION_PROVIDER=gemini, HAVEN_REPORT_WORDING=gemini and "
        "HAVEN_READ_ALOUD_PROVIDER=gemini.",
    )
    read_aloud_provider: str | None = Field(
        default=None,
        description="Read-aloud speech provider (HAVEN_READ_ALOUD_PROVIDER): 'gemini', or "
        "unset for none (POST /v1/read-aloud returns 501 and the app uses the browser's own "
        "voice instead).",
    )
    gemini_tts_model: str = Field(
        default="gemini-3.8-flash-lite-tts",
        description="Gemini text-to-speech model used for read-aloud (HAVEN_GEMINI_TTS_MODEL).",
    )
    gemini_tts_voice: str = Field(
        default="Kore",
        description="Prebuilt Gemini voice used for read-aloud (HAVEN_GEMINI_TTS_VOICE).",
    )
    gemini_model: str = Field(
        default="gemini-3.8-flash",
        description="Gemini model used for photo screening and report wording "
        "(HAVEN_GEMINI_MODEL).",
    )
    gemini_timeout_seconds: float = Field(
        default=30.0, gt=0, description="Timeout for one Gemini request, in seconds."
    )
    report_wording: Literal["template", "gemini"] = Field(
        default="template",
        description="How report sentences are worded (HAVEN_REPORT_WORDING): 'template' uses "
        "the findings' own wording; 'gemini' asks Gemini to reword them and keeps the template "
        "if the rewording changes what is cited or sounds more certain than the evidence.",
    )
    quality: QualityThresholds = Field(
        default_factory=QualityThresholds,
        description="Image quality gate thresholds (HAVEN_QUALITY__<NAME>).",
    )
    upload_max_bytes: int = Field(
        default=UPLOAD_MAX_BYTES, gt=0, description="Largest accepted upload, in bytes."
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

    @field_validator(
        "database_url", "gemini_api_key", "vision_provider", "read_aloud_provider", mode="before"
    )
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        """``KEY=""`` (as in .env.example) means "not set", never an empty URL or key."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def auth_configured(self) -> bool:
        return bool(self.auth0_domain and self.auth0_audience)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
