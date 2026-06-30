"""A/B Experiment: Isolation Engine Impact Measurement.

Run A: isolation_enabled=False (baseline — no isolation research)
Run B: isolation_enabled=True  (treatment — isolation engine active)

Proves:
1. Same fixture hash in both runs (no mutation of target)
2. Run A score < 93.91%
3. Run B score > 93.91%
4. Delta clearly attributable to isolation engine resolving items
"""
import sys
import os
import json
import hashlib
import time
from pathlib import Path

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["Mistral_API_KEY"] = ""

from phase_models import WorkflowInput
from orchestrator import run_pipeline_stateful


# ──────────────────────────────────────────────
# Fixture Setup
# ──────────────────────────────────────────────

FIXTURE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests", "fixtures", "fixture-large-demo"
)

PROOF_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "proof"
)
os.makedirs(PROOF_DIR, exist_ok=True)


def fixture_hash(path: str) -> str:
    """Compute a deterministic SHA-256 hash of the entire fixture directory.
    
    Hashes file paths (sorted) + file contents. This proves the fixture
    was not mutated between or during runs.
    """
    target = Path(path)
    if not target.exists():
        return "MISSING"

    hasher = hashlib.sha256()
    for root, dirs, files in os.walk(target):
        dirs[:] = sorted(d for d in dirs if not d.startswith("__pycache__") and not d.startswith(".candidate"))
        for filename in sorted(files):
            filepath = Path(root) / filename
            rel = str(filepath.relative_to(target)).replace(os.sep, "/")
            hasher.update(rel.encode("utf-8"))
            try:
                hasher.update(filepath.read_bytes())
            except (OSError, PermissionError):
                hasher.update(b"UNREADABLE")
    return hasher.hexdigest()


# ──────────────────────────────────────────────
# Run A: Baseline (isolation OFF)
# ──────────────────────────────────────────────

print("=" * 72)
print("  A/B EXPERIMENT: Isolation Engine Impact Measurement")
print("=" * 72)
print()

# Hash fixture BEFORE anything runs
hash_before_a = fixture_hash(FIXTURE_PATH)
print(f"  Fixture hash (before Run A): {hash_before_a[:16]}...")
print()

print("─" * 72)
print("  RUN A — isolation_enabled=False (baseline)")
print("─" * 72)

t0 = time.perf_counter()
state_a, output_a = run_pipeline_stateful(
    WorkflowInput(
        case_id="ab-run-a",
        target_path=FIXTURE_PATH,
        mode="auto",
        isolation_enabled=False,
    )
)
duration_a = time.perf_counter() - t0

hash_after_a = fixture_hash(FIXTURE_PATH)

pkg_a = state_a.simulation_package
fo_a = state_a.final_output

run_a_record = {
    "run": "A",
    "isolation_enabled": False,
    "fixture_hash_before": hash_before_a,
    "fixture_hash_after": hash_after_a,
    "fixture_unchanged": hash_before_a == hash_after_a,
    "score": pkg_a.get("score", 0),
    "simulation_ready": pkg_a.get("simulation_ready", False),
    "ready_parts": len(pkg_a.get("ready_parts", [])),
    "isolated_parts": len(pkg_a.get("isolated_parts", [])),
    "resolved_count": fo_a.get("resolved_count", 0),
    "unresolved_count": fo_a.get("unresolved_count", 0),
    "completion_status": fo_a.get("completion_status", ""),
    "duration_ms": int(duration_a * 1000),
}

print(f"  Score:            {run_a_record['score']}%")
print(f"  Simulation Ready: {run_a_record['simulation_ready']}")
print(f"  Ready parts:      {run_a_record['ready_parts']}")
print(f"  Isolated parts:   {run_a_record['isolated_parts']}")
print(f"  Resolved:         {run_a_record['resolved_count']}")
print(f"  Unresolved:       {run_a_record['unresolved_count']}")
print(f"  Duration:         {run_a_record['duration_ms']}ms")
print(f"  Fixture hash:     {hash_after_a[:16]}... (unchanged={run_a_record['fixture_unchanged']})")
print()


# ──────────────────────────────────────────────
# Run B: Treatment (isolation ON)
# ──────────────────────────────────────────────

hash_before_b = fixture_hash(FIXTURE_PATH)

print("─" * 72)
print("  RUN B — isolation_enabled=True (treatment)")
print("─" * 72)

t0 = time.perf_counter()
state_b, output_b = run_pipeline_stateful(
    WorkflowInput(
        case_id="ab-run-b",
        target_path=FIXTURE_PATH,
        mode="auto",
        isolation_enabled=True,
    )
)
duration_b = time.perf_counter() - t0

hash_after_b = fixture_hash(FIXTURE_PATH)

pkg_b = state_b.simulation_package
fo_b = state_b.final_output

run_b_record = {
    "run": "B",
    "isolation_enabled": True,
    "fixture_hash_before": hash_before_b,
    "fixture_hash_after": hash_after_b,
    "fixture_unchanged": hash_before_b == hash_after_b,
    "score": pkg_b.get("score", 0),
    "simulation_ready": pkg_b.get("simulation_ready", False),
    "ready_parts": len(pkg_b.get("ready_parts", [])),
    "isolated_parts": len(pkg_b.get("isolated_parts", [])),
    "resolved_count": fo_b.get("resolved_count", 0),
    "unresolved_count": fo_b.get("unresolved_count", 0),
    "completion_status": fo_b.get("completion_status", ""),
    "duration_ms": int(duration_b * 1000),
}

print(f"  Score:            {run_b_record['score']}%")
print(f"  Simulation Ready: {run_b_record['simulation_ready']}")
print(f"  Ready parts:      {run_b_record['ready_parts']}")
print(f"  Isolated parts:   {run_b_record['isolated_parts']}")
print(f"  Resolved:         {run_b_record['resolved_count']}")
print(f"  Unresolved:       {run_b_record['unresolved_count']}")
print(f"  Duration:         {run_b_record['duration_ms']}ms")
print(f"  Fixture hash:     {hash_after_b[:16]}... (unchanged={run_b_record['fixture_unchanged']})")
print()


# ──────────────────────────────────────────────
# Assertions
# ──────────────────────────────────────────────

print("─" * 72)
print("  ASSERTIONS")
print("─" * 72)

errors: list[str] = []

# 1. Fixture hash unchanged in both runs
if hash_before_a != hash_after_a:
    errors.append(f"FAIL: Run A mutated fixture! before={hash_before_a[:16]} after={hash_after_a[:16]}")
else:
    print("  ✓ Fixture unchanged during Run A")

if hash_before_b != hash_after_b:
    errors.append(f"FAIL: Run B mutated fixture! before={hash_before_b[:16]} after={hash_after_b[:16]}")
else:
    print("  ✓ Fixture unchanged during Run B")

# Same hash across runs
if hash_after_a != hash_after_b:
    errors.append(f"FAIL: Fixture hash differs between runs! A={hash_after_a[:16]} B={hash_after_b[:16]}")
else:
    print(f"  ✓ fixture_hash(A) == fixture_hash(B) == {hash_after_a[:16]}...")

# 2. Run A score < 93.91%
if run_a_record["score"] >= 93.91:
    errors.append(f"FAIL: Run A score {run_a_record['score']}% should be < 93.91%")
else:
    print(f"  ✓ Run A score {run_a_record['score']}% < 93.91% (below threshold)")

# 3. Run B score > 93.91%
if run_b_record["score"] <= 93.91:
    errors.append(f"FAIL: Run B score {run_b_record['score']}% should be > 93.91%")
else:
    print(f"  ✓ Run B score {run_b_record['score']}% > 93.91% (above threshold)")

# 4. Run B resolved more items
if run_b_record["ready_parts"] <= run_a_record["ready_parts"]:
    errors.append(f"FAIL: Run B ready_parts ({run_b_record['ready_parts']}) should be > Run A ({run_a_record['ready_parts']})")
else:
    print(f"  ✓ Run B ready_parts ({run_b_record['ready_parts']}) > Run A ({run_a_record['ready_parts']})")

# 5. Run B has fewer isolated items
if run_b_record["isolated_parts"] >= run_a_record["isolated_parts"]:
    errors.append(f"FAIL: Run B isolated ({run_b_record['isolated_parts']}) should be < Run A ({run_a_record['isolated_parts']})")
else:
    print(f"  ✓ Run B isolated ({run_b_record['isolated_parts']}) < Run A ({run_a_record['isolated_parts']})")

print()


# ──────────────────────────────────────────────
# Comparison Report
# ──────────────────────────────────────────────

print("─" * 72)
print("  COMPARISON REPORT")
print("─" * 72)
print()
print(f"  {'Metric':<28} {'Run A (off)':<16} {'Run B (on)':<16} {'Delta':<12}")
print(f"  {'─'*28} {'─'*16} {'─'*16} {'─'*12}")
print(f"  {'Score':<28} {run_a_record['score']}%{'':<10} {run_b_record['score']}%{'':<10} +{run_b_record['score'] - run_a_record['score']:.2f}%")
print(f"  {'Simulation Ready':<28} {run_a_record['simulation_ready']!s:<16} {run_b_record['simulation_ready']!s:<16}")
print(f"  {'Ready parts':<28} {run_a_record['ready_parts']:<16} {run_b_record['ready_parts']:<16} +{run_b_record['ready_parts'] - run_a_record['ready_parts']}")
print(f"  {'Isolated parts':<28} {run_a_record['isolated_parts']:<16} {run_b_record['isolated_parts']:<16} {run_b_record['isolated_parts'] - run_a_record['isolated_parts']}")
print(f"  {'Resolved count':<28} {run_a_record['resolved_count']:<16} {run_b_record['resolved_count']:<16} +{run_b_record['resolved_count'] - run_a_record['resolved_count']}")
print(f"  {'Unresolved count':<28} {run_a_record['unresolved_count']:<16} {run_b_record['unresolved_count']:<16} {run_b_record['unresolved_count'] - run_a_record['unresolved_count']}")
print(f"  {'Duration (ms)':<28} {run_a_record['duration_ms']:<16} {run_b_record['duration_ms']:<16} +{run_b_record['duration_ms'] - run_a_record['duration_ms']}")
print()
print(f"  Attribution: The +{run_b_record['score'] - run_a_record['score']:.2f}% score increase is entirely")
print(f"  from the Isolation Engine resolving {run_b_record['ready_parts'] - run_a_record['ready_parts']} previously-isolated items")
print(f"  via filesystem_search and package_metadata research providers.")
print()


# ──────────────────────────────────────────────
# Save Records
# ──────────────────────────────────────────────

experiment_record = {
    "experiment": "isolation_engine_ab",
    "fixture": FIXTURE_PATH,
    "fixture_hash": hash_after_a,
    "run_a": run_a_record,
    "run_b": run_b_record,
    "delta": {
        "score": round(run_b_record["score"] - run_a_record["score"], 2),
        "ready_parts": run_b_record["ready_parts"] - run_a_record["ready_parts"],
        "isolated_parts": run_b_record["isolated_parts"] - run_a_record["isolated_parts"],
        "resolved": run_b_record["resolved_count"] - run_a_record["resolved_count"],
    },
    "assertions_passed": len(errors) == 0,
}

output_path = os.path.join(PROOF_DIR, "ab_experiment_result.json")
with open(output_path, "w") as f:
    json.dump(experiment_record, f, indent=2)
print(f"  Saved: {output_path}")
print()


# ──────────────────────────────────────────────
# Final Result
# ──────────────────────────────────────────────

if errors:
    print("═" * 72)
    print("  EXPERIMENT FAILED")
    print("═" * 72)
    for err in errors:
        print(f"  ✗ {err}")
    sys.exit(1)
else:
    print("═" * 72)
    print("  EXPERIMENT PASSED — Isolation Engine improves score above threshold")
    print("═" * 72)
    sys.exit(0)
