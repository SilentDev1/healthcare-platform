from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field


@dataclass(frozen=True)
class ProviderResult:
    """Model output plus token usage for budget/cost telemetry. No prompt text retained."""

    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class ProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    system_prompt: str
    user_prompt: str
    model: str
    max_output_tokens: int = Field(ge=64, le=2000)
    timeout_seconds: float = Field(gt=0, le=60)
    # When set, ask the provider for a strict JSON object matching this schema
    # (OpenAI Responses structured outputs). The result text is then a JSON string.
    json_schema: dict[str, object] | None = None
    schema_name: str = "carevero_intent"


class AIProvider(Protocol):
    async def generate_result(self, request: ProviderRequest) -> ProviderResult: ...

    async def generate(self, request: ProviderRequest) -> str: ...


class OpenAICompatibleProvider:
    """Adapter for OpenAI's Responses API (or any Responses-compatible endpoint).

    Configuration supplies the HTTPS endpoint, model, and secret. The secret is used
    only as a server-side Authorization header and is never logged or returned. No web
    search, tools, or state are enabled; this only turns a prompt into text + usage.
    """

    def __init__(self, *, endpoint: str, api_key: str) -> None:
        if not endpoint.startswith("https://"):
            raise ValueError("AI provider endpoint must use HTTPS")
        if not api_key:
            raise ValueError("AI provider requires an API key")
        self._endpoint = endpoint
        self._api_key = api_key

    def _payload(self, request: ProviderRequest) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": request.model,
            "input": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "max_output_tokens": request.max_output_tokens,
            # NOTE: do NOT send `temperature`. The configured GPT-5.6 reasoning models
            # (Luna/Terra) reject it — "Unsupported parameter: 'temperature' is not
            # supported with this model" (HTTP 400) — confirmed via scripts.diagnose_openai.
            # Determinism does not depend on it: this layer only interprets language, and
            # every candidate is canonical-validated + grounding-guarded downstream.
            "store": False,
        }
        if request.json_schema is not None:
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": request.schema_name,
                    "strict": True,
                    "schema": request.json_schema,
                }
            }
        return payload

    @staticmethod
    def _extract_text(data: dict[str, object]) -> str:
        text = data.get("output_text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        # Fall back to the structured Responses output array.
        output = data.get("output")
        if isinstance(output, list):
            chunks: list[str] = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                for content in item.get("content", []) or []:
                    if isinstance(content, dict) and isinstance(content.get("text"), str):
                        chunks.append(content["text"])
            joined = "".join(chunks).strip()
            if joined:
                return joined
        raise ValueError("AI provider returned no text")

    @staticmethod
    def _usage(data: dict[str, object]) -> tuple[int, int]:
        usage = data.get("usage")
        if isinstance(usage, dict):
            in_tok = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
            out_tok = usage.get("output_tokens") or usage.get("completion_tokens") or 0
            try:
                return int(in_tok), int(out_tok)
            except (TypeError, ValueError):
                return 0, 0
        return 0, 0

    async def generate_result(self, request: ProviderRequest) -> ProviderResult:
        async with httpx.AsyncClient(
            timeout=request.timeout_seconds, follow_redirects=False
        ) as client:
            response = await client.post(
                self._endpoint,
                headers={"authorization": f"Bearer {self._api_key}"},
                json=self._payload(request),
            )
            response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("AI provider returned an unexpected payload")
        text = self._extract_text(data)
        in_tok, out_tok = self._usage(data)
        return ProviderResult(text=text, input_tokens=in_tok, output_tokens=out_tok)

    async def generate(self, request: ProviderRequest) -> str:
        return (await self.generate_result(request)).text


def build_provider(*, endpoint: str | None, api_key: str | None) -> OpenAICompatibleProvider | None:
    """Construct the configured provider, or None when unset (deterministic-only mode)."""
    if not endpoint or not api_key:
        return None
    return OpenAICompatibleProvider(endpoint=endpoint, api_key=api_key)
