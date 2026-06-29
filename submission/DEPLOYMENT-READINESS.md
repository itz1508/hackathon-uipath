# UiPath AgentHack Deployment Readiness

<!-- Modified: 2026-06-27T19:30:00Z -->

> **⚠️ HISTORICAL SNAPSHOT** — This document was written against the old
> `maestro-backend` + `audisor-agentic-process` + `maestro-backend-bridge` architecture.
> The current validated runtime chain is: `isolated-integration → workbench_backend → pipeline`.
> References to `maestro-backend`, `maestro-backend-bridge`, and `audisor-agentic-process`
> below describe the **proven Debug_hackaton deployment** (Job 139a9fab) which remains
> read-only. For current authority, see `AGENTS.md`.

## 1. Current State Verification ✓

### What Is Réально Runnable

| Component | Status | How to Run |
|-----------|--------|-----------|
| **workbench_backend** (FastAPI, port 8790) | ✓ RUNNABLE | `python -m workbench_backend` from workspace root |
| **Pipeline (7-phase, Phase 0–6)** | ✓ RUNNABLE | Triggered via POST /execute or POST /v1/executions |
| **maestro-backend-bridge** (API Workflow) | ✓ PACKAGED | .nupkg built, deployed to tenant feed |
| **audisor-agentic-process** (BPMN) | ✓ DEPLOYED | Running in Debug_hackaton folder |
| **UiPath CLI** | ✓ AVAILABLE | `uipath` v2.11.5 in pipeline/.venv |
| **Auth** | ✓ ACTIVE | OAuth token valid, scopes include OrchestratorApiUserAccess |

### Proven End-to-End Execution

**Job 139a9fab** (Audisor Debug environment):
- BPMN reached "Successful End"
- API Workflow executed and returned normalized response
- Edge Workflow completed Phase 6
- Correlation ID matched across all 3 layers

### API Endpoints on workbench_backend (port 8790)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/execute` | POST | Submit execution (returns 202 + executionId) |
| `/v1/executions` | POST | Bridge-compatible submit (same flow) |
| `/v1/executions/{id}` | GET | Poll status (BridgeOutput format) |
| `/status/{id}` | GET | Detailed status with phase/progress |
| `/logs/{id}` | GET | Structured execution log with timeline |
| `/executions/{id}` | DELETE | Cancel execution |
| `/health` | GET | Health check |
| `/version` | GET | Version info |
| `/metrics` | GET | Execution statistics |

---

## 2. Gap Analysis

### What Is NOT Missing (Already Exists)

| Requirement | Status | Evidence |
|-------------|--------|----------|
| .nupkg package structure (pipeline) | ✓ BUILT | `pipeline/.uipath/pipeline.edge.1.0.0.nupkg` (158 KB) |
| .nupkg package structure (bridge) | ✓ BUILT | `audisor/maestro-backend-bridge/.uipath/bridge.maestro.2.5.0.nupkg` |
| Entry point for UiPath workflow | ✓ DEFINED | `pipeline/entry-points.json` → `main.py:main(WorkflowInput)` |
| Orchestrator process definition mapping | ✓ DEPLOYED | `audisor-agentic-process/operate.json` + BPMN |
| Ability to trigger /execute from UiPath robot | ✓ PROVEN | Job 139a9fab executed via Service Task → API Workflow → backend |
| Input/Output contract | ✓ DEFINED | `entry-points.json` has full JSON Schema for WorkflowInput/WorkflowOutput |
| Solution structure (.uipx) | ✓ DEFINED | `audisor/Audisor.uipx` links both projects |

### Actual Gaps (Minor)

| Gap | Severity | Resolution |
|-----|----------|------------|
| `pipeline/bindings.json` was missing | ✓ FIXED | `uipath init` regenerated it (just done) |
| No tunnel URL configured for demo | LOW | Need cloudflared or fixed URL for judge demo |
| Shared folder service task NOT bound | KNOWN | Debug_hackaton works; Shared is optional |

---

## 3. Execution Flow Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                    UiPath Automation Cloud                               │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Studio Web / Orchestrator                                        │   │
│  │                                                                    │   │
│  │  ┌──────────────────────┐     ┌────────────────────────────────┐ │   │
│  │  │ BPMN Process         │     │ API Workflow                    │ │   │
│  │  │ (audisor-agentic-    │     │ (bridge.maestro)               │ │   │
│  │  │  process)            │     │                                 │ │   │
│  │  │                      │     │  1. Validate inputs             │ │   │
│  │  │  Start               │     │  2. POST /v1/executions         │ │   │
│  │  │    │                 │────▶│  3. Poll /v1/executions/{id}    │ │   │
│  │  │    ▼                 │     │  4. Return BridgeOutput         │ │   │
│  │  │  Service Task        │     │                                 │ │   │
│  │  │  (ExecuteApiWorkflow)│◀────│  {execution_id, status,         │ │   │
│  │  │    │                 │     │   backend_result, success}      │ │   │
│  │  │    ▼                 │     └────────────────────────────────┘ │   │
│  │  │  Gateway             │                                         │   │
│  │  │   ├─ success ──▶ ✓  │                                         │   │
│  │  │   └─ failure ──▶ ✗  │                                         │   │
│  │  └──────────────────────┘                                         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└────────────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS (cloudflared tunnel)
                              ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     Local Machine (Developer Laptop)                     │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  workbench_backend (FastAPI, port 8790)                          │   │
│  │                                                                    │   │
│  │  POST /v1/executions                                              │   │
│  │    │                                                               │   │
│  │    ▼ Validate → Create Record → Start Async Task                  │   │
│  │                                                                    │   │
│  │  ┌────────────────────────────────────────────────────────────┐  │   │
│  │  │  pipeline_runner.py (async thread)                          │  │   │
│  │  │                                                              │  │   │
│  │  │  imports pipeline.main.main(WorkflowInput)                   │  │   │
│  │  │    │                                                         │  │   │
│  │  │    ▼                                                         │  │   │
│  │  │  orchestrator.run_pipeline()                                 │  │   │
│  │  │    │                                                         │  │   │
│  │  │    ├── Phase 0: Snapshot (SHA-256 folder hash)               │  │   │
│  │  │    ├── Phase 1: Scan + Analysis (AST parsing)                │  │   │
│  │  │    ├── Phase 2: Pre-simulation (scoring, partition)          │  │   │
│  │  │    ├── Phase 3: Simulation (candidate fixes)                 │  │   │
│  │  │    ├── Phase 4: Inspection (convergence, hashes)             │  │   │
│  │  │    ├── Phase 5: Relay (decision: auto or manual)             │  │   │
│  │  │    └── Phase 6: Final Output (report)                        │  │   │
│  │  │                                                              │  │   │
│  │  │  Returns WorkflowOutput → State → Succeeded/Failed           │  │   │
│  │  └────────────────────────────────────────────────────────────┘  │   │
│  │                                                                    │   │
│  │  GET /v1/executions/{id} → {execution_status, success, result}    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Deployment Checklist

### Pre-flight (Already Done ✓)

- [x] Pipeline packages successfully: `pipeline.edge.1.0.0.nupkg` (158 KB)
- [x] Bridge packages successfully: `bridge.maestro.2.5.0.nupkg`
- [x] `uipath init` executed — `bindings.json`, `entry-points.json` current
- [x] UiPath auth active (OAuth token, OrchestratorApiUserAccess scope)
- [x] Pipeline importable and executable locally
- [x] workbench_backend starts on port 8790
- [x] POST /v1/executions → 202 with executionId
- [x] GET /v1/executions/{id} returns BridgeOutput format
- [x] BPMN process deployed in Debug_hackaton folder
- [x] Service task bound to API Workflow (bridge.maestro)
- [x] E2E proven: Job 139a9fab reached "Successful End"

### To Execute the Demo (Steps for Judge Day)

```powershell
# ─── Step 1: Start the backend ───
cd d:\Dev\hackaton-uipath-jun29-workbench
& pipeline\.venv\Scripts\python.exe -m workbench_backend

# ─── Step 2: Start cloudflared tunnel (exposes 8790 to internet) ───
cloudflared tunnel --url http://localhost:8790
# Note the generated URL (e.g., https://xxx.trycloudflare.com)

# ─── Step 3: Trigger from UiPath Cloud (Option A: via Orchestrator) ───
# In UiPath Automation Cloud → Orchestrator → Debug_hackaton folder:
# 1. Find process "Audisor.Agentic.Process"
# 2. Start Job with input variables:
#    backend_base_url = <tunnel URL from Step 2>
#    case_id = "DEMO-JUDGE-001"
#    payload = {"action": "run_pipeline", "caseId": "DEMO-JUDGE-001"}

# ─── Step 3 (Option B: Trigger via CLI) ───
& pipeline\.venv\Scripts\uipath.exe invoke `
  --process "Audisor.Agentic.Process" `
  --folder "Debug_hackaton" `
  --input '{"backend_base_url":"<tunnel-url>","case_id":"DEMO-JUDGE-001","payload":{"action":"run_pipeline","caseId":"DEMO-JUDGE-001"}}'

# ─── Step 3 (Option C: Direct local trigger — no UiPath needed) ───
Invoke-RestMethod -Method POST -Uri "http://localhost:8790/execute" `
  -ContentType "application/json" `
  -Body '{"caseId":"DEMO-JUDGE-001","targetPath":"d:\\Dev\\hackaton-uipath-jun29-workbench\\demo-workspace","mode":"auto","action":"run_pipeline"}'
```

### Package Publishing (If Packages Need Re-deploy)

```powershell
# Re-pack pipeline
cd d:\Dev\hackaton-uipath-jun29-workbench\pipeline
& .venv\Scripts\uipath.exe pack --nolock
# Output: .uipath/pipeline.edge.1.0.0.nupkg

# Re-pack bridge
cd d:\Dev\hackaton-uipath-jun29-workbench\audisor\maestro-backend-bridge
& .venv\Scripts\uipath.exe pack --nolock
# Output: .uipath/bridge.maestro.2.5.0.nupkg

# Publish to UiPath feed
cd d:\Dev\hackaton-uipath-jun29-workbench\pipeline
& .venv\Scripts\uipath.exe publish --folder "Debug_hackaton"

cd d:\Dev\hackaton-uipath-jun29-workbench\audisor\maestro-backend-bridge
& .venv\Scripts\uipath.exe publish --folder "Debug_hackaton"
```

### Orchestrator Upload Checklist

- [ ] Ensure cloudflared tunnel is running and stable
- [ ] Update `backend_base_url` input variable with current tunnel URL
- [ ] Verify backend health: `curl <tunnel-url>/health` returns `{"status":"healthy"}`
- [ ] In Orchestrator, verify process "Audisor.Agentic.Process" version matches deployed
- [ ] Start job from Orchestrator UI or CLI
- [ ] Monitor job status: should complete in ~15–30 seconds (auto mode)
- [ ] Verify terminal state: "Successful End" in Execution Trail
- [ ] Check backend logs: `GET /logs/{execution_id}` shows all 7 phases completed

---

## 5. Architecture Summary

| Layer | Component | Package | Version | Status |
|-------|-----------|---------|---------|--------|
| **Orchestration** | BPMN Process | audisor-agentic-process | 1.0.0 | DEPLOYED |
| **Integration** | API Workflow (bridge) | bridge.maestro | 2.5.0 | DEPLOYED |
| **Execution** | Edge Pipeline | pipeline.edge | 1.0.0 | PACKAGED |
| **Backend** | workbench_backend | (not packaged, runs locally) | 0.1.0 | RUNNABLE |
| **Tunnel** | cloudflared | (system binary) | — | AVAILABLE |

### UiPath Solution Structure (`audisor/Audisor.uipx`)

```
Audisor (Solution)
├── audisor-agentic-process/  (ProcessOrchestration)
│   ├── project.uiproj
│   ├── operate.json
│   ├── entry-points.json
│   └── audisor-agentic-process.bpmn
│
└── maestro-backend-bridge/   (API Workflow / Function)
    ├── project.uiproj
    ├── pyproject.toml
    ├── entry-points.json
    ├── bindings.json
    ├── main.py
    └── .uipath/bridge.maestro.2.5.0.nupkg
```

---

## 6. What You Do NOT Need

- ❌ No additional orchestration framework
- ❌ No new abstract layers
- ❌ No backend modifications (all endpoints exist)
- ❌ No new .nupkg packaging scripts (deploy.py + uipath pack already work)
- ❌ No new entry points (main.py:main already conforms to UiPath SDK contract)
- ❌ No service task rebinding (already bound in Debug_hackaton)

**The system is deployment-ready.** The only runtime dependency is:
1. workbench_backend running on port 8790
2. cloudflared tunnel exposing it to UiPath Cloud
