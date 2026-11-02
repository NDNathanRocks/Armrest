"""Groq (free tier, the user's own key) as a backup brain, over its OpenAI-compatible API.

Text only: the screen reader stays on Gemini / the local vision model. Groq answers in well
under a second, so it sits between Gemini and the local model: it should fail over fast too.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from llm.base import LLMError, LLMReply

_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


class GroqClient:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        *,
        client: httpx.AsyncClient | None = None,
        max_attempts: int = 2,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.AsyncClient(timeout=20.0)
        self._max_attempts = max_attempts
        self._sleep = sleep

    async def complete(self, system: str, user: str) -> LLMReply:
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        last, kind = "no attempts made", "unavailable"
        for attempt in range(self._max_attempts):
            try:
                resp = await self._client.post(_URL, json=body, headers=headers)
            except httpx.HTTPError as exc:
                last = f"network error: {type(exc).__name__}"
                kind = "timeout" if isinstance(exc, httpx.TimeoutException) else "unavailable"
            else:
                if resp.status_code == 200:
                    return self._parse(resp.json())
                last = f"HTTP {resp.status_code}"
                kind = {429: "rate_limited", 401: "bad_key", 403: "bad_key"}.get(
                    resp.status_code, "unavailable"
                )
                if resp.status_code not in (429, 500, 502, 503, 504):
                    break
            if attempt + 1 < self._max_attempts:
                await self._sleep(1.0 * 2**attempt)
        raise LLMError(f"groq request failed: {last}", kind)

    def _parse(self, data: dict[str, Any]) -> LLMReply:
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("groq returned no choice", "bad_reply") from exc
        usage = data.get("usage") or {}
        return LLMReply(
            text=str(text),
            system="groq",
            model=self._model,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
        )
