<!-- Modified: 2025-06-29T15:00:00Z -->
# Audisor — UiPath AgentHack Track 2 (BPMN) Submission

> **Team:** TheOneShot  
> **Track:** Track 2 — Agentic Processes (BPMN)  
> **License:** Apache 2.0  
> **Tagline:** *"The work is done before you decide."*

---

## 1. What It Does

Audisor is a governed 7-phase execution pipeline that **completes the work before the user commits to it**. The fix is ready before the user decides — they see exactly what was resolved and what was not, instantly.

It integrates UiPath BPMN orchestration with a deterministic Edge pipeline, an Operator Dashboard for human-in-the-loop decisions, and a UiPath Coded Agent for information-completeness scoring.

**Key innovation:** The user never encounters "something went wrong" without context. At the decision point (Phase 5 — Relay), they see a before/after diff of completed work and choose: **Apply** (release the result) or **Cancel** (restore from snapshot). Zero risk either way.

---

## 2. How It Works

### Architecture (4 Subsystems)

```
BPMN Agentic Process (Maestro)
    → API Workflow Bridge (submit-and-poll)
        → Edge Backend (FastAPI, Phase Controller)
            → WorkflowControl Pipeline (Phases 0–6)
                → Operator Dashboard (Apply/Cancel)
```

| Subsystem | Technology | Role |
|-----------|-----------|------|
| **UiPath Cloud** | BPMN Process + API Workflow + Action Center | Orchestration, service task invocation, human escalation |
| **Edge Backend** | FastAPI + Uvicorn (port 8790) | Phase controller, execution state machine, SSE streaming |
| **WorkflowControl** | Python 3.11 + UiPath Coded Function | 7-phase deterministic pipeline, candidate-copy mutation |
| **Resolution Planner** | Claude Code CLI (UiPath Coded Function) | AI resolution designer in Phase 2 — produces contracts, not mutations |
| **Operator Dashboard** | PySide6 (Qt Widgets) | Real-time status, before/after diff, Apply/Cancel decision |

### Pipeline Phases

| Phase | Name | What Happens |
|-------|------|-------------|
| 0 | **Snapshot** | Hash all files (SHA-256). Restore point always available. |
| 1 | **Scan + Analysis** | Classify findings → dossier + 3 statements |
| 2 | **Pre-simulation** | Score against 93.91% information-completeness threshold |
| 3 | **Simulation** | Execute mutations on **candidate copy only** — never real target |
| 4 | **Inspection** | Convergence — wait for ALL branches, validate, hash |
| 5 | **Relay** | Present before/after diff. Human decides: Apply or Cancel |
| 6 | **Final Output** | resolved.html, root causes, complete documentation |

### UiPath Agent: PreSimulation Evaluator

- **Model:** Claude Sonnet 4 (claude-sonnet-4-20250514)
- **Threshold:** 93.91% information completeness (exactly 93.91% passes; 93.90% does not)
- **Scoring formula:** completeness×0.25 + traceability×0.20 + scope_and_boundary×0.15 + simulation_executability×0.20 + safety_and_reversibility×0.15 + determinism×0.05
- **Tool allowlist:** Read-only (lookup_artifact, validate_schema)
- **Denied operations:** simulation, mutation, approval, phase_advance
- **Evaluation set:** 6 test cases, all passing

### UiPath Coding Agent: Resolution Planner (Bonus)

- **Architecture:** Contract-driven execution — the coding agent is a **resolution designer**, not a fixer
- **Placement:** PreSimulation (Phase 2) — produces ResolutionContracts, never touches files
- **Backend:** Claude Code CLI → Anthropic API → Deterministic heuristics (cascading fallback)
- **Output:** ResolutionContract specifying recommended tools, execution order, parameters, expected outcome, confidence
- **Execution:** Toolkit executes contracts deterministically in Simulation (Phase 3)
- **Key principle:** No single entity can both propose AND validate AND execute
- **Flow:** `Issue → ResolutionPlanner → ResolutionContract → Tool Binding → Simulation → Inspection → Promotion`
- **Agent competition:** All contracts (deterministic, AI, manual) enter the same pipeline — the winner is the one that survives simulation and inspection
- **Architecture blend:** Combines UiPath-native agent (PreSimulation Evaluator via Agent Builder) with external coding agent (Claude Code) — both orchestrated by BPMN through UiPath
- **Test coverage:** 20 tests covering data models, planning, tool selection, confidence scoring, and integration

### Agent Performance Ledger (Bonus)

- **Purpose:** Standardized evaluation and comparison of coding agents
- **Architecture:** Every agent run = comparable experiment (same input, same scoring, fully logged)
- **Data model:** `AgentRunRecord` captures full trace: agent_id, model, contract, tools, simulation/inspection results, score
- **Scoring:** `final_score = correctness + coverage + tool_bonus - regression_penalty - conflict_penalty`
- **Storage:** Immutable JSON records in `~/.audisor/agent_ledger/`
- **Aggregation:** `AgentLedgerEntry` per agent: avg score, success rate, regression rate, failure patterns
- **Fair protocol:** Same input set, same toolkit, same simulation/inspection, no hidden retries
- **Failure classification:** tool_misuse, regression, conflict, simulation_failure, inspection_failure
- **Test coverage:** 23 tests covering scoring, classification, storage, aggregation, and reporting

---

## 3. How We Built It

### Development Stack

- **Language:** Python 3.11+
- **UiPath SDK:** uipath==2.11.5
- **Web Framework:** FastAPI + Uvicorn
- **Desktop UI:** PySide6 6.7+
- **Testing:** pytest + Hypothesis (property-based testing)
- **Tunnel:** Cloudflare quick tunnels (cloudflared)
- **CLI:** UiPath CLI v1.195.0

### Development Methodology

Built using a **Kernel-governed runtime model** where every action follows:
```
NODE → EDGE → STATE TRANSITION → VALIDATION → COMMIT
```

The Kernel (`audisor-kernel/`) serves as the truth authority — it validates every transition, rejects invalid graph edges, and enforces evidence requirements before any claim enters the proof ledger.

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Phase Locking** | Controller owns all routing. No agent can skip phases. |
| **Candidate Copy** | All mutation in simulation. Real target never at risk. |
| **93.91% Threshold** | Information completeness gate. Below = info gap, not failure. |
| **Pipeline Never Stops** | Isolated items research in parallel. Good parts continue. |
| **Tool Allowlists** | Each executor scoped to permitted ops. Phase-jumping rejected. |
| **Apply = Release** | Work already done. Apply delivers it. Cancel restores. |
| **Action Center Fallback** | UiPath-native human escalation when dashboard unavailable. |

---

## 4. Proven End-to-End Execution

**Proven run:** Job `139a9fab-28e3-48f7-9158-6a94b0944cda`  
**Environment:** Audisor Debug (folder: `Debug_hackaton`)  
**Status:** Successful End  
**Duration:** 2,730ms  

### Execution Flow (Verified)

1. Maestro BPMN instance started (Agentic Process)
2. BPMN service task invoked API Workflow bridge
3. API Workflow POSTed to tunnel → backend → `/v1/executions`
4. Backend resolved taskRef → workflow-control/ dir
5. UiPath CLI executed: `uipath run main <json> --output-file <path>`
6. WorkflowControl ran Phase 0–6 pipeline
7. Output written → backend completed execution
8. API Workflow polled status → received 'succeeded'
9. Normalized response returned to BPMN
10. BPMN gateway evaluated success=true → Successful End

### Correlation ID Verification

The same correlation ID traced across all 3 layers:
- ✅ BPMN Layer (job arguments)
- ✅ API Workflow (X-Correlation-Id header)
- ✅ Edge Backend (execution record)

---

## 5. Test Coverage

| Category | Assertions |
|----------|-----------|
| Phase 4 (Inspection) | 16 |
| Phase 5 (Relay) | 36 |
| Phase 6 (Final Output) | 59 |
| Contract verification | 71 |
| **Total** | **184** |

**Fixture regression:** 8 fixtures × 2 modes (auto + manual) = all passing  
**Deployment guard:** SHA-256 integrity verification for all pipeline source files  
**Entry-points verification:** JSON Schema comparison pre/post rename  

---

## 6. Deployment Package

The `audisor-pipeline` v1.0.0 package is ready for production deployment:

| Artifact | Status |
|----------|--------|
| `pyproject.toml` renamed | ✅ `audisor-pipeline` v1.0.0 |
| Source hashes computed | ✅ 8 files baselined |
| Regression suite | ✅ 184 assertions passing |
| Deploy script (`deploy.py`) | ✅ Full CLI lifecycle orchestration |
| Deployment guard | ✅ Pipeline integrity preserved |
| Entry-points verification | ✅ Schema identical pre/post |
| Post-deploy verification | ✅ Script ready for Orchestrator check |

### Deploy Command

```powershell
cd workflow-control
python deploy.py
```

Executes: auth → init → verify schemas → guard → regression → pack → verify artifact → publish

---

## 7. Repository Structure

```
hackaton-uipath-jun29-workbench/
├── maestro-backend/              # Edge Backend (FastAPI)
│   └── src/                      # Phase controller, agents, SSE
├── maestro-backend-bridge/       # API Workflow Bridge
├── workflow-control/             # UiPath Coded Function (7-phase pipeline)
│   ├── main.py                   # Entry point: Phases 0–6
│   ├── deploy.py                 # Deployment orchestration
│   └── tests/                    # 184 assertions + integrity tools
├── operator_dashboard/           # PySide6 Operator Dashboard
├── audisor/                      # UiPath BPMN Agentic Process
├── audisor-kernel/               # Runtime truth authority (kernel)
├── action-center/                # Action Center schema (HITL fallback)
├── handoff/                      # UiPath solution artifacts
├── submission-proof/             # Cloud E2E proof artifacts
├── submission-materials/         # Presentation deck + demo script
├── uipath-img/                   # Screenshots
└── SUBMISSION.md                 # This file
```

---

## 8. How to Run

### Prerequisites

- Python 3.11+
- UiPath CLI (`uipath` or `uip`)
- PySide6 6.7+
- Active UiPath Automation Cloud account

### Quick Start

```bash
# Clone
git clone <repository-url>
cd hackaton-uipath-jun29-workbench

# Install dependencies
pip install -e ".[dev]"

# Run Edge Backend
uvicorn maestro-backend.src.main:app --port 8790

# Run Operator Dashboard (separate terminal)
python -m operator_dashboard.main

# Run pipeline regression (from workflow-control/)
cd workflow-control
.venv/Scripts/python.exe tests/run_fixture_regression.py

# Deploy to UiPath Orchestrator
python deploy.py
```

---

## 9. Track 2 Requirements Checklist

| Requirement | Evidence |
|-------------|----------|
| BPMN Process orchestration | ✅ `audisor/audisor-agentic-process/audisor-agentic-process.bpmn` |
| Service Task invocation | ✅ API Workflow Bridge bound in solution |
| Exclusive Gateway routing | ✅ Success/Failure end events based on response |
| Agent evaluation | ✅ PreSimulation Evaluator (93.91% threshold, 6 eval cases) |
| Human-in-the-Loop | ✅ Relay decision (Apply/Cancel) via Dashboard + Action Center |
| End-to-end cloud execution | ✅ Job `139a9fab`, Successful End, 2.73s |
| Correlation ID tracing | ✅ Matched across BPMN, Bridge, Edge |

---

## 10. What Makes This Different

1. **The work is done before you decide.** At the decision point, you're looking at a completed fix — not a problem.
2. **Zero-risk decision.** Apply releases proven work. Cancel restores from snapshot. Either way, safe.
3. **Pipeline never stops.** Items needing more info branch off; good parts continue forward.
4. **184 assertions verify correctness.** Not "it works on my machine" — property-based testing with Hypothesis.
5. **Deterministic pipeline, zero LLM credits per run.** The pipeline itself is pure Python logic. The agent evaluates but doesn't execute.
6. **Governed by Kernel.** Every transition validated, every claim requires evidence.

---

*Built for UiPath AgentHack 2025 — Track 2 (BPMN)*  
*Apache License 2.0 — © 2025 TheOneShot*
