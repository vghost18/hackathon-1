"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_DATA_DIR = Path("data")
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_MODEL_PROVIDER = "openai"


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration that is safe to pass through the app."""

    data_dir: Path
    database_path: Path
    gemini_api_key: str | None
    gemini_model: str
    openai_api_key: str | None
    openai_model: str
    model_provider: str
    local_mode: bool = False
    ms_client_id: str | None = None
    ms_tenant_id: str | None = None
    ms_client_secret: str | None = None
    ms_sender_user: str | None = None

    @property
    def gemini_configured(self) -> bool:
        """Whether a non-empty Gemini key is available for a later phase."""
        return self.gemini_api_key is not None

    @property
    def openai_configured(self) -> bool:
        """Whether a non-empty OpenAI key is available."""
        return self.openai_api_key is not None


def load_settings(data_dir: str | Path | None = None) -> Settings:
    """Load optional environment configuration without validating connectivity."""
    load_dotenv()

    selected_data_dir = Path(data_dir or os.getenv("IDP_DATA_DIR") or DEFAULT_DATA_DIR)
    api_key = os.getenv("GEMINI_API_KEY", "").strip() or None
    model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip() or None
    openai_model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL
    model_provider = (os.getenv("MODEL_PROVIDER", DEFAULT_MODEL_PROVIDER).strip().lower() or DEFAULT_MODEL_PROVIDER)

    return Settings(
        data_dir=selected_data_dir,
        database_path=selected_data_dir / "documind.sqlite3",
        gemini_api_key=api_key,
        gemini_model=model or DEFAULT_GEMINI_MODEL,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        model_provider=model_provider,
        ms_client_id=os.getenv("MS_CLIENT_ID","").strip() or None,
        ms_tenant_id=os.getenv("MS_TENANT_ID","").strip() or None,
        ms_client_secret=os.getenv("MS_CLIENT_SECRET","").strip() or None,
        ms_sender_user=os.getenv("MS_SENDER_USER","").strip() or None,
    )
