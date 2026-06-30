# Modified: 2026-06-29T14:30:00Z
"""Phase 4 — Inspection: Convergence point for all paths.

Inspection waits for ALL expected items before completing.
It must receive and account for:
- Successful Simulation results
- Simulation failures and their isolation reports
- Pre-Simulation isolated items
- Fixable items that were researched, rescored, and rejoined
- Items determined not currently fixable

Inspection must NOT complete until every expected item has produced an outcome.
Inspection must NOT modify the real target.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from models import (
    InspectionOutput,
    IsolationBrief,
    IsolationReport,
    SimulationOutput,
)


# ──────────────────────────────────────────────
# Inspection Input Models
# ──────────────────────────────────────────────


@dataclass
class SimulationItemResult:
    """Result from a single item that went through Simulation."""
    item_id: str
    status: str  # "resolved" | "failed"
    simulation_id: str = ""
    candidate_hash: str = ""
    mutation_record: dict[str, Any] = field(default_factory=dict)
    validation_record: dict[str, Any] = field(default_factory=dict)
    source_pre_simulation_item_id: str = ""
    source_finding_id: str = ""
    source_snapshot_id: str = ""


@dataclass
class IsolationItemResult:
    """Result from a single item that went through Isolation."""
    item_id: str
    status: str  # "information_required" | "resolved" | "information_unavailable"
    isolation_id: str = ""
    why_isolated: str = ""
    missing_information: list[str] = field(default_factory=list)
    what_was_tried: list[str] = field(default_factory=list)
    current_outcome: str = ""
    next_steps: list[str] = field(default_factory=list)
    source_pre_simulation_item_id: str = ""
    source_finding_id: str = ""
    source_snapshot_id: str = ""


@dataclass
class InspectionInput:
    """Input for Inspection phase."""
    case_id: str
    snapshot_id: str
    expected_item_ids: list[str]
    simulation_results: list[SimulationItemResult] = field(default_factory=list)
    isolation_results: list[IsolationItemResult] = field(default_factory=list)
    candidate_path: str = ""
    candidate_hash_expected: str = ""
    tool_results: list = field(default_factory=list)  # ToolResult objects from toolkit execution


# ──────────────────────────────────────────────
# Inspection Trace Model
# ──────────────────────────────────────────────


@dataclass
class InspectionItemTrace:
    """Backward trace for a single item through all phases."""
    inspection_item_id: str
    simulation_or_isolation_id: str
    pre_simulation_item_id: str
    finding_id: str
    snapshot_id: str
    status: str  # "resolved" | "unresolved" | "information_required"


# ──────────────────────────────────────────────
# Inspection Errors
# ──────────────────────────────────────────────


@dataclass
class InspectionError:
    """Error preventing Inspection completion."""
    code: str
    message: str
    item_id: str = ""


# ──────────────────────────────────────────────
# Extended Inspection Output
# ──────────────────────────────────────────────


@dataclass
class InspectionResult:
    """Complete Inspection result with tracing and validation."""
    inspection_id: str
    case_id: str
    snapshot_id: str
    expected_item_ids: list[str]
    received_item_ids: list[str]
    missing_item_ids: list[str]
    duplicate_item_ids: list[str]
    resolved_items: list[str]
    unresolved_items: list[str]
    candidate_hash: str
    inspection_hash: str
    reports_complete: bool
    inspection_complete: bool
    errors: list[InspectionError] = field(default_factory=list)
    item_traces: list[InspectionItemTrace] = field(default_factory=list)


# ──────────────────────────────────────────────
# Core Inspection Logic
# ──────────────────────────────────────────────


def run_inspection(inp: InspectionInput) -> InspectionResult:
    """Execute Phase 4 Inspection.

    Validates convergence: every expected item must have exactly one outcome.
    Produces inspection hash and complete tracing.

    Returns InspectionResult which includes completion status and any errors.
    """
    inspection_id = f"inspection-{uuid.uuid4().hex[:8]}"
    errors: list[InspectionError] = []
    item_traces: list[InspectionItemTrace] = []

    # Collect all received item IDs
    received_ids: list[str] = []
    received_set: set[str] = set()

    # Process simulation results
    resolved: list[str] = []
    unresolved: list[str] = []

    for sim_item in inp.simulation_results:
        item_id = sim_item.item_id
        if item_id in received_set:
            errors.append(InspectionError(
                code="DUPLICATE_ITEM",
                message=f"Item '{item_id}' received from multiple branches.",
                item_id=item_id,
            ))
        received_set.add(item_id)
        received_ids.append(item_id)

        if sim_item.status == "resolved":
            resolved.append(item_id)
        else:
            unresolved.append(item_id)

        # Build trace
        item_traces.append(InspectionItemTrace(
            inspection_item_id=f"insp-{item_id}",
            simulation_or_isolation_id=sim_item.simulation_id,
            pre_simulation_item_id=sim_item.source_pre_simulation_item_id or item_id,
            finding_id=sim_item.source_finding_id or item_id,
            snapshot_id=sim_item.source_snapshot_id or inp.snapshot_id,
            status=sim_item.status,
        ))

    # Process isolation results
    for iso_item in inp.isolation_results:
        item_id = iso_item.item_id
        if item_id in received_set:
            errors.append(InspectionError(
                code="DUPLICATE_ITEM",
                message=f"Item '{item_id}' received from multiple branches.",
                item_id=item_id,
            ))
        received_set.add(item_id)
        received_ids.append(item_id)

        # Validate isolation report completeness
        if not iso_item.why_isolated:
            errors.append(InspectionError(
                code="INCOMPLETE_REPORT",
                message=f"Isolated item '{item_id}' missing 'why_isolated'.",
                item_id=item_id,
            ))
        if not iso_item.missing_information and iso_item.status == "information_required":
            errors.append(InspectionError(
                code="INCOMPLETE_REPORT",
                message=f"Isolated item '{item_id}' missing 'missing_information'.",
                item_id=item_id,
            ))
        if not iso_item.next_steps and iso_item.status != "resolved":
            errors.append(InspectionError(
                code="INCOMPLETE_REPORT",
                message=f"Isolated item '{item_id}' missing 'next_steps'.",
                item_id=item_id,
            ))

        if iso_item.status == "resolved":
            resolved.append(item_id)
        else:
            unresolved.append(item_id)

        # Build trace
        item_traces.append(InspectionItemTrace(
            inspection_item_id=f"insp-{item_id}",
            simulation_or_isolation_id=iso_item.isolation_id,
            pre_simulation_item_id=iso_item.source_pre_simulation_item_id or item_id,
            finding_id=iso_item.source_finding_id or item_id,
            snapshot_id=iso_item.source_snapshot_id or inp.snapshot_id,
            status=iso_item.status,
        ))

    # ── Scoring gate evaluation (toolkit results) ─────────────────────────
    if inp.tool_results:
        gate_results = scoring_gate(inp.tool_results)
        for item_id, gate_result in gate_results.items():
            if item_id not in received_set:
                # This is a toolkit-only item not yet tracked
                received_set.add(item_id)
                received_ids.append(item_id)

            if gate_result.passed:
                if item_id not in resolved:
                    resolved.append(item_id)
                # Remove from unresolved if it was there
                if item_id in unresolved:
                    unresolved.remove(item_id)
            else:
                if item_id not in resolved and item_id not in unresolved:
                    unresolved.append(item_id)

            # Build trace for gate-evaluated items
            item_traces.append(InspectionItemTrace(
                inspection_item_id=f"insp-gate-{item_id}",
                simulation_or_isolation_id="scoring_gate",
                pre_simulation_item_id=item_id,
                finding_id=item_id,
                snapshot_id=inp.snapshot_id,
                status="resolved" if gate_result.passed else "unresolved",
            ))

    # Check for missing items
    expected_set = set(inp.expected_item_ids)
    missing = list(expected_set - received_set)
    duplicates = [e.item_id for e in errors if e.code == "DUPLICATE_ITEM"]

    if missing:
        errors.append(InspectionError(
            code="MISSING_BRANCH",
            message=f"Items not yet reported: {missing}. Inspection cannot complete.",
        ))

    # Validate candidate hash if provided
    if inp.candidate_hash_expected and inp.candidate_path:
        actual_hash = _hash_candidate(inp.candidate_path)
        if actual_hash != inp.candidate_hash_expected:
            errors.append(InspectionError(
                code="CANDIDATE_HASH_MISMATCH",
                message=(
                    f"Candidate hash mismatch. Expected: {inp.candidate_hash_expected[:16]}... "
                    f"Actual: {actual_hash[:16]}..."
                ),
            ))

    # Compute inspection hash (hash of all results + candidate)
    candidate_hash = _hash_candidate(inp.candidate_path) if inp.candidate_path else ""
    inspection_hash = _compute_inspection_hash(
        resolved, unresolved, candidate_hash, inp.snapshot_id
    )

    # Determine completion
    reports_complete = len(errors) == 0 or all(
        e.code not in ("MISSING_BRANCH", "DUPLICATE_ITEM", "INCOMPLETE_REPORT", "CANDIDATE_HASH_MISMATCH")
        for e in errors
    )
    inspection_complete = (
        not missing
        and not duplicates
        and reports_complete
    )

    return InspectionResult(
        inspection_id=inspection_id,
        case_id=inp.case_id,
        snapshot_id=inp.snapshot_id,
        expected_item_ids=inp.expected_item_ids,
        received_item_ids=received_ids,
        missing_item_ids=missing,
        duplicate_item_ids=duplicates,
        resolved_items=resolved,
        unresolved_items=unresolved,
        candidate_hash=candidate_hash,
        inspection_hash=inspection_hash,
        reports_complete=reports_complete,
        inspection_complete=inspection_complete,
        errors=errors,
        item_traces=item_traces,
    )


# ──────────────────────────────────────────────
# Hashing Utilities
# ──────────────────────────────────────────────


def _hash_candidate(candidate_path: str) -> str:
    """Compute a combined hash of all files in the candidate."""
    if not candidate_path or not Path(candidate_path).exists():
        return ""

    hasher = hashlib.sha256()
    target = Path(candidate_path)

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
    """Compute a hash representing the complete inspection state."""
    data = json.dumps({
        "resolved": sorted(resolved),
        "unresolved": sorted(unresolved),
        "candidate_hash": candidate_hash,
        "snapshot_id": snapshot_id,
    }, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()


# Need os for walk
import os


# ──────────────────────────────────────────────
# Scoring Gate (Toolkit results evaluation)
# ──────────────────────────────────────────────

# Gate threshold (matches pre-simulation threshold)
GATE_CONFIDENCE_THRESHOLD = 0.9391


@dataclass
class GateResult:
    """Result of scoring gate evaluation for a single item."""
    item_id: str
    passed: bool
    confidence: float
    no_conflict: bool
    no_regression: bool
    reason: str


def scoring_gate(tool_results: list) -> dict[str, GateResult]:
    """Evaluate toolkit results against the scoring gate.

    Gate criteria (all must be True to pass):
      - confidence >= 0.9391
      - no_conflict: no overlapping file mutations between results for same item
      - no_regression: validation_passed is True

    Args:
        tool_results: List of ToolResult objects from toolkit execution.

    Returns:
        Mapping of item_id → GateResult indicating pass/fail and reasons.
    """
    # Group results by item_id (take the best successful result per item)
    best_per_item: dict[str, Any] = {}
    all_per_item: dict[str, list] = {}

    for result in tool_results:
        item_id = result.item_id
        if item_id not in all_per_item:
            all_per_item[item_id] = []
        all_per_item[item_id].append(result)

        # Keep the best successful result (highest confidence)
        if result.success:
            current_best = best_per_item.get(item_id)
            if current_best is None or result.confidence > current_best.confidence:
                best_per_item[item_id] = result

    # Evaluate gate for each item
    gate_results: dict[str, GateResult] = {}

    for item_id, results_for_item in all_per_item.items():
        best = best_per_item.get(item_id)

        if not best:
            # No successful result for this item
            gate_results[item_id] = GateResult(
                item_id=item_id,
                passed=False,
                confidence=0.0,
                no_conflict=True,
                no_regression=False,
                reason="No successful tool execution for this item",
            )
            continue

        # Criterion 1: confidence >= threshold
        confidence_ok = best.confidence >= GATE_CONFIDENCE_THRESHOLD

        # Criterion 2: no_conflict (no overlapping file mutations)
        no_conflict = _check_no_conflict(results_for_item)

        # Criterion 3: no_regression (validation passed)
        no_regression = best.validation_passed

        # Gate decision
        passed = confidence_ok and no_conflict and no_regression

        # Build reason
        reasons: list[str] = []
        if not confidence_ok:
            reasons.append(f"confidence {best.confidence:.4f} < {GATE_CONFIDENCE_THRESHOLD}")
        if not no_conflict:
            reasons.append("conflicting file mutations detected")
        if not no_regression:
            reasons.append("validation did not pass")

        reason = "PASSED" if passed else f"FAILED: {'; '.join(reasons)}"

        gate_results[item_id] = GateResult(
            item_id=item_id,
            passed=passed,
            confidence=best.confidence,
            no_conflict=no_conflict,
            no_regression=no_regression,
            reason=reason,
        )

    return gate_results


def _check_no_conflict(results: list) -> bool:
    """Check that no two successful results for the same item modified the same file.

    Conflict = two different tools both modified the same file for the same item.
    This indicates overlapping mutations that could interact unpredictably.
    """
    successful = [r for r in results if r.success]

    # Collect all (tool_name, file) pairs
    file_owners: dict[str, str] = {}  # file → first tool that touched it
    for result in successful:
        for modified_file in result.files_modified:
            if modified_file in file_owners:
                if file_owners[modified_file] != result.tool_name:
                    return False  # Conflict: different tools touched same file
            else:
                file_owners[modified_file] = result.tool_name

    return True
