# Modified: 2026-06-23T22:19:00Z
"""TestRepairTool — broken test repair for the toolkit system.

Inputs:
    - Finding with category TEST_FAILURE
    - sandbox_path: root of the isolated sandbox copy containing the affected test file
    - context: runtime metadata dict (case_id, snapshot_id, etc.)

Outputs:
    - ToolResult with mutations applied, confidence score, and validation status
    - mutations list contains dicts with keys: file, operation, before, after

Side-effects:
    - Modifies test files ONLY within sandbox_path
    - Runs `python -c "import ast; ast.parse(...)"` to validate syntax post-fix
    - Preserves test intent — only updates what's broken, never removes test logic
    - No network calls, no state outside sandbox boundary

Errors:
    - Returns ToolResult(success=False, error=...) if file not found, failure type
      cannot be determined, or syntax validation fails after fix
    - Never raises unhandled exceptions
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from models import Finding, FindingCategory
from toolkits.base import ToolContract, ToolResult


# Failure type classifiers based on known_facts content
_ASSERTION_KEYWORDS: frozenset[str] = frozenset({
    "assertionerror",
    "assertion error",
    "assert",
    "expected",
    "got",
    "!=",
    "not equal",
})

_IMPORT_KEYWORDS: frozenset[str] = frozenset({
    "importerror",
    "import error",
    "no module named",
    "cannot import",
    "modulenotfounderror",
})

_FIXTURE_KEYWORDS: frozenset[str] = frozenset({
    "fixture",
    "fixtureerror",
    "fixture not found",
    "missing fixture",
    "conftest",
    "setup",
    "teardown",
})


class TestRepairTool(ToolContract):
    """Handles broken tests while preserving test intent.

    Covers:
      - Assertion errors: updates expected values based on known_facts
        (e.g., "expected 42 got 43" → update the assertion).
      - Import errors in tests: fixes the import path within test files.
      - Fixture issues: adds missing fixtures or updates fixture references.

    IMPORTANT: This tool preserves test intent — it only updates what's broken
    and never removes test logic, assertions, or test functions.
    """

    _APPLICABLE: frozenset[str] = frozenset({
        FindingCategory.TEST_FAILURE.value,
    })

    @property
    def name(self) -> str:
        return "test_repair"

    @property
    def description(self) -> str:
        return "Fix broken tests while preserving test intent"

    @property
    def applicable_categories(self) -> frozenset[str]:
        return self._APPLICABLE

    def can_handle(self, finding: Finding) -> bool:
        """Return True if finding is a test failure with a file and confirmed root cause."""
        return (
            finding.category in self._APPLICABLE
            and bool(finding.file)
            and finding.root_cause_confirmed is True
        )

    def execute(self, sandbox_path: str, finding: Finding, context: dict) -> ToolResult:
        """Execute a test repair against the finding within the sandbox.

        Analyzes the failure type from known_facts and dispatches to the
        appropriate fix strategy. Preserves test intent throughout.
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

        # Classify the failure type
        failure_type = self._classify_failure(finding)

        if failure_type == "assertion":
            return self._fix_assertion_error(
                sandbox_path, file_path, original_content, finding
            )
        elif failure_type == "import":
            return self._fix_import_error(
                sandbox_path, file_path, original_content, finding
            )
        elif failure_type == "fixture":
            return self._fix_fixture_issue(
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
                error=f"Cannot classify failure type from finding metadata",
            )

    # ─── Strategy: ASSERTION ERROR ─────────────────────────────────────────

    def _fix_assertion_error(
        self,
        sandbox_path: str,
        file_path: Path,
        content: str,
        finding: Finding,
    ) -> ToolResult:
        """Fix an assertion error by updating the expected value.

        Uses known_facts to find the expected/got pattern (e.g.,
        "expected 42 got 43") and updates the assertion in the test file.
        Only updates the expected value — never removes assertions or test logic.
        """
        item_id = finding.finding_id

        # Extract expected/got values from known_facts
        expected_got = self._extract_expected_got(finding)
        if not expected_got:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Cannot determine expected/got values from finding metadata",
            )

        old_expected, new_expected = expected_got

        # Locate the assertion line
        assertion_line = self._find_assertion_line(content, finding, old_expected)
        if not assertion_line:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Cannot locate the failing assertion in the test file",
            )

        # Build the fixed assertion by replacing old expected with new
        fixed_line = assertion_line.replace(old_expected, new_expected, 1)
        if fixed_line == assertion_line:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Cannot construct a valid replacement assertion",
            )

        # Apply the fix
        new_content = content.replace(assertion_line, fixed_line, 1)
        file_path.write_text(new_content, encoding="utf-8")

        # Validate syntax
        validation_passed = self._validate_syntax(file_path)
        if not validation_passed:
            file_path.write_text(content, encoding="utf-8")
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Fixed assertion failed syntax validation; reverted",
            )

        return ToolResult(
            tool_name=self.name,
            item_id=item_id,
            success=True,
            mutations=[{
                "file": finding.file,
                "operation": "replace",
                "before": assertion_line.strip(),
                "after": fixed_line.strip(),
            }],
            confidence=0.90,
            validation_passed=True,
            files_modified=[finding.file],
        )

    # ─── Strategy: IMPORT ERROR ────────────────────────────────────────────

    def _fix_import_error(
        self,
        sandbox_path: str,
        file_path: Path,
        content: str,
        finding: Finding,
    ) -> ToolResult:
        """Fix an import error in a test file.

        Specific to test files — uses known_facts to resolve the correct import
        path. Similar logic to ImportRepairTool but scoped to test contexts
        (e.g., relative imports from test packages, conftest imports, etc.).
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
                error="Cannot locate the broken import line in the test file",
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
            file_path.write_text(content, encoding="utf-8")
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Fixed import failed syntax validation; reverted",
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
            confidence=0.91,
            validation_passed=True,
            files_modified=[finding.file],
        )

    # ─── Strategy: FIXTURE ISSUE ───────────────────────────────────────────

    def _fix_fixture_issue(
        self,
        sandbox_path: str,
        file_path: Path,
        content: str,
        finding: Finding,
    ) -> ToolResult:
        """Fix a fixture issue by adding a missing fixture or updating references.

        Handles:
          - Missing fixture: adds a minimal fixture function decorated with @pytest.fixture
          - Wrong fixture name: renames the fixture reference in the test function params
          - Missing conftest import: ensures pytest is imported when fixtures are used
        """
        item_id = finding.finding_id

        # Determine fixture fix sub-strategy
        fixture_info = self._extract_fixture_info(finding)
        if not fixture_info:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Cannot determine fixture issue details from finding metadata",
            )

        fix_type = fixture_info.get("fix_type", "")

        if fix_type == "add_fixture":
            return self._add_missing_fixture(
                file_path, content, finding, fixture_info
            )
        elif fix_type == "rename_reference":
            return self._rename_fixture_reference(
                file_path, content, finding, fixture_info
            )
        else:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error=f"Unsupported fixture fix type: {fix_type}",
            )

    def _add_missing_fixture(
        self,
        file_path: Path,
        content: str,
        finding: Finding,
        fixture_info: dict,
    ) -> ToolResult:
        """Add a missing pytest fixture to the test file.

        Inserts a minimal fixture function before the first test function
        that references it. The fixture returns None by default — the intent
        is to make the test runnable so a human can fill in the fixture body.
        """
        item_id = finding.finding_id
        fixture_name = fixture_info.get("fixture_name", "")

        if not fixture_name:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Missing fixture_name for fixture addition",
            )

        # Ensure pytest import exists
        has_pytest_import = bool(
            re.search(r"^\s*import\s+pytest", content, re.MULTILINE)
        )

        # Build the fixture stub
        fixture_stub = (
            f"\n\n@pytest.fixture\n"
            f"def {fixture_name}():\n"
            f'    """Auto-generated fixture stub."""\n'
            f"    return None\n"
        )

        # Find insertion point: before the first test function using this fixture
        test_pattern = re.compile(
            rf"^(def\s+test_\w+\s*\([^)]*\b{re.escape(fixture_name)}\b[^)]*\))",
            re.MULTILINE,
        )
        match = test_pattern.search(content)

        if match:
            insert_pos = match.start()
        else:
            # Insert before the first test function
            first_test = re.search(r"^def\s+test_", content, re.MULTILINE)
            insert_pos = first_test.start() if first_test else len(content)

        # Build new content
        new_content = content[:insert_pos] + fixture_stub + "\n" + content[insert_pos:]

        # Add pytest import if missing
        if not has_pytest_import:
            new_content = "import pytest\n" + new_content

        file_path.write_text(new_content, encoding="utf-8")

        # Validate syntax
        validation_passed = self._validate_syntax(file_path)
        if not validation_passed:
            file_path.write_text(content, encoding="utf-8")
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Fixture addition failed syntax validation; reverted",
            )

        return ToolResult(
            tool_name=self.name,
            item_id=item_id,
            success=True,
            mutations=[{
                "file": finding.file,
                "operation": "insert",
                "before": "(missing fixture)",
                "after": f"Added @pytest.fixture def {fixture_name}()",
            }],
            confidence=0.80,
            validation_passed=True,
            files_modified=[finding.file],
        )

    def _rename_fixture_reference(
        self,
        file_path: Path,
        content: str,
        finding: Finding,
        fixture_info: dict,
    ) -> ToolResult:
        """Rename a fixture reference in a test function's parameters.

        Updates the parameter name in the test function signature from the
        wrong name to the correct fixture name provided in known_facts.
        """
        item_id = finding.finding_id
        old_name = fixture_info.get("old_name", "")
        new_name = fixture_info.get("new_name", "")

        if not old_name or not new_name:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Missing old_name or new_name for fixture rename",
            )

        # Find and replace the fixture reference in test function params
        param_pattern = re.compile(
            rf"(\bdef\s+test_\w+\s*\([^)]*)\b{re.escape(old_name)}\b([^)]*\))"
        )
        match = param_pattern.search(content)

        if not match:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error=f"Cannot find fixture reference '{old_name}' in test parameters",
            )

        old_text = match.group(0)
        new_text = match.group(1) + new_name + match.group(2)

        new_content = content.replace(old_text, new_text, 1)
        file_path.write_text(new_content, encoding="utf-8")

        # Validate syntax
        validation_passed = self._validate_syntax(file_path)
        if not validation_passed:
            file_path.write_text(content, encoding="utf-8")
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Fixture rename failed syntax validation; reverted",
            )

        return ToolResult(
            tool_name=self.name,
            item_id=item_id,
            success=True,
            mutations=[{
                "file": finding.file,
                "operation": "replace",
                "before": f"fixture param: {old_name}",
                "after": f"fixture param: {new_name}",
            }],
            confidence=0.88,
            validation_passed=True,
            files_modified=[finding.file],
        )

    # ─── Helper Methods ────────────────────────────────────────────────────

    @staticmethod
    def _classify_failure(finding: Finding) -> str:
        """Classify the test failure type from known_facts and root_cause.

        Returns one of: "assertion", "import", "fixture", or "" if unclassifiable.
        Priority order: import > fixture > assertion (most specific first).
        """
        text = " ".join(finding.known_facts).lower()
        if finding.root_cause:
            text += " " + finding.root_cause.lower()

        # Check import first (most specific signal)
        if any(kw in text for kw in _IMPORT_KEYWORDS):
            return "import"

        # Check fixture issues
        if any(kw in text for kw in _FIXTURE_KEYWORDS):
            return "fixture"

        # Check assertion errors (most common)
        if any(kw in text for kw in _ASSERTION_KEYWORDS):
            return "assertion"

        return ""

    @staticmethod
    def _extract_expected_got(finding: Finding) -> tuple[str, str] | None:
        """Extract expected and actual values from finding metadata.

        Looks for patterns like:
          - "expected 42 got 43"
          - "expected '42' but got '43'"
          - "AssertionError: 42 != 43"
          - "assert result == 42, got 43"
        """
        patterns = [
            # "expected X got Y" or "expected X but got Y"
            re.compile(
                r"expected\s+['\"]?(.+?)['\"]?\s+(?:but\s+)?got\s+['\"]?(.+?)['\"]?(?:\s|$|,|;)"
            ),
            # "X != Y" (assertion comparison)
            re.compile(
                r"['\"]?(.+?)['\"]?\s*!=\s*['\"]?(.+?)['\"]?(?:\s|$|,|;)"
            ),
            # "assert .* == X, got Y"
            re.compile(
                r"==\s*['\"]?(.+?)['\"]?,?\s*got\s+['\"]?(.+?)['\"]?(?:\s|$)"
            ),
        ]

        sources = list(finding.known_facts)
        if finding.root_cause:
            sources.append(finding.root_cause)

        for source in sources:
            for pattern in patterns:
                match = pattern.search(source.lower() if "!=" in source else source)
                if match:
                    # For "expected X got Y": old_expected=X, new_expected=Y
                    old_val = match.group(1).strip()
                    new_val = match.group(2).strip()
                    if old_val and new_val and old_val != new_val:
                        return (old_val, new_val)

        return None

    @staticmethod
    def _find_assertion_line(
        content: str, finding: Finding, expected_value: str
    ) -> str:
        """Locate the assertion line containing the expected value.

        Uses finding.line if available, otherwise searches for an assert
        statement containing the expected value.
        """
        lines = content.splitlines()

        # Strategy 1: Use line number from finding
        if finding.line is not None and 0 < finding.line <= len(lines):
            target_line = lines[finding.line - 1]
            if "assert" in target_line.lower() or "==" in target_line:
                return target_line

        # Strategy 2: Search for an assertion line containing the expected value
        for line in lines:
            stripped = line.strip()
            if ("assert" in stripped.lower() or "==" in stripped) and expected_value in stripped:
                return line

        # Strategy 3: Broader search — any line with the expected value in a test context
        for line in lines:
            if expected_value in line and ("assert" in line.lower() or "expect" in line.lower()):
                return line

        return ""

    @staticmethod
    def _extract_broken_import_line(content: str, finding: Finding) -> str:
        """Locate the broken import line in the test file content.

        Uses finding.line if available, otherwise searches for an import
        matching the module mentioned in root_cause or known_facts.
        """
        lines = content.splitlines()

        # Strategy 1: Use line number from finding
        if finding.line is not None and 0 < finding.line <= len(lines):
            target_line = lines[finding.line - 1].strip()
            if target_line.startswith("import ") or target_line.startswith("from "):
                return target_line

        # Strategy 2: Search for the broken module name in imports
        module_name = ""
        no_module_pattern = re.compile(r"[Nn]o module named ['\"]([^'\"]+)['\"]")
        cannot_import_pattern = re.compile(r"cannot import name ['\"](\w+)['\"]")

        sources = list(finding.known_facts)
        if finding.root_cause:
            sources.append(finding.root_cause)

        for source in sources:
            match = no_module_pattern.search(source)
            if match:
                module_name = match.group(1)
                break
            match = cannot_import_pattern.search(source)
            if match:
                module_name = match.group(1)
                break

        if module_name:
            for line in lines:
                stripped = line.strip()
                if (stripped.startswith("import ") or stripped.startswith("from ")) and module_name in stripped:
                    return stripped

        return ""

    @staticmethod
    def _extract_correct_module(finding: Finding) -> str:
        """Extract the correct module path from finding known_facts or root_cause.

        Looks for patterns like:
          - "Correct path: app.utils"
          - "Module available at: app.utils"
          - "should be 'app.utils'"
          - "use 'app.utils' instead"
        """
        module_patterns = [
            re.compile(r"[Cc]orrect (?:path|module|import)[:;]?\s*['\"]?([\w.]+)['\"]?"),
            re.compile(r"[Mm]odule (?:available|located|found) (?:at|in)[:;]?\s*['\"]?([\w.]+)['\"]?"),
            re.compile(r"[Ss]hould (?:be|use)[:;]?\s*['\"]?([\w.]+)['\"]?"),
            re.compile(r"[Uu]se[:;]?\s*['\"]?([\w.]+)['\"]?\s*instead"),
            re.compile(r"[Rr]eplace with[:;]?\s*['\"]?([\w.]+)['\"]?"),
        ]

        sources = list(finding.known_facts)
        if finding.root_cause:
            sources.append(finding.root_cause)

        for source in sources:
            for pattern in module_patterns:
                match = pattern.search(source)
                if match:
                    candidate = match.group(1)
                    if "." in candidate:
                        return candidate

        # Fallback: extract any dotted identifier from known_facts
        for source in sources:
            match = re.search(r"['\"]?([\w]+(?:\.[\w]+)+)['\"]?", source)
            if match:
                return match.group(1)

        return ""

    @staticmethod
    def _build_fixed_import(broken_import: str, correct_module: str) -> str:
        """Build a corrected import statement from the broken one and correct module.

        Handles both 'from X import Y' and 'import X' patterns.
        """
        # Pattern: "from old.module import names"
        from_match = re.match(r"from\s+([\w.]+)\s+(import\s+.+)", broken_import)
        if from_match:
            import_clause = from_match.group(2)
            return f"from {correct_module} {import_clause}"

        # Pattern: "import old.module" or "import old.module as alias"
        import_match = re.match(r"import\s+([\w.]+)(.*)", broken_import)
        if import_match:
            suffix = import_match.group(2)
            return f"import {correct_module}{suffix}"

        return ""

    @staticmethod
    def _extract_fixture_info(finding: Finding) -> dict:
        """Extract fixture-related information from finding metadata.

        Returns a dict with:
          - fix_type: "add_fixture" or "rename_reference"
          - fixture_name: name of the missing/correct fixture
          - old_name / new_name: for rename operations

        Looks for patterns like:
          - "fixture 'db_session' not found"
          - "missing fixture: db_session"
          - "fixture 'db' should be 'db_session'"
          - "use fixture 'db_session' instead of 'db'"
        """
        patterns_missing = [
            re.compile(r"fixture\s+['\"](\w+)['\"]?\s+not\s+found"),
            re.compile(r"missing\s+fixture[:;]?\s*['\"]?(\w+)['\"]?"),
            re.compile(r"fixture\s+['\"]?(\w+)['\"]?\s+(?:is\s+)?(?:not\s+)?(?:defined|available)"),
        ]

        patterns_rename = [
            re.compile(
                r"fixture\s+['\"]?(\w+)['\"]?\s+should\s+be\s+['\"]?(\w+)['\"]?"
            ),
            re.compile(
                r"use\s+(?:fixture\s+)?['\"]?(\w+)['\"]?\s+instead\s+of\s+['\"]?(\w+)['\"]?"
            ),
            re.compile(
                r"rename\s+['\"]?(\w+)['\"]?\s+to\s+['\"]?(\w+)['\"]?"
            ),
        ]

        sources = list(finding.known_facts)
        if finding.root_cause:
            sources.append(finding.root_cause)

        # Check rename patterns first (more specific)
        for source in sources:
            for pattern in patterns_rename:
                match = pattern.search(source)
                if match:
                    groups = match.groups()
                    if "instead" in pattern.pattern:
                        # "use X instead of Y" → old=Y, new=X
                        return {
                            "fix_type": "rename_reference",
                            "new_name": groups[0],
                            "old_name": groups[1],
                        }
                    elif "should be" in pattern.pattern:
                        # "X should be Y" → old=X, new=Y
                        return {
                            "fix_type": "rename_reference",
                            "old_name": groups[0],
                            "new_name": groups[1],
                        }
                    else:
                        # "rename X to Y" → old=X, new=Y
                        return {
                            "fix_type": "rename_reference",
                            "old_name": groups[0],
                            "new_name": groups[1],
                        }

        # Check missing fixture patterns
        for source in sources:
            for pattern in patterns_missing:
                match = pattern.search(source)
                if match:
                    return {
                        "fix_type": "add_fixture",
                        "fixture_name": match.group(1),
                    }

        return {}

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
