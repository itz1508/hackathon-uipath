# Audisor Demo Video Script

> **Duration:** 5 minutes maximum  
> **Resolution:** 1920×1080  
> **Theme:** Dark on all visible UIs  
> **Format:** Screen recording with voiceover narration

---

## [0:00–0:30] Introduction

**Narration:**

> "Audisor completes the work BEFORE the user commits to it. The result is ready before the user decides — you see exactly what was resolved and what was not, instantly."

**Architecture overview (one sentence per subsystem):**

- **BPMN Agentic Process** — orchestrates the end-to-end run in UiPath Automation Cloud with gateway-based success/failure routing.
- **API Workflow Bridge** — translates between UiPath's service task invocation and the Edge Backend HTTP API, normalizing every response.
- **Edge Backend** — FastAPI execution engine with a phase-locked pipeline (Phases 0–6), correlation tracking, and SSE streaming.
- **Phase Controller** — state machine enforcing strict phase ordering, branch authorization, and convergence.
- **PreSimulation Evaluator Agent** — Claude-based coded agent scoring information completeness against the 93.91% threshold.
- **Operator Dashboard** — PySide6 dark-themed UI showing real-time pipeline status, findings, and the human-in-the-loop relay decision.

**On-screen:** Show the architecture diagram (Mermaid from README) briefly while narrating.

---

## [0:30–1:00] BPMN Process Start (Track 2 Requirement)

**Narration:**

> "We start from a BPMN process running in UiPath Automation Cloud. This is Track 2 — agentic processes orchestrated through BPMN."

**Actions to show:**

1. Open the BPMN process definition in UiPath Automation Cloud
2. Point out the flow: **Start Event → Service Task (API Workflow Bridge) → Exclusive Gateway → End Events**
3. Highlight the 7 process input arguments mapped to the Service Task (backend_base_url, request_id, case_id, task_ref, idempotency_key, correlation_id, payload)
4. Trigger the process with pre-populated test inputs
5. Show the process instance starting — note the instance ID in the job log

**Key point:** The BPMN process invokes the API Workflow with `waitForCompletion=true` — it blocks until the entire pipeline finishes.

---

## [1:00–2:00] API Workflow Bridge Executing

**Narration:**

> "The Service Task invokes our API Workflow. This is the bridge between UiPath's cloud orchestration and our Edge Backend. Watch the correlation ID flow through every layer."

**Actions to show:**

1. Show the API Workflow running in UiPath (job execution view)
2. Highlight the initial POST to Edge Backend `/v1/executions`:
   - Headers: `X-Correlation-Id`, `Idempotency-Key`
   - Body: target path, payload, request metadata
3. Show the 202 Accepted response with `execution_id`
4. Show the polling loop:
   - GET `/v1/executions/{id}` at 2-second intervals
   - Status transitions visible: `ACCEPTED → QUEUED → RUNNING → ...`
5. Point out the correlation ID appearing in Edge Backend logs — same value as sent from BPMN

**Key point:** The bridge guarantees exactly one normalized BridgeOutput on every code path. No silent failures.

---

## [2:00–3:00] Edge Pipeline Processing (Phases 0–4)

**Narration:**

> "Now we switch to the Operator Dashboard to watch the pipeline execute in real time. Each phase produces verifiable output before the next can begin."

**Actions to show on Operator Dashboard:**

1. **Phase 0 — Snapshot captured:**
   - All files hashed (SHA-256)
   - File count and hash summary displayed
   - "Restore point is now available for the entire pipeline"

2. **Phase 1 — Scan + Analysis:**
   - "Three statements produced: Handoff, LLM, Pre-calibration"
   - Show the Findings Review screen with classification results

3. **Phase 2 — Pre-simulation scoring:**
   - Show the evaluator running
   - Score displayed: **93.91%** (at threshold — passes)
   - Show partitioning: "Ready for Simulation: N items, Awaiting Information: 0 items"
   - Mention: "Exactly 93.91% passes. 93.90% does not. This is an information completeness gate, not a quality gate."

4. **Phase 3 — Simulation:**
   - "All mutation happens here — on the candidate copy, never the real target"
   - Show status updating to "running" then "completed"

5. **Phase 4 — Inspection:**
   - "Convergence of all branches — simulation results, any isolation reports"
   - "Inspection waits for ALL paths before proceeding"
   - Show validation and hash computation completing

**On-screen:** Phase Status display updating via SSE in real time. Each phase card transitions from pending → running → completed.

---

## [3:00–4:00] Human-in-the-Loop Decision (Key Moment)

**Narration:**

> "This is the key moment. The work is done. You are not looking at a problem waiting to be fixed — you are looking at a fix waiting to be accepted."

**Actions to show on Relay Decision screen:**

1. Show the pipeline pausing at Phase 5 (Relay) — status: "awaiting_user_approval"
2. Show the before/after diff displayed instantly:
   - **Snapshot state** (original) vs **Candidate Copy state** (simulation result)
   - Full file-level diff visible
3. Show the issue summary:
   - **Resolved issues** (green section) — these are fixed and ready
   - **Unresolved issues** (red section) — with full explanation of why
4. Narrate: "The user sees the complete picture at the moment of decision. No digging through logs."

**Decision — Apply path:**

5. Operator clicks **"Apply"**
6. Show the pipeline resuming:
   - Pre-apply hash verification runs (integrity check)
   - Simulation-proven result released to real target folder
   - Post-apply verification: **zero drift confirmed**
7. Narrate: "Apply is not mutation. The work was done in simulation. Apply delivers it."

**Mention Cancel path:**

> "If the operator clicks Cancel instead, the snapshot restores the original files — exactly as attached, clean, no trace. The user is never at risk either way."

---

## [4:00–4:30] Agent Builder Evaluation

**Narration:**

> "Let's look at the PreSimulation Evaluator Agent in UiPath Agent Builder. This is the coded agent that enforces the 93.91% information completeness threshold."

**Actions to show:**

1. Open the PreSimulation Evaluator Agent definition in UiPath Agent Builder
2. Show the evaluation set with test cases:
   - **Passing case:** Score 98.2% — clearly above threshold, proceeds to simulation
   - **Boundary pass:** Score exactly 93.91% — passes (>= 93.91)
   - **Boundary fail:** Score exactly 93.90% — does NOT pass
   - **Critical blocker:** High score but missing snapshot hash — blocked regardless
3. Run the evaluation set — show `agent_evaluation_score` achieving 93.91%+
4. Narrate: "The agent has everything it needs for one-shot success. No back-and-forth. No clarifying questions."

---

## [4:30–5:00] Final Output and Wrap-up

**Narration:**

> "Every execution produces a complete report. Nothing is silent. Nothing is skipped."

**Actions to show:**

1. Show Phase 6 final output:
   - `resolved.html` — full resolved diff report
   - Total issues found (integer count)
   - Root cause per issue
   - Handoff report
2. Narrate: "This report is complete enough that another agent can pick it up and continue the work. That's by design."

**Recap key design decisions (on-screen bullet points):**

- **Phase locking prevents agent bypass** — the agent never controls transitions
- **Candidate copy protects real files** — mutation only in simulation
- **Pipeline never stops** — isolation is information gap, not failure
- **93.91% = one-shot success threshold** — information completeness, not quality
- **Every path produces a report** — no silent outcomes, ever

**Closing:**

> "Audisor: the work is done before you decide. Thank you."

---

## Recording Notes

### Environment Setup (Before Recording)

- [ ] Edge Backend running and healthy (`GET /health` returns 200)
- [ ] Operator Dashboard launched with dark theme
- [ ] BPMN process published in UiPath Automation Cloud
- [ ] API Workflow deployed and accessible
- [ ] PreSimulation Evaluator Agent configured in Agent Builder
- [ ] Test data pre-populated (target folder with known issues)
- [ ] Use a fresh execution for each recorded attempt
- [ ] Correlation ID pre-generated for traceability demo

### Technical Requirements

- **Resolution:** 1920×1080
- **Theme:** Dark on ALL visible UIs (Dashboard, terminal, browser)
- **Frame rate:** 30fps minimum
- **Audio:** Clear voiceover, no background noise
- **Duration:** Strict 5-minute maximum

### Demo Flow Tips

- Pre-populate test data so no waiting during recording
- Use a folder with 3–5 known issues for clear demonstration
- Ensure the evaluator scores ≥93.91% on first pass (no isolation path in main demo)
- If demonstrating the Apply path, verbally mention that Cancel restores from snapshot
- Keep terminal/logs visible but not the primary focus — Dashboard is the star
- Practice the narration timing: each section has strict time allocation

### Contingency

- If the pipeline takes longer than expected, fast-forward in editing (note the cut point)
- If Edge Backend is slow to respond, mention "in a production run, this completes in seconds"
- Have a pre-recorded backup of the pipeline execution available as fallback
- If SSE drops connection during recording, the Dashboard shows "connection lost" gracefully — this demonstrates resilience

### Files to Have Open

1. UiPath Automation Cloud — BPMN process view
2. UiPath Automation Cloud — API Workflow job view
3. Operator Dashboard — Phase Status screen
4. Operator Dashboard — Relay Decision screen
5. UiPath Agent Builder — Evaluator Agent evaluation results
6. Terminal — Edge Backend logs (for correlation ID visibility)
