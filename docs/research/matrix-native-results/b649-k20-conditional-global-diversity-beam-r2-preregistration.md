# B649 K20 Conditional Global Diversity Beam R2 — frozen protocol

## Question and start

Test whether H R1 lost useful interaction-aware repair paths when equal-coverage
partial states were retained only by lowest canonical identity.

Use the durable H R1 start portfolio, count `313239661`, SHA-256
`7ce41ff21d5c0821f1d5dda683e23114086f5024fc6d98d4e574df5306659b1e`, reproduced
from `b649-k20-three-ticket-cycle-full-family-r1-result.json` at commit
`3655b0f4bc43450748b4fc87c641d0acd11a8509` and pinned by H R1. H R1's source
and result reuse commits are `bf8f41d72750f881f5a68188eb7cb3bab7b3c108` and
`3cab702fc65235a9b0fa6b98ba29edfad11899b3`.

Use the exact six position sets from the H R1 result:

- destroy 4: `[12,13,17,19]`, `[0,1,14,19]`, `[1,9,15,16]`
- destroy 5: `[2,3,4,10,11]`, `[1,7,15,16,19]`, `[5,9,10,14,17]`

## Frozen search

- Search class: heuristic conditional beam; no N4, N5, or global K20 optimality
  claim.
- Beam width: 16. Children per expanded state: 8, matching H R1.
- At every retained partial state `S`, freeze `R + S`, exact-score all
  `13,983,816` legal 6-number tickets with the H R1 exact scorer, exclude
  tickets already frozen, and take the 8 greatest conditional marginals;
  equal ticket marginals go to the lexicographically lowest ticket.
- Deduplicate child states as canonical sets of replacement tickets. Check the
  exact scorer identities and canonical recounts fail-closed.
- Primary retention order is higher exact current coverage.
- Within an equal-coverage group that must be cut to fit the beam, greedily
  choose the candidate whose nearest already-retained state is farthest under
  this lexicographic pair:
  1. symmetric-difference cardinality of the two partial replacement-ticket
     sets;
  2. Hamming distance between their residual-coverage signatures, where a
     signature is the set of uncovered 7-number subsets after `R + S`.
- Compute that exact residual-signature distance without sampling. If `C(A)`
  and `C(B)` are canonical official-outcome counts for the two 20-ticket
  portfolios, and `C(A ∪ B)` is the canonical count for their ticket union,
  then the number of differing uncovered 7-subsets is
  `(2*C(A ∪ B) - C(A) - C(B))/7`. Assert the numerator is nonnegative and
  divisible by 7.
- Candidate separation is the lexicographically minimum pair-distance to the
  already-retained states; greedily maximize that minimum. The first state in a
  tied top-coverage group has no prior neighbor, so its distance is `null` and
  it is seeded by the lowest canonical state SHA. Final tie-break is lowest
  SHA-256 of compact canonical JSON for the sorted partial replacement-ticket
  set. Higher-coverage states retained earlier also count as already-retained
  neighbors.
- Record tie groups by distinct exact coverage value. Count tie states dropped
  only when an equal-coverage group straddles the beam cutoff. If a whole
  equal-coverage group fits, retain every state and order that group by
  canonical state SHA for deterministic expansion order.

## Controls and acceptance

- Compatibility control: rerun the original H R1 width-8/8-child algorithm on
  the first destroy-4 set `[12,13,17,19]`; require its count and canonical
  portfolio SHA to match the H R1 per-set result. This control set is also one
  of the six predeclared width-16 sets.
- To determine whether the winning width-16 path survived only because of the
  diversity rule, replay width 16/8 children with H R1's original lowest
  canonical-state-identity tie-break on the winning destroy set. That identity
  is the lexicographically lowest tuple of sorted replacement tickets. Compare
  retained partial-state sets at every depth.
- Required parity mismatch count: zero. Require every main beam state to have
  all legal tickets scored, every retained state's chained coverage to match
  the canonical recount, and the final best canonical recount to pass.
- `BEST_COUNT`, `BEST_DELTA`, `BEST_SHA256`, `BEST_DESTROY_SET`, and
  `BEST_NEW_TICKETS` use H R1's canonical portfolio conventions. Across
  destroy sets, equal final counts are resolved by lowest full-portfolio SHA.
- If `BEST_COUNT` exceeds the start count, report
  `DIVERSITY_BEAM_GAIN_ESTABLISHED: YES`. Otherwise report `NO`.

## Resource and change boundary

Use one CPU worker while unrelated CPU-heavy work is active. Do not write
project memory, touch protected lane 3, alter production, commit, push, open a
PR, or merge. The result is a heuristic research artifact only.
