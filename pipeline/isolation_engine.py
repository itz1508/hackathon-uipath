"""Isolation Engine — bounded research workflow for isolated items.

NOT a pipeline phase. An internal execution loop owned by Pre-simulation.
Receives isolated items, executes research providers, collects evidence,
and rebuilds the package for re-scoring.

The engine itself does not know how evidence is collected.
It only orchestrates research via pluggable providers.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


# ──────────────────────────────────────────────
# Research Providers
# ──────────────────────────────────────────────

def _filesystem_search(module_name: str, target_path: str) -> dict[str, Any]:
    """Search local filesystem for the module (file or package directory)."""
    target = Path(target_path)
    if not target.exists():
        return {"found": False, "source": "filesystem_search", "detail": "target path does not exist"}

    # Check for module_name.py
    py_file = target / f"{module_name}.py"
    if py_file.exists():
        return {"found": True, "source": "filesystem_search", "detail": f"Found {module_name}.py", "path": str(py_file)}

    # Check for package directory (module_name/__init__.py)
    pkg_dir = target / module_name
    if pkg_dir.is_dir() and (pkg_dir / "__init__.py").exists():
        return {"found": True, "source": "filesystem_search", "detail": f"Found package {module_name}/", "path": str(pkg_dir)}

    # Check for any file containing the module name (case-insensitive)
    for f in target.rglob("*.py"):
        if f.stem.lower() == module_name.lower() and f.stem != module_name:
            return {"found": True, "source": "filesystem_search", "detail": f"Found similar: {f.name}", "path": str(f)}

    return {"found": False, "source": "filesystem_search", "detail": f"No file or package matching '{module_name}'"}


def _requirements_analysis(module_name: str, target_path: str) -> dict[str, Any]:
    """Check requirements.txt / pyproject.toml for declaration of the module."""
    target = Path(target_path)

    # Check requirements.txt
    req_file = target / "requirements.txt"
    if req_file.exists():
        content = req_file.read_text(encoding="utf-8", errors="ignore").lower()
        # Normalize: replace - with _ for comparison
        normalized_name = module_name.lower().replace("-", "_")
        for line in content.splitlines():
            line_stripped = line.strip().lower().replace("-", "_")
            if line_stripped.startswith(normalized_name):
                return {"found": True, "source": "requirements_analysis", "detail": f"Declared in requirements.txt"}

    # Check pyproject.toml
    pyproject = target / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8", errors="ignore").lower()
        normalized_name = module_name.lower().replace("-", "_")
        if normalized_name in content:
            return {"found": True, "source": "requirements_analysis", "detail": "Referenced in pyproject.toml"}

    return {"found": False, "source": "requirements_analysis", "detail": "Not declared in any manifest"}


def _ast_analysis(module_name: str, target_path: str) -> dict[str, Any]:
    """Parse imports across the project to find where module should come from."""
    import ast

    target = Path(target_path)
    importing_files: list[str] = []

    for py_file in target.rglob("*.py"):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] == module_name:
                        importing_files.append(str(py_file.relative_to(target)))
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] == module_name:
                    importing_files.append(str(py_file.relative_to(target)))

    if importing_files:
        return {
            "found": True,
            "source": "ast_analysis",
            "detail": f"Imported in {len(importing_files)} file(s)",
            "importing_files": importing_files[:10],
        }
    return {"found": False, "source": "ast_analysis", "detail": "Not imported anywhere"}


def _package_metadata(module_name: str, target_path: str) -> dict[str, Any]:
    """Check if module name maps to a known PyPI package pattern."""
    # Common patterns that indicate internal/generated modules
    internal_patterns = [
        r"^generated_",
        r"^internal_",
        r"^private_",
        r"_client$",
        r"_provider$",
        r"_connector$",
        r"_sdk$",
        r"^company_",
        r"^org_",
    ]

    for pattern in internal_patterns:
        if re.search(pattern, module_name):
            return {
                "found": True,
                "source": "package_metadata",
                "detail": f"Module name matches internal pattern: {pattern}",
                "likely_internal": True,
            }

    # Common PyPI package names that differ from import name
    KNOWN_PYPI_MAPPINGS: dict[str, str] = {
        "PIL": "Pillow",
        "cv2": "opencv-python",
        "sklearn": "scikit-learn",
        "yaml": "PyYAML",
        "bs4": "beautifulsoup4",
        "attr": "attrs",
        "dateutil": "python-dateutil",
        "dotenv": "python-dotenv",
        "jwt": "PyJWT",
        "celery": "celery",
        "redis": "redis",
        "pandas": "pandas",
        "numpy": "numpy",
        "matplotlib": "matplotlib",
    }

    if module_name in KNOWN_PYPI_MAPPINGS:
        return {
            "found": True,
            "source": "package_metadata",
            "detail": f"Maps to PyPI package: {KNOWN_PYPI_MAPPINGS[module_name]}",
            "pypi_package": KNOWN_PYPI_MAPPINGS[module_name],
        }

    return {"found": False, "source": "package_metadata", "detail": "No known PyPI mapping"}


def _documentation_lookup(module_name: str, target_path: str) -> dict[str, Any]:
    """Check if README/docs mention the module."""
    target = Path(target_path)

    doc_files = ["README.md", "README.rst", "README.txt", "docs/index.md", "DEFECT.md"]
    for doc_name in doc_files:
        doc_path = target / doc_name
        if doc_path.exists():
            content = doc_path.read_text(encoding="utf-8", errors="ignore")
            if module_name in content:
                return {
                    "found": True,
                    "source": "documentation_lookup",
                    "detail": f"Referenced in {doc_name}",
                }

    return {"found": False, "source": "documentation_lookup", "detail": "Not mentioned in documentation"}


# ──────────────────────────────────────────────
# Provider Registry
# ──────────────────────────────────────────────

RESEARCH_PROVIDERS = {
    "filesystem_search": _filesystem_search,
    "requirements_analysis": _requirements_analysis,
    "ast_analysis": _ast_analysis,
    "package_metadata": _package_metadata,
    "documentation_lookup": _documentation_lookup,
}

# Category -> which providers are applicable
CATEGORY_PROVIDERS: dict[str, list[str]] = {
    "missing_import": ["filesystem_search", "requirements_analysis", "ast_analysis", "package_metadata", "documentation_lookup"],
    "missing_dependency": ["requirements_analysis", "package_metadata", "documentation_lookup"],
    "dependency_conflict": ["requirements_analysis", "package_metadata"],
    "broken_dependency": ["requirements_analysis", "package_metadata"],
    "ambiguous_import": ["filesystem_search", "requirements_analysis", "ast_analysis", "package_metadata", "documentation_lookup"],
    "configuration_missing": ["filesystem_search", "documentation_lookup"],
}


# ──────────────────────────────────────────────
# Isolation Research for AMBIGUOUS_IMPORT
# ──────────────────────────────────────────────

def _research_ambiguous_import(item: dict[str, Any], target_path: str) -> dict[str, Any]:
    """Research provider for AMBIGUOUS_IMPORT category.

    - Search target_path for files matching the module name
    - Check if a .py file or package directory exists
    - Check if the module is referenced in any config file
    - If found → confidence=0.95, root_cause_confirmed=True
    - If not found but name matches known PyPI package → confidence=0.85
    - If nothing → stays isolated
    """
    # Extract module name from item
    description = item.get("description", "")
    module_name = _extract_module_name(item, target_path)

    if not module_name:
        return {
            "evidence_collected": False,
            "evidence_source": "none",
            "confidence_delta": 0.0,
            "root_cause_confirmed": False,
            "resolution": "still_isolated",
        }

    # Search filesystem
    fs_result = _filesystem_search(module_name, target_path)
    if fs_result["found"]:
        return {
            "evidence_collected": True,
            "evidence_source": "filesystem_search",
            "confidence_delta": 0.25,
            "root_cause_confirmed": True,
            "resolution": "ready_for_simulation",
            "detail": fs_result["detail"],
        }

    # Check requirements
    req_result = _requirements_analysis(module_name, target_path)
    if req_result["found"]:
        return {
            "evidence_collected": True,
            "evidence_source": "requirements_analysis",
            "confidence_delta": 0.20,
            "root_cause_confirmed": True,
            "resolution": "ready_for_simulation",
            "detail": req_result["detail"],
        }

    # Check PyPI mapping
    pkg_result = _package_metadata(module_name, target_path)
    if pkg_result["found"]:
        confidence_delta = 0.15 if pkg_result.get("likely_internal") else 0.10
        return {
            "evidence_collected": True,
            "evidence_source": "package_metadata",
            "confidence_delta": confidence_delta,
            "root_cause_confirmed": pkg_result.get("likely_internal", False),
            "resolution": "ready_for_simulation" if pkg_result.get("likely_internal") else "still_isolated",
            "detail": pkg_result["detail"],
        }

    return {
        "evidence_collected": False,
        "evidence_source": "none",
        "confidence_delta": 0.0,
        "root_cause_confirmed": False,
        "resolution": "still_isolated",
    }


# ──────────────────────────────────────────────
# Isolation Research for DEPENDENCY_CONFLICT
# ──────────────────────────────────────────────

def _research_dependency_conflict(item: dict[str, Any], target_path: str) -> dict[str, Any]:
    """Research provider for DEPENDENCY_CONFLICT with missing_information.

    - Check if a lock file exists
    - Check if pyproject.toml has the dependency
    - Check .python-version
    - If lock file found → missing_info cleared, confidence increased
    - If python version found → missing_info cleared
    """
    target = Path(target_path)
    missing_info = item.get("missing_information", [])

    evidence_found = False
    cleared_info: list[str] = []
    confidence_delta = 0.0

    # Check lock file
    lock_files = ["poetry.lock", "Pipfile.lock", "requirements.lock", "pdm.lock"]
    for lf in lock_files:
        if (target / lf).exists():
            evidence_found = True
            cleared_info.append("lock_file_found")
            confidence_delta += 0.15
            break

    # Check python version declaration
    pyver_files = [".python-version", "runtime.txt"]
    for pvf in pyver_files:
        if (target / pvf).exists():
            evidence_found = True
            cleared_info.append("python_version_found")
            confidence_delta += 0.10
            break

    # Check pyproject.toml for python version
    pyproject = target / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8", errors="ignore")
        if "requires-python" in content or "python_requires" in content:
            evidence_found = True
            if "python_version_found" not in cleared_info:
                cleared_info.append("python_version_in_pyproject")
                confidence_delta += 0.10

    # Determine remaining missing info
    remaining = [m for m in missing_info if not any(c in m.lower() for c in ["lock", "python version"])]

    if evidence_found:
        return {
            "evidence_collected": True,
            "evidence_source": "dependency_conflict_research",
            "confidence_delta": confidence_delta,
            "root_cause_confirmed": len(remaining) == 0,
            "resolution": "ready_for_simulation" if len(remaining) == 0 else "still_isolated",
            "cleared_info": cleared_info,
            "remaining_missing": remaining,
        }

    return {
        "evidence_collected": False,
        "evidence_source": "none",
        "confidence_delta": 0.0,
        "root_cause_confirmed": False,
        "resolution": "still_isolated",
    }


# ──────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────

def _extract_module_name(item: dict[str, Any], target_path: str = "") -> str:
    """Extract module name from an isolated item.
    
    Strategies (in order):
    1. Check affected_component field directly
    2. Parse description for module name patterns
    3. Read the source file and find unresolved imports via AST
    """
    # 1. Direct affected_component
    affected = item.get("affected_component", "")
    if affected:
        return affected.split(".")[0]

    description = item.get("description", "")

    # 2. Try patterns like "Module 'X' ...", "'X' imported..."
    match = re.search(r"[Mm]odule '([^']+)'", description)
    if match:
        return match.group(1).split(".")[0]

    match = re.search(r"'([^']+)'\s+(?:imported|does not)", description)
    if match:
        return match.group(1).split(".")[0]

    # 3. Read source file and find imports that don't resolve locally
    file_path = item.get("file", "")
    if file_path and target_path:
        module_name = _extract_module_from_source(file_path, target_path)
        if module_name:
            return module_name

    return ""


def _extract_module_from_source(file_path: str, target_path: str) -> str:
    """Read a source file and find imports that don't resolve locally."""
    import ast as _ast

    target = Path(target_path)
    source_file = target / file_path

    if not source_file.exists():
        return ""

    try:
        source = source_file.read_text(encoding="utf-8")
        tree = _ast.parse(source, filename=str(source_file))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return ""

    # Collect local module names
    local_modules: set[str] = set()
    for f in target.rglob("*.py"):
        local_modules.add(f.stem)
    for d in target.iterdir():
        if d.is_dir() and (d / "__init__.py").exists():
            local_modules.add(d.name)

    # Known stdlib (subset for quick check)
    from scanner import STDLIB_MODULES

    # Find first import that doesn't resolve
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in local_modules and top.lower() not in STDLIB_MODULES:
                    return top
        elif isinstance(node, _ast.ImportFrom):
            if node.module and node.level == 0:
                top = node.module.split(".")[0]
                if top not in local_modules and top.lower() not in STDLIB_MODULES:
                    return top

    return ""


def _run_research_for_item(item: dict[str, Any], target_path: str) -> dict[str, Any]:
    """Run the appropriate research strategy for an isolated item."""
    category = item.get("category", "")
    isolation_reason = item.get("isolation_reason", "")

    # Route to category-specific research
    if category == "missing_import" or "ambiguous" in isolation_reason.lower():
        return _research_ambiguous_import(item, target_path)
    elif category == "dependency_conflict" and item.get("missing_information"):
        return _research_dependency_conflict(item, target_path)
    elif category == "missing_dependency":
        return _research_ambiguous_import(item, target_path)
    elif category == "broken_dependency":
        # For broken dependencies, check if valid version exists in requirements
        return _research_dependency_conflict(item, target_path)
    else:
        # Generic research: try all providers
        module_name = _extract_module_name(item, target_path)
        if module_name:
            return _research_ambiguous_import(item, target_path)
        return {
            "evidence_collected": False,
            "evidence_source": "none",
            "confidence_delta": 0.0,
            "root_cause_confirmed": False,
            "resolution": "still_isolated",
        }


# ──────────────────────────────────────────────
# Main Entry Point
# ──────────────────────────────────────────────

def run_isolation_engine(
    isolated_items: list[dict],
    classification_results: list[dict],
    target_path: str,
    enabled: bool = True,
) -> dict:
    """Execute isolation research for all isolated items.

    If enabled=False, returns immediately with no changes (Run A behavior).
    If enabled=True, executes research for each item (Run B behavior).

    Returns:
        {
            "executed": bool,
            "items_processed": int,
            "items_resolved": int,
            "items_remaining": int,
            "resolution_records": list[dict],
            "rebuilt_classification": list[dict],  # updated classification with new confidence
        }
    """
    if not enabled:
        return {
            "executed": False,
            "items_processed": 0,
            "items_resolved": 0,
            "items_remaining": len(isolated_items),
            "resolution_records": [],
            "rebuilt_classification": classification_results,
        }

    if not isolated_items:
        return {
            "executed": True,
            "items_processed": 0,
            "items_resolved": 0,
            "items_remaining": 0,
            "resolution_records": [],
            "rebuilt_classification": classification_results,
        }

    resolution_records: list[dict] = []
    items_resolved = 0
    items_remaining = 0

    # Build classification lookup for confidence updates
    classification_map: dict[str, dict] = {}
    for item in classification_results:
        item_id = item.get("id", "")
        if item_id:
            classification_map[item_id] = item

    for isolated_item in isolated_items:
        item_id = isolated_item.get("item_id", "")
        confidence_before = classification_map.get(item_id, {}).get("confidence", 0.7)

        # Run research
        research_result = _run_research_for_item(isolated_item, target_path)

        confidence_after = min(1.0, confidence_before + research_result.get("confidence_delta", 0.0))
        root_cause_confirmed = research_result.get("root_cause_confirmed", False)
        resolution = research_result.get("resolution", "still_isolated")

        # Determine retry recommendation
        if resolution == "ready_for_simulation":
            retry_recommendation = "ready_for_simulation"
            items_resolved += 1
        elif confidence_after >= 0.9 and root_cause_confirmed:
            retry_recommendation = "ready_for_simulation"
            items_resolved += 1
        elif confidence_after < 0.5:
            retry_recommendation = "unfixable"
            items_remaining += 1
        else:
            retry_recommendation = "still_isolated"
            items_remaining += 1

        # Determine remaining missing information
        remaining_missing = research_result.get("remaining_missing", [])
        if not root_cause_confirmed and not remaining_missing:
            remaining_missing = ["root cause not confirmed by evidence"]

        record = {
            "item_id": item_id,
            "evidence_collected": research_result.get("evidence_collected", False),
            "evidence_source": research_result.get("evidence_source", "none"),
            "confidence_before": confidence_before,
            "confidence_after": confidence_after,
            "root_cause_confirmed": root_cause_confirmed,
            "remaining_missing_information": remaining_missing,
            "retry_recommendation": retry_recommendation,
        }
        resolution_records.append(record)

        # Update classification with new confidence
        if item_id in classification_map:
            classification_map[item_id]["confidence"] = confidence_after
            if root_cause_confirmed:
                classification_map[item_id]["root_cause_confirmed"] = True
                # When ambiguous_import is confirmed, reclassify to missing_dependency
                # (now we know what it is, it can be fixed by adding to deps)
                if classification_map[item_id].get("category") == "ambiguous_import":
                    classification_map[item_id]["category"] = "missing_dependency"
            # Clear missing_information if evidence resolved it
            if research_result.get("cleared_info"):
                existing_missing = classification_map[item_id].get("missing_information", [])
                cleared = research_result["cleared_info"]
                classification_map[item_id]["missing_information"] = [
                    m for m in existing_missing
                    if not any(c in m.lower() for c in [x.replace("_", " ") for x in cleared])
                ]
            # Clear missing_information when root cause is confirmed for ambiguous imports
            if root_cause_confirmed and classification_map[item_id].get("category") in ("missing_dependency", "ambiguous_import"):
                classification_map[item_id]["missing_information"] = []

    # Rebuild classification list preserving order
    rebuilt_classification = []
    for item in classification_results:
        item_id = item.get("id", "")
        if item_id in classification_map:
            rebuilt_classification.append(classification_map[item_id])
        else:
            rebuilt_classification.append(item)

    return {
        "executed": True,
        "items_processed": len(isolated_items),
        "items_resolved": items_resolved,
        "items_remaining": items_remaining,
        "resolution_records": resolution_records,
        "rebuilt_classification": rebuilt_classification,
    }
