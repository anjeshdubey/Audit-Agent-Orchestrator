"""Minimal multi-provider LLM gateway for structured output via Instructor.

Picks the first configured provider in priority order (Groq, Gemini, Together,
Anthropic) unless AUDIT_PROVIDER pins one. Each provider's SDK is imported
lazily, so you only need the SDK for the provider you actually use.

This is the slim spike version. A later phase adds automatic fallback across
the whole chain plus response caching; here we just need one working provider
to prove the extraction-and-verify loop.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

API_KEY_ENV_VARS: dict[str, str] = {
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "together": "TOGETHER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

# Capable-but-cheap first; Anthropic last (most expensive, emergency only).
PROVIDER_PRIORITY: tuple[str, ...] = ("groq", "gemini", "together", "anthropic")

DEFAULT_MODELS: dict[str, str] = {
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-flash-latest",
    "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "anthropic": "claude-sonnet-4-5-20250929",
}

TOGETHER_BASE_URL = "https://api.together.xyz/v1"


class GatewayError(Exception):
    """Raised when no provider is configured or a provider is unknown."""


@dataclass
class GatewayConfig:
    provider: str
    auth_token: str
    model: str

    @classmethod
    def from_env(cls) -> GatewayConfig:
        """Resolve the provider to use from environment variables.

        AUDIT_PROVIDER pins a specific provider; otherwise the first provider
        in PROVIDER_PRIORITY that has an API key set wins.
        """
        pinned = os.environ.get("AUDIT_PROVIDER", "").strip().lower() or None
        if pinned and pinned not in API_KEY_ENV_VARS:
            raise GatewayError(
                f"Unknown AUDIT_PROVIDER '{pinned}'. "
                f"Choose from: {', '.join(sorted(API_KEY_ENV_VARS))}"
            )

        order = (pinned,) if pinned else PROVIDER_PRIORITY
        for provider in order:
            token = os.environ.get(API_KEY_ENV_VARS[provider], "").strip()
            if token:
                model = (
                    os.environ.get("AUDIT_MODEL", "").strip()
                    or DEFAULT_MODELS[provider]
                )
                return cls(provider=provider, auth_token=token, model=model)

        wanted = pinned or "any provider"
        raise GatewayError(
            f"No API key found for {wanted}. Set one of: "
            + ", ".join(API_KEY_ENV_VARS[p] for p in PROVIDER_PRIORITY)
        )


def _instructor_client(config: GatewayConfig) -> Any:
    """Build an Instructor-wrapped client for the configured provider."""
    import instructor

    if config.provider == "anthropic":
        from anthropic import Anthropic

        return instructor.from_anthropic(Anthropic(api_key=config.auth_token))

    if config.provider == "gemini":
        from google import genai

        return instructor.from_genai(
            genai.Client(api_key=config.auth_token),
            mode=instructor.Mode.GENAI_STRUCTURED_OUTPUTS,
        )

    if config.provider == "groq":
        from groq import Groq

        return instructor.from_groq(Groq(api_key=config.auth_token))

    if config.provider == "together":
        from openai import OpenAI

        return instructor.from_openai(
            OpenAI(api_key=config.auth_token, base_url=TOGETHER_BASE_URL)
        )

    raise GatewayError(f"Unknown provider '{config.provider}'")


def extract(
    *,
    response_model: type[T],
    system_prompt: str,
    user_prompt: str,
    config: GatewayConfig | None = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    max_retries: int = 2,
) -> tuple[T, GatewayConfig]:
    """Run a structured-output completion, returning the parsed model + the
    config that served it (so callers can report which provider ran).

    Anthropic takes `system=` as a top-level kwarg; the OpenAI-style providers
    take a "system" role message — Instructor hides most of it but the call
    shape still differs, so branch here.
    """
    config = config or GatewayConfig.from_env()
    client = _instructor_client(config)

    if config.provider == "anthropic":
        result = client.messages.create(
            model=config.model,
            max_tokens=max_tokens,
            temperature=temperature,
            max_retries=max_retries,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            response_model=response_model,
        )
    else:
        result = client.chat.completions.create(
            model=config.model,
            max_tokens=max_tokens,
            temperature=temperature,
            max_retries=max_retries,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=response_model,
        )

    return result, config
