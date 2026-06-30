# NextFlow — Deterministic Pipeline Processing

> **Live reports:** [itz1508.github.io/hackathon-uipath](https://itz1508.github.io/hackathon-uipath/)

See the result before you apply it. No guessing. No surprises.

**Team:** The OneShot | **Author:** Minh Le | **Track:** UiPath Maestro BPMN

---

## 3 Steps to Try

### Step 1 — Run the pipeline

```powershell
.\run.ps1
```
Or double-click `run.bat`. Auto-installs Python 3.11 venv + pydantic, then runs the full 8-phase pipeline.

**You'll see:**
```
Phase 0 (snapshot) completed
Phase 1 (scan) completed
Phase 2 (analysis) completed
Phase 3 (pre_simulation) completed
Phase 4 (simulation) completed
Phase 5 (inspection) completed
Phase 6 (relay) completed
Phase 7 (final_output) completed

Status: succeeded
completion_status: fully_resolved
```

### Step 2 — View the presentation

Open in browser: [`docs/deck.html`](docs/deck.html)

10 slides covering problem, solution, architecture, safety contract, demo results, and UiPath components.

### Step 3 — Review execution evidence

Open in browser: [`docs/reports/pipeline-report.html`](docs/reports/pipeline-report.html)

Visual report with phase timings, scoring breakdown, isolation results, and final locked state.

More reports in `docs/reports/`:
- `ab_pipeline_demo.html` — A/B isolation comparison
- `ab_harness_report.html` — 5-fixture experiment
- `edge_scan_report.html` — admission gate scoring
- `resolution_report.html` — final resolution breakdown

---

## What is NextFlow?

AI generates configuration fixes fast. Proving one exact result is safe — that's the bottleneck.

NextFlow solves this with an 8-phase deterministic pipeline:

1. **Snapshot** — hash the target (read-only)
2. **Scan** — detect issues
3. **Analysis** — AI classifies (advisory only, zero authority)
4. **Pre-Simulation** — deterministic admission gate (≥93.91% confidence required)
5. **Simulation** — execute fix in isolated sandbox
6. **Inspection** — verify convergence
7. **Relay** — human decision (Apply/Cancel via Action Center)
8. **Final Output** — locked immutable record

AI recommends. Gates admit. Humans authorize. Nothing else mutates production.

---

## Repository Structure

```
/                       ← You are here
├── run.ps1, run.bat    ← One-click pipeline runner
├── README.md           ← This file
├── docs/               ← Presentation deck + proof reports (HTML)
├── pipeline/           ← 8-phase engine source code
├── submission/         ← DevPost materials
└── system/             ← Internal: contracts, tests, schemas, BPMN
```

---

**License:** Apache 2.0 | **Copyright © 2026 The OneShot**
