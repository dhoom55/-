"""Create the folder "الامن والحماية لوحدات رابغ" on the Desktop and copy the Word plan into it.

    python save_to_desktop.py          (or double-click "حفظ على سطح المكتب.bat" on Windows)

Standard library only. Existing files on the Desktop are never deleted; a file with the same
name is replaced by the newer copy.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = "الامن والحماية لوحدات رابغ"


def desktop_dir() -> Path:
    """The real Desktop (handles OneDrive on Windows and localized names on Linux)."""
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
            out = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True,
                                 text=True, timeout=5).stdout.strip()
            if out:
                return Path(out)
        except (OSError, subprocess.SubprocessError):
            pass
    return Path.home() / "Desktop"


def open_folder(path: Path) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError:
        pass


def main(dest_root: Path | None = None, open_after: bool = True) -> Path:
    dest = (dest_root or desktop_dir()) / FOLDER
    dest.mkdir(parents=True, exist_ok=True)
    for doc in sorted(HERE.glob("*.docx")):
        shutil.copy2(doc, dest / doc.name)
        print(f"تم الحفظ: {dest / doc.name}")
    if open_after:
        open_folder(dest)
    return dest


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
