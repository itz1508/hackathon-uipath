# Modified: 2026-06-23T00:00:00Z
"""Precalibration toolkit tests."""
from toolkits.precalibration import normalize


def test_precalibration_importable():
    from toolkits import precalibration
    assert hasattr(precalibration, "normalize")


def test_normalize_minimal_snapshot():
    """Accepts valid snapshot even with empty raw_signals."""
    result = normalize({
        "snapshot_id": "abc123",
        "file_hashes": {},
        "target_path": "/tmp/test",
        "raw_signals": [],
        "file_metadata": {},
    })
    assert result["signal_count"] == 0
    assert result["dropped_count"] == 0
    assert result["normalization_stats"]["raw_count"] == 0
    assert "calibrated_signals" in result


def test_normalize_with_file_hashes():
    """File hashes produce file_change signals."""
    result = normalize({
        "snapshot_id": "abc123",
        "file_hashes": {
            "/tmp/test/main.py": "abcdef123456",
            "/tmp/test/README.md": "7890123456",
        },
        "target_path": "/tmp/test",
        "raw_signals": [],
        "file_metadata": {},
    })
    assert result["signal_count"] == 2
    cats = {s["category"] for s in result["calibrated_signals"]}
    assert cats == {"file_change"}
    signals = sorted(result["calibrated_signals"], key=lambda s: s["payload"]["file_path"])
    # README.md sorts before main.py (R < m)
    assert signals[0]["severity"] == 0.2   # README.md (.md)
    assert signals[1]["severity"] == 0.5   # main.py (.py)


def test_normalize_deduplication():
    """Duplicate signals with same fingerprint are collapsed."""
    result = normalize({
        "snapshot_id": "abc123",
        "file_hashes": {},
        "target_path": "/tmp/test",
        "raw_signals": [
            {"type": "permission", "source": "/tmp/test/secret.key", "message": "chmod 777"},
            {"type": "permission", "source": "/tmp/test/secret.key", "message": "chmod 777"},
        ],
        "file_metadata": {},
    })
    assert result["signal_count"] == 1


def test_normalize_bounding():
    """MAX_SIGNALS cap is enforced."""
    raw_signals = [{"type": "file_change", "source": f"/tmp/file_{i}.py", "message": f"change {i}"} for i in range(15000)]
    result = normalize({"snapshot_id": "abc123", "file_hashes": {}, "target_path": "/tmp/test", "raw_signals": raw_signals, "file_metadata": {}})
    assert result["signal_count"] <= 10000
    assert result["dropped_count"] >= 5000


def test_normalize_classification():
    """Raw signals are correctly classified by type."""
    result = normalize({
        "snapshot_id": "abc123", "file_hashes": {}, "target_path": "/tmp/test",
        "raw_signals": [
            {"type": "dependency", "source": "requirements.txt", "message": "new dep: flask"},
            {"type": "config", "source": "config.json", "message": "port changed"},
            {"type": "network", "source": "0.0.0.0:8080", "message": "port open"},
        ],
        "file_metadata": {},
    })
    categories = {s["category"] for s in result["calibrated_signals"]}
    assert "dependency" in categories
    assert "config" in categories
    assert "network" in categories


def test_normalize_rejects_missing_keys():
    """Missing required keys raise ValueError."""
    import pytest
    with pytest.raises(ValueError):
        normalize({})
    with pytest.raises(ValueError):
        normalize({"snapshot_id": "abc"})
    with pytest.raises(ValueError):
        normalize({"snapshot_id": "abc", "file_hashes": {}, "target_path": "/tmp", "raw_signals": None})


def test_normalize_deterministic():
    """Same input always produces same output."""
    snapshot = {
        "snapshot_id": "xyz789",
        "file_hashes": {"/a/b.py": "hash1", "/c/d.json": "hash2"},
        "target_path": "/test",
        "raw_signals": [{"type": "certificate", "source": "cert.pem", "message": "expired"}],
        "file_metadata": {},
    }
    r1 = normalize(snapshot)
    r2 = normalize(snapshot)
    assert r1["signal_count"] == r2["signal_count"]
    assert r1["calibrated_signals"] == r2["calibrated_signals"]