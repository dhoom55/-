"""Picks a brain for each question and falls back automatically.

Each brain has a circuit breaker: after a failure it is skipped for a cool-down
that doubles with each consecutive failure (30 s -> 10 min max). A success
resets it. The offline brain is always the final fallback.
"""
from __future__ import annotations

import time

from .base import Brain, BrainError


class BrainRouter:
    def __init__(self, brains: list[Brain], healer=None):
        self.brains = brains
        self.healer = healer
        self._fail_count: dict[str, int] = {}
        self._skip_until: dict[str, float] = {}
        self.last_used: str | None = None

    def get(self, name: str) -> Brain | None:
        return next((b for b in self.brains if b.name == name), None)

    def _cooling(self, b: Brain) -> bool:
        return time.time() < self._skip_until.get(b.name, 0)

    def _failed(self, b: Brain, exc: Exception) -> None:
        n = self._fail_count.get(b.name, 0) + 1
        self._fail_count[b.name] = n
        self._skip_until[b.name] = time.time() + min(600, 30 * 2 ** (n - 1))
        if self.healer:
            self.healer.record(f"brain:{b.name}", exc, quiet=True)

    def _ok(self, b: Brain) -> None:
        self._fail_count.pop(b.name, None)
        self._skip_until.pop(b.name, None)

    def reset(self) -> None:
        self._fail_count.clear()
        self._skip_until.clear()

    def ask(self, messages: list[dict], system: str = "", llm_only: bool = False) -> tuple[str, str]:
        """Returns (reply, brain_name). Raises BrainError only if every brain failed."""
        errors = []
        for b in self.brains:
            if llm_only and not b.is_llm:
                continue
            if self._cooling(b):
                continue
            try:
                if not b.available():
                    continue
                reply = b.ask(messages, system)
                self._ok(b)
                self.last_used = b.name
                return reply, b.name
            except Exception as exc:  # any brain crash must not crash Jarvis
                errors.append(f"{b.name}: {exc}")
                self._failed(b, exc)
        raise BrainError("no brain could answer: " + " | ".join(errors) if errors else "no brain available")

    def status(self) -> list[tuple[str, str]]:
        out = []
        for b in self.brains:
            s = b.status()
            if self._cooling(b):
                s += f" - cooling down {int(self._skip_until[b.name] - time.time())}s after errors"
            out.append((b.name, s))
        return out
