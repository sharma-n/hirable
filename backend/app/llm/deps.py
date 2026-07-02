from __future__ import annotations

from fastapi import Request
from llm_kit import LLMClient


def get_llm(request: Request) -> LLMClient:
    return request.app.state.llm
