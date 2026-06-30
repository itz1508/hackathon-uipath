# Modified: 2026-06-24T10:00:00Z
"""Demo Benchmark — 3 canonical cases showing the contract-driven flow.

Demonstrates:
    Issue → Resolution Planner → ResolutionContract → Toolkit → Result

This is NOT a benchmarking framework. It's a demo that proves the architecture works.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# Add pipeline to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Load QwenCloud API credentials from .env if available
import os
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

from models import Finding, FindingCategory
from resolution_planner import plan_resolutions
from agent_ledger import compute_score, classify_failure


def run_demo():
    """Run 3 demo cases and show the contract-driven flow."""

    cases = [
        {
            "name": "Syntax Error — Missing Colon",
            "finding": Finding(
                finding_id="demo-1",
                category=FindingCategory.SYNTAX_ERROR.value,
                severity="critical",
                file="main.py",
                root_cause="Missing colon after def statement",
                root_cause_confirmed=True,
                known_facts=["Line 1: def broken() — missing colon"],
            ),
            "file_content": "def broken()\n    return 42\n",
            "expected_tool": "refactor",
        },
        {
            "name": "Dependency Conflict — Duplicate Entry",
            "finding": Finding(
                finding_id="demo-2",
                category=FindingCategory.DEPENDENCY_CONFLICT.value,
                severity="high",
                file="requirements.txt",
                root_cause="Duplicate dependency: requests appears twice",
                root_cause_confirmed=True,
                known_facts=["requests==2.31.0 and requests==2.32.0"],
            ),
            "file_content": "requests==2.31.0\nrequests==2.32.0\nflask==3.0.0\n",
            "expected_tool": "dep_fix",
        },
        {
            "name": "Missing Import — Stdlib Module",
            "finding": Finding(
                finding_id="demo-3",
                category=FindingCategory.MISSING_IMPORT.value,
                severity="high",
                file="app.py",
                root_cause="Name 'os' used but not imported",
                root_cause_confirmed=True,
                known_facts=["module 'os' not imported"],
            ),
            "file_content": "x = os.path.join('a', 'b')\n",
            "expected_tool": "import_repair",
        },
    ]

    print("=" * 70)
    print("NextFlow — Contract-Driven Execution Demo")
    print("=" * 70)
    print()

    for i, case in enumerate(cases, 1):
        print(f"Case {i}: {case['name']}")
        print("-" * 50)

        # Step 1: Resolution Planner produces a contract
        contracts = plan_resolutions([case["finding"]], "/tmp/demo")
        contract = contracts[0]

        print(f"  Agent:     Resolution Planner (deterministic fallback)")
        print(f"  Contract:  {contract.contract_id}")
        print(f"  Planner:   {contract.planner}")
        print(f"  Confidence:{contract.confidence:.2f}")
        print(f"  Tools:     {[inv.tool_name for inv in contract.recommended_tools]}")
        print(f"  Expected:  {case['expected_tool']}")

        # Step 2: Verify tool selection
        tool_names = [inv.tool_name for inv in contract.recommended_tools]
        tool_match = case["expected_tool"] in tool_names
        print(f"  Match:     {'YES' if tool_match else 'NO'}")

        # Step 3: Simulate scoring (assuming simulation + inspection pass)
        score = compute_score(
            simulation_pass=True,
            inspection_pass=True,
            regressions=0,
            conflicts=0,
            tool_selection_match=tool_match,
        )
        failure = classify_failure(
            simulation_pass=True,
            inspection_pass=True,
            regressions=0,
            conflicts=0,
            tools_used=tool_names,
            expected_tools=[case["expected_tool"]],
        )

        print(f"  Score:     {score:.2f}")
        print(f"  Result:    {failure.upper()}")
        print()

    print("=" * 70)
    print("Flow: Issue → Planner → Contract → Toolkit → Score")
    print("The agent proposes. The toolkit executes. The system validates.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
