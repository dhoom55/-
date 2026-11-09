"""Self-test for a built or installed Jarvis:  Jarvis.exe --selftest

Boots Jarvis in a temporary data folder (your real data is untouched), checks
that the desktop UI toolkit is bundled, that every skill loads, that the
health check is clean, and that typical messages get the expected answers.
Writes the report to selftest.txt next to the program and exits 0 on success.
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path


def run(report_dir: Path) -> int:
    from jarvis.text import utf8_console
    utf8_console()
    lines, failed = [], 0

    def check(name, ok, detail=""):
        nonlocal failed
        failed += not ok
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail else ""))

    def info(name, ok, detail=""):   # reported, but never fails the test (e.g. no speakers on a server)
        lines.append(f"[{'INFO' if ok else 'WARN'}] {name}" + (f": {detail}" if detail else ""))

    try:
        import tkinter  # noqa: F401  (the desktop window needs it)
        check("tkinter bundled", True, f"Tk {tkinter.TkVersion}")
        import jarvis.gui  # noqa: F401
        check("desktop UI module", True)
    except Exception as exc:
        check("desktop UI", False, repr(exc))

    try:
        from jarvis import Jarvis
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["JARVIS_OUTPUTS"] = str(Path(tmp) / "outputs")   # keep the real Desktop folder clean
            j = Jarvis(home=tmp, brains=None)
            j.config.set("open_created_files", False)
            skills = j.skills.skills
            broken = {n: s.error for n, s in skills.items() if s.error}
            check("skills load", not broken and len(skills) >= 5, f"{len(skills)} skills {broken or ''}")
            bad = [c for c in j.healer.health_check() if not c.ok and not c.warn]
            check("health check", not bad, "; ".join(f"{c.name}: {c.detail}" for c in bad))
            cases = [
                ("السلام عليكم", "وعليكم السلام"),
                ("احسب 6 * 7", "42"),
                ("what time is it", ":"),
                ("إذا سألتك من صنعك قل صنعني عبدالله", "صنعني عبدالله"),
                ("من صنعك؟", "صنعني عبدالله"),
                ("افحص نفسك", "memory"),
            ]
            for msg, expect in cases:
                r = j.handle(msg)
                check(f"reply to {msg!r}", expect in r.text, f"[{r.source}] {r.text[:80]!r}")
            _office(j, check)
            _coding(j, check)
            _agent_x(check)
            _voice(j, info, Path(tmp))
            errs = j.memory.recent_errors(5)
            check("no internal errors", not [e for e in errs if not e["component"].startswith(("brain:", "voice"))],
                  "; ".join(f"{e['component']}: {e['message'][:60]}" for e in errs))
            j.close()
    except Exception:
        check("core", False, traceback.format_exc()[-600:])

    lines.append(f"\n{'ALL PASSED' if not failed else f'{failed} FAILED'}")
    text = "\n".join(lines)
    try:
        (report_dir / "selftest.txt").write_text(text, encoding="utf-8")
    except OSError:
        pass
    try:
        print(text)
    except Exception:  # windowed .exe has no console
        pass
    return 1 if failed else 0


def _office(j, check):
    try:
        r = j.handle("اعمل عرض تقديمي عن الطاقة الشمسية: الفكرة، الفوائد، التكلفة")
        pptx = list(j.config.outputs.glob("*.pptx"))
        check("PowerPoint", bool(pptx) and "جهزت" in r.text, pptx[0].name if pptx else r.text[:120])
        r = j.handle("اكتب تقرير وورد عن السلامة")
        docx = list(j.config.outputs.glob("*.docx"))
        check("Word", bool(docx) and "جهزت" in r.text, docx[0].name if docx else r.text[:120])
    except Exception:
        check("Office", False, traceback.format_exc()[-400:])


def _coding(j, check):
    try:
        from jarvis.coder import Coder
        c = Coder(j)
        folder = c.root / "selftest"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "main.py").write_text("import json, math\nprint('sum', sum(range(10)), math.sqrt(16))\n",
                                        encoding="utf-8")
        r = c.run(folder, auto_fix=False)
        check("run a program", r.ok and "sum 45 4.0" in r.output, r.output[-200:])
    except Exception:
        check("run a program", False, traceback.format_exc()[-400:])


def _agent_x(check):
    """The safety check + sandbox Agent X uses before installing a skill it wrote."""
    try:
        from jarvis.agent_x import check_skill_safety, sandbox_test
        good = ("NAME = 'x_echo'\nPATTERNS = [r'^echo (.+)']\nTESTS = ['echo hi']\n"
                "def handle(text, match, jarvis):\n    return match.group(1)\n")
        bad = good + "import subprocess\n"
        ok, detail = sandbox_test(good)
        check("Agent X skill sandbox", ok and check_skill_safety(good) is None
              and "subprocess" in (check_skill_safety(bad) or ""), detail[-150:])
    except Exception:
        check("Agent X skill sandbox", False, traceback.format_exc()[-300:])


def _voice(j, info, tmp: Path):
    try:
        st = j.ai_setup.status()
        info("local AI (Ollama)", True, f"installed={st['installed']} running={st['running']} models={st['models']}")
    except Exception as exc:
        info("local AI (Ollama)", False, str(exc)[:150])
    sp, ls = j.voice.speaker, j.voice.listener
    info("voice engines", True, f"speak={sp.engines()} listen={ls.engines()}")
    for engine in sp.engines():
        for text, tag in (("Good evening sir, all systems are online.", "en"), ("مرحباً سيدي", "ar")):
            out = tmp / f"voice_{engine}_{tag}.wav"
            try:
                getattr(sp, f"_speak_{engine}")(text, tag, out)
                made = [p for p in tmp.glob(f"voice_{engine}_{tag}.*") if p.stat().st_size > 1000]
                info(f"speak {tag} with {engine}", bool(made), made[0].name if made else "no audio file")
            except Exception as exc:
                info(f"speak {tag} with {engine}", False, f"{type(exc).__name__}: {str(exc)[:150]}")
    wav = next(iter(sorted(tmp.glob("voice_*_en.wav"))), None)
    if wav is not None:
        try:
            heard = ls.listen(language="en", from_file=wav)
            info("listen (from recording)", True, f"{ls.last_engine}: {heard!r}")
        except Exception as exc:
            info("listen (from recording)", False, str(exc)[:200])


if __name__ == "__main__":
    sys.exit(run(Path.cwd()))
