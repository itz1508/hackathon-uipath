"""Recorder — Frame-to-MP4 video encoder via ffmpeg rawvideo pipe."""
from __future__ import annotations

import math
import subprocess
import time
import logging
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from pipeline.viewers.terminal_viewer import Frame, Section, TerminalViewer

logger = logging.getLogger(__name__)


class RecorderError(Exception):
    pass


class Recorder:
    """Records TerminalViewer Frames to MP4 via ffmpeg stdin pipe."""

    def __init__(
        self,
        viewer: TerminalViewer,
        output_path: str,
        resolution: tuple[int, int] = (1920, 1080),
        fps: int = 30,
    ) -> None:
        self._viewer = viewer
        self._output_path = output_path
        self._resolution = resolution
        self._fps = fps
        self._process: subprocess.Popen | None = None
        self._held_frame: Frame | None = None
        self._held_time: float = 0.0
        self._finalized = False
        self._font = self._load_font()
        viewer.subscribe_frames(self.ingest_frame)

    def _load_font(self) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for p in ["C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/cour.ttf"]:
            if Path(p).exists():
                return ImageFont.truetype(p, 20)
        return ImageFont.load_default()

    def _validate_output_path(self, path: str) -> None:
        parent = Path(path).parent
        if not parent.exists():
            raise RecorderError(f"parent directory does not exist: {parent}")

    def start(self) -> None:
        self._validate_output_path(self._output_path)
        w, h = self._resolution
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{w}x{h}",
            "-r", str(self._fps),
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            self._output_path,
        ]
        try:
            self._process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            raise RecorderError("ffmpeg not found")

    def _rasterize(self, frame: Frame) -> bytes:
        w, h = self._resolution
        img = Image.new("RGB", (w, h), (11, 15, 20))
        d = ImageDraw.Draw(img)

        y = 30
        for section in frame.sections:
            st = section.section_type
            c = section.content
            if st == "header":
                d.text((30, y), f"Pipeline: {c.get('run_id', '')}", font=self._font, fill=(88, 166, 255))
                y += 30
                d.text((30, y), f"Phase: {c.get('phase', '')}", font=self._font, fill=(230, 230, 230))
                y += 30
            elif st == "phases":
                for p in c.get("completed", []):
                    d.text((30, y), f"● {p['phase_name']} ✓ ({p['duration_ms']:.0f}ms)", font=self._font, fill=(63, 185, 80))
                    y += 25
                if c.get("current"):
                    d.text((30, y), f"▶ {c['current']}", font=self._font, fill=(88, 166, 255))
                    y += 25
            elif st == "score":
                d.text((30, y), f"Score: {c.get('value', 0)}%", font=self._font, fill=(230, 230, 230))
                y += 30
            elif st == "findings":
                for item in c.get("items", [])[:5]:
                    d.text((30, y), f"• {item[:80]}", font=self._font, fill=(240, 136, 62))
                    y += 22
            elif st == "isolation":
                for route in c.get("routes", [])[:3]:
                    d.text((30, y), f"◄ {route.get('file', '')} → {route.get('routing', '')}", font=self._font, fill=(140, 140, 140))
                    y += 22
            elif st == "tool_detail":
                d.text((30, y), f"[TOOL] {c.get('tool_name', '')} (phase {c.get('phase_id', '')})", font=self._font, fill=(88, 166, 255))
                y += 30

        return img.tobytes()

    def _write_frame_duplicated(self, frame: Frame, duration_seconds: float) -> None:
        if self._finalized or not self._process or not self._process.stdin:
            return
        n_frames = math.ceil(duration_seconds * self._fps)
        if n_frames < 1:
            n_frames = 1
        rgb_bytes = self._rasterize(frame)
        for _ in range(n_frames):
            self._process.stdin.write(rgb_bytes)

    def ingest_frame(self, frame: Frame) -> None:
        if self._finalized:
            return
        now = time.monotonic()
        if self._held_frame is not None:
            duration = now - self._held_time
            self._write_frame_duplicated(self._held_frame, duration)
        self._held_frame = frame
        self._held_time = now

    def finalize(self) -> dict[str, Any]:
        if self._finalized:
            return self._build_meta()
        self._finalized = True

        # Flush last held frame (min 1/fps duration)
        if self._held_frame is not None:
            self._write_frame_duplicated(self._held_frame, 1.0 / self._fps)

        if self._process and self._process.stdin:
            self._process.stdin.close()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()

        return self._build_meta()

    def _build_meta(self) -> dict[str, Any]:
        p = Path(self._output_path)
        exists = p.exists()
        return {
            "path": self._output_path,
            "exists": exists,
            "size_bytes": p.stat().st_size if exists else 0,
            "size_mb": round(p.stat().st_size / (1024 * 1024), 2) if exists else 0,
            "resolution": f"{self._resolution[0]}x{self._resolution[1]}",
            "fps": self._fps,
            "frame_count": 0,
            "duration_seconds": 0,
        }
