# Modified: 2026-06-23T22:22:00Z
"""Phase 2 — Pre-Simulation Information Completeness Scoring.

Calculates item-level information-completeness scores from Phase 1 findings.
Determines whether the agent has enough information for one-shot execution.

This is NOT a code-quality score. It is an INFORMATION score.
A broken dependency with full resolution info scores HIGH.
A broken dependency with missing info scores LOW.

Threshold: 93.91% (PASS_THRESHOLD = 9391 integer hundredth-points)
Exactly 93.91 passes. 93.90 does not.

Routes:
- Complete items → Simulation
- Information-gap items → Isolation
- Good items continue while isolated items branch
"""
from __future__ import annotations

from pathlib import Path

from models import (
    Finding,
    FindingCategory,
    IsolationBrief,
    ItemRoute,
    ItemScore,
    PreSimulationOutput,
    ResolutionContract,
)

# Threshold in hundredth-points for deterministic comparison
PASS_THRESHOLD = 9391  # 93.91%

# Import deterministic helper to avoid floating point rounding issues
from utils import to_hundredths


def score_package(
    case_id: str,
    findings: list[Finding],
    target_path: str,
    has_lock_file: bool = False,
    has_python_version: bool = False,
    has_tests: bool = False,
) -> PreSimulationOutput:
    """Calculate information-completeness scores for all items.

    Each finding becomes a scoreable item. Clean files get implicit high scores.
    The overall package score determines whether the entire package qualifies,
    but individual items are scored and routed independently.

    Args:
        case_id: Case identifier for tracking.
        findings: Normalized findings from Phase 1.
        target_path: Path to the target project.
        has_lock_file: Whether the project has a lock file (poetry.lock, etc.)
        has_python_version: Whether Python version is declared.
        has_tests: Whether tests exist in the project.
    """
    target = Path(target_path)
    item_scores: list[ItemScore] = []
    qualified: list[str] = []
    isolated: list[str] = []
    unfixable: list[str] = []

    if not findings:
        # Clean project — everything qualifies
        return PreSimulationOutput(
            case_id=case_id,
            overall_information_score=98.5,
            threshold=93.91,
            simulation_ready=True,
            package_complete_for_one_shot=True,
            route_mode="full_simulation",
            qualified_items=["CLEAN-ALL"],
            isolated_items=[],
            unfixable_items=[],
            item_scores=[
                ItemScore(
                    item_id="CLEAN-ALL",
                    information_score=98.5,
                    information_complete=True,
                    known_information=["All checks passed", "No issues detected"],
                    route=ItemRoute.SIMULATION,
                    reason="All required checks completed and the package satisfies the admission threshold.",
                )
            ],
            pipeline_continues=True,
            decision_reason="All required checks completed and the package satisfies the admission threshold.",
        )

    # Score each finding as an item
    for finding in findings:
        score, known, missing, route, reason = _score_finding(
            finding, has_lock_file, has_python_version, has_tests
        )
        
        item = ItemScore(
            item_id=finding.finding_id,
            information_score=score,
            threshold=93.91,
            information_complete=(to_hundredths(score) >= PASS_THRESHOLD),
            known_information=known,
            missing_information=missing,
            route=route,
            reason=reason,
        )
        item_scores.append(item)

        if route == ItemRoute.SIMULATION:
            qualified.append(finding.finding_id)
        elif route == ItemRoute.UNFIXABLE:
            unfixable.append(finding.finding_id)
        else:
            isolated.append(finding.finding_id)

    # Overall score = average of item scores (weighted by severity)
    if item_scores:
        total_weight = 0.0
        weighted_sum = 0.0
        for item in item_scores:
            weight = 1.0
            weighted_sum += item.information_score * weight
            total_weight += weight
        overall = round(weighted_sum / total_weight, 2) if total_weight > 0 else 0.0
    else:
        overall = 98.5

    # Package-level simulation_ready = whether ALL items qualify
    # This is informational — does NOT override item-level routing
    # Good items continue independently even when package_complete_for_one_shot is False
    simulation_ready = len(isolated) == 0 and len(unfixable) == 0

    # Determine route mode
    if not qualified and not isolated:
        route_mode = "clean"
    elif qualified and not isolated:
        route_mode = "full_simulation"
    elif not qualified and isolated:
        route_mode = "full_isolation"
    else:
        route_mode = "split"

    # Decision reason
    if simulation_ready:
        decision_reason = (
            f"All items score at or above 93.91%. "
            f"Package qualifies for Simulation."
        )
    elif route_mode == "split":
        decision_reason = (
            f"Split routing: {len(qualified)} item(s) qualified for Simulation, "
            f"{len(isolated)} item(s) routed to Isolation. "
            f"Qualified items continue independently. Pipeline does not stop."
        )
    else:
        decision_reason = (
            f"{len(isolated)} item(s) below threshold — routed to Isolation. "
            f"Pipeline continues."
        )

    # Filter tool candidates for qualified items (feasibility mapping only)
    tool_candidates = filter_tool_candidates(qualified, findings, item_scores)

    # Generate Resolution Contracts via the Resolution Planner
    # The coding agent analyzes issues and produces contracts that specify
    # which tools to use, in what order, with what parameters.
    # No files are modified — contracts enter the same pipeline as deterministic candidates.
    from resolution_planner import plan_resolutions
    resolution_contracts = plan_resolutions(findings, target_path)

    # Merge AI-recommended tools into tool_candidates
    for contract in resolution_contracts:
        if contract.finding_id in qualified and contract.recommended_tools:
            existing = tool_candidates.get(contract.finding_id, [])
            ai_tools = [inv.tool_name for inv in contract.recommended_tools
                        if inv.tool_name not in existing]
            if ai_tools:
                tool_candidates[contract.finding_id] = existing + ai_tools

    return PreSimulationOutput(
        case_id=case_id,
        overall_information_score=overall,
        threshold=93.91,
        simulation_ready=simulation_ready,
        package_complete_for_one_shot=simulation_ready,
        route_mode=route_mode,
        qualified_items=qualified,
        isolated_items=isolated,
        unfixable_items=unfixable,
        item_scores=item_scores,
        pipeline_continues=True,  # Pipeline NEVER stops
        decision_reason=decision_reason,
        tool_candidates=tool_candidates,
    )


def _score_finding(
    finding: Finding,
    has_lock_file: bool,
    has_python_version: bool,
    has_tests: bool,
) -> tuple[float, list[str], list[str], str, str]:
    """Score a single finding for information completeness.

    Returns: (score, known_information, missing_information, route, reason)

    Scoring dimensions:
    - Root cause confirmed: +30
    - Affected file identified: +15
    - Supporting tool output: +15
    - Resolution path known: +25
    - Context available (lock file, python version): +15
    Base: 0
    Max: 100
    """
    score = 0.0
    known: list[str] = list(finding.known_facts)
    missing: list[str] = list(finding.missing_information)

    # Dimension 1: Root cause confirmed (30 points)
    if finding.root_cause_confirmed:
        score += 30.0
        known.append("Root cause confirmed")
    else:
        missing.append("Root cause not confirmed")

    # Dimension 2: Affected file identified (15 points)
    if finding.file and finding.file != "unknown":
        score += 15.0
        known.append(f"Affected file: {finding.file}")
    else:
        missing.append("Affected file not identified")

    # Dimension 3: Supporting tool output (15 points)
    if finding.supporting_tools:
        score += 15.0
        known.append(f"Tool evidence: {', '.join(finding.supporting_tools)}")
    else:
        missing.append("No supporting tool output")

    # Dimension 4: Resolution path known (25 points)
    # Confirmed root cause with no missing info = resolution is clear
    if finding.root_cause_confirmed and not finding.missing_information:
        score += 25.0
        known.append("Resolution path is clear")
    elif finding.root_cause_confirmed and finding.missing_information:
        # Root cause known but some context missing — partial
        score += 10.0
        missing.append("Resolution path partially known — context missing")
    else:
        missing.append("Resolution path unknown")

    # Dimension 5: Context completeness (15 points)
    # IMPORTANT: context is only required when it's needed for the fix.
    # A confirmed, fully-specified fix does NOT require a lock file to be "information complete."
    # Context items are bonus validation, not admission blockers.
    if finding.root_cause_confirmed and not finding.missing_information:
        # Fully specified fix — give full context score (info IS complete)
        score += 15.0
        known.append("Fix is fully specified — additional context is validation, not admission requirement")
    else:
        # Fix is NOT fully specified — context gaps become blockers
        context_score = 0.0
        if has_lock_file:
            context_score += 5.0
            known.append("Lock file available")
        else:
            if finding.category in (
                FindingCategory.DEPENDENCY_CONFLICT,
                FindingCategory.BROKEN_DEPENDENCY,
                FindingCategory.MISSING_DEPENDENCY,
            ):
                missing.append("No lock file — cannot verify transitive dependencies")

        if has_python_version:
            context_score += 5.0
            known.append("Python version declared")
        else:
            if finding.category in (
                FindingCategory.DEPENDENCY_CONFLICT,
                FindingCategory.BROKEN_DEPENDENCY,
            ):
                missing.append("Target Python version not declared")

        if has_tests:
            context_score += 5.0
            known.append("Tests available for validation")
        else:
            missing.append("No tests for validation")

        score += context_score

    # Cap at 100
    score = min(100.0, round(score, 2))

    # Determine route based on score
    score_hundredths = to_hundredths(score)
    if score_hundredths >= PASS_THRESHOLD:
        route = ItemRoute.SIMULATION
        reason = f"Information complete ({score}% >= 93.91%). Qualifies for Simulation."
    elif finding.category == FindingCategory.AMBIGUOUS_IMPORT and not finding.root_cause_confirmed:
        # Ambiguous with no confirmed root cause = might be unfixable
        if finding.confidence < 0.3:
            route = ItemRoute.ISOLATION
            reason = (
                f"Information incomplete ({score}% < 93.91%). "
                f"Root cause unconfirmed. Routed to Isolation for targeted research."
            )
        else:
            route = ItemRoute.ISOLATION
            reason = f"Information incomplete ({score}% < 93.91%). Routed to Isolation."
    else:
        route = ItemRoute.ISOLATION
        reason = f"Information incomplete ({score}% < 93.91%). Routed to Isolation."

    return score, known, missing, route, reason


def build_isolation_briefs(
    item_scores: list[ItemScore],
    findings: list[Finding],
) -> list[IsolationBrief]:
    """Generate focused isolation briefs for items below threshold.

    Each brief narrows the search — does not repeat broad analysis.
    """
    briefs: list[IsolationBrief] = []
    finding_map = {f.finding_id: f for f in findings}

    for item in item_scores:
        if item.route != ItemRoute.ISOLATION:
            continue

        finding = finding_map.get(item.item_id)
        if not finding:
            continue

        brief = IsolationBrief(
            item_id=item.item_id,
            reason_for_isolation=item.reason,
            known_facts=item.known_information,
            missing_information=item.missing_information,
            research_scope=_determine_research_scope(finding),
            what_was_tried=[
                f"Deterministic scan with {', '.join(finding.supporting_tools) or 'import-validation'}",
                "Repository file search",
                "Import graph analysis",
            ],
            next_action=_determine_next_action(finding),
            retry_condition=_determine_retry_condition(finding),
        )
        briefs.append(brief)

    return briefs


def _determine_research_scope(finding: Finding) -> list[str]:
    """Determine what targeted research should look for."""
    if finding.category == FindingCategory.AMBIGUOUS_IMPORT:
        return [
            "Project build scripts (Makefile, setup.py, pyproject.toml [build-system])",
            "README setup instructions",
            "Code-generation configuration (openapi-generator, protoc, etc.)",
            "CI/CD pipeline definitions",
            ".gitignore patterns for generated files",
        ]
    elif finding.category in (FindingCategory.DEPENDENCY_CONFLICT, FindingCategory.BROKEN_DEPENDENCY):
        return [
            "Lock files (poetry.lock, Pipfile.lock, requirements.lock)",
            "Python version constraints (pyproject.toml [python], .python-version)",
            "Deployment environment documentation",
            "CI/CD dependency installation commands",
        ]
    elif finding.category == FindingCategory.MISSING_DEPENDENCY:
        return [
            "Package index configuration (pip.conf, .pypirc)",
            "Private registry documentation",
            "Setup or installation scripts",
        ]
    return ["Project documentation", "Configuration files"]


def _determine_next_action(finding: Finding) -> str:
    """Determine the next action for an isolated item."""
    if finding.category == FindingCategory.AMBIGUOUS_IMPORT:
        return "Perform targeted research on module generation or installation workflow."
    elif finding.category in (FindingCategory.DEPENDENCY_CONFLICT, FindingCategory.BROKEN_DEPENDENCY):
        return "Identify target Python version and dependency resolution policy."
    return "Gather missing context to confirm resolution path."


def _determine_retry_condition(finding: Finding) -> str:
    """Determine when an isolated item can retry."""
    if finding.category == FindingCategory.AMBIGUOUS_IMPORT:
        return "Module source, generation command, or installation path identified."
    elif finding.category in (FindingCategory.DEPENDENCY_CONFLICT, FindingCategory.BROKEN_DEPENDENCY):
        return "Compatible version range confirmed with lock policy and Python version."
    return "Missing information provided and validated."


def filter_tool_candidates(
    qualified_items: list[str],
    findings: list[Finding],
    item_scores: list[ItemScore],
) -> dict[str, list[str]]:
    """Map each qualified issue to compatible tool names (feasibility filtering).

    This is a FILTERING ONLY function — no tool execution happens here.
    Called during Phase 3 (Pre-Simulation) to determine which tools
    can handle each qualified item. Phase 4 (Simulation) then executes them.

    Args:
        qualified_items: List of finding IDs that scored >= 93.91%
        findings: All findings from Phase 1
        item_scores: All item scores from Phase 2

    Returns:
        Mapping of item_id → list of tool names that can handle it.
        Items with no compatible tools are excluded from the mapping.
    """
    from toolkits.base import ToolContract
    from toolkits.refactor import RefactorTool
    from toolkits.dep_fix import DepFixTool
    from toolkits.import_repair import ImportRepairTool
    from toolkits.contract_align import ContractAlignTool
    from toolkits.test_repair import TestRepairTool

    # Registry of deterministic tools.
    # The coding agent is now a Resolution Planner (PreSimulation layer),
    # not an execution tool. It produces contracts, not mutations.
    tools: list[ToolContract] = [
        RefactorTool(),
        DepFixTool(),
        ImportRepairTool(),
        ContractAlignTool(),
        TestRepairTool(),
    ]

    # Build finding lookup
    finding_map = {f.finding_id: f for f in findings}

    # Filter: for each qualified item, find compatible tools
    candidates: dict[str, list[str]] = {}
    for item_id in qualified_items:
        finding = finding_map.get(item_id)
        if not finding:
            continue

        compatible = [tool.name for tool in tools if tool.can_handle(finding)]
        if compatible:
            candidates[item_id] = compatible

    return candidates
