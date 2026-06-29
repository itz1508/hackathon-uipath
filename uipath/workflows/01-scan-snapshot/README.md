# 01 Scan / Snapshot

- Purpose/owner: read-only scan component establishes the source snapshot.
- Inputs: approved target and locked scope.
- Outputs: `snapshot.schema.json` artifact.
- Permitted: enumerate, read, hash, and record findings.
- Prohibited: target mutation, package installation, arbitrary user-code execution.
- Entry: target and scope are explicit. Exit: snapshot is complete and referenceable.
- Failure: stop and report inaccessible or ambiguous scope.
- Receiver: 02 Analysis / Classification.
- Authority: no mutation or approval.
