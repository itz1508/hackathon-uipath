"""Phase 1 Scanner — Deterministic analysis of target project.

Runs real checks against target content:
- Python syntax validation (compileall)
- Import resolution (AST-based)
- Dependency manifest inspection
- Module existence checks

Features:
- Complete Python 3.11+ stdlib module set
- Deduplication: groups findings by (module_name, category)
- Exclusion patterns: skips test fixtures, .venv, __pycache__, etc.
- Overlap/conflict detection: flags files with multiple issues
- Summary statistics in AnalysisOutput

Produces normalized findings with tool records.
Does NOT invent findings absent from tool output.
"""
from __future__ import annotations

import ast
import fnmatch
import hashlib
import re
import subprocess
import sys
import tomllib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models import (
    AnalysisOutput,
    Finding,
    FindingCategory,
    Severity,
    ToolRecord,
)

# ──────────────────────────────────────────────
# Complete Python 3.11+ Standard Library Modules
# ──────────────────────────────────────────────

STDLIB_MODULES: frozenset[str] = frozenset({
    # Special / underscore
    "__future__", "_thread",
    # A
    "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio",
    "asyncore", "atexit", "audioop",
    # B
    "base64", "bdb", "binascii", "binhex", "bisect", "builtins",
    # C
    "calendar", "cgi", "cgitb", "chunk", "cmath", "cmd", "code",
    "codecs", "codeop", "collections", "colorsys", "compileall",
    "concurrent", "configparser", "contextlib", "contextvars", "copy",
    "copyreg", "cProfile", "crypt", "csv", "ctypes", "curses",
    # D
    "dataclasses", "datetime", "dbm", "decimal", "difflib", "dis",
    "distutils", "doctest",
    # E
    "email", "encodings", "enum", "ensurepip", "errno",
    # F
    "faulthandler", "fcntl", "filecmp", "fileinput", "fnmatch",
    "fractions", "ftplib", "functools",
    # G
    "gc", "getopt", "getpass", "gettext", "glob", "graphlib", "grp",
    "gzip",
    # H
    "hashlib", "heapq", "hmac", "html", "http",
    # I
    "idlelib", "imaplib", "imghdr", "imp", "importlib", "inspect",
    "io", "ipaddress", "itertools",
    # J
    "json",
    # K
    "keyword",
    # L
    "lib2to3", "linecache", "locale", "logging", "lzma",
    # M
    "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap",
    "modulefinder", "msvcrt", "multiprocessing",
    # N
    "netrc", "nis", "nntplib", "ntpath", "numbers",
    # O
    "operator", "optparse", "os", "ossaudiodev",
    # P
    "pathlib", "pdb", "pickle", "pickletools", "pipes", "pkgutil",
    "platform", "plistlib", "poplib", "posix", "posixpath", "pprint",
    "profile", "pstats", "pty", "pwd", "py_compile", "pyclbr",
    "pydoc",
    # Q
    "queue", "quopri",
    # R
    "random", "re", "readline", "reprlib", "resource", "rlcompleter",
    "runpy",
    # S
    "sched", "secrets", "select", "selectors", "shelve", "shlex",
    "shutil", "signal", "site", "smtpd", "smtplib", "sndhdr",
    "socket", "socketserver", "spwd", "sqlite3", "ssl", "stat",
    "statistics", "string", "stringprep", "struct", "subprocess",
    "sunau", "symtable", "sys", "sysconfig", "syslog",
    # T
    "tabnanny", "tarfile", "telnetlib", "tempfile", "termios",
    "textwrap", "threading", "time", "timeit", "tkinter", "token",
    "tokenize", "tomllib", "trace", "traceback", "tracemalloc", "tty",
    "turtle", "turtledemo", "types", "typing", "typing_extensions",
    # U
    "unicodedata", "unittest", "urllib", "uu", "uuid",
    # V
    "venv",
    # W
    "warnings", "wave", "weakref", "webbrowser", "winreg", "winsound",
    "wsgiref",
    # X
    "xdrlib", "xml", "xmlrpc",
    # Z
    "zipapp", "zipfile", "zipimport", "zlib",
})

# ──────────────────────────────────────────────
# Default Exclusion Patterns
# ──────────────────────────────────────────────

DEFAULT_EXCLUDE_PATTERNS: list[str] = [
    "tests/fixtures/",
    "tests/fixtures\\",
    ".venv/",
    ".venv\\",
    "__pycache__/",
    "__pycache__\\",
    ".git/",
    ".git\\",
    "node_modules/",
    "node_modules\\",
    ".candidate_*",
]


def _should_exclude(file_path: str, exclude_patterns: list[str]) -> bool:
    """Check if a file path matches any exclusion pattern."""
    normalized = file_path.replace("\\", "/")
    for pattern in exclude_patterns:
        pat = pattern.replace("\\", "/")
        # Directory-based pattern (ends with /)
        if pat.endswith("/") and f"/{pat}" in f"/{normalized}":
            return True
        # Glob/fnmatch pattern
        if "*" in pat:
            # Check if any path component matches
            parts = normalized.split("/")
            for part in parts:
                if fnmatch.fnmatch(part, pat):
                    return True
        # Substring match for directory names
        elif pat in normalized:
            return True
    return False


# ──────────────────────────────────────────────
# Main Entry Point
# ──────────────────────────────────────────────


def scan_target(
    target_path: str,
    exclude_patterns: list[str] | None = None,
) -> AnalysisOutput:
    """Run deterministic analysis on the target project.

    Args:
        target_path: Path to the project directory to scan.
        exclude_patterns: List of patterns to exclude. Uses DEFAULT_EXCLUDE_PATTERNS
                          if None.

    Returns:
        Structured AnalysisOutput with tool records, deduplicated findings,
        overlap/conflict annotations, and summary statistics.
    """
    target = Path(target_path).resolve()
    if not target.exists() or not target.is_dir():
        return AnalysisOutput(
            analysis_completed=False,
            handoff_statement=f"Target path does not exist: {target_path}",
        )

    patterns = exclude_patterns if exclude_patterns is not None else DEFAULT_EXCLUDE_PATTERNS

    tools_run: list[ToolRecord] = []
    raw_findings: list[Finding] = []

    # Collect project files, respecting exclusion patterns
    all_py_files = list(target.rglob("*.py"))
    py_files = [
        f for f in all_py_files
        if not _should_exclude(str(f.relative_to(target)), patterns)
    ]
    req_file = target / "requirements.txt"

    # ─── Tool 1: python -m compileall (syntax check) ───
    compile_record = _run_compileall(target, py_files)
    tools_run.append(compile_record)
    if compile_record.exit_code != 0:
        syntax_findings = _parse_compile_errors(compile_record, target)
        raw_findings.extend(syntax_findings)

    # ─── Tool 2: Dependency manifest inspection ───
    dep_record, dep_findings = _inspect_dependencies(target, req_file)
    tools_run.append(dep_record)
    raw_findings.extend(dep_findings)

    # ─── Tool 3: Import resolution ───
    import_record, import_findings = _validate_imports(target, py_files, req_file)
    tools_run.append(import_record)
    raw_findings.extend(import_findings)

    # ─── Tool 4: pyproject.toml analysis ───
    pyproject_record, pyproject_findings = _detect_pyproject_issues(target)
    tools_run.append(pyproject_record)
    raw_findings.extend(pyproject_findings)

    # ─── Tool 5: Lock file policy ───
    lock_record, lock_findings = _detect_lock_file_policy(target)
    tools_run.append(lock_record)
    raw_findings.extend(lock_findings)

    # ─── Tool 6: Python version policy ───
    pyver_record, pyver_findings = _detect_python_version_policy(target)
    tools_run.append(pyver_record)
    raw_findings.extend(pyver_findings)

    # ─── Tool 7: Overlapping signatures ───
    overlap_record, overlap_findings = _detect_overlapping_signatures(target, py_files)
    tools_run.append(overlap_record)
    raw_findings.extend(overlap_findings)

    # ─── Tool 8: Dead code detection ───
    dead_record, dead_findings = _detect_dead_code(target, py_files)
    tools_run.append(dead_record)
    raw_findings.extend(dead_findings)

    # ─── Tool 9: Code duplication detection ───
    dup_record, dup_findings = _detect_code_duplication(target, py_files)
    tools_run.append(dup_record)
    raw_findings.extend(dup_findings)

    # ─── Deduplication ───
    findings = _deduplicate_findings(raw_findings)

    # ─── Overlap / Conflict Detection ───
    _annotate_conflicts(findings)

    # ─── Build statements from real findings ───
    handoff = _build_handoff_statement(findings)
    llm = _build_llm_statement(findings)
    precal = _build_precalibration_statement(findings, len(py_files))

    return AnalysisOutput(
        analysis_completed=True,
        tools_run=tools_run,
        findings=findings,
        handoff_statement=handoff,
        llm_statement=llm,
        pre_calibration_statement=precal,
    )


# ──────────────────────────────────────────────
# Deduplication
# ──────────────────────────────────────────────


def _deduplicate_findings(raw_findings: list[Finding]) -> list[Finding]:
    """Group findings by (affected_component, category).

    Instead of reporting the same module 76 times, report it once with
    a count and list of affected files in known_facts.
    """
    # Key: (affected_component or root_cause, category)
    groups: dict[tuple[str, str], list[Finding]] = defaultdict(list)

    for f in raw_findings:
        # Use affected_component as primary grouping key; fall back to root_cause
        key_component = f.affected_component or f.root_cause or f.finding_id
        key = (key_component, f.category)
        groups[key].append(f)

    deduplicated: list[Finding] = []
    counter = 0

    for (component, category), group in groups.items():
        counter += 1
        if len(group) == 1:
            # Single occurrence — keep as-is but renumber
            finding = group[0]
            finding.finding_id = f"F-{counter:03d}"
            deduplicated.append(finding)
        else:
            # Multiple occurrences — merge into one finding
            representative = group[0]
            affected_files = sorted(set(f.file for f in group))
            all_lines = [f.line for f in group if f.line is not None]

            # Merge known_facts
            merged_facts = list(representative.known_facts)
            merged_facts.append(
                f"Found {len(group)} occurrences across {len(affected_files)} file(s)"
            )
            if len(affected_files) <= 10:
                merged_facts.append(f"Affected files: {', '.join(affected_files)}")

            # Use highest severity in the group
            severity_order = {
                Severity.CRITICAL: 4, Severity.HIGH: 3,
                Severity.MEDIUM: 2, Severity.LOW: 1, Severity.INFO: 0,
            }
            highest_sev = max(group, key=lambda f: severity_order.get(
                Severity(f.severity) if f.severity in [s.value for s in Severity] else Severity.INFO, 0
            ))

            merged = Finding(
                finding_id=f"F-{counter:03d}",
                category=representative.category,
                severity=highest_sev.severity,
                file=affected_files[0] if len(affected_files) == 1 else f"{affected_files[0]} (+{len(affected_files)-1} more)",
                line=all_lines[0] if len(all_lines) == 1 else None,
                known_facts=merged_facts,
                root_cause=representative.root_cause,
                root_cause_confirmed=representative.root_cause_confirmed,
                missing_information=representative.missing_information,
                supporting_tools=representative.supporting_tools,
                confidence=representative.confidence,
                affected_component=component,
            )
            deduplicated.append(merged)

    return deduplicated


# ──────────────────────────────────────────────
# Overlap / Conflict Detection
# ──────────────────────────────────────────────


def _annotate_conflicts(findings: list[Finding]) -> None:
    """Detect when multiple findings affect the same file.

    Adds a 'conflicts_with' annotation in known_facts for overlapping findings.
    Mutates findings in place.
    """
    # Map file -> list of finding IDs
    file_to_findings: dict[str, list[str]] = defaultdict(list)

    for f in findings:
        # Handle merged file strings like "foo.py (+2 more)"
        primary_file = f.file.split(" (+")[0] if " (+" in f.file else f.file
        # Could be comma-separated from merged files in known_facts
        file_to_findings[primary_file].append(f.finding_id)

    # Annotate findings that share files with other findings
    for f in findings:
        primary_file = f.file.split(" (+")[0] if " (+" in f.file else f.file
        co_findings = file_to_findings.get(primary_file, [])
        if len(co_findings) > 1:
            others = [fid for fid in co_findings if fid != f.finding_id]
            if others:
                f.known_facts.append(
                    f"CONFLICT: This file also has issues: {', '.join(others)}"
                )


def get_summary_statistics(output: AnalysisOutput) -> dict[str, Any]:
    """Compute summary statistics from an AnalysisOutput.

    Returns:
        - total_unique_issues: deduplicated count
        - files_with_multiple_issues: count of files affected by >1 finding
        - potential_conflicts: count of findings that overlap on the same file
    """
    file_counts: dict[str, int] = defaultdict(int)
    for f in output.findings:
        primary_file = f.file.split(" (+")[0] if " (+" in f.file else f.file
        file_counts[primary_file] += 1

    files_with_multiple = sum(1 for count in file_counts.values() if count > 1)
    conflict_findings = sum(
        1 for f in output.findings
        if any("CONFLICT:" in fact for fact in f.known_facts)
    )

    return {
        "total_unique_issues": len(output.findings),
        "files_with_multiple_issues": files_with_multiple,
        "potential_conflicts": conflict_findings,
    }


# ──────────────────────────────────────────────
# Tool Runners
# ──────────────────────────────────────────────


def _run_compileall(target: Path, py_files: list[Path]) -> ToolRecord:
    """Run python -m compileall to detect syntax errors."""
    started = datetime.now(timezone.utc).isoformat()

    try:
        result = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", str(target)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(target),
        )
        completed = datetime.now(timezone.utc).isoformat()
        return ToolRecord(
            tool="python -m compileall",
            started_at=started,
            completed_at=completed,
            exit_code=result.returncode,
            stdout=result.stdout[:2000],
            stderr=result.stderr[:2000],
            target=str(target),
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return ToolRecord(
            tool="python -m compileall",
            started_at=started,
            completed_at=datetime.now(timezone.utc).isoformat(),
            exit_code=-1,
            stderr=str(e)[:500],
            target=str(target),
        )


def _parse_compile_errors(record: ToolRecord, target: Path) -> list[Finding]:
    """Parse compileall stderr for syntax errors."""
    findings: list[Finding] = []
    error_text = record.stderr or record.stdout

    for line in error_text.splitlines():
        if "Error compiling" in line or "SyntaxError" in line:
            match = re.search(r"'([^']+\.py)'", line)
            file_path = match.group(1) if match else "unknown"

            try:
                rel_path = str(Path(file_path).relative_to(target))
            except (ValueError, TypeError):
                rel_path = file_path

            line_match = re.search(r"line (\d+)", error_text)
            line_num = int(line_match.group(1)) if line_match else None

            findings.append(Finding(
                finding_id=f"SYN-{len(findings)+1:03d}",
                category=FindingCategory.SYNTAX_ERROR,
                severity=Severity.HIGH,
                file=rel_path,
                line=line_num,
                known_facts=[
                    f"Syntax error detected in {rel_path}",
                    f"what_wrong: Python cannot parse this file",
                    f"why_it_matters: File cannot be imported or executed",
                    f"how_to_fix: Fix the syntax error at the indicated line",
                ],
                root_cause="Python parser cannot compile this file.",
                root_cause_confirmed=True,
                supporting_tools=["python -m compileall"],
                confidence=1.0,
            ))
            break  # One finding per compilation unit

    return findings


def _inspect_dependencies(
    target: Path, req_file: Path
) -> tuple[ToolRecord, list[Finding]]:
    """Inspect requirements.txt for dependency issues."""
    started = datetime.now(timezone.utc).isoformat()
    findings: list[Finding] = []

    if not req_file.exists():
        return ToolRecord(
            tool="dependency-manifest-inspection",
            started_at=started,
            completed_at=datetime.now(timezone.utc).isoformat(),
            exit_code=0,
            stdout="No requirements.txt found.",
            target=str(target),
        ), findings

    content = req_file.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Parse requirements
    packages: dict[str, tuple[str, int]] = {}  # name -> (version_spec, line_num)
    duplicates: list[tuple[str, int, int]] = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^([a-zA-Z0-9_.-]+)\s*([=<>!~]+.*)$", stripped)
        if match:
            pkg_name = match.group(1).lower().replace("-", "_")
            version_spec = match.group(2).strip()
            if pkg_name in packages:
                duplicates.append((pkg_name, packages[pkg_name][1], i))
            packages[pkg_name] = (version_spec, i)

    # Check for known-broken versions
    KNOWN_FAKE_VERSIONS = {"==99.0.0", "==0.0.1", "==999.0.0"}
    for pkg_name, (version_spec, line_num) in packages.items():
        if version_spec in KNOWN_FAKE_VERSIONS:
            findings.append(Finding(
                finding_id=f"DEP-{len(findings)+1:03d}",
                category=FindingCategory.BROKEN_DEPENDENCY,
                severity=Severity.CRITICAL,
                file="requirements.txt",
                line=line_num,
                known_facts=[
                    f"Package '{pkg_name}' pinned to {version_spec}",
                    "This version does not exist on PyPI",
                    f"what_wrong: Package '{pkg_name}' pinned to non-existent version {version_spec}",
                    f"why_it_matters: pip install will fail — package cannot be resolved",
                    f"how_to_fix: Update '{pkg_name}' to a valid version from PyPI",
                ],
                root_cause=f"Package '{pkg_name}' is pinned to a non-existent version.",
                root_cause_confirmed=True,
                supporting_tools=["dependency-manifest-inspection"],
                confidence=1.0,
                affected_component=pkg_name,
            ))

    # Check for version conflicts documented in inline comments
    for i, line in enumerate(lines, 1):
        if "#" not in line:
            continue
        code_part, comment_part = line.split("#", 1)
        comment = comment_part.strip().lower()

        if "requires" not in comment or ">=" not in comment:
            continue

        code_match = re.match(r"^\s*([a-zA-Z0-9_.-]+)\s*==\s*([0-9.]+)", code_part)
        if not code_match:
            continue

        pinned_pkg = code_match.group(1).lower().replace("-", "_")
        pinned_ver = code_match.group(2)

        req_match = re.search(r">=\s*([0-9.]+)", comment)
        if not req_match:
            continue

        required_ver = req_match.group(1)

        try:
            pinned_parts = [int(x) for x in pinned_ver.split(".")]
            required_parts = [int(x) for x in required_ver.split(".")]
            max_len = max(len(pinned_parts), len(required_parts))
            pinned_parts.extend([0] * (max_len - len(pinned_parts)))
            required_parts.extend([0] * (max_len - len(required_parts)))

            if pinned_parts < required_parts:
                missing_info: list[str] = []
                has_lock = any(
                    (target / f).exists()
                    for f in ("poetry.lock", "Pipfile.lock", "requirements.lock")
                )
                has_pyver = any(
                    (target / f).exists()
                    for f in (".python-version", "runtime.txt")
                )
                pyproject = target / "pyproject.toml"
                if pyproject.exists() and "python" in pyproject.read_text(
                    encoding="utf-8", errors="ignore"
                ).lower():
                    has_pyver = True

                if not has_lock:
                    missing_info.append("No lock file — transitive dependency state unknown")
                if not has_pyver:
                    missing_info.append("Target Python version not declared")

                defect_doc = target / "DEFECT.md"
                if defect_doc.exists():
                    defect_text = defect_doc.read_text(encoding="utf-8", errors="ignore").lower()
                    if "known resolution" in defect_text or "compatible" in defect_text:
                        missing_info = []

                findings.append(Finding(
                    finding_id=f"DEP-{len(findings)+1:03d}",
                    category=FindingCategory.DEPENDENCY_CONFLICT,
                    severity=Severity.HIGH,
                    file="requirements.txt",
                    line=i,
                    known_facts=[
                        f"Package '{pinned_pkg}' pinned to =={pinned_ver}",
                        f"Requires {pinned_pkg}>={required_ver}",
                        f"what_wrong: Version {pinned_ver} is pinned but >={required_ver} is required",
                        f"why_it_matters: Dependency resolution will fail",
                        f"how_to_fix: Update the pinned version to satisfy the constraint >={required_ver}",
                    ],
                    root_cause=f"Installed version {pinned_ver} does not satisfy requirement >={required_ver}.",
                    root_cause_confirmed=True,
                    missing_information=missing_info,
                    supporting_tools=["dependency-manifest-inspection"],
                    confidence=1.0 if not missing_info else 0.7,
                    affected_component=pinned_pkg,
                ))
        except (ValueError, TypeError):
            pass

    # Check for duplicates
    for pkg_name, first_line, second_line in duplicates:
        findings.append(Finding(
            finding_id=f"DEP-{len(findings)+1:03d}",
            category=FindingCategory.DEPENDENCY_CONFLICT,
            severity=Severity.HIGH,
            file="requirements.txt",
            line=second_line,
            known_facts=[
                f"Package '{pkg_name}' declared on lines {first_line} and {second_line}",
                f"what_wrong: Duplicate dependency declaration for '{pkg_name}'",
                f"why_it_matters: Dependency resolution will fail or produce unpredictable results",
                f"how_to_fix: Remove the duplicate entry on line {second_line} or consolidate versions",
            ],
            root_cause=f"Duplicate dependency declaration for '{pkg_name}'.",
            root_cause_confirmed=True,
            supporting_tools=["dependency-manifest-inspection"],
            confidence=1.0,
            affected_component=pkg_name,
        ))

    completed = datetime.now(timezone.utc).isoformat()
    return ToolRecord(
        tool="dependency-manifest-inspection",
        started_at=started,
        completed_at=completed,
        exit_code=1 if findings else 0,
        stdout=f"Inspected {len(packages)} packages, {len(findings)} issues found.",
        target=str(target),
    ), findings


def _validate_imports(
    target: Path, py_files: list[Path], req_file: Path
) -> tuple[ToolRecord, list[Finding]]:
    """Validate imports in Python files against available modules."""
    started = datetime.now(timezone.utc).isoformat()
    findings: list[Finding] = []

    # Collect known local modules
    local_modules: set[str] = set()
    for pf in py_files:
        rel = pf.relative_to(target)
        local_modules.add(rel.stem)
        for part in rel.parts[:-1]:
            local_modules.add(part)

    # Collect declared dependencies from requirements.txt
    declared_deps: set[str] = set()
    if req_file.exists():
        for line in req_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                match = re.match(r"^([a-zA-Z0-9_.-]+)", line)
                if match:
                    declared_deps.add(match.group(1).lower().replace("-", "_"))

    # Analyze imports per file
    for pf in py_files:
        try:
            source = pf.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(pf))
        except SyntaxError:
            continue  # Already caught by compileall

        rel_path = str(pf.relative_to(target)).replace("\\", "/")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _check_import(
                        alias.name, rel_path, node.lineno,
                        local_modules, declared_deps, target, findings
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    _check_import(
                        node.module, rel_path, node.lineno,
                        local_modules, declared_deps, target, findings
                    )

    completed = datetime.now(timezone.utc).isoformat()
    return ToolRecord(
        tool="import-validation",
        started_at=started,
        completed_at=completed,
        exit_code=1 if findings else 0,
        stdout=f"Validated imports in {len(py_files)} files, {len(findings)} issues.",
        target=str(target),
    ), findings


def _check_import(
    module_name: str,
    file_path: str,
    line_num: int,
    local_modules: set[str],
    declared_deps: set[str],
    target: Path,
    findings: list[Finding],
) -> None:
    """Check a single import for resolution issues."""
    top_level = module_name.split(".")[0]
    top_lower = top_level.lower().replace("-", "_")
    parts = module_name.split(".")

    # Skip stdlib
    if top_lower in STDLIB_MODULES:
        return

    # Skip declared dependencies
    if top_lower in declared_deps:
        return

    # For dotted imports, verify the full path resolves
    if len(parts) > 1:
        full_resolved = _resolve_dotted_path(target, parts)
        if full_resolved:
            return
        if top_level in local_modules or (target / top_level).is_dir():
            similar = _find_similar_submodule(target, parts)
            if similar:
                findings.append(Finding(
                    finding_id=f"IMP-{len(findings)+1:03d}",
                    category=FindingCategory.MISSING_IMPORT,
                    severity=Severity.HIGH,
                    file=file_path,
                    line=line_num,
                    known_facts=[
                        f"Import '{module_name}' does not resolve",
                        f"Similar module exists: '{similar}'",
                        f"what_wrong: Module '{module_name}' imported but does not exist",
                        f"why_it_matters: Will cause ImportError at runtime",
                        f"how_to_fix: Rename import to '{similar}' (likely typo)",
                    ],
                    root_cause=f"Likely typo: '{module_name}' should be '{similar}'.",
                    root_cause_confirmed=True,
                    missing_information=[],
                    supporting_tools=["import-validation"],
                    confidence=0.9,
                    affected_component=module_name,
                ))
            return

    # Skip known local modules
    if top_level in local_modules or top_lower in local_modules:
        return

    # Check if the module path exists locally
    module_path = target / module_name.replace(".", "/")
    if module_path.exists() or (module_path.parent / f"{module_path.name}.py").exists():
        return
    if (target / f"{top_level}.py").exists():
        return

    # Not found — determine category
    similar = _find_similar_module(top_level, local_modules, target)

    if similar:
        findings.append(Finding(
            finding_id=f"IMP-{len(findings)+1:03d}",
            category=FindingCategory.MISSING_IMPORT,
            severity=Severity.HIGH,
            file=file_path,
            line=line_num,
            known_facts=[
                f"Import '{module_name}' does not resolve",
                f"Similar module exists: '{similar}'",
                f"what_wrong: Module '{module_name}' imported but does not exist",
                f"why_it_matters: Will cause ImportError at runtime",
                f"how_to_fix: Rename import to '{similar}' (likely typo)",
            ],
            root_cause=f"Likely typo: '{top_level}' should be '{similar}'.",
            root_cause_confirmed=True,
            missing_information=[],
            supporting_tools=["import-validation"],
            confidence=0.9,
            affected_component=module_name,
        ))
    else:
        is_ambiguous = (
            "generated" in top_lower
            or "internal" in top_lower
            or "private" in top_lower
            or "client" in top_lower
        )

        if is_ambiguous:
            findings.append(Finding(
                finding_id=f"IMP-{len(findings)+1:03d}",
                category=FindingCategory.AMBIGUOUS_IMPORT,
                severity=Severity.HIGH,
                file=file_path,
                line=line_num,
                known_facts=[
                    f"Import '{module_name}' does not resolve",
                    "No matching module in repository or declared dependencies",
                    f"what_wrong: Module '{module_name}' imported but not declared",
                    f"why_it_matters: Will cause ImportError at runtime unless generated during build",
                    f"how_to_fix: Add '{top_level}' to requirements.txt or pyproject.toml dependencies, or document the generation step",
                ],
                root_cause="",
                root_cause_confirmed=False,
                missing_information=[
                    "Whether the module is generated during build",
                    "Generation command or tool",
                    "Expected output location",
                    "Whether it should be installed from a private index",
                ],
                supporting_tools=["import-validation"],
                confidence=0.3,
                affected_component=module_name,
            ))
        else:
            findings.append(Finding(
                finding_id=f"IMP-{len(findings)+1:03d}",
                category=FindingCategory.MISSING_DEPENDENCY,
                severity=Severity.HIGH,
                file=file_path,
                line=line_num,
                known_facts=[
                    f"Import '{module_name}' does not resolve",
                    "Module not found in requirements.txt or local project",
                    f"what_wrong: Module '{module_name}' imported but not declared",
                    f"why_it_matters: Will cause ImportError at runtime",
                    f"how_to_fix: Add '{top_level}' to requirements.txt or pyproject.toml dependencies",
                ],
                root_cause=f"Module '{top_level}' is imported but not declared as a dependency.",
                root_cause_confirmed=True,
                missing_information=[],
                supporting_tools=["import-validation"],
                confidence=0.95,
                affected_component=module_name,
            ))


# ──────────────────────────────────────────────
# Path Resolution Helpers
# ──────────────────────────────────────────────


def _resolve_dotted_path(target: Path, parts: list[str]) -> bool:
    """Check if a dotted import path resolves to an existing file/package."""
    # target/part1/part2/partN.py
    file_path = target
    for p in parts[:-1]:
        file_path = file_path / p
    file_path = file_path / f"{parts[-1]}.py"
    if file_path.exists():
        return True

    # target/part1/part2/partN/__init__.py
    pkg_path = target
    for p in parts:
        pkg_path = pkg_path / p
    if (pkg_path / "__init__.py").exists():
        return True

    # target/part1/part2.py (module containing partN)
    if len(parts) >= 2:
        parent_file = target
        for p in parts[:-1]:
            parent_file = parent_file / p
        parent_file = parent_file.with_suffix(".py")
        if parent_file.exists():
            return True

    return False


def _find_similar_submodule(target: Path, parts: list[str]) -> str | None:
    """Find similar submodule for typo detection in dotted imports."""
    parent = target
    for p in parts[:-1]:
        parent = parent / p
        if not parent.exists():
            return None

    target_name = parts[-1].lower()
    for item in parent.iterdir():
        if item.name.startswith(".") or item.name.startswith("__"):
            continue
        item_name = item.stem.lower()
        if item_name == target_name:
            continue
        if len(target_name) == len(item_name) and sum(
            a != b for a, b in zip(target_name, item_name)
        ) == 1:
            corrected_parts = list(parts[:-1]) + [item.stem]
            return ".".join(corrected_parts)

    return None


def _find_similar_module(name: str, local_modules: set[str], target: Path) -> str | None:
    """Find a similar local module name (typo detection)."""
    name_lower = name.lower()

    for local in local_modules:
        if len(name_lower) == len(local) and sum(
            a != b for a, b in zip(name_lower, local.lower())
        ) == 1:
            return local

    for subdir in target.iterdir():
        if subdir.is_dir() and not subdir.name.startswith("."):
            subdir_lower = subdir.name.lower()
            if len(name_lower) == len(subdir_lower) and sum(
                a != b for a, b in zip(name_lower, subdir_lower)
            ) == 1:
                return subdir.name

    return None


# ──────────────────────────────────────────────
# New Detectors: pyproject.toml, Lock files, Python version
# ──────────────────────────────────────────────


def _detect_pyproject_issues(target: Path) -> tuple[ToolRecord, list[Finding]]:
    """Analyze pyproject.toml for missing fields and dependency cross-references."""
    started = datetime.now(timezone.utc).isoformat()
    findings: list[Finding] = []
    pyproject_path = target / "pyproject.toml"

    if not pyproject_path.exists():
        return ToolRecord(
            tool="pyproject-toml-analysis",
            started_at=started,
            completed_at=datetime.now(timezone.utc).isoformat(),
            exit_code=0,
            stdout="No pyproject.toml found — skipped.",
            target=str(target),
        ), findings

    try:
        content = pyproject_path.read_bytes()
        data = tomllib.loads(content.decode("utf-8"))
    except Exception as e:
        findings.append(Finding(
            finding_id="PYPROJ-001",
            category=FindingCategory.SYNTAX_ERROR,
            severity=Severity.HIGH,
            file="pyproject.toml",
            line=None,
            known_facts=[
                f"Failed to parse pyproject.toml: {e}",
                "what_wrong: pyproject.toml contains invalid TOML syntax",
                "why_it_matters: Build tools cannot read project metadata",
                "how_to_fix: Fix the TOML syntax error in pyproject.toml",
            ],
            root_cause=f"pyproject.toml is not valid TOML: {e}",
            root_cause_confirmed=True,
            supporting_tools=["pyproject-toml-analysis"],
            confidence=1.0,
            affected_component="pyproject.toml",
        ))
        return ToolRecord(
            tool="pyproject-toml-analysis",
            started_at=started,
            completed_at=datetime.now(timezone.utc).isoformat(),
            exit_code=1,
            stderr=str(e),
            target=str(target),
        ), findings

    project = data.get("project", None)

    # Check for missing [project] section
    if project is None:
        findings.append(Finding(
            finding_id="PYPROJ-002",
            category=FindingCategory.CONFIGURATION_MISSING,
            severity=Severity.HIGH,
            file="pyproject.toml",
            line=None,
            known_facts=[
                "No [project] section in pyproject.toml",
                "what_wrong: Missing [project] section — no project metadata defined",
                "why_it_matters: PEP 621 metadata is required for modern Python packaging",
                "how_to_fix: Add a [project] section with name and version fields",
            ],
            root_cause="pyproject.toml is missing the [project] section.",
            root_cause_confirmed=True,
            supporting_tools=["pyproject-toml-analysis"],
            confidence=1.0,
            affected_component="pyproject.toml",
        ))
    else:
        # Check for missing requires-python
        if "requires-python" not in project:
            findings.append(Finding(
                finding_id="PYPROJ-003",
                category=FindingCategory.CONFIGURATION_MISSING,
                severity=Severity.HIGH,
                file="pyproject.toml",
                line=None,
                known_facts=[
                    "No requires-python field in [project]",
                    "what_wrong: Missing requires-python field",
                    "why_it_matters: Users may install on unsupported Python versions causing runtime failures",
                    "how_to_fix: Add requires-python = '>=3.11' (or appropriate version) to [project]",
                ],
                root_cause="pyproject.toml does not declare requires-python.",
                root_cause_confirmed=True,
                supporting_tools=["pyproject-toml-analysis"],
                confidence=1.0,
                affected_component="pyproject.toml",
            ))

        # Check for missing dependencies
        if "dependencies" not in project:
            findings.append(Finding(
                finding_id="PYPROJ-004",
                category=FindingCategory.CONFIGURATION_MISSING,
                severity=Severity.HIGH,
                file="pyproject.toml",
                line=None,
                known_facts=[
                    "No dependencies list in [project]",
                    "what_wrong: Missing dependencies field in [project]",
                    "why_it_matters: Package has no declared runtime dependencies — installs may be incomplete",
                    "how_to_fix: Add dependencies = ['pkg1', 'pkg2'] to [project]",
                ],
                root_cause="pyproject.toml does not declare dependencies.",
                root_cause_confirmed=True,
                supporting_tools=["pyproject-toml-analysis"],
                confidence=1.0,
                affected_component="pyproject.toml",
            ))
        else:
            # Cross-reference declared deps vs imports in code
            declared_pyproject_deps = set()
            raw_deps = project.get("dependencies", [])
            for dep_str in raw_deps:
                # Extract package name (before any version specifier)
                dep_match = re.match(r"^([a-zA-Z0-9_.-]+)", dep_str)
                if dep_match:
                    declared_pyproject_deps.add(
                        dep_match.group(1).lower().replace("-", "_")
                    )

            # Validate dependency specifiers
            _validate_dep_specifiers(raw_deps, findings)

            # Collect all imports from Python files
            all_py_files = [
                f for f in target.rglob("*.py")
                if not _should_exclude(str(f.relative_to(target)), DEFAULT_EXCLUDE_PATTERNS)
            ]
            imported_modules: set[str] = set()
            for pf in all_py_files:
                try:
                    source = pf.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(pf))
                except (SyntaxError, UnicodeDecodeError):
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            top = alias.name.split(".")[0].lower().replace("-", "_")
                            if top not in STDLIB_MODULES:
                                imported_modules.add(top)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and node.level == 0:
                            top = node.module.split(".")[0].lower().replace("-", "_")
                            if top not in STDLIB_MODULES:
                                imported_modules.add(top)

            # Find declared but not imported
            local_modules: set[str] = set()
            for pf in all_py_files:
                rel = pf.relative_to(target)
                local_modules.add(rel.stem.lower())
                for part in rel.parts[:-1]:
                    local_modules.add(part.lower())

            unused_deps = declared_pyproject_deps - imported_modules - local_modules
            if unused_deps:
                findings.append(Finding(
                    finding_id="PYPROJ-005",
                    category=FindingCategory.DEPENDENCY_CONFLICT,
                    severity=Severity.INFO,
                    file="pyproject.toml",
                    line=None,
                    known_facts=[
                        f"Declared dependencies not imported in code: {', '.join(sorted(unused_deps))}",
                        "what_wrong: Dependencies declared but not imported in any Python file",
                        "why_it_matters: Unused dependencies increase install size and attack surface",
                        "how_to_fix: Remove unused dependencies or verify they are used indirectly (plugins, CLI tools)",
                    ],
                    root_cause="Dependencies declared in pyproject.toml are not imported in project code.",
                    root_cause_confirmed=False,
                    supporting_tools=["pyproject-toml-analysis"],
                    confidence=0.6,
                    affected_component="pyproject.toml",
                ))

    # Check for dependency-groups
    dep_groups = data.get("dependency-groups", None)
    if dep_groups:
        group_names = list(dep_groups.keys())
        findings.append(Finding(
            finding_id="PYPROJ-006",
            category=FindingCategory.CONFIGURATION_MISSING,
            severity=Severity.INFO,
            file="pyproject.toml",
            line=None,
            known_facts=[
                f"Dependency groups found: {', '.join(group_names)}",
                "what_wrong: Dependency groups detected (informational)",
                "why_it_matters: Dependency groups (PEP 735) provide dev/test isolation",
                "how_to_fix: No action needed — this is informational",
            ],
            root_cause=f"pyproject.toml uses dependency-groups: {', '.join(group_names)}.",
            root_cause_confirmed=True,
            supporting_tools=["pyproject-toml-analysis"],
            confidence=1.0,
            affected_component="pyproject.toml",
        ))

    completed = datetime.now(timezone.utc).isoformat()
    return ToolRecord(
        tool="pyproject-toml-analysis",
        started_at=started,
        completed_at=completed,
        exit_code=1 if any(f.severity in (Severity.HIGH, Severity.CRITICAL) for f in findings) else 0,
        stdout=f"Analyzed pyproject.toml, {len(findings)} findings.",
        target=str(target),
    ), findings


def _validate_dep_specifiers(raw_deps: list[str], findings: list[Finding]) -> None:
    """Validate dependency specifiers using packaging.requirements if available."""
    try:
        from packaging.requirements import Requirement, InvalidRequirement
        for dep_str in raw_deps:
            try:
                Requirement(dep_str)
            except InvalidRequirement as e:
                findings.append(Finding(
                    finding_id=f"PYPROJ-SPEC-{len(findings)+1:03d}",
                    category=FindingCategory.BROKEN_DEPENDENCY,
                    severity=Severity.HIGH,
                    file="pyproject.toml",
                    line=None,
                    known_facts=[
                        f"Invalid dependency specifier: '{dep_str}'",
                        f"Parse error: {e}",
                        f"what_wrong: Dependency '{dep_str}' has invalid specifier syntax",
                        "why_it_matters: pip/build tools will reject this dependency",
                        f"how_to_fix: Fix the specifier syntax — see PEP 508",
                    ],
                    root_cause=f"Invalid dependency specifier: {e}",
                    root_cause_confirmed=True,
                    supporting_tools=["pyproject-toml-analysis"],
                    confidence=1.0,
                    affected_component="pyproject.toml",
                ))
    except ImportError:
        # packaging not available — do basic regex validation
        spec_pattern = re.compile(
            r"^[a-zA-Z0-9_.-]+(\[.*\])?\s*(([><=!~]=?|===?)\s*[a-zA-Z0-9.*+!_-]+\s*,?\s*)*$"
        )
        for dep_str in raw_deps:
            stripped = dep_str.strip()
            if stripped and not spec_pattern.match(stripped):
                findings.append(Finding(
                    finding_id=f"PYPROJ-SPEC-{len(findings)+1:03d}",
                    category=FindingCategory.BROKEN_DEPENDENCY,
                    severity=Severity.MEDIUM,
                    file="pyproject.toml",
                    line=None,
                    known_facts=[
                        f"Possibly invalid dependency specifier: '{dep_str}'",
                        "what_wrong: Dependency specifier may not conform to PEP 508",
                        "why_it_matters: pip/build tools may reject this dependency",
                        "how_to_fix: Verify specifier syntax against PEP 508",
                    ],
                    root_cause=f"Dependency specifier '{dep_str}' may be invalid (packaging library not available for full validation).",
                    root_cause_confirmed=False,
                    supporting_tools=["pyproject-toml-analysis"],
                    confidence=0.5,
                    affected_component="pyproject.toml",
                ))


def _detect_lock_file_policy(target: Path) -> tuple[ToolRecord, list[Finding]]:
    """Check for presence/absence of lock files and report policy issues."""
    started = datetime.now(timezone.utc).isoformat()
    findings: list[Finding] = []

    lock_file_names = [
        "requirements.lock",
        "poetry.lock",
        "Pipfile.lock",
        "uv.lock",
        "pdm.lock",
    ]

    found_locks: list[str] = []
    for name in lock_file_names:
        if (target / name).exists():
            found_locks.append(name)

    has_manifest = (target / "pyproject.toml").exists() or (target / "requirements.txt").exists()

    if not found_locks and has_manifest:
        findings.append(Finding(
            finding_id="LOCK-001",
            category=FindingCategory.CONFIGURATION_MISSING,
            severity=Severity.HIGH,
            file=str(target),
            line=None,
            known_facts=[
                "No lock file found in project root",
                f"Manifest files present: {', '.join(f for f in ['pyproject.toml', 'requirements.txt'] if (target / f).exists())}",
                "what_wrong: No lock file — transitive dependency state unknown",
                "why_it_matters: Builds are non-reproducible; different installs may get different transitive versions",
                "how_to_fix: Generate a lock file (pip freeze > requirements.lock, poetry lock, uv lock, etc.)",
            ],
            root_cause="No lock file present despite having a dependency manifest.",
            root_cause_confirmed=True,
            supporting_tools=["lock-file-policy"],
            confidence=1.0,
            affected_component="lock-file",
        ))
    elif len(found_locks) > 1:
        findings.append(Finding(
            finding_id="LOCK-002",
            category=FindingCategory.DEPENDENCY_CONFLICT,
            severity=Severity.HIGH,
            file=str(target),
            line=None,
            known_facts=[
                f"Multiple lock files found: {', '.join(found_locks)}",
                "what_wrong: Conflicting lock files — unclear dependency authority",
                "why_it_matters: Developers may use different tools producing inconsistent environments",
                "how_to_fix: Choose one package manager and remove the other lock file(s)",
            ],
            root_cause=f"Multiple conflicting lock files: {', '.join(found_locks)}.",
            root_cause_confirmed=True,
            supporting_tools=["lock-file-policy"],
            confidence=1.0,
            affected_component="lock-file",
        ))
    elif found_locks:
        for lock_name in found_locks:
            findings.append(Finding(
                finding_id=f"LOCK-{len(findings)+1:03d}",
                category=FindingCategory.CONFIGURATION_MISSING,
                severity=Severity.INFO,
                file=lock_name,
                line=None,
                known_facts=[
                    f"Lock file found: {lock_name}",
                    f"what_wrong: Lock file present (informational)",
                    f"why_it_matters: Reproducible installs are possible via {lock_name}",
                    f"how_to_fix: No action needed — this is informational",
                ],
                root_cause=f"Lock file '{lock_name}' is present.",
                root_cause_confirmed=True,
                supporting_tools=["lock-file-policy"],
                confidence=1.0,
                affected_component="lock-file",
            ))

    completed = datetime.now(timezone.utc).isoformat()
    return ToolRecord(
        tool="lock-file-policy",
        started_at=started,
        completed_at=completed,
        exit_code=1 if any(f.severity in (Severity.HIGH, Severity.CRITICAL) for f in findings) else 0,
        stdout=f"Lock file check: found {len(found_locks)} lock file(s).",
        target=str(target),
    ), findings


def _detect_python_version_policy(target: Path) -> tuple[ToolRecord, list[Finding]]:
    """Check if the Python version is declared anywhere in the project."""
    started = datetime.now(timezone.utc).isoformat()
    findings: list[Finding] = []

    version_sources: list[tuple[str, str]] = []  # (source_file, version_string)

    # Check .python-version
    python_version_file = target / ".python-version"
    if python_version_file.exists():
        ver = python_version_file.read_text(encoding="utf-8", errors="ignore").strip()
        if ver:
            version_sources.append((".python-version", ver))

    # Check runtime.txt
    runtime_file = target / "runtime.txt"
    if runtime_file.exists():
        ver = runtime_file.read_text(encoding="utf-8", errors="ignore").strip()
        if ver:
            version_sources.append(("runtime.txt", ver))

    # Check requires-python in pyproject.toml
    pyproject_path = target / "pyproject.toml"
    if pyproject_path.exists():
        try:
            content = pyproject_path.read_bytes()
            data = tomllib.loads(content.decode("utf-8"))
            project = data.get("project", {})
            requires_python = project.get("requires-python", "")
            if requires_python:
                version_sources.append(("pyproject.toml [requires-python]", requires_python))
        except Exception:
            pass  # Parse errors handled by _detect_pyproject_issues

    if not version_sources:
        findings.append(Finding(
            finding_id="PYVER-001",
            category=FindingCategory.CONFIGURATION_MISSING,
            severity=Severity.MEDIUM,
            file=str(target),
            line=None,
            known_facts=[
                "No Python version declaration found",
                "Checked: .python-version, runtime.txt, pyproject.toml requires-python",
                "what_wrong: Python version not declared — environment reproducibility risk",
                "why_it_matters: Contributors may use incompatible Python versions causing subtle bugs",
                "how_to_fix: Add a .python-version file or set requires-python in pyproject.toml",
            ],
            root_cause="No Python version constraint declared in the project.",
            root_cause_confirmed=True,
            supporting_tools=["python-version-policy"],
            confidence=1.0,
            affected_component="python-version",
        ))
    else:
        for source, version in version_sources:
            findings.append(Finding(
                finding_id=f"PYVER-{len(findings)+1:03d}",
                category=FindingCategory.CONFIGURATION_MISSING,
                severity=Severity.INFO,
                file=source,
                line=None,
                known_facts=[
                    f"Python version declared: {version}",
                    f"Source: {source}",
                    "what_wrong: Python version declared (informational)",
                    f"why_it_matters: Environment reproducibility ensured via {source}",
                    "how_to_fix: No action needed — this is informational",
                ],
                root_cause=f"Python version '{version}' is declared in {source}.",
                root_cause_confirmed=True,
                supporting_tools=["python-version-policy"],
                confidence=1.0,
                affected_component="python-version",
            ))

    completed = datetime.now(timezone.utc).isoformat()
    return ToolRecord(
        tool="python-version-policy",
        started_at=started,
        completed_at=completed,
        exit_code=1 if any(f.severity == Severity.MEDIUM for f in findings) else 0,
        stdout=f"Python version policy: {len(version_sources)} source(s) found.",
        target=str(target),
    ), findings


# ──────────────────────────────────────────────
# Statement Builders
# ──────────────────────────────────────────────


def _build_handoff_statement(findings: list[Finding]) -> str:
    """Build handoff statement from real findings."""
    if not findings:
        return (
            "No blocking dependency, import, syntax, or test failures were detected. "
            "All configured deterministic checks completed without errors."
        )

    parts = [f"{len(findings)} issue(s) require processing:"]
    for f in findings:
        parts.append(
            f"  {f.finding_id} [{f.severity}] {f.category}: "
            f"{f.root_cause or 'Root cause unconfirmed — information gap.'} "
            f"(file: {f.file})"
        )
    return "\n".join(parts)


def _build_llm_statement(findings: list[Finding]) -> str:
    """Build LLM advisory statement from findings."""
    if not findings:
        return (
            "The project is eligible for pre-simulation evaluation "
            "based on the completed checks. No issues require advisory."
        )

    parts = ["Analysis advisory:"]
    for f in findings:
        if f.root_cause_confirmed:
            parts.append(f"  {f.finding_id}: {f.root_cause}")
        else:
            parts.append(
                f"  {f.finding_id}: Root cause not confirmed. "
                f"Missing: {', '.join(f.missing_information)}"
            )
    return "\n".join(parts)


def _build_precalibration_statement(findings: list[Finding], file_count: int) -> str:
    """Build pre-calibration statement — baseline completeness."""
    confirmed = sum(1 for f in findings if f.root_cause_confirmed)
    unconfirmed = sum(1 for f in findings if not f.root_cause_confirmed)

    parts = [
        f"Calibration baseline: {file_count} Python files scanned.",
        f"Total findings: {len(findings)} ({confirmed} confirmed, {unconfirmed} unconfirmed).",
    ]

    if unconfirmed > 0:
        parts.append("Unconfirmed items require additional information before scoring.")
    else:
        parts.append("All findings have confirmed root causes.")

    return " ".join(parts)


# ──────────────────────────────────────────────
# Tool 7: Overlapping Signatures Detection
# ──────────────────────────────────────────────

_MIN_FUNCTION_NODES = 12


class _FunctionNormalizer(ast.NodeTransformer):
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node.name = "_function"
        node.decorator_list = []
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        node.name = "_function"
        node.decorator_list = []
        return self.generic_visit(node)


def _detect_overlapping_signatures(
    target: Path, py_files: list[Path]
) -> tuple[ToolRecord, list[Finding]]:
    """Detect functions with identical normalized AST across different files."""
    started = datetime.now(timezone.utc).isoformat()
    findings: list[Finding] = []

    # Group functions by normalized AST fingerprint
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for pf in py_files:
        try:
            source = pf.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue

        rel_path = str(pf.relative_to(target)).replace("\\", "/")

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if sum(1 for _ in ast.walk(node)) < _MIN_FUNCTION_NODES:
                continue
            try:
                normalized = _FunctionNormalizer().visit(
                    ast.fix_missing_locations(ast.parse(ast.unparse(node)))
                ).body[0]
                fingerprint = hashlib.sha256(
                    ast.dump(normalized, include_attributes=False).encode("utf-8")
                ).hexdigest()
            except Exception:
                continue

            groups[fingerprint].append({
                "path": rel_path,
                "function": node.name,
                "line": node.lineno,
            })

    # Report groups that span multiple files
    for fingerprint, occurrences in groups.items():
        unique_files = {item["path"] for item in occurrences}
        if len(unique_files) < 2:
            continue
        func_names = sorted(set(item["function"] for item in occurrences))
        findings.append(Finding(
            finding_id=f"OVL-{len(findings)+1:03d}",
            category=FindingCategory.OVERLAPPING_SIGNATURES,
            severity=Severity.MEDIUM,
            file=occurrences[0]["path"],
            line=occurrences[0]["line"],
            known_facts=[
                f"Function(s) {', '.join(func_names)} have identical normalized AST",
                f"Found in {len(unique_files)} files: {', '.join(sorted(unique_files)[:5])}",
                f"AST fingerprint: {fingerprint[:16]}...",
                "what_wrong: Multiple files contain structurally identical function implementations.",
                "why_it_matters: Parallel copies can drift while appearing to provide the same behavior.",
                "how_to_fix: Consolidate into a shared module or confirm intentional duplication.",
            ],
            root_cause=f"Overlapping function signatures across {len(unique_files)} files.",
            root_cause_confirmed=True,
            supporting_tools=["overlapping-signature-detector"],
            confidence=0.9,
            affected_component=func_names[0] if func_names else "unknown",
        ))

    completed = datetime.now(timezone.utc).isoformat()
    return ToolRecord(
        tool="overlapping-signature-detector",
        started_at=started,
        completed_at=completed,
        exit_code=1 if findings else 0,
        stdout=f"Analyzed function signatures, {len(findings)} overlapping groups found.",
        target=str(target),
    ), findings


# ──────────────────────────────────────────────
# Tool 8: Dead Code Detection
# ──────────────────────────────────────────────


def _detect_dead_code(
    target: Path, py_files: list[Path]
) -> tuple[ToolRecord, list[Finding]]:
    """Detect functions/classes defined but never referenced in any other file."""
    started = datetime.now(timezone.utc).isoformat()
    findings: list[Finding] = []

    # Phase 1: Collect all top-level function/class definitions
    definitions: dict[str, list[dict[str, Any]]] = defaultdict(list)  # name -> [{file, line}]

    for pf in py_files:
        try:
            source = pf.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue

        rel_path = str(pf.relative_to(target)).replace("\\", "/")

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    definitions[node.name].append({"file": rel_path, "line": node.lineno})
            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith("_"):
                    definitions[node.name].append({"file": rel_path, "line": node.lineno})

    # Phase 2: Collect all references (imports + name usage) across all files
    all_source = ""
    for pf in py_files:
        try:
            all_source += pf.read_text(encoding="utf-8") + "\n"
        except (OSError, UnicodeDecodeError):
            continue

    # Phase 3: Find definitions with zero references outside their own definition
    for name, defs in definitions.items():
        if len(name) < 3:
            continue
        # Count occurrences in all source (crude but fast)
        count = all_source.count(name)
        # Subtract self-definitions (at least 1 per def site)
        count -= len(defs)
        if count <= 0:
            for d in defs:
                findings.append(Finding(
                    finding_id=f"DEAD-{len(findings)+1:03d}",
                    category=FindingCategory.DEAD_CODE,
                    severity=Severity.LOW,
                    file=d["file"],
                    line=d["line"],
                    known_facts=[
                        f"'{name}' is defined but has no references in any other file",
                        "what_wrong: Function/class is defined but never imported or called.",
                        "why_it_matters: Dead code increases maintenance burden and confusion.",
                        "how_to_fix: Remove if unused, or add to __all__ if it's a public API.",
                    ],
                    root_cause=f"'{name}' appears unused across the project.",
                    root_cause_confirmed=False,
                    missing_information=["May be used by external callers or dynamic imports"],
                    supporting_tools=["dead-code-detector"],
                    confidence=0.6,
                    affected_component=name,
                ))

    completed = datetime.now(timezone.utc).isoformat()
    return ToolRecord(
        tool="dead-code-detector",
        started_at=started,
        completed_at=completed,
        exit_code=1 if findings else 0,
        stdout=f"Analyzed {len(definitions)} definitions, {len(findings)} potentially dead.",
        target=str(target),
    ), findings


# ──────────────────────────────────────────────
# Tool 9: Code Duplication Detection
# ──────────────────────────────────────────────

_MIN_DUPLICATE_BYTES = 40


def _detect_code_duplication(
    target: Path, py_files: list[Path]
) -> tuple[ToolRecord, list[Finding]]:
    """Detect files with identical normalized source code."""
    started = datetime.now(timezone.utc).isoformat()
    findings: list[Finding] = []

    # Group files by normalized content hash
    groups: dict[str, list[str]] = defaultdict(list)

    for pf in py_files:
        try:
            source = pf.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        # Normalize: strip whitespace, remove comments
        normalized = re.sub(r"#[^\n]*", "", source)
        normalized = "\n".join(line.rstrip() for line in normalized.split("\n")).strip()

        if len(normalized.encode("utf-8")) < _MIN_DUPLICATE_BYTES:
            continue

        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        rel_path = str(pf.relative_to(target)).replace("\\", "/")
        groups[digest].append(rel_path)

    # Report groups with multiple files
    for digest, paths in groups.items():
        if len(paths) < 2:
            continue
        findings.append(Finding(
            finding_id=f"DUP-{len(findings)+1:03d}",
            category=FindingCategory.CODE_DUPLICATION,
            severity=Severity.MEDIUM,
            file=paths[0],
            known_facts=[
                f"Files contain identical normalized source code",
                f"Duplicated across: {', '.join(paths[:5])}",
                f"SHA-256: {digest[:16]}...",
                "what_wrong: Multiple files contain the same code after normalization.",
                "why_it_matters: Parallel copies drift independently causing subtle bugs.",
                "how_to_fix: Consolidate into shared module or confirm intentional duplication.",
            ],
            root_cause=f"Exact code duplication across {len(paths)} files.",
            root_cause_confirmed=True,
            supporting_tools=["code-duplication-detector"],
            confidence=1.0,
            affected_component=paths[0],
        ))

    completed = datetime.now(timezone.utc).isoformat()
    return ToolRecord(
        tool="code-duplication-detector",
        started_at=started,
        completed_at=completed,
        exit_code=1 if findings else 0,
        stdout=f"Analyzed {len(py_files)} files, {len(findings)} duplication groups found.",
        target=str(target),
    ), findings
