# 07 Post-Apply Verification

- Purpose/owner: verification component checks the applied result against proof and success criteria.
- Inputs: apply result, proof, expected outcome.
- Outputs: `valid`, `not_valid`, or `not_run` verification state.
- Permitted: read-only inspection and validation.
- Prohibited: corrective mutation or overstating incomplete checks.
- Entry: apply attempt is recorded. Exit: evidence and limitations are explicit.
- Failure: record `not_valid` or `not_run` with reason.
- Receiver: 08 Final Result Locked.
- Authority: verification only.
