# Modified: 2026-06-29T22:00:00Z
"""Phase 2: Analysis — produces statements and classification from raw scan.

Takes raw scan results from Phase 1 and produces:
- 2.1 LLM statement — call real LLM (Mistral) for advisory analysis
- 2.2 Handoff statement — structured schema of what gets handed off
- 2.3 Classification — structured dossier classifying each finding

This phase is pure analysis — no execution, no mutation, no scoring.
Reads: findings. Writes: analysis, flags. CANNOT mutate findings. Only DERIVES from them.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pipeline_state import PipelineState

import json
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase_models import PhaseResult, PHASE_NAMES
from phase_controller import PhaseController

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# API Configuration
# ──────────────────────────────────────────────

_MISTRAL_BASE_URL = "https://api.mistral.ai/v1"
_MISTRAL_MODEL = "mistral-small-latest"
_LLM_TIMEOUT = 15  # seconds


def _load_api_key() -> str:
    """Load Mistral API key from environment or .env file."""
    key = os.environ.get("Mistral_API_KEY", "")
    if key:
        return key

    # Try loading from .env files (repo root first, then _archive)
    for env_path in [
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent.parent / "_archive" / ".env",
    ]:
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("Mistral_API_KEY=") and not line.startswith("#"):
                        val = line.split("=", 1)[1].strip()
                        if val:
                            return val
            except OSError:
                continue

    return ""


# ──────────────────────────────────────────────
# LLM Call (with graceful fallback)
# ──────────────────────────────────────────────


def _call_llm(prompt: str) -> str | None:
    """Call Mistral LLM via OpenAI-compatible API. Returns response text or None on failure."""
    api_key = _load_api_key()
    if not api_key:
        logger.warning("No Mistral API key found — using fallback")
        return None

    # Strategy: try openai package first, then httpx, then urllib
    response = _try_openai_client(api_key, prompt)
    if response is not None:
        return response

    response = _try_httpx(api_key, prompt)
    if response is not None:
        return response

    response = _try_urllib(api_key, prompt)
    if response is not None:
        return response

    return None


def _try_openai_client(api_key: str, prompt: str) -> str | None:
    """Attempt LLM call using openai package."""
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(
            api_key=api_key,
            base_url=_MISTRAL_BASE_URL,
            timeout=_LLM_TIMEOUT,
        )
        completion = client.chat.completions.create(
            model=_MISTRAL_MODEL,
            messages=[
                {"role": "system", "content": "You are a senior software analysis advisor. Analyze scan findings and produce a concise advisory."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=512,
            temperature=0.3,
        )
        content = completion.choices[0].message.content
        if content:
            return content.strip()
        return None
    except ImportError:
        logger.debug("openai package not available")
        return None
    except Exception as e:
        logger.warning(f"openai client call failed: {e}")
        return None


def _try_httpx(api_key: str, prompt: str) -> str | None:
    """Attempt LLM call using httpx."""
    try:
        import httpx  # type: ignore

        payload = {
            "model": _MISTRAL_MODEL,
            "messages": [
                {"role": "system", "content": "You are a senior software analysis advisor. Analyze scan findings and produce a concise advisory."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 512,
            "temperature": 0.3,
        }
        resp = httpx.post(
            f"{_MISTRAL_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=_LLM_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        if content:
            return content.strip()
        return None
    except ImportError:
        logger.debug("httpx package not available")
        return None
    except Exception as e:
        logger.warning(f"httpx call failed: {e}")
        return None


def _try_urllib(api_key: str, prompt: str) -> str | None:
    """Attempt LLM call using stdlib urllib (last resort)."""
    try:
        import urllib.request
        import urllib.error

        payload = json.dumps({
            "model": _MISTRAL_MODEL,
            "messages": [
                {"role": "system", "content": "You are a senior software analysis advisor. Analyze scan findings and produce a concise advisory."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 512,
            "temperature": 0.3,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{_MISTRAL_BASE_URL}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_LLM_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            if content:
                return content.strip()
        return None
    except Exception as e:
        logger.warning(f"urllib call failed: {e}")
        return None


# ──────────────────────────────────────────────
# Phase 2 Entry Point
# ──────────────────────────────────────────────


def execute_phase_2_analysis(
    controller: PhaseController,
    snapshot: dict[str, Any],
    phase_1_outputs: dict[str, Any],
) -> PhaseResult:
    """Phase 2: Analysis — build statements and classification from raw scan.

    Sub-steps:
      2.1 LLM statement — advisory from real LLM call (Mistral)
      2.2 Handoff statement — structured schema output
      2.3 Classification — structured dossier for Phase 3

    Returns all 3 statements + classification_results.
    """
    controller.start_phase(2)
    start = datetime.now(timezone.utc)

    scan_results = phase_1_outputs.get("scan_results", [])

    # 2.1 LLM statement (real LLM call with fallback)
    llm_statement = _build_llm_statement(scan_results)

    # 2.2 Handoff statement (structured JSON schema)
    handoff_statement = _build_handoff_statement(scan_results)

    # 2.3 Classification
    classification_results = _classify_findings(scan_results)
    pre_calibration_statement = _build_precalibration_statement(scan_results)

    duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    result = PhaseResult(
        phase=2,
        phase_name=PHASE_NAMES[2],
        exit_status="completed",
        required_outputs={
            "llm_statement": llm_statement,
            "handoff_statement": handoff_statement,
            "pre_calibration_statement": pre_calibration_statement,
            "classification_results": classification_results,
            "total_issues": len(classification_results),
            "critical_count": sum(
                1 for i in classification_results if i.get("severity") == "critical"
            ),
            "high_count": sum(
                1 for i in classification_results if i.get("severity") == "high"
            ),
        },
        duration_ms=duration,
    )
    controller.complete_phase(result)
    return result


# ──────────────────────────────────────────────
# 2.1 LLM Statement
# ──────────────────────────────────────────────


def _build_llm_statement(scan_results: list[dict[str, Any]]) -> str:
    """Build LLM statement — call real LLM for advisory analysis.

    Sends scan_results as context, asks for analysis advisory.
    Falls back to deterministic string formatting if LLM call fails.
    """
    if not scan_results:
        return "LLM advisory: No issues detected. Project appears clean."

    # Build prompt from scan results
    prompt = _format_scan_results_for_llm(scan_results)

    # Attempt real LLM call
    llm_response = _call_llm(prompt)
    if llm_response:
        return f"LLM advisory (Mistral): {llm_response}"

    # Fallback: deterministic string formatting
    return _build_llm_fallback(scan_results)


def _format_scan_results_for_llm(scan_results: list[dict[str, Any]]) -> str:
    """Format scan results into a prompt for the LLM."""
    lines = [
        f"Analyze the following {len(scan_results)} scan finding(s) from a Python project.",
        "Provide a concise advisory covering: key risks, root cause patterns, and recommended priorities.",
        "",
        "Findings:",
    ]
    for i, finding in enumerate(scan_results[:20], 1):  # Cap at 20 for token budget
        severity = finding.get("severity", "unknown")
        category = finding.get("category", "unknown")
        root_cause = finding.get("root_cause", "N/A")
        file = finding.get("file", "unknown")
        confirmed = finding.get("root_cause_confirmed", False)
        lines.append(
            f"  {i}. [{severity}] {category} in {file} — "
            f"root_cause: {root_cause} (confirmed={confirmed})"
        )
    return "\n".join(lines)


def _build_llm_fallback(scan_results: list[dict[str, Any]]) -> str:
    """Deterministic fallback when LLM is unavailable."""
    categories: dict[str, int] = {}
    severities: dict[str, int] = {}
    for finding in scan_results:
        cat = finding.get("category", "unknown")
        sev = finding.get("severity", "unknown")
        categories[cat] = categories.get(cat, 0) + 1
        severities[sev] = severities.get(sev, 0) + 1

    parts = [f"LLM advisory (fallback): {len(scan_results)} issue(s) detected."]
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        parts.append(f"  - {cat}: {count}")

    sev_parts = [f"{sev}={count}" for sev, count in sorted(severities.items())]
    parts.append(f"  Severity breakdown: {', '.join(sev_parts)}")

    avg_confidence = sum(
        f.get("confidence", 0.0) for f in scan_results
    ) / len(scan_results)
    parts.append(f"  Average confidence: {avg_confidence:.2f}")

    confirmed_count = sum(1 for f in scan_results if f.get("root_cause_confirmed"))
    parts.append(f"  Root causes confirmed: {confirmed_count}/{len(scan_results)}")

    return "\n".join(parts)


# ──────────────────────────────────────────────
# 2.2 Handoff Statement (structured JSON schema)
# ──────────────────────────────────────────────


def _build_handoff_statement(scan_results: list[dict[str, Any]]) -> str:
    """Build handoff statement — structured JSON schema of what gets handed off.

    Returns a JSON-serialized dict with:
    - total_issues, files_affected, tools_used
    - root_causes_confirmed vs unconfirmed
    - items_requiring_additional_information
    """
    if not scan_results:
        return json.dumps({
            "total_issues": 0,
            "files_affected": [],
            "tools_used": [],
            "root_causes_confirmed": 0,
            "root_causes_unconfirmed": 0,
            "items_requiring_additional_information": [],
            "handoff_ready": True,
        }, indent=2)

    files_affected: set[str] = set()
    tools_used: set[str] = set()
    confirmed = 0
    unconfirmed = 0
    items_needing_info: list[dict[str, Any]] = []

    for finding in scan_results:
        # Files
        file_str = finding.get("file", "")
        if file_str:
            primary = file_str.split(" (+")[0] if " (+" in file_str else file_str
            files_affected.add(primary)

        # Tools
        for tool in finding.get("supporting_tools", []):
            tools_used.add(tool)

        # Root cause status
        if finding.get("root_cause_confirmed", False):
            confirmed += 1
        else:
            unconfirmed += 1

        # Missing information
        missing = finding.get("missing_information", [])
        if missing:
            items_needing_info.append({
                "finding_id": finding.get("finding_id", ""),
                "category": finding.get("category", ""),
                "missing": missing,
            })

    schema = {
        "total_issues": len(scan_results),
        "files_affected": sorted(files_affected),
        "tools_used": sorted(tools_used),
        "root_causes_confirmed": confirmed,
        "root_causes_unconfirmed": unconfirmed,
        "items_requiring_additional_information": items_needing_info,
        "handoff_ready": True,
    }

    return json.dumps(schema, indent=2)


# ──────────────────────────────────────────────
# 2.3 Classification + Pre-calibration
# ──────────────────────────────────────────────


def _classify_findings(scan_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Classify raw findings into structured dossier items for Phase 3.

    Each item contains: id, type, severity, description, file, category,
    confidence, root_cause_confirmed, missing_information.
    """
    classification_results: list[dict[str, Any]] = []

    for finding in scan_results:
        finding_id = finding.get("finding_id", f"item-{len(classification_results)}")
        category = finding.get("category", "unknown")

        classification_results.append({
            "id": finding_id,
            "type": _map_category_to_type(category),
            "severity": finding.get("severity", "medium"),
            "description": finding.get("root_cause", "") or (
                f"[{category}] in {finding.get('file', 'unknown')}"
            ),
            "file": finding.get("file", ""),
            "category": category,
            "confidence": finding.get("confidence", 0.0),
            "root_cause_confirmed": finding.get("root_cause_confirmed", False),
            "missing_information": finding.get("missing_information", []),
        })

    return classification_results


def _build_precalibration_statement(scan_results: list[dict[str, Any]]) -> str:
    """Build pre-calibration statement — scan baseline with real data.

    Establishes the calibration baseline before scoring in Phase 3.
    """
    if not scan_results:
        return "Pre-calibration: Clean project. No findings to calibrate against."

    total = len(scan_results)
    categories: dict[str, int] = {}
    for f in scan_results:
        cat = f.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    high_confidence = sum(1 for f in scan_results if f.get("confidence", 0) >= 0.9)
    low_confidence = sum(1 for f in scan_results if f.get("confidence", 0) < 0.5)

    parts = [
        f"Pre-calibration: {total} findings baseline.",
        f"  Categories: {', '.join(f'{cat}({count})' for cat, count in sorted(categories.items()))}.",
        f"  High confidence (>=0.9): {high_confidence}. Low confidence (<0.5): {low_confidence}.",
    ]

    return "\n".join(parts)


def _map_category_to_type(category: str) -> str:
    """Map FindingCategory values to the type field Phase 3 expects."""
    type_map = {
        "dependency_conflict": "dependency",
        "missing_dependency": "dependency",
        "broken_dependency": "dependency",
        "missing_import": "code_quality",
        "ambiguous_import": "code_quality",
        "syntax_error": "code_quality",
        "circular_import": "code_quality",
        "undefined_reference": "code_quality",
        "test_failure": "test",
        "configuration_missing": "configuration",
    }
    return type_map.get(category, "unknown")


# ──────────────────────────────────────────────
# State Algebra Transform
# ──────────────────────────────────────────────


def transform_phase_2(state: "PipelineState", controller: PhaseController) -> "PipelineState":
    """Phase 2 pure transformation: Reads findings. Writes analysis, flags.

    CANNOT mutate findings. Only DERIVES from them.
    Produces: handoff_statement, llm_statement, pre_calibration_statement, classification_dossier.
    """
    from pipeline_state import PipelineState

    state.validate_transition(2)
    controller.start_phase(2)

    scan_results = state.findings

    llm_statement = _build_llm_statement(scan_results)
    handoff_statement = _build_handoff_statement(scan_results)
    classification_results = _classify_findings(scan_results)
    pre_calibration_statement = _build_precalibration_statement(scan_results)

    state.analysis = {
        "llm_statement": llm_statement,
        "handoff_statement": handoff_statement,
        "pre_calibration_statement": pre_calibration_statement,
        "classification_dossier": classification_results,
        "classification_results": classification_results,
        "total_issues": len(classification_results),
        "critical_count": sum(
            1 for i in classification_results if i.get("severity") == "critical"
        ),
        "high_count": sum(
            1 for i in classification_results if i.get("severity") == "high"
        ),
    }
    state.flags.analysis_complete = True

    result = PhaseResult(
        phase=2,
        phase_name=PHASE_NAMES[2],
        exit_status="completed",
        required_outputs={
            "llm_statement": llm_statement,
            "handoff_statement": handoff_statement,
            "pre_calibration_statement": pre_calibration_statement,
            "classification_results": classification_results,
            "total_issues": len(classification_results),
            "critical_count": state.analysis["critical_count"],
            "high_count": state.analysis["high_count"],
        },
        duration_ms=0,
    )
    controller.complete_phase(result)
    return state
