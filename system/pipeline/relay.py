"""Phase 5 — Relay: Present inspected result, execute user decision.

Relay receives the complete Inspection output and constructs a user-facing
packet showing: resolved items, unresolved items, before/after diff, and
available decisions (apply / cancel).

Critical rules:
- NEVER rerun Scan, Pre-Simulation, or Simulation.
- NEVER modify the real target while awaiting user decision.
- NEVER silently remove unresolved items.
- Apply releases the exact inspected candidate (no re-mutation).
- Cancel restores/preserves the original snapshot (candidate NOT released).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# ──────────────────────────────────────────────
# Relay Dataclasses
# ──────────────────────────────────────────────


@dataclass
class RelayInput:
    """Input for the Relay phase."""
    case_id: str
    snapshot_id: str
    snapshot_path: str
    snapshot_hash: str
    inspection_id: str
    inspection_hash: str
    candidate_path: str
    candidate_hash: str
    resolved_items: list[dict[str, Any]] = field(default_factory=list)
    unresolved_items: list[dict[str, Any]] = field(default_factory=list)
    item_traces: list[dict[str, Any]] = field(default_factory=list)
    target_path: str = ""
    decision: str = ""  # "" | "apply" | "cancel"


@dataclass
class RelayResolvedDetail:
    """Detail record for a resolved item in the Relay packet."""
    item_id: str
    status: str
    summary: str = ""
    diff_refs: list[str] = field(default_factory=list)


@dataclass
class RelayUnresolvedDetail:
    """Detail record for an unresolved item in the Relay packet."""
    item_id: str
    status: str
    why_unresolved: str = ""
    what_was_tried: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


@dataclass
class ApplyResult:
    """Result of an apply decision."""
    decision: str = "apply"
    operation: str = "release_candidate_to_target"
    simulation_rerun: bool = False  # Always False — never rerun
    target_hash_before: str = ""
    target_hash_after: str = ""
    expected_candidate_hash: str = ""
    release_verified: bool = False


@dataclass
class CancelResult:
    """Result of a cancel decision."""
    decision: str = "cancel"
    operation: str = "restore_snapshot_to_target"
    candidate_released: bool = False  # Always False — candidate NOT released
    target_hash_after: str = ""
    expected_snapshot_hash: str = ""
    restore_verified: bool = False


@dataclass
class RelayError:
    """Error encountered during Relay."""
    code: str
    message: str


@dataclass
class RelayResult:
    """Complete Relay result."""
    relay_id: str
    case_id: str
    inspection_id: str
    inspection_hash_expected: str = ""
    inspection_hash_actual: str = ""
    inspection_hash_verified: bool = False
    snapshot_id: str = ""
    snapshot_hash: str = ""
    candidate_hash: str = ""
    resolved: list[RelayResolvedDetail] = field(default_factory=list)
    unresolved: list[RelayUnresolvedDetail] = field(default_factory=list)
    before_after_diff: dict[str, Any] = field(default_factory=dict)
    decision_status: str = "awaiting_user"  # "awaiting_user" | "applied" | "cancelled" | "rejected"
    available_actions: list[str] = field(default_factory=lambda: ["apply", "cancel"])
    apply_result: ApplyResult | None = None
    cancel_result: CancelResult | None = None
    errors: list[RelayError] = field(default_factory=list)
    backward_traces: list[dict[str, Any]] = field(default_factory=list)


# ──────────────────────────────────────────────
# Hash Utilities
# ──────────────────────────────────────────────


def _hash_directory(dir_path: str) -> str:
    """Compute a combined SHA-256 hash of all files in a directory.

    Uses the same algorithm as inspection.py._hash_candidate:
    hash(relative_path + file_content) for each file in sorted order.
    """
    if not dir_path or not Path(dir_path).exists():
        return ""

    hasher = hashlib.sha256()
    target = Path(dir_path)

    for root, _dirs, files in sorted(os.walk(target)):
        for filename in sorted(files):
            filepath = Path(root) / filename
            relative = str(filepath.relative_to(target)).replace(os.sep, "/")
            hasher.update(relative.encode())
            with open(filepath, "rb") as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)

    return hasher.hexdigest()


def _compute_inspection_hash(
    resolved: list[str],
    unresolved: list[str],
    candidate_hash: str,
    snapshot_id: str,
) -> str:
    """Compute the inspection hash using the same algorithm as inspection.py."""
    data = json.dumps({
        "resolved": sorted(resolved),
        "unresolved": sorted(unresolved),
        "candidate_hash": candidate_hash,
        "snapshot_id": snapshot_id,
    }, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()


# ──────────────────────────────────────────────
# Core Relay Functions
# ──────────────────────────────────────────────


def verify_inspection_hash(
    expected: str,
    candidate_path: str,
    snapshot_id: str,
    resolved_items: list[dict[str, Any]],
    unresolved_items: list[dict[str, Any]],
) -> tuple[bool, str]:
    """Verify the inspection hash by recomputing from components.

    Returns (verified: bool, actual_hash: str).
    """
    # Extract item IDs for hash computation (same as inspection.py uses)
    resolved_ids = [item.get("item_id", "") for item in resolved_items]
    unresolved_ids = [item.get("item_id", "") for item in unresolved_items]

    # Compute candidate hash from directory
    candidate_hash = _hash_directory(candidate_path) if candidate_path else ""

    actual_hash = _compute_inspection_hash(
        resolved_ids, unresolved_ids, candidate_hash, snapshot_id
    )

    return (actual_hash == expected, actual_hash)


def build_before_after_diff(snapshot_path: str, candidate_path: str) -> dict[str, Any]:
    """Compare snapshot_path vs candidate_path file by file.

    Returns a diff dict with:
    - added: files in candidate but not in snapshot
    - removed: files in snapshot but not in candidate
    - modified: files present in both but with different content
    - unchanged: files identical in both
    """
    diff: dict[str, Any] = {
        "added": [],
        "removed": [],
        "modified": [],
        "unchanged": [],
    }

    if not snapshot_path or not Path(snapshot_path).exists():
        return diff
    if not candidate_path or not Path(candidate_path).exists():
        return diff

    # Get all relative paths from both directories
    snapshot_files = _get_relative_files(snapshot_path)
    candidate_files = _get_relative_files(candidate_path)

    snapshot_set = set(snapshot_files.keys())
    candidate_set = set(candidate_files.keys())

    # Added: in candidate but not snapshot
    for rel in sorted(candidate_set - snapshot_set):
        diff["added"].append(rel)

    # Removed: in snapshot but not candidate
    for rel in sorted(snapshot_set - candidate_set):
        diff["removed"].append(rel)

    # Modified or unchanged: in both
    for rel in sorted(snapshot_set & candidate_set):
        if snapshot_files[rel] != candidate_files[rel]:
            diff["modified"].append(rel)
        else:
            diff["unchanged"].append(rel)

    return diff


def _get_relative_files(dir_path: str) -> dict[str, str]:
    """Get a mapping of relative_path -> sha256 for all files in a directory."""
    result: dict[str, str] = {}
    target = Path(dir_path)

    if not target.exists():
        return result

    for root, _dirs, files in os.walk(target):
        for filename in sorted(files):
            filepath = Path(root) / filename
            relative = str(filepath.relative_to(target)).replace(os.sep, "/")
            sha256 = hashlib.sha256()
            with open(filepath, "rb") as f:
                while chunk := f.read(8192):
                    sha256.update(chunk)
            result[relative] = sha256.hexdigest()

    return result


def execute_apply(
    candidate_path: str,
    target_path: str,
    expected_candidate_hash: str,
) -> ApplyResult:
    """Apply: copy candidate to target, verify hash matches.

    No simulation rerun. Release the exact inspected candidate.
    """
    result = ApplyResult(
        expected_candidate_hash=expected_candidate_hash,
    )

    # Hash target before mutation
    result.target_hash_before = _hash_directory(target_path) if target_path and Path(target_path).exists() else ""

    # Copy candidate to target
    target = Path(target_path)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(candidate_path, target_path)

    # Hash target after mutation
    result.target_hash_after = _hash_directory(target_path)

    # Verify: final target hash must equal expected candidate hash
    result.release_verified = (result.target_hash_after == expected_candidate_hash)

    return result


def execute_cancel(
    snapshot_path: str,
    target_path: str,
    expected_snapshot_hash: str,
) -> CancelResult:
    """Cancel: restore snapshot to target, candidate NOT released.

    Candidate is preserved but not applied. Target is restored to snapshot state.
    """
    result = CancelResult(
        expected_snapshot_hash=expected_snapshot_hash,
    )

    # Copy snapshot to target
    target = Path(target_path)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(snapshot_path, target_path)

    # Hash target after restoration
    result.target_hash_after = _hash_directory(target_path)

    # Verify: final target hash must equal expected snapshot hash
    result.restore_verified = (result.target_hash_after == expected_snapshot_hash)

    return result


# ──────────────────────────────────────────────
# Main Relay Entry Point
# ──────────────────────────────────────────────


def run_relay(inp: RelayInput) -> RelayResult:
    """Execute Phase 5 Relay.

    1. Verify inspection hash — reject if mismatched.
    2. Build resolved/unresolved packet (never drop unresolved items).
    3. Compute before/after diff.
    4. If decision provided, execute apply or cancel.
    5. Retain backward traces.

    Critical: NEVER rerun Scan/PreSimulation/Simulation.
    Critical: NEVER modify real target while awaiting decision.
    Critical: NEVER silently remove unresolved items.
    """
    relay_id = f"relay-{uuid.uuid4().hex[:8]}"
    errors: list[RelayError] = []

    # Step 1: Verify inspection hash
    hash_verified, hash_actual = verify_inspection_hash(
        expected=inp.inspection_hash,
        candidate_path=inp.candidate_path,
        snapshot_id=inp.snapshot_id,
        resolved_items=inp.resolved_items,
        unresolved_items=inp.unresolved_items,
    )

    # If hash mismatch, reject immediately
    if not hash_verified:
        errors.append(RelayError(
            code="INSPECTION_HASH_MISMATCH",
            message=(
                f"Inspection hash mismatch. Expected: {inp.inspection_hash[:16]}... "
                f"Actual: {hash_actual[:16]}..."
            ),
        ))
        return RelayResult(
            relay_id=relay_id,
            case_id=inp.case_id,
            inspection_id=inp.inspection_id,
            inspection_hash_expected=inp.inspection_hash,
            inspection_hash_actual=hash_actual,
            inspection_hash_verified=False,
            snapshot_id=inp.snapshot_id,
            snapshot_hash=inp.snapshot_hash,
            candidate_hash=inp.candidate_hash,
            decision_status="rejected",
            available_actions=[],
            errors=errors,
            backward_traces=inp.item_traces,
        )

    # Step 2: Build resolved/unresolved detail packets
    resolved_details: list[RelayResolvedDetail] = []
    for item in inp.resolved_items:
        resolved_details.append(RelayResolvedDetail(
            item_id=item.get("item_id", ""),
            status=item.get("status", "resolved"),
            summary=item.get("summary", ""),
            diff_refs=item.get("diff_refs", []),
        ))

    unresolved_details: list[RelayUnresolvedDetail] = []
    for item in inp.unresolved_items:
        unresolved_details.append(RelayUnresolvedDetail(
            item_id=item.get("item_id", ""),
            status=item.get("status", "unresolved"),
            why_unresolved=item.get("why_unresolved", ""),
            what_was_tried=item.get("what_was_tried", []),
            missing_information=item.get("missing_information", []),
            next_steps=item.get("next_steps", []),
        ))

    # Step 3: Build before/after diff
    before_after_diff = build_before_after_diff(inp.snapshot_path, inp.candidate_path)

    # Step 4: Determine decision status and execute if decision provided
    decision_status = "awaiting_user"
    apply_result: ApplyResult | None = None
    cancel_result: CancelResult | None = None

    if inp.decision == "apply":
        apply_result = execute_apply(
            candidate_path=inp.candidate_path,
            target_path=inp.target_path,
            expected_candidate_hash=inp.candidate_hash,
        )
        decision_status = "applied"
        if not apply_result.release_verified:
            errors.append(RelayError(
                code="APPLY_HASH_MISMATCH",
                message="Target hash after apply does not match expected candidate hash.",
            ))

    elif inp.decision == "cancel":
        cancel_result = execute_cancel(
            snapshot_path=inp.snapshot_path,
            target_path=inp.target_path,
            expected_snapshot_hash=inp.snapshot_hash,
        )
        decision_status = "cancelled"
        if not cancel_result.restore_verified:
            errors.append(RelayError(
                code="CANCEL_HASH_MISMATCH",
                message="Target hash after cancel does not match expected snapshot hash.",
            ))

    # Step 5: Construct result with backward traces retained
    return RelayResult(
        relay_id=relay_id,
        case_id=inp.case_id,
        inspection_id=inp.inspection_id,
        inspection_hash_expected=inp.inspection_hash,
        inspection_hash_actual=hash_actual,
        inspection_hash_verified=True,
        snapshot_id=inp.snapshot_id,
        snapshot_hash=inp.snapshot_hash,
        candidate_hash=inp.candidate_hash,
        resolved=resolved_details,
        unresolved=unresolved_details,
        before_after_diff=before_after_diff,
        decision_status=decision_status,
        available_actions=["apply", "cancel"] if decision_status == "awaiting_user" else [],
        apply_result=apply_result,
        cancel_result=cancel_result,
        errors=errors,
        backward_traces=inp.item_traces,
    )
