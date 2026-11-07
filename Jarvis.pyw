"""Double-click to start Jarvis (Windows: opens without a console window).

Everything stays inside this folder: the program in ./jarvis and all of
Jarvis's memory, settings, backups and logs in ./data. Move the folder
anywhere (e.g. your Desktop) and it keeps working.
"""
import os
import sys
from pathlib import Path

# For a packaged Jarvis.exe the data folder sits next to the .exe.
HERE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("JARVIS_HOME", str(HERE / "data"))
os.environ.setdefault("JARVIS_OUTPUTS", str(HERE / "ملفات جارفيس"))   # documents, presentations, code

if len(sys.argv) >= 4 and sys.argv[1] == "--run-script":   # used by the coding feature
    from jarvis.runner import run as run_script
    raise SystemExit(run_script(sys.argv[2], sys.argv[3]))

if "--selftest" in sys.argv:
    from jarvis.selftest import run
    raise SystemExit(run(HERE))

try:
    from jarvis.gui import main
except ImportError as exc:  # most often: Python installed without tkinter
    print("Jarvis needs Python with tkinter (the standard installer from python.org includes it).")
    print(exc)
    try:
        input("Press Enter to close...")
    except (EOFError, RuntimeError):
        pass
    raise SystemExit(1)

main()
