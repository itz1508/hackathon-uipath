"""EventDrivenReportGenerator — generates JSON/HTML reports from EventBus log."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pipeline.events.bus import EventBus, EventType


class EventDrivenReportGenerator:
    """Generates pipeline reports from the EventBus event log."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def generate(self, output_dir: str = "reports") -> tuple[str, str]:
        os.makedirs(output_dir, exist_ok=True)
        log = self._bus.get_log()

        report: dict[str, Any] = {
            "events": len(log),
            "phases": [],
            "findings": [],
            "score": None,
            "status": "unknown",
        }

        for event in log:
            if event.event_type == EventType.PHASE_END:
                report["phases"].append(event.payload)
            elif event.event_type == EventType.FINDING_CREATED:
                report["findings"].append(event.payload)
            elif event.event_type == EventType.SCORE_COMPUTED:
                report["score"] = event.payload.get("final_score")
            elif event.event_type == EventType.PIPELINE_COMPLETE:
                report["status"] = event.payload.get("status", "unknown")

        json_path = os.path.join(output_dir, "pipeline_report.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

        html_path = os.path.join(output_dir, "pipeline_report.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(f"<html><body><pre>{json.dumps(report, indent=2, default=str)}</pre></body></html>")

        return json_path, html_path
