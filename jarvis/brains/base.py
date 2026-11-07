from __future__ import annotations


class BrainError(Exception):
    """A brain could not answer (no credentials, offline, refused, bad reply...)."""


class Brain:
    """Something that turns a conversation into a reply."""

    name = "brain"
    is_llm = True  # False for the rule-based offline brain

    def available(self) -> bool:
        raise NotImplementedError

    def ask(self, messages: list[dict], system: str = "") -> str:
        """messages: [{"role": "user"|"assistant", "content": str}, ...]"""
        raise NotImplementedError

    def status(self) -> str:
        return "ready" if self.available() else "unavailable"
