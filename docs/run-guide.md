# Run Guide

From the template root, run:

```powershell
python -m pytest tests -q
```

The suite parses schemas, templates, examples, and fixtures; validates accepted examples; confirms invalid fixtures are rejected; and applies contract checks that JSON Schema cannot express reliably.

A successful test run proves only that the committed template artifacts satisfy the local contract tests. It does not prove UiPath runtime enforcement, artifact existence, workflow execution, mutation, deployment, or integration with the downloaded desktop application.
