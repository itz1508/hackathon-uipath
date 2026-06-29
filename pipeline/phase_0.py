# Modified: 2026-06-29T15:30:00Z
from __future__ import annotations
from datetime import datetime, timezone

from phase_models import PhaseResult, PHASE_NAMES
from phase_controller import PhaseController
from snapshot_utils import capture_snapshot


def transform_phase_0(state: "PipelineState", controller: PhaseController) -> "PipelineState":
    """Phase 0 pure transformation: Reads target_path. Writes snapshot, flags.

    Captures full state of original folder. Hash every file.
    """
    from pipeline_state import PipelineState

    controller.start_phase(0)

    snapshot = capture_snapshot(state.target_path)

    state.snapshot = {
        "snapshot_id": snapshot["snapshot_id"],
        "file_hashes": snapshot["file_hashes"],
        "total_files": snapshot["total_files"],
        "storage_path": snapshot["storage_path"],
        "target_path": snapshot["target_path"],
    }
    state.flags.snapshot_locked = True

    result = PhaseResult(
        phase=0,
        phase_name=PHASE_NAMES[0],
        exit_status="completed",
        required_outputs=state.snapshot,
        duration_ms=0,
    )
    controller.complete_phase(result)
    return state


def execute_phase_0_snapshot(
    controller: PhaseController, target_path: str
) -> PhaseResult:
    """Phase 0: Snapshot — auto-triggered on folder attach.

    Captures full state of original folder. Hash every file.
    Stores in two locations: user directory + temp copy.
    Snapshot is always available throughout the pipeline.
    """
    controller.start_phase(0)
    start = datetime.now(timezone.utc)

    snapshot = capture_snapshot(target_path)

    duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    result = PhaseResult(
        phase=0,
        phase_name=PHASE_NAMES[0],
        exit_status="completed",
        required_outputs={
            "snapshot_id": snapshot["snapshot_id"],
            "file_hashes": snapshot["file_hashes"],
            "total_files": snapshot["total_files"],
            "storage_path": snapshot["storage_path"],
            "target_path": snapshot["target_path"],
        },
        duration_ms=duration,
    )
    controller.complete_phase(result)
    return result
