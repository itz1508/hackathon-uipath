"""End-to-end fixture regression: A, G, H, I, J, K in auto and manual modes."""
# Modified: 2026-06-22T22:25:00Z
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import main, WorkflowInput

BASE = str(Path(__file__).resolve().parent / "fixtures") + "/"

fixtures = [
    ("A-auto", "fixture-a-clean", "auto"),
    ("G-auto", "fixture-g-mixed", "auto"),
    ("H-auto", "fixture-h-sim-failure", "auto"),
    ("I-auto", "fixture-i-unfixable", "auto"),
    ("J-auto", "fixture-j-cancel", "auto"),
    ("K-auto", "fixture-k-apply", "auto"),
    ("J-manual", "fixture-j-cancel", "manual"),
    ("K-manual", "fixture-k-apply", "manual"),
]

print("=" * 90)
print(f"{'Fixture':<12} {'Status':<22} {'Phases':<8} {'Resolved':<10} {'Unresolved':<12} {'DecReq'}")
print("-" * 90)

all_pass = True
for name, fixture, mode in fixtures:
    inp = WorkflowInput(case_id=f"CASE-{name}", target_path=BASE + fixture, mode=mode)
    out = main(inp)
    fo = out.final_output
    status = str(out.pipeline_status).split(".")[1]
    phases = len(out.phase_results)
    resolved = fo.get("resolved_count", "-")
    unresolved = fo.get("unresolved_count", "-")
    dec_req = out.decision_required

    print(f"{name:<12} {status:<22} {phases:<8} {resolved:<10} {unresolved:<12} {dec_req}")

    # Validation
    if mode == "auto":
        if status != "SUCCEEDED":
            print(f"  FAIL: expected SUCCEEDED, got {status}")
            all_pass = False
    elif mode == "manual":
        if status != "AWAITING_DECISION":
            print(f"  FAIL: expected AWAITING_DECISION, got {status}")
            all_pass = False
        if not dec_req:
            print(f"  FAIL: decision_required should be True")
            all_pass = False

print("-" * 90)
if all_pass:
    print("ALL FIXTURES PASSED")
else:
    print("SOME FIXTURES FAILED")
    sys.exit(1)
