"""DAGRecorder — records DAGViewer frames to MP4."""
from __future__ import annotations

import math
import os
import subprocess
import time
import logging
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from pipeline.viewers.dag_viewer import DAGFrame, DAGViewer

logger = logging.getLogger(__name__)


class DAGRecorderError(Exception):
    pass


class DAGRecorder:
    """Records DAGViewer frames to MP4 via ffmpeg rawvideo pipe."""

    def __init__(
        self,
        viewer: DAGViewer,
        output_path: str,
        resolution: tuple[int, int] = (1920, 1080),
        fps: int = 30,
        diagnostics: bool = False,
    ) -> None:
        self._viewer = viewer
        self._output_path = output_path
        self._resolution = resolution
        self._fps = fps
        self._diagnostics = diagnostics
        self._process: subprocess.Popen | None = None
        self._held_frame: DAGFrame | None = None
        self._held_time: float = 0.0
        self._finalized = False
        self._frame_count = 0
        self._font = self._load_font()
        self._diag_png: str | None = None
        viewer.subscribe_frames(self._ingest_frame)

    def _load_font(self) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for p in ["C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/cour.ttf"]:
            if Path(p).exists():
                return ImageFont.truetype(p, 22)
        return ImageFont.load_default()

    def start(self) -> None:
        parent = Path(self._output_path).parent
        if not parent.exists():
            raise DAGRecorderError(f"parent directory does not exist: {parent}")

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
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            self._output_path,
        ]
        try:
            self._process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            raise DAGRecorderError("ffmpeg not found")

    def _rasterize(self, frame: DAGFrame) -> bytes:
        w, h = self._resolution
        img = Image.new("RGB", (w, h), (11, 15, 20))
        d = ImageDraw.Draw(img)

        y = 40
        d.text((40, y), "EDGE PIPELINE — DAG EXECUTION TREE", font=self._font, fill=(88, 166, 255))
        y += 50

        for line in frame.rendered_lines:
            if y > h - 40:
                break
            # Color based on content
            if "✓" in line:
                color = (63, 185, 80)
            elif "✗" in line:
                color = (248, 81, 73)
            elif "ISOLATED" in line:
                color = (240, 136, 62)
            elif "READY" in line:
                color = (63, 185, 80)
            elif "COMPLETE" in line:
                color = (88, 166, 255)
            else:
                color = (230, 230, 230)
            d.text((40, y), line, font=self._font, fill=color)
            y += 28

        # Save diagnostic PNG on first frame
        if self._diagnostics and self._frame_count == 0:
            diag_path = self._output_path.replace(".mp4", "_diagnostic.png")
            img.save(diag_path)
            self._diag_png = diag_path

        self._frame_count += 1
        return img.tobytes()

    def _write_frame(self, frame: DAGFrame, duration: float) -> None:
        if self._finalized or not self._process or not self._process.stdin:
            return
        n = max(1, math.ceil(duration * self._fps))
        rgb = self._rasterize(frame)
        for _ in range(n):
            self._process.stdin.write(rgb)

    def _ingest_frame(self, frame: DAGFrame) -> None:
        if self._finalized:
            return
        now = time.monotonic()
        if self._held_frame is not None:
            duration = now - self._held_time
            self._write_frame(self._held_frame, duration)
        self._held_frame = frame
        self._held_time = now

    def finalize(self) -> dict[str, Any]:
        if self._finalized:
            return self._build_meta()
        self._finalized = True

        if self._held_frame:
            self._write_frame(self._held_frame, 2.0)  # Hold final frame 2s

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
        size = p.stat().st_size if exists else 0
        duration = self._frame_count / self._fps if self._fps else 0

        meta: dict[str, Any] = {
            "path": self._output_path,
            "exists": exists,
            "size_bytes": size,
            "size_mb": round(size / (1024 * 1024), 2),
            "resolution": f"{self._resolution[0]}x{self._resolution[1]}",
            "fps": self._fps,
            "frame_count": self._frame_count,
            "duration_seconds": round(duration, 1),
        }

        if self._diagnostics:
            meta["diagnostics"] = {
                "renderer_type": "Pillow",
                "renderer_canvas": f"{self._resolution[0]}x{self._resolution[1]}",
                "font_family": "Consolas",
                "encoder": "libx264",
                "encoder_crf": 20,
                "encoder_preset": "fast",
                "pixel_format_in": "rgb24",
                "pixel_format_out": "yuv420p",
                "frame_hold_ms": round(1000 / self._fps),
                "diagnostic_png": self._diag_png,
            }

        return meta
