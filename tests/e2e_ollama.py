"""End-to-end on a real machine (run in CI): install real Ollama, download a model, answer through it.

    python tests/e2e_ollama.py [MODEL]

Fails (exit 1) unless Jarvis installs + starts Ollama and answers a question with the
`ollama` brain. The coding and presentation checks with the small model are reported only.
"""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jarvis import Jarvis  # noqa: E402
from jarvis.text import utf8_console  # noqa: E402

utf8_console()


def main(model: str) -> int:
    home = Path(tempfile.mkdtemp(prefix="jarvis-e2e-"))
    j = Jarvis(home=home)
    j.config.set("open_created_files", False)
    s = j.ai_setup
    s.notify = lambda m: print("  >", m, flush=True)

    print("before:", s.status(), flush=True)
    t = time.time()
    s.run(model)
    print(f"setup took {time.time() - t:.0f}s; after:", s.status(), flush=True)

    r = j.handle("In one word, what is the capital of France?")
    print(f"[{r.source}] {r.text}", flush=True)
    ok = r.source == "brain:ollama" and "paris" in r.text.lower()

    # Informational: what the small model manages for code and slides
    w = j.handle("write a python script that prints the sum of the numbers from 1 to 10")
    print(f"[code] {w.text[:300]}", flush=True)
    run = j.handle("run it")
    print(f"[run] {run.text[:300]}", flush=True)
    p = j.handle("make a presentation about the solar system 3 slides")
    print(f"[slides] {p.text}", flush=True)

    # Agent X: learn a real topic from real GitHub with the real local AI (required)
    r = j.agent_x.learn("python http requests library")
    print(f"[agent x] {r}", flush=True)
    print(f"[agent x] {j.agent_x.describe(r)}", flush=True)
    # Quality, not just "something was saved": the actual library must be among the sources,
    # and big link collections (awesome-*, public-apis) must not be.
    relevant = "psf/requests" in r["sources"]          # the real Python library
    lists = [src for src in r["sources"] if "awesome" in src.lower() or "public-apis" in src.lower()]
    print(f"[agent x] relevant source: {relevant}; link-list sources: {lists}", flush=True)
    ax_ok = not r["error"] and r["learned"] > 0 and relevant and not lists
    j.router.brains = [b for b in j.router.brains if not b.is_llm]          # go offline
    after = j.handle("python http requests library")
    print(f"[agent x, offline afterwards] [{after.source}] {after.text[:300]}", flush=True)
    ax_ok = ax_ok and "I don't know" not in after.text
    print("AGENT X PASSED" if ax_ok else "AGENT X FAILED", flush=True)
    ok = ok and ax_ok

    j.close()
    print("E2E PASSED" if ok else "E2E FAILED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:0.5b"))
