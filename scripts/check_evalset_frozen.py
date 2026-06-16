#!/usr/bin/env python3
"""Fail loud if the eval transcript set drifts from the frozen manifest.

Once faculty start scoring, the eval set MUST NOT change: regenerating it (different tiers/count/seed)
silently re-maps every encounter_id to different dialogue, invalidating any scores already collected.
This guard recomputes the set hash and compares it to data/eval_transcripts.FROZEN.json; any mismatch
(added/removed/edited transcript) exits non-zero so it is caught before commit and before scoring.

To intentionally re-freeze (only when NO scoring has started): regenerate, then rewrite the manifest.
"""
from __future__ import annotations

import glob
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "eval_transcripts.FROZEN.json"
EVAL_DIR = ROOT / "data" / "eval_transcripts"


def set_hash(files: list[str]) -> tuple[str, dict[str, str]]:
    per: dict[str, str] = {}
    h = hashlib.sha256()
    for f in sorted(files):
        digest = hashlib.sha256(Path(f).read_bytes()).hexdigest()
        per[Path(f).name] = digest
        h.update(digest.encode())
    return h.hexdigest(), per


def main() -> int:
    if not MANIFEST.exists():
        print(f"FAIL: freeze manifest missing: {MANIFEST}")
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = glob.glob(str(EVAL_DIR / "*.json"))
    if len(files) != manifest["n_transcripts"]:
        print(f"FAIL: eval set has {len(files)} transcripts, frozen at {manifest['n_transcripts']}")
        return 1
    live_hash, live_per = set_hash(files)
    if live_hash != manifest["set_sha256"]:
        changed = sorted(
            n for n in set(live_per) | set(manifest["files"])
            if live_per.get(n) != manifest["files"].get(n)
        )
        print(f"FAIL: eval set drifted from frozen manifest ({MANIFEST.name}).")
        print(f"  frozen {manifest['set_sha256'][:16]} != live {live_hash[:16]}")
        print(f"  changed/added/removed: {changed}")
        print("  The eval set is FROZEN (faculty scoring). Do not regenerate; restore the frozen set,")
        print("  or re-freeze ONLY if no scoring has started.")
        return 1
    print(f"evalset_frozen: PASS ({len(files)} transcripts match {manifest['set_sha256'][:16]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
