# Architecture

NextFlow separates advisory reasoning from deterministic authority. Maestro owns progression; agents describe and classify; deterministic gates admit execution; Action Center owns the Apply decision; RPA/API workflows own controlled side effects.

| Stage | Cloud owner | Input | Output | Authority |
|---|---|---|---|---|
| 01 Scan / Snapshot | API Workflow + storage | Case and target | Immutable snapshot/hash | Read-only |
| 02 Analysis / Recalibration | Agent Builder/coded agent | Snapshot and scope | Structured advisory finding | None |
| Handoff / 02.5 | Maestro Script Tasks | Finding and policy | Locked handoff/package | Admission only |
| 03 Simulation | RPA workflow | Qualified package | Inspected, validated result/hash | Sandbox only |
| 04 Replay / Proof | API Workflow | Recorded inputs/result | Identity/equivalence proof | Evidence only |
| 05 User Decision | Action Center | Exact proof packet | Apply/cancel/preserve | Human authority |
| 06 Apply Relay | RPA workflow | Approved ID/hash/target | Apply result | Exact approved mutation |
| 07 Verification | API Workflow | Live/proven result | Match/drift/failure | Read-only |
| 08 Final Lock | Maestro Script Task | Full state/provenance | Locked final result/hash | Terminal record |

`workflow_state` is the sole authoritative case object. Individual BPMN variables exist only as mapping/admission conveniences and must be synchronized back into it.

The Demo uses an in-memory JSON sandbox in BPMN and a file-backed deterministic Python runner for offline proof. The Real-Case process replaces those boundaries with explicit cloud resource bindings. No unbound task is described as operational.
