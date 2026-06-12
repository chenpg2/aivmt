"""Input contract for the SQ1 scoring-validity phase.

Inputs:
  - encounters_dir: directory of scored-encounter JSONs (see aivmt.dataio.encounter_to_dict).
    Each must carry the overall score AND the subscores the validity suite analyses: the five
    SEGUE domains, history_completion, and reasoning.
  - faculty_csv: filled blinded faculty rating sheet (long format, FACULTY_SHEET_FIELDS) with a
    rater_id and >=2 distinct raters, scoring the same dimensions.
No silent fallback: a violated assumption raises, it is never worked around.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Union

from aivmt.metrics.validity import ALL_DIMENSIONS, SEGUE_DOMAINS

PathLike = Union[str, Path]

#: Faculty CSV columns the validity suite requires (beyond identifiers).
_REQUIRED_FACULTY_COLUMNS = {"encounter_id", "rater_id", *ALL_DIMENSIONS}


def _check_unit_interval(value: object, ctx: str) -> None:
    v = float(value)  # type: ignore[arg-type]
    assert not math.isnan(v), f"{ctx}: NaN value"
    assert 0.0 <= v <= 1.0, f"{ctx}: value {v} out of [0,1]"


def check_scoring_validity_inputs(encounters_dir: PathLike, faculty_csv: PathLike) -> None:
    enc_dir = Path(encounters_dir)
    fac_path = Path(faculty_csv)
    assert enc_dir.is_dir(), f"encounters dir missing: {enc_dir}"
    assert fac_path.is_file(), f"faculty ratings csv missing: {fac_path}"

    enc_files = sorted(enc_dir.glob("*.json"))
    assert enc_files, f"no encounter JSON files in {enc_dir}"

    enc_ids: set[str] = set()
    for f in enc_files:
        data = json.loads(f.read_text(encoding="utf-8"))
        for key in ("encounter_id", "score"):
            assert key in data, f"{f.name}: missing key '{key}'"
        score = data["score"]
        _check_unit_interval(score.get("overall"), f"{f.name}: overall")
        for dim in ("history_completion", "reasoning"):
            assert dim in score, f"{f.name}: missing subscore '{dim}'"
            _check_unit_interval(score[dim], f"{f.name}: {dim}")
        segue = score.get("segue")
        assert isinstance(segue, dict), f"{f.name}: missing 'segue' subscore object"
        for dom in SEGUE_DOMAINS:
            assert dom in segue, f"{f.name}: missing SEGUE domain '{dom}'"
            _check_unit_interval(segue[dom], f"{f.name}: segue.{dom}")
        assert data["encounter_id"] not in enc_ids, f"duplicate encounter_id {data['encounter_id']}"
        enc_ids.add(data["encounter_id"])

    with fac_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows, f"empty faculty csv: {fac_path}"
    missing_cols = _REQUIRED_FACULTY_COLUMNS - set(rows[0].keys())
    assert not missing_cols, f"faculty csv missing columns {missing_cols}"

    raters: set[str] = set()
    fac_ids: set[str] = set()
    for r in rows:
        eid = (r.get("encounter_id") or "").strip()
        if not eid:
            continue
        fac_ids.add(eid)
        rid = (r.get("rater_id") or "").strip()
        assert rid, f"faculty row for encounter {eid!r} has no rater_id"
        raters.add(rid)
        for dim in ALL_DIMENSIONS:
            val = r.get(dim, "")
            assert val not in ("", None), f"faculty[{eid},{rid}]: missing {dim} (no silent imputation)"
            _check_unit_interval(val, f"faculty[{eid},{rid}].{dim}")

    assert len(raters) >= 2, f"need >=2 distinct faculty raters (got {len(raters)})"
    overlap = enc_ids & fac_ids
    assert overlap, "no overlapping encounter_id between system encounters and faculty ratings"
