# Modified: 2026-06-23T22:10:00Z
"""Toolkit system — swappable phase implementations for the pipeline.

Architecture:
  - Each toolkit module implements the ToolContract ABC (defined in base.py)
  - The orchestrator (main.py) imports toolkits by name via this package
  - One-way dependency: toolkits depend on models/contracts, never on orchestrator
  - Tools are deterministic pure transformations executed in parallel sandboxes

Modules:
  - base: ToolContract ABC and ToolResult dataclass
  - precalibration: Phase 1 signal normalization (existing)
  - refactor: Structural code transformations (rename, extract, inline)
  - dep_fix: Dependency version conflict resolution
  - import_repair: Broken/missing import fixes
  - contract_align: Interface/contract alignment
  - test_repair: Test fixes preserving intent
"""
from __future__ import annotations

__all__: list[str] = []

# ── Existing modules ───────────────────────────────────────────────────────

try:
    from . import precalibration
    __all__.append("precalibration")
except ImportError:
    pass

# ── Core contract (added in Task 1.2) ─────────────────────────────────────

try:
    from . import base
    __all__.append("base")
except ImportError:
    pass

# ── Tool implementations (added in Task 2) ────────────────────────────────

try:
    from . import refactor
    __all__.append("refactor")
except ImportError:
    pass

try:
    from . import dep_fix
    __all__.append("dep_fix")
except ImportError:
    pass

try:
    from . import import_repair
    __all__.append("import_repair")
except ImportError:
    pass

try:
    from . import contract_align
    __all__.append("contract_align")
except ImportError:
    pass

try:
    from . import test_repair
    __all__.append("test_repair")
except ImportError:
    pass
