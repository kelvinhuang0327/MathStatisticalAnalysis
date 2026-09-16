# P638 Track D — Higher-Order (Triple/Quadruple) Joint Uniformity R1

TASK_ID: P638_TRACK_D_HIGHER_ORDER_JOINT_UNIFORMITY_R1
MODE: READ_ONLY_DISCOVERY_ANALYSIS
DATE: 2026-08-15

## PACKET-VS-REPOSITORY CONFLICT (read this first)

The task packet instructs: "完全沿用已完成 B649 / T539 higher-order diagnostic
semantics" (fully reuse the already-completed B649/T539 higher-order
triple/quadruple diagnostic semantics), treating that prior art as an
existing, citable methodology to replicate with the null swapped to 6-of-38.

A full read-only search of this repository — `main`, all 17 other local
branches, all worktrees, and the complete 370-commit git history (`git grep`
across `git rev-list --all` for `track.?d`, `joint.uniform`, `triple.wise`,
`quadruple.wise`, `omnibus`, `higher_order`) — found **no such artifact**.
The only related precedent is an orphaned, never-committed **pairwise-only**
B649 audit (`docs/audits/biglotto-uniformity-dependence-audit-r1.md` +
`tools/audit_biglotto_uniformity_dependence.py`, sitting uncommitted in a
separate worktree, branch `codex/b649-uniformity-dependence-audit-rebuild-r1`)
which explicitly documents triples+ as `NOT_TESTED`
(`docs/audits/biglotto-uniformity-dependence-audit-r1.md:170`). No T539
higher-order diagnostic and no P638 zone-1 marginal/pairwise Track-D
replication exist anywhere either.

Per fable-method's contract-conflict rule, this is flagged rather than
silently resolved. It did **not** block execution, because the packet's own
step-by-step instructions (fixed statistic, fixed seed, 20,000 MC reps, exact
per-triple binomial test, pooled Holm/FWER, no fishing) are precise enough to
execute a principled, self-contained analysis without the missing precedent.
The exact statistical design actually used is documented in full below so a
downstream reviewer or a genuine B649/T539 run can verify comparability
rather than assume it. **The cross-lottery synthesis this task's own NEXT
step calls for (B649 + T539 + P638 zone-1) cannot be trusted as
"comparable methodology" until B649 and T539 versions of this diagnostic
are actually run** — they do not yet exist.

IS_EXPLICIT_OVERRIDE: NO (no Owner override obtained; proceeding was
justified by the packet's self-contained spec, not by treating the false
premise as true)

**Provenance correction (added by
`TRACK_D_CROSS_LOTTERY_HIGHER_ORDER_SYNTHESIS_AND_NEXT_DIRECTION_R1`,
2026-08-15, later the same day):** `B649_TRACK_D_HIGHER_ORDER_JOINT_UNIFORMITY_B649_R1.md`
and `T539_TRACK_D_HIGHER_ORDER_JOINT_UNIFORMITY_R1.md` now exist (both
completed after this report started, per their own file timestamps).
Read-only comparison confirms the same semantic design across all three:
a fixed, zero-tuning chi-square-type global omnibus statistic (this
report's `S_k`/`T_k` pair is algebraically equivalent to B649/T539's direct
`Σ(O-E)²/E` form), a fixed-seed Monte Carlo null with R=20,000 replications,
an exact per-triple two-sided binomial local scan with Holm-Bonferroni
correction at α=0.05, and no local quadruple fishing scan in any of the
three. Only the game-shape-dependent inclusion probabilities differ, as
expected. **The "cross-lottery comparability is provisional" caveat below
is resolved as of this correction** — the three-way synthesis can now be
trusted on methodology grounds. The conflict narrative above is left
unedited as an accurate record of what was true when this report was
executed; only this note reflects the later, complete state. No statistics
in this report were rerun.

## Data source and integrity

**Primary source**: `p638_wave1_replay_r4.sqlite3` (`.runs/…/P638_WAVE1_REPLAY_R4_LEDGER_SOURCE_AUTHORITY/`),
table `draws`, queried read-only (`main_numbers_json`, `second_number`),
ordered by `draw_date ASC, CAST(draw_number AS INTEGER) ASC`.

**Cross-check source**: `powerlotto_draws.sqlite3` (`.runs/…/P638_OLD_DB_DRAW_MIGRATION_R1/`),
tables `lottery_draw` + `lottery_draw_number` (zone=1) — an independently
migrated copy whose schema mechanically enforces exactly-6 ascending zone-1
numbers per COMPLETE draw via `CHECK`/trigger constraints.

Both sources were loaded and reconciled per-draw. Only zone-1 (6-of-38) is
used; zone-2 (1-of-8) was never read into the analysis.

```
row_count_source1:            1933
valid_draw_count:              1933
duplicate_draw_numbers:        [] (0)
illegal_count_rows (≠6 uniq):  [] (0)
out_of_range_rows (∉1..38):    [] (0)
chronology_violations:         [] (0)
crosscheck_missing:            [] (0)
crosscheck_mismatches:         [] (0)
date_range:                    2008-01-24 .. 2026-07-30
```

DATA_INTEGRITY: CONFIRMED_CLEAN — 1,933 valid zone-1 draws, no duplicates,
no illegal/out-of-range rows, chronology monotonic, and the two independent
DB sources agree exactly on every draw's zone-1 number set.

## Method

Null hypothesis: each draw is an independent uniformly-random 6-subset of
{1..38} (the standard fair-lottery null used throughout this program's prior
uniformity work).

**Fixed triple/quadruple inclusion probabilities** (exact, as specified in
the packet):
- `p_triple = C(35,3)/C(38,6) = 0.0023708…` → `E_triple = n·p_triple = 4.5827`
- `p_quad = C(34,2)/C(38,6) = 0.0002032…` → `E_quad = n·p_quad = 0.3928`

**Chi-square-type omnibus statistic, computed via an exact algebraic
shortcut.** For a fixed-size combination family (triples, quadruples), the
naive chi-square statistic `T_k = Σ_c (count_c − E_k)² / E_k` over all
`C(38,k)` combinations reduces algebraically to an affine, strictly
increasing function of a single pairwise quantity:

```
S_k = Σ_{i<j} C(|draw_i ∩ draw_j|, k)          (sum over all C(1933,2) draw pairs)
sum_c count_c² = n·C(6,k) + 2·S_k
T_k = sum_c count_c² / E_k − 2·n·C(6,k) + E_k·C(38,k)
```

Because `T_k` is an increasing affine function of `S_k`, ranking/p-values from
comparing `T_k` to its Monte Carlo null are identical to comparing `S_k`
directly — so `S_k` (a pairwise near-duplicate count, computed via a single
`M @ Mᵀ` matrix product per dataset, `M` = 1933×38 binary draw-membership
matrix) was used as the fixed statistic. `T_k` is reported alongside `S_k`
for interpretability as a genuine chi-square-shaped quantity.

**GLOBAL TRIPLE / QUADRUPLE OMNIBUS**: `S_3` and `S_4` computed once from the
real 1,933 draws, then compared against 20,000 Monte Carlo replicate
datasets, each of 1,933 independent uniform-random 6-subsets of 38 (drawn via
`argsort` of per-row uniform randoms — an unbiased random-subset generator).
Both `S_3` and `S_4` were computed from the *same* 20,000 replicates (one MC
run, not two independent ones), avoiding any statistic/window search.
Two-sided MC p-value convention: `p = (1 + #{rep : S_rep ≥ S_obs}) / (reps+1)`
(one-sided "≥", which is the standard and correct convention for a
chi-square-type statistic where only large values indicate departure).

`SEED = 638193320260815` (fixed, documented, chosen once before any result
was seen). `REPS = 20000` (full run; no early stopping, no rep-count
search).

**LOCAL TRIPLE SCAN**: for each of the `C(38,3) = 8436` triples, an exact
two-sided binomial test (`scipy.stats.binomtest`, `n=1933`, `p=p_triple`)
against its observed count, followed by Holm–Bonferroni step-down correction
across the full family of 8,436 tests (`α = 0.05`). No quadruple-level local
scan was run, per the packet's explicit "no fishing" instruction — quadruples
were tested only at the global-omnibus level.

## Results

```
GLOBAL_TRIPLE_OMNIBUS
  S3_obs                = 88,610
  S3_mc_null (mean, sd) = 88,533.15, 397.55   (z ≈ 0.19)
  T3_obs (chi-sq form)  = 8,447.18
  p_triple_omnibus      = 0.4181

GLOBAL_QUADRUPLE_OMNIBUS
  S4_obs                = 5,732
  S4_mc_null (mean, sd) = 5,689.94, 92.07     (z ≈ 0.46)
  T4_obs (chi-sq form)  = 74,004.86
  p_quad_omnibus        = 0.3223

LOCAL_TRIPLE_SCAN (8,436 exact binomial tests, Holm/FWER, α=0.05)
  min_raw_p             = 8.7395e-05   (triple {9,29,36}: 15 obs vs 4.58 exp)
  min_adjusted_p        = 0.7373
  Holm survivors        = 0 / 8436
  count distribution:   mean 4.583, var 4.589, dispersion index 1.0014
                         (essentially Poisson — no over/under-dispersion)
  percentiles (1/5/25/50/75/95/99): 1, 1, 3, 4, 6, 8, 10

TOP RAW DEVIATIONS (largest |observed − expected|, none Holm-significant)
  {9,29,36}   obs=15  exp=4.58  raw_p=8.74e-05  adj_p=0.737
  {8,20,23}   obs=14  exp=4.58  raw_p=2.95e-04  adj_p=1.000
  {20,25,32}  obs=14  exp=4.58  raw_p=2.95e-04  adj_p=1.000
  {4,9,33}    obs=13  exp=4.58  raw_p=9.31e-04  adj_p=1.000
  {22,25,32}  obs=13  exp=4.58  raw_p=9.31e-04  adj_p=1.000
  (+ 15 more triples at obs=12-13, all adj_p=1.000 — full list in run JSON)

TEMPORAL SPLIT STABILITY (n1=966 draws 2008-01-24..~2017, n2=967 ..2026-07-30)
  S3_half1 = 22,173   S3_half2 = 22,121   (near-identical, no drift)
  z-score correlation of local triple deviations across halves: 0.0012
  → the largest local deviations (e.g. {9,29,36}) do NOT reproduce with
    consistent direction across the two halves — behavior expected of
    multiple-testing noise, not a real recurring effect.
```

## FINAL

```
TASK_ID:                         P638_TRACK_D_HIGHER_ORDER_JOINT_UNIFORMITY_R1
STATUS:                          COMPLETE
LOTTERY:                         P638
ZONE:                            1
GAME:                            6-of-38
DRAW_COUNT:                      1933
DATA_INTEGRITY:                  CONFIRMED_CLEAN (0 duplicates, 0 illegal,
                                  0 out-of-range, 0 chronology violations,
                                  0 cross-source mismatches)
TRIPLES_TESTED:                  8436
GLOBAL_TRIPLE_OMNIBUS_METHOD:    Chi-square-type statistic over C(38,3)
                                  triple counts (computed via exact pairwise
                                  near-duplicate identity S3), Monte Carlo
                                  null, fixed seed 638193320260815,
                                  20000 reps, no statistic/window search
GLOBAL_TRIPLE_OMNIBUS_P:         0.4181
LOCAL_HOLM_FAMILY_SIZE:          8436
MIN_RAW_P:                       8.7395e-05
MIN_ADJUSTED_P:                  0.7373
LOCAL_HOLM_SURVIVORS:            0
QUADRUPLE_GLOBAL_OMNIBUS:        Same MC design/seed/reps as triple omnibus,
                                  applied to C(38,4) quadruple counts via S4;
                                  no per-quadruple fishing scan performed
QUADRUPLE_P:                     0.3223
UNIFORMITY_VERDICT:              NO_DETECTABLE_HIGHER_ORDER_DEPARTURE
IMPORTANT_EFFECTS:                - Both global omnibus tests (triple, quad)
                                    are unremarkable (p=0.42, p=0.32),
                                    each well within 1 MC-sd of the null mean.
                                  - 0/8436 local triples survive Holm at
                                    α=0.05; the single largest deviation
                                    (raw p=8.7e-5) does not even clear an
                                    uncorrected Bonferroni threshold
                                    (0.05/8436=5.9e-6).
                                  - Local count dispersion index ≈1.0014:
                                    no over/under-dispersion signal.
                                  - Temporal split: near-zero (0.0012)
                                    cross-half correlation of local
                                    deviations — the top raw-p triples do
                                    not replicate across time, consistent
                                    with sampling noise, not structure.
INTERPRETATION:                  No higher-order (triple- or
                                  quadruple-wise) joint dependence beyond
                                  fair random 6-of-38 is detectable in P638
                                  zone-1 history by this diagnostic. Per the
                                  packet's own caveat, 0 Holm survivors does
                                  NOT by itself prove no higher-order
                                  dependence exists — the global omnibus
                                  (also null, p=0.42/0.32) is the primary
                                  verdict basis, and both lines of evidence
                                  agree. This extends the existing
                                  marginal/pairwise NO_DETECTABLE_DEPARTURE
                                  finding for P638 zone-1 to the
                                  triple/quadruple level, using a
                                  methodology designed to satisfy this
                                  packet's spec in the ABSENCE of a citable
                                  B649/T539 precedent (see conflict section
                                  above) — cross-lottery comparability is
                                  provisional, not yet verified against
                                  actual B649/T539 higher-order runs.
REPO_MUTATION:                   NONE
DB_MUTATION:                     NONE
```

## NEXT

Per the packet's routing: since the verdict is `NO_DETECTABLE`, the
indicated next step is a Track D cross-lottery higher-order synthesis
(B649 + T539 + P638 zone-1) and an Owner decision on deprioritizing
draw-history structure mining in favor of other predictive information
sources.

**Before that synthesis can proceed honestly**, the packet-vs-repository
conflict above needs resolving: no B649 or T539 higher-order (triple/quad)
diagnostic currently exists in this repository under any name, committed or
uncommitted. Two paths:

1. Run the B649 and T539 equivalents of this exact methodology (the script
   used here generalizes directly by pool/draw-size — `POOL=49, DRAW=6` for
   B649; `POOL=39, DRAW=5` for T539 — swapping only `p_triple`/`p_quad`),
   then perform the three-way synthesis for real, or
2. If an Owner or a concurrent session already has a genuine B649/T539
   higher-order result (several peer sessions were observed active on this
   repository during this task), reconcile against that artifact's actual
   methodology before claiming comparability — do not assume the memory
   trail referencing "B649 Track D higher-order" describes real, committed
   work without checking the live repository state first.

## Reproducibility

Analysis script and full raw JSON output (all 8,436 raw/adjusted p-values,
not just the top 20 shown above) are scratch artifacts outside the git
repository and outside any tracked source, per the packet's read-only /
no-repo-mutation constraint:
`p638_track_d_higher_order.py`, `full_result.json` — available on request;
not embedded here to keep this report readable. Rerunning with the same
`--seed 638193320260815 --reps 20000` reproduces the omnibus p-values
exactly (MC generation is deterministic given the seed); the local scan and
integrity checks are exact/deterministic with no seed dependence.
