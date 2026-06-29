# Scan and Analysis Agent Template

- Purpose: create an immutable snapshot, factual findings, Raw Statement, and initial classification.
- Inputs: approved target, locked scope, user constraints.
- Outputs: snapshot and analysis artifacts.
- Allowed: read, enumerate, hash, classify, record missing information.
- Prohibited: mutation, installation, arbitrary execution, approval.
- Exit: references are available for recalibration; otherwise stop with missing information.
- Receiver: Recalibration activity inside Phase 02.
- Authority: read-only and advisory.
