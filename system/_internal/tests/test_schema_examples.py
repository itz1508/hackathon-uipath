import json

import pytest
from jsonschema import Draft202012Validator

from tests._support import EXAMPLES, FIXTURES, ROOT, SCHEMAS, contract_errors, load_json, materialize_fixture, schema_errors


def test_every_json_file_parses():
    # Scan only project-owned JSON. TheOneShot/ and downloaded desktop-operator
    # material are preservation boundaries, not implementation inputs.
    included_roots = [ROOT / "uipath", ROOT / "workflow", ROOT / "contracts", ROOT / "cases", ROOT / "maestro"]
    for included_root in included_roots:
        if not included_root.exists():
            continue
        for path in included_root.rglob("*.json"):
            if ".local" in path.parts or "dist" in path.parts:
                continue
            with path.open(encoding="utf-8") as stream:
                json.load(stream)


def test_every_schema_is_valid_draft_2020_12():
    for path in SCHEMAS.glob("*.schema.json"):
        Draft202012Validator.check_schema(load_json(path))


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.json")), ids=lambda path: path.name)
def test_accepted_example_validates(path):
    document = load_json(path)
    assert schema_errors(document) == []
    assert contract_errors(document) == []


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.json")), ids=lambda path: path.name)
def test_invalid_fixture_is_rejected(path):
    fixture, document = materialize_fixture(path)
    errors = schema_errors(document) + contract_errors(document)
    assert errors, fixture["expected_rule"]
