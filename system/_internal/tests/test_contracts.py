import copy
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts.nextflow_demo import run_demo


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"


def load_schema(name):
    import json

    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def validate(name, value):
    validator = Draft202012Validator(load_schema(name))
    return sorted(validator.iter_errors(value), key=lambda error: list(error.path))


def test_all_contracts_are_valid_draft_2020_12():
    for path in CONTRACTS.glob("*.schema.json"):
        Draft202012Validator.check_schema(load_schema(path.name))


def test_happy_path_artifacts_validate(tmp_path):
    state = run_demo(ROOT, run_root=tmp_path)["state"]
    assert validate("workflow-state.schema.json", state) == []
    assert validate("handoff.schema.json", state["handoff_statement"]) == []
    assert validate("pre-simulation-package.schema.json", state["pre_simulation_package"]) == []
    assert validate("simulation-result.schema.json", state["simulation_result"]) == []
    assert validate("replay-proof.schema.json", state["replay_proof"]) == []
    assert validate("apply-relay.schema.json", state["apply_relay_result"]) == []
    assert validate("post-apply-verification.schema.json", state["post_apply_verification"]) == []
    assert validate("final-result.schema.json", state["final_result"]) == []


def test_ready_contract_enforces_every_admission_condition(tmp_path):
    package = run_demo(ROOT, run_root=tmp_path)["state"]["pre_simulation_package"]
    mutations = {
        "required_grader_failures": ["grader-failed"],
        "isolation_required": True,
        "reattempt_required": True,
        "confidence_score": 93.90,
        "required_dependencies_available": False,
        "admission_failures": ["blocked"],
    }
    for field, value in mutations.items():
        candidate = copy.deepcopy(package)
        candidate[field] = value
        assert validate("pre-simulation-package.schema.json", candidate), field


def test_auto_dependency_status_matches_boolean(tmp_path):
    handoff = run_demo(ROOT, run_root=tmp_path)["state"]["handoff_statement"]
    invalid = copy.deepcopy(handoff)
    invalid["auto_dependency"]["status"] = "on"
    assert validate("handoff.schema.json", invalid)
