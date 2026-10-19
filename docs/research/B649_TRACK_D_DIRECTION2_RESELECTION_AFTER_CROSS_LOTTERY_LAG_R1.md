# B649 Track D — Direction 2 Reselection After Cross-Lottery Lag R1

TASK_ID: `B649_TRACK_D_DIRECTION2_RESELECTION_AFTER_CROSS_LOTTERY_LAG_R1`
MODE: `READ_ONLY_RESEARCH_DECISION`
STATUS: `COMPLETE`
DATE: 2026-08-16

## Input verified (not taken on faith)

Read `.task-data/B649_TRACK_B_CROSS_LOTTERY_LAGGED_CONTEXT_NATIVE_PREDICTION_LEVEL1_R1/{report.md,locked_config.json,placebo_results.csv}` directly. Confirms: `STATUS: COMPLETE`, `RESEARCH_CLASSIFICATION: WEAK_SIGNAL`, `DECISION: DO_NOT_ADVANCE`. Locked config `C026`/`PLUS_BOTH` (T539 window 60, P638 window 20) beat the B649-only baseline on 300-target chronological holdout: M2+ +0.046667, M3+ +0.016667, positive in 5/5 blocks. Gate `real_beats_all_placebos: FAIL` — the `MISALIGNED_28_DAY_STALE` placebo (ΔM2 +0.053333) beat the real aligned signal (ΔM2 +0.046667), while the real signal beat the other two placebos (shuffled-prior-date, feature-count-matched). This result had no memory entry until this task backfilled it — the prior session's quota exhaustion happened after this task, not at the ball-set-acquisition task the original continuation packet named.

## Reconsideration against 5 stated priorities

(new info/representation · low era-proxy risk · chronological-transfer potential · direct M2+/M3+ path · failure-information value)

| Option | New info/repr. | Era-proxy risk | Transfer potential | Direct M2+/M3+ path | Failure-info value | Verdict |
|---|---|---|---|---|---|---|
| A. Structured contrastive legal-set quality target | representation-only, no new raw data | **Low** — pure objective change, untouched by any date/era dimension | Medium — still same B649 substrate | Yes, directly | **High** — last live "wrong objective" hypothesis; closes it cleanly either way | **Selected** |
| C. Cross-lottery native replication (T539-first) | new population, same mechanism | Low-medium | Its own source report already rated this `LOW-MEDIUM` prior expectation | Yes | Low-medium — re-tests "structure in raw draw history," already null via marginal/pair/triple/quadruple/uniformity lines | Not selected |
| D. Genuinely orthogonal external information (another candidate) | **None ready** — 14 metadata families + equipment + venue + cross-lottery-as-metadata + cross-lottery-as-lagged-outcome are now all closed | n/a | n/a | n/a | Would need a fresh discovery sub-task first | Not selected now |
| B/E (generation mechanism / other synthesis) | No new input | n/a | n/a | n/a | Low without a new input or target change | Not selected |

**Additional evidence beyond the predecessor's own pre-registration:** the failed cross-lottery-lag result is itself a soft argument against A's competitors, not just a neutral null. A stale 28-day-old cross-lottery snapshot outperforming the real aligned one is the signature of a slow-moving era/drift confound, not causal lag-dependence — reinforcing that another temporal/external-data variant (C or a new D candidate) is likely to hit the same confound. Option A is the only candidate that changes the objective/representation rather than the temporal data source, sidestepping that specific risk.

## D decision

`PIVOT_TO_STRUCTURED_CONTRASTIVE_LEGAL_SET_QUALITY_TARGET`

## NEXT_TASK_ID (B)

`B649_TRACK_B_STRUCTURED_CONTRASTIVE_LEGAL_SET_QUALITY_LEVEL1_R1`

(Not started. No new data source — reuses existing sealed B649 history. Needs: a frozen matched-negative protocol, a bounded legal-set scorer trained on relative match-depth ordering rather than 6 independent absolute-number labels, and the same chronological dev/holdout replay discipline used by the just-closed cross-lottery task.)

## FINAL

TASK_ID: B649_TRACK_D_DIRECTION2_RESELECTION_AFTER_CROSS_LOTTERY_LAG_R1
STATUS: COMPLETE
D_DECISION: PIVOT_TO_STRUCTURED_CONTRASTIVE_LEGAL_SET_QUALITY_TARGET
NEXT_TASK_ID: B649_TRACK_B_STRUCTURED_CONTRASTIVE_LEGAL_SET_QUALITY_LEVEL1_R1
COHORT_V2_PROSPECTIVE_DATA_USED: NO
B_EXPERIMENT_EXECUTED_THIS_TASK: NO
REPO_MUTATION: NONE
DB_MUTATION: NONE
END
