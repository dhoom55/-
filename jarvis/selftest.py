"""Self-test for a built or installed Jarvis:  Jarvis.exe --selftest

Boots Jarvis in a temporary data folder (your real data is untouched), checks
that the desktop UI toolkit is bundled, that every skill loads, that the
health check is clean, and that typical messages get the expected answers.
Writes the report to selftest.txt next to the program and exits 0 on success.
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path


def run(report_dir: Path) -> int:
    lines, failed = [], 0

    def check(name, ok, detail=""):
        nonlocal failed
        failed += not ok
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail else ""))

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
            j = Jarvis(home=tmp, brains=None)
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
            errs = j.memory.recent_errors(5)
            check("no internal errors", not [e for e in errs if not e["component"].startswith("brain:")],
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


if __name__ == "__main__":
    sys.exit(run(Path.cwd()))
