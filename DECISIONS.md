# DevFlow decisions

This file records the current MVP choices. Update it when implementation or evaluation changes a decision.

## Workflow model

- Dependencies are Finish-to-Start: the dependent task is blocked while any prerequisite is not Done.
- Dependencies stay within one project. Self-links and edges that create cycles are rejected.
- Cycle detection and critical-path calculation are iterative to avoid recursion-depth failures.
- Moving a blocked task to In Progress is allowed but returns a warning. This preserves team flexibility while making the blocker visible.
- Blocked state is computed from persisted dependencies and prerequisite statuses when a task is read; no background job is needed.

## Intelligence rules

- Findings are deterministic and include evidence. The backend computes them from stored project data, not client-supplied values.
- Initial defaults: bottleneck impact 3 downstream tasks; stale blocker 5 days; due soon 3 days; At Risk at 2 overdue High/Critical tasks, an overdue bottleneck with impact 5+, or a critical path longer than days remaining to the target date.
- These thresholds are initial assumptions. The five initial scenarios are recorded in `docs/INTELLIGENCE_EVALUATION.md`; broader evaluation and threshold tuning remain future work.
- Health indicators are heuristics, not guaranteed predictions.
- Workload counts are informational assignment counts, not a productivity measure.

## Data and lifecycle

- Task activity timestamps support stale-blocker calculations.
- Completing a task sets `completed_at`; reopening it clears that timestamp.
- Tasks may be deleted only by project managers and workspace Owners/Admins while the project is active. Deletion also removes related activity and dependency records through database cascades.
- Projects with tasks cannot be deleted. An empty project generally must be archived before deletion; workspace Admins can delete an empty active project.
- A workspace can be deleted only by its Owner and only after its projects are removed.

## Deferred scope

- Sprint planning, burndown, notifications, mentions, and background workers are out of the MVP scope.
- Pick no more than one stretch feature after core acceptance criteria and evaluation are complete.
- An AI feature is deferred until the deterministic baseline has been evaluated.
