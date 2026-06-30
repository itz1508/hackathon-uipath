# Modified: 2026-06-24T07:10:00Z
"""RefactorTool — structural code transformations for the toolkit system.

Inputs:
    - Finding with category in {SYNTAX_ERROR, CIRCULAR_IMPORT, UNDEFINED_REFERENCE}
    - sandbox_path: root of the isolated sandbox copy containing the affected file
    - context: runtime metadata dict (case_id, snapshot_id, etc.)

Outputs:
    - ToolResult with mutations applied, confidence score, and validation status
    - mutations list contains dicts with keys: file, operation, before, after

Side-effects:
    - Modifies files ONLY within sandbox_path
    - No network calls, no state outside sandbox boundary

Errors:
    - Returns ToolResult(success=False, error=...) if file not found or fix cannot be applied
    - Never raises unhandled exceptions
"""
from __future__ import annotations

import re
from difflib import get_close_matches
from pathlib import Path

from models import Finding, FindingCategory
from toolkits.base import ToolContract, ToolResult


class RefactorTool(ToolContract):
    """Handles structural code transformations for code-structure issues.

    Covers:
      - SYNTAX_ERROR: attempts common syntax fixes (missing colons, parens, brackets)
      - CIRCULAR_IMPORT: detects circular pattern and moves import to function scope
      - UNDEFINED_REFERENCE: checks if the reference is a typo of an existing name
    """

    _APPLICABLE: frozenset[str] = frozenset({
        FindingCategory.SYNTAX_ERROR.value,
        FindingCategory.CIRCULAR_IMPORT.value,
        FindingCategory.UNDEFINED_REFERENCE.value,
    })

    @property
    def name(self) -> str:
        return "refactor"

    @property
    def description(self) -> str:
        return "Structural code transformations for syntax, circular imports, and undefined references"

    @property
    def applicable_categories(self) -> frozenset[str]:
        return self._APPLICABLE

    # Keywords that indicate a contract/interface issue — these belong to ContractAlignTool
    _CONTRACT_KEYWORDS: frozenset[str] = frozenset({
        "interface", "contract", "signature", "method",
        "implements", "protocol", "abstract",
    })

    def can_handle(self, finding: Finding) -> bool:
        """Return True if finding is in applicable categories, has a file, and root cause is confirmed.

        For UNDEFINED_REFERENCE: explicitly yields to ContractAlignTool when
        contract/interface keywords are present in known_facts or root_cause.
        """
        if finding.category not in self._APPLICABLE:
            return False
        if not finding.file or not finding.root_cause_confirmed:
            return False

        # Disambiguate UNDEFINED_REFERENCE: contract issues go to contract_align
        if finding.category == FindingCategory.UNDEFINED_REFERENCE.value:
            text = " ".join(finding.known_facts).lower()
            if finding.root_cause:
                text += " " + finding.root_cause.lower()
            if any(kw in text for kw in self._CONTRACT_KEYWORDS):
                return False  # Yield to ContractAlignTool

        return True

    def execute(self, sandbox_path: str, finding: Finding, context: dict) -> ToolResult:
        """Execute a structural refactor against the finding within the sandbox.

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

        if category == FindingCategory.SYNTAX_ERROR.value:
            return self._fix_syntax_error(file_path, original_content, finding, context)
        elif category == FindingCategory.CIRCULAR_IMPORT.value:
            return self._fix_circular_import(file_path, original_content, finding, context)
        elif category == FindingCategory.UNDEFINED_REFERENCE.value:
            return self._fix_undefined_reference(file_path, original_content, finding, context)
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

    # ─── Strategy: SYNTAX_ERROR ────────────────────────────────────────────

    def _fix_syntax_error(
        self, file_path: Path, content: str, finding: Finding, context: dict
    ) -> ToolResult:
        """Attempt common syntax fixes: missing colons, unbalanced parens/brackets."""
        item_id = finding.finding_id
        mutations: list[dict] = []
        new_content = content
        line_num = finding.line

        # Strategy 1: Fix missing colon after def/class/if/elif/else/for/while/try/except/finally/with
        if line_num is not None:
            lines = new_content.splitlines(keepends=True)
            if 0 < line_num <= len(lines):
                target_line = lines[line_num - 1]
                # Check if line looks like a statement that needs a colon
                stmt_pattern = re.compile(
                    r"^(\s*)(def |class |if |elif |else|for |while |try|except|finally|with )"
                )
                if stmt_pattern.match(target_line) and not target_line.rstrip().endswith(":"):
                    fixed_line = target_line.rstrip() + ":\n"
                    mutations.append({
                        "file": finding.file,
                        "operation": "replace",
                        "before": target_line.rstrip("\n"),
                        "after": fixed_line.rstrip("\n"),
                    })
                    lines[line_num - 1] = fixed_line
                    new_content = "".join(lines)

        # Strategy 2: Fix unbalanced parentheses/brackets at end of file
        if not mutations:
            open_parens = new_content.count("(") - new_content.count(")")
            open_brackets = new_content.count("[") - new_content.count("]")
            open_braces = new_content.count("{") - new_content.count("}")

            suffix = ""
            if open_parens > 0:
                suffix += ")" * open_parens
            if open_brackets > 0:
                suffix += "]" * open_brackets
            if open_braces > 0:
                suffix += "}" * open_braces

            if suffix:
                mutations.append({
                    "file": finding.file,
                    "operation": "replace",
                    "before": "(unbalanced brackets/parens)",
                    "after": f"Appended closing: {suffix}",
                })
                new_content = new_content.rstrip() + suffix + "\n"

        if mutations:
            file_path.write_text(new_content, encoding="utf-8")
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=True,
                mutations=mutations,
                confidence=0.75,
                validation_passed=False,  # Caller must validate
                files_modified=[finding.file],
            )

        return ToolResult(
            tool_name=self.name,
            item_id=item_id,
            success=False,
            mutations=[],
            confidence=0.0,
            validation_passed=False,
            error="No applicable syntax fix found",
        )

    # ─── Strategy: CIRCULAR_IMPORT ─────────────────────────────────────────

    def _fix_circular_import(
        self, file_path: Path, content: str, finding: Finding, context: dict
    ) -> ToolResult:
        """Move top-level import into function scope to break circular dependency."""
        item_id = finding.finding_id
        mutations: list[dict] = []

        # Extract the problematic import from root_cause or known_facts
        import_target = self._extract_import_target(finding)
        if not import_target:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Cannot determine which import causes the cycle",
            )

        # Find top-level import lines matching the target
        lines = content.splitlines(keepends=True)
        import_pattern = re.compile(
            rf"^(from\s+{re.escape(import_target)}\s+import\s+.+|import\s+{re.escape(import_target)}.*)\s*$"
        )

        import_lines_indices: list[int] = []
        for idx, line in enumerate(lines):
            if import_pattern.match(line):
                import_lines_indices.append(idx)

        if not import_lines_indices:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error=f"Import for '{import_target}' not found at top level",
            )

        # Find all functions that use the imported name(s)
        # For simplicity, move the import into every function that references it
        imported_names = self._get_imported_names(lines, import_lines_indices)

        # Remove the top-level import
        removed_import_text = ""
        for idx in sorted(import_lines_indices, reverse=True):
            removed_import_text = lines[idx].strip()
            lines[idx] = ""

        # Find function definitions and inject local import where the name is used
        func_pattern = re.compile(r"^(\s*)(def\s+\w+\s*\()")
        injected = False
        new_lines = list(lines)

        i = 0
        while i < len(new_lines):
            match = func_pattern.match(new_lines[i])
            if match:
                indent = match.group(1)
                body_indent = indent + "    "
                # Scan function body for usage of imported names
                j = i + 1
                uses_import = False
                while j < len(new_lines):
                    if new_lines[j].strip() and not new_lines[j].startswith(body_indent) and not new_lines[j].strip() == "":
                        if not new_lines[j].startswith(indent + " "):
                            break
                    for name in imported_names:
                        if name in new_lines[j]:
                            uses_import = True
                            break
                    j += 1

                if uses_import:
                    # Insert local import after def line (after any docstring)
                    insert_idx = i + 1
                    # Skip docstring
                    if insert_idx < len(new_lines):
                        stripped = new_lines[insert_idx].strip()
                        if stripped.startswith('"""') or stripped.startswith("'''"):
                            # Multi-line or single-line docstring
                            if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                                insert_idx += 1
                            else:
                                quote = stripped[:3]
                                insert_idx += 1
                                while insert_idx < len(new_lines) and quote not in new_lines[insert_idx]:
                                    insert_idx += 1
                                insert_idx += 1

                    local_import = f"{body_indent}{removed_import_text}\n"
                    new_lines.insert(insert_idx, local_import)
                    injected = True
            i += 1

        if injected:
            new_content = "".join(new_lines)
            mutations.append({
                "file": finding.file,
                "operation": "replace",
                "before": f"Top-level import: {removed_import_text}",
                "after": "Moved import to function scope(s)",
            })
            file_path.write_text(new_content, encoding="utf-8")
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=True,
                mutations=mutations,
                confidence=0.70,
                validation_passed=False,
                files_modified=[finding.file],
            )

        return ToolResult(
            tool_name=self.name,
            item_id=item_id,
            success=False,
            mutations=[],
            confidence=0.0,
            validation_passed=False,
            error="Could not determine where to inject local import",
        )

    # ─── Strategy: UNDEFINED_REFERENCE ─────────────────────────────────────

    def _fix_undefined_reference(
        self, file_path: Path, content: str, finding: Finding, context: dict
    ) -> ToolResult:
        """Check if the undefined reference is a typo of an existing name in the file."""
        item_id = finding.finding_id
        mutations: list[dict] = []

        # Extract the undefined name from root_cause or known_facts
        undefined_name = self._extract_undefined_name(finding)
        if not undefined_name:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Cannot determine which name is undefined",
            )

        # Collect all defined names in the file (function defs, class defs, assignments, imports)
        defined_names = self._collect_defined_names(content)

        # Check for close matches (typo detection)
        matches = get_close_matches(undefined_name, defined_names, n=1, cutoff=0.8)

        if matches:
            best_match = matches[0]
            # Replace the undefined name with the best match
            new_content = content.replace(undefined_name, best_match)

            if new_content != content:
                mutations.append({
                    "file": finding.file,
                    "operation": "replace",
                    "before": undefined_name,
                    "after": best_match,
                })
                file_path.write_text(new_content, encoding="utf-8")
                return ToolResult(
                    tool_name=self.name,
                    item_id=item_id,
                    success=True,
                    mutations=mutations,
                    confidence=0.85,
                    validation_passed=False,
                    files_modified=[finding.file],
                )

        return ToolResult(
            tool_name=self.name,
            item_id=item_id,
            success=False,
            mutations=[],
            confidence=0.0,
            validation_passed=False,
            error=f"No close match found for '{undefined_name}' among defined names",
        )

    # ─── Helper Methods ────────────────────────────────────────────────────

    def _extract_import_target(self, finding: Finding) -> str:
        """Extract the module name causing circular import from finding metadata."""
        # Try root_cause first
        if finding.root_cause:
            # Pattern: "circular import between X and Y" or "import X causes cycle"
            match = re.search(r"(?:import|from)\s+([\w.]+)", finding.root_cause)
            if match:
                return match.group(1)

        # Try known_facts
        for fact in finding.known_facts:
            match = re.search(r"(?:import|from)\s+([\w.]+)", fact)
            if match:
                return match.group(1)

        return ""

    def _get_imported_names(self, lines: list[str], import_indices: list[int]) -> list[str]:
        """Extract the actual names imported from the import lines."""
        names: list[str] = []
        for idx in import_indices:
            line = lines[idx].strip()
            # "from module import name1, name2"
            match = re.match(r"from\s+\S+\s+import\s+(.+)", line)
            if match:
                for name in match.group(1).split(","):
                    clean = name.strip().split(" as ")[-1].strip()
                    if clean:
                        names.append(clean)
            else:
                # "import module" or "import module as alias"
                match = re.match(r"import\s+(.+)", line)
                if match:
                    for name in match.group(1).split(","):
                        clean = name.strip().split(" as ")[-1].strip()
                        if clean:
                            names.append(clean)
        return names

    def _extract_undefined_name(self, finding: Finding) -> str:
        """Extract the undefined name from finding metadata."""
        # Try root_cause
        if finding.root_cause:
            # Pattern: "undefined name 'X'" or "'X' is not defined" or "NameError: name 'X'"
            match = re.search(r"(?:name\s+['\"](\w+)['\"]|['\"](\w+)['\"]\s+is not defined|undefined\s+(?:name\s+)?['\"]?(\w+)['\"]?)", finding.root_cause)
            if match:
                return next(g for g in match.groups() if g is not None)

        # Try known_facts
        for fact in finding.known_facts:
            match = re.search(r"(?:name\s+['\"](\w+)['\"]|['\"](\w+)['\"]\s+is not defined|undefined\s+(?:name\s+)?['\"]?(\w+)['\"]?)", fact)
            if match:
                return next(g for g in match.groups() if g is not None)

        return ""

    def _collect_defined_names(self, content: str) -> list[str]:
        """Collect all names defined in the file (functions, classes, assignments, imports)."""
        names: set[str] = set()

        # Function definitions
        for match in re.finditer(r"^\s*def\s+(\w+)", content, re.MULTILINE):
            names.add(match.group(1))

        # Class definitions
        for match in re.finditer(r"^\s*class\s+(\w+)", content, re.MULTILINE):
            names.add(match.group(1))

        # Top-level assignments (simple name = ...)
        for match in re.finditer(r"^(\w+)\s*=", content, re.MULTILINE):
            names.add(match.group(1))

        # Imports: from X import name1, name2
        for match in re.finditer(r"^\s*from\s+\S+\s+import\s+(.+)", content, re.MULTILINE):
            for name in match.group(1).split(","):
                clean = name.strip().split(" as ")[-1].strip()
                if clean and clean.isidentifier():
                    names.add(clean)

        # Imports: import module (use module name)
        for match in re.finditer(r"^\s*import\s+(.+)", content, re.MULTILINE):
            for name in match.group(1).split(","):
                clean = name.strip().split(" as ")[-1].strip().split(".")[-1]
                if clean and clean.isidentifier():
                    names.add(clean)

        return list(names)
