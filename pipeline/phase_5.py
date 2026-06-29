# Modified: 2026-06-29T20:00:00Z
"""Phase 5: Inspection — convergence, validation, hashing.

Waits for ALL expected items before completing.
Validates that simulation + isolation branches have reported.
Computes inspection hash for integrity verification.
Builds complete item traces through all phases.

Reads: simulation_result + simulation_package.isolated_parts. Writes: inspection_result, flags.
This is a JOIN operator. Waits for both simulation and isolation.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from phase_models import PhaseResult, PHASE_NAMES
from phase_controller import PhaseController, PhaseViolation

if TYPE_CHECKING:
    from pipeline_state import PipelineState

logger = logging.getLogger(__name__)


def execute_phase_5_inspection(
    controller: PhaseController,
    snapshot: dict[str, Any],
    phase_3_outputs: dict[str, Any],
    phase_4_outputs: dict[str, Any],
) -> PhaseResult:
    """Phase 5: Inspection — real convergence using inspection.py.

    Uses inspection.py to:
    1. Validate that ALL expected items have reported (convergence)
    2. Check for missing items, duplicates, incomplete reports
    3. Compute inspection hash for integrity verification
    4. Build complete item traces through all phases

    Every path — simulation success, simulation failure, isolation —
    must have reported. No silent failures. No skipped reports.
    """
    from inspection import (
        InspectionInput,
        SimulationItemResult,
        IsolationItemResult,
        run_inspection,
    )

    controller.start_phase(5)
    start = datetime.now(timezone.utc)

    # CONVERGENCE WAIT: check that ALL branches have reported
    if not controller.check_inspection_convergence():
        controller.set_convergence_waiting()
        logger.warning("Inspection waiting for branch convergence...")
        if not controller.check_inspection_convergence():
            raise PhaseViolation(
                "Inspection cannot proceed: not all branches have reported",
                phase=5,
            )

    # Gather data from earlier phases
    ready_parts = phase_3_outputs.get("ready_parts", [])
    isolated_parts = phase_3_outputs.get("isolated_parts", [])
    simulation_result = phase_4_outputs.get("simulation_result", {})
    candidate_path = phase_4_outputs.get("candidate_path", "")
    snapshot_id = snapshot.get("snapshot_id", "")

    # Build expected item IDs (all items from Phase 3 — both ready and isolated)
    expected_item_ids = [p["item_id"] for p in ready_parts] + [p["item_id"] for p in isolated_parts]

    # Build SimulationItemResult objects from Phase 4 output
    sim_results: list[SimulationItemResult] = []
    resolved_items = simulation_result.get("resolved_items", [])
    failed_items = simulation_result.get("failed_items", [])

    for item_id in resolved_items:
        sim_results.append(SimulationItemResult(
            item_id=item_id,
            status="resolved",
            simulation_id=simulation_result.get("simulation_id", ""),
            source_finding_id=item_id,
            source_snapshot_id=snapshot_id,
        ))
    for item_id in failed_items:
        sim_results.append(SimulationItemResult(
            item_id=item_id,
            status="failed",
            simulation_id=simulation_result.get("simulation_id", ""),
            source_finding_id=item_id,
            source_snapshot_id=snapshot_id,
        ))

    # Build IsolationItemResult objects from Phase 3 isolated items
    iso_results: list[IsolationItemResult] = []
    for item in isolated_parts:
        item_id = item.get("item_id", "")
        iso_results.append(IsolationItemResult(
            item_id=item_id,
            status="information_required",
            isolation_id=f"iso-{item_id}",
            why_isolated=item.get("isolation_reason", "Information gap detected"),
            missing_information=[item.get("description", "Unknown information needed")],
            what_was_tried=["Automated analysis"],
            next_steps=["Provide missing information", "Manual investigation required"],
            source_finding_id=item_id,
            source_snapshot_id=snapshot_id,
        ))

    # Run real inspection
    inp = InspectionInput(
        case_id=controller.execution_id,
        snapshot_id=snapshot_id,
        expected_item_ids=expected_item_ids,
        simulation_results=sim_results,
        isolation_results=iso_results,
        candidate_path=candidate_path,
    )
    inspection_result = run_inspection(inp)

    # Build convergence status with full inspection data
    convergence_status = {
        "all_converged": controller.check_inspection_convergence(),
        "branch_status": controller.get_branch_status().model_dump(),
        "inspection_id": inspection_result.inspection_id,
        "inspection_hash": inspection_result.inspection_hash,
        "inspection_complete": inspection_result.inspection_complete,
        "resolved_items": inspection_result.resolved_items,
        "unresolved_items": inspection_result.unresolved_items,
        "candidate_hash": inspection_result.candidate_hash,
        "item_traces": [
            {
                "inspection_item_id": t.inspection_item_id,
                "simulation_or_isolation_id": t.simulation_or_isolation_id,
                "pre_simulation_item_id": t.pre_simulation_item_id,
                "finding_id": t.finding_id,
                "snapshot_id": t.snapshot_id,
                "status": t.status,
            }
            for t in inspection_result.item_traces
        ],
        "errors": [
            {"code": e.code, "message": e.message, "item_id": e.item_id}
            for e in inspection_result.errors
        ],
    }

    duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    result = PhaseResult(
        phase=5,
        phase_name=PHASE_NAMES[5],
        exit_status="completed",
        required_outputs={"convergence_status": convergence_status},
        duration_ms=duration,
    )
    controller.complete_phase(result)
    return result


# ──────────────────────────────────────────────
# State Algebra Transform
# ──────────────────────────────────────────────


def transform_phase_5(state: "PipelineState", controller: PhaseController) -> "PipelineState":
    """Phase 5 pure transformation: Reads simulation_result + simulation_package.isolated_parts.
    Writes inspection_result, flags.

    This is a JOIN operator. Waits for both simulation and isolation.
    """
    from inspection import (
        InspectionInput,
        SimulationItemResult,
        IsolationItemResult,
        run_inspection,
    )
    from pipeline_state import PipelineState

    state.validate_transition(5)
    controller.start_phase(5)

    if not controller.check_inspection_convergence():
        controller.set_convergence_waiting()
        if not controller.check_inspection_convergence():
            raise PhaseViolation(
                "Inspection cannot proceed: not all branches have reported",
                phase=5,
            )

    ready_parts = state.simulation_package.get("ready_parts", [])
    isolated_parts = state.simulation_package.get("isolated_parts", [])
    simulation_result = state.simulation_result
    candidate_path = simulation_result.get("candidate_path", "")
    snapshot_id = state.snapshot.get("snapshot_id", "")

    expected_item_ids = [p["item_id"] for p in ready_parts] + [p["item_id"] for p in isolated_parts]

    sim_results: list[SimulationItemResult] = []
    resolved_items = simulation_result.get("resolved_items", [])
    failed_items = simulation_result.get("failed_items", [])

    for item_id in resolved_items:
        sim_results.append(SimulationItemResult(
            item_id=item_id,
            status="resolved",
            simulation_id=simulation_result.get("simulation_id", ""),
            source_finding_id=item_id,
            source_snapshot_id=snapshot_id,
        ))
    for item_id in failed_items:
        sim_results.append(SimulationItemResult(
            item_id=item_id,
            status="failed",
            simulation_id=simulation_result.get("simulation_id", ""),
            source_finding_id=item_id,
            source_snapshot_id=snapshot_id,
        ))

    iso_results: list[IsolationItemResult] = []
    for item in isolated_parts:
        item_id = item.get("item_id", "")
        iso_results.append(IsolationItemResult(
            item_id=item_id,
            status="information_required",
            isolation_id=f"iso-{item_id}",
            why_isolated=item.get("isolation_reason", "Information gap detected"),
            missing_information=[item.get("description", "Unknown information needed")],
            what_was_tried=["Automated analysis"],
            next_steps=["Provide missing information", "Manual investigation required"],
            source_finding_id=item_id,
            source_snapshot_id=snapshot_id,
        ))

    inp = InspectionInput(
        case_id=controller.execution_id,
        snapshot_id=snapshot_id,
        expected_item_ids=expected_item_ids,
        simulation_results=sim_results,
        isolation_results=iso_results,
        candidate_path=candidate_path,
    )
    inspection_output = run_inspection(inp)

    convergence_status = {
        "all_converged": controller.check_inspection_convergence(),
        "branch_status": controller.get_branch_status().model_dump(),
        "inspection_id": inspection_output.inspection_id,
        "inspection_hash": inspection_output.inspection_hash,
        "inspection_complete": inspection_output.inspection_complete,
        "resolved_items": inspection_output.resolved_items,
        "unresolved_items": inspection_output.unresolved_items,
        "candidate_hash": inspection_output.candidate_hash,
        "item_traces": [
            {
                "inspection_item_id": t.inspection_item_id,
                "simulation_or_isolation_id": t.simulation_or_isolation_id,
                "pre_simulation_item_id": t.pre_simulation_item_id,
                "finding_id": t.finding_id,
                "snapshot_id": t.snapshot_id,
                "status": t.status,
            }
            for t in inspection_output.item_traces
        ],
        "errors": [
            {"code": e.code, "message": e.message, "item_id": e.item_id}
            for e in inspection_output.errors
        ],
    }

    state.inspection_result = convergence_status
    state.flags.inspection_complete = True

    result = PhaseResult(
        phase=5,
        phase_name=PHASE_NAMES[5],
        exit_status="completed",
        required_outputs={"convergence_status": convergence_status},
        duration_ms=0,
    )
    controller.complete_phase(result)
    return state
