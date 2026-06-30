# Modified: 2026-06-23T22:18:00Z
"""ContractAlignTool — interface/contract alignment for the toolkit system.

Inputs:
    - Finding with category in {CONFIGURATION_MISSING, UNDEFINED_REFERENCE}
    - sandbox_path: root of the isolated sandbox copy containing the affected file
    - context: runtime metadata dict (case_id, snapshot_id, etc.)

Outputs:
    - ToolResult with mutations applied, confidence score, and validation status
    - mutations list contains dicts with keys: file, operation, before, after

Side-effects:
    - Modifies or creates files ONLY within sandbox_path
    - Runs `python -c "import ast; ast.parse(...)"` to validate syntax post-fix
    - No network calls, no state outside sandbox boundary

Errors:
    - Returns ToolResult(success=False, error=...) if file not found, configuration
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

# Keywords that indicate a contract/interface issue in known_facts
_CONTRACT_KEYWORDS: frozenset[str] = frozenset({
    "interface",
    "contract",
    "signature",
    "method",
    "implements",
    "protocol",
    "abstract",
})


class ContractAlignTool(ToolContract):
    """Handles interface/contract alignment and missing configuration issues.

    Covers:
      - CONFIGURATION_MISSING: reads the affected file (or creates a config file if
        needed), adds the missing configuration based on known_facts.
      - UNDEFINED_REFERENCE (contract-type): adds a missing method stub or fixes a
        function signature to match the expected interface. Only handles cases where
        known_facts indicate an interface/contract issue (not typos — those go to
        the refactor tool).
    """

    _APPLICABLE: frozenset[str] = frozenset({
        FindingCategory.CONFIGURATION_MISSING.value,
        FindingCategory.UNDEFINED_REFERENCE.value,
    })

    @property
    def name(self) -> str:
        return "contract_align"

    @property
    def description(self) -> str:
        return "Align code with contract/interface expectations and add missing configuration"

    @property
    def applicable_categories(self) -> frozenset[str]:
        return self._APPLICABLE

    def can_handle(self, finding: Finding) -> bool:
        """Return True if finding is a contract/interface issue or missing config.

        For CONFIGURATION_MISSING: requires root_cause_confirmed and a file.
        For UNDEFINED_REFERENCE: requires root_cause_confirmed, a file, AND
        known_facts must contain contract/interface keywords to differentiate
        from typo-based undefined references (handled by RefactorTool).
        """
        if not finding.root_cause_confirmed or not finding.file:
            return False

        if finding.category == FindingCategory.CONFIGURATION_MISSING.value:
            return True

        if finding.category == FindingCategory.UNDEFINED_REFERENCE.value:
            return self._has_contract_keywords(finding)

        return False

    def execute(self, sandbox_path: str, finding: Finding, context: dict) -> ToolResult:
        """Execute a contract alignment or configuration fix within the sandbox.

        Dispatches to the appropriate fix strategy based on finding category.
        """
        item_id = finding.finding_id
        file_path = Path(sandbox_path) / finding.file

        category = finding.category

        if category == FindingCategory.CONFIGURATION_MISSING.value:
            return self._fix_configuration_missing(
                sandbox_path, file_path, finding, context
            )
        elif category == FindingCategory.UNDEFINED_REFERENCE.value:
            return self._fix_contract_reference(
                sandbox_path, file_path, finding, context
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

    # ─── Strategy: CONFIGURATION_MISSING ───────────────────────────────────

    def _fix_configuration_missing(
        self,
        sandbox_path: str,
        file_path: Path,
        finding: Finding,
        context: dict,
    ) -> ToolResult:
        """Add missing configuration to an existing file or create a new config file.

        Uses known_facts to determine what configuration is needed. Supports:
          - Adding key=value entries to existing config files (.ini, .cfg, .env)
          - Adding dict entries to Python settings modules
          - Creating a new config file with the required entries
        """
        item_id = finding.finding_id

        # Extract configuration details from known_facts
        config_entries = self._extract_config_entries(finding)
        if not config_entries:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Cannot determine required configuration from finding metadata",
            )

        mutations: list[dict] = []

        if file_path.exists():
            # Append configuration to existing file
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

            new_content = self._append_config_to_content(
                original_content, config_entries, file_path.suffix
            )

            if new_content == original_content:
                return ToolResult(
                    tool_name=self.name,
                    item_id=item_id,
                    success=False,
                    mutations=[],
                    confidence=0.0,
                    validation_passed=False,
                    error="Configuration entries already exist or cannot be appended",
                )

            file_path.write_text(new_content, encoding="utf-8")
            mutations.append({
                "file": finding.file,
                "operation": "replace",
                "before": "(missing configuration)",
                "after": f"Added config entries: {', '.join(e[0] for e in config_entries)}",
            })
        else:
            # Create a new config file with the required entries
            file_path.parent.mkdir(parents=True, exist_ok=True)
            new_content = self._create_config_content(config_entries, file_path.suffix)
            file_path.write_text(new_content, encoding="utf-8")
            mutations.append({
                "file": finding.file,
                "operation": "create",
                "before": "",
                "after": f"Created config with entries: {', '.join(e[0] for e in config_entries)}",
            })

        # Validate syntax for Python files
        validation_passed = True
        if file_path.suffix == ".py":
            validation_passed = self._validate_syntax(file_path)
            if not validation_passed:
                # Revert if validation failed
                if file_path.exists():
                    if mutations and mutations[0]["operation"] == "create":
                        file_path.unlink()
                    else:
                        file_path.write_text(original_content, encoding="utf-8")  # type: ignore[possibly-undefined]
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
            mutations=mutations,
            confidence=0.88,
            validation_passed=validation_passed,
            files_modified=[finding.file],
        )

    # ─── Strategy: UNDEFINED_REFERENCE (contract/interface) ────────────────

    def _fix_contract_reference(
        self,
        sandbox_path: str,
        file_path: Path,
        finding: Finding,
        context: dict,
    ) -> ToolResult:
        """Fix an undefined reference that is a contract/interface alignment issue.

        Handles:
          - Missing method implementation: adds a method stub to the class
          - Wrong function signature: updates the signature to match the expected interface
        """
        item_id = finding.finding_id

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

        # Determine which sub-strategy to use based on known_facts
        method_info = self._extract_method_info(finding)
        signature_info = self._extract_signature_info(finding)

        if method_info:
            result = self._add_method_stub(
                file_path, original_content, finding, method_info
            )
        elif signature_info:
            result = self._fix_signature(
                file_path, original_content, finding, signature_info
            )
        else:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Cannot determine contract fix strategy from finding metadata",
            )

        return result

    # ─── Sub-strategies ────────────────────────────────────────────────────

    def _add_method_stub(
        self,
        file_path: Path,
        content: str,
        finding: Finding,
        method_info: dict,
    ) -> ToolResult:
        """Add a missing method stub to the class specified in the finding.

        method_info keys: class_name, method_name, params (optional), return_type (optional)
        """
        item_id = finding.finding_id
        class_name = method_info.get("class_name", "")
        method_name = method_info.get("method_name", "")
        params = method_info.get("params", "self")
        return_type = method_info.get("return_type", "")

        if not class_name or not method_name:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Missing class_name or method_name for stub generation",
            )

        # Find the class in the file and locate its end
        class_pattern = re.compile(
            rf"^([ \t]*)class\s+{re.escape(class_name)}\b[^:]*:", re.MULTILINE
        )
        class_match = class_pattern.search(content)

        if not class_match:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error=f"Class '{class_name}' not found in {finding.file}",
            )

        class_indent = class_match.group(1)
        method_indent = class_indent + "    "
        body_indent = method_indent + "    "

        # Build the method stub
        return_annotation = f" -> {return_type}" if return_type else ""
        stub_lines = [
            "",
            f"{method_indent}def {method_name}({params}){return_annotation}:",
            f'{body_indent}"""TODO: Implement to satisfy interface contract."""',
            f"{body_indent}raise NotImplementedError(",
            f'{body_indent}    "{method_name} must be implemented"',
            f"{body_indent})",
            "",
        ]
        stub_text = "\n".join(stub_lines)

        # Find the end of the class body (next line at same or lower indent, or EOF)
        lines = content.splitlines(keepends=True)
        class_start_line = content[: class_match.start()].count("\n")
        insert_pos = len(content)  # default: append at end

        in_class_body = False
        for idx in range(class_start_line + 1, len(lines)):
            line = lines[idx]
            stripped = line.rstrip()
            if not stripped:
                continue  # skip blank lines
            line_indent = len(line) - len(line.lstrip())
            class_indent_len = len(class_indent) + 4  # methods are indented 4 from class

            if not in_class_body:
                if line_indent >= class_indent_len:
                    in_class_body = True
            else:
                # If we hit a line at the class indent level or less, that's outside the class
                if line_indent <= len(class_indent) and not line.strip().startswith("#"):
                    # Insert before this line
                    insert_pos = sum(len(l) for l in lines[:idx])
                    break

        # Insert the stub
        new_content = content[:insert_pos].rstrip("\n") + stub_text + "\n" + content[insert_pos:]

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
                error="Method stub insertion failed syntax validation; reverted",
            )

        return ToolResult(
            tool_name=self.name,
            item_id=item_id,
            success=True,
            mutations=[{
                "file": finding.file,
                "operation": "replace",
                "before": f"(missing method {method_name} in {class_name})",
                "after": f"Added method stub: {class_name}.{method_name}({params})",
            }],
            confidence=0.82,
            validation_passed=True,
            files_modified=[finding.file],
        )

    def _fix_signature(
        self,
        file_path: Path,
        content: str,
        finding: Finding,
        signature_info: dict,
    ) -> ToolResult:
        """Fix a function/method signature to match the expected interface.

        signature_info keys: func_name, expected_params, expected_return (optional)
        """
        item_id = finding.finding_id
        func_name = signature_info.get("func_name", "")
        expected_params = signature_info.get("expected_params", "")

        if not func_name or not expected_params:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Missing func_name or expected_params for signature fix",
            )

        # Find the function definition
        func_pattern = re.compile(
            rf"^([ \t]*def\s+{re.escape(func_name)}\s*)\(([^)]*)\)",
            re.MULTILINE,
        )
        func_match = func_pattern.search(content)

        if not func_match:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error=f"Function '{func_name}' not found in {finding.file}",
            )

        old_signature = func_match.group(0)
        prefix = func_match.group(1)
        old_params = func_match.group(2)
        new_signature = f"{prefix}({expected_params})"

        if old_signature == new_signature:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Function signature already matches expected interface",
            )

        new_content = content.replace(old_signature, new_signature, 1)
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
                error="Signature fix failed syntax validation; reverted",
            )

        return ToolResult(
            tool_name=self.name,
            item_id=item_id,
            success=True,
            mutations=[{
                "file": finding.file,
                "operation": "replace",
                "before": f"def {func_name}({old_params})",
                "after": f"def {func_name}({expected_params})",
            }],
            confidence=0.85,
            validation_passed=True,
            files_modified=[finding.file],
        )

    # ─── Helper Methods ────────────────────────────────────────────────────

    @staticmethod
    def _has_contract_keywords(finding: Finding) -> bool:
        """Check if known_facts contain contract/interface-related keywords."""
        text = " ".join(finding.known_facts).lower()
        if finding.root_cause:
            text += " " + finding.root_cause.lower()
        return any(kw in text for kw in _CONTRACT_KEYWORDS)

    @staticmethod
    def _extract_config_entries(finding: Finding) -> list[tuple[str, str]]:
        """Extract key=value configuration entries from finding known_facts.

        Looks for patterns like:
          - "Missing key: DATABASE_URL"
          - "Required: SECRET_KEY = 'changeme'"
          - "Add: timeout = 30"
          - "key: value"
        """
        entries: list[tuple[str, str]] = []
        seen_keys: set[str] = set()

        patterns = [
            # "Missing key: KEY_NAME" or "Required key: KEY_NAME"
            re.compile(r"(?:[Mm]issing|[Rr]equired)\s+(?:key|config|setting)[:;]?\s*['\"]?(\w+)['\"]?\s*(?:=\s*(.+))?"),
            # "Add: KEY = VALUE" or "Set: KEY = VALUE"
            re.compile(r"(?:[Aa]dd|[Ss]et)[:;]?\s*['\"]?(\w+)['\"]?\s*=\s*(.+)"),
            # "KEY = VALUE" (simple assignment)
            re.compile(r"^['\"]?([A-Z_][A-Z_0-9]*)['\"]?\s*=\s*(.+)"),
            # "key: value" (config style)
            re.compile(r"^['\"]?([A-Za-z_]\w*)['\"]?\s*:\s*(.+)"),
        ]

        sources = list(finding.known_facts)
        if finding.root_cause:
            sources.append(finding.root_cause)

        for source in sources:
            for pattern in patterns:
                match = pattern.search(source)
                if match:
                    key = match.group(1).strip().strip("'\"")
                    value = match.group(2).strip().strip("'\"") if match.group(2) else ""
                    if key and key not in seen_keys:
                        seen_keys.add(key)
                        entries.append((key, value))

        return entries

    @staticmethod
    def _append_config_to_content(
        content: str, entries: list[tuple[str, str]], suffix: str
    ) -> str:
        """Append configuration entries to existing file content.

        Format depends on file suffix:
          .py: NAME = "value" or NAME = value
          .env: NAME=value
          .ini/.cfg: name = value
          others: name = value
        """
        lines_to_add: list[str] = []

        for key, value in entries:
            # Skip if key already exists in content
            if re.search(rf"^\s*{re.escape(key)}\s*[=:]", content, re.MULTILINE):
                continue

            if suffix == ".py":
                # Use Python assignment style
                if value and value.replace(".", "").replace("-", "").isdigit():
                    lines_to_add.append(f"{key} = {value}")
                elif value.lower() in ("true", "false", "none"):
                    lines_to_add.append(f"{key} = {value.capitalize()}")
                else:
                    lines_to_add.append(f'{key} = "{value}"')
            elif suffix == ".env":
                lines_to_add.append(f"{key}={value}")
            else:
                lines_to_add.append(f"{key} = {value}")

        if not lines_to_add:
            return content  # Nothing to add

        # Ensure content ends with newline before appending
        if content and not content.endswith("\n"):
            content += "\n"

        content += "\n".join(lines_to_add) + "\n"
        return content

    @staticmethod
    def _create_config_content(entries: list[tuple[str, str]], suffix: str) -> str:
        """Create a new config file content with the required entries."""
        lines: list[str] = []

        if suffix == ".py":
            lines.append('"""Auto-generated configuration."""')
            lines.append("")
            for key, value in entries:
                if value and value.replace(".", "").replace("-", "").isdigit():
                    lines.append(f"{key} = {value}")
                elif value.lower() in ("true", "false", "none"):
                    lines.append(f"{key} = {value.capitalize()}")
                else:
                    lines.append(f'{key} = "{value}"')
        elif suffix == ".env":
            for key, value in entries:
                lines.append(f"{key}={value}")
        elif suffix in (".ini", ".cfg"):
            lines.append("[DEFAULT]")
            for key, value in entries:
                lines.append(f"{key} = {value}")
        else:
            for key, value in entries:
                lines.append(f"{key} = {value}")

        lines.append("")  # trailing newline
        return "\n".join(lines)

    @staticmethod
    def _extract_method_info(finding: Finding) -> dict:
        """Extract method stub information from finding known_facts.

        Looks for patterns like:
          - "Missing method 'process' in class 'Handler'"
          - "Class Handler must implement method process(self, data)"
          - "Interface requires: def process(self, data) -> bool"
        """
        patterns = [
            # "Missing method 'X' in class 'Y'" or "class Y missing method X"
            re.compile(
                r"[Mm]issing\s+method\s+['\"]?(\w+)['\"]?\s+in\s+class\s+['\"]?(\w+)['\"]?"
            ),
            # "Class Y must implement method X(params)"
            re.compile(
                r"[Cc]lass\s+['\"]?(\w+)['\"]?\s+must\s+implement\s+(?:method\s+)?['\"]?(\w+)['\"]?\s*\(([^)]*)\)"
            ),
            # "Interface requires: def X(params) -> return_type"
            re.compile(
                r"(?:[Ii]nterface|[Pp]rotocol|[Cc]ontract)\s+requires[:;]?\s*def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*(\S+))?"
            ),
            # "implement X in Y" or "add method X to Y"
            re.compile(
                r"(?:[Ii]mplement|[Aa]dd\s+method)\s+['\"]?(\w+)['\"]?\s+(?:in|to)\s+['\"]?(\w+)['\"]?"
            ),
        ]

        sources = list(finding.known_facts)
        if finding.root_cause:
            sources.append(finding.root_cause)

        for source in sources:
            # Pattern 1: Missing method 'X' in class 'Y'
            match = patterns[0].search(source)
            if match:
                return {
                    "method_name": match.group(1),
                    "class_name": match.group(2),
                    "params": "self",
                }

            # Pattern 2: Class Y must implement method X(params)
            match = patterns[1].search(source)
            if match:
                return {
                    "class_name": match.group(1),
                    "method_name": match.group(2),
                    "params": match.group(3) or "self",
                }

            # Pattern 3: Interface requires: def X(params) -> return_type
            match = patterns[2].search(source)
            if match:
                info: dict = {
                    "method_name": match.group(1),
                    "params": match.group(2) or "self",
                }
                if match.group(3):
                    info["return_type"] = match.group(3)
                # Try to find class name from other facts
                class_name = _find_class_name_in_facts(sources)
                if class_name:
                    info["class_name"] = class_name
                return info

            # Pattern 4: implement X in Y
            match = patterns[3].search(source)
            if match:
                return {
                    "method_name": match.group(1),
                    "class_name": match.group(2),
                    "params": "self",
                }

        return {}

    @staticmethod
    def _extract_signature_info(finding: Finding) -> dict:
        """Extract expected function signature from finding known_facts.

        Looks for patterns like:
          - "Expected signature: process(self, data, timeout=30)"
          - "Function 'process' should accept (self, data, timeout)"
          - "Signature mismatch: expected (self, data) got (self)"
        """
        patterns = [
            # "Expected signature: func_name(params)"
            re.compile(
                r"[Ee]xpected\s+signature[:;]?\s*['\"]?(\w+)['\"]?\s*\(([^)]*)\)"
            ),
            # "Function 'X' should accept (params)"
            re.compile(
                r"[Ff]unction\s+['\"]?(\w+)['\"]?\s+should\s+accept\s*\(([^)]*)\)"
            ),
            # "Signature mismatch.*expected (params)"
            re.compile(
                r"[Ss]ignature\s+mismatch.*['\"]?(\w+)['\"]?.*expected\s*\(([^)]*)\)"
            ),
            # "def X should be def X(params)"
            re.compile(
                r"def\s+(\w+)\s+should\s+be\s+def\s+\w+\s*\(([^)]*)\)"
            ),
        ]

        sources = list(finding.known_facts)
        if finding.root_cause:
            sources.append(finding.root_cause)

        for source in sources:
            for pattern in patterns:
                match = pattern.search(source)
                if match:
                    return {
                        "func_name": match.group(1),
                        "expected_params": match.group(2),
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


def _find_class_name_in_facts(sources: list[str]) -> str:
    """Search for a class name reference in a list of fact strings."""
    pattern = re.compile(r"[Cc]lass\s+['\"]?(\w+)['\"]?")
    for source in sources:
        match = pattern.search(source)
        if match:
            return match.group(1)
    return ""
