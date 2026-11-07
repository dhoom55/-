"""Local LLM brain via Ollama (https://ollama.com) - free, private, no token.

Install Ollama, run `ollama pull llama3.2` (or any model), and Jarvis uses it
automatically whenever Claude is not available.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from .base import Brain, BrainError


class OllamaBrain(Brain):
    name = "ollama"

    def __init__(self, url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.url = url.rstrip("/")
        self.model = model
        self._checked_at = 0.0
        self._up = False

    def _get(self, path: str, timeout: float):
        with urllib.request.urlopen(self.url + path, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def available(self) -> bool:
        # Cache the probe for 30 s so we don't slow every message down.
        if time.time() - self._checked_at < 30:
            return self._up
        self._checked_at = time.time()
        try:
            tags = self._get("/api/tags", timeout=1.5)
            names = [m.get("name", "") for m in tags.get("models", [])]
            if names and not any(n.split(":")[0] == self.model.split(":")[0] for n in names):
                self.model = names[0]   # self-adjust: use whatever model is installed
            self._up = bool(names)
        except (urllib.error.URLError, OSError, ValueError):
            self._up = False
        return self._up

    def status(self) -> str:
        return f"ready ({self.model})" if self.available() else "unavailable (Ollama not running)"

    def ask(self, messages: list[dict], system: str = "") -> str:
        payload = {"model": self.model, "stream": False,
                   "messages": ([{"role": "system", "content": system}] if system else []) + messages}
        req = urllib.request.Request(self.url + "/api/chat", data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            self._checked_at = 0
            raise BrainError(f"ollama failed: {exc}") from exc
        text = (data.get("message") or {}).get("content", "").strip()
        if not text:
            raise BrainError("empty reply from ollama")
        return text
