"""HTMLLiveViewer — WebSocket server for live dashboard (stub for headless)."""
from __future__ import annotations

from pipeline.viewers.terminal_viewer import TerminalViewer


class HTMLLiveViewer:
    """Minimal stub — WebSocket viewer for browser dashboard."""

    def __init__(self, viewer: TerminalViewer) -> None:
        self._viewer = viewer
        self.port: int | None = None

    async def start(self) -> None:
        pass  # No-op in headless mode

    async def stop(self) -> None:
        pass
