"""Record pipeline demo — window capture only (1280x720), auto start/stop.

Launches a Tk window titled "Edge Pipeline Demo", runs the pipeline inside it
with live phase updates, records ONLY that window via ffmpeg gdigrab title capture,
and saves to proof/{execution_id}/demo.mp4.

Usage:
    python tools/demo/record_demo.py [target_path]
"""
import os
import sys
import subprocess
import threading
import time
import uuid
from pathlib import Path

PIPELINE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PIPELINE_ROOT)

from phase_models import WorkflowInput
from orchestrator import run_pipeline

# ──────────────────────────────────────────────
# Tk Window (1280x720, titled for gdigrab)
# ──────────────────────────────────────────────

WINDOW_TITLE = "Edge Pipeline Demo"
WIDTH, HEIGHT = 1280, 720

import tkinter as tk
from tkinter import font as tkfont


class DemoWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WIDTH}x{HEIGHT}")
        self.root.resizable(False, False)
        self.root.configure(bg="#0b0f14")

        # Header
        self.header = tk.Label(
            self.root, text="EDGE PIPELINE — EXECUTION TRACE",
            fg="#58a6ff", bg="#0b0f14", font=("Consolas", 24, "bold"),
        )
        self.header.pack(pady=(30, 10))

        # Status
        self.status_var = tk.StringVar(value="Initializing...")
        self.status = tk.Label(
            self.root, textvariable=self.status_var,
            fg="#e6e6e6", bg="#0b0f14", font=("Consolas", 14),
        )
        self.status.pack(pady=5)

        # Phase list frame
        self.phase_frame = tk.Frame(self.root, bg="#161b22", padx=20, pady=20)
        self.phase_frame.pack(fill="both", expand=True, padx=40, pady=20)

        self.phase_labels: list[tk.Label] = []
        for i in range(8):
            names = ["SNAPSHOT", "SCAN", "ANALYSIS", "PRE-SIMULATION",
                     "SIMULATION", "INSPECTION", "RELAY", "FINAL OUTPUT"]
            lbl = tk.Label(
                self.phase_frame,
                text=f"  ○  Phase {i} — {names[i]}",
                fg="#555555", bg="#161b22", font=("Consolas", 16),
                anchor="w",
            )
            lbl.pack(fill="x", pady=4)
            self.phase_labels.append(lbl)

        # Footer
        self.footer = tk.Label(
            self.root, text="Mode: AUTO  |  Isolation: ON  |  Threshold: 93.91%",
            fg="#666666", bg="#0b0f14", font=("Consolas", 11),
        )
        self.footer.pack(pady=(0, 15))

        self.root.update()

    def set_phase_active(self, phase: int):
        self.phase_labels[phase].config(text=self.phase_labels[phase].cget("text").replace("○", "▶"), fg="#58a6ff")
        self.root.update()

    def set_phase_done(self, phase: int, duration_ms: int, detail: str = ""):
        txt = self.phase_labels[phase].cget("text").replace("▶", "●").replace("○", "●")
        txt += f"  ({duration_ms}ms)"
        if detail:
            txt += f"  {detail}"
        self.phase_labels[phase].config(text=txt, fg="#3fb950")
        self.root.update()

    def set_status(self, text: str):
        self.status_var.set(text)
        self.root.update()

    def set_final(self, resolved: int, unresolved: int, status: str):
        color = "#3fb950" if "resolved" in status else "#f0883e"
        self.status_var.set(f"✔ {status}  |  Resolved: {resolved}  |  Unresolved: {unresolved}")
        self.status.config(fg=color)
        self.root.update()


# ──────────────────────────────────────────────
# Recording + Pipeline
# ──────────────────────────────────────────────


def run_demo(target_path: str):
    execution_id = uuid.uuid4().hex[:12]
    output_dir = os.path.join(PIPELINE_ROOT, "..", "proof", execution_id)
    os.makedirs(output_dir, exist_ok=True)
    output_mp4 = os.path.join(output_dir, "demo.mp4")

    # Create window
    win = DemoWindow()
    win.set_status(f"Target: {os.path.basename(target_path)}")
    time.sleep(1)
    win.root.update()

    # Start ffmpeg recording (window title capture)
    recorder = subprocess.Popen([
        "ffmpeg", "-y",
        "-f", "gdigrab",
        "-framerate", "30",
        "-i", f"title={WINDOW_TITLE}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        output_mp4,
    ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    time.sleep(1)  # Let recorder stabilize

    # Run pipeline in thread
    result_holder = [None]

    def pipeline_thread():
        inp = WorkflowInput(
            case_id=f"demo-{execution_id}",
            target_path=target_path,
            mode="auto",
        )
        result_holder[0] = run_pipeline(inp)

    win.set_status("Pipeline running...")
    t = threading.Thread(target=pipeline_thread, daemon=True)
    t.start()

    # Poll for completion, update UI from phase_results
    phases_shown = set()
    while t.is_alive():
        win.root.update()
        time.sleep(0.3)
        result = result_holder[0]
        if result and hasattr(result, "phase_results"):
            for pr in result.phase_results:
                if pr.phase not in phases_shown:
                    win.set_phase_active(pr.phase)

    # Thread done — show all phases
    t.join()
    result = result_holder[0]

    if result and result.phase_results:
        for pr in result.phase_results:
            if pr.phase not in phases_shown:
                win.set_phase_active(pr.phase)
                win.root.update()
                time.sleep(0.1)
            detail = ""
            if pr.phase == 3:
                score = pr.required_outputs.get("package_confidence_score", 0)
                detail = f"score={score:.1f}%"
            elif pr.phase == 7:
                fo = pr.required_outputs.get("final_output", {})
                detail = f"resolved={fo.get('resolved_count', 0)}"
            win.set_phase_done(pr.phase, pr.duration_ms, detail)
            phases_shown.add(pr.phase)
            time.sleep(0.2)

        fo = result.final_output or {}
        win.set_final(
            resolved=fo.get("resolved_count", 0),
            unresolved=fo.get("unresolved_count", 0),
            status=fo.get("completion_status", result.pipeline_status.value),
        )

    # Hold final frame for 3 seconds
    time.sleep(3)

    # Stop recording
    if recorder.poll() is None:
        recorder.stdin.write(b"q")
        recorder.stdin.flush()
        try:
            recorder.wait(timeout=10)
        except subprocess.TimeoutExpired:
            recorder.kill()

    win.root.destroy()

    if os.path.exists(output_mp4):
        size_kb = os.path.getsize(output_mp4) / 1024
        print(f"Done: {output_mp4} ({size_kb:.0f} KB)")
    else:
        print(f"ERROR: MP4 not produced at {output_mp4}")


if __name__ == "__main__":
    _REPO_ROOT = str(Path(__file__).resolve().parents[3])
    target = sys.argv[1] if len(sys.argv) > 1 else _REPO_ROOT
    run_demo(target)
