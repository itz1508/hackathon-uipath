# Package and deploy

1. Validate both BPMN files with `scripts/validate.ps1`.
2. Authenticate with `uip login` and confirm the intended tenant/folder.
3. Complete every Real-Case binding in Studio Web.
4. Pack with `scripts/pack.ps1 -Version 1.0.0`.
5. Verify package entries/hash with `scripts/verify-package.ps1`.
6. Publish or upload the generated `.nupkg` to Orchestrator.
7. Select `NextFlow Real Case` as the process entry point and configure package requirements.
8. Deploy and run one instance using the sample case.
9. Capture the instance ID, jobs, variables, incidents, Action Center decision, and final artifact references.

Do not call the process deployed or working until the cloud instance reaches `08 Final Result Locked` with `locked=true`.
