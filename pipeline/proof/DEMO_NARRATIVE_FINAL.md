# Audisor — Demo Narrative (Full Detail)

## Hackathon: UiPath AI Agent Developer Track 2
## Team: The One Shot

---

## Business Scenario

Audisor is an automated compliance audit platform for Python codebases.

A user attaches a project folder. The system:
1. Captures the original state (immutable snapshot)
2. Scans for real issues using deterministic tools
3. Evaluates whether it has enough information to fix issues in one shot (93.91% threshold)
4. Fixes what it can on a safe copy (never touches the original)
5. Presents the operator with a before/after view
6. The operator decides: Apply (release the fix) or Cancel (restore original)

Every path produces a report. Nothing is silent. Nothing is skipped.

The right actor does the right task at the right time:
- AI agent: analysis and advisory
- Deterministic tools: actual fixes
- Human operator: final decision

---

## System Architecture

```
UiPath Cloud (Automation Cloud)
    └── isolated-integration (Coded Function package — Python)
            ├── POST /v1/executions     → Submit audit case
            └── GET  /v1/executions/{id}/progress → Poll phases
                        │ HTTP (via Cloudflare tunnel)
                        ▼
              workbench_backend (FastAPI, port 8790)
                        │ Python function call
                        ▼
                pipeline (8-phase engine: Phases 0–7)
                        │
                        ├── Phase 0: Snapshot (SHA-256 capture)
                        ├── Phase 1: Scan (6 deterministic tools)
                        ├── Phase 2: Analysis (Mistral LLM advisory)
                        ├── Phase 3: Pre-simulation (grader-based scoring)
                        │       └── Isolation Engine (bounded research)
                        ├── Phase 4: Simulation (sandbox, proposed changes)
                        ├── Phase 5: Inspection (convergence, hash integrity)
                        ├── Phase 6: Relay (Apply/Cancel decision gate)
                        └── Phase 7: Final Output (resolved.html, handoff)
```

---

## UiPath Components (What Is Actually Running)

| Component | Type | Deployment | Evidence |
|-----------|------|-----------|----------|
| isolated-integration | Coded Function package (Python) | Deployed to UiPath Automation Cloud, folder "Debug_hackaton" | Cloud run 139a9fab succeeded (screenshot: screen16-succeed.png) |
| pipeline | Coded Function package (Python) | Published via `uipath pack` + `uipath publish` to "Audisor" folder | deploy.py runs 184 assertion regression + pack + publish lifecycle |
| workbench_backend | FastAPI (port 8790) | Local server exposed via Cloudflare tunnel | Health check: {"status": "healthy"} |
| UiPath Action Center | Human-in-the-loop fallback | Configured as Phase 6 decision channel | action-center/action-schema.json defines task form |
| BPMN process | Visual reference ONLY | Studio Web (not runtime) | uipath/maestro/workflow.bpmn — documentation for judges |

NOT used: Agent Builder. All agents are custom Python coded functions.

---

## Pipeline Phases (Detail)

### Phase 0 — Snapshot
- Captures SHA-256 hash of every file in target folder
- Creates immutable restore point
- Two copies: user directory + temp
- Always available for Cancel/restore

### Phase 1 — Scan (6 Deterministic Tools)
1. `python -m compileall` — syntax validation
2. `dependency-manifest-inspection` — requirements.txt analysis
3. `import-validation` — AST-based import resolution with typo detection
4. `pyproject-toml-analysis` — PEP 621 metadata validation
5. `lock-file-policy` — lock file presence/absence check
6. `python-version-policy` — version declaration check

Each finding includes: `what_wrong`, `why_it_matters`, `how_to_fix`

### Phase 2 — Analysis
- Calls Mistral AI (model: mistral-small-latest) for LLM advisory
- Produces structured handoff statement (JSON schema)
- Produces classification dossier (per-item: id, type, severity, confidence)
- LLM is advisory only — does not execute, does not decide

### Phase 3 — Pre-simulation (Grader-Based Scoring)

Code graders (blockers — can override any score):
- `scan_hash_verified`: integrity check
- `scope_defined`: classification results exist
- `no_fabricated_findings`: all findings have confidence > 0

Weighted graders (scoring dimensions):
- `claim_support_score` (weight 0.25): confirmed root causes / total
- `conflict_score` (weight 0.15): no file overlaps
- `scope_narrowing_score` (weight 0.15): specificity of findings
- `simulation_executability_score` (weight 0.25): fixable categories / total
- `determinism_score` (weight 0.10): all confirmed
- `information_completeness_score` (weight 0.10): no missing information

Threshold: 93.91% (integer hundredths: round(score*100) >= 9391)
- Exactly 93.91% passes. 93.90% does not.

Routing:
- Score >= 93.91%: all items → simulation
- Score < 93.91%: confirmed + fixable → simulation; unconfirmed/missing info → isolation

#### Isolation Engine (internal, not a phase)
- Executes bounded research via 5 providers:
  - filesystem_search
  - requirements_analysis
  - ast_analysis
  - package_metadata
  - documentation_lookup
- Per item produces: evidence_collected, confidence_before/after, root_cause_confirmed, resolution
- Resolved items reclassified and moved to ready_parts
- Package rescored
- Only score determines simulation authorization

### Phase 4 — Simulation (Sandbox Pattern)
- Creates sandbox in OS temp dir (verified NOT inside target)
- Generates proposed_changes with full before/after content
- Applies changes ONLY to sandbox
- Validates via `python -m compileall`
- Verifies real target is byte-for-byte unchanged

Runtime policy:
- network_allowed: False
- package_install_allowed: False
- target_mutation_allowed: False
- user_code_execution_allowed: False
- sandbox_only: True

### Phase 5 — Inspection
- Convergence gate: waits for ALL branches (simulation + isolation) to report
- Validates no missing items, no duplicates
- Computes inspection hash for integrity
- Produces item traces (forward and backward)

### Phase 6 — Relay (Decision Gate)
- Verifies inspection hash
- Builds before/after diff
- Manual mode: pauses for Apply/Cancel decision (UiPath Action Center fallback)
- Auto mode: applies immediately
- Apply = release candidate to target (not mutation — work already done)
- Cancel = restore from snapshot

### Phase 7 — Final Output
- resolved.html (full HTML report)
- Total issues + root cause per issue
- Handoff report (for unresolved items — complete enough for another agent to continue)
- Forward and backward traces
- Success note OR continuation handoff

---

## A/B Isolation Experiment (Proof)

Same fixture. Same pipeline. Same scoring logic. Only variable: `isolation_enabled`.

| Metric | Run A (OFF) | Run B (ON) | Delta |
|--------|-------------|------------|-------|
| Score | 80.0% | 95.0% | +15.0% |
| Simulation Ready | False | True | unlocked |
| Ready parts | 11 | 15 | +4 |
| Isolated parts | 5 | 1 | -4 |
| Resolved | 11 | 15 | +4 |
| Unresolved | 5 | 1 | -4 |

Fixture hash verified identical in both runs: `9fc2ede5b95548b5...`
Target never mutated.

Attribution: +15% score increase entirely from Isolation Engine resolving 4 ambiguous_import items via package_metadata research provider.

---

## Chaos Test (24/24 Pass)

| Attack Vector | Tests | Result |
|---------------|-------|--------|
| Structure Injection (phases 8, 99, -1) | 5 | PASS |
| Multi-Source Conflict (double-complete, double-start) | 3 | PASS |
| Isolation Abuse (empty inputs) | 2 | PASS |
| Pre-Simulation Gate Collapse (93.91 boundary) | 4 | PASS |
| Simulation Mutation Safety (target unchanged) | 1 | PASS |
| Relay Spoof (fake hash) | 2 | PASS |
| Loop Injection (repeated operations) | 3 | PASS |
| Phase Drift (skip/reverse ordering) | 4 | PASS |

---

## Edge Backend Integration

The Edge backend (`D:\Dev\Edge\edge_backend`) was also run against this repo:
- 29 findings (PEP-based policy checks: editable install, simple API, attestation, provenance)
- Score: 97.81% (ready_for_simulation)
- Isolation: NOT REQUIRED

This proves the pipeline repo passes a production-grade policy scanner.

---

## Coding Agent Roles

| Agent | What It Built | Evidence |
|-------|---------------|----------|
| Claude (Anthropic) | Resolution Planner — analyzes findings, recommends tool invocations. PreSimulation Evaluator Agent (claude-sonnet-4, temp 0) | pipeline/resolution_planner.py, agent_definitions/presimulation_evaluator.json |
| Kiro | State algebra pipeline, isolation engine, scanner (6 detectors), simulation sandbox, phase controller (transition table), resolution report schema | All pipeline/*.py files, .kiro/specs/ |
| Mistral | Phase 2 Analysis LLM advisory — produces risk assessment from scan findings | pipeline/phase_2.py (confirmed: real API call with key 42qURzQt...) |

Key principle: **Tools decide the final result, not LLMs.** The LLM is advisory only — produces a statement. The deterministic tools do the fixes. The graders decide the score. The operator makes the final call.

---

## Artifacts Produced

```
proof/
  resolution_report.json       — Canonical truth object (schema-compliant)
  resolution_report.html       — Plain text report
  ab_experiment_result.json    — A/B isolation comparison
  ab_harness_report.json       — 5-fixture harness results
  ab_harness_report.html       — Visual comparison
  ab_pipeline_demo.html        — Interactive A/B visualizer
  before_3runs.json            — Determinism proof (3 identical runs)
  DEMO_STORY.md                — Presentation script
  EVIDENCE_LOG.md              — Raw terminal evidence
  edge_run/                    — Edge backend scan artifacts (3 runs, 8 JSON files)
```

---

## One-Liner

> "Audisor: a deterministic 8-phase pipeline that scans Python projects, scores information completeness via grader-based evaluation, resolves fixable issues in an isolated sandbox using deterministic tools, and presents the operator with Apply/Cancel on a proven result — orchestrated by UiPath, powered by the principle that tools decide, not LLMs."

---

## Demo Flow (5 minutes)

1. (30s) Architecture — show the three-layer chain
2. (30s) UiPath Cloud — show the cloud run succeeded (screenshot)
3. (60s) Run the pipeline — show Phase 1-7 output
4. (60s) A/B Isolation — show score jump from 80% to 95% with same input
5. (30s) Simulation — show sandbox isolation + proposed changes
6. (30s) Final output — show resolution report
7. (30s) Chaos test — 24/24 pass, system resists adversarial attacks
8. (30s) Close — "Tools decide. Not LLMs."
