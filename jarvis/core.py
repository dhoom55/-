"""Jarvis: ties together memory, learning, skills, brains and self-repair.

How a message is handled:
  1. Teaching / feedback phrases   -> learner
  2. Skills (time, math, notes...) -> skill plugins
  3. Known facts & learned answers -> memory (works offline)
  4. Everything else               -> brains: Claude -> Ollama -> offline
Any crash along the way is caught, recorded and handed to the self-healer.
"""
from __future__ import annotations

import queue
from dataclasses import dataclass
from pathlib import Path

from .brains import BrainError, BrainRouter, build_brains
from .config import Config
from .healing import SelfHealer
from .learning import Learner
from .memory import Memory
from .skills import SkillManager
from .text import is_arabic

PERSONA = """You are {name}, a personal AI assistant: calm, precise, loyal and lightly witty, \
like a highly capable butler who is also an engineer. Address the user as "{title}". \
Reply in the same language the user writes in (Arabic or English); when in Arabic, use \
natural, friendly Arabic. Be concise unless asked for detail.

Things you know about the user and their world (learned from them):
{facts}"""


@dataclass
class Reply:
    text: str
    source: str   # learner | skill:<name> | memory | brain:<name> | error


class Jarvis:
    def __init__(self, home: Path | str | None = None, brains=None):
        self.healer = SelfHealer(self)
        self.config = Config(Path(home) if home else None)
        self.memory = Memory(self.config.home / "memory.db", self.config.backups,
                             keep=int(self.config["backups_to_keep"]))
        self.router = BrainRouter(brains if brains is not None else build_brains(self.config, self.memory),
                                  healer=self.healer)
        self.skills = SkillManager(self)
        self.learner = Learner(self)
        self._voice = None
        self._ai_setup = None
        self._agent_x = None
        self.notifications: "queue.Queue[str]" = queue.Queue()   # background news for the UI
        self.startup_notes = self.healer.startup()

    # ---- language helpers ------------------------------------------------
    def is_ar(self, text: str = "") -> bool:
        lang = self.config["language"]
        return lang == "ar" or (lang == "auto" and is_arabic(text))

    def title(self, text: str = "") -> str:
        t = self.config["user_title"]
        return t if (self.is_ar(text) or not is_arabic(t)) else "sir"

    def say(self, ar: str, en: str, text: str = "") -> str:
        return ar if self.is_ar(text) else en

    # ---- main entry ------------------------------------------------------
    def handle(self, text: str) -> Reply:
        text = (text or "").strip()
        if not text:
            return Reply("", "none")
        try:
            reply = self._handle(text)
        except Exception as exc:   # last line of defence: never die on a message
            err_id = self.healer.record("core", exc, context={"input": text})
            self.healer.heal("core", exc, context={"input": text, "error_id": err_id})
            reply = Reply(self.say("صار عندي عطل داخلي وسجلته، وحاولت أصلحه. جرّب مرة ثانية.",
                                   "I hit an internal fault, logged it and attempted a repair. Please try again.",
                                   text), "error")
        try:
            self.memory.log("user", text)
            self.memory.log("assistant", reply.text, reply.source)
        except Exception as exc:
            self.healer.record("memory", exc)
            self.healer.heal("memory", exc)
        return reply

    def _handle(self, text: str) -> Reply:
        lesson = self.learner.process(text)
        if lesson:
            return Reply(lesson, "learner")

        ran = self.skills.run(text)
        if ran:
            self.learner.remember_exchange(text, None)
            return Reply(ran[0], f"skill:{ran[1]}")

        fact = self.learner.fact_answer(text)
        if fact:
            self.learner.remember_exchange(text, None)
            return Reply(fact, "memory")

        hit = self.memory.recall(text, threshold=float(self.config["recall_threshold"]))
        if hit and hit[0]["source"] == "taught":
            self.learner.remember_exchange(text, hit[0]["id"])
            return Reply(hit[0]["answer"], "memory")

        try:
            answer, brain = self.router.ask(self._messages(text), system=self._system())
        except BrainError:
            # Every brain failed (should not happen: offline never fails) - use memory if we can.
            if hit:
                return Reply(hit[0]["answer"], "memory")
            raise
        qa_id = None
        if self.router.get(brain) and self.router.get(brain).is_llm:
            qa_id = self.learner.learn_from_llm(text, answer)
        elif hit:
            qa_id = hit[0]["id"]
        self.learner.remember_exchange(text, qa_id)
        return Reply(answer, f"brain:{brain}")

    # ---- prompt building -------------------------------------------------
    def _system(self) -> str:
        facts = self.memory.all_facts()[:40]
        lines = "\n".join(f"- {f['key']}: {f['value']}" for f in facts) or "- (nothing yet)"
        return PERSONA.format(name=self.config["name"], title=self.config["user_title"], facts=lines)

    def _messages(self, text: str) -> list[dict]:
        history = []
        for row in self.memory.recent(8):
            role = "user" if row["role"] == "user" else "assistant"
            if history and history[-1]["role"] == role:
                history[-1]["content"] += "\n" + row["text"]
            else:
                history.append({"role": role, "content": row["text"]})
        while history and history[0]["role"] != "user":
            history.pop(0)
        if history and history[-1]["role"] == "user":
            history[-1]["content"] += "\n" + text
        else:
            history.append({"role": "user", "content": text})
        return history

    def notify(self, text: str) -> None:
        """Message from background work (e.g. installing the local AI); the app shows it when it can."""
        self.notifications.put(text)

    def pending_notifications(self) -> list[str]:
        out = []
        while True:
            try:
                out.append(self.notifications.get_nowait())
            except queue.Empty:
                return out

    def has_ai(self) -> bool:
        return any(b.is_llm and b.available() for b in self.router.brains)

    @property
    def ai_setup(self):
        """Installer/activator for the free local AI brain (Ollama)."""
        if self._ai_setup is None:
            from .ai_setup import OllamaSetup
            self._ai_setup = OllamaSetup(self)
        return self._ai_setup

    @property
    def agent_x(self):
        """Agent X: learns what Jarvis doesn't know yet from GitHub."""
        if self._agent_x is None:
            from .agent_x import AgentX
            self._agent_x = AgentX(self)
        return self._agent_x

    @property
    def voice(self):
        """Speech in/out, created on first use."""
        if self._voice is None:
            from .voice import Voice
            self._voice = Voice(self.config, self.healer)
        return self._voice

    def close(self) -> None:
        try:
            self.memory.close()
        except Exception:
            pass
