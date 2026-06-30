# NextFlow: AI-Powered Compliance Audit Platform

<!-- Modified: 2026-06-27T13:50:00Z -->

> Automated compliance auditing powered by a 7-phase AI pipeline, orchestrated via UiPath and exposed through a FastAPI backend.

---

## Quick Start

**Prerequisites:**

- Python 3.11+
- pip

---

## Install

The pipeline ships with a pre-built virtual environment (`pipeline/.venv`). To install project dependencies:

```bash
pip install -e ".[dev]"
```

> **Note:** The `pipeline/` directory includes its own `.venv` with all ML/AI dependencies pre-installed. The start scripts (`backend/run.bat`, `backend/run.sh`) automatically set `PYTHONPATH` to include both `pipeline/` and the repo root.

---

## Run Backend

> **⚠️ CRITICAL: How to Run the Backend**
> **DO NOT** run `python backend/main.py` directly. Because this project uses a multi-module architecture (`pipeline/` and `workbench_backend/`), running it directly will cause Python import errors.
>
> **You MUST use the provided run script**, which automatically configures the `PYTHONPATH` and installs dependencies:

**Windows:**

```cmd
cd backend
run.bat
```

*(The script will automatically set up the environment and start the server on port 8790).*

**Unix / macOS:**

```bash
bash backend/run.sh
```

The backend starts on `http://localhost:8790`. Verify it's running:

```bash
curl http://localhost:8790/health
```

Expected response:

```json
{"status": "healthy"}
```

---

## Test the API

Submit a mock audit request using the included sample payload:

```bash
curl -X POST http://localhost:8790/v1/executions \
  -H "Content-Type: application/json" \
  -d @backend/data/mock_requests.json
```

On Windows (PowerShell):

```powershell
$body = Get-Content backend\data\mock_requests.json -Raw
Invoke-RestMethod -Uri http://localhost:8790/v1/executions -Method POST -ContentType "application/json" -Body $body
```

The mock request file (`backend/data/mock_requests.json`) contains a valid payload conforming to the API contract:

```json
{
  "executionType": "audit",
  "tenant": "hackathon-demo",
  "process": {
    "taskRef": "demo-audit-task-001",
    "entryPoint": "isolated-integration"
  },
  "input": {
    "requestId": "demo-request-001",
    "caseId": "CASE-2026-DEMO",
    "payload": {
      "action": "full_audit",
      "caseId": "CASE-2026-DEMO"
    }
  }
}
```

---

## Expected Output

### Submission Response (HTTP 202)

```json
{
  "executionId": "exec-<uuid>",
  "status": "accepted"
}
```

### Status Progression

Poll the execution status via `GET /v1/executions/{executionId}`:

```bash
curl http://localhost:8790/v1/executions/<executionId>
```

The execution progresses through 7 phases:

| Phase | Name | Description |
|-------|------|-------------|
| 0 | snapshot | Initial state capture |
| 1 | scan_analysis | Document scanning and analysis |
| 2 | pre_simulation | Simulation preparation |
| 3 | simulation | Compliance scenario simulation |
| 4 | inspection | Results inspection and validation |
| 5 | relay | Output relay and formatting |
| 6 | final_result | Final compliance report |

Status progression: `accepted` → `running` → `completed`

---

## UiPath Integration

The UiPath integration layer bridges UiPath Orchestrator to the backend API.

### Import the Function Package

1. Navigate to `uipath/api-workflows/isolated-integration/`
2. Import the Function package into UiPath Orchestrator
3. The package triggers `POST /v1/executions` and polls `GET /v1/executions/{id}/progress` for phase updates

### Orchestrator Setup

See [`uipath/ORCHESTRATOR_SETUP.md`](uipath/ORCHESTRATOR_SETUP.md) for full deployment and configuration steps.

### Architecture

```
UiPath Orchestrator
    └── isolated-integration (Function package)
            ├── POST /v1/executions     → Submit audit
            └── GET  /v1/executions/{id}/progress → Poll phases
                        │
                        ▼
              workbench_backend (FastAPI, port 8790)
                        │
                        ▼
                pipeline (7-phase engine)
```

---

## Run Tests

Smoke test to verify backend health and mock execution:

```bash
pytest backend/tests/test_api.py
```

Or using the pipeline venv:

```powershell
$env:PYTHONPATH="$PWD;$PWD\pipeline"; .\pipeline\.venv\Scripts\python.exe -m pytest backend\tests\test_api.py -q
```

---

## Architecture

The system follows a three-layer runtime chain:

| Layer | Location | Role |
|-------|----------|------|
| **Bridge** | `isolated-integration/` | UiPath Function package — stateless HTTP router |
| **Backend** | `workbench_backend/` | FastAPI adapter (port 8790) — execution management |
| **Pipeline** | `pipeline/` | 7-phase AI workflow engine (Phases 0–6) |

For detailed architecture documentation, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Documentation

| Document | Description |
|----------|-------------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Three-layer runtime chain explanation |
| [`docs/API_SPECIFICATION.md`](docs/API_SPECIFICATION.md) | Full API endpoint reference |
| [`docs/DEMO_GUIDE.md`](docs/DEMO_GUIDE.md) | 5-minute judge demo script |
| [`docs/AGENT_PROMPTS.md`](docs/AGENT_PROMPTS.md) | AI agent configurations and prompts |
| [`uipath/README.md`](uipath/README.md) | UiPath integration overview |
| [`uipath/ORCHESTRATOR_SETUP.md`](uipath/ORCHESTRATOR_SETUP.md) | UiPath Orchestrator deployment guide |

---

## Project Structure

```
├── backend/                  # Facade entry point (thin wrapper over workbench_backend)
│   ├── main.py              # FastAPI app re-export + uvicorn runner
│   ├── config.py            # Centralized configuration
│   ├── run.bat / run.sh     # Platform start scripts
│   ├── data/                # Mock request payloads
│   ├── services/            # Service facades
│   └── tests/               # Smoke tests + property tests
├── workbench_backend/        # Core FastAPI backend (runtime)
├── pipeline/                 # 7-phase AI execution engine (runtime)
├── isolated-integration/     # UiPath Function package (runtime)
├── uipath/                   # UiPath presentation surface
│   ├── api-workflows/       # Copy of isolated-integration for review
│   └── maestro/             # Visual BPMN reference (non-runtime)
├── docs/                     # Architecture, API spec, demo guide
├── media/                    # Demo video and diagrams
├── tests/                    # Integration and verification tests
└── _archive/                 # Historical artifacts (not active runtime)
```
