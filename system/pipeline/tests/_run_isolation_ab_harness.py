"""A/B Isolation Harness — Multi-fixture comparative test suite.

Discovers all fixtures in tests/fixtures/isolation_ab_suite/,
runs each with isolation_enabled=False (A) and isolation_enabled=True (B),
verifies fixture integrity, computes deltas, and generates proof reports.

Usage:
    python tests/_run_isolation_ab_harness.py
"""
import sys
import os
import json
import hashlib
import time
from pathlib import Path
from datetime import datetime, timezone

# Setup path — pipeline root
PIPELINE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PIPELINE_ROOT)
os.environ.setdefault("Mistral_API_KEY", "")

from phase_models import WorkflowInput
from orchestrator import run_pipeline_stateful


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

SUITE_DIR = os.path.join(PIPELINE_ROOT, "tests", "fixtures", "isolation_ab_suite")
PROOF_DIR = os.path.join(PIPELINE_ROOT, "proof")
os.makedirs(PROOF_DIR, exist_ok=True)


# ──────────────────────────────────────────────
# Utility Functions
# ──────────────────────────────────────────────

def fixture_hash(path: str) -> str:
    """Compute deterministic SHA-256 hash of a fixture directory."""
    target = Path(path)
    if not target.exists():
        return "MISSING"

    hasher = hashlib.sha256()
    for root, dirs, files in os.walk(target):
        dirs[:] = sorted(d for d in dirs if not d.startswith("__pycache__") and not d.startswith(".candidate"))
        for filename in sorted(files):
            filepath = Path(root) / filename
            rel = str(filepath.relative_to(target)).replace(os.sep, "/")
            hasher.update(rel.encode("utf-8"))
            try:
                hasher.update(filepath.read_bytes())
            except (OSError, PermissionError):
                hasher.update(b"UNREADABLE")
    return hasher.hexdigest()


def discover_fixtures(suite_dir: str) -> list[str]:
    """Discover all fixture directories in the suite, sorted by name."""
    suite = Path(suite_dir)
    if not suite.exists():
        return []
    fixtures = sorted([
        str(d) for d in suite.iterdir()
        if d.is_dir() and d.name.startswith("fixture_")
    ])
    return fixtures


def run_single(fixture_path: str, isolation_enabled: bool, label: str) -> dict:
    """Run a single pipeline invocation on a fixture."""
    case_id = f"harness-{label}-{Path(fixture_path).name}"
    t0 = time.perf_counter()

    state, output = run_pipeline_stateful(
        WorkflowInput(
            case_id=case_id,
            target_path=fixture_path,
            mode="auto",
            isolation_enabled=isolation_enabled,
        )
    )

    duration_ms = int((time.perf_counter() - t0) * 1000)
    pkg = state.simulation_package
    fo = state.final_output

    return {
        "isolation_enabled": isolation_enabled,
        "score": pkg.get("score", 0),
        "simulation_ready": pkg.get("simulation_ready", False),
        "ready_parts": pkg.get("ready_parts", []),
        "isolated_parts": pkg.get("isolated_parts", []),
        "ready_count": len(pkg.get("ready_parts", [])),
        "isolated_count": len(pkg.get("isolated_parts", [])),
        "resolved_count": fo.get("resolved_count", 0),
        "unresolved_count": fo.get("unresolved_count", 0),
        "completion_status": fo.get("completion_status", ""),
        "pipeline_status": output.pipeline_status.value if hasattr(output.pipeline_status, 'value') else str(output.pipeline_status),
        "duration_ms": duration_ms,
        "isolation_engine": pkg.get("isolation_engine_result", {}),
        "simulation_unlock": pkg.get("simulation_ready", False),
    }


# ──────────────────────────────────────────────
# Main Harness
# ──────────────────────────────────────────────

def run_harness():
    """Execute full A/B harness across all fixtures."""
    print("=" * 76)
    print("  A/B ISOLATION HARNESS — Multi-Fixture Comparative Suite")
    print("=" * 76)
    print()

    fixtures = discover_fixtures(SUITE_DIR)
    if not fixtures:
        print(f"  ERROR: No fixtures found in {SUITE_DIR}")
        sys.exit(1)

    print(f"  Discovered {len(fixtures)} fixtures in: {SUITE_DIR}")
    for f in fixtures:
        print(f"    • {Path(f).name}")
    print()

    results: list[dict] = []
    all_passed = True

    for i, fixture_path in enumerate(fixtures, 1):
        fixture_name = Path(fixture_path).name
        print("─" * 76)
        print(f"  [{i}/{len(fixtures)}] {fixture_name}")
        print("─" * 76)

        # Hash before any run
        hash_before = fixture_hash(fixture_path)
        print(f"  Hash before: {hash_before[:16]}...")

        # Run A (isolation OFF)
        print(f"  Running A (isolation=OFF)...", end=" ", flush=True)
        run_a = run_single(fixture_path, isolation_enabled=False, label="A")
        print(f"score={run_a['score']}%  ready={run_a['ready_count']}  isolated={run_a['isolated_count']}")

        # Verify hash after A
        hash_after_a = fixture_hash(fixture_path)
        fixture_ok_a = hash_before == hash_after_a

        # Run B (isolation ON)
        print(f"  Running B (isolation=ON)...", end=" ", flush=True)
        run_b = run_single(fixture_path, isolation_enabled=True, label="B")
        print(f"score={run_b['score']}%  ready={run_b['ready_count']}  isolated={run_b['isolated_count']}")

        # Verify hash after B
        hash_after_b = fixture_hash(fixture_path)
        fixture_ok_b = hash_after_a == hash_after_b

        # Compute delta
        delta_score = round(run_b["score"] - run_a["score"], 2)
        delta_ready = run_b["ready_count"] - run_a["ready_count"]
        delta_isolated = run_b["isolated_count"] - run_a["isolated_count"]

        # Fixture integrity check
        fixture_intact = fixture_ok_a and fixture_ok_b
        if not fixture_intact:
            all_passed = False

        print(f"  Delta: score={delta_score:+.2f}%  ready={delta_ready:+d}  isolated={delta_isolated:+d}")
        print(f"  Fixture integrity: {'✓ intact' if fixture_intact else '✗ MUTATED'}")
        print(f"  Simulation unlock: A={run_a['simulation_unlock']}  B={run_b['simulation_unlock']}")
        print()

        result_record = {
            "fixture": fixture_name,
            "fixture_path": fixture_path,
            "hash_before": hash_before,
            "hash_after_a": hash_after_a,
            "hash_after_b": hash_after_b,
            "fixture_intact": fixture_intact,
            "run_a": run_a,
            "run_b": run_b,
            "delta": {
                "score": delta_score,
                "ready_parts": delta_ready,
                "isolated_parts": delta_isolated,
                "resolved": run_b["resolved_count"] - run_a["resolved_count"],
            },
            "simulation_unlock_a": run_a["simulation_unlock"],
            "simulation_unlock_b": run_b["simulation_unlock"],
        }
        results.append(result_record)

    # ── Summary ──
    print("═" * 76)
    print("  SUMMARY")
    print("═" * 76)
    print()
    print(f"  {'Fixture':<30} {'Score A':<10} {'Score B':<10} {'Delta':<10} {'Unlock B':<10}")
    print(f"  {'─'*30} {'─'*10} {'─'*10} {'─'*10} {'─'*10}")
    for r in results:
        print(f"  {r['fixture']:<30} {r['run_a']['score']:<10.1f} {r['run_b']['score']:<10.1f} {r['delta']['score']:+<10.2f} {r['simulation_unlock_b']!s:<10}")
    print()

    # ── Generate JSON report ──
    report = {
        "harness": "isolation_ab_suite",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite_dir": SUITE_DIR,
        "fixture_count": len(fixtures),
        "all_fixtures_intact": all_passed,
        "results": results,
        "summary": {
            "avg_score_a": round(sum(r["run_a"]["score"] for r in results) / len(results), 2) if results else 0,
            "avg_score_b": round(sum(r["run_b"]["score"] for r in results) / len(results), 2) if results else 0,
            "avg_delta": round(sum(r["delta"]["score"] for r in results) / len(results), 2) if results else 0,
            "fixtures_with_improvement": sum(1 for r in results if r["delta"]["score"] > 0),
            "fixtures_with_unlock": sum(1 for r in results if r["simulation_unlock_b"] and not r["simulation_unlock_a"]),
        },
    }

    json_path = os.path.join(PROOF_DIR, "ab_harness_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"  JSON report: {json_path}")

    # ── Generate HTML report ──
    html_path = os.path.join(PROOF_DIR, "ab_harness_report.html")
    generate_html_report(report, html_path)
    print(f"  HTML report: {html_path}")
    print()

    if all_passed:
        print("═" * 76)
        print("  HARNESS PASSED — All fixtures intact, reports generated")
        print("═" * 76)
    else:
        print("═" * 76)
        print("  HARNESS WARNING — Some fixture integrity checks failed")
        print("═" * 76)
        sys.exit(1)


# ──────────────────────────────────────────────
# HTML Report Generator
# ──────────────────────────────────────────────

def generate_html_report(report: dict, output_path: str):
    """Generate a visual HTML report with bar charts and per-fixture details."""
    results = report["results"]
    summary = report["summary"]

    rows_html = ""
    for r in results:
        score_a = r["run_a"]["score"]
        score_b = r["run_b"]["score"]
        delta = r["delta"]["score"]
        ready_a = r["run_a"]["ready_count"]
        ready_b = r["run_b"]["ready_count"]
        isolated_a = r["run_a"]["isolated_count"]
        isolated_b = r["run_b"]["isolated_count"]
        unlock_a = r["simulation_unlock_a"]
        unlock_b = r["simulation_unlock_b"]
        intact = r["fixture_intact"]

        # Bar widths (percentage of 100)
        bar_a_width = min(100, max(1, score_a))
        bar_b_width = min(100, max(1, score_b))

        delta_class = "positive" if delta > 0 else ("negative" if delta < 0 else "neutral")
        unlock_icon_b = "&#x2713;" if unlock_b else "&#x2717;"
        unlock_icon_a = "&#x2713;" if unlock_a else "&#x2717;"
        intact_icon = "&#x2713;" if intact else "&#x2717; MUTATED"

        rows_html += f"""
        <tr>
            <td class="fixture-name">{r['fixture']}</td>
            <td>
                <div class="bar-container">
                    <div class="bar bar-a" style="width: {bar_a_width}%">{score_a:.1f}%</div>
                </div>
                <div class="bar-container">
                    <div class="bar bar-b" style="width: {bar_b_width}%">{score_b:.1f}%</div>
                </div>
            </td>
            <td class="delta {delta_class}">{delta:+.2f}%</td>
            <td>{ready_a} &rarr; {ready_b}</td>
            <td>{isolated_a} &rarr; {isolated_b}</td>
            <td class="unlock">{unlock_icon_a} &rarr; {unlock_icon_b}</td>
            <td class="intact">{intact_icon}</td>
        </tr>
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>A/B Isolation Harness Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0d1117; color: #c9d1d9; padding: 2rem; }}
        h1 {{ color: #58a6ff; margin-bottom: 0.5rem; font-size: 1.6rem; }}
        .meta {{ color: #8b949e; margin-bottom: 2rem; font-size: 0.9rem; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .summary-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1rem; text-align: center; }}
        .summary-card .value {{ font-size: 1.8rem; font-weight: bold; color: #58a6ff; }}
        .summary-card .label {{ font-size: 0.8rem; color: #8b949e; margin-top: 0.3rem; }}
        table {{ width: 100%; border-collapse: collapse; background: #161b22; border-radius: 8px; overflow: hidden; }}
        th {{ background: #21262d; color: #58a6ff; padding: 0.8rem; text-align: left; font-size: 0.85rem; text-transform: uppercase; }}
        td {{ padding: 0.7rem 0.8rem; border-top: 1px solid #21262d; font-size: 0.9rem; vertical-align: middle; }}
        .fixture-name {{ font-weight: 600; color: #f0f6fc; }}
        .bar-container {{ background: #21262d; border-radius: 4px; height: 20px; margin: 2px 0; position: relative; min-width: 200px; }}
        .bar {{ height: 100%; border-radius: 4px; display: flex; align-items: center; padding-left: 6px; font-size: 0.75rem; font-weight: bold; color: #fff; min-width: 40px; }}
        .bar-a {{ background: linear-gradient(90deg, #f85149, #da3633); }}
        .bar-b {{ background: linear-gradient(90deg, #3fb950, #238636); }}
        .delta.positive {{ color: #3fb950; font-weight: bold; }}
        .delta.negative {{ color: #f85149; font-weight: bold; }}
        .delta.neutral {{ color: #8b949e; }}
        .unlock {{ text-align: center; }}
        .intact {{ text-align: center; }}
        .threshold-line {{ position: absolute; left: 93.91%; top: 0; bottom: 0; border-left: 2px dashed #f0883e; z-index: 10; }}
        .legend {{ margin-top: 1.5rem; display: flex; gap: 2rem; font-size: 0.85rem; color: #8b949e; }}
        .legend-item {{ display: flex; align-items: center; gap: 0.4rem; }}
        .legend-swatch {{ width: 14px; height: 14px; border-radius: 3px; }}
        .swatch-a {{ background: #da3633; }}
        .swatch-b {{ background: #238636; }}
    </style>
</head>
<body>
    <h1>A/B Isolation Harness Report</h1>
    <div class="meta">
        Generated: {report['timestamp']} | Fixtures: {report['fixture_count']} | All Intact: {report['all_fixtures_intact']}
    </div>

    <div class="summary">
        <div class="summary-card">
            <div class="value">{summary['avg_score_a']:.1f}%</div>
            <div class="label">Avg Score A (Off)</div>
        </div>
        <div class="summary-card">
            <div class="value">{summary['avg_score_b']:.1f}%</div>
            <div class="label">Avg Score B (On)</div>
        </div>
        <div class="summary-card">
            <div class="value">{summary['avg_delta']:+.1f}%</div>
            <div class="label">Avg Delta</div>
        </div>
        <div class="summary-card">
            <div class="value">{summary['fixtures_with_improvement']}/{report['fixture_count']}</div>
            <div class="label">Improved</div>
        </div>
        <div class="summary-card">
            <div class="value">{summary['fixtures_with_unlock']}/{report['fixture_count']}</div>
            <div class="label">Unlocked Sim</div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Fixture</th>
                <th>Score (A=red, B=green)</th>
                <th>Delta</th>
                <th>Ready Parts</th>
                <th>Isolated Parts</th>
                <th>Sim Unlock</th>
                <th>Intact</th>
            </tr>
        </thead>
        <tbody>
{rows_html}
        </tbody>
    </table>

    <div class="legend">
        <div class="legend-item"><div class="legend-swatch swatch-a"></div> Run A (isolation OFF)</div>
        <div class="legend-item"><div class="legend-swatch swatch-b"></div> Run B (isolation ON)</div>
        <div class="legend-item">| Threshold: 93.91%</div>
    </div>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


# ──────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────

if __name__ == "__main__":
    run_harness()
