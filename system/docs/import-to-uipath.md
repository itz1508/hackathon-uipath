# Import to UiPath Studio Web

1. Sign into the assigned UiPath Automation Cloud/Labs tenant.
2. Create or open an Agentic Process/Maestro BPMN project.
3. Import `maestro/NextFlow-RealCase-Template/NextFlow-Demo.bpmn`.
4. Inspect the entry point, `workflow_state`, gateway expressions, and all Script Tasks.
5. Supply `case_input` and `user_decision` (`apply`, `cancel`, or `preserve_for_later`) and start a debug instance.
6. Import `NextFlow-RealCase.bpmn` only after the Demo topology is visible.
7. Follow `bind-real-case.md`; every task containing `BIND REQUIRED` must be resolved before cloud execution.

Import success proves that Studio Web accepted the model. It does not prove resource binding or runtime execution.
