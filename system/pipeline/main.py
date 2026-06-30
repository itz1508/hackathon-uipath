# Modified: 2026-06-29T20:00:00Z
"""Standalone 8-phase pipeline runtime — UiPath Python SDK Function entry point.

Orchestrates the canonical 8-phase pipeline (Phase 0–7) by wiring
the Phase Controller state machine. This is a DEFINITION — the
authoritative entry point that the UiPath Function bridge invokes.
"""
import logging
import uuid

from phase_models import (
    WorkflowInput,
    WorkflowOutput,
    PhaseResult,
    PipelineStatus,
    PhaseStatus,
    DecisionAction,
    BranchStatus,
    ActionCenterFallback,
    PHASE_ORDER,
    PHASE_NAMES,
    REQUIRED_OUTPUTS,
    PASS_THRESHOLD,
    VALID_EXIT_STATUSES,
)
from phase_controller import PhaseController, PhaseViolation
from orchestrator import run_pipeline, resume_with_decision

logger = logging.getLogger(__name__)

# ── Backwards-compatible re-exports ──────────────────────────────────────────
# Consumers:
#   pipeline/tests/run_fixture_regression.py  → main, WorkflowInput
#   pipeline/tests/verify_contract.py         → main, WorkflowInput, WorkflowOutput,
#                                               PhaseResult, PipelineStatus
#   NextFlow-mcp/server.py                     → WorkflowInput, main
#   NextFlow/core/runner.py                    → main, WorkflowInput
#   pipeline/_run_analysis.py                 → main, WorkflowInput (via pipeline.main)


def main(input: WorkflowInput) -> WorkflowOutput:
    """Pipeline runtime — UiPath Python SDK entry point."""
    if not input.correlation_id:
        input.correlation_id = str(uuid.uuid4())

    logger.info(
        f"workflow_control.main action={input.requested_action} "
        f"case_id={input.case_id} correlation_id={input.correlation_id}"
    )

    if input.requested_action == "resume_decision":
        return resume_with_decision(input)

    return run_pipeline(input)
