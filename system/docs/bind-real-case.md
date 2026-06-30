# Bind the Real-Case process

Copy `cases/template/mapping.template.json` into the case-specific configuration and fill every `resource_name`.

| Binding key | UiPath resource | Required contract |
|---|---|---|
| `scan_snapshot_api_workflow` | API Workflow + storage | Return snapshot, SHA-256, target identity |
| `config_risk_analysis_agent` | Agent Builder/coded agent | Return classification, supported correction, missing information, confidence |
| `sandbox_simulation_process` | RPA process | Execute isolated mutation; inspect, validate, and hash result |
| `replay_proof_api_workflow` | API Workflow | Verify all recorded identities and replay equivalence |
| `NextFlow_apply_decision_action` | Action Center app/task | Return apply, cancel, or preserve_for_later plus exact IDs |
| `exact_apply_relay_process` | RPA process | Check approval/hash/target/drift/recovery; reproduce only proven result |
| `post_apply_verification_api_workflow` | API Workflow | Return one allowed verification status; never repair |

Use Studio Web resource discovery to replace each `__BIND_REQUIRED_*__` marker. Update `bindings_v2.json` only through UiPath tooling/Studio Web. A successful binding must be followed by BPMN validation, debug, and one captured process instance.
