# Modified: 2026-06-29T20:00:00Z
"""Pipeline orchestration — sequences all phase executors, handles
mode routing (manual vs auto), and wraps errors in WorkflowOutput.

Phase structure:
  0 — Snapshot
  1 — Scan (raw tool output only)
  2 — Analysis (LLM statement, Handoff statement, Classification)
  3 — Pre-simulation (scoring, 93.91% gate, item-level routing)
  4 — Simulation (mutation on candidate copy)
  5 — Inspection (convergence, validation, hashing)
  6 — Relay (hash verify, before/after diff, Apply/Cancel decision)
  7 — Final Output (resolved.html, root causes, handoff report)

State Algebra: S |> P0 |> P1 |> P2 |> P3 |> P4 |> P5 |> P6 |> P7
Each phase reads from state, writes ONLY to its own field.
Controller enforces phase ordering. State holds all data.
"""

import logging
import uuid
from pathlib import Path
from phase_models import (
    WorkflowInput, WorkflowOutput, PhaseResult,
    PipelineStatus, DecisionAction, PHASE_NAMES, REQUIRED_OUTPUTS,
    ActionCenterFallback, BranchStatus,
)
from phase_controller import PhaseController, PhaseViolation
from pipeline_state import PipelineState, Flags
from phase_0 import execute_phase_0_snapshot, transform_phase_0
from phase_1 import execute_phase_1_scan, transform_phase_1
from phase_2 import execute_phase_2_analysis, transform_phase_2
from phase_3 import execute_phase_3_presimulation, transform_phase_3
from phase_4 import execute_phase_4_simulation, transform_phase_4
from phase_5 import execute_phase_5_inspection, transform_phase_5
from phase_6 import (
    execute_phase_6_relay,
    execute_phase_6_relay_auto,
    resume_phase_6_with_decision,
    transform_phase_6,
)
from phase_7 import execute_phase_7_final_output, transform_phase_7

logger = logging.getLogger(__name__)


def run_pipeline(input: WorkflowInput) -> WorkflowOutput:
    """Execute the full Phase 0–7 pipeline.

    Orchestrates all phases sequentially with the Phase Controller
    enforcing strict ordering and phase-lock semantics.

    Internally threads PipelineState through each phase:
      S |> P0 |> P1 |> P2 |> P3 |> P4 |> P5 |> P6 |> P7

    Pauses at Phase 6 (Relay) for operator decision in manual mode.
    """
    execution_id = str(uuid.uuid4())
    controller = PhaseController(execution_id)
    phase_results: list[PhaseResult] = []

    # ── Initialize PipelineState ──
    state = PipelineState(
        case_id=input.case_id,
        execution_id=execution_id,
        target_path=input.target_path,
        mode=input.mode,
        decision="apply" if input.mode == "auto" else input.decision,
    )

    # ── Execution Trace (self-documenting proof-of-work) ──
    from execution_trace import ExecutionTracer, trace_phase_result
    tracer = ExecutionTracer(case_id=input.case_id, execution_id=execution_id)

    try:
        # ── Phase 0: Snapshot (auto-triggered on folder attach) ──
        tracer.before(phase=0, intent="Capture SHA-256 snapshot of target folder for restore point")
        p0_result = execute_phase_0_snapshot(controller, input.target_path)
        phase_results.append(p0_result)
        trace_phase_result(tracer, 0, p0_result)
        snapshot = p0_result.required_outputs

        # ── Phase 1: Scan (raw tool output only) ──
        tracer.before(phase=1, intent="Scan target folder: detect code issues via compileall, AST, dependency analysis")
        p1_result = execute_phase_1_scan(controller, snapshot)
        phase_results.append(p1_result)
        trace_phase_result(tracer, 1, p1_result)

        # ── Phase 2: Analysis (LLM statement, Handoff statement, Classification) ──
        tracer.before(phase=2, intent="Analyze raw scan results: produce statements and classification")
        p2_result = execute_phase_2_analysis(
            controller, snapshot, p1_result.required_outputs
        )
        phase_results.append(p2_result)
        trace_phase_result(tracer, 2, p2_result)

        # ── Phase 3: Pre-simulation (scoring + partitioning) ──
        tracer.before(phase=3, intent="Score information completeness against 93.91% threshold, partition into ready/isolated")
        # Isolation is always enabled per product decision — ignore incoming toggle
        snapshot["isolation_enabled"] = True
        p3_result = execute_phase_3_presimulation(
            controller, snapshot, p2_result.required_outputs
        )
        phase_results.append(p3_result)
        trace_phase_result(tracer, 3, p3_result)

        # ── Phase 4: Simulation (mutation on candidate copy) ──
        tracer.before(phase=4, intent="Execute fixes on candidate copy only — never touch real target")
        p4_result = execute_phase_4_simulation(
            controller, snapshot, p2_result.required_outputs, p3_result.required_outputs
        )
        phase_results.append(p4_result)
        trace_phase_result(tracer, 4, p4_result)

        # ── Phase 5: Inspection (convergence wait) ──
        tracer.before(phase=5, intent="Wait for all branches to converge, validate results, compute hashes")
        p5_result = execute_phase_5_inspection(
            controller, snapshot, p3_result.required_outputs, p4_result.required_outputs
        )
        phase_results.append(p5_result)
        trace_phase_result(tracer, 5, p5_result)

        # ── Phase 6: Relay ──
        if input.mode == "auto":
            tracer.before(phase=6, intent="Auto-mode: apply decision immediately without human pause")
            # Auto mode: use relay.py with immediate apply decision
            p6_result = execute_phase_6_relay_auto(
                controller, snapshot, p4_result.required_outputs,
                p5_result.required_outputs, "apply"
            )
            phase_results.append(p6_result)
            trace_phase_result(tracer, 6, p6_result)

            # ── Phase 7: Final Output ──
            tracer.before(phase=7, intent="Produce final report: resolved items, root causes, documentation")
            p7_result = execute_phase_7_final_output(
                controller, phase_results, "apply"
            )
            phase_results.append(p7_result)
            trace_phase_result(tracer, 7, p7_result)

            # Save execution trace as proof-of-work
            try:
                trace_path = tracer.save()
                logger.info(f"Execution trace saved: {trace_path}")
            except Exception:
                pass  # Trace save failure must not block pipeline

            return WorkflowOutput(
                case_id=input.case_id,
                execution_id=execution_id,
                pipeline_status=PipelineStatus.SUCCEEDED,
                current_phase=7,
                current_phase_name=PHASE_NAMES[7],
                phase_results=phase_results,
                branch_status=controller.get_branch_status(),
                snapshot_id=snapshot.get("snapshot_id", ""),
                decision_required=False,
                final_output=p7_result.required_outputs.get("final_output", {}),
                message="Pipeline completed end-to-end in auto mode. Result applied.",
            )

        # Manual mode: pause at Relay for operator decision
        tracer.before(phase=6, intent="Manual mode: present diff and pause for human Apply/Cancel decision")
        p6_result = execute_phase_6_relay(
            controller, snapshot, p5_result.required_outputs,
            input.backend_base_url, execution_id
        )
        phase_results.append(p6_result)
        trace_phase_result(tracer, 6, p6_result)

        # Save trace before pausing
        try:
            tracer.save()
        except Exception:
            pass

        # Pipeline pauses here — awaiting operator decision
        decision_endpoint = p6_result.required_outputs.get("decision_endpoint", "")
        action_center_ctx = p6_result.required_outputs.get(
            "action_center_fallback", {}
        )

        return WorkflowOutput(
            case_id=input.case_id,
            execution_id=execution_id,
            pipeline_status=PipelineStatus.AWAITING_DECISION,
            current_phase=6,
            current_phase_name=PHASE_NAMES[6],
            phase_results=phase_results,
            branch_status=controller.get_branch_status(),
            snapshot_id=snapshot.get("snapshot_id", ""),
            decision_required=True,
            decision_endpoint=decision_endpoint,
            action_center_fallback=ActionCenterFallback(
                enabled=True,
                schema_path="action-center/action-schema.json",
                task_title="Pipeline Relay Decision - Apply or Cancel",
                context=action_center_ctx,
            ),
            message="Pipeline paused at Relay. Awaiting operator decision (Apply/Cancel).",
        )

    except PhaseViolation as exc:
        logger.error(f"Pipeline failed: {exc}")
        return WorkflowOutput(
            case_id=input.case_id,
            execution_id=execution_id,
            pipeline_status=PipelineStatus.FAILED,
            current_phase=exc.phase or -1,
            current_phase_name=PHASE_NAMES.get(exc.phase or -1, "Unknown"),
            phase_results=phase_results,
            error={"code": "PHASE_VIOLATION", "message": str(exc), "phase": exc.phase},
            message=f"Pipeline failed at phase {exc.phase}: {exc}",
        )
    except Exception as exc:
        logger.error(f"Unexpected pipeline error: {exc}")
        return WorkflowOutput(
            case_id=input.case_id,
            execution_id=execution_id,
            pipeline_status=PipelineStatus.FAILED,
            phase_results=phase_results,
            error={"code": "UNEXPECTED_ERROR", "message": str(exc)},
            message=f"Unexpected error: {exc}",
        )


def resume_with_decision(input: WorkflowInput) -> WorkflowOutput:
    """Resume pipeline from Phase 6 with operator decision.

    Called when the operator makes a decision (Apply or Cancel) via
    the decision endpoint or Action Center.

    Apply  = Release simulation-proven result to real target folder.
    Cancel = Restore from snapshot — original files, no trace.
    """
    execution_id = input.execution_id or str(uuid.uuid4())

    if not input.decision:
        return WorkflowOutput(
            case_id=input.case_id,
            execution_id=execution_id,
            pipeline_status=PipelineStatus.FAILED,
            error={"code": "MISSING_DECISION", "message": "No decision provided"},
            message="Resume requires a decision (apply or cancel).",
        )

    # In production, we'd reload the controller state from persistence
    # For the workflow definition, we create a new controller at Phase 6
    controller = PhaseController(execution_id)

    # Fast-forward controller to Phase 6 awaiting state
    # (In production, this state is loaded from the execution store)
    for phase in range(6):
        controller.start_phase(phase)
        controller.complete_phase(PhaseResult(
            phase=phase,
            phase_name=PHASE_NAMES[phase],
            exit_status="completed",
            required_outputs={k: f"<persisted_{k}>" for k in REQUIRED_OUTPUTS[phase]},
        ))
    controller.start_phase(6)
    controller.set_awaiting_approval(6)

    # Reconstruct snapshot reference for restore capability
    snapshot = {
        "snapshot_id": f"persisted_{execution_id}",
        "storage_path": str(Path(input.target_path).parent / f".edge_snapshot_persisted_{execution_id}"),
        "file_hashes": {},
    }

    phase_results: list[PhaseResult] = []

    try:
        # Resume Phase 6 with decision
        p6_result = resume_phase_6_with_decision(
            controller, input.decision, snapshot, input.target_path
        )
        phase_results.append(p6_result)

        # Determine pipeline status based on decision
        if input.decision == DecisionAction.CANCEL:
            return WorkflowOutput(
                case_id=input.case_id,
                execution_id=execution_id,
                pipeline_status=PipelineStatus.CANCELLED,
                current_phase=6,
                current_phase_name=PHASE_NAMES[6],
                phase_results=phase_results,
                snapshot_id=snapshot["snapshot_id"],
                message="Cancelled. Restored from snapshot. Original files intact.",
            )

        # Phase 7: Final Output (Apply path)
        p7_result = execute_phase_7_final_output(
            controller, phase_results, input.decision
        )
        phase_results.append(p7_result)

        return WorkflowOutput(
            case_id=input.case_id,
            execution_id=execution_id,
            pipeline_status=PipelineStatus.SUCCEEDED,
            current_phase=7,
            current_phase_name=PHASE_NAMES[7],
            phase_results=phase_results,
            branch_status=controller.get_branch_status(),
            snapshot_id=snapshot["snapshot_id"],
            final_output=p7_result.required_outputs.get("final_output", {}),
            message="Pipeline completed successfully. Result applied.",
        )

    except PhaseViolation as exc:
        return WorkflowOutput(
            case_id=input.case_id,
            execution_id=execution_id,
            pipeline_status=PipelineStatus.FAILED,
            current_phase=exc.phase or 6,
            phase_results=phase_results,
            error={"code": "PHASE_VIOLATION", "message": str(exc)},
            message=f"Resume failed: {exc}",
        )


# ──────────────────────────────────────────────
# State Algebra Runner (pure S |> P0 |> ... |> P7)
# ──────────────────────────────────────────────


def run_pipeline_stateful(input: WorkflowInput) -> tuple[PipelineState, WorkflowOutput]:
    """Execute the full pipeline using pure state algebra.

    S |> P0 |> P1 |> P2 |> P3 |> P4 |> P5 |> P6 |> P7

    Each phase is a pure transformation: state -> state.
    Controller enforces ordering. State holds all data.

    Returns both the final PipelineState and a WorkflowOutput for compatibility.
    """
    execution_id = str(uuid.uuid4())
    controller = PhaseController(execution_id)

    # Initialize state
    state = PipelineState(
        case_id=input.case_id,
        execution_id=execution_id,
        target_path=input.target_path,
        mode=input.mode,
        decision="apply" if input.mode == "auto" else input.decision,
        isolation_enabled=True,
    )

    try:
        # S |> P0 |> P1 |> P2 |> P3 |> P4 |> P5 |> P6 |> P7
        state = transform_phase_0(state, controller)
        state = transform_phase_1(state, controller)
        state = transform_phase_2(state, controller)
        state = transform_phase_3(state, controller)
        state = transform_phase_4(state, controller)
        state = transform_phase_5(state, controller)
        state = transform_phase_6(state, controller)
        state = transform_phase_7(state, controller)

        output = WorkflowOutput(
            case_id=input.case_id,
            execution_id=execution_id,
            pipeline_status=PipelineStatus.SUCCEEDED,
            current_phase=7,
            current_phase_name=PHASE_NAMES[7],
            phase_results=[],
            branch_status=controller.get_branch_status(),
            snapshot_id=state.snapshot.get("snapshot_id", ""),
            decision_required=False,
            final_output=state.final_output,
            message="Pipeline completed via state algebra. All phases transformed successfully.",
        )
        return state, output

    except PhaseViolation as exc:
        logger.error(f"State algebra pipeline failed: {exc}")
        output = WorkflowOutput(
            case_id=input.case_id,
            execution_id=execution_id,
            pipeline_status=PipelineStatus.FAILED,
            current_phase=exc.phase or -1,
            current_phase_name=PHASE_NAMES.get(exc.phase or -1, "Unknown"),
            error={"code": "PHASE_VIOLATION", "message": str(exc), "phase": exc.phase},
            message=f"State algebra pipeline failed at phase {exc.phase}: {exc}",
        )
        return state, output

    except ValueError as exc:
        logger.error(f"State transition validation failed: {exc}")
        output = WorkflowOutput(
            case_id=input.case_id,
            execution_id=execution_id,
            pipeline_status=PipelineStatus.FAILED,
            error={"code": "STATE_TRANSITION_VIOLATION", "message": str(exc)},
            message=f"State transition validation failed: {exc}",
        )
        return state, output

    except Exception as exc:
        logger.error(f"Unexpected error in state algebra pipeline: {exc}")
        output = WorkflowOutput(
            case_id=input.case_id,
            execution_id=execution_id,
            pipeline_status=PipelineStatus.FAILED,
            error={"code": "UNEXPECTED_ERROR", "message": str(exc)},
            message=f"Unexpected error: {exc}",
        )
        return state, output
