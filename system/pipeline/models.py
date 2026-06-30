# Modified: 2026-06-27T20:15:00Z
"""Shared data models for the standalone pipeline Phase 0–6 outputs.

These models define the structured output contracts required by the
comprehensive system test. Each phase produces typed results that
can be validated, serialized, and traced.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────


class FindingCategory(str, Enum):
    DEPENDENCY_CONFLICT = "dependency_conflict"
    MISSING_DEPENDENCY = "missing_dependency"
    BROKEN_DEPENDENCY = "broken_dependency"
    MISSING_IMPORT = "missing_import"
    AMBIGUOUS_IMPORT = "ambiguous_import"
    SYNTAX_ERROR = "syntax_error"
    CIRCULAR_IMPORT = "circular_import"
    UNDEFINED_REFERENCE = "undefined_reference"
    TEST_FAILURE = "test_failure"
    CONFIGURATION_MISSING = "configuration_missing"
    OVERLAPPING_SIGNATURES = "overlapping_signatures"
    DEAD_CODE = "dead_code"
    CODE_DUPLICATION = "code_duplication"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ItemRoute(str, Enum):
    SIMULATION = "simulation"
    ISOLATION = "isolation"
    UNFIXABLE = "unfixable"


class IsolationStatus(str, Enum):
    PENDING = "pending"
    RESEARCH_IN_PROGRESS = "research_in_progress"
    RESOLVED = "resolved"
    INFORMATION_UNAVAILABLE = "information_unavailable"


# ──────────────────────────────────────────────
# Phase 0 — Snapshot
# ──────────────────────────────────────────────


@dataclass
class FileEntry:
    path: str
    hash: str
    size_bytes: int = 0


@dataclass
class SnapshotOutput:
    snapshot_id: str
    case_id: str
    target_path: str
    project_type: str = "python"
    file_count: int = 0
    files: list[FileEntry] = field(default_factory=list)
    dependency_files: list[str] = field(default_factory=list)
    snapshot_hash: str = ""
    user_snapshot_path: str = ""
    temp_snapshot_path: str = ""
    snapshot_complete: bool = False


# ──────────────────────────────────────────────
# Phase 1 — Scan + Analysis
# ──────────────────────────────────────────────


@dataclass
class ToolRecord:
    tool: str
    started_at: str = ""
    completed_at: str = ""
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    target: str = ""


@dataclass
class Finding:
    finding_id: str
    category: str  # FindingCategory value
    severity: str  # Severity value
    file: str
    line: int | None = None
    known_facts: list[str] = field(default_factory=list)
    root_cause: str = ""
    root_cause_confirmed: bool = False
    missing_information: list[str] = field(default_factory=list)
    supporting_tools: list[str] = field(default_factory=list)
    confidence: float = 0.0
    affected_component: str = ""


@dataclass
class AnalysisOutput:
    analysis_completed: bool = False
    tools_run: list[ToolRecord] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    handoff_statement: str = ""
    llm_statement: str = ""
    pre_calibration_statement: str = ""


# ──────────────────────────────────────────────
# Phase 2 — Pre-Simulation Information Completeness
# ──────────────────────────────────────────────


@dataclass
class ItemScore:
    item_id: str
    information_score: float = 0.0
    threshold: float = 93.91
    information_complete: bool = False
    known_information: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    route: str = ""  # ItemRoute value
    reason: str = ""


@dataclass
class PreSimulationOutput:
    case_id: str = ""
    overall_information_score: float = 0.0
    threshold: float = 93.91
    simulation_ready: bool = False
    package_complete_for_one_shot: bool = False
    route_mode: str = ""  # "clean" | "full_simulation" | "full_isolation" | "split"
    qualified_items: list[str] = field(default_factory=list)
    isolated_items: list[str] = field(default_factory=list)
    unfixable_items: list[str] = field(default_factory=list)
    item_scores: list[ItemScore] = field(default_factory=list)
    pipeline_continues: bool = True
    decision_reason: str = ""
    tool_candidates: dict[str, list[str]] = field(default_factory=dict)


# ──────────────────────────────────────────────
# Isolation
# ──────────────────────────────────────────────


@dataclass
class IsolationBrief:
    item_id: str
    reason_for_isolation: str = ""
    known_facts: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    research_scope: list[str] = field(default_factory=list)
    what_was_tried: list[str] = field(default_factory=list)
    next_action: str = ""
    retry_condition: str = ""


@dataclass
class IsolationReport:
    item_id: str
    status: str = ""  # IsolationStatus value
    why_isolated: str = ""
    missing_information: list[str] = field(default_factory=list)
    what_was_searched: list[str] = field(default_factory=list)
    what_was_tried: list[str] = field(default_factory=list)
    what_was_learned: str = ""
    is_fixable: bool | None = None
    next_action: str = ""
    user_must_provide: str = ""


# ──────────────────────────────────────────────
# Phase 3 — Simulation
# ──────────────────────────────────────────────


@dataclass
class PlannedMutation:
    file: str
    operation: str  # "replace", "create", "delete"
    before: str = ""
    after: str = ""


@dataclass
class CommandResult:
    command: str
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""


@dataclass
class SimulationOutput:
    simulation_id: str = ""
    candidate_path: str = ""
    source_snapshot_id: str = ""
    items_to_execute: list[str] = field(default_factory=list)
    planned_mutations: list[PlannedMutation] = field(default_factory=list)
    mutations_executed: list[dict[str, str]] = field(default_factory=list)
    validation_commands: list[str] = field(default_factory=list)
    commands: list[CommandResult] = field(default_factory=list)
    resolved_items: list[str] = field(default_factory=list)
    failed_items: list[str] = field(default_factory=list)
    simulation_succeeded: bool = False
    real_target_unchanged: bool = True


# ──────────────────────────────────────────────
# Phase 4 — Inspection
# ──────────────────────────────────────────────


@dataclass
class InspectionOutput:
    inspection_id: str = ""
    expected_items: list[str] = field(default_factory=list)
    received_items: list[str] = field(default_factory=list)
    resolved_items: list[str] = field(default_factory=list)
    unresolved_items: list[str] = field(default_factory=list)
    candidate_hash: str = ""
    report_hash: str = ""
    reports_complete: bool = False
    inspection_complete: bool = False


# ──────────────────────────────────────────────
# Phase 5 — Relay
# ──────────────────────────────────────────────


@dataclass
class RelayResolvedItem:
    item_id: str
    summary: str = ""


@dataclass
class RelayUnresolvedItem:
    item_id: str
    reason: str = ""
    next_steps: list[str] = field(default_factory=list)


@dataclass
class RelayOutput:
    inspection_hash_verified: bool = False
    snapshot_hash: str = ""
    candidate_hash: str = ""
    resolved: list[RelayResolvedItem] = field(default_factory=list)
    unresolved: list[RelayUnresolvedItem] = field(default_factory=list)
    available_actions: list[str] = field(default_factory=lambda: ["apply", "cancel"])
    decision: str = ""  # "apply" | "cancel" | "" (awaiting)


# ──────────────────────────────────────────────
# Phase 6 — Final Output
# ──────────────────────────────────────────────


@dataclass
class FinalOutputResult:
    total_issues: int = 0
    root_causes: list[dict[str, str]] = field(default_factory=list)
    resolved_items: list[dict[str, Any]] = field(default_factory=list)
    unresolved_items: list[dict[str, Any]] = field(default_factory=list)
    resolved_html: str = ""
    what_was_tried: list[str] = field(default_factory=list)
    user_next_steps: list[str] = field(default_factory=list)
    continuation_handoff: str = ""
    success_note: str = ""


# ──────────────────────────────────────────────
# Resolution Contract (PreSimulation → Simulation)
# ──────────────────────────────────────────────


@dataclass
class ToolInvocation:
    """A single tool invocation within a resolution contract.

    The Resolution Planner specifies which tool to use, with what parameters,
    and in what order. The toolkit executes these invocations deterministically.
    """
    tool_name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    expected_files_modified: list[str] = field(default_factory=list)


@dataclass
class ResolutionContract:
    """Contract produced by the Resolution Planner (PreSimulation phase).

    The coding agent does NOT mutate files. It analyzes issues and produces
    a contract that specifies:
    - Which tools should be used
    - In what order
    - With what parameters
    - What outcome is expected

    The contract then enters the same pipeline as deterministic candidates:
    Tool Binding → Simulation → Inspection → Scoring

    No single entity can both propose AND validate AND execute.
    """
    contract_id: str = ""
    finding_id: str = ""
    planner: str = ""  # "coding_agent" | "deterministic" | "manual"
    recommended_tools: list[ToolInvocation] = field(default_factory=list)
    execution_order: list[str] = field(default_factory=list)
    expected_outcome: str = ""
    confidence: float = 0.0
    rationale: str = ""
    survived_simulation: bool = False
    survived_inspection: bool = False


# ──────────────────────────────────────────────
# Agent Performance Ledger
# ──────────────────────────────────────────────


@dataclass
class AgentRunRecord:
    """Standardized evaluation trace for a single agent run.

    Every agent invocation produces one record. Records are immutable.
    Same input + same scoring pipeline = comparable experiments.

    Captures:
    - PreSimulation: agent intent (ResolutionContract)
    - Simulation: tool execution behavior
    - Inspection: truth validation
    - Scoring: unified final score
    """
    run_id: str = ""
    agent_id: str = ""
    model_version: str = ""
    finding_id: str = ""
    issue_type: str = ""
    resolution_contract: dict[str, Any] = field(default_factory=dict)
    tools_used: list[str] = field(default_factory=list)
    simulation_pass: bool = False
    inspection_pass: bool = False
    regressions: int = 0
    conflicts: int = 0
    execution_time_ms: int = 0
    final_score: float = 0.0
    pass_fail: str = ""  # "pass" | "fail"
    timestamp: str = ""


@dataclass
class AgentLedgerEntry:
    """Aggregated performance metrics for a single agent.

    Built from multiple AgentRunRecords. Enables fair comparison
    across agents under identical conditions.
    """
    agent_id: str = ""
    total_runs: int = 0
    pass_count: int = 0
    fail_count: int = 0
    avg_score: float = 0.0
    success_rate: float = 0.0
    regression_rate: float = 0.0
    conflict_rate: float = 0.0
    avg_execution_time_ms: int = 0
    failure_patterns: dict[str, int] = field(default_factory=dict)
    tool_selection_quality: float = 0.0
