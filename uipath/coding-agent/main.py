# Modified: 2026-06-24T07:30:00Z
"""Coding Agent — UiPath Coded Function wrapping Claude Code CLI.

This is a SEPARATE UiPath coded function that the pipeline invokes via
`uipath run main <json>` during Phase 3 (Simulation). It wraps Claude Code
CLI (or the Anthropic API) to fix code issues on the candidate copy.

Invocation:
    uipath run main '{"file_path": "...", "file_content": "...", "finding": {...}}'

Output:
    {"fixed_content": "...", "summary": "...", "confidence": 0.85, "success": true}

Architecture:
    BPMN → API Workflow → Edge Backend → Pipeline Phase 3
        → uipath run main <json>  (THIS FUNCTION — through UiPath)
        → Claude Code CLI / Anthropic API
        → Fixed code returned to pipeline

This gives the "coding agent through UiPath" integration:
    - PreSimulation Evaluator = UiPath Agent Builder (Claude) — scores at Phase 2
    - Coding Agent = Claude Code CLI — fixes at Phase 3
    - Both orchestrated by BPMN through UiPath
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


# ──────────────────────────────────────────────
# Input / Output Schema
# ──────────────────────────────────────────────


def main(input_json: str) -> str:
    """Entry point for UiPath coded function.

    Args:
        input_json: JSON string with:
            - file_path: str — relative path of the file (for context)
            - file_content: str — full content of the file to fix
            - finding: dict — the finding to fix:
                - category: str
                - severity: str
                - file: str
                - root_cause: str
                - known_facts: list[str]
                - description: str

    Returns:
        JSON string with:
            - fixed_content: str — fixed file content (or original if failed)
            - summary: str — what was changed
            - confidence: float — 0.0 to 1.0
            - success: bool — whether a fix was applied
            - method: str — "claude_code" | "anthropic_api" | "deterministic"
    """
    data = json.loads(input_json)
    file_path = data.get("file_path", "")
    file_content = data.get("file_content", "")
    finding = data.get("finding", {})

    result = fix_with_coding_agent(file_path, file_content, finding)
    return json.dumps(result)


def fix_with_coding_agent(
    file_path: str,
    file_content: str,
    finding: dict[str, Any],
) -> dict[str, Any]:
    """Fix a code issue using the best available coding agent.

    Tries in order:
    1. Claude Code CLI (if `claude` is on PATH and ANTHROPIC_API_KEY is set)
    2. Anthropic API (if `anthropic` package is installed and API key is set)
    3. Deterministic heuristics (fallback — always available)
    """
    # Try Claude Code CLI
    claude_path = shutil.which("claude")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if claude_path and api_key:
        result = _fix_with_claude_cli(claude_path, file_path, file_content, finding, api_key)
        if result["success"]:
            return result

    # Try Anthropic API
    if api_key:
        result = _fix_with_anthropic_api(file_path, file_content, finding, api_key)
        if result["success"]:
            return result

    # Fallback: deterministic heuristics
    return _fix_deterministic(file_path, file_content, finding)


# ──────────────────────────────────────────────
# Backend 1: Claude Code CLI
# ──────────────────────────────────────────────


def _build_prompt(file_path: str, file_content: str, finding: dict[str, Any]) -> str:
    """Build a focused fix prompt for the coding agent."""
    category = finding.get("category", "unknown")
    severity = finding.get("severity", "medium")
    root_cause = finding.get("root_cause", finding.get("description", ""))
    known_facts = finding.get("known_facts", [])
    facts_str = "\n".join(f"  - {f}" for f in known_facts) if known_facts else "  (none)"

    return f"""Fix the following code issue. Return ONLY the fixed file content — no explanation, no markdown fences.

Issue:
- Category: {category}
- Severity: {severity}
- File: {file_path}
- Root cause: {root_cause}
- Known facts:
{facts_str}

File content:
```
{file_content}
```

Fix the identified issue. Do not make unrelated changes. Return the complete fixed file content."""


def _fix_with_claude_cli(
    claude_path: str,
    file_path: str,
    file_content: str,
    finding: dict[str, Any],
    api_key: str,
) -> dict[str, Any]:
    """Invoke Claude Code CLI to fix the code."""
    prompt = _build_prompt(file_path, file_content, finding)

    try:
        result = subprocess.run(
            [claude_path, "--print", prompt],
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "ANTHROPIC_API_KEY": api_key},
        )

        if result.returncode != 0:
            return {
                "fixed_content": file_content,
                "summary": f"Claude Code CLI failed: {result.stderr[:200]}",
                "confidence": 0.0,
                "success": False,
                "method": "claude_code",
            }

        fixed = result.stdout.strip()
        # Strip markdown code fences if present
        if fixed.startswith("```"):
            lines = fixed.split("\n")
            # Remove first line (```python or ```)
            lines = lines[1:]
            # Remove trailing ``` if present
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            fixed = "\n".join(lines)

        if fixed and fixed != file_content:
            return {
                "fixed_content": fixed,
                "summary": f"Claude Code fixed {category_label(finding)} in {file_path}",
                "confidence": 0.85,
                "success": True,
                "method": "claude_code",
            }

        return {
            "fixed_content": file_content,
            "summary": "Claude Code returned no changes",
            "confidence": 0.0,
            "success": False,
            "method": "claude_code",
        }
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {
            "fixed_content": file_content,
            "summary": f"Claude Code CLI error: {exc}",
            "confidence": 0.0,
            "success": False,
            "method": "claude_code",
        }


# ──────────────────────────────────────────────
# Backend 2: Anthropic API
# ──────────────────────────────────────────────


def _fix_with_anthropic_api(
    file_path: str,
    file_content: str,
    finding: dict[str, Any],
    api_key: str,
) -> dict[str, Any]:
    """Invoke Anthropic API directly to fix the code."""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        prompt = _build_prompt(file_path, file_content, finding)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        fixed = message.content[0].text.strip()
        # Strip markdown code fences if present
        if fixed.startswith("```"):
            lines = fixed.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            fixed = "\n".join(lines)

        if fixed and fixed != file_content:
            return {
                "fixed_content": fixed,
                "summary": f"Anthropic API fixed {category_label(finding)} in {file_path}",
                "confidence": 0.85,
                "success": True,
                "method": "anthropic_api",
            }

        return {
            "fixed_content": file_content,
            "summary": "Anthropic API returned no changes",
            "confidence": 0.0,
            "success": False,
            "method": "anthropic_api",
        }
    except Exception as exc:
        return {
            "fixed_content": file_content,
            "summary": f"Anthropic API error: {exc}",
            "confidence": 0.0,
            "success": False,
            "method": "anthropic_api",
        }


# ──────────────────────────────────────────────
# Backend 3: Deterministic Heuristics (Fallback)
# ──────────────────────────────────────────────


def _fix_deterministic(
    file_path: str,
    file_content: str,
    finding: dict[str, Any],
) -> dict[str, Any]:
    """Deterministic fallback when no coding agent is available.

    Applies simple, rule-based fixes for common issue categories.
    This ensures the tool always produces a result (for testing and
    as a safety net in production).
    """
    import ast
    import re

    category = finding.get("category", "")
    root_cause = finding.get("root_cause", finding.get("description", ""))
    original = file_content
    fixed = file_content
    summary = ""

    if category == "syntax_error":
        # Try to fix common syntax errors
        try:
            ast.parse(fixed)
        except SyntaxError as e:
            lines = fixed.splitlines(keepends=True)
            if e.lineno and 0 < e.lineno <= len(lines):
                line = lines[e.lineno - 1]
                stripped = line.rstrip()
                # Missing colon after def/class/if/for/while/try/except/else/elif/with
                stmt_re = re.compile(r"^(\s*)(def |class |if |elif |else|for |while |try|except|finally|with )")
                if stmt_re.match(stripped) and not stripped.endswith(":"):
                    lines[e.lineno - 1] = stripped + ":\n"
                    fixed = "".join(lines)
                    summary = f"Added missing colon at line {e.lineno}"

                # Missing closing paren
                elif "(" in stripped and ")" not in stripped:
                    lines[e.lineno - 1] = stripped + "):\n"
                    fixed = "".join(lines)
                    summary = f"Added missing closing paren at line {e.lineno}"

    elif category == "missing_import":
        # Try to add missing import
        undefined_name = ""
        for fact in finding.get("known_facts", []):
            match = re.search(r"module\s+'?(\w+)'?", fact, re.IGNORECASE)
            if match:
                undefined_name = match.group(1)
                break
        if not undefined_name and root_cause:
            match = re.search(r"'(\w+)'", root_cause)
            if match:
                undefined_name = match.group(1)

        if undefined_name:
            # Check if it's a stdlib module
            stdlib = {
                "os", "sys", "json", "pathlib", "hashlib", "uuid", "datetime",
                "shutil", "logging", "typing", "enum", "dataclasses", "abc",
                "collections", "functools", "itertools", "re", "math", "time",
                "ast", "importlib", "unittest", "tempfile", "io", "copy",
            }
            if undefined_name in stdlib:
                # Add import at the top
                import_line = f"import {undefined_name}\n"
                # Find insertion point (after any __future__ imports or module docstring)
                insert_idx = 0
                lines = fixed.splitlines(keepends=True)
                for i, line in enumerate(lines):
                    if line.strip().startswith("from __future__") or line.strip().startswith("#"):
                        insert_idx = i + 1
                    elif line.strip() == "":
                        continue
                    else:
                        break
                lines.insert(insert_idx, import_line)
                fixed = "".join(lines)
                summary = f"Added missing import: {undefined_name}"

    elif category == "broken_dependency":
        # Fix requirements.txt — replace broken version
        if file_path.endswith("requirements.txt") or file_path == "requirements.txt":
            for fact in finding.get("known_facts", []):
                match = re.search(r"'([^']+)'.*pinned to.*?(==|>=|<=|~=)([\d.]+)", fact)
                if match:
                    pkg, op, ver = match.groups()
                    # Replace with a known-good version
                    fixed = fixed.replace(
                        f"{pkg}{op}{ver}",
                        f"{pkg}>=1.0.0",
                    )
                    summary = f"Fixed broken dependency version for {pkg}"

    elif category == "dependency_conflict":
        # Remove duplicate entries in requirements.txt
        if file_path.endswith("requirements.txt") or file_path == "requirements.txt":
            lines = fixed.splitlines()
            seen = set()
            deduped = []
            for line in lines:
                pkg_match = re.match(r"^([a-zA-Z0-9_.-]+)", line.strip())
                if pkg_match:
                    pkg = pkg_match.group(1).lower()
                    if pkg not in seen:
                        seen.add(pkg)
                        deduped.append(line)
                else:
                    deduped.append(line)
            if len(deduped) < len(lines):
                fixed = "\n".join(deduped) + "\n"
                summary = "Removed duplicate dependency entries"

    elif category == "circular_import":
        # Move import to function scope
        for fact in finding.get("known_facts", []):
            match = re.search(r"(?:import|from)\s+([\w.]+)", fact)
            if match:
                target = match.group(1)
                # Find top-level import
                lines = fixed.splitlines(keepends=True)
                import_re = re.compile(
                    rf"^(from\s+{re.escape(target)}\s+import\s+.+|import\s+{re.escape(target)}.*)\s*$"
                )
                for i, line in enumerate(lines):
                    if import_re.match(line):
                        import_text = line.strip()
                        lines[i] = ""
                        # Find first function and inject local import
                        for j, l in enumerate(lines):
                            if re.match(r"^(\s*)def\s+\w+", l):
                                indent = re.match(r"^(\s*)", l).group(1)
                                body_indent = indent + "    "
                                lines.insert(j + 1, f"{body_indent}{import_text}\n")
                                break
                        fixed = "".join(lines)
                        summary = f"Moved import of {target} to function scope"
                        break

    success = fixed != original
    return {
        "fixed_content": fixed,
        "summary": summary or "No deterministic fix found",
        "confidence": 0.60 if success else 0.0,
        "success": success,
        "method": "deterministic",
    }


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────


def category_label(finding: dict[str, Any]) -> str:
    """Human-readable category label."""
    return finding.get("category", "unknown").replace("_", " ")


if __name__ == "__main__":
    # Allow direct invocation: python main.py <json_file_or_string>
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if not arg:
        print(json.dumps({"error": "No input provided"}))
        sys.exit(1)

    # If it's a file path, read it
    if os.path.isfile(arg):
        with open(arg, "r", encoding="utf-8") as f:
            arg = f.read()

    print(main(arg))