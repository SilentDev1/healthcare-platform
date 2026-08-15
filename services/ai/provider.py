from __future__ import annotations

from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field


class ProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    system_prompt: str
    user_prompt: str
    model: str
    max_output_tokens: int = Field(ge=64, le=2000)
    timeout_seconds: float = Field(gt=0, le=60)


class AIProvider(Protocol):
    async def generate(self, request: ProviderRequest) -> str: ...


class OpenAICompatibleProvider:
    """Small replaceable provider adapter; configuration supplies URL, model and secret."""

    def __init__(self, *, endpoint: str, api_key: str) -> None:
        if not endpoint.startswith("https://"):
            raise ValueError("AI provider endpoint must use HTTPS")
        self._endpoint = endpoint
        self._api_key = api_key

    async def generate(self, request: ProviderRequest) -> str:
        payload = {
            "model": request.model,
            "input": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "max_output_tokens": request.max_output_tokens,
        }
        async with httpx.AsyncClient(
            timeout=request.timeout_seconds, follow_redirects=False
        ) as client:
            response = await client.post(
                self._endpoint,
                headers={"authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
            response.raise_for_status()
        data = response.json()
        text = data.get("output_text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("AI provider returned no text")
        return text.strip()
