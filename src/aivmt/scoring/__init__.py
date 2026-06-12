"""Competency scorer factory & registry."""

from __future__ import annotations

from typing import Any, Dict, Type

from .base import BaseScorer

SCORER_REGISTRY: Dict[str, Type[BaseScorer]] = {}


def register_scorer(name: str):
    """Class decorator that registers a scorer under ``name``."""

    def decorator(cls: Type[BaseScorer]) -> Type[BaseScorer]:
        SCORER_REGISTRY[name] = cls
        return cls

    return decorator


def ScorerFactory(name: str, **kwargs: Any) -> BaseScorer:
    """Instantiate a registered scorer."""
    if name not in SCORER_REGISTRY:
        raise KeyError(f"Unknown scorer '{name}'. Available: {sorted(SCORER_REGISTRY)}")
    return SCORER_REGISTRY[name](**kwargs)


# Populate the registry.
from . import checklist, reasoning, segue  # noqa: E402,F401

__all__ = ["BaseScorer", "SCORER_REGISTRY", "register_scorer", "ScorerFactory"]
