# T540 anytime-valid inference ledger R1

This document records the preregistered statistical contract and local
implementation for the frozen T539 prospective experiment. The implementation
and its conformance tests use synthetic fixtures only. No real prospective
outcome, database, network draw refresh, or post-freeze result was read while
building or verifying this artifact.

## Sealed authority

| Field | Frozen value |
|---|---|
| Freeze boundary | `115000186` |
| Freeze SHA-256 | `f1b299ace019393440bce8bd2768f6618b2362d220d81b4cc14151a5080908a8` |
| Rule fingerprint | `eb4eb89082cd782041c240e80858efd8453c3bbf08edec3b76e98e2e8051f446` |
| Primary metric | `OFFICIAL_ANY_PRIZE_TARGET_RATE` |
| Statistical-contract fingerprint | `57d6b1109d1b00b2af3cf42e1fa323bf616963abe1f959943b1e4b3aef538492` |
| Contract artifact byte SHA-256 | `74e295c2ddbbb582994cc523546da3aad08747682440f10cacbf8ac5934e83a5` |
| Contract artifact size | `22827` bytes |

The machine-readable authority is
`docs/research/matrix-native-results/t540-anytime-valid-inference-protocol-r1.json`.
It was built twice from the same implementation. Both builds produced the
same bytes and the same artifact SHA-256 shown above. Its statistical-contract
fingerprint seals the compact canonical contract core; its artifact SHA-256
seals the complete sorted, indented JSON file including that fingerprint.

The contract contains no real result record. Its integrity section fixes:

```text
REAL_FUTURE_OUTCOME_ACCESS = NO
PROSPECTIVE_OBSERVATIONS_AT_CONTRACT_FREEZE = 0
EMBEDDED_REAL_RESULTS = []
DATABASE_ACCESS = NO
NETWORK_DRAW_REFRESH = NOT RUN
SYNTHETIC_FIXTURE_POLICY = TESTS ONLY
```

## Frozen 60-stream surface

The ledger contains exactly 30 K x window experiments and two paired streams
per experiment.

- K: `1,2,3,4,5,7,10,11,12,25`
- Windows: `W50,W300,W750`
- Arm A: `ORIGINAL_ROLLING`
- Arm B: `CALLABLE_FAMILY_DEDUP_ROLLING`
- Arm C: `CALLABLE_FAMILY_DEDUP_FROZEN_BASELINE`
- Comparisons: `B_MINUS_A`, `B_MINUS_C`
- Stream identity: `T539:K{K}:{WINDOW}:{COMPARISON}`

The order is K-major, then `W50,W300,W750`, then
`B_MINUS_A,B_MINUS_C`. The first identity is
`T539:K1:W50:B_MINUS_A`; the last is
`T539:K25:W750:B_MINUS_C`. The generated contract enumerates all 60
identities explicitly.

## Whole-target eligibility

One official target is one observation unit. A valid source must bind to the
frozen SHA and rule fingerprint, carry the confirmed pretarget-seal status,
declare `VALID_PROSPECTIVE_OBSERVATION`, and contain all 30 experiments with
all three exact arms. The tool validates the complete 90-arm source before it
derives or appends any paired record.

No partial cell is ingested. A missing, duplicate, or mismatched experiment or
arm rejects the whole attempted append before state mutation. Technical
exclusions such as `MISSED_PRETARGET_SEAL` are retained separately and add
zero to every confirmatory denominator. An accepted target can never later be
dropped based on its arm results.

Each accepted target preserves:

- its exact chronological target identity;
- the T539 result-content hash and canonical source hash;
- pretarget snapshot, input-authority, and official-outcome identity hashes;
- the raw source arm-record count (`90`);
- all 60 replay-complete `(Y_B,Y_X,D)` paired records.

The persisted state never stores floating counts or an unsealed substitute for
the source identity.

## Exact paired accounting

For each stream and accepted target:

```text
D = Y_B - Y_X
Y_B,Y_X in {0,1}
D in {-1,0,1}
```

The ledger maintains exact integers `n11,n10,n01,n00,N` and the exact current
fraction

```text
delta_hat = (n10 - n01) / N.
```

At `N=0`, `delta_hat` is absent rather than assigned a floating or artificial
value.

## Frozen e-process

At `delta=0`, each prefix uses

```text
E_u(0) = integral_0^1 (1+gamma)^n10 (1-gamma)^n01 dgamma,
```

with `E_0=1`. For `-1 < delta <= 1`, it uses

```text
E_u(delta)
  = integral_0^1 product_i [1 + gamma*(D_i-delta)/(1+delta)] dgamma,
gamma ~ Uniform(0,1).
```

There is no adaptive stake. The physical lambda support is
`[0,1/(1+delta)]` with uniform density `1+delta`.

The authoritative evaluator is the preregistered positive-term expansion. For
prefix counts `p=n10`, `z=n11+n00`, and `r=n01`:

```text
A_u,k = sum_{j=max(0,k-z)}^{min(k,p)} C(p,j) C(z,k-j) 2^j

E_u(delta)
  = 1/(u+1)
    * sum_{k=0}^{p+z} [A_u,k / C(u,k) * (1+delta)^(-k)].
```

The implementation evaluates these positive terms with arbitrary-integer
`Fraction` arithmetic. Generic numerical quadrature, float residuals,
overflow clipping, underflow saturation, and floating threshold comparisons
are absent.

For every `delta`, the retained statistic is

```text
M_t(delta) = max_{0<=u<=t} E_u(delta).
```

Prefix zero is retained forever, so the running maximum cannot reset.

Boundary behavior is exact:

- `E_0(-1)=1`;
- for `t>=1`, `E_t(-1)=1/(t+1)` only when every `D_i=-1`, otherwise it is
  positive infinity;
- `M_t(1)=1` for every path.

## Multiplicity and evidence tiers

The family alpha is `1/20`; the per-stream alpha is `1/1200`. A confirmatory
stream crossing is

```text
M_t(0) >= 1200.
```

Equality crosses. The adjusted anytime p-value is stored as the exact fraction

```text
min(1, 60/M_t(0)).
```

For one named K/window, `SUPPORTS_FURTHER_STUDY` requires both comparison
streams to have `M_t(0)>=600` and both current `delta_hat>0`. This lower tier
does not establish confirmatory predictive advantage and does not support a
95% simultaneous-coverage claim.

`PREDICTIVE_ADVANTAGE_ESTABLISHED_AT_K_AND_WINDOW` requires both comparison
streams to have `M_t(0)>=1200` and both current `delta_hat>0`. Reports do not
rank or call any cell "best". Whole-surface predictive advantage requires all
60 streams to cross and all 60 current paired deltas to be positive.

## Exact confidence-sequence inversion

The rejected set is

```text
R_t = {delta : M_t(delta) >= 1200}.
```

If `R_t` is empty, `L_t=-1`. Otherwise

```text
L_t = sup {delta : M_t(delta) >= 1200},
```

and the lower confidence set is `(L_t,1]`. Equality is rejected.

The implementation performs exactly 49 bisections on `[-1,1]`. Every midpoint
and threshold comparison is an exact rational operation. The final nonempty
bracket has certified width `2^-48`; the persisted conservative scalar is the
lower bracket endpoint. Both exact bracket endpoints are retained.

## Persistence and replay

State serialization is deterministic UTF-8 JSON with sorted keys, two-space
indentation, and exactly one trailing newline. Each state binds the schema,
freeze SHA, rule fingerprint, statistical-contract fingerprint, and contract
artifact SHA.

Loading a state replays all 60 streams from the accepted target records and
recomputes paired counts, `E_t(0)`, `M_t(0)`, the 49-step confidence bracket,
cell tiers, reporting flags, and stopping state. The rebuilt canonical bytes
must equal the persisted bytes. A mismatch fails closed.

An exact retry is `EXACT_IDEMPOTENT_NO_OP`. A different canonical source for
an already processed target is `CONFLICT`. New targets must be strictly
chronological. Writes use same-directory temporary bytes, expected-before
identity checks, atomic replacement, and readback verification.

`init` is byte-idempotent only for the unique empty state. Once any accepted
target or technical exclusion exists, it raises `NO_RESET_AFTER_EVIDENCE`.
There is no reset command.

## Reporting and stopping

The common denominator is the accepted whole-target count shared by all 60
streams. Formal cadence flags occur at `N=50,100,150,...`; terminal status also
forces a formal report. Every report contains all 60 stream records and all 30
cell statuses. No best-cell-only report exists.

There is no futility stop and no cell-specific winner stop. The only efficacy
stop is:

```text
all 60 M_t(0) >= 1200
AND
all 60 current delta_hat > 0.
```

Administrative termination can be represented with a reason and forces a
terminal report, but it preserves all evidence and cannot reset the state.
After any terminal state, new ingestion is rejected. A future change to freeze,
selector, eligibility, or contract semantics cannot be loaded as the same
experiment because the contract bindings fail closed; a successor must start
as a distinct experiment.

## Command surface

```text
python tools/run_t540_anytime_valid_inference_ledger.py build-contract \
  --output-json docs/research/matrix-native-results/t540-anytime-valid-inference-protocol-r1.json

python tools/run_t540_anytime_valid_inference_ledger.py init \
  --state-json <ledger-state.json>

python tools/run_t540_anytime_valid_inference_ledger.py ingest \
  --state-json <ledger-state.json> \
  --target-result-json <sealed-t539-target-score.json>

python tools/run_t540_anytime_valid_inference_ledger.py report \
  --state-json <ledger-state.json> \
  --output-json <all-60-stream-report.json>

python tools/run_t540_anytime_valid_inference_ledger.py terminate-administratively \
  --state-json <ledger-state.json> \
  --reason <reason>
```

The implementation does not discover or fetch a target result. `ingest` only
consumes the explicitly supplied sealed T539 score file.

## Synthetic conformance

The focused test module covers the required 60-stream identity, whole-target
validation, exact counts, frozen and shifted e-process parity, both delta
boundaries, running-max retention, thresholds, adjusted p-values, exact
confidence inversion, duplicates, conflicts, replay, serialization, no-reset,
cadence, and full-surface stopping.

The supplied exact reference behavior is preserved:

| Synthetic path | Exact result |
|---|---|
| Empty | `L=-1` |
| All `-1` | `M=1`, `L=-1` |
| Single tie | `L=-2398/2399` |
| Single `+1` | `L=-2397/2399` |
| `(+1,-1)` | running-max `L=-2397/2399` |
| `(-1,+1)` | `L=-3598/3599` |
| 13 consecutive `+1` | `M_13(0)=16383/14<1200` |
| 14 consecutive `+1` | `M_14(0)=32767/15>1200` |

No test fixture includes winning numbers or an official-outcome payload. Test
target identities are synthetic values beginning at `900000000`.
