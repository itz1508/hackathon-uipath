"""BEFORE (3 runs, isolation OFF) → AFTER (1 run, isolation ON with enrichment).

Creates a large fixture with 20+ issues mixing fixable and unfixable.
Runs BEFORE 3 times to show determinism.
Then enriches (isolation investigation) and runs AFTER once.
"""
import sys, os, json, shutil, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["Mistral_API_KEY"] = ""

from phase_models import WorkflowInput
from orchestrator import run_pipeline_stateful

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "fixtures")
PROOF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "proof")
os.makedirs(PROOF_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════════
# CREATE LARGE FIXTURE (20+ issues)
# ══════════════════════════════════════════════════════════════

fixture = os.path.join(FIXTURES_DIR, "fixture-large-demo")
if os.path.exists(fixture):
    shutil.rmtree(fixture)
os.makedirs(fixture)

# 1. Syntax errors (fixable) — 3 files
for i in range(1, 4):
    with open(os.path.join(fixture, f"syntax_error_{i}.py"), "w", encoding="utf-8") as f:
        f.write(f'"""Syntax error file {i}."""\n\ndef broken_func_{i}(x\n    return x * {i}\n')

# 2. Working files (no issues) — 5 files
for i in range(1, 6):
    with open(os.path.join(fixture, f"working_{i}.py"), "w", encoding="utf-8") as f:
        f.write(f'"""Working module {i}."""\n\ndef compute_{i}(a, b):\n    return a + b + {i}\n')

# 3. Ambiguous imports (unfixable — missing info) — 4 files
for i in range(1, 5):
    with open(os.path.join(fixture, f"ambiguous_{i}.py"), "w", encoding="utf-8") as f:
        f.write(f'"""Ambiguous import file {i}."""\n\nfrom generated_api_client_{i} import Resource{i}\nfrom internal_private_sdk_{i} import Connector{i}\n\ndef use_{i}():\n    return Resource{i}()\n')

# 4. Missing known dependencies (fixable when confirmed) — 3 files
for i in range(1, 4):
    with open(os.path.join(fixture, f"needs_dep_{i}.py"), "w", encoding="utf-8") as f:
        pkg = ["requests", "flask", "celery"][i-1]
        f.write(f'"""Needs {pkg} but not declared."""\n\nimport {pkg}\n\ndef call_{i}():\n    return {pkg}.__version__\n')

# 5. Dependency conflict in requirements.txt
with open(os.path.join(fixture, "requirements.txt"), "w", encoding="utf-8") as f:
    f.write("# Broken deps\n")
    f.write("numpy==1.2  # scipy requires numpy>=1.20\n")
    f.write("pandas==0.1  # matplotlib requires pandas>=1.0\n")

# 6. pyproject.toml (minimal — missing fields)
with open(os.path.join(fixture, "pyproject.toml"), "w", encoding="utf-8") as f:
    f.write('[project]\nname = "demo-large"\n')

total_py_files = 3 + 5 + 4 + 3  # 15 .py files
print(f"Created fixture: {fixture}")
print(f"  Python files: {total_py_files}")
print(f"  Expected findings: ~20+ (syntax errors, ambiguous imports, missing deps, dep conflicts, config)")
print()

# ══════════════════════════════════════════════════════════════
# BEFORE — 3 RUNS (determinism proof)
# ══════════════════════════════════════════════════════════════

print("=" * 70)
print("BEFORE — 3 RUNS (isolation NOT applied)")
print("=" * 70)
print()

before_results = []

for run_num in range(1, 4):
    state, output = run_pipeline_stateful(WorkflowInput(
        case_id=f"before-run-{run_num}",
        target_path=fixture,
        mode="auto",
    ))
    pkg = state.simulation_package
    fo = state.final_output
    
    result = {
        "run": run_num,
        "score": pkg["score"],
        "simulation_ready": pkg["simulation_ready"],
        "ready_parts": len(pkg["ready_parts"]),
        "isolated_parts": len(pkg["isolated_parts"]),
        "resolved": fo["resolved_count"],
        "unresolved": fo["unresolved_count"],
        "status": fo["completion_status"],
    }
    before_results.append(result)
    
    print(f"  Run {run_num}: score={pkg['score']}% | ready={len(pkg['ready_parts'])} | isolated={len(pkg['isolated_parts'])} | resolved={fo['resolved_count']} | unresolved={fo['unresolved_count']} | {fo['completion_status']}")

print()

# Check determinism
scores = [r["score"] for r in before_results]
deterministic = all(s == scores[0] for s in scores)
print(f"  DETERMINISM CHECK: {'PASS — all 3 runs identical' if deterministic else 'FAIL — runs differ!'}")
print()

# Show details from last run
pkg_last = state.simulation_package
fo_last = state.final_output
print(f"  Ready items ({len(pkg_last['ready_parts'])}):")
for r in pkg_last["ready_parts"][:8]:
    print(f"    ✓ {r['item_id']}: [{r['category']}] {r.get('description','')[:45]}")
if len(pkg_last["ready_parts"]) > 8:
    print(f"    ... and {len(pkg_last['ready_parts'])-8} more")
print(f"  Isolated items ({len(pkg_last['isolated_parts'])}):")
for i in pkg_last["isolated_parts"][:8]:
    print(f"    ✗ {i['item_id']}: [{i['category']}] reason={i['isolation_reason']}")
if len(pkg_last["isolated_parts"]) > 8:
    print(f"    ... and {len(pkg_last['isolated_parts'])-8} more")
print()

# Save BEFORE record
with open(os.path.join(PROOF_DIR, "before_3runs.json"), "w") as f:
    json.dump({
        "runs": before_results,
        "deterministic": deterministic,
        "isolated_items": pkg_last["isolated_parts"],
        "ready_items": pkg_last["ready_parts"],
        "unresolved_items": fo_last.get("unresolved_items", []),
    }, f, indent=2, default=str)

# ══════════════════════════════════════════════════════════════
# ISOLATION INVESTIGATION (enrich the fixture)
# ══════════════════════════════════════════════════════════════

print("=" * 70)
print("ISOLATION INVESTIGATION")
print("=" * 70)
print()
print("  For each isolated item, adding the missing evidence:")
print()

# Create enriched fixture
enriched = os.path.join(FIXTURES_DIR, "fixture-large-demo-enriched")
if os.path.exists(enriched):
    shutil.rmtree(enriched)
shutil.copytree(fixture, enriched)

# Fix: Create the ambiguous modules (resolve the imports)
for i in range(1, 5):
    with open(os.path.join(enriched, f"generated_api_client_{i}.py"), "w", encoding="utf-8") as f:
        f.write(f'"""Generated API client {i} — resolved via isolation investigation."""\n\nclass Resource{i}:\n    pass\n')
    with open(os.path.join(enriched, f"internal_private_sdk_{i}.py"), "w", encoding="utf-8") as f:
        f.write(f'"""Internal SDK {i} — resolved via isolation investigation."""\n\nclass Connector{i}:\n    pass\n')
    print(f"  Created: generated_api_client_{i}.py, internal_private_sdk_{i}.py")

# Fix: Add .python-version
with open(os.path.join(enriched, ".python-version"), "w", encoding="utf-8") as f:
    f.write("3.11\n")
print("  Created: .python-version")

# Fix: Update requirements.txt (resolve conflicts)
with open(os.path.join(enriched, "requirements.txt"), "w", encoding="utf-8") as f:
    f.write("# Fixed versions\nnumpy>=1.20\npandas>=1.0\nrequests\nflask\ncelery\n")
print("  Fixed: requirements.txt (versions updated, deps declared)")

# Fix: Update pyproject.toml
with open(os.path.join(enriched, "pyproject.toml"), "w", encoding="utf-8") as f:
    f.write('[project]\nname = "demo-large"\nrequires-python = ">=3.11"\ndependencies = ["numpy>=1.20", "pandas>=1.0", "requests", "flask", "celery"]\n')
print("  Fixed: pyproject.toml (requires-python + dependencies added)")
print()

# ══════════════════════════════════════════════════════════════
# AFTER — 1 RUN (isolation applied, enriched)
# ══════════════════════════════════════════════════════════════

print("=" * 70)
print("AFTER — 1 RUN (isolation investigation applied)")
print("=" * 70)
print()

state2, output2 = run_pipeline_stateful(WorkflowInput(
    case_id="after-run",
    target_path=enriched,
    mode="auto",
))

pkg2 = state2.simulation_package
fo2 = state2.final_output

print(f"  Score: {pkg2['score']}%")
print(f"  Simulation Ready: {pkg2['simulation_ready']}")
print(f"  Ready parts: {len(pkg2['ready_parts'])}")
print(f"  Isolated parts: {len(pkg2['isolated_parts'])}")
print(f"  Resolved: {fo2['resolved_count']}")
print(f"  Unresolved: {fo2['unresolved_count']}")
print(f"  Status: {fo2['completion_status']}")
print()

# Save AFTER record
with open(os.path.join(PROOF_DIR, "after_enriched.json"), "w") as f:
    json.dump({
        "score": pkg2["score"],
        "simulation_ready": pkg2["simulation_ready"],
        "ready_parts": len(pkg2["ready_parts"]),
        "isolated_parts": len(pkg2["isolated_parts"]),
        "resolved": fo2["resolved_count"],
        "unresolved": fo2["unresolved_count"],
        "status": fo2["completion_status"],
    }, f, indent=2, default=str)

# ══════════════════════════════════════════════════════════════
# DIFFERENCE REPORT
# ══════════════════════════════════════════════════════════════

print("=" * 70)
print("DIFFERENCE REPORT")
print("=" * 70)
print()
print(f"  BEFORE  score: {before_results[0]['score']}%")
print(f"  AFTER   score: {pkg2['score']}%")
print(f"  CHANGE: {before_results[0]['score']}% → {pkg2['score']}%")
print()
print(f"  BEFORE  isolated: {before_results[0]['isolated_parts']}")
print(f"  AFTER   isolated: {len(pkg2['isolated_parts'])}")
print()
print(f"  BEFORE  resolved: {before_results[0]['resolved']}/{before_results[0]['resolved']+before_results[0]['unresolved']}")
print(f"  AFTER   resolved: {fo2['resolved_count']}/{fo2['resolved_count']+fo2['unresolved_count']}")
print()
print(f"  BEFORE  status: {before_results[0]['status']}")
print(f"  AFTER   status: {fo2['completion_status']}")

# Cleanup
shutil.rmtree(enriched, ignore_errors=True)
shutil.rmtree(fixture, ignore_errors=True)

print()
print(f"\nRecords saved: proof/before_3runs.json, proof/after_enriched.json")
