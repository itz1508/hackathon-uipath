# Modified: 2026-06-27T18:49:29Z
"""Snapshot capture and restore utilities for the NextFlow pipeline.

Provides filesystem snapshot capture and restore functions used by
Phase 0 (initial snapshot) and Phase 5 (cancel/restore path).
Storage path: ~/.NextFlow/snapshots/current
"""
import hashlib
import logging
import os
import shutil
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Directories to exclude from hashing AND copying
SNAPSHOT_EXCLUDED_DIRS: set[str] = {
    ".git", ".hg", ".svn",
    ".venv", "venv", "env",
    "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox",
    "node_modules", ".NextFlow",
}

# File extensions to exclude from hashing AND copying
SNAPSHOT_EXCLUDED_EXTENSIONS: set[str] = {".pyc", ".pyo"}


def _force_remove_readonly(func, path, exc_info):
    """onerror handler for shutil.rmtree: clears read-only flag and retries."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _snapshot_ignore(directory: str, entries: list[str]) -> set[str]:
    """Ignore function for shutil.copytree — excludes generated dirs and bytecode."""
    ignored = set()
    for entry in entries:
        if entry in SNAPSHOT_EXCLUDED_DIRS:
            ignored.add(entry)
        elif Path(entry).suffix.lower() in SNAPSHOT_EXCLUDED_EXTENSIONS:
            ignored.add(entry)
    return ignored


def capture_snapshot(target_path: str) -> dict[str, Any]:
    """Capture a full snapshot of the target folder.

    Hashes every file, overrides previous snapshot (no accumulation).
    Stores in user directory (~/.NextFlow/snapshots/), not project folder.
    Returns snapshot dict with snapshot_id, file_hashes, total_files, storage_path.
    """
    target = Path(target_path).resolve()
    if not target.exists() or not target.is_dir():
        raise ValueError(f"Target path does not exist or is not a directory: {target_path}")

    snapshot_id = str(uuid.uuid4())
    file_hashes: dict[str, str] = {}

    for root, _dirs, files in os.walk(target):
        # Prune excluded directories IN-PLACE to prevent descent
        _dirs[:] = [d for d in _dirs if d not in SNAPSHOT_EXCLUDED_DIRS]

        for filename in sorted(files):
            # Skip bytecode files
            if Path(filename).suffix.lower() in SNAPSHOT_EXCLUDED_EXTENSIONS:
                continue

            file_path = Path(root) / filename
            relative = str(file_path.relative_to(target)).replace(os.sep, "/")
            sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    sha256.update(chunk)
            file_hashes[relative] = sha256.hexdigest()

    # Store in user folder, override previous snapshot (no accumulation)
    user_snapshot_dir = Path.home() / ".NextFlow" / "snapshots"
    user_snapshot_dir.mkdir(parents=True, exist_ok=True)
    storage_path = str(user_snapshot_dir / "current")

    # Override: remove previous snapshot if exists
    if Path(storage_path).exists():
        shutil.rmtree(storage_path, onerror=_force_remove_readonly)

    shutil.copytree(target, storage_path, ignore=_snapshot_ignore)

    return {
        "snapshot_id": snapshot_id,
        "file_hashes": file_hashes,
        "total_files": len(file_hashes),
        "target_path": str(target),
        "storage_path": storage_path,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def restore_from_snapshot(snapshot: dict[str, Any], target_path: str) -> bool:
    """Restore target folder from snapshot. Cancel = restore from Snapshot.

    Original files exactly as attached, clean, no trace.
    """
    storage_path = snapshot.get("storage_path", "")
    if not storage_path or not Path(storage_path).exists():
        logger.error(f"Snapshot storage not found: {storage_path}")
        return False

    target = Path(target_path).resolve()
    try:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(storage_path, target)
        logger.info(f"Restored target from snapshot {snapshot.get('snapshot_id')}")
        return True
    except (OSError, shutil.Error) as exc:
        logger.error(f"Restore failed: {exc}")
        return False
