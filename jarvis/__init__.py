"""Jarvis - a personal assistant that learns and repairs itself.

Works with Claude (if a key is set), a local Ollama model (if running),
or fully offline with its own learned knowledge.
"""
from .core import Jarvis, Reply

__version__ = "0.1.0"
__all__ = ["Jarvis", "Reply"]
