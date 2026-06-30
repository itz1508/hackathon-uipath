# Modified: 2026-06-23T22:16:00Z
"""DepFixTool — dependency version conflict resolution for the toolkit system.

Inputs:
    - Finding with category in {DEPENDENCY_CONFLICT, MISSING_DEPENDENCY, BROKEN_DEPENDENCY}
    - sandbox_path: root of the isolated sandbox copy containing requirements files
    - context: runtime metadata dict (case_id, snapshot_id, etc.)

Outputs:
    - ToolResult with mutations applied, confidence score, and validation status
    - mutations list contains dicts with keys: file, operation, before, after

Side-effects:
    - Modifies dependency files ONLY within sandbox_path (requirements.txt, setup.cfg, pyproject.toml)
    - No network calls, no state outside sandbox boundary

Errors:
    - Returns ToolResult(success=False, error=...) if no requirements file found or fix cannot be applied
    - Never raises unhandled exceptions
"""
from __future__ import annotations

import re
from pathlib import Path

from models import Finding, FindingCategory
from toolkits.base import ToolContract, ToolResult


# Requirement file names to search for (priority order)
_REQUIREMENTS_FILES = ("requirements.txt", "setup.cfg", "pyproject.toml")


class DepFixTool(ToolContract):
    """Handles dependency version conflicts, missing dependencies, and broken dependencies.

    Covers:
      - DEPENDENCY_CONFLICT: extracts pinned version from known_facts, computes compatible
        version, and updates the pin in the requirements file.
      - MISSING_DEPENDENCY: adds the missing package to the requirements file.
      - BROKEN_DEPENDENCY: updates the broken version to a compatible one.
    """

    _APPLICABLE: frozenset[str] = frozenset({
        FindingCategory.DEPENDENCY_CONFLICT.value,
        FindingCategory.MISSING_DEPENDENCY.value,
        FindingCategory.BROKEN_DEPENDENCY.value,
    })

    @property
    def name(self) -> str:
        return "dep_fix"

    @property
    def description(self) -> str:
        return "Dependency version conflict resolution, missing dependency addition, and broken dependency repair"

    @property
    def applicable_categories(self) -> frozenset[str]:
        return self._APPLICABLE

    def can_handle(self, finding: Finding) -> bool:
        """Return True if finding is a dependency issue with confirmed root cause."""
        return (
            finding.category in self._APPLICABLE
            and finding.root_cause_confirmed is True
        )

    def execute(self, sandbox_path: str, finding: Finding, context: dict) -> ToolResult:
        """Execute a dependency fix against the finding within the sandbox.

        Dispatches to the appropriate fix strategy based on finding category.
        """
        item_id = finding.finding_id
        sandbox = Path(sandbox_path)

        # Locate requirements file in the sandbox
        req_file = self._find_requirements_file(sandbox)
        if req_file is None:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="No requirements file found in sandbox (requirements.txt, setup.cfg, pyproject.toml)",
            )

        try:
            original_content = req_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error=f"Cannot read requirements file: {exc}",
            )

        rel_path = str(req_file.relative_to(sandbox))
        category = finding.category

        if category == FindingCategory.DEPENDENCY_CONFLICT.value:
            return self._fix_dependency_conflict(req_file, rel_path, original_content, finding)
        elif category == FindingCategory.MISSING_DEPENDENCY.value:
            return self._fix_missing_dependency(req_file, rel_path, original_content, finding)
        elif category == FindingCategory.BROKEN_DEPENDENCY.value:
            return self._fix_broken_dependency(req_file, rel_path, original_content, finding)
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

    # ─── Strategy: DEPENDENCY_CONFLICT ─────────────────────────────────────

    def _fix_dependency_conflict(
        self, req_file: Path, rel_path: str, content: str, finding: Finding
    ) -> ToolResult:
        """Resolve a version conflict by updating the pinned version to a compatible one."""
        item_id = finding.finding_id
        package_name = self._extract_package_name(finding)
        if not package_name:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Cannot determine package name from finding",
            )

        # Extract target version from known_facts
        target_version = self._extract_target_version(finding)
        if not target_version:
            # Fall back: bump the minor of the current pinned version
            current_version = self._find_current_version(content, package_name)
            if current_version:
                target_version = self._compute_compatible_version(current_version)
            else:
                return ToolResult(
                    tool_name=self.name,
                    item_id=item_id,
                    success=False,
                    mutations=[],
                    confidence=0.0,
                    validation_passed=False,
                    error=f"Cannot determine target version for '{package_name}'",
                )

        # Replace the existing pin with the target version
        new_content, replaced = self._replace_version_pin(content, package_name, target_version)
        if not replaced:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error=f"Package '{package_name}' not found in {rel_path}",
            )

        req_file.write_text(new_content, encoding="utf-8")
        return ToolResult(
            tool_name=self.name,
            item_id=item_id,
            success=True,
            mutations=[{
                "file": rel_path,
                "operation": "replace",
                "before": f"{package_name} (conflicting version)",
                "after": f"{package_name}=={target_version}",
            }],
            confidence=0.85,
            validation_passed=False,
            files_modified=[rel_path],
        )

    # ─── Strategy: MISSING_DEPENDENCY ──────────────────────────────────────

    def _fix_missing_dependency(
        self, req_file: Path, rel_path: str, content: str, finding: Finding
    ) -> ToolResult:
        """Add a missing package to the requirements file."""
        item_id = finding.finding_id
        package_name = self._extract_package_name(finding)
        if not package_name:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Cannot determine missing package name from finding",
            )

        # Check if package is already present (case-insensitive)
        if self._package_exists_in_content(content, package_name):
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error=f"Package '{package_name}' already present in {rel_path}",
            )

        # Extract version hint from known_facts if available
        version = self._extract_target_version(finding)
        if version:
            new_entry = f"{package_name}=={version}"
        else:
            new_entry = package_name

        # Append to requirements file
        new_content = content.rstrip("\n") + "\n" + new_entry + "\n"
        req_file.write_text(new_content, encoding="utf-8")

        return ToolResult(
            tool_name=self.name,
            item_id=item_id,
            success=True,
            mutations=[{
                "file": rel_path,
                "operation": "replace",
                "before": "(package not present)",
                "after": new_entry,
            }],
            confidence=0.90,
            validation_passed=False,
            files_modified=[rel_path],
        )

    # ─── Strategy: BROKEN_DEPENDENCY ───────────────────────────────────────

    def _fix_broken_dependency(
        self, req_file: Path, rel_path: str, content: str, finding: Finding
    ) -> ToolResult:
        """Update a broken dependency version to a compatible one."""
        item_id = finding.finding_id
        package_name = self._extract_package_name(finding)
        if not package_name:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error="Cannot determine broken package name from finding",
            )

        # Extract target version from known_facts or compute from current
        target_version = self._extract_target_version(finding)
        if not target_version:
            current_version = self._find_current_version(content, package_name)
            if current_version:
                target_version = self._compute_compatible_version(current_version)
            else:
                # Package exists without version pin — add a version
                target_version = self._extract_version_hint_from_facts(finding)
                if not target_version:
                    return ToolResult(
                        tool_name=self.name,
                        item_id=item_id,
                        success=False,
                        mutations=[],
                        confidence=0.0,
                        validation_passed=False,
                        error=f"Cannot determine compatible version for '{package_name}'",
                    )

        # Replace existing entry or add version pin
        new_content, replaced = self._replace_version_pin(content, package_name, target_version)
        if not replaced:
            # Package line exists without version specifier — add pin
            new_content, replaced = self._add_version_to_existing(content, package_name, target_version)

        if not replaced:
            return ToolResult(
                tool_name=self.name,
                item_id=item_id,
                success=False,
                mutations=[],
                confidence=0.0,
                validation_passed=False,
                error=f"Package '{package_name}' not found in {rel_path}",
            )

        req_file.write_text(new_content, encoding="utf-8")
        return ToolResult(
            tool_name=self.name,
            item_id=item_id,
            success=True,
            mutations=[{
                "file": rel_path,
                "operation": "replace",
                "before": f"{package_name} (broken version)",
                "after": f"{package_name}=={target_version}",
            }],
            confidence=0.80,
            validation_passed=False,
            files_modified=[rel_path],
        )

    # ─── Helper Methods ────────────────────────────────────────────────────

    def _find_requirements_file(self, sandbox: Path) -> Path | None:
        """Search for a requirements file in the sandbox (priority order)."""
        for filename in _REQUIREMENTS_FILES:
            candidate = sandbox / filename
            if candidate.exists():
                return candidate
        return None

    def _extract_package_name(self, finding: Finding) -> str:
        """Extract the package name from finding metadata."""
        # Try root_cause
        if finding.root_cause:
            match = re.search(r"['\"]?([\w\-_.]+)['\"]?\s*(?:==|>=|<=|!=|~=|>|<)", finding.root_cause)
            if match:
                return self._normalize_package_name(match.group(1))
            # Pattern: "package X" or "missing X" or "broken X"
            match = re.search(r"(?:package|dependency|missing|broken|conflict(?:ing)?)\s+['\"]?([\w\-_.]+)['\"]?", finding.root_cause, re.IGNORECASE)
            if match:
                return self._normalize_package_name(match.group(1))

        # Try known_facts
        for fact in finding.known_facts:
            match = re.search(r"['\"]?([\w\-_.]+)['\"]?\s*(?:==|>=|<=|!=|~=|>|<)", fact)
            if match:
                return self._normalize_package_name(match.group(1))
            match = re.search(r"(?:package|dependency|missing|broken|conflict(?:ing)?|requires?)\s+['\"]?([\w\-_.]+)['\"]?", fact, re.IGNORECASE)
            if match:
                return self._normalize_package_name(match.group(1))

        # Try affected_component
        if finding.affected_component:
            # If affected_component looks like a package name
            name = finding.affected_component.strip()
            if re.match(r"^[\w\-_.]+$", name) and not name.endswith(".py"):
                return self._normalize_package_name(name)

        return ""

    def _extract_target_version(self, finding: Finding) -> str:
        """Extract a target/compatible version from finding known_facts or root_cause."""
        # Look for patterns like "requires ==1.2.3", "compatible version: 1.2.3",
        # "upgrade to 1.2.3", "use version 1.2.3"
        version_pattern = re.compile(
            r"(?:requires?|compatible|upgrade\s+to|use\s+version|target|needs?|pin\s+to|resolved?\s+(?:by|with))\s*"
            r"(?:version\s*)?['\"]?(?:==|>=|~=)?\s*(\d+\.\d+(?:\.\d+)?)['\"]?",
            re.IGNORECASE,
        )

        for fact in finding.known_facts:
            match = version_pattern.search(fact)
            if match:
                return match.group(1)

        if finding.root_cause:
            match = version_pattern.search(finding.root_cause)
            if match:
                return match.group(1)

        # Try a simpler pattern: just grab a version number from known_facts
        # that isn't the current (conflicting) version — take the last one mentioned
        versions_found: list[str] = []
        for fact in finding.known_facts:
            for m in re.finditer(r"(\d+\.\d+(?:\.\d+)?)", fact):
                versions_found.append(m.group(1))

        if len(versions_found) >= 2:
            # Heuristic: the second version mentioned is typically the target
            return versions_found[-1]

        return ""

    def _extract_version_hint_from_facts(self, finding: Finding) -> str:
        """Extract any version number from known_facts as a hint."""
        for fact in finding.known_facts:
            match = re.search(r"(\d+\.\d+(?:\.\d+)?)", fact)
            if match:
                return match.group(1)
        if finding.root_cause:
            match = re.search(r"(\d+\.\d+(?:\.\d+)?)", finding.root_cause)
            if match:
                return match.group(1)
        return ""

    def _find_current_version(self, content: str, package_name: str) -> str:
        """Find the currently pinned version of a package in requirements content."""
        escaped = re.escape(package_name)
        # Match: package==version, package>=version, etc.
        pattern = re.compile(
            rf"^{escaped}\s*(?:==|>=|<=|~=)\s*(\d+\.\d+(?:\.\d+)?)",
            re.MULTILINE | re.IGNORECASE,
        )
        match = pattern.search(content)
        if match:
            return match.group(1)
        return ""

    def _compute_compatible_version(self, current_version: str) -> str:
        """Compute the next compatible version by bumping the patch or minor.

        Strategy: bump patch version by 1. If only major.minor, bump minor by 1.
        """
        parts = current_version.split(".")
        if len(parts) >= 3:
            # Bump patch
            parts[2] = str(int(parts[2]) + 1)
        elif len(parts) == 2:
            # Bump minor
            parts[1] = str(int(parts[1]) + 1)
        else:
            # Just major — add .1
            parts.append("1")
        return ".".join(parts)

    def _replace_version_pin(self, content: str, package_name: str, new_version: str) -> tuple[str, bool]:
        """Replace the version pin for a package in requirements content.

        Returns (new_content, was_replaced).
        """
        escaped = re.escape(package_name)
        # Match lines like: package==1.0.0, package>=1.0.0, package~=1.0.0
        pattern = re.compile(
            rf"^({escaped}\s*)(==|>=|<=|~=|!=|>|<)\s*\d+\.\d+(?:\.\d+)?(.*)$",
            re.MULTILINE | re.IGNORECASE,
        )
        new_content, count = pattern.subn(rf"\g<1>=={new_version}\g<3>", content)
        return new_content, count > 0

    def _add_version_to_existing(self, content: str, package_name: str, version: str) -> tuple[str, bool]:
        """Add a version pin to an existing package line that has no version specifier.

        Returns (new_content, was_replaced).
        """
        escaped = re.escape(package_name)
        # Match bare package name on its own line (no version specifier)
        pattern = re.compile(
            rf"^({escaped})\s*$",
            re.MULTILINE | re.IGNORECASE,
        )
        new_content, count = pattern.subn(rf"\g<1>=={version}", content)
        return new_content, count > 0

    def _package_exists_in_content(self, content: str, package_name: str) -> bool:
        """Check if a package already appears in the requirements content."""
        escaped = re.escape(package_name)
        pattern = re.compile(rf"^{escaped}\s*(?:==|>=|<=|~=|!=|>|<|$)", re.MULTILINE | re.IGNORECASE)
        return bool(pattern.search(content))

    @staticmethod
    def _normalize_package_name(name: str) -> str:
        """Normalize package name: lowercase and replace underscores/dots with hyphens."""
        return re.sub(r"[-_.]+", "-", name).lower()
