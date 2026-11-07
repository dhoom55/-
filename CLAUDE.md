# Jarvis

Personal assistant in pure Python (stdlib only). Arabic + English.

- Desktop app: `jarvis/gui.py` (tkinter) via `Jarvis.pyw`; `install_desktop.py` installs to Desktop/Jarvis or builds a zip; `build_exe.py` builds a standalone app
- Run: `python -m jarvis` · one message: `python -m jarvis -c "..."` · health: `--doctor` · repair: `--heal`
- Test: `python -m unittest discover -s tests` (run before every commit)
- Layout: `jarvis/core.py` (message flow) · `brains/` (claude → ollama → offline, with circuit breaker) ·
  `learning.py` (teaching, facts, feedback, caching LLM answers) · `healing.py` (diagnose → ranked fix
  strategies, health checks, tested code repair + rollback) · `memory.py` (SQLite + backups) · `skills/` (plugins)
- Jarvis must keep working with no Anthropic key and no network: never make the offline path depend on Claude.
- New skills: a module with `NAME`, `PATTERNS`, `handle(text, match, jarvis)`, `TESTS`. Patterns are matched
  against normalized text (see `text.normalize`) and the raw lower-cased text.
