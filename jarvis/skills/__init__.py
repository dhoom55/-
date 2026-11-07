"""Skill (plugin) system.

A skill is a .py file that defines:

    NAME = "my_skill"
    PATTERNS = [r"...", ...]          # regexes, matched against normalized text
    def handle(text, match, jarvis):  # returns the reply string
        ...
    TESTS = ["example input", ...]    # optional: inputs that must not crash

Built-in skills live in this folder. Your own skills go in ~/.jarvis/plugins/.
A skill that crashes is handed to the self-healer, which may install a missing
package, ask an LLM brain to repair the code (backed up and tested first), or
quarantine the skill so the rest of Jarvis keeps working.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from ..text import normalize

BUILTIN_DIR = Path(__file__).parent


@dataclass
class Skill:
    name: str
    path: Path
    module: ModuleType | None = None
    patterns: list = field(default_factory=list)
    error: str | None = None  # load error, if any

    @property
    def tests(self) -> list[str]:
        return list(getattr(self.module, "TESTS", []) or [])

    def match(self, text: str):
        """Try the normalized text first, then the raw lower-cased text (keeps + - * / etc.)."""
        for variant in (normalize(text), text.strip().lower()):
            for p in self.patterns:
                m = p.search(variant)
                if m:
                    return m
        return None


def load_module(path: Path, unique: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(unique, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(unique, None)
        raise
    return module


def compile_skill(module: ModuleType) -> list:
    if not callable(getattr(module, "handle", None)):
        raise AttributeError("skill has no handle(text, match, jarvis) function")
    return [re.compile(p, re.IGNORECASE) for p in getattr(module, "PATTERNS", [])]


class SkillManager:
    def __init__(self, jarvis):
        self.jarvis = jarvis
        self.skills: dict[str, Skill] = {}
        self.qfile = jarvis.config.home / "quarantine.json"
        self.quarantined: set[str] = self._load_quarantine()
        self.load_all()

    # ---- quarantine ------------------------------------------------------
    def _load_quarantine(self) -> set[str]:
        try:
            return set(json.loads(self.qfile.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return set()

    def _save_quarantine(self) -> None:
        self.qfile.write_text(json.dumps(sorted(self.quarantined), ensure_ascii=False), encoding="utf-8")

    def quarantine(self, name: str) -> bool:
        if name not in self.skills:
            return False
        self.quarantined.add(name)
        self._save_quarantine()
        return True

    def release(self, name: str) -> bool:
        if name not in self.quarantined:
            return False
        self.quarantined.discard(name)
        self._save_quarantine()
        self.reload(name)
        return True

    # ---- loading -----------------------------------------------------------
    def skill_files(self) -> list[Path]:
        files = sorted(p for p in BUILTIN_DIR.glob("*.py") if not p.name.startswith("_"))
        files += sorted(p for p in self.jarvis.config.plugins.glob("*.py") if not p.name.startswith("_"))
        return files

    def load_all(self) -> None:
        self.skills.clear()
        for path in self.skill_files():
            self._load(path)

    def _load(self, path: Path) -> Skill:
        name = path.stem
        skill = Skill(name=name, path=path)
        try:
            skill.module = load_module(path, f"jarvis_skill_{name}")
            skill.name = getattr(skill.module, "NAME", name)
            skill.patterns = compile_skill(skill.module)
        except Exception as exc:  # a broken plugin must not stop Jarvis from starting
            skill.error = f"{type(exc).__name__}: {exc}"
            self.jarvis.healer.record(f"skill:{skill.name}", exc, context={"stage": "load", "path": str(path)}, quiet=True)
        self.skills[skill.name] = skill
        return skill

    def reload(self, name: str) -> Skill | None:
        skill = self.skills.get(name)
        if not skill:
            return None
        return self._load(skill.path)

    def active(self) -> list[Skill]:
        return [s for s in self.skills.values() if s.module and not s.error and s.name not in self.quarantined]

    # ---- running -----------------------------------------------------------
    def find(self, text: str):
        for s in self.active():
            m = s.match(text)
            if m:
                return s, m
        return None, None

    def run(self, text: str) -> tuple[str, str] | None:
        """Returns (reply, skill_name) or None if no skill matches."""
        skill, match = self.find(text)
        if not skill:
            return None
        for attempt in (1, 2):
            try:
                return str(skill.module.handle(text, match, self.jarvis)), skill.name
            except Exception as exc:
                healer = self.jarvis.healer
                err_id = healer.record(f"skill:{skill.name}", exc, context={"input": text, "path": str(skill.path)})
                fixed = attempt == 1 and healer.heal(f"skill:{skill.name}", exc,
                                                     context={"input": text, "path": str(skill.path), "error_id": err_id})
                if fixed and skill.name not in self.quarantined:
                    skill = self.skills.get(skill.name, skill)
                    match = skill.match(text) or match
                    continue  # retry once with the repaired skill
                return self.jarvis.say(
                    f"واجهت عطلاً في مهارة «{skill.name}» وسجلته. {healer.last_note}",
                    f"The '{skill.name}' skill hit a fault; I've logged it. {healer.last_note}",
                    text), skill.name
        return None
