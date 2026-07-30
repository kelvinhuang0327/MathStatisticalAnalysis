# Executable Worker Task — {{TASK_ID}}: {{TASK_TITLE}}

Document status: `DRAFT_FOR_OWNER_REVIEW`
Rendered by: Planner / Task Compiler

## Decision envelope

- Risk: `{{RISK_LEVEL}}`
- Authorization class: `{{AUTHORIZATION_CLASS}}`
- Authorization state: `{{AUTHORIZATION_STATE}}`
- Owner statement reference: `{{OWNER_STATEMENT_REF}}`
- Route: `{{ROUTING_PATH}}`
- Stages: {{ROUTING_STAGES_INLINE}}

The Owner statement reference is evidence metadata only; it does not independently authorize
execution. This prompt records but does not create authorization. STOP if the required authorization
state is not satisfied or if the live task exceeds the authorized scope.

## Project context

- Project: `{{PROJECT_IDENTITY}}`
- Canonical repository: `{{CANONICAL_REPO}}`
- Canonical branch: `{{CANONICAL_BRANCH}}`
- Expected base: `{{BASE_SHA}}`
- Expected head: `{{HEAD_SHA}}`
- Project profile: `{{PROFILE_PATH}}`
- Worktree mode: `{{WORKTREE_MODE}}`
- Exact worktree path: `{{WORKTREE_PATH}}`
- Exact task branch: `{{WORKTREE_BRANCH}}`

Read the repo-local project profile when available, then observe the relevant live state. Consumer
context overrides examples; the manifest does not override contrary live facts.

## Goal

{{TASK_GOAL}}

## Allowed reads

{{ALLOWED_READS}}

## Allowed writes

{{ALLOWED_WRITES}}

## Protected paths

{{PROTECTED_PATHS}}

## Forbidden actions

{{FORBIDDEN_ACTIONS}}

## Execution

{{TASK_STEPS}}

Before the first write, record project root, branch, head, upstream if present, dirty/staged state,
selected worktree identity, and relevant protected-state observations. Preserve unrelated dirty work.
STOP on project mismatch, manifest/profile conflict, scope expansion, missing authorization, unsafe
worktree state, protected-data risk, or a failed hard gate. Do not create a fallback path.

## Verification

Run only checks authorized by the manifest. Record each as `PASS`, `FAIL`, `NOT_RUN`, `UNKNOWN`,
`STALE`, or `OUTDATED` and bind results to the observed state.

Commands:

{{VERIFICATION_COMMANDS}}

Required observations:

{{EXPECTED_OBSERVATIONS}}

## Memory and lifecycle

- Memory read: `{{MEMORY_READ}}`
- Memory write: `{{MEMORY_WRITE}}`
- Integration: {{LIFECYCLE_INTEGRATION}}
- Cleanup: {{LIFECYCLE_CLEANUP}}

Standard cleanup is part of this task only when its preconditions pass and no force is needed.
Never delete durable evidence or unrelated work. External activation or publication is absent unless
the manifest explicitly authorizes it.

## Handoff

Report the outcome first, exact branch/base/head, changed paths, commands actually run, observed
counts/results, authorization used, lifecycle state, external effects, remaining risks, and these
required fields:

{{HANDOFF_FIELDS}}

Finish with the acting role and exactly one shared classification: `READY`, `READY_WITH_RISKS`,
`NEEDS_DECISION`, or `BLOCKED`.
