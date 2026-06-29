"""Bug Condition Exploration Test — Edge Pipeline Workflow Conformance.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7**

This test encodes the EXPECTED (correct) behavior of the pipeline per Edge-WORKFLOW.md.
On UNFIXED code, these tests will FAIL — failure confirms the bug exists.
On FIXED code, these tests will PASS — confirming the fix works.

Property 1: Bug Condition — Pipeline Contains Unauthorized Phase 7 and Workflow Drift

Scoped PBT Approach: Concrete structural assertions on the loaded pipeline module.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure the project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phase_models import PHASE_NAMES, REQUIRED_OUTPUTS, WorkflowOutput


class TestBugConditionExploration:
    """Property 1: Bug Condition — Pipeline Contains Unauthorized Phase 7 and Workflow Drift.

    Each test asserts the EXPECTED (correct) state per the workflow specification.
    These tests are expected to FAIL on unfixed code, confirming the bug exists.
    """

    def test_phase_7_file_does_not_exist(self):
        """Assert that phase_7.py does NOT exist in the pipeline directory.

        Bug Condition: file_exists("phase_7.py")
        Expected: phase_7.py should NOT exist — the pipeline defines exactly phases 0–6.
        """
        phase_7_path = PROJECT_ROOT / "phase_7.py"
        assert not phase_7_path.exists(), (
            f"COUNTEREXAMPLE: phase_7.py exists at {phase_7_path}. "
            f"The pipeline specification defines exactly phases 0–6. "
            f"Phase 7 is unauthorized."
        )

    def test_required_outputs_does_not_contain_key_7(self):
        """Assert that 7 is NOT in REQUIRED_OUTPUTS keys.

        Bug Condition: 7 IN keys(REQUIRED_OUTPUTS)
        Expected: REQUIRED_OUTPUTS should only contain keys 0–6.
        """
        assert 7 not in REQUIRED_OUTPUTS, (
            f"COUNTEREXAMPLE: REQUIRED_OUTPUTS contains key 7 with value "
            f"{REQUIRED_OUTPUTS.get(7)}. The workflow spec defines only phases 0–6."
        )

    def test_phase_names_6_is_final_output(self):
        """Assert that PHASE_NAMES[6] == "final_output".

        Bug Condition: PHASE_NAMES[6] != "final_output"
        Expected: Phase 6 should be named "final_output" per workflow spec.
        """
        assert PHASE_NAMES[6] == "final_output", (
            f"COUNTEREXAMPLE: PHASE_NAMES[6] is '{PHASE_NAMES[6]}' "
            f"instead of 'final_output'. The workflow spec defines Phase 6 as 'Final Output'."
        )

    def test_workflow_output_has_no_cleanup_summary_field(self):
        """Assert that WorkflowOutput does NOT have a 'cleanup_summary' field.

        Bug Condition: "cleanup_summary" IN fields(WorkflowOutput)
        Expected: WorkflowOutput should not include cleanup_summary since Phase 7 doesn't exist.
        """
        model_fields = set(WorkflowOutput.model_fields.keys())
        assert "cleanup_summary" not in model_fields, (
            f"COUNTEREXAMPLE: WorkflowOutput includes 'cleanup_summary' field. "
            f"This field references unauthorized Phase 7 output. "
            f"Current fields: {sorted(model_fields)}"
        )

    def test_phase_5_manual_mode_exit_status_not_awaiting_user_approval(self):
        """Assert that execute_phase_5_relay() does NOT return exit_status="awaiting_user_approval".

        Bug Condition: phase5_manual_mode_uses_invalid_exit_status
        Expected: The returned PhaseResult should NOT carry "awaiting_user_approval"
        as exit_status — this value is not in VALID_EXIT_STATUSES and would fail
        controller exit validation.
        """
        from phase_controller import PhaseController

        # Set up a controller with phases 0-4 already completed
        controller = PhaseController(execution_id="test-exploration-001")

        # Complete phases 0–4 so we can start phase 5
        from phase_models import PhaseResult as PR

        for phase_idx in range(5):
            controller.start_phase(phase_idx)
            result = PR(
                phase=phase_idx,
                phase_name=PHASE_NAMES[phase_idx],
                exit_status="completed",
                required_outputs={k: f"val_{k}" for k in REQUIRED_OUTPUTS.get(phase_idx, [])},
            )
            controller.complete_phase(result)

        # Mock relay dependencies to avoid needing actual relay infrastructure
        mock_relay_input_cls = MagicMock()
        mock_run_relay = MagicMock()
        mock_hash_directory = MagicMock(return_value="fakehash123")

        with patch.dict(
            "sys.modules",
            {"relay": MagicMock(RelayInput=mock_relay_input_cls, run_relay=mock_run_relay, _hash_directory=mock_hash_directory)},
        ):
            from phase_5 import execute_phase_5_relay

            result = execute_phase_5_relay(
                controller=controller,
                snapshot={"target_path": "/tmp/target", "storage_path": "/tmp/storage", "snapshot_id": "snap-001"},
                phase_4_outputs={"convergence_status": {"inspection_hash": "abc", "resolved_items": [], "unresolved_items": [], "candidate_hash": "", "item_traces": []}},
                backend_base_url="http://localhost:8790",
                execution_id="exec-001",
            )

        assert result.exit_status != "awaiting_user_approval", (
            f"COUNTEREXAMPLE: Phase 5 manual mode returns exit_status="
            f"'{result.exit_status}'. This value is not in VALID_EXIT_STATUSES "
            f"and would fail controller validation if passed to complete_phase()."
        )

    def test_phase_5_manual_mode_decision_not_none(self):
        """Assert that execute_phase_5_relay() returns decision that is NOT None.

        Bug Condition: phase5_manual_mode_sets_decision_to_None
        Expected: required_outputs["decision"] should be a valid non-None placeholder.
        """
        from phase_controller import PhaseController

        # Set up a controller with phases 0-4 already completed
        controller = PhaseController(execution_id="test-exploration-002")

        from phase_models import PhaseResult as PR

        for phase_idx in range(5):
            controller.start_phase(phase_idx)
            result = PR(
                phase=phase_idx,
                phase_name=PHASE_NAMES[phase_idx],
                exit_status="completed",
                required_outputs={k: f"val_{k}" for k in REQUIRED_OUTPUTS.get(phase_idx, [])},
            )
            controller.complete_phase(result)

        # Mock relay dependencies
        mock_relay_input_cls = MagicMock()
        mock_run_relay = MagicMock()
        mock_hash_directory = MagicMock(return_value="fakehash456")

        with patch.dict(
            "sys.modules",
            {"relay": MagicMock(RelayInput=mock_relay_input_cls, run_relay=mock_run_relay, _hash_directory=mock_hash_directory)},
        ):
            from phase_5 import execute_phase_5_relay

            result = execute_phase_5_relay(
                controller=controller,
                snapshot={"target_path": "/tmp/target", "storage_path": "/tmp/storage", "snapshot_id": "snap-002"},
                phase_4_outputs={"convergence_status": {"inspection_hash": "def", "resolved_items": [], "unresolved_items": [], "candidate_hash": "", "item_traces": []}},
                backend_base_url="http://localhost:8790",
                execution_id="exec-002",
            )

        decision_value = result.required_outputs.get("decision")
        assert decision_value is not None, (
            f"COUNTEREXAMPLE: Phase 5 manual mode sets required_outputs['decision'] = None. "
            f"This would fail the controller's required-output validation (non-None check)."
        )
