# Run the sample configuration repair

```powershell
.\scripts\debug-demo.ps1 -Decision apply -Scenario happy_path
```

Other decision paths:

```powershell
.\scripts\debug-demo.ps1 -Decision cancel
.\scripts\debug-demo.ps1 -Decision preserve_for_later
```

Failure proofs:

```powershell
.\scripts\debug-demo.ps1 -Scenario readiness_rejected
.\scripts\debug-demo.ps1 -Scenario simulation_failure
```

The command prints a JSON result and a temp-directory path containing `workflow-state.json`, `final-result.json`, the sandbox copy, and—only for Apply—the separate live-target copy. Blocked scenarios intentionally return non-zero.
