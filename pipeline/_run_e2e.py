"""Run pipeline end-to-end against this repo with full logging."""
import sys
import logging
from pathlib import Path

_PIPELINE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PIPELINE_DIR.parent
sys.path.insert(0, str(_PIPELINE_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)

from main import main
from phase_models import WorkflowInput

# Default: run against this repo root; override via CLI arg
target_path = sys.argv[1] if len(sys.argv) > 1 else str(_REPO_ROOT)

inp = WorkflowInput(
    case_id="e2e-repo-run",
    target_path=target_path,
    mode="auto",
    requested_action="run_pipeline",
)

result = main(inp)

print("\n===== RESULT =====")
print(f"Status: {result.pipeline_status.value}")
print(f"Phases completed: {len(result.phase_results)}")
for pr in result.phase_results:
    print(f"  [{pr.phase}] {pr.phase_name}: {pr.exit_status} ({pr.duration_ms}ms)")

if result.final_output:
    fo = result.final_output
    print(f"\nFinal output ({len(fo)} fields):")
    print(f"  resolved_count: {fo.get('resolved_count', '?')}")
    print(f"  unresolved_count: {fo.get('unresolved_count', '?')}")
    print(f"  completion_status: {fo.get('completion_status', '?')}")
    print(f"  snapshot_hash: {fo.get('snapshot_hash', '?')}")
    print(f"  inspection_hash: {fo.get('inspection_hash', '?')}")

# Auto-render MP4 from execution trace
import glob
import os
traces = sorted(glob.glob(os.path.join("..", "proof", "execution_trace_*.json")), key=os.path.getmtime)
if traces:
    from tools.demo.render_mp4 import render_mp4
    render_mp4(traces[-1], os.path.join("..", "artifacts", "demo.mp4"))
    print(f"\n  MP4: artifacts/demo.mp4")
