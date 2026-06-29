"""EventAwareEngine — wraps PipelineEngine to emit events on the EventBus."""
from __future__ import annotations

import time
from typing import Any

from pipeline.events.bus import Event, EventBus, EventType


class EventAwareEngine:
    """Wraps a PipelineEngine and emits events for each phase."""

    def __init__(self, engine: Any, bus: EventBus) -> None:
        self._engine = engine
        self._bus = bus

    def run(self) -> Any:
        state = self._engine.state
        pipeline_id = getattr(state, "run_id", "unknown")
        fixture_path = getattr(state, "fixture_path", "")
        isolation_mode = getattr(state, "isolation_mode", False)

        # Emit PIPELINE_START
        self._bus.publish(Event(
            sequence_id=0,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            pipeline_id=pipeline_id,
            phase="PIPELINE",
            event_type=EventType.PIPELINE_START,
            payload={"pipeline_id": pipeline_id, "fixture_path": fixture_path, "isolation_mode": isolation_mode},
        ))

        # Run phases
        from pipeline.events.bus import PHASES
        for phase_idx, phase_func in enumerate(self._engine._phases):
            phase_name = PHASES[phase_idx] if phase_idx < len(PHASES) else f"PHASE_{phase_idx}"

            self._bus.publish(Event(
                sequence_id=0,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                pipeline_id=pipeline_id,
                phase=phase_name,
                event_type=EventType.PHASE_START,
                payload={"phase_id": phase_idx, "phase_name": phase_name},
            ))

            t0 = time.perf_counter()
            try:
                state = phase_func(state)
                duration_ms = (time.perf_counter() - t0) * 1000
                status = "success"
            except Exception as e:
                duration_ms = (time.perf_counter() - t0) * 1000
                status = "failed"

            self._bus.publish(Event(
                sequence_id=0,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                pipeline_id=pipeline_id,
                phase=phase_name,
                event_type=EventType.PHASE_END,
                payload={"phase_id": phase_idx, "phase_name": phase_name, "status": status, "duration_ms": duration_ms},
            ))

            if status == "failed":
                break

        # Emit PIPELINE_COMPLETE
        self._bus.publish(Event(
            sequence_id=0,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            pipeline_id=pipeline_id,
            phase="PIPELINE",
            event_type=EventType.PIPELINE_COMPLETE,
            payload={"status": "success" if status == "success" else "failed", "last_phase_index": phase_idx, "phases_executed": phase_idx + 1},
        ))

        self._engine.state = state
        return state
