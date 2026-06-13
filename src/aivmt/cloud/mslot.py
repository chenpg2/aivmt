"""Load cloud comparators from the user's generic ``M{n}_*`` .env scheme.

The user's keys live in a ``.env`` using a 7-slot generic scheme rather than the named
DEEPSEEK_API_KEY / DASHSCOPE_API_KEY / OPENAI_API_KEY convention:

    M1_API_KEY=...    M1_MODEL_ID=gpt-5.5         M1_ENDPOINT=https://.../v1
    ...
    M6_API_KEY=...    M6_MODEL_ID=deepseek-v4-pro M6_ENDPOINT=https://api.deepseek.com

This module parses those triples into :class:`~aivmt.cloud.providers.CloudProvider` objects, registers
them in ``CLOUD_PROVIDERS`` so ``resolve_provider`` finds them, and loads each key into ``os.environ``
under its ``M{n}_API_KEY`` name (the provider's ``env_key_name``) so the fail-loud key resolution in
``build_cloud_client`` works unchanged. Keys are never logged or written elsewhere.

Endpoint normalization: the OpenAI client appends ``/chat/completions`` to ``base_url``. Every probed
endpoint serves the OpenAI route under ``/v1``, so an endpoint that does not already end in ``/v1`` is
suffixed with it (verified against the live endpoints 2026-06-13).
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from .providers import CLOUD_PROVIDERS, CloudProvider

logger = logging.getLogger(__name__)

#: Slot indices to probe in the .env (M1..M7).
_SLOTS = range(1, 8)
#: A provider name must be a safe slug (no path separators) for filenames/CLI; derived from model_id.
_SLUG_RE = re.compile(r"[^a-z0-9.-]+")


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines from a .env file (ignores blanks/comments, strips quotes)."""
    vals: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        vals[key.strip()] = value.strip().strip('"').strip("'")
    return vals


def _normalize_base_url(endpoint: str) -> str:
    """Ensure the base_url carries the ``/v1`` the OpenAI client expects before ``/chat/completions``."""
    base = endpoint.rstrip("/")
    return base if base.endswith("/v1") else base + "/v1"


def _slug(model_id: str, slot: int) -> str:
    """A CLI-safe, human-readable provider name derived from the model id (falls back to the slot)."""
    slug = _SLUG_RE.sub("-", model_id.lower()).strip("-")
    return slug or f"m{slot}"


def load_mslot_providers(env_path: Path) -> dict[str, CloudProvider]:
    """Register every complete ``M{n}`` slot as a cloud provider and load its key into the environment.

    A slot counts as complete when all of ``M{n}_API_KEY``/``M{n}_MODEL_ID``/``M{n}_ENDPOINT`` are
    present and non-empty. Incomplete slots are skipped with a debug log (not an error — the scheme is
    sparse by design).

    Returns:
        Mapping of provider-name -> CloudProvider for the slots that were registered. Side effects:
        ``CLOUD_PROVIDERS`` is updated and ``os.environ[M{n}_API_KEY]`` is set for each.

    Raises:
        FileNotFoundError: if ``env_path`` does not exist (fail loud — a real run needs the keys).
    """
    if not env_path.exists():
        raise FileNotFoundError(f"cloud key file not found: {env_path}")
    vals = _parse_env_file(env_path)
    registered: dict[str, CloudProvider] = {}
    for slot in _SLOTS:
        key = vals.get(f"M{slot}_API_KEY", "").strip()
        model_id = vals.get(f"M{slot}_MODEL_ID", "").strip()
        endpoint = vals.get(f"M{slot}_ENDPOINT", "").strip()
        if not (key and model_id and endpoint):
            logger.debug("M%d: incomplete slot, skipped", slot)
            continue
        env_key_name = f"M{slot}_API_KEY"
        os.environ[env_key_name] = key  # so build_cloud_client's fail-loud key lookup succeeds
        name = _slug(model_id, slot)
        provider = CloudProvider(
            name=name,
            base_url=_normalize_base_url(endpoint),
            model_id=model_id,
            env_key_name=env_key_name,
            note=f"M{slot} slot from {env_path.name}",
        )
        CLOUD_PROVIDERS[name] = provider
        registered[name] = provider
        logger.info("registered cloud provider %s (M%d: model=%s)", name, slot, model_id)
    return registered


__all__ = ["load_mslot_providers"]
