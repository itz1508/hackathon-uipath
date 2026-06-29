"""EventBus — synchronous pub/sub for pipeline phase events.

Provides Event, EventType, EventBus, and validation functions.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# EventType enum (16 members)
# ──────────────────────────────────────────────


class EventType(str, Enum):
    PIPELINE_START = "PIPELINE_START"
    PHASE_START = "PHASE_START"
    PHASE_END = "PHASE_END"
    TOOL_START = "TOOL_START"
    TOOL_END = "TOOL_END"
    FINDING_CREATED = "FINDING_CREATED"
    FINDING_CLASSIFIED = "FINDING_CLASSIFIED"
    SCORE_COMPUTED = "SCORE_COMPUTED"
    ISOLATION_ROUTED = "ISOLATION_ROUTED"
    ISOLATION_RESOLVED = "ISOLATION_RESOLVED"
    SIMULATION_START = "SIMULATION_START"
    SIMULATION_END = "SIMULATION_END"
    INSPECTION_START = "INSPECTION_START"
    INSPECTION_END = "INSPECTION_END"
    RELAY_DECISION = "RELAY_DECISION"
    PIPELINE_COMPLETE = "PIPELINE_COMPLETE"


# ──────────────────────────────────────────────
# Phases
# ──────────────────────────────────────────────

PHASES = (
    "SNAPSHOT", "SCAN", "ANALYSIS", "PRE_SIMULATION",
    "SIMULATION", "INSPECTION", "RELAY", "FINAL_OUTPUT",
)
VALID_PHASES = frozenset(PHASES) | {"PIPELINE"}


# ──────────────────────────────────────────────
# Event dataclass (frozen)
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class Event:
    sequence_id: int
    timestamp: str
    pipeline_id: str
    phase: str
    event_type: EventType | str
    payload: dict[str, Any]


# ──────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────


class ValidationError(Exception):
    pass


def validate_pipeline_id(pipeline_id: Any) -> None:
    if not isinstance(pipeline_id, str):
        raise ValidationError("pipeline_id must be a string")
    if len(pipeline_id) < 1:
        raise ValidationError("pipeline_id must have at least 1 character")
    if len(pipeline_id) > 128:
        raise ValidationError("pipeline_id must have at most 128 characters")


def validate_phase(phase: str) -> None:
    if phase not in VALID_PHASES:
        raise ValidationError(f"Invalid phase: '{phase}'. Must be one of {sorted(VALID_PHASES)}")


def validate_event_type(event_type: Any) -> None:
    if not isinstance(event_type, EventType):
        raise ValidationError(f"Must be an EventType enum member, got {type(event_type)}: {event_type}")


# Payload schemas: event_type → list of (field_name, expected_type)
_PAYLOAD_SCHEMAS: dict[EventType, list[tuple[str, type | tuple[type, ...]]]] = {
    EventType.PIPELINE_START: [("pipeline_id", str), ("fixture_path", str), ("isolation_mode", bool)],
    EventType.PHASE_START: [("phase_id", (int,)), ("phase_name", str)],
    EventType.PHASE_END: [("phase_id", (int,)), ("phase_name", str), ("status", str), ("duration_ms", (int, float))],
    EventType.TOOL_START: [("tool_id", str), ("tool_name", str), ("phase_id", (int,))],
    EventType.TOOL_END: [("tool_id", str), ("tool_name", str), ("phase_id", (int,)), ("result", str)],
    EventType.FINDING_CREATED: [("file", str), ("issue_type", str), ("severity", str), ("detail", str)],
    EventType.FINDING_CLASSIFIED: [("file", str), ("issue_type", str), ("classification", str), ("routing", str)],
    EventType.SCORE_COMPUTED: [("base_score", (int, float)), ("deltas", list), ("final_score", (int, float)), ("phase_context", str)],
    EventType.ISOLATION_ROUTED: [("file", str), ("routing", str)],
    EventType.ISOLATION_RESOLVED: [("file", str), ("resolved_as", str), ("strategy", str), ("confidence", (int, float))],
    EventType.SIMULATION_START: [("candidate_folder", str), ("ready_file_count", (int,))],
    EventType.SIMULATION_END: [("candidate_folder", str), ("status", str), ("duration_ms", (int, float))],
    EventType.INSPECTION_START: [("candidate_folder", str), ("original_folder", str)],
    EventType.INSPECTION_END: [("status", str), ("files_compared", (int,)), ("duration_ms", (int, float))],
    EventType.RELAY_DECISION: [("decision", str), ("reason", str), ("confidence", (int, float))],
    EventType.PIPELINE_COMPLETE: [("status", str), ("last_phase_index", (int,)), ("phases_executed", (int,))],
}

MAX_PAYLOAD_BYTES = 64 * 1024


def validate_payload(event_type: EventType, payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValidationError("payload must be a dict")
    # Size check
    serialized = json.dumps(payload, default=str)
    if len(serialized.encode()) > MAX_PAYLOAD_BYTES:
        raise ValidationError(f"payload exceeds maximum size ({MAX_PAYLOAD_BYTES} bytes)")
    # Schema check
    schema = _PAYLOAD_SCHEMAS.get(event_type, [])
    for field_name, expected_type in schema:
        if field_name not in payload:
            raise ValidationError(f"payload missing required field '{field_name}' for {event_type.value}")
        value = payload[field_name]
        if isinstance(expected_type, tuple):
            if not isinstance(value, expected_type):
                raise ValidationError(f"payload['{field_name}'] must be {expected_type}, got {type(value)}")
        elif expected_type is bool:
            if not isinstance(value, bool):
                raise ValidationError(f"payload['{field_name}'] must be bool, got {type(value)}")
        elif not isinstance(value, expected_type):
            raise ValidationError(f"payload['{field_name}'] must be {expected_type.__name__}, got {type(value)}")


def validate_event(event: Event) -> None:
    validate_pipeline_id(event.pipeline_id)
    validate_event_type(event.event_type)
    validate_phase(event.phase)
    validate_payload(event.event_type, event.payload)


# ──────────────────────────────────────────────
# Subscriber type
# ──────────────────────────────────────────────

Subscriber = Callable[[Event], None]


# ──────────────────────────────────────────────
# EventBus
# ──────────────────────────────────────────────


class EventBus:
    """Synchronous pub/sub event bus with validation and logging."""

    def __init__(self) -> None:
        self._type_subscribers: dict[EventType, list[Subscriber]] = {}
        self._wildcard_subscribers: list[Subscriber] = []
        self._log: list[Event] = []
        self._sequence_counter: int = 0

    def subscribe(self, event_type: EventType | str, subscriber: Subscriber) -> None:
        if event_type == "*":
            self._wildcard_subscribers.append(subscriber)
        else:
            if event_type not in self._type_subscribers:
                self._type_subscribers[event_type] = []
            self._type_subscribers[event_type].append(subscriber)

    def publish(self, event: Event) -> None:
        # Validate
        validate_event(event)

        # Assign sequence_id (override whatever was passed)
        from dataclasses import replace
        event = replace(event, sequence_id=self._sequence_counter)
        self._sequence_counter += 1

        # Log
        self._log.append(event)

        # Deliver to type-specific subscribers
        for sub in self._type_subscribers.get(event.event_type, []):
            try:
                sub(event)
            except Exception as e:
                logger.warning(f"Subscriber {sub.__name__} raised {type(e).__name__}: {e}")

        # Deliver to wildcard subscribers
        for sub in self._wildcard_subscribers:
            try:
                sub(event)
            except Exception as e:
                logger.warning(f"Subscriber {sub.__name__} raised {type(e).__name__}: {e}")

    def get_log(self) -> list[Event]:
        return list(self._log)

    def clear(self) -> None:
        self._type_subscribers.clear()
        self._wildcard_subscribers.clear()
        self._log.clear()
        self._sequence_counter = 0
