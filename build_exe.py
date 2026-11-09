"""Build a standalone Jarvis app (no Python needed on the target machine).

    pip install pyinstaller -r requirements-optional.txt
    python build_exe.py           # -> dist/Jarvis/Jarvis(.exe)

Copy the whole dist/Jarvis folder to the Desktop and double-click Jarvis.exe.
Data (memory, settings, backups, logs, plugins) is created in dist/Jarvis/data.
"""
import importlib.util
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


# Loaded lazily by skills, so list them explicitly.
JARVIS_MODULES = ["jarvis.runner", "jarvis.coder", "jarvis.office", "jarvis.voice", "jarvis.ai_setup",
                  "jarvis.agent_x"]
# python-pptx / python-docx (PowerPoint, Word), edge_tts (natural voices),
# speech_recognition + pyaudio (microphone).
OPTIONAL_PACKAGES = ["pptx", "docx", "edge_tts", "speech_recognition", "pyaudio"]


def main() -> int:
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--onedir", "--name", "Jarvis",
            "--add-data", f"{HERE / 'jarvis' / 'skills'}{os.pathsep}jarvis/skills",
            "--hidden-import", "jarvis.gui", "--hidden-import", "jarvis.selftest",
            "--additional-hooks-dir", str(HERE / "packaging" / "hooks")]
    for mod in STDLIB_FOR_PLUGINS + JARVIS_MODULES:
        args += ["--hidden-import", mod]
    # Optional features: bundled when the package is installed in the build environment.
    for pkg in OPTIONAL_PACKAGES:
        if importlib.util.find_spec(pkg):
            # speech_recognition's data comes from packaging/hooks (FLAC encoder only, no 40 MB models)
            args += ["--hidden-import", pkg] + ([] if pkg == "speech_recognition" else ["--collect-data", pkg])
        else:
            print(f"note: {pkg} not installed - that feature will be missing from this build")
    args += sys.argv[1:] + [str(HERE / "Jarvis.pyw")]
    return subprocess.call(args, cwd=HERE)


if __name__ == "__main__":
    sys.exit(main())
