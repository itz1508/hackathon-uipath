# Edge Pipeline — Demo Story

## Hackathon Presentation: AI-Powered Code Audit Pipeline

---

## The Story

"We built a deterministic pipeline that scans, analyzes, and fixes code — without relying on LLMs for execution. Tools decide the final result. The LLM is advisory only."

---

## Scene 1: The Problem

**What we started with:**
- A Python project with 13 findings
- Missing dependencies, syntax errors, no lock file, undeclared packages
- Score: **below 93.91%** (information gap detected)

**Evidence:**
```
BEFORE:
  Score: 97.31% → ALL items route to simulation
  OR
  Score: 83.33% → split routing (ready + isolated)
  
  Findings: syntax_error, missing_dependency, configuration_missing
  No lock file. No .python-version. Dependencies not declared.
```

---

## Scene 2: The Architecture

**8-phase strict state algebra pipeline:**

| Phase | Name | What it does |
|-------|------|-------------|
| 0 | Snapshot | Hash every file. Restore point. |
| 1 | Scan | Raw tool output (compileall, imports, deps, pyproject, lock, python version) |
| 2 | Analysis | LLM advisory + Handoff schema + Classification dossier |
| 3 | Pre-simulation | Grader-based scoring. 93.91% gate. Item-level routing. |
| 4 | Simulation | Sandbox isolation. Proposed changes. No target mutation. |
| 5 | Inspection | Convergence. All paths must report. Hash integrity. |
| 6 | Relay | Before/after diff. Apply or Cancel. |
| 7 | Final Output | resolved.html. Root causes. Handoff report. |

**Key rules:**
- Tools decide the result, not LLMs
- Sandbox in OS temp dir — target NEVER mutated
- State algebra: each phase writes ONLY its own field
- Transition table (not phase += 1)
- Isolation is advisory only — no execution authority

---

## Scene 3: The Scan (6 Tools)

```
Tools ran:
  1. python -m compileall    → syntax check
  2. dependency-manifest     → requirements.txt analysis
  3. import-validation       → AST-based import resolution
  4. pyproject-toml-analysis → PEP 621 metadata check
  5. lock-file-policy        → lock file presence/absence
  6. python-version-policy   → version declaration check

Result: 13 findings with what_wrong, why_it_matters, how_to_fix
```

---

## Scene 4: The Graders (Pre-simulation)

```
CODE GRADERS (blockers):
  scan_hash_verified:       passed=True
  scope_defined:            passed=True
  no_fabricated_findings:   passed=True

WEIGHTED GRADERS:
  claim_support_score:              1.0000 (weight=0.25)
  conflict_score:                   1.0000 (weight=0.15)
  scope_narrowing_score:            1.0000 (weight=0.15)
  simulation_executability_score:   0.3333 (weight=0.25)  ← drags score down
  determinism_score:                1.0000 (weight=0.10)
  information_completeness_score:   1.0000 (weight=0.10)

Score: 83.33% → below 93.91% threshold
Status: below_threshold
Ready: 1 | Isolated: 2
```

---

## Scene 5: The Fix (Simulation)

```
Sandbox: C:\Users\...\AppData\Local\Temp\edge_simulation_*
Sandbox isolated: True
Target mutation attempted: False
Target files mutated: False

Proposed changes:
  F-001 | modify | broken_syntax.py     (def process_data( → def process_data():)
  F-002 | modify | pyproject.toml       (add "openai" to dependencies)
  F-003 | create | .python-version      (3.11)
  F-011 | create | requirements.lock    (generated from pyproject.toml)

Resolved: ALL items
Real target unchanged: True
```

---

## Scene 6: The Result

```
AFTER:
  Score: 100% resolution rate
  Resolved: 13/13
  Unresolved: 0
  Status: fully_resolved
  
  ✓ Syntax error fixed
  ✓ Missing dependencies added to pyproject.toml
  ✓ Lock file generated
  ✓ Python version declared
  ✓ Target NEVER touched (sandbox only)
```

---

## Scene 7: The Proof

**Chaos test: 24/24 adversarial tests pass**
- Structure injection blocked
- Phase drift blocked
- Loop injection terminated
- Relay spoof detected
- Target mutation prevented
- Invalid exit statuses rejected

**State algebra guarantees:**
- No phantom phases
- No arithmetic progression
- Closed transition table
- Isolation is orthogonal (not a phase)

---

## Key Differentiators

1. **Tools decide, not LLMs** — LLM is fallback advisory only
2. **Sandbox isolation** — OS temp dir, verified not inside target
3. **Proposed changes first** — diff plan generated before any mutation
4. **93.91% information completeness gate** — not a quality score
5. **Every path produces a report** — nothing silent, nothing skipped
6. **State algebra** — deterministic, composable, closed under execution

---

## Screenshots Reference

| Slide | Content | File |
|-------|---------|------|
| Architecture | Pipeline phase diagram | 08-Architecture/ |
| Scan output | 6 tools, 13 findings | 01-Scan/ |
| Analysis | LLM advisory + Handoff | 02-Analysis/ |
| Pre-simulation | Grader scores, routing | 03-PreSimulation/ |
| Simulation | Sandbox isolation proof | 04-Simulation/ |
| Inspection | Convergence, hash integrity | 05-Inspection/ |
| Relay | Before/after diff | 06-Relay/ |
| Final output | resolved.html, status | 07-FinalOutput/ |
| Cloud deploy | UiPath cloud run succeeded | 09-CloudDeploy/ |
| Evidence | Execution traces, correlation IDs | 11-Evidence/ |

---

## One-liner Summary

> "A deterministic 8-phase pipeline that scans Python projects, routes issues through grader-based scoring, fixes them in an isolated sandbox, and produces complete reports — with tools deciding the outcome, not AI narratives."
