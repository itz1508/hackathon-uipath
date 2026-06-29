# Modified: 2026-06-24T06:57:46Z
"""
Compute SHA-256 hashes for pipeline source files.

This script computes SHA-256 hashes for the 8 pipeline source files
and outputs them to tests/source_hashes.json for later integrity comparison.

Usage (from pipeline/ directory):
    python tests/compute_source_hashes.py

Requirements: 7.1, 7.5
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


def compute_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def main() -> int:
    # Determine the project root (parent of tests/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    hashes = {}
    missing = []

    for filename in PIPELINE_SOURCE_FILES:
        filepath = os.path.join(project_root, filename)
        if not os.path.isfile(filepath):
            missing.append(filename)
            continue
        hashes[filename] = compute_sha256(filepath)

    if missing:
        print(f"ERROR: Missing pipeline source files: {missing}", file=sys.stderr)
        return 1

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "description": "Pre-deployment SHA-256 hashes for pipeline source files",
        "hashes": hashes,
    }

    output_path = os.path.join(script_dir, "source_hashes.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Computed SHA-256 hashes for {len(hashes)} pipeline source files.")
    print(f"Output written to: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
