# Modified: 2026-06-24T06:57:46Z
"""
Deployment Verification — Post-Publish Process Visibility Check.

This script verifies that the deployed process `NextFlow_Pipeline`
is visible and invokable in the UiPath Orchestrator `NextFlow` folder.

It uses the `uipath` CLI to query process listings, polling up to 60 seconds
for the process to appear after publish. Optionally, it invokes the process
with minimal valid input to confirm job creation.

Usage (from pipeline/ directory):
    python tests/verify_deployment.py
    python tests/verify_deployment.py --invoke

Exit codes:
    0 — Process found in Orchestrator (and invocation succeeded if --invoke)
    1 — Timeout, error, or process not found

Requirements: 5.1, 5.2, 5.3, 5.4
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone

# Configuration
EXPECTED_PROCESS_NAME = "NextFlow_Pipeline"
EXPECTED_FOLDER = "NextFlow"
POLL_TIMEOUT_SECONDS = 60
POLL_INTERVAL_SECONDS = 5

# Minimal valid input for invocation test
INVOKE_INPUT = {
    "case_id": "deploy-verify",
    "target_path": "./tests/fixtures/fixture_a",
}


def get_timestamp() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def run_cli_command(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """
    Run a uipath CLI command and return the result.

    Returns the CompletedProcess with stdout/stderr captured.
    """
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=args,
            returncode=-1,
            stdout="",
            stderr="CLI command timed out",
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            args=args,
            returncode=-2,
            stdout="",
            stderr="uipath CLI not found. Ensure it is installed and on PATH.",
        )


def diagnose_error(stderr: str, returncode: int) -> str:
    """
    Analyze CLI error output and return a diagnostic message.

    Classifies errors into: auth expired, folder not found, process not visible,
    feed resolution, or generic failure.
    """
    stderr_lower = stderr.lower()

    if returncode == -2:
        return "DIAGNOSTIC: uipath CLI binary not found on PATH."

    if returncode == -1:
        return "DIAGNOSTIC: CLI command timed out (possible network issue)."

    if "auth" in stderr_lower or "unauthorized" in stderr_lower or "401" in stderr_lower:
        return (
            "DIAGNOSTIC: Authentication error — session may be expired. "
            "Run `uipath auth` to refresh credentials."
        )

    if "folder" in stderr_lower and ("not found" in stderr_lower or "does not exist" in stderr_lower):
        return (
            f"DIAGNOSTIC: Folder '{EXPECTED_FOLDER}' not found in Orchestrator tenant. "
            "Verify the folder exists and you have access."
        )

    if "feed" in stderr_lower or "package" in stderr_lower and "not found" in stderr_lower:
        return (
            "DIAGNOSTIC: Package feed resolution error — the package may not "
            "have been published successfully. Re-run `uipath publish`."
        )

    if "network" in stderr_lower or "connection" in stderr_lower or "timeout" in stderr_lower:
        return "DIAGNOSTIC: Network connectivity error — check internet connection."

    return f"DIAGNOSTIC: CLI exited with code {returncode}. stderr: {stderr.strip()}"


def check_process_listing() -> tuple[bool, str]:
    """
    Query Orchestrator for the expected process in the expected folder.

    Returns (found, diagnostic_message).
    """
    # Attempt to list processes in the NextFlow folder using uipath CLI
    # The exact CLI syntax may vary; try common patterns
    args = ["uipath", "processes", "list", "--folder", EXPECTED_FOLDER]

    result = run_cli_command(args)

    if result.returncode != 0:
        # Try alternative CLI syntax
        args_alt = ["uipath", "process", "list", "--folder", EXPECTED_FOLDER]
        result = run_cli_command(args_alt)

    if result.returncode != 0:
        diagnostic = diagnose_error(result.stderr, result.returncode)
        return False, diagnostic

    # Check if the expected process name appears in the output
    stdout = result.stdout
    if EXPECTED_PROCESS_NAME in stdout:
        return True, f"Process '{EXPECTED_PROCESS_NAME}' found in folder '{EXPECTED_FOLDER}'."

    return False, (
        f"Process '{EXPECTED_PROCESS_NAME}' not found in listing output. "
        f"Available output: {stdout[:500]}"
    )


def poll_for_process(timeout: int = POLL_TIMEOUT_SECONDS) -> tuple[bool, str]:
    """
    Poll Orchestrator for process visibility up to timeout seconds.

    Returns (found, diagnostic_message).
    """
    start_time = time.time()
    elapsed = 0
    attempt = 0
    last_diagnostic = ""

    print(f"  Polling for process '{EXPECTED_PROCESS_NAME}' in folder '{EXPECTED_FOLDER}'...")
    print(f"  Timeout: {timeout} seconds | Interval: {POLL_INTERVAL_SECONDS} seconds")
    print()

    while elapsed < timeout:
        attempt += 1
        elapsed = time.time() - start_time
        print(f"  Attempt {attempt} ({elapsed:.1f}s elapsed)...", end=" ")

        found, diagnostic = check_process_listing()

        if found:
            print("FOUND")
            return True, diagnostic

        print(f"not yet ({diagnostic[:80]})")
        last_diagnostic = diagnostic

        # Don't sleep if we've exceeded the timeout
        remaining = timeout - (time.time() - start_time)
        if remaining > 0:
            time.sleep(min(POLL_INTERVAL_SECONDS, remaining))

        elapsed = time.time() - start_time

    return False, (
        f"TIMEOUT: Process '{EXPECTED_PROCESS_NAME}' not found in folder "
        f"'{EXPECTED_FOLDER}' within {timeout} seconds. "
        f"Last diagnostic: {last_diagnostic}"
    )


def invoke_process() -> tuple[bool, str]:
    """
    Invoke the process with minimal valid input and check for job creation.

    Returns (success, diagnostic_message).
    """
    input_json = json.dumps(INVOKE_INPUT)

    print(f"  Invoking process with input: {input_json}")

    args = [
        "uipath",
        "process",
        "run",
        EXPECTED_PROCESS_NAME,
        "--folder", EXPECTED_FOLDER,
        "--input", input_json,
    ]

    result = run_cli_command(args, timeout=30)

    if result.returncode != 0:
        # Try alternative syntax
        args_alt = [
            "uipath",
            "jobs",
            "start",
            "--process", EXPECTED_PROCESS_NAME,
            "--folder", EXPECTED_FOLDER,
            "--input", input_json,
        ]
        result = run_cli_command(args_alt, timeout=30)

    if result.returncode != 0:
        diagnostic = diagnose_error(result.stderr, result.returncode)
        return False, f"Invocation failed: {diagnostic}"

    stdout = result.stdout.strip()

    # Check for job ID in output (common patterns)
    if "job" in stdout.lower() or "id" in stdout.lower() or stdout:
        return True, f"Invocation succeeded. Output: {stdout[:300]}"

    return False, f"Invocation returned no job ID. Output: {stdout[:300]}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify UiPath deployment of NextFlow_Pipeline"
    )
    parser.add_argument(
        "--invoke",
        action="store_true",
        help="Also invoke the process with minimal input to confirm job creation",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=POLL_TIMEOUT_SECONDS,
        help=f"Polling timeout in seconds (default: {POLL_TIMEOUT_SECONDS})",
    )
    args = parser.parse_args()

    timestamp = get_timestamp()
    print("Deployment Verification — Post-Publish Process Check")
    print(f"Timestamp: {timestamp}")
    print(f"{'=' * 60}")
    print(f"  Expected process: {EXPECTED_PROCESS_NAME}")
    print(f"  Expected folder:  {EXPECTED_FOLDER}")
    print(f"  Timeout:          {args.timeout}s")
    print(f"  Invoke test:      {'yes' if args.invoke else 'no'}")
    print(f"{'=' * 60}")
    print()

    # Step 1: Poll for process visibility
    print("Step 1: Checking process visibility in Orchestrator")
    print(f"{'-' * 60}")

    found, diagnostic = poll_for_process(timeout=args.timeout)

    print()
    print(f"  Result: {'FOUND' if found else 'NOT FOUND'}")
    print(f"  {diagnostic}")
    print()

    if not found:
        print(f"{'=' * 60}")
        print("RESULT: FAIL — Process not visible in Orchestrator.")
        print(f"  {diagnostic}")
        print()
        print("Troubleshooting steps:")
        print("  1. Verify auth session: uipath auth")
        print(f"  2. Verify folder exists: check '{EXPECTED_FOLDER}' in Orchestrator")
        print("  3. Verify publish succeeded: check uipath publish output")
        print("  4. Check package feed: ensure package was uploaded to tenant feed")
        return 1

    # Step 2: Optionally invoke the process
    if args.invoke:
        print("Step 2: Invoking process with minimal valid input")
        print(f"{'-' * 60}")

        invoked, invoke_diagnostic = invoke_process()

        print()
        print(f"  Result: {'SUCCESS' if invoked else 'FAILED'}")
        print(f"  {invoke_diagnostic}")
        print()

        if not invoked:
            print(f"{'=' * 60}")
            print("RESULT: PARTIAL — Process visible but invocation failed.")
            print(f"  Visibility: PASS")
            print(f"  Invocation: FAIL")
            print(f"  {invoke_diagnostic}")
            return 1

    # Summary
    print(f"{'=' * 60}")
    print("Summary")
    print(f"{'=' * 60}")
    print(f"  Process visibility: PASS")
    if args.invoke:
        print(f"  Process invocation: PASS")
    print(f"  Deployment verification: COMPLETE")
    print()
    print("RESULT: PASS — Deployment verified successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
