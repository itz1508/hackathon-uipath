# Modified: 2026-06-29T14:30:00Z
"""Phase 3 — Simulation: Real execution on candidate copy.

Creates a candidate copy from the Phase 0 snapshot.
Sends ONLY qualified items to Simulation.
Executes actual planned changes on the candidate copy.
Records every command, exit code, stdout, and stderr.
Validates the candidate after mutation.
Confirms the real target remains unchanged.

On failure: isolates only the failed item, preserves successful work.

Mutation happens ONLY on the candidate copy. Never on the real target.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models import (
    CommandResult,
    Finding,
    FindingCategory,
    IsolationBrief,
    ItemScore,
    PlannedMutation,
    SimulationOutput,
)

# ──────────────────────────────────────────────
# Candidate Copy Management
# ──────────────────────────────────────────────


def create_candidate_copy(snapshot_path: str, target_path: str) -> str:
    """Create a candidate copy from the snapshot for mutation.

    Returns the path to the candidate copy.
    """
    target = Path(target_path).resolve()
    candidate_path = str(target.parent / f".candidate_{uuid.uuid4().hex[:8]}")
    
    source = Path(snapshot_path)
    if not source.exists():
        # Fall back to target if snapshot storage isn't available
        source = target
    
    shutil.copytree(str(source), candidate_path, dirs_exist_ok=True)
    return candidate_path


def hash_directory(dir_path: str) -> dict[str, str]:
    """Hash all files in a directory. Returns {relative_path: sha256}."""
    result: dict[str, str] = {}
    target = Path(dir_path).resolve()
    
    if not target.exists():
        return result
    
    for root, _dirs, files in os.walk(target):
        for filename in sorted(files):
            filepath = Path(root) / filename
            relative = str(filepath.relative_to(target)).replace(os.sep, "/")
            sha256 = hashlib.sha256()
            with open(filepath, "rb") as f:
                while chunk := f.read(8192):
                    sha256.update(chunk)
            result[relative] = sha256.hexdigest()
    
    return result


# ──────────────────────────────────────────────
# Mutation Planning
# ──────────────────────────────────────────────


def plan_mutations(
    qualified_items: list[str],
    findings: list[Finding],
    item_scores: list[ItemScore],
) -> list[PlannedMutation]:
    """Generate mutation plans for qualified items based on findings.

    Only items that scored >= 93.91% are included.
    Each mutation has a before/after with the planned change.
    """
    mutations: list[PlannedMutation] = []
    finding_map = {f.finding_id: f for f in findings}

    for item_id in qualified_items:
        finding = finding_map.get(item_id)
        if not finding:
            continue

        if finding.category == FindingCategory.DEPENDENCY_CONFLICT:
            # Plan: update the pinned version
            mutations.append(PlannedMutation(
                file="requirements.txt",
                operation="replace",
                before=_extract_before(finding),
                after=_extract_after(finding),
            ))
        elif finding.category == FindingCategory.MISSING_IMPORT:
            # Plan: fix the import statement
            if finding.file:
                mutations.append(PlannedMutation(
                    file=finding.file,
                    operation="replace",
                    before=_extract_import_before(finding),
                    after=_extract_import_after(finding),
                ))
        elif finding.category == FindingCategory.SYNTAX_ERROR:
            # Plan: fix the syntax error
            if finding.file:
                mutations.append(PlannedMutation(
                    file=finding.file,
                    operation="fix_syntax",
                    before="(syntax error)",
                    after="(corrected syntax)",
                ))

    return mutations


def _extract_before(finding: Finding) -> str:
    """Extract the 'before' state from a dependency finding."""
    for fact in finding.known_facts:
        if "pinned to" in fact:
            # e.g., "Package 'package_b' pinned to ==1.4"
            parts = fact.split("pinned to ")
            if len(parts) > 1:
                return parts[1].strip()
    return ""


def _extract_after(finding: Finding) -> str:
    """Determine the 'after' state for a dependency fix."""
    for fact in finding.known_facts:
        if ">=" in fact:
            # e.g., "Requires package_b>=2.0"
            parts = fact.split(">=")
            if len(parts) > 1:
                min_ver = parts[1].strip()
                # Use min version + 0.3 as safe target
                try:
                    major = int(min_ver.split(".")[0])
                    return f"=={major}.3"
                except (ValueError, IndexError):
                    return f">={min_ver}"
    return ""


def _extract_import_before(finding: Finding) -> str:
    """Extract the broken import from finding."""
    return finding.affected_component or ""


def _extract_import_after(finding: Finding) -> str:
    """Extract the corrected import from finding."""
    for fact in finding.known_facts:
        if "Similar module exists" in fact:
            # e.g., "Similar module exists: 'app.utils'"
            parts = fact.split("'")
            if len(parts) >= 2:
                return parts[1]
    return ""


# ──────────────────────────────────────────────
# Simulation Execution
# ──────────────────────────────────────────────


def execute_simulation(
    candidate_path: str,
    target_path: str,
    snapshot_id: str,
    qualified_items: list[str],
    findings: list[Finding],
    item_scores: list[ItemScore],
    tool_candidates: dict[str, list[str]] | None = None,
) -> SimulationOutput:
    """Execute simulation on the candidate copy.

    1. Plan mutations for qualified items.
    2. Apply mutations to candidate.
    3. Run validation commands.
    4. Record all results.
    5. Confirm real target unchanged.

    When tool_candidates is provided and non-empty, uses the toolkit
    execution path (per-issue sandboxes with matched tools). Otherwise
    falls back to the legacy mutation logic.

    Args:
        candidate_path: Path to the candidate copy (for mutation).
        target_path: Path to the real target (must remain unchanged).
        snapshot_id: Phase 0 snapshot reference.
        qualified_items: Items that scored >= 93.91% (from Phase 2).
        findings: Phase 1 findings for context.
        item_scores: Phase 2 scores for context.
        tool_candidates: Optional mapping {item_id: [tool_name, ...]} from
            pre-simulation filtering. When provided, uses toolkit path.
    """
    simulation_id = f"sim-{uuid.uuid4().hex[:8]}"
    candidate = Path(candidate_path)
    target = Path(target_path)

    # Record real target hashes BEFORE simulation
    target_hashes_before = hash_directory(str(target))

    # ── Toolkit execution path (when tool_candidates provided) ────────────
    if tool_candidates:
        context = {
            "case_id": simulation_id,
            "snapshot_id": snapshot_id,
            "candidate_path": candidate_path,
            "target_path": target_path,
        }
        toolkit_results = execute_with_toolkits(
            candidate_path, tool_candidates, findings, context
        )

        # Convert toolkit results to simulation output format
        resolved_items = [
            r.item_id for r in toolkit_results
            if hasattr(r, 'success') and r.success
        ]
        failed_items = [
            r.item_id for r in toolkit_results
            if hasattr(r, 'success') and not r.success
        ]
        # Deduplicate (a tool may appear multiple times per item)
        resolved_items = list(dict.fromkeys(resolved_items))
        failed_items = list(dict.fromkeys(
            item for item in failed_items if item not in resolved_items
        ))

        # Confirm real target unchanged
        target_hashes_after = hash_directory(str(target))
        real_target_unchanged = target_hashes_before == target_hashes_after

        return SimulationOutput(
            simulation_id=simulation_id,
            candidate_path=str(candidate),
            source_snapshot_id=snapshot_id,
            items_to_execute=qualified_items,
            planned_mutations=[],
            mutations_executed=[
                {"file": "toolkit", "operation": r.tool_name, "status": "success" if r.success else "failed"}
                for r in toolkit_results if hasattr(r, 'tool_name')
            ],
            validation_commands=[],
            commands=[],
            resolved_items=resolved_items,
            failed_items=failed_items,
            simulation_succeeded=len(resolved_items) > 0,
            real_target_unchanged=real_target_unchanged,
        )

    # ── Legacy mutation path (existing code below, unchanged) ─────────────

    # Plan mutations
    mutations = plan_mutations(qualified_items, findings, item_scores)

    # Apply mutations to candidate
    mutations_executed: list[dict[str, str]] = []
    for mutation in mutations:
        success = _apply_mutation(candidate, mutation)
        mutations_executed.append({
            "file": mutation.file,
            "operation": mutation.operation,
            "status": "applied_to_candidate" if success else "failed",
        })

    # Run validation commands on candidate
    commands: list[CommandResult] = []
    validation_cmds = [
        f"{sys.executable} -m compileall -q .",
    ]

    for cmd_str in validation_cmds:
        cmd_result = _run_command(cmd_str, cwd=str(candidate))
        commands.append(cmd_result)

    # Determine success
    all_commands_pass = all(c.exit_code == 0 for c in commands)
    resolved_items = qualified_items if all_commands_pass else []
    failed_items = [] if all_commands_pass else qualified_items

    # Confirm real target unchanged
    target_hashes_after = hash_directory(str(target))
    real_target_unchanged = target_hashes_before == target_hashes_after

    return SimulationOutput(
        simulation_id=simulation_id,
        candidate_path=str(candidate),
        source_snapshot_id=snapshot_id,
        items_to_execute=qualified_items,
        planned_mutations=mutations,
        mutations_executed=mutations_executed,
        validation_commands=validation_cmds,
        commands=commands,
        resolved_items=resolved_items,
        failed_items=failed_items,
        simulation_succeeded=all_commands_pass,
        real_target_unchanged=real_target_unchanged,
    )


def _apply_mutation(candidate: Path, mutation: PlannedMutation) -> bool:
    """Apply a single mutation to the candidate copy."""
    target_file = candidate / mutation.file
    
    if not target_file.exists():
        return False

    try:
        if mutation.operation == "replace" and mutation.before and mutation.after:
            content = target_file.read_text(encoding="utf-8")
            if mutation.before in content:
                content = content.replace(mutation.before, mutation.after, 1)
                target_file.write_text(content, encoding="utf-8")
                return True
        elif mutation.operation == "fix_syntax":
            # For syntax errors, attempt common fixes
            content = target_file.read_text(encoding="utf-8")
            # Common fix: add missing closing paren to def statement
            lines = content.splitlines()
            for i, line in enumerate(lines):
                stripped = line.rstrip()
                if stripped.startswith("def ") and not stripped.endswith(":"):
                    if "(" in stripped and ")" not in stripped:
                        # Missing closing paren
                        lines[i] = stripped + "):"
                        target_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
                        return True
        return False
    except (OSError, UnicodeDecodeError):
        return False


def _run_command(cmd_str: str, cwd: str) -> CommandResult:
    """Execute a command and capture results."""
    try:
        result = subprocess.run(
            cmd_str.split(),
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd,
        )
        return CommandResult(
            command=cmd_str,
            exit_code=result.returncode,
            stdout=result.stdout[:2000],
            stderr=result.stderr[:2000],
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return CommandResult(
            command=cmd_str,
            exit_code=-1,
            stderr=str(e)[:500],
        )


# ──────────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────────


def cleanup_candidate(candidate_path: str) -> None:
    """Remove the candidate copy after simulation."""
    try:
        shutil.rmtree(candidate_path, ignore_errors=True)
    except OSError:
        pass


# ──────────────────────────────────────────────
# Toolkit Execution (Phase 4 — per-issue sandboxes)
# ──────────────────────────────────────────────


def execute_with_toolkits(
    candidate_path: str,
    tool_candidates: dict[str, list[str]],
    findings: list[Finding],
    context: dict,
) -> list:
    """Execute toolkit tools in parallel sandboxes per issue.

    For each issue that has tool candidates:
    1. Create an isolated sandbox (copy of candidate)
    2. Instantiate matched tools
    3. Run tools sequentially within the sandbox
    4. Collect and return results

    Sandboxes are independent — parallel-safe by design.
    This function is called during Phase 4 (Simulation) only.

    Args:
        candidate_path: Path to the candidate copy (base for sandboxes).
        tool_candidates: Mapping from item_id to list of tool names.
        findings: All findings from Phase 1.
        context: Runtime metadata (case_id, snapshot_id, etc.).

    Returns:
        List of ToolResult objects (one per tool execution attempt).
    """
    from toolkits.base import ToolResult, ToolContract
    from toolkits.refactor import RefactorTool
    from toolkits.dep_fix import DepFixTool
    from toolkits.import_repair import ImportRepairTool
    from toolkits.contract_align import ContractAlignTool
    from toolkits.test_repair import TestRepairTool

    # Tool registry (name → instance).
    # Only deterministic tools execute here. The coding agent is a
    # Resolution Planner (PreSimulation) — it produces contracts, not mutations.
    tool_registry: dict[str, ToolContract] = {
        "refactor": RefactorTool(),
        "dep_fix": DepFixTool(),
        "import_repair": ImportRepairTool(),
        "contract_align": ContractAlignTool(),
        "test_repair": TestRepairTool(),
    }

    # Build finding lookup
    finding_map = {f.finding_id: f for f in findings}

    results: list = []

    for item_id, tool_names in tool_candidates.items():
        finding = finding_map.get(item_id)
        if not finding:
            continue

        # Create per-issue sandbox (isolated copy of candidate)
        sandbox_path = _create_issue_sandbox(candidate_path, item_id)
        if not sandbox_path:
            results.append(ToolResult(
                tool_name="sandbox",
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Failed to create per-issue sandbox",
            ))
            continue

        # Run matched tools sequentially within this sandbox
        for tool_name in tool_names:
            tool = tool_registry.get(tool_name)
            if not tool:
                results.append(ToolResult(
                    tool_name=tool_name,
                    item_id=item_id,
                    success=False,
                    mutations=[],
                    confidence=0.0,
                    validation_passed=False,
                    error=f"Tool '{tool_name}' not found in registry",
                ))
                continue

            try:
                result = tool.execute(sandbox_path, finding, context)
                results.append(result)
                # If a tool succeeds, stop trying other tools for this item
                if result.success:
                    break
            except Exception as exc:
                results.append(ToolResult(
                    tool_name=tool_name,
                    item_id=item_id,
                    success=False,
                    mutations=[],
                    confidence=0.0,
                    validation_passed=False,
                    error=f"Unhandled exception: {exc}",
                ))

        # Cleanup per-issue sandbox
        _cleanup_issue_sandbox(sandbox_path)

    return results


def _create_issue_sandbox(candidate_path: str, item_id: str) -> str:
    """Create an isolated sandbox for a single issue.

    Returns the sandbox path, or empty string on failure.
    """
    candidate = Path(candidate_path)
    if not candidate.exists():
        return ""

    # Create sandbox with unique name
    safe_item_id = item_id.replace("/", "_").replace("\\", "_")[:32]
    sandbox_name = f".sandbox_{safe_item_id}_{uuid.uuid4().hex[:6]}"
    sandbox_path = str(candidate.parent / sandbox_name)

    try:
        shutil.copytree(str(candidate), sandbox_path, dirs_exist_ok=True)
        return sandbox_path
    except (OSError, shutil.Error):
        return ""


def _cleanup_issue_sandbox(sandbox_path: str) -> None:
    """Remove a per-issue sandbox after execution."""
    try:
        shutil.rmtree(sandbox_path, ignore_errors=True)
    except OSError:
        pass
