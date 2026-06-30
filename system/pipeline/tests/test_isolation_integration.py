import types

from phase_controller import PhaseController


def test_transform_phase_3_applies_isolation_resolution(monkeypatch):
    """Ensure transform_phase_3 applies isolation engine resolutions to move items to ready."""
    from pipeline_state import PipelineState, Flags
    from phase_3 import transform_phase_3

    # Build a minimal state with one classification result that will be isolated
    state = PipelineState(
        case_id="test-case",
        execution_id="exec-1",
        target_path=".",
        mode="auto",
        decision="apply",
        isolation_enabled=True,
    )

    # Minimal analysis with one issue that would be isolated
    state.analysis = {
        "classification_results": [
            {
                "id": "item-1",
                "category": "missing_information",
                "root_cause_confirmed": False,
                "file": "unknown",
                "description": "Missing dependency info",
                "missing_information": ["lock_file"],
                "confidence": 0.2,
            }
        ],
        "total_issues": 1,
    }

    # Stub the isolation engine to pretend it resolved the item
    def fake_run_isolation_engine(isolated_items, classification_results, target_path, enabled=True):
        return {
            "items_resolved": 1,
            "resolution_records": [
                {"item_id": "item-1", "retry_recommendation": "ready_for_simulation"}
            ],
            "rebuilt_classification": [
                {
                    "id": "item-1",
                    "category": "missing_information",
                    "root_cause_confirmed": True,
                    "file": "some_file.py",
                    "description": "Resolved by isolation research",
                    "confidence": 0.95,
                }
            ],
        }

    monkeypatch.setattr("isolation_engine.run_isolation_engine", fake_run_isolation_engine)

    controller = PhaseController("test-exec")

    new_state = transform_phase_3(state, controller)

    pkg = new_state.simulation_package
    # After engine, isolated_parts should be empty and ready_parts should include the item
    assert len(pkg.get("isolated_parts", [])) == 0
    ready_ids = [p["item_id"] for p in pkg.get("ready_parts", [])]
    assert "item-1" in ready_ids
