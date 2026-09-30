# B649 Direct Exact Success Coverage vs Sealed v6: strict PRE_DRAW OOS R1

Evaluation cutoff: **2026-09-30 (Asia/Taipei)**<br>
Primary K: **K10**<br>
Secondary K: **K20 (descriptive only)**<br>
Primary verdict: **INSUFFICIENT_EVIDENCE**<br>
READY_FOR_BRANCH6_ADOPTION: **NO**

## Protocol

The candidate was generated from each target's timestamped PRE_DRAW 11-stream records. The frozen ordered pool uses the pinned K-DPP pool builder with an empty quality map (support count descending, then ticket ascending). The selector and sealed-v6 portfolios were written to the outcome-blind freeze artifact before the replay opened the result database.

Each eligible pair uses the same target draw and official BIG_LOTTO outcome. The scoring phase used the canonical prize evaluator and read the application database in query-only mode. The exact fair-draw probabilities below are structural diagnostics; they are not observed OOS lift.

Frozen portfolio artifact SHA-256: `1aa85daa9cfdcebe4c4de45275388fa858869c6821fa19205b4d7ade226f7013`
Read-only outcome database SHA-256 (unchanged across scoring): `beb7ed32e5f395be6d60fdd4f2836c774cb60a28c0d17b18673630d349110c0c`
Official result reference: [Taiwan Lottery Lotto 649 results](https://apislb.taiwanlottery.com/lotto/result/lotto649/).

## Paired PRE_DRAW results

| K | Eligible pairs | Candidate wins | Sealed-v6 wins | Candidate-only | Sealed-only | Both win | Both lose | Discordant | Absolute delta | Relative lift | Exact McNemar p | Assessment |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| K10 | 10 | 3 | 3 | 2 | 2 | 1 | 5 | 4 | 0.00 pp | 0.00% | 1/1 | INSUFFICIENT_EVIDENCE |
| K20 | 10 | 4 | 4 | 4 | 4 | 0 | 2 | 8 | 0.00 pp | 0.00% | 1/1 | DESCRIPTIVE ONLY |

### Per-draw paired outcomes

| Draw | Date | K10 candidate / v6 | K20 candidate / v6 | Official API outcome |
|---|---|---|---|---|
| 115000081 | 2026-08-21 | loss / loss | win / loss | 8,14,23,24,26,47 + special 30 |
| 115000082 | 2026-08-25 | win / loss | win / loss | 12,24,26,32,35,40 + special 6 |
| 115000083 | 2026-08-28 | win / win | win / loss | 9,20,23,26,36,44 + special 4 |
| 115000086 | 2026-09-08 | loss / loss | loss / win | 3,15,28,35,47,49 + special 27 |
| 115000087 | 2026-09-11 | loss / win | loss / win | 12,15,19,27,43,48 + special 25 |
| 115000088 | 2026-09-15 | win / loss | win / loss | 2,3,18,21,22,39 + special 7 |
| 115000089 | 2026-09-18 | loss / loss | loss / win | 1,6,14,21,31,35 + special 16 |
| 115000090 | 2026-09-22 | loss / loss | loss / loss | 14,15,18,30,35,45 + special 10 |
| 115000091 | 2026-09-25 | loss / loss | loss / win | 5,13,24,25,28,33 + special 40 |
| 115000092 | 2026-09-29 | loss / win | loss / loss | 1,2,4,13,30,38 + special 27 |

## Exact fair-draw geometry (diagnostic only)

### K10

Candidate mean across eligible per-draw portfolios: `33543547/122715120` (27.334486%); range `2097793/7809144` to `23799499/85900584`.
Sealed v6: `536005/1827672` (29.327199%).
Mean geometry difference: `-17117521/859005840` (-1.992713 pp).

These exact uniform-draw quantities describe portfolio geometry. The paired PRE_DRAW outcome counts above determine the OOS result.

| Draw | Candidate exact probability | Sealed-v6 exact probability |
|---|---:|---:|
| 115000081 | `23491925/85900584` | `536005/1827672` |
| 115000082 | `23682823/85900584` | `536005/1827672` |
| 115000083 | `11891657/42950292` | `536005/1827672` |
| 115000086 | `7790093/28633528` | `536005/1827672` |
| 115000087 | `23799499/85900584` | `536005/1827672` |
| 115000088 | `2097793/7809144` | `536005/1827672` |
| 115000089 | `7792581/28633528` | `536005/1827672` |
| 115000090 | `509545/1867404` | `536005/1827672` |
| 115000091 | `23590727/85900584` | `536005/1827672` |
| 115000092 | `3865621/14316764` | `536005/1827672` |

### K20

Candidate mean across eligible per-draw portfolios: `2973701/7469616` (39.810627%); range `5532831/14316764` to `34949219/85900584`.
Sealed v6: `44748521/85900584` (52.093384%).
Mean geometry difference: `-149659/1218448` (-12.282756 pp).

These exact uniform-draw quantities describe portfolio geometry. The paired PRE_DRAW outcome counts above determine the OOS result.

| Draw | Candidate exact probability | Sealed-v6 exact probability |
|---|---:|---:|
| 115000081 | `16797103/42950292` | `44748521/85900584` |
| 115000082 | `8471273/21475146` | `44748521/85900584` |
| 115000083 | `33899879/85900584` | `44748521/85900584` |
| 115000086 | `34619677/85900584` | `44748521/85900584` |
| 115000087 | `34932263/85900584` | `44748521/85900584` |
| 115000088 | `5532831/14316764` | `44748521/85900584` |
| 115000089 | `34949219/85900584` | `44748521/85900584` |
| 115000090 | `34922383/85900584` | `44748521/85900584` |
| 115000091 | `11362223/28633528` | `44748521/85900584` |
| 115000092 | `33889241/85900584` | `44748521/85900584` |

## Excluded targets and reasons

- 115000079: INCOMPLETE_PRE_DRAW_STREAM_SET (excluded for K10, K20; 1/11 stream snapshots, pool=2).
- 115000080: INCOMPLETE_PRE_DRAW_STREAM_SET (excluded for K10, K20; 6/11 stream snapshots, pool=7).
- 115000084: NO_SAVED_PREDRAW_STREAMS (excluded for K10, K20; 0 stream snapshots, pool=0).
- 115000085: NO_SAVED_PREDRAW_STREAMS (excluded for K10, K20; 0 stream snapshots, pool=0).
- 115000093: TARGET_AFTER_EVALUATION_CUTOFF (excluded for K10, K20; 11 stream snapshots, pool=21, target date 2026-10-02, after cutoff 2026-09-30).

## Verdict rule

A positive or negative lift is validated only when the paired exact two-sided McNemar p-value is below 0.05 and the delta has the same direction. If fewer than six pairs are discordant, even a unanimous direction cannot reach 0.05 in this exact test, so the verdict is INSUFFICIENT_EVIDENCE. K20 cannot change the primary K10 verdict.

## Boundaries

Candidate algorithm, two-swap bound, tie-breaks, pool order, and K were not tuned. Sealed v6 was read-only. No production activation, Lane3 mutation, push, PR, or merge occurred.
