# Dependency Policy

## Auto-Dependency ON

`enabled=true` and `status="on"` permits only detection, use, or local preparation of dependencies already declared in the handoff and inside the locked scope. It does not authorize installation, download, credentials, external access, services, or undeclared tools.

## Auto-Dependency OFF

`enabled=false` and `status="off"` requires every dependency record to use `action_taken="none"`. Missing required dependencies are reported with a participant action and block Simulation readiness.

## Isolation

A missing identifiable dependency does not by itself require Isolation. Isolation is limited to unclear dependency identity, unclear requirement, failure of the normal tool to resolve it, missing Pre-Simulation information, or undefined success criteria.

Schema validation enforces ON/OFF shape. Python contract checks enforce unique dependency IDs, unresolved-reference membership, and declared-action membership.
