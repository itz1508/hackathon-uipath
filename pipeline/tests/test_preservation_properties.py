# Modified: 2025-06-29T12:00:00Z
"""Preservation property tests — capture baseline behavior that must NOT change after bugfix.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8**

These tests run on the UNFIXED code and are expected to PASS.
They verify behaviors that should remain unchanged after the bugfix:
- Phase-lock ordering enforcement
- Constants (PHASE_ORDER, VALID_EXIT_STATUSES, PASS_THRESHOLD)
- Auto-mode Phase 5 completion
- Resume-from-decision flow
"""
import sys
import os
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, assume, settings
from hypothesis import strategies as st

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phase_models import (
    PHASE_ORDER,
    VALID_EXIT_STATUSES,
    PASS_THRESHOLD,
    PHASE_NAMES,
    PhaseResult,
    DecisionAction,
)
from phase_controller import PhaseController, PhaseViolation


# ──────────────────────────────────────────────
# Strategy definitions
# ──────────────────────────────────────────────

# Valid phase indices 0-6
valid_phases = st.sampled_from(PHASE_ORDER)

# Random out-of-order phase attempts: skip at least one phase
out_of_order_attempts = st.tuples(
    st.integers(min_value=0, max_value=6),  # phase to attempt
    st.integers(min_value=0, max_value=5),  # how many phases to complete first
).filter(lambda t: t[0] != t[1] + 1)  # ensure it's actually out of order (not the next expected)

# Valid decision values for resume flow
valid_decisions = st.sampled_from(["apply", "cancel"])

# Execution IDs for PhaseController
execution_ids = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=20,
)


# ──────────────────────────────────────────────
# Property: Constants remain unchanged
# **Validates: Requirements 3.1, 3.2**
# ──────────────────────────────────────────────


def test_phase_order_is_0_through_6():
    """PHASE_ORDER must be exactly [0, 1, 2, 3, 4, 5, 6]."""
    assert PHASE_ORDER == [0, 1, 2, 3, 4, 5, 6]


def test_valid_exit_statuses_are_completed_and_isolated():
    """VALID_EXIT_STATUSES must be exactly {"completed", "isolated"}."""
    assert VALID_EXIT_STATUSES == {"completed", "isolated"}


def test_pass_threshold_is_9391():
    """PASS_THRESHOLD must be exactly 9391 (93.91%)."""
    assert PASS_THRESHOLD == 9391


# ──────────────────────────────────────────────
# Property: PhaseController allows sequential progression (0-6)
# **Validates: Requirements 3.1**
# ──────────────────────────────────────────────


@given(exec_id=execution_ids)
@settings(max_examples=50)
def test_sequential_phase_progression_allowed(exec_id):
    """For all valid execution IDs, PhaseController allows sequential phases 0-6.

    **Validates: Requirements 3.1**
    """
    controller = PhaseController(execution_id=exec_id)

    for phase in PHASE_ORDER:
        # start_phase should not raise for sequential progression
        controller.start_phase(phase)

        # Complete phase with valid result
        result = PhaseResult(
            phase=phase,
            phase_name=PHASE_NAMES[phase],
            exit_status="completed",
            required_outputs={k: f"value_{k}" for k in (
                ["snapshot_id", "file_hashes"] if phase == 0 else
                ["pre_calibration_statement", "handoff_statement", "llm_statement"] if phase == 1 else
                ["package_confidence_score", "simulation_ready", "ready_parts", "isolated_parts"] if phase == 2 else
                ["simulation_result"] if phase == 3 else
                ["convergence_status"] if phase == 4 else
                ["decision"] if phase == 5 else
                ["final_output"] if phase == 6 else
                []
            )},
        )
        controller.complete_phase(result)

    # After completing all phases, pipeline is complete
    assert controller.is_pipeline_complete()


# ──────────────────────────────────────────────
# Property: PhaseController rejects out-of-order phase attempts
# **Validates: Requirements 3.1**
# ──────────────────────────────────────────────


@given(data=st.data(), exec_id=execution_ids)
@settings(max_examples=50)
def test_out_of_order_phase_raises_violation(data, exec_id):
    """For all random out-of-order phase attempts, PhaseController raises PhaseViolation.

    **Validates: Requirements 3.1**
    """
    controller = PhaseController(execution_id=exec_id)

    # Complete some number of phases sequentially (0 to N)
    phases_to_complete = data.draw(st.integers(min_value=0, max_value=5))

    for i in range(phases_to_complete):
        phase = PHASE_ORDER[i]
        controller.start_phase(phase)
        result = PhaseResult(
            phase=phase,
            phase_name=PHASE_NAMES[phase],
            exit_status="completed",
            required_outputs={k: f"value_{k}" for k in (
                ["snapshot_id", "file_hashes"] if phase == 0 else
                ["pre_calibration_statement", "handoff_statement", "llm_statement"] if phase == 1 else
                ["package_confidence_score", "simulation_ready", "ready_parts", "isolated_parts"] if phase == 2 else
                ["simulation_result"] if phase == 3 else
                ["convergence_status"] if phase == 4 else
                ["decision"] if phase == 5 else
                ["final_output"] if phase == 6 else
                []
            )},
        )
        controller.complete_phase(result)

    # Now attempt a phase that is NOT the next expected one
    next_expected = PHASE_ORDER[phases_to_complete]  # The next valid phase
    wrong_phase = data.draw(
        st.sampled_from([p for p in PHASE_ORDER if p != next_expected])
    )

    with pytest.raises(PhaseViolation):
        controller.start_phase(wrong_phase)


# ──────────────────────────────────────────────
# Property: resume_phase_5_with_decision produces valid outcomes
# **Validates: Requirements 3.6, 3.8**
# ──────────────────────────────────────────────


@given(decision=valid_decisions, exec_id=execution_ids)
@settings(max_examples=30)
def test_resume_phase_5_produces_valid_outcome(decision, exec_id):
    """For all valid decision values, resume_phase_5_with_decision produces valid outcomes.

    **Validates: Requirements 3.6, 3.8**
    """
    controller = PhaseController(execution_id=exec_id)

    # Progress controller to phase 5 awaiting approval
    for i in range(5):
        phase = PHASE_ORDER[i]
        controller.start_phase(phase)
        result = PhaseResult(
            phase=phase,
            phase_name=PHASE_NAMES[phase],
            exit_status="completed",
            required_outputs={k: f"value_{k}" for k in (
                ["snapshot_id", "file_hashes"] if phase == 0 else
                ["pre_calibration_statement", "handoff_statement", "llm_statement"] if phase == 1 else
                ["package_confidence_score", "simulation_ready", "ready_parts", "isolated_parts"] if phase == 2 else
                ["simulation_result"] if phase == 3 else
                ["convergence_status"] if phase == 4 else
                []
            )},
        )
        controller.complete_phase(result)

    # Start phase 5 and set to awaiting approval
    controller.start_phase(5)
    controller.set_awaiting_approval(5)

    # Mock snapshot_utils.restore_from_snapshot since it does filesystem operations
    with patch("phase_5.restore_from_snapshot", return_value=True):
        from phase_5 import resume_phase_5_with_decision

        snapshot = {"snapshot_id": "test-snap", "storage_path": "/tmp/test", "target_path": "/tmp/target"}
        target_path = "/tmp/target"

        result = resume_phase_5_with_decision(
            controller=controller,
            decision=decision,
            snapshot=snapshot,
            target_path=target_path,
        )

    # Verify the result is valid
    assert result.phase == 5
    assert result.phase_name == PHASE_NAMES[5]
    assert result.exit_status == "completed"
    assert result.required_outputs["decision"] is not None
    assert result.required_outputs["decision"]["action"] == decision


# ──────────────────────────────────────────────
# Property: Phase 5 auto mode completes with valid exit_status
# **Validates: Requirements 3.6**
# ──────────────────────────────────────────────


@given(decision=valid_decisions, exec_id=execution_ids)
@settings(max_examples=30)
def test_phase_5_auto_mode_completes_with_valid_status(decision, exec_id):
    """For all auto-mode executions, Phase 5 completes with exit_status='completed' and non-None decision.

    **Validates: Requirements 3.6**
    """
    controller = PhaseController(execution_id=exec_id)

    # Progress controller to phase 5
    for i in range(5):
        phase = PHASE_ORDER[i]
        controller.start_phase(phase)
        result = PhaseResult(
            phase=phase,
            phase_name=PHASE_NAMES[phase],
            exit_status="completed",
            required_outputs={k: f"value_{k}" for k in (
                ["snapshot_id", "file_hashes"] if phase == 0 else
                ["pre_calibration_statement", "handoff_statement", "llm_statement"] if phase == 1 else
                ["package_confidence_score", "simulation_ready", "ready_parts", "isolated_parts"] if phase == 2 else
                ["simulation_result"] if phase == 3 else
                ["convergence_status"] if phase == 4 else
                []
            )},
        )
        controller.complete_phase(result)

    # Mock relay module dependencies
    mock_relay_result = MagicMock()
    mock_relay_result.relay_id = "relay-clean"
    mock_relay_result.inspection_hash_verified = True
    mock_relay_result.decision_status = "applied" if decision == "apply" else "cancelled"
    mock_relay_result.resolved = []
    mock_relay_result.unresolved = []
    mock_relay_result.before_after_diff = {}
    mock_relay_result.snapshot_hash = "abc123"
    mock_relay_result.candidate_hash = ""
    mock_relay_result.errors = []

    with patch.dict("sys.modules", {"relay": MagicMock()}):
        with patch("phase_5.restore_from_snapshot", return_value=True):
            from phase_5 import execute_phase_5_relay_auto

            # Use clean project path (no candidate, no resolved/unresolved)
            # This triggers the early-return "clean project" branch
            snapshot = {"snapshot_id": "test-snap", "storage_path": "/tmp/test", "target_path": "/tmp/target"}
            phase_3_outputs = {}
            phase_4_outputs = {"convergence_status": {}}

            result = execute_phase_5_relay_auto(
                controller=controller,
                snapshot=snapshot,
                phase_3_outputs=phase_3_outputs,
                phase_4_outputs=phase_4_outputs,
                decision=decision,
            )

    # Verify the result
    assert result.phase == 5
    assert result.phase_name == PHASE_NAMES[5]
    assert result.exit_status == "completed"
    assert result.required_outputs["decision"] is not None
    # Decision should contain the action
    assert result.required_outputs["decision"]["action"] == decision


# ──────────────────────────────────────────────
# Property: PhaseController rejects starting beyond phase 6
# **Validates: Requirements 3.1**
# ──────────────────────────────────────────────


@given(exec_id=execution_ids)
@settings(max_examples=20)
def test_controller_rejects_phase_beyond_6(exec_id):
    """After all phases 0-6 complete, controller rejects further phase starts.

    **Validates: Requirements 3.1**
    """
    controller = PhaseController(execution_id=exec_id)

    # Complete all 7 phases
    for phase in PHASE_ORDER:
        controller.start_phase(phase)
        result = PhaseResult(
            phase=phase,
            phase_name=PHASE_NAMES[phase],
            exit_status="completed",
            required_outputs={k: f"value_{k}" for k in (
                ["snapshot_id", "file_hashes"] if phase == 0 else
                ["pre_calibration_statement", "handoff_statement", "llm_statement"] if phase == 1 else
                ["package_confidence_score", "simulation_ready", "ready_parts", "isolated_parts"] if phase == 2 else
                ["simulation_result"] if phase == 3 else
                ["convergence_status"] if phase == 4 else
                ["decision"] if phase == 5 else
                ["final_output"] if phase == 6 else
                []
            )},
        )
        controller.complete_phase(result)

    # Any further phase start should raise PhaseViolation
    with pytest.raises(PhaseViolation):
        controller.start_phase(7)


# ──────────────────────────────────────────────
# Property: Invalid exit statuses are rejected by controller
# **Validates: Requirements 3.1**
# ──────────────────────────────────────────────


@given(
    exec_id=execution_ids,
    invalid_status=st.text(min_size=1, max_size=20).filter(
        lambda s: s not in VALID_EXIT_STATUSES
    ),
)
@settings(max_examples=30)
def test_controller_rejects_invalid_exit_status(exec_id, invalid_status):
    """PhaseController rejects phase completion with invalid exit statuses.

    **Validates: Requirements 3.1**
    """
    controller = PhaseController(execution_id=exec_id)
    controller.start_phase(0)

    result = PhaseResult(
        phase=0,
        phase_name=PHASE_NAMES[0],
        exit_status=invalid_status,
        required_outputs={"snapshot_id": "test", "file_hashes": {"a": "b"}},
    )

    with pytest.raises(PhaseViolation):
        controller.complete_phase(result)
