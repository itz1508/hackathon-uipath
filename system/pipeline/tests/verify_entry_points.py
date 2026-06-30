# Modified: 2026-06-24T06:57:46Z
"""
Entry-points schema comparison script.

Compares the pre-rename entry-points.json snapshot against the current
entry-points.json to verify that the input/output JSON Schemas remain
structurally equivalent after package rename and `uipath init`.

Checks: property names, property types, required arrays, enum values, title fields.
Exit 0 if schemas are equivalent, exit 1 if any differences found.

Requirements: 8.3, 8.4, 8.5
"""

import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict:
    """Load and parse a JSON file."""
    if not path.exists():
        print(f"ERROR: File not found: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_enum_values(
    pre_enums: list | None, current_enums: list | None, path: str
) -> list[str]:
    """Compare enum value lists."""
    diffs = []
    if pre_enums is None and current_enums is None:
        return diffs
    if pre_enums is None and current_enums is not None:
        diffs.append(f"  ADDED enum at {path}: {current_enums}")
        return diffs
    if pre_enums is not None and current_enums is None:
        diffs.append(f"  REMOVED enum at {path}")
        return diffs
    pre_set = set(str(v) for v in pre_enums)
    cur_set = set(str(v) for v in current_enums)
    added = cur_set - pre_set
    removed = pre_set - cur_set
    if added:
        diffs.append(f"  ADDED enum values at {path}: {sorted(added)}")
    if removed:
        diffs.append(f"  REMOVED enum values at {path}: {sorted(removed)}")
    return diffs


def compare_properties(
    pre_props: dict[str, Any],
    current_props: dict[str, Any],
    schema_path: str,
) -> list[str]:
    """Compare property definitions between two schemas recursively."""
    diffs = []

    pre_names = set(pre_props.keys())
    cur_names = set(current_props.keys())

    # Check for added/removed properties
    added = cur_names - pre_names
    removed = pre_names - cur_names

    if added:
        for name in sorted(added):
            diffs.append(f"  ADDED property: {schema_path}.{name}")

    if removed:
        for name in sorted(removed):
            diffs.append(f"  REMOVED property: {schema_path}.{name}")

    # Compare shared properties
    shared = pre_names & cur_names
    for name in sorted(shared):
        prop_path = f"{schema_path}.{name}"
        pre_prop = pre_props[name]
        cur_prop = current_props[name]

        # Compare type
        pre_type = pre_prop.get("type")
        cur_type = cur_prop.get("type")
        if pre_type != cur_type:
            diffs.append(
                f"  TYPE CHANGED at {prop_path}: '{pre_type}' -> '{cur_type}'"
            )

        # Compare title
        pre_title = pre_prop.get("title")
        cur_title = cur_prop.get("title")
        if pre_title != cur_title:
            diffs.append(
                f"  TITLE CHANGED at {prop_path}: '{pre_title}' -> '{cur_title}'"
            )

        # Compare enum values
        diffs.extend(
            compare_enum_values(
                pre_prop.get("enum"), cur_prop.get("enum"), prop_path
            )
        )

        # Recurse into nested properties (for objects like branch_status, action_center_fallback)
        pre_nested = pre_prop.get("properties")
        cur_nested = cur_prop.get("properties")
        if pre_nested or cur_nested:
            diffs.extend(
                compare_properties(
                    pre_nested or {},
                    cur_nested or {},
                    prop_path,
                )
            )

        # Recurse into items (for arrays like phase_results)
        pre_items = pre_prop.get("items")
        cur_items = cur_prop.get("items")
        if isinstance(pre_items, dict) and isinstance(cur_items, dict):
            pre_item_props = pre_items.get("properties", {})
            cur_item_props = cur_items.get("properties", {})
            if pre_item_props or cur_item_props:
                diffs.extend(
                    compare_properties(
                        pre_item_props,
                        cur_item_props,
                        f"{prop_path}[items]",
                    )
                )
            # Compare required in items
            pre_item_req = set(pre_items.get("required", []))
            cur_item_req = set(cur_items.get("required", []))
            if pre_item_req != cur_item_req:
                added_req = cur_item_req - pre_item_req
                removed_req = pre_item_req - cur_item_req
                if added_req:
                    diffs.append(
                        f"  ADDED required in {prop_path}[items]: {sorted(added_req)}"
                    )
                if removed_req:
                    diffs.append(
                        f"  REMOVED required in {prop_path}[items]: {sorted(removed_req)}"
                    )

    return diffs


def compare_required(
    pre_required: list[str], current_required: list[str], schema_path: str
) -> list[str]:
    """Compare required field arrays."""
    diffs = []
    pre_set = set(pre_required)
    cur_set = set(current_required)

    added = cur_set - pre_set
    removed = pre_set - cur_set

    if added:
        diffs.append(
            f"  ADDED required fields in {schema_path}: {sorted(added)}"
        )
    if removed:
        diffs.append(
            f"  REMOVED required fields in {schema_path}: {sorted(removed)}"
        )

    return diffs


def compare_schema(pre_schema: dict, current_schema: dict, name: str) -> list[str]:
    """Compare a single input or output schema."""
    diffs = []

    # Compare title
    pre_title = pre_schema.get("title")
    cur_title = current_schema.get("title")
    if pre_title != cur_title:
        diffs.append(f"  TITLE CHANGED in {name}: '{pre_title}' -> '{cur_title}'")

    # Compare top-level type
    pre_type = pre_schema.get("type")
    cur_type = current_schema.get("type")
    if pre_type != cur_type:
        diffs.append(f"  TYPE CHANGED in {name}: '{pre_type}' -> '{cur_type}'")

    # Compare properties
    pre_props = pre_schema.get("properties", {})
    cur_props = current_schema.get("properties", {})
    diffs.extend(compare_properties(pre_props, cur_props, name))

    # Compare required arrays
    pre_required = pre_schema.get("required", [])
    cur_required = current_schema.get("required", [])
    diffs.extend(compare_required(pre_required, cur_required, name))

    return diffs


def main() -> int:
    """Main comparison logic."""
    # Resolve paths relative to pipeline/ directory
    script_dir = Path(__file__).parent
    workflow_control_dir = script_dir.parent

    pre_rename_path = script_dir / "entry-points.pre-rename.json"
    current_path = workflow_control_dir / "entry-points.json"

    print("=" * 60)
    print("Entry-Points Schema Comparison")
    print("=" * 60)
    print(f"  Pre-rename: {pre_rename_path}")
    print(f"  Current:    {current_path}")
    print()

    pre_data = load_json(pre_rename_path)
    current_data = load_json(current_path)

    # Extract entry points arrays
    pre_entries = pre_data.get("entryPoints", [])
    cur_entries = current_data.get("entryPoints", [])

    if len(pre_entries) != len(cur_entries):
        print(
            f"FAIL: Entry point count differs: "
            f"pre-rename={len(pre_entries)}, current={len(cur_entries)}"
        )
        return 1

    all_diffs: list[str] = []

    for i, (pre_ep, cur_ep) in enumerate(zip(pre_entries, cur_entries)):
        ep_id = pre_ep.get("filePath", f"entry[{i}]")

        # Compare input schema
        pre_input = pre_ep.get("input", {})
        cur_input = cur_ep.get("input", {})
        input_diffs = compare_schema(pre_input, cur_input, f"{ep_id}/input")
        all_diffs.extend(input_diffs)

        # Compare output schema
        pre_output = pre_ep.get("output", {})
        cur_output = cur_ep.get("output", {})
        output_diffs = compare_schema(pre_output, cur_output, f"{ep_id}/output")
        all_diffs.extend(output_diffs)

    if all_diffs:
        print(f"FAIL: Found {len(all_diffs)} schema difference(s):\n")
        for diff in all_diffs:
            print(diff)
        print()
        print("Action required: Restore the original entry-points.json and")
        print("investigate the discrepancy before proceeding with pack.")
        return 1

    print("PASS: Input and output schemas are equivalent.")
    print("  - Property names: MATCH")
    print("  - Property types: MATCH")
    print("  - Required arrays: MATCH")
    print("  - Enum values: MATCH")
    print("  - Title fields: MATCH")
    return 0


if __name__ == "__main__":
    sys.exit(main())
