"""Self-repair.

How it works:
  1. Every crash is recorded (in memory + logs/errors.log) with a "signature"
     (error type + component + code location) so repeats can be recognized.
  2. A diagnosis step proposes repair strategies for that kind of error.
  3. Strategies are tried in order of their *learned* success rate for this
     signature - Jarvis learns which fixes actually work.
  4. Health checks run at startup (and on "diagnose"/"heal yourself") and fix
     what they can: broken config, corrupted memory, missing folders, missing
     backups, crashing skills.

Code repair: if a skill keeps crashing and an LLM brain is available, the
healer asks it for a corrected file, compiles it, loads it in isolation and
runs the input that crashed plus the skill's TESTS. Only if all pass is the
original backed up (~/.jarvis/backups/code) and replaced. Otherwise nothing
changes. After repeated crashes the skill is quarantined instead.
"""
from __future__ import annotations

import importlib
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

# Missing modules the healer may pip-install by itself (module -> pip package).
# Anything not on this list is never installed automatically.
ALLOWED_PACKAGES = {
    "anthropic": "anthropic",
    "psutil": "psutil",
    "requests": "requests",
    "yaml": "pyyaml",
    "dateutil": "python-dateutil",
    "pyttsx3": "pyttsx3",
    "speech_recognition": "SpeechRecognition",
}


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    fix: str | None = None   # strategy that can repair it
    warn: bool = False       # not broken, just worth knowing


class SelfHealer:
    def __init__(self, jarvis):
        self.j = jarvis
        self.last_note = ""
        self.repairs: list[str] = []

    # ------------------------------------------------------------------ record
    @staticmethod
    def signature(component: str, exc: BaseException) -> str:
        tb = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ else []
        where = f"{Path(tb[-1].filename).name}:{tb[-1].name}" if tb else "?"
        msg = re.sub(r"\d+", "N", str(exc))[:60]
        return f"{type(exc).__name__}|{component}|{where}|{msg}"

    def record(self, component: str, exc: BaseException, context: dict | None = None, quiet: bool = False) -> int | None:
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        sig = self.signature(component, exc)
        try:
            log = self.j.config.logs / "errors.log"
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {component} {sig}\n{tb}")
        except OSError:
            pass
        mem = getattr(self.j, "memory", None)
        if mem is None:
            return None
        try:
            return mem.log_error(component, type(exc).__name__, str(exc)[:500], tb[-4000:], sig)
        except sqlite3.DatabaseError:
            return None

    # --------------------------------------------------------------- diagnose
    def diagnose(self, component: str, exc: BaseException, context: dict) -> list[str]:
        """Rule-based list of strategies that could fix this error."""
        out: list[str] = []
        if isinstance(exc, ModuleNotFoundError) and (exc.name or "").split(".")[0] in ALLOWED_PACKAGES:
            out.append("install_package")
        if isinstance(exc, sqlite3.DatabaseError):
            out.append("restore_memory")
        if isinstance(exc, (FileNotFoundError, NotADirectoryError, PermissionError)):
            out.append("recreate_dirs")
        if component == "config":
            out.append("reset_config")
        if component.startswith("skill:"):
            # One crash may be a fluke; from the second one we try to repair the code,
            # and after `quarantine_after` crashes the skill is switched off.
            crashes = self._recent_crashes(component)
            if crashes >= 2 or context.get("stage") == "load":
                out.append("repair_code")
            if crashes >= int(self.j.config["quarantine_after"]):
                out.append("quarantine_skill")
        return out

    def _recent_crashes(self, component: str) -> int:
        try:
            return self.j.memory.error_count(component, since=time.time() - 24 * 3600)
        except Exception:
            return 0

    # -------------------------------------------------------------------- heal
    def heal(self, component: str, exc: BaseException, context: dict | None = None) -> bool:
        """Try the diagnosed strategies, best-performing first. Returns True if fixed."""
        context = context or {}
        sig = self.signature(component, exc)
        strategies = self.diagnose(component, exc, context)
        if not strategies:
            self.last_note = ""
            return False
        try:
            ranking = self.j.memory.fix_ranking(sig)
        except Exception:
            ranking = {}
        # Learned success rate first; the rule order breaks ties. Quarantine stays last.
        strategies.sort(key=lambda s: (s == "quarantine_skill", -ranking.get(s, 0.5)))
        for name in strategies:
            fn = getattr(self, f"_fix_{name}")
            try:
                ok, note = fn(component, exc, context)
            except Exception as fix_exc:   # a failing fix must never crash Jarvis
                ok, note = False, f"{name} failed: {fix_exc}"
            try:
                self.j.memory.record_fix(sig, name, ok)
            except Exception:
                pass
            self.last_note = note
            if ok:
                self.repairs.append(note)
                if context.get("error_id"):
                    try:
                        self.j.memory.mark_fixed(context["error_id"], note)
                    except Exception:
                        pass
                # quarantine "fixes" Jarvis but not the skill: report it as not repaired
                return name != "quarantine_skill"
        return False

    # --------------------------------------------------------- fix strategies
    def _fix_install_package(self, component, exc, context):
        mod = (exc.name or "").split(".")[0]
        pkg = ALLOWED_PACKAGES.get(mod)
        if not pkg or not self.j.config["auto_install"]:
            return False, f"missing package {mod} (auto-install is off)"
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", pkg],
                           capture_output=True, text=True, timeout=300)
        importlib.invalidate_caches()
        if r.returncode != 0:
            return False, f"pip install {pkg} failed: {r.stderr.strip()[-200:]}"
        if component.startswith("skill:"):
            self.j.skills.reload(component.split(":", 1)[1])
        return True, f"installed missing package {pkg}"

    def _fix_restore_memory(self, component, exc, context):
        self.j.memory.reopen()
        ok = self.j.memory.integrity_ok()
        note = self.j.memory.recovered_from or "re-opened memory"
        return ok, f"memory repaired: {note}"

    def _fix_recreate_dirs(self, component, exc, context):
        self.j.config.ensure_dirs()
        return True, "recreated data folders"

    def _fix_reset_config(self, component, exc, context):
        moved = self.j.config.reset()
        return True, f"config was invalid; restored defaults (old file saved as {moved.name if moved else '-'})"

    def _fix_quarantine_skill(self, component, exc, context):
        name = component.split(":", 1)[1]
        self.j.skills.quarantine(name)
        return True, (f"skill '{name}' was disabled after repeated crashes "
                      f"(say 'enable skill {name}' to turn it back on)")

    def _fix_repair_code(self, component, exc, context):
        if not self.j.config["allow_code_repair"]:
            return False, "code repair is turned off"
        from .brains import BrainError
        from .skills import compile_skill, load_module

        name = component.split(":", 1)[1]
        skill = self.j.skills.skills.get(name)
        if not skill:
            return False, f"unknown skill {name}"
        source = skill.path.read_text(encoding="utf-8")
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-3000:]
        prompt = (
            "A plugin of my Python assistant crashed. Fix the bug and return the COMPLETE corrected "
            "file in a single ```python code block, nothing else. Keep NAME, PATTERNS, TESTS and the "
            "signature handle(text, match, jarvis). Do not add imports of third-party packages.\n\n"
            f"Input that crashed: {context.get('input', '(during load)')!r}\n\nTraceback:\n{tb}\n\n"
            f"File {skill.path.name}:\n```python\n{source}\n```")
        try:
            reply, brain = self.j.router.ask([{"role": "user", "content": prompt}],
                                             system="You are a careful senior Python engineer.", llm_only=True)
        except BrainError:
            return False, "no AI brain is available to repair the code"
        m = re.search(r"```(?:python)?\s*\n(.*?)```", reply, re.S)
        code = (m.group(1) if m else reply).strip() + "\n"
        try:
            compile(code, skill.path.name, "exec")
        except SyntaxError as e:
            return False, f"proposed fix from {brain} did not compile: {e}"

        # Test the candidate in isolation before touching the real file.
        cand = self.j.config.backups / "code" / f"_candidate_{name}.py"
        cand.write_text(code, encoding="utf-8")
        try:
            module = load_module(cand, f"jarvis_candidate_{name}_{int(time.time() * 1000)}")
            patterns = compile_skill(module)
            inputs = [i for i in [context.get("input")] + list(getattr(module, "TESTS", []) or []) if i]
            from .skills import Skill
            probe = Skill(name=name, path=cand, module=module, patterns=patterns)
            for text in inputs:
                match = probe.match(text)
                if match:
                    module.handle(text, match, self.j)
        except Exception as e:
            return False, f"proposed fix from {brain} failed its tests: {type(e).__name__}: {e}"
        finally:
            cand.unlink(missing_ok=True)

        backup = self.j.config.backups / "code" / f"{skill.path.stem}.{time.strftime('%Y%m%d-%H%M%S')}.py"
        shutil.copy(skill.path, backup)
        skill.path.write_text(code, encoding="utf-8")
        self.j.skills.reload(name)
        return True, f"rewrote skill '{name}' with a fix from {brain} (tests passed; backup: {backup.name})"

    # -------------------------------------------------------- code rollback
    def code_backups(self) -> list[Path]:
        return sorted((self.j.config.backups / "code").glob("*.py"), reverse=True)

    def rollback(self, skill_name: str | None = None) -> list[str]:
        """Restore the newest backup of each repaired skill (or just one)."""
        done, seen = [], set()
        for b in self.code_backups():
            stem = b.name.split(".")[0]
            if stem.startswith("_") or stem in seen or (skill_name and stem != skill_name):
                continue
            seen.add(stem)
            target = next((s.path for s in self.j.skills.skills.values() if s.path.stem == stem), None)
            if target:
                shutil.copy(b, target)
                done.append(f"restored {target.name} from {b.name}")
        self.j.skills.load_all()
        return done

    # --------------------------------------------------------- health checks
    def health_check(self) -> list[Check]:
        c = self.j.config
        checks: list[Check] = []

        try:
            probe = c.home / ".write_test"
            probe.write_text("ok")
            probe.unlink()
            checks.append(Check("data folder", True, str(c.home)))
        except OSError as e:
            checks.append(Check("data folder", False, f"not writable: {e}", "recreate_dirs"))

        if c.load_error:
            checks.append(Check("config", False, f"invalid config.json: {c.load_error}", "reset_config"))
        else:
            checks.append(Check("config", True, "valid"))

        mem = self.j.memory
        if mem.integrity_ok():
            detail = "ok" + (f" ({mem.recovered_from})" if mem.recovered_from else "")
            checks.append(Check("memory", True, detail, warn=bool(mem.recovered_from)))
        else:
            checks.append(Check("memory", False, "database integrity check failed", "restore_memory"))

        backups = mem.list_backups()
        if not backups:
            checks.append(Check("backups", False, "no memory backup yet", "make_backup", warn=True))
        else:
            age_h = (time.time() - backups[0].stat().st_mtime) / 3600
            checks.append(Check("backups", age_h < 48, f"{len(backups)} saved, newest {age_h:.0f}h old",
                                None if age_h < 48 else "make_backup", warn=age_h >= 48))

        free = shutil.disk_usage(c.home).free / 1e6
        checks.append(Check("disk space", free > 200, f"{free:.0f} MB free", warn=free <= 200))

        skills = self.j.skills
        broken = [s for s in skills.skills.values() if s.error]
        for s in broken:
            checks.append(Check(f"skill {s.name}", False, s.error, "repair_skill"))
        if skills.quarantined:
            checks.append(Check("quarantined skills", True, ", ".join(sorted(skills.quarantined)), warn=True))
        checks.append(Check("skills", not broken, f"{len(skills.active())} active / {len(skills.skills)} total"))

        for name, status in self.j.router.status():
            ok = status.startswith("ready")
            checks.append(Check(f"brain {name}", True, status, warn=not ok))
        return checks

    def heal_all(self) -> list[str]:
        notes = []
        for check in self.health_check():
            if check.ok or not check.fix:
                continue
            try:
                if check.fix == "make_backup":
                    notes.append(f"made memory backup {self.j.memory.backup().name}")
                elif check.fix == "repair_skill":
                    name = check.name.split(" ", 1)[1]
                    skill = self.j.skills.reload(name)
                    if skill and skill.error:
                        err = ImportError(skill.error)
                        mnf = re.match(r"ModuleNotFoundError: No module named '([\w\.]+)'", skill.error)
                        if mnf:
                            err = ModuleNotFoundError(skill.error, name=mnf.group(1))
                        if self.heal(f"skill:{name}", err, {"stage": "load", "path": str(skill.path)}):
                            notes.append(self.last_note)
                        elif self.last_note:
                            notes.append(f"could not repair skill {name}: {self.last_note}")
                    else:
                        notes.append(f"skill {name} reloaded fine")
                else:
                    ok, note = getattr(self, f"_fix_{check.fix}")(check.name, RuntimeError(check.detail), {})
                    notes.append(note if ok else f"could not fix {check.name}: {note}")
            except Exception as e:
                self.record("healer", e)
                notes.append(f"repair of {check.name} failed: {e}")
        self.j.router.reset()
        self.repairs.extend(notes)
        return notes

    def startup(self) -> list[str]:
        """Run at boot: repair what is broken, keep a fresh backup."""
        if not self.j.config["auto_heal"]:
            return []
        return self.heal_all()
