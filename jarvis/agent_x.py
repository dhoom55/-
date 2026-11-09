"""Agent X - Jarvis's self-teaching agent.

Agent X finds what Jarvis doesn't know yet and learns it from GitHub:

  1. Gaps      - questions Jarvis couldn't answer, topics you ask it to study
                 ("تعلم عن ..."), and recurring errors.
  2. Research  - searches GitHub for the best repositories on the topic and downloads
                 their README/documentation (and SKILL.md files, which are written to teach).
  3. Learning  - with an AI brain: turns what it read into question/answer pairs and facts.
                 Without one: keeps a clean summary and the sources.
                 Everything goes into Jarvis's memory, so it is usable offline afterwards.
  4. Skills    - when a gap is an *action* ("convert currency", "translate ..."), the AI writes
                 a new skill plugin. It must pass a safety check (no deleting files, no shell,
                 no eval...) and its own tests in an isolated process before it is installed.

Safety rule: Agent X reads what it downloads; it never runs code downloaded from GitHub.
Runs in the background with a daily limit; reports through jarvis.notify().
Uses $GITHUB_TOKEN when set (higher API limits), otherwise anonymous access.
"""
from __future__ import annotations

import ast
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .text import is_arabic, keywords

API = "https://api.github.com"
GAP_MARKERS = ("للأسف ما أعرف الجواب بعد", "I don't know that yet")
ACTION_WORDS = re.compile(r"^(?:حول|ترجم|احسب|حمل|ابحث|اعرض|افتح|ارسل|convert|translate|download|search|show|open|send|"
                          r"check|get|fetch|calculate)\b", re.I)
# Things a generated skill may never do.
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__", "system", "popen", "remove", "unlink", "rmdir",
                   "rmtree", "removedirs", "kill", "chmod", "chown", "rename", "replace", "truncate", "spawn",
                   "fork", "execv", "execve", "startfile"}
FORBIDDEN_MODULES = {"subprocess", "ctypes", "socket", "shutil", "multiprocessing", "pty", "signal", "winreg",
                     "importlib", "pickle", "marshal"}


class AgentX:
    name = "Agent X"

    def __init__(self, jarvis, api: str | None = None):
        self.j = jarvis
        self.api = (api or os.environ.get("JARVIS_GITHUB_API") or API).rstrip("/")
        self.queue_file = jarvis.config.home / "agent_x.json"
        self.state = self._load()
        self.thread: threading.Thread | None = None
        self.stop = threading.Event()
        self.busy = threading.Lock()

    # ------------------------------------------------------------------ state
    def _load(self) -> dict:
        try:
            data = json.loads(self.queue_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {"queue": [], "done": [], "log": [], "day": "", "count": 0, **data}
        except (OSError, ValueError):
            pass
        return {"queue": [], "done": [], "log": [], "day": "", "count": 0}

    def _save(self) -> None:
        self.state["log"] = self.state["log"][-200:]
        self.state["done"] = self.state["done"][-500:]
        tmp = self.queue_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.queue_file)

    def _log(self, text: str) -> None:
        self.state["log"].append({"t": time.strftime("%Y-%m-%d %H:%M"), "msg": text})
        self._save()

    def _say(self, text: str) -> None:
        try:
            self.j.notify(f"🕵️ {self.name}: {text}")
        except Exception:
            pass

    def add_topic(self, topic: str, front: bool = True) -> bool:
        topic = topic.strip(" ؟?.!،,\"'«»")
        if not topic or topic.lower() in (t.lower() for t in self.state["queue"] + self.state["done"][-50:]):
            return False
        (self.state["queue"].insert(0, topic) if front else self.state["queue"].append(topic))
        self._save()
        return True

    def _budget_left(self) -> int:
        today = time.strftime("%Y-%m-%d")
        if self.state["day"] != today:
            self.state["day"], self.state["count"] = today, 0
        return int(self.j.config["agent_x_daily_limit"]) - self.state["count"]

    # ------------------------------------------------------------------ 1. gaps
    def find_gaps(self) -> list[str]:
        """Questions Jarvis answered with "I don't know" become learning topics."""
        rows = self.j.memory.conn.execute(
            "SELECT role, text, source FROM conversations ORDER BY id DESC LIMIT 400").fetchall()
        rows = list(reversed(rows))
        found = []
        for prev, cur in zip(rows, rows[1:]):
            if prev["role"] == "user" and cur["role"] == "assistant" and any(m in cur["text"] for m in GAP_MARKERS):
                if not self.j.memory.recall(prev["text"], threshold=0.9):   # still unknown
                    found.append(prev["text"])
        added = [t for t in dict.fromkeys(found) if self.add_topic(t, front=False)]
        return added

    # ------------------------------------------------------------------ 2. research
    def _get(self, path_or_url: str, accept: str = "application/vnd.github+json", timeout: float = 20):
        url = path_or_url if path_or_url.startswith("http") else self.api + path_or_url
        headers = {"User-Agent": "Jarvis-AgentX", "Accept": accept}
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token and url.startswith(self.api):
            headers["Authorization"] = f"Bearer {token}"
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
            return r.read()

    def search_query(self, topic: str) -> str:
        """GitHub search works best in English: let the AI translate, else keep the Latin words."""
        if is_arabic(topic):
            from .brains import BrainError
            try:
                reply, _ = self.j.router.ask(
                    [{"role": "user", "content": f"Give 2-4 English search keywords for GitHub about: {topic}\n"
                                                 "Reply with the keywords only."}],
                    system="You output short keyword lists only.", llm_only=True)
                words = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]+", reply)[:4]
                if words:
                    return " ".join(words)
            except BrainError:
                pass
            latin = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]+", topic)
            return " ".join(latin) if latin else " ".join(sorted(keywords(topic)))
        words = [w for w in re.findall(r"[\w+#.-]+", topic.lower())
                 if w not in {"what", "is", "the", "a", "an", "how", "to", "do", "does", "about", "learn", "of", "in"}]
        return " ".join(words[:6]) or topic

    def find_repos(self, q: str, repos: int = 3) -> list[dict]:
        """Most relevant repositories for a query.

        GitHub search ANDs every word, so "python http requests library" misses psf/requests (its
        description doesn't say "python"). So: a language word becomes a `language:` filter, generic
        words ("library", "tool"...) are dropped, several queries are merged, then everything is ranked
        by keyword hits + language + log(stars). Link collections ("awesome-...") are skipped."""
        words = [w for w in re.findall(r"[a-z0-9+#]+", q.lower()) if len(w) > 1]
        lang = next((LANGUAGES[w] for w in words if w in LANGUAGES), None)
        core = [w for w in words if w not in LANGUAGES and w not in GENERIC] or \
               [w for w in words if w not in LANGUAGES] or words
        filt = f" language:{lang}" if lang else ""
        queries = [f"{' '.join(core)}{filt} in:name,description",
                   f"{' '.join(core[:2])}{filt} in:name,description",
                   f"{' '.join(core)}{filt} in:name,description,readme"]
        candidates: dict[str, tuple[int, dict]] = {}
        for qi, query in enumerate(dict.fromkeys(queries)):
            data = json.loads(self._get("/search/repositories?" + urllib.parse.urlencode({"q": query, "per_page": 15})))
            for rank, item in enumerate(data.get("items", [])):
                if item["full_name"] not in candidates:
                    candidates[item["full_name"]] = (qi * 15 + rank, item)
            if len(candidates) >= 25:
                break
        scored = []
        for full, (rank, item) in candidates.items():
            if is_list_repo(item):
                continue
            text = f"{full} {item.get('description') or ''}".lower()
            hits = sum(w in text for w in core)
            name_hits = sum(w in full.lower() for w in core)
            stars = item.get("stargazers_count", 0) or 0
            lang_bonus = 4 if lang and (item.get("language") or "").lower() == lang else 0
            # relevance first, then popularity on a log scale (trusted projects), then GitHub's order
            score = hits * 3 + name_hits * 2 + lang_bonus + 2 * math.log10(stars + 1) - rank * 0.1
            scored.append((score, item))
        scored.sort(key=lambda x: -x[0])
        return [item for _, item in scored[:repos]]

    def research(self, topic: str, repos: int = 3) -> list[dict]:
        q = self.search_query(topic)
        sources = []
        for item in self.find_repos(q, repos):
            full = item["full_name"]
            try:
                text = self._get(f"/repos/{full}/readme", accept="application/vnd.github.raw").decode("utf-8", "replace")
            except urllib.error.HTTPError:
                continue
            sources.append({"repo": full, "url": item.get("html_url", f"https://github.com/{full}"),
                            "stars": item.get("stargazers_count", 0), "about": item.get("description") or "",
                            "text": clean_markdown(text)[:12000]})
        return sources

    # ------------------------------------------------------------------ 3. learning
    def digest(self, topic: str, sources: list[dict]) -> tuple[list[dict], str]:
        """Returns (qa_pairs, how). how = 'ai' or 'summary'."""
        ar = is_arabic(topic)
        if not sources:
            return [], "none"
        from .brains import BrainError
        material = "\n\n".join(f"### {s['repo']} ({s['stars']}★)\n{s['about']}\n{s['text'][:5000]}" for s in sources)
        try:
            reply, _ = self.j.router.ask([{"role": "user", "content": (
                f"Topic: {topic}\nStudy these GitHub documents and teach me the topic.\n\n{material}\n\n"
                f"Return JSON: {{\"qa\": [{{\"q\": question, \"a\": clear answer}}]}} with 4-8 useful pairs, "
                f"written in {'Arabic' if ar else 'English'}. The first pair must answer the topic itself.")}],
                system="You are a precise teacher. Output JSON only.", llm_only=True)
            m = re.search(r"\{.*\}", reply, re.S)
            pairs = json.loads(m.group(0)).get("qa", []) if m else []
            pairs = [{"q": str(p["q"]).strip(), "a": str(p["a"]).strip()} for p in pairs
                     if isinstance(p, dict) and p.get("q") and p.get("a")]
            if pairs:
                return pairs[:8], "ai"
        except (BrainError, ValueError, KeyError, TypeError):
            pass
        # No AI (or unusable reply): keep an honest extractive summary with sources.
        best = sources[0]
        summary = first_paragraphs(best["text"]) or best["about"]
        links = "، ".join(s["url"] for s in sources) if ar else ", ".join(s["url"] for s in sources)
        answer = (f"{best['about']}\n{summary}".strip() + (f"\n(المصادر: {links})" if ar else f"\n(Sources: {links})"))
        return [{"q": topic, "a": answer[:1500]}], "summary"

    def store(self, topic: str, pairs: list[dict], sources: list[dict]) -> int:
        n = 0
        for p in pairs:
            self.j.memory.learn_answer(p["q"], p["a"], source="agent_x")
            n += 1
        if pairs and pairs[0]["q"].strip().lower() != topic.strip().lower():
            # asking about the topic itself should always find the overview answer
            self.j.memory.learn_answer(topic, pairs[0]["a"], source="agent_x")
        if sources:
            self.j.memory.set_fact(f"مصادر {topic}" if is_arabic(topic) else f"sources for {topic}",
                                   ", ".join(s["url"] for s in sources))
        return n

    # ------------------------------------------------------------------ 4. skills
    def wants_skill(self, topic: str) -> bool:
        return bool(ACTION_WORDS.search(topic.strip())) and self.j.config["agent_x_skills"]

    def build_skill(self, topic: str, sources: list[dict]) -> Path | None:
        from .brains import BrainError
        name = "x_" + (re.sub(r"[^a-z0-9]+", "_", self.search_query(topic).lower()).strip("_")[:30] or "skill")
        refs = "\n\n".join(f"### {s['repo']}\n{s['text'][:3000]}" for s in sources[:2])
        try:
            reply, _ = self.j.router.ask([{"role": "user", "content": (
                f"Write a Jarvis skill plugin (one Python file, standard library only) that does: {topic}\n"
                "It must define NAME (str), PATTERNS (list of regex strings matching the user's request, "
                "Arabic and English), TESTS (list of example requests) and handle(text, match, jarvis) "
                "returning a reply string. Use jarvis.say(arabic, english, text) for bilingual replies. "
                "Network access only via urllib.request with a timeout. Never delete or modify files, "
                f"never run shell commands.\nReference material:\n{refs}\n\nReply with one ```python block.")}],
                system="You are a careful Python engineer.", llm_only=True)
        except BrainError:
            return None
        m = re.search(r"```(?:python)?\s*\n(.*?)```", reply, re.S)
        code = (m.group(1) if m else "").strip()
        if not code:
            return None
        problem = check_skill_safety(code)
        if problem:
            self._log(f"rejected skill for '{topic}': {problem}")
            return None
        ok, detail = sandbox_test(code)
        if not ok:
            self._log(f"skill for '{topic}' failed its tests: {detail[:200]}")
            return None
        header = (f"# Written by Agent X for: {topic}\n# Sources: {', '.join(s['url'] for s in sources)}\n"
                  f"# Passed the safety check and its tests on {time.strftime('%Y-%m-%d %H:%M')}\n")
        path = self.j.config.plugins / f"{name}.py"
        path.write_text(header + code + "\n", encoding="utf-8")
        self.j.skills.load_all()
        return path

    # ------------------------------------------------------------------ the loop
    def learn(self, topic: str) -> dict:
        """Learn one topic now (blocking). Returns a short report."""
        report = {"topic": topic, "sources": [], "learned": 0, "how": "none", "skill": None, "error": ""}
        try:
            sources = self.research(topic)
            report["sources"] = [s["repo"] for s in sources]
            pairs, report["how"] = self.digest(topic, sources)
            report["learned"] = self.store(topic, pairs, sources)
            if self.wants_skill(topic):
                skill = self.build_skill(topic, sources)
                report["skill"] = skill.stem if skill else None
        except urllib.error.HTTPError as exc:
            report["error"] = f"GitHub HTTP {exc.code}" + (" (rate limit - try later or set GITHUB_TOKEN)"
                                                           if exc.code in (403, 429) else "")
        except Exception as exc:  # never let learning crash Jarvis
            report["error"] = f"{type(exc).__name__}: {exc}"
            self.j.healer.record("agent_x", exc, quiet=True)
        self.state["count"] += 1
        if topic in self.state["queue"]:
            self.state["queue"].remove(topic)
        self.state["done"].append(topic)
        self._log(json.dumps({k: v for k, v in report.items() if v}, ensure_ascii=False))
        return report

    def describe(self, r: dict) -> str:
        ar = is_arabic(r["topic"]) or self.j.config["language"] == "ar"
        if r["error"]:
            return (f"ما قدرت أتعلم «{r['topic']}»: {r['error']}" if ar
                    else f"Couldn't learn \"{r['topic']}\": {r['error']}")
        if not r["sources"]:
            return f"ما لقيت مصادر عن «{r['topic']}» في GitHub." if ar else f"No GitHub sources found for \"{r['topic']}\"."
        how = {"ai": "بالذكاء الاصطناعي" if ar else "with AI", "summary": "كملخّص" if ar else "as a summary"}.get(r["how"], "")
        out = (f"تعلّمت «{r['topic']}» من {len(r['sources'])} مستودعات ({', '.join(r['sources'])}) "
               f"وحفظت {r['learned']} معلومة {how}." if ar else
               f"Learned \"{r['topic']}\" from {len(r['sources'])} repos ({', '.join(r['sources'])}); "
               f"saved {r['learned']} item(s) {how}.")
        if r["skill"]:
            out += (f" وكتبت مهارة جديدة «{r['skill']}» ونجحت اختباراتها ✅" if ar
                    else f" Also wrote a new skill '{r['skill']}' that passed its tests ✅")
        return out

    def cycle(self) -> list[dict]:
        """One round: collect gaps, then learn as many queued topics as today's budget allows."""
        if not self.busy.acquire(blocking=False):
            return []
        try:
            self.find_gaps()
            reports = []
            while self.state["queue"] and self._budget_left() > 0 and not self.stop.is_set():
                r = self.learn(self.state["queue"][0])
                reports.append(r)
                self._say(self.describe(r))
            self._save()
            return reports
        finally:
            self.busy.release()

    def start(self) -> bool:
        """Background mode: a cycle now and then every `agent_x_interval_hours`."""
        if self.thread and self.thread.is_alive():
            return False
        self.stop.clear()

        def loop():
            while not self.stop.is_set():
                try:
                    self.cycle()
                except Exception as exc:
                    self.j.healer.record("agent_x", exc, quiet=True)
                self.stop.wait(float(self.j.config["agent_x_interval_hours"]) * 3600)
        self.thread = threading.Thread(target=loop, daemon=True, name="agent-x")
        self.thread.start()
        return True

    def learn_now(self, topic: str) -> bool:
        """Queue a topic and study it in the background right away."""
        self.add_topic(topic, front=True)
        if self.busy.locked():
            return False
        threading.Thread(target=self.cycle, daemon=True, name="agent-x-now").start()
        return True


# ---------------------------------------------------------------------- helpers
LANGUAGES = {"python": "python", "py": "python", "javascript": "javascript", "js": "javascript",
             "node": "javascript", "nodejs": "javascript", "typescript": "typescript", "ts": "typescript",
             "java": "java", "go": "go", "golang": "go", "rust": "rust", "ruby": "ruby", "php": "php",
             "kotlin": "kotlin", "swift": "swift", "dart": "dart", "flutter": "dart", "c#": "c#",
             "csharp": "c#", "cpp": "c++", "c++": "c++", "lua": "lua", "r": "r", "bash": "shell", "shell": "shell"}
GENERIC = {"library", "libraries", "lib", "framework", "tool", "tools", "package", "module", "app", "project",
           "example", "examples", "tutorial", "code", "simple", "best", "using", "with", "for", "and"}

LIST_REPO = re.compile(r"(^|[/_-])(awesome|public-apis|free-programming-books|cheatsheets?|interview|"
                       r"roadmaps?|resources|collection|curated|list)([/_-]|$)", re.I)


def is_list_repo(item: dict) -> bool:
    """Link collections teach little about a specific topic."""
    desc = (item.get("description") or "").lower()
    return bool(LIST_REPO.search(item["full_name"])) or desc.startswith(("a curated list", "a collective list",
                                                                         "a list of", "curated list"))


def clean_markdown(text: str) -> str:
    t = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t)                 # images / badges
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)              # links -> text
    t = re.sub(r"<[^>]+>", " ", t)                               # html
    t = re.sub(r"^[#>*\-\s]+", "", t, flags=re.M)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", t)).strip()


def first_paragraphs(text: str, limit: int = 600) -> str:
    paras = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 60]
    out = ""
    for p in paras:
        if len(out) + len(p) > limit:
            break
        out += p + "\n"
    return (out or (paras[0][:limit] if paras else "")).strip()


def check_skill_safety(code: str) -> str | None:
    """Static check of AI-written skill code. Returns a reason to reject, or None."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"syntax error: {exc}"
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for m in mods:
                if m.split(".")[0] in FORBIDDEN_MODULES:
                    return f"imports forbidden module {m}"
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""
            if name in FORBIDDEN_CALLS:
                return f"calls forbidden function {name}()"
            if name == "open":
                mode = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords if k.arg == "mode"), None)
                if isinstance(mode, ast.Constant) and any(c in str(mode.value) for c in "wax+"):
                    return "writes files"
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
            {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    funcs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for required in ("NAME", "PATTERNS", "TESTS"):
        if required not in names:
            return f"missing {required}"
    if "handle" not in funcs:
        return "missing handle()"
    return None


SANDBOX = r'''
import importlib.util, json, re, sys
spec = importlib.util.spec_from_file_location("candidate", sys.argv[1])
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
class FakeJarvis:
    def say(self, ar, en, text=""):
        return ar if re.search("[؀-ۿ]", text or "") else en
pats = [re.compile(p, re.I) for p in mod.PATTERNS]
tests = list(mod.TESTS)
assert tests, "no TESTS"
for t in tests:
    m = next((p.search(t) or p.search(t.lower()) for p in pats if p.search(t) or p.search(t.lower())), None)
    assert m, f"no pattern matches its own test {t!r}"
    out = mod.handle(t, m, FakeJarvis())
    assert isinstance(out, str) and out.strip(), f"empty reply for {t!r}"
print(json.dumps({"ok": True, "tests": len(tests)}))
'''


def sandbox_test(code: str, timeout: float = 30) -> tuple[bool, str]:
    """Run the skill's own TESTS in a separate, isolated Python process with a time limit."""
    with tempfile.TemporaryDirectory() as tmp:
        cand = Path(tmp) / "candidate.py"
        cand.write_text(code, encoding="utf-8")
        runner = Path(tmp) / "sandbox.py"
        runner.write_text(SANDBOX, encoding="utf-8")
        if getattr(sys, "frozen", False):   # packaged app: no separate interpreter to call
            return _inprocess_test(cand)
        cmd = [sys.executable, "-I", str(runner), str(cand)]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=timeout, cwd=tmp, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                               creationflags=0x08000000 if sys.platform == "win32" else 0)
        except subprocess.TimeoutExpired:
            return False, "tests timed out"
        return (p.returncode == 0, (p.stdout + p.stderr).strip()[-500:])


def _inprocess_test(path: Path) -> tuple[bool, str]:
    ns: dict = {}
    try:
        exec(compile(SANDBOX.replace("sys.argv[1]", repr(str(path))), "sandbox", "exec"), ns)  # noqa: S102
        return True, "ok"
    except BaseException as exc:
        return False, f"{type(exc).__name__}: {exc}"
