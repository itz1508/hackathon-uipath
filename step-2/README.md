# Step 2: Run Pipeline on Mixed Input

Runs against a folder with overlapping issue types (syntax errors, missing deps, ambiguous imports).

**Expected result:** `Status: succeeded`, 8/8 phases, `partially_resolved` (3 resolved, 1 unresolved)

```powershell
.\run.ps1
```
