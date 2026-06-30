# Modified: 2026-06-24T06:57:46Z
"""
Deployment Guard — Pipeline Integrity Verification.

This script verifies that no pipeline source files were modified during
the deployment process. It loads pre-deployment SHA-256 hashes from
source_hashes.json, recomputes current hashes, and reports any differences.

Additionally, it verifies that only allowed files (pyproject.toml,
entry-points.json, and .uipath/*) were modified during deployment.

Usage (from pipeline/ directory):
    python tests/deployment_guard.py

Exit codes:
    0 — All pipeline source file hashes match (integrity preserved)
    1 — One or more pipeline source file hashes differ (integrity violated)

Requirements: 7.1, 7.3, 7.4, 7.5
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

PIPELINE_SOURCE_FILES = [
    "main.py",
    "pre_simulation.py",
    "simulation.py",
    "inspection.py",
    "relay.py",
    "final_output.py",
    "scanner.py",
    "models.py",
]

# Files that are allowed to be modified during deployment
ALLOWED_MODIFIED_FILES = {
    "pyproject.toml",
    "entry-points.json",
}

# Directory prefix for allowed modifications
ALLOWED_MODIFIED_DIRS = [
    ".uipath/",
    ".uipath\\",
]


def compute_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def load_source_hashes(hashes_path: str) -> dict:
    """Load pre-deployment hashes from source_hashes.json."""
    with open(hashes_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def is_allowed_modification(filepath: str) -> bool:
    """Check if a file is in the allowed modification set."""
    basename = os.path.basename(filepath)
    if basename in ALLOWED_MODIFIED_FILES:
        return True
    for prefix in ALLOWED_MODIFIED_DIRS:
        if filepath.startswith(prefix) or f"/{prefix}" in filepath:
            return True
    return False


def main() -> int:
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"Deployment Guard — Pipeline Integrity Check")
    print(f"Timestamp: {timestamp}")
    print(f"{'=' * 60}")

    # Determine paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    hashes_path = os.path.join(script_dir, "source_hashes.json")

    # Step 1: Load pre-deployment hashes
    if not os.path.isfile(hashes_path):
        print(f"ERROR: source_hashes.json not found at: {hashes_path}", file=sys.stderr)
        print("Run compute_source_hashes.py first to establish baseline.", file=sys.stderr)
        return 1

    data = load_source_hashes(hashes_path)
    stored_hashes = data.get("hashes", {})
    baseline_timestamp = data.get("timestamp", "unknown")

    print(f"\nBaseline timestamp: {baseline_timestamp}")
    print(f"Pipeline source files to verify: {len(PIPELINE_SOURCE_FILES)}")
    print()

    # Step 2: Recompute current hashes and compare
    differences = []
    missing_files = []

    for filename in PIPELINE_SOURCE_FILES:
        filepath = os.path.join(project_root, filename)

        if not os.path.isfile(filepath):
            missing_files.append(filename)
            print(f"  MISSING: {filename}")
            continue

        current_hash = compute_sha256(filepath)
        stored_hash = stored_hashes.get(filename)

        if stored_hash is None:
            print(f"  NO BASELINE: {filename} (not in source_hashes.json)")
            differences.append(filename)
        elif current_hash != stored_hash:
            print(f"  MODIFIED: {filename}")
            print(f"    Before: {stored_hash}")
            print(f"    After:  {current_hash}")
            differences.append(filename)
        else:
            print(f"  OK: {filename}")

    # Step 3: Verify modification scope
    print(f"\n{'=' * 60}")
    print("Modification Scope Verification")
    print(f"{'=' * 60}")
    print(f"Allowed modifications: pyproject.toml, entry-points.json, .uipath/*")
    print()

    # Check that pipeline source files are NOT in the modified set
    unauthorized_modifications = []
    for filename in differences:
        if not is_allowed_modification(filename):
            unauthorized_modifications.append(filename)

    if unauthorized_modifications:
        print(f"  UNAUTHORIZED modifications detected:")
        for f in unauthorized_modifications:
            print(f"    - {f}")
    else:
        print(f"  All modifications within allowed scope.")

    # Step 4: Summary and exit
    print(f"\n{'=' * 60}")
    print("Summary")
    print(f"{'=' * 60}")

    has_errors = False

    if missing_files:
        print(f"  Missing files: {missing_files}")
        has_errors = True

    if differences:
        print(f"  Modified pipeline source files: {differences}")
        print(f"  INTEGRITY VIOLATION: Pipeline source files have been altered!")
        has_errors = True
    else:
        print(f"  All {len(PIPELINE_SOURCE_FILES)} pipeline source files are byte-identical.")
        print(f"  Pipeline integrity: PRESERVED")

    if has_errors:
        print(f"\nRESULT: FAIL — Deployment guard detected integrity violations.")
        return 1
    else:
        print(f"\nRESULT: PASS — Pipeline integrity preserved.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
