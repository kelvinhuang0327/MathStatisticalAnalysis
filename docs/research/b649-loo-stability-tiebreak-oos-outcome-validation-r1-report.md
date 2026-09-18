# B649 frozen LOO stability tiebreak: paired OOS outcome validation R1

`TASK_STATUS: COMPLETE` · `CANDIDATE_VERDICT: INSUFFICIENT_EVIDENCE` · `NEXT_STAGE: NONE`

The frozen candidate did not improve observed official-any-prize success. Across 1,779 paired draws, K5 and K20 tied the incumbent; K10 lost one successful draw. Primary discordance was only 0 / 1 / 0 draws, below the predeclared 10-discordance adequacy gate. This is `INSUFFICIENT_EVIDENCE` / `INSUFFICIENT_POWER`, not a statistically established negative effect or proof of equivalence.

Principal metric: `OFFICIAL_ANY_PRIZE`, the proportion of paired draws with at least one officially winning ticket, including 2 main matches plus special. Baseline for K5/K10/K20: `B649_OPERATIONAL_PORTFOLIO_SELECTOR` v1.0.0, the exact eleven-stream pool, empty quality mapping, distinct-stream support then lexical ticket. K2/K3: `NO_CURRENT_OPERATIONAL_INCUMBENT`; no synthetic baseline was substituted.

| K | Paired n | Baseline wins / rate | Candidate wins / rate | Absolute delta (pp) | Relative lift | Nominal family-adjusted interval (pp) | Discordant draws |
|---|---:|---:|---:|---:|---:|---:|---:|
| 5 | 1779 | 248 / 13.9404% | 248 / 13.9404% | +0.0000 | +0.0000% | [+0.0000, +0.0000] | 0 |
| 10 | 1779 | 432 / 24.2833% | 431 / 24.2271% | -0.0562 | -0.2315% | [-0.2248, +0.0000] | 1 |
| 20 | 1779 | 711 / 39.9663% | 711 / 39.9663% | +0.0000 | +0.0000% | [+0.0000, +0.0000] | 0 |

All three exact paired McNemar p-values and Holm-adjusted p-values are 1.0. Intervals use 10,000 seeded paired draw bootstrap samples, with nominal 98.333% marginal coverage for the three-K family. Zero-width intervals arise from no observed discordant pairs; they are not proof of zero population uncertainty. IID bootstrap and McNemar assumptions do not establish temporal independence.

| K | P(max hits ≥3), baseline → candidate | P(max hits ≥4), baseline → candidate | Expected max matches, baseline → candidate | Changed ticket-set draws |
|---|---|---|---|---:|
| 5 | 140/1779 (7.8696%) → 139/1779 (7.8134%) | 8/1779 (0.4497%) → 8/1779 (0.4497%) | 1.527263 → 1.526700 | 41 |
| 10 | 260/1779 (14.6150%) → 259/1779 (14.5587%) | 19/1779 (1.0680%) → 19/1779 (1.0680%) | 1.847105 → 1.845419 | 37 |
| 20 | 465/1779 (26.1383%) → 465/1779 (26.1383%) | 35/1779 (1.9674%) → 35/1779 (1.9674%) | 2.159078 → 2.159078 | 0 |

Full-history secondary directions are flat or slightly negative. Recent stability uses the last 750 / 300 / 50 canonical draws, containing 682 / 281 / 49 valid pairs respectively. K10 official success delta is −0.1466 pp in RECENT_750 and zero in RECENT_300/50; K5/K20 official deltas are zero throughout. K5 expected max matches improves by 0.003559 in RECENT_300, while its principal metric remains tied. Overlapping windows are descriptive, not independent confirmations.

Ticket-level hit distributions below are counts for 0,1,2,3,4,5,6 main matches, respectively.

| K | Baseline hit distribution | Candidate hit distribution |
|---|---|---|
| 5 | [3861, 3687, 1193, 146, 8, 0, 0] | [3866, 3682, 1195, 144, 8, 0, 0] |
| 10 | [7676, 7385, 2412, 298, 19, 0, 0] | [7684, 7382, 2408, 297, 19, 0, 0] |
| 20 | [15328, 14701, 4902, 614, 35, 0, 0] | [15328, 14701, 4902, 614, 35, 0, 0] |

Coverage: 2,170 canonical draws (2007-01-02 through 2026-09-15); 200 warmup exclusions plus 191 exclusions with fewer than 20 distinct tickets. All K use the same 1,779 pairs, from 97000098 / 2008-12-05 to 115000088 / 2026-09-15: 81.9816% total coverage, 90.3046% after warmup. Joint K5/K10/K20 eligibility exactly follows the current materializer. Excluded dates/reasons and all actual ticket/max hits are in the JSON.

`LEAKAGE_STATUS: PASS_STRICT_PREFIX_AND_OUTCOME_ISOLATED_SELECTION`; all eleven producers receive only strictly earlier draw rows. Both frozen selections complete before the target outcome is scored. This reconstructs causal prefixes from the current canonical DB; it does not establish historical ingestion-time availability. Canonical data were read in one read-only snapshot and their logical hash was unchanged at result verification.

`OUTCOME_TUNING: NONE`; `READY_FOR_CONFIRMATORY_STAGE: NO`; `READY_FOR_BRANCH6_ADOPTION: NO`. Stage 2 and Stage 3 were not triggered. Publication and production remain outside this result.

Authority and validation:

- `BASE_HEAD` / `CANDIDATE_HEAD`: `fd5cabd8be8d8db564c51efdf2e3d56575a1cea3`.
- `BASE_TREE` / `CANDIDATE_TREE`: `903345ea425bb39bb49ae167caf6d855473ce7d2`.
- `CANDIDATE_METHOD`: `LOO_STABILITY_TIEBREAK_V1`.
- Canonical authority: `origin/main` resolved once to `bc9d5b4dac571bf361cd82c25213513ecbf191d1`, tree `1759aa35a681599f7452170299bf4bf76240a3db`.
- Result: [b649-loo-stability-tiebreak-oos-outcome-validation-r1-result.json](b649-loo-stability-tiebreak-oos-outcome-validation-r1-result.json), SHA-256 `d1d497b7d9b9cddd4a55f9261421c02de9bab8a988ab26cc3d6f4ca96dd5b4d3`.
- Canonical logical dataset SHA-256: `4b77c2abb1974a24e7eee2356e7bbd856203a790ceb86a3744d4f1de95156f8f`.
- Focused checks: 64 PASS, including exact identity, temporal guard, pairing, baseline identity, metric calculation and ranking determinism. A deliberate in-memory removal of the cutoff guard made its test fail; restore and recheck PASS.
- Affected replay/operational regressions: 59 PASS. Ruff PASS; scoped Pyright PASS (0 errors, 0 warnings); whitespace diff check PASS.
- Determinism: all paired candidate/baseline selections repeated; stream generation repeated at the first warmup-eligible and final target; all 5,337 draw-K rows independently rescored, all full/recent summaries reproduced exactly. A second complete stream-generation replay was not run.
- Initial launcher attempt failed before upstream execution because that checkout lacked `--run`. Resolved the existing clean `FABLE_LONG_RUNNING_ATOMIC_EXECUTION_GUARD_R1` launcher; protected replay and deterministic result audit then completed. Initial strict type/format checks were corrected before replay. No outcome-driven revisions followed scoring.
- Changed paths: this report, the linked result, `src/lottolab/research/b649_loo_oos_validation.py`, and `tests/unit/test_b649_loo_oos_validation.py`. Frozen upstream source was unchanged.
- Task-created retained surfaces: isolated worktree/branch; four task files; protected execution records/captures under the existing primary `.fable/checkpoints/B649_LOO_STABILITY_TIEBREAK_OOS_OUTCOME_VALIDATION_R1` namespace. Existing primary source edits were retained untouched. No task-created files were deleted.
- Local commit is the commit containing this report; exact final HEAD/tree are returned in the task handoff. `PUSH: NOT RUN`; `PR: NOT CREATED`; `PRODUCTION_MUTATION: NONE`.

INTENT: code does frozen same-draw, same-cutoff, same-K outcome replay; the check/task expects verified out-of-sample success lift; the opened spec says the principal success metric controls advancement and no positive lift is required for completion.
