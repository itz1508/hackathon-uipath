# Modified: 2026-06-29T20:00:00Z
"""Runner script to invoke the NextFlow pipeline main() from CLI."""
import json
import sys
from pathlib import Path

# Add workspace root to path
_PIPELINE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PIPELINE_DIR.parent
sys.path.insert(0, str(_REPO_ROOT))

from pipeline.main import main, WorkflowInput


def get_repo_root() -> Path:
    """Return the repository root (parent of the pipeline/ directory)."""
    return _REPO_ROOT


def run():
    # Default target: cases/sample-config-repair/source in this repo
    target_path = str(_REPO_ROOT / "cases" / "sample-config-repair" / "source")
    if len(sys.argv) > 1:
        target_path = sys.argv[1]

    workflow_input = WorkflowInput(
        case_id="BAPA-20260624-001",
        target_path=target_path,
        mode="manual",  # Pause at Phase 5 for decision
        requested_action="run_pipeline",
    )

    print(f"Invoking NextFlow Pipeline on: {target_path}")
    print(f"Case ID: {workflow_input.case_id}")
    print(f"Mode: {workflow_input.mode}")
    print()

    try:
        output = main(workflow_input)
        result = output.model_dump()
        print(json.dumps(result, indent=2, default=str))

        # Save output
        output_path = Path(__file__).parent / "pipeline_output.json"
        output_path.write_text(json.dumps(result, indent=2, default=str))
        print(f"\nOutput saved to: {output_path}")

    except Exception as e:
        print(f"Pipeline error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run()
