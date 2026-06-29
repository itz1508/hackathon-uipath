# 05 User Apply or Cancel

- Purpose/owner: user supplies the explicit terminal decision.
- Inputs: proof packet and proposed mutation description.
- Outputs: `apply` or `cancel` decision.
- Permitted: user review and explicit selection.
- Prohibited: inferred, default, or agent-generated approval.
- Entry: proof is available. Exit: exactly one decision is recorded.
- Failure: absence or ambiguity stops processing without mutation.
- Receiver: 06 Apply Relay for apply; 08 Final Result for cancel.
- Authority: human decision boundary.
