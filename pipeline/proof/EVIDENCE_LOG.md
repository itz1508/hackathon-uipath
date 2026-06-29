# Evidence Log — Pipeline Execution Records

## Record 1: Fixture-G-Mixed (3 issues → fully resolved)

```
PHASE 0 — SNAPSHOT
  snapshot_id: 544e372c-23c8-431f-b726-5767e3f2ee90
  total_files: 3
  file_hashes count: 3

PHASE 1 — SCAN
  total_findings: 2
  tools_run: 3
    python -m compileall: exit_code=1
    dependency-manifest-inspection: exit_code=0
    import-validation: exit_code=1
  findings:
    [HIGH] SYNTAX_ERROR: Python parser cannot compile this file.
    [HIGH] MISSING_DEPENDENCY: Module 'nonexistent_package_xyz' is imported but not declared

PHASE 2 — ANALYSIS
  total_issues: 2
  critical_count: 0
  high_count: 2
  LLM statement (Mistral): "Key Risks: 1. Syntax Error — Prevents Python from compiling. 2. Missing Dependency — Causes ImportError."
  Handoff: {"total_issues": 2, "files_affected": ["bad_dep.py", "broken_syntax.py"], "root_causes_confirmed": 2}

PHASE 3 — PRE-SIMULATION
  Score: 100.0% (all fixable categories)
  Status: ready_for_simulation
  Ready parts: 3
  Isolated parts: 0
  Code graders: ALL PASS
  Weighted graders: all 1.0

PHASE 4 — SIMULATION
  sandbox_path: C:\Users\itz15\AppData\Local\Temp\edge_simulation_abgh305e
  sandbox_isolated: True
  target_mutation_attempted: False
  real_target_unchanged: True
  simulation_passed: True
  Proposed changes:
    F-001 | modify | broken_syntax.py (def process_data( → def process_data():)
    F-002 | create | pyproject.toml (dependencies = ["nonexistent_package_xyz"])
    F-003 | create | .python-version (3.11)
  resolved_items: ['F-001', 'F-002', 'F-003']
  failed_items: []

PHASE 5 — INSPECTION
  all_converged: True
  inspection_complete: True
  resolved_items: ['F-001', 'F-002', 'F-003']
  unresolved_items: []

PHASE 6 — RELAY
  inspection_hash_verified: True
  decision_status: applied
  resolved_count: 3
  unresolved_count: 0

PHASE 7 — FINAL OUTPUT
  total_issues: 3
  resolved_count: 3
  unresolved_count: 0
  completion_status: fully_resolved
```

---

## Record 2: Full Pipeline Repo (13 issues → fully resolved)

```
PHASE 0 — SNAPSHOT
  total_files: 105
  file_hashes: 105 files hashed

PHASE 1 — SCAN (6 tools)
  python -m compileall: exit_code=1
  dependency-manifest-inspection: exit_code=0
  import-validation: exit_code=1
  pyproject-toml-analysis: exit_code=0
  lock-file-policy: exit_code=1
  python-version-policy: exit_code=0
  total_findings: 13

PHASE 2 — ANALYSIS
  LLM (Mistral): "Key Risks: Runtime Failures from missing deps, Inconsistent Environments, Security"
  Handoff: {"total_issues": 13, "files_affected": 12 files, "root_causes_confirmed": 12}

PHASE 3 — PRE-SIMULATION
  Score: 97.31%
  Status: ready_for_simulation
  Ready parts: 13
  Isolated parts: 0

PHASE 4 — SIMULATION
  sandbox_path: C:\Users\itz15\AppData\Local\Temp\edge_simulation_1nhotcmu
  sandbox_isolated: True
  target_mutation_attempted: False
  target_files_mutated: False
  simulation_passed: True
  real_target_unchanged: True
  Proposed changes: 13
    F-001 | modify | broken_syntax.py
    F-002–F-010 | modify | pyproject.toml (add openai, httpx, pydantic, anthropic, packaging, pipeline, pytest, hypothesis, PIL)
    F-011 | create | requirements.txt
    F-012 | create | requirements.lock
    F-013 | create | .python-version

PHASE 5 — INSPECTION
  all_converged: True
  resolved: 13
  unresolved: 0

PHASE 6 — RELAY
  inspection_hash_verified: True
  decision: applied

PHASE 7 — FINAL OUTPUT
  resolved_count: 13
  unresolved_count: 0
  completion_status: fully_resolved
```

---

## Record 3: Split Routing (score below threshold)

```
PHASE 3 — PRE-SIMULATION (earlier run with 83.33% score)
  Score: 83.33%
  Status: below_threshold
  Simulation Ready: False

  CODE GRADERS:
    scan_hash_verified: passed=True
    scope_defined: passed=True
    no_fabricated_findings: passed=True

  WEIGHTED GRADERS:
    claim_support_score: 1.0000 (weight=0.25)
    conflict_score: 1.0000 (weight=0.15)
    scope_narrowing_score: 1.0000 (weight=0.15)
    simulation_executability_score: 0.3333 (weight=0.25) ← dragged score down
    determinism_score: 1.0000 (weight=0.10)
    information_completeness_score: 1.0000 (weight=0.10)

  Ready parts: 1 (syntax_error → fixable)
  Isolated parts: 2 (missing_dependency, configuration_missing → unfixable at that time)

  ISOLATION HANDOFF:
    packet_status: advisory_isolation
    authority: advisory_isolation_only
    execution_authority: False
    reviewer_targets: ['F-002', 'F-003']
    forbidden_output: ['approval to simulate', 'approval to mutate']
```

---

## Record 4: Chaos Test (24/24 pass)

```
24 passed in 0.41s

TestStructureInjection: 5 PASSED (phases 8, 99, -1 all rejected)
TestMultiSourceConflict: 3 PASSED (double-complete, double-start blocked)
TestIsolationAbuse: 2 PASSED (empty inputs → clean path)
TestPreSimulationGate: 4 PASSED (93.91 passes, 93.90 fails, deterministic)
TestSimulationMutationSafety: 1 PASSED (target byte-for-byte unchanged)
TestRelaySpoofAttack: 2 PASSED (fake hash → rejected)
TestLoopInjection: 3 PASSED (PhaseViolation raised, no infinite loop)
TestPhaseDrift: 4 PASSED (skip/reverse all blocked)
```

---

## Record 5: State Algebra Pipeline Run

```
STATE FLAGS:
  snapshot_locked: True
  scan_complete: True
  analysis_complete: True
  partition_complete: True
  simulation_complete: True
  inspection_complete: True
  relay_complete: True
  final_complete: True
  isolation_active: True

Pipeline completed via state algebra. All phases transformed successfully.
Status: SUCCEEDED
```

---

## Record 6: Both Repos Scanned

```
PIPELINE (12 findings):
  F-001: openai undeclared
  F-002: httpx undeclared
  F-003: pydantic undeclared
  F-004: anthropic undeclared
  F-005: packaging undeclared
  F-006: pipeline undeclared
  F-007: pytest undeclared (7 files)
  F-008: hypothesis undeclared
  F-009: PIL undeclared
  F-010: unused declared deps (info)
  F-011: no lock file
  F-012: Python version declared ✓

EDGE (12 findings):
  F-001: clickhouse_connect undeclared
  F-002: shared undeclared
  F-003: pytest undeclared (18 files)
  F-004–F-006: fastapi undeclared
  F-007: uvicorn undeclared
  F-008: pydantic undeclared
  F-009–F-010: packaging undeclared
  F-011: no lock file
  F-012: Python version declared ✓
```
