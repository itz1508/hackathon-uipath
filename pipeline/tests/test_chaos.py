"""
CHAOS TEST — 8 Attack Vectors Against the Edge Pipeline
========================================================

Tests the PhaseController state machine and pipeline phases against:
1. Structure Injection (invalid phase numbers)
2. Multi-Source Conflict (duplicate/out-of-order operations)
3. Isolation Abuse (empty inputs to phases)
4. Pre-Simulation Gate Collapse (boundary testing at 93.91%)
5. Simulation Mutation Safety (real target unchanged)
6. Relay Spoof (fake convergence data)
7. Loop Injection (repeated operations)
8. Phase Drift (skip/reverse ordering)
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, ".")

import pytest

from phase_models import (
    PhaseResult,
    PHASE_NAMES,
    PHASE_ORDER,
    PASS_THRESHOLD,
    REQUIRED_OUTPUTS,
)
from phase_controller import PhaseController, PhaseViolation


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_controller(execution_id: str = "chaos-test") -> PhaseController:
    """Create a fresh PhaseController."""
    return PhaseController(execution_id)


def _advance_controller_to(controller: PhaseController, up_to_phase: int) -> None:
    """Advance a controller through all phases [0..up_to_phase] inclusive.

    Completes each phase with minimal valid outputs.
    """
    for phase in PHASE_ORDER:
        if phase > up_to_phase:
            break
        controller.start_phase(phase)
        outputs = {k: f"<stub_{k}>" for k in REQUIRED_OUTPUTS[phase]}
        result = PhaseResult(
            phase=phase,
            phase_name=PHASE_NAMES[phase],
            exit_status="completed",
            required_outputs=outputs,
        )
        controller.complete_phase(result)


# ═══════════════════════════════════════════════════════════════
# VECTOR 1: STRUCTURE INJECTION ATTACK
# ═══════════════════════════════════════════════════════════════


class TestStructureInjection:
    """Try to start/complete phases that don't exist in PHASE_ORDER."""

    def test_start_phase_7_is_invalid_when_not_at_correct_index(self):
        """Phase 7 exists but you can't jump to it from the start."""
        ctrl = _make_controller()
        with pytest.raises(PhaseViolation):
            ctrl.start_phase(7)

    def test_start_phase_8_does_not_exist(self):
        """Phase 8 is not in PHASE_ORDER — must raise PhaseViolation."""
        ctrl = _make_controller()
        with pytest.raises(PhaseViolation):
            ctrl.start_phase(8)

    def test_start_phase_99_does_not_exist(self):
        """Phase 99 is not in PHASE_ORDER — must raise PhaseViolation."""
        ctrl = _make_controller()
        with pytest.raises(PhaseViolation):
            ctrl.start_phase(99)

    def test_start_phase_negative_1(self):
        """Phase -1 is not in PHASE_ORDER — must raise PhaseViolation."""
        ctrl = _make_controller()
        with pytest.raises(PhaseViolation):
            ctrl.start_phase(-1)

    def test_complete_phase_outside_order(self):
        """Completing a phase that isn't the current one raises PhaseViolation."""
        ctrl = _make_controller()
        ctrl.start_phase(0)
        # Try to complete phase 99 (not the current phase)
        result = PhaseResult(
            phase=99,
            phase_name="ghost",
            exit_status="completed",
            required_outputs={"snapshot_id": "x", "file_hashes": {}},
        )
        with pytest.raises(PhaseViolation):
            ctrl.complete_phase(result)


# ═══════════════════════════════════════════════════════════════
# VECTOR 2: MULTI-SOURCE CONFLICT ATTACK
# ═══════════════════════════════════════════════════════════════


class TestMultiSourceConflict:
    """Try conflicting operations: double-complete, double-start, wrong phase complete."""

    def test_complete_same_phase_twice(self):
        """After completing phase 0 and starting phase 1, trying to complete
        phase 0 again should raise PhaseViolation because current is now phase 1.
        """
        ctrl = _make_controller()
        ctrl.start_phase(0)
        result_0 = PhaseResult(
            phase=0,
            phase_name=PHASE_NAMES[0],
            exit_status="completed",
            required_outputs={k: f"v_{k}" for k in REQUIRED_OUTPUTS[0]},
        )
        ctrl.complete_phase(result_0)
        # Advance to phase 1
        ctrl.start_phase(1)
        # Now try to complete phase 0 again — current is phase 1
        with pytest.raises(PhaseViolation):
            ctrl.complete_phase(result_0)

    def test_start_phase_already_running(self):
        """Starting the same phase again when it's already running should fail."""
        ctrl = _make_controller()
        ctrl.start_phase(0)
        # Phase 0 is running. Try to start phase 0 again.
        with pytest.raises(PhaseViolation):
            ctrl.start_phase(0)

    def test_complete_different_phase_than_current(self):
        """Completing a phase that is not the current one should raise PhaseViolation."""
        ctrl = _make_controller()
        ctrl.start_phase(0)
        # Current is phase 0, try to complete phase 1
        result = PhaseResult(
            phase=1,
            phase_name=PHASE_NAMES[1],
            exit_status="completed",
            required_outputs={k: f"v_{k}" for k in REQUIRED_OUTPUTS[1]},
        )
        with pytest.raises(PhaseViolation):
            ctrl.complete_phase(result)


# ═══════════════════════════════════════════════════════════════
# VECTOR 3: ISOLATION ABUSE ATTACK
# ═══════════════════════════════════════════════════════════════


class TestIsolationAbuse:
    """Feed phases with empty/missing data — pipeline should not crash."""

    def test_phase_3_with_empty_inputs(self):
        """Phase 3 (pre-simulation) with empty scan and classification results.

        Pipeline should continue forward (clean project path) without crashing.
        """
        from phase_3 import execute_phase_3_presimulation

        ctrl = _make_controller()
        # Advance to phase 2 completed
        _advance_controller_to(ctrl, 2)

        snapshot = {"total_files": 0, "target_path": ".", "snapshot_id": "test"}
        phase_2_outputs = {
            "classification_results": [],
            "total_issues": 0,
        }
        # Should NOT crash — clean project path
        result = execute_phase_3_presimulation(ctrl, snapshot, phase_2_outputs)
        assert result.exit_status == "completed"
        assert result.required_outputs["simulation_ready"] is True
        assert result.required_outputs["ready_parts"] == []
        assert result.required_outputs["isolated_parts"] == []

    def test_phase_4_with_empty_ready_parts(self):
        """Phase 4 (simulation) with empty ready_parts.

        Should produce a simulation result with 0 items and succeed.
        """
        from phase_4 import execute_phase_4_simulation

        ctrl = _make_controller()
        _advance_controller_to(ctrl, 3)

        snapshot = {
            "target_path": ".",
            "storage_path": ".",
            "snapshot_id": "test-snap",
        }
        phase_2_outputs = {"classification_results": []}
        phase_3_outputs = {"ready_parts": [], "isolated_parts": []}

        result = execute_phase_4_simulation(ctrl, snapshot, phase_2_outputs, phase_3_outputs)
        assert result.exit_status == "completed"
        sim = result.required_outputs["simulation_result"]
        assert sim["items_processed"] == 0
        assert sim["simulation_succeeded"] is True
        assert sim["real_target_unchanged"] is True


# ═══════════════════════════════════════════════════════════════
# VECTOR 4: PRE-SIMULATION GATE COLLAPSE
# ═══════════════════════════════════════════════════════════════


class TestPreSimulationGate:
    """Test the 93.91% boundary with hundredth-point precision."""

    def test_score_9391_passes(self):
        """Score of 93.91 passes — hundredths: 9391 >= 9391."""
        score = 93.91
        score_hundredths = round(score * 100)
        assert score_hundredths == 9391
        assert score_hundredths >= PASS_THRESHOLD

    def test_score_9390_fails(self):
        """Score of 93.90 does NOT pass — hundredths: 9390 < 9391."""
        score = 93.90
        score_hundredths = round(score * 100)
        assert score_hundredths == 9390
        assert score_hundredths < PASS_THRESHOLD

    def test_malformed_classification_missing_keys(self):
        """Feed Phase 3 with classification items missing keys.

        Phase 3 should handle gracefully (use defaults) and not crash.
        """
        from phase_3 import execute_phase_3_presimulation

        ctrl = _make_controller()
        _advance_controller_to(ctrl, 2)

        snapshot = {"total_files": 5, "target_path": ".", "snapshot_id": "t"}
        # Malformed: missing 'severity', 'id', 'file' keys
        phase_2_outputs = {
            "classification_results": [
                {"category": "syntax_error"},  # missing id, file, etc.
                {},  # completely empty
                {"type": "unknown", "confidence": "not_a_number"},  # wrong types
            ],
            "total_issues": 3,
        }
        # Should NOT crash
        result = execute_phase_3_presimulation(ctrl, snapshot, phase_2_outputs)
        assert result.exit_status == "completed"
        assert result.required_outputs["package_confidence_score"] is not None

    def test_boundary_deterministic_regardless_of_input_quality(self):
        """Deterministic behavior: same inputs always produce same routing."""
        from phase_3 import execute_phase_3_presimulation

        results = []
        for _ in range(3):
            ctrl = _make_controller()
            _advance_controller_to(ctrl, 2)
            snapshot = {"total_files": 10, "target_path": ".", "snapshot_id": "det"}
            phase_2_outputs = {
                "classification_results": [
                    {"id": "item-1", "category": "syntax_error", "file": "a.py"},
                    {"id": "item-2", "category": "missing_dependency", "file": "b.py"},
                ],
                "total_issues": 2,
            }
            result = execute_phase_3_presimulation(ctrl, snapshot, phase_2_outputs)
            results.append(result.required_outputs)

        # All 3 runs produce identical outputs
        assert results[0] == results[1] == results[2]


# ═══════════════════════════════════════════════════════════════
# VECTOR 5: SIMULATION MUTATION SAFETY ATTACK
# ═══════════════════════════════════════════════════════════════


class TestSimulationMutationSafety:
    """Verify the real target file is UNCHANGED after simulation."""

    def test_real_target_unchanged_after_simulation(self):
        """Create a temp target folder with a known file.

        Run execute_simulation(). Verify real target is UNCHANGED.
        """
        from simulation import (
            create_candidate_copy,
            execute_simulation,
            cleanup_candidate,
            hash_directory,
        )
        from models import Finding, FindingCategory, ItemScore

        # Create a temp directory as the "real target"
        target_dir = tempfile.mkdtemp(prefix="chaos_target_")
        try:
            # Write a known file
            known_file = Path(target_dir) / "known.py"
            known_content = "# This must not change\nprint('original')\n"
            known_file.write_text(known_content, encoding="utf-8")

            # Hash before
            hashes_before = hash_directory(target_dir)

            # Create candidate copy
            candidate_path = create_candidate_copy(target_dir, target_dir)

            # Run simulation with a dummy finding
            findings = [
                Finding(
                    finding_id="F-001",
                    category=FindingCategory.SYNTAX_ERROR,
                    severity="high",
                    file="known.py",
                    root_cause="test",
                    root_cause_confirmed=True,
                )
            ]
            item_scores = [
                ItemScore(item_id="F-001", information_score=95.0, information_complete=True)
            ]

            sim_output = execute_simulation(
                candidate_path=candidate_path,
                target_path=target_dir,
                snapshot_id="snap-chaos",
                qualified_items=["F-001"],
                findings=findings,
                item_scores=item_scores,
            )

            # CRITICAL CHECK: real target must be unchanged
            assert sim_output.real_target_unchanged is True

            # Double-check manually
            hashes_after = hash_directory(target_dir)
            assert hashes_before == hashes_after

            # Verify known file content is still original
            assert known_file.read_text(encoding="utf-8") == known_content

            # Cleanup
            cleanup_candidate(candidate_path)
        finally:
            shutil.rmtree(target_dir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════
# VECTOR 6: RELAY SPOOF ATTACK
# ═══════════════════════════════════════════════════════════════


class TestRelaySpoofAttack:
    """Feed Phase 6 relay with fake/empty convergence data and mismatched hashes."""

    def test_relay_auto_with_fake_convergence(self):
        """Feed relay auto mode with fake convergence_status and mismatched hashes.

        Should NOT crash — detects the mismatch and produces a result.
        """
        from relay import RelayInput, run_relay

        # Build a relay input with completely fake/mismatched data
        inp = RelayInput(
            case_id="spoof-case",
            snapshot_id="fake-snapshot-id",
            snapshot_path="",  # Empty — doesn't exist
            snapshot_hash="0000000000000000000000000000000000000000000000000000000000000000",
            inspection_id="fake-inspection-id",
            inspection_hash="aaaa_this_will_never_match_bbbb",  # Mismatched hash
            candidate_path="",  # Empty — doesn't exist
            candidate_hash="1111111111111111111111111111111111111111111111111111111111111111",
            resolved_items=[{"item_id": "spoofed-item", "status": "resolved"}],
            unresolved_items=[],
            item_traces=[],
            target_path="",
            decision="",  # No decision — just verify hash
        )

        # Should NOT crash
        result = run_relay(inp)

        # Relay should detect mismatch
        assert result.inspection_hash_verified is False
        assert result.decision_status == "rejected"
        assert any(e.code == "INSPECTION_HASH_MISMATCH" for e in result.errors)

    def test_relay_with_empty_everything(self):
        """Relay with all-empty inputs should not crash."""
        from relay import RelayInput, run_relay

        inp = RelayInput(
            case_id="",
            snapshot_id="",
            snapshot_path="",
            snapshot_hash="",
            inspection_id="",
            inspection_hash="mismatched",  # Will fail verification
            candidate_path="",
            candidate_hash="",
            resolved_items=[],
            unresolved_items=[],
            item_traces=[],
            target_path="",
            decision="",
        )

        # Should NOT crash
        result = run_relay(inp)
        assert result is not None
        # With empty paths and mismatched hash, it should either reject or handle gracefully
        assert result.decision_status in ("rejected", "awaiting_user")


# ═══════════════════════════════════════════════════════════════
# VECTOR 7: LOOP INJECTION ATTACK
# ═══════════════════════════════════════════════════════════════


class TestLoopInjection:
    """Try to start the same phase multiple times or complete without starting."""

    def test_start_same_phase_multiple_times(self):
        """Starting the same phase repeatedly should raise PhaseViolation, not loop."""
        ctrl = _make_controller()
        ctrl.start_phase(0)
        # Try to start phase 0 again (already running)
        with pytest.raises(PhaseViolation):
            ctrl.start_phase(0)
        # Try a third time
        with pytest.raises(PhaseViolation):
            ctrl.start_phase(0)

    def test_complete_without_start(self):
        """Calling complete_phase() without start_phase() should raise PhaseViolation."""
        ctrl = _make_controller()
        # Current phase is None (nothing started)
        result = PhaseResult(
            phase=0,
            phase_name=PHASE_NAMES[0],
            exit_status="completed",
            required_outputs={k: f"v_{k}" for k in REQUIRED_OUTPUTS[0]},
        )
        with pytest.raises(PhaseViolation):
            ctrl.complete_phase(result)

    def test_repeated_start_after_complete_raises(self):
        """After completing phase 0, trying to start phase 0 again raises PhaseViolation."""
        ctrl = _make_controller()
        ctrl.start_phase(0)
        result = PhaseResult(
            phase=0,
            phase_name=PHASE_NAMES[0],
            exit_status="completed",
            required_outputs={k: f"v_{k}" for k in REQUIRED_OUTPUTS[0]},
        )
        ctrl.complete_phase(result)
        # Phase 0 is completed. Trying to start phase 0 again should fail.
        with pytest.raises(PhaseViolation):
            ctrl.start_phase(0)


# ═══════════════════════════════════════════════════════════════
# VECTOR 8: PHASE DRIFT ATTACK
# ═══════════════════════════════════════════════════════════════


class TestPhaseDrift:
    """Try to skip phases or go backwards."""

    def test_skip_phases_forward(self):
        """Start phase 3 after only completing phase 0 — should raise PhaseViolation."""
        ctrl = _make_controller()
        ctrl.start_phase(0)
        result = PhaseResult(
            phase=0,
            phase_name=PHASE_NAMES[0],
            exit_status="completed",
            required_outputs={k: f"v_{k}" for k in REQUIRED_OUTPUTS[0]},
        )
        ctrl.complete_phase(result)
        # Try to skip to phase 3 (expected next is phase 1)
        with pytest.raises(PhaseViolation):
            ctrl.start_phase(3)

    def test_go_backwards_after_completing_phase_2(self):
        """Complete phase 2, then try to start phase 1 — should raise PhaseViolation."""
        ctrl = _make_controller()
        _advance_controller_to(ctrl, 2)
        # Now try to start phase 1 (going backwards)
        with pytest.raises(PhaseViolation):
            ctrl.start_phase(1)

    def test_skip_to_last_phase(self):
        """Skip from phase 0 to phase 7 — should raise PhaseViolation."""
        ctrl = _make_controller()
        ctrl.start_phase(0)
        result = PhaseResult(
            phase=0,
            phase_name=PHASE_NAMES[0],
            exit_status="completed",
            required_outputs={k: f"v_{k}" for k in REQUIRED_OUTPUTS[0]},
        )
        ctrl.complete_phase(result)
        with pytest.raises(PhaseViolation):
            ctrl.start_phase(7)

    def test_go_backwards_to_phase_0(self):
        """After all phases are done, cannot restart from phase 0."""
        ctrl = _make_controller()
        _advance_controller_to(ctrl, 7)
        with pytest.raises(PhaseViolation):
            ctrl.start_phase(0)
