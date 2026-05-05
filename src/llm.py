"""Unified LLM interface supporting Claude (Anthropic) and Gemini (Google).

Usage:
    from src.llm import LLMClient
    client = LLMClient(provider="claude")          # or "gemini"
    text = client.complete(system=..., user=...)
"""

from __future__ import annotations

import os
from typing import Literal

Provider = Literal["claude", "gemini"]


class LLMClient:
    def __init__(
        self,
        provider: Provider = "claude",
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.provider = provider
        self.api_key = api_key
        self.model = model or _default_model(provider)
        self._client = self._build_client()

    def complete(self, *, system: str, user: str, max_tokens: int = 8192) -> str:
        if self.provider == "claude":
            return self._complete_claude(system=system, user=user, max_tokens=max_tokens)
        return self._complete_gemini(system=system, user=user, max_tokens=max_tokens)

    # ── Claude ─────────────────────────────────────────────────────────────

    def _complete_claude(self, *, system: str, user: str, max_tokens: int) -> str:
        message = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in message.content if b.type == "text")

    # ── Gemini ─────────────────────────────────────────────────────────────

    def _complete_gemini(self, *, system: str, user: str, max_tokens: int) -> str:
        import google.generativeai as genai  # type: ignore

        model = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system,
            generation_config={"max_output_tokens": max_tokens, "temperature": 0.2},
        )
        response = model.generate_content(user)
        return response.text

    # ── init ───────────────────────────────────────────────────────────────

    def _build_client(self):
        if self.provider == "claude":
            from anthropic import Anthropic
            key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                raise ValueError("ANTHROPIC_API_KEY is not set.")
            return Anthropic(api_key=key)
        else:
            import google.generativeai as genai  # type: ignore
            key = self.api_key or os.environ.get("GEMINI_API_KEY")
            if not key:
                raise ValueError(
                    "GEMINI_API_KEY is not set. "
                    "Get one from https://aistudio.google.com/app/apikey"
                )
            genai.configure(api_key=key)
            return None  # Gemini uses module-level config


def _default_model(provider: Provider) -> str:
    return {
        "claude": "claude-opus-4-7",
        "gemini": "gemini-2.0-flash",
    }[provider]


def from_env() -> LLMClient:
    """Pick provider based on which key is set; prefer Claude."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return LLMClient(provider="claude")
    if os.environ.get("GEMINI_API_KEY"):
        return LLMClient(provider="gemini")
    raise ValueError(
        "No API key found. Set ANTHROPIC_API_KEY or GEMINI_API_KEY in .env"
    )
