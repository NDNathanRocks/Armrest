from __future__ import annotations

import base64
import json

import httpx
import pytest

from llm.base import LLMError
from llm.gemini import GeminiClient
from llm.groq import GroqClient
from llm.ollama import OllamaClient


def ollama(handler: httpx.MockTransport) -> OllamaClient:
    return OllamaClient(
        "http://ollama:11434/", "qwen2.5vl:7b", client=httpx.AsyncClient(transport=handler)
    )


async def test_ollama_text_request_and_usage() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["body"] = str(request.url), json.loads(request.content)
        return httpx.Response(
            200,
            json={"message": {"content": '{"a":1}'}, "prompt_eval_count": 120, "eval_count": 7},
        )

    reply = await ollama(httpx.MockTransport(handler)).complete("sys", "hi")
    assert reply.text == '{"a":1}' and (reply.input_tokens, reply.output_tokens) == (120, 7)
    assert reply.system == "ollama" and reply.model == "qwen2.5vl:7b"
    body = seen["body"]
    assert seen["url"] == "http://ollama:11434/api/chat"
    assert isinstance(body, dict) and body["format"] == "json" and body["stream"] is False
    assert body["options"] == {"temperature": 0}


async def test_ollama_sends_image_base64() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"content": "{}"}})

    await ollama(httpx.MockTransport(handler)).complete_with_image("s", "u", b"\x89PNG")
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["messages"][1]["images"] == [base64.b64encode(b"\x89PNG").decode()]


@pytest.mark.parametrize(
    "response", [httpx.Response(500), httpx.Response(200, content=b"not json")]
)
async def test_ollama_errors_become_llmerror(response: httpx.Response) -> None:
    with pytest.raises(LLMError):
        await ollama(httpx.MockTransport(lambda r: response)).complete("s", "u")


async def test_ollama_connection_failure_becomes_llmerror() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(LLMError, match="ConnectError"):
        await ollama(httpx.MockTransport(refuse)).complete("s", "u")


def gemini(handler: httpx.MockTransport, sleeps: list[float]) -> GeminiClient:
    async def sleep(s: float) -> None:
        sleeps.append(s)

    return GeminiClient("key123", client=httpx.AsyncClient(transport=handler), sleep=sleep)


GEMINI_OK = {
    "candidates": [{"content": {"parts": [{"text": '{"ok":true}'}]}}],
    "usageMetadata": {"promptTokenCount": 33, "candidatesTokenCount": 4},
}


async def test_gemini_request_shape_and_parse() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["key"] = request.headers["x-goog-api-key"]
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=GEMINI_OK)

    reply = await gemini(httpx.MockTransport(handler), []).complete_with_image(
        "sys", "find it", b"img"
    )
    assert reply.text == '{"ok":true}' and (reply.input_tokens, reply.output_tokens) == (33, 4)
    assert seen["key"] == "key123" and "key123" not in str(seen["url"])  # key only in the header
    assert str(seen["url"]).endswith("gemini-2.5-flash:generateContent")
    body = seen["body"]
    assert isinstance(body, dict)
    parts = body["contents"][0]["parts"]
    assert parts[1]["inline_data"]["mime_type"] == "image/png"
    assert body["generationConfig"]["responseMimeType"] == "application/json"


async def test_gemini_retries_rate_limits_with_backoff() -> None:
    calls = [0]
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        return httpx.Response(429) if calls[0] < 3 else httpx.Response(200, json=GEMINI_OK)

    reply = await gemini(httpx.MockTransport(handler), sleeps).complete("s", "u")
    assert reply.text and calls[0] == 3 and sleeps == [1.0, 2.0]


async def test_gemini_gives_up_and_does_not_retry_auth_errors() -> None:
    sleeps: list[float] = []
    with pytest.raises(LLMError, match="HTTP 429"):
        await gemini(httpx.MockTransport(lambda r: httpx.Response(429)), sleeps).complete("s", "u")
    assert len(sleeps) == 3
    calls = [0]

    def forbidden(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        return httpx.Response(403)

    with pytest.raises(LLMError, match="HTTP 403"):
        await gemini(httpx.MockTransport(forbidden), []).complete("s", "u")
    assert calls[0] == 1


async def test_gemini_empty_candidates_is_an_error() -> None:
    with pytest.raises(LLMError, match="no candidate"):
        await gemini(
            httpx.MockTransport(lambda r: httpx.Response(200, json={"candidates": []})), []
        ).complete("s", "u")


def groq(handler: httpx.MockTransport, sleeps: list[float]) -> GroqClient:
    async def sleep(s: float) -> None:
        sleeps.append(s)

    return GroqClient("gsk_abc", client=httpx.AsyncClient(transport=handler), sleep=sleep)


GROQ_OK = {
    "choices": [{"message": {"content": '{"ok":true}'}}],
    "usage": {"prompt_tokens": 50, "completion_tokens": 6},
}


async def test_groq_request_shape_and_parse() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=GROQ_OK)

    reply = await groq(httpx.MockTransport(handler), []).complete("sys", "pause it")
    assert reply.text == '{"ok":true}' and (reply.input_tokens, reply.output_tokens) == (50, 6)
    assert reply.system == "groq" and reply.model == "llama-3.3-70b-versatile"
    assert seen["auth"] == "Bearer gsk_abc" and "gsk_abc" not in str(seen["url"])
    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "pause it"},
    ]
    assert body["response_format"] == {"type": "json_object"} and body["temperature"] == 0


async def test_groq_backs_off_once_then_hands_over_quickly() -> None:
    """A backup brain must fail fast: the next provider is waiting."""
    sleeps: list[float] = []
    with pytest.raises(LLMError, match="HTTP 429") as err:
        await groq(httpx.MockTransport(lambda r: httpx.Response(429)), sleeps).complete("s", "u")
    assert err.value.kind == "rate_limited" and sleeps == [1.0]


@pytest.mark.parametrize(
    ("status", "kind"), [(401, "bad_key"), (403, "bad_key"), (400, "unavailable")]
)
async def test_groq_does_not_retry_client_errors(status: int, kind: str) -> None:
    calls = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        return httpx.Response(status)

    with pytest.raises(LLMError) as err:
        await groq(httpx.MockTransport(handler), []).complete("s", "u")
    assert err.value.kind == kind and calls[0] == 1


async def test_groq_reply_without_choices_is_an_error() -> None:
    with pytest.raises(LLMError, match="no choice") as err:
        await groq(
            httpx.MockTransport(lambda r: httpx.Response(200, json={"choices": []})), []
        ).complete("s", "u")
    assert err.value.kind == "bad_reply"
