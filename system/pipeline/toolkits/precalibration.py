# Modified: 2026-06-23T00:00:00Z
"""Precalibration toolkit — Phase 1.

Deterministic normalization layer between Snapshot (Phase 0) and Scanner (Phase 2).
Stabilizes raw system signals into bounded, deduplicated, structured inputs,
ensuring controlled downstream tool activation without inflating issue granularity.

Inputs:
  - snapshot: dict — raw output from Phase 0 containing:
      - snapshot_id: str
      - file_hashes: dict[str, str]   (path → sha256)
      - file_metadata: dict[str, dict] (path → {size, mtime, permissions, ...})
      - raw_signals: list[dict]       (unprocessed signals from target environment)
      - target_path: str

Outputs:
  - calibrated_signals: list[dict] — deduplicated, bounded, structured signals
      Each signal:
        - signal_id: str           (deterministic hash of normalized content)
        - category: str            (bounded enum: "file_change", "permission", "dependency", ...)
        - severity: float          (bounded [0.0, 1.0])
        - fingerprint: str         (dedup key — same fingerprint = duplicate)
        - payload: dict            (normalized data, schema per category)
        - confidence: float        (bounded [0.0, 1.0])
  - signal_count: int             (after dedup, before bounding)
  - dropped_count: int            (signals dropped by bounds/rules)
  - normalization_stats: dict     (dedup rate, bound violations, category distribution)

Side effects:
  - none (pure computation)

Errors:
  - ValueError if snapshot dict is missing required keys
  - ValueError if raw_signals contain unprocessable entries after 3 retries
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

# ── Category taxonomy (bounded enum) ───────────────────────────────────────

VALID_CATEGORIES = frozenset({
    "file_change",
    "permission",
    "dependency",
    "config",
    "environment",
    "network",
    "process",
    "registry",
    "certificate",
    "unknown",
})

SEVERITY_WEIGHTS = {
    "file_change": 0.3,
    "permission": 0.6,
    "dependency": 0.7,
    "config": 0.4,
    "environment": 0.5,
    "network": 0.8,
    "process": 0.6,
    "registry": 0.5,
    "certificate": 0.9,
    "unknown": 0.1,
}

MAX_SIGNALS = 10_000          # hard bound — prevents inflation
MAX_SEVERITY = 1.0
MIN_SEVERITY = 0.0
MAX_CONFIDENCE = 1.0


# ── Public API ─────────────────────────────────────────────────────────────

def normalize(snapshot: dict) -> dict[str, Any]:
    """Normalize raw snapshot signals into bounded, deduplicated output.

    Pipeline: raw_signals → classify → deduplicate → bound → calibrate
    """
    _validate_snapshot(snapshot)

    raw_signals = snapshot.get("raw_signals", [])
    file_hashes = snapshot.get("file_hashes", {})
    file_metadata = snapshot.get("file_metadata", {})

    # Step 1: Classify every raw signal into a category
    classified = [_classify(signal, file_hashes, file_metadata) for signal in raw_signals]

    # Step 2: Generate file-change signals from hashes (baseline deduction)
    hash_signals = _hash_to_signals(file_hashes, file_metadata)
    classified.extend(hash_signals)

    # Step 3: Deduplicate by fingerprint
    deduped = _deduplicate(classified)

    # Step 4: Bound — apply severity caps and max signal count
    bounded = _bound(deduped)

    # Step 5: Compute stats
    dropped_count = len(classified) - len(bounded)
    dedup_rate = 1.0 - (len(deduped) / max(len(classified), 1))
    category_dist: dict[str, int] = {}
    for sig in bounded:
        cat = sig["category"]
        category_dist[cat] = category_dist.get(cat, 0) + 1

    return {
        "calibrated_signals": bounded,
        "signal_count": len(bounded),
        "dropped_count": dropped_count,
        "normalization_stats": {
            "raw_count": len(raw_signals),
            "classified_count": len(classified),
            "deduped_count": len(deduped),
            "dedup_rate": round(dedup_rate, 4),
            "bound_violations": dropped_count,
            "category_distribution": category_dist,
        },
    }


# ── Internal steps ─────────────────────────────────────────────────────────

def _validate_snapshot(snapshot: dict) -> None:
    """Raise ValueError if snapshot is missing required keys."""
    required = {"snapshot_id", "file_hashes", "target_path"}
    missing = required - set(snapshot.keys())
    if missing:
        raise ValueError(f"Snapshot missing required keys: {missing}")
    if not isinstance(snapshot.get("raw_signals"), list):
        raise ValueError("raw_signals must be a list")


def _classify(
    signal: dict,
    file_hashes: dict[str, str],
    file_metadata: dict[str, dict],
) -> dict[str, Any]:
    """Classify a raw signal into a typed, structured signal.

    Uses heuristic rules to determine category and compute initial severity.
    """
    raw_type = str(signal.get("type", "")).lower()
    raw_source = str(signal.get("source", "")).lower()

    # Classification rules (deterministic, ordered by specificity)
    category = "unknown"
    if raw_type in VALID_CATEGORIES:
        category = raw_type
    elif "perm" in raw_type or "chmod" in raw_type:
        category = "permission"
    elif "dep" in raw_type or "import" in raw_type or "require" in raw_type:
        category = "dependency"
    elif "config" in raw_type or raw_source.endswith((".json", ".yaml", ".toml", ".ini", ".conf")):
        category = "config"
    elif "env" in raw_type or "var" in raw_type:
        category = "environment"
    elif "net" in raw_type or "http" in raw_type or "socket" in raw_type:
        category = "network"
    elif "proc" in raw_type or "pid" in raw_type:
        category = "process"
    elif "cert" in raw_type or "tls" in raw_type or "ssl" in raw_type:
        category = "certificate"

    # Normalize content to string for fingerprinting
    content = signal.get("content", signal.get("message", ""))
    if not isinstance(content, str):
        content = json.dumps(content, sort_keys=True, default=str)

    # Compute bounded severity
    base_severity = SEVERITY_WEIGHTS.get(category, 0.1)
    signal_severity = float(signal.get("severity", signal.get("weight", base_severity)))
    severity = max(MIN_SEVERITY, min(MAX_SEVERITY, signal_severity))

    # Compute confidence
    confidence = max(MIN_SEVERITY, min(MAX_CONFIDENCE, float(signal.get("confidence", 0.8))))

    # Build payload with normalized fields
    payload = {
        "source": signal.get("source", "unknown"),
        "content": content[:10_000],  # truncate to prevent blowup
        "file_path": signal.get("file_path", signal.get("path", "")),
        "line": signal.get("line", signal.get("line_number", 0)),
        "timestamp": signal.get("timestamp", ""),
    }

    # Generate fingerprint for dedup (hash of normalized fields)
    fingerprint_data = f"{category}|{payload['file_path']}|{payload['line']}|{content[:500]}"
    fingerprint = hashlib.sha256(fingerprint_data.encode()).hexdigest()[:32]

    signal_id = hashlib.sha256(f"{fingerprint}|{severity}|{confidence}".encode()).hexdigest()[:16]

    return {
        "signal_id": signal_id,
        "category": category,
        "severity": round(severity, 4),
        "fingerprint": fingerprint,
        "payload": payload,
        "confidence": round(confidence, 4),
    }


def _hash_to_signals(
    file_hashes: dict[str, str],
    file_metadata: dict[str, dict],
) -> list[dict[str, Any]]:
    """Convert file hash changes into structured signals.

    Every file in the snapshot with a hash becomes a 'file_change' signal
    with bounded severity based on file type.
    """
    signals: list[dict[str, Any]] = []
    for path_str, file_hash in file_hashes.items():
        meta = file_metadata.get(path_str, {})
        ext = Path(path_str).suffix.lower()

        # Severity by file type (code files > docs > binaries)
        if ext in (".py", ".js", ".ts", ".java", ".cs", ".go", ".rs"):
            severity = 0.5
        elif ext in (".json", ".yaml", ".yml", ".toml", ".ini", ".conf"):
            severity = 0.4
        elif ext in (".md", ".txt", ".rst", ".doc"):
            severity = 0.2
        elif ext in (".exe", ".dll", ".so", ".dylib", ".bin"):
            severity = 0.3
        else:
            severity = 0.1

        payload = {
            "source": "snapshot",
            "content": f"SHA256:{file_hash}",
            "file_path": path_str,
            "line": 0,
            "timestamp": meta.get("mtime", ""),
        }

        fingerprint = hashlib.sha256(f"file_change|{path_str}|{file_hash}".encode()).hexdigest()[:32]
        signal_id = hashlib.sha256(f"{fingerprint}|{severity}".encode()).hexdigest()[:16]

        signals.append({
            "signal_id": signal_id,
            "category": "file_change",
            "severity": severity,
            "fingerprint": fingerprint,
            "payload": payload,
            "confidence": 0.95,
        })

    return signals


def _deduplicate(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate signals by fingerprint, keeping the highest severity."""
    seen: dict[str, dict[str, Any]] = {}
    for sig in signals:
        fp = sig["fingerprint"]
        if fp in seen:
            # Keep the one with higher severity
            if sig["severity"] > seen[fp]["severity"]:
                seen[fp] = sig
        else:
            seen[fp] = sig
    return list(seen.values())


def _bound(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply hard bounds: max signal count, severity clamping."""
    # Severity already bounded in _classify, but double-check
    for sig in signals:
        sig["severity"] = max(MIN_SEVERITY, min(MAX_SEVERITY, sig["severity"]))
        sig["confidence"] = max(MIN_SEVERITY, min(MAX_CONFIDENCE, sig["confidence"]))

    # Sort by severity descending, keep top MAX_SIGNALS
    signals.sort(key=lambda s: s["severity"], reverse=True)
    return signals[:MAX_SIGNALS]