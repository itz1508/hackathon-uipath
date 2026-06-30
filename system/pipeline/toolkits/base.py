# Modified: 2026-06-23T22:12:00Z
"""ToolContract ABC and ToolResult dataclass for the toolkit system.

Inputs:
    - Finding instances from the analysis phase (models.Finding)
    - Sandbox path for isolated execution
    - Context dict with runtime metadata (case_id, snapshot_id, etc.)

Outputs:
    - ToolResult dataclass capturing execution outcome, mutations applied,
      confidence score, and validation status

Side-effects:
    - Tool implementations modify files within the sandbox_path only
    - No mutations outside the sandbox boundary are permitted

Errors:
    - ToolResult.success=False with error message when execution fails
    - Tools must never raise unhandled exceptions; all errors captured in ToolResult
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from models import Finding, FindingCategory


@dataclass
class ToolResult:
    """Result of a single tool execution against one finding."""

    tool_name: str
    item_id: str
    success: bool
    mutations: list[dict]
    confidence: float
    validation_passed: bool
    error: str | None = None
    files_modified: list[str] = field(default_factory=list)


class ToolContract(ABC):
    """Abstract base class for all toolkit implementations.

    Each tool declares which finding categories it handles and provides
    a deterministic execute() method that operates within a sandbox.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this tool."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does."""
        ...

    @property
    @abstractmethod
    def applicable_categories(self) -> frozenset[str]:
        """Set of FindingCategory values this tool can handle."""
        ...

    @abstractmethod
    def can_handle(self, finding: Finding) -> bool:
        """Return True if this tool can attempt to fix the given finding.

        This is a fast pre-filter — it should check category membership
        and any other preconditions without performing expensive analysis.
        """
        ...

    @abstractmethod
    def execute(self, sandbox_path: str, finding: Finding, context: dict) -> ToolResult:
        """Execute the tool against a finding within the sandbox.

        Args:
            sandbox_path: Root path of the isolated sandbox copy.
            finding: The Finding instance to attempt fixing.
            context: Runtime metadata (case_id, snapshot_id, etc.).

        Returns:
            ToolResult with execution outcome.
        """
        ...
