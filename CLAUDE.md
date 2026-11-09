# Jarvis

Personal assistant in pure Python (stdlib only). Arabic + English.

- Desktop app: `jarvis/gui.py` (tkinter) via `Jarvis.pyw`; `install_desktop.py` installs to Desktop/Jarvis or builds a zip; `build_exe.py` builds a standalone app
- Run: `python -m jarvis` · one message: `python -m jarvis -c "..."` · health: `--doctor` · repair: `--heal`
- Test: `python -m unittest discover -s tests` (run before every commit)
- Layout: `jarvis/core.py` (message flow) · `brains/` (claude → ollama → offline, with circuit breaker) ·
  `learning.py` (teaching, facts, feedback, caching LLM answers) · `healing.py` (diagnose → ranked fix
  strategies, health checks, tested code repair + rollback) · `memory.py` (SQLite + backups) · `skills/` (plugins)
- Features: `voice.py` (TTS edge-tts → SAPI/say/espeak; STT Google → SAPI) · `office.py` (python-pptx/python-docx,
  Arabic RTL; keep OOXML child order valid) · `coder.py` + `runner.py` (write/run/auto-fix code; runner also works
  inside Jarvis.exe via `--run-script`) · `selftest.py` (`Jarvis.exe --selftest`, run on Windows/macOS in CI)
- Agent X (`agent_x.py`): learns gaps from GitHub; reads downloads but NEVER executes downloaded code;
  generated skills must pass `check_skill_safety` + `sandbox_test`. Plan/roadmap in `PLAN.md` (Arabic).
- Optional deps live in `requirements-optional.txt`; import them lazily so the core never needs them.
- Jarvis must keep working with no Anthropic key and no network: never make the offline path depend on Claude.
- New skills: a module with `NAME`, `PATTERNS`, `handle(text, match, jarvis)`, `TESTS`. Patterns are matched
  against normalized text (see `text.normalize`) and the raw lower-cased text.
