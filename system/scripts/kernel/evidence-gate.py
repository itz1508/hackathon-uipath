"""Evidence Gate — nothing enters proof.ledger.json unless evidence exists.

Rule: Every proof run must have at least one evidence artifact that exists on disk.
"""
import json
import sys
from pathlib import Path

KERNEL_DIR = Path(__file__).resolve().parent.parent.parent / "audisor-kernel"
PROJECT_ROOT = KERNEL_DIR.parent


def check_evidence():
    proof_path = KERNEL_DIR / "proof.ledger.json"
    if not proof_path.exists():
        return {"status": "FAIL", "reason": "proof.ledger.json not found"}

    with open(proof_path, "r", encoding="utf-8") as f:
        proof = json.load(f)

    results = []

    for run in proof.get("runs", []):
        run_id = run.get("runId", "unknown")
        evidence_list = run.get("proof", [])

        if not evidence_list:
            results.append({
                "runId": run_id,
                "status": "REJECTED",
                "reason": "No proof artifacts listed"
            })
            continue

        all_found = True
        missing = []
        for artifact in evidence_list:
            artifact_path = PROJECT_ROOT / artifact
            if not artifact_path.exists():
                all_found = False
                missing.append(str(artifact))

        if all_found:
            results.append({
                "runId": run_id,
                "status": "VERIFIED",
                "evidence": evidence_list
            })
        else:
            results.append({
                "runId": run_id,
                "status": "REJECTED",
                "reason": f"Missing proof artifacts: {missing}"
            })

    # Check unproven claims
    for claim in proof.get("unproven", []):
        results.append({
            "claim": claim.get("claim", "unknown"),
            "status": "UNPROVEN",
            "reason": claim.get("reason", "No evidence")
        })

    overall = "PASS" if all(r.get("status") == "VERIFIED" for r in results if "runId" in r) else "INCOMPLETE"
    return {"status": overall, "results": results}


if __name__ == "__main__":
    result = check_evidence()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "PASS" else 1)
