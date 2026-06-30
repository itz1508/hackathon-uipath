"""Module requiring human decision at relay phase."""

import json
import hashlib

def compute_hash(data: str) -> str:
    """Compute SHA-256 hash."""
    return hashlib.sha256(data.encode()).hexdigest()

def serialize(obj: dict) -> str:
    """Serialize to JSON."""
    return json.dumps(obj, indent=2)
