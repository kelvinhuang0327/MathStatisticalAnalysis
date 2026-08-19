# B649 Track B — new information source data readiness discovery

GOAL_ID: `B649_TRACK_B_NEW_INFORMATION_SOURCE_DATA_READINESS_DISCOVERY_R1`

STATUS: COMPLETE (data-readiness discovery only — no predictor selected, no DB/strategy-matrix mutation)

## Scope

This task is supporting discovery for Track D, not a Track D hypothesis selection. It asks one question per candidate source: **does usable pre-target historical data actually exist, and can it be causally and record-level aligned to a B649 target draw?** It does not build, test, or recommend a predictor.

Five sources in scope, per the packet:

- **A.** calendar / schedule context
- **B.** verified physical draw order / draw position
- **C.** realized crowd popularity
- **D.** jackpot / sales state
- **E.** equipment / ball-set / machine regime metadata

Cross-lottery lagged context is explicitly out of scope for re-assessment — it was already fully executed and closed (`b649-track-b-cross-lottery-lagged-context-native-prediction-level1-r1`: real lag +0.047 M2+, but beaten by a 28-day-stale placebo → `WEAK_SIGNAL/DO_NOT_ADVANCE`). It is referenced below only where its failure mode is a relevant risk analogue for sources C/D.

## Prior work reused, not redone

1. **`.task-data/B649_TRACK_B_STRATEGY_INFORMATION_SOURCE_PROVENANCE_DISCOVERY_R1/`** — an existing, un-memory-indexed predecessor task in this same repo. It already inventoried all 69 production B649 strategies and confirmed all five of this task's sources are at **0/69 (`ABSENT`)** strategy-level usage, and produced a first-pass qualitative ranking (`missing_information_candidates.csv`) with the same five source names used here. This task goes one level deeper: **actual historical-data existence, date range, granularity, and causal timestamp**, not strategy-usage counts.
2. **Track D's equipment/ball-set research chain** (`b649-track-d-orthogonal-draw-metadata-feasibility-recon` → `b649-track-d-ball-set-assignment-bounded-acquisition-r1` → `b649-track-d-pre-cutoff-orthogonal-information-reselection-r1` → `b649-track-d-concession-protocol-era-mechanism-feasibility-r1`) — four already-completed, evidence-backed tasks covering source E. Reused verbatim below; not re-derived, not re-litigated.
3. The cross-lottery-lag result above, as a risk analogue only.

## Method

- Read both DB schemas that exist in/near this repo: the canonical production schema (`src/lottolab/infrastructure/persistence/draw_schema.py`, resolving to `lottolab.db` under `$LOTTOLAB_DATA_DIR`, default `~/Library/Application Support/LottoLab/`) and the sealed legacy snapshot (`.local/snapshots/p600ab-r1-20260715T122730+0800/lottery_v2.db`, per `[[legacy-reference-corpus-location]]`).
- Queried both live, read-only, for BIG_LOTTO row counts, date ranges, and the fill rate of every column that could plausibly carry order/jackpot information.
- Read `src/lottolab/infrastructure/taiwan_lottery_draw_provider.py` (the project's own production ingestion adapter) end to end to see exactly which upstream API fields are parsed today.
- Made **three bounded, read-only GET requests** to the exact same public official endpoint (`api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result`) this adapter already calls in production, using the same headers, at three widely separated dates (2007-01/03, 2015-06, 2026-08) to inspect the *raw* payload the project's own code discards fields from. Saved as offline fixtures (`fixtures/*.json`) so `reproduce_analysis.py` needs no network access to re-verify the claims below. This is diligence on field semantics, not a scraping project — three small requests, not a historical backfill.
- Grep-searched `src/`, `docs/`, `tools/`, `frontend/`, `contracts/` for existing jackpot/popularity/equipment/ball-set/draw-position handling. Found none beyond the unrelated strategy name string `biglotto_social_wisdom_anti_popularity` (a static assumed prior, not observed popularity data).

## Critical interpretation rule: `drawNumberSize` ≠ physical draw order

The packet is explicit that sorted winning numbers must not be assumed to equal physical draw order. Verified directly from the raw upstream payload — example, period 115000078 (2026-08-11):

```
drawNumberSize:   [8, 12, 16, 24, 29, 46, 10]   <- sorted ascending, special last
drawNumberAppear: [8, 46, 24, 29, 12, 16, 10]   <- NOT sorted; same 6 numbers, different order
```

`reproduce_analysis.py` confirms across all 7 sampled records (three eras: 2007, 2015, 2026) that `drawNumberAppear` is always a **permutation** of `drawNumberSize` (same multiset, different order) and that the special number sits in the same last slot in both fields every time. This is exactly the kind of order-preserving field the packet asks to distinguish from the sorted one — and the project's own `_record()` function in `taiwan_lottery_draw_provider.py` reads **only** `drawNumberSize`, then re-sorts it again (`main_numbers = tuple(sorted(numbers_int[:config.numbers_count]))`), and never looks at `drawNumberAppear` at all. This field is fetched over the wire on every existing sync and silently dropped before storage.

What this does **not** establish: an official field dictionary or FAQ confirming `drawNumberAppear` literally means ball-drop order (as opposed to, say, on-screen reveal order or some other display convention). The evidence is strong circumstantial (a genuine reordering of the same numbers, consistent special-number placement across every sample) but not a confirmed field definition the way source E's cutoff timing was confirmed directly from the official FAQ text. Flagged as the one open provenance question before this source is used for anything beyond exploratory analysis.

## Source-by-source findings

### A. Calendar / schedule context — `READY_NOW`

| Field | Value |
|---|---|
| HISTORICAL_DATA_EXISTS | YES |
| SOURCE | `draws.draw_date` in the canonical `lottolab.db`; corroborated by `draws.date` in the legacy snapshot |
| DATE_RANGE | 2007-01-02 to 2026-08-11 (canonical, n=3,158); 2007/01/02 to 2026/07/10 (legacy, n=3,149) |
| GRANULARITY | per-draw, daily resolution |
| CAUSAL_TIMESTAMP_AVAILABLE | YES — draw dates, and even the *next* scheduled draw date, are known well ahead of each draw. Confirmed operationally: `~/Library/Application Support/LottoLab/pre-outcome-target-announcements-v1.json` already records a forward-looking `NextDrawDate` fetch from the official schedule endpoint. |
| B649_TARGET_ALIGNMENT_POSSIBLE | YES — same table/key as the draw being predicted |
| MISSINGNESS | 0% (`NOT NULL` by schema; verified populated for all rows) |
| TRUST_LEVEL | HIGH |
| ACQUISITION_COST | NONE — already stored; weekday/month/holiday-proximity/spacing/irregularity are pure local computation |

**Calendar context vs. era proxy (the packet's explicit distinction), with real numbers:**

`reproduce_analysis.py` recomputes the live weekday histogram: Tuesday+Friday = 2,405/3,158 draws (76.2%) — the dominant, stable schedule across the full history. The remaining 753 non-Tue/Fri draws split sharply by era: **643 fall in 2007–2013**, only **110 in 2014–present** (12 years). The pre-2014 block is not scattered holiday noise — e.g. 2010 alone has 52 Monday + 52 Wednesday + 52 Thursday draws (every week that year). That is a structural, multi-year different-schedule block, not an exception. From 2014 on, non-Tue/Fri draws drop to 1–3/year — consistent with ordinary single-day holiday reschedules.

**Implication:** a naive `weekday` feature is safe from 2014 onward but **would silently encode era** for any pre-2014 row, exactly the calendar-vs-era-proxy trap the packet warns about. Any future calendar-context feature must either scope to the post-2014 regime or explicitly model the pre-2014 block as its own regime, not fold it into a generic weekday encoding. No predictor is built here per the packet's instruction — this is reported as a design constraint for whoever does build one.

### B. Verified physical draw order / draw position — `READY_WITH_SMALL_INGEST`

| Field | Value |
|---|---|
| HISTORICAL_DATA_EXISTS | NOT INGESTED LOCALLY (0/3,158 canonical rows have any slot for it; 0/3,149 legacy rows populated) but VERIFIED AT SOURCE |
| SOURCE | `api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result`, field `drawNumberAppear` — the exact endpoint `taiwan_lottery_draw_provider.py` already calls in production |
| DATE_RANGE | verified present 2007-03-27 through 2026-08-14 (3 spot-checked windows); **not exhaustively confirmed for every draw in between** — see Historical Coverage below |
| GRANULARITY | per-draw, all 7 slots (6 main + 1 special) |
| CAUSAL_TIMESTAMP_AVAILABLE | YES for training rows — public immediately after each past draw, well before any future draw's cutoff. NO for the target draw itself: its own draw order is generated at that draw, same causal status as its outcome. |
| B649_TARGET_ALIGNMENT_POSSIBLE | YES — the API's `period` field is the same identifier format as `draws.draw_number` (canonical) / `draws.draw` (legacy), e.g. `115000078` |
| MISSINGNESS | 100% in every current project-local store; 0/7 sampled source-API records missing the field |
| TRUST_LEVEL | MEDIUM-HIGH — official regulator API, same trust tier the project already keys its entire prediction pipeline on for `main_numbers`; semantic equivalence to physical ball order is inferred (see interpretation-rule section above), not FAQ-confirmed |
| ACQUISITION_COST | LOW-MEDIUM — `ProviderDrawRecord` (in `application/draw_automation.py`) and the canonical `draws` schema (`draw_schema.py`, currently version 2) have **no slot for this at all** today. Needs: a new dataclass field, a version-3 schema migration (this codebase's schema verification is exact-match/strict, so this is a deliberate migration, not a casual `ALTER TABLE`), and a one-time backfill re-fetch of existing periods. |

A separate, negative but important data point: the legacy schema's own `numbers_positional` column exists and is **0% filled for BIG_LOTTO** (0/3,149) — but it is **100% filled** for the structurally different `3_STAR`/`4_STAR` digit-position games (5,850/5,850 each, verified by `reproduce_analysis.py`). This proves the schema slot is populated whenever the upstream source actually provides positional semantics natively for a game — the emptiness for BIG_LOTTO is specifically an ingestion gap for this game, not a systemic legacy-schema limitation.

### C. Realized crowd popularity — `UNAVAILABLE` (genuine signal); lagged proxy only

| Field | Value |
|---|---|
| HISTORICAL_DATA_EXISTS | NO genuine pre-draw popularity source found, anywhere. A weak POST-draw proxy exists: per-prize-tier `winnerCount`/`perPrize` in the same API payload as source D. |
| SOURCE | None for genuine popularity. `api.taiwanlottery.com` `winnerCount`/`perPrize` fields for the weak proxy only. |
| DATE_RANGE | N/A for genuine source; proxy verified present in the same 3 spot-checked windows as source D |
| GRANULARITY | N/A; proxy is per-draw, per-prize-tier |
| CAUSAL_TIMESTAMP_AVAILABLE | NO for genuine popularity — the source does not exist. The proxy is strictly settled **after** that same draw's own cutoff (you cannot know how many people matched a tier until the draw determines who matched), so it is usable only lagged into the *next* draw, never same-draw. |
| B649_TARGET_ALIGNMENT_POSSIBLE | N/A for genuine source; lag-only for the proxy |
| MISSINGNESS | 100% (the source itself does not exist) |
| TRUST_LEVEL | N/A |
| ACQUISITION_COST | Likely HIGH-TO-INFEASIBLE for genuine pre-draw popularity — the official operator does not publish per-number pick/quick-pick-ratio data, and no third-party channel was identified in this session. LOW for the lagged `winnerCount` proxy (same ingest path as B/D). |

Per the packet's explicit instruction not to invent popularity data: no popularity source is named here beyond what was actually found. The current production strategy that uses the word "popularity" (`biglotto_social_wisdom_anti_popularity`) consumes a **static assumed prior** (numbers 1–31 penalized as likely birthdays), not any observed player-choice data — this was already established by the predecessor provenance task and reconfirmed here. If a genuine popularity source is ever proposed, it should come with its own independently verified provenance; third-party "hot number" sites frequently just relabel historical frequency and should not be trusted at face value.

### D. Jackpot / sales state — `READY_WITH_SMALL_INGEST`

| Field | Value |
|---|---|
| HISTORICAL_DATA_EXISTS | NOT INGESTED LOCALLY (canonical schema has no slot at all; legacy `jackpot_amount` is 0/3,149 populated) but VERIFIED AT SOURCE, same endpoint as B |
| SOURCE | same API response as B: `totalAmount`, `sellAmount`, `jackpotAssign.{prize,lastPrize,winnerCount,perPrize}` plus 7 more named prize tiers |
| DATE_RANGE | verified present 2007-03-27 through 2026-08-14 (3 spot-checked windows) |
| GRANULARITY | per-draw; 8 prize tiers per draw |
| CAUSAL_TIMESTAMP_AVAILABLE | **Split — this is the important nuance.** The advertised pre-draw jackpot/rollover *is* legitimately known before the target draw: it is reconstructable as the prior draw's `lastPrize + prize` whenever that prior draw had zero jackpot winners. `reproduce_analysis.py` verifies this arithmetic **exactly, to the dollar**, across two consecutive real draws: `115000077 → 078`: 42,496,650 + 19,189,810 = 61,686,460 (078's `lastPrize`, exact match); `078 → 079`: 61,686,460 + 16,397,730 = 78,084,190 (079's `lastPrize`, exact match). By contrast, `sellAmount`, `winnerCount`, and per-tier `perPrize` for a given draw are only settled after that same draw's own cutoff — usable only lagged into the next draw, not as same-draw predictors. |
| B649_TARGET_ALIGNMENT_POSSIBLE | YES, same draw-key join as B |
| MISSINGNESS | 100% missing in every current project-local store; 0/7 sampled source-API records missing |
| TRUST_LEVEL | HIGH — official source, and internally self-consistent (the rollover-chain arithmetic above is exact, not just plausible-looking) |
| ACQUISITION_COST | LOW-MEDIUM, same shape as B — likely shareable in one migration/backfill pass since both live in the same response |

**Risk flag, explicitly carried over from the cross-lottery-lag result:** the lag-only sub-fields here (`sellAmount`, `winnerCount`, per-tier `perPrize`) have the exact same causal shape as the cross-lottery-context features that already produced `WEAK_SIGNAL/DO_NOT_ADVANCE` — a real-looking lag effect beaten by a deliberately stale placebo. Do not assume this source is exempt from that failure mode merely because the fields are new; the same placebo-controlled design used for cross-lottery lag should gate any future experiment on the lagged pieces of this source. The pre-draw advertised-jackpot sub-feature is the cleaner, genuinely same-draw-causal piece and does not inherit this specific risk.

### E. Equipment / ball-set / machine regime metadata — `UNAVAILABLE` (net verdict)

Reused entirely from the already-completed Track D chain; not re-derived.

| Field | Value |
|---|---|
| HISTORICAL_DATA_EXISTS | YES, but retrospective-only and partial |
| SOURCE | official YouTube livestream archive (channel `@48ilottery48`, linked from `taiwanlottery.com`), read manually per broadcast |
| DATE_RANGE | **2024-01-01 onward ONLY** — the archive's own oldest video, confirmed by complete channel enumeration, not sampling. Nothing earlier exists on this channel. |
| GRANULARITY | per-broadcast, when successfully localized and read |
| CAUSAL_TIMESTAMP_AVAILABLE | Before the physical draw, but **after** that draw's own 20:00 betting cutoff. The official FAQ (Q6, `taiwanlottery.com/customer_service/faq`) states the 20:00–20:30 window is reserved for sales-statistics computation *before* the machine/ball-set/loading-order selection ceremony can even start. This information can never inform a bet placed for the draw it describes. |
| B649_TARGET_ALIGNMENT_POSSIBLE | Partial — only draws from 2024-01-01 forward (roughly the most recent 11% of the full 2007–2026 history), and only probabilistically |
| MISSINGNESS | ~89% of the full draw history is categorically unreachable (pre-2024). Within the reachable window, Track D's own 3-sample test found roughly **1/3 clean-read rate** — the bottleneck is locating a few-second ball-set window inside 30–70 minute VODs with no chapter markers and interleaved unrelated content, not label legibility. |
| TRUST_LEVEL | Source itself HIGH (official, notary-witnessed, per Track D's direct FAQ read); realized read quality MEDIUM given the manual, low-yield extraction process |
| ACQUISITION_COST | MEDIUM-HIGH — manual video segment localization, no automation exists |

**Net classification:** `UNAVAILABLE` for this packet's purpose — driven by two independent, already-proven reasons: `NOT_CAUSALLY_USABLE` for live prediction (post-cutoff timing makes it structurally unable to inform a bet for the draw it describes) **and** `INSUFFICIENT_HISTORY` (83%+ of the draw history is structurally unreachable regardless of the causality problem). This is a closed Track D research line (`BALL_SET_DATA_USABLE_FOR_RETROSPECTIVE_DISCOVERY_ONLY`, predictive live usability explicitly `NO`). Track D's own named next step — a segment-localization feasibility check before any larger acquisition — remains Owner-pending and is not started here; this task does not re-open or re-litigate that decision.

## Official API field confirmation and historical coverage

Fields directly confirmed present, with real values, in the raw upstream payload (not inferred from documentation): `period`, `lotteryDate`, `drawNumberSize`, `drawNumberAppear`, `totalAmount`, `sellAmount`, `jackpotAssign` (and 7 sibling prize-tier objects each with `prize`/`lastPrize`/`winnerCount`/`perPrize`). Saved verbatim in `fixtures/*.json`.

**HISTORICAL_COVERAGE: PARTIAL.** Three narrow windows were checked (2007-01→03: 2 records; 2015-06: 2 records; 2026-08: 3 records = 7 records total), spanning close to the full nominal 2007–2026 range and all returning clean, populated `drawNumberAppear`/prize-tier data — including the earliest window, which was the main open question (by analogy with source E's 2024-only video-archive cutoff, there was a real risk this API might also have a shallow historical floor; it does not appear to). But 7 records is a sparse sample against ~2,900+ actual BIG_LOTTO draws in that span, and the API's own `totalSize` field returned inconsistent values across the three queries (26, 899, 2,161) that do not resolve cleanly to either a per-query-window count or a stable grand total — this field is not understood and is not relied on for any claim here. **Do not report full 2007–2026 coverage as confirmed.** A systematic backfill-validation pass (fetching every month and checking for gaps) would be needed to upgrade this from PARTIAL to CONFIRMED, and that is explicitly out of scope for this task ("do not launch a large scraping project").

T539 and P638 were not live-verified in this task (out of scope — the packet's primary goal is B649-specific). `taiwan_lottery_draw_provider.py`'s `SOURCE_CONFIG` table shows the same adapter pattern serves `daily539Res`/`superLotto638Res` from sibling endpoints on the same host; structurally likely to carry the same field family, but this is `[Inferred]`, not verified live.

## Causal alignment summary (see `causal_alignment_summary.csv` for the full table)

| Source | Prior to betting cutoff | Prior to draw outcome | Same-draw or lag-only |
|---|---|---|---|
| calendar_schedule_context | YES | YES | SAME_DRAW |
| draw_order_position | NO (that draw's own order doesn't exist yet) | NO | LAG_ONLY (feature of prior draws) |
| realized_player_popularity | N/A (no source) | N/A | N/A / proxy is LAG_ONLY |
| jackpot_sales_market_state | SPLIT (rollover: YES; sales/winners: NO) | SPLIT | rollover: SAME_DRAW; sales/winners: LAG_ONLY |
| equipment_ballset_regime | NO | YES | NOT USABLE for the draw it describes |

The alignment key across every source is the draw identifier (`draws.draw_number` / `draws.draw` / API `period`, all the same format, e.g. `115000078`). `src/lottolab/domain/draws.py` carries its own load-bearing warning worth repeating here: `draw_id` is `TEXT` and must always be ordered through `sort_key` (`int(draw_id)`), never lexicographically — any new join code for these sources must respect that.

## Classification summary

```
CLASSIFICATION_SUMMARY
calendar_schedule_context: READY_NOW
draw_order_position: READY_WITH_SMALL_INGEST
realized_player_popularity: UNAVAILABLE
jackpot_sales_market_state: READY_WITH_SMALL_INGEST
equipment_ballset_regime: UNAVAILABLE
END_CLASSIFICATION_SUMMARY
```

This block is machine-checked against `source_readiness.csv` by `reproduce_analysis.py` (`check_report_csv_reconciliation`).

## What this task deliberately did not do

- Did not build, tune, or evaluate any predictor or feature on any of these sources.
- Did not select Track D's next hypothesis.
- Did not mutate any DB, the strategy matrix, or any production file.
- Did not perform a historical backfill or bulk scrape of the official API (3 bounded spot-check requests only).
- Did not verify T539/P638 live (out of scope; noted as inferred-only above).
- Did not re-run or second-guess Track D's already-closed equipment/ball-set conclusion.

## Reproduction

```bash
python3 .task-data/B649_TRACK_B_NEW_INFORMATION_SOURCE_DATA_READINESS_DISCOVERY_R1/reproduce_analysis.py
```

Runs fully offline against `fixtures/*.json` for the API-field claims (permutation property, special-slot consistency, jackpot rollover-chain arithmetic), against the canonical schema/live DB for the calendar statistics and the schema-lacks-rich-fields check (SKIPPED gracefully if not present on the running machine), against the sealed legacy snapshot for the positional/jackpot 0%-fill claim (SKIPPED gracefully if not present), and cross-checks this report's classification block against `source_readiness.csv`. All checks PASS on this machine as of this task's execution.
