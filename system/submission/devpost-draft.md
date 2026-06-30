# NextFlow — Deterministic Pipeline Processing for AI-Generated Configuration Repairs

**Track:** UiPath Maestro BPMN

NextFlow addresses a production problem: AI can propose configuration fixes quickly, but enterprises still need evidence that one exact result is safe and explicit authority before touching a live target.

UiPath Maestro coordinates an advisory analysis agent, deterministic admission, isolated RPA simulation, API-based replay proof, an Action Center decision, exact-result apply relay, and read-only verification. The process retains one simulation result and binds approval to its ID, hash, and target. Cancel and Preserve remain first-class outcomes; verification failures are reported rather than silently repaired.

The sample repairs only `retry_limit=-1` to `3` while proving that the source and unrelated fields remain unchanged. The same BPMN structure exposes documented bindings for enterprise agents, APIs, RPA, storage, and human tasks.

**Truthful status:** replace this paragraph only after recording an Automation Cloud process instance. Until then, the repository proves offline execution, contracts, BPMN validation, and packaging—not cloud runtime completion.
