# 03 Simulation Environment

- Purpose/owner: simulation component evaluates proposed behavior in an isolated environment.
- Inputs: package with `simulation_ready=true`.
- Outputs: simulation result and validation observations.
- Permitted: bounded simulation and evidence capture.
- Prohibited: target mutation, undeclared access, package installation, authority escalation.
- Entry: all admission gates pass. Exit: result is complete and target remains unmodified.
- Failure: capture failure and return a bounded corrective handoff or Isolation reason.
- Receiver: 04 Replay / Proof.
- Authority: isolated simulation only.
