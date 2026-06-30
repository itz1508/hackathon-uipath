"""Phase controller — enforces strict phase ordering via named transition table.

Contains PhaseViolation exception and PhaseController state machine.
Uses TRANSITIONS dict for phase ordering — NO arithmetic progression.
Tracks current phase by name, not index.

Backward compatible: start_phase(int) maps integer to name via PHASE_NAMES.

Dependencies: stdlib (logging, typing) + phase_models + pipeline_state only.
No side effects on import.
"""
import logging
from typing import Any

from phase_models import (
    PHASE_NAMES,
    PHASE_ORDER,
    REQUIRED_OUTPUTS,
    VALID_EXIT_STATUSES,
    BranchStatus,
    PhaseResult,
    PhaseStatus,
)
from pipeline_state import TRANSITIONS

logger = logging.getLogger(__name__)


class PhaseViolation(Exception):
    """Raised when a phase-lock or exit-validation rule is violated."""

    def __init__(self, message: str, phase: int | None = None) -> None:
        self.phase = phase
        super().__init__(message)


class PhaseController:
    """Embedded phase controller enforcing strict phase ordering.

    Uses named-phase transition table (TRANSITIONS) instead of index arithmetic.
    The controller owns all routing. Phase N is inaccessible until Phase N-1
    completes with a valid exit status and all required outputs present.
    Controller-authorized concurrent branches (simulation + isolation) are
    permitted. Phase 5 (Inspection) is the convergence point.
    """

    def __init__(self, execution_id: str) -> None:
        self.execution_id = execution_id
        self._current_phase: str | None = None
        self._phase_statuses: dict[int, PhaseStatus] = {
            p: PhaseStatus.PENDING for p in PHASE_ORDER
        }
        self._phase_exits: dict[int, PhaseResult] = {}
        self._violations: list[dict[str, Any]] = []

        # Branch tracking
        self._authorized_simulation_parts: list[str] = []
        self._authorized_isolation_items: list[str] = []
        self._pending_branch_outcomes: dict[str, str] = {}
        self._inspection_convergence_status: str = "pending"

    def get_current_phase(self) -> int | None:
        """Return current phase as integer for backward compatibility."""
        if self._current_phase is None:
            return None
        # Reverse lookup: name -> int
        for num, name in PHASE_NAMES.items():
            if name == self._current_phase:
                return num
        return None

    def start_phase(self, phase: int) -> None:
        """Start the next phase in sequence. Enforces phase-lock ordering.

        Accepts integer phase number for backward compatibility.
        Internally validates using named transition table.
        """
        # Validate phase number exists
        if phase not in PHASE_NAMES:
            raise PhaseViolation(
                f"Phase lock: phase {phase} does not exist in PHASE_NAMES",
                phase=phase,
            )

        requested_name = PHASE_NAMES[phase]

        # Determine expected next phase from transition table
        if self._current_phase is None:
            # Pipeline hasn't started — only "snapshot" (phase 0) is valid
            expected_next = "snapshot"
        else:
            expected_next = TRANSITIONS.get(self._current_phase)

        # Terminal check: if current phase has no successor, pipeline is done
        if expected_next is None:
            raise PhaseViolation(
                "Pipeline has completed all phases", phase=phase
            )

        # Enforce ordering: requested phase must match the next allowed phase
        if requested_name != expected_next:
            raise PhaseViolation(
                f"Phase lock: cannot start phase {phase} ({requested_name}), "
                f"expected '{expected_next}'",
                phase=phase,
            )

        # Validate previous phase exit (skip for first phase)
        if self._current_phase is not None:
            prev_num = self.get_current_phase()
            if prev_num is not None and self._phase_statuses.get(prev_num) != PhaseStatus.COMPLETED:
                raise PhaseViolation(
                    f"Phase {prev_num} ({self._current_phase}) has not completed. "
                    f"Cannot start phase {phase}.",
                    phase=phase,
                )

        self._current_phase = requested_name
        self._phase_statuses[phase] = PhaseStatus.RUNNING
        logger.info(f"Phase {phase} ({requested_name}) started")

    def complete_phase(self, phase_result: PhaseResult) -> None:
        """Complete the current phase with validated exit."""
        current_num = self.get_current_phase()
        if current_num is None or phase_result.phase != current_num:
            raise PhaseViolation(
                f"Cannot complete phase {phase_result.phase}: current is {current_num}",
                phase=phase_result.phase,
            )

        if phase_result.exit_status not in VALID_EXIT_STATUSES:
            self._phase_statuses[current_num] = PhaseStatus.FAILED
            raise PhaseViolation(
                f"Invalid exit status '{phase_result.exit_status}' for phase {current_num}",
                phase=current_num,
            )

        # Validate required outputs
        required = REQUIRED_OUTPUTS.get(current_num, [])
        missing = [k for k in required if k not in phase_result.required_outputs
                   or phase_result.required_outputs[k] is None]
        if missing:
            self._phase_statuses[current_num] = PhaseStatus.FAILED
            raise PhaseViolation(
                f"Phase {current_num} missing required outputs: {missing}",
                phase=current_num,
            )

        self._phase_exits[current_num] = phase_result
        self._phase_statuses[current_num] = PhaseStatus.COMPLETED
        logger.info(f"Phase {current_num} ({self._current_phase}) completed")

    def set_awaiting_approval(self, phase: int) -> None:
        """Set phase to awaiting user approval (Phase 6 Relay)."""
        if self._phase_statuses.get(phase) != PhaseStatus.RUNNING:
            raise PhaseViolation(
                f"Phase {phase} must be RUNNING to await approval", phase=phase
            )
        self._phase_statuses[phase] = PhaseStatus.AWAITING_USER_APPROVAL

    def resume_from_approval(self, phase: int) -> None:
        """Resume from awaiting approval back to running."""
        if self._phase_statuses.get(phase) != PhaseStatus.AWAITING_USER_APPROVAL:
            raise PhaseViolation(
                f"Phase {phase} is not awaiting approval", phase=phase
            )
        self._phase_statuses[phase] = PhaseStatus.RUNNING

    def authorize_simulation_branch(self, item_ids: list[str]) -> None:
        """Register items authorized to proceed to simulation."""
        self._authorized_simulation_parts.extend(item_ids)
        logger.info(f"Authorized {len(item_ids)} items for simulation branch")

    def authorize_isolation_branch(self, item_ids: list[str]) -> None:
        """Register items routed to targeted research (concurrent)."""
        self._authorized_isolation_items.extend(item_ids)
        logger.info(f"Authorized {len(item_ids)} items for isolation branch")

    def set_convergence_waiting(self) -> None:
        """Mark inspection convergence as waiting for branch reports."""
        self._inspection_convergence_status = "waiting"

    def report_branch_outcome(self, branch_id: str, status: str) -> None:
        """Record that a controller-authorized branch has reported."""
        self._pending_branch_outcomes[branch_id] = status
        if self.check_inspection_convergence():
            self._inspection_convergence_status = "converged"

    def check_inspection_convergence(self) -> bool:
        """Return True if ALL authorized branches have reported outcomes.

        Convergence requires:
        - All simulation results (success or failure fix)
        - All isolation outcomes (resolved or information_unavailable)
        """
        all_branch_ids: set[str] = set()
        for item_id in self._authorized_simulation_parts:
            all_branch_ids.add(f"simulation:{item_id}")
        for item_id in self._authorized_isolation_items:
            all_branch_ids.add(f"isolation:{item_id}")

        if not all_branch_ids:
            return True  # No branches — trivially converged

        reported = set(self._pending_branch_outcomes.keys())
        return all_branch_ids.issubset(reported)

    def get_branch_status(self) -> BranchStatus:
        """Return current state of all authorized branches."""
        return BranchStatus(
            simulation_parts=list(self._authorized_simulation_parts),
            isolation_items=list(self._authorized_isolation_items),
            branch_outcomes=dict(self._pending_branch_outcomes),
            convergence_status=self._inspection_convergence_status,
            all_converged=self.check_inspection_convergence(),
        )

    def is_pipeline_complete(self) -> bool:
        return all(s == PhaseStatus.COMPLETED for s in self._phase_statuses.values())

    def is_pipeline_failed(self) -> bool:
        return any(s == PhaseStatus.FAILED for s in self._phase_statuses.values())
