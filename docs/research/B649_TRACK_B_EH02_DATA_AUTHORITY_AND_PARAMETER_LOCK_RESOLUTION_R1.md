# B649 Track B EH02 Data-Authority and Parameter-Lock Resolution R1

```text
TASK_ID: B649_TRACK_B_EH02_DATA_AUTHORITY_AND_PARAMETER_LOCK_RESOLUTION_R1
TASK_CLASS: PLANNING_ONLY
WORKER_ROUTE: STANDARD
CONTINUES: B649_TRACK_B_EH02_PARAMETER_LOCK_PROPOSAL_R1 (resolves proposal
  §14 prelock issues 2 and 3 only; issues 1, 4, 5, 6, 7 remain open — see §7)
STATUS: DATA_AUTHORITY_AND_PARAMETER_LOCK_RESOLVED_FOR_OWNER_REVIEW
EH02_EXECUTION: NOT_RUN
SCIENTIFIC_DATA_ANALYSIS: NOT_RUN
PREREGISTRATION_SHA256: NOT_CREATED (explicitly deferred by this task's own
  instruction)
REPO_MUTATION: NONE
DB_MUTATION: NONE (every connection opened `mode=ro`; only `SELECT`
  statements were issued against every SQLite file touched)
```

## 0. Scope and method note

This task resolves exactly two of the seven prelock issues the proposal
(`B649_TRACK_B_EH02_PARAMETER_LOCK_PROPOSAL_R1.md`, §14) left open: the B649
`2,138 vs 2,145` dataset conflict (issue 2), and independent verification of
the T539 / P638 Zone-1 counts the proposal had only carried forward from a
predecessor study without re-checking (issue 3). No transfer-entropy,
mutual-information, p-value, or any other EH02 statistic was computed at any
point. All work below reads only `draw_id` / `draw_date` / `main_numbers`
(and, for provenance tracing, file/table metadata) — never interprets a
result, ranks a hypothesis, or forms a conclusion about EH02 itself.

Every dataset claim below was independently reproduced by direct read-only
SQL/file inspection in this task, not copied from any memory, report, or the
proposal document. Full working scripts and console output are preserved in
this session; the exact reproduction commands are given inline so the Owner
or a future task can re-run them verbatim.

**Canonical-repo instruction, checked explicitly:** local `main` (commit
`e273eb44763e293312153bc82176351af55f016c`) and `origin/main` (commit
`52b8353c932589c3f3ea8ff61fe7982c667cbbb0`) are diverged (5 local-only vs 7
origin-only commits, common ancestor `1aee7538f77076054c8a197d412f63514ee9be24`).
Diffed both refs directly: `src/lottolab/infrastructure/persistence/research_schema.py`,
`research_repository.py`, and `src/lottolab/domain/lottery_rules.py` — the
files that define the `research_draw_bindings` table and the three lottery
rule contracts — are **byte-identical** on both refs (empty `git diff
origin/main..HEAD -- <those files>`). The only B649-relevant local-only
addition is a convenience loader module,
`src/lottolab/research/b649_eh01_eh10_dataset.py` (confirmed absent from
`origin/main` via `git cat-file -e origin/main:<path>` — file-not-found),
added by the not-yet-pushed EH01/EH10 lock-execute commit. This task's own
dataset verification queried `research_draw_bindings` with raw SQL directly
against the physical `baseline.sqlite` file, **not** through that module, so
none of the findings below depend on code that is absent from `origin/main`.
A future EH02 implementation on a fresh `origin/main` checkout can either
port that loader module over or inline the equivalent 15-line SQL query
below — both are shown to produce the identical, hash-verified result.

## 1. B649 authority: the `2,138 vs 2,145` conflict, resolved

### 1.1 Authority A — `research_draw_bindings` (SELECTED)

- **Locator:** `/Users/kelvin/VibeCoding-WorkSpace/.task-data/BIGLOTTO_CANONICAL_FULL_HISTORY_BASELINE_R4/baseline.sqlite`
  (file SHA-256 `67f8295375f50a7b2d9ba1c0a68e4ef7be23a1b4a64aef8bb45a57b7fa9485a7`,
  897,015,808 bytes).
- **Table/schema:** `research_draw_bindings`, defined in
  `src/lottolab/infrastructure/persistence/research_schema.py` (identical on
  both git refs, §0).
- **Query (reproduced verbatim, raw SQL, no module dependency):**
  ```sql
  SELECT draw_number, draw_date, main_numbers_json
  FROM research_draw_bindings
  WHERE lottery_type = 'BIG_LOTTO'
    AND draw_data_version = 'canonical-full-history-2382-draws-v1'
    AND draw_number != replace(draw_date, '-', '')
  ORDER BY draw_date ASC, CAST(draw_number AS INTEGER) ASC
  ```
- **Raw/eligible counts:** 2,288 total rows tagged
  `draw_data_version='canonical-full-history-2382-draws-v1'` +
  `lottery_type='BIG_LOTTO'`; 150 excluded as `DATE_LIKE` contaminants
  (`draw_number == replace(draw_date,'-','')` — a different, non-BigLotto
  game mislabeled at import time, per the exclusion rule's own precedent);
  **2,138 clean/eligible rows** remain.
- **Date range:** `2007-03-09 .. 2026-07-31`.
- **Lottery identity rule:** `lottery_type='BIG_LOTTO'` exact match; no
  special/7th number in this series (excluded identically to every other
  series in this design).
- **Logical content SHA-256** (sorted-key JSON of
  `{draw_ids, draw_dates, main_number_sums}`, ascending `(draw_date,
  draw_id)` order — the exact representation EH02 itself consumes):
  `a1f39161797cadc132a4ae561e382b577a9c4a573c9866e34f61ee4af71a9918`.
- **Independent reconfirmation:** this exact table + filter + result
  (2,138 rows, same date range) has now been produced **four separate
  times** by unrelated tasks: the BIG_LOTTO uniformity/contamination audit,
  the sealed `REGIME_CHANGE_POINT_CUSUM_B649_V1` cell, the EH01/EH10
  lock-execute task (`b649-track-b-eh01-eh10-lock-execute-r1`, which calls
  it "a triply-independent hit... the settled clean-B649-history rule"),
  and this task (4th, freshly re-run, not copied).

### 1.2 Authority B — legacy strategy-replay chain (REJECTED)

- **Locator:** `~/VibeCoding-WorkSpace/.task-data/B649_ALL_STRATEGIES_ALL_TICKETS_HISTORICAL_RAW_FOUNDATION_R2/`
  — `draw_index.csv` (3,149 raw rows, the foundation's own consolidated raw
  draw catalog) plus one legacy prediction strategy's replay chain,
  `raw_records/legacy_biglotto__attention_replay_predictor__a811e2eb8215.jsonl.gz`
  (2,144 target rows, each linked to the previous by an explicit
  `historical_input_cutoff_draw` field), seeded by `draw_index.csv`'s first
  row (`96000001`, 2007-01-02) as the chain's initial node. `1 + 2,144 =
  2,145`.
- **What this artifact actually is:** per its own `source_provenance.json`
  and `README.md`, `B649_ALL_STRATEGIES_ALL_TICKETS_HISTORICAL_RAW_FOUNDATION_R2`
  is a "consolidation-only... historical raw ticket foundation" holding
  **2,590,280 raw ticket rows across 133 canonical legacy strategies**,
  built for strategy-backtest replay, not a maintained draw-history table.
  The "2,145-draw chain" is the coverage footprint of **one single named
  legacy strategy's** replay — a byproduct of that strategy having an
  unbroken cutoff-chain over 2,144 successive targets — not an independent
  draw-history pull.
- **Ultimate data ancestor:** the strategy corpus (and its `draw_index.csv`)
  was itself built from a frozen legacy database snapshot,
  `<repo>/.local/snapshots/p600ab-r1-20260715T122730+0800/lottery_v2.db`
  (verified this task: file SHA-256
  `e8a56e9f4979d3fbe91951be1f9d1ae4820ea1dcd92be47ef61cacd296c4b439`, exactly
  matching both the reproducer's `SNAPSHOT_DB_SHA256` constant and the
  `[[legacy-reference-corpus-location]]` memory's recorded hash for "the
  only copy of the legacy DB"). That memory explicitly designates this
  corpus a **`REFERENCE_BASELINE`, "excluded from authoritative
  coverage/ranking by default"** — a prior, independent provenance ruling,
  not an inference made for this task.
- **Chain-of-custody hash check (this task, independent):** re-extracted the
  full 2,145-draw chain from the sealed foundation files and recomputed
  both fingerprints the predecessor study recorded:
  - Target chain (2,144 rows) SHA-256:
    `af15c2578cab534c673904b1e1a4e6a0ca30f7e32d03ecc85a8cb6bba45f602f` — **MATCH**.
  - Full chain (2,145 rows) SHA-256:
    `9a8f9bdd3153c3b88e4df7dab8081c0ea83bff957a7cea1b3a894dd7ab978e8b` — **MATCH**.

  Confirms the artifact is unchanged since the predecessor study read it —
  not a re-derivation from a drifted copy.
- **Date range:** `2007-01-02 .. 2026-07-10`.

### 1.3 Row-level identity comparison (exact, this task)

Directly diffed Authority A's 2,138 rows against Authority B's 2,145 rows on
`(draw_id, draw_date, main_numbers)`:

| | Count |
|---|---:|
| Common `draw_id` between A and B | 2,126 |
| Common rows with **identical** `(draw_date, main_numbers)` | 2,126 (100%) |
| Common rows with **mismatched** content | **0** |
| Rows only in B (not in A) | 19 |
| Rows only in A (not in B) | 12 |

**Zero content disagreement anywhere the two chains overlap** — this is the
same real-world draw history, not two diverging datasets.

- **The 19 B-only rows** are exactly B649's earliest 19 draws
  (`96000001..96000019`, 2007-01-02..2007-03-06) — one calendar day short of
  where Authority A's `canonical-full-history-2382-draws-v1` version
  actually begins (2007-03-09). None match the `DATE_LIKE` contamination
  pattern; this is a documented version-scope boundary in the canonical
  table, not a data-quality exclusion. At a 200-observation burn-in and
  ≥800-eligible geometry floor (§4), 19 rows at the very start of history
  are immaterial to either edge.
- **The 12 A-only rows** split into two fully-explained groups: 6 postdate
  B's freeze entirely (`2026-07-14..2026-07-31` — Authority A is simply 21
  days more current, since Authority B was sealed on 2026-08-10 against
  data frozen earlier); the other 6 are real **internal gaps inside B's own
  date range** (2007-07-20, 2007-11-09, 2008-08-26, 2009-09-08, 2011-01-11,
  2011-04-29) — draws the one legacy strategy's replay simply never covered
  (consistent with that foundation's own accounting: "Original gaps
  accounted for: 4,438... Explicit remaining terminal or Owner-accepted
  exceptions: 3,880").

### 1.4 Resolution and rejection rationale

**`B649_2138_VS_2145_RESOLUTION`: Authority A (`research_draw_bindings`,
`canonical-full-history-2382-draws-v1`, `EXCLUDE_DATE_LIKE`, 2,138 rows,
2007-03-09..2026-07-31) is the resolved EH02 B649 authority.**

This is a structural/provenance decision, not a bigger-or-newer default —
Authority A has the *smaller* raw row count of the two candidates. The
selection rests on evidence, not intuition:

1. **Purpose and maintenance.** A is the project's purpose-built, schema-
   native, actively-maintained canonical draw-history table. B is an
   incidental byproduct of one specific legacy prediction strategy's
   backtest-replay coverage inside a strategy-analysis corpus that performs
   "no new strategy research, ranking, statistical analysis... or external
   draw validation" by its own charter.
2. **Independent reconfirmation.** A's exact result has been produced four
   times by unrelated tasks using the same table/filter. B's count has been
   produced once, by the one predecessor study that happened to build it.
3. **Completeness over the shared window.** Where the two overlap, content
   agrees 100%. A has zero internal gaps; B has 6 (real, accepted-exception
   gaps inherited from the legacy strategy corpus).
4. **Currency.** A extends 21 days further (through 2026-07-31 vs.
   2026-07-10).
5. **A prior, independent provenance ruling.** B's ultimate data ancestor
   (the frozen `lottery_v2.db` snapshot) was already designated
   `REFERENCE_BASELINE`, "excluded from authoritative coverage/ranking by
   default," by an earlier, unrelated task — this task did not invent that
   downgrade.

The 19 early draws unique to B (2007-01-02..2007-03-06) are the only
material completeness loss from selecting A, and are immaterial at this
design's 200-observation burn-in / ≥800-eligible-total scale (§4).

## 2. T539 authority (independently pinned, not copied)

- **Locator (canonical copy):**
  `/Users/kelvin/VibeCoding-WorkSpace/.runs/MathStatisticalAnalysis/T539_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2/t539_wave1.sqlite3`
  (file SHA-256 `cddfd82e39359bbff1e781f624fca42afd26849c38dab628223e7afd857b9b81`).
- **Table/schema:** `source_draws(draw_id TEXT PK, lottery_type TEXT,
  draw_date TEXT, main_numbers_json TEXT, draw_order INTEGER)`, confirmed
  via `PRAGMA table_info` this task.
- **Lottery identity rule:** `lottery_type='DAILY_539'` (single value
  present in this table; no filter needed).
- **Eligible row count:** **5,930**. **Date range:** `2007-01-01 ..
  2026-08-01`.
- **Known exclusions/contamination:** **none required.** Full integrity
  re-check this task: every row has exactly 5 distinct integers in `[1,39]`,
  `draw_id` unique (5,930/5,930), `draw_date` unique and strictly
  increasing — 0 violations.
- **Cross-copy verification (this task, independent):** a second,
  independently-materialized copy
  (`.runs/MathStatisticalAnalysis/T539_ALL_STRATEGIES_MIGRATION_BACKTEST_WAVE1_R1/t539_wave1.sqlite3`,
  file SHA-256 `091ade9e4a91c56b674e21ca53a859a6deb2d0a54139623d6885dc8f9e698f50`
  — byte-different file, same logical content) reproduces the identical
  5,930-row, same-date-range result. Two further copies elsewhere in this
  program (`T539_WAVE4_REMAINING5_BATCH_COVERAGE_CLOSURE_R1`,
  `T539_WAVE3_ACB1_ALIAS_COVERAGE_CLOSURE_R1`) were also queried this task
  and agree exactly — 5-way agreement across independently-materialized
  copies.
- **Logical content SHA-256** (same convention as B649 §1.1):
  `794ef4e5ed3268c750f484836b0c31591ce56f287dca4b882b5925a6fddcaa42`,
  confirmed identical across both independently-materialized copies.
- **Comparison against the proposal's carried-forward figure (5,913 draws,
  2007-01-01..2026-07-13, sourced from the same legacy `lottery_v2.db`
  snapshot as B649 Authority B):** row-level diff (this task) shows all
  5,913 legacy rows present, byte-identical, inside the 5,930-row current
  source — a **clean superset**, zero mismatches, zero internal gaps. The
  current source simply has 17 additional, more recent draws
  (2026-07-14..2026-08-01) that occurred after the legacy snapshot was
  frozen. The proposal's carried-forward number was stale, not wrong.

**`T539_DATA_AUTHORITY`: `source_draws` in `t539_wave1.sqlite3`
(`T539_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2`), 5,930 rows,
2007-01-01..2026-08-01.**

## 3. P638 Zone-1 authority (independently pinned, not copied)

- **Locator (canonical copy):**
  `/Users/kelvin/VibeCoding-WorkSpace/.runs/MathStatisticalAnalysis/P638_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2/p638_wave1.sqlite3`
  (file SHA-256 `9a697b3384d469f032d0649e8fd05b9a9900beb46e5527b129e3b1a6624d434a`).
- **Table/schema:** `draws(run_id, draw_number, draw_date,
  main_numbers_json, second_number, source_reference)`, confirmed via
  `PRAGMA table_info` this task. `source_reference` traces to the Taiwan
  Lottery official API, `SuperLotto638Result` endpoint.
- **Zone rule:** Zone-1 = `main_numbers_json` (6 of 38). **Zone-2
  (`second_number`, 1-of-8) is out of scope** — read only to confirm it
  stays within `[1,8]`, never used in any join, hash, or count below,
  matching the task's explicit boundary.
- **Eligible row count:** **1,933**. **Date range:** `2008-01-24 ..
  2026-07-30`.
- **Known exclusions/contamination:** **none required.** Full integrity
  re-check this task: 6 distinct integers in `[1,38]` per row,
  `second_number` in `[1,8]`, `draw_number` and `draw_date` both unique
  (1,933/1,933), numeric `draw_number` order strictly matches increasing
  `draw_date` — 0 violations. (Note carried from the source report and
  reconfirmed: `draw_number` is TEXT and mixes 8-digit/9-digit ROC-year
  values, so plain lexicographic sort is chronologically wrong — every
  ordering operation in this resolution uses `draw_date` or `CAST(...AS
  INTEGER)`, never raw TEXT sort.)
- **Cross-copy verification (this task, independent):** a second,
  independently-materialized copy
  (`.runs/MathStatisticalAnalysis/P638_ALL_STRATEGIES_MIGRATION_BACKTEST_WAVE1_R1/p638_wave1.sqlite3`,
  file SHA-256 `a59e47f07ee86e800ab3fadf8c22d40cd3f13e88a0b9f91543568c7349211bcf`)
  reproduces the identical 1,933-row result. A third copy
  (`P638_WAVE1_REPLAY_R4_LEDGER_SOURCE_AUTHORITY`) was also queried this
  task and agrees exactly — 3-way agreement.
- **Logical content SHA-256** (Zone-1 numbers only, same convention as §1.1):
  `49c1911154a0f95256ab12b25f5301dfb4480e4302dc0d3b6f422d247ee46df0`,
  confirmed identical across both independently-materialized copies.
- **Comparison against the proposal's carried-forward figure (1,928 draws,
  2008-01-24..2026-07-13, same legacy snapshot ancestor):** row-level diff
  (this task) shows all 1,928 legacy rows present, byte-identical, inside
  the 1,933-row current source — a **clean superset**, zero mismatches,
  zero internal gaps. 5 additional, more recent draws
  (2026-07-16..2026-07-30) account for the entire difference. Same stale
  -snapshot pattern as B649 and T539.

**`P638_ZONE1_DATA_AUTHORITY`: `draws` (Zone-1 only) in `p638_wave1.sqlite3`
(`P638_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2`), 1,933 rows,
2008-01-24..2026-07-30. Zone-2: `OUT_OF_SCOPE`, confirmed unused.**

## 4. Causal alignment — computability verification

Rule preserved unchanged from the proposal (§2.3): for B649 target `t`,
`prior_L(t)` = the draw of lottery `L` with the maximum `draw_date` strictly
less than `draw_date_B649(t)`; equality excluded; if none exists, `t` is
ineligible for that edge. Verified this task, using only `draw_id`/
`draw_date` from the three now-pinned datasets (no main-number content
inspected for this step):

| Edge | Eligible targets (`t-1` exists AND `prior_L(t)` exists) | Same-day exclusion triggered | No-prior-at-all | Post-burn-in(200) eligible | ERA4 partition sizes |
|---|---:|---:|---:|---:|---|
| `T539 -> B649` | 2,137 / 2,137 possible (100%) | 2,117 targets | 0 | 1,937 (floor ≥800: **PASS**) | 485, 484, 484, 484 (floor ≥30: **PASS**) |
| `P638Z1 -> B649` | 2,046 / 2,137 possible (95.7%) | 42 targets | 91 (P638 history starts 2008-01-24, after B649's 2007-03-09 start) | 1,846 (floor ≥800: **PASS**) | 462, 461, 462, 461 (floor ≥30: **PASS**) |

Chronology invariants independently reverified for all three pinned series
this task (ascending order, unique `draw_id`, unique `draw_date` — 0
violations in every series). Same-day exclusion is confirmed **non-vacuous**
(triggers on 99.1% of T539-edge targets, since T539 draws near-daily; 2.1%
of P638Z1-edge targets) via direct spot-check against a strictly-prior
`bisect` lookup (three manually inspected cases, all correct).

**`CAUSAL_ALIGNMENT_STATUS`: `COMPUTABLE_VERIFIED` for both edges** — join
rule, same-day exclusion, and the proposal's own §11 geometry floor
(`>=800` total, `>=30` per era) all hold against the pinned datasets, using
only date/id metadata. No transfer-entropy, mutual-information, or other
EH02 statistic was computed.

## 5. EH02 final parameter table

All non-dataset locks are **reproduced unchanged** from
`B649_TRACK_B_EH02_PARAMETER_LOCK_PROPOSAL_R1.md` (§0, §12) — this task
applies them to the pinned identities above; it does not revise any of them.

| Item | Lock |
|---|---|
| Target representation | B649 chronological main-number sum, one scalar/draw |
| Source representation | T539 / P638 Zone-1 chronological main-number sum, one scalar/draw |
| Cross-lottery alignment | last strictly-prior source draw, `draw_date < B649_target_date`, same-day excluded |
| Lag / embedding | source order 1 (single most-recent strictly-prior draw); target self-order 1; no grid |
| Discretization | causal expanding-window equal-frequency tertiles (`B=3`), independently per series |
| Estimator | discrete plug-in (Schreiber 2000) conditional transfer entropy, natural log |
| Comparator | unconditioned lagged mutual information, same discretization |
| Primary null | `999` source-only permutations (`GLOBAL`) |
| Era robustness null | `999` source-only permutations within `ERA4` |
| Timing control | `TE_observed > TE_stale@28d` |
| Directionality control | `p_raw(forward) < p_raw(reverse)` AND `p_raw(reverse) > 0.10` |
| Multiplicity | Holm within 2-endpoint `GLOBAL` family + 2-endpoint `ERA4` family |
| Classification | `SIGNAL` / `WEAK_SIGNAL` / `NO_SIGNAL` / `INVALID_OR_UNIDENTIFIABLE` per proposal §10 |
| Burn-in | 200 eligible observations |
| Geometry floor | ≥800 eligible total, ≥30 per era |
| Master seed | `6490110`, SHA-256 hash-sort, `EDGE_ID`-salted |

### 5.1 Dataset block (this task's resolution — the only section that changes)

```yaml
dataset:
  b649_authority_mode: research_draw_bindings_exclude_date_like
  b649_source_path: /Users/kelvin/VibeCoding-WorkSpace/.task-data/BIGLOTTO_CANONICAL_FULL_HISTORY_BASELINE_R4/baseline.sqlite
  b649_table: research_draw_bindings
  b649_filter: "lottery_type='BIG_LOTTO' AND draw_data_version='canonical-full-history-2382-draws-v1' AND draw_number != replace(draw_date,'-','')"
  t539_source_path: /Users/kelvin/VibeCoding-WorkSpace/.runs/MathStatisticalAnalysis/T539_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2/t539_wave1.sqlite3
  t539_table: source_draws
  t539_filter: "lottery_type='DAILY_539'"
  p638_zone1_source_path: /Users/kelvin/VibeCoding-WorkSpace/.runs/MathStatisticalAnalysis/P638_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2/p638_wave1.sqlite3
  p638_zone1_table: draws
  p638_zone1_columns: [draw_number, draw_date, main_numbers_json]
  eligible_history_rule: "ascending (draw_date, draw_id); B649 EXCLUDE_DATE_LIKE; T539/P638 no exclusion needed (0 violations)"
  cutoff:
    b649: "2026-07-31"
    t539: "2026-08-01"
    p638_zone1: "2026-07-30"
  row_counts:
    b649: 2138
    t539: 5930
    p638_zone1: 1933
  logical_sha256:
    b649: a1f39161797cadc132a4ae561e382b577a9c4a573c9866e34f61ee4af71a9918
    t539: 794ef4e5ed3268c750f484836b0c31591ce56f287dca4b882b5925a6fddcaa42
    p638_zone1: 49c1911154a0f95256ab12b25f5301dfb4480e4302dc0d3b6f422d247ee46df0
eligibility:
  t539_to_b649:
    eligible_post_burn_in: 1937
    era4_partition_sizes: [485, 484, 484, 484]
  p638zone1_to_b649:
    eligible_post_burn_in: 1846
    era4_partition_sizes: [462, 461, 462, 461]
approval:
  owner_decision_id: TBD_BEFORE_DATA_READ   # see §7 item 1
  approved_at: TBD_BEFORE_DATA_READ
implementation:
  repository: TBD_BEFORE_DATA_READ           # see §7 item 2
  commit: TBD_BEFORE_DATA_READ
  tree: TBD_BEFORE_DATA_READ
  runtime: TBD_BEFORE_DATA_READ
  dependency_lock_sha256: TBD_BEFORE_DATA_READ
  runner_path: TBD_BEFORE_DATA_READ
  synthetic_fixture_check: PASS_REQUIRED     # see §7 item 3
preregistration_sha256: null_until_owner_approval   # NOT created this task, per instruction
```

Every other field of the proposal's §15 schema (`input`, `representation`,
`edges`, `estimator`, `comparator`, `null`, `controls`, `diagnostics`,
`multiplicity`, `classification`, `geometry_floor`, `claim_boundaries`) is
unchanged from the proposal and is not repeated here in full to keep this
artifact minimal — see `B649_TRACK_B_EH02_PARAMETER_LOCK_PROPOSAL_R1.md` §15
for the complete YAML.

## 6. Timing and directionality controls (unchanged; restated for completeness)

- **`TIMING_CONTROL`**: `stale_days=28`, computed with the identical
  estimator/eligible-set/discretization/`GLOBAL` permutation procedure,
  substituting `stale_prior_L(t)` (last source draw `<= target_date - 28
  days`) for `prior_L(t)`. Gate: `TE_observed(edge) > TE_stale(edge)`. Not
  Holm-adjusted; cannot rescue a `NO_SIGNAL` result; evaluated once, at this
  exact offset only. **Status: `LOCKED_UNCHANGED`, not yet evaluated
  (`EH02_EXECUTION: NOT_RUN`).**
- **`DIRECTIONALITY_CONTROL`**: reverse-direction `TE(B649 -> L)`, same
  discretization/estimator/`GLOBAL` null, salted `..._REVERSE` edge IDs.
  Gate: `p_raw(forward) < p_raw(reverse)` AND `p_raw(reverse) > 0.10`. Not
  Holm-adjusted; both required for `SIGNAL`. **Status: `LOCKED_UNCHANGED`,
  not yet evaluated.**

Both controls are computable against the pinned datasets — the join,
eligible-set, and discretization machinery they depend on is exactly the
machinery verified in §4 — but neither was run. No TE, MI, permutation, or
p-value was computed at any point in this task.

## 7. Remaining prelock issues (proposal §14, updated status)

| # | Issue | Status after this task |
|---|---|---|
| 1 | Owner approval of the two-edge, single-lag, dual-control design | This task's own authorizing packet reproduces the proposal's exact design verbatim and directs "apply the existing proposal without outcome-dependent revision" — a strong, but still informal, ratification (the same pattern `[[b649-track-b-eh01-eh10-lock-execute-r1]]` used: a chat-level authorization treated as the acceptance record). No separate `owner_decision_id` artifact exists yet; still formally `TBD_BEFORE_DATA_READ` in §5.1. |
| 2 | **B649 dataset pin** | **RESOLVED this task — §1.** |
| 3 | **T539 / P638 Zone-1 dataset pin** | **RESOLVED this task — §2, §3.** |
| 4 | Implementation route (runner, runtime, dependency lock, commit, tree) | Still open — out of this task's scope. Note: the convenience loader `b649_eh01_eh10_dataset.py` used by the precedent EH01/EH10 work is local-only (absent from `origin/main`, §0); a future runner should either port it or inline the 15-line SQL query in §1.1, both verified equivalent this task. |
| 5 | Synthetic fixture (hand-verifiable 3-symbol TE check) | Still open — not constructed this task (would require touching the estimator itself, out of scope for a data-authority/parameter-lock resolution). |
| 6 | Code identity (repo path, branch, commit, tree, `.task-data` output root) | Still open. |
| 7 | Final canonical preregistration JSON + its digest | Still open — explicitly **not** created this task per instruction. |

No item above required inspecting an EH02 result, and none was.

## 8. Hash/provenance summary

| Artifact | SHA-256 |
|---|---|
| `baseline.sqlite` (B649 Authority A, physical file) | `67f8295375f50a7b2d9ba1c0a68e4ef7be23a1b4a64aef8bb45a57b7fa9485a7` |
| B649 Authority A logical content (2,138 rows) | `a1f39161797cadc132a4ae561e382b577a9c4a573c9866e34f61ee4af71a9918` |
| Legacy snapshot `lottery_v2.db` (B649 Authority B's ultimate ancestor; also T539/P638 legacy comparator) | `e8a56e9f4979d3fbe91951be1f9d1ae4820ea1dcd92be47ef61cacd296c4b439` |
| B649 Authority B target chain (2,144 rows) | `af15c2578cab534c673904b1e1a4e6a0ca30f7e32d03ecc85a8cb6bba45f602f` |
| B649 Authority B full chain (2,145 rows) | `9a8f9bdd3153c3b88e4df7dab8081c0ea83bff957a7cea1b3a894dd7ab978e8b` |
| `t539_wave1.sqlite3` (`CLEAN_REPRODUCTION_R2`, physical file) | `cddfd82e39359bbff1e781f624fca42afd26849c38dab628223e7afd857b9b81` |
| `t539_wave1.sqlite3` (`MIGRATION_BACKTEST_WAVE1_R1`, physical file) | `091ade9e4a91c56b674e21ca53a859a6deb2d0a54139623d6885dc8f9e698f50` |
| T539 logical content (5,930 rows, both copies) | `794ef4e5ed3268c750f484836b0c31591ce56f287dca4b882b5925a6fddcaa42` |
| `p638_wave1.sqlite3` (`CLEAN_REPRODUCTION_R2`, physical file) | `9a697b3384d469f032d0649e8fd05b9a9900beb46e5527b129e3b1a6624d434a` |
| `p638_wave1.sqlite3` (`MIGRATION_BACKTEST_WAVE1_R1`, physical file) | `a59e47f07ee86e800ab3fadf8c22d40cd3f13e88a0b9f91543568c7349211bcf` |
| P638 Zone-1 logical content (1,933 rows, both copies) | `49c1911154a0f95256ab12b25f5301dfb4480e4302dc0d3b6f422d247ee46df0` |

Physical file hashes legitimately differ across "independently-materialized
copies" (different SQLite page layout/vacuum state); logical content hashes
are identical across copies in every case checked, confirming the copies
disagree only at the byte level, never in content.

## 9. Required return block

```text
B649_DATA_AUTHORITY:
  RESEARCH_DRAW_BINDINGS_EXCLUDE_DATE_LIKE; baseline.sqlite
  (BIGLOTTO_CANONICAL_FULL_HISTORY_BASELINE_R4); lottery_type=BIG_LOTTO,
  draw_data_version=canonical-full-history-2382-draws-v1;
  2138_ROWS; 2007-03-09_TO_2026-07-31;
  LOGICAL_SHA256_a1f39161797cadc132a4ae561e382b577a9c4a573c9866e34f61ee4af71a9918

B649_2138_VS_2145_RESOLUTION:
  AUTHORITY_A_SELECTED_2138; AUTHORITY_B_REJECTED_2145_LEGACY_STRATEGY_REPLAY_BYPRODUCT;
  ZERO_CONTENT_DISAGREEMENT_ON_2126_COMMON_ROWS; B_ONLY_19_ROWS_ARE_PRE_VERSION_SCOPE_EARLIEST_DRAWS;
  A_ONLY_12_ROWS_SPLIT_6_MORE_CURRENT_PLUS_6_ACCEPTED_GAPS_IN_B;
  B_ULTIMATE_ANCESTOR_IS_PRIOR_DESIGNATED_REFERENCE_BASELINE_NOT_AUTHORITATIVE;
  DECISION_IS_STRUCTURAL_PROVENANCE_NOT_SIZE_HEURISTIC

T539_DATA_AUTHORITY:
  source_draws; t539_wave1.sqlite3 (T539_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2);
  lottery_type=DAILY_539; 5930_ROWS; 2007-01-01_TO_2026-08-01; ZERO_EXCLUSIONS_NEEDED;
  5_WAY_INDEPENDENT_COPY_AGREEMENT;
  LOGICAL_SHA256_794ef4e5ed3268c750f484836b0c31591ce56f287dca4b882b5925a6fddcaa42;
  SUPERSEDES_PROPOSAL_CARRIED_FORWARD_5913_STALE_LEGACY_SNAPSHOT_CLEAN_SUPERSET

P638_ZONE1_DATA_AUTHORITY:
  draws (zone-1 only); p638_wave1.sqlite3 (P638_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2);
  source_reference=Taiwan_Lottery_official_API_SuperLotto638Result;
  1933_ROWS; 2008-01-24_TO_2026-07-30; ZERO_EXCLUSIONS_NEEDED; ZONE2_OUT_OF_SCOPE_CONFIRMED_UNUSED;
  3_WAY_INDEPENDENT_COPY_AGREEMENT;
  LOGICAL_SHA256_49c1911154a0f95256ab12b25f5301dfb4480e4302dc0d3b6f422d247ee46df0;
  SUPERSEDES_PROPOSAL_CARRIED_FORWARD_1928_STALE_LEGACY_SNAPSHOT_CLEAN_SUPERSET

CAUSAL_ALIGNMENT_STATUS:
  COMPUTABLE_VERIFIED_BOTH_EDGES;
  T539_TO_B649_ELIGIBLE_2137_OF_2137_POSSIBLE_POST_BURNIN_1937_ERA4_MIN_484;
  P638Z1_TO_B649_ELIGIBLE_2046_OF_2137_POSSIBLE_POST_BURNIN_1846_ERA4_MIN_461;
  SAME_DAY_EXCLUSION_CONFIRMED_NON_VACUOUS_BOTH_EDGES;
  GEOMETRY_FLOOR_800_TOTAL_30_PER_ERA_PASS_BOTH_EDGES;
  CHRONOLOGY_INVARIANTS_REVERIFIED_ALL_THREE_SERIES

EH02_FINAL_PARAMETER_LOCK:
  ALL_NON_DATASET_LOCKS_REPRODUCED_UNCHANGED_FROM_PROPOSAL_R1_SECTION_0_AND_12;
  DATASET_BLOCK_RESOLVED_SECTION_5.1_THIS_DOCUMENT;
  NO_PARAMETER_REVISION_OF_ANY_KIND

TIMING_CONTROL:
  LOCKED_UNCHANGED_STALE_DAYS_28_GATE_OBSERVED_GT_STALE; COMPUTABLE_AGAINST_PINNED_DATA; NOT_YET_EVALUATED

DIRECTIONALITY_CONTROL:
  LOCKED_UNCHANGED_REVERSE_TE_GATE_FWD_P_LT_REV_P_AND_REV_P_GT_0.10; COMPUTABLE_AGAINST_PINNED_DATA; NOT_YET_EVALUATED

PREREGISTRATION_READY:
  DATA_AUTHORITY_AND_PARAMETER_TABLE_COMPLETE;
  APPROVAL_IMPLEMENTATION_SYNTHETIC_FIXTURE_FIELDS_STILL_TBD_BEFORE_DATA_READ;
  PREREGISTRATION_SHA256_NOT_CREATED_PER_INSTRUCTION

REMAINING_PRELOCK_ISSUES:
  OWNER_APPROVAL_FORMAL_RECORD_STILL_INFORMAL_SEE_SECTION_7_ITEM_1;
  PINNED_RUNNER_RUNTIME_COMMIT_AND_TREE;
  SYNTHETIC_FIXTURE_CONSTRUCTION_AND_ACCEPTANCE;
  FINAL_CANONICAL_PREREGISTRATION_AND_HASH_NOT_YET_CREATED

EH02_EXECUTION: NOT_RUN
SCIENTIFIC_OUTCOME_ANALYSIS: NOT_RUN
FINAL_CLASSIFICATION:
  EH02_DATA_AUTHORITY_AND_PARAMETER_LOCK_READY_FOR_OWNER_REVIEW
```

STOP.
