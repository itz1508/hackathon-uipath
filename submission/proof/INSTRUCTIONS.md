# Cloud Run Instructions

Step-by-step procedure for performing the end-to-end cloud run and capturing proof artifacts.

## Prerequisites

- UiPath Automation Cloud account with access to Orchestrator
- Edge Backend deployed to a stable HTTPS endpoint (ngrok, Cloudflare Tunnel, or cloud VM)
- API Workflow Bridge published to UiPath Automation Cloud
- BPMN Agentic Process published to UiPath Automation Cloud
- A test folder with files to process through the pipeline

---

## Step 1: Deploy Edge Backend to a Stable HTTPS Endpoint

1. Start the Edge Backend locally:
   ```bash
   cd maestro-backend
   uvicorn src.main:app --host 0.0.0.0 --port 8000
   ```

2. Expose via HTTPS tunnel (choose one):
   - **ngrok**: `ngrok http 8000`
   - **Cloudflare Tunnel**: `cloudflared tunnel --url http://localhost:8000`
   - **Cloud VM**: Deploy directly with TLS termination

3. Verify the endpoint is reachable:
   ```bash
   curl https://<your-endpoint>/health
   ```
   Expected response: `{"status": "healthy"}`

4. Record the HTTPS URL: `___________________________`

---

## Step 2: Configure API Workflow Bridge with EDGE_BACKEND_URL

1. In UiPath Automation Cloud, navigate to the API Workflow Bridge process
2. Set the `backend_base_url` argument to your HTTPS endpoint from Step 1
3. Ensure the workflow has the correct environment variables or asset references
4. Verify the bridge can reach the backend by checking connection logs

---

## Step 3: Trigger BPMN Process from UiPath Automation Cloud

1. Navigate to Orchestrator → Processes → Agentic Process
2. Start a new job with the following arguments:
   - `backend_base_url`: Your HTTPS endpoint from Step 1
   - `request_id`: A unique request identifier (e.g., UUID)
   - `case_id`: A test case identifier
   - `task_ref`: Reference to the processing task
   - `idempotency_key`: A unique key for this run (e.g., UUID)
   - `correlation_id`: A unique correlation ID — **record this value**
   - `payload`: JSON payload with the test folder path or content

3. Record the BPMN Process Instance ID from Orchestrator: `___________________________`

---

## Step 4: Wait for Pipeline to Reach Relay → Make Decision

1. Monitor the Edge Backend logs or Operator Dashboard for phase progression:
   - Phase 0 (Snapshot) → Phase 1 (Scan + Analysis) → Phase 2 (Pre-simulation)
   - Phase 3 (Simulation) → Phase 4 (Inspection) → Phase 5 (Relay)

2. When Phase 5 (Relay) is reached, the pipeline pauses with status `awaiting_user_approval`

3. Review the resolved/unresolved items displayed in the dashboard or API response

4. Make the decision via one of:
   - **Operator Dashboard**: Click "Apply" or "Cancel"
   - **API**: `POST /v1/executions/{id}/decision` with `{"decision": "apply"}` or `{"decision": "cancel"}`
   - **Action Center**: Submit Apply/Cancel through UiPath Action Center

5. Wait for Phase 6 (Final Output) to complete

---

## Step 5: Capture All IDs and Output from the Cloud Console

Collect the following from UiPath Automation Cloud and Edge Backend:

| Item | Where to Find | Value |
|------|--------------|-------|
| BPMN Process Instance ID | Orchestrator → Jobs → Job Details | |
| API Workflow Run ID | Orchestrator → Jobs → API Workflow job | |
| Edge execution_id | Edge Backend logs or GET /v1/executions | |
| Correlation ID | All three layers (verify match) | |
| Terminal Status | Edge Backend GET response | |
| Service Task Output | BPMN job output arguments | |

### Verify Correlation ID Match

Confirm the same correlation_id appears in:
1. BPMN job arguments (input)
2. API Workflow Bridge HTTP request headers (X-Correlation-Id)
3. Edge Backend execution record (correlation_id field)

---

## Step 6: Store Artifacts in This Directory

1. Copy `cloud-run-template.json` to `cloud-run-proof.json`
2. Fill in all fields with actual values captured in Step 5
3. Set `correlation_id_verification.all_match` to `true` if all three match
4. Optionally add supporting evidence:
   - `screenshots/` — Orchestrator job details, dashboard state
   - `logs/` — Edge Backend execution logs showing phase transitions
   - `response.json` — Raw API response from Edge Backend

### Final Checklist

- [ ] BPMN Process Instance ID captured
- [ ] API Workflow Run ID captured
- [ ] Edge execution_id captured with terminal status
- [ ] Correlation IDs match across all three layers
- [ ] Service task output shows real data (not mocked)
- [ ] Gateway evaluated actual response to route to Success/Failure end
- [ ] `cloud-run-proof.json` saved in this directory
