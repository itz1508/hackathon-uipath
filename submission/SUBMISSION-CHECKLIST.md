<!-- Modified: 2025-06-29T15:00:00Z -->
# Hackathon Submission Checklist — Audisor

## Required Deliverables (No Video)

### ✅ Source Code
- [x] Full repository with all subsystems
- [x] README.md with architecture overview
- [x] SUBMISSION.md with complete writeup
- [x] Apache 2.0 LICENSE

### ✅ Documentation
- [x] Architecture diagram (Mermaid in README)
- [x] Phase 0–6 pipeline explanation
- [x] Design decisions table
- [x] Setup & run instructions
- [x] Judges quick reference (`submission-materials/JUDGES-QUICKREF.md`)

### ✅ UiPath Artifacts
- [x] BPMN Process definition (`audisor/audisor-agentic-process/`)
- [x] API Workflow Bridge (`handoff/API Workflow-Workflow.json`)
- [x] Action Center schema (`action-center/action-schema.json`)
- [x] UiPath Coded Function entry (`audisor_api_workflow/`)
- [x] Solution package file (`Audisor.uipx`)
- [x] Agent definition (PreSimulation Evaluator — in `pre_simulation.py`)

### ✅ Proof of Execution
- [x] Cloud E2E proof (`submission-proof/cloud-e2e-proof.json`)
- [x] Proof ledger (`audisor-kernel/proof.ledger.json`)
- [x] Deployment inventory (`audisor-kernel/deployment.inventory.json`)
- [x] Screenshots (`uipath-img/`)

### ✅ Testing & Validation
- [x] 184 assertions across 8 fixtures
- [x] Fixture regression runner (`tests/run_fixture_regression.py`)
- [x] Deployment guard (SHA-256 integrity)
- [x] Entry-points schema verification
- [x] Contract verification (`tests/verify_contract.py`)

### ✅ Deployment Package
- [x] `pyproject.toml` production-ready (audisor-pipeline v1.0.0)
- [x] `deploy.py` orchestration script
- [x] Post-deploy verification script
- [x] Source hash baseline

### ✅ Presentation Materials
- [x] Deck outline (`submission-materials/presentation/deck-outline.md`)
- [x] Demo script (`submission-materials/demo-script.md`)

---

## What to Submit

1. **Repository link** — this repo (public or shared with judges)
2. **SUBMISSION.md** — complete project writeup (root of repo)
3. **JUDGES-QUICKREF.md** — where to find everything
4. **Screenshots** — `uipath-img/` directory

---

## Not Included (Intentionally)

- ❌ Video demo (not required for this submission)
- ❌ Live Orchestrator access (proof artifacts provided instead)
- ❌ API keys / secrets (`.env` gitignored)
