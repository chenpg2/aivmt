"""Cloud provider registry for the local-vs-cloud non-inferiority head-to-head.

Each cloud comparator is an OpenAI-compatible endpoint, so it is just a different
``(base_url, api_key, model_id)`` for the EXISTING :class:`~aivmt.llm.openai_compat.OpenAICompatClient`
— this module writes no new HTTP client. A provider is described by an immutable
:class:`CloudProvider` carrying the env-var NAME that holds its key (never the key value, which is
read from ``os.environ`` only at client-construction time and never logged or committed).

Fail-loud: :func:`build_cloud_client` raises :class:`MissingApiKeyError` with an actionable message
when a requested provider's env key is unset. The batch runner catches that to SKIP a keyless
provider with a loud log (partial-key runs still work); nothing degrades silently.

The default comparator table is anchored on the scoop threat: DeepSeek is #1 (AMTES/Liu 2025 used
DeepSeek-V2.5), then Qwen-Max (AMTES also used Qwen-Max), then GPT-4o (ECOSBot communication-ICC
collapse comparator).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..llm.base import BaseLLMClient
from ..utils import get_logger

logger = get_logger(__name__)


class MissingApiKeyError(RuntimeError):
    """Raised when a requested cloud provider's API-key env var is unset (fail-loud, never faked)."""


@dataclass(frozen=True)
class CloudProvider:
    """An OpenAI-compatible cloud comparator (key resolved from ``env_key_name`` at call time)."""

    name: str
    base_url: str
    model_id: str
    env_key_name: str
    #: Free-text note (e.g. which AMTES/ECOSBot comparator this is) for the report; not load-bearing.
    note: str = ""

    def has_key(self) -> bool:
        """True iff the provider's API-key env var is set to a non-empty value."""
        return bool(os.environ.get(self.env_key_name, "").strip())


#: Default comparator table. base_url / model_id per the prompt; keys live ONLY in these env vars.
CLOUD_PROVIDERS: dict[str, CloudProvider] = {
    "deepseek": CloudProvider(
        name="deepseek",
        base_url="https://api.deepseek.com/v1",
        model_id="deepseek-chat",
        env_key_name="DEEPSEEK_API_KEY",
        note="AMTES/Liu 2025 used DeepSeek-V2.5 — #1 comparator (deepseek-chat = V3).",
    ),
    "qwen-max": CloudProvider(
        name="qwen-max",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_id="qwen-max",
        env_key_name="DASHSCOPE_API_KEY",
        note="AMTES also used Qwen-Max (Alibaba DashScope OpenAI-compat mode).",
    ),
    "gpt-4o": CloudProvider(
        name="gpt-4o",
        base_url="https://api.openai.com/v1",
        model_id="gpt-4o",
        env_key_name="OPENAI_API_KEY",
        note="ECOSBot (CKJ 2025) reported GPT-4o communication-subdomain ICC collapse 0.31-0.44.",
    ),
}


def resolve_provider(name: str) -> CloudProvider:
    """Look up a provider by name; raise ``KeyError`` with the available set if unknown."""
    if name not in CLOUD_PROVIDERS:
        raise KeyError(f"unknown cloud provider {name!r}; available: {sorted(CLOUD_PROVIDERS)}")
    return CLOUD_PROVIDERS[name]


def build_cloud_client(provider: CloudProvider, *, temperature: float = 0.0) -> BaseLLMClient:
    """Build an :class:`OpenAICompatClient` for ``provider`` (key read from its env var, fail-loud).

    The key is read from ``os.environ[provider.env_key_name]`` and passed straight to the existing
    client; it is never logged. Reusing the local client guarantees the cloud model is scored through
    the SAME request shape (temperature 0, ``response_format=json_object``) as the local model.

    Raises:
        MissingApiKeyError: if the provider's env-var key is unset/empty.
    """
    key = os.environ.get(provider.env_key_name, "").strip()
    if not key:
        raise MissingApiKeyError(
            f"cloud provider {provider.name!r} requires env var {provider.env_key_name} to be set "
            "(see .env.example); it is unset. Export the key, or omit this provider from --providers."
        )
    from .robust_client import RobustCloudClient  # noqa: PLC0415

    logger.info(
        "built cloud client: provider=%s base_url=%s model=%s (key from $%s)",
        provider.name, provider.base_url, provider.model_id, provider.env_key_name,
    )
    # Cloud comparators use the reasoning-tolerant client (no response_format dependency; strips
    # <think> blocks; generous max_tokens) because the aggregator/reasoning endpoints break the stock
    # client. The local model keeps using OpenAICompatClient, so the local scoring path is unchanged.
    return RobustCloudClient(
        model_id=provider.model_id,
        base_url=provider.base_url,
        api_key=key,
        temperature=temperature,
    )


__all__ = [
    "MissingApiKeyError",
    "CloudProvider",
    "CLOUD_PROVIDERS",
    "resolve_provider",
    "build_cloud_client",
]
