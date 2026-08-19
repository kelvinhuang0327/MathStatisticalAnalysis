# INPUT_X_COVERAGE_VALIDATION_R1

TASK_ID: `INPUT_X_COVERAGE_VALIDATION_R1`
MODE: `READ_ONLY_COMPLETION_REVIEW` (as declared) → reclassified `PLANNING_ONLY` (bounded read-only research/data-profiling decision; no antecedent claimed-complete Worker output existed to adversarially review)
DATE: 2026-08-16
REPO_MUTATION: NONE — DB_MUTATION: NONE — INGESTION_CHANGE: NONE — COMMIT/PUSH/PR/MERGE: NONE

ALIAS_MAP (exact identifiers, kept here per the Packet's own reproducibility carve-out; chat/handoff uses aliases):
- **Dataset A** = B649 canonical draw history — internal lottery_type `BIG_LOTTO` (Taiwan Lotto 649 / 大樂透) in `lottolab.db`
- **Field X** = `drawNumberAppear` (official API field)
- **Provider P** = official Taiwan Lottery API, `api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result`, called in production by `src/lottolab/infrastructure/taiwan_lottery_draw_provider.py`

---

## Authority discovery

Located via the memory index (most recent Track-D successor-selection entry): `b649-track-d-post-eh01-eh10-eh02-successor-reselection-r1`, pointing to the off-repo artifact `/Users/kelvin/VibeCoding-WorkSpace/B649_TRACK_D_POST_EH01_EH10_EH02_SUCCESSOR_RESELECTION_R1.md`. This artifact was read in full (not inferred from chat/memory summary) and satisfies all three required criteria uniquely:

1. **Selected exactly one order-like provider field for bounded validation** — Section 1.3 / Section 3: Candidate D, `drawNumberAppear`.
2. **Routed the next action to a read-only Track-A coverage/semantic check** — `NEXT_TASK_TRACK: TRACK_A`, `NEXT_TASK_ID: B649_TRACK_A_DRAW_ORDER_POSITION_COVERAGE_VALIDATION_R1`.
3. **Identified a predefined fallback if this input is not ready** — `(Fallback if this stops: B649_TRACK_B_EH27_SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE_R1)`.

No other memory entry routes to TRACK_A with a named fallback; authority is unique. Checked for a superseding/orphan artifact (this program's own established failure mode — see memory `b649-track-d-post-eh01-eh10-eh02-successor-reselection-r1` Section 0) by scanning `.task-data/` mtimes and the `~/VibeCoding-WorkSpace` top level for anything newer matching `TRACK_A`/`DRAW_ORDER`/`INPUT_X`: none found. Authority is current and unambiguous.

The authority artifact itself leans heavily on a second, richer artifact it cites as "today's readiness-discovery report": `.task-data/B649_TRACK_B_NEW_INFORMATION_SOURCE_DATA_READINESS_DISCOVERY_R1/report.md` (+ `fixtures/*.json`, `source_readiness.csv`, `reproduce_analysis.py`). This task treats that report's claims as evidence to be independently re-verified against current live state, not assumed — see Phase 0 below.

---

## Phase 0 — current-state verification (fresh, this task, not inherited)

- Branch `main`, HEAD `e8de3bff6985a156f0902f8012713f5e8768709c`. Working tree dirty files match the session-start `git status` exactly (`tools/b649_operational_prediction_loop.py` modified; `.task-data/`, `docs/research/strategy-matrix-phase5-geometry-only-portfolio-application-r1-report.md`, `src/lottolab/research/cyclic_sidon_shift_p638_zone1.py`, `src/lottolab/research/low_overlap_portfolio_constructor.py` + test, all untracked) — none touched, none relevant to Field X.
- Cached local ref `origin/main` = `4a106bf...`, behind local HEAD. Not fetched (avoided an unnecessary network call for a read-only task); local `main` is treated as canonical per this project's established working pattern. Flagged, not treated as a blocker.
- **Provider path / current handling, reverified directly against the live file** (`src/lottolab/infrastructure/taiwan_lottery_draw_provider.py`, `_record()`, lines 159–186): reads only `mapping.get("drawNumberSize")`, validates length/type, and builds `main_numbers = tuple(sorted(numbers_int[:config.numbers_count]))`. Zero references to `drawNumberAppear` anywhere in the file. Confirms: Field X is fetched over the wire and silently discarded before storage, unchanged from the prior report's claim, reverified on current HEAD rather than assumed.
- **Schema, reverified directly**: `src/lottolab/infrastructure/persistence/draw_schema.py`, `CURRENT_SCHEMA_VERSION = 2`. `CREATE TABLE draws` columns: `id, lottery_type, draw_number, draw_date, main_numbers_json, special_numbers_json, normalized_record_hash, source_name, source_reference, ingestion_run_id, created_at, updated_at`. No order/positional/appearance column exists at schema version 2.
- **Live DB, queried read-only** (`~/Library/Application Support/LottoLab/lottolab.db`, file mtime 2026-08-14 15:33, i.e. unchanged since the prior report — no new draws ingested in the interim): `BIG_LOTTO` → 3,158 rows, `2007-01-02` to `2026-08-11`. Exact match to the prior report's cited canonical count; independently reconfirmed, not inherited.
- **Fixtures, read directly and independently re-derived by this task** (not just trusted from prose): `fixtures/lotto649_2007-01to03.json` (totalSize 26, 2 records), `fixtures/lotto649_2015-06.json` (totalSize 899, 2 records), `fixtures/lotto649_2026-08.json` (totalSize 2161, 3 records) — 7 records total. For every one of the 7, manually confirmed: `drawNumberAppear` is a genuine permutation of the same 6 main numbers as `drawNumberSize` (identical multiset, different order) with the special number in the same last slot in both fields. Example newly reproduced here: period `96000026` (2007-03-30): `drawNumberSize=[14,31,33,40,45,46,49]` vs `drawNumberAppear=[14,45,46,40,33,31,49]` — same 6-set `{14,31,33,40,45,46}`, special `49` last in both, order genuinely different. All 7/7 records pass this check with zero exceptions.
- `reproduce_analysis.py` inspected directly: it is a **pure offline analyzer** — re-derives claims from the saved fixtures/local DBs only; it contains no HTTP request-construction code. This means the exact query parameters that produced the three `totalSize` values (26 / 899 / 2161) are **not recoverable from this repository**; the original fetch was ad hoc and not preserved. This is a genuine, currently irresolvable-within-scope gap, not a gap this task chose to leave open.
- Grepped `docs/`, `src/`, `tools/` for any official field-dictionary text mentioning `drawNumberAppear`: **zero matches**. No official Provider P documentation of this field exists anywhere in this repository.

---

## 1. Semantic authority

Evidence priority applied: (1) official documentation — **absent**, confirmed by direct grep, not merely assumed; (2) official raw responses — **present and independently re-verified by this task** (see Phase 0); (3) current provider implementation — **present and independently re-verified** (field fetched, never parsed); (4) inference — used only where explicitly labeled below.

Field X is **confirmed** (structurally, from raw responses, not inference) to be:
- NOT the sorted/canonical representation (`drawNumberSize`) — a distinct, independently-varying field.
- A genuine permutation of the same 6 numbers, not a constant, not random noise unrelated to the draw, not degenerate — same multiset, different order, in all 7 sampled records across three 19-years-apart windows.
- Structurally consistent in one respect across all 7 samples: the special number always occupies the same (last) slot in both fields.

Field X is **not confirmed** (no official documentation located, not FAQ-text-confirmed) to specifically mean:
- Physical ball-drop order (the most natural reading of the field name), as opposed to an on-screen reveal/display convention or another API-internal encoding.

`[Inferred, explicitly labeled]`: the field name and the structural evidence (genuine reordering + stable special-slot placement) are circumstantially consistent with some form of announcement/reveal order. This is short of "verified physical draw order" and must not be reported as more than that.

```
SEMANTIC_STATUS: PARTIALLY_CONFIRMED
```
Confirmed: genuine non-sorted order/permutation information, distinct from the stored sorted set (evidence tier 2+3). Not confirmed: which specific real-world event this order corresponds to (no tier-1 evidence found).

---

## 2. Historical coverage

Two distinct denominators, kept separate (the same discipline the `totalSize` anomaly demands — collapsing two different counts into one number is exactly the failure mode already seen in this field):

| Metric | LOCAL (Dataset A as ingested) | SOURCE (Provider P, spot-checked) |
|---|---|---|
| Earliest populated record for Field X | N/A — never ingested | `96000026` / 2007-03-30 (2007-01to03 fixture); Field X also verified present at the adjacent record `96000025` / 2007-03-27 |
| Latest populated record for Field X | N/A — never ingested | `115000079` / 2026-08-14 (2026-08 fixture) |
| Populated count | **0** / 3,158 canonical rows (0%) | 7 / 7 sampled source records (100% of the *sample*, but the sample is sparse) |
| Missing/null count | 3,158 / 3,158 (100%) | 0 / 7 sampled |
| Malformed count | N/A (no slot exists) | 0 / 7 sampled |
| Duplicate/inconsistent count | N/A | 0 duplicate periods; **1 unresolved inconsistency** — the API's own `totalSize` metadata field returned 26 / 899 / 2,161 across the three queries, internally inconsistent with each other and not explained by anything recoverable in-repo (see Phase 0) |
| Coverage rate | 0% (ingestion) | **PARTIAL** — 7 records verified against Dataset A's 3,158 canonical / 2,138 clean-history draws (2007-03-09 to 2026-07-31, the program's independently-reconfirmed-four-times research subset) ≈ 0.2–0.3% direct sampling density, spread across 3 non-adjacent windows (2007, 2015, 2026) rather than a systematic pull |
| Format changes across eras | None observed in the 7 samples checked (identical JSON shape/field set in the 2007 and 2026 fixtures) — but this is not a claim of no format drift in between; only 3 points were ever checked, and the prerequisite for a real answer (one query per calendar year, or denser) has not been executed, in or out of this task | |
| Expected element-count/value invariants | Held in all 7/7 samples: exactly 7 values (6 main + 1 special), same multiset as `drawNumberSize`, special number in the same slot position in both fields | |

```
HISTORY_IDENTITY_STATUS: PARTIAL — NOT EXHAUSTIVELY CONFIRMED
EARLIEST_POPULATED (source, spot-check): 2007-03-30 (period 96000026)
LATEST_POPULATED (source, spot-check): 2026-08-14 (period 115000079)
POPULATED_COUNT: 0/3,158 local; 7/7 sampled at source
MISSING_COUNT: 3,158/3,158 local (100%); source-side missingness beyond the 7 sampled points is UNKNOWN, not zero and not nonzero — genuinely unmeasured
MALFORMED_COUNT: 0/7 sampled
COVERAGE_RATE: 0% local; source coverage PARTIAL, ~0.2-0.3% direct-sample density against Dataset A's full history
ERA_STABILITY: no drift observed in the 3 checked eras (2007/2015/2026), but this is 3 points, not a stratified series — not a stability claim the program's own stated bar ("all 4 ERA blocks", per the authority artifact's REQUIRED_PREREQUISITE) would accept as met
```

This task did **not** perform new Provider P queries to close this gap — Phase 0 of this Packet scopes verification to "available raw/provider fixtures or archived responses," not new acquisition, and the FORBIDDEN section prohibits any ingestion step. The systematic stratified pull the authority artifact itself specifies as the prerequisite (`REQUIRED_PREREQUISITE`, one query per calendar year 2007–2026 or denser) remains **not executed**.

---

## 3. Information novelty

- **Identical to the existing canonical representation?** No. Independently confirmed in all 7 samples: different element order from `drawNumberSize`, same multiset.
- **Deterministic transformation of what's stored?** No plausible one exists locally — the canonical store keeps only the sorted form; the unsorted form cannot be reconstructed from a sorted list (order information is destroyed by sorting, not recoverable).
- **Genuinely additional ordering/state information?** Yes. This is corroborated by an independent, earlier finding in this same research program (`b649-rank-authority-absent-combination-semantics`): the sealed foundation dataset is 100% ascending-sorted by construction, and every draw-content analysis this program has ever run (marginal/pairwise/triple/quadruple co-occurrence, motif/discord, permutation entropy, static-consensus alignment, etc.) operates on that sorted form. Field X is the only data channel in this program's history that was never looked at by any of those.
- **Semantics stable over time?** Circumstantially yes for the one structural invariant checked (special-number slot placement, stable in 7/7 samples across 19 years) — but see the coverage caveat above; 7 points cannot fully bound a stability claim.

```
INFORMATION_NOVELTY_STATUS: CONFIRMED_ADDITIONAL — genuinely new ordering information, not a re-derivation of anything in the current canonical schema
```

---

## 4. Current pipeline gap

Provider P → parser → persistence flow, read end to end (`taiwan_lottery_draw_provider.py`):

- **Arrives upstream**: Yes — present in every one of the 7 sampled raw payloads, at zero missingness in-sample.
- **Is parsed**: No — `_record()` never references `drawNumberAppear`.
- **Is discarded**: Yes — implicitly, by never being read out of the response mapping.
- **Can theoretically be preserved without changing existing canonical semantics**: Yes — this would be a purely additive change (a new nullable field), not a modification of the existing `main_numbers`/`special_numbers` sort-based semantics that the entire current strategy catalog depends on.

```
PROVIDER_PATH_STATUS: FIELD PRESENT AT SOURCE, NOT REFERENCED BY PARSER
CURRENT_HANDLING: FETCHED_THEN_DISCARDED (silent — no error, no log, no schema slot)
MINIMAL_FUTURE_IMPLEMENTATION_SURFACE (not implemented, description only, per FORBIDDEN):
  1. Extend the transport dataclass in taiwan_lottery_draw_provider.py to also capture drawNumberAppear from the existing mapping (no change to main_numbers/special_numbers derivation).
  2. A schema v3 migration (draw_schema.py's migration path is exact-match/strict, so this is a deliberate versioned migration, not an ad hoc ALTER TABLE) adding one new nullable column to draws.
  3. A one-time backfill re-fetch against Provider P for existing periods to populate the new column historically.
  None of this is implemented or started by this task.
```

---

## 5. Causal boundary

For the draw a given Field X value describes: it is generated **at** that draw, the same causal moment as the winning-number outcome itself. It cannot be known before that draw's own betting cutoff — same causal status as the outcome.

```
PRE_OR_POST_EVENT_STATUS: POST_EVENT (for the draw it describes)
→ OUTCOME_METADATA
FUTURE_CAUSAL_BOUNDARY: Same-event predictive use is PROHIBITED — Field X for draw N is exactly as unavailable before draw N as draw N's own outcome. Future research may use Field X only as a LAGGED historical feature (values from draws strictly prior to a target draw), never as a same-draw predictor for the draw it was generated at. No separate causal authority in this program currently establishes otherwise.
```

This mirrors the authority artifact's own `causal_alignment_summary.csv` row for `draw_order_position` (`LAG_ONLY (feature of prior draws)`), reproduced here as a fresh conclusion from first principles rather than copied uncritically.

---

## Readiness decision

Per-dimension summary:

| Dimension | Status |
|---|---|
| Semantically authoritative | PARTIALLY — structure confirmed, specific real-world referent not confirmed |
| Historically populated | **NOT ADEQUATE** — 7 spot-check records against ~3,158 draws, 3 non-adjacent windows, not a stratified series |
| Structurally stable | LIMITED evidence — no drift in 3 checked points, but 3 points cannot support a program-standard stability claim |
| Information-novel | CONFIRMED |
| Causally classifiable | CONFIRMED — explicit, unambiguous boundary |

Two of five criteria are cleanly met. The historical-population and structural-stability gaps are the same root cause (sampling density), and that root cause was explicitly named by the authority artifact itself as the prerequisite before any next design — it has not been closed since, and this task's own bounded scope does not permit closing it (no new Provider P acquisition authorized here).

```
NEXT_DESIGN_READINESS: INPUT_X_NOT_READY
```

Criteria were not weakened to force a READY verdict — see explicit gap table above.

```
BLOCKERS:
1. Historical coverage is PARTIAL, not CONFIRMED: only 7 source-side records verified (3 non-adjacent windows: 2007, 2015, 2026) against Dataset A's 3,158-row canonical / 2,138-row clean-history span. The systematic stratified pull (one query per calendar year or denser, per the authority artifact's own REQUIRED_PREREQUISITE) has not been executed, and this task's scope does not authorize performing it now.
2. Provider P's totalSize pagination field is internally inconsistent (26 / 899 / 2,161 across the three historical queries) for reasons not recoverable from this repository (the original fetch parameters were not preserved) — this must be resolved or explicitly bounded before any future "gap" in Field X can be trusted as a true missing-data gap rather than a query/pagination artifact.
3. Semantic meaning of Field X (physical draw order vs. presentation/reveal order vs. another encoding) has no tier-1 (official documentation) evidence anywhere in or out of this repo that this task could locate; only tier-2/3 structural evidence exists.

REMAINING_RISK:
Even conditional on the coverage gap closing cleanly, the semantic-referent ambiguity may not be fully resolvable without a direct Provider P statement, which would cap (not block, but cap) confidence in any causal story built on this field going forward. Separately — carried forward from the authority artifact, not re-litigated here — this program has closed approximately nine prior "detect a regime, gate a decision"-shaped mechanisms against this same population (most recently pre-draw jackpot/rollover, sealed WEAK_SIGNAL the same day as the authority artifact); Field X's own downstream predictive path was already characterized by the authority artifact as "genuinely uncertain," and any future Track B design on this field would need the program's now-standard placebo battery (shuffled-order placebo, stale/misaligned-order placebo, era-stratified control) from the start.
```

---

## What this task deliberately did not do

- Did not query Provider P live (no new network acquisition; used only existing fixtures/archived responses per Phase 0 scope).
- Did not implement any parser/schema/ingestion change.
- Did not perform or design a predictive/backtest experiment.
- Did not execute the pre-registered fallback (EH27) — that fallback trigger belongs to a future task, not this validation gate.
- Did not inspect or comment on unrelated concurrent working-tree changes (`tools/b649_operational_prediction_loop.py`, the Strategy-Matrix/Sidon research files) beyond confirming their existence/irrelevance in Phase 0.
- Did not commit, push, open a PR, or merge anything.

## Reproduction

All claims above are reproducible read-only from: `taiwan_lottery_draw_provider.py:159-186`, `draw_schema.py` (`CURRENT_SCHEMA_VERSION`, `CREATE TABLE draws`), `~/Library/Application Support/LottoLab/lottolab.db` (read-only SQLite query), and the three fixture files under `.task-data/B649_TRACK_B_NEW_INFORMATION_SOURCE_DATA_READINESS_DISCOVERY_R1/fixtures/`. No step requires network access.

---

## FINAL

```
TASK_ID: INPUT_X_COVERAGE_VALIDATION_R1
STATUS: COMPLETE — READINESS ASSESSED, NOT ADVANCED
SEMANTIC_STATUS: PARTIALLY_CONFIRMED
SEMANTIC_EVIDENCE_GRADE: TIER_2_3_ONLY (raw responses + current implementation; no tier-1 official documentation found)
PROVIDER_PATH_STATUS: FIELD PRESENT AT SOURCE, NOT REFERENCED BY PARSER
CURRENT_HANDLING: FETCHED_THEN_DISCARDED
HISTORY_IDENTITY_STATUS: PARTIAL
EARLIEST_POPULATED: 2007-03-30 (source spot-check)
LATEST_POPULATED: 2026-08-14 (source spot-check)
POPULATED_COUNT: 0/3,158 local; 7/7 sampled at source
MISSING_COUNT: 3,158/3,158 local; source-side beyond sample UNKNOWN
MALFORMED_COUNT: 0/7 sampled
COVERAGE_RATE: 0% local; PARTIAL (~0.2-0.3% direct-sample density) at source
ERA_STABILITY: no drift in 3 checked points; not a stratified series, does not meet program's stated 4-ERA-block bar
INFORMATION_NOVELTY_STATUS: CONFIRMED_ADDITIONAL
PRE_OR_POST_EVENT_STATUS: POST_EVENT / OUTCOME_METADATA
FUTURE_CAUSAL_BOUNDARY: LAGGED HISTORICAL USE ONLY, SAME-EVENT USE PROHIBITED
MINIMAL_FUTURE_IMPLEMENTATION_SURFACE: additive transport field + schema v3 migration + one-time backfill (NOT IMPLEMENTED)
NEXT_DESIGN_READINESS: INPUT_X_NOT_READY
BLOCKERS: coverage-sampling density (7 records only); unresolved totalSize/pagination inconsistency; no tier-1 semantic confirmation
REMAINING_RISK: semantic-referent ambiguity may persist even after coverage closes; population has ~9 prior null "regime-gate" mechanisms; downstream path already characterized as uncertain
REPO_MUTATION: NONE
DB_MUTATION: NONE
INGESTION_CHANGE: NONE
COMMIT: NO
PUSH_PR_MERGE: NO
```
