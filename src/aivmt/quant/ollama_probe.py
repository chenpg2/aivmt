"""Parse ``ollama ps`` / ``ollama list`` for the quant lane's memory (d) and disk (c) measurements.

The pure parsers (:func:`parse_ollama_ps`, :func:`parse_ollama_list`, :func:`parse_size`) take CLI
text and never shell out, so they are unit-tested against captured sample outputs. The thin
:func:`probe_loaded_memory` / :func:`probe_disk_size` wrappers run the real command and parse it.

Fail-loud (AI4S no-silent-fallback): an unparseable line, a missing tag, or a model absent from
``ollama ps`` (i.e. not loaded, so its runtime footprint cannot be measured) raises
:class:`OllamaProbeError` instead of returning a fabricated or zero value.
"""

from __future__ import annotations

import logging
import re
import subprocess
from typing import Final

from .types import DiskUsage, MemoryUsage

logger = logging.getLogger(__name__)


class OllamaProbeError(RuntimeError):
    """An ``ollama`` CLI output could not be parsed or the requested tag was absent."""


#: Ollama renders sizes with the decimal (base-1000) ``HumanBytes`` formatter ("GB", not "GiB").
_UNIT_FACTORS: Final[dict[str, int]] = {
    "B": 1,
    "KB": 1000,
    "MB": 1000**2,
    "GB": 1000**3,
    "TB": 1000**4,
}

#: A size token such as ``"4.7 GB"`` or ``"669 MB"`` (optional space between number and unit).
_SIZE_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([KMGT]?B)\s*$")
_SIZE_INLINE: Final[str] = r"\d+(?:\.\d+)?\s*[KMGT]?B"
_HEX_ID: Final[str] = r"[0-9a-f]{12}"

#: ``ollama list`` row: NAME  ID  SIZE  MODIFIED…
_LIST_ROW: Final[re.Pattern[str]] = re.compile(
    rf"^(\S+)\s+({_HEX_ID})\s+({_SIZE_INLINE})\s+(.*)$"
)
#: ``ollama ps`` row: NAME  ID  SIZE  PROCESSOR  CONTEXT  UNTIL…  (PROCESSOR/UNTIL contain spaces).
_PS_ROW: Final[re.Pattern[str]] = re.compile(
    rf"^(\S+)\s+({_HEX_ID})\s+({_SIZE_INLINE})\s+(.+?)\s+(\d+)\s+.*$"
)


def parse_size(token: str) -> tuple[int, str]:
    """Parse a human size token into ``(bytes, normalized_display)``.

    Raises:
        OllamaProbeError: if the token is not a recognizable ``<number> <unit>`` size.
    """
    m = _SIZE_RE.match(token)
    if m is None:
        raise OllamaProbeError(f"unparseable size token: {token!r}")
    value, unit = float(m.group(1)), m.group(2)
    factor = _UNIT_FACTORS.get(unit)
    if factor is None:  # pragma: no cover - regex constrains the unit set
        raise OllamaProbeError(f"unknown size unit in {token!r}")
    return int(round(value * factor)), f"{m.group(1)} {unit}"


def _data_rows(text: str) -> list[str]:
    """Non-empty, non-header rows from a tabular ``ollama`` listing."""
    rows = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("NAME"):
            continue
        rows.append(line.rstrip())
    return rows


def parse_ollama_list(text: str, model_tag: str) -> DiskUsage:
    """Parse the on-disk size for ``model_tag`` from ``ollama list`` output.

    Raises:
        OllamaProbeError: if the tag is absent or its row cannot be parsed.
    """
    for row in _data_rows(text):
        m = _LIST_ROW.match(row)
        if m is None or m.group(1) != model_tag:
            continue
        size_bytes, display = parse_size(m.group(3))
        return DiskUsage(model_tag=model_tag, size_bytes=size_bytes, size_display=display)
    raise OllamaProbeError(
        f"model {model_tag!r} not found in 'ollama list' output (cannot measure disk size)"
    )


def parse_ollama_ps(text: str, model_tag: str) -> MemoryUsage:
    """Parse the loaded RAM/VRAM footprint for ``model_tag`` from ``ollama ps`` output.

    A model absent from ``ollama ps`` is NOT loaded, so its runtime footprint is unknowable — this
    raises rather than reporting a fake/zero number.

    Raises:
        OllamaProbeError: if the tag is not loaded or its row cannot be parsed.
    """
    for row in _data_rows(text):
        m = _PS_ROW.match(row)
        if m is None or m.group(1) != model_tag:
            continue
        size_bytes, display = parse_size(m.group(3))
        return MemoryUsage(
            model_tag=model_tag,
            size_bytes=size_bytes,
            size_display=display,
            processor=m.group(4).strip(),
            context=int(m.group(5)),
        )
    raise OllamaProbeError(
        f"model {model_tag!r} not loaded (absent from 'ollama ps'); cannot measure runtime memory"
    )


def _run(args: list[str]) -> str:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, check=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise OllamaProbeError(f"failed to run {' '.join(args)!r}: {exc}") from exc
    return proc.stdout


def probe_disk_size(model_tag: str) -> DiskUsage:
    """Run ``ollama list`` and parse the on-disk size for ``model_tag`` (fail-loud)."""
    return parse_ollama_list(_run(["ollama", "list"]), model_tag)


def probe_loaded_memory(model_tag: str) -> MemoryUsage:
    """Run ``ollama ps`` and parse the loaded RAM/VRAM footprint for ``model_tag`` (fail-loud)."""
    return parse_ollama_ps(_run(["ollama", "ps"]), model_tag)


__all__ = [
    "OllamaProbeError",
    "parse_size",
    "parse_ollama_list",
    "parse_ollama_ps",
    "probe_disk_size",
    "probe_loaded_memory",
]
