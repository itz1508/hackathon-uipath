"""Honest run — no isolation fix. Save as BEFORE record."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["Mistral_API_KEY"] = ""

from phase_models import WorkflowInput
from orchestrator import run_pipeline_stateful

target = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "fixtures", "fixture-demo-split")
state, output = run_pipeline_stateful(WorkflowInput(case_id="before-record", target_path=target, mode="auto"))

pkg = state.simulation_package
sim = state.simulation_result
fo = state.final_output

print("BEFORE RECORD (honest — no isolation fix):")
print(f"  Score: {pkg['score']}%")
print(f"  Threshold: 93.91%")
print(f"  Simulation Ready: {pkg['simulation_ready']}")
print(f"  Ready parts: {len(pkg['ready_parts'])}")
print(f"  Isolated parts: {len(pkg['isolated_parts'])}")
print(f"  Simulation passed: {sim.get('simulation_passed')}")
print(f"  Resolved: {fo['resolved_count']}")
print(f"  Unresolved: {fo['unresolved_count']}")
print(f"  Status: {fo['completion_status']}")
print()
print("  Resolved items:")
for r in fo.get("resolved_items", []):
    print(f"    ✓ {r['item_id']}: {r['root_cause'][:50]}")
print("  Unresolved items:")
for u in fo.get("unresolved_items", []):
    print(f"    ✗ {u['item_id']}: {u['root_cause'][:50]}")
    print(f"      why: {u['why_unresolved']}")

# Save
record = {
    "score": pkg["score"],
    "threshold": 93.91,
    "simulation_ready": pkg["simulation_ready"],
    "ready_parts": len(pkg["ready_parts"]),
    "isolated_parts": len(pkg["isolated_parts"]),
    "resolved": fo["resolved_count"],
    "unresolved": fo["unresolved_count"],
    "status": fo["completion_status"],
    "resolved_items": fo.get("resolved_items", []),
    "unresolved_items": fo.get("unresolved_items", []),
}
proof_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "proof")
os.makedirs(proof_dir, exist_ok=True)
with open(os.path.join(proof_dir, "before_record.json"), "w") as f:
    json.dump(record, f, indent=2, default=str)
print(f"\nSaved: proof/before_record.json")
