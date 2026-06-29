# 06 Explicit User Apply Mutation Relay

- Purpose/owner: apply component relays only the explicitly approved mutation.
- Inputs: user apply decision, locked scope, proof-linked change.
- Outputs: apply result.
- Permitted: approved mutation inside exact scope.
- Prohibited: scope expansion, undeclared changes, approval inference.
- Entry: explicit apply decision is valid. Exit: result records actual outcome.
- Failure: stop, preserve evidence, and do not claim application.
- Receiver: 07 Post-Apply Verification.
- Authority: limited to the explicit user-approved mutation.
