import json
from pathlib import Path

import pytest

from scripts.nextflow_demo import run_demo, sha256_json


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "cases" / "sample-config-repair" / "source" / "application-config.json"


@pytest.mark.parametrize("decision", ["apply", "cancel", "preserve_for_later"])
def test_decision_paths_lock_result_without_mutating_source(tmp_path, decision):
    before = SOURCE.read_bytes()
    result = run_demo(ROOT, user_decision=decision, run_root=tmp_path)
    state = result["state"]
    assert SOURCE.read_bytes() == before
    assert state["final_result"]["locked"] is True
    assert len(state["final_result_hash"]) == 64
    if decision == "apply":
        assert state["apply_relay_result"]["status"] == "applied"
        assert state["post_apply_verification"]["status"] == "verified_match"
    else:
        assert state["apply_relay_result"]["status"] == "not_applied"


def test_simulation_changes_only_retry_limit(tmp_path):
    state = run_demo(ROOT, run_root=tmp_path)["state"]
    original = state["snapshot"]
    result = state["simulation_result"]["result"]
    assert result["retry_limit"] == 3
    assert result["service_name"] == original["service_name"]
    assert result["enabled"] == original["enabled"]
    assert state["simulation_result_hash"] == sha256_json(result)


def test_invalid_package_cannot_enter_simulation(tmp_path):
    state = run_demo(ROOT, scenario="readiness_rejected", run_root=tmp_path)["state"]
    assert state["workflow_status"] == "blocked"
    assert state["simulation_status"] == "not_run"
    assert "confidence_score" in state["pre_simulation_package"]["admission_failures"]


def test_failed_simulation_cannot_be_approved(tmp_path):
    state = run_demo(ROOT, scenario="simulation_failure", run_root=tmp_path)["state"]
    assert state["simulation_status"] == "failed"
    assert state["approved_result_id"] == ""
    assert state["apply_relay_result"] == {}
