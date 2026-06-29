from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any


READY_THRESHOLD = 93.91


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def admission_failures(package: dict[str, Any]) -> list[str]:
    checks = {
        "simulation_ready": package.get("simulation_ready") is True,
        "required_grader_failures": package.get("required_grader_failures") == [],
        "isolation_required": package.get("isolation_required") is False,
        "reattempt_required": package.get("reattempt_required") is False,
        "confidence_score": package.get("confidence_score", 0) >= READY_THRESHOLD,
        "required_dependencies_available": package.get("required_dependencies_available") is True,
    }
    return [name for name, accepted in checks.items() if not accepted]


def build_handoff(state: dict[str, Any]) -> dict[str, Any]:
    enabled = state["auto_dependency_enabled"]
    return {
        "current_stage": "handoff_statement",
        "completed_stage": "02-analysis-classification-recalibration",
        "destination_stage": "02.5-pre-simulation",
        "status": "ready",
        "snapshot_ref": {"hash": state["snapshot_hash"]},
        "raw_statement_ref": {"statement": state["raw_statement"]},
        "target": copy.deepcopy(state["target_state"]),
        "scope": {
            "locked": True,
            "included": ["retry_limit"],
            "excluded": ["service_name", "enabled"],
        },
        "classification": copy.deepcopy(state["classification"]),
        "missing_information": [],
        "unresolved_items": [],
        "auto_dependency": {
            "enabled": enabled,
            "status": "on" if enabled else "off",
            "dependencies": copy.deepcopy(state["dependencies"]),
            "unresolved_dependencies": copy.deepcopy(state["unresolved_dependencies"]),
        },
        "isolation_required": False,
        "next_action": "build_pre_simulation_package",
    }


def run_demo(
    repo_root: Path,
    *,
    user_decision: str = "apply",
    scenario: str = "happy_path",
    run_root: Path | None = None,
) -> dict[str, Any]:
    if user_decision not in {"apply", "cancel", "preserve_for_later"}:
        raise ValueError(f"unsupported user decision: {user_decision}")

    case_root = repo_root / "cases" / "sample-config-repair"
    source_path = case_root / "source" / "application-config.json"
    expected_path = case_root / "expected" / "application-config.json"
    case_input = load_json(case_root / "case-input.json")
    source_before = source_path.read_bytes()
    source = load_json(source_path)
    expected = load_json(expected_path)
    run_id = str(uuid.uuid4())
    run_dir = (run_root or Path(tempfile.gettempdir()) / "nextflow-demo-runs") / run_id
    sandbox_path = run_dir / "sandbox" / "application-config.json"
    live_path = run_dir / "live-target" / "application-config.json"
    sandbox_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, sandbox_path)

    state: dict[str, Any] = {
        "case_id": case_input["case_id"],
        "run_id": run_id,
        "workflow_status": "running",
        "current_stage": "01-scan-snapshot",
        "completed_stage": "",
        "destination_stage": "02-analysis-classification-recalibration",
        "case_input": case_input,
        "target_state": {"target_id": case_input["target_id"], "source": str(source_path)},
        "snapshot": source,
        "snapshot_hash": sha256_json(source),
        "raw_statement": "retry_limit=-1 violates the non-negative retry policy",
        "classification": {
            "type": "invalid_configuration",
            "field": "retry_limit",
            "observed": source["retry_limit"],
        },
        "recalibration_findings": {
            "supported": True,
            "correction": {"retry_limit": expected["retry_limit"]},
            "successful_result_definition": "sandbox equals expected configuration",
        },
        "handoff_statement": {},
        "llm_statement": {
            "role": "advisory",
            "authority": "none",
            "statement": "Correct retry_limit only; deterministic gates control admission and apply.",
        },
        "auto_dependency_enabled": False,
        "auto_dependency_status": "off",
        "dependencies": [],
        "unresolved_dependencies": [],
        "required_dependencies_available": True,
        "pre_simulation_package": {},
        "simulation_ready": True,
        "required_grader_failures": [],
        "isolation_required": False,
        "reattempt_required": False,
        "confidence_score": READY_THRESHOLD,
        "simulation_result": {},
        "simulation_result_hash": "",
        "simulation_status": "not_run",
        "failure_capture": None,
        "retry_count": 0,
        "replay_proof": {},
        "proof_status": "not_run",
        "user_decision": user_decision,
        "approved_result_id": "",
        "approved_result_hash": "",
        "apply_relay_result": {},
        "post_apply_verification": {},
        "final_result": {},
        "final_result_hash": "",
        "audit_trail": ["01 Scan / Snapshot"],
    }

    state["current_stage"] = "02-analysis-classification-recalibration"
    state["audit_trail"].append("02 Analysis / Classification / Recalibration / Output")
    state["handoff_statement"] = build_handoff(state)
    state["audit_trail"].append("Build Handoff State")

    package = {
        "package_id": f"package-{run_id}",
        "handoff_hash": sha256_json(state["handoff_statement"]),
        "simulation_ready": True,
        "required_grader_failures": [],
        "isolation_required": False,
        "reattempt_required": False,
        "confidence_score": READY_THRESHOLD,
        "required_dependencies_available": True,
    }
    if scenario == "readiness_rejected":
        package["confidence_score"] = 93.90
    package["admission_failures"] = admission_failures(package)
    state["pre_simulation_package"] = package
    state["current_stage"] = "02.5-pre-simulation"
    state["audit_trail"].append("02.5 Pre-Simulation Package")

    if package["admission_failures"]:
        state["workflow_status"] = "blocked"
        state["simulation_ready"] = False
        state["failure_capture"] = {
            "stage": "02.5-pre-simulation",
            "reasons": package["admission_failures"],
        }
        return _finalize(state, source_path, source_before, run_dir)

    sandbox = load_json(sandbox_path)
    sandbox["retry_limit"] = expected["retry_limit"]
    write_json(sandbox_path, sandbox)
    validation_passed = sandbox == expected and set(sandbox) == set(source)
    if scenario == "simulation_failure":
        validation_passed = False
    state["simulation_result"] = {
        "result_id": f"simulation-{run_id}",
        "target_id": case_input["target_id"],
        "sandbox_path": str(sandbox_path),
        "sandbox_execution_completed": True,
        "inspection_completed": True,
        "validation_passed": validation_passed,
        "result": sandbox,
    }
    state["simulation_result_hash"] = sha256_json(sandbox)
    state["simulation_status"] = "passed" if validation_passed else "failed"
    state["current_stage"] = "03-simulation"
    state["audit_trail"].append("03 Simulation Environment")
    if not validation_passed:
        state["workflow_status"] = "blocked"
        state["failure_capture"] = {"stage": "03-simulation", "reason": "validation_failed"}
        return _finalize(state, source_path, source_before, run_dir)

    replayed = load_json(sandbox_path)
    proof_passed = (
        sha256_json(state["snapshot"]) == state["snapshot_hash"]
        and sha256_json(replayed) == state["simulation_result_hash"]
        and replayed == expected
    )
    state["replay_proof"] = {
        "snapshot_identity": state["snapshot_hash"],
        "package_identity": sha256_json(package),
        "execution_identity": state["simulation_result"]["result_id"],
        "simulation_result_identity": state["simulation_result"]["result_id"],
        "simulation_result_hash": state["simulation_result_hash"],
        "validation_result": validation_passed,
        "replay_equivalence": proof_passed,
    }
    state["proof_status"] = "passed" if proof_passed else "failed"
    state["current_stage"] = "04-replay-proof"
    state["audit_trail"].append("04 Replay / Proof")
    if not proof_passed:
        state["workflow_status"] = "proof_pending"
        return _finalize(state, source_path, source_before, run_dir)

    state["current_stage"] = "05-user-decision"
    state["audit_trail"].append(f"05 User Decision: {user_decision}")
    if user_decision == "apply":
        state["approved_result_id"] = state["simulation_result"]["result_id"]
        state["approved_result_hash"] = state["simulation_result_hash"]
        live_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, live_path)
        live_before = load_json(live_path)
        preconditions = {
            "user_approval_confirmed": True,
            "approved_hash_matches": state["approved_result_hash"] == sha256_json(replayed),
            "target_matches": case_input["target_id"] == state["simulation_result"]["target_id"],
            "no_invalidating_drift": sha256_json(live_before) == state["snapshot_hash"],
            "recovery_available": True,
        }
        if not all(preconditions.values()):
            state["apply_relay_result"] = {"status": "blocked", "preconditions": preconditions}
            state["post_apply_verification"] = {"status": "incomplete_verification"}
        else:
            shutil.copy2(sandbox_path, live_path)
            live_after = load_json(live_path)
            state["apply_relay_result"] = {
                "status": "applied",
                "target_id": case_input["target_id"],
                "applied_result_id": state["approved_result_id"],
                "applied_result_hash": sha256_json(live_after),
                "preconditions": preconditions,
            }
            verification = "verified_match" if live_after == replayed else "drift_detected"
            state["post_apply_verification"] = {
                "status": verification,
                "live_hash": sha256_json(live_after),
                "expected_hash": state["simulation_result_hash"],
            }
        state["audit_trail"].extend(["06 Explicit Apply Relay", "07 Post-Apply Verification"])
    else:
        state["apply_relay_result"] = {"status": "not_applied"}
        state["post_apply_verification"] = {"status": "not_run"}

    state["workflow_status"] = "completed"
    return _finalize(state, source_path, source_before, run_dir)


def _finalize(
    state: dict[str, Any], source_path: Path, source_before: bytes, run_dir: Path
) -> dict[str, Any]:
    if source_path.read_bytes() != source_before:
        raise RuntimeError("sample source was mutated")
    state["current_stage"] = "08-final-result-locked"
    state["completed_stage"] = "08-final-result-locked"
    state["destination_stage"] = "end"
    state["audit_trail"].append("08 Final Result Locked")
    final_result = {
        "case_id": state["case_id"],
        "run_id": state["run_id"],
        "snapshot_ref": {"hash": state["snapshot_hash"]},
        "handoff_ref": {"hash": sha256_json(state["handoff_statement"])},
        "package_ref": {"hash": sha256_json(state["pre_simulation_package"])},
        "simulation_result_ref": {
            "id": state["simulation_result"].get("result_id", ""),
            "hash": state["simulation_result_hash"],
        },
        "proof_result": state["replay_proof"],
        "user_decision": state["user_decision"],
        "apply_status": state["apply_relay_result"].get("status", "not_run"),
        "post_apply_verification": state["post_apply_verification"],
        "unresolved_items": state["handoff_statement"].get("unresolved_items", []),
        "drift_status": state["post_apply_verification"].get("status", "not_run"),
        "provenance": {"engine": "nextflow_demo.py", "workflow": "NextFlow-Demo"},
        "locked": True,
    }
    state["final_result"] = final_result
    state["final_result_hash"] = sha256_json(final_result)
    write_json(run_dir / "workflow-state.json", state)
    write_json(run_dir / "final-result.json", final_result)
    return {"state": state, "run_dir": str(run_dir)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the deterministic NextFlow sample case")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--decision", choices=["apply", "cancel", "preserve_for_later"], default="apply"
    )
    parser.add_argument(
        "--scenario", choices=["happy_path", "readiness_rejected", "simulation_failure"], default="happy_path"
    )
    parser.add_argument("--run-root", type=Path)
    args = parser.parse_args()
    result = run_demo(
        args.repo_root.resolve(),
        user_decision=args.decision,
        scenario=args.scenario,
        run_root=args.run_root,
    )
    print(json.dumps({"run_dir": result["run_dir"], "final_result": result["state"]["final_result"]}))
    return 0 if result["state"]["workflow_status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
