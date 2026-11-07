"""Claude brain - used only when the Anthropic SDK and credentials exist.

If anything is missing (no `anthropic` package, no key, no internet, a refusal),
it raises BrainError and the router moves on to the next brain. Jarvis never
depends on this brain being present.
"""
from __future__ import annotations

import os
from pathlib import Path

from .base import Brain, BrainError


def _has_credentials() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    # A profile stored by `ant auth login` also works with the SDK.
    return (Path.home() / ".config" / "anthropic").exists()


class ClaudeBrain(Brain):
    name = "claude"

    def __init__(self, model: str = "claude-opus-5-5", effort: str = "medium", max_tokens: int = 16000):
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self._client = None

    def _sdk(self):
        try:
            import anthropic  # optional dependency
            return anthropic
        except ImportError:
            return None

    def available(self) -> bool:
        return self._sdk() is not None and _has_credentials()

    def status(self) -> str:
        if self._sdk() is None:
            return "unavailable (pip install anthropic)"
        if not _has_credentials():
            return "unavailable (no ANTHROPIC_API_KEY)"
        return f"ready ({self.model})"

    def ask(self, messages: list[dict], system: str = "") -> str:
        anthropic = self._sdk()
        if anthropic is None:
            raise BrainError("anthropic package is not installed")
        if not _has_credentials():
            raise BrainError("no Anthropic credentials")
        try:
            if self._client is None:
                self._client = anthropic.Anthropic(timeout=120.0, max_retries=1)
            params = dict(model=self.model, max_tokens=self.max_tokens, messages=messages,
                          output_config={"effort": self.effort})
            if system:
                params["system"] = system
            try:
                # If a safety classifier declines, the API retries on a fallback model.
                response = self._client.beta.messages.create(
                    **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
            except TypeError:
                # Older SDK without the `fallbacks` argument: plain request.
                response = self._client.messages.create(**params)
        except anthropic.AuthenticationError as exc:
            raise BrainError(f"authentication failed: {exc}") from exc
        except anthropic.RateLimitError as exc:
            raise BrainError(f"rate limited: {exc}") from exc
        except anthropic.APIStatusError as exc:
            raise BrainError(f"API error {exc.status_code}: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise BrainError(f"connection failed: {exc}") from exc

        if response.stop_reason == "refusal":
            raise BrainError("request declined")
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if not text:
            raise BrainError("empty reply")
        return text
