"""Pipeline invariants — checked before/after each phase."""
from __future__ import annotations

from typing import Any


class SnapshotImmutableInvariant:
    """Snapshot data must not change after Phase 0."""
    def check_before(self, state: Any, phase_idx: int) -> None:
        pass

    def check_after(self, state: Any, phase_idx: int) -> None:
        pass


class SimulationReadyOnlyInvariant:
    """Only ready items may enter simulation."""
    def check_before(self, state: Any, phase_idx: int) -> None:
        pass

    def check_after(self, state: Any, phase_idx: int) -> None:
        pass


class IsolatedNoResolveInvariant:
    """Isolated items must not be marked resolved without re-evaluation."""
    def check_before(self, state: Any, phase_idx: int) -> None:
        pass

    def check_after(self, state: Any, phase_idx: int) -> None:
        pass


class RelayReadonlyInvariant:
    """Relay phase must not mutate any prior state."""
    def check_before(self, state: Any, phase_idx: int) -> None:
        pass

    def check_after(self, state: Any, phase_idx: int) -> None:
        pass
