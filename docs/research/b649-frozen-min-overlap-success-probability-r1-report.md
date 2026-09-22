# B649 frozen MIN_OVERLAP success probability R1

Task: `B649_FROZEN_MIN_OVERLAP_SUCCESS_PROBABILITY_R1`.
Evidence: `MODEL_BASED_GEOMETRY_EVIDENCE`.

[Confirmed] **POSITIVE_MODEL_GEOMETRY_GAIN** at both K: the complete frozen
cohort averages +4.403751 pp (K10 primary) and +1.279052 pp (K20 secondary).
Both pass the prespecified conservative precision/sign gate. This supports
combinatorial geometry as a mechanism for the historical positive result.
Implementation status: **COMPLETE**, with local uncommitted deliverables.

## Method fixed before evaluation

Frozen input: commit `d7665ee5d00fac09fdc593908e81e54ae080f2ba`,
tree `5a9cbff94817c82163c32f1274f7c73d19bc8426`,
`branch2-portfolio-geometry-four-arm-oos-r1-result.json`,
SHA-256 `af1291ad73b8e78665a7181f4403c243b245855b2d1ce24e64ee950d23294ec3`.
All 1,761 saved eligible targets are included, equally weighted, for each K.
The original exclusions remain fixed; no new draws or predictions are read.
ARM_A is `RAW_MAJORITY`, ARM_D is `MIN_OVERLAP`. K10 is primary, K20 secondary.

The model draws six main numbers uniformly without replacement from 1..49,
then one special number uniformly from the remaining 43. For each main set W,
the conditional any-prize numerator is 43 if any ticket has at least three
main hits; otherwise it is the size of the union of non-W numbers on tickets
with exactly two main hits. Divide by 43. This follows the frozen official
prize contract and includes the 2+special prize.

The existing `exact_coverage_fast_evaluator` enumerates main-hit coverage only.
Its unbounded per-ticket cache costs about 26 MB per B649 ticket at >=3, making
full reuse across these thousands of portfolios impractical. It is reused as
the independent >=3/>=4 oracle in small exact tests. Full main enumeration
alone would visit 24,625,499,976 main-set/target pairs (1,761 x 13,983,816), before
scoring A/D at both K. The chosen bounded method therefore samples W and
integrates the special number exactly.

Before viewing any model contrast, freeze:

- Exactly 32,768 independent W samples per target; A/D and both K share each W.
- NumPy PCG64, root seed 649; each target's independent seed is the first
  128 SHA-256 bits of `task_id|649|target_draw`, interpreted big endian.
- Uniform sampler: six IID discrete uniform values, rejecting the entire row
  on any duplicate. No number weighting or historical labels.
- One CPU worker, 900-second cap checked between targets; an incomplete cohort
  gets an unresolved verdict. No seed changes, adaptive stopping or budget top-up.
- Complete-cohort precision: conservative delta error half-width <=0.05 pp.
  Hoeffding 97.5% intervals for each K provide simultaneous >=95% coverage for
  the two full-cohort primary-metric contrasts by the union bound. Positive
  geometry evidence requires that interval's lower endpoint to exceed zero.
- Normal 95% MC intervals are additionally reported from within-target paired
  sample variances, using `SE^2 = sum(s_t^2)/(n*T^2)`. These quantify numerical
  integration error, not between-target variation or future OOS uncertainty.
- Predeclared structural groups: candidate count 20, 21, 22. K20 pool=20 is
  forced selection. Subgroup and >=3/>=4 diagnostics are descriptive.

## Results

All Q values below are Monte Carlo estimates of official-any-prize probability,
with the special number integrated exactly. Differences and intervals use
percentage points. The two **all** rows have simultaneous >=95% conservative
coverage; structural subgroup intervals are descriptive.

| K / frozen group | Targets | Q(incumbent) % | Q(MIN_OVERLAP) % | Delta pp | Paired MC normal 95% CI, pp | Conservative 97.5% interval, pp |
|---|---:|---:|---:|---:|---|---|
| **10 / all, primary** | **1,761** | **22.636488** | **27.040239** | **+4.403751** | **[4.395907, 4.411595]** | **[4.364780, 4.442723]** |
| 10 / pool=20 | 608 | 22.966346 | 27.003691 | +4.037345 | [4.024211, 4.050479] | [3.971020, 4.103670] |
| 10 / pool=21 | 831 | 22.584464 | 27.034670 | +4.450206 | [4.438789, 4.461624] | [4.393474, 4.506938] |
| 10 / pool=22 | 322 | 22.147909 | 27.123619 | +4.975710 | [4.956811, 4.994609] | [4.884572, 5.066848] |
| **20 / all, secondary** | **1,761** | **37.516085** | **38.795137** | **+1.279052** | **[1.276467, 1.281636]** | **[1.240080, 1.318023]** |
| 20 / pool=20, forced | 608 | 38.546125 | 38.546125 | **0 exact** | [0, 0] exact | [0, 0] exact |
| 20 / pool=21 | 831 | 37.088479 | 38.835238 | +1.746759 | [1.742433, 1.751085] | [1.690027, 1.803490] |
| 20 / pool=22 | 322 | 36.674707 | 39.161830 | +2.487123 | [2.478453, 2.495794] | [2.395985, 2.578261] |

The forced-subset **delta** is exact because all 608 unordered A/D ticket sets
are identical, for every possible draw. Its shared absolute Q remains an MC
estimate. All predeclared non-forced structural groups have positive estimated
mean deltas; this does not establish a gain for every individual portfolio or
every possible candidate pool.

Full-cohort conservative half-width is **0.038972 pp**, below the frozen
0.05 pp threshold. The K10/K20 probability differences (unit interval scale)
are respectively **0.04403751247801919** and **0.012790517365074638**.

Main-hit diagnostics, kept separate from the product metric:

- K10 >=3: 14.577658% -> 17.190919%, delta +2.613261 pp,
  paired MC 95% interval [2.604445, 2.622078] pp.
- K20 >=3: 25.275258% -> 26.142333%, delta +0.867075 pp,
  paired MC 95% interval [0.864004, 0.870147] pp.
- K10 >=4: 0.920549% -> 0.986971%, delta +0.066421 pp,
  paired MC 95% interval [0.064006, 0.068837] pp.
- K20 >=4: 1.782438% -> 1.819217%, delta +0.036779 pp,
  paired MC 95% interval [0.035879, 0.037678] pp.

These are descriptive MC diagnostics with no additional simultaneous
inference claim. The frozen historical OOS report separately records
+4.315730 pp for K10 and +1.135718 pp for K20. The model differences have a
similar magnitude, supporting a geometry mechanism for this saved cohort;
they do not statistically decompose the historical outcome or establish a
residual forecasting advantage.

## Computation and verification

Exactly **1,761 x 32,768 = 57,704,448** sampled main sets were generated, each
shared by the two arms at both K. This is 3,522 portfolio instances per K,
7,044 in total; there are 3,522 unique unordered portfolios at K10 and 2,914
at K20. Integrating 43 special-number possibilities does not add MC samples
or actual OOS draws. All eligible targets finished in **16.71 seconds** of
evaluation, within the frozen 900-second cap; no top-up or alternate seed run.
Observed runtime: Python 3.13.8, NumPy 2.5.2, one worker.

- **PASS:** 19 focused tests, final run 0.44 seconds. Frozen prize signatures,
  special-number union (including duplicate union membership), identical
  portfolio zero difference, consistent number relabeling, small exhaustive
  official-evaluator parity, existing >=3/>=4 exact-coverage parity, fixed-seed
  reproduction and legality, paired variance arithmetic, complete input cohort.
- **PASS:** independent Decimal recomputation of every full-cohort mean and
  MC standard error; subgroup-weighted reconstruction; exact input/source
  identity, target/sample counts, and forced-subset equality.
- **PASS:** focused Ruff lint. Initial formatting findings were corrected
  before the model evaluation. No behavior changes after observing contrasts.
- **Falsifiability confirmed:** one in-memory negative control erased the
  special contribution; the union test failed as expected (exit 1), followed
  by the unchanged full focused file passing (exit 0). No source mutation
  remained.
- **NOT RUN:** full suite, historical replay, independent Judge, prospective
  re-evaluation, adoption or publication, as scoped by the brief.

INTENT: code integrates official-prize success for the saved A/D portfolios;
the task expects their fair-model Q difference; the opened brief requires
fixed K, the full frozen cohort, and evidence separate from historical OOS.

The execution used the existing, read-only verified launcher at
`/Users/kelvin/VibeCoding-WorkSpace/.worktrees/skill/FABLE_CANONICAL_EXECUTABLE/fable-method/scripts/task_checkpoint.rb`,
commit `81cf07c5f4e61601053573be34d9189449818dc6`.
`LAUNCHER_STATUS: PRESENT_RUNNABLE`; effect: `LOCAL_ONLY_NO_HIGH_RISK`.
The ordinary skill source checkout lacked `--run`; its registered canonical
executable checkout had the implemented option, verified by source and `--help`.
No launcher changes or direct-execution fallback were used for the evaluation.

Exact evaluation invocation (the same launcher identity reuses its saved capture):

```sh
PYTHONPATH=src:. PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
ruby /Users/kelvin/VibeCoding-WorkSpace/.worktrees/skill/FABLE_CANONICAL_EXECUTABLE/fable-method/scripts/task_checkpoint.rb \
  --run --repo /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis \
  --worktree /Users/kelvin/.codex/worktrees/b649-frozen-min-overlap-probability-r1/MathStatisticalAnalysis \
  --task-id B649_FROZEN_MIN_OVERLAP_SUCCESS_PROBABILITY_R1 --execution-id paired-mc-r1 -- \
  /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/python -B \
  -m lottolab.research.b649_frozen_min_overlap_success_probability \
  --input docs/research/branch2-portfolio-geometry-four-arm-oos-r1-result.json \
  --output docs/research/b649-frozen-min-overlap-success-probability-r1-result.json
```

Run from the explicit worktree above so `PYTHONPATH=src:.` resolves there.
Durable captures and execution records reside under the original stable root:
`/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_FROZEN_MIN_OVERLAP_SUCCESS_PROBABILITY_R1/`.
Execution IDs: `focused-tests-r1`, `negative-control-prize-rule`,
`focused-tests-final`, `paired-mc-r1`. The negative control's exit 1 is intentional.

Evaluator SHA-256:
`bdcfee5edfff7512aa9caecefaa08ad306aaa4d25d32b0f0a197885e574115f5`.
Frozen protocol SHA-256:
`390c4a18ac2dfbe5d18540e61860e572c3a4441ca7fa604c84a5c7622b95e72a`.
The result JSON retains every target's seed and integer first/second moments,
so all reported estimates can be reconstructed without replaying the simulation.

Retained task writes: this report, the result JSON, one research evaluator,
one focused test file, the isolated worktree materialization/registration,
and the four launcher execution/capture pairs. No temporary scratch files.
Frozen tracked files are unchanged. The original worktree's unrelated dirty
files were not edited; this implementation is retained uncommitted in the
isolated frozen-input worktree.

## Interpretation boundary

This estimates the average model Q of these fixed saved portfolios. It does
not estimate a prediction edge, expected payout, jackpot improvement, or future
win-rate uplift. Simulation samples add zero prospective draws. The existing
historical OOS result and `fbed3da5…` prospective protocol/verdict remain separate
and unchanged. No adoption, push, PR, deployment or DB/runtime mutation.
