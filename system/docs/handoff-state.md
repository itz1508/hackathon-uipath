# Handoff State

The Handoff Statement carries the built workflow state from completed recalibration to Pre-Simulation. It identifies what happened, what is available, what remains unresolved, and the required next action.

Required fields are defined by `uipath/schemas/handoff.schema.json`. `current_stage` is `handoff_statement`, `completed_stage` is `02.25-recalibration`, and `destination_stage` is `02.5-pre-simulation`.

`scope.locked` must be true. Artifact references are non-empty identifiers but are not proven to exist by schema validation. `missing_information` records absent inputs; `unresolved_items` records known incomplete work. Isolation requires at least one enumerated `isolation_reasons` value and routes to `build_isolation_addon`.

Use `uipath/templates/handoff.template.json` as the reusable starting point and `workflow/examples/` for populated contract examples.
