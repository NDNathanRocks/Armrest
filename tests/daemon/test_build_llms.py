"""Which brains answer, in which order, for each set of keys and ARMREST_ROUTER_PROVIDER."""

from __future__ import annotations

from typing import Any

import pytest

from config import Settings
from llm.fallback import FallbackLLM
from llm.gemini import GeminiClient
from llm.groq import GroqClient
from llm.ollama import OllamaClient
from main import build_llms


def chain(llm: Any) -> list[str]:
    providers = llm._providers if isinstance(llm, FallbackLLM) else [llm]
    names = {GeminiClient: "gemini", GroqClient: "groq", OllamaClient: "local"}
    return [names[type(p)] for p in providers]


def settings(**values: Any) -> Settings:
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("keys", "provider", "text", "vision"),
    [
        ({}, "auto", ["local"], ["local"]),
        ({"gemini_api_key": "AIza1"}, "auto", ["gemini", "local"], ["gemini", "local"]),
        ({"groq_api_key": "gsk_1"}, "auto", ["groq", "local"], ["local"]),
        (
            {"gemini_api_key": "AIza1", "groq_api_key": "gsk_1"},
            "auto",
            ["gemini", "groq", "local"],
            ["gemini", "local"],
        ),
        (
            {"gemini_api_key": "AIza1", "groq_api_key": "gsk_1"},
            "groq",
            ["groq", "gemini", "local"],
            ["gemini", "local"],
        ),
        # "This PC only" keeps commands on the PC; a Gemini key still reads the screen
        (
            {"gemini_api_key": "AIza1", "groq_api_key": "gsk_1"},
            "ollama",
            ["local"],
            ["gemini", "local"],
        ),
    ],
)
def test_brain_order(
    keys: dict[str, str], provider: str, text: list[str], vision: list[str]
) -> None:
    router, vlm = build_llms(settings(router_provider=provider, **keys))
    assert chain(router) == text
    assert chain(vlm) == vision


def test_groq_model_can_be_changed() -> None:
    router, _ = build_llms(settings(groq_api_key="gsk_1", groq_text_model="llama-3.1-8b-instant"))
    groq = next(p for p in router._providers if isinstance(p, GroqClient))  # type: ignore[attr-defined]
    assert groq._model == "llama-3.1-8b-instant"


def test_gemini_hands_over_sooner_when_groq_is_behind_it() -> None:
    """Gemini's 1+2+4 s rate-limit backoff would hide the faster backup: retry once, then go."""
    router, _ = build_llms(settings(gemini_api_key="AIza1", groq_api_key="gsk_1"))
    gemini = router._providers[0]  # type: ignore[attr-defined]
    assert isinstance(gemini, GeminiClient) and gemini._max_attempts == 2
    alone, _ = build_llms(settings(gemini_api_key="AIza1"))
    assert alone._providers[0]._max_attempts == 3  # type: ignore[attr-defined]
