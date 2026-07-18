# Legacy Four-Prompt Responsibility Mapping

Document status: `DRAFT_FOR_OWNER_REVIEW`

Compatibility-analysis fixture only. This is migration evidence, not a policy source. The four
supplied files were read completely; only their generic capabilities are mapped into the new system.
Consumer-specific operational examples and repeated policy prose are intentionally not reproduced.

## Source inventory

| Legacy source | Version observed | Lines | Bytes | SHA-256 |
|---|---:|---:|---:|---|
| `[對話交接報告]— ChatGPT 對話總結.md` | Planner / Worker Trace v2 | 487 | 11,830 | `11d7bbd9138caf19c41f2f94f250818a21e1b15a050610e254dbd0f9ea38f846` |
| `[CEO] Decision Review Prompt .md` | Implementation-First v1 | 709 | 16,679 | `bbedaa3dc4652eae5b376a042d6cac99ac50182de025caf934f69afe9da1a695` |
| `[CTO] Technical Review Prompt .md` | Implementation-First v1 | 593 | 14,041 | `5611f4eda4b184a506f661581c6563f45e110b47cb7ff3fe97935e29bf014dae` |
| `Personal Planner Handoff Prompt.md` | v5.1 Lean Worktree Lifecycle Generic | 1,090 | 29,226 | `9bb4bd4682e30106ac1822f159742b25dcd9b9c5855c9b7414839b063a4f2743` |

Disposition values are `RETAINED_IN_ROLE`, `MOVED_TO_SHARED_CORE`, `MOVED_TO_ROUTING`,
`MOVED_TO_MANIFEST`, `REMOVED_DUPLICATE`, and `REMOVED_ROLE_VIOLATION`.

## Handoff Reporter mapping

| Legacy responsibility | Disposition | New owner / reason |
|---|---|---|
| Web conversation report is not a repo audit | `RETAINED_IN_ROLE` | Handoff source qualification boundary |
| Filter mixed conversation content to the active project | `RETAINED_IN_ROLE` | Handoff project filter |
| Initial goal, direction changes, and event timeline | `RETAINED_IN_ROLE` | Handoff narrative |
| Planner / Owner / Worker / Reviewer traceability | `RETAINED_IN_ROLE` | Handoff actor trace |
| Completed versus planned, stopped, excluded, or not run | `RETAINED_IN_ROLE` | Handoff truthfulness |
| Risks, blockers, unknowns, and evidenced state snapshot | `RETAINED_IN_ROLE` | Handoff output |
| Candidate memory entry | `RETAINED_IN_ROLE` | Proposal only; no write |
| Evidence tags and unexecuted-check handling | `MOVED_TO_SHARED_CORE` | One shared evidence vocabulary |
| `.ai` context and project paths | `MOVED_TO_MANIFEST` | Consumer profile/manifest values |
| Model and role routing matrix | `MOVED_TO_ROUTING` | Planner resolves routes |
| Full next Worker Prompt | `REMOVED_ROLE_VIOLATION` | Planner is sole renderer |
| Authorization-needed table or token packaging | `REMOVED_ROLE_VIOLATION` | Handoff cannot authorize |
| Exact repo/branch/worktree and cleanup decision | `REMOVED_ROLE_VIOLATION` | Planner and lifecycle own it |
| Repeated evidence, Phase 0, and STOP prose | `REMOVED_DUPLICATE` | Shared Core centralization |
| Long fixed 18-section response | `REMOVED_DUPLICATE` | Replaced by concise outcome contract |

## CEO Decision Reviewer mapping

| Legacy responsibility | Disposition | New owner / reason |
|---|---|---|
| Review recent-work value and system maturity | `RETAINED_IN_ROLE` | CEO value judgment |
| Distinguish substantive from superficial completion | `RETAINED_IN_ROLE` | CEO evidence-based assessment |
| Review CTO judgment and correct optimism/scope | `RETAINED_IN_ROLE` | CEO technical-decision review |
| Adopt, partially adopt, reject, or remain unknown | `RETAINED_IN_ROLE` | CEO decision vocabulary |
| P0 / P1 / P2 / P3+ prioritization | `RETAINED_IN_ROLE` | CEO priority judgment |
| Continue, pause, or pivot | `RETAINED_IN_ROLE` | CEO strategic direction |
| High-risk escalation and Owner decision requirement | `RETAINED_IN_ROLE` | CEO escalation, not authorization |
| Evidence, fact precedence, memory, and safety rules | `MOVED_TO_SHARED_CORE` | Shared semantics |
| Conditional CEO triggers | `MOVED_TO_ROUTING` | CEO is not routine |
| Project config, paths, checks, and risk overrides | `MOVED_TO_MANIFEST` | Consumer-owned context |
| Complete Worker Prompt generation | `REMOVED_ROLE_VIOLATION` | Planner only |
| Task Manifest or active-task ownership | `REMOVED_ROLE_VIOLATION` | Planner only |
| Implementation, branch, worktree, integration, cleanup | `REMOVED_ROLE_VIOLATION` | Worker/lifecycle responsibilities |
| Optional decision-file mode matrix | `REMOVED_ROLE_VIOLATION` | Not a shared CEO responsibility |
| Repeated Phase 0, authorization, Git, and STOP inventories | `REMOVED_DUPLICATE` | Shared Core/routing centralization |

## CTO Technical Reviewer mapping

| Legacy responsibility | Disposition | New owner / reason |
|---|---|---|
| Architecture and roadmap technical alignment | `RETAINED_IN_ROLE` | CTO review axis |
| Correctness and traceable data flow | `RETAINED_IN_ROLE` | CTO review axis |
| Testability, actual checks, gaps, and required tests | `RETAINED_IN_ROLE` | CTO review axis |
| Database, data, runtime, and output safety | `RETAINED_IN_ROLE` | CTO review axis |
| Security, secrets, and external-side-effect risk | `RETAINED_IN_ROLE` | CTO review axis |
| Dependency reuse and avoidable reinvention | `RETAINED_IN_ROLE` | CTO review axis |
| Developer workflow risk | `RETAINED_IN_ROLE` | Retained only when technically material |
| Blockers and one technical recommendation | `RETAINED_IN_ROLE` | CTO output |
| Evidence, precedence, memory, and shared safety | `MOVED_TO_SHARED_CORE` | Shared semantics |
| Technical invocation conditions | `MOVED_TO_ROUTING` | CTO is conditional |
| Project paths, protected data, commands, base/head | `MOVED_TO_MANIFEST` | Consumer-owned context |
| Full Worker Prompt generation | `REMOVED_ROLE_VIOLATION` | Planner only |
| Final manifest and Owner authorization ownership | `REMOVED_ROLE_VIOLATION` | Planner records; Owner decides |
| Routine mandatory review | `REMOVED_ROLE_VIOLATION` | Lean routes bypass CTO |
| Roadmap/bootstrap/active-task direct editing modes | `REMOVED_ROLE_VIOLATION` | Separate authorized tasks only |
| Repeated Phase 0, Git, authorization, and STOP prose | `REMOVED_DUPLICATE` | Shared Core/routing centralization |

## Planner / Task Compiler mapping

| Legacy responsibility | Disposition | New owner / reason |
|---|---|---|
| Resolve one next task from current evidence | `RETAINED_IN_ROLE` | Planner compilation purpose |
| Compile and lint one Task Manifest | `RETAINED_IN_ROLE` | Sole manifest compiler |
| Render one complete Worker Prompt | `RETAINED_IN_ROLE` | Sole template renderer |
| Select worktree mode and exact approved path | `RETAINED_IN_ROLE` | Planner decision from project context |
| Include normal lifecycle cleanup in the task | `RETAINED_IN_ROLE` | Avoid cleanup-only governance |
| Optional active-task compatibility projection | `RETAINED_IN_ROLE` | Derived from the same manifest |
| Evidence states, precedence, memory, and authorization classes | `MOVED_TO_SHARED_CORE` | Shared semantics |
| LOW/MEDIUM/technical/strategic routes and role triggers | `MOVED_TO_ROUTING` | Shared route table |
| Worktree modes and lifecycle gates | `MOVED_TO_ROUTING` | Shared lifecycle contract |
| Project identity, paths, restrictions, checks, risk override | `MOVED_TO_MANIFEST` | Consumer-owned variables |
| Authorization reference and current base/head | `MOVED_TO_MANIFEST` | Task-bound state |
| Multiple Worker-prompt generators and variants | `REMOVED_DUPLICATE` | One canonical template |
| Repeated Phase 0, evidence, authorization, and STOP prose | `REMOVED_DUPLICATE` | Shared Core centralization |
| Obsolete permanent-worktree and cleanup detail | `REMOVED_DUPLICATE` | Four concise modes plus lifecycle |
| Fabricating or inheriting Owner authorization | `REMOVED_ROLE_VIOLATION` | Owner-only decision |
| Impersonating CEO/CTO or generating competing tasks | `REMOVED_ROLE_VIOLATION` | Role separation and one-task rule |

## Shared versus project-specific result

The shared system owns evidence states, fact precedence, authorization classes, risk routing, role
boundaries, worktree modes, lifecycle, manifest shape, rendering, memory semantics, STOP/WARN, and
final classifications. Each consumer owns its identity, repository/branch, allowed and protected
paths, data/runtime restrictions, verification commands, exact worktree, risk overrides,
authorization evidence, and current base/head through its profile and manifest.
