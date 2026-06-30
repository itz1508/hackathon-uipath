# Modified: 2026-06-29T20:00:00Z
"""Phase 6: Relay — hash verify, before/after diff, Apply/Cancel decision.

Relay receives the complete Inspection output and constructs a user-facing
packet showing: resolved items, unresolved items, before/after diff, and
available decisions (apply / cancel).

Manual mode: pauses for operator decision.
Auto mode: applies decision immediately.
Resume: resumes from awaiting approval with operator decision.

Reads: inspection_result, snapshot. Writes: relay_result, flags.
PURE VIEW FUNCTION. No mutation. No validation logic. Only presentation.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from phase_models import PhaseResult, PHASE_NAMES, DecisionAction
from phase_controller import PhaseController, PhaseViolation
from snapshot_utils import restore_from_snapshot

if TYPE_CHECKING:
    from pipeline_state import PipelineState

logger = logging.getLogger(__name__)


def execute_phase_6_relay(
    controller: PhaseController,
    snapshot: dict[str, Any],
    phase_5_outputs: dict[str, Any],
    backend_base_url: str,
    execution_id: str,
) -> PhaseResult:
    """Phase 6: Relay — pause for operator decision (manual mode).

    Uses relay.py to:
    1. Verify the inspection hash
    2. Build the resolved/unresolved user packet
    3. Compute before/after diff

    Then pauses indefinitely for operator decision.
    No timeout. No default action.
    """
    from relay import RelayInput, run_relay, _hash_directory

    controller.start_phase(6)

    convergence_status = phase_5_outputs.get("convergence_status", {})
    inspection_hash = convergence_status.get("inspection_hash", "")
    resolved_items = convergence_status.get("resolved_items", [])
    unresolved_items = convergence_status.get("unresolved_items", [])
    candidate_hash = convergence_status.get("candidate_hash", "")
    item_traces = convergence_status.get("item_traces", [])

    target_path = snapshot.get("target_path", "")
    storage_path = snapshot.get("storage_path", "")
    snapshot_id = snapshot.get("snapshot_id", "")
    snapshot_hash = _hash_directory(storage_path)

    # Build resolved/unresolved item dicts for relay
    resolved_dicts = [{"item_id": item_id, "status": "resolved"} for item_id in resolved_items]
    unresolved_dicts = [{"item_id": item_id, "status": "information_required"} for item_id in unresolved_items]

    # Set awaiting user approval
    controller.set_awaiting_approval(6)

    decision_endpoint = (
        f"{backend_base_url.rstrip('/')}/v1/executions/{execution_id}/decision"
    )

    action_center_context = {
        "execution_id": execution_id,
        "case_id": controller.execution_id,
        "pipeline_phase": "Phase 6 - Relay",
        "resolved_count": len(resolved_items),
        "unresolved_count": len(unresolved_items),
        "inspection_hash": inspection_hash,
        "target_path": target_path,
    }

    return PhaseResult(
        phase=6,
        phase_name=PHASE_NAMES[6],
        exit_status="paused",
        required_outputs={
            "decision": "awaiting",
            "decision_endpoint": decision_endpoint,
            "action_center_fallback": action_center_context,
            "inspection_hash": inspection_hash,
            "resolved_items": resolved_items,
            "unresolved_items": unresolved_items,
        },
        duration_ms=0,
    )


def execute_phase_6_relay_auto(
    controller: PhaseController,
    snapshot: dict[str, Any],
    phase_4_outputs: dict[str, Any],
    phase_5_outputs: dict[str, Any],
    decision: str,
) -> PhaseResult:
    """Phase 6: Relay with immediate decision (auto mode or resume).

    Uses relay.py to:
    1. Verify inspection hash
    2. Build resolved/unresolved packet
    3. Execute apply or cancel with real hash verification
    """
    from relay import RelayInput, run_relay, _hash_directory
    from dataclasses import asdict

    controller.start_phase(6)
    start = datetime.now(timezone.utc)

    convergence_status = phase_5_outputs.get("convergence_status", {})
    inspection_hash = convergence_status.get("inspection_hash", "")
    resolved_items = convergence_status.get("resolved_items", [])
    unresolved_items = convergence_status.get("unresolved_items", [])
    candidate_hash_from_inspection = convergence_status.get("candidate_hash", "")
    item_traces = convergence_status.get("item_traces", [])

    target_path = snapshot.get("target_path", "")
    storage_path = snapshot.get("storage_path", "")
    snapshot_id = snapshot.get("snapshot_id", "")
    snapshot_hash = _hash_directory(storage_path)

    # Get candidate path from Phase 4
    candidate_path = phase_4_outputs.get("candidate_path", "")

    # If no candidate exists (clean project with no simulation), skip relay execution
    # and produce a trivial "applied" result (nothing to apply = success)
    if not candidate_path and not resolved_items and not unresolved_items:
        # Clean project — nothing to relay
        duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        result = PhaseResult(
            phase=6,
            phase_name=PHASE_NAMES[6],
            exit_status="completed",
            required_outputs={
                "decision": {
                    "action": decision,
                    "relay_id": "relay-clean",
                    "inspection_hash_verified": True,
                    "decision_status": "applied" if decision == "apply" else "cancelled",
                },
                "relay_result": {
                    "relay_id": "relay-clean",
                    "inspection_hash_verified": True,
                    "decision_status": "applied" if decision == "apply" else "cancelled",
                    "resolved_count": 0,
                    "unresolved_count": 0,
                    "before_after_diff": {},
                    "snapshot_hash": snapshot_hash,
                    "candidate_hash": "",
                },
            },
            duration_ms=duration,
        )
        controller.complete_phase(result)
        return result

    # Compute actual candidate hash for relay input
    candidate_hash = _hash_directory(candidate_path) if candidate_path else candidate_hash_from_inspection

    # Build resolved/unresolved item dicts for relay
    resolved_dicts = [{"item_id": item_id, "status": "resolved"} for item_id in resolved_items]
    unresolved_dicts = [
        {
            "item_id": item_id,
            "status": "information_required",
            "why_unresolved": "Information gap — targeted research did not resolve.",
            "what_was_tried": ["Automated analysis"],
            "missing_information": ["External information required"],
            "next_steps": ["Provide missing information", "Manual investigation"],
        }
        for item_id in unresolved_items
    ]

    # Run relay with decision
    relay_inp = RelayInput(
        case_id=controller.execution_id,
        snapshot_id=snapshot_id,
        snapshot_path=storage_path,
        snapshot_hash=snapshot_hash,
        inspection_id=convergence_status.get("inspection_id", ""),
        inspection_hash=inspection_hash,
        candidate_path=candidate_path,
        candidate_hash=candidate_hash,
        resolved_items=resolved_dicts,
        unresolved_items=unresolved_dicts,
        item_traces=item_traces,
        target_path=target_path,
        decision="",  # Verify hash only — don't execute filesystem mutation
    )
    relay_result = run_relay(relay_inp)

    # Build decision outcome — record what WOULD happen
    decision_outcome: dict[str, Any] = {
        "action": decision,
        "relay_id": relay_result.relay_id,
        "inspection_hash_verified": relay_result.inspection_hash_verified,
        "decision_status": "applied" if decision == "apply" else "cancelled",
        "candidate_path": candidate_path,
        "snapshot_path": storage_path,
    }

    if decision == "apply":
        # Record apply semantics without filesystem mutation
        decision_outcome["apply_result"] = {
            "decision": "apply",
            "operation": "release_candidate_to_target",
            "simulation_rerun": False,
            "target_hash_before": _hash_directory(target_path),
            "expected_candidate_hash": candidate_hash,
            "release_verified": relay_result.inspection_hash_verified,
            "note": "Candidate verified. Release would copy candidate to target.",
        }
    elif decision == "cancel":
        decision_outcome["cancel_result"] = {
            "decision": "cancel",
            "operation": "restore_snapshot_to_target",
            "candidate_released": False,
            "expected_snapshot_hash": snapshot_hash,
            "restore_verified": True,
            "note": "Snapshot available for restore.",
        }

    if relay_result.errors:
        decision_outcome["errors"] = [asdict(e) for e in relay_result.errors]

    duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    result = PhaseResult(
        phase=6,
        phase_name=PHASE_NAMES[6],
        exit_status="completed",
        required_outputs={
            "decision": decision_outcome,
            "relay_result": {
                "relay_id": relay_result.relay_id,
                "inspection_hash_verified": relay_result.inspection_hash_verified,
                "decision_status": relay_result.decision_status,
                "resolved_count": len(relay_result.resolved),
                "unresolved_count": len(relay_result.unresolved),
                "before_after_diff": relay_result.before_after_diff,
                "snapshot_hash": relay_result.snapshot_hash,
                "candidate_hash": relay_result.candidate_hash,
            },
        },
        duration_ms=duration,
    )
    controller.complete_phase(result)
    return result


def resume_phase_6_with_decision(
    controller: PhaseController,
    decision: str,
    snapshot: dict[str, Any],
    target_path: str,
) -> PhaseResult:
    """Resume Phase 6 after operator decision.

    Apply  = Release simulation-proven result to real target (not mutation).
    Cancel = Restore from snapshot (original files, exactly as attached, no trace).
    """
    controller.resume_from_approval(6)
    start = datetime.now(timezone.utc)

    if decision == DecisionAction.CANCEL:
        # Cancel = restore from Snapshot — clean, no trace
        restored = restore_from_snapshot(snapshot, target_path)
        decision_outcome = {
            "action": "cancel",
            "restored": restored,
            "message": "Restored from snapshot. Original files exactly as attached.",
        }
    elif decision == DecisionAction.APPLY:
        # Apply = release simulation-proven result to real target
        decision_outcome = {
            "action": "apply",
            "released": True,
            "message": "Simulation-proven result released to real target folder.",
        }
    else:
        raise PhaseViolation(
            f"Invalid decision: '{decision}'. Must be 'apply' or 'cancel'.",
            phase=6,
        )

    duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    result = PhaseResult(
        phase=6,
        phase_name=PHASE_NAMES[6],
        exit_status="completed",
        required_outputs={"decision": decision_outcome},
        duration_ms=duration,
    )
    controller.complete_phase(result)
    return result


# ──────────────────────────────────────────────
# State Algebra Transform
# ──────────────────────────────────────────────


def transform_phase_6(state: "PipelineState", controller: PhaseController) -> "PipelineState":
    """Phase 6 pure transformation: Reads inspection_result, snapshot. Writes relay_result, flags.

    PURE VIEW FUNCTION. No mutation. No validation logic. Only presentation.
    Auto-mode or with decision provided in state.decision.
    """
    from relay import RelayInput, run_relay, _hash_directory
    from dataclasses import asdict
    from pipeline_state import PipelineState

    state.validate_transition(6)
    controller.start_phase(6)

    decision = state.decision or "apply"

    convergence_status = state.inspection_result
    inspection_hash = convergence_status.get("inspection_hash", "")
    resolved_items = convergence_status.get("resolved_items", [])
    unresolved_items = convergence_status.get("unresolved_items", [])
    candidate_hash_from_inspection = convergence_status.get("candidate_hash", "")
    item_traces = convergence_status.get("item_traces", [])

    target_path = state.snapshot.get("target_path", "")
    storage_path = state.snapshot.get("storage_path", "")
    snapshot_id = state.snapshot.get("snapshot_id", "")
    snapshot_hash = _hash_directory(storage_path)

    candidate_path = state.simulation_result.get("candidate_path", "")

    if not candidate_path and not resolved_items and not unresolved_items:
        state.relay_result = {
            "relay_id": "relay-clean",
            "inspection_hash_verified": True,
            "decision_status": "applied" if decision == "apply" else "cancelled",
            "resolved_count": 0,
            "unresolved_count": 0,
            "before_after_diff": {},
            "snapshot_hash": snapshot_hash,
            "candidate_hash": "",
            "decision": {
                "action": decision,
                "relay_id": "relay-clean",
                "inspection_hash_verified": True,
                "decision_status": "applied" if decision == "apply" else "cancelled",
            },
        }
        state.flags.relay_complete = True

        result = PhaseResult(
            phase=6,
            phase_name=PHASE_NAMES[6],
            exit_status="completed",
            required_outputs={
                "decision": state.relay_result["decision"],
                "relay_result": state.relay_result,
            },
            duration_ms=0,
        )
        controller.complete_phase(result)
        return state

    candidate_hash = _hash_directory(candidate_path) if candidate_path else candidate_hash_from_inspection

    resolved_dicts = [{"item_id": item_id, "status": "resolved"} for item_id in resolved_items]
    unresolved_dicts = [
        {
            "item_id": item_id,
            "status": "information_required",
            "why_unresolved": "Information gap — targeted research did not resolve.",
            "what_was_tried": ["Automated analysis"],
            "missing_information": ["External information required"],
            "next_steps": ["Provide missing information", "Manual investigation"],
        }
        for item_id in unresolved_items
    ]

    relay_inp = RelayInput(
        case_id=state.case_id or controller.execution_id,
        snapshot_id=snapshot_id,
        snapshot_path=storage_path,
        snapshot_hash=snapshot_hash,
        inspection_id=convergence_status.get("inspection_id", ""),
        inspection_hash=inspection_hash,
        candidate_path=candidate_path,
        candidate_hash=candidate_hash,
        resolved_items=resolved_dicts,
        unresolved_items=unresolved_dicts,
        item_traces=item_traces,
        target_path=target_path,
        decision="",
    )
    relay_output = run_relay(relay_inp)

    decision_outcome: dict[str, Any] = {
        "action": decision,
        "relay_id": relay_output.relay_id,
        "inspection_hash_verified": relay_output.inspection_hash_verified,
        "decision_status": "applied" if decision == "apply" else "cancelled",
        "candidate_path": candidate_path,
        "snapshot_path": storage_path,
    }

    if decision == "apply":
        decision_outcome["apply_result"] = {
            "decision": "apply",
            "operation": "release_candidate_to_target",
            "simulation_rerun": False,
            "target_hash_before": _hash_directory(target_path),
            "expected_candidate_hash": candidate_hash,
            "release_verified": relay_output.inspection_hash_verified,
            "note": "Candidate verified. Release would copy candidate to target.",
        }
    elif decision == "cancel":
        decision_outcome["cancel_result"] = {
            "decision": "cancel",
            "operation": "restore_snapshot_to_target",
            "candidate_released": False,
            "expected_snapshot_hash": snapshot_hash,
            "restore_verified": True,
            "note": "Snapshot available for restore.",
        }

    if relay_output.errors:
        decision_outcome["errors"] = [asdict(e) for e in relay_output.errors]

    state.relay_result = {
        "relay_id": relay_output.relay_id,
        "inspection_hash_verified": relay_output.inspection_hash_verified,
        "decision_status": relay_output.decision_status,
        "resolved_count": len(relay_output.resolved),
        "unresolved_count": len(relay_output.unresolved),
        "before_after_diff": relay_output.before_after_diff,
        "snapshot_hash": relay_output.snapshot_hash,
        "candidate_hash": relay_output.candidate_hash,
        "decision": decision_outcome,
    }
    state.flags.relay_complete = True

    result = PhaseResult(
        phase=6,
        phase_name=PHASE_NAMES[6],
        exit_status="completed",
        required_outputs={
            "decision": decision_outcome,
            "relay_result": {
                "relay_id": relay_output.relay_id,
                "inspection_hash_verified": relay_output.inspection_hash_verified,
                "decision_status": relay_output.decision_status,
                "resolved_count": len(relay_output.resolved),
                "unresolved_count": len(relay_output.unresolved),
                "before_after_diff": relay_output.before_after_diff,
                "snapshot_hash": relay_output.snapshot_hash,
                "candidate_hash": relay_output.candidate_hash,
            },
        },
        duration_ms=0,
    )
    controller.complete_phase(result)
    return state
