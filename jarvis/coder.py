"""Programming: Jarvis writes code, saves it, runs it and fixes it until it works.

  write   - asks an AI brain for a complete program, saves every file into
            outputs/code/<name>-<time>/
  run     - runs the program (Python) with a time limit and captures the output.
            If it fails and an AI brain is available, the error is sent back to
            the AI, the corrected code is saved (old version kept in .history/)
            and run again - up to `code_fix_attempts` times.
  modify  - applies a change you describe to the current project.

Writing and fixing need an AI brain (Claude, or Ollama - free and local, e.g.
`ollama pull qwen2.5-coder`). Running works offline.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .brains import BrainError
from .office import open_file
from .text import is_arabic

LANG_EXT = {
    "python": ".py", "py": ".py", "python3": ".py", "javascript": ".js", "js": ".js", "node": ".js",
    "typescript": ".ts", "ts": ".ts", "html": ".html", "css": ".css", "java": ".java", "c": ".c",
    "cpp": ".cpp", "c++": ".cpp", "csharp": ".cs", "cs": ".cs", "c#": ".cs", "go": ".go", "rust": ".rs",
    "php": ".php", "ruby": ".rb", "kotlin": ".kt", "swift": ".swift", "bash": ".sh", "sh": ".sh",
    "shell": ".sh", "powershell": ".ps1", "ps1": ".ps1", "bat": ".bat", "sql": ".sql", "json": ".json",
    "yaml": ".yml", "yml": ".yml", "markdown": ".md", "md": ".md", "txt": ".txt", "text": ".txt",
}
FILE_TAG = re.compile(r"^\s*(?:#|//|<!--|--|/\*|;|')\s*file(?:name)?\s*:\s*([\w .\-/\\]+?)\s*(?:-->|\*/)?\s*$", re.I)
BLOCK = re.compile(r"```([\w+#.-]*)[^\n]*\n(.*?)```", re.S)
GUI_IMPORT = re.compile(r"^\s*(?:import|from)\s+(tkinter|turtle|pygame|PyQt\d|PySide\d|kivy|wx)\b", re.M)


@dataclass
class Project:
    folder: Path
    files: list[Path] = field(default_factory=list)
    explanation: str = ""
    brain: str = ""


@dataclass
class RunResult:
    ok: bool
    output: str
    attempts: int = 1
    fixes: list[str] = field(default_factory=list)
    note: str = ""          # 'gui' | 'timeout' | 'needs_input' | 'no_python' | 'opened' | ''


def _lang_words(ar: bool) -> str:
    return "Arabic" if ar else "English"


def parse_files(reply: str, default_stem: str = "main") -> tuple[dict[str, str], str]:
    """Split an AI reply into {filename: code} and the explanation text around the code."""
    files: dict[str, str] = {}
    for i, m in enumerate(BLOCK.finditer(reply)):
        lang, code = m.group(1).lower(), m.group(2)
        lines = code.splitlines()
        name = None
        if lines:
            t = FILE_TAG.match(lines[0])
            if t:
                name = t.group(1).strip()
                lines = lines[1:]
        ext = LANG_EXT.get(lang, ".txt" if lang else ".py")
        if not name:
            name = f"{default_stem}{ext}" if i == 0 else f"{default_stem}_{i + 1}{ext}"
        name = Path(name.replace("\\", "/")).name or f"file{i + 1}{ext}"   # never leave the folder
        files[name] = "\n".join(lines).rstrip() + "\n"
    explanation = BLOCK.sub("", reply).strip()
    return files, re.sub(r"\n{3,}", "\n\n", explanation)


def _slug(text: str) -> str:
    words = re.findall(r"\w+", text, re.UNICODE)
    drop = {"اكتب", "لي", "برنامج", "كود", "سكربت", "سوي", "اعمل", "برمج", "write", "me", "a", "an",
            "the", "program", "code", "script", "create", "make", "build", "that", "which", "يقوم", "يسوي"}
    keep = [w for w in words if w.lower() not in drop][:5]
    return ("-".join(keep) or "program")[:40]


class Coder:
    def __init__(self, jarvis):
        self.j = jarvis

    # ---- state -------------------------------------------------------------
    @property
    def root(self) -> Path:
        p = self.j.config.outputs / "code"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def current(self) -> Path | None:
        last = self.j.config.get("last_code_project")
        if last and Path(last).is_dir():
            return Path(last)
        projects = sorted((p for p in self.root.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime)
        return projects[-1] if projects else None

    def _ask(self, prompt: str, ar: bool) -> tuple[str, str]:
        system = ("You are an expert software engineer. Write complete, correct, runnable code - never "
                  "placeholders or '...'. Put every file in its own fenced code block tagged with its language, "
                  "and make the FIRST line of each block a comment naming the file, e.g. `# file: main.py` or "
                  "`<!-- file: index.html -->`. Unless the user asks for another language, use Python 3 with the "
                  "standard library only, entry file main.py. Programs must not wait for keyboard input unless "
                  "the user explicitly wants an interactive program; use example values instead. "
                  f"After the code, explain briefly in {_lang_words(ar)} what it does and how to use it.")
        return self.j.router.ask([{"role": "user", "content": prompt}], system=system, llm_only=True)

    def _save(self, folder: Path, files: dict[str, str]) -> list[Path]:
        folder.mkdir(parents=True, exist_ok=True)
        saved = []
        for name, code in files.items():
            path = folder / name
            if path.exists():   # keep the previous version
                hist = folder / ".history"
                hist.mkdir(exist_ok=True)
                shutil.copy2(path, hist / f"{path.stem}.{time.strftime('%H%M%S')}{path.suffix}")
            path.write_text(code, encoding="utf-8")
            saved.append(path)
        return saved

    # ---- write -------------------------------------------------------------
    def write(self, request: str) -> Project:
        ar = is_arabic(request)
        reply, brain = self._ask(f"Request: {request}", ar)   # raises BrainError when no AI brain
        files, explanation = parse_files(reply)
        if not files:
            raise BrainError("the AI reply contained no code")
        folder = self.root / f"{_slug(request)}-{time.strftime('%Y%m%d-%H%M%S')}"
        saved = self._save(folder, files)
        self.j.config.set("last_code_project", str(folder))
        return Project(folder, saved, explanation, brain)

    def modify(self, instruction: str) -> Project:
        folder = self.current()
        if not folder:
            raise FileNotFoundError("no code project yet")
        ar = is_arabic(instruction)
        listing = "\n\n".join(f"```{_lang_for(p.suffix)}\n# file: {p.name}\n{p.read_text(encoding='utf-8')}```"
                              for p in self.source_files(folder))
        reply, brain = self._ask(f"Here is my current project:\n\n{listing}\n\nChange it as follows: {instruction}\n"
                                 "Return every file you change, complete.", ar)
        files, explanation = parse_files(reply, default_stem=self.entry(folder).stem if self.entry(folder) else "main")
        if not files:
            raise BrainError("the AI reply contained no code")
        saved = self._save(folder, files)
        return Project(folder, saved, explanation, brain)

    # ---- run ---------------------------------------------------------------
    @staticmethod
    def source_files(folder: Path) -> list[Path]:
        return sorted(p for p in folder.iterdir() if p.is_file() and not p.name.startswith("."))

    @staticmethod
    def entry(folder: Path) -> Path | None:
        for name in ("main.py", "app.py", "index.html"):
            if (folder / name).exists():
                return folder / name
        py = sorted(folder.glob("*.py"))
        if py:
            return py[0]
        html = sorted(folder.glob("*.html"))
        return html[0] if html else None

    def _command(self, script: Path, out: Path) -> list[str] | None:
        if getattr(sys, "frozen", False):           # Jarvis.exe carries its own Python
            return [sys.executable, "--run-script", str(script), str(out)]
        return [sys.executable, "-m", "jarvis.runner", str(script), str(out)]

    def run_once(self, folder: Path) -> RunResult:
        script = self.entry(folder)
        if script is None:
            return RunResult(False, "no runnable file (main.py / index.html) in the project", note="nothing")
        if script.suffix == ".html":
            open_file(script)
            return RunResult(True, str(script), note="opened")
        if script.suffix != ".py":
            return RunResult(False, f"I can only run Python programs; open {script.name} in its own tool.",
                             note="nothing")
        source = script.read_text(encoding="utf-8", errors="replace")
        out = folder / ".last_output.txt"
        cmd = self._command(script, out)
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        pkg_root = str(Path(__file__).resolve().parent.parent)
        env["PYTHONPATH"] = pkg_root + os.pathsep + env.get("PYTHONPATH", "")
        flags = 0x08000000 if sys.platform == "win32" else 0
        if GUI_IMPORT.search(source):   # windows / games stay open: start them and don't wait
            subprocess.Popen(cmd, cwd=folder, env=env, creationflags=flags)
            return RunResult(True, f"started {script.name}", note="gui")
        try:
            p = subprocess.run(cmd, cwd=folder, env=env, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=int(self.j.config["code_timeout"]), creationflags=flags)
            text = out.read_text(encoding="utf-8", errors="replace") if out.exists() else ""
            text = (text + (p.stdout or "") + (p.stderr or "")).strip()
            ok = p.returncode == 0
        except subprocess.TimeoutExpired:
            text = out.read_text(encoding="utf-8", errors="replace") if out.exists() else ""
            return RunResult(False, text.strip(), note="timeout")
        note = "needs_input" if (not ok and "EOFError" in text) else ""
        return RunResult(ok, text[-4000:], note=note)

    def run(self, folder: Path | None = None, auto_fix: bool = True) -> RunResult:
        folder = folder or self.current()
        if folder is None:
            return RunResult(False, "no code project yet", note="nothing")
        result = self.run_once(folder)
        attempts, fixes = 1, []
        while (not result.ok and auto_fix and result.note == "" and
               attempts <= int(self.j.config["code_fix_attempts"])):
            script = self.entry(folder)
            listing = "\n\n".join(f"```{_lang_for(p.suffix)}\n# file: {p.name}\n"
                                  f"{p.read_text(encoding='utf-8', errors='replace')}```"
                                  for p in self.source_files(folder))
            try:
                reply, brain = self._ask(
                    f"This program fails when I run `{script.name}`.\n\n{listing}\n\nOutput / error:\n"
                    f"```\n{result.output[-3000:]}\n```\nFind the root cause and return the corrected files, "
                    "complete.", is_arabic(result.output))
            except BrainError:
                break
            files, _ = parse_files(reply, default_stem=script.stem)
            if not files:
                break
            self._save(folder, files)
            fixes.append(f"{brain}: {', '.join(files)}")
            attempts += 1
            result = self.run_once(folder)
        result.attempts, result.fixes = attempts, fixes
        return result


def _lang_for(suffix: str) -> str:
    for lang, ext in LANG_EXT.items():
        if ext == suffix:
            return lang
    return ""
