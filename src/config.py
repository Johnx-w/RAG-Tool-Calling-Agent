"""Load YAML config + .env settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_base_url: str | None = Field(default=None, alias="LLM_BASE_URL")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    embedding_api_key: str = Field(default="", alias="EMBEDDING_API_KEY")
    embedding_base_url: str | None = Field(default=None, alias="EMBEDDING_BASE_URL")
    embedding_model: str = Field(
        default="text-embedding-3-small", alias="EMBEDDING_MODEL"
    )
    chroma_path: str = Field(default="indexes/chroma", alias="CHROMA_PATH")

    def resolved_embedding_key(self) -> str:
        return self.embedding_api_key or self.llm_api_key

    def resolved_embedding_base_url(self) -> str | None:
        return self.embedding_base_url or self.llm_base_url

    def resolved_chroma_path(self) -> Path:
        p = Path(self.chroma_path)
        return p if p.is_absolute() else ROOT / p


def load_yaml_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or (ROOT / "configs" / "default.yaml")
    with cfg_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_config() -> dict[str, Any]:
    return load_yaml_config()
