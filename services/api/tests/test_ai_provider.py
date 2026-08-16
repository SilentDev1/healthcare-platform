"""OpenAI Responses adapter: payload shaping, parsing, usage capture, HTTPS enforcement.

No real network or API key: the HTTP round-trip is monkeypatched. Verifies the request
matches the Responses API (system+user input, max_output_tokens, strict json_schema) and
that text + token usage are parsed for budget tracking.
"""

from __future__ import annotations

import asyncio
from typing import cast

import httpx
import pytest

from packages.search.ai_contract import intent_json_schema
from services.ai.provider import (
    OpenAICompatibleProvider,
    ProviderRequest,
    ProviderResult,
    build_provider,
)


def _request(**kw: object) -> ProviderRequest:
    base: dict[str, object] = {
        "system_prompt": "sys",
        "user_prompt": "usr",
        "model": "gpt-5.6-luna",
        "max_output_tokens": 400,
        "timeout_seconds": 10.0,
    }
    base.update(kw)
    return ProviderRequest(**base)


def test_endpoint_must_be_https() -> None:
    with pytest.raises(ValueError):
        OpenAICompatibleProvider(endpoint="http://api.openai.com/v1/responses", api_key="k")


def test_empty_api_key_rejected() -> None:
    with pytest.raises(ValueError):
        OpenAICompatibleProvider(endpoint="https://api.openai.com/v1/responses", api_key="")


def test_build_provider_returns_none_without_config() -> None:
    assert build_provider(endpoint=None, api_key="k") is None
    assert build_provider(endpoint="https://x/y", api_key=None) is None
    assert build_provider(endpoint="https://x/y", api_key="k") is not None


def test_payload_shapes_responses_api_with_json_schema() -> None:
    provider = OpenAICompatibleProvider(endpoint="https://api.openai.com/v1/responses", api_key="k")
    payload = provider._payload(_request(json_schema=intent_json_schema()))
    assert payload["model"] == "gpt-5.6-luna"
    assert payload["max_output_tokens"] == 400
    assert payload["store"] is False
    # Regression: the GPT-5.6 reasoning models reject `temperature` (HTTP 400
    # "Unsupported parameter") — it must NOT be sent. See scripts.diagnose_openai.
    assert "temperature" not in payload
    messages = cast(list[dict[str, str]], payload["input"])
    assert [m["role"] for m in messages] == ["system", "user"]
    text_format = cast(dict[str, dict[str, object]], payload["text"])["format"]
    assert text_format["type"] == "json_schema"
    assert text_format["strict"] is True


def test_payload_never_sends_temperature_even_without_schema() -> None:
    provider = OpenAICompatibleProvider(endpoint="https://api.openai.com/v1/responses", api_key="k")
    payload = provider._payload(_request())
    assert "temperature" not in payload
    assert "text" not in payload  # no structured format unless a schema is requested


def test_parse_output_text_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self: object, url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "output_text": '{"domain":"carevero"}',
                "usage": {"input_tokens": 123, "output_tokens": 45},
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    provider = OpenAICompatibleProvider(endpoint="https://api.openai.com/v1/responses", api_key="k")
    result = asyncio.run(provider.generate_result(_request()))
    assert isinstance(result, ProviderResult)
    assert result.text == '{"domain":"carevero"}'
    assert result.input_tokens == 123
    assert result.output_tokens == 45


def test_parse_output_array_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self: object, url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "output": [{"content": [{"type": "output_text", "text": "hello world"}]}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    provider = OpenAICompatibleProvider(endpoint="https://api.openai.com/v1/responses", api_key="k")
    result = asyncio.run(provider.generate_result(_request()))
    assert result.text == "hello world"
    assert result.input_tokens == 10
    assert result.output_tokens == 2


def test_empty_output_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self: object, url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(200, json={"output_text": "   "}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    provider = OpenAICompatibleProvider(endpoint="https://api.openai.com/v1/responses", api_key="k")
    with pytest.raises(ValueError):
        asyncio.run(provider.generate_result(_request()))
