"""TerminalDisplay — renders Frames to console using rich."""
from __future__ import annotations

import logging
from typing import Callable

from rich.console import Console
from rich.panel import Panel

from pipeline.viewers.terminal_viewer import Frame, TerminalViewer

logger = logging.getLogger(__name__)


class FrameProducer:
    """Subscribes to TerminalViewer frame stream."""
    def __init__(self, viewer: TerminalViewer):
        self._frames: list[Frame] = []
        viewer.subscribe_frames(self._on_frame)

    def _on_frame(self, frame: Frame) -> None:
        self._frames.append(frame)

    @property
    def latest(self) -> Frame | None:
        return self._frames[-1] if self._frames else None


class TerminalDisplay:
    """Renders frames to the terminal."""

    def __init__(self, viewer: TerminalViewer) -> None:
        self._console = Console()
        self._viewer = viewer
        viewer.subscribe_frames(self._render_frame)

    def _render_frame(self, frame: Frame) -> None:
        if frame.render_mode == "tool_focus":
            self._render_tool_focus(frame)
        else:
            self._render_standard(frame)

    def _render_standard(self, frame: Frame) -> None:
        self._console.clear()
        for section in frame.sections:
            st = section.section_type
            content = section.content
            if st == "header":
                self._console.print(f"[bold cyan]Pipeline: {content.get('run_id', '')}[/]")
                self._console.print(f"  Phase: {content.get('phase', '')}")
            elif st == "phases":
                for p in content.get("completed", []):
                    self._console.print(f"  ● {p['phase_name']} ✓ ({p['duration_ms']:.0f}ms)")
                if content.get("current"):
                    self._console.print(f"  ▶ {content['current']}")
            elif st == "score":
                val = content.get("value", 0)
                self._console.print(f"  Score: {val}%")
            elif st == "findings":
                for item in content.get("items", [])[:3]:
                    self._console.print(f"  • {item}")
            elif st == "isolation":
                for route in content.get("routes", [])[:3]:
                    self._console.print(f"  ◄ {route.get('file', '')} → {route.get('routing', '')}")

    def _render_tool_focus(self, frame: Frame) -> None:
        self._console.clear()
        for section in frame.sections:
            if section.section_type == "tool_detail":
                c = section.content
                panel = Panel(
                    f"Tool: {c.get('tool_name', '')}\nPhase: {c.get('phase_id', '')}\nID: {c.get('tool_id', '')}",
                    title="[bold]Tool Focus[/]",
                )
                self._console.print(panel)
