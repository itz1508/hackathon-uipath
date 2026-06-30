<!-- Modified: 2026-06-24T06:57:46Z -->
# Judges Quick Reference — Audisor

> **30-second summary:** A governed 7-phase pipeline that completes work before the user commits. The user sees a before/after diff of a finished fix and chooses Apply (release) or Cancel (restore). Zero risk either way.

---

## Track 2 Compliance (BPMN)

| What to look for | Where to find it |
|-----------------|-----------------|
| BPMN Process definition | `audisor/audisor-agentic-process/audisor-agentic-process.bpmn` |
| Service Task → API Workflow | `handoff/API Workflow-Workflow.json` |
| Exclusive Gateway (Success/Failure) | Inside the BPMN — routes based on real response |
| Coded Agent (PreSimulation Evaluator) | `pipeline/pre_simulation.py` + Agent Builder eval set |
| Human-in-the-Loop | Phase 5 Relay → Operator Dashboard or Action Center |
| E2E Proof | `submission-proof/cloud-e2e-proof.json` (Job `139a9fab`, Successful End) |

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Pipeline phases | 7 (0–6) |
| Total test assertions | 184 |
| Test fixtures | 8 |
| E2E cloud run duration | 2,730 ms |
| Agent eval cases | 6 |
| Info-completeness threshold | 93.91% |
| LLM credits per pipeline run | 0 (deterministic Python) |
| Lines of pipeline code | ~2,000 (pipeline/) |

---

## Architecture in One Diagram

```
UiPath Cloud                    Local/Tunnel
┌─────────────────────┐         ┌──────────────────────────┐
│ BPMN Agentic Process│         │ Edge Backend (FastAPI)    │
│   → Service Task    │────────▶│   → Phase Controller     │
│   → Gateway         │◀────────│   → WorkflowControl 0-6  │
│   → End Events      │         │   → SSE Streaming        │
└─────────────────────┘         └──────────────────────────┘
                                         │
                                         ▼
                                ┌──────────────────────────┐
                                │ Operator Dashboard        │
                                │   → Before/After Diff     │
                                │   → Apply / Cancel        │
                                └──────────────────────────┘
```

---

## How to Verify

```powershell
# Run the full regression suite (from pipeline/)
cd pipeline
.venv\Scripts\python.exe tests\run_fixture_regression.py
# Expected: 8 fixtures pass, 184 assertions

# Verify pipeline integrity
.venv\Scripts\python.exe tests\deployment_guard.py
# Expected: PASS — all 8 source files byte-identical

# Verify entry-points schema preserved
.venv\Scripts\python.exe tests\verify_entry_points.py
# Expected: PASS — all properties match
```

---

## Screenshots Available

See `uipath-img/` for:
- UiPath Cloud process execution screenshots
- Debug/iteration screenshots showing BPMN execution
- Successful job completion evidence

---

## Proof Artifacts

| Artifact | Location |
|----------|----------|
| Cloud E2E proof JSON | `submission-proof/cloud-e2e-proof.json` |
| Kernel proof ledger | `audisor-kernel/proof.ledger.json` |
| Deployment inventory | `audisor-kernel/deployment.inventory.json` |
| Test regression output | Run `tests/run_fixture_regression.py` |
| Source integrity hashes | `pipeline/tests/source_hashes.json` |
