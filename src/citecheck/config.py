"""Settings from environment variables (and an optional local ``.env`` file). Keys are never in code."""
from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

ENV = {
    "CITECHECK_DATA_DIR": "data_dir",
    "CITECHECK_RESULTS_DIR": "results_dir",
    "CITECHECK_CACHE_DIR": "cache_dir",
    "CITECHECK_CONTACT_EMAIL": "contact_email",
    "CITECHECK_MIN_INTERVAL_S": "min_interval_s",
    "CITECHECK_LLM_PROVIDER": "llm_provider",
    "CITECHECK_LLM_BASE_URL": "llm_base_url",
    "CITECHECK_LLM_MODEL": "llm_model",
    "CITECHECK_LLM_API_KEY": "llm_api_key",
    "CITECHECK_LLM_TIMEOUT_S": "llm_timeout_s",
}


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    data_dir: Path = Path("data")
    results_dir: Path = Path("results")
    cache_dir: Path = Path("data/cache")
    contact_email: str | None = None  # sent to Crossref and OpenAlex as "mailto" (polite pool)
    min_interval_s: float = Field(0.2, ge=0)
    llm_provider: str = "simulated"  # "simulated" or "openai" (any OpenAI-compatible server)
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str | None = Field(default=None, repr=False)
    llm_timeout_s: float = Field(60.0, gt=0)


def load_dotenv(path: str | os.PathLike = ".env") -> list[str]:
    p = Path(path)
    if not p.is_file():
        return []
    loaded = []
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (x.strip() for x in line.split("=", 1))
        if (key in ENV or key == "OPENAI_API_KEY") and value and not os.environ.get(key):
            os.environ[key] = value.strip("\"'")
            loaded.append(key)
    return loaded


def settings_from_env() -> Settings:
    values = {field: os.environ[var] for var, field in ENV.items() if os.environ.get(var)}
    if "llm_api_key" not in values and os.environ.get("OPENAI_API_KEY"):
        values["llm_api_key"] = os.environ["OPENAI_API_KEY"]
    return Settings.model_validate(values)
