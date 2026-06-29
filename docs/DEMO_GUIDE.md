# Demo Guide — NextFlow Hackathon Submission

<!-- Modified: 2026-06-28T14:00:00Z -->

> **Time to complete: ~5 minutes**

This guide walks a judge through starting the backend, submitting a mock audit request, observing execution progress, and verifying the final output.

---

## Prerequisites

- Python 3.11+
- pip
- Dependencies installed (see Step 1)
- A terminal (PowerShell on Windows, bash on Unix)
- `curl` available on PATH (or any HTTP client)

---

## Step 1: Install Dependencies

From the repository root:

```bash
pip install -r backend/requirements.txt
```

This installs FastAPI, Uvicorn, httpx, and all runtime dependencies.

---

## Step 2: Start the Backend

**Windows:**

```batch
backend\run.bat
```

**Unix / macOS:**

```bash
bash backend/run.sh
```

Both scripts set the correct `PYTHONPATH` and start the FastAPI application on port **8790**.

> The start scripts are located at:
> - Windows: `backend\run.bat`
> - Unix: `backend/run.sh`

---

## Step 3: Verify Health

In a separate terminal, confirm the backend is running:

```bash
curl http://localhost:8790/health
```

**Expected response:**

```json
{
  "status": "healthy"
}
```

---

## Step 4: Submit Mock Request

Submit the pre-built mock request from `backend/data/mock_requests.json`:

**Windows (PowerShell):**

```powershell
$body = Get-Content backend/data/mock_requests.json -Raw | ConvertFrom-Json
# Remove metadata field before submission
$body.PSObject.Properties.Remove('lastModified')
$json = $body | ConvertTo-Json -Depth 10
Invoke-RestMethod -Uri http://localhost:8790/v1/executions -Method POST -Body $json -ContentType "application/json"
```

**Unix / macOS (curl):**

```bash
curl -X POST http://localhost:8790/v1/executions \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

**Expected response (HTTP 202 Accepted):**

```json
{
  "executionId": "<generated-uuid>",
  "status": "accepted"
}
```

> The mock request payload is located at: `backend/data/mock_requests.json`

---

## Step 5: Poll for Progress

Using the `executionId` from Step 4, poll for phase progress:

```bash
curl http://localhost:8790/v1/executions/{executionId}/progress
```

Replace `{executionId}` with the actual ID returned in Step 4.

**Expected response (execution in progress):**

```json
{
  "executionId": "<id>",
  "currentPhase": "scan_analysis",
  "phaseIndex": 1,
  "totalPhases": 7,
  "phases": [
    { "name": "snapshot", "status": "completed" },
    { "name": "scan_analysis", "status": "running" },
    { "name": "pre_simulation", "status": "pending" },
    { "name": "simulation", "status": "pending" },
    { "name": "inspection", "status": "pending" },
    { "name": "relay", "status": "pending" },
    { "name": "final_result", "status": "pending" }
  ]
}
```

Poll every 2–3 seconds until `currentPhase` reaches `final_result`.

---

## Step 6: Verify Final Status

Once the execution completes, retrieve the full result:

```bash
curl http://localhost:8790/v1/executions/{executionId}
```

**Expected response (completed execution):**

```json
{
  "executionId": "<id>",
  "status": "completed",
  "currentPhase": "final_result",
  "result": {
    "summary": "...",
    "findings": [...]
  }
}
```

A `status` of `"completed"` confirms the full 7-phase pipeline executed successfully.

---

## Summary of the Judge Path

| Step | Action | Endpoint | Expected |
|------|--------|----------|----------|
| 1 | Install deps | — | No errors |
| 2 | Start backend | — | Server listening on :8790 |
| 3 | Health check | `GET /health` | `{"status": "healthy"}` |
| 4 | Submit request | `POST /v1/executions` | HTTP 202 + `executionId` |
| 5 | Poll progress | `GET /v1/executions/{id}/progress` | Phase progression |
| 6 | Final status | `GET /v1/executions/{id}` | `"status": "completed"` |

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError: workbench_backend` | PYTHONPATH not set | Use the start scripts (`backend\run.bat` or `backend/run.sh`) which set it automatically |
| Port 8790 already in use | Another process on that port | Stop the other process or set `BACKEND_PORT` environment variable |
| `Connection refused` on curl | Backend not started | Run the start script and wait for "Uvicorn running" message |
| HTTP 400 on POST | Invalid request payload | Ensure you are using the exact content from `backend/data/mock_requests.json` (without the `lastModified` field) |
| Import errors on startup | Missing dependencies | Run `pip install -r backend/requirements.txt` |

---

## File Reference

| Artifact | Path |
|----------|------|
| Start script (Windows) | `backend\run.bat` |
| Start script (Unix) | `backend/run.sh` |
| Mock request payload | `backend/data/mock_requests.json` |
| Requirements | `backend/requirements.txt` |
| Smoke tests | `backend/tests/test_api.py` |
