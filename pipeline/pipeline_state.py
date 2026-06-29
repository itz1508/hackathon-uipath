"""Pipeline State — strict state algebra.

RULES:
- NO phase field inside state
- NO integer phase counter
- NO phase += 1
- State is purely structured data
- Isolation is orthogonal (not a phase)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from phase_models import PHASE_NAMES


VALID_PHASES = frozenset({
    "snapshot",
    "scan",
    "analysis",
    "pre_simulation",
    "simulation",
    "inspection",
    "relay",
    "final_output",
})

# Named transition table — NO arithmetic progression
TRANSITIONS: dict[str, str | None] = {
    "snapshot": "scan",
    "scan": "analysis",
    "analysis": "pre_simulation",
    "pre_simulation": "simulation",
    "simulation": "inspection",
    "inspection": "relay",
    "relay": "final_output",
    "final_output": None,  # terminal
}


@dataclass
class Isolation:
    """Orthogonal isolation state — advisory only, no execution authority."""
    active: bool = False
    items: list[dict[str, Any]] = field(default_factory=list)
    isolation_handoff: dict[str, Any] = field(default_factory=dict)
    # Advisory packet structure:
    # { packet_status, reviewer_targets, authority, execution_authority,
    #   blocked_next_phases, external_reviewer_task }
    retry_queue: list[dict[str, Any]] = field(default_factory=list)
    reattempt_count: int = 0
    max_reattempts: int = 3


@dataclass
class Flags:
    """Pipeline execution flags — marks what has been computed."""
    snapshot_locked: bool = False
    scan_complete: bool = False
    analysis_complete: bool = False
    partition_complete: bool = False
    simulation_complete: bool = False
    inspection_complete: bool = False
    relay_complete: bool = False
    final_complete: bool = False
    isolation_active: bool = False


@dataclass
class PipelineState:
    """The ONE global state. Pure data. No control logic.

    Phases read from state, write ONLY to their own field.
    No phase may:
    - mutate snapshot
    - mutate other phase outputs
    - decide routing outside its responsibility
    - overwrite another phase's field
    
    Isolation is orthogonal — never changes phase, only enriches data.
    """
    # Phase outputs (each phase writes ONLY its own field)
    snapshot: dict[str, Any] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)
    analysis: dict[str, Any] = field(default_factory=dict)
    simulation_package: dict[str, Any] = field(default_factory=dict)
    simulation_result: dict[str, Any] = field(default_factory=dict)
    inspection_result: dict[str, Any] = field(default_factory=dict)
    relay_result: dict[str, Any] = field(default_factory=dict)
    final_output: dict[str, Any] = field(default_factory=dict)

    # Orthogonal state (NOT a phase)
    isolation: Isolation = field(default_factory=Isolation)

    # Flags
    flags: Flags = field(default_factory=Flags)

    # Metadata
    case_id: str = ""
    execution_id: str = ""
    target_path: str = ""
    mode: str = "manual"
    decision: str = ""
    isolation_enabled: bool = True  # default True; set to False for Run A (no isolation engine)

    def validate_transition(self, phase_name: str | int) -> None:
        """Validate that a phase transition is legal given current flags.
        
        Accepts named phases (str) or integer phase numbers for backward
        compatibility. Internally resolves to named phases.
        """
        if isinstance(phase_name, int):
            phase_name = PHASE_NAMES.get(phase_name, f"unknown_{phase_name}")
        
        assert phase_name in VALID_PHASES, f"Invalid phase: {phase_name}"
        
        checks = {
            "scan": self.flags.snapshot_locked,
            "analysis": self.flags.scan_complete,
            "pre_simulation": self.flags.analysis_complete,
            "simulation": self.flags.partition_complete,
            "inspection": self.flags.simulation_complete,
            "relay": self.flags.inspection_complete,
            "final_output": self.flags.relay_complete,
        }
        required = checks.get(phase_name)
        if required is not None and not required:
            raise ValueError(
                f"Cannot enter '{phase_name}': prerequisite flag not set"
            )
