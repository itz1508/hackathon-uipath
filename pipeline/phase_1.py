# Modified: 2026-06-29T20:00:00Z
"""Phase 1: Scan — raw tool output only.

Phase 1 ONLY runs the scanner tools and returns raw results.
No analysis, no statements, no classification.
Just:
- Run compileall
- Run import validation
- Run dependency inspection
- Return raw findings and tool records

Analysis (statements + classification) is Phase 2.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from phase_models import PhaseResult, PHASE_NAMES
from phase_controller import PhaseController
from scanner import scan_target


def transform_phase_1(state: "PipelineState", controller: PhaseController) -> "PipelineState":
    """Phase 1 pure transformation: Reads snapshot. Writes findings, flags.

    Runs scanner tools and returns raw output. CANNOT interpret meaning.
    """
    from pipeline_state import PipelineState

    state.validate_transition(1)
    controller.start_phase(1)

    target_path = state.snapshot.get("target_path", "")
    analysis = scan_target(target_path)

    scan_results: list[dict[str, Any]] = []
    for finding in analysis.findings:
        scan_results.append({
            "finding_id": finding.finding_id,
            "category": finding.category,
            "severity": finding.severity,
            "file": finding.file,
            "line": finding.line,
            "known_facts": finding.known_facts,
            "root_cause": finding.root_cause,
            "root_cause_confirmed": finding.root_cause_confirmed,
            "missing_information": finding.missing_information,
            "supporting_tools": finding.supporting_tools,
            "confidence": finding.confidence,
            "affected_component": finding.affected_component,
        })

    state.findings = scan_results
    state.flags.scan_complete = True

    result = PhaseResult(
        phase=1,
        phase_name=PHASE_NAMES[1],
        exit_status="completed",
        required_outputs={
            "scan_results": scan_results,
            "tools_run": [
                {
                    "tool": record.tool,
                    "started_at": record.started_at,
                    "completed_at": record.completed_at,
                    "exit_code": record.exit_code,
                    "stdout": record.stdout,
                    "stderr": record.stderr,
                    "target": record.target,
                }
                for record in analysis.tools_run
            ],
            "total_findings": len(scan_results),
        },
        duration_ms=0,
    )
    controller.complete_phase(result)
    return state


def execute_phase_1_scan(
    controller: PhaseController, snapshot: dict[str, Any]
) -> PhaseResult:
    """Phase 1: Scan — run scanner tools and return raw output.

    Delegates scanning to scanner.scan_target() which performs:
    - Python syntax validation (compileall)
    - Import resolution (AST-based)
    - Dependency manifest inspection
    - Deduplication and conflict detection

    Returns raw scan_results (list of findings) and tools_run (list of tool records).
    NO statements, NO classification — that's Phase 2.
    """
    controller.start_phase(1)
    start = datetime.now(timezone.utc)

    target_path = snapshot.get("target_path", "")

    # Delegate to the scanner module — get raw output
    analysis = scan_target(target_path)

    # Convert findings to raw dicts for downstream consumption
    scan_results: list[dict[str, Any]] = []
    for finding in analysis.findings:
        scan_results.append({
            "finding_id": finding.finding_id,
            "category": finding.category,
            "severity": finding.severity,
            "file": finding.file,
            "line": finding.line,
            "known_facts": finding.known_facts,
            "root_cause": finding.root_cause,
            "root_cause_confirmed": finding.root_cause_confirmed,
            "missing_information": finding.missing_information,
            "supporting_tools": finding.supporting_tools,
            "confidence": finding.confidence,
            "affected_component": finding.affected_component,
        })

    # Convert tool records to raw dicts
    tools_run: list[dict[str, Any]] = []
    for record in analysis.tools_run:
        tools_run.append({
            "tool": record.tool,
            "started_at": record.started_at,
            "completed_at": record.completed_at,
            "exit_code": record.exit_code,
            "stdout": record.stdout,
            "stderr": record.stderr,
            "target": record.target,
        })

    duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    result = PhaseResult(
        phase=1,
        phase_name=PHASE_NAMES[1],
        exit_status="completed",
        required_outputs={
            "scan_results": scan_results,
            "tools_run": tools_run,
            "total_findings": len(scan_results),
        },
        duration_ms=duration,
    )
    controller.complete_phase(result)
    return result
