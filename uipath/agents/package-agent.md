# Package Agent Template

- Purpose: validate the Handoff Statement and build the Pre-Simulation Package.
- Inputs: schema-valid handoff and referenced Phase 02 artifacts.
- Outputs: package with admission state and next action.
- Allowed: validate contracts, derive dependency availability, evaluate admission conditions.
- Prohibited: bypassing any gate, installing dependencies, granting mutation authority.
- Exit: Simulation only when every admission condition is true; otherwise emit the bounded next action.
- Receiver: Simulation, participant request, package reattempt, or Isolation Add-On.
- Authority: admission decision only.
