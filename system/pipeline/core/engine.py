"""PipelineEngine — phase executor with invariant checking."""
from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class PipelineEngine:
    """Registers and executes pipeline phases in order with invariant checks."""

    def __init__(self, state: Any, verbose: bool = True) -> None:
        self.state = state
        self._phases: list[Callable] = []
        self._invariants: list[Any] = []
        self._verbose = verbose

    def register(self, phase_func: Callable) -> None:
        self._phases.append(phase_func)

    def register_invariant(self, invariant: Any) -> None:
        self._invariants.append(invariant)

    def run(self) -> Any:
        for i, phase_func in enumerate(self._phases):
            # Check invariants before
            for inv in self._invariants:
                if hasattr(inv, "check_before"):
                    inv.check_before(self.state, i)

            # Execute phase
            self.state = phase_func(self.state)

            # Check invariants after
            for inv in self._invariants:
                if hasattr(inv, "check_after"):
                    inv.check_after(self.state, i)

        return self.state
