# Historical Replay Meta-Feature Interaction Discovery R2

FINAL_CLASSIFICATION: **DISCOVERY_ONLY_CANDIDATE_FROZEN**

the highest pooled-ranked interaction satisfying the separately frozen robustness gate has strictly positive M2 and average-match deltas versus the pooled first-ticket baseline in each trailing 50/300/750 discovery window; no confirmation claim is made

This is discovery-only hypothesis generation. The consumed R1 confirmation set was excluded at the SQL boundary; no confirmation or strategy-promotion claim is made.

## Required output

FEATURE_COUNT: **18**
INTERACTION_CANDIDATE_COUNT: **612**
COMPLETED_COUNT: **612**
FAILED_COUNT: **0**
PRUNED_COUNT: **0**
ROBUST_CANDIDATE_COUNT: **63**

BEST_DISCOVERY_INTERACTION: `hrmfi_r2__m2_stability_gap_w010_w050__min__recent_m2_rate_w010__max`

Exact selector: m2_stability_gap_w010_w050 MIN primary; recent_m2_rate_w010 MAX resolves equal primary values; final ties use LEXICOGRAPHIC_STRATEGY_ID_ASC; evaluate CANONICAL_FIRST_TICKET_ONE_TICKET_EXPOSURE

RAW_BEST_POOLED_DISCOVERY_INTERACTION: `hrmfi_r2__m2_rank_improvement_w010_w050__min__recent_m2_rate_w300__min`

Raw pooled winner result: support=750; M2+=64/375 (0.170667); pool=413/2750; delta_pool=169/8250; avg_match=583/750; avg_match_delta_pool=149/4125

Acceptance rule: keep the pooled ranking unchanged and freeze the first ranked interaction that passes the separately preregistered temporal gate.

DISCOVERY_RESULT: support=750; M2+=21/125 (0.168000); pool=413/2750; delta_pool=49/2750; avg_match=587/750; avg_match_delta_pool=57/1375

TEMPORAL_ROBUSTNESS:

- 50 draws: support=50; M2+=11/50 (0.220000); pool=117/550; delta_pool=2/275; avg_match=26/25; avg_match_delta_pool=32/275
- 300 draws: support=300; M2+=29/150 (0.193333); pool=134/825; delta_pool=17/550; avg_match=121/150; avg_match_delta_pool=49/825
- 750 draws: support=750; M2+=21/125 (0.168000); pool=413/2750; delta_pool=49/2750; avg_match=587/750; avg_match_delta_pool=57/1375
- Frozen gate passed: **TRUE**
- Gate: M2 and average-match deltas versus the pooled first-ticket baseline must both be strictly positive in each trailing 50/300/750 discovery window.
- Robustness did not alter pooled discovery scores or rank order; it is the predeclared acceptance gate applied after all 612 candidates complete.

DELTA_VS_BEST_R1_SINGLE_FEATURE_RULE:

- R1 rule: `hrmfms_r1__recent_avg_match_w010__argmin`
- R1 pooled discovery M2 delta vs pool: `1/66`
- R2 pooled discovery M2 delta vs pool: `49/2750`
- Difference: `1/375`
- R1 pooled discovery average-match delta vs pool: `53/1650`
- R2 pooled discovery average-match delta vs pool: `57/1375`
- Difference: `7/750`

FUTURE_CONFIRMATION_STATUS: **REQUIRES_FRESH_UNSEEN_DATA**

PROMOTION_DECISION: **NOT_AUTHORIZED**

## Corpus and exclusion evidence

- R1 result SHA-256: `383680a0d07f97702e22407f8a068034297ee64e45044688e7b40b8bbb314aea`
- R1 discovery-authority projection SHA-256: `fc2c7f04d207e8d62bb0603579b4fe16e825e79005631993bf35c8ec49222192`
- Database SHA-256: `c597d7273648d2419e348b203b5a6da99b0f275a0236bab1eb8ce1b0614fe578`
- Source run: `run-reference-baseline-big-lotto-1c1287519185c97efce58349bd116875765c12adf91d1e56d6c5ef5e7ec79a8b`
- Loaded draws: 1198 (448 warmup + 750 discovery)
- Loaded confirmation observations: 0
- Discovery first target: 2017-03-10 / 106000024
- Discovery last target: 2023-11-21 / 112000105
- Bounded targets / tickets / results: 13290 / 19320 / 19320
- Required nulls / invalid JSON / recomputed-hit mismatches / causal-date violations / extra result versions: 0 / 0 / 0 / 0 / 0
- Duplicate native ticket positions retained: 40

## Frozen universe and determinism

- Candidate universe SHA-256: `f26fec349d9c992a07745238bd33aa61f064b5f217e4aab5c1114e438cb87f42`
- Preregistration SHA-256: `99cccb19737f1319f8b38890a68fc481efefbfd9197c09f785b3ee8f369346b4`
- Canonical result / determinism SHA-256: `763e20846e84fa45883db5ad7dd1b11f044c2c1a4fa8a683bda613c7fae875ed`
- Candidate construction: C(18,2) unordered feature pairs x four MAX/MIN direction combinations.
- A is primary; B only resolves equal A; strategy ID is the final tie-break.
- No learned threshold, continuous tuning, optimizer dependency, or pruning.

## Top pooled discovery candidates

### 1. `hrmfi_r2__m2_rank_improvement_w010_w050__min__recent_m2_rate_w300__min`

- Exact interaction: m2_rank_improvement_w010_w050 MIN primary; recent_m2_rate_w300 MIN resolves equal primary values; final ties use LEXICOGRAPHIC_STRATEGY_ID_ASC; evaluate CANONICAL_FIRST_TICKET_ONE_TICKET_EXPOSURE
- Pooled discovery: support=750; M2+=64/375 (0.170667); pool=413/2750; delta_pool=169/8250; avg_match=583/750; avg_match_delta_pool=149/4125
- Frozen trailing discovery windows:

  - 50 draws: support=50; M2+=3/25 (0.120000); pool=117/550; delta_pool=-51/550; avg_match=47/50; avg_match_delta_pool=9/550
  - 300 draws: support=300; M2+=1/6 (0.166667); pool=134/825; delta_pool=7/1650; avg_match=47/60; avg_match_delta_pool=119/3300
  - 750 draws: support=750; M2+=64/375 (0.170667); pool=413/2750; delta_pool=169/8250; avg_match=583/750; avg_match_delta_pool=149/4125

- Selected-strategy support: bet2_fourier_expansion_biglotto=88, biglotto_deviation_2bet=140, biglotto_echo_aware_3bet=112, biglotto_triple_strike=47, cold_complement_biglotto=127, fourier30_markov30_biglotto=115, markov_2bet_biglotto=121

### 2. `hrmfi_r2__m2_rank_improvement_w010_w050__min__recent_avg_match_w300__min`

- Exact interaction: m2_rank_improvement_w010_w050 MIN primary; recent_avg_match_w300 MIN resolves equal primary values; final ties use LEXICOGRAPHIC_STRATEGY_ID_ASC; evaluate CANONICAL_FIRST_TICKET_ONE_TICKET_EXPOSURE
- Pooled discovery: support=750; M2+=127/750 (0.169333); pool=413/2750; delta_pool=79/4125; avg_match=58/75; avg_match_delta_pool=53/1650
- Frozen trailing discovery windows:

  - 50 draws: support=50; M2+=7/50 (0.140000); pool=117/550; delta_pool=-4/55; avg_match=9/10; avg_match_delta_pool=-13/550
  - 300 draws: support=300; M2+=1/6 (0.166667); pool=134/825; delta_pool=7/1650; avg_match=39/50; avg_match_delta_pool=9/275
  - 750 draws: support=750; M2+=127/750 (0.169333); pool=413/2750; delta_pool=79/4125; avg_match=58/75; avg_match_delta_pool=53/1650

- Selected-strategy support: bet2_fourier_expansion_biglotto=76, biglotto_deviation_2bet=120, biglotto_echo_aware_3bet=111, biglotto_triple_strike=51, cold_complement_biglotto=139, fourier30_markov30_biglotto=130, markov_2bet_biglotto=123

### 3. `hrmfi_r2__m2_momentum_w010_prev010__min__m2_stability_gap_w050_w300__max`

- Exact interaction: m2_momentum_w010_prev010 MIN primary; m2_stability_gap_w050_w300 MAX resolves equal primary values; final ties use LEXICOGRAPHIC_STRATEGY_ID_ASC; evaluate CANONICAL_FIRST_TICKET_ONE_TICKET_EXPOSURE
- Pooled discovery: support=750; M2+=21/125 (0.168000); pool=413/2750; delta_pool=49/2750; avg_match=98/125; avg_match_delta_pool=353/8250
- Frozen trailing discovery windows:

  - 50 draws: support=50; M2+=9/50 (0.180000); pool=117/550; delta_pool=-9/275; avg_match=21/25; avg_match_delta_pool=-23/275
  - 300 draws: support=300; M2+=13/75 (0.173333); pool=134/825; delta_pool=3/275; avg_match=229/300; avg_match_delta_pool=53/3300
  - 750 draws: support=750; M2+=21/125 (0.168000); pool=413/2750; delta_pool=49/2750; avg_match=98/125; avg_match_delta_pool=353/8250

- Selected-strategy support: bet2_fourier_expansion_biglotto=56, biglotto_deviation_2bet=143, biglotto_echo_aware_3bet=120, biglotto_triple_strike=48, cold_complement_biglotto=157, fourier30_markov30_biglotto=110, markov_2bet_biglotto=116

### 4. `hrmfi_r2__m2_stability_gap_w010_w050__min__recent_m2_rate_w010__max`

- Exact interaction: m2_stability_gap_w010_w050 MIN primary; recent_m2_rate_w010 MAX resolves equal primary values; final ties use LEXICOGRAPHIC_STRATEGY_ID_ASC; evaluate CANONICAL_FIRST_TICKET_ONE_TICKET_EXPOSURE
- Pooled discovery: support=750; M2+=21/125 (0.168000); pool=413/2750; delta_pool=49/2750; avg_match=587/750; avg_match_delta_pool=57/1375
- Frozen trailing discovery windows:

  - 50 draws: support=50; M2+=11/50 (0.220000); pool=117/550; delta_pool=2/275; avg_match=26/25; avg_match_delta_pool=32/275
  - 300 draws: support=300; M2+=29/150 (0.193333); pool=134/825; delta_pool=17/550; avg_match=121/150; avg_match_delta_pool=49/825
  - 750 draws: support=750; M2+=21/125 (0.168000); pool=413/2750; delta_pool=49/2750; avg_match=587/750; avg_match_delta_pool=57/1375

- Selected-strategy support: bet2_fourier_expansion_biglotto=182, biglotto_deviation_2bet=142, biglotto_echo_aware_3bet=88, biglotto_triple_strike=37, cold_complement_biglotto=117, fourier30_markov30_biglotto=105, markov_2bet_biglotto=79

### 5. `hrmfi_r2__cross_strategy_jaccard_mean__min__recent_avg_match_w300__min`

- Exact interaction: cross_strategy_jaccard_mean MIN primary; recent_avg_match_w300 MIN resolves equal primary values; final ties use LEXICOGRAPHIC_STRATEGY_ID_ASC; evaluate CANONICAL_FIRST_TICKET_ONE_TICKET_EXPOSURE
- Pooled discovery: support=750; M2+=21/125 (0.168000); pool=413/2750; delta_pool=49/2750; avg_match=23/30; avg_match_delta_pool=7/275
- Frozen trailing discovery windows:

  - 50 draws: support=50; M2+=6/25 (0.240000); pool=117/550; delta_pool=3/110; avg_match=47/50; avg_match_delta_pool=9/550
  - 300 draws: support=300; M2+=11/60 (0.183333); pool=134/825; delta_pool=23/1100; avg_match=39/50; avg_match_delta_pool=9/275
  - 750 draws: support=750; M2+=21/125 (0.168000); pool=413/2750; delta_pool=49/2750; avg_match=23/30; avg_match_delta_pool=7/275

- Selected-strategy support: bet2_fourier_expansion_biglotto=5, biglotto_deviation_2bet=156, biglotto_echo_aware_3bet=370, cold_complement_biglotto=4, fourier30_markov30_biglotto=187, markov_2bet_biglotto=28

### 6. `hrmfi_r2__cross_strategy_jaccard_mean__min__m2_stability_gap_w010_w050__min`

- Exact interaction: cross_strategy_jaccard_mean MIN primary; m2_stability_gap_w010_w050 MIN resolves equal primary values; final ties use LEXICOGRAPHIC_STRATEGY_ID_ASC; evaluate CANONICAL_FIRST_TICKET_ONE_TICKET_EXPOSURE
- Pooled discovery: support=750; M2+=21/125 (0.168000); pool=413/2750; delta_pool=49/2750; avg_match=286/375; avg_match_delta_pool=59/2750
- Frozen trailing discovery windows:

  - 50 draws: support=50; M2+=6/25 (0.240000); pool=117/550; delta_pool=3/110; avg_match=23/25; avg_match_delta_pool=-1/275
  - 300 draws: support=300; M2+=14/75 (0.186667); pool=134/825; delta_pool=4/165; avg_match=58/75; avg_match_delta_pool=43/1650
  - 750 draws: support=750; M2+=21/125 (0.168000); pool=413/2750; delta_pool=49/2750; avg_match=286/375; avg_match_delta_pool=59/2750

- Selected-strategy support: bet2_fourier_expansion_biglotto=5, biglotto_deviation_2bet=156, biglotto_echo_aware_3bet=380, cold_complement_biglotto=3, fourier30_markov30_biglotto=177, markov_2bet_biglotto=29

### 7. `hrmfi_r2__m2_rank_improvement_w010_w050__min__m2_stability_gap_w010_w050__min`

- Exact interaction: m2_rank_improvement_w010_w050 MIN primary; m2_stability_gap_w010_w050 MIN resolves equal primary values; final ties use LEXICOGRAPHIC_STRATEGY_ID_ASC; evaluate CANONICAL_FIRST_TICKET_ONE_TICKET_EXPOSURE
- Pooled discovery: support=750; M2+=21/125 (0.168000); pool=413/2750; delta_pool=49/2750; avg_match=286/375; avg_match_delta_pool=59/2750
- Frozen trailing discovery windows:

  - 50 draws: support=50; M2+=7/50 (0.140000); pool=117/550; delta_pool=-4/55; avg_match=21/25; avg_match_delta_pool=-23/275
  - 300 draws: support=300; M2+=13/75 (0.173333); pool=134/825; delta_pool=3/275; avg_match=19/25; avg_match_delta_pool=7/550
  - 750 draws: support=750; M2+=21/125 (0.168000); pool=413/2750; delta_pool=49/2750; avg_match=286/375; avg_match_delta_pool=59/2750

- Selected-strategy support: bet2_fourier_expansion_biglotto=107, biglotto_deviation_2bet=136, biglotto_echo_aware_3bet=135, biglotto_triple_strike=14, cold_complement_biglotto=130, fourier30_markov30_biglotto=104, markov_2bet_biglotto=124

### 8. `hrmfi_r2__m2_rank_improvement_w010_w050__min__recent_avg_match_w050__min`

- Exact interaction: m2_rank_improvement_w010_w050 MIN primary; recent_avg_match_w050 MIN resolves equal primary values; final ties use LEXICOGRAPHIC_STRATEGY_ID_ASC; evaluate CANONICAL_FIRST_TICKET_ONE_TICKET_EXPOSURE
- Pooled discovery: support=750; M2+=21/125 (0.168000); pool=413/2750; delta_pool=49/2750; avg_match=286/375; avg_match_delta_pool=59/2750
- Frozen trailing discovery windows:

  - 50 draws: support=50; M2+=7/50 (0.140000); pool=117/550; delta_pool=-4/55; avg_match=22/25; avg_match_delta_pool=-12/275
  - 300 draws: support=300; M2+=1/6 (0.166667); pool=134/825; delta_pool=7/1650; avg_match=77/100; avg_match_delta_pool=1/44
  - 750 draws: support=750; M2+=21/125 (0.168000); pool=413/2750; delta_pool=49/2750; avg_match=286/375; avg_match_delta_pool=59/2750

- Selected-strategy support: bet2_fourier_expansion_biglotto=80, biglotto_deviation_2bet=121, biglotto_echo_aware_3bet=120, biglotto_triple_strike=48, cold_complement_biglotto=134, fourier30_markov30_biglotto=115, markov_2bet_biglotto=132

### 9. `hrmfi_r2__cross_strategy_jaccard_mean__min__recent_avg_match_w050__min`

- Exact interaction: cross_strategy_jaccard_mean MIN primary; recent_avg_match_w050 MIN resolves equal primary values; final ties use LEXICOGRAPHIC_STRATEGY_ID_ASC; evaluate CANONICAL_FIRST_TICKET_ONE_TICKET_EXPOSURE
- Pooled discovery: support=750; M2+=21/125 (0.168000); pool=413/2750; delta_pool=49/2750; avg_match=571/750; avg_match_delta_pool=83/4125
- Frozen trailing discovery windows:

  - 50 draws: support=50; M2+=6/25 (0.240000); pool=117/550; delta_pool=3/110; avg_match=23/25; avg_match_delta_pool=-1/275
  - 300 draws: support=300; M2+=14/75 (0.186667); pool=134/825; delta_pool=4/165; avg_match=233/300; avg_match_delta_pool=97/3300
  - 750 draws: support=750; M2+=21/125 (0.168000); pool=413/2750; delta_pool=49/2750; avg_match=571/750; avg_match_delta_pool=83/4125

- Selected-strategy support: bet2_fourier_expansion_biglotto=5, biglotto_deviation_2bet=155, biglotto_echo_aware_3bet=377, cold_complement_biglotto=4, fourier30_markov30_biglotto=181, markov_2bet_biglotto=28

### 10. `hrmfi_r2__cross_strategy_jaccard_mean__min__recent_m2_rate_w050__min`

- Exact interaction: cross_strategy_jaccard_mean MIN primary; recent_m2_rate_w050 MIN resolves equal primary values; final ties use LEXICOGRAPHIC_STRATEGY_ID_ASC; evaluate CANONICAL_FIRST_TICKET_ONE_TICKET_EXPOSURE
- Pooled discovery: support=750; M2+=21/125 (0.168000); pool=413/2750; delta_pool=49/2750; avg_match=19/25; avg_match_delta_pool=31/1650
- Frozen trailing discovery windows:

  - 50 draws: support=50; M2+=6/25 (0.240000); pool=117/550; delta_pool=3/110; avg_match=23/25; avg_match_delta_pool=-1/275
  - 300 draws: support=300; M2+=14/75 (0.186667); pool=134/825; delta_pool=4/165; avg_match=58/75; avg_match_delta_pool=43/1650
  - 750 draws: support=750; M2+=21/125 (0.168000); pool=413/2750; delta_pool=49/2750; avg_match=19/25; avg_match_delta_pool=31/1650

- Selected-strategy support: bet2_fourier_expansion_biglotto=5, biglotto_deviation_2bet=155, biglotto_echo_aware_3bet=375, cold_complement_biglotto=3, fourier30_markov30_biglotto=183, markov_2bet_biglotto=29
