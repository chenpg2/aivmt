"""Local-vs-cloud scoring head-to-head (scoop defense for the SQ1 validity claim).

AMTES/Liu 2025 (JMIR Med Educ e73419) reported ICC 0.92-0.98 for history-taking scoring on CLOUD
models (DeepSeek-V2.5, Qwen-Max). Our wedge is "first faculty-valid scoring on a LOCAL open model".
This lane defends it by running a LOCAL-vs-CLOUD head-to-head: the SAME scorers, SAME prompts, SAME
(synthetic / de-identified) transcripts through cloud endpoints, reporting whether the local model is
non-inferior to cloud (pre-registered margin delta = 0.10) overall AND per SEGUE domain (ECOSBot
showed cloud communication-subdomain ICC collapses to 0.31-0.44).

ABSOLUTE PHI RULE — structural: the ACTIVE guard is the type gate — the cloud path accepts ONLY a
provenance-stamped :class:`CloudSafeDataset` (synthetic / explicitly de-identified); a raw transcript
list that could originate from real data is refused, which is what keeps PHI off the wire today.
:func:`assert_path_is_offdevice_safe` is a defense-in-depth path check (case-insensitive) that
hard-refuses anything resolving inside ``data/transcripts`` / ``data/encounters``; it is the seam a
FUTURE real-data / ``--transcripts-dir`` run must route through, not yet on an active code path. See
:mod:`aivmt.cloud.provenance`.

Cloud comparators are OpenAI-compatible endpoints, so they reuse the EXISTING
:class:`~aivmt.llm.openai_compat.OpenAICompatClient` (different base_url / key / model_id); no new
HTTP client is written. Keys come from env vars (NAMES only in config; values never committed).
"""

from __future__ import annotations

from .compare import (
    DEFAULT_NI_MARGIN,
    compare_local_vs_cloud,
    score_provider_cell,
)
from .providers import (
    CLOUD_PROVIDERS,
    CloudProvider,
    MissingApiKeyError,
    build_cloud_client,
    resolve_provider,
)
from .provenance import (
    DEIDENTIFIED,
    REAL_DATA_DIRS,
    SYNTHETIC,
    CloudSafeDataset,
    PhiLeakError,
    assert_dataset_cloud_safe,
    assert_path_is_offdevice_safe,
    deidentified_cloud_dataset,
    synthetic_cloud_dataset,
)
from .report import render_markdown, write_local_vs_cloud_artifacts
from .scoring import SEGUE_DOMAINS, DomainScores, score_with_domains
from .types import (
    DomainValidity,
    LocalVsCloudComparison,
    LocalVsCloudDelta,
    ProviderCell,
)

__all__ = [
    # provenance / PHI guard
    "PhiLeakError",
    "CloudSafeDataset",
    "REAL_DATA_DIRS",
    "SYNTHETIC",
    "DEIDENTIFIED",
    "assert_path_is_offdevice_safe",
    "assert_dataset_cloud_safe",
    "synthetic_cloud_dataset",
    "deidentified_cloud_dataset",
    # providers
    "MissingApiKeyError",
    "CloudProvider",
    "CLOUD_PROVIDERS",
    "resolve_provider",
    "build_cloud_client",
    # scoring
    "DomainScores",
    "score_with_domains",
    "SEGUE_DOMAINS",
    # compare
    "DEFAULT_NI_MARGIN",
    "score_provider_cell",
    "compare_local_vs_cloud",
    # types
    "DomainValidity",
    "ProviderCell",
    "LocalVsCloudDelta",
    "LocalVsCloudComparison",
    # report
    "render_markdown",
    "write_local_vs_cloud_artifacts",
]
