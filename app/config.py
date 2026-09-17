"""Runtime configuration for SurvivalAgent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv() -> None:
    dotenv_path = Path(__file__).resolve().parents[1] / ".env"
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    model_name: str = os.getenv("SURVIVAL_AGENT_MODEL", "deepseek-v4-flash")
    llm_base_url: str = os.getenv("SURVIVAL_AGENT_LLM_BASE_URL", "https://api.deepseek.com")
    llm_api_key_env: str = os.getenv("SURVIVAL_AGENT_LLM_API_KEY_ENV", "DEEPSEEK_API_KEY")
    llm_input_cost_per_1m: float = float(os.getenv("SURVIVAL_AGENT_INPUT_COST_PER_1M", "0.14"))
    llm_output_cost_per_1m: float = float(os.getenv("SURVIVAL_AGENT_OUTPUT_COST_PER_1M", "0.28"))
    llm_timeout_seconds: float = float(os.getenv("SURVIVAL_AGENT_LLM_TIMEOUT_SECONDS", "90"))
    llm_max_retries: int = int(os.getenv("SURVIVAL_AGENT_LLM_MAX_RETRIES", "2"))
    llm_retry_backoff_seconds: float = float(
        os.getenv("SURVIVAL_AGENT_LLM_RETRY_BACKOFF_SECONDS", "1.5")
    )
    log_level: str = os.getenv("SURVIVAL_AGENT_LOG_LEVEL", "INFO")
    skills_allow_inspect: bool = _bool_env("SURVIVAL_AGENT_SKILLS_ALLOW_INSPECT", True)
    max_episode_steps: int = 40
    max_memories: int = 20
    retrieved_memories: int = 3


settings = Settings()
