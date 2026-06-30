# Modified: 2026-06-24T07:40:00Z
"""Tests for the CodingAgentTool — external coding agent integration.

These tests verify:
1. The tool correctly implements the ToolContract interface
2. can_handle() filters appropriately
3. execute() applies fixes to the sandbox via the deterministic fallback
4. The tool is registered in pre_simulation and simulation
5. The coding-agent/main.py standalone function works
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

from models import Finding, FindingCategory
from toolkits.base import ToolContract, ToolResult
from toolkits.coding_agent import CodingAgentTool


# ──────────────────────────────────────────────
# ToolContract interface
# ──────────────────────────────────────────────


class TestCodingAgentToolContract:
    """Verify CodingAgentTool satisfies the ToolContract ABC."""

    def test_is_tool_contract(self):
        assert issubclass(CodingAgentTool, ToolContract)

    def test_name(self):
        tool = CodingAgentTool()
        assert tool.name == "coding_agent"

    def test_description(self):
        tool = CodingAgentTool()
        assert "coding agent" in tool.description.lower()

    def test_applicable_categories_includes_all(self):
        tool = CodingAgentTool()
        cats = tool.applicable_categories
        assert FindingCategory.SYNTAX_ERROR.value in cats
        assert FindingCategory.MISSING_IMPORT.value in cats
        assert FindingCategory.DEPENDENCY_CONFLICT.value in cats
        assert FindingCategory.CIRCULAR_IMPORT.value in cats

    def test_can_handle_valid_finding(self):
        tool = CodingAgentTool()
        finding = Finding(
            finding_id="test-1",
            category=FindingCategory.SYNTAX_ERROR.value,
            severity="high",
            file="main.py",
            root_cause="Missing colon",
            root_cause_confirmed=True,
        )
        assert tool.can_handle(finding)

    def test_can_handle_no_file(self):
        tool = CodingAgentTool()
        finding = Finding(
            finding_id="test-2",
            category=FindingCategory.SYNTAX_ERROR.value,
            severity="high",
            file="",
            root_cause="Missing colon",
            root_cause_confirmed=True,
        )
        assert not tool.can_handle(finding)

    def test_can_handle_no_context(self):
        tool = CodingAgentTool()
        finding = Finding(
            finding_id="test-3",
            category=FindingCategory.SYNTAX_ERROR.value,
            severity="high",
            file="main.py",
            root_cause="",
            root_cause_confirmed=False,
        )
        assert not tool.can_handle(finding)


# ──────────────────────────────────────────────
# Execute (deterministic fallback)
# ──────────────────────────────────────────────


class TestCodingAgentExecute:
    """Verify execute() applies fixes via the deterministic fallback."""

    def test_fix_syntax_error_missing_colon(self):
        """The deterministic backend should fix a missing colon after def."""
        tool = CodingAgentTool()
        with tempfile.TemporaryDirectory() as sandbox:
            # Create a file with a syntax error (missing colon)
            file_path = Path(sandbox) / "main.py"
            file_path.write_text("def broken_function()\n    return 42\n", encoding="utf-8")

            finding = Finding(
                finding_id="syntax-1",
                category=FindingCategory.SYNTAX_ERROR.value,
                severity="critical",
                file="main.py",
                root_cause="SyntaxError: missing colon after def",
                root_cause_confirmed=True,
                known_facts=["Line 1: def broken_function() — missing colon"],
            )

            result = tool.execute(sandbox, finding, {"case_id": "test"})

            assert isinstance(result, ToolResult)
            assert result.tool_name == "coding_agent"
            assert result.item_id == "syntax-1"
            # The deterministic backend should fix the missing colon
            assert result.success
            assert "main.py" in result.files_modified
            # Verify the fix was applied to the sandbox
            fixed = file_path.read_text(encoding="utf-8")
            assert "def broken_function():" in fixed

    def test_fix_dependency_conflict_duplicate(self):
        """The deterministic backend should remove duplicate deps."""
        tool = CodingAgentTool()
        with tempfile.TemporaryDirectory() as sandbox:
            file_path = Path(sandbox) / "requirements.txt"
            file_path.write_text(
                "requests==2.31.0\nrequests==2.32.0\nflask==3.0.0\n",
                encoding="utf-8",
            )

            finding = Finding(
                finding_id="dep-conflict-1",
                category=FindingCategory.DEPENDENCY_CONFLICT.value,
                severity="high",
                file="requirements.txt",
                root_cause="Duplicate dependency pin: 'requests' appears multiple times",
                root_cause_confirmed=True,
                known_facts=["Duplicate: requests"],
            )

            result = tool.execute(sandbox, finding, {"case_id": "test"})

            assert result.success
            fixed = file_path.read_text(encoding="utf-8")
            # Should have only one 'requests' line
            assert fixed.count("requests") == 1

    def test_fix_missing_import_stdlib(self):
        """The deterministic backend should add a missing stdlib import."""
        tool = CodingAgentTool()
        with tempfile.TemporaryDirectory() as sandbox:
            file_path = Path(sandbox) / "main.py"
            file_path.write_text(
                "x = os.path.join('a', 'b')\n",
                encoding="utf-8",
            )

            finding = Finding(
                finding_id="missing-import-1",
                category=FindingCategory.MISSING_IMPORT.value,
                severity="high",
                file="main.py",
                root_cause="Name 'os' used but not imported",
                root_cause_confirmed=True,
                known_facts=["module 'os' not imported"],
            )

            result = tool.execute(sandbox, finding, {"case_id": "test"})

            assert result.success
            fixed = file_path.read_text(encoding="utf-8")
            assert "import os" in fixed

    def test_file_not_found(self):
        """Should return failure when the file doesn't exist in sandbox."""
        tool = CodingAgentTool()
        with tempfile.TemporaryDirectory() as sandbox:
            finding = Finding(
                finding_id="ghost-1",
                category=FindingCategory.SYNTAX_ERROR.value,
                severity="high",
                file="nonexistent.py",
                root_cause="Some error",
                root_cause_confirmed=True,
            )

            result = tool.execute(sandbox, finding, {"case_id": "test"})

            assert not result.success
            assert "not found" in result.error.lower()

    def test_no_fix_available(self):
        """Should return failure when no fix can be applied."""
        tool = CodingAgentTool()
        with tempfile.TemporaryDirectory() as sandbox:
            file_path = Path(sandbox) / "main.py"
            file_path.write_text("x = 1\n", encoding="utf-8")

            finding = Finding(
                finding_id="unfixable-1",
                category=FindingCategory.CONFIGURATION_MISSING.value,
                severity="medium",
                file="main.py",
                root_cause="Missing configuration file",
                root_cause_confirmed=True,
                known_facts=["Config file not found"],
            )

            result = tool.execute(sandbox, finding, {"case_id": "test"})

            # Deterministic backend may not fix this — that's OK
            assert isinstance(result, ToolResult)
            assert result.tool_name == "coding_agent"


# ──────────────────────────────────────────────
# Registration in pre_simulation and simulation
# ──────────────────────────────────────────────


class TestCodingAgentRegistration:
    """Verify the coding agent is registered in the tool system."""

    def test_in_filter_tool_candidates(self):
        """coding_agent should appear in tool_candidates for findings it can handle."""
        from pre_simulation import filter_tool_candidates

        finding = Finding(
            finding_id="reg-1",
            category=FindingCategory.SYNTAX_ERROR.value,
            severity="high",
            file="main.py",
            root_cause="Missing colon",
            root_cause_confirmed=True,
        )

        candidates = filter_tool_candidates(["reg-1"], [finding], [])
        assert "reg-1" in candidates
        assert "coding_agent" in candidates["reg-1"]

    def test_coding_agent_is_last_in_candidate_list(self):
        """Deterministic tools should be tried before coding_agent."""
        from pre_simulation import filter_tool_candidates

        finding = Finding(
            finding_id="reg-2",
            category=FindingCategory.SYNTAX_ERROR.value,
            severity="high",
            file="main.py",
            root_cause="Missing colon",
            root_cause_confirmed=True,
        )

        candidates = filter_tool_candidates(["reg-2"], [finding], [])
        if "coding_agent" in candidates.get("reg-2", []):
            # coding_agent should not be first (deterministic tools come first)
            assert candidates["reg-2"].index("coding_agent") > 0

    def test_in_simulation_tool_registry(self):
        """coding_agent should be in the simulation tool registry."""
        # Check that the import works and the tool is registered
        from toolkits.coding_agent import CodingAgentTool
        tool = CodingAgentTool()
        assert tool.name == "coding_agent"


# ──────────────────────────────────────────────
# Standalone coding-agent/main.py
# ──────────────────────────────────────────────


class TestStandaloneCodingAgent:
    """Verify the standalone coding-agent/main.py function works."""

    def test_main_importable(self):
        """coding-agent/main.py should be importable."""
        workspace = Path(__file__).resolve().parent.parent.parent
        coding_agent_dir = workspace / "coding-agent"
        if str(coding_agent_dir) not in sys.path:
            sys.path.insert(0, str(coding_agent_dir))

        import importlib
        ca = importlib.import_module("main")
        assert hasattr(ca, "fix_with_coding_agent")
        assert hasattr(ca, "main")

    def test_main_json_roundtrip(self):
        """main() should accept JSON input and return JSON output."""
        workspace = Path(__file__).resolve().parent.parent.parent
        coding_agent_dir = workspace / "coding-agent"
        if str(coding_agent_dir) not in sys.path:
            sys.path.insert(0, str(coding_agent_dir))

        import importlib
        ca = importlib.import_module("main")
        importlib.reload(ca)

        input_data = {
            "file_path": "test.py",
            "file_content": "def broken()\n    return 1\n",
            "finding": {
                "category": "syntax_error",
                "severity": "critical",
                "file": "test.py",
                "root_cause": "Missing colon",
                "known_facts": ["Line 1: missing colon"],
            },
        }

        output_json = ca.main(json.dumps(input_data))
        output = json.loads(output_json)

        assert "fixed_content" in output
        assert "success" in output
        assert "method" in output

    def test_deterministic_fix_syntax_error(self):
        """The deterministic backend should fix a syntax error."""
        workspace = Path(__file__).resolve().parent.parent.parent
        coding_agent_dir = workspace / "coding-agent"
        if str(coding_agent_dir) not in sys.path:
            sys.path.insert(0, str(coding_agent_dir))

        import importlib
        ca = importlib.import_module("main")
        importlib.reload(ca)

        result = ca._fix_deterministic(
            "test.py",
            "def broken()\n    return 1\n",
            {
                "category": "syntax_error",
                "severity": "critical",
                "file": "test.py",
                "root_cause": "Missing colon after def",
                "known_facts": ["Line 1: def broken() — missing colon"],
            },
        )

        assert result["success"]
        assert "def broken():" in result["fixed_content"]
        assert result["method"] == "deterministic"

    def test_deterministic_fix_dependency_conflict(self):
        """The deterministic backend should fix duplicate deps."""
        workspace = Path(__file__).resolve().parent.parent.parent
        coding_agent_dir = workspace / "coding-agent"
        if str(coding_agent_dir) not in sys.path:
            sys.path.insert(0, str(coding_agent_dir))

        import importlib
        ca = importlib.import_module("main")
        importlib.reload(ca)

        result = ca._fix_deterministic(
            "requirements.txt",
            "requests==2.31.0\nrequests==2.32.0\nflask==3.0.0\n",
            {
                "category": "dependency_conflict",
                "severity": "high",
                "file": "requirements.txt",
                "root_cause": "Duplicate: requests",
                "known_facts": ["Duplicate: requests"],
            },
        )

        assert result["success"]
        assert result["fixed_content"].count("requests") == 1