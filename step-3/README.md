# Step 3: Run Pipeline on Chaos Input

Runs against 10 different failure modes (syntax breaks, missing deps, import cycles, invalid configs, runtime exceptions, tool failures, event corruption, partial state, snapshot corruption, dead tool calls).

**Expected result:** `Status: succeeded`, 8/8 phases, `partially_resolved` (6 resolved, 3 unresolved)

```powershell
.\run.ps1
```
