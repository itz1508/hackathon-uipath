# NextFlow — Deterministic Pipeline Processing

> **Live demo & reports:** [itz1508.github.io/hackathon-uipath](https://itz1508.github.io/hackathon-uipath/)

NextFlow is a UiPath AgentHack **Track 2: UiPath Maestro BPMN** project. It coordinates AI-assisted configuration analysis, deterministic admission, isolated simulation, replay proof, an exact-result human approval boundary, controlled apply, and post-apply verification.

The repository contains two Maestro processes:

- `NextFlow-Demo.bpmn` — dependency-free process structure plus a deterministic local runner for the sample configuration repair.
- `NextFlow-RealCase.bpmn` — the cloud submission topology with registry-valid binding points for Agent Builder, API Workflows, RPA, Action Center, and storage-backed artifacts.

## Business problem

Enterprise configuration repairs are often generated faster than teams can prove they are safe. NextFlow prevents advisory AI output from becoming mutation authority. It retains one exact simulated result, asks a human to approve that result ID/hash/target, applies only that result, and reports drift or failure without silent repair.

## UiPath components

| Component | Responsibility | Current state |
|---|---|---|
| Maestro BPMN | End-to-end orchestration and gateways | Implemented and locally validated |
| Script Tasks | Deterministic state, admission, and final lock | Implemented in BPMN |
| Agent Builder/coded agent | Advisory classification and recalibration | Binding required |
| API Workflows | Snapshot, replay proof, verification | Bindings required |
| RPA workflows | Isolated simulation and exact apply relay | Bindings required |
| Action Center | Apply, cancel, preserve-for-later authority | Binding required |
| UiPath storage | Immutable inputs and proof artifacts | Binding required |
| Codex via UiPath for Coding Agents | CLI-driven authoring and validation | Used during development; cloud demonstration still required |

## Prerequisites

- Node.js 18 or newer and npm.
- Python 3.11 or newer with `pytest` and `jsonschema`.
- `@uipath/cli` and `@uipath/maestro-tool`.
- UiPath Automation Cloud/Labs access for discovery, binding, debug, and deployment.

## Quick start (Try it out)

```powershell
# Clone and enter
git clone https://github.com/itz1508/hackathon-uipath.git
cd hackathon-uipath

# Option A: One-click (sets up everything automatically)
.\run.ps1          # PowerShell
# or
run.bat            # CMD / double-click

# Option B: Manual
uv venv .venv --python 3.11
uv pip install pydantic --python .venv\Scripts\python.exe
.venv\Scripts\python.exe pipeline\_run_e2e.py cases\sample-config-repair\source
```

Expected output: `Status: succeeded`, 8/8 phases completed, `completion_status: fully_resolved`.

## Validate and run

```powershell
.\scripts\validate.ps1
.\scripts\debug-demo.ps1 -Decision apply
.\scripts\pack.ps1 -Version 1.0.0
.\scripts\verify-package.ps1
```

The local runner writes run-specific sandbox/live-target artifacts only under the user temp directory. It never modifies `cases/sample-config-repair/source/application-config.json`.

## Cloud completion status

The BPMN files are importable and packageable only to the extent proven by the commands reported in this repository. `NextFlow-RealCase.bpmn` deliberately contains `BIND REQUIRED` markers because no authenticated Automation Cloud resource discovery was available during offline authoring. It is not operational until [the binding procedure](docs/bind-real-case.md) is completed and a cloud instance is executed.

## Documentation

- [Architecture](docs/architecture.md)
- [Run the demo](docs/run-demo.md)
- [Import to UiPath](docs/import-to-uipath.md)
- [Bind the real case](docs/bind-real-case.md)
- [Deploy to Orchestrator](docs/deploy-orchestrator.md)
- [Hackathon demo script](docs/hackathon-demo-script.md)

## Team

**The OneShot**

- **Author:** Minh Le — cs1508.4ever@gmail.com
- **License:** Apache License 2.0
- **Copyright © 2026 The OneShot**
