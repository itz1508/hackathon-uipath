==============================
CLOUD ORCHESTRATION EVIDENCE (JSON EXTRACT)
==============================
**Source:** Image 3 & 4 (Code Editor - `proof_type: cloud_end_to_end_execution`)

**VISIBLE JSON STRUCTURE:**
{
  "proof_type": "cloud_end_to_end_execution",
  "project": "Audisor",
  "timestamp": "2026-06-22T18:09:00Z",
  "org": "theoneshot",
  "tenant": "DefaultTenant",
  "folder": "Debug_hackaton",
  
  "bpmn_execution": {
    "process_name": "Agentic Process",
    "process_key": "4FBE2950-3B67-4DD6-803E-074776736898",
    "job_state": "Successful",
    "source": "Manual",
    "duration_ms": 2730
  },

  "api_workflow": {
    "process_name": "API Workflow",
    "role": "Submit-and-poll bridge between BPMN and Edge backend"
  },

  "edge_workflow": {
    "process_name": "Audisor.Edge.Workflow",
    "phases_executed": "0-6 (Snapshot -> Scan -> PreSim -> Simulation -> Inspect...)",
    "role": "Edge WorkflowControl pipeline - Phase 0 through Phase 6"
  },

  "infrastructure": {
    "backend": "maestro-backend (uvicorn port 8790)",
    "tunnel_type": "Cloudflare quick tunnel (ephemeral)",
    "cli": "uip v1.195.0",
    "python": "3.14.4"
  },

  "execution_flow": [
    "1. Maestro BPMN instance started (Agentic Process)",
    "2. BPMN service task invoked API Workflow bridge",
    "3. API Workflow POSTed to tunnel -> backend -> /v1/executions",
    "4. Backend resolved taskRef 'WorkflowControl' -> audisor_api_workflow",
    "5. UiPath CLI executed: uipath run main <json> --output-file <path>",
    "6. WorkflowControl v0.2.0 ran Phase 0-6 pipeline",
    "7. Output written -> backend completed execution",
    "8. API Workflow polled status -> received 'succeeded'",
    "9. Normalized response returned to BPMN",
    "10. BPMN gateway evaluated success=true -> Successful End"
  ],

  "contract_verification": {
    "execution_lifecycle": "aligned",
    "polling_schema": "aligned",
    "terminal_states": "aligned",
    "payload_normalization": "aligned",
    "task_ref_resolution": "filesystem-bound (not Orchestrator-name-bound)"
  },

  "agent_definition": {
    "name": "PreSimulation Evaluator Agent",
    "model": "claude-sonnet-4-20250514",
    "scoring_threshold": "93.91% (PASS_THRESHOLD = 9391)",
    "scoring_formula": "completeness*0.25 + traceability*0.20 + scope_and_bo..."
  }
}

==============================
EXECUTION EVIDENCE SUMMARY
==============================
**Source:** Image 2 (Web UI Table - "Evidence Summary")

**VISIBLE TABLE DATA:**
| Evidence | Value |
|---|---|
| Execution ID | 8df078e3-54f8-47fc-88ad-ba98655aefba |
| Correlation ID | demo-correlation-001 |
| Final State | Succeeded |
| Final Phase | 6 |
| Final Progress | 100 |
| Phases Completed | 7/7 (0->6) |
| Total Duration | ~86ms |
| Target Path | d:\Dev\hackaton-uipath-jun29-workbench\demo-workspace |
| Snapshot ID | f290d59e-b221-4364-a0d0-24e0ca98d579 |

**Target Selection Documentation:**
- Target: Workspace root (.)
- Result: Failed
- Reason: shutil.copytree hits .git/objects with...

==============================
TEST SUITE EVIDENCE
==============================
**Source:** Image 1 (Terminal Output)

**VISIBLE TEST RESULTS:**
- Backend facade smoke tests: 2 passed
- Workbench backend tests: 218 passed
- Pipeline contract verification: 71 passed
- Pipeline fixture regression: All 8 fixtures passed
- Property tests (API spec + timestamps): 2 passed
- Root directory is clean, all tests pass, no runtime breakage.

==============================
RAW EVIDENCE DUMP (PYTHON REPL)
==============================
**Source:** Image 5 (Python REPL & Chat Interface)

**VISIBLE DICTIONARY OUTPUT:**
{
  "execution_id": "7f130811-d2c7-43fb-81fe-a63c112c3c07",
  "correlation_id": "demo-evidence-final",
  "idempotency_key": "demo-evidence-key",
  "uiapth_job_id": "UIPATH-JOB-DEMO-FINAL",
  "target_path": "d:\\Dev\\hackaton-uipath-jun29-workbench\\demo-workspace",
  "mode": "auto",
  "final_state": "Succeeded",
  "error": null,
  "execution_log": {
    "execution_id": "7f130811-d2c7-43fb-81fe-a63c112c3c07",
    "start_time": "2026-06-27T01:32:53.211Z",
    "finish_time": "2026-06-27T01:32:53.261Z",
    "duration_ms": 50,
    "final_status": "Succeeded",
    "phase_at_completion": 6
  }
}

**VISIBLE CHAT SNIPPET:**
"Full evidence captured. Let me address the advisor's question about 0ms phases and save this"