from .base import Brain, BrainError
from .claude import ClaudeBrain
from .offline import OfflineBrain
from .ollama import OllamaBrain
from .router import BrainRouter


def build_brains(config, memory) -> list[Brain]:
    """Create brains in the order set by config['brain_order']; offline is always last."""
    factories = {
        "claude": lambda: ClaudeBrain(config["claude_model"], config["claude_effort"], config["claude_max_tokens"]),
        "ollama": lambda: OllamaBrain(config["ollama_url"], config["ollama_model"]),
    }
    brains = [factories[n]() for n in config["brain_order"] if n in factories]
    brains.append(OfflineBrain(memory, config))
    return brains


__all__ = ["Brain", "BrainError", "BrainRouter", "ClaudeBrain", "OllamaBrain", "OfflineBrain", "build_brains"]
