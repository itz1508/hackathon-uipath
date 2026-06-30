import copy

import pytest

from tests._support import EXAMPLES, load_json, schema_errors


def ready_package():
    return load_json(EXAMPLES / "pre-simulation-ready.json")


def test_fully_qualified_package_is_ready():
    package = ready_package()
    assert package["confidence_score"] == 93.91
    assert package["simulation_ready"] is True
    assert schema_errors(package) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("required_grader_failures", ["grader-1"]),
        ("isolation_required", True),
        ("reattempt_required", True),
        ("confidence_score", 93.90),
        ("required_dependencies_available", False),
    ],
)
def test_each_failed_admission_condition_rejects_ready(field, value):
    package = copy.deepcopy(ready_package())
    package[field] = value
    assert schema_errors(package)


def test_dependency_blocked_package_remains_out_of_simulation():
    package = load_json(EXAMPLES / "pre-simulation-dependency-blocked.json")
    assert package["required_dependencies_available"] is False
    assert package["simulation_ready"] is False
    assert package["isolation_required"] is False
    assert schema_errors(package) == []


def test_reattempt_package_routes_to_rebuild():
    package = load_json(EXAMPLES / "pre-simulation-reattempt.json")
    assert package["reattempt_required"] is True
    assert package["next_action"] == "rebuild_pre_simulation_package"
    assert schema_errors(package) == []
