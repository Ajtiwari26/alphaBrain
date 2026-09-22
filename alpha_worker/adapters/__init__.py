"""Worker execution adapters for AlphaBrain."""

from .antigravity import AntigravityAdapter
from .antigravity_live import AntigravityLiveBridge
from .base import BaseAgentAdapter
from .etta import EttaAdapter
from .etta_live import EttaLiveBridge

__all__ = [
    "AntigravityAdapter",
    "AntigravityLiveBridge",
    "BaseAgentAdapter",
    "EttaAdapter",
    "EttaLiveBridge",
]
