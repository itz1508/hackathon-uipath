# Modified: 2026-06-24T08:30:00Z
"""Resolution Planner — coding agent as resolution designer, not fixer.

Architecture (contract-driven execution):

    Issue → ResolutionPlanner → ResolutionContract
                                      ↓
                              Tool Binding Layer
                                      ↓
                                 Simulation
                                      ↓
                                 Inspection
                                      ↓
                                 Promotion

The Resolution Planner sits in PreSimulation (Phase 2). It analyzes issues
using Claude Code CLI (or Anthropic API) and produces ResolutionContracts
that specify which tools to use, in what order, with what parameters.

The planner does NOT mutate files. It does NOT execute fixes. It only
designs resolution packages that the toolkit then executes deterministically.

Key principle: No single entity can both propose AND validate AND execute.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from models import Finding, FindingCategory, ResolutionContract, ToolInvocation


# ──────────────────────────────────────────────
# Path resolution
# ──────────────────────────────────────────────

_PIPELINE_DIR = Path(__file__).resolve().parent
_WORKSPACE_ROOT = _PIPELINE_DIR.parent
_CODING_AGENT_DIR = _WORKSPACE_ROOT / "coding-agent"


# ──────────────────────────────────────────────
# Tool selection heuristics
# ──────────────────────────────────────────────

# Maps finding categories to the deterministic tools that handle them
_CATEGORY_TOOL_MAP: dict[str, list[str]] = {
    FindingCategory.SYNTAX_ERROR.value: ["refactor"],
    FindingCategory.CIRCULAR_IMPORT.value: ["refactor"],
    FindingCategory.UNDEFINED_REFERENCE.value: ["refactor", "contract_align"],
    FindingCategory.MISSING_IMPORT.value: ["import_repair"],
    FindingCategory.AMBIGUOUS_IMPORT.value: ["import_repair"],
    FindingCategory.MISSING_DEPENDENCY.value: ["dep_fix"],
    FindingCategory.BROKEN_DEPENDENCY.value: ["dep_fix"],
    FindingCategory.DEPENDENCY_CONFLICT.value: ["dep_fix"],
    FindingCategory.TEST_FAILURE.value: ["test_repair"],
    FindingCategory.CONFIGURATION_MISSING.value: [],
}


def plan_resolutions(
    findings: list[Finding],
    target_path: str,
) -> list[ResolutionContract]:
    """Generate ResolutionContracts for all findings.

    For each finding:
    1. Determine which deterministic tools can handle it
    2. Ask the coding agent to analyze and recommend a resolution plan
    3. Merge deterministic + AI recommendations into a contract

    The contract specifies tools, parameters, execution order, and expected outcome.
    No files are modified.

    Args:
        findings: Phase 1 findings to plan resolutions for.
        target_path: Path to the target project (for context, not mutation).

    Returns:
        List of ResolutionContracts, one per finding.
    """
    contracts: list[ResolutionContract] = []

    for finding in findings:
        contract = _plan_single_resolution(finding, target_path)
        contracts.append(contract)

    return contracts


def _plan_single_resolution(
    finding: Finding,
    target_path: str,
) -> ResolutionContract:
    """Plan a resolution for a single finding.

    Combines deterministic tool selection with coding agent analysis.
    """
    # Deterministic contract_id: derived from finding_id, not random.
    # This ensures same input → same contract → same fingerprint.
    import hashlib as _hl
    contract_id = f"rc-{_hl.sha256(finding.finding_id.encode()).hexdigest()[:8]}"

    # Step 1: Deterministic tool selection (baseline)
    deterministic_tools = _select_deterministic_tools(finding)

    # Step 2: Ask coding agent for analysis and recommendations
    ai_recommendation = _ask_coding_agent(finding, target_path)

    # Step 3: Merge into a ResolutionContract
    tool_invocations = _build_tool_invocations(
        finding, deterministic_tools, ai_recommendation
    )

    execution_order = [inv.tool_name for inv in tool_invocations]

    # Confidence: AI recommendation boosts confidence if it agrees with deterministic
    confidence = _compute_confidence(deterministic_tools, ai_recommendation)

    expected_outcome = _describe_expected_outcome(finding, ai_recommendation)

    return ResolutionContract(
        contract_id=contract_id,
        finding_id=finding.finding_id,
        planner="coding_agent" if ai_recommendation else "deterministic",
        recommended_tools=tool_invocations,
        execution_order=execution_order,
        expected_outcome=expected_outcome,
        confidence=confidence,
        rationale=ai_recommendation.get("rationale", "") if ai_recommendation else "",
    )


# ──────────────────────────────────────────────
# Deterministic tool selection
# ──────────────────────────────────────────────


def _select_deterministic_tools(finding: Finding) -> list[str]:
    """Select deterministic tools based on finding category."""
    return _CATEGORY_TOOL_MAP.get(finding.category, [])


# ──────────────────────────────────────────────
# Coding agent analysis (Claude Code)
# ──────────────────────────────────────────────


def _ask_coding_agent(
    finding: Finding,
    target_path: str,
) -> dict[str, Any] | None:
    """Ask the coding agent to analyze a finding and recommend a resolution.

    Tries in order:
    1. Claude Code CLI (if available)
    2. Anthropic API (if available)
    3. Returns None (fallback to deterministic-only)

    The coding agent does NOT see or modify files. It receives the finding
    metadata and returns a recommendation.
    """
    # Try Claude Code CLI
    claude_path = shutil.which("claude")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if claude_path and api_key:
        result = _ask_via_claude_cli(claude_path, finding, api_key)
        if result:
            return result

    # Try Anthropic API
    if api_key:
        result = _ask_via_anthropic_api(finding, api_key)
        if result:
            return result

    # Try QwenCloud API (OpenAI-compatible)
    qwen_key = os.environ.get("QWEN_API_KEY", "")
    qwen_base = os.environ.get("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
    if qwen_key:
        result = _ask_via_qwen_api(finding, qwen_key, qwen_base)
        if result:
            return result

    # No coding agent available — return None (deterministic-only)
    return None


def _build_planning_prompt(finding: Finding) -> str:
    """Build a prompt that asks the coding agent to plan a resolution.

    The agent does NOT see file contents. It receives the finding metadata
    and must recommend tools, parameters, and execution order.
    """
    return f"""You are a resolution planner for a code analysis pipeline.
Analyze the following issue and recommend a resolution plan.

Available tools:
- refactor: structural code transformations (syntax fixes, circular imports, undefined references)
- dep_fix: dependency version fixes (broken versions, conflicts)
- import_repair: import statement fixes (missing imports, ambiguous imports)
- contract_align: interface/contract alignment (signature mismatches, protocol violations)
- test_repair: test fixes (broken tests, missing assertions)

Issue:
- Category: {finding.category}
- Severity: {finding.severity}
- File: {finding.file}
- Root cause: {finding.root_cause}
- Known facts: {json.dumps(finding.known_facts, indent=2)}

Respond in JSON format:
{{
    "recommended_tools": ["tool_name1", "tool_name2"],
    "execution_order": ["tool_name1", "tool_name2"],
    "parameters": {{"tool_name1": {{"param": "value"}}}},
    "expected_outcome": "description of what should be fixed",
    "confidence": 0.95,
    "rationale": "why these tools and this order"
}}

Only respond with valid JSON. No markdown fences."""


def _ask_via_claude_cli(
    claude_path: str,
    finding: Finding,
    api_key: str,
) -> dict[str, Any] | None:
    """Ask Claude Code CLI for a resolution recommendation."""
    prompt = _build_planning_prompt(finding)

    try:
        proc = subprocess.run(
            [claude_path, "--print", prompt],
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "ANTHROPIC_API_KEY": api_key},
        )

        if proc.returncode != 0:
            return None

        response = proc.stdout.strip()
        # Strip markdown fences if present
        if response.startswith("```"):
            lines = response.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            response = "\n".join(lines)

        return json.loads(response)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None


def _ask_via_anthropic_api(
    finding: Finding,
    api_key: str,
) -> dict[str, Any] | None:
    """Ask Anthropic API for a resolution recommendation."""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        prompt = _build_planning_prompt(finding)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        response = message.content[0].text.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            response = "\n".join(lines)

        return json.loads(response)
    except Exception:
        return None



def _ask_via_qwen_api(
    finding: Finding,
    api_key: str,
    base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
) -> dict[str, Any] | None:
    """Ask QwenCloud API (OpenAI-compatible) for a resolution recommendation."""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)
        prompt = _build_planning_prompt(finding)

        response = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "zai-org/GLM-5.2"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )

        result_text = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        if result_text.startswith("```"):
            lines = result_text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            result_text = "\n".join(lines)

        return json.loads(result_text)
    except Exception:
        return None

# ──────────────────────────────────────────────
# Contract assembly
# ──────────────────────────────────────────────


def _build_tool_invocations(
    finding: Finding,
    deterministic_tools: list[str],
    ai_recommendation: dict[str, Any] | None,
) -> list[ToolInvocation]:
    """Build ToolInvocation list from deterministic + AI recommendations.

    If the AI recommends tools, merge them with deterministic tools.
    AI recommendations take priority for execution order, but deterministic
    tools are always included as a safety net.
    """
    invocations: list[ToolInvocation] = []
    seen: set[str] = set()

    if ai_recommendation:
        # AI-recommended tools first
        ai_tools = ai_recommendation.get("recommended_tools", [])
        ai_params = ai_recommendation.get("parameters", {})

        for tool_name in ai_tools:
            if tool_name not in seen:
                invocations.append(ToolInvocation(
                    tool_name=tool_name,
                    parameters=ai_params.get(tool_name, {}),
                    expected_files_modified=[finding.file] if finding.file else [],
                ))
                seen.add(tool_name)

    # Add deterministic tools not already covered
    for tool_name in deterministic_tools:
        if tool_name not in seen:
            invocations.append(ToolInvocation(
                tool_name=tool_name,
                parameters={},
                expected_files_modified=[finding.file] if finding.file else [],
            ))
            seen.add(tool_name)

    return invocations


def _compute_confidence(
    deterministic_tools: list[str],
    ai_recommendation: dict[str, Any] | None,
) -> float:
    """Compute confidence score for the resolution contract.

    - Deterministic-only: 0.70 (baseline)
    - AI agrees with deterministic: 0.90 (high confidence)
    - AI disagrees: 0.75 (moderate — simulation will prove)
    - AI-only (no deterministic tools): 0.80 (AI has insight but unverified)
    """
    if not ai_recommendation:
        return 0.70 if deterministic_tools else 0.0

    ai_tools = set(ai_recommendation.get("recommended_tools", []))
    det_tools = set(deterministic_tools)

    ai_confidence = ai_recommendation.get("confidence", 0.8)

    if not det_tools:
        return min(0.85, ai_confidence)

    overlap = ai_tools & det_tools
    if overlap:
        return min(0.95, max(0.85, ai_confidence))
    else:
        return 0.75


def _describe_expected_outcome(
    finding: Finding,
    ai_recommendation: dict[str, Any] | None,
) -> str:
    """Describe what the resolution should achieve."""
    if ai_recommendation and ai_recommendation.get("expected_outcome"):
        return ai_recommendation["expected_outcome"]

    category = finding.category
    file = finding.file or "unknown"

    outcome_map = {
        FindingCategory.SYNTAX_ERROR.value: f"Syntax error in {file} resolved",
        FindingCategory.CIRCULAR_IMPORT.value: f"Circular import involving {file} broken",
        FindingCategory.UNDEFINED_REFERENCE.value: f"Undefined reference in {file} resolved",
        FindingCategory.MISSING_IMPORT.value: f"Missing import in {file} added",
        FindingCategory.AMBIGUOUS_IMPORT.value: f"Ambiguous import in {file} clarified",
        FindingCategory.MISSING_DEPENDENCY.value: f"Missing dependency resolved",
        FindingCategory.BROKEN_DEPENDENCY.value: f"Broken dependency version fixed",
        FindingCategory.DEPENDENCY_CONFLICT.value: f"Dependency conflict resolved",
        FindingCategory.TEST_FAILURE.value: f"Test failure resolved",
        FindingCategory.CONFIGURATION_MISSING.value: f"Missing configuration addressed",
    }

    return outcome_map.get(category, f"Issue in {file} addressed")
