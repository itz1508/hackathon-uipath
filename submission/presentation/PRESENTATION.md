<!-- Modified: 2025-06-29T15:00:00Z -->
# Audisor Pipeline
## UiPath AgentHack Track 2 (BPMN)

**Team:** TheOneShot  
**Track:** Track 2 — Agentic Processes (BPMN)

---

## The Problem

Complex multi-phase operations need governance, safety, and human oversight.

Current approaches:
- **Manual:** Slow, error-prone, no guarantee of completeness
- **Fire-and-forget automation:** No rollback, no visibility, "something went wrong" with no context

**What's missing:** A system where the fix is done BEFORE the user decides, and they can accept or reject with zero risk.

---

## Our Solution: Audisor

> *"The work is done before you decide."*

A deterministic 7-phase pipeline that:
1. Captures a snapshot (restore point always available)
2. Analyzes and scores information completeness
3. Executes all mutations on a **candidate copy** (never the real target)
4. Presents a complete before/after diff at the decision point
5. User chooses: **Apply** (release proven work) or **Cancel** (restore from snapshot)

**Zero risk either way.**

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│              UiPath Automation Cloud              │
│                                                   │
│  BPMN Agentic Process                            │
│    → Service Task (API Workflow Bridge)           │
│    → Exclusive Gateway (Success / Failure)        │
│    → End Events                                   │
└───────────────────────┬─────────────────────────┘
                        │ HTTP (Cloudflare Tunnel)
                        ▼
┌─────────────────────────────────────────────────┐
│            Edge Backend (FastAPI)                 │
│                                                   │
│  Phase Controller (state machine)                │
│    → Phase 0: Snapshot                           │
│    → Phase 1: Scan + Analysis                    │
│    → Phase 2: Pre-simulation (93.91% gate)       │
│    → Phase 3: Simulation (candidate copy only)   │
│    → Phase 4: Inspection (convergence)           │
│    → Phase 5: Relay (human decision)             │
│    → Phase 6: Final Output                       │
└───────────────────────┬─────────────────────────┘
                        │ SSE (real-time updates)
                        ▼
┌─────────────────────────────────────────────────┐
│         Operator Dashboard (PySide6)             │
│                                                   │
│  • Real-time phase status                        │
│  • Before/After diff view                        │
│  • Apply / Cancel decision                       │
│  • Action Center fallback (UiPath native)        │
└─────────────────────────────────────────────────┘
```

---

## The 93.91% Threshold

**What it is:** An information-completeness gate (not a quality gate).

- Exactly 93.91% passes → proceeds to simulation
- 93.90% does not → item branches to targeted research
- Pipeline never stops — good parts continue while isolated items research

**Scoring formula:**
- Completeness × 0.25
- Traceability × 0.20
- Scope & Boundary × 0.15
- Simulation Executability × 0.20
- Safety & Reversibility × 0.15
- Determinism × 0.05

**Agent:** PreSimulation Evaluator (Claude Sonnet 4)  
**Scope:** Read-only. Cannot mutate, approve, or advance phases.

---

## Human-in-the-Loop (Track 2 Requirement)

At Phase 5 (Relay), the pipeline pauses with `awaiting_user_approval`:

**What the operator sees:**
- Complete before/after diff (snapshot vs. candidate copy)
- Resolved issues (green) — fixed and ready
- Unresolved issues (red) — with full explanation

**Two choices:**
- **Apply** → Pre-apply hash verification → Release to real target → Post-apply drift check
- **Cancel** → Restore from snapshot → Original state, no trace

**Fallback:** If Operator Dashboard unavailable → UiPath Action Center handles the decision.

---

## Proven Cloud Execution

**Job ID:** `139a9fab-28e3-48f7-9158-6a94b0944cda`  
**Status:** Successful End  
**Duration:** 2,730 ms  
**Environment:** Debug_hackaton folder, UiPath Automation Cloud

**Full flow verified:**
1. BPMN Start → Service Task → API Workflow Bridge
2. Bridge POSTed to Edge Backend → Phase 0–6 executed
3. Bridge polled → received `succeeded`
4. BPMN Gateway → Success End Event

**Correlation ID matched across all 3 layers** (BPMN, Bridge, Edge)

---

## Testing Rigor

| Category | Assertions |
|----------|-----------|
| Phase 4 (Inspection) | 16 |
| Phase 5 (Relay) | 36 |
| Phase 6 (Final Output) | 59 |
| Contract verification | 71 |
| **Total** | **184** |

- 8 test fixtures × auto + manual modes
- Property-based testing (Hypothesis)
- SHA-256 integrity guard (pipeline files never modified)
- JSON Schema round-trip verification

---

## Key Design Principles

1. **Phase locking** — Controller owns transitions. Agent never selects next phase.
2. **Candidate copy** — All mutation in simulation. Real target untouched until Apply.
3. **Pipeline never stops** — Isolation = research, not failure.
4. **Tool allowlists** — Each executor scoped. Phase-jumping outputs rejected.
5. **Every path produces a report** — No silent outcomes.
6. **Zero LLM credits per pipeline run** — Pure deterministic Python.
7. **Governed by Kernel** — Every transition validated. Every claim requires evidence.

---

## Deployment (Production-Ready)

Package: `audisor-pipeline` v1.0.0  
Target: Orchestrator → `Audisor` folder  
Type: UiPath Coded Function (zero AI credit consumption)

```powershell
cd audisor_api_workflow
python deploy.py
# auth → init → verify → guard → regression → pack → publish
```

---

## Thank You

**Audisor:** The work is done before you decide.

*UiPath AgentHack 2025 — Track 2 (BPMN)*  
*Apache License 2.0 — © 2025 TheOneShot*
