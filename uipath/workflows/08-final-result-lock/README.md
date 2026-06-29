# 08 Final Result Locked

- Purpose/owner: result component creates the terminal workflow record.
- Inputs: proof, user decision, apply status, verification state.
- Outputs: final result with `locked=true`.
- Permitted: aggregate final facts and references.
- Prohibited: changing prior evidence, reopening authority, claiming unrun validation.
- Entry: terminal path is complete. Exit: immutable final representation exists.
- Failure: do not lock an incomplete or contradictory result.
- Receiver: none.
- Authority: terminal record only.
