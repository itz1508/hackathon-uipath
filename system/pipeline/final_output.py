"""Phase 6 — Final Output: Produce complete output package for any decision path.

Final Output receives the Relay result and constructs:
- final_report.json (always produced regardless of decision)
- handoff_report.json (when unresolved items exist)
- resolved.html (human-readable summary)
- Forward and backward traces

Critical rules:
- ALWAYS produce final report regardless of decision path.
- Do NOT call the report "fully resolved" when unresolved items remain.
- Handoff report must include exact unresolved issue detail for continuation.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any


# ──────────────────────────────────────────────
# Final Output Dataclasses
# ──────────────────────────────────────────────


@dataclass
class FinalOutputInput:
    """Input for the Final Output phase."""
    case_id: str
    decision: str  # "apply" | "cancel"
    total_issues: int
    resolved_items: list[dict[str, Any]] = field(default_factory=list)
    # Each resolved_item has: item_id, root_cause, resolution, validation, released (bool)
    unresolved_items: list[dict[str, Any]] = field(default_factory=list)
    # Each unresolved_item has: item_id, root_cause, why_unresolved, what_was_tried (list),
    #   missing_information (list), next_steps (list), retry_guidance
    snapshot_hash: str = ""
    inspection_hash: str = ""
    final_target_hash: str = ""
    item_traces: list[dict[str, Any]] = field(default_factory=list)
    # Full backward trace dicts with: item_id, phase_6_final, phase_5_relay,
    #   phase_4_inspection, phase_3_result, phase_2_item, phase_1_finding,
    #   phase_0_snapshot, trace_complete
    relay_result: dict[str, Any] = field(default_factory=dict)
    # RelayResult-compatible dict


@dataclass
class FinalOutputPackage:
    """Complete Final Output package."""
    case_id: str
    decision: str
    total_issues: int
    resolved_count: int
    unresolved_count: int
    resolved_items: list[dict[str, Any]] = field(default_factory=list)
    unresolved_items: list[dict[str, Any]] = field(default_factory=list)
    snapshot_hash: str = ""
    inspection_hash: str = ""
    final_target_hash: str = ""
    reports: dict[str, str] = field(default_factory=dict)
    # keys: "final_report_json" (str path), "handoff_report_json" (str path),
    #        "resolved_html" (str content)
    forward_traces: list[dict[str, Any]] = field(default_factory=list)
    backward_traces: list[dict[str, Any]] = field(default_factory=list)
    success_note: str = ""  # For fully resolved apply
    continuation_handoff: str = ""  # For partial/cancel


# ──────────────────────────────────────────────
# HTML Generation
# ──────────────────────────────────────────────


def generate_resolved_html(
    resolved_items: list[dict[str, Any]],
    unresolved_items: list[dict[str, Any]],
    decision: str,
    snapshot_hash: str,
    inspection_hash: str,
    final_target_hash: str,
) -> str:
    """Produce a valid HTML document summarizing the final output.

    Separates: original state, candidate state, final target state,
    resolved items, unresolved items, before/after diff, root cause,
    resolution or remaining gap, what was tried, next action,
    user decision, hash verification.

    Does NOT call the report "fully resolved" when unresolved items remain.
    """
    has_unresolved = len(unresolved_items) > 0
    title = "Final Output Report"
    if not has_unresolved and decision == "apply":
        status_label = "All Issues Resolved"
    elif has_unresolved and decision == "apply":
        status_label = "Partial Resolution — Continuation Required"
    else:
        status_label = "Cancelled — Snapshot Preserved"

    # Build resolved items HTML
    resolved_rows = ""
    for item in resolved_items:
        released_str = "Yes" if item.get("released", False) else "No"
        resolved_rows += f"""
        <tr>
            <td>{_esc(item.get('item_id', ''))}</td>
            <td>{_esc(item.get('root_cause', ''))}</td>
            <td>{_esc(item.get('resolution', ''))}</td>
            <td>{_esc(item.get('validation', ''))}</td>
            <td>{released_str}</td>
        </tr>"""

    # Build unresolved items HTML
    unresolved_rows = ""
    for item in unresolved_items:
        tried_list = ", ".join(item.get("what_was_tried", []))
        missing_list = ", ".join(item.get("missing_information", []))
        next_list = ", ".join(item.get("next_steps", []))
        unresolved_rows += f"""
        <tr>
            <td>{_esc(item.get('item_id', ''))}</td>
            <td>{_esc(item.get('root_cause', ''))}</td>
            <td>{_esc(item.get('why_unresolved', ''))}</td>
            <td>{_esc(tried_list)}</td>
            <td>{_esc(missing_list)}</td>
            <td>{_esc(next_list)}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{_esc(title)}</title>
    <style>
        body {{ font-family: sans-serif; margin: 2em; color: #222; }}
        h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.3em; }}
        h2 {{ color: #444; margin-top: 1.5em; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 0.5em; }}
        th, td {{ border: 1px solid #ccc; padding: 0.5em 0.75em; text-align: left; }}
        th {{ background: #f5f5f5; }}
        .status {{ font-weight: bold; padding: 0.3em 0.6em; border-radius: 3px; }}
        .status-resolved {{ background: #d4edda; color: #155724; }}
        .status-partial {{ background: #fff3cd; color: #856404; }}
        .status-cancelled {{ background: #f8d7da; color: #721c24; }}
        .hash {{ font-family: monospace; font-size: 0.85em; word-break: break-all; }}
        section {{ margin-bottom: 2em; }}
    </style>
</head>
<body>
    <h1>{_esc(title)}</h1>
    <p class="status {_status_class(decision, has_unresolved)}">{_esc(status_label)}</p>

    <section id="user-decision">
        <h2>User Decision</h2>
        <p><strong>Decision:</strong> {_esc(decision)}</p>
    </section>

    <section id="original-state">
        <h2>Original State (Snapshot)</h2>
        <p class="hash"><strong>Snapshot Hash:</strong> {_esc(snapshot_hash)}</p>
    </section>

    <section id="candidate-state">
        <h2>Candidate State</h2>
        <p class="hash"><strong>Inspection Hash:</strong> {_esc(inspection_hash)}</p>
    </section>

    <section id="final-target-state">
        <h2>Final Target State</h2>
        <p class="hash"><strong>Final Target Hash:</strong> {_esc(final_target_hash)}</p>
    </section>

    <section id="resolved-items">
        <h2>Resolved Items ({len(resolved_items)})</h2>
        <table>
            <thead>
                <tr>
                    <th>Item ID</th>
                    <th>Root Cause</th>
                    <th>Resolution</th>
                    <th>Validation</th>
                    <th>Released</th>
                </tr>
            </thead>
            <tbody>{resolved_rows if resolved_rows else '<tr><td colspan="5">None</td></tr>'}
            </tbody>
        </table>
    </section>

    <section id="unresolved-items">
        <h2>Unresolved Items ({len(unresolved_items)})</h2>
        <table>
            <thead>
                <tr>
                    <th>Item ID</th>
                    <th>Root Cause</th>
                    <th>Why Unresolved</th>
                    <th>What Was Tried</th>
                    <th>Missing Information</th>
                    <th>Next Steps</th>
                </tr>
            </thead>
            <tbody>{unresolved_rows if unresolved_rows else '<tr><td colspan="6">None</td></tr>'}
            </tbody>
        </table>
    </section>

    <section id="hash-verification">
        <h2>Hash Verification</h2>
        <table>
            <thead>
                <tr><th>Hash Type</th><th>Value</th></tr>
            </thead>
            <tbody>
                <tr><td>Snapshot Hash</td><td class="hash">{_esc(snapshot_hash)}</td></tr>
                <tr><td>Inspection Hash</td><td class="hash">{_esc(inspection_hash)}</td></tr>
                <tr><td>Final Target Hash</td><td class="hash">{_esc(final_target_hash)}</td></tr>
            </tbody>
        </table>
    </section>
</body>
</html>"""

    return html


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _status_class(decision: str, has_unresolved: bool) -> str:
    """Return the CSS class for the status label."""
    if decision == "cancel":
        return "status-cancelled"
    if has_unresolved:
        return "status-partial"
    return "status-resolved"


# ──────────────────────────────────────────────
# Handoff Report Generation
# ──────────────────────────────────────────────


def generate_handoff_report(unresolved_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate a handoff report for partial results.

    For each unresolved item, includes:
    - Exact unresolved issue
    - Root cause (known or unconfirmed)
    - Why not resolved
    - What was attempted
    - Missing information
    - User next steps
    - Step-by-step continuation
    - Retry conditions

    Returns a dict suitable for JSON serialization.
    """
    items_detail: list[dict[str, Any]] = []

    for item in unresolved_items:
        item_id = item.get("item_id", "")
        root_cause = item.get("root_cause", "Unknown")
        why_unresolved = item.get("why_unresolved", "")
        what_was_tried = item.get("what_was_tried", [])
        missing_information = item.get("missing_information", [])
        next_steps = item.get("next_steps", [])
        retry_guidance = item.get("retry_guidance", "")

        items_detail.append({
            "item_id": item_id,
            "exact_issue": why_unresolved,
            "root_cause": root_cause,
            "why_not_resolved": why_unresolved,
            "what_was_attempted": what_was_tried,
            "missing_information": missing_information,
            "user_next_steps": next_steps,
            "step_by_step_continuation": _build_continuation_steps(item),
            "retry_conditions": retry_guidance,
        })

    return {
        "handoff_type": "continuation",
        "total_unresolved": len(unresolved_items),
        "items": items_detail,
    }


def _build_continuation_steps(item: dict[str, Any]) -> list[str]:
    """Build step-by-step continuation instructions for an unresolved item."""
    steps: list[str] = []
    missing = item.get("missing_information", [])
    next_steps = item.get("next_steps", [])

    if missing:
        steps.append(f"1. Gather missing information: {', '.join(missing)}")
    if next_steps:
        for i, step in enumerate(next_steps, start=len(steps) + 1):
            steps.append(f"{i}. {step}")
    if not steps:
        steps.append("1. Review the item and determine next action manually.")

    return steps


# ──────────────────────────────────────────────
# Trace Construction
# ──────────────────────────────────────────────


def build_forward_trace(item_traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build forward traces: Snapshot → Scan → Pre-Sim → Sim/Iso → Inspection → Relay → Final.

    Each trace maps an item through all phases in forward order.
    """
    forward: list[dict[str, Any]] = []

    for trace in item_traces:
        forward.append({
            "item_id": trace.get("item_id", ""),
            "phase_0_snapshot": trace.get("phase_0_snapshot", ""),
            "phase_1_finding": trace.get("phase_1_finding", ""),
            "phase_2_item": trace.get("phase_2_item", ""),
            "phase_3_result": trace.get("phase_3_result", ""),
            "phase_4_inspection": trace.get("phase_4_inspection", ""),
            "phase_5_relay": trace.get("phase_5_relay", ""),
            "phase_6_final": trace.get("phase_6_final", ""),
            "trace_complete": trace.get("trace_complete", False),
        })

    return forward


def build_backward_trace(item_traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build backward traces: Final → Relay → Inspection → Sim/Iso → Pre-Sim → Phase 1 → Phase 0.

    Each trace maps an item through all phases in reverse order.
    """
    backward: list[dict[str, Any]] = []

    for trace in item_traces:
        backward.append({
            "item_id": trace.get("item_id", ""),
            "phase_6_final": trace.get("phase_6_final", ""),
            "phase_5_relay": trace.get("phase_5_relay", ""),
            "phase_4_inspection": trace.get("phase_4_inspection", ""),
            "phase_3_result": trace.get("phase_3_result", ""),
            "phase_2_item": trace.get("phase_2_item", ""),
            "phase_1_finding": trace.get("phase_1_finding", ""),
            "phase_0_snapshot": trace.get("phase_0_snapshot", ""),
            "trace_complete": trace.get("trace_complete", False),
        })

    return backward


# ──────────────────────────────────────────────
# Main Final Output Entry Point
# ──────────────────────────────────────────────


def build_final_output(inp: FinalOutputInput) -> FinalOutputPackage:
    """Execute Phase 6 Final Output.

    Always produces a final report regardless of decision path.

    Handles 3 paths:
    a) Apply (fully resolved): all issues resolved, released=True, success_note present.
    b) Apply (partial): some resolved + some unresolved, continuation_handoff present.
    c) Cancel: report what was resolved on candidate, not released, snapshot preserved.

    Returns a complete FinalOutputPackage with all artifacts.
    """
    resolved_count = len(inp.resolved_items)
    unresolved_count = len(inp.unresolved_items)

    # Enrich item traces with phase_6_final reference
    enriched_traces = _enrich_traces_with_final(inp.item_traces, inp.case_id)

    # Build forward and backward traces
    forward_traces = build_forward_trace(enriched_traces)
    backward_traces = build_backward_trace(enriched_traces)

    # Generate resolved.html
    resolved_html = generate_resolved_html(
        resolved_items=inp.resolved_items,
        unresolved_items=inp.unresolved_items,
        decision=inp.decision,
        snapshot_hash=inp.snapshot_hash,
        inspection_hash=inp.inspection_hash,
        final_target_hash=inp.final_target_hash,
    )

    # Generate handoff report if unresolved items exist
    handoff_report: dict[str, Any] | None = None
    if unresolved_count > 0:
        handoff_report = generate_handoff_report(inp.unresolved_items)

    # Build reports dict
    reports: dict[str, str] = {
        "final_report_json": f"final_report_{inp.case_id}.json",
        "resolved_html": resolved_html,
    }
    if handoff_report is not None:
        reports["handoff_report_json"] = f"handoff_report_{inp.case_id}.json"

    # Determine success_note or continuation_handoff based on path
    success_note = ""
    continuation_handoff = ""

    if inp.decision == "apply" and unresolved_count == 0:
        # Path A: Fully resolved apply
        success_note = (
            f"All {inp.total_issues} issues resolved and released. "
            f"Final target hash verified: {inp.final_target_hash[:16]}..."
        )
    elif inp.decision == "apply" and unresolved_count > 0:
        # Path B: Partial apply
        continuation_handoff = (
            f"{resolved_count} of {inp.total_issues} issues resolved and released. "
            f"{unresolved_count} issues require continuation. "
            f"See handoff report for step-by-step guidance."
        )
    else:
        # Path C: Cancel
        continuation_handoff = (
            f"Operation cancelled. {resolved_count} issues were resolved on candidate "
            f"but NOT released. Snapshot preserved (hash: {inp.snapshot_hash[:16]}...). "
            f"Reports preserved for review."
        )

    return FinalOutputPackage(
        case_id=inp.case_id,
        decision=inp.decision,
        total_issues=inp.total_issues,
        resolved_count=resolved_count,
        unresolved_count=unresolved_count,
        resolved_items=inp.resolved_items,
        unresolved_items=inp.unresolved_items,
        snapshot_hash=inp.snapshot_hash,
        inspection_hash=inp.inspection_hash,
        final_target_hash=inp.final_target_hash,
        reports=reports,
        forward_traces=forward_traces,
        backward_traces=backward_traces,
        success_note=success_note,
        continuation_handoff=continuation_handoff,
    )


# ──────────────────────────────────────────────
# Internal Helpers
# ──────────────────────────────────────────────


def _enrich_traces_with_final(
    item_traces: list[dict[str, Any]],
    case_id: str,
) -> list[dict[str, Any]]:
    """Add phase_6_final reference to each trace record."""
    enriched: list[dict[str, Any]] = []
    for trace in item_traces:
        enriched_trace = dict(trace)
        item_id = trace.get("item_id", "")
        enriched_trace["phase_6_final"] = f"final-{case_id}-{item_id}"
        # Mark trace as complete if all phases are present
        enriched_trace["trace_complete"] = all(
            enriched_trace.get(key, "")
            for key in [
                "phase_0_snapshot",
                "phase_1_finding",
                "phase_2_item",
                "phase_3_result",
                "phase_4_inspection",
                "phase_5_relay",
                "phase_6_final",
            ]
        )
        enriched.append(enriched_trace)
    return enriched
