"""DAGViewer — tree-based execution visualization."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from pipeline.events.bus import Event, EventBus, EventType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DAGFrame:
    frame_id: int
    sequence_id: int
    pipeline_id: str
    rendered_lines: list[str]


@dataclass
class DAGNode:
    label: str
    children: list[DAGNode] = field(default_factory=list)
    status: str = ""
    annotations: list[str] = field(default_factory=list)


class EventGraphBuilder:
    """Builds a tree from pipeline events and renders it as text lines."""

    def __init__(self, expanded: bool = False) -> None:
        self._root: DAGNode | None = None
        self._phases: dict[int, DAGNode] = {}
        self._current_phase_id: int | None = None
        self._expanded = expanded

    def process_event(self, event: Event) -> list[str]:
        et = event.event_type
        p = event.payload

        if et == EventType.PIPELINE_START:
            self._root = DAGNode(label=p.get("pipeline_id", event.pipeline_id))
        elif et == EventType.PHASE_START:
            phase_id = p.get("phase_id", 0)
            phase_name = p.get("phase_name", "?")
            node = DAGNode(label=phase_name)
            self._phases[phase_id] = node
            self._current_phase_id = phase_id
            if self._root:
                self._root.children.append(node)
        elif et == EventType.PHASE_END:
            phase_id = p.get("phase_id", 0)
            status = p.get("status", "")
            if phase_id in self._phases:
                self._phases[phase_id].status = "✓" if status == "success" else "✗"
        elif et == EventType.TOOL_START:
            phase_id = p.get("phase_id", 0)
            tool_name = p.get("tool_name", "?")
            parent = self._phases.get(phase_id, self._root)
            if parent:
                parent.children.append(DAGNode(label=tool_name))
        elif et == EventType.ISOLATION_ROUTED:
            file_name = p.get("file", "?")
            routing = p.get("routing", "?")
            if self._current_phase_id is not None and self._current_phase_id in self._phases:
                node = self._phases[self._current_phase_id]
                node.annotations.append(f"{file_name} ─◄ {routing}")
        elif et == EventType.PIPELINE_COMPLETE:
            status = p.get("status", "?")
            if self._root:
                self._root.annotations.append(f"[COMPLETE: {status}]")

        return self.render()

    def render(self) -> list[str]:
        if not self._root:
            return []
        lines: list[str] = []
        lines.append(self._root.label)
        self._render_children(self._root, "", lines)
        for ann in self._root.annotations:
            lines.append(ann)
        return lines

    def _render_children(self, node: DAGNode, prefix: str, lines: list[str]) -> None:
        children = node.children
        for i, child in enumerate(children):
            is_last = (i == len(children) - 1)
            connector = "└── " if is_last else "├── "
            status_str = f" {child.status}" if child.status else ""
            lines.append(f"{prefix}{connector}{child.label}{status_str}")
            child_prefix = prefix + ("    " if is_last else "│   ")
            # Annotations
            for ann in child.annotations:
                lines.append(f"{child_prefix}{ann}")
            self._render_children(child, child_prefix, lines)

    @staticmethod
    def replay(events: list[Event]) -> list[list[str]]:
        builder = EventGraphBuilder()
        results = []
        for event in events:
            lines = builder.process_event(event)
            results.append(lines)
        return results


class DAGViewer:
    """Subscribes to EventBus, produces DAGFrames from tree rendering."""

    def __init__(self, bus: EventBus, expanded: bool = False) -> None:
        self._builder = EventGraphBuilder(expanded=expanded)
        self._frame_counter = 0
        self._pipeline_id = ""
        self._frame_consumers: list[Callable[[DAGFrame], None]] = []
        bus._wildcard_subscribers.append(self.on_event)

    def subscribe_frames(self, consumer: Callable[[DAGFrame], None]) -> None:
        self._frame_consumers.append(consumer)

    def on_event(self, event: Event) -> None:
        if event.event_type == EventType.PIPELINE_START:
            self._pipeline_id = event.payload.get("pipeline_id", event.pipeline_id)
        lines = self._builder.process_event(event)
        self._frame_counter += 1
        frame = DAGFrame(
            frame_id=self._frame_counter,
            sequence_id=event.sequence_id,
            pipeline_id=self._pipeline_id,
            rendered_lines=lines,
        )
        for consumer in self._frame_consumers:
            try:
                consumer(frame)
            except Exception as e:
                logger.warning(f"DAGViewer consumer error: {e}")

    @staticmethod
    def from_event_log(events: list[Event]) -> list[DAGFrame]:
        if not events:
            return []
        builder = EventGraphBuilder()
        frames: list[DAGFrame] = []
        pipeline_id = ""
        for i, event in enumerate(events):
            if event.event_type == EventType.PIPELINE_START:
                pipeline_id = event.payload.get("pipeline_id", event.pipeline_id)
            lines = builder.process_event(event)
            frames.append(DAGFrame(
                frame_id=i + 1,
                sequence_id=event.sequence_id,
                pipeline_id=pipeline_id,
                rendered_lines=lines,
            ))
        return frames
