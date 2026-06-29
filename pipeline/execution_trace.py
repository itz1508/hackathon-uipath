# Modified: 2026-06-24T08:30:00Z
"""Execution Trace Capture — self-documenting pipeline proof-of-work.

Records every phase's intent, action, result, duration, and evidence
into a structured narrative that proves the AI agent's reasoning.

Usage:
    from execution_trace import ExecutionTracer

    tracer = ExecutionTracer(case_id="DEMO-001", execution_id="exec-abc")
    tracer.before(phase=0, intent="Capture snapshot of target folder")
    # ... do work ...
    tracer.after(phase=0, result="Hashed 12 files", confidence=1.0, evidence="snapshot_id=abc123")
    tracer.save()  # writes to proof/execution_trace_<id>.json
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ExecutionTracer:
    """Captures structured execution narrative for proof-of-work."""

    def __init__(self, case_id: str, execution_id: str, output_dir: str | None = None):
        self.case_id = case_id
        self.execution_id = execution_id
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.steps: list[dict[str, Any]] = []
        self._step_counter = 0
        self._phase_starts: dict[int, float] = {}
        self._output_dir = Path(output_dir) if output_dir else (
            Path(__file__).resolve().parent.parent / "proof"
        )

    def before(self, phase: int, intent: str) -> None:
        """Record intent BEFORE executing a phase."""
        self._step_counter += 1
        self._phase_starts[phase] = time.perf_counter()
        self.steps.append({
            "step": self._step_counter,
            "type": "before",
            "phase": phase,
            "intent": intent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def after(
        self,
        phase: int,
        result: str,
        confidence: float = 1.0,
        evidence: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record result AFTER executing a phase."""
        start_time = self._phase_starts.pop(phase, time.perf_counter())
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        entry: dict[str, Any] = {
            "step": self._step_counter,
            "type": "after",
            "phase": phase,
            "result": result,
            "confidence": confidence,
            "duration_ms": duration_ms,
            "evidence": evidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if details:
            entry["details"] = details
        self.steps.append(entry)

    def note(self, phase: int, message: str) -> None:
        """Record an informational note during execution."""
        self.steps.append({
            "step": self._step_counter,
            "type": "note",
            "phase": phase,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def build_narrative(self) -> dict[str, Any]:
        """Build the complete execution narrative."""
        ended_at = datetime.now(timezone.utc).isoformat()

        # Build human-readable summary from after steps
        summary_lines: list[str] = []
        for step in self.steps:
            if step["type"] == "before":
                summary_lines.append(f"Phase {step['phase']}: {step['intent']}")
            elif step["type"] == "after":
                summary_lines.append(
                    f"  → {step['result']} "
                    f"(confidence={step['confidence']}, {step['duration_ms']}ms)"
                )

        return {
            "execution_id": self.execution_id,
            "case_id": self.case_id,
            "started_at": self.started_at,
            "ended_at": ended_at,
            "total_steps": self._step_counter,
            "execution_narrative": self.steps,
            "human_readable_summary": "\n".join(summary_lines),
        }

    def save(self) -> str:
        """Save the narrative to a JSON file. Returns the file path."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"execution_trace_{self.execution_id[:8]}.json"
        output_path = self._output_dir / filename

        narrative = self.build_narrative()
        output_path.write_text(
            json.dumps(narrative, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        return str(output_path)


def trace_phase_result(tracer: ExecutionTracer, phase: int, phase_result: Any) -> None:
    """Helper: extract meaningful info from a PhaseResult and record it."""
    outputs = getattr(phase_result, "required_outputs", {})
    exit_status = getattr(phase_result, "exit_status", "unknown")
    duration = getattr(phase_result, "duration_ms", 0)

    if phase == 0:
        file_count = len(outputs.get("file_hashes", {}))
        snapshot_id = outputs.get("snapshot_id", "")[:12]
        tracer.after(
            phase=0,
            result=f"Snapshot captured: {file_count} files hashed",
            confidence=1.0,
            evidence=f"snapshot_id={snapshot_id}",
        )
    elif phase == 1:
        total = outputs.get("total_issues", 0)
        critical = outputs.get("critical_count", 0)
        tracer.after(
            phase=1,
            result=f"Scan complete: {total} issues found ({critical} critical)",
            confidence=1.0,
            evidence=outputs.get("handoff_statement", "")[:100],
        )
    elif phase == 2:
        score = outputs.get("package_confidence_score", 0)
        ready = len(outputs.get("ready_parts", []))
        isolated = len(outputs.get("isolated_parts", []))
        tracer.after(
            phase=2,
            result=f"Scored {score}%. {ready} ready, {isolated} isolated",
            confidence=score / 100.0 if score else 0,
            evidence=f"threshold=93.91%, simulation_ready={outputs.get('simulation_ready', False)}",
        )
    elif phase == 3:
        sim = outputs.get("simulation_result", {})
        resolved = len(sim.get("resolved_items", [])) if isinstance(sim, dict) else 0
        failed = len(sim.get("failed_items", [])) if isinstance(sim, dict) else 0
        tracer.after(
            phase=3,
            result=f"Simulation: {resolved} resolved, {failed} failed",
            confidence=0.95 if resolved > 0 else 0.5,
            evidence=f"candidate_path={sim.get('candidate_path', 'N/A')}" if isinstance(sim, dict) else "",
        )
    elif phase == 4:
        status = outputs.get("convergence_status", "unknown")
        tracer.after(
            phase=4,
            result=f"Inspection: convergence={status}",
            confidence=1.0 if status == "converged" else 0.7,
            evidence=f"exit_status={exit_status}",
        )
    elif phase == 5:
        decision = outputs.get("decision", "unknown")
        tracer.after(
            phase=5,
            result=f"Relay decision: {decision}",
            confidence=1.0,
            evidence=f"decision={decision}",
        )
    elif phase == 6:
        resolved_count = outputs.get("resolved_count", 0)
        unresolved_count = outputs.get("unresolved_count", 0)
        tracer.after(
            phase=6,
            result=f"Final: {resolved_count} resolved, {unresolved_count} unresolved",
            confidence=1.0,
            evidence="final_output produced",
            details={"resolved_count": resolved_count, "unresolved_count": unresolved_count},
        )
    else:
        tracer.after(
            phase=phase,
            result=f"Phase {phase} completed: {exit_status}",
            confidence=1.0,
            evidence=f"duration_ms={duration}",
        )
