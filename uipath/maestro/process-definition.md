# Maestro Process Definition Template

This document is a design mapping, not a deployed Maestro process.

Service-task candidates: Scan, Analysis, Recalibration, Handoff construction, Pre-Simulation packaging, Simulation, Replay/Proof, Apply relay, Post-Apply verification, and Final lock. The user decision is a user task. Admission, dependency mode, and apply/cancel are gateways.

Every task receives a versioned artifact and emits another artifact. Gateways evaluate explicit fields; they do not infer authority. Apply relay is reachable only after an explicit user `apply` decision.
