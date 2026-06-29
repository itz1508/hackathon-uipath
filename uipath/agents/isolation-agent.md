# Isolation Agent Template

- Purpose: isolate an unresolved definition or evidence problem.
- Inputs: handoff, package state, and one allowed Isolation reason.
- Outputs: Isolation Add-On describing missing evidence and measurable success criteria.
- Allowed: narrow the unresolved problem and request evidence.
- Prohibited: treating a merely missing identifiable dependency as Isolation, execution, approval, or mutation.
- Exit: return to package construction after the reason is resolved.
- Receiver: Pre-Simulation Package activity.
- Authority: advisory only; `execution_authority=false`.
