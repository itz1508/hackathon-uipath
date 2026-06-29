# 02.5 Pre-Simulation Package

- Purpose/owner: package component evaluates admission to Simulation.
- Inputs: schema-valid Handoff Statement and referenced state.
- Outputs: Pre-Simulation Package.
- Permitted: validate, derive availability, score, and select a bounded next action.
- Prohibited: gate bypass, dependency installation, Simulation execution, mutation approval.
- Entry: handoff fields and references are complete. Exit: one explicit readiness state exists.
- Failure: request dependency, reattempt package, resolve grader failures, or build Isolation Add-On.
- Receiver: 03 Simulation only when all admission conditions pass.
- Authority: admission only.
