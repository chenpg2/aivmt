"""Run every registered phase's contract (if inputs present) + negative controls.

Exit 0 only if all present checks pass. Run: `python -m harness.run_all`
"""

from __future__ import annotations

import sys

from harness.registry import PHASE_REGISTRY


def main() -> int:
    failures = 0
    for name, cls in PHASE_REGISTRY.items():
        phase = cls()
        print(f"[phase] {name}")

        if phase.inputs_exist():
            try:
                phase.run()
                print("  contract + run: OK")
            except NotImplementedError as exc:
                print(f"  run pending (contract passed): {exc}")
            except AssertionError as exc:
                print(f"  CONTRACT FAIL: {exc}")
                failures += 1
        else:
            print("  inputs absent -> contract skipped (no real data yet)")

        for check in phase.sanity():
            try:
                result = check()
                print(f"  sanity OK: {result}")
            except AssertionError as exc:
                print(f"  SANITY FAIL: {exc}")
                failures += 1

    print("\nrun_all:", "PASS" if failures == 0 else f"{failures} FAILURE(S)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
