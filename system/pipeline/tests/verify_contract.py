"""Verify WorkflowOutput contract matches CURRENT_CONTRACT.md expectations."""
import sys
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import main, WorkflowInput

BASE = str(Path(__file__).resolve().parent / "fixtures") + "/"

# Required top-level fields per CURRENT_CONTRACT.md
REQUIRED_FIELDS = [
    "case_id", "execution_id", "pipeline_status", "current_phase",
    "current_phase_name", "phase_results", "branch_status", "snapshot_id",
    "decision_required", "decision_endpoint", "action_center_fallback",
    "final_output", "error", "message",
]

# Required PhaseResult fields
PHASE_RESULT_FIELDS = ["phase", "phase_name", "exit_status", "required_outputs", "timestamp", "duration_ms"]

print("=" * 70)
print("CONTRACT VERIFICATION")
print("=" * 70)

pass_count = 0
fail_count = 0

def check(name, condition, detail=""):
    global pass_count, fail_count
    if condition:
        pass_count += 1
        print(f"  PASS: {name}")
    else:
        fail_count += 1
        print(f"  FAIL: {name} — {detail}")

# Test with auto mode (full pipeline)
inp = WorkflowInput(case_id="CONTRACT-TEST", target_path=BASE + "fixture-g-mixed", mode="auto")
out = main(inp)
out_dict = out.model_dump()

print("\n1. Top-level fields present:")
for field in REQUIRED_FIELDS:
    check(f"field '{field}'", field in out_dict, f"missing from output")

print("\n2. pipeline_status is valid enum:")
valid_statuses = {"accepted", "running", "awaiting_decision", "succeeded", "failed", "cancelled"}
check("pipeline_status valid", out_dict["pipeline_status"] in valid_statuses, out_dict["pipeline_status"])

print("\n3. Phase results (7 phases in auto mode):")
check("7 phase results", len(out_dict["phase_results"]) == 7, f"got {len(out_dict['phase_results'])}")

print("\n4. Each phase result has required fields:")
for pr in out_dict["phase_results"]:
    phase = pr.get("phase", "?")
    for field in PHASE_RESULT_FIELDS:
        check(f"phase {phase} has '{field}'", field in pr, f"missing from phase {phase}")

print("\n5. Phase order is 0,1,2,3,4,5,6:")
phases = [pr["phase"] for pr in out_dict["phase_results"]]
check("phase order correct", phases == [0, 1, 2, 3, 4, 5, 6], f"got {phases}")

print("\n6. Branch status fields:")
bs = out_dict.get("branch_status", {})
for field in ["simulation_parts", "isolation_items", "branch_outcomes", "convergence_status", "all_converged"]:
    check(f"branch_status.{field}", field in bs, "missing")

print("\n7. final_output has content (auto mode):")
fo = out_dict.get("final_output", {})
check("final_output not empty", bool(fo), "empty dict")
check("has resolved_html", "resolved_html" in fo, "missing")
check("has total_issues", "total_issues" in fo, "missing")
check("has completion_status", "completion_status" in fo, "missing")

print("\n8. Manual mode produces decision_required=True:")
inp_manual = WorkflowInput(case_id="CONTRACT-MANUAL", target_path=BASE + "fixture-k-apply", mode="manual")
out_manual = main(inp_manual)
check("decision_required=True", out_manual.decision_required == True, str(out_manual.decision_required))
check("pipeline_status=awaiting_decision", str(out_manual.pipeline_status) == "PipelineStatus.AWAITING_DECISION", str(out_manual.pipeline_status))
check("decision_endpoint present", bool(out_manual.decision_endpoint), "empty")

print(f"\n{'=' * 70}")
print(f"SUMMARY: {pass_count} PASSED, {fail_count} FAILED")
print(f"{'=' * 70}")

if fail_count:
    sys.exit(1)
