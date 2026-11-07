"""Voice, Office documents and coding."""
import importlib.util
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from jarvis import Jarvis
from jarvis.brains import Brain, OfflineBrain
from jarvis.coder import parse_files
from jarvis.voice import Speaker, VoiceError, clean_for_speech

HAS_OFFICE = all(importlib.util.find_spec(m) for m in ("pptx", "docx"))


class ScriptedLLM(Brain):
    """Fake AI brain: returns replies by matching a keyword in the prompt."""
    name = "fake"
    is_llm = True

    def __init__(self, replies: dict, default=""):
        self.replies, self.default, self.prompts = replies, default, []

    def available(self):
        return True

    def ask(self, messages, system=""):
        prompt = messages[-1]["content"]
        self.prompts.append(prompt)
        for key, reply in self.replies.items():
            if key in prompt:
                return reply
        return self.default


class Base(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="jarvis-feat-"))
        self.jarvises = []

    def tearDown(self):
        for j in self.jarvises:
            j.close()
        shutil.rmtree(self.home, ignore_errors=True)

    def make(self, *llms):
        j = Jarvis(home=self.home, brains=[])
        j.router.brains = list(llms) + [OfflineBrain(j.memory, j.config)]
        j.config.set("open_created_files", False)
        self.jarvises.append(j)
        return j


# ------------------------------------------------------------------ voice
class VoiceTests(Base):
    def test_clean_for_speech(self):
        t = clean_for_speech("✅ تم!\n```python\nprint(1)\n```\n📁 /home/user/very/long/path/to/some/file.pptx **مهم**")
        self.assertNotIn("print", t)
        self.assertNotIn("✅", t)
        self.assertNotIn("/home/user", t)
        self.assertIn("مهم", t)

    def test_falls_back_to_next_engine_and_rests_failed_one(self):
        j = self.make()
        sp = Speaker(j.config, j.healer)
        calls = []

        def broken(*a):
            calls.append("edge")
            raise VoiceError("offline")

        with mock.patch.object(Speaker, "engines", return_value=["edge", "espeak"]), \
                mock.patch.object(Speaker, "_speak_edge", side_effect=broken, create=True), \
                mock.patch.object(Speaker, "_speak_espeak", side_effect=lambda *a: calls.append("espeak")):
            self.assertEqual(sp.speak("مرحبا"), "espeak")
            self.assertEqual(sp.speak("مرحبا"), "espeak")
        self.assertEqual(calls, ["edge", "espeak", "espeak"])   # edge skipped the 2nd time (cool-down)

    def test_all_engines_failing_raises_cleanly(self):
        j = self.make()
        with mock.patch.object(Speaker, "engines", return_value=[]):
            with self.assertRaises(VoiceError):
                Speaker(j.config).speak("hello")

    @unittest.skipUnless(shutil.which("espeak-ng") or shutil.which("espeak"), "espeak not installed")
    def test_offline_voice_writes_audio(self):
        j = self.make()
        j.config.set("voice_online", False)
        out = self.home / "say.wav"
        self.assertEqual(j.voice.speaker.speak("مرحباً سيدي", to_file=out), "espeak")
        self.assertGreater(out.stat().st_size, 1000)

    def test_voice_commands_toggle_setting(self):
        j = self.make()
        j.handle("فعّل الصوت")
        self.assertTrue(j.config["speak_replies"])
        j.handle("اسكت")
        self.assertFalse(j.config["speak_replies"])
        self.assertIn("speaking engines", j.voice.status())


# ------------------------------------------------------------------ office
@unittest.skipUnless(HAS_OFFICE, "python-pptx / python-docx not installed")
class OfficeTests(Base):
    def slides(self, path):
        from pptx import Presentation
        return list(Presentation(str(path)).slides)

    def test_presentation_skeleton_without_ai(self):
        j = self.make()
        r = j.handle("اعمل عرض تقديمي عن الذكاء الاصطناعي 5 شرائح")
        self.assertEqual(r.source, "skill:office")
        path = next(j.config.outputs.glob("*.pptx"))
        self.assertEqual(path.stem, "الذكاء الاصطناعي")
        self.assertEqual(len(self.slides(path)), 5 + 2)            # + title and closing slides
        xml = zipfile.ZipFile(path).read("ppt/slides/slide2.xml").decode()
        self.assertIn('rtl="1"', xml)
        self.assertLess(xml.index("<a:latin"), xml.index("<a:ea"))  # schema order latin, ea, cs
        self.assertLess(xml.index("<a:ea"), xml.index("<a:cs"))

    def test_presentation_from_points(self):
        j = self.make()
        j.handle("سوي بوربوينت عن مشروعي: الفكرة، السوق، الميزانية")
        slides = self.slides(next(j.config.outputs.glob("*.pptx")))
        titles = [sh.text_frame.text for s in slides for sh in s.shapes if sh.has_text_frame]
        for point in ("الفكرة", "السوق", "الميزانية"):
            self.assertIn(point, titles)

    def test_presentation_written_by_ai(self):
        outline = ('{"title": "Solar Power", "subtitle": "Clean energy", "slides": ['
                   '{"title": "How it works", "bullets": ["Photons hit cells", "Electrons flow"], "notes": "n"},'
                   '{"title": "Benefits", "bullets": ["No fuel", "Low upkeep"], "notes": ""}]}')
        j = self.make(ScriptedLLM({"presentation outline": "Sure! " + outline}))
        r = j.handle("make a presentation about solar power")
        self.assertIn("AI", r.text)
        slides = self.slides(j.config.outputs / "Solar Power.pptx")
        self.assertEqual(len(slides), 4)
        self.assertIn("Photons hit cells", "".join(sh.text_frame.text for sh in slides[1].shapes if sh.has_text_frame))

    def test_bad_ai_json_falls_back_to_skeleton(self):
        j = self.make(ScriptedLLM({}, default="sorry, I can't do JSON"))
        r = j.handle("make a presentation about the moon")
        self.assertIn("skeleton", r.text)
        self.assertTrue(list(j.config.outputs.glob("*.pptx")))

    def test_word_document_rtl_and_schema_order(self):
        j = self.make()
        r = j.handle("اكتب تقرير وورد عن السلامة في المصانع")
        self.assertIn("مستند الوورد", r.text)
        path = next(j.config.outputs.glob("*.docx"))
        xml = zipfile.ZipFile(path).read("word/document.xml").decode()
        self.assertIn("<w:bidi/>", xml)
        self.assertIn("<w:rtl/>", xml)
        self.assertNotIn('w:jc w:val="right"', xml)                # RTL paragraphs start on the right already
        for ppr in xml.split("<w:pPr>")[1:]:                        # pStyle must precede bidi
            ppr = ppr.split("</w:pPr>")[0]
            if "<w:pStyle" in ppr and "<w:bidi/>" in ppr:
                self.assertLess(ppr.index("<w:pStyle"), ppr.index("<w:bidi/>"))
        sect = xml[xml.index("<w:sectPr"):]
        self.assertLess(sect.index("<w:bidi/>"), sect.index("<w:docGrid"))

    def test_word_document_by_ai_and_unique_names(self):
        doc = ('{"title": "Time Management", "sections": [{"heading": "Plan", "paragraphs": ["Plan the day."], '
               '"bullets": ["List tasks", "Set priorities"]}]}')
        j = self.make(ScriptedLLM({"well-structured document": doc}))
        j.handle("write a word document about time management")
        j.handle("write a word document about time management")
        names = sorted(p.name for p in j.config.outputs.glob("*.docx"))
        self.assertEqual(names, ["Time Management (2).docx", "Time Management.docx"])
        from docx import Document
        text = "\n".join(p.text for p in Document(str(j.config.outputs / "Time Management.docx")).paragraphs)
        self.assertIn("Set priorities", text)

    def test_missing_library_is_installed_by_healer(self):
        j = self.make()
        calls = []
        real = __import__

        def fake_import(name, *a, **k):
            if name == "pptx" and not calls:
                calls.append("blocked")
                raise ModuleNotFoundError("No module named 'pptx'", name="pptx")
            return real(name, *a, **k)

        with mock.patch("builtins.__import__", side_effect=fake_import), \
                mock.patch("jarvis.healing.subprocess.run") as pip:
            pip.return_value = mock.Mock(returncode=0, stderr="")
            r = j.handle("اعمل عرض تقديمي عن الفضاء")
        self.assertIn("python-pptx", " ".join(pip.call_args[0][0]))
        self.assertIn("جهزت", r.text)                                # retried after the repair


# ------------------------------------------------------------------ coding
BUGGY = 'Here:\n```python\n# file: main.py\nnums = [3, 5, 8]\nprint("avg", sum(nums) / len(numz))\n```\nAverage.'
FIXED = '```python\n# file: main.py\nnums = [3, 5, 8]\nprint("avg", sum(nums) / len(nums))\n```'


class CodingTests(Base):
    def test_parse_files_names_and_safety(self):
        files, expl = parse_files("Intro\n```python\n# file: ../../evil.py\nprint(1)\n```\n"
                                  "```html\n<!-- file: index.html -->\n<p>x</p>\n```\n```js\nconsole.log(1)\n```\nDone")
        self.assertEqual(sorted(files), ["evil.py", "index.html", "main_3.js"])
        self.assertNotIn("file:", files["evil.py"])
        self.assertEqual(expl, "Intro\n\nDone")

    def test_write_run_and_auto_fix(self):
        llm = ScriptedLLM({"fails when I run": FIXED}, default=BUGGY)
        j = self.make(llm)
        r = j.handle("اكتب برنامج بايثون يحسب متوسط الأرقام")
        self.assertIn("كتبت البرنامج", r.text)
        r = j.handle("شغل الكود")
        self.assertIn("avg 5.33", r.text)
        self.assertIn("صلّحت", r.text)
        folder = Path(j.config["last_code_project"])
        self.assertTrue(list((folder / ".history").glob("main.*.py")))   # old version kept

    def test_programming_without_ai_explains_how(self):
        j = self.make()
        self.assertIn("Ollama", j.handle("اكتب برنامج يرتب الملفات").text)

    def test_run_works_offline_and_reports_errors(self):
        j = self.make(ScriptedLLM({}, default=BUGGY))
        j.handle("write a python script that prints the average")
        j.router.brains = [OfflineBrain(j.memory, j.config)]      # AI goes away
        r = j.handle("run it")
        self.assertIn("NameError", r.text)
        self.assertIn("Claude or Ollama", r.text)

    def test_program_waiting_for_input_is_not_auto_fixed(self):
        llm = ScriptedLLM({}, default='```python\n# file: main.py\nname = input("name? ")\nprint(name)\n```')
        j = self.make(llm)
        j.handle("write a python program that asks my name")
        r = j.handle("run it")
        self.assertIn("input", r.text)
        self.assertEqual(sum("fails when I run" in p for p in llm.prompts), 0)

    def test_endless_program_is_stopped(self):
        llm = ScriptedLLM({}, default='```python\n# file: main.py\nimport time\nprint("start", flush=True)\n'
                                      'while True:\n    time.sleep(0.1)\n```')
        j = self.make(llm)
        j.config.set("code_timeout", 2)
        j.handle("write a python program that runs forever")
        r = j.handle("run it")
        self.assertIn("2s", r.text)

    def test_modify_existing_project(self):
        llm = ScriptedLLM({"Change it as follows": '```python\n# file: main.py\nprint("hello v2")\n```'},
                          default='```python\n# file: main.py\nprint("hello")\n```')
        j = self.make(llm)
        j.handle("write a python script that says hello")
        j.handle("modify the code: print v2")
        self.assertIn("hello v2", j.handle("run it").text)


class HealerFrozenTests(Base):
    def test_no_pip_inside_packaged_app(self):
        j = self.make()
        with mock.patch.object(sys, "frozen", True, create=True):
            ok, note = j.healer._fix_install_package("skill:office", ModuleNotFoundError("x", name="pptx"), {})
        self.assertFalse(ok)
        self.assertIn("python-pptx", note)


if __name__ == "__main__":
    unittest.main()
