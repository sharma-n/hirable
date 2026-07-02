from __future__ import annotations

from llm_kit import LLMClient
from llm_kit.config import AppConfig

from app.config import get_config


def build_llm() -> LLMClient:
    """Build an LLMClient from the llm_kit block in config.yaml."""
    return LLMClient(AppConfig.from_dict(get_config()["llm_kit"]))
