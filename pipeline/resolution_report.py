"""Resolution Report — Schema + Generator.

Defines the ResolutionReport schema as Python dataclasses and provides
a generate_report() function that runs pipeline A (isolation OFF) and
pipeline B (isolation ON), computes fixture hash, builds the canonical
proof object, and returns JSON + rendered HTML.

Usage:
    from resolution_report import generate_report
    json_str, html_str = generate_report("path/to/fixture")
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure pipeline root is importable
PIPELINE_ROOT = os.path.dirname(os.path.abspath(__file__))
if PIPELINE_ROOT not in sys.path:
    sys.path.insert(0, PIPELINE_ROOT)

from phase_models import WorkflowInput
from orchestrator import run_pipeline_stateful


# ──────────────────────────────────────────────
# Schema (Dataclasses)
# ──────────────────────────────────────────────


@dataclass
class ReportSummary:
    """Top-level summary of the resolution outcome."""
    initial_score: float = 0.0
    final_score: float = 0.0
    delta_score: float = 0.0
    total_issues: int = 0
    resolved: int = 0
    unresolved: int = 0
    status: str = "unknown"  # "fully_resolved" | "partially_resolved" | "failed"


@dataclass
class RunRecord:
    """Record of a single pipeline run (A or B)."""
    isolation: bool = False
    score: float = 0.0
    simulation_ready: bool = False
    ready_count: int = 0
    isolated_count: int = 0
    resolved_count: int = 0
    unresolved_count: int = 0
    final_state: str = ""  # completion_status from final_output


@dataclass
class DiffRecord:
    """Differences between Run A and Run B."""
    score_delta: dict[str, float] = field(default_factory=dict)
    # {"before": score_a, "after": score_b}
    behavioral_delta: dict[str, Any] = field(default_factory=dict)
    # {"ready_a": n, "ready_b": n, "isolated_a": n, "isolated_b": n}
    resolution_delta: list[dict[str, str]] = field(default_factory=list)
    # [{"item_id": ..., "status_a": ..., "status_b": ...}]


@dataclass
class ResolutionItem:
    """A single resolved/unresolved issue."""
    issue_id: str = ""
    type: str = ""       # finding category
    cause: str = ""      # root cause
    action: str = ""     # what was done
    result: str = ""     # "resolved" | "unresolved" | "isolated"


@dataclass
class Metrics:
    """Pipeline quality metrics."""
    scan_coverage: float = 0.0
    analysis_confidence: float = 0.0
    simulation_success_rate: float = 0.0
    isolation_effectiveness: float = 0.0
    pipeline_stability: float = 0.0


@dataclass
class ResolutionReport:
    """The canonical resolution proof object."""
    report_id: str = ""
    fixture: str = ""
    fixture_hash: str = ""
    run_config: dict[str, Any] = field(default_factory=dict)
    summary: ReportSummary = field(default_factory=ReportSummary)
    runs: dict[str, RunRecord] = field(default_factory=dict)
    diff: DiffRecord = field(default_factory=DiffRecord)
    resolution: list[ResolutionItem] = field(default_factory=list)
    metrics: Metrics = field(default_factory=Metrics)
    timestamp: str = ""


# ──────────────────────────────────────────────
# Utility
# ──────────────────────────────────────────────


def compute_fixture_hash(path: str) -> str:
    """Compute deterministic SHA-256 hash of a fixture directory."""
    target = Path(path)
    if not target.exists():
        return "MISSING"

    hasher = hashlib.sha256()
    for root, dirs, files in os.walk(target):
        dirs[:] = sorted(d for d in dirs if not d.startswith("__pycache__") and not d.startswith(".candidate"))
        for filename in sorted(files):
            filepath = Path(root) / filename
            rel = str(filepath.relative_to(target)).replace(os.sep, "/")
            hasher.update(rel.encode("utf-8"))
            try:
                hasher.update(filepath.read_bytes())
            except (OSError, PermissionError):
                hasher.update(b"UNREADABLE")
    return hasher.hexdigest()


def _run_pipeline(fixture_path: str, isolation_enabled: bool, label: str) -> tuple[Any, Any]:
    """Run pipeline with given config and return (state, output)."""
    case_id = f"resolution-{label}-{Path(fixture_path).name}"
    state, output = run_pipeline_stateful(
        WorkflowInput(
            case_id=case_id,
            target_path=fixture_path,
            mode="auto",
            isolation_enabled=isolation_enabled,
        )
    )
    return state, output


def _extract_run_record(state: Any, output: Any, isolation: bool) -> RunRecord:
    """Extract a RunRecord from pipeline state/output."""
    pkg = state.simulation_package
    fo = state.final_output

    # resolved/unresolved from final_output OR from simulation_package partitioning
    resolved_count = fo.get("resolved_count", 0)
    unresolved_count = fo.get("unresolved_count", 0)

    # If final_output didn't fire, infer from ready_parts/isolated_parts
    if resolved_count == 0 and unresolved_count == 0:
        ready_parts = pkg.get("ready_parts", [])
        isolated_parts = pkg.get("isolated_parts", [])
        resolved_count = len(ready_parts)
        unresolved_count = len(isolated_parts)

    final_state = fo.get("completion_status", "")
    if not final_state:
        # Infer from pipeline status
        ps = output.pipeline_status.value if hasattr(output.pipeline_status, 'value') else str(output.pipeline_status)
        if ps == "succeeded":
            final_state = "fully_resolved" if unresolved_count == 0 else "partially_resolved"
        else:
            final_state = ps

    return RunRecord(
        isolation=isolation,
        score=pkg.get("score", 0.0),
        simulation_ready=pkg.get("simulation_ready", False),
        ready_count=len(pkg.get("ready_parts", [])),
        isolated_count=len(pkg.get("isolated_parts", [])),
        resolved_count=resolved_count,
        unresolved_count=unresolved_count,
        final_state=final_state,
    )


def _build_resolution_items(state_a: Any, state_b: Any) -> list[ResolutionItem]:
    """Build per-item resolution records from both runs."""
    items: list[ResolutionItem] = []

    # Primary source: run B (isolation run) final_output
    fo_b = state_b.final_output
    resolved_b = fo_b.get("resolved_items", [])
    unresolved_b = fo_b.get("unresolved_items", [])

    # If run B didn't produce final_output items, use simulation_package partitions
    if not resolved_b and not unresolved_b:
        pkg_b = state_b.simulation_package
        ready_parts = pkg_b.get("ready_parts", [])
        isolated_parts = pkg_b.get("isolated_parts", [])

        for part in ready_parts:
            items.append(ResolutionItem(
                issue_id=part.get("item_id", ""),
                type=part.get("category", ""),
                cause=part.get("description", ""),
                action="resolved via isolation pipeline",
                result="resolved",
            ))

        for part in isolated_parts:
            items.append(ResolutionItem(
                issue_id=part.get("item_id", ""),
                type=part.get("category", ""),
                cause=part.get("description", part.get("isolation_reason", "")),
                action="isolated — requires external review",
                result="isolated",
            ))
    else:
        for item in resolved_b:
            items.append(ResolutionItem(
                issue_id=item.get("item_id", ""),
                type=item.get("category", item.get("type", "")),
                cause=item.get("root_cause", ""),
                action=item.get("resolution", item.get("action", "")),
                result="resolved",
            ))

        for item in unresolved_b:
            items.append(ResolutionItem(
                issue_id=item.get("item_id", ""),
                type=item.get("category", item.get("type", "")),
                cause=item.get("root_cause", item.get("why_unresolved", "")),
                action="; ".join(item.get("what_was_tried", [])) if item.get("what_was_tried") else "",
                result="unresolved",
            ))

    return items


def _build_diff(run_a: RunRecord, run_b: RunRecord, state_a: Any, state_b: Any) -> DiffRecord:
    """Build diff between the two runs."""
    # Per-item status change
    items_a: dict[str, str] = {}
    items_b: dict[str, str] = {}

    # Run A: from final_output or simulation_package
    fo_a = state_a.final_output
    if fo_a.get("resolved_items") or fo_a.get("unresolved_items"):
        for item in fo_a.get("resolved_items", []):
            items_a[item.get("item_id", "")] = "resolved"
        for item in fo_a.get("unresolved_items", []):
            items_a[item.get("item_id", "")] = "unresolved"
    else:
        pkg_a = state_a.simulation_package
        for part in pkg_a.get("ready_parts", []):
            items_a[part.get("item_id", "")] = "resolved"
        for part in pkg_a.get("isolated_parts", []):
            items_a[part.get("item_id", "")] = "isolated"

    # Run B: from final_output or simulation_package
    fo_b = state_b.final_output
    if fo_b.get("resolved_items") or fo_b.get("unresolved_items"):
        for item in fo_b.get("resolved_items", []):
            items_b[item.get("item_id", "")] = "resolved"
        for item in fo_b.get("unresolved_items", []):
            items_b[item.get("item_id", "")] = "unresolved"
    else:
        pkg_b = state_b.simulation_package
        for part in pkg_b.get("ready_parts", []):
            items_b[part.get("item_id", "")] = "resolved"
        for part in pkg_b.get("isolated_parts", []):
            items_b[part.get("item_id", "")] = "isolated"

    all_ids = sorted(set(list(items_a.keys()) + list(items_b.keys())))
    resolution_delta = []
    for item_id in all_ids:
        if not item_id:
            continue
        sa = items_a.get(item_id, "not_seen")
        sb = items_b.get(item_id, "not_seen")
        resolution_delta.append({"item_id": item_id, "status_a": sa, "status_b": sb})

    return DiffRecord(
        score_delta={"before": run_a.score, "after": run_b.score},
        behavioral_delta={
            "ready_a": run_a.ready_count,
            "ready_b": run_b.ready_count,
            "isolated_a": run_a.isolated_count,
            "isolated_b": run_b.isolated_count,
        },
        resolution_delta=resolution_delta,
    )


def _compute_metrics(run_a: RunRecord, run_b: RunRecord, state_b: Any) -> Metrics:
    """Compute quality metrics."""
    pkg_b = state_b.simulation_package
    total_items = run_b.ready_count + run_b.isolated_count
    total_resolved_b = run_b.resolved_count
    total_issues = total_resolved_b + run_b.unresolved_count

    # Scan coverage: ready items / total items found
    scan_coverage = (run_b.ready_count / max(1, total_items)) * 100 if total_items > 0 else 0

    # Analysis confidence: score from pre-simulation
    analysis_confidence = run_b.score

    # Simulation success rate: resolved / total issues
    simulation_success_rate = (total_resolved_b / max(1, total_issues)) * 100 if total_issues > 0 else 100.0

    # Isolation effectiveness: improvement from A to B
    if run_a.score < 100:
        isolation_effectiveness = max(0, ((run_b.score - run_a.score) / max(1, 100 - run_a.score)) * 100)
    else:
        isolation_effectiveness = 100.0 if run_b.score >= run_a.score else 0.0

    # Pipeline stability: both runs completed (have a final_state)
    pipeline_stability = 100.0 if run_a.final_state and run_b.final_state else 50.0

    return Metrics(
        scan_coverage=round(scan_coverage, 2),
        analysis_confidence=round(analysis_confidence, 2),
        simulation_success_rate=round(simulation_success_rate, 2),
        isolation_effectiveness=round(isolation_effectiveness, 2),
        pipeline_stability=round(pipeline_stability, 2),
    )


# ──────────────────────────────────────────────
# Main Generator
# ──────────────────────────────────────────────


def generate_report(
    fixture_path: str,
) -> tuple[str, str]:
    """Run the pipeline with always-on isolation and produce the canonical resolution report.

    This pipeline no longer supports an A/B toggle: isolation is always enabled.

    Returns: Tuple of (json_string, html_string).
    """
    fixture_path = str(Path(fixture_path).resolve())
    print(f"  [Resolution Report] Fixture: {fixture_path}")
    print(f"  [Resolution Report] Computing fixture hash...")
    fhash = compute_fixture_hash(fixture_path)
    print(f"  [Resolution Report] Hash: {fhash[:16]}...")

    # Single run with isolation forced ON by orchestrator
    print(f"  [Resolution Report] Running pipeline (isolation=ON)...")
    t0 = time.perf_counter()
    state_b, output_b = _run_pipeline(fixture_path, True, "B")
    dur_b = int((time.perf_counter() - t0) * 1000)
    run_b = _extract_run_record(state_b, output_b, True)
    print(f"  [Resolution Report] Run complete: score={run_b.score}% ({dur_b}ms)")

    # Populate a placeholder run_a for compatibility in downstream diffs
    run_a = RunRecord(isolation=False, score=0.0, simulation_ready=False, ready_count=0, isolated_count=0, resolved_count=0, unresolved_count=0, final_state="")

    # Build components
    resolution_items = _build_resolution_items(state_a, state_b)
    diff = _build_diff(run_a, run_b, state_a, state_b)
    metrics = _compute_metrics(run_a, run_b, state_b)

    # Determine status based on run_b record
    total_issues = run_b.resolved_count + run_b.unresolved_count
    if total_issues == 0:
        # Fallback: count from resolution items
        total_issues = len(resolution_items)
        resolved_count = sum(1 for r in resolution_items if r.result == "resolved")
        unresolved_count = total_issues - resolved_count
    else:
        resolved_count = run_b.resolved_count
        unresolved_count = run_b.unresolved_count

    if unresolved_count == 0 and total_issues > 0:
        status = "fully_resolved"
    elif resolved_count > 0:
        status = "partially_resolved"
    else:
        status = "failed"

    summary = ReportSummary(
        initial_score=run_a.score,
        final_score=run_b.score,
        delta_score=round(run_b.score - run_a.score, 2),
        total_issues=total_issues,
        resolved=resolved_count,
        unresolved=unresolved_count,
        status=status,
    )

    report = ResolutionReport(
        report_id=str(uuid.uuid4()),
        fixture=fixture_path,
        fixture_hash=fhash,
        run_config={
            "isolation_enabled": True,
            "mode": "SINGLE_ISOLATION",
        },
        summary=summary,
        runs={"A": run_a, "B": run_b},
        diff=diff,
        resolution=resolution_items,
        metrics=metrics,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # Serialize to JSON
    report_dict = asdict(report)
    json_str = json.dumps(report_dict, indent=2, default=str)

    # Render HTML
    from resolution_report_html import render_report_html
    html_str = render_report_html(report_dict)

    return json_str, html_str
