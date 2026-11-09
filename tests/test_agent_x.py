"""Agent X: self-teaching from GitHub (against a fake GitHub API)."""
import json
import shutil
import tempfile
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from jarvis import Jarvis
from jarvis.agent_x import AgentX, check_skill_safety, clean_markdown, sandbox_test
from jarvis.brains import Brain, OfflineBrain

README = """# Solar Kit
![badge](https://img.shields.io/x.svg) [![ci](https://ci/x.svg)](https://ci)

Solar Kit is a toolkit for planning **solar energy** systems: it estimates panel output from sunlight
hours, sizes batteries and inverters, and reports the expected savings for a home installation.

## Install
```bash
pip install solar-kit
```
"""


class FakeGitHub(BaseHTTPRequestHandler):
    queries: list = []
    status = 200

    def log_message(self, *a):
        pass

    def _send(self, body: bytes, ctype="application/json"):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if FakeGitHub.status != 200:
            self.send_error(FakeGitHub.status, "rate limited")
            return
        url = urllib.parse.urlparse(self.path)
        if url.path == "/search/repositories":
            q = urllib.parse.parse_qs(url.query)["q"][0]
            FakeGitHub.queries.append(q)
            topic = q.split(" in:")[0]
            # a huge link-collection first (it would win on stars), then relevant repos
            items = [{"full_name": "someone/awesome-everything", "html_url": "https://github.com/someone/awesome-everything",
                      "stargazers_count": 300000, "description": "A curated list of everything"}]
            items += [{"full_name": f"demo/repo{i}", "html_url": f"https://github.com/demo/repo{i}",
                       "stargazers_count": 1000 - i, "description": f"Demo repository {i} about {topic}"} for i in range(3)]
            return self._send(json.dumps({"items": items}).encode())
        if url.path.endswith("/readme"):
            return self._send(README.encode(), "text/plain")
        self.send_error(404)


class ScriptedLLM(Brain):
    name, is_llm = "fake", True

    def __init__(self, replies):
        self.replies, self.prompts = replies, []

    def available(self):
        return True

    def ask(self, messages, system=""):
        prompt = messages[-1]["content"]
        self.prompts.append(prompt)
        for key, reply in self.replies.items():
            if key in prompt:
                return reply
        return "ok"


SAFE_SKILL = '''```python
import re
NAME = "x_temp"
PATTERNS = [r"(?:convert|حول)\\s+(-?\\d+(?:\\.\\d+)?)\\s*(?:c|celsius|سيليزي)"]
TESTS = ["convert 100 c to fahrenheit", "حول 0 سيليزي"]

def handle(text, match, jarvis):
    c = float(match.group(1))
    f = c * 9 / 5 + 32
    return jarvis.say(f"{c:g}° مئوية = {f:g}° فهرنهايت", f"{c:g}°C = {f:g}°F", text)
```'''
UNSAFE_SKILL = SAFE_SKILL.replace("import re", "import re, os").replace(
    "    c = float", "    os.remove('/tmp/x')\n    c = float")
BROKEN_SKILL = SAFE_SKILL.replace("c * 9 / 5 + 32", "c / 0")


class AgentXTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeGitHub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.api = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="jarvis-ax-"))
        FakeGitHub.queries, FakeGitHub.status = [], 200
        self.jarvises = []

    def tearDown(self):
        for j in self.jarvises:
            j.agent_x.stop.set()
            j.close()
        shutil.rmtree(self.home, ignore_errors=True)

    def make(self, *llms):
        j = Jarvis(home=self.home, brains=[])
        j.router.brains = list(llms) + [OfflineBrain(j.memory, j.config)]
        j._agent_x = AgentX(j, api=self.api)
        self.jarvises.append(j)
        return j

    # --- learning ---------------------------------------------------------
    def test_learns_without_ai_and_answers_offline_afterwards(self):
        j = self.make()
        r = j.agent_x.learn("solar energy")
        self.assertEqual(r["how"], "summary")
        self.assertEqual(len(r["sources"]), 3)
        self.assertEqual(FakeGitHub.queries[0], "solar energy in:name,description")
        self.assertNotIn("someone/awesome-everything", r["sources"])   # link lists are skipped
        answer = j.handle("what is solar energy").text
        self.assertIn("toolkit for planning", answer)                 # learned from the README
        self.assertIn("https://github.com/demo/repo0", answer)        # with sources
        self.assertNotIn("badge", answer)                             # markdown noise removed

    def test_learns_with_ai(self):
        qa = json.dumps({"qa": [{"q": "ما هي الطاقة الشمسية؟", "a": "طاقة نحصل عليها من ضوء الشمس عبر الألواح."},
                                {"q": "كيف أحسب عدد الألواح؟", "a": "اقسم استهلاكك اليومي على إنتاج اللوح الواحد."}]},
                        ensure_ascii=False)
        llm = ScriptedLLM({"English search keywords": "solar energy", "Study these GitHub documents": qa})
        j = self.make(llm)
        r = j.agent_x.learn("الطاقة الشمسية")
        self.assertEqual((r["how"], r["learned"]), ("ai", 2))
        self.assertEqual(FakeGitHub.queries[0], "solar energy in:name,description")  # Arabic -> English search
        self.assertIn("Solar Kit", llm.prompts[-1])                  # the AI got the downloaded docs
        j.router.brains = [OfflineBrain(j.memory, j.config)]           # later, offline
        self.assertIn("اقسم استهلاكك", j.handle("كيف أحسب عدد الألواح").text)

    def test_never_overwrites_what_you_taught(self):
        j = self.make()
        j.handle("إذا سألتك solar energy قل الشمس مصدر طاقتي المفضل")
        j.agent_x.learn("solar energy")
        self.assertEqual(j.handle("solar energy").text, "الشمس مصدر طاقتي المفضل")

    def test_finds_gaps_from_unanswered_questions_and_learns_them(self):
        j = self.make()
        self.assertIn("ما أعرف", j.handle("ما هي الطاقة الشمسية solar energy").text)
        reports = j.agent_x.cycle()
        self.assertEqual(len(reports), 1)
        notes = "\n".join(j.pending_notifications())
        self.assertIn("Agent X", notes)
        self.assertIn("تعلّمت", notes)
        self.assertIn("toolkit", j.handle("ما هي الطاقة الشمسية solar energy").text)
        self.assertEqual(j.agent_x.find_gaps(), [])                    # no longer a gap

    def test_daily_limit(self):
        j = self.make()
        j.config.set("agent_x_daily_limit", 2)
        for t in ("solar energy", "wind power", "hydro power"):
            j.agent_x.add_topic(t)
        self.assertEqual(len(j.agent_x.cycle()), 2)
        self.assertEqual(len(j.agent_x.state["queue"]), 1)

    def test_github_errors_are_reported_not_crashing(self):
        j = self.make()
        FakeGitHub.status = 403
        r = j.agent_x.learn("solar energy")
        self.assertIn("rate limit", r["error"])
        self.assertIn("ما قدرت", j.agent_x.describe({**r, "topic": "طاقة"}))

    # --- skills -------------------------------------------------------------
    def test_writes_tests_and_installs_a_safe_skill(self):
        llm = ScriptedLLM({"Write a Jarvis skill plugin": SAFE_SKILL, "Study these": '{"qa": []}'})
        j = self.make(llm)
        r = j.agent_x.learn("convert celsius to fahrenheit")
        self.assertEqual(r["skill"], "x_convert_celsius_fahrenheit")
        path = j.config.plugins / "x_convert_celsius_fahrenheit.py"
        self.assertIn("Written by Agent X", path.read_text())
        reply = j.handle("convert 100 c to fahrenheit")
        self.assertEqual((reply.source, reply.text), ("skill:x_temp", "100°C = 212°F"))

    def test_rejects_dangerous_or_broken_skills(self):
        for code in (UNSAFE_SKILL, BROKEN_SKILL):
            llm = ScriptedLLM({"Write a Jarvis skill plugin": code, "Study these": '{"qa": []}'})
            j = self.make(llm)
            r = j.agent_x.learn("convert celsius to fahrenheit")
            self.assertIsNone(r["skill"])
            self.assertFalse(list(j.config.plugins.glob("x_*.py")))
            j.agent_x.stop.set()
            j.close()
            self.jarvises.remove(j)
            shutil.rmtree(self.home, ignore_errors=True)

    def test_safety_check(self):
        ok = SAFE_SKILL.split("```python\n")[1].split("```")[0]
        self.assertIsNone(check_skill_safety(ok))
        for bad, why in (("import subprocess", "subprocess"), ("import shutil", "shutil"),
                         ("open('x', 'w')", "writes files"), ("eval('1')", "eval"), ("__import__('os')", "__import__")):
            self.assertIn(why, check_skill_safety(ok + "\n" + bad))
        self.assertIn("missing handle", check_skill_safety("NAME='a'\nPATTERNS=[]\nTESTS=[]"))
        self.assertTrue(sandbox_test(ok)[0])
        self.assertFalse(sandbox_test(ok.replace("c * 9 / 5 + 32", "c / 0"))[0])

    def test_ranks_the_real_library_first(self):
        """Mirrors the real run: same-name libraries in other languages must not beat the Python one."""
        items = [
            {"full_name": "asmcos/requests", "description": "A golang http request library for humans",
             "stargazers_count": 1100, "language": "Go"},
            {"full_name": "ikod/dlang-requests", "description": "dlang http client library inspired by python-requests",
             "stargazers_count": 160, "language": "D"},
            {"full_name": "psf/requests", "description": "A simple, yet elegant, HTTP library.",
             "stargazers_count": 52000, "language": "Python"},
            {"full_name": "sindresorhus/awesome", "description": "Awesome lists about all kinds of interesting topics",
             "stargazers_count": 380000, "language": None},
        ]
        j = self.make()
        from unittest import mock
        with mock.patch.object(AgentX, "_get", return_value=json.dumps({"items": items}).encode()):
            picked = [i["full_name"] for i in j.agent_x.find_repos("python http requests library")]
        self.assertEqual(picked[0], "psf/requests")
        self.assertNotIn("sindresorhus/awesome", picked)

    def test_language_becomes_a_filter_and_generic_words_are_dropped(self):
        j = self.make()
        seen = []
        from unittest import mock

        def fake_get(path, accept=None, timeout=20):
            seen.append(urllib.parse.parse_qs(urllib.parse.urlparse(path).query)["q"][0])
            return json.dumps({"items": []}).encode()
        with mock.patch.object(AgentX, "_get", side_effect=fake_get):
            j.agent_x.find_repos("python http requests library")
        self.assertEqual(seen[0], "http requests language:python in:name,description")
        self.assertNotIn("library", seen[0])

    def test_clean_markdown(self):
        t = clean_markdown(README)
        self.assertNotIn("img.shields", t)
        self.assertNotIn("pip install", t)
        self.assertIn("Solar Kit is a toolkit", t)

    # --- commands -------------------------------------------------------------
    def test_commands(self):
        j = self.make()
        r = j.handle("تعلم عن الطاقة الشمسية solar")
        self.assertIn("Agent X", r.text)
        for _ in range(100):
            if j.agent_x.state["done"]:
                break
            threading.Event().wait(0.05)
        self.assertIn("الطاقة الشمسية solar", j.agent_x.state["done"])
        self.assertIn("تعلّم: 1", j.handle("تقرير ايجنت اكس").text)
        self.assertIn("بدأ", j.handle("شغل ايجنت اكس").text)
        self.assertTrue(j.agent_x.thread.is_alive())
        self.assertIn("أوقفت", j.handle("وقف ايجنت اكس").text)
        self.assertFalse(j.config["agent_x_auto"])


if __name__ == "__main__":
    unittest.main()
