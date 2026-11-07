"""Run a Python script and capture everything it prints into a file.

    python -m jarvis.runner SCRIPT OUTPUT_FILE
    Jarvis.exe --run-script SCRIPT OUTPUT_FILE      (the packaged app carries its own Python)

Used by the coding feature so programs run the same way with or without a
Python installation, and so output is captured even from the windowed .exe.
"""
from __future__ import annotations

import os
import runpy
import sys
import traceback


def run(script: str, output: str) -> int:
    script = os.path.abspath(script)
    code = 0
    with open(output, "w", encoding="utf-8", errors="replace") as out:
        old = sys.stdout, sys.stderr, sys.stdin, sys.argv[:], os.getcwd()
        sys.stdout = sys.stderr = out
        sys.stdin = open(os.devnull, encoding="utf-8")   # programs must not wait for typing
        sys.argv = [script]
        os.chdir(os.path.dirname(script))
        sys.path.insert(0, os.path.dirname(script))
        try:
            runpy.run_path(script, run_name="__main__")
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
            if not isinstance(e.code, (int, type(None))):
                print(e.code)
        except BaseException:
            traceback.print_exc()
            code = 1
        finally:
            out.flush()
            sys.stdin.close()
            sys.stdout, sys.stderr, sys.stdin, sys.argv, cwd = old
            os.chdir(cwd)
    return code


if __name__ == "__main__":
    sys.exit(run(sys.argv[1], sys.argv[2]))
