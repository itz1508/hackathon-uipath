# NextFlow — Deterministic Pipeline Processing

**See the result before you apply it. No guessing. No surprises.**

AI generates config fixes fast — but proving one exact result is safe requires deterministic admission, isolated simulation, cryptographic proof, and human authority. NextFlow enforces all four.

## How to Run

**Requires:** Python 3.11+, [uv](https://docs.astral.sh/uv/getting-started/installation/)

```powershell
git clone https://github.com/itz1508/hackathon-uipath.git
cd hackathon-uipath
./run.ps1
```

Or double-click `run.bat`.

The script runs three demos back-to-back:

| Step | Input | Expected Result |
|------|-------|-----------------|
| 1 | Clean config (1 issue) | `fully_resolved` — 1 resolved, 0 unresolved |
| 2 | Mixed severity (3 issues) | `partially_resolved` — 3 resolved, 1 unresolved |
| 3 | Chaos (10 failure types) | `partially_resolved` — 6 resolved, 3 unresolved |

Each step runs the full 8-phase pipeline: Snapshot → Scan → Analysis → Pre-Simulation → Simulation → Inspection → Relay → Final Output.

## Live Reports

[itz1508.github.io/hackathon-uipath](https://itz1508.github.io/hackathon-uipath/)

## Team

**The OneShot** — Minh Le — cs1508.4ever@gmail.com — Apache License 2.0
