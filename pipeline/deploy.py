# Modified: 2026-06-24T06:57:46Z
"""
Deployment Orchestration Script — UiPath CLI Lifecycle.

Orchestrates the full deployment lifecycle for NextFlow-pipeline:
  1. Compute and save source hashes (pre-deployment baseline)
  2. Run `uipath auth` — halt on non-zero exit
  3. Run `uipath init` — halt on non-zero exit
  4. Run entry-points schema verification (compare against pre-rename snapshot)
  5. Run deployment guard (verify source files unchanged)
  6. Run regression suite — halt if any of 184 assertions fail
  7. Run `uipath pack --output ./dist` — halt on non-zero exit
  8. Verify `.nupkg` file exists with expected name pattern
  9. Run `uipath publish --folder "NextFlow"` — halt on non-zero exit

Each step logs: step name, success/failure status, failure reason.
Halts entire sequence on any non-zero exit code.

Usage (from pipeline/ directory):
    python deploy.py

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6
"""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Expected .nupkg filename after pack
EXPECTED_NUPKG = "NextFlow-pipeline.1.0.0.nupkg"
DIST_DIR = "./dist"


class DeploymentStep:
    """Represents a single step in the deployment lifecycle."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.status: str = "PENDING"
        self.reason: str = ""

    def pass_step(self) -> None:
        self.status = "PASS"

    def fail_step(self, reason: str) -> None:
        self.status = "FAIL"
        self.reason = reason

    def log(self) -> str:
        if self.status == "PASS":
            return f"  [{self.status}] {self.name}"
        else:
            return f"  [{self.status}] {self.name} — {self.reason}"


def run_command(cmd: list[str], step: DeploymentStep, cwd: str | None = None) -> bool:
    """Run a shell command. Returns True on success, False on failure."""
    print(f"\n  Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
    except FileNotFoundError as e:
        step.fail_step(f"Command not found: {e}")
        return False
    except Exception as e:
        step.fail_step(f"Unexpected error: {e}")
        return False

    if result.stdout:
        for line in result.stdout.strip().splitlines():
            print(f"    {line}")

    if result.returncode != 0:
        error_output = result.stderr.strip() if result.stderr else result.stdout.strip()
        step.fail_step(
            f"Exit code {result.returncode}: {error_output[:500]}"
        )
        if result.stderr:
            for line in result.stderr.strip().splitlines():
                print(f"    [stderr] {line}")
        return False

    step.pass_step()
    return True


def run_python_script(script_path: str, step: DeploymentStep, cwd: str | None = None) -> bool:
    """Run a Python script using the current interpreter. Returns True on success."""
    cmd = [sys.executable, script_path]
    return run_command(cmd, step, cwd=cwd)


def main() -> int:
    """Orchestrate the full deployment lifecycle."""
    start_time = datetime.now(timezone.utc)
    print("=" * 70)
    print("  DEPLOYMENT ORCHESTRATION — NextFlow-pipeline v1.0.0")
    print(f"  Started: {start_time.isoformat()}")
    print("=" * 70)

    # Determine project root (same directory as this script)
    project_root = Path(__file__).parent.resolve()
    os.chdir(project_root)

    steps: list[DeploymentStep] = []

    # ─────────────────────────────────────────────────────────────────────
    # Step 1: Compute and save source hashes (pre-deployment baseline)
    # ─────────────────────────────────────────────────────────────────────
    step = DeploymentStep("1. Compute Source Hashes", "Pre-deployment baseline")
    steps.append(step)
    print(f"\n{'─' * 70}")
    print(f"  Step 1: {step.description}")
    print(f"{'─' * 70}")

    if not run_python_script("tests/compute_source_hashes.py", step):
        print(f"\n{step.log()}")
        print("\n  HALTED: Deployment aborted due to step failure.")
        return 1
    print(step.log())

    # ─────────────────────────────────────────────────────────────────────
    # Step 2: uipath auth — establish authenticated session
    # ─────────────────────────────────────────────────────────────────────
    step = DeploymentStep("2. UiPath Auth", "Establish authenticated session")
    steps.append(step)
    print(f"\n{'─' * 70}")
    print(f"  Step 2: {step.description}")
    print(f"{'─' * 70}")

    if not run_command(["uipath", "auth"], step):
        print(f"\n{step.log()}")
        print("\n  HALTED: Deployment aborted due to authentication failure.")
        return 1
    print(step.log())

    # ─────────────────────────────────────────────────────────────────────
    # Step 3: uipath init — regenerate metadata
    # ─────────────────────────────────────────────────────────────────────
    step = DeploymentStep("3. UiPath Init", "Regenerate metadata after rename")
    steps.append(step)
    print(f"\n{'─' * 70}")
    print(f"  Step 3: {step.description}")
    print(f"{'─' * 70}")

    if not run_command(["uipath", "init"], step):
        print(f"\n{step.log()}")
        print("\n  HALTED: Deployment aborted due to init failure.")
        return 1
    print(step.log())

    # ─────────────────────────────────────────────────────────────────────
    # Step 4: Entry-points schema verification
    # ─────────────────────────────────────────────────────────────────────
    step = DeploymentStep("4. Entry-Points Verification", "Compare schema against pre-rename snapshot")
    steps.append(step)
    print(f"\n{'─' * 70}")
    print(f"  Step 4: {step.description}")
    print(f"{'─' * 70}")

    if not run_python_script("tests/verify_entry_points.py", step):
        print(f"\n{step.log()}")
        print("\n  HALTED: Entry-points schema has changed. Investigate before proceeding.")
        return 1
    print(step.log())

    # ─────────────────────────────────────────────────────────────────────
    # Step 5: Deployment guard — verify source files unchanged
    # ─────────────────────────────────────────────────────────────────────
    step = DeploymentStep("5. Deployment Guard", "Verify pipeline source files unchanged")
    steps.append(step)
    print(f"\n{'─' * 70}")
    print(f"  Step 5: {step.description}")
    print(f"{'─' * 70}")

    if not run_python_script("tests/deployment_guard.py", step):
        print(f"\n{step.log()}")
        print("\n  HALTED: Pipeline integrity violation detected.")
        return 1
    print(step.log())

    # ─────────────────────────────────────────────────────────────────────
    # Step 6: Regression suite — 8 fixtures, 184 assertions
    # ─────────────────────────────────────────────────────────────────────
    step = DeploymentStep("6. Regression Suite", "Run 8 fixtures with 184 assertions")
    steps.append(step)
    print(f"\n{'─' * 70}")
    print(f"  Step 6: {step.description}")
    print(f"{'─' * 70}")

    if not run_python_script("tests/run_fixture_regression.py", step):
        print(f"\n{step.log()}")
        print("\n  HALTED: Regression suite failed. Do not pack or publish.")
        return 1
    print(step.log())

    # ─────────────────────────────────────────────────────────────────────
    # Step 7: uipath pack — produce .nupkg artifact
    # ─────────────────────────────────────────────────────────────────────
    step = DeploymentStep("7. UiPath Pack", "Produce .nupkg artifact")
    steps.append(step)
    print(f"\n{'─' * 70}")
    print(f"  Step 7: {step.description}")
    print(f"{'─' * 70}")

    if not run_command(["uipath", "pack", "--output", DIST_DIR], step):
        print(f"\n{step.log()}")
        print("\n  HALTED: Pack operation failed.")
        return 1
    print(step.log())

    # ─────────────────────────────────────────────────────────────────────
    # Step 8: Verify .nupkg file exists with expected name and is the only artifact
    # ─────────────────────────────────────────────────────────────────────
    step = DeploymentStep("8. Verify .nupkg Artifact", f"Check for exactly one .nupkg: {EXPECTED_NUPKG}")
    steps.append(step)
    print(f"\n{'─' * 70}")
    print(f"  Step 8: {step.description}")
    print(f"{'─' * 70}")

    dist_path = Path(DIST_DIR)

    # Check output directory exists
    if not dist_path.exists():
        step.fail_step(f"Output directory '{DIST_DIR}/' does not exist")
        print(f"\n{step.log()}")
        print("\n  HALTED: Pack artifact verification failed.")
        return 1

    # Enumerate all .nupkg files in the output directory
    nupkg_files = list(dist_path.glob("*.nupkg"))

    # Verify at least one .nupkg exists
    if not nupkg_files:
        step.fail_step(f"No .nupkg files found in {DIST_DIR}/")
        print(f"\n{step.log()}")
        print("\n  HALTED: Pack artifact verification failed.")
        return 1

    # Verify exactly one .nupkg file exists
    if len(nupkg_files) > 1:
        found_list = "\n".join(f"      - {f.name} ({f.stat().st_size:,} bytes)" for f in nupkg_files)
        step.fail_step(
            f"Expected exactly 1 .nupkg file but found {len(nupkg_files)}"
        )
        print(f"    Multiple .nupkg files found in {DIST_DIR}/:")
        print(found_list)
        print(f"\n{step.log()}")
        print("\n  HALTED: Pack artifact verification failed — multiple artifacts detected.")
        return 1

    # Verify the single .nupkg has the expected name
    nupkg_path = nupkg_files[0]
    if nupkg_path.name != EXPECTED_NUPKG:
        step.fail_step(
            f"Expected '{EXPECTED_NUPKG}' but found '{nupkg_path.name}'"
        )
        print(f"\n{step.log()}")
        print("\n  HALTED: Pack artifact verification failed.")
        return 1

    # Log artifact details
    file_size = nupkg_path.stat().st_size
    print(f"    Artifact: {nupkg_path.resolve()}")
    print(f"    Size:     {file_size:,} bytes")
    print(f"    Count:    1 .nupkg file (expected)")
    step.pass_step()
    print(step.log())

    # ─────────────────────────────────────────────────────────────────────
    # Step 9: uipath publish — upload to Orchestrator
    # ─────────────────────────────────────────────────────────────────────
    step = DeploymentStep("9. UiPath Publish", "Upload to Orchestrator (NextFlow folder)")
    steps.append(step)
    print(f"\n{'─' * 70}")
    print(f"  Step 9: {step.description}")
    print(f"{'─' * 70}")

    if not run_command(["uipath", "publish", "--folder", "NextFlow"], step):
        print(f"\n{step.log()}")
        print("\n  HALTED: Publish operation failed.")
        return 1
    print(step.log())

    # ─────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    print(f"\n{'=' * 70}")
    print("  DEPLOYMENT SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Completed: {end_time.isoformat()}")
    print(f"  Duration:  {duration:.1f}s")
    print()

    passed = [s for s in steps if s.status == "PASS"]
    for s in passed:
        print(s.log())

    print(f"\n  All {len(passed)}/{len(steps)} steps PASSED.")
    print(f"  Package: {EXPECTED_NUPKG}")
    print(f"  Folder:  NextFlow")
    print(f"\n  Deployment SUCCEEDED.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
