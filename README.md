# NextFlow — Deterministic Pipeline Processing

**See the result before you apply it. No guessing. No surprises.**

## Project Description

NextFlow solves the problem of unverified AI-generated configuration repairs reaching production. AI can propose fixes fast, but enterprises need **proof** that one exact result is safe and **explicit human authority** before applying it.

NextFlow enforces a deterministic 8-phase pipeline: Snapshot → Scan → Analysis → Pre-Simulation → Simulation → Inspection → Relay → Final Output. Each phase must pass exit validation before the next begins. The pipeline produces cryptographic execution traces as proof-of-work.

## UiPath Components

| Component | Role in NextFlow |
|-----------|-----------------|
| **Maestro BPMN** | End-to-end workflow orchestration and gateway enforcement |
| **Coded Agents** | Advisory classification, analysis, and recalibration (Python) |
| **API Workflows** | Snapshot capture, replay proof, post-apply verification |
| **RPA Workflows** | Isolated simulation and exact-result apply relay |
| **Action Center** | Human-in-the-loop Apply/Cancel/Preserve decision |
| **UiPath Storage** | Immutable input snapshots and proof artifacts |

## Agent Type

**Coded Agents** — The pipeline engine and all phase logic are implemented as Python coded agents using the UiPath Python SDK Function pattern.

## Setup Instructions

**Requires:** [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)

```powershell
# Clone
git clone https://github.com/itz1508/hackathon-uipath.git
cd hackathon-uipath

# Run (handles venv + deps automatically)
./run.ps1
```

Or double-click `run.bat`.

The script runs 3 steps:
1. Plays demo video (Audisor execution flow)
2. Shows 12-slide presentation + runs live pipeline + opens execution evidence
3. Opens interactive test menu (judge runs tests)

**Manual single test:**
```powershell
.venv\Scripts\python.exe system\pipeline\_run_e2e.py system\cases\sample-config-repair\source
```

Expected: `Status: succeeded`, 8/8 phases, `completion_status: fully_resolved`

## UiPath Labs Environment

https://staging.uipath.com/hackathon26_802/

## Live Evidence

https://itz1508.github.io/hackathon-uipath/

## Team

**The OneShot** — Minh Le — cs1508.4ever@gmail.com — Apache License 2.0
