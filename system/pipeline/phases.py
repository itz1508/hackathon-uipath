"""Pipeline phases — thin wrappers exposing a .run(state) interface for the engine."""
from __future__ import annotations

import sys
import os

# Ensure pipeline root is importable
_pipeline_root = os.path.dirname(os.path.abspath(__file__))
if _pipeline_root not in sys.path:
    sys.path.insert(0, _pipeline_root)

from pipeline_state import PipelineState as _PS
from phase_controller import PhaseController
from phase_0 import transform_phase_0
from phase_1 import transform_phase_1
from phase_2 import transform_phase_2
from phase_3 import transform_phase_3
from phase_4 import transform_phase_4
from phase_5 import transform_phase_5
from phase_6 import transform_phase_6
from phase_7 import transform_phase_7

import uuid


# Each phase module exposes a `run(state)` function that the engine calls.
# The engine passes state, the phase returns modified state.

class _PhaseModule:
    """Namespace wrapper to give each phase a .run method."""
    def __init__(self, transform_fn, phase_num: int):
        self._fn = transform_fn
        self._phase_num = phase_num

    def run(self, state):
        """Execute the phase transform. Creates a controller per-run."""
        from pipeline_state import PipelineState as RealState
        import uuid

        # If state is from core.state_machine (dashboard), convert to real PipelineState
        if not isinstance(state, RealState):
            real_state = RealState(
                target_path=getattr(state, "fixture_path", ""),
                mode="auto",
                decision="apply",
                isolation_enabled=getattr(state, "isolation_mode", True),
            )
            # Copy any existing phase data
            for attr in ("snapshot", "findings", "analysis", "simulation_package",
                         "simulation_result", "inspection_result", "relay_result", "final_output"):
                if hasattr(state, attr):
                    val = getattr(state, attr)
                    if val:
                        setattr(real_state, attr, val)
            state = real_state

        execution_id = getattr(state, "execution_id", "") or getattr(state, "run_id", "") or str(uuid.uuid4())
        controller = PhaseController(execution_id)

        # Fast-forward controller to this phase
        from phase_models import PHASE_NAMES, PhaseResult
        for i in range(self._phase_num):
            controller.start_phase(i)
            controller.complete_phase(PhaseResult(
                phase=i, phase_name=PHASE_NAMES[i], exit_status="completed",
                required_outputs={k: "ok" for k in _required_outputs_keys(i)},
            ))

        return self._fn(state, controller)


def _required_outputs_keys(phase: int) -> list[str]:
    from phase_models import REQUIRED_OUTPUTS
    return REQUIRED_OUTPUTS.get(phase, [])


# Expose as module-level objects with .run methods
phase_0_snapshot = _PhaseModule(transform_phase_0, 0)
phase_1_scan = _PhaseModule(transform_phase_1, 1)
phase_2_analysis = _PhaseModule(transform_phase_2, 2)
phase_3_pre_sim = _PhaseModule(transform_phase_3, 3)
phase_4_simulation = _PhaseModule(transform_phase_4, 4)
phase_5_inspection = _PhaseModule(transform_phase_5, 5)
phase_6_relay = _PhaseModule(transform_phase_6, 6)
phase_7_final_output = _PhaseModule(transform_phase_7, 7)
