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

try:
    from jarvis.gui import main
except ImportError as exc:  # most often: Python installed without tkinter
    print("Jarvis needs Python with tkinter (the standard installer from python.org includes it).")
    print(exc)
    input("Press Enter to close...")
    raise SystemExit(1)

main()
