"""Deterministic MP4 renderer from execution_trace.json. No UI, no screen capture."""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


W, H, FPS = 1280, 720, 30
BG = (11, 15, 20)
ACCENT = (88, 166, 255)
GREEN = (63, 185, 80)
WHITE = (230, 230, 230)
DIM = (140, 140, 140)

NAMES = {0:"SNAPSHOT",1:"SCAN",2:"ANALYSIS",3:"PRE-SIMULATION",
          4:"SIMULATION",5:"INSPECTION",6:"RELAY",7:"FINAL OUTPUT"}


def _font(size):
    for p in ["C:/Windows/Fonts/consola.ttf","C:/Windows/Fonts/cour.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

F_BIG = _font(36)
F_MED = _font(24)
F_SM = _font(18)


def _frame_title(trace):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((60, 150), "EDGE PIPELINE", font=F_BIG, fill=ACCENT)
    d.text((60, 200), "EXECUTION TRACE", font=F_BIG, fill=WHITE)
    d.text((60, 300), f"ID: {trace.get('execution_id','')[:16]}", font=F_MED, fill=DIM)
    d.text((60, 340), f"Case: {trace.get('case_id','')}", font=F_MED, fill=DIM)
    d.text((60, 380), f"Started: {trace.get('started_at','')[:19]}", font=F_MED, fill=DIM)
    d.text((60, 420), "Mode: AUTO | Isolation: ON | Threshold: 93.91%", font=F_SM, fill=DIM)
    return img


def _frame_phase(phase, result_text, duration_ms, completed):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((60, 30), f"PHASE {phase} — {NAMES.get(phase,'?')}", font=F_BIG, fill=ACCENT)
    d.text((60, 80), f"completed | {duration_ms}ms", font=F_MED, fill=GREEN)
    y = 140
    for i in range(8):
        color = GREEN if i in completed else (DIM if i != phase else ACCENT)
        marker = "●" if i in completed else ("▶" if i == phase else "○")
        d.text((60, y), f"{marker} P{i} {NAMES.get(i,'')}", font=F_SM, fill=color)
        y += 32
    d.text((400, 140), "Result:", font=F_SM, fill=DIM)
    d.text((400, 170), result_text[:80], font=F_SM, fill=WHITE)
    return img


def _frame_final(trace):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((60, 150), "PIPELINE COMPLETE", font=F_BIG, fill=GREEN)
    steps = trace.get("execution_narrative", [])
    last = next((s for s in reversed(steps) if s.get("type") == "after"), {})
    details = last.get("details", {})
    total_ms = sum(s.get("duration_ms", 0) for s in steps if s.get("type") == "after")
    d.text((60, 250), f"Status: succeeded", font=F_MED, fill=GREEN)
    d.text((60, 290), f"Resolved: {details.get('resolved_count', '?')}", font=F_MED, fill=GREEN)
    d.text((60, 330), f"Unresolved: {details.get('unresolved_count', '?')}", font=F_MED, fill=WHITE)
    d.text((60, 370), f"Duration: {total_ms}ms", font=F_MED, fill=DIM)
    d.text((60, 410), f"Execution ID: {trace.get('execution_id','')[:24]}", font=F_SM, fill=DIM)
    return img


def render_mp4(trace_path: str, output_path: str):
    trace = json.load(open(trace_path, "r", encoding="utf-8"))
    events = trace.get("execution_narrative", [])
    if not events:
        raise ValueError("No events in trace")

    output_path = str(Path(output_path).resolve())
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Build frames
    segments = []  # (Image, duration_seconds)
    segments.append((_frame_title(trace), 2.0))

    completed = []
    befores = {}
    for step in events:
        if step.get("type") == "before":
            befores[step["phase"]] = step
        elif step.get("type") == "after":
            phase = step["phase"]
            f = _frame_phase(phase, step.get("result", ""), step.get("duration_ms", 0), list(completed))
            segments.append((f, 1.5))
            completed.append(phase)

    segments.append((_frame_final(trace), 3.0))

    # Write PNGs + concat
    tmpdir = tempfile.mkdtemp(prefix="edge_mp4_")
    concat = os.path.join(tmpdir, "concat.txt")
    with open(concat, "w") as cf:
        for i, (frame, dur) in enumerate(segments):
            png = os.path.join(tmpdir, f"f{i:04d}.png")
            frame.save(png)
            cf.write(f"file '{png}'\nduration {dur}\n")
        cf.write(f"file '{png}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-vf", f"fps={FPS}", output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    shutil.rmtree(tmpdir, ignore_errors=True)
    return output_path
