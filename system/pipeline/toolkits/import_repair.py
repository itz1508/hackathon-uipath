# Modified: 2026-06-23T22:17:00Z
"""ImportRepairTool — broken/missing import resolution for the toolkit system.

Inputs:
    - Finding with category in {MISSING_IMPORT, AMBIGUOUS_IMPORT}
    - sandbox_path: root of the isolated sandbox copy containing the affected file
    - context: runtime metadata dict (case_id, snapshot_id, etc.)

Outputs:
    - ToolResult with mutations applied, confidence score, and validation status
    - mutations list contains dicts with keys: file, operation, before, after

Side-effects:
    - Modifies Python source files ONLY within sandbox_path
    - Runs `python -c "import ast; ast.parse(...)"` to validate syntax post-fix
    - No network calls, no state outside sandbox boundary

Errors:
    - Returns ToolResult(success=False, error=...) if file not found, import cannot
      be resolved, or syntax validation fails after fix
    - Never raises unhandled exceptions
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from models import Finding, FindingCategory
from toolkits.base import ToolContract, ToolResult


class ImportRepairTool(ToolContract):
    """Handles broken/missing imports and ambiguous import resolution.

    Covers:
      - MISSING_IMPORT: reads the affected file, locates the broken import line,
        and fixes the import path using known_facts (e.g. "Similar module exists: 'app.utils'").
      - AMBIGUOUS_IMPORT: if multiple resolution paths are available in known_facts,
        selects the most specific one; if only one option exists, applies it directly.
    """

    _APPLICABLE: frozenset[str] = frozenset({
        FindingCategory.MISSING_IMPORT.value,
        FindingCategory.AMBIGUOUS_IMPORT.value,
    })

    @property
    def name(self) -> str:
        return "import_repair"

    @property
    def description(self) -> str:
        return "Fix broken/missing imports and resolve ambiguous import paths"

    @property
    def applicable_categories(self) -> frozenset[str]:
        return self._APPLICABLE

    def can_handle(self, finding: Finding) -> bool:
        """Return True if finding is an import issue with a file and confirmed root cause."""
        return (
            finding.category in self._APPLICABLE
            and bool(finding.file)
            and finding.root_cause_confirmed is True
        )

    def execute(self, sandbox_path: str, finding: Finding, context: dict) -> ToolResult:
        """Execute an import repair against the finding within the sandbox.

        Dispatches to the appropriate fix strategy based on finding category.
        """
        item_id = finding.finding_id
        file_path = Path(sandbox_path) / finding.file

        if not file_path.exists():
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error=f"File not found in sandbox: {finding.file}",
            )

        try:
            original_content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error=f"Cannot read file: {exc}",
            )

        category = finding.category

        if category == FindingCategory.MISSING_IMPORT.value:
            return self._fix_missing_import(
                sandbox_path, file_path, original_content, finding
            )
        elif category == FindingCategory.AMBIGUOUS_IMPORT.value:
            return self._fix_ambiguous_import(
                sandbox_path, file_path, original_content, finding
            )
        else:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error=f"Unsupported category: {category}",
            )

    # ─── Strategy: MISSING_IMPORT ──────────────────────────────────────────

    def _fix_missing_import(
        self,
        sandbox_path: str,
        file_path: Path,
        content: str,
        finding: Finding,
    ) -> ToolResult:
        """Fix a missing/broken import by replacing it with the correct module path.

        Uses known_facts to find the correct module (e.g. "Similar module exists: 'app.utils'").
        Falls back to extracting module info from root_cause if known_facts is empty.
        """
        item_id = finding.finding_id

        # Extract the broken import line
        broken_import = self._extract_broken_import_line(content, finding)
        if not broken_import:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Cannot locate the broken import line in the file",
            )

        # Extract the correct module path from known_facts
        correct_module = self._extract_correct_module(finding)
        if not correct_module:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Cannot determine correct module path from finding metadata",
            )

        # Build the fixed import statement
        fixed_import = self._build_fixed_import(broken_import, correct_module)
        if not fixed_import or fixed_import == broken_import:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Cannot construct a valid replacement import statement",
            )

        # Apply the fix
        new_content = content.replace(broken_import, fixed_import, 1)
        file_path.write_text(new_content, encoding="utf-8")

        # Validate syntax
        validation_passed = self._validate_syntax(file_path)

        if not validation_passed:
            # Revert the change
            file_path.write_text(content, encoding="utf-8")
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Fixed file failed syntax validation; reverted",
            )

        return ToolResult(
            tool_name=self.name,
            item_id=item_id,
            success=True,
            mutations=[{
                "file": finding.file,
                "operation": "replace",
                "before": broken_import,
                "after": fixed_import,
            }],
            confidence=0.92,
            validation_passed=True,
            files_modified=[finding.file],
        )

    # ─── Strategy: AMBIGUOUS_IMPORT ────────────────────────────────────────

    def _fix_ambiguous_import(
        self,
        sandbox_path: str,
        file_path: Path,
        content: str,
        finding: Finding,
    ) -> ToolResult:
        """Resolve an ambiguous import by selecting the best candidate from known_facts.

        If multiple resolution paths are available, selects the most specific one
        (longest dotted path). If only one option exists, applies it directly.
        """
        item_id = finding.finding_id

        # Extract the ambiguous import line
        ambiguous_import = self._extract_broken_import_line(content, finding)
        if not ambiguous_import:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Cannot locate the ambiguous import line in the file",
            )

        # Extract all candidate module paths from known_facts
        candidates = self._extract_candidate_modules(finding)
        if not candidates:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="No resolution candidates found in finding metadata",
            )

        # Select the most specific candidate (longest dotted path)
        best_candidate = max(candidates, key=lambda c: c.count("."))

        # Build the fixed import statement
        fixed_import = self._build_fixed_import(ambiguous_import, best_candidate)
        if not fixed_import or fixed_import == ambiguous_import:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Cannot construct a valid replacement import statement",
            )

        # Apply the fix
        new_content = content.replace(ambiguous_import, fixed_import, 1)
        file_path.write_text(new_content, encoding="utf-8")

        # Validate syntax
        validation_passed = self._validate_syntax(file_path)

        if not validation_passed:
            # Revert the change
            file_path.write_text(content, encoding="utf-8")
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Fixed file failed syntax validation; reverted",
            )

        # Confidence: higher when only one candidate, lower when we had to choose
        confidence = 0.95 if len(candidates) == 1 else 0.85

        return ToolResult(
            tool_name=self.name,
            item_id=item_id,
            success=True,
            mutations=[{
                "file": finding.file,
                "operation": "replace",
                "before": ambiguous_import,
                "after": fixed_import,
            }],
            confidence=confidence,
            validation_passed=True,
            files_modified=[finding.file],
        )

    # ─── Helper Methods ────────────────────────────────────────────────────

    def _extract_broken_import_line(self, content: str, finding: Finding) -> str:
        """Locate the broken import line in the file content.

        Uses finding.line if available, otherwise searches for an import
        referencing the affected component or module mentioned in root_cause.
        """
        lines = content.splitlines()

        # Strategy 1: Use line number from finding
        if finding.line is not None and 0 < finding.line <= len(lines):
            target_line = lines[finding.line - 1].strip()
            if self._is_import_line(target_line):
                return target_line

        # Strategy 2: Search for an import matching the affected component or root_cause
        search_terms = self._get_search_terms(finding)
        for line in lines:
            stripped = line.strip()
            if self._is_import_line(stripped):
                for term in search_terms:
                    if term in stripped:
                        return stripped

        # Strategy 3: If there's exactly one broken-looking import (module doesn't exist), use it
        # This is a broad fallback — only used when nothing else matched
        if finding.root_cause:
            # Try to extract module name from root_cause like "No module named 'xyz'"
            match = re.search(r"[Nn]o module named ['\"]([^'\"]+)['\"]", finding.root_cause)
            if match:
                missing_module = match.group(1)
                for line in lines:
                    stripped = line.strip()
                    if self._is_import_line(stripped) and missing_module in stripped:
                        return stripped

        return ""

    def _extract_correct_module(self, finding: Finding) -> str:
        """Extract the correct module path from finding known_facts or root_cause.

        Looks for patterns like:
          - "Similar module exists: 'app.utils'"
          - "Correct path: app.utils"
          - "Module available at: app.utils"
          - "should be 'app.utils'"
          - Just a dotted path in known_facts
        """
        module_patterns = [
            re.compile(r"[Ss]imilar module (?:exists|found)[:;]?\s*['\"]?([\w.]+)['\"]?"),
            re.compile(r"[Cc]orrect (?:path|module|import)[:;]?\s*['\"]?([\w.]+)['\"]?"),
            re.compile(r"[Mm]odule (?:available|located|found) (?:at|in)[:;]?\s*['\"]?([\w.]+)['\"]?"),
            re.compile(r"[Ss]hould (?:be|use)[:;]?\s*['\"]?([\w.]+)['\"]?"),
            re.compile(r"[Rr]eplace with[:;]?\s*['\"]?([\w.]+)['\"]?"),
            re.compile(r"[Uu]se[:;]?\s*['\"]?([\w.]+)['\"]?"),
        ]

        # Search known_facts first (highest signal)
        for fact in finding.known_facts:
            for pattern in module_patterns:
                match = pattern.search(fact)
                if match:
                    candidate = match.group(1)
                    if "." in candidate:  # Must be a dotted module path
                        return candidate

        # Search root_cause
        if finding.root_cause:
            for pattern in module_patterns:
                match = pattern.search(finding.root_cause)
                if match:
                    candidate = match.group(1)
                    if "." in candidate:
                        return candidate

        # Fallback: extract any dotted identifier from known_facts that looks like a module
        for fact in finding.known_facts:
            match = re.search(r"['\"]?([\w]+(?:\.[\w]+)+)['\"]?", fact)
            if match:
                return match.group(1)

        return ""

    def _extract_candidate_modules(self, finding: Finding) -> list[str]:
        """Extract all candidate module paths from known_facts for ambiguous resolution.

        Returns a deduplicated list of dotted module paths found in known_facts.
        """
        candidates: list[str] = []
        seen: set[str] = set()

        # Pattern: any dotted identifier that looks like a Python module path
        module_pattern = re.compile(r"['\"]?([\w]+(?:\.[\w]+)+)['\"]?")

        for fact in finding.known_facts:
            for match in module_pattern.finditer(fact):
                candidate = match.group(1)
                if candidate not in seen:
                    seen.add(candidate)
                    candidates.append(candidate)

        # Also check root_cause for candidates
        if finding.root_cause:
            for match in module_pattern.finditer(finding.root_cause):
                candidate = match.group(1)
                if candidate not in seen:
                    seen.add(candidate)
                    candidates.append(candidate)

        return candidates

    def _build_fixed_import(self, broken_import: str, correct_module: str) -> str:
        """Build a corrected import statement from the broken one and the correct module path.

        Handles both 'from X import Y' and 'import X' patterns.
        """
        # Pattern: "from old.module import names"
        from_match = re.match(r"from\s+([\w.]+)\s+(import\s+.+)", broken_import)
        if from_match:
            # Replace the module path, keep the imported names
            import_clause = from_match.group(2)
            return f"from {correct_module} {import_clause}"

        # Pattern: "import old.module" or "import old.module as alias"
        import_match = re.match(r"import\s+([\w.]+)(.*)", broken_import)
        if import_match:
            suffix = import_match.group(2)  # captures " as alias" or ""
            return f"import {correct_module}{suffix}"

        return ""

    def _get_search_terms(self, finding: Finding) -> list[str]:
        """Build a list of search terms from finding metadata to locate the import line."""
        terms: list[str] = []

        if finding.affected_component:
            terms.append(finding.affected_component)

        if finding.root_cause:
            # Extract module names from root_cause
            for match in re.finditer(r"['\"]?([\w]+(?:\.[\w]+)*)['\"]?", finding.root_cause):
                term = match.group(1)
                if "." in term or len(term) > 3:
                    terms.append(term)

        for fact in finding.known_facts:
            # Extract module-like identifiers from facts
            for match in re.finditer(r"['\"]?([\w]+(?:\.[\w]+)+)['\"]?", fact):
                terms.append(match.group(1))

        return terms

    @staticmethod
    def _is_import_line(line: str) -> bool:
        """Check if a line is a Python import statement."""
        stripped = line.strip()
        return stripped.startswith("import ") or stripped.startswith("from ")

    @staticmethod
    def _validate_syntax(file_path: Path) -> bool:
        """Validate that a Python file has correct syntax using ast.parse.

        Runs in a subprocess to avoid polluting the current process state.
        """
        cmd = [
            sys.executable,
            "-c",
            f"import ast; ast.parse(open(r'{file_path}').read())",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False
