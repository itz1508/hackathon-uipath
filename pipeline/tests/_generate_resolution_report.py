"""Generate Resolution Report — Runner.

Runs the report generator against fixture-large-demo, saves:
- proof/resolution_report.json
- proof/resolution_report.html

Prints summary to terminal.

Usage:
    python tests/_generate_resolution_report.py
"""
import sys
import os
import json
from pathlib import Path

# Setup path — pipeline root
PIPELINE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PIPELINE_ROOT)
os.environ.setdefault("Mistral_API_KEY", "")

from resolution_report import generate_report


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

FIXTURE_PATH = os.path.join(PIPELINE_ROOT, "tests", "fixtures", "fixture-large-demo")
PROOF_DIR = os.path.join(PIPELINE_ROOT, "proof")
os.makedirs(PROOF_DIR, exist_ok=True)


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    print("=" * 76)
    print("  RESOLUTION REPORT GENERATOR")
    print("=" * 76)
    print()
    print(f"  Fixture: {FIXTURE_PATH}")
    print(f"  Output:  {PROOF_DIR}/")
    print()

    # Generate report (single-run, isolation always enabled)
    json_str, html_str = generate_report(FIXTURE_PATH)

    # Parse for summary display
    report = json.loads(json_str)

    # Save JSON
    json_path = os.path.join(PROOF_DIR, "resolution_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(json_str)
    print(f"\n  Saved: {json_path}")

    # Save HTML
    html_path = os.path.join(PROOF_DIR, "resolution_report.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_str)
    print(f"  Saved: {html_path}")

    # Print summary
    summary = report.get("summary", {})
    metrics = report.get("metrics", {})

    print()
    print("─" * 76)
    print("  REPORT SUMMARY")
    print("─" * 76)
    print(f"  Report ID:  {report.get('report_id', '')}")
    print(f"  Status:     {summary.get('status', '')}")
    print(f"  Score:      {summary.get('initial_score', 0):.2f}% → {summary.get('final_score', 0):.2f}%  (Δ {summary.get('delta_score', 0):+.2f}%)")
    print(f"  Issues:     {summary.get('total_issues', 0)} total, {summary.get('resolved', 0)} resolved, {summary.get('unresolved', 0)} unresolved")
    print()
    print("  Metrics:")
    print(f"    Scan Coverage:           {metrics.get('scan_coverage', 0):.1f}%")
    print(f"    Analysis Confidence:     {metrics.get('analysis_confidence', 0):.1f}%")
    print(f"    Simulation Success:      {metrics.get('simulation_success_rate', 0):.1f}%")
    print(f"    Isolation Effectiveness: {metrics.get('isolation_effectiveness', 0):.1f}%")
    print(f"    Pipeline Stability:      {metrics.get('pipeline_stability', 0):.1f}%")
    print()
    print("═" * 76)
    print("  DONE")
    print("═" * 76)


if __name__ == "__main__":
    main()
