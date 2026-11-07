"""Build a standalone Jarvis app (no Python needed on the target machine).

    pip install pyinstaller
    python build_exe.py           # -> dist/Jarvis/Jarvis(.exe)

Copy the whole dist/Jarvis folder to the Desktop and double-click Jarvis.exe.
Data (memory, settings, backups, logs, plugins) is created in dist/Jarvis/data.
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Skills and your own plugins are loaded at runtime, so PyInstaller can't see
# their imports. Bundle the standard-library modules they are likely to use.
STDLIB_FOR_PLUGINS = [
    "platform", "ast", "math", "operator", "datetime", "json", "random", "statistics",
    "urllib.request", "urllib.parse", "csv", "uuid", "hashlib", "webbrowser", "subprocess",
    "calendar", "decimal", "fractions", "itertools", "collections", "textwrap", "html",
    "zipfile", "shutil", "glob", "string", "time", "difflib", "socket", "ssl", "base64",
]


def main() -> int:
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--onedir", "--name", "Jarvis",
            "--add-data", f"{HERE / 'jarvis' / 'skills'}{os.pathsep}jarvis/skills",
            "--hidden-import", "jarvis.gui", "--hidden-import", "jarvis.selftest"]
    for mod in STDLIB_FOR_PLUGINS:
        args += ["--hidden-import", mod]
    args += sys.argv[1:] + [str(HERE / "Jarvis.pyw")]
    return subprocess.call(args, cwd=HERE)


if __name__ == "__main__":
    sys.exit(main())
