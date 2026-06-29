"""TerminalViewer — event-to-frame reducer for pipeline visualization."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from pipeline.events.bus import Event, EventBus, EventType

logger = logging.getLogger(__name__)


@dataclass
class TerminalLayout:
    columns: int = 80
    rows: int = 24


@dataclass
class Section:
    section_type: str  # header, phases, score, findings, isolation, event_stream, tool_detail
    content: dict[str, Any] = field(default_factory=dict)


@dataclass
class PhaseInfo:
    phase_id: int
    phase_name: str
    status: str = ""
    duration_ms: float = 0.0


@dataclass
class Frame:
    frame_id: int
    sequence_id: int
    pipeline_id: str
    layout: TerminalLayout
    sections: list[Section]
    render_mode: str = "standard"  # standard | tool_focus
    tool_focus: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ViewerState:
    pipeline_id: str = ""
    isolation_mode: bool | None = None
    phases: list[PhaseInfo] = field(default_factory=list)
    current_phase: PhaseInfo | None = None
    score: int | None = None
    findings: list[dict[str, Any]] = field(default_factory=list)
    isolation_routes: list[dict[str, Any]] = field(default_factory=list)
    render_mode: str = "standard"
    tool_focus: str | None = None
    frame_counter: int = 0
    pipeline_complete: bool = False
    total_phases: int = 8


class TerminalViewer:
    """Subscribes to EventBus wildcard, reduces events into Frames."""

    def __init__(self, bus: EventBus) -> None:
        self.state = ViewerState()
        self._frame_consumers: list[Callable[[Frame], None]] = []
        bus._wildcard_subscribers.append(self.on_event)

    def subscribe_frames(self, consumer: Callable[[Frame], None]) -> None:
        self._frame_consumers.append(consumer)

    def on_event(self, event: Event) -> None:
        self._reduce(event)
        frame = self._emit_frame(event)
        for consumer in self._frame_consumers:
            try:
                consumer(frame)
            except Exception as e:
                logger.warning(f"Frame consumer error: {e}")

    def _reduce(self, event: Event) -> None:
        et = event.event_type
        p = event.payload

        if et == EventType.PIPELINE_START:
            self.state = ViewerState(
                pipeline_id=p.get("pipeline_id", ""),
                isolation_mode=p.get("isolation_mode"),
            )
        elif et == EventType.PHASE_START:
            self.state.current_phase = PhaseInfo(
                phase_id=p["phase_id"], phase_name=p["phase_name"]
            )
        elif et == EventType.PHASE_END:
            if self.state.current_phase:
                self.state.current_phase.status = p.get("status", "")
                self.state.current_phase.duration_ms = p.get("duration_ms", 0)
                self.state.phases.append(self.state.current_phase)
                self.state.current_phase = None
        elif et == EventType.SCORE_COMPUTED:
            self.state.score = p.get("final_score", 0)
        elif et == EventType.FINDING_CREATED:
            self.state.findings.append({"type": "created", **p})
        elif et == EventType.FINDING_CLASSIFIED:
            self.state.findings.append({"type": "classified", **p})
        elif et == EventType.ISOLATION_ROUTED:
            self.state.isolation_routes.append(p)
        elif et == EventType.TOOL_START:
            self.state.render_mode = "tool_focus"
            self.state.tool_focus = p.get("tool_id", "")
        elif et == EventType.TOOL_END:
            self.state.render_mode = "standard"
            self.state.tool_focus = None
        elif et == EventType.PIPELINE_COMPLETE:
            self.state.pipeline_complete = True

    def _emit_frame(self, event: Event) -> Frame:
        self.state.frame_counter += 1
        s = self.state

        if s.render_mode == "tool_focus" and s.tool_focus:
            sections = [Section(
                section_type="tool_detail",
                content={
                    "tool_name": event.payload.get("tool_name", ""),
                    "phase_id": event.payload.get("phase_id", 0),
                    "tool_id": s.tool_focus,
                    "payload": event.payload,
                },
            )]
        else:
            phase_display = ""
            if s.current_phase:
                phase_display = f"{s.current_phase.phase_id + 1}/{s.total_phases} {s.current_phase.phase_name}"

            sections = [
                Section(section_type="header", content={
                    "run_id": s.pipeline_id,
                    "isolation": s.isolation_mode,
                    "phase": phase_display,
                }),
                Section(section_type="phases", content={
                    "completed": [
                        {"phase_id": p.phase_id, "phase_name": p.phase_name,
                         "status": p.status, "duration_ms": p.duration_ms}
                        for p in s.phases
                    ],
                    "current": s.current_phase.phase_name if s.current_phase else "",
                    "pending": [],
                }),
                Section(section_type="score", content={
                    "value": s.score or 0,
                    "bar_pct": s.score or 0,
                }),
                Section(section_type="findings", content={
                    "items": [
                        f"{f.get('issue_type', '?')} ({f.get('severity', '?')}): {f.get('file', '?')}"
                        for f in s.findings[-5:]
                    ],
                }),
                Section(section_type="isolation", content={
                    "routes": s.isolation_routes[-5:],
                }),
                Section(section_type="event_stream", content={
                    "recent": [],
                }),
            ]

        return Frame(
            frame_id=s.frame_counter,
            sequence_id=event.sequence_id,
            pipeline_id=s.pipeline_id,
            layout=TerminalLayout(columns=80, rows=24),
            sections=sections,
            render_mode=s.render_mode,
            tool_focus=s.tool_focus,
            meta={
                "score": s.score,
                "phase_index": s.current_phase.phase_id if s.current_phase else len(s.phases),
                "isolation_mode": s.isolation_mode,
                "pipeline_complete": s.pipeline_complete,
            },
        )
