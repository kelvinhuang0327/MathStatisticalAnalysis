# LotteryNew wiki integrity audit

Status: P600A VERIFIED ｜ pin `520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f`

The requested `wiki/README.md` index does not exist at the pinned commit and has no reachable Git history. An ignored unmanaged copy in one dirty active checkout was not copied, trusted, or treated as canonical.

The committed `.ai/ai-wiki/INDEX.yml` is therefore the only machine-declared wiki index available at the pin. Its nine declared routes resolve through the recorded relocation from `ai-wiki/` to `.ai/ai-wiki/`.

| Route | Status | Evidence |
|---|---|---|
| `wiki/README.md` | MISSING | absent at pin and in reachable history; unmanaged checkout copy excluded |
| `.ai/ai-wiki/modules/frontend-spa.md` | PRESENT | tracked at pin |
| `.ai/ai-wiki/modules/backend-api.md` | PRESENT | tracked at pin |
| `.ai/ai-wiki/modules/research-tooling.md` | PRESENT | tracked at pin |
| `.ai/ai-wiki/modules/data-assets.md` | PRESENT | tracked at pin |
| `.ai/ai-wiki/flows/prediction-request.md` | PRESENT | tracked at pin |
| `.ai/ai-wiki/flows/strategy-research-cycle.md` | PRESENT | tracked at pin |
| `.ai/ai-wiki/modules/orchestration-runtime.md` | SUPERSEDED | page marks itself stale and redirects to current context/runbook |
| `.ai/ai-wiki/flows/startup-and-health.md` | SUPERSEDED | page marks itself stale and redirects to current context/runbook |
| `.ai/ai-wiki/flows/llm-execution-control.md` | SUPERSEDED | page marks itself stale and redirects to current context/runbook |
| `wiki/system/randomness_final_verdict.md` | PRESENT | tracked but not indexed |
| `wiki/system/replay_data_hygiene.md` | PRESENT | tracked but not indexed |

Summary: PRESENT 8, SUPERSEDED 3, MISSING 1, UNKNOWN_LOCATION 0.

No missing page was recovered from an unknown worktree. The missing index has no provable committed last path or commit, so its last provable location is recorded as `NONE`.
