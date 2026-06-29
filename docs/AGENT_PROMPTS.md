# Agent Prompts & Configurations

<!-- Modified: 2026-06-28T18:00:00Z -->

## Overview

The NextFlow system uses multiple AI agent configurations to orchestrate code analysis, fixing, and deployment tasks. This document catalogues the agents that participate in the system, their configuration sources, and their roles.

---

## 1. Root Agent Authority — `AGENTS.md`

**Source:** [`AGENTS.md`](../AGENTS.md) (repository root)

**Role:** System-wide operating rules and authority for all AI agents working in this repository.

**Summary of configuration:**

- Defines the validated runtime chain: `isolated-integration → workbench_backend → pipeline`
- Establishes layer responsibilities (Pipeline, Backend, UiPath Bridge)
- Documents canonical phase names (Phases 0–6)
- Specifies the frozen API contract location (`workbench_backend/contract.json`)
- Enforces operating principles:
  - *Read Wide, Act Narrow* — read any file, write only within task scope
  - *Dirty Worktree Disclosure* — acknowledge uncommitted changes before mutations
  - *Timestamp Requirement* — ISO 8601 UTC timestamp in every created/modified file
  - *No Hybrid BPMN* — no mixing coded-workflow logic with BPMN activities
- Lists forbidden actions (e.g., no manual `bindings_v2.json` edits, no E2E claims without evidence)
- Identifies historical/stale references agents should not bootstrap from
- Provides test commands for contract verification, fixture regression, and backend tests

---

## 2. Agent Onboarding Guide — `.agent-onboarding.md`

**Source:** [`.agent-onboarding.md`](../.agent-onboarding.md) (repository root)

**Role:** Quick-reference onboarding document for newly bootstrapped agents.

**Summary of configuration:**

- Describes the project as a 7-phase pipeline with human approval at Phase 5 (Relay)
- Reiterates the runtime chain and component entry points
- Lists prerequisite reading before modifications (AGENTS.md, pipeline/main.py)
- Documents the API submission contract (legacy `POST /execute` and bridge-compatible `POST /v1/executions`)
- Identifies known issues that agents should not attempt to fix (e.g., UiPath Studio Web bindings)

---

## 3. Coding Agent — `coding-agent/main.py`

**Source:** [`coding-agent/main.py`](../coding-agent/main.py)

**Role:** UiPath Coded Function that wraps AI coding capabilities (Claude Code CLI or Anthropic API) to automatically fix code issues during Pipeline Phase 3 (Simulation).

**Invocation:** Called by the pipeline via `uipath run main <json>` during simulation phase.

**Agent prompt strategy:**

The coding agent builds a focused fix prompt containing:
- Issue category and severity
- File path and full content
- Root cause description and known facts
- Explicit instruction: "Fix the identified issue. Do not make unrelated changes. Return the complete fixed file content."

**Execution backends (tried in order):**

1. **Claude Code CLI** — invoked if `claude` binary is on PATH and `ANTHROPIC_API_KEY` is set. Confidence: 0.85 on success.
2. **Anthropic API** — invoked directly via the `anthropic` Python package if API key is available. Confidence: 0.85 on success.
3. **Deterministic Heuristics** — rule-based fallback for common patterns (syntax errors, missing imports, broken dependencies, circular imports). Confidence: 0.60 on success.

**Input/Output schema:** Defined in [`coding-agent/entry-points.json`](../coding-agent/entry-points.json) as a UiPath coded function entry point.

---

## 4. Kiro Spec System — `.kiro/specs/`

**Source:** [`.kiro/specs/`](../.kiro/specs/)

**Role:** Structured feature specifications that guide Kiro (the development environment agent) through requirements, design, and implementation tasks.

**Active specs:**

| Spec | Type | Purpose |
|------|------|---------|
| `submission-canonicalization` | feature | Creates the judge-facing presentation layer over the runtime chain |
| `snapshot-permissions-fix` | — | Addresses snapshot permission issues |
| `uipath-isolated-integration` | — | UiPath Function integration spec |

**Configuration format:** Each spec contains:
- `.config.kiro` — spec metadata (ID, workflow type, spec type)
- `requirements.md` — acceptance criteria and user stories
- `design.md` — architecture, components, data models, testing strategy
- `tasks.md` — implementation plan with task dependencies

---

## 5. Kiro Hooks — `.kiro/hooks/`

**Source:** [`.kiro/hooks/`](../.kiro/hooks/)

**Role:** Event-driven automation hooks for the Kiro development environment.

**Current state:** No hooks are currently configured. This directory is reserved for future file-edit, prompt-submit, or tool-use hooks that automate agent actions based on IDE events.

---

## Agent Interaction Model

```
┌─────────────────────────────────────────────────────┐
│  Developer / Judge                                  │
│  (triggers via API, CLI, or UiPath Orchestrator)    │
└────────────────────┬────────────────────────────────┘
                     │
        ┌────────────▼────────────────┐
        │  UiPath Bridge              │
        │  (isolated-integration)     │
        │  HTTP polling orchestration  │
        └────────────┬────────────────┘
                     │ HTTP
        ┌────────────▼────────────────┐
        │  Workbench Backend          │
        │  (FastAPI, port 8790)       │
        │  Execution management       │
        └────────────┬────────────────┘
                     │ Python call
        ┌────────────▼────────────────┐
        │  Pipeline (Phases 0–6)      │
        │  Phase 3: Simulation        │
        │       │                     │
        │       ▼                     │
        │  Coding Agent               │
        │  (Claude Code / API /       │
        │   Deterministic fallback)   │
        └─────────────────────────────┘

AI Agent Governance:
  • AGENTS.md — rules for ALL agents
  • .agent-onboarding.md — bootstrap guide
  • .kiro/specs/ — task-level guidance for Kiro
```

---

## Summary

| Agent / Config | Source File | Primary Role |
|----------------|-------------|--------------|
| System Authority | `AGENTS.md` | Operating rules, forbidden actions, runtime chain definition |
| Agent Onboarding | `.agent-onboarding.md` | Quick bootstrap guide for new agent sessions |
| Coding Agent | `coding-agent/main.py` | AI-powered code fixing during Pipeline Phase 3 |
| Kiro Specs | `.kiro/specs/` | Feature specification and task orchestration |
| Kiro Hooks | `.kiro/hooks/` | Event-driven automation (currently empty) |
