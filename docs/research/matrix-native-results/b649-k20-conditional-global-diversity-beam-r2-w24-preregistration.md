# B649_K20_CONDITIONAL_GLOBAL_DIVERSITY_BEAM_R2 / W24_SIGNATURE_FIRST: preregistration

Status: FROZEN before any scientific execution. This file is committed, and the pilot refuses to
run unless it is tracked, clean and contains the rule text below byte for byte. The rule text hash
is `8c5e869d6fa0f1c7e004007dc1819bb5b1c8c9e1bffac1433b5ee19eb76059f3`.

## Question

Does preventing equal-coverage partial repair states from being collapsed solely by the
lowest-identity tie-break (R1, commit `bf8f41d7`) find a K20 portfolio above the latest stable
count 313,239,661 (portfolio SHA-256
`7ce41ff21d5c0821f1d5dda683e23114086f5024fc6d98d4e574df5306659b1e`)?

## Relationship to the earlier width-16 R2 result

A result for the same task name already exists (`8073551372c9d6c8b83b9434bf8e4e52f0d46e8e`, beam width 16,
replacement-ticket-set distance ranked before the residual-signature distance, no strict gain).
This variant is the Owner's width-24, signature-first specification. It is a separate source
module, preregistration and result file; nothing of the earlier result is reused or overwritten.

## Frozen rule

```text
B649_K20_CONDITIONAL_GLOBAL_DIVERSITY_BEAM_R2 / W24_SIGNATURE_FIRST: frozen retention rule

1. Candidate generation is the R1 rule, unchanged. Every retained partial replacement set S
   conditions on R + S, exact-scores all 13,983,816 legal tickets, and its 8 largest conditional
   marginals (ties to the lexicographically lowest ticket; tickets already in R + S are illegal)
   become children. Children are deduplicated as canonical replacement-ticket sets and the first
   expansion that reaches a set owns its provenance.
2. BEAM_WIDTH is 24. The PRIMARY RANK is the exact coverage of R + S, higher first.
3. A coverage group whose states all fit in the remaining beam slots is retained whole, ordered by
   lowest canonical state SHA-256. Only the one group that straddles the cutoff (more states than
   remaining slots) is a diversity group. A strictly lower coverage group is never retained
   instead of a higher one.
4. A diversity group of g tied states retaining s < g of them is not cut by lowest identity.
   (A) retain the tied state with the lowest canonical state SHA-256 first.
   (B) repeat until s tied states are retained: retain the not-yet-retained tied state whose
       minimum distance to the already-retained states OF THE SAME TIE GROUP is largest.
   (C) The primary distance is the residual-coverage signature symmetric difference
       |U(R+S1) xor U(R+S2)|, where U(R+S) is the set of 7-subsets of 1..49 not won by R+S.
   (D) The secondary distance, compared only when the primary minimum ties, is the
       replacement-ticket-set symmetric difference |S1 xor S2|.
   (E) Any remaining tie goes to the lowest canonical state SHA-256.
   Canonical state SHA-256 is the SHA-256 of the compact JSON (separators "," and ":") of the
   state's replacement tickets, each sorted ascending and the tickets sorted ascending.
5. The selection order inside a diversity group is the beam order of its states.
6. Depth is 4 for a destroy-4 set and 5 for a destroy-5 set. The six destroy sets are the R1 sets.
7. CONTROL: before any scientific beam runs, the first R1 destroy-4 set is rerun at BEAM_WIDTH 8
   with R1's lowest-identity retention (coverage descending, then ascending sorted ticket tuple);
   every retained state of every level and the terminal best must equal R1's recorded result.
8. The search is heuristic. No complete N4 optimum, complete N5 optimum or global K20 optimum is
   claimed.
```

## Reported statistics (definitions frozen here)

- `TIE_GROUPS_TOTAL`, `MAX_TIE_GROUP_SIZE`: groups of two or more unique candidate states of equal
  exact coverage, over every level of the six scientific beams.
- `TIED_STATES_CONSIDERED`, `TIED_STATES_RETAINED_BY_DIVERSITY`: the states of the tie groups that
  straddled a retention cutoff, and how many of them the diversity rule retained.
- `AVERAGE_COVERAGE_SIGNATURE_DISTANCE`, `AVERAGE_TICKET_SET_DISTANCE`: mean, over every state
  retained by diversity after the first of its group, of its minimum distance to the
  already-retained states of the same group at the moment of its selection.
- `DID_DIVERSITY_SAVE_A_STATE_R1_WOULD_DROP`: YES when any diversity-retained state is absent from
  the first `s` states of the same candidates in R1's order (coverage descending, then ascending
  sorted ticket tuple).
- `DID_BEST_PATH_DIFFER_FROM_R1`: YES when the winning destroy set differs from R1's winner or the
  winning provenance chain differs from R1's recorded winning chain.
- `SCIENTIFIC_RESULT`: `IMPROVED` only when `BEST_COUNT > 313239661` and the canonical recount of
  the best and of every best-count tie passes; otherwise `NO_IMPROVEMENT`.

## Exactness and parity

The signature distance is computed on exact bitmaps over the 7-subsets that `R` does not win and is
cross-checked against the canonical evaluator through
`|A xor B| = 2 |won(R + S_A + S_B)| - |won(R + S_A)| - |won(R + S_B)|` on toy lotteries (all
selected pairs) and on the real 49/6 space (sampled pairs). The retention code is compared with an
independent reference written from this rule on toy lotteries, and its `LOWEST_IDENTITY` mode is
compared with R1's own `run_beam`. R1's scorer and beam parity (at least 100 real conditional
marginal comparisons) runs unchanged. `PARITY_MISMATCHES` must be 0 before any scientific beam is
scored.

## Not claimed

Complete N4 optimum, complete N5 optimum, global K20 optimum, optimality of any beam state, and any
statement about protected Lane 3.
