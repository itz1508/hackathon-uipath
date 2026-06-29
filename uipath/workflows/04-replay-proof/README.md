# 04 Replay / Proof

- Purpose/owner: proof component records reproducible evidence from Simulation.
- Inputs: simulation result and associated package.
- Outputs: proof artifact with commands, observations, and hashes.
- Permitted: replay, inspect, hash, and report evidence.
- Prohibited: target mutation or substituting claims for observations.
- Entry: simulation artifact exists. Exit: verification state is explicit.
- Failure: mark proof unverified and stop user-decision admission.
- Receiver: 05 User Apply or Cancel.
- Authority: evidence only.
