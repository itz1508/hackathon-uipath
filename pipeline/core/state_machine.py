"""PipelineState — state machine for the dashboard-video nextflow system."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScoreRecord:
    base: int = 100
    deltas: tuple = ()
    final: int = 100


@dataclass(frozen=True)
class SimulationState:
    candidate_hash: str = ""
    mutation_log: tuple = ()


@dataclass(frozen=True)
class InspectionState:
    resolved: tuple = ()
    unresolved: tuple = ()
    diff: tuple = ()


@dataclass(frozen=True)
class RelayState:
    decision: str = ""
    verified_hash: str = ""


@dataclass(frozen=True)
class InvariantFlags:
    snapshot_lock: bool = False
    determinism_hash: str = ""


@dataclass(frozen=True)
class StateVector:
    """Immutable state vector for property-based testing."""
    snapshot_id: str = ""
    run_id: str = ""
    fixture_path: str = ""
    isolation_mode: bool = False
    started_at: float = 0.0
    phase_vector: tuple = ()
    findings: tuple = ()
    ready_set: tuple = ()
    isolated_set: tuple = ()
    score: ScoreRecord = field(default_factory=ScoreRecord)
    routing_map: tuple = ()
    simulation: SimulationState = field(default_factory=SimulationState)
    inspection: InspectionState = field(default_factory=InspectionState)
    relay: RelayState = field(default_factory=RelayState)
    invariants: InvariantFlags = field(default_factory=InvariantFlags)


@dataclass
class PipelineState:
    """Mutable pipeline state for the engine."""
    fixture_path: str = ""
    isolation_mode: bool = False
    run_id: str = ""
    started_at: float = 0.0
    snapshot: dict[str, Any] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)
    analysis: dict[str, Any] = field(default_factory=dict)
    simulation_package: dict[str, Any] = field(default_factory=dict)
    simulation_result: dict[str, Any] = field(default_factory=dict)
    inspection_result: dict[str, Any] = field(default_factory=dict)
    relay_result: dict[str, Any] = field(default_factory=dict)
    final_output: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "fixture_path": self.fixture_path,
            "isolation_mode": self.isolation_mode,
            "snapshot": self.snapshot,
            "findings": self.findings,
            "analysis": self.analysis,
            "simulation_package": self.simulation_package,
            "simulation_result": self.simulation_result,
            "inspection_result": self.inspection_result,
            "relay_result": self.relay_result,
            "final_output": self.final_output,
        }
