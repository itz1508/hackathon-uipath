"""BEFORE and AFTER with large fixture (22 files, multiple issue types)."""
import sys, os, json, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["Mistral_API_KEY"] = ""

from phase_models import WorkflowInput
from orchestrator import run_pipeline_stateful

FIXTURE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "fixtures", "fixture-large-demo")
PROOF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "proof")
os.makedirs(PROOF, exist_ok=True)

# ════════════════════════════════════════════════════════════════
# BEFORE RUN (isolation OFF — just run pipeline as-is)
# ════════════════════════════════════════════════════════════════
print("=" * 70)
print("BEFORE RUN — Original fixture, no enrichment")
print("=" * 70)

state, output = run_pipeline_stateful(WorkflowInput(case_id="before", target_path=FIXTURE, mode="auto"))
pkg = state.simulation_package
fo = state.final_output

print(f"  Files scanned: {state.snapshot.get('total_files')}")
print(f"  Findings: {len(state.findings)}")
print(f"  Score: {pkg['score']}%")
print(f"  Simulation Ready: {pkg['simulation_ready']}")
print(f"  Ready parts: {len(pkg['ready_parts'])}")
print(f"  Isolated parts: {len(pkg['isolated_parts'])}")
print(f"  Resolved: {fo['resolved_count']}")
print(f"  Unresolved: {fo['unresolved_count']}")
print(f"  Status: {fo['completion_status']}")
print()
print("  Ready items (will be fixed):")
for r in pkg["ready_parts"]:
    print(f"    ✓ {r['item_id']}: [{r['category']}] {r.get('description','')[:45]}")
print("  Isolated items (blocked):")
for i in pkg["isolated_parts"]:
    print(f"    ✗ {i['item_id']}: [{i['category']}] reason={i['isolation_reason']}")
print()

# Save
before = {
    "files": state.snapshot.get("total_files"),
    "findings": len(state.findings),
    "score": pkg["score"],
    "ready": len(pkg["ready_parts"]),
    "isolated": len(pkg["isolated_parts"]),
    "resolved": fo["resolved_count"],
    "unresolved": fo["unresolved_count"],
    "status": fo["completion_status"],
}
with open(os.path.join(PROOF, "large_before.json"), "w") as f:
    json.dump(before, f, indent=2)

# ════════════════════════════════════════════════════════════════
# ISOLATION RESOLUTION — add the missing modules
# ════════════════════════════════════════════════════════════════
print("=" * 70)
print("ISOLATION FIX — Adding missing evidence")
print("=" * 70)

enriched = os.path.join(os.path.dirname(FIXTURE), "fixture-large-demo-enriched")
if os.path.exists(enriched):
    shutil.rmtree(enriched)
shutil.copytree(FIXTURE, enriched)

# Create the ambiguous modules that isolation investigation found
modules_to_create = {
    "generated_api_client.py": '"""Resolved: Generated API client."""\n\nclass RestClient:\n    def __init__(self): pass\n',
    "internal_auth_provider.py": '"""Resolved: Internal auth provider."""\n\nclass TokenService:\n    def get_token(self): return "token"\n',
    "private_db_connector.py": '"""Resolved: Private DB connector."""\n\nclass Connection:\n    def query(self, sql): return []\n',
    "generated_event_client.py": '"""Resolved: Generated event client."""\n\nclass EventPublisher:\n    def send(self, event): return True\n',
}

for name, content in modules_to_create.items():
    with open(os.path.join(enriched, name), "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Created: {name}")

# Fix the broken dependency version
with open(os.path.join(enriched, "requirements.txt"), "w", encoding="utf-8") as f:
    f.write("# Fixed dependencies\nflask>=2.0\nsqlalchemy>=2.0\nrequests>=2.28\npydantic>=2.0\ncelery>=5.0\nredis>=4.0\npandas>=2.0\nmatplotlib>=3.0\n")
print("  Fixed: requirements.txt (valid versions)")
print()

# ════════════════════════════════════════════════════════════════
# AFTER RUN (isolation resolved — enriched fixture)
# ════════════════════════════════════════════════════════════════
print("=" * 70)
print("AFTER RUN — Enriched fixture with isolation resolved")
print("=" * 70)

state2, output2 = run_pipeline_stateful(WorkflowInput(case_id="after", target_path=enriched, mode="auto"))
pkg2 = state2.simulation_package
fo2 = state2.final_output

print(f"  Files scanned: {state2.snapshot.get('total_files')}")
print(f"  Findings: {len(state2.findings)}")
print(f"  Score: {pkg2['score']}%")
print(f"  Simulation Ready: {pkg2['simulation_ready']}")
print(f"  Ready parts: {len(pkg2['ready_parts'])}")
print(f"  Isolated parts: {len(pkg2['isolated_parts'])}")
print(f"  Resolved: {fo2['resolved_count']}")
print(f"  Unresolved: {fo2['unresolved_count']}")
print(f"  Status: {fo2['completion_status']}")
print()

# Save
after = {
    "files": state2.snapshot.get("total_files"),
    "findings": len(state2.findings),
    "score": pkg2["score"],
    "ready": len(pkg2["ready_parts"]),
    "isolated": len(pkg2["isolated_parts"]),
    "resolved": fo2["resolved_count"],
    "unresolved": fo2["unresolved_count"],
    "status": fo2["completion_status"],
}
with open(os.path.join(PROOF, "large_after.json"), "w") as f:
    json.dump(after, f, indent=2)

# ════════════════════════════════════════════════════════════════
# COMPARISON
# ════════════════════════════════════════════════════════════════
print("=" * 70)
print("COMPARISON: BEFORE vs AFTER")
print("=" * 70)
print(f"  {'Metric':<25} {'BEFORE':<15} {'AFTER':<15}")
print(f"  {'─'*25} {'─'*15} {'─'*15}")
print(f"  {'Score':<25} {before['score']}%{'':<10} {after['score']}%")
print(f"  {'Ready parts':<25} {before['ready']:<15} {after['ready']}")
print(f"  {'Isolated parts':<25} {before['isolated']:<15} {after['isolated']}")
print(f"  {'Resolved':<25} {before['resolved']:<15} {after['resolved']}")
print(f"  {'Unresolved':<25} {before['unresolved']:<15} {after['unresolved']}")
print(f"  {'Status':<25} {before['status']:<15} {after['status']}")
print()
print(f"  Saved: proof/large_before.json, proof/large_after.json")

# Cleanup
shutil.rmtree(enriched, ignore_errors=True)
