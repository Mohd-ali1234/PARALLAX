"""Application settings, loaded from environment with the PARALLAX_ prefix."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PARALLAX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Runtime ----------------------------------------------------------
    env: Literal["local", "ci", "staging", "prod"] = "local"
    debug: bool = False
    log_level: str = "INFO"
    project_name: str = "PARALLAX"
    api_v1_prefix: str = "/api/v1"

    # --- API --------------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    # Vite dev server. Both the dev proxy and the nginx image serve the app
    # same-origin, so CORS only matters when the frontend is run standalone.
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # --- PostgreSQL -------------------------------------------------------
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "parallax"
    postgres_password: str = "parallax"
    postgres_db: str = "parallax"
    postgres_pool_size: int = 10
    postgres_max_overflow: int = 20
    postgres_echo: bool = False

    # --- Infrastructure ---------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "parallax_claims"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "parallax"
    minio_secret_key: str = "parallax123"
    minio_bucket: str = "parallax-artifacts"
    minio_secure: bool = False

    # --- Models -----------------------------------------------------------
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    llm_provider: Literal["anthropic", "openai", "qwen"] = "anthropic"
    llm_model: str = "claude-sonnet-5"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Async DSN used by the application and Alembic."""
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                path=self.postgres_db,
            )
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_database_url(self) -> str:
        """Sync DSN, for tooling that cannot drive an async driver."""
        return str(
            PostgresDsn.build(
                scheme="postgresql+psycopg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                path=self.postgres_db,
            )
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
