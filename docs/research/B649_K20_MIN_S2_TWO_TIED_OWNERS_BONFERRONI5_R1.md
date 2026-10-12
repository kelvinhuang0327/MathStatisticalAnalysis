# B649_K20_MIN_S2_TWO_TIED_OWNERS_BONFERRONI5_R1

TASK_STATUS: COMPLETE_SELF_CHECK_ONLY. REMAINING_TASK_MODEL: 最強模型.
The complete Minimum-S2 upper bound decreases from **313398144 to 313397860**.
The remaining owner is `66665555554421100000`; the gap to incumbent 313263888
is **133972**. Both tied owners were installed before recomputing the family.

The immutable input identities are BASE_HEAD
`2cc39e82c3c75c128ee32c0ad7557917277f98d6`, BASE_TREE
`d9b389c00f84d1c44c42b53610bc34cc437fec6b`, and BASE_RESULT_SHA256
`5245210f0236f6d6923586bf818184cf437203857082f8e6677995d1e09404aa`.
The predecessor source bytes and all transitive module provenance match their
committed blobs, and the predecessor result replays exactly.

| Quantity | Owner A `66665555555331000000` | Owner B `66665555555411100000` |
| --- | --- | --- |
| Triple degree sequence | 6^4, 5^7, 3^2, 1, 0^6 | 6^4, 5^7, 4, 1^3, 0^5 |
| R30 cap authority | GROUP_ATTEMPTS[3089] | GROUP_ATTEMPTS[3088] |
| NB replay locator | NB_CERTIFICATES[872] | NB_CERTIFICATES[871] |
| Triangle cap / load-bearing t | 264 | 264 |
| H1..H6 caps | 22,21,21,19,19,8 | 22,21,21,21,18,8 |
| Common-pair sum cap | 808 | 814 |
| N_2T cap | 136 | 136 |
| S5 cap | 7560 | 7602 |
| W / B / A_MAX | 832 / 602 / 200 | 832 / 602 / 200 |
| J | 2358 | 2360 |
| Existing S4 floor at t264 | 286510 | 286510 |
| Original t264 bound | 313398144 | 313398144 |
| New t264 bound | 313282914 | 313282956 |
| Retained t<=263 maximum | 313389376 | 313388988 |
| New complete profile bound | 313389376 | 313388988 |

For each linear triple tau, a vertex v in tau has graph degree 6+d_v and two
neighbours inside tau, so m_tau <= 4+min(d_v). Let H_k count triples all of
whose vertex degrees are at least k. Three high incidences are required per
such triple, giving H_k <= floor(sum_{d_v>=k} d_v / 3). A low vertex with
0<d_v<k has d_v distinct incident triples outside H_k, giving
H_k <= 22-max_{0<d_v<k} d_v. Fewer than three high vertices force H_k=0.
These necessary inequalities give the displayed threshold caps. An independent
integer dynamic program in the tests optimizes the same necessary relaxation.

Since H1=22, threshold summation gives
sum_tau C(m_tau,2) <= 220+5H2+6H3+7H4+8H5+9H6.
For A this is 220+105+126+133+152+72=808; for B it is
220+105+126+147+144+72=814. Every intersecting pair of linear triples has one
common vertex, hence N_2T <= sum_v C(d_v,2)=136 for both profiles.
The inherited exact identity
`S5 = 7*(sum_tau C(m_tau,2) + 2*N_2T)` therefore gives caps 7560 and 7602.
The established double-triple K5 weight remains 28, and its complete local
identity table is replayed by the unchanged predecessor verifier.

At t264, the open-wedge count is 832-3*264=40. With maximum graph degree 12,
the existing Route-B K4 floor is ceil((J-10*40)/4)=490 for either owner;
A_MAX=floor(602/3)=200. Thus the inherited S4 floor is
448*200+679*(490-200)=286510. S3=5171824, and S1-S2+S3=313561864.
The safe fifth-order inequality `Union <= S1-S2+S3-S4+S5_cap` gives the new
cap-term bounds in the table. Each is combined with the existing fourth-order
bound by **taking the minimum**. Overlapping credits are never added.

Each owner retains every one of its 242 lower-t terms, including every column;
only the BOUND column of its t264 term changes. All 243 per-t terms are stored
in the JSON. Lower-term digests are
`5ade386708108df7f20d83950be8fb06ab483c967cb0f700245dc07ff97352a3` (A) and
`100bebca08bf05e5a8b91c75fb961dffa7832ff5bb6d26f5c0c15360cf9e88bf` (B).
All other 4645 resolved rows, the cursor, triangle caps and witness supports
remain unchanged. The family verifier checks the inherited partition by counts
and ID digests: 4647 resolved profiles plus 197 under the cursor, all 4844
admissible profiles, zero uncovered profiles. It independently sorts the full
ledger plus cursor and agrees with the inherited family calculation.

Both recorded owner witnesses, P2, and STS13 pass realization and moment-bound
checks. STS13 retains exact union 313263867 and exact S5=6860. No new realization
or witness was installed. Historical module import orders pass in fresh Python
processes. Source tampering, cap-authority tampering, lower-term/result tampering,
and missing or extra profile coverage are rejected.

Validation observed under Python 3.13.8:

- Focused pytest: **79 passed in 316.39s**, new two-tied-owner tests plus the
  unchanged predecessor three-tied-owner tests; no cache provider or bytecode writes.
- Ruff 0.15.21 check and format check: PASS on the two new Python files.
- Pyright 1.1.411: strict, Python version 3.13, **2 files analyzed, 0 errors,
  0 warnings**. The config uses the task's src and the canonical dependency venv.
- Seventeen new non-equivalent mutations are killed by semantic guards, followed
  by restored green guards: wrong S5 sign, weight 14, copied owner degrees,
  omitted intersecting-pair correction, wrong high-incidence divisor, omitted
  low-vertex constraint, wrong special weight, fourth-order rounding down,
  overlapping credits, weaker bound, dropped lower-t terms, cap term substituted
  for profile maximum, summed profile terms, ignored cap source, ignored witness
  bound, omitted Owner A, and omitted Owner B.
- Result replay: parsed JSON equals recomputation, rendered bytes equal the saved
  bytes, and immutable-result overwrite is rejected.

The first Ruff pass found one long test line and the formatter repaired it.
The first temporary Pyright config used absolute include paths, which Pyright
ignored; that invocation is not counted as validation. Relative include paths
were then used and the filesAnalyzed count was checked explicitly. A final
comment correction describes the inherited owner realizations accurately;
it changes no executable test code.

Machine result: `matrix-native-results/b649-k20-min-s2-two-tied-owners-bonferroni5-r1-result.json`.
RESULT_SHA256: `1998f36a92cea15ea4f7413a21a48dd1cad3a90aa7f5c840110ede30034a97ec`.
SOURCE_SHA256: `5a57c5d1e12d5d44d9853c8c28f7906a2118ab358190537d4642922941a931e5`.

The task writes exactly the new verifier, its focused test file, the machine
result, and this report in the explicitly authorized isolated worktree. Worktree
and branch creation update ordinary Git metadata; temporary Pyright configs are
created in OS temporary directories and removed. Tests use in-memory mutation
seams, restore each seam, and leave no source mutation. The canonical checkout's
pre-existing untracked files remain untouched. No donor checkout, Fiber,
production source, solver, R30 census, portfolio search, official-outcome
enumeration, push, PR, merge, or worktree removal is performed. The worktree is
retained, and task HEAD/tree and the one local commit are identified in the
Worker's final handoff.
