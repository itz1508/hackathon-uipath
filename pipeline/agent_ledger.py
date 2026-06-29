# Modified: 2026-06-24T09:00:00Z
"""Agent Performance Ledger — standardized evaluation and comparison.

Every agent run is a comparable experiment:
    Same input → Same scoring pipeline → Fully logged intermediate artifacts

Architecture:
    AgentRunRecord (per run) → Scoring Engine → AgentLedgerEntry (aggregated)

Scoring model:
    final_score = correctness + coverage - regression_penalty - conflict_penalty

Storage:
    Immutable JSON records in .agent_ledger/ directory.
    Each run is one JSON file. Aggregation reads all records.

Fair validation protocol:
    Rule 1: Same input set for all agents
    Rule 2: Same toolkit (agents cannot change execution tools)
    Rule 3: Same simulation + inspection (only pipeline evaluates truth)
    Rule 4: No hidden retries (1 run = 1 evaluation)
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models import AgentLedgerEntry, AgentRunRecord, ResolutionContract


# ──────────────────────────────────────────────
# Ledger storage
# ──────────────────────────────────────────────

_LEDGER_DIR = Path.home() / ".NextFlow" / "agent_ledger"


def _ensure_ledger_dir() -> Path:
    """Create the ledger directory if it doesn't exist."""
    _LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    return _LEDGER_DIR


def save_run_record(record: AgentRunRecord) -> str:
    """Save an immutable agent run record as JSON.

    Returns the file path where the record was saved.
    """
    ledger_dir = _ensure_ledger_dir()

    if not record.run_id:
        record.run_id = f"run-{uuid.uuid4().hex[:12]}"
    if not record.timestamp:
        record.timestamp = datetime.now(timezone.utc).isoformat()

    file_path = ledger_dir / f"{record.run_id}.json"
    data = asdict(record)
    file_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return str(file_path)


def load_run_records(agent_id: str | None = None) -> list[AgentRunRecord]:
    """Load all run records, optionally filtered by agent_id."""
    ledger_dir = _ensure_ledger_dir()
    records: list[AgentRunRecord] = []

    for file_path in sorted(ledger_dir.glob("run-*.json")):
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            record = AgentRunRecord(**data)
            if agent_id is None or record.agent_id == agent_id:
                records.append(record)
        except (json.JSONDecodeError, TypeError):
            continue

    return records


# ──────────────────────────────────────────────
# Scoring engine
# ──────────────────────────────────────────────


def compute_score(
    simulation_pass: bool,
    inspection_pass: bool,
    regressions: int,
    conflicts: int,
    tool_selection_match: bool = False,
) -> float:
    """Compute unified final score for an agent run.

    Scoring model:
        final_score = correctness_score + coverage_score
                    - regression_penalty - conflict_penalty

    Components:
        correctness_score: 0.50 if simulation passes, 0 otherwise
        coverage_score:    0.30 if inspection passes, 0 otherwise
        regression_penalty: 0.10 per regression (capped at 0.30)
        conflict_penalty:   0.10 per conflict (capped at 0.20)
        tool_selection_bonus: 0.10 if tools match expected (AI recommended correctly)

    Range: 0.0 to 1.0
    """
    correctness = 0.50 if simulation_pass else 0.0
    coverage = 0.30 if inspection_pass else 0.0
    regression_penalty = min(0.30, regressions * 0.10)
    conflict_penalty = min(0.20, conflicts * 0.10)
    tool_bonus = 0.10 if tool_selection_match else 0.0

    score = correctness + coverage + tool_bonus - regression_penalty - conflict_penalty
    return max(0.0, min(1.0, round(score, 4)))


def classify_failure(
    simulation_pass: bool,
    inspection_pass: bool,
    regressions: int,
    conflicts: int,
    tools_used: list[str],
    expected_tools: list[str],
) -> str:
    """Classify the failure mode of an agent run.

    Categories:
        - tool_misuse: agent recommended wrong tools
        - regression: fix introduced new issues
        - conflict: fix conflicted with other changes
        - simulation_failure: fix didn't pass simulation
        - inspection_failure: fix passed simulation but failed inspection
        - success: no failure
    """
    if tools_used and expected_tools and set(tools_used) != set(expected_tools):
        return "tool_misuse"

    if simulation_pass and inspection_pass and regressions == 0 and conflicts == 0:
        return "success"
    if regressions > 0:
        return "regression"
    if conflicts > 0:
        return "conflict"
    if not simulation_pass:
        return "simulation_failure"
    if not inspection_pass:
        return "inspection_failure"
    return "unknown"


# ──────────────────────────────────────────────
# Record creation
# ──────────────────────────────────────────────


def create_run_record(
    agent_id: str,
    finding_id: str,
    issue_type: str,
    contract: ResolutionContract,
    tools_used: list[str],
    expected_tools: list[str],
    simulation_pass: bool,
    inspection_pass: bool,
    regressions: int = 0,
    conflicts: int = 0,
    execution_time_ms: int = 0,
    model_version: str = "",
) -> AgentRunRecord:
    """Create a complete AgentRunRecord from pipeline execution data.

    This is the main entry point for logging agent runs. Called at the
    end of the pipeline (after Inspection) to capture the full trace.
    """
    tool_match = set(tools_used) == set(expected_tools) if expected_tools else False
    score = compute_score(simulation_pass, inspection_pass, regressions, conflicts, tool_match)
    failure = classify_failure(simulation_pass, inspection_pass, regressions, conflicts, tools_used, expected_tools)

    return AgentRunRecord(
        run_id=f"run-{uuid.uuid4().hex[:12]}",
        agent_id=agent_id,
        model_version=model_version,
        finding_id=finding_id,
        issue_type=issue_type,
        resolution_contract={
            "contract_id": contract.contract_id,
            "planner": contract.planner,
            "tools": [inv.tool_name for inv in contract.recommended_tools],
            "confidence": contract.confidence,
        },
        tools_used=tools_used,
        simulation_pass=simulation_pass,
        inspection_pass=inspection_pass,
        regressions=regressions,
        conflicts=conflicts,
        execution_time_ms=execution_time_ms,
        final_score=score,
        pass_fail="pass" if failure == "success" else "fail",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ──────────────────────────────────────────────
# Aggregation
# ──────────────────────────────────────────────


def build_ledger_entry(agent_id: str) -> AgentLedgerEntry:
    """Build an aggregated ledger entry for a single agent.

    Reads all run records for the agent and computes:
    - Average score
    - Success rate
    - Regression rate
    - Conflict rate
    - Failure pattern distribution
    - Tool selection quality
    """
    records = load_run_records(agent_id)

    if not records:
        return AgentLedgerEntry(agent_id=agent_id)

    total = len(records)
    pass_count = sum(1 for r in records if r.pass_fail == "pass")
    fail_count = total - pass_count
    avg_score = sum(r.final_score for r in records) / total
    success_rate = pass_count / total
    total_regressions = sum(r.regressions for r in records)
    total_conflicts = sum(r.conflicts for r in records)
    regression_rate = total_regressions / total
    conflict_rate = total_conflicts / total
    avg_time = sum(r.execution_time_ms for r in records) // total

    # Failure patterns
    patterns: dict[str, int] = {}
    for r in records:
        if r.pass_fail == "fail":
            failure_type = classify_failure(
                r.simulation_pass, r.inspection_pass,
                r.regressions, r.conflicts,
                r.tools_used, [],
            )
            patterns[failure_type] = patterns.get(failure_type, 0) + 1

    # Tool selection quality: % of runs where tools matched expected
    tool_matches = sum(
        1 for r in records
        if r.resolution_contract.get("tools") and
        set(r.tools_used) == set(r.resolution_contract.get("tools", []))
    )
    tool_quality = tool_matches / total if total > 0 else 0.0

    return AgentLedgerEntry(
        agent_id=agent_id,
        total_runs=total,
        pass_count=pass_count,
        fail_count=fail_count,
        avg_score=round(avg_score, 4),
        success_rate=round(success_rate, 4),
        regression_rate=round(regression_rate, 4),
        conflict_rate=round(conflict_rate, 4),
        avg_execution_time_ms=avg_time,
        failure_patterns=patterns,
        tool_selection_quality=round(tool_quality, 4),
    )


def build_full_ledger() -> list[AgentLedgerEntry]:
    """Build ledger entries for all agents."""
    all_records = load_run_records()
    agent_ids = set(r.agent_id for r in all_records)
    return [build_ledger_entry(aid) for aid in sorted(agent_ids)]


def format_ledger_report(entries: list[AgentLedgerEntry]) -> str:
    """Format ledger entries as a human-readable comparison report."""
    if not entries:
        return "No agent runs recorded."

    lines = [
        "=" * 70,
        "Agent Performance Ledger",
        "=" * 70,
        "",
    ]

    for entry in entries:
        lines.append(f"Agent: {entry.agent_id}")
        lines.append(f"  Runs:           {entry.total_runs}")
        lines.append(f"  Avg Score:      {entry.avg_score:.2%}")
        lines.append(f"  Success Rate:   {entry.success_rate:.2%}")
        lines.append(f"  Regression Rate:{entry.regression_rate:.2%}")
        lines.append(f"  Conflict Rate:  {entry.conflict_rate:.2%}")
        lines.append(f"  Tool Quality:   {entry.tool_selection_quality:.2%}")
        lines.append(f"  Avg Time:       {entry.avg_execution_time_ms}ms")
        if entry.failure_patterns:
            lines.append(f"  Failures:       {entry.failure_patterns}")
        lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)
