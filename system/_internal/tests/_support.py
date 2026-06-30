import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "uipath" / "schemas"
EXAMPLES = ROOT / "workflow" / "examples"
FIXTURES = ROOT / "workflow" / "invalid-fixtures"


def load_json(path: Path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def schema_for(document: dict):
    schema_ref = document.get("$schema_ref")
    if not schema_ref:
        raise AssertionError("Example does not declare $schema_ref")
    return load_json((EXAMPLES / schema_ref).resolve())


def schema_errors(document: dict):
    return list(Draft202012Validator(schema_for(document)).iter_errors(document))


def contract_errors(document: dict):
    errors = []
    auto_dependency = document.get("auto_dependency")
    if not isinstance(auto_dependency, dict):
        return errors

    dependencies = auto_dependency.get("dependencies", [])
    ids = [item.get("dependency_id") for item in dependencies]
    if len(ids) != len(set(ids)):
        errors.append("dependency ids are not unique")

    unresolved = set(auto_dependency.get("unresolved_dependencies", []))
    undeclared = unresolved - set(ids)
    if undeclared:
        errors.append(f"unresolved dependency ids are undeclared: {sorted(undeclared)}")

    by_id = {item.get("dependency_id"): item for item in dependencies}
    for dependency_id in unresolved & set(ids):
        if by_id[dependency_id].get("resulting_status") == "available":
            errors.append(f"available dependency is unresolved: {dependency_id}")

    for dependency in dependencies:
        if dependency.get("required") and dependency.get("resulting_status") != "available":
            if dependency.get("dependency_id") not in unresolved:
                errors.append(f"required unavailable dependency is not unresolved: {dependency.get('dependency_id')}")
    return errors


def set_pointer(document: dict, pointer: str, value, add: bool = False):
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.strip("/").split("/")]
    cursor = document
    for part in parts[:-1]:
        cursor = cursor[int(part)] if isinstance(cursor, list) else cursor[part]
    last = parts[-1]
    if isinstance(cursor, list):
        cursor[int(last)] = value
    else:
        cursor[last] = value


def materialize_fixture(fixture_path: Path):
    fixture = load_json(fixture_path)
    document = copy.deepcopy(load_json(EXAMPLES / fixture["base"]))
    for operation in fixture["operations"]:
        if operation["op"] in {"replace", "add"}:
            set_pointer(document, operation["path"], operation["value"], operation["op"] == "add")
        elif operation["op"] == "duplicate_dependency":
            dependencies = document["auto_dependency"]["dependencies"]
            dependencies.append(copy.deepcopy(dependencies[operation["index"]]))
        else:
            raise AssertionError(f"Unsupported fixture operation: {operation['op']}")
    return fixture, document
