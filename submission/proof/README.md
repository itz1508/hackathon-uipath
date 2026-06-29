# Submission Proof — End-to-End Cloud Run Artifacts

This directory stores proof artifacts from the end-to-end cloud run demonstrating the full pipeline:

**BPMN Start → API Workflow Bridge → Edge Backend → Relay → Decision → Final Output**

## Required Artifacts

| Artifact | Description |
|----------|-------------|
| BPMN Process Instance ID | The UiPath Automation Cloud process instance identifier |
| API Workflow Run ID | The API Workflow Bridge job run identifier |
| Edge execution_id | The Edge Backend execution identifier with terminal status |
| Correlation ID | Must match across all three components (BPMN, Bridge, Edge) |
| Service Task Output | Gateway-evaluated real response data (not mocked) |

## Correlation ID Matching

The correlation ID (`X-Correlation-Id`) must be traceable across all three layers:

1. **BPMN Layer** — Process instance passes correlation_id as a Job Argument to the Service Task
2. **API Workflow Bridge** — Sets `X-Correlation-Id` header on the outbound HTTP request to Edge
3. **Edge Backend** — Receives and propagates the correlation ID through all phase transitions

All three must reference the same correlation ID value, proving the pipeline executed as a connected unit.

## Service Task Output Requirements

The service task output stored here must demonstrate:

- The BPMN Exclusive Gateway evaluated a **real** response (not mocked data)
- The response contains actual execution results from the Edge pipeline
- Terminal status reflects genuine phase completion (succeeded or failed with real reason)

## File Structure

```
submission-proof/
├── README.md                  # This file
├── cloud-run-template.json    # Template for proof artifact structure
├── INSTRUCTIONS.md            # Step-by-step cloud run instructions
└── (artifacts added after cloud run)
```

## How to Use

1. Read `INSTRUCTIONS.md` for step-by-step cloud run procedure
2. Perform the cloud run following those instructions
3. Fill in `cloud-run-template.json` with actual values
4. Save completed proof as `cloud-run-proof.json` in this directory
5. Optionally add screenshots or log excerpts as additional evidence
