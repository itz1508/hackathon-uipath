# Current Pipeline Runtime Contract

<!-- Modified: 2026-06-27T20:15:00Z -->

## Invocation (by AgentRunner)

```
command: [uipath.exe, "run", "main", <json_input>, "--output-file", <output_path>]
cwd: pipeline/
```

## Input Model (WorkflowInput)

```python
class WorkflowInput(BaseModel):
    case_id: str            # required, min_length=1
    target_path: str        # required, min_length=1
    backend_base_url: str   # default "http://localhost:8790"
    correlation_id: str     # default ""
    requested_action: Literal["run_pipeline", "resume_decision"]  # default "run_pipeline"
    decision: Literal["apply", "cancel", ""]  # default ""
    execution_id: str       # default ""
    mode: Literal["manual", "auto"]  # default "manual"
```

## Output Model (WorkflowOutput)

```python
class WorkflowOutput(BaseModel):
    case_id: str
    execution_id: str
    pipeline_status: PipelineStatus  # accepted|running|awaiting_decision|succeeded|failed|cancelled
    current_phase: int
    current_phase_name: str
    phase_results: list[PhaseResult]
    branch_status: BranchStatus
    snapshot_id: str
    decision_required: bool
    decision_endpoint: str
    action_center_fallback: ActionCenterFallback | None
    final_output: dict[str, Any]
    error: dict[str, Any]
    message: str
```

## Phase Results (per phase)

```python
class PhaseResult(BaseModel):
    phase: int
    phase_name: str
    exit_status: str  # "completed" | "failed" | "isolated" | "awaiting_user_approval"
    required_outputs: dict[str, Any]
    timestamp: str
    duration_ms: int
```

## Backend expectations

- Returns JSON matching WorkflowOutput
- Backend reads `output.pipeline_status` to determine terminal status
- Backend reads `output.phase_results` for phase details
- Backend reads `output.error` for failure details
- Backend maps succeeded → StatusValue.SUCCEEDED, failed → StatusValue.FAILED

## Compatibility Rules

- Do NOT remove or rename existing top-level fields
- New structured output may be ADDED to required_outputs
- Phase order must remain: 0, 1, 2, 3, 4, 5, 6
- Controller owns all transitions
- PASS_THRESHOLD = 9391 (93.91%)
