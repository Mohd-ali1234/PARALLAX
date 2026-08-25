"""Application settings, loaded from environment with the PARALLAX_ prefix."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py -> core -> parallax -> src -> backend -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PARALLAX_",
        # The one .env lives at the repo root, but backend commands run from
        # backend/ and env_file is CWD-relative. Give both paths; later entries
        # win, so a local .env still overrides. Missing files are ignored.
        env_file=(_REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Runtime ----------------------------------------------------------
    env: Literal["local", "ci", "staging", "prod"] = "local"
    debug: bool = False
    log_level: str = "INFO"
    project_name: str = "PARALLAX Support"
    api_v1_prefix: str = "/api/v1"

    # --- API --------------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # --- LLM --------------------------------------------------------------
    # Any OpenAI-compatible server: Ollama (/v1), LM Studio, llama.cpp, vLLM.
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "qwen2.5-coder:7b"
    llm_api_key: str = "not-needed"  # local servers ignore it, but want the header
    llm_temperature: float = 0.0
    llm_timeout_s: float = 120.0

    # --- Agents -----------------------------------------------------------
    # Hard ceiling on tool-calling rounds per specialist agent, so a model that
    # keeps asking for tools cannot loop forever.
    agent_max_iterations: int = 4

    # Each agent may run on its own model. Blank means "use llm_model", which
    # is the normal setup when you only have one model pulled locally.
    supervisor_model: str = ""
    mobile_model: str = ""
    computer_model: str = ""

    def model_for(self, agent: Literal["supervisor", "mobile", "computer"]) -> str:
        override = {
            "supervisor": self.supervisor_model,
            "mobile": self.mobile_model,
            "computer": self.computer_model,
        }[agent]
        return override or self.llm_model


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
