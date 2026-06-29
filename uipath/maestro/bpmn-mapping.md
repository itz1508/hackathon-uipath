# BPMN Mapping Template

| Workflow element | BPMN element | Notes |
|---|---|---|
| Scan through recalibration | Service tasks | Read-only/advisory |
| Handoff Statement | Service task | Transfers built state |
| Admission conditions | Exclusive gateway | All readiness conditions required |
| Auto-Dependency mode | Exclusive gateway | ON or OFF from handoff |
| Isolation Add-On | Service task | Advisory; no execution authority |
| User apply/cancel | User task plus exclusive gateway | Explicit human authority |
| Apply relay | Service task | Mutation only after apply decision |
| Final lock | Service task | Terminal artifact |

No `.xaml`, package, queue, asset, credential, tenant, or deployed process is created in this phase.
