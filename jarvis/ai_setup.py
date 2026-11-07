"""Install and activate a free local AI brain (Ollama) - no account, no token.

What it does, on Windows, macOS and Linux:
  1. finds Ollama, or downloads and installs it for the current user
       Windows: official installer, silent   macOS: Ollama.app into ~/Applications
       Linux:   official archive into ~/.local/share/jarvis/ollama (no root needed)
  2. starts the Ollama server if it isn't running (the self-healer also does this)
  3. downloads a model that fits the computer's memory (qwen2.5, good at Arabic and code)
  4. switches Jarvis to it

Runs in the background and reports progress through jarvis.notify().
Command line:  python -m jarvis.ai_setup [--model NAME] [--status]
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
DETACHED = 0x00000008 if sys.platform == "win32" else 0

URLS = {
    "win32": "https://ollama.com/download/OllamaSetup.exe",
    "darwin": "https://ollama.com/download/Ollama-darwin.zip",
    "linux-amd64": "https://ollama.com/download/ollama-linux-amd64.tgz",
    "linux-arm64": "https://ollama.com/download/ollama-linux-arm64.tgz",
}
RELEASES_API = "https://api.github.com/repos/ollama/ollama/releases/latest"
# (minimum RAM in GB, model, approximate download in GB)
MODELS = [(15, "qwen2.5:7b", 4.7), (7, "qwen2.5:3b", 1.9), (0, "qwen2.5:1.5b", 1.0)]
MODEL_SIZES = {"qwen2.5:7b": 4.7, "qwen2.5:3b": 1.9, "qwen2.5:1.5b": 1.0, "qwen2.5:0.5b": 0.4}


class SetupCancelled(Exception):
    pass


def ram_gb() -> float:
    try:
        if sys.platform == "win32":
            import ctypes

            class MEMSTAT(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MEMSTAT()
            m.dwLength = ctypes.sizeof(m)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullTotalPhys / 1024 ** 3
        if sys.platform == "darwin":
            return int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout) / 1024 ** 3
        with open("/proc/meminfo") as f:
            return int(f.readline().split()[1]) / 1024 ** 2
    except Exception:
        return 8.0


def pick_model(ram: float, free_gb: float) -> str:
    for min_ram, model, size in MODELS:
        if ram >= min_ram and free_gb >= size + 1.5:
            return model
    return MODELS[-1][1]


class OllamaSetup:
    def __init__(self, jarvis=None, url: str | None = None, notify=None):
        self.j = jarvis
        self.url = (url or (jarvis.config["ollama_url"] if jarvis else "http://localhost:11434")).rstrip("/")
        self.notify = notify or (jarvis.notify if jarvis else print)

    def _say(self, text: str) -> None:
        try:
            self.notify(text)
        except Exception:   # a display problem must never stop the installation
            pass
        self.thread: threading.Thread | None = None
        self.cancel = threading.Event()
        self.stage = "idle"          # idle | installing | starting | downloading | done | failed | cancelled
        self.progress = ""
        self.error = ""

    # ---- detection ---------------------------------------------------------
    @staticmethod
    def home_dir() -> Path:
        return Path.home() / ".local" / "share" / "jarvis" / "ollama"

    def exe(self) -> Path | None:
        found = shutil.which("ollama")
        if found:
            return Path(found)
        candidates = []
        if sys.platform == "win32":
            local = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
            candidates += [Path(local) / "Programs" / "Ollama" / "ollama.exe",
                           Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Ollama" / "ollama.exe"]
        elif sys.platform == "darwin":
            for apps in (Path.home() / "Applications", Path("/Applications")):
                candidates.append(apps / "Ollama.app" / "Contents" / "Resources" / "ollama")
            candidates.append(Path("/usr/local/bin/ollama"))
        else:
            candidates += [self.home_dir() / "bin" / "ollama", Path("/usr/local/bin/ollama"), Path("/usr/bin/ollama")]
        return next((p for p in candidates if p.exists()), None)

    def _get(self, path: str, timeout: float = 3):
        with urllib.request.urlopen(self.url + path, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def server_up(self) -> bool:
        try:
            self._get("/api/tags", 2)
            return True
        except Exception:
            return False

    def models(self) -> list[str]:
        try:
            return [m["name"] for m in self._get("/api/tags").get("models", [])]
        except Exception:
            return []

    def status(self) -> dict:
        exe = self.exe()
        up = self.server_up()
        return {"installed": bool(exe), "exe": str(exe or ""), "running": up, "models": self.models() if up else [],
                "stage": self.stage, "progress": self.progress, "error": self.error}

    # ---- start ---------------------------------------------------------------
    def start_server(self, wait: float = 30) -> bool:
        if self.server_up():
            return True
        exe = self.exe()
        if not exe:
            return False
        log = open(Path(tempfile.gettempdir()) / "jarvis-ollama.log", "ab")
        subprocess.Popen([str(exe), "serve"], stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                         creationflags=NO_WINDOW | DETACHED, start_new_session=(sys.platform != "win32"))
        deadline = time.time() + wait
        while time.time() < deadline:
            if self.server_up():
                return True
            time.sleep(0.5)
        return False

    # ---- install -------------------------------------------------------------
    def _download(self, url: str, dest: Path, label: str) -> Path:
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis-assistant"})
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done, last = 0, -10
            while True:
                if self.cancel.is_set():
                    raise SetupCancelled()
                chunk = r.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                pct = int(done * 100 / total) if total else 0
                self.progress = f"{label}: {done / 1e6:.0f}/{total / 1e6:.0f} MB" if total else f"{label}: {done / 1e6:.0f} MB"
                if total and pct >= last + 10:
                    last = pct - pct % 10
                    self._say(f"⬇️ {label} {last}%")
        return dest

    def install(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="jarvis-ollama-"))
        if sys.platform == "win32":
            setup = self._download(URLS["win32"], tmp / "OllamaSetup.exe", "Ollama")
            self.progress = "installing Ollama…"
            subprocess.run([str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"],
                           check=True, timeout=900, creationflags=NO_WINDOW)
        elif sys.platform == "darwin":
            archive = self._download(URLS["darwin"], tmp / "Ollama-darwin.zip", "Ollama")
            apps = Path.home() / "Applications"
            apps.mkdir(exist_ok=True)
            subprocess.run(["ditto", "-x", "-k", str(archive), str(apps)], check=True, timeout=600)
        else:
            arch = "arm64" if platform.machine().lower() in ("aarch64", "arm64") else "amd64"
            try:
                archive = self._download(URLS[f"linux-{arch}"], tmp / "ollama.tgz", "Ollama")
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise
                url = self._linux_asset(arch)       # the file was renamed: ask GitHub for the current one
                archive = self._download(url, tmp / url.rsplit("/", 1)[-1], "Ollama")
            target = self.home_dir()
            target.mkdir(parents=True, exist_ok=True)
            self._extract(archive, target)
            (target / "bin" / "ollama").chmod(0o755)
        shutil.rmtree(tmp, ignore_errors=True)
        exe = self.exe()
        if not exe:
            raise RuntimeError("Ollama was installed but its program was not found")
        return exe

    @staticmethod
    def _linux_asset(arch: str) -> str:
        """URL of the plain Linux build in Ollama's latest GitHub release (.tgz or .tar.zst)."""
        req = urllib.request.Request(RELEASES_API, headers={"User-Agent": "Jarvis-assistant",
                                                            "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            assets = json.loads(r.read().decode("utf-8")).get("assets", [])
        names = {a["name"]: a["browser_download_url"] for a in assets}
        for ext in (".tgz", ".tar.zst", ".tar.gz"):
            name = f"ollama-linux-{arch}{ext}"
            if name in names:
                return names[name]
        raise RuntimeError(f"no Linux {arch} build in the latest Ollama release: {sorted(names)[:12]}")

    @staticmethod
    def _extract(archive: Path, target: Path) -> None:
        if archive.name.endswith(".zst"):
            try:
                from compression import zstd   # Python 3.14+
                with zstd.open(archive) as raw, tarfile.open(fileobj=raw, mode="r|") as t:
                    t.extractall(target, filter="data")
                return
            except ImportError:
                pass
            if not shutil.which("zstd") and not shutil.which("unzstd"):
                raise RuntimeError("this Ollama build is .tar.zst - install zstd (e.g. sudo apt install zstd)")
            subprocess.run(["tar", "--use-compress-program=unzstd" if shutil.which("unzstd") else "--zstd",
                            "-xf", str(archive), "-C", str(target)], check=True, timeout=900)
            return
        with tarfile.open(archive) as t:
            if hasattr(tarfile, "data_filter"):
                t.extractall(target, filter="data")
            else:
                t.extractall(target)

    # ---- model ---------------------------------------------------------------
    def pull(self, model: str) -> None:
        req = urllib.request.Request(self.url + "/api/pull", data=json.dumps({"model": model, "stream": True}).encode(),
                                     headers={"Content-Type": "application/json"})
        last = -10
        with urllib.request.urlopen(req, timeout=60 * 60) as r:
            for line in r:
                if self.cancel.is_set():
                    raise SetupCancelled()
                if not line.strip():
                    continue
                msg = json.loads(line)
                if msg.get("error"):
                    raise RuntimeError(msg["error"])
                total, done = msg.get("total"), msg.get("completed")
                if total and done is not None:
                    pct = int(done * 100 / total)
                    self.progress = f"{model}: {done / 1e9:.2f}/{total / 1e9:.2f} GB"
                    if total > 50e6 and pct >= last + 10:
                        last = pct - pct % 10
                        self._say(f"🧠 {model} {last}%")
                elif msg.get("status"):
                    self.progress = f"{model}: {msg['status']}"
        if model not in self.models() and f"{model}:latest" not in self.models():
            raise RuntimeError(f"model {model} did not appear after download")

    # ---- whole flow ----------------------------------------------------------
    def run(self, model: str | None = None) -> str:
        """Blocking: install if needed, start, download a model, switch Jarvis to it. Returns the model."""
        try:
            if not self.exe():
                self.stage = "installing"
                self._say("⬇️ أنزّل Ollama وأثبته… / Downloading and installing Ollama…")
                self.install()
                self._say("✅ تم تثبيت Ollama / Ollama installed")
            self.stage = "starting"
            if not self.start_server():
                raise RuntimeError("Ollama is installed but its server did not start")
            have = self.models()
            if not model:
                free = shutil.disk_usage(Path.home()).free / 1e9
                model = pick_model(ram_gb(), free)
                usable = [m for m in have if m.split(":")[0].startswith(("qwen", "llama", "mistral", "gemma", "phi"))]
                if usable and not any(m.startswith(model) for m in have):
                    model = usable[0]          # a model is already there - use it, no big download
            if not any(m == model or m == f"{model}:latest" for m in have):
                self.stage = "downloading"
                size = MODEL_SIZES.get(model)
                self._say(f"🧠 أنزّل نموذج الذكاء {model}" + (f" (~{size} GB)" if size else "") + " …")
                self.pull(model)
            if self.j:
                self.j.config.set("ollama_model", model)
                brain = self.j.router.get("ollama")
                if brain:
                    brain.model, brain._checked_at = model, 0
                self.j.router.reset()
            self.stage, self.progress = "done", ""
            self._say(f"✅ الذكاء الاصطناعي المحلي جاهز ({model}). الحين أقدر أبرمج وأكتب العروض والمستندات بدون إنترنت.\n"
                        f"✅ Local AI is ready ({model}).")
            return model
        except SetupCancelled:
            self.stage = "cancelled"
            self._say("⏹️ أوقفت التثبيت. / Setup cancelled.")
            raise
        except Exception as exc:
            self.stage, self.error = "failed", f"{type(exc).__name__}: {exc}"
            if self.j:
                self.j.healer.record("ai_setup", exc)
            self._say(f"❌ ما قدرت أكمل تثبيت الذكاء الاصطناعي: {exc}\nأعد المحاولة بقول «فعّل الذكاء الاصطناعي».")
            raise

    def start(self, model: str | None = None) -> bool:
        """Non-blocking. Returns False if a setup is already running."""
        if self.thread and self.thread.is_alive():
            return False
        self.cancel.clear()
        self.error = ""

        def work():
            try:
                self.run(model)
            except Exception:
                pass
        self.thread = threading.Thread(target=work, daemon=True)
        self.thread.start()
        return True


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Install and activate Ollama for Jarvis")
    ap.add_argument("--model", help="model to download (default: chosen from your RAM)")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--home", help="Jarvis data folder")
    args = ap.parse_args(argv)
    from .core import Jarvis
    from .text import utf8_console
    utf8_console()
    j = Jarvis(home=args.home)
    s = OllamaSetup(j, notify=lambda m: print(m, flush=True))
    if args.status:
        print(json.dumps(s.status(), indent=2))
        return 0
    s.run(args.model)
    print(json.dumps(s.status(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
