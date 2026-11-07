"""Put Jarvis on your Desktop, or build a ready-to-unzip package.

    python install_desktop.py              # copy everything to Desktop/Jarvis + create a launcher
    python install_desktop.py --zip FILE   # build a zip containing the Jarvis folder

After installing, everything lives in one folder on the Desktop:

    Desktop/Jarvis/
        Jarvis.pyw              <- double-click to start (Windows / macOS / Linux with Python)
        Start Jarvis.bat        <- Windows launcher (finds Python for you)
        Start Jarvis.command    <- macOS launcher
        start-jarvis.sh         <- Linux launcher
        jarvis/                 <- the program (brains, skills, memory, self-repair)
        data/                   <- created on first run: memory, settings, backups, logs, your plugins
"""
from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

SRC = Path(__file__).resolve().parent
FILES = ["Jarvis.pyw", "README.md", "requirements-optional.txt"]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "_candidate_*")

BAT = r"""@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul && (start "" pythonw "Jarvis.pyw" & exit /b)
where py >nul 2>nul && (start "" py -3w "Jarvis.pyw" & exit /b)
echo Python was not found. Install it from python.org (tick "Add python.exe to PATH"), then run this again.
start "" https://www.python.org/downloads/
pause
"""
COMMAND = """#!/bin/bash
cd "$(dirname "$0")"
exec python3 Jarvis.pyw
"""
SH = """#!/bin/sh
cd "$(dirname "$0")"
exec python3 Jarvis.pyw
"""
LAUNCHERS = {"Start Jarvis.bat": BAT, "Start Jarvis.command": COMMAND, "start-jarvis.sh": SH}


def desktop_dir() -> Path:
    """The real Desktop folder (handles OneDrive on Windows and localized names on Linux)."""
    if sys.platform == "win32":
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  "[Environment]::GetFolderPath('Desktop')"],
                                 capture_output=True, text=True, timeout=20).stdout.strip()
            if out:
                return Path(out)
        except (OSError, subprocess.SubprocessError):
            pass
        for p in (Path(os.environ.get("USERPROFILE", "~")) / "OneDrive" / "Desktop",
                  Path(os.environ.get("USERPROFILE", "~")) / "Desktop"):
            if p.expanduser().exists():
                return p.expanduser()
    elif sys.platform.startswith("linux"):
        try:
            out = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, timeout=5).stdout.strip()
            if out:
                return Path(out)
        except (OSError, subprocess.SubprocessError):
            pass
    return Path.home() / "Desktop"


def build_folder(dest: Path) -> Path:
    """Copy the program into dest (keeps an existing data/ folder untouched)."""
    dest.mkdir(parents=True, exist_ok=True)
    if (dest / "jarvis").exists():
        shutil.rmtree(dest / "jarvis")
    shutil.copytree(SRC / "jarvis", dest / "jarvis", ignore=IGNORE)
    for f in FILES:
        if (SRC / f).exists():
            shutil.copy2(SRC / f, dest / f)
    for name, body in LAUNCHERS.items():
        p = dest / name
        p.write_text(body, encoding="utf-8", newline="\r\n" if name.endswith(".bat") else "\n")
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    (dest / "data").mkdir(exist_ok=True)
    return dest


def make_shortcut(folder: Path) -> str:
    """Create a clickable icon next to the folder on the Desktop."""
    desktop = folder.parent
    if sys.platform == "win32":
        lnk = desktop / "Jarvis.lnk"
        target = shutil.which("pythonw") or shutil.which("pyw") or sys.executable.replace("python.exe", "pythonw.exe")
        ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
              f"$s.TargetPath='{target}';$s.Arguments='\"{folder / 'Jarvis.pyw'}\"';"
              f"$s.WorkingDirectory='{folder}';$s.Description='Jarvis';$s.Save()")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=30)
        return str(lnk) if lnk.exists() else "(shortcut could not be created; use Start Jarvis.bat)"
    if sys.platform.startswith("linux"):
        entry = desktop / "jarvis.desktop"
        entry.write_text("[Desktop Entry]\nType=Application\nName=Jarvis\nTerminal=false\n"
                         f"Exec=python3 \"{folder / 'Jarvis.pyw'}\"\nPath={folder}\nIcon=utilities-terminal\n",
                         encoding="utf-8")
        entry.chmod(0o755)
        return str(entry)
    return str(folder / "Start Jarvis.command")   # macOS: double-click this file


def build_zip(out: Path) -> Path:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        folder = build_folder(Path(tmp) / "Jarvis")
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(folder.rglob("*")):
                arc = Path("Jarvis") / p.relative_to(folder)
                z.write(p, str(arc))   # keeps dates and the +x bit of the launchers
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zip", type=Path, help="build a zip package instead of installing")
    ap.add_argument("--dest", type=Path, help="install somewhere other than Desktop/Jarvis")
    args = ap.parse_args()
    if args.zip:
        print(f"Package: {build_zip(args.zip)}")
        return 0
    folder = build_folder(args.dest or desktop_dir() / "Jarvis")
    print(f"Jarvis installed in: {folder}")
    print(f"Launcher: {make_shortcut(folder)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
