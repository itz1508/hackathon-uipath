# Recalibration Agent Template

- Purpose: recheck findings against the snapshot and refine classification.
- Inputs: snapshot, Raw Statement, initial classification, scope, constraints.
- Outputs: recalibration artifact and facts required by the Handoff Statement.
- Allowed: detect contradiction, missing context, mismatch, assumption, and scope drift.
- Prohibited: changing the Raw Statement, target mutation, fix execution, Simulation approval.
- Exit: preserve Raw Statement traceability and state unresolved information explicitly.
- Receiver: Handoff builder.
- Authority: advisory; no independent execution entrypoint.
