"""Input contract for the SQ1 scoring-validity phase.

Inputs:
  - encounters_dir: directory of scored-encounter JSONs (see aivmt.dataio.encounter_to_dict)
  - faculty_csv: blinded faculty rating sheet (see aivmt.dataio.FACULTY_SHEET_FIELDS)
No silent fallback: a violated assumption raises, it is never worked around.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]


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
        overall = data["score"].get("overall")
        assert overall is not None and not math.isnan(float(overall)), f"{f.name}: bad overall"
        assert 0.0 <= float(overall) <= 1.0, f"{f.name}: overall out of [0,1]"
        assert data["encounter_id"] not in enc_ids, f"duplicate encounter_id {data['encounter_id']}"
        enc_ids.add(data["encounter_id"])

    with fac_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows, f"empty faculty csv: {fac_path}"
    required = {"encounter_id", "overall"}
    assert required <= set(rows[0].keys()), f"faculty csv missing columns {required - set(rows[0])}"

    fac_ids = {r["encounter_id"] for r in rows if r["encounter_id"]}
    overlap = enc_ids & fac_ids
    assert overlap, "no overlapping encounter_id between system encounters and faculty ratings"

    for r in rows:
        val = r.get("overall", "")
        if val not in ("", None):
            v = float(val)
            assert 0.0 <= v <= 1.0, f"faculty overall out of [0,1] for {r['encounter_id']}"
