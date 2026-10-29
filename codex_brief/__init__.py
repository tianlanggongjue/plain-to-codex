"""Offline prompt linting and brief building, using only the standard library."""

__version__ = "0.1.0"

from .core import build_brief, lint, load_config

__all__ = ["build_brief", "lint", "load_config", "__version__"]
