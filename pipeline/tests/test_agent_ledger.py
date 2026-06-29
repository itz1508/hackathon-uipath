# Modified: 2026-06-24T09:10:00Z
"""Tests for the Agent Performance Ledger.

Verifies:
1. AgentRunRecord and AgentLedgerEntry data models
2. Scoring engine (compute_score)
3. Failure classification
4. Record creation and storage
5. Aggregation and ledger building
6. Fair comparison across agents
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from models import AgentLedgerEntry, AgentRunRecord, ResolutionContract, ToolInvocation
from agent_ledger import (
    build_ledger_entry,
    build_full_ledger,
    classify_failure,
    compute_score,
    create_run_record,
    format_ledger_report,
    load_run_records,
    save_run_record,
    _LEDGER_DIR,
)


# ──────────────────────────────────────────────
# Scoring engine
# ──────────────────────────────────────────────


class TestScoringEngine:
    """Verify the unified scoring function."""

    def test_perfect_run(self):
        """Simulation pass + inspection pass + no regressions/conflicts = 0.90"""
        score = compute_score(
            simulation_pass=True,
            inspection_pass=True,
            regressions=0,
            conflicts=0,
            tool_selection_match=False,
        )
        assert score == 0.80  # 0.50 + 0.30

    def test_perfect_with_tool_bonus(self):
        """Perfect run + correct tool selection = 0.90"""
        score = compute_score(
            simulation_pass=True,
            inspection_pass=True,
            regressions=0,
            conflicts=0,
            tool_selection_match=True,
        )
        assert score == 0.90  # 0.50 + 0.30 + 0.10

    def test_simulation_failure(self):
        """Simulation fails = 0.0 correctness"""
        score = compute_score(
            simulation_pass=False,
            inspection_pass=False,
            regressions=0,
            conflicts=0,
        )
        assert score == 0.0

    def test_inspection_failure(self):
        """Simulation passes but inspection fails = 0.50"""
        score = compute_score(
            simulation_pass=True,
            inspection_pass=False,
            regressions=0,
            conflicts=0,
        )
        assert score == 0.50

    def test_regression_penalty(self):
        """Each regression costs 0.10, capped at 0.30"""
        score = compute_score(
            simulation_pass=True,
            inspection_pass=True,
            regressions=2,
            conflicts=0,
        )
        assert score == 0.60  # 0.80 - 0.20

    def test_regression_penalty_capped(self):
        """Regression penalty capped at 0.30"""
        score = compute_score(
            simulation_pass=True,
            inspection_pass=True,
            regressions=5,
            conflicts=0,
        )
        assert score == 0.50  # 0.80 - 0.30

    def test_conflict_penalty(self):
        """Each conflict costs 0.10, capped at 0.20"""
        score = compute_score(
            simulation_pass=True,
            inspection_pass=True,
            regressions=0,
            conflicts=1,
        )
        assert score == 0.70  # 0.80 - 0.10

    def test_combined_penalties(self):
        """Both regressions and conflicts"""
        score = compute_score(
            simulation_pass=True,
            inspection_pass=True,
            regressions=1,
            conflicts=1,
        )
        assert score == 0.60  # 0.80 - 0.10 - 0.10

    def test_score_never_negative(self):
        """Score is bounded at 0.0"""
        score = compute_score(
            simulation_pass=True,
            inspection_pass=True,
            regressions=10,
            conflicts=10,
        )
        assert score >= 0.0

    def test_score_never_exceeds_one(self):
        """Score is bounded at 1.0"""
        score = compute_score(
            simulation_pass=True,
            inspection_pass=True,
            regressions=0,
            conflicts=0,
            tool_selection_match=True,
        )
        assert score <= 1.0


# ──────────────────────────────────────────────
# Failure classification
# ──────────────────────────────────────────────


class TestFailureClassification:
    """Verify failure mode classification."""

    def test_success(self):
        assert classify_failure(True, True, 0, 0, ["refactor"], ["refactor"]) == "success"

    def test_tool_misuse(self):
        assert classify_failure(True, True, 0, 0, ["dep_fix"], ["refactor"]) == "tool_misuse"

    def test_regression(self):
        assert classify_failure(True, True, 2, 0, ["refactor"], ["refactor"]) == "regression"

    def test_conflict(self):
        assert classify_failure(True, True, 0, 1, ["refactor"], ["refactor"]) == "conflict"

    def test_simulation_failure(self):
        assert classify_failure(False, False, 0, 0, ["refactor"], ["refactor"]) == "simulation_failure"

    def test_inspection_failure(self):
        assert classify_failure(True, False, 0, 0, ["refactor"], ["refactor"]) == "inspection_failure"


# ──────────────────────────────────────────────
# Record creation and storage
# ──────────────────────────────────────────────


class TestRecordStorage:
    """Verify immutable JSON record storage."""

    def test_create_run_record(self):
        contract = ResolutionContract(
            contract_id="rc-001",
            finding_id="f-1",
            planner="coding_agent",
            recommended_tools=[ToolInvocation(tool_name="refactor")],
            confidence=0.92,
        )

        record = create_run_record(
            agent_id="claude-sonnet-4",
            finding_id="f-1",
            issue_type="syntax_error",
            contract=contract,
            tools_used=["refactor"],
            expected_tools=["refactor"],
            simulation_pass=True,
            inspection_pass=True,
        )

        assert record.agent_id == "claude-sonnet-4"
        assert record.pass_fail == "pass"
        assert record.final_score > 0.0
        assert record.run_id.startswith("run-")

    def test_save_and_load(self, tmp_path, monkeypatch):
        """Records can be saved and loaded back."""
        monkeypatch.setattr("agent_ledger._LEDGER_DIR", tmp_path)

        contract = ResolutionContract(
            contract_id="rc-002",
            finding_id="f-2",
            planner="deterministic",
            recommended_tools=[ToolInvocation(tool_name="dep_fix")],
            confidence=0.70,
        )

        record = create_run_record(
            agent_id="test-agent",
            finding_id="f-2",
            issue_type="dependency_conflict",
            contract=contract,
            tools_used=["dep_fix"],
            expected_tools=["dep_fix"],
            simulation_pass=True,
            inspection_pass=True,
        )

        file_path = save_run_record(record)
        assert Path(file_path).exists()

        loaded = load_run_records("test-agent")
        assert len(loaded) == 1
        assert loaded[0].agent_id == "test-agent"
        assert loaded[0].finding_id == "f-2"

    def test_load_filters_by_agent(self, tmp_path, monkeypatch):
        """Loading can filter by agent_id."""
        monkeypatch.setattr("agent_ledger._LEDGER_DIR", tmp_path)

        for agent in ["agent-a", "agent-b"]:
            contract = ResolutionContract(contract_id=f"rc-{agent}")
            record = create_run_record(
                agent_id=agent,
                finding_id="f-1",
                issue_type="syntax_error",
                contract=contract,
                tools_used=["refactor"],
                expected_tools=["refactor"],
                simulation_pass=True,
                inspection_pass=True,
            )
            save_run_record(record)

        a_records = load_run_records("agent-a")
        assert len(a_records) == 1
        assert a_records[0].agent_id == "agent-a"

        b_records = load_run_records("agent-b")
        assert len(b_records) == 1
        assert b_records[0].agent_id == "agent-b"


# ──────────────────────────────────────────────
# Aggregation
# ──────────────────────────────────────────────


class TestAggregation:
    """Verify ledger aggregation."""

    def test_build_ledger_entry(self, tmp_path, monkeypatch):
        """Ledger entry aggregates multiple runs."""
        monkeypatch.setattr("agent_ledger._LEDGER_DIR", tmp_path)

        for i in range(5):
            contract = ResolutionContract(contract_id=f"rc-{i}")
            record = create_run_record(
                agent_id="claude",
                finding_id=f"f-{i}",
                issue_type="syntax_error",
                contract=contract,
                tools_used=["refactor"],
                expected_tools=["refactor"],
                simulation_pass=True,
                inspection_pass=True,
            )
            save_run_record(record)

        entry = build_ledger_entry("claude")
        assert entry.agent_id == "claude"
        assert entry.total_runs == 5
        assert entry.pass_count == 5
        assert entry.success_rate == 1.0
        assert entry.avg_score > 0.0

    def test_empty_ledger_entry(self, tmp_path, monkeypatch):
        """Empty agent gets zeroed entry."""
        monkeypatch.setattr("agent_ledger._LEDGER_DIR", tmp_path)

        entry = build_ledger_entry("nonexistent")
        assert entry.total_runs == 0
        assert entry.avg_score == 0.0

    def test_format_report(self, tmp_path, monkeypatch):
        """Report formatting works."""
        monkeypatch.setattr("agent_ledger._LEDGER_DIR", tmp_path)

        contract = ResolutionContract(contract_id="rc-rpt")
        record = create_run_record(
            agent_id="test-agent",
            finding_id="f-1",
            issue_type="syntax_error",
            contract=contract,
            tools_used=["refactor"],
            expected_tools=["refactor"],
            simulation_pass=True,
            inspection_pass=True,
        )
        save_run_record(record)

        entries = build_full_ledger()
        report = format_ledger_report(entries)
        assert "test-agent" in report
        assert "Avg Score" in report

    def test_empty_report(self):
        """Empty ledger produces a message."""
        report = format_ledger_report([])
        assert "No agent runs" in report
