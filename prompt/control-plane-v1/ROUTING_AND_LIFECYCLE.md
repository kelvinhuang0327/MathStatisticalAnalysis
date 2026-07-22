# Shared Routing and Lifecycle v1

Document status: `DRAFT_FOR_OWNER_REVIEW`

This canonical source defines when roles run and how a compiled task moves through delivery.

<!-- SHARED_ROUTING:START -->
## Risk and route selection

Classify the concrete action, not the document label. Start at the project profile's risk floor and
raise risk for triggered side effects or uncertainty. Never lower a project override without a
current explicit Owner decision.

- `LOW`: read-only inspection, analysis, or handoff with no repository or external mutation.
- `MEDIUM`: reversible local implementation or ordinary delivery work within an exact allowlist.
- `HIGH`: irreversible/destructive action, production or executable activation, protected data or
  database write, credential/secret handling, payment, external message/publication, or equivalent
  externally observable effect.

Technical routing triggers include architectural boundary changes, security or dependency changes,
data/database/runtime safety, concurrency, migrations, uncertain correctness, material test gaps, or
conflicting technical evidence. CEO routing triggers include `HIGH` risk, investment or priority
conflicts, continue/pause/pivot decisions, or disagreement after CTO review. Routine work has no CEO
or CTO hop.

The exact default routes are machine-readable and normative:

<!-- ROUTE_TABLE:START -->
```json
{
  "LOW_READ_ONLY": {
    "risk": "LOW",
    "authorization": "NONE",
    "stages": ["PLANNER", "WORKER", "HANDOFF"]
  },
  "MEDIUM_IMPLEMENTATION": {
    "risk": "MEDIUM",
    "authorization": "SINGLE_PROMPT",
    "stages": ["PLANNER", "WORKER", "INDEPENDENT_FIXED_HEAD_REVIEW", "INTEGRATION", "STANDARD_LIFECYCLE_CLEANUP"]
  },
  "TECHNICAL": {
    "risk": "MEDIUM",
    "authorization": "SINGLE_PROMPT",
    "stages": ["CTO", "PLANNER", "WORKER", "REVIEW"]
  },
  "STRATEGIC_HIGH": {
    "risk": "HIGH",
    "authorization": "STANDALONE",
    "stages": ["CTO", "CEO", "OWNER_DECISION", "PLANNER", "WORKER", "REVIEW"]
  }
}
```
<!-- ROUTE_TABLE:END -->

If a required upstream decision is missing, return `NEEDS_DECISION`; do not render executable work.
The Handoff Reporter may run after any route when a handoff is useful, but it does not become a gate.
<!-- SHARED_ROUTING:END -->

<!-- PLANNER_ROUTING:START -->
## Planner compilation and lifecycle

### Context boundary

The consumer project supplies these values through `.ai/agent-profile.yaml` and the Task Manifest:
project identity, canonical repository and branch, allowed/protected paths, data/database/runtime
restrictions, verification commands, approved worktree roots and exact path, risk overrides,
authorization evidence, and current base/head. A missing value remains `UNKNOWN`; examples are never
defaults.

### Worktree modes

Choose exactly one mode and record it in the manifest:

1. `NOT_APPLICABLE`: read-only/no-checkout work. Create no branch or worktree.
2. `REUSABLE_AGENT_WORKTREE`: default sequential implementation in a clean, approved reusable path.
3. `EPHEMERAL_TASK_WORKTREE`: only for approved parallelism or isolation; use one exact path and no
   fallback.
4. `EXISTING_TASK_WORKTREE`: continue an existing review/fix at one verified exact path.

Never invent a path. A dirty, active, missing-required, wrong-branch, or wrong-head worktree is a
STOP. Do not stash, reset, clean, force-remove, or broadly prune to bypass it.

### Task lifecycle

`DRAFT` -> `LINTED` -> `AUTHORIZED` (or `NOT_REQUIRED`) -> `RUNNING` -> `VERIFIED` -> `REVIEWED`
-> `INTEGRATED` -> `CLEANED` -> `COMPLETE`.

- The Planner owns `DRAFT` and `LINTED`; only Owner evidence can satisfy required authorization.
- The Worker acts only after lint and authorization gates pass.
- MEDIUM implementation receives independent review bound to the exact head before integration.
- Integration and cleanup run only when manifest preconditions and authorization permit them.
- Standard cleanup belongs to the same task: restore an approved reusable worktree after exact-head
  checks, remove a clean approved ephemeral worktree when its policy allows, and delete merged task
  branches without force only after verified merge containment.
- Pending/failed checks, dirty state, Owner retention override, or need for force stops cleanup and
  leaves an explicit blocker. Never delete durable evidence or unrelated work.
- Metadata-only lifecycle publication follows its actual side effects. Production promotion,
  executable activation, protected data writes, and irreversible external actions remain `HIGH`.

### Manifest and rendering gates

Lint before rendering. Require schema validity, a route whose risk/authorization/stages match the
route table, an exact allowed scope, verification observations, and safe placeholders rather than
secrets or real tokens. Render the complete Worker Prompt only from `WORKER_TASK_TEMPLATE.md`.
Generated text must remain byte-reproducible for the same five durable sources and manifest.
<!-- PLANNER_ROUTING:END -->
