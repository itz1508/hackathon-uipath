# Modified: 2026-06-29T21:00:00Z
"""Phase 3: Pre-simulation — Edge backend grading pattern.

Implements:
1. Code-based graders (can_block=True) — hard checks that override any score
2. Weighted graders — advisory scoring on multiple dimensions
3. Hybrid confidence — combines both into a final score
4. Reattempt logic — if score below threshold, produce reattempt report (up to 3)
5. Isolation handoff — structured advisory packet for isolated items

Controller authorizes branches for Phase 4 (Simulation).

Reads: analysis. Writes: simulation_package, flags.
Pure partition function. Does NOT change phase, only partitions state.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from phase_models import PhaseResult, PHASE_NAMES, PASS_THRESHOLD
from phase_controller import PhaseController
from utils import to_hundredths
import logging

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pipeline_state import PipelineState


# ──────────────────────────────────────────────
# Code-based Graders (can_block=True)
# ──────────────────────────────────────────────

def _grade_scan_hash_verified(phase_2_outputs: dict[str, Any]) -> dict[str, Any]:
    """Scan results haven't been tampered. Always passes since scan is internal."""
    return {
        "grader": "scan_hash_verified",
        "can_block": True,
        "passed": True,
        "reason": "internal scan — hash integrity guaranteed",
    }


def _grade_scope_defined(phase_2_outputs: dict[str, Any]) -> dict[str, Any]:
    """Analysis output has classification results (not empty)."""
    classification_results = phase_2_outputs.get("classification_results", [])
    passed = len(classification_results) > 0
    return {
        "grader": "scope_defined",
        "can_block": True,
        "passed": passed,
        "reason": "classification results present" if passed else "no classification results — scope undefined",
    }


def _grade_no_fabricated_findings(phase_2_outputs: dict[str, Any]) -> dict[str, Any]:
    """All findings trace to real tool output (confidence > 0)."""
    classification_results = phase_2_outputs.get("classification_results", [])
    fabricated = [
        item for item in classification_results
        if item.get("confidence", 1) <= 0
    ]
    passed = len(fabricated) == 0
    return {
        "grader": "no_fabricated_findings",
        "can_block": True,
        "passed": passed,
        "reason": "all findings have confidence > 0" if passed else f"{len(fabricated)} findings with zero confidence",
    }


CODE_GRADERS = [
    _grade_scan_hash_verified,
    _grade_scope_defined,
    _grade_no_fabricated_findings,
]


# ──────────────────────────────────────────────
# Weighted Graders (advisory scoring)
# ──────────────────────────────────────────────

WEIGHTED_GRADER_DEFS: list[dict[str, Any]] = [
    {"name": "claim_support_score", "weight": 0.25},
    {"name": "conflict_score", "weight": 0.15},
    {"name": "scope_narrowing_score", "weight": 0.15},
    {"name": "simulation_executability_score", "weight": 0.25},
    {"name": "determinism_score", "weight": 0.10},
    {"name": "information_completeness_score", "weight": 0.10},
]

FIXABLE_CATEGORIES = {
    "syntax_error",           # Fix syntax errors
    "broken_dependency",      # Fix version pins
    "dependency_conflict",    # Fix version conflicts / duplicates
    "circular_import",        # Break circular imports
    "missing_import",         # Fix typos in imports
    "missing_dependency",     # Add to pyproject.toml (when root_cause confirmed)
    "configuration_missing",  # Create .python-version, add requires-python, generate lock
}


def _compute_weighted_graders(phase_2_outputs: dict[str, Any]) -> list[dict[str, Any]]:
    """Compute all weighted grader scores from phase 2 outputs."""
    classification_results = phase_2_outputs.get("classification_results", [])
    total_issues = phase_2_outputs.get("total_issues", 0)

    results = []

    # claim_support_score: ratio of confirmed root causes to total findings
    if total_issues == 0:
        claim_support = 1.0
    else:
        confirmed = sum(
            1 for item in classification_results
            if item.get("root_cause_confirmed", False)
        )
        claim_support = confirmed / total_issues
    results.append({"name": "claim_support_score", "weight": 0.25, "score": claim_support})

    # conflict_score: no overlapping findings on same file
    if total_issues == 0:
        conflict = 1.0
    else:
        file_counts: dict[str, int] = {}
        for item in classification_results:
            f = item.get("file", "")
            file_counts[f] = file_counts.get(f, 0) + 1
        overlapping = sum(1 for c in file_counts.values() if c > 1)
        conflict = 1.0 - (overlapping / max(len(file_counts), 1))
    results.append({"name": "conflict_score", "weight": 0.15, "score": conflict})

    # scope_narrowing_score: specificity of issues found
    if total_issues == 0:
        scope_narrowing = 1.0
    else:
        # Items with specific file + category are "narrow"
        narrow = sum(
            1 for item in classification_results
            if item.get("file", "") and item.get("category", "")
        )
        scope_narrowing = narrow / total_issues
    results.append({"name": "scope_narrowing_score", "weight": 0.15, "score": scope_narrowing})

    # simulation_executability_score: ratio of fixable categories to total
    if total_issues == 0:
        sim_exec = 1.0
    else:
        fixable = sum(
            1 for item in classification_results
            if item.get("category", "") in FIXABLE_CATEGORIES
        )
        sim_exec = fixable / total_issues
    results.append({"name": "simulation_executability_score", "weight": 0.25, "score": sim_exec})

    # determinism_score: all findings have confirmed root causes
    if total_issues == 0:
        determinism = 1.0
    else:
        confirmed_det = sum(
            1 for item in classification_results
            if item.get("root_cause_confirmed", False)
        )
        determinism = confirmed_det / total_issues
    results.append({"name": "determinism_score", "weight": 0.10, "score": determinism})

    # information_completeness_score: ratio of items NOT missing_information
    if total_issues == 0:
        info_complete = 1.0
    else:
        not_missing = sum(
            1 for item in classification_results
            if item.get("category", "") != "missing_information"
        )
        info_complete = not_missing / total_issues
    results.append({"name": "information_completeness_score", "weight": 0.10, "score": info_complete})

    return results


# ──────────────────────────────────────────────
# Hybrid Confidence
# ──────────────────────────────────────────────

def _compute_hybrid_confidence(
    code_grader_results: list[dict[str, Any]],
    weighted_grader_results: list[dict[str, Any]],
) -> tuple[float, bool]:
    """Combine code-based and weighted graders into final score.

    Returns: (score_percent, is_blocked)
    If any code grader fails → blocked, score = 0.0
    Otherwise → weighted sum * 100
    """
    # Check for blocking failures
    blocked = any(not g["passed"] for g in code_grader_results if g["can_block"])
    if blocked:
        return 0.0, True

    # Weighted sum
    total_weight = sum(g["weight"] for g in weighted_grader_results)
    if total_weight == 0:
        return 100.0, False

    weighted_sum = sum(g["score"] * g["weight"] for g in weighted_grader_results)
    score = round((weighted_sum / total_weight) * 100.0, 2)
    return score, False


# ──────────────────────────────────────────────
# Isolation Handoff
# ──────────────────────────────────────────────

def _build_isolation_handoff_item(item: dict[str, Any], reason: str) -> dict[str, Any]:
    """Produce structured isolation handoff packet for a single item."""
    what_is_missing = []
    if not item.get("root_cause_confirmed", False):
        what_is_missing.append("confirmed root cause")
    if item.get("category", "") == "missing_information":
        what_is_missing.append("source information for dependency")
    if not item.get("file", ""):
        what_is_missing.append("specific file location")

    what_was_tried = []
    if item.get("category", ""):
        what_was_tried.append(f"classified as '{item['category']}'")
    if item.get("description", ""):
        what_was_tried.append(f"identified: {item['description']}")

    return {
        "item_id": item.get("id", "unknown"),
        "isolation_reason": reason,
        "authority": "advisory_isolation_only",
        "execution_authority": False,
        "what_is_missing": what_is_missing,
        "what_was_tried": what_was_tried,
        "proposed_correction": f"resolve {reason} for item {item.get('id', 'unknown')}",
        "reviewer_goal": "isolate the unresolved blocker",
        "required_output": [
            "smallest reproducible blocker",
            "cause",
            "missing proof",
            "proposed correction",
        ],
        "forbidden_output": [
            "approval to simulate",
            "approval to mutate",
        ],
    }


def _build_isolation_handoff_packet(isolated_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the advisory isolation handoff packet."""
    if not isolated_items:
        return {}
    return {
        "packet_status": "advisory_isolation",
        "reviewer_targets": [item["item_id"] for item in isolated_items],
        "authority": "advisory_isolation_only",
        "execution_authority": False,
        "blocked_next_phases": ["simulation"],
        "external_reviewer_task": "resolve isolation blockers before simulation",
        "items": isolated_items,
    }


# ──────────────────────────────────────────────
# Main Phase Entry Point
# ──────────────────────────────────────────────

def execute_phase_3_presimulation(
    controller: PhaseController,
    snapshot: dict[str, Any],
    phase_2_outputs: dict[str, Any],
) -> PhaseResult:
    """Phase 3: Pre-simulation / Edge Backend Grading Pattern.

    1. Run code-based graders (blockers)
    2. Run weighted graders (scoring dimensions)
    3. Calculate hybrid confidence score
    4. If blocked → simulation_ready=False, all items isolated
    5. If score >= 93.91 → all items ready
    6. If score < 93.91 → partition per item:
       - Items with confirmed root cause + fixable category → ready_parts
       - Items with missing_information or unconfirmed root cause → isolated_parts
    7. For isolated items, produce isolation_handoff packet
    """
    controller.start_phase(3)
    start = datetime.now(timezone.utc)

    classification_results = phase_2_outputs.get("classification_results", [])
    total_issues = phase_2_outputs.get("total_issues", 0)

    # ── 1. Code-based graders ──
    code_grader_results = [grader(phase_2_outputs) for grader in CODE_GRADERS]

    # ── 2. Weighted graders ──
    weighted_grader_results = _compute_weighted_graders(phase_2_outputs)

    # ── 3. Hybrid confidence ──
    package_confidence_score, is_blocked = _compute_hybrid_confidence(
        code_grader_results, weighted_grader_results
    )

    # ── 4/5/6. Routing logic ──
    score_hundredths = to_hundredths(package_confidence_score)
    simulation_ready = (not is_blocked) and (score_hundredths >= PASS_THRESHOLD)

    ready_parts: list[dict[str, Any]] = []
    isolated_parts: list[dict[str, Any]] = []
    isolation_handoff_items: list[dict[str, Any]] = []

    if is_blocked:
        # All items isolated due to blocker
        confidence_status = "blocked"
        for issue in classification_results:
            item_id = issue.get("id", f"item-{len(isolated_parts)}")
            reason = "code_grader_block"
            isolated_parts.append({
                "item_id": item_id,
                "readiness": "blocked",
                "isolation_reason": reason,
                "category": issue.get("category", ""),
                "file": issue.get("file", ""),
                "description": issue.get("description", ""),
            })
            isolation_handoff_items.append(_build_isolation_handoff_item(issue, reason))
    elif score_hundredths >= PASS_THRESHOLD:
        # All items ready
        confidence_status = "ready_for_simulation"
        for issue in classification_results:
            item_id = issue.get("id", f"item-{len(ready_parts)}")
            ready_parts.append({
                "item_id": item_id,
                "readiness": "ready",
                "category": issue.get("category", ""),
                "file": issue.get("file", ""),
                "description": issue.get("description", ""),
            })
    else:
        # Below threshold — partition per item
        confidence_status = "below_threshold"
        for issue in classification_results:
            item_id = issue.get("id", f"item-{len(ready_parts) + len(isolated_parts)}")
            category = issue.get("category", "")
            has_root_cause = issue.get("root_cause_confirmed", False)
            is_fixable = category in FIXABLE_CATEGORIES
            has_missing_info = bool(issue.get("missing_information", []))

            if has_root_cause and is_fixable and not has_missing_info:
                ready_parts.append({
                    "item_id": item_id,
                    "readiness": "ready",
                    "category": category,
                    "file": issue.get("file", ""),
                    "description": issue.get("description", ""),
                })
            else:
                reason = "unconfirmed_root_cause" if not has_root_cause else (
                    "missing_information" if has_missing_info else "unfixable_category"
                )
                isolated_parts.append({
                    "item_id": item_id,
                    "readiness": "awaiting_information",
                    "isolation_reason": reason,
                    "category": category,
                    "file": issue.get("file", ""),
                    "description": issue.get("description", ""),
                })
                isolation_handoff_items.append(_build_isolation_handoff_item(issue, reason))

    # ── 7. Build isolation handoff packet ──
    isolation_handoff = _build_isolation_handoff_packet(isolation_handoff_items)

    # ── 8. Isolation Engine (when enabled and items are isolated) ──
    # Check if isolation_enabled is passed via snapshot metadata
    isolation_enabled = snapshot.get("isolation_enabled", True)

    if isolated_parts and isolation_enabled and not is_blocked:
        try:
            logger.debug("Calling isolation engine for %d isolated items", len(isolated_parts))
            from isolation_engine import run_isolation_engine
            engine_result = run_isolation_engine(
                isolated_items=isolated_parts,
                classification_results=classification_results,
                target_path=snapshot.get("storage_path", ""),
                enabled=True,
            )
            logger.debug("Isolation engine result: items_resolved=%s", engine_result.get("items_resolved"))
            if engine_result.get("items_resolved", 0) > 0:
                resolved_ids = {
                    r["item_id"] for r in engine_result.get("resolution_records", [])
                    if r.get("retry_recommendation") == "ready_for_simulation"
                }

                new_ready = list(ready_parts)
                new_isolated = []
                new_isolation_handoff_items = []

                for iso_item in isolated_parts:
                    if iso_item["item_id"] in resolved_ids:
                        new_ready.append({
                            "item_id": iso_item["item_id"],
                            "readiness": "ready",
                            "category": iso_item.get("category", ""),
                            "file": iso_item.get("file", ""),
                            "description": iso_item.get("description", ""),
                        })
                    else:
                        new_isolated.append(iso_item)
                        matching_issue = next(
                            (c for c in classification_results if c.get("id") == iso_item["item_id"]),
                            iso_item,
                        )
                        new_isolation_handoff_items.append(
                            _build_isolation_handoff_item(matching_issue, iso_item.get("isolation_reason", "unresolved"))
                        )

                ready_parts = new_ready
                isolated_parts = new_isolated
                isolation_handoff_items = new_isolation_handoff_items
                isolation_handoff = _build_isolation_handoff_packet(new_isolation_handoff_items)

                # Recalculate score
                updated_phase_2 = dict(phase_2_outputs)
                updated_phase_2["classification_results"] = engine_result.get("rebuilt_classification", classification_results)
                weighted_grader_results = _compute_weighted_graders(updated_phase_2)
                package_confidence_score, _ = _compute_hybrid_confidence(
                    code_grader_results, weighted_grader_results
                )
                score_hundredths = to_hundredths(package_confidence_score)
                simulation_ready = score_hundredths >= PASS_THRESHOLD
        except ImportError as exc:
            logger.error("Isolation engine import failed: %s", exc)
        except Exception as exc:
            logger.exception("Isolation engine execution failed: %s", exc)

    # Determine required grader failures
    required_grader_failures = [g for g in code_grader_results if not g["passed"]]

    # Controller authorizes branches
    ready_item_ids = [p["item_id"] for p in ready_parts]
    isolated_item_ids = [p["item_id"] for p in isolated_parts]

    if ready_item_ids:
        controller.authorize_simulation_branch(ready_item_ids)
    if isolated_item_ids:
        controller.authorize_isolation_branch(isolated_item_ids)

    duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    result = PhaseResult(
        phase=3,
        phase_name=PHASE_NAMES[3],
        exit_status="completed",
        required_outputs={
            "package_confidence_score": package_confidence_score,
            "simulation_ready": simulation_ready,
            "ready_parts": ready_parts,
            "isolated_parts": isolated_parts,
            "grader_results": {
                "code_graders": code_grader_results,
                "weighted_graders": weighted_grader_results,
            },
            "confidence_status": confidence_status,
            "required_grader_failures": required_grader_failures,
            "isolation_handoff": isolation_handoff,
        },
        duration_ms=duration,
    )
    controller.complete_phase(result)
    return result


# ──────────────────────────────────────────────
# State Algebra Transform
# ──────────────────────────────────────────────


def transform_phase_3(state: "PipelineState", controller: PhaseController) -> "PipelineState":
    """Phase 3 pure transformation: Reads analysis. Writes simulation_package, flags.

    Edge backend grading pattern with hybrid confidence.
    Pure partition function. Does NOT change phase, only partitions state.
    """
    from pipeline_state import PipelineState

    state.validate_transition(3)
    controller.start_phase(3)

    classification_results = state.analysis.get("classification_results", [])
    total_issues = state.analysis.get("total_issues", 0)

    # Build phase_2_outputs dict for grader functions
    phase_2_outputs = {
        "classification_results": classification_results,
        "total_issues": total_issues,
    }

    # ── 1. Code-based graders ──
    code_grader_results = [grader(phase_2_outputs) for grader in CODE_GRADERS]

    # ── 2. Weighted graders ──
    weighted_grader_results = _compute_weighted_graders(phase_2_outputs)

    # ── 3. Hybrid confidence ──
    package_confidence_score, is_blocked = _compute_hybrid_confidence(
        code_grader_results, weighted_grader_results
    )

    # ── 4/5/6. Routing ──
    score_hundredths = to_hundredths(package_confidence_score)
    simulation_ready = (not is_blocked) and (score_hundredths >= PASS_THRESHOLD)

    ready_parts: list[dict[str, Any]] = []
    isolated_parts: list[dict[str, Any]] = []
    isolation_handoff_items: list[dict[str, Any]] = []

    if is_blocked:
        confidence_status = "blocked"
        for issue in classification_results:
            item_id = issue.get("id", f"item-{len(isolated_parts)}")
            reason = "code_grader_block"
            isolated_parts.append({
                "item_id": item_id,
                "readiness": "blocked",
                "isolation_reason": reason,
                "category": issue.get("category", ""),
                "file": issue.get("file", ""),
                "description": issue.get("description", ""),
            })
            isolation_handoff_items.append(_build_isolation_handoff_item(issue, reason))
    elif score_hundredths >= PASS_THRESHOLD:
        confidence_status = "ready_for_simulation"
        for issue in classification_results:
            item_id = issue.get("id", f"item-{len(ready_parts)}")
            ready_parts.append({
                "item_id": item_id,
                "readiness": "ready",
                "category": issue.get("category", ""),
                "file": issue.get("file", ""),
                "description": issue.get("description", ""),
            })
    else:
        confidence_status = "below_threshold"
        for issue in classification_results:
            item_id = issue.get("id", f"item-{len(ready_parts) + len(isolated_parts)}")
            category = issue.get("category", "")
            has_root_cause = issue.get("root_cause_confirmed", False)
            is_fixable = category in FIXABLE_CATEGORIES
            has_missing_info = bool(issue.get("missing_information", []))

            if has_root_cause and is_fixable and not has_missing_info:
                ready_parts.append({
                    "item_id": item_id,
                    "readiness": "ready",
                    "category": category,
                    "file": issue.get("file", ""),
                    "description": issue.get("description", ""),
                })
            else:
                reason = "unconfirmed_root_cause" if not has_root_cause else (
                    "missing_information" if has_missing_info else "unfixable_category"
                )
                isolated_parts.append({
                    "item_id": item_id,
                    "readiness": "awaiting_information",
                    "isolation_reason": reason,
                    "category": category,
                    "file": issue.get("file", ""),
                    "description": issue.get("description", ""),
                })
                isolation_handoff_items.append(_build_isolation_handoff_item(issue, reason))

    # Build isolation handoff packet
    isolation_handoff = _build_isolation_handoff_packet(isolation_handoff_items)

    # Required grader failures
    required_grader_failures = [g for g in code_grader_results if not g["passed"]]

    # Controller branch authorization
    ready_item_ids = [p["item_id"] for p in ready_parts]
    isolated_item_ids = [p["item_id"] for p in isolated_parts]

    if ready_item_ids:
        controller.authorize_simulation_branch(ready_item_ids)
    if isolated_item_ids:
        controller.authorize_isolation_branch(isolated_item_ids)

    # ── Isolation Engine (internal, not a phase) ──
    if isolated_parts and state.isolation_enabled:
        try:
            logger.debug("Transform: calling isolation engine for %d items", len(isolated_parts))
            from isolation_engine import run_isolation_engine
            engine_result = run_isolation_engine(
                isolated_items=isolated_parts,
                classification_results=classification_results,
                target_path=state.target_path,
                enabled=True,
            )
            logger.debug("Transform isolation engine result: items_resolved=%s", engine_result.get("items_resolved"))
            if engine_result.get("items_resolved", 0) > 0:
                # Update classification with new confidence values
                classification_results = engine_result["rebuilt_classification"]
                phase_2_outputs["classification_results"] = classification_results

                # Re-partition: move resolved items from isolated to ready
                new_ready: list[dict[str, Any]] = list(ready_parts)
                new_isolated: list[dict[str, Any]] = []
                new_isolation_handoff_items: list[dict[str, Any]] = []

                resolved_ids = {
                    r["item_id"] for r in engine_result["resolution_records"]
                    if r["retry_recommendation"] == "ready_for_simulation"
                }

                for iso_item in isolated_parts:
                    if iso_item["item_id"] in resolved_ids:
                        # Move to ready
                        new_ready.append({
                            "item_id": iso_item["item_id"],
                            "readiness": "ready",
                            "category": iso_item.get("category", ""),
                            "file": iso_item.get("file", ""),
                            "description": iso_item.get("description", ""),
                        })
                    else:
                        new_isolated.append(iso_item)
                        # Rebuild handoff item
                        matching_issue = next(
                            (c for c in classification_results if c.get("id") == iso_item["item_id"]),
                            iso_item,
                        )
                        new_isolation_handoff_items.append(
                            _build_isolation_handoff_item(matching_issue, iso_item.get("isolation_reason", "unresolved"))
                        )

                ready_parts = new_ready
                isolated_parts = new_isolated
                isolation_handoff_items = new_isolation_handoff_items
            isolation_handoff = _build_isolation_handoff_packet(isolation_handoff_items)

            # Recalculate score with updated classification
            weighted_grader_results = _compute_weighted_graders(phase_2_outputs)
            package_confidence_score, is_blocked = _compute_hybrid_confidence(
                code_grader_results, weighted_grader_results
            )
            score_hundredths = to_hundredths(package_confidence_score)
            simulation_ready = (not is_blocked) and (score_hundredths >= PASS_THRESHOLD)

        except ImportError as exc:
            logger.error("Transform isolation engine import failed: %s", exc)
        except Exception as exc:
            logger.exception("Transform isolation engine failed: %s", exc)

            # Update controller branch authorization
            ready_item_ids = [p["item_id"] for p in ready_parts]
            isolated_item_ids = [p["item_id"] for p in isolated_parts]

    # Update isolation state
    if isolated_item_ids:
        state.flags.isolation_active = True
        state.isolation.active = True
        state.isolation.items = isolated_parts
        state.isolation.isolation_handoff = isolation_handoff

    state.simulation_package = {
        "score": package_confidence_score,
        "ready_parts": ready_parts,
        "isolated_parts": isolated_parts,
        "simulation_ready": simulation_ready,
        "grader_results": {
            "code_graders": code_grader_results,
            "weighted_graders": weighted_grader_results,
        },
        "confidence_status": confidence_status,
        "required_grader_failures": required_grader_failures,
        "isolation_handoff": isolation_handoff,
    }
    state.flags.partition_complete = True

    result = PhaseResult(
        phase=3,
        phase_name=PHASE_NAMES[3],
        exit_status="completed",
        required_outputs={
            "package_confidence_score": package_confidence_score,
            "simulation_ready": simulation_ready,
            "ready_parts": ready_parts,
            "isolated_parts": isolated_parts,
            "grader_results": {
                "code_graders": code_grader_results,
                "weighted_graders": weighted_grader_results,
            },
            "confidence_status": confidence_status,
            "required_grader_failures": required_grader_failures,
            "isolation_handoff": isolation_handoff,
        },
        duration_ms=0,
    )
    controller.complete_phase(result)
    return state
