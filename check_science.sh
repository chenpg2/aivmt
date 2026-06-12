#!/usr/bin/env bash
# Scientific-rigor gate for the AIVMT harness. Run from the project root (AIVMT/).
set -uo pipefail
fail=0

need() {  # need <file> <regex> <label>
  if ! grep -qiE "$2" "$1" 2>/dev/null; then
    echo "FAIL: $1 missing /$2/ ($3)"; fail=1
  fi
}

echo "[science] HYPOTHESIS.md required sections"
need HYPOTHESIS.md "^## +Hypothesis"            "hypothesis"
need HYPOTHESIS.md "null"                        "null hypothesis"
need HYPOTHESIS.md "(ICC|statistical test|kappa)" "pre-registered test"
need HYPOTHESIS.md "(sample size|power|n ?[=≈])"  "sample size / power"
need HYPOTHESIS.md "seed"                         "seed declared"

echo "[science] narrative + reproducibility anchors"
[ -f plan/STORY_LOCK.md ] || { echo "FAIL: plan/STORY_LOCK.md missing"; fail=1; }
[ -f configs/seed.yaml ]  || { echo "FAIL: configs/seed.yaml missing (seed must not be hardcoded)"; fail=1; }

echo "[science] multiple-testing / non-inferiority declared"
grep -qiE "non-inferiority|FDR|Bonferroni|BH|correction|adjust" HYPOTHESIS.md \
  || echo "WARN: no multiple-testing / non-inferiority statement found"

if [ "$fail" -eq 0 ]; then echo "check_science: PASS"; else echo "check_science: FAIL"; exit 1; fi
