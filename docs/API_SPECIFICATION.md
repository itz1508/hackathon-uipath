# API Specification

<!-- Modified: 2026-06-28T14:00:00Z -->

Complete API reference for the Workbench Backend (FastAPI, port 8790). All endpoints are documented from `workbench_backend/contract.json`.

**Base URL:** `http://localhost:8790`

---

## Table of Contents

- [Health & Info](#health--info)
- [Execution Submission](#execution-submission)
- [Execution Status](#execution-status)
- [Logs & Metrics](#logs--metrics)
- [Execution Management](#execution-management)
- [Error Codes](#error-codes)
- [State Machine](#state-machine)

---

## Health & Info

### GET /health

Health check endpoint.

**Request:** No request body.

**Response (200):**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"healthy"` or `"unhealthy"` |
| `version` | string | Semantic version (e.g., `"0.1.0"`) |

**Status Codes:**

| Code | Meaning |
|------|---------|
| 200 | Service is running |

---

### GET /version

Version and build information.

**Request:** No request body.

**Response (200):**

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | Semantic version (e.g., `"0.1.0"`) |
| `build_timestamp` | string | ISO 8601 UTC build timestamp |
| `migration_phase` | string | Current migration phase identifier |

**Status Codes:**

| Code | Meaning |
|------|---------|
| 200 | Success |

---

## Execution Submission

### POST /execute

Submit a new execution request (legacy path).

**Headers:**

| Header | Required | Description |
|--------|----------|-------------|
| `Idempotency-Key` | Optional | Overrides body `idempotency_key` field |
| `X-Correlation-Id` | Optional | Overrides body `correlation_id` field |
| `X-UiPath-JobId` | Optional | Propagated to logs |

**Request Schema:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `request_id` | string | Yes | Non-whitespace request identifier |
| `case_id` | string | Yes | Non-whitespace case identifier |
| `task_ref` | string | Yes | Non-whitespace task reference |
| `payload` | object | Yes | Must contain `action` and `caseId` fields |
| `idempotency_key` | string | Yes | Non-whitespace idempotency key |
| `correlation_id` | string | Yes | Non-whitespace correlation identifier |

**Response (202 — Created / 200 — Idempotent duplicate):**

| Field | Type | Description |
|-------|------|-------------|
| `executionId` | string | UUID v4 identifier for the execution |
| `statusUrl` | string | URL path to poll status (`/status/{executionId}`) |

**Status Codes:**

| Code | Meaning |
|------|---------|
| 202 | Execution accepted and created |
| 200 | Idempotent duplicate — execution already exists |
| 400 | Malformed request or validation failure |
| 503 | Service not ready (starting up or shutting down) |

---

### POST /v1/executions

Submit execution (Bridge-compatible schema).

**Headers:**

| Header | Required | Description |
|--------|----------|-------------|
| `Idempotency-Key` | Optional | Overrides `input.requestId` for deduplication |
| `X-Correlation-Id` | Optional | Overrides `input.requestId` for tracing |
| `X-UiPath-JobId` | Optional | Propagated to logs |

**Request Schema:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `executionType` | string | Yes | Execution type identifier |
| `tenant` | string | Yes | Tenant identifier |
| `process` | object | Yes | Process definition (see below) |
| `process.taskRef` | string | Yes | Task reference |
| `process.entryPoint` | string | Yes | Entry point identifier |
| `input` | object | Yes | Execution input (see below) |
| `input.requestId` | string | Yes | Request identifier |
| `input.caseId` | string | Yes | Case identifier |
| `input.payload` | object | Yes | Must contain `action` and `caseId` fields |

**Response (202 — Created / 200 — Idempotent duplicate):**

| Field | Type | Description |
|-------|------|-------------|
| `executionId` | string | UUID v4 identifier for the execution |
| `statusUrl` | string | URL path to poll status (`/v1/executions/{executionId}`) |

**Status Codes:**

| Code | Meaning |
|------|---------|
| 202 | Execution accepted and created |
| 200 | Idempotent duplicate — execution already exists |
| 400 | Malformed request or validation failure |
| 503 | Service not ready (starting up or shutting down) |

---

## Execution Status

### GET /status/{id}

Get execution status with phase and progress information.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Execution UUID |

**Request:** No request body.

**Response (200):**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | UUID v4 execution identifier |
| `status` | string | One of: `Received`, `Validated`, `Queued`, `Running`, `Succeeded`, `Failed`, `Cancelled` |
| `phase` | integer | Current phase number (0–6) |
| `progress` | integer | Progress percentage (0–100) |

**Status Codes:**

| Code | Meaning |
|------|---------|
| 200 | Execution found |
| 404 | Execution ID does not exist |

---

### GET /v1/executions/{id}

Get execution status in BridgeOutput-compatible format.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Execution UUID |

**Request:** No request body.

**Response (200):**

| Field | Type | Description |
|-------|------|-------------|
| `execution_id` | string | Execution identifier |
| `execution_status` | string | One of: `succeeded`, `failed`, `faulted`, `cancelled`, `timed_out`, `error`, `running` |
| `backend_result` | object | Result data (when succeeded) |
| `backend_error` | object | Error data (when failed) |
| `success` | boolean | Whether execution completed successfully |

**Status Codes:**

| Code | Meaning |
|------|---------|
| 200 | Execution found |
| 404 | Execution ID does not exist |

---

### GET /v1/executions/{id}/progress

Phase progress for UiPath polling.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Execution UUID |

**Request:** No request body.

**Response (200):**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Execution identifier |
| `phase` | integer | Current phase number (0–6) |
| `phase_name` | string | Human-readable phase name |
| `progress` | integer | Progress percentage (0–100) |
| `status` | string | Current execution status |

**Status Codes:**

| Code | Meaning |
|------|---------|
| 200 | Execution found |
| 404 | Execution ID does not exist |

> **Note:** This endpoint exists in the backend's actual routes (per AGENTS.md) for UiPath polling support.

---

## Logs & Metrics

### GET /logs/{id}

Retrieve the structured execution log for a completed or in-progress execution.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Execution UUID |

**Request:** No request body.

**Response (200):**

| Field | Type | Description |
|-------|------|-------------|
| `execution_id` | string | Execution identifier |
| `correlation_id` | string | End-to-end tracing identifier |
| `uipath_job_id` | string or null | UiPath Job ID (omitted when absent) |
| `start_time` | string | ISO 8601 UTC with millisecond precision |
| `finish_time` | string or null | ISO 8601 UTC with millisecond precision |
| `duration_ms` | integer or null | Total execution duration in milliseconds |
| `final_status` | string | Terminal execution state |
| `phase_at_completion` | integer | Phase number (0–6) at which execution ended |
| `errors` | array or null | List of ErrorRecord objects (omitted when empty) |
| `timeline` | array | List of PhaseLogEntry objects |

**PhaseLogEntry Schema:**

| Field | Type | Description |
|-------|------|-------------|
| `phase` | integer | Phase number (0–6) |
| `phase_name` | string | One of: `snapshot`, `scan_analysis`, `pre_simulation`, `simulation`, `inspection`, `relay`, `final_result` |
| `entry_timestamp` | string | ISO 8601 UTC with millisecond precision |
| `exit_timestamp` | string or null | ISO 8601 UTC with millisecond precision |
| `duration_ms` | integer or null | Phase duration in milliseconds |

**ErrorRecord Schema:**

| Field | Type | Description |
|-------|------|-------------|
| `exception_type` | string | Exception class name |
| `message` | string | Error message |
| `stack_trace` | string | Truncated to max 5000 characters |
| `phase` | integer or null | Phase where error occurred |

**Status Codes:**

| Code | Meaning |
|------|---------|
| 200 | Log found |
| 404 | Execution ID does not exist |

---

### GET /metrics

Aggregate execution statistics.

**Request:** No request body.

**Response (200):**

| Field | Type | Description |
|-------|------|-------------|
| `total_executions` | integer | Total number of executions |
| `success_count` | integer | Number of successful executions |
| `failure_count` | integer | Number of failed executions |
| `average_duration_ms` | float | Average execution duration in milliseconds |
| `by_state` | object | Map of state name → count |

**Status Codes:**

| Code | Meaning |
|------|---------|
| 200 | Success |

---

## Execution Management

### DELETE /executions/{id}

Cancel an in-progress execution.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Execution UUID |

**Request:** No request body.

**Response (200):**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Execution identifier |
| `status` | string | `"Cancelled"` |

**Status Codes:**

| Code | Meaning |
|------|---------|
| 200 | Execution cancelled successfully |
| 404 | Execution ID does not exist |
| 409 | Invalid transition — execution is already in a terminal state or not in a cancellable state |

---

## Error Codes

All error responses include a structured error body with the following codes:

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `MALFORMED_REQUEST` | 400 | Request body is not valid JSON or cannot be parsed |
| `VALIDATION_FAILED` | 400 | One or more required fields are missing, null, or whitespace-only |
| `NOT_FOUND` | 404 | Execution ID does not exist in the store |
| `INVALID_TRANSITION` | 409 | Attempted state transition is not valid |
| `ALREADY_TERMINAL` | 409 | Execution is already in a terminal state and cannot be cancelled |
| `NOT_READY` | 503 | Service is starting up or shutting down |

---

## State Machine

Executions follow a deterministic state machine with the following states and transitions:

### States

| State | Terminal | Cancellable | Description |
|-------|----------|-------------|-------------|
| `Received` | No | No | Initial state after submission |
| `Validated` | No | No | Request validated, ready to queue |
| `Queued` | No | Yes | Waiting for execution slot |
| `Running` | No | Yes | Pipeline actively processing |
| `Succeeded` | Yes | No | Execution completed successfully |
| `Failed` | Yes | No | Execution failed with error |
| `Cancelled` | Yes | No | Execution cancelled by user |

### Transitions

```
Received  →  Validated  →  Queued  →  Running  →  Succeeded
    ↓            ↓                       ↓
  Failed       Failed                  Failed
                                         ↓
Queued  →  Cancelled              Cancelled
```

| From | Allowed Transitions |
|------|-------------------|
| `Received` | `Validated`, `Failed` |
| `Validated` | `Queued`, `Failed` |
| `Queued` | `Running`, `Cancelled` |
| `Running` | `Succeeded`, `Failed`, `Cancelled` |

### Phase Mapping

| Phase | Name | Description |
|-------|------|-------------|
| 0 | `snapshot` | Initial data capture |
| 1 | `scan_analysis` | Document scanning and analysis |
| 2 | `pre_simulation` | Pre-simulation preparation |
| 3 | `simulation` | Core simulation execution |
| 4 | `inspection` | Result inspection and validation |
| 5 | `relay` | Output relay and formatting |
| 6 | `final_result` | Final result assembly |
