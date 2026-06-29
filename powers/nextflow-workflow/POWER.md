---
name: "NextFlow-workflow"
displayName: "NextFlow Governed Change Pipeline"
description: "8-stage governed pipeline for AI-assisted configuration remediation with deterministic admission, isolated simulation, cryptographic proof, human approval, and post-apply verification."
keywords: ["NextFlow", "governed-change", "uipath-maestro", "configuration-remediation", "proof-pipeline"]
author: "Hackathon Team"
---

# NextFlow Governed Change Pipeline

## Overview

NextFlow enforces the principle that AI can analyze and recommend, but must never directly mutate production. It implements an 8-stage deterministic workflow where:

- Advisory AI output is structured but carries zero authority
- Deterministic gates control admission into simulation
- Simulation executes the change in isolation with cryptographic hashing
- Replay proof guarantees identity and equivalence
- A human decision (via Action Center) is the sole mutation authority
- Apply relay reproduces only the exact approved result
- Post-apply verification detects drift without silent repair

This power documents the complete workflow pattern, contracts, and integration points.

## Onboarding

### Prerequisites

- Node.js 18+ and npm
- Python 3.11+ with `pytest` and `jsonschema`
- `@uipath/cli` and `@uipath/maestro-tool`
- UiPath Automation Cloud access (for cloud deployment)

### Quick Start — Run the Demo Locally

```powershell
# Validate all contracts and schemas
.\scripts\validate.ps1

# Run the deterministic demo (apply decision)
.\scripts\debug-demo.ps1 -Decision apply

# Pack for deployment
.\scripts\pack.ps1 -Version 1.0.0

# Verify the package
.\scripts\verify-package.ps1
```

### Python Demo Runner

```powershell
python scripts/NextFlow_demo.py --decision apply --scenario happy_path
```

Scenarios: `happy_path`, `readiness_rejected`, `simulation_failure`

## Architecture — 8 Stage Pipeline

| Stage | Owner | Authority | Purpose |
|-------|-------|-----------|---------|
| 01 Scan/Snapshot | API Workflow + Storage | Read-only | Capture immutable snapshot with SHA-256 hash |
| 02 Analysis/Recalibration | Agent Builder/Coded Agent | None (advisory) | Classify issue, recommend correction |
| 02.5 Handoff/Pre-Simulation | Maestro Script Tasks | Admission only | Build locked handoff, 6-part readiness gate |
| 03 Simulation | RPA Workflow | Sandbox only | Execute isolated mutation, inspect, validate, hash |
| 04 Replay/Proof | API Workflow | Evidence only | Verify identity and equivalence |
| 05 User Decision | Action Center | Human authority | Apply / Cancel / Preserve for later |
| 06 Apply Relay | RPA Workflow | Exact approved mutation | Reproduce only the proven result |
| 07 Verification | API Workflow | Read-only | Detect match, drift, or failure |
| 08 Final Lock | Maestro Script Task | Terminal record | Lock provenance and audit trail |

## Common Workflows

### Workflow 1: Happy Path — Apply a Configuration Fix

1. **Scan** — Capture the current config state and hash it
2. **Analyze** — AI classifies the issue (e.g., `retry_limit=-1` violates policy)
3. **Admission Gate** — 6 checks must pass at confidence ≥ 93.91:
   - `simulation_ready == true`
   - `required_grader_failures == []`
   - `isolation_required == false`
   - `reattempt_required == false`
   - `confidence_score >= 93.91`
   - `required_dependencies_available == true`
4. **Simulate** — Apply fix in sandbox, validate result matches expected
5. **Prove** — Replay verifies snapshot identity + simulation result hash
6. **Approve** — Human reviews proof packet and selects "Apply"
7. **Apply** — Relay checks 5 preconditions, then copies exact sandbox result to live target
8. **Verify** — Confirms live state matches approved hash; reports drift if not

### Workflow 2: Readiness Rejected

Same as above but at step 3, one or more admission checks fail (e.g., confidence below threshold). The workflow halts with `workflow_status: "blocked"` and records the failure reasons.

### Workflow 3: User Cancels or Preserves

Proof passes, but the human selects "Cancel" or "Preserve for Later" at step 6. No apply occurs. The final result records the decision with full provenance.

## Contract Schemas

All inter-stage data is governed by JSON Schema (2020-12):

| Schema | Purpose |
|--------|---------|
| `workflow-state.schema.json` | The sole authoritative case object |
| `handoff.schema.json` | Locked handoff from analysis to pre-simulation |
| `pre-simulation-package.schema.json` | Admission-checked simulation package |
| `simulation-result.schema.json` | Isolated execution result with hash |
| `replay-proof.schema.json` | Identity and equivalence evidence |
| `user-decision.schema.json` | Human authority boundary |
| `apply-relay.schema.json` | Precondition-checked apply result |
| `post-apply-verification.schema.json` | Live verification status |
| `final-result.schema.json` | Locked terminal record |
| `isolation-addon.schema.json` | Isolation requirements (when needed) |

## Stop Conditions

Processing halts when:
- Input is invalid
- Required information is absent
- Scope is unlocked
- A required dependency is unavailable
- Admission fails
- Explicit user authority is required
- An artifact cannot be validated

Stopping preserves current state and identifies the next action.

## Best Practices

- Never allow advisory AI output to become mutation authority
- Hash every artifact at every stage boundary
- Validate contracts at the receiving stage, not the sending stage
- Keep simulation isolated — sandbox files only, never touch source
- Apply relay must verify 5 preconditions before reproducing result
- Report drift and failure transparently; never silently repair
- Use `workflow_state` as the single source of truth

## Troubleshooting

### Admission Gate Rejects the Package

**Cause:** One or more of the 6 readiness checks failed
**Solution:**
1. Check `pre_simulation_package.admission_failures` array
2. Common issues: confidence below 93.91, unresolved dependencies
3. Fix the upstream stage that produces the failing value

### Simulation Validation Fails

**Cause:** Sandbox result doesn't match expected configuration
**Solution:**
1. Verify `recalibration_findings.correction` is correct
2. Ensure sandbox starts from a clean copy of the snapshot
3. Check that only scoped fields are modified

### Source File Was Mutated

**Cause:** The demo runner detected the original source was changed
**Solution:**
1. Restore `cases/sample-config-repair/source/application-config.json`
2. The runner writes only to temp directories, never to source

---

**Project:** NextFlow — Governed Configuration Remediation
**Track:** UiPath AgentHack Track 2 (Maestro BPMN)
