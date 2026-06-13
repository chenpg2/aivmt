"""Unit tests for the reasoning-tolerant cloud client + M-slot loader (no network)."""

from __future__ import annotations


import pytest

from aivmt.cloud.robust_client import _extract_json_object
from aivmt.cloud.mslot import _normalize_base_url, load_mslot_providers
from aivmt.cloud.providers import CLOUD_PROVIDERS


def test_extract_json_strips_think_prefix() -> None:
    raw = '<think>The user asks for JSON. Let me reason...</think>\n{"score": 0.7}'
    # the client strips <think> before extraction; emulate by extracting from the stripped tail
    import re
    stripped = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    assert _extract_json_object(stripped) == '{"score": 0.7}'


def test_extract_json_handles_nested_braces_and_strings() -> None:
    raw = 'noise {"a": {"b": 1}, "s": "has } brace"} trailing'
    assert _extract_json_object(raw) == '{"a": {"b": 1}, "s": "has } brace"}'


def test_extract_json_fails_loud_when_no_object() -> None:
    with pytest.raises(ValueError, match="no '{'"):
        _extract_json_object("just reasoning, no json here")
    with pytest.raises(ValueError, match="unbalanced"):
        _extract_json_object('{"a": 1')


def test_normalize_base_url_appends_v1_only_when_missing() -> None:
    # Fake hosts only — the no-network guard forbids real provider hostnames in test sources.
    assert _normalize_base_url("https://api.example-llm.test") == "https://api.example-llm.test/v1"
    assert _normalize_base_url("https://x.test/v1") == "https://x.test/v1"
    assert _normalize_base_url("https://x.test/v1/") == "https://x.test/v1"
    assert _normalize_base_url("https://p.test/api/cc_minimax21/v1") == "https://p.test/api/cc_minimax21/v1"


def test_load_mslot_providers_registers_complete_slots(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("M6_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text(
        "M6_API_KEY=sk-secret6\nM6_MODEL_ID=deepseek-v4-pro\nM6_ENDPOINT=https://api.example-llm.test\n"
        "M3_MODEL_ID=incomplete\nM3_ENDPOINT=https://x.test\n",  # M3 has no key -> skipped
        encoding="utf-8",
    )
    registered = load_mslot_providers(env)
    assert "deepseek-v4-pro" in registered
    assert "incomplete" not in registered  # incomplete slot skipped
    p = registered["deepseek-v4-pro"]
    assert p.base_url == "https://api.example-llm.test/v1"
    assert p.env_key_name == "M6_API_KEY"
    import os
    assert os.environ["M6_API_KEY"] == "sk-secret6"  # loaded for fail-loud lookup
    assert CLOUD_PROVIDERS["deepseek-v4-pro"].model_id == "deepseek-v4-pro"
    # cleanup global registry mutation
    CLOUD_PROVIDERS.pop("deepseek-v4-pro", None)


def test_load_mslot_providers_missing_file_fails_loud(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_mslot_providers(tmp_path / "nope.env")
