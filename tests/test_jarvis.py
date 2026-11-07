import os
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from jarvis import Jarvis
from jarvis.brains import Brain, BrainError, OfflineBrain
from jarvis.text import normalize, similarity


class FakeLLM(Brain):
    """Stands in for Claude/Ollama in tests."""
    name = "fake"
    is_llm = True

    def __init__(self, answer="fake answer", fixed_code=None):
        self.answer = answer
        self.fixed_code = fixed_code
        self.calls = 0

    def available(self):
        return True

    def ask(self, messages, system=""):
        self.calls += 1
        prompt = messages[-1]["content"]
        if "Fix the bug" in prompt and self.fixed_code is not None:
            return f"```python\n{self.fixed_code}\n```"
        return self.answer


class BrokenBrain(Brain):
    name = "broken"

    def available(self):
        return True

    def ask(self, messages, system=""):
        raise BrainError("simulated outage")


class Base(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="jarvis-test-"))
        self._env = {k: os.environ.pop(k, None) for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
        self.jarvises = []

    def tearDown(self):
        for j in self.jarvises:
            j.close()
        shutil.rmtree(self.home, ignore_errors=True)
        for k, v in self._env.items():
            if v is not None:
                os.environ[k] = v

    def make(self, *llms):
        """Jarvis with the given fake brains + the real offline brain."""
        j = Jarvis(home=self.home, brains=[])
        j.router.brains = list(llms) + [OfflineBrain(j.memory, j.config)]
        self.jarvises.append(j)
        return j

    def plugin(self, name, code):
        path = self.home / "plugins" / f"{name}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(code), encoding="utf-8")
        return path


class TextTests(unittest.TestCase):
    def test_arabic_normalization(self):
        self.assertEqual(normalize("مَنْ صنعكَ؟"), normalize("من صنعك"))
        self.assertEqual(normalize("أإآ"), "ااا")

    def test_similarity(self):
        self.assertGreater(similarity("ما عاصمة اليابان", "ما هي عاصمة اليابان؟"), 0.8)
        self.assertLess(similarity("ما عاصمة اليابان", "كم الساعة"), 0.5)


class LearningTests(Base):
    def test_teach_and_recall_with_spelling_variation(self):
        j = self.make()
        j.handle("إذا سألتك من صنعك قل صنعني عبود")
        r = j.handle("مَن صنعك؟")
        self.assertEqual(r.text, "صنعني عبود")
        self.assertEqual(r.source, "memory")

    def test_english_teaching_and_facts(self):
        j = self.make()
        j.handle("when I ask what is your purpose say to serve")
        self.assertEqual(j.handle("what is your purpose").text, "to serve")
        j.handle("remember that my car is black")
        self.assertEqual(j.handle("what is my car").text, "black")

    def test_correction_survives_restart(self):
        j = self.make()
        j.handle("ما عاصمة اليابان؟")       # offline brain doesn't know
        j.close()
        self.jarvises.remove(j)
        j2 = self.make()                    # new process / restart
        self.assertIn("حفظت", j2.handle("الجواب الصحيح هو طوكيو").text)
        self.assertEqual(j2.handle("ما عاصمة اليابان").text, "طوكيو")

    def test_learns_from_llm_and_answers_offline_later(self):
        j = self.make(FakeLLM("باريس"))
        self.assertEqual(j.handle("ما عاصمة فرنسا؟").source, "brain:fake")
        j.close()
        self.jarvises.remove(j)
        offline_only = self.make()          # no AI brain, no token, no internet
        r = offline_only.handle("ما هي عاصمة فرنسا")
        self.assertEqual(r.text, "باريس")
        self.assertEqual(r.source, "brain:offline")

    def test_volatile_questions_not_cached(self):
        j = self.make(FakeLLM("sunny"))
        j.handle("what is the weather today?")
        self.assertEqual(j.memory.learned(), [])

    def test_forget(self):
        j = self.make()
        j.handle("تذكر أن رقم الغرفة هو 12")
        j.handle("انسى رقم الغرفة")
        self.assertIsNone(j.memory.get_fact("رقم الغرفة"))


class BrainTests(Base):
    def test_works_without_any_token(self):
        j = Jarvis(home=self.home)          # real default brains, no key set
        self.jarvises.append(j)
        r = j.handle("السلام عليكم")
        self.assertEqual(r.source, "brain:offline")
        self.assertIn("وعليكم السلام", r.text)

    def test_falls_back_and_cools_down_failed_brain(self):
        broken, good = BrokenBrain(), FakeLLM("hello from backup")
        j = self.make(broken, good)
        r = j.handle("tell me a story?")
        self.assertEqual(r.source, "brain:fake")
        self.assertIn("broken", j.router._skip_until)          # circuit breaker engaged
        self.assertTrue(any(e["component"] == "brain:broken" for e in j.memory.recent_errors()))


class SkillTests(Base):
    def test_calculator_is_safe(self):
        j = self.make()
        self.assertIn("62", j.handle("احسب 15 * 4 + 2").text)
        self.assertIn("4", j.handle("احسب جذر 16").text)
        from jarvis.skills.calculator import calculate
        with self.assertRaises(ValueError):
            calculate("__import__('os').system('echo hacked')")
        r = j.handle("calculate __import__('os').system('echo hacked')")
        self.assertNotEqual(r.source, "skill:calculator")

    def test_notes(self):
        j = self.make()
        j.handle("سجل ملاحظة اشتري قهوة")
        self.assertIn("اشتري قهوة", j.handle("ملاحظاتي").text)
        j.handle("خلصت ملاحظة 1")
        self.assertIn("ما عندك", j.handle("ملاحظاتي").text)


class HealingTests(Base):
    def test_corrupted_memory_is_restored_from_backup(self):
        j = self.make()
        j.handle("تذكر أن كلمة السر للواي فاي هو 1234")
        j.memory.backup()
        j.close()
        self.jarvises.remove(j)
        (self.home / "memory.db").write_bytes(b"this is not a database" * 100)
        j2 = self.make()
        self.assertIn("restored", j2.memory.recovered_from)
        self.assertEqual(j2.memory.get_fact("كلمة السر للواي فاي"), "1234")

    def test_broken_config_is_reset(self):
        self.home.mkdir(exist_ok=True)
        (self.home / "config.json").write_text("{ this is broken", encoding="utf-8")
        j = self.make()
        self.assertIsNone(j.config.load_error)
        self.assertTrue(list((self.home / "backups").glob("config.broken.*.json")))
        self.assertTrue(any("config" in n for n in j.startup_notes))

    def test_crashing_skill_is_quarantined_without_ai(self):
        self.plugin("bomb", '''
            NAME = "bomb"
            PATTERNS = [r"^boom$"]
            def handle(text, match, jarvis):
                raise RuntimeError("kaboom")
        ''')
        j = self.make()
        for _ in range(3):
            r = j.handle("boom")
            self.assertEqual(r.source, "skill:bomb")      # Jarvis answers, doesn't die
        self.assertIn("bomb", j.skills.quarantined)
        self.assertIn("62", j.handle("احسب 60 + 2").text)  # rest of Jarvis still fine
        self.assertTrue(j.skills.release("bomb"))

    def test_ai_repairs_crashing_skill_and_can_roll_back(self):
        buggy = '''
            NAME = "greeter"
            PATTERNS = [r"^greet (\\w+)$"]
            TESTS = ["greet bob"]
            def handle(text, match, jarvis):
                return "Hello " + match.group(2)
        '''
        fixed = textwrap.dedent('''
            NAME = "greeter"
            PATTERNS = [r"^greet (\\w+)$"]
            TESTS = ["greet bob"]
            def handle(text, match, jarvis):
                return "Hello " + match.group(1)
        ''')
        path = self.plugin("greeter", buggy)
        llm = FakeLLM(fixed_code=fixed)
        j = self.make(llm)
        j.handle("greet sam")                    # crash 1: logged
        r = j.handle("greet sam")                # crash 2: AI repair, tested, applied, retried
        self.assertEqual(r.text, "Hello sam")
        self.assertIn("match.group(1)", path.read_text())
        self.assertTrue(list((self.home / "backups" / "code").glob("greeter.*.py")))
        self.assertTrue(j.healer.rollback("greeter"))
        self.assertIn("match.group(2)", path.read_text())

    def test_bad_ai_fix_is_rejected(self):
        buggy = '''
            NAME = "div"
            PATTERNS = [r"^divide$"]
            def handle(text, match, jarvis):
                return str(1 / 0)
        '''
        path = self.plugin("div", buggy)
        original = path.read_text()
        j = self.make(FakeLLM(fixed_code=textwrap.dedent(buggy)))   # "fix" that still crashes
        j.handle("divide")
        j.handle("divide")
        self.assertEqual(path.read_text(), original)                 # untouched
        self.assertIn("failed its tests", j.healer.last_note)

    def test_plugin_that_fails_to_load_does_not_break_startup(self):
        self.plugin("needs_lib", '''
            import some_library_that_does_not_exist
            NAME = "needs_lib"
            PATTERNS = [r"x"]
            def handle(text, match, jarvis):
                return "x"
        ''')
        j = self.make()
        self.assertTrue(j.skills.skills["needs_lib"].error)
        self.assertTrue(any(c.name == "skill needs_lib" and not c.ok for c in j.healer.health_check()))
        self.assertIn("وعليكم", j.handle("السلام عليكم").text)

    def test_learns_which_fix_works(self):
        j = self.make()
        sig = "X|skill:demo|f.py:h|msg"
        j.memory.record_fix(sig, "repair_code", False)
        j.memory.record_fix(sig, "repair_code", False)
        j.memory.record_fix(sig, "install_package", True)
        rank = j.memory.fix_ranking(sig)
        self.assertGreater(rank["install_package"], rank["repair_code"])


if __name__ == "__main__":
    unittest.main()
