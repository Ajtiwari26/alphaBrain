"""
alpha_core/safety/__init__.py
Safety Gate package exports.
"""

from alpha_core.safety.gate import (
    MAX_ALLOWED_FILES,
    PROTECTED_PATHS,
    SafetyGate,
    SafetyVerdict,
)

__all__ = [
    "MAX_ALLOWED_FILES",
    "PROTECTED_PATHS",
    "SafetyGate",
    "SafetyVerdict",
]
