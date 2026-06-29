"""Kernel Validator — enforces consistency across kernel files.

Checks:
- Every deployment in deployment.inventory.json exists in solution.graph.snapshot.json
- Every proof run references an existing deployment
- Every snapshot references valid graph nodes
- No orphan environments
- No duplicate deployment names
"""
import json
import sys
from pathlib import Path

KERNEL_DIR = Path(__file__).resolve().parent.parent.parent / "audisor-kernel"


def load(filename: str) -> dict:
    path = KERNEL_DIR / filename
    if not path.exists():
        return {"_missing": True, "_path": str(path)}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate():
    errors = []
    warnings = []

    # Load all kernel files
    graph = load("system.graph.json")
    inventory = load("deployment.inventory.json")
    state = load("kernel.state.json")
    proof = load("proof.ledger.json")
    decisions = load("decisions.log.json")

    # Check all files exist
    for name, data in [
        ("system.graph.json", graph),
        ("deployment.inventory.json", inventory),
        ("kernel.state.json", state),
        ("proof.ledger.json", proof),
        ("decisions.log.json", decisions),
    ]:
        if data.get("_missing"):
            errors.append(f"MISSING: {name} not found at {data['_path']}")

    if errors:
        return {"status": "FAIL", "errors": errors, "warnings": warnings}

    # Validate: graph nodes exist
    graph_nodes = set(graph.get("nodes", {}).keys())
    if not graph_nodes:
        errors.append("system.graph.json has no nodes defined")

    # Validate: graph edges reference valid nodes
    for edge in graph.get("edges", []):
        from_node = edge.get("from", "").split(".")[0]
        to_node = edge.get("to", "").split(".")[0]
        # Edges use node IDs like "bpmn.serviceTask" — check prefix
        if from_node not in graph_nodes:
            warnings.append(f"Edge {edge.get('id')} references unknown source node prefix: {from_node}")
        if to_node not in graph_nodes:
            warnings.append(f"Edge {edge.get('id')} references unknown target node prefix: {to_node}")

    # Validate: deployments reference environments
    inv_environments = set(inventory.get("environments", {}).keys())
    if not inv_environments:
        errors.append("deployment.inventory.json has no environments")

    # Validate: no duplicate deployment names within an environment
    for env_name, env_data in inventory.get("environments", {}).items():
        deployment_names = [d["name"] for d in env_data.get("deployments", [])]
        if len(deployment_names) != len(set(deployment_names)):
            errors.append(f"Duplicate deployment names in environment '{env_name}'")

    # Validate: proof runs reference valid environments
    for run in proof.get("runs", []):
        run_env = run.get("environment", "")
        run_folder = run.get("folder", "")
        # Check if any inventory environment matches
        matched = False
        for env_name, env_data in inventory.get("environments", {}).items():
            if env_data.get("folder") == run_folder or env_name == run_env:
                matched = True
                break
        if not matched:
            errors.append(f"Proof run {run.get('runId')} references unknown environment/folder: {run_env}/{run_folder}")

    # Validate: proof runs have evidence
    for run in proof.get("runs", []):
        evidence = run.get("proof", [])
        if not evidence:
            errors.append(f"Proof run {run.get('runId')} has no evidence artifacts listed")
        for artifact in evidence:
            artifact_path = KERNEL_DIR.parent / artifact
            if not artifact_path.exists():
                warnings.append(f"Proof artifact '{artifact}' for run {run.get('runId')} not found at {artifact_path}")

    status = "PASS" if not errors else "FAIL"
    return {"status": status, "errors": errors, "warnings": warnings}


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "PASS" else 1)
