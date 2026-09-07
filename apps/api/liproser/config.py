from __future__ import annotations

import ipaddress
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "personal"
    personal_mode: bool = True
    app_bind_host: str = "127.0.0.1"
    database_url: str = "postgresql+psycopg://liproser:liproser@127.0.0.1:5432/liproser"
    private_storage_root: Path = Path("data/private")
    redis_url: str = "redis://127.0.0.1:6379/0"
    ai_provider: str = "unconfigured"
    ai_monthly_budget_usd: float = 10.0
    ai_budget_warning_percent: int = 80
    ai_budget_hard_stop: bool = True
    ai_max_request_cost_usd: float = 1.0
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    openai_api_key: str = Field(default="", repr=False)
    openai_model: str = ""
    openai_store_responses: bool = False
    anthropic_api_key: str = Field(default="", repr=False)
    anthropic_model: str = ""
    bootstrap_owner_email: str = "local@liproser.invalid"
    bootstrap_workspace_name: str = "Personal Liproser"
    max_pdf_bytes: int = 10 * 1024 * 1024

    @model_validator(mode="after")
    def validate_personal_mode(self) -> Settings:
        if self.personal_mode:
            if self.app_env.lower() == "production":
                raise ValueError("PERSONAL_MODE cannot run in production")
            try:
                if not ipaddress.ip_address(self.app_bind_host).is_loopback:
                    raise ValueError("PERSONAL_MODE must bind to a loopback address")
            except ValueError as exc:
                if "loopback" in str(exc):
                    raise
                if self.app_bind_host.lower() != "localhost":
                    raise ValueError("PERSONAL_MODE must bind to a loopback address") from exc
        if self.ai_provider not in {"unconfigured", "fake", "ollama", "openai", "anthropic"}:
            raise ValueError("Unsupported AI_PROVIDER")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
