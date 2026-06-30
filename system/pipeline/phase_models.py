# Modified: 2026-06-29T20:00:00Z
"""Constants, enums, and Pydantic models for the pipeline.

Single source of truth for all data contracts used across phase modules.
No side effects on import — no logging, no I/O, no network calls.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

# Ordered phase sequence — strictly enforced
PHASE_ORDER: list[int] = [0, 1, 2, 3, 4, 5, 6, 7]

PHASE_NAMES: dict[int, str] = {
    0: "snapshot",
    1: "scan",
    2: "analysis",
    3: "pre_simulation",
    4: "simulation",
    5: "inspection",
    6: "relay",
    7: "final_output",
}

# Required outputs per phase for exit validation
REQUIRED_OUTPUTS: dict[int, list[str]] = {
    0: ["snapshot_id", "file_hashes"],
    1: ["scan_results", "tools_run"],
    2: ["llm_statement", "handoff_statement", "pre_calibration_statement", "classification_results"],
    3: ["package_confidence_score", "simulation_ready", "ready_parts", "isolated_parts"],
    4: ["simulation_result"],
    5: ["convergence_status"],
    6: ["decision"],
    7: ["final_output"],
}

# Information completeness threshold (integer hundredth-points)
PASS_THRESHOLD = 9391  # 93.91%

# Valid exit statuses that allow advancement
VALID_EXIT_STATUSES = {"completed", "isolated"}


# ──────────────────────────────────────────────
# Enums and Data Models
# ──────────────────────────────────────────────


class PhaseStatus(str, Enum):
    """Status of an individual phase in the pipeline."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ISOLATED = "isolated"
    AWAITING_USER_APPROVAL = "awaiting_user_approval"


class PipelineStatus(str, Enum):
    """Overall pipeline execution status."""

    ACCEPTED = "accepted"
    RUNNING = "running"
    AWAITING_DECISION = "awaiting_decision"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DecisionAction(str, Enum):
    """Operator decision at Phase 6 (Relay)."""

    APPLY = "apply"
    CANCEL = "cancel"


class WorkflowInput(BaseModel):
    """Input for the standalone pipeline runtime.

    The minimum required fields to start the pipeline.
    """

    case_id: str = Field(min_length=1, description="Case correlation ID")
    target_path: str = Field(min_length=1, description="Folder path to process")
    backend_base_url: str = Field(
        default="http://localhost:8790",
        description="Workbench backend URL for decision endpoint integration",
    )
    correlation_id: str = Field(
        default="", description="End-to-end tracing correlation ID"
    )
    requested_action: Literal["run_pipeline", "resume_decision"] = Field(
        default="run_pipeline",
        description="Whether to start a new pipeline or resume from awaiting decision",
    )
    decision: Literal["apply", "cancel", ""] = Field(
        default="", description="Operator decision when resuming (Phase 6)"
    )
    execution_id: str = Field(
        default="", description="Execution ID when resuming from decision"
    )
    mode: Literal["manual", "auto"] = Field(
        default="manual",
        description="Pipeline mode: 'manual' pauses at Relay for operator decision, 'auto' completes end-to-end",
    )
    isolation_enabled: bool = Field(
        default=True,
        description="Enable Isolation Engine between pre-simulation scoring and simulation. False = Run A (no isolation research).",
    )


class PhaseResult(BaseModel):
    """Exit record for a single phase."""

    phase: int
    phase_name: str
    exit_status: str
    required_outputs: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    duration_ms: int = 0


class BranchStatus(BaseModel):
    """Status of controller-authorized concurrent branches."""

    simulation_parts: list[str] = Field(default_factory=list)
    isolation_items: list[str] = Field(default_factory=list)
    branch_outcomes: dict[str, str] = Field(default_factory=dict)
    convergence_status: Literal["pending", "waiting", "converged"] = "pending"
    all_converged: bool = False


class ActionCenterFallback(BaseModel):
    """Action Center fallback configuration for human-in-the-loop decision.

    When the Operator Dashboard is unavailable or disconnected, Action Center
    serves as the fallback decision channel. The schema at
    action-center/action-schema.json defines the task form presented to the
    operator with execution context, diff stats, and Apply/Cancel outcomes.
    """

    enabled: bool = True
    schema_path: str = "action-center/action-schema.json"
    task_title: str = "Pipeline Relay Decision - Apply or Cancel"
    context: dict[str, Any] = Field(default_factory=dict)


class WorkflowOutput(BaseModel):
    """Deterministic output from the pipeline runtime.

    Produced on every code path — success, failure, or awaiting decision.
    """

    case_id: str
    execution_id: str
    pipeline_status: PipelineStatus
    current_phase: int = -1
    current_phase_name: str = ""
    phase_results: list[PhaseResult] = Field(default_factory=list)
    branch_status: BranchStatus = Field(default_factory=BranchStatus)
    snapshot_id: str = ""
    decision_required: bool = False
    decision_endpoint: str = ""
    action_center_fallback: ActionCenterFallback | None = None
    final_output: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] = Field(default_factory=dict)
    message: str = ""
