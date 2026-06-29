# Edge Workflow Comprehensive System Test

## 1. Objective

Test the complete Edge workflow from folder attachment through Final Output.

The test must determine whether the system:
- Captures the original target correctly.
- Detects real issues from target content.
- Produces the required three Phase 1 statements.
- Calculates information completeness from actual information.
- Separates information-complete items from information-gap items.
- Allows good items to continue while isolated items receive targeted research.
- Executes real candidate-copy mutation during Simulation.
- Converges all paths at Inspection.
- Produces a valid before/after Relay result.
- Releases only the approved result to the real target.
- Produces complete final reports for resolved and unresolved items.

Do not test only whether the pipeline reaches Relay.
Do not treat the entire project as a single pass/fail object.
The system must prove item-level routing.

## 2. Workflow Under Test

- Phase 0 — Snapshot
- Phase 1 — Scan + Analysis
- Phase 2 — Pre-simulation / Package Preparation
- Phase 3 — Simulation
- Phase 4 — Inspection
- Phase 5 — Relay
- Phase 6 — Final Output

Required routing:
```
Phase 2 score >= 93.91% → all qualified items continue to Simulation
Phase 2 score < 93.91%
  → information-complete items continue to Simulation
  → information-gap items branch to Isolation
  → fixable isolated items retry and rejoin
  → unfixable isolated items become documented results
  → every path converges at Inspection
```

The score is an information-completeness score.
It is not a code-quality score.
It is not a whole-project pass/fail score.
Exactly 93.91 passes. 93.90 does not qualify.

## 3. Required Test Fixtures

Fixture A — Fully Clean Project
Fixture B — Broken Dependency With Known Resolution
Fixture C — Broken Dependency With Missing Resolution Information
Fixture D — Missing Import With Clear Local Fix
Fixture E — Missing Import With Ambiguous Ownership
Fixture F — Syntax Error
Fixture G — Mixed Project (MOST IMPORTANT)
Fixture H — Simulation-Time Failure
Fixture I — Unfixable Item
Fixture J — User Cancel
Fixture K — User Apply

## 4. Required Test Matrix

| Case | Phase 1 | Phase 2 | Phase 3 | Relay result |
|------|---------|---------|---------|--------------|
| Clean | No issues | All complete | Runs | Fully resolved |
| Known dependency fix | Conflict found | Complete information | Fix executes | Resolved |
| Unknown dependency resolution | Conflict found | Item incomplete | Good items continue; issue isolates | Pending or unresolved |
| Clear missing import | Import found | Complete information | Fix executes | Resolved |
| Ambiguous generated import | Import found | Missing information | Isolates | Unresolved until info supplied |
| Syntax error | Parser failure | Usually complete | Candidate fix executes | Resolved if validation passes |
| Mixed project | Multiple findings | Split routing | Qualified items run | Mixed resolved/unresolved |
| Simulation runtime failure | Initially qualified | Passes completeness | Fails and isolates | Fix or unresolved report |
| Unfixable external requirement | Finding confirmed | Information remains unavailable | No unsafe mutation | Unresolved report |
| Apply | Candidate ready | — | Already complete | Released |
| Cancel | Candidate ready | — | Already complete | Original restored |

## 5. Implementation Order

1. Test fixtures and expected assertions
2. Real Phase 1 deterministic analysis
3. Structured findings and three required statements
4. Phase 2 item-level information-completeness scoring
5. Split routing and isolation briefs
6. Candidate-copy Simulation execution
7. Inspection convergence
8. Relay and Final Output reports
9. Full regression and end-to-end tests

## 6. Threshold Rules

- PASS_THRESHOLD = 9391 (integer hundredth-points)
- 93.91% passes (round(score*100) >= 9391)
- 93.90% does NOT pass
- Critical blockers override any numeric score
- The controller owns all transitions, not the agent
