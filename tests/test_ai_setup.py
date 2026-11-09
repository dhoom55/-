"""Installing and activating the local AI (Ollama), with a fake Ollama and a local download server."""
import functools
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from jarvis import Jarvis
from jarvis import ai_setup
from jarvis.ai_setup import OllamaSetup, pick_model
from jarvis.brains import OllamaBrain, OfflineBrain

FAKE = Path(__file__).with_name("fake_ollama.py")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


POSIX_ONLY = unittest.skipIf(sys.platform == "win32", "fake Ollama install uses a POSIX launcher script")


class OllamaSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jarvis-ai-"))
        self.port = free_port()
        self.env = mock.patch.dict(os.environ, {"FAKE_OLLAMA_PORT": str(self.port), "HOME": str(self.tmp / "home"),
                                                "PATH": "/usr/bin:/bin", "FAKE_OLLAMA_MODELS": ""})
        self.env.start()
        (self.tmp / "home").mkdir()
        self.jarvises, self.procs = [], []

    def tearDown(self):
        for j in self.jarvises:
            j.close()
        if sys.platform != "win32":
            subprocess.run(["pkill", "-f", f"{self.tmp}"], capture_output=True)
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def jarvis(self):
        j = Jarvis(home=self.tmp / "data", brains=[])
        j.config.set("ollama_url", f"http://127.0.0.1:{self.port}")
        j.router.brains = [OllamaBrain(j.config["ollama_url"], "none"), OfflineBrain(j.memory, j.config)]
        j._ai_setup = None
        self.jarvises.append(j)
        return j

    def serve_download(self):
        """Local 'ollama.com' serving an archive whose bin/ollama is the fake server."""
        site = self.tmp / "site"
        site.mkdir()
        launcher = f"#!/bin/sh\nexec {sys.executable} {FAKE} \"$@\"\n".encode()
        with tarfile.open(site / "ollama.tgz", "w:gz") as t:
            info = tarfile.TarInfo("bin/ollama")
            info.size, info.mode = len(launcher), 0o755
            t.addfile(info, io.BytesIO(launcher))
        handler = functools.partial(SimpleHTTPRequestHandler, directory=str(site))
        handler.log_message = lambda *a: None
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        url = f"http://127.0.0.1:{server.server_address[1]}/ollama.tgz"
        return mock.patch.dict(ai_setup.URLS, {"linux-amd64": url, "linux-arm64": url})

    def serve_renamed(self, fmt: str):
        """'ollama.com' answers 404 for the old name; a fake GitHub API points to the new file."""
        site = self.tmp / "site2"
        site.mkdir()
        launcher = f"#!/bin/sh\nexec {sys.executable} {FAKE} \"$@\"\n".encode()
        tar_path = site / "ollama.tar"
        with tarfile.open(tar_path, "w") as t:
            info = tarfile.TarInfo("bin/ollama")
            info.size, info.mode = len(launcher), 0o755
            t.addfile(info, io.BytesIO(launcher))
        if fmt == "zst":
            subprocess.run(["zstd", "-q", "-f", str(tar_path), "-o", str(site / "ollama-linux-amd64.tar.zst")], check=True)
            name = "ollama-linux-amd64.tar.zst"
        else:
            import gzip
            (site / "ollama-linux-amd64.tgz").write_bytes(gzip.compress(tar_path.read_bytes()))
            name = "ollama-linux-amd64.tgz"
        handler = functools.partial(SimpleHTTPRequestHandler, directory=str(site))
        handler.log_message = lambda *a: None
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_address[1]}"
        (site / "latest.json").write_text(json.dumps({"assets": [
            {"name": "ollama-linux-amd64-rocm.tar.zst", "browser_download_url": base + "/nope"},
            {"name": name, "browser_download_url": f"{base}/{name}"}]}))
        return mock.patch.multiple(ai_setup, URLS={"linux-amd64": base + "/old.tgz", "linux-arm64": base + "/old.tgz"},
                                   RELEASES_API=base + "/latest.json")

    @POSIX_ONLY
    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux installer path")
    def test_renamed_download_is_found_via_release_list(self):
        j = self.jarvis()
        with self.serve_renamed("tgz"), mock.patch("platform.machine", return_value="x86_64"):
            j.ai_setup.install()
        self.assertTrue(j.ai_setup.exe())

    @unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("zstd"), "needs zstd")
    def test_zstd_archive(self):
        j = self.jarvis()
        with self.serve_renamed("zst"), mock.patch("platform.machine", return_value="x86_64"):
            j.ai_setup.install()
        self.assertTrue(j.ai_setup.start_server())

    def test_pick_model_by_memory_and_disk(self):
        self.assertEqual(pick_model(32, 100), "qwen2.5:7b")
        self.assertEqual(pick_model(8, 100), "qwen2.5:3b")
        self.assertEqual(pick_model(4, 100), "qwen2.5:1.5b")
        self.assertEqual(pick_model(32, 3), "qwen2.5:1.5b")      # not enough disk for the big one

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux installer path")
    def test_install_start_download_and_answer(self):
        j = self.jarvis()
        self.assertFalse(j.has_ai())
        with self.serve_download():
            r = j.handle("فعّل الذكاء الاصطناعي")
            self.assertIn("أنزّل Ollama", r.text)
            j.ai_setup.thread.join(60)
        notes = "\n".join(j.pending_notifications())
        self.assertIn("تم تثبيت Ollama", notes)
        self.assertIn("✅ الذكاء الاصطناعي المحلي جاهز", notes)
        self.assertIn("100%", notes)
        self.assertTrue((self.tmp / "home/.local/share/jarvis/ollama/bin/ollama").exists())
        model = j.config["ollama_model"]
        self.assertTrue(model.startswith("qwen2.5"))
        r = j.handle("what is the capital of japan?")              # now answered by the local AI
        self.assertEqual(r.source, "brain:ollama")
        self.assertIn(f"ollama({model})", r.text)
        status = j.handle("ai status").text
        self.assertIn("server running", status)
        self.assertIn(model, status)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux installer path")
    def test_healer_restarts_stopped_ollama(self):
        j = self.jarvis()
        with self.serve_download():
            j.ai_setup.install()                                    # installed, but server not running
        self.assertFalse(j.ai_setup.server_up())
        check = next(c for c in j.healer.health_check() if c.name == "brain ollama")
        self.assertEqual(check.fix, "start_ollama")
        notes = j.healer.heal_all()
        self.assertTrue(any("started the local AI" in n for n in notes))
        self.assertTrue(j.ai_setup.server_up())

    def test_uses_existing_model_without_big_download(self):
        os.environ["FAKE_OLLAMA_MODELS"] = "llama3.2:latest"
        proc = subprocess.Popen([sys.executable, str(FAKE), "serve"])
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        j = self.jarvis()
        for _ in range(50):
            if j.ai_setup.server_up():
                break
            time.sleep(0.1)
        with mock.patch.object(OllamaSetup, "exe", return_value=Path("/fake/ollama")), \
                mock.patch.object(OllamaSetup, "pull") as pull:
            self.assertEqual(j.ai_setup.run(), "llama3.2:latest")
        pull.assert_not_called()
        self.assertEqual(j.config["ollama_model"], "llama3.2:latest")

    def test_failure_is_reported_and_recorded(self):
        j = self.jarvis()
        with mock.patch.dict(ai_setup.URLS, {"linux-amd64": "http://127.0.0.1:1/nothing.tgz",
                                             "linux-arm64": "http://127.0.0.1:1/nothing.tgz",
                                             "darwin": "http://127.0.0.1:1/x.zip", "win32": "http://127.0.0.1:1/x.exe"}):
            with self.assertRaises(Exception):
                j.ai_setup.run()
        self.assertEqual(j.ai_setup.stage, "failed")
        self.assertIn("❌", "\n".join(j.pending_notifications()))
        self.assertTrue(any(e["component"] == "ai_setup" for e in j.memory.recent_errors()))

    @POSIX_ONLY
    def test_cancel(self):
        j = self.jarvis()
        j.ai_setup.cancel.set()
        with self.serve_download(), self.assertRaises(ai_setup.SetupCancelled):
            j.ai_setup.run()
        self.assertEqual(j.ai_setup.stage, "cancelled")


if __name__ == "__main__":
    unittest.main()
