from tests._support import EXAMPLES, load_json, schema_errors


def test_handoff_stage_placement_is_fixed():
    handoff = load_json(EXAMPLES / "handoff-auto-dependency-on.json")
    assert handoff["current_stage"] == "handoff_statement"
    assert handoff["completed_stage"] == "02.25-recalibration"
    assert handoff["destination_stage"] == "02.5-pre-simulation"


def test_identifiable_missing_dependency_does_not_require_isolation():
    handoff = load_json(EXAMPLES / "handoff-auto-dependency-off.json")
    assert handoff["auto_dependency"]["unresolved_dependencies"] == ["dependency-002"]
    assert handoff["isolation_required"] is False
    assert handoff["next_action"] == "request_required_dependency"
    assert schema_errors(handoff) == []


def test_valid_isolation_has_bounded_reason_and_action():
    handoff = load_json(EXAMPLES / "handoff-isolation-required.json")
    assert handoff["isolation_required"] is True
    assert handoff["isolation_reasons"] == ["dependency_identity_unclear"]
    assert handoff["next_action"] == "build_isolation_addon"
    assert schema_errors(handoff) == []
