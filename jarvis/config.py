"""Settings for Jarvis.

Everything lives in one data folder (default: ~/.jarvis, or the JARVIS_HOME
environment variable). If config.json is missing or broken, Jarvis falls back
to the defaults below and the self-healer rewrites a clean file.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

DEFAULTS: dict = {
    "name": "Jarvis",
    "user_title": "سيدي",          # how Jarvis addresses you ("sir")
    "language": "auto",            # auto | ar | en
    # The order in which brains are tried. The offline brain is always the
    # last resort, so Jarvis keeps answering with no token and no internet.
    "brain_order": ["claude", "ollama", "offline"],
    "claude_model": "claude-opus-5-5",
    "claude_effort": "medium",     # low | medium | high | xhigh | max
    "claude_max_tokens": 16000,
    "ollama_url": "http://localhost:11434",
    "ollama_model": "qwen2.5:3b",
    "auto_setup_ai": True,         # desktop app: install + start Ollama by itself when no AI brain exists
    "ai_setup_attempted": 0,       # time of the last automatic attempt (retried after a day)
    # Agent X - self-teaching from GitHub
    "agent_x_auto": True,          # desktop app: start Agent X in the background
    "agent_x_interval_hours": 3,   # how often it looks for new things to learn
    "agent_x_daily_limit": 10,     # topics per day (keeps within GitHub's free API limits)
    "agent_x_skills": True,        # may write new skills (safety-checked + tested) for action requests
    # Self-learning
    "learn_from_llm": True,        # cache LLM answers so they work offline later
    "recall_threshold": 0.82,      # how close a question must be to a learned one
    # Self-repair
    "auto_heal": True,             # run health checks and repairs at startup
    "auto_install": True,          # pip-install missing *allow-listed* packages
    "allow_code_repair": True,     # let an LLM brain rewrite a crashing skill (backed up + tested)
    "quarantine_after": 3,         # disable a skill after this many crashes
    "backups_to_keep": 5,
    # Voice
    "speak_replies": False,        # read every reply aloud
    "voice_online": True,          # use natural online voices (edge-tts) when the internet is up
    "listen_language": "ar",       # ar | en  - language for the microphone
    "tts_voice_ar": "ar-SA-HamedNeural",
    "tts_voice_en": "en-GB-RyanNeural",
    "listen_seconds": 8,
    # Files Jarvis creates (documents, presentations, code)
    "outputs_dir": "",             # empty = <data folder>/outputs (or JARVIS_OUTPUTS)
    "open_created_files": True,    # open a new document/presentation automatically
    "code_timeout": 30,            # seconds a program may run
    "code_fix_attempts": 3,        # how many times Jarvis may auto-fix a failing program
}


def data_dir() -> Path:
    return Path(os.environ.get("JARVIS_HOME", Path.home() / ".jarvis")).expanduser()


class Config:
    def __init__(self, home: Path | None = None):
        self.home = Path(home) if home else data_dir()
        self.path = self.home / "config.json"
        self.values: dict = dict(DEFAULTS)
        self.load_error: Exception | None = None
        self.ensure_dirs()
        self.load()

    # ---- folders -------------------------------------------------------
    @property
    def backups(self) -> Path:
        return self.home / "backups"

    @property
    def plugins(self) -> Path:
        return self.home / "plugins"

    @property
    def logs(self) -> Path:
        return self.home / "logs"

    @property
    def outputs(self) -> Path:
        custom = os.environ.get("JARVIS_OUTPUTS") or self.values.get("outputs_dir")
        path = Path(custom).expanduser() if custom else self.home / "outputs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ensure_dirs(self) -> None:
        for p in (self.home, self.backups, self.backups / "code", self.plugins, self.logs):
            p.mkdir(parents=True, exist_ok=True)

    # ---- load / save ---------------------------------------------------
    def load(self) -> None:
        self.values = dict(DEFAULTS)
        if not self.path.exists():
            self.save()
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("config.json must contain a JSON object")
            self.values.update(data)
            self.load_error = None
        except (ValueError, OSError) as exc:  # JSONDecodeError is a ValueError
            # Keep running on defaults; the healer will repair the file.
            self.load_error = exc

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.values, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def reset(self) -> Path | None:
        """Move a broken config aside and write the defaults. Returns the backup path."""
        moved = None
        if self.path.exists():
            moved = self.backups / f"config.broken.{int(time.time())}.json"
            shutil.move(str(self.path), moved)
        self.values = dict(DEFAULTS)
        self.load_error = None
        self.save()
        return moved

    def __getitem__(self, key: str):
        return self.values.get(key, DEFAULTS.get(key))

    def get(self, key: str, default=None):
        return self.values.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value) -> None:
        self.values[key] = value
        self.save()
