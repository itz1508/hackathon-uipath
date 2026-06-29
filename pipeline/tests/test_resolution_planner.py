# Modified: 2026-06-24T08:40:00Z
"""Tests for the Resolution Planner — contract-driven execution architecture.

The Resolution Planner sits in PreSimulation (Phase 2). It analyzes issues
using Claude Code CLI (or Anthropic API) and produces ResolutionContracts.

Key principle: The planner does NOT mutate files. It produces contracts
that specify which tools to use, in what order, with what parameters.
The toolkit executes deterministically. Simulation proves. Inspection validates.

Tests verify:
1. ResolutionContract and ToolInvocation data models
2. plan_resolutions() produces valid contracts
3. Deterministic tool selection works
4. AI recommendation merging works
5. Confidence scoring works
6. Integration with pre_simulation.filter_tool_candidates
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from models import (
    Finding,
    FindingCategory,
    ResolutionContract,
    ToolInvocation,
)


# ──────────────────────────────────────────────
# Data model tests
# ──────────────────────────────────────────────


class TestResolutionContract:
    """Verify ResolutionContract data model."""

    def test_contract_creation(self):
        contract = ResolutionContract(
            contract_id="rc-001",
            finding_id="finding-1",
            planner="coding_agent",
            recommended_tools=[
                ToolInvocation(tool_name="refactor", parameters={"fix": "colon"}),
                ToolInvocation(tool_name="import_repair"),
            ],
            execution_order=["refactor", "import_repair"],
            expected_outcome="Syntax error resolved",
            confidence=0.92,
            rationale="Missing colon after def statement",
        )
        assert contract.contract_id == "rc-001"
        assert contract.planner == "coding_agent"
        assert len(contract.recommended_tools) == 2
        assert contract.confidence == 0.92
        assert not contract.survived_simulation
        assert not contract.survived_inspection

    def test_tool_invocation_parameters(self):
        inv = ToolInvocation(
            tool_name="dep_fix",
            parameters={"package": "requests", "from_version": "2.28", "to_version": "2.31"},
            expected_files_modified=["requirements.txt"],
        )
        assert inv.tool_name == "dep_fix"
        assert inv.parameters["package"] == "requests"
        assert "requirements.txt" in inv.expected_files_modified

    def test_empty_contract(self):
        contract = ResolutionContract()
        assert contract.contract_id == ""
        assert contract.recommended_tools == []
        assert contract.confidence == 0.0


# ──────────────────────────────────────────────
# Resolution Planner tests
# ──────────────────────────────────────────────


class TestResolutionPlanner:
    """Verify the Resolution Planner produces valid contracts."""

    def test_plan_resolutions_importable(self):
        from resolution_planner import plan_resolutions
        assert callable(plan_resolutions)

    def test_plan_single_syntax_error(self):
        """Syntax error should produce a contract with refactor tool."""
        from resolution_planner import plan_resolutions

        finding = Finding(
            finding_id="syn-1",
            category=FindingCategory.SYNTAX_ERROR.value,
            severity="critical",
            file="main.py",
            root_cause="Missing colon after def",
            root_cause_confirmed=True,
            known_facts=["Line 1: def broken() — missing colon"],
        )

        contracts = plan_resolutions([finding], "/tmp/test")

        assert len(contracts) == 1
        contract = contracts[0]
        assert contract.finding_id == "syn-1"
        assert len(contract.recommended_tools) > 0
        # refactor should be in the tools (deterministic match)
        tool_names = [inv.tool_name for inv in contract.recommended_tools]
        assert "refactor" in tool_names
        assert contract.confidence > 0.0
        assert contract.expected_outcome != ""

    def test_plan_dependency_conflict(self):
        """Dependency conflict should produce a contract with dep_fix tool."""
        from resolution_planner import plan_resolutions

        finding = Finding(
            finding_id="dep-1",
            category=FindingCategory.DEPENDENCY_CONFLICT.value,
            severity="high",
            file="requirements.txt",
            root_cause="Duplicate dependency: requests",
            root_cause_confirmed=True,
            known_facts=["requests appears twice"],
        )

        contracts = plan_resolutions([finding], "/tmp/test")

        assert len(contracts) == 1
        tool_names = [inv.tool_name for inv in contracts[0].recommended_tools]
        assert "dep_fix" in tool_names

    def test_plan_missing_import(self):
        """Missing import should produce a contract with import_repair tool."""
        from resolution_planner import plan_resolutions

        finding = Finding(
            finding_id="imp-1",
            category=FindingCategory.MISSING_IMPORT.value,
            severity="high",
            file="app.py",
            root_cause="Module 'os' not imported",
            root_cause_confirmed=True,
            known_facts=["os used but not imported"],
        )

        contracts = plan_resolutions([finding], "/tmp/test")

        assert len(contracts) == 1
        tool_names = [inv.tool_name for inv in contracts[0].recommended_tools]
        assert "import_repair" in tool_names

    def test_plan_multiple_findings(self):
        """Multiple findings should produce multiple contracts."""
        from resolution_planner import plan_resolutions

        findings = [
            Finding(
                finding_id="f-1",
                category=FindingCategory.SYNTAX_ERROR.value,
                severity="critical",
                file="a.py",
                root_cause="Missing colon",
                root_cause_confirmed=True,
            ),
            Finding(
                finding_id="f-2",
                category=FindingCategory.DEPENDENCY_CONFLICT.value,
                severity="high",
                file="requirements.txt",
                root_cause="Duplicate dep",
                root_cause_confirmed=True,
            ),
        ]

        contracts = plan_resolutions(findings, "/tmp/test")

        assert len(contracts) == 2
        assert contracts[0].finding_id == "f-1"
        assert contracts[1].finding_id == "f-2"

    def test_plan_empty_findings(self):
        """Empty findings should produce empty contracts."""
        from resolution_planner import plan_resolutions

        contracts = plan_resolutions([], "/tmp/test")
        assert contracts == []


# ──────────────────────────────────────────────
# Deterministic tool selection
# ──────────────────────────────────────────────


class TestDeterministicToolSelection:
    """Verify deterministic tool selection maps categories correctly."""

    def test_syntax_error_maps_to_refactor(self):
        from resolution_planner import _select_deterministic_tools

        finding = Finding(
            finding_id="t-1",
            category=FindingCategory.SYNTAX_ERROR.value,
            severity="critical",
            file="main.py",
            root_cause="error",
        )
        tools = _select_deterministic_tools(finding)
        assert "refactor" in tools

    def test_circular_import_maps_to_refactor(self):
        from resolution_planner import _select_deterministic_tools

        finding = Finding(
            finding_id="t-2",
            category=FindingCategory.CIRCULAR_IMPORT.value,
            severity="high",
            file="a.py",
            root_cause="cycle",
        )
        tools = _select_deterministic_tools(finding)
        assert "refactor" in tools

    def test_dependency_conflict_maps_to_dep_fix(self):
        from resolution_planner import _select_deterministic_tools

        finding = Finding(
            finding_id="t-3",
            category=FindingCategory.DEPENDENCY_CONFLICT.value,
            severity="high",
            file="requirements.txt",
            root_cause="dup",
        )
        tools = _select_deterministic_tools(finding)
        assert "dep_fix" in tools

    def test_missing_import_maps_to_import_repair(self):
        from resolution_planner import _select_deterministic_tools

        finding = Finding(
            finding_id="t-4",
            category=FindingCategory.MISSING_IMPORT.value,
            severity="high",
            file="app.py",
            root_cause="missing",
        )
        tools = _select_deterministic_tools(finding)
        assert "import_repair" in tools

    def test_unknown_category_returns_empty(self):
        from resolution_planner import _select_deterministic_tools

        finding = Finding(
            finding_id="t-5",
            category="unknown_category",
            severity="low",
            file="x.py",
            root_cause="?",
        )
        tools = _select_deterministic_tools(finding)
        assert tools == []


# ──────────────────────────────────────────────
# Confidence scoring
# ──────────────────────────────────────────────


class TestConfidenceScoring:
    """Verify confidence computation logic."""

    def test_deterministic_only_baseline(self):
        from resolution_planner import _compute_confidence

        confidence = _compute_confidence(["refactor"], None)
        assert confidence == 0.70

    def test_no_tools_no_ai(self):
        from resolution_planner import _compute_confidence

        confidence = _compute_confidence([], None)
        assert confidence == 0.0

    def test_ai_agrees_with_deterministic(self):
        from resolution_planner import _compute_confidence

        ai_rec = {
            "recommended_tools": ["refactor"],
            "confidence": 0.95,
        }
        confidence = _compute_confidence(["refactor"], ai_rec)
        assert confidence >= 0.85

    def test_ai_disagrees_with_deterministic(self):
        from resolution_planner import _compute_confidence

        ai_rec = {
            "recommended_tools": ["import_repair"],
            "confidence": 0.90,
        }
        confidence = _compute_confidence(["refactor"], ai_rec)
        assert confidence == 0.75

    def test_ai_only_no_deterministic(self):
        from resolution_planner import _compute_confidence

        ai_rec = {
            "recommended_tools": ["test_repair"],
            "confidence": 0.85,
        }
        confidence = _compute_confidence([], ai_rec)
        assert confidence <= 0.85


# ──────────────────────────────────────────────
# Integration with pre_simulation
# ──────────────────────────────────────────────


class TestPreSimulationIntegration:
    """Verify the planner integrates correctly with filter_tool_candidates."""

    def test_filter_tool_candidates_no_coding_agent(self):
        """CodingAgentTool should NOT be in filter_tool_candidates anymore."""
        from pre_simulation import filter_tool_candidates

        finding = Finding(
            finding_id="int-1",
            category=FindingCategory.SYNTAX_ERROR.value,
            severity="high",
            file="main.py",
            root_cause="Missing colon",
            root_cause_confirmed=True,
        )

        candidates = filter_tool_candidates(["int-1"], [finding], [])
        assert "int-1" in candidates
        # coding_agent should NOT be in the list (it's a planner now)
        assert "coding_agent" not in candidates["int-1"]
        # refactor should still be there
        assert "refactor" in candidates["int-1"]
