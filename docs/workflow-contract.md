# Workflow Contract

## Stage sequence

The only template transition is the sequence documented in `README.md`. Recalibration is an internal Phase 02 activity and does not create another executable entrypoint.

## Common stage contract

Every stage definition states purpose, owner, inputs, outputs, allowed actions, prohibited actions, entry conditions, exit conditions, failure behavior, receiving stage, and authority boundary. A receiving stage must validate its input contract before using it.

## Stop conditions

Processing stops when an input is invalid, required information is absent, scope is unlocked, a required dependency is unavailable, admission fails, explicit user authority is required, or an artifact cannot be validated. Stopping must preserve the current state and identify the next action; it must not imply Isolation unless an allowed Isolation reason exists.

## Runtime responsibility

JSON Schema validates document shape and local conditional rules. Runtime code must validate cross-artifact references, dependency-ID uniqueness, unresolved-reference membership, actual file existence, hashes, action history, and authority.
