# B649 Track D — Orthogonal Draw Metadata Feasibility Recon R1

**TASK_ID:** `B649_TRACK_D_ORTHOGONAL_DRAW_METADATA_FEASIBILITY_RECON_R1`  
**MODE:** `READ_ONLY_DISCOVERY_RECON`  
**DATE:** 2026-08-15 Asia/Taipei  
**STATUS:** `COMPLETE_WITH_SMALL_DATA_ACQUISITION_REQUIRED`

## Primary decision

`ORTHOGONAL_METADATA_REQUIRES_SMALL_DATA_ACQUISITION`

Exactly one selected source: **official archived pre-draw B649 ball-set assignment ID**.

This is a real orthogonal source, not a transform of historical winning-number sequences. Taiwan Lottery's official process says a draw guest selects the draw machine, ball set, and loading order before the draw. A direct spot-check of the archived 2026-02-21 broadcast (official API period `115000022`) visibly records main B649 **machine 1**, **ball set 2**, and **reverse loading direction** before the winning numbers are drawn: [machine selection at 6:44](https://www.youtube.com/watch?v=60oYVtUDx38&t=404s), [loading direction at 7:09](https://www.youtube.com/watch?v=60oYVtUDx38&t=429s), and [ball-set selection at 7:19](https://www.youtube.com/watch?v=60oYVtUDx38&t=439s). The local repo, DBs, CSV archives, and JSON provider do not store these assignments.

This is **not** evidence that ball-set ID predicts numbers. It only establishes a causally prior, physically relevant metadata source worth a bounded acquisition/coverage check.

## Evidence summary

- `[Confirmed]` Active `data/lottery_v2.db` has the expected schema but zero rows.
- `[Confirmed]` The read-only legacy snapshot has 2,124 canonical B649 rows covering 2007-01-02 through 2026-07-10. It stores draw period/date/numbers, but B649 `jackpot_amount`, `sell_amount`, `total_amount`, and `numbers_positional` are all NULL; there are no machine, ball-set, venue, protocol, maintenance, or operator columns.
- `[Confirmed]` Local annual ZIPs contain 2,074 unique B649 rows from 2007-01-02 through 2026-01-30. `銷售總額`, `銷售注數`, and `總獎金` are present and numeric in all 2,074 rows, but the local copies are incomplete after 2025-10-31/2026-01-30.
- `[Confirmed]` A live official API spot-check returned only `period`, `lotteryDate`, draw-number fields, `sellAmount`, `totalAmount`, and prize-assignment objects; it exposed no machine/ball-set/venue/operator/protocol field. The current adapter further retains only period, date, and numbers.
- `[Confirmed]` The [official draw process](https://www.taiwanlottery.com/run_lottery/info/) explicitly states that, before drawing, the guest selects the machine, ball set, and loading order. The [official FAQ](https://www.taiwanlottery.com/customer_service/faq/) publishes the current 20:30 draw time, Studio 5 venue, monthly maintenance/annual inspection cadence, and says sales/prize totals are announced before the draw.
- `[Confirmed]` Official/authorized video archives are discoverable at least at [2024-01-05](https://www.youtube.com/watch?v=T5Tq1vkcT6Y) and the directly inspected [2026-02-21](https://www.youtube.com/watch?v=60oYVtUDx38). Complete draw-by-draw coverage and pre-2024 availability were not audited.

## Metadata inventory

| Field | Availability status | PRE_DRAW_AVAILABLE | HISTORICAL_COVERAGE / DATA_QUALITY | JOIN_KEY | CAN_REPLAY_CAUSALLY | Possible P(match) mechanism / classification |
|---|---|---|---|---|---|---|
| Draw machine / machine ID | `EXISTS_UPSTREAM_BUT_NOT_STORED` | YES; selected before outcome | One 2026 B649 instance directly confirmed; 2024–2026 archive candidates exist; completeness `UNKNOWN`; visual quality MEDIUM | broadcast date + game → official `lotteryDate` + `period` | YES for outcome-blind retrospective coding; public availability before ticket cutoff not confirmed | Machine-specific airflow/geometry could interact with stable ball properties; hypothesis only (`PREDICTION_METADATA`) |
| Ball set / ball-set rotation | `EXISTS_UPSTREAM_BUT_NOT_STORED` | YES; selected before outcome | Same video boundary; exact history not yet extracted; visual label explicit; quality MEDIUM | broadcast date + game → period | YES under frozen video-coding protocol | Stable numbered-ball mass/diameter/wear differences could be set-specific; hypothesis only (`PREDICTION_METADATA`) |
| Draw session / sequence | `EXISTS_UPSTREAM_BUT_NOT_STORED` | YES | Broadcast order and on-screen prework timestamp visible; archive completeness `UNKNOWN`; quality MEDIUM | date + program + game order | YES if coded before viewing outcome | May proxy setup order, reuse, or thermal/session state; weak mechanism |
| Draw venue | `EXISTS_UPSTREAM_BUT_NOT_STORED` | YES | Current venue is published as SETN Studio 5; historical venue eras not compiled; quality HIGH current / UNKNOWN historical | date-era | YES for verified eras | Only useful at venue changes; nearly constant within era, so low information |
| Scheduled draw time | `EXISTS_UPSTREAM_BUT_NOT_STORED` | YES | Current official time 20:30; legacy P271H found no authoritative per-draw `draw_close_at` or exception calendar; historical quality LOW–MEDIUM | draw date | CONDITIONAL; exceptions need an as-of schedule | Weak proxy for protocol/session conditions; not independently persuasive |
| Weekday / holiday context | `EXISTS_LOCAL` for date/weekday; holiday label not stored | YES | 2,124 canonical B649 dates, 2007-01-02–2026-07-10; date quality HIGH | period + date | YES for weekday; holiday exceptions need external calendar | No direct physical mechanism; only a proxy for equipment/session assignment |
| Equipment maintenance / replacement | `POSSIBLY_EXTERNAL` | UNKNOWN for exact logs | Official cadence exists (monthly maintenance, annual inspection), but no draw-level dates or replacement log found; quality/coverage `UNKNOWN` | machine ID + maintenance date | NO with current evidence | Wear/reset could define real equipment regimes if exact logs become available |
| Machine/ball-set assignment history | `EXISTS_UPSTREAM_BUT_NOT_STORED` | YES relative to outcome | Recoverable candidate in archived pre-draw segments; full coverage `UNKNOWN`; not structured | period + date + game | YES after blinded extraction and timestamp verification | Enables within-machine/within-set comparisons and prevents era pooling |
| Sales / ticket volume | `EXISTS_LOCAL` in annual ZIP; also upstream API | YES immediately before draw announcement; not confirmed before 20:00 sales cutoff | 2,074/2,074 local B649 rows numeric, 2007-01-02–2026-01-30; recent local gap; quality HIGH for archived values | period + date | YES relative to outcome | No defensible causal path to draw probabilities; `PAYOUT/EV_METADATA`, not a P(match) feature |
| Jackpot / rollover state | `EXISTS_UPSTREAM_BUT_NOT_STORED`; local B649 DB column is 0/2,124 populated | YES for prior rollover/estimate | Current announcement/API source exists; historical completeness and as-of timestamps not audited | period | CONDITIONAL | Changes demand and payout sharing, not physical draw probability; `PAYOUT/EV_METADATA` |
| Draw protocol / version | `POSSIBLY_EXTERNAL` | YES as policy | Current process is public; no versioned per-draw protocol history found locally; quality current HIGH / historical `UNKNOWN` | effective-date era | CONDITIONAL on version dates | Protocol changes could alter physical initialization; no usable version history yet |
| Operator / session metadata | `POSSIBLY_EXTERNAL` | YES where visible | Host, guest, independent observer, and prework timestamp may be visible in videos, but stable IDs/roles and coverage are unverified | date + program | CONDITIONAL | At most a handling/session proxy; no current direct P(match) mechanism |
| Loading direction / order | `EXISTS_UPSTREAM_BUT_NOT_STORED` | YES | Explicitly visible in inspected 2026 pre-draw segment; complete history `UNKNOWN`; quality MEDIUM | date + game → period | YES for retrospective research | Changes initial conditions and may interact with a ball set; hypothesis only (`PREDICTION_METADATA`) |
| Abnormal draw / equipment incident marker | `POSSIBLY_EXTERNAL` | Usually NO (many incidents occur during drawing) | Official handling rules exist, but no structured per-draw incident history was found; coverage `UNKNOWN` | period/date/video | NO as a pre-draw feature unless an incident occurs before outcome and is timestamped | Useful mainly for exclusions/data quality, not routine prediction |

## Candidate ranking and acquisition boundary

1. **Ball-set ID — selected.** It maps most directly to persistent numbered physical objects and is visibly recorded upstream.
2. **Machine ID.** Also physically relevant and visible, but number-specific effects would usually require interaction with ball properties.
3. **Loading direction/order.** Causally prior and visible, but likely lower-dimensional and potentially less stable.

The acquisition task should be a small, frozen manual/OCR-assisted pilot—not a scraper or ingestion pipeline. It should first test whether a chronologically spaced B649 sample can be double-coded with unambiguous ball-set labels and joined to periods. Modeling must remain `NOT RUN` until coverage, label stability, and timestamp causality pass. The broadcast proves the assignment occurred before the draw, but it does **not** yet prove that ordinary viewers received it before the 20:00 ticket-sales cutoff; that operational limitation must be recorded separately.

## Final

TASK_ID:  
`B649_TRACK_D_ORTHOGONAL_DRAW_METADATA_FEASIBILITY_RECON_R1`

STATUS:  
`COMPLETE_WITH_SMALL_DATA_ACQUISITION_REQUIRED`

METADATA_FIELDS_CHECKED:  
14 field families: machine ID; ball set/rotation; session/sequence; venue; scheduled time; weekday/holiday; maintenance/replacement; assignment history; sales/ticket volume; jackpot/rollover; protocol/version; operator/session; loading direction/order; abnormal incident markers.

LOCAL_PRE_DRAW_FIELDS_FOUND:  
Draw period/date and derived weekday; archived sales total/ticket count/total prize exist locally but are `PAYOUT/EV_METADATA`, not P(match) features.

UPSTREAM_PRE_DRAW_FIELDS_FOUND:  
Machine ID, ball-set ID, loading direction/order, prework session timestamp/order, current venue/time, and pre-draw sales/prize announcements. Machine/ball/direction are visible in archived broadcasts but not structured in repo/API/DB.

EXTERNAL_POSSIBLE_FIELDS:  
Exact maintenance/replacement history, versioned protocol eras, operator/session identities, and per-draw abnormal-equipment logs.

TOP_3_METADATA_CANDIDATES:  
1. Ball-set ID from official archived pre-draw footage.  
2. Machine ID from the same footage.  
3. Loading direction/order from the same footage.

PRIMARY_DECISION:  
`ORTHOGONAL_METADATA_REQUIRES_SMALL_DATA_ACQUISITION`

SELECTED_METADATA_SOURCE:  
Official archived pre-draw B649 **ball-set assignment ID**.

WHY_IT_IS_ORTHOGONAL:  
It is an independently randomized physical-equipment assignment made before the outcome and is not derived from historical winning-number frequency, gap, entropy, motif, Markov state, higher-order combinations, or consensus geometry.

WHY_IT_COULD_AFFECT_P_MATCH:  
If—and only if—a numbered ball set has persistent within-set physical heterogeneity (mass, diameter, surface wear), conditioning on the selected set could expose set-specific outcome asymmetry that pooling across rotating sets hides. No such asymmetry is currently demonstrated.

HISTORICAL_COVERAGE:  
One B649 assignment instance directly confirmed for 2026-02-21 / period 115000022; official/authorized archive candidates confirmed from at least 2024-01-05 to 2026-02-21. Draw-by-draw completeness, pre-2024 availability, label continuity, and public-before-sales-cutoff timing remain `UNKNOWN` and are the purpose of the small acquisition task.

NEXT_TASK_TRACK:  
Track D — Orthogonal Physical Draw Metadata Acquisition

NEXT_TASK_ID:  
`B649_TRACK_D_BALL_SET_ASSIGNMENT_BOUNDED_ACQUISITION_R1`

REPO_MUTATION:  
NONE

DB_MUTATION:  
NONE

END
