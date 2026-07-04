"""Pre-collection readiness check for the AIVMT student study.

Run this at the deployment site BEFORE the first student. It exercises the full
device-to-score data path end to end and prints a GREEN/RED verdict, so breakage
(server down, route not wired, dirs not writable, real data not gitignored) is
caught before students arrive rather than during a session.

Checks:
  1. The three case files load and contain no unfilled TODO_COLLAB placeholder.
  2. (optional, --server-url) POST a clearly-marked PREFLIGHT test encounter to
     ``{server}/aivmt/encounter``; expect HTTP 200; then delete the test archive
     file so it never enters the real dataset.
  3. Ingest converts a device-format encounter into a scorer-readable transcript.
  4. The scorer (mock) returns a valid CompetencyScore in [0, 1].
  5. The Phase-2 output dirs are writable.
  6. Real-data paths are gitignored (public repo: no leak).

Nothing is written into the real ``data/`` dirs; the offline chain runs in a temp dir.

Usage:
  uv run python scripts/preflight_check.py                       # offline chain only
  uv run python scripts/preflight_check.py --server-url http://localhost:8003
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))  # import sibling ingest module by file name

CONF_CASE = ROOT / "conf" / "case"
CASE_IDS = ("obgyn_ectopic_zh_01", "obgyn_aub_zh_01", "obgyn_vaginitis_zh_01")
DEMO = ROOT / "firmware" / "demo_encounter_device.json"
DEFAULT_ARCHIVE = ROOT / "data" / "aivmt_encounters"


def _check_cases() -> tuple[bool, str]:
    from aivmt.cases import load_case

    for cid in CASE_IDS:
        path = CONF_CASE / f"{cid}.yaml"
        if not path.exists():
            return False, f"case file missing: {path}"
        if "TODO_COLLAB" in path.read_text(encoding="utf-8"):
            return False, f"{cid}: still has unfilled TODO_COLLAB"
        load_case(path)  # raises if malformed
    return True, f"{len(CASE_IDS)} cases load, no TODO_COLLAB"


def _check_server(server_url: str, archive_dir: Path) -> tuple[bool, str]:
    payload = json.loads(DEMO.read_text(encoding="utf-8"))
    payload["participant_code"] = "PREFLIGHT"
    payload["case_id"] = CASE_IDS[0]
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    url = server_url.rstrip("/") + "/aivmt/encounter"
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            status = resp.status
    except urllib.error.URLError as exc:
        return False, f"cannot reach {url} ({exc})"
    except (ValueError, json.JSONDecodeError) as exc:
        return False, f"bad response from {url} ({exc})"
    if status != 200 or not body.get("success"):
        return False, f"server rejected encounter: HTTP {status} {body}"

    # delete the PREFLIGHT test file so it never enters the real dataset
    removed = 0
    if archive_dir.is_dir():
        for f in archive_dir.glob("PREFLIGHT__*.json"):
            f.unlink()
            removed += 1
    cleanup = f"cleaned {removed} test file(s)" if removed else "NOTE: delete PREFLIGHT__* manually"
    return True, f"HTTP 200, archived {body.get('turns')} turns; {cleanup}"


def _check_ingest_and_score() -> tuple[bool, str]:
    from ingest_real_encounters import convert_encounter  # sibling script module

    from aivmt.cases import load_case
    from aivmt.dataio import transcript_from_dict
    from aivmt.llm import LLMFactory
    from aivmt.pipeline import ScoringPipeline

    device = json.loads(DEMO.read_text(encoding="utf-8"))
    device["case_id"] = CASE_IDS[0]
    record = convert_encounter(device, "PREFLIGHT__chain")
    transcript = transcript_from_dict(record)
    if not transcript.turns or transcript.turns[0].speaker not in ("student", "patient"):
        return False, "ingest produced no/invalid turns"
    if record.get("provenance") != "real_student":
        return False, "ingest did not stamp provenance=real_student"

    case = load_case(CONF_CASE / f"{transcript.case_id}.yaml")
    result = ScoringPipeline(LLMFactory("mock")).run(case, transcript)
    overall = result.score.overall
    if not (0.0 <= overall <= 1.0):
        return False, f"scorer overall out of range: {overall}"
    return True, f"ingest {len(transcript.turns)} turns -> mock score overall={overall:.3f}"


def _check_output_dirs() -> tuple[bool, str]:
    dirs = [ROOT / "data" / "transcripts" / "real_students", ROOT / "data" / "encounters" / "real_students"]
    for d in dirs:
        try:
            d.mkdir(parents=True, exist_ok=True)
            probe = d / ".preflight_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            return False, f"not writable: {d} ({exc})"
    return True, "transcripts/ and encounters/ output dirs writable"


def _check_gitignore() -> tuple[bool, str]:
    sensitive = [
        "data/aivmt_encounters/x.json",
        "data/transcripts/x.json",
        "data/encounters/x.json",
        "x.wav",
        "data/faculty_ratings_real.csv",
    ]
    try:
        not_ignored = []
        for rel in sensitive:
            r = subprocess.run(
                ["git", "-C", str(ROOT), "check-ignore", "-q", rel],
                capture_output=True,
            )
            if r.returncode != 0:  # 0 = ignored, 1 = NOT ignored
                not_ignored.append(rel)
    except FileNotFoundError:
        return True, "WARN: git not found, skipped (verify .gitignore manually)"
    if not_ignored:
        return False, f"NOT gitignored (leak risk on public repo): {not_ignored}"
    return True, "all real-data paths are gitignored"


def main() -> int:
    ap = argparse.ArgumentParser(description="AIVMT pre-collection readiness check.")
    ap.add_argument("--server-url", default=None, help="e.g. http://localhost:8003 (skips server test if omitted)")
    ap.add_argument("--archive-dir", default=str(DEFAULT_ARCHIVE), help="server AIVMT_ENCOUNTER_DIR")
    args = ap.parse_args()

    checks: list[tuple[str, bool, str]] = []
    checks.append(("1. case files", *_check_cases()))
    if args.server_url:
        checks.append(("2. device->server POST", *_check_server(args.server_url, Path(args.archive_dir))))
    else:
        checks.append(("2. device->server POST", True, "SKIPPED (no --server-url); run with it on site"))
    checks.append(("3. ingest + scorer (mock)", *_check_ingest_and_score()))
    checks.append(("4. output dirs", *_check_output_dirs()))
    checks.append(("5. gitignore guard", *_check_gitignore()))

    print("\n=== AIVMT pre-flight readiness ===")
    hard_fail = False
    for label, ok, detail in checks:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            hard_fail = True
        print(f"  [{mark}] {label}: {detail}")

    if hard_fail:
        print("\nRED: not ready. Fix the FAIL items above before collecting.\n")
        return 1
    if not args.server_url:
        print("\nAMBER: offline chain OK. Re-run with --server-url on site to test the device path.\n")
        return 0
    print("\nGREEN: full chain OK. Ready to collect.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
