from tests._support import EXAMPLES, contract_errors, load_json, schema_errors


def test_auto_dependency_on_uses_only_declared_local_dependency():
    handoff = load_json(EXAMPLES / "handoff-auto-dependency-on.json")
    dependency = handoff["auto_dependency"]["dependencies"][0]
    assert handoff["auto_dependency"]["enabled"] is True
    assert handoff["auto_dependency"]["status"] == "on"
    assert dependency["source"] == "local-environment"
    assert dependency["action_taken"] == "used"
    assert schema_errors(handoff) == []
    assert contract_errors(handoff) == []


def test_auto_dependency_off_takes_no_action():
    handoff = load_json(EXAMPLES / "handoff-auto-dependency-off.json")
    assert handoff["auto_dependency"]["enabled"] is False
    assert handoff["auto_dependency"]["status"] == "off"
    assert all(item["action_taken"] == "none" for item in handoff["auto_dependency"]["dependencies"])
    assert schema_errors(handoff) == []
    assert contract_errors(handoff) == []
