"""LLM client factory & registry."""

from __future__ import annotations

from typing import Any, Dict, Type

from .base import BaseLLMClient

LLM_REGISTRY: Dict[str, Type[BaseLLMClient]] = {}


def register_llm(name: str):
    """Class decorator that registers an LLM client under ``name``."""

    def decorator(cls: Type[BaseLLMClient]) -> Type[BaseLLMClient]:
        LLM_REGISTRY[name] = cls
        return cls

    return decorator


def LLMFactory(name: str, **kwargs: Any) -> BaseLLMClient:
    """Instantiate a registered LLM client."""
    if name not in LLM_REGISTRY:
        raise KeyError(f"Unknown LLM client '{name}'. Available: {sorted(LLM_REGISTRY)}")
    return LLM_REGISTRY[name](**kwargs)


# Populate the registry (import after register_llm is defined).
from . import mock, openai_compat  # noqa: E402,F401

__all__ = ["BaseLLMClient", "LLM_REGISTRY", "register_llm", "LLMFactory"]
