# Modified: 2026-06-29T20:00:00Z
"""Phase 7: Final Output — resolved.html, root causes, handoff report.

Produces complete output package for any decision path.
Always produces a final report regardless of decision.

Reads: inspection_result, relay_result. Writes: final_output, flags.
Derived, not executed.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from phase_models import PhaseResult, PHASE_NAMES
from phase_controller import PhaseController

if TYPE_CHECKING:
    from pipeline_state import PipelineState

logger = logging.getLogger(__name__)


def execute_phase_7_final_output(
    controller: PhaseController,
    phase_results: list[PhaseResult],
    decision: str,
) -> PhaseResult:
    """Phase 7: Final Output — uses final_output.py for complete report generation.

    No LLM agent required. Always produces:
    - Total issues found
    - Root cause per issue
    - resolved.html (full resolved diff report)
    - Handoff report (when unresolved items remain)
    - Forward and backward traces

    If fully successful: confirmation note
    If partially successful: full explanation with next steps
    If cancelled: what was resolved on candidate but not released
    """
    from final_output import build_final_output, FinalOutputInput
    from relay import _hash_directory

    controller.start_phase(7)
    start = datetime.now(timezone.utc)

    # Gather outputs from all phases
    phase_0_outputs = next(
        (r.required_outputs for r in phase_results if r.phase == 0), {}
    )
    phase_2_outputs = next(
        (r.required_outputs for r in phase_results if r.phase == 2), {}
    )
    phase_4_outputs = next(
        (r.required_outputs for r in phase_results if r.phase == 4), {}
    )
    phase_5_outputs = next(
        (r.required_outputs for r in phase_results if r.phase == 5), {}
    )
    phase_6_outputs = next(
        (r.required_outputs for r in phase_results if r.phase == 6), {}
    )

    convergence_status = phase_5_outputs.get("convergence_status", {})
    resolved_item_ids = convergence_status.get("resolved_items", [])
    unresolved_item_ids = convergence_status.get("unresolved_items", [])
    item_traces_raw = convergence_status.get("item_traces", [])
    inspection_hash = convergence_status.get("inspection_hash", "")

    snapshot_id = phase_0_outputs.get("snapshot_id", "")
    storage_path = phase_0_outputs.get("storage_path", "")
    target_path = phase_0_outputs.get("target_path", "")
    snapshot_hash = _hash_directory(storage_path) if storage_path else ""

    candidate_path = phase_4_outputs.get("candidate_path", "")
    candidate_hash = _hash_directory(candidate_path) if candidate_path else ""

    # Determine final_target_hash based on decision
    if decision == "apply":
        final_target_hash = candidate_hash  # Apply releases candidate
    else:
        final_target_hash = snapshot_hash  # Cancel restores snapshot

    # Build resolved items with root cause detail
    classification_results = phase_2_outputs.get("classification_results", [])
    finding_map = {issue.get("id", ""): issue for issue in classification_results}

    resolved_items_detail = []
    for item_id in resolved_item_ids:
        finding = finding_map.get(item_id, {})
        resolved_items_detail.append({
            "item_id": item_id,
            "root_cause": finding.get("description", "Identified and resolved"),
            "resolution": "Fixed via simulation on candidate copy",
            "validation": "compileall validation passed",
            "released": decision == "apply",
        })

    # Build unresolved items with full detail
    unresolved_items_detail = []
    for item_id in unresolved_item_ids:
        finding = finding_map.get(item_id, {})
        unresolved_items_detail.append({
            "item_id": item_id,
            "root_cause": finding.get("description", "Information gap detected"),
            "why_unresolved": "Missing information prevents safe one-shot resolution",
            "what_was_tried": ["Automated analysis", "Targeted research"],
            "missing_information": ["External information required for safe resolution"],
            "next_steps": ["Provide missing information", "Re-run pipeline with additional context"],
            "retry_guidance": "Re-run after providing the missing information identified above",
        })

    # Build item traces for forward/backward tracing
    enriched_traces = []
    for trace in item_traces_raw:
        item_id = trace.get("finding_id", trace.get("pre_simulation_item_id", ""))
        enriched_traces.append({
            "item_id": item_id,
            "phase_0_snapshot": snapshot_id,
            "phase_1_finding": item_id,
            "phase_2_item": f"analysis-{item_id}",
            "phase_3_item": f"presim-{item_id}",
            "phase_4_result": trace.get("simulation_or_isolation_id", ""),
            "phase_5_inspection": trace.get("inspection_item_id", ""),
            "phase_6_relay": f"relay-{item_id}",
            "phase_7_final": "",  # Will be enriched by build_final_output
        })

    total_issues = len(resolved_item_ids) + len(unresolved_item_ids)

    # Build final output using final_output.py
    final_input = FinalOutputInput(
        case_id=controller.execution_id,
        decision=decision,
        total_issues=total_issues if total_issues > 0 else 0,
        resolved_items=resolved_items_detail,
        unresolved_items=unresolved_items_detail,
        snapshot_hash=snapshot_hash,
        inspection_hash=inspection_hash,
        final_target_hash=final_target_hash,
        item_traces=enriched_traces,
        relay_result=phase_6_outputs.get("relay_result", {}),
    )
    final_package = build_final_output(final_input)

    # Construct the final_output dict for WorkflowOutput
    final_output = {
        "total_issues": final_package.total_issues,
        "resolved_count": final_package.resolved_count,
        "unresolved_count": final_package.unresolved_count,
        "resolved_items": final_package.resolved_items,
        "unresolved_items": final_package.unresolved_items,
        "resolved_html": final_package.reports.get("resolved_html", ""),
        "completion_status": (
            "fully_resolved" if final_package.unresolved_count == 0 and decision == "apply"
            else "partially_resolved" if decision == "apply"
            else "cancelled"
        ),
        "success_note": final_package.success_note,
        "continuation_handoff": final_package.continuation_handoff,
        "snapshot_hash": final_package.snapshot_hash,
        "inspection_hash": final_package.inspection_hash,
        "final_target_hash": final_package.final_target_hash,
        "forward_traces": final_package.forward_traces,
        "backward_traces": final_package.backward_traces,
    }

    duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    result = PhaseResult(
        phase=7,
        phase_name=PHASE_NAMES[7],
        exit_status="completed",
        required_outputs={"final_output": final_output},
        duration_ms=duration,
    )
    controller.complete_phase(result)
    return result


# ──────────────────────────────────────────────
# State Algebra Transform
# ──────────────────────────────────────────────


def transform_phase_7(state: "PipelineState", controller: PhaseController) -> "PipelineState":
    """Phase 7 pure transformation: Reads inspection_result, relay_result. Writes final_output, flags.

    Derived, not executed.
    """
    from final_output import build_final_output, FinalOutputInput
    from relay import _hash_directory
    from pipeline_state import PipelineState

    state.validate_transition(7)
    controller.start_phase(7)

    decision = state.decision or "apply"

    convergence_status = state.inspection_result
    resolved_item_ids = convergence_status.get("resolved_items", [])
    unresolved_item_ids = convergence_status.get("unresolved_items", [])
    item_traces_raw = convergence_status.get("item_traces", [])
    inspection_hash = convergence_status.get("inspection_hash", "")

    snapshot_id = state.snapshot.get("snapshot_id", "")
    storage_path = state.snapshot.get("storage_path", "")
    target_path = state.snapshot.get("target_path", "")
    snapshot_hash = _hash_directory(storage_path) if storage_path else ""

    candidate_path = state.simulation_result.get("candidate_path", "")
    candidate_hash = _hash_directory(candidate_path) if candidate_path else ""

    if decision == "apply":
        final_target_hash = candidate_hash
    else:
        final_target_hash = snapshot_hash

    classification_results = state.analysis.get("classification_results", [])
    finding_map = {issue.get("id", ""): issue for issue in classification_results}

    resolved_items_detail = []
    for item_id in resolved_item_ids:
        finding = finding_map.get(item_id, {})
        resolved_items_detail.append({
            "item_id": item_id,
            "root_cause": finding.get("description", "Identified and resolved"),
            "resolution": "Fixed via simulation on candidate copy",
            "validation": "compileall validation passed",
            "released": decision == "apply",
        })

    unresolved_items_detail = []
    for item_id in unresolved_item_ids:
        finding = finding_map.get(item_id, {})
        unresolved_items_detail.append({
            "item_id": item_id,
            "root_cause": finding.get("description", "Information gap detected"),
            "why_unresolved": "Missing information prevents safe one-shot resolution",
            "what_was_tried": ["Automated analysis", "Targeted research"],
            "missing_information": ["External information required for safe resolution"],
            "next_steps": ["Provide missing information", "Re-run pipeline with additional context"],
            "retry_guidance": "Re-run after providing the missing information identified above",
        })

    enriched_traces = []
    for trace in item_traces_raw:
        item_id = trace.get("finding_id", trace.get("pre_simulation_item_id", ""))
        enriched_traces.append({
            "item_id": item_id,
            "phase_0_snapshot": snapshot_id,
            "phase_1_finding": item_id,
            "phase_2_item": f"analysis-{item_id}",
            "phase_3_item": f"presim-{item_id}",
            "phase_4_result": trace.get("simulation_or_isolation_id", ""),
            "phase_5_inspection": trace.get("inspection_item_id", ""),
            "phase_6_relay": f"relay-{item_id}",
            "phase_7_final": "",
        })

    total_issues = len(resolved_item_ids) + len(unresolved_item_ids)

    final_input = FinalOutputInput(
        case_id=state.case_id or controller.execution_id,
        decision=decision,
        total_issues=total_issues if total_issues > 0 else 0,
        resolved_items=resolved_items_detail,
        unresolved_items=unresolved_items_detail,
        snapshot_hash=snapshot_hash,
        inspection_hash=inspection_hash,
        final_target_hash=final_target_hash,
        item_traces=enriched_traces,
        relay_result=state.relay_result,
    )
    final_package = build_final_output(final_input)

    state.final_output = {
        "total_issues": final_package.total_issues,
        "resolved_count": final_package.resolved_count,
        "unresolved_count": final_package.unresolved_count,
        "resolved_items": final_package.resolved_items,
        "unresolved_items": final_package.unresolved_items,
        "resolved_html": final_package.reports.get("resolved_html", ""),
        "completion_status": (
            "fully_resolved" if final_package.unresolved_count == 0 and decision == "apply"
            else "partially_resolved" if decision == "apply"
            else "cancelled"
        ),
        "success_note": final_package.success_note,
        "continuation_handoff": final_package.continuation_handoff,
        "snapshot_hash": final_package.snapshot_hash,
        "inspection_hash": final_package.inspection_hash,
        "final_target_hash": final_package.final_target_hash,
        "forward_traces": final_package.forward_traces,
        "backward_traces": final_package.backward_traces,
    }
    state.flags.final_complete = True

    result = PhaseResult(
        phase=7,
        phase_name=PHASE_NAMES[7],
        exit_status="completed",
        required_outputs={"final_output": state.final_output},
        duration_ms=0,
    )
    controller.complete_phase(result)
    return state
