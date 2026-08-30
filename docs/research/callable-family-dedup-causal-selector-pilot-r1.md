# Callable-family dedup causal selector pilot R1

This bounded exploratory pilot compares the sealed original rolling selector, a callable-family-deduplicated rolling selector, and a frozen baseline selected from the same deduplicated universe. It is historical evidence only.

## Fixed rule and authority boundary

- Grouping scope: source authority x lottery x native ticket-count cell x callable.
- Representative: lexicographically smallest complete `(source_authority_id, lottery_id, strategy_id, strategy_version)` identity.
- Representative selection uses no historical score, prize, target, future, or rolling-performance input.
- Windows are fixed at W50, W300, and W750; selection is strictly before target.
- Original, dedup rolling, and dedup frozen use identical target sets.

## Callable-family accounting

- Original candidate count summed across cells: 170
- Deduplicated callable count summed across cells: 122
- Removed sibling count summed across cells: 48

## Complete lottery x K x window results

| Lottery | K | Window | Status | Original candidates | Dedup callables | Removed | Targets | Original rolling | Dedup rolling | Dedup frozen | Dedup-original | Dedup-frozen | Original switches | Dedup switches | First | Last | Exclusion |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| B649 | 2 | W50 | EXCLUDED | 19 | 19 | 0 | 0 | — | — | — | — | — | 0 | 0 | — | — | NO_COMPLETE_FIXED_UNIVERSE_TARGET |
| B649 | 2 | W300 | EXCLUDED | 19 | 19 | 0 | 0 | — | — | — | — | — | 0 | 0 | — | — | NO_COMPLETE_FIXED_UNIVERSE_TARGET |
| B649 | 2 | W750 | EXCLUDED | 19 | 19 | 0 | 0 | — | — | — | — | — | 0 | 0 | — | — | NO_COMPLETE_FIXED_UNIVERSE_TARGET |
| B649 | 3 | W50 | COMPLETE | 19 | 19 | 0 | 654 | 21/218 | 21/218 | 59/654 | 0/1 | 2/327 | 69 | 69 | 109000077 | 115000081 | — |
| B649 | 3 | W300 | COMPLETE | 19 | 19 | 0 | 404 | 6/101 | 6/101 | 31/404 | 0/1 | -7/404 | 28 | 28 | 111000114 | 115000081 | — |
| B649 | 3 | W750 | EXCLUDED | 19 | 19 | 0 | 0 | — | — | — | — | — | 0 | 0 | — | — | INSUFFICIENT_COMPARABLE_TARGETS_FOR_PRIOR_WINDOW_AND_CURRENT_TARGET |
| P638 | 1 | W50 | COMPLETE | 22 | 10 | 12 | 847 | 96/847 | 14/121 | 13/121 | 2/847 | 1/121 | 115 | 78 | 102000067 | 115000061 | — |
| P638 | 1 | W300 | COMPLETE | 22 | 10 | 12 | 597 | 65/597 | 20/199 | 67/597 | -5/597 | -7/597 | 21 | 35 | 106000081 | 115000061 | — |
| P638 | 1 | W750 | COMPLETE | 22 | 10 | 12 | 147 | 4/49 | 11/147 | 11/147 | -1/147 | 0/1 | 4 | 0 | 113000079 | 115000061 | — |
| P638 | 2 | W50 | COMPLETE | 21 | 21 | 0 | 1783 | 312/1783 | 312/1783 | 321/1783 | 0/1 | -9/1783 | 241 | 241 | 98000053 | 115000061 | — |
| P638 | 2 | W300 | COMPLETE | 21 | 21 | 0 | 1533 | 284/1533 | 284/1533 | 277/1533 | 0/1 | 1/219 | 69 | 69 | 100000094 | 115000061 | — |
| P638 | 2 | W750 | COMPLETE | 21 | 21 | 0 | 1083 | 68/361 | 68/361 | 59/361 | 0/1 | 9/361 | 34 | 34 | 105000022 | 115000061 | — |
| P638 | 3 | W50 | COMPLETE | 14 | 14 | 0 | 1833 | 138/611 | 138/611 | 388/1833 | 0/1 | 2/141 | 196 | 196 | 98000003 | 115000061 | — |
| P638 | 3 | W300 | COMPLETE | 14 | 14 | 0 | 1583 | 338/1583 | 338/1583 | 359/1583 | 0/1 | -21/1583 | 72 | 72 | 100000044 | 115000061 | — |
| P638 | 3 | W750 | COMPLETE | 14 | 14 | 0 | 1133 | 256/1133 | 256/1133 | 22/103 | 0/1 | 14/1133 | 11 | 11 | 104000077 | 115000061 | — |
| P638 | 4 | W50 | COMPLETE | 3 | 3 | 0 | 1832 | 459/1832 | 459/1832 | 221/916 | 0/1 | 17/1832 | 114 | 114 | 98000004 | 115000061 | — |
| P638 | 4 | W300 | COMPLETE | 3 | 3 | 0 | 1582 | 403/1582 | 403/1582 | 207/791 | 0/1 | -11/1582 | 41 | 41 | 100000045 | 115000061 | — |
| P638 | 4 | W750 | COMPLETE | 3 | 3 | 0 | 1132 | 153/566 | 153/566 | 77/283 | 0/1 | -1/566 | 4 | 4 | 104000078 | 115000061 | — |
| P638 | 5 | W50 | COMPLETE | 3 | 3 | 0 | 1853 | 488/1853 | 488/1853 | 497/1853 | 0/1 | -9/1853 | 79 | 79 | 97000081 | 115000061 | — |
| P638 | 5 | W300 | COMPLETE | 3 | 3 | 0 | 1603 | 423/1603 | 423/1603 | 433/1603 | 0/1 | -10/1603 | 55 | 55 | 100000024 | 115000061 | — |
| P638 | 5 | W750 | COMPLETE | 3 | 3 | 0 | 1153 | 312/1153 | 312/1153 | 322/1153 | 0/1 | -10/1153 | 12 | 12 | 104000057 | 115000061 | — |
| P638 | 7 | W50 | COMPLETE | 3 | 3 | 0 | 1783 | 573/1783 | 573/1783 | 539/1783 | 0/1 | 34/1783 | 92 | 92 | 98000053 | 115000061 | — |
| P638 | 7 | W300 | COMPLETE | 3 | 3 | 0 | 1533 | 509/1533 | 509/1533 | 520/1533 | 0/1 | -11/1533 | 32 | 32 | 100000094 | 115000061 | — |
| P638 | 7 | W750 | COMPLETE | 3 | 3 | 0 | 1083 | 370/1083 | 370/1083 | 370/1083 | 0/1 | 0/1 | 0 | 0 | 105000022 | 115000061 | — |
| P638 | 10 | W50 | COMPLETE | 1 | 1 | 0 | 1853 | 590/1853 | 590/1853 | 590/1853 | 0/1 | 0/1 | 0 | 0 | 97000081 | 115000061 | — |
| P638 | 10 | W300 | COMPLETE | 1 | 1 | 0 | 1603 | 520/1603 | 520/1603 | 520/1603 | 0/1 | 0/1 | 0 | 0 | 100000024 | 115000061 | — |
| P638 | 10 | W750 | COMPLETE | 1 | 1 | 0 | 1153 | 380/1153 | 380/1153 | 380/1153 | 0/1 | 0/1 | 0 | 0 | 104000057 | 115000061 | — |
| P638 | 11 | W50 | COMPLETE | 1 | 1 | 0 | 1853 | 709/1853 | 709/1853 | 709/1853 | 0/1 | 0/1 | 0 | 0 | 97000081 | 115000061 | — |
| P638 | 11 | W300 | COMPLETE | 1 | 1 | 0 | 1603 | 611/1603 | 611/1603 | 611/1603 | 0/1 | 0/1 | 0 | 0 | 100000024 | 115000061 | — |
| P638 | 11 | W750 | COMPLETE | 1 | 1 | 0 | 1153 | 435/1153 | 435/1153 | 435/1153 | 0/1 | 0/1 | 0 | 0 | 104000057 | 115000061 | — |
| P638 | 12 | W50 | COMPLETE | 1 | 1 | 0 | 1853 | 733/1853 | 733/1853 | 733/1853 | 0/1 | 0/1 | 0 | 0 | 97000081 | 115000061 | — |
| P638 | 12 | W300 | COMPLETE | 1 | 1 | 0 | 1603 | 640/1603 | 640/1603 | 640/1603 | 0/1 | 0/1 | 0 | 0 | 100000024 | 115000061 | — |
| P638 | 12 | W750 | COMPLETE | 1 | 1 | 0 | 1153 | 466/1153 | 466/1153 | 466/1153 | 0/1 | 0/1 | 0 | 0 | 104000057 | 115000061 | — |
| P638 | 25 | W50 | COMPLETE | 1 | 1 | 0 | 1853 | 840/1853 | 840/1853 | 840/1853 | 0/1 | 0/1 | 0 | 0 | 97000081 | 115000061 | — |
| P638 | 25 | W300 | COMPLETE | 1 | 1 | 0 | 1603 | 743/1603 | 743/1603 | 743/1603 | 0/1 | 0/1 | 0 | 0 | 100000024 | 115000061 | — |
| P638 | 25 | W750 | COMPLETE | 1 | 1 | 0 | 1153 | 544/1153 | 544/1153 | 544/1153 | 0/1 | 0/1 | 0 | 0 | 104000057 | 115000061 | — |
| T539 | 1 | W50 | COMPLETE | 25 | 12 | 13 | 5680 | 123/1136 | 31/284 | 65/568 | 1/1136 | -3/568 | 887 | 663 | 96000251 | 115000186 | — |
| T539 | 1 | W300 | COMPLETE | 25 | 12 | 13 | 5430 | 113/905 | 641/5430 | 332/2715 | -37/5430 | -23/5430 | 259 | 265 | 97000240 | 115000186 | — |
| T539 | 1 | W750 | COMPLETE | 25 | 12 | 13 | 4980 | 39/332 | 31/249 | 283/2490 | 7/996 | 9/830 | 174 | 94 | 99000167 | 115000186 | — |
| T539 | 2 | W50 | COMPLETE | 13 | 3 | 10 | 5780 | 63/289 | 332/1445 | 337/1445 | 1/85 | -1/289 | 829 | 452 | 96000151 | 115000186 | — |
| T539 | 2 | W300 | COMPLETE | 13 | 3 | 10 | 5530 | 626/2765 | 257/1106 | 631/2765 | 33/5530 | 23/5530 | 287 | 154 | 97000140 | 115000186 | — |
| T539 | 2 | W750 | COMPLETE | 13 | 3 | 10 | 5080 | 233/1016 | 287/1270 | 579/2540 | -17/5080 | -1/508 | 126 | 101 | 99000067 | 115000186 | — |
| T539 | 3 | W50 | COMPLETE | 13 | 3 | 10 | 5780 | 365/1156 | 951/2890 | 1899/5780 | 77/5780 | 3/5780 | 889 | 434 | 96000151 | 115000186 | — |
| T539 | 3 | W300 | COMPLETE | 13 | 3 | 10 | 5530 | 1811/5530 | 932/2765 | 934/2765 | 53/5530 | -2/2765 | 262 | 91 | 97000140 | 115000186 | — |
| T539 | 3 | W750 | COMPLETE | 13 | 3 | 10 | 5080 | 429/1270 | 863/2540 | 863/2540 | 1/508 | 0/1 | 118 | 42 | 99000067 | 115000186 | — |
| T539 | 4 | W50 | COMPLETE | 1 | 1 | 0 | 5879 | 2268/5879 | 2268/5879 | 2268/5879 | 0/1 | 0/1 | 0 | 0 | 96000052 | 115000186 | — |
| T539 | 4 | W300 | COMPLETE | 1 | 1 | 0 | 5629 | 2162/5629 | 2162/5629 | 2162/5629 | 0/1 | 0/1 | 0 | 0 | 97000041 | 115000186 | — |
| T539 | 4 | W750 | COMPLETE | 1 | 1 | 0 | 5179 | 1976/5179 | 1976/5179 | 1976/5179 | 0/1 | 0/1 | 0 | 0 | 98000229 | 115000186 | — |
| T539 | 5 | W50 | COMPLETE | 3 | 2 | 1 | 5780 | 3007/5780 | 3007/5780 | 253/578 | 0/1 | 477/5780 | 193 | 193 | 96000151 | 115000186 | — |
| T539 | 5 | W300 | COMPLETE | 3 | 2 | 1 | 5530 | 1473/2765 | 1473/2765 | 295/553 | 0/1 | -2/2765 | 2 | 2 | 97000140 | 115000186 | — |
| T539 | 5 | W750 | COMPLETE | 3 | 2 | 1 | 5080 | 68/127 | 68/127 | 68/127 | 0/1 | 0/1 | 0 | 0 | 99000067 | 115000186 | — |
| T539 | 7 | W50 | COMPLETE | 3 | 1 | 2 | 5780 | 1543/2890 | 267/578 | 267/578 | -104/1445 | 0/1 | 280 | 0 | 96000151 | 115000186 | — |
| T539 | 7 | W300 | COMPLETE | 3 | 1 | 2 | 5530 | 3047/5530 | 1278/2765 | 1278/2765 | -491/5530 | 0/1 | 10 | 0 | 97000140 | 115000186 | — |
| T539 | 7 | W750 | COMPLETE | 3 | 1 | 2 | 5080 | 1403/2540 | 2359/5080 | 2359/5080 | -447/5080 | 0/1 | 0 | 0 | 99000067 | 115000186 | — |
| T539 | 10 | W50 | COMPLETE | 1 | 1 | 0 | 5879 | 3239/5879 | 3239/5879 | 3239/5879 | 0/1 | 0/1 | 0 | 0 | 96000052 | 115000186 | — |
| T539 | 10 | W300 | COMPLETE | 1 | 1 | 0 | 5629 | 3101/5629 | 3101/5629 | 3101/5629 | 0/1 | 0/1 | 0 | 0 | 97000041 | 115000186 | — |
| T539 | 10 | W750 | COMPLETE | 1 | 1 | 0 | 5179 | 2845/5179 | 2845/5179 | 2845/5179 | 0/1 | 0/1 | 0 | 0 | 98000229 | 115000186 | — |
| T539 | 11 | W50 | COMPLETE | 1 | 1 | 0 | 5860 | 3857/5860 | 3857/5860 | 3857/5860 | 0/1 | 0/1 | 0 | 0 | 96000071 | 115000186 | — |
| T539 | 11 | W300 | COMPLETE | 1 | 1 | 0 | 5610 | 1229/1870 | 1229/1870 | 1229/1870 | 0/1 | 0/1 | 0 | 0 | 97000060 | 115000186 | — |
| T539 | 11 | W750 | COMPLETE | 1 | 1 | 0 | 5160 | 225/344 | 225/344 | 225/344 | 0/1 | 0/1 | 0 | 0 | 98000248 | 115000186 | — |
| T539 | 12 | W50 | COMPLETE | 1 | 1 | 0 | 5879 | 3848/5879 | 3848/5879 | 3848/5879 | 0/1 | 0/1 | 0 | 0 | 96000052 | 115000186 | — |
| T539 | 12 | W300 | COMPLETE | 1 | 1 | 0 | 5629 | 3693/5629 | 3693/5629 | 3693/5629 | 0/1 | 0/1 | 0 | 0 | 97000041 | 115000186 | — |
| T539 | 12 | W750 | COMPLETE | 1 | 1 | 0 | 5179 | 3397/5179 | 3397/5179 | 3397/5179 | 0/1 | 0/1 | 0 | 0 | 98000229 | 115000186 | — |
| T539 | 25 | W50 | COMPLETE | 1 | 1 | 0 | 5879 | 4502/5879 | 4502/5879 | 4502/5879 | 0/1 | 0/1 | 0 | 0 | 96000052 | 115000186 | — |
| T539 | 25 | W300 | COMPLETE | 1 | 1 | 0 | 5629 | 4344/5629 | 4344/5629 | 4344/5629 | 0/1 | 0/1 | 0 | 0 | 97000041 | 115000186 | — |
| T539 | 25 | W750 | COMPLETE | 1 | 1 | 0 | 5179 | 3979/5179 | 3979/5179 | 3979/5179 | 0/1 | 0/1 | 0 | 0 | 98000229 | 115000186 | — |

## Required descriptive answers

### 1. Does family dedup improve more cells than it worsens?

Answer: `YES`

```json
{
  "improved": 8,
  "unchanged": 47,
  "worsened": 7
}
```

### 2. Among the five repeated-positive R2 cells, does sign stability improve?

Answer: `YES`

```json
{
  "dedup_discordant_window_pairs": 9,
  "original_discordant_window_pairs": 10,
  "per_cell": [
    {
      "cell_id": "P638:K2",
      "dedup_discordant_window_pairs": 2,
      "dedup_signs": {
        "W300": "POSITIVE",
        "W50": "NEGATIVE",
        "W750": "POSITIVE"
      },
      "original_discordant_window_pairs": 2,
      "original_signs": {
        "W300": "POSITIVE",
        "W50": "NEGATIVE",
        "W750": "POSITIVE"
      }
    },
    {
      "cell_id": "P638:K3",
      "dedup_discordant_window_pairs": 2,
      "dedup_signs": {
        "W300": "NEGATIVE",
        "W50": "POSITIVE",
        "W750": "POSITIVE"
      },
      "original_discordant_window_pairs": 2,
      "original_signs": {
        "W300": "NEGATIVE",
        "W50": "POSITIVE",
        "W750": "POSITIVE"
      }
    },
    {
      "cell_id": "T539:K1",
      "dedup_discordant_window_pairs": 2,
      "dedup_signs": {
        "W300": "NEGATIVE",
        "W50": "NEGATIVE",
        "W750": "POSITIVE"
      },
      "original_discordant_window_pairs": 2,
      "original_signs": {
        "W300": "POSITIVE",
        "W50": "NEGATIVE",
        "W750": "POSITIVE"
      }
    },
    {
      "cell_id": "T539:K2",
      "dedup_discordant_window_pairs": 2,
      "dedup_signs": {
        "W300": "POSITIVE",
        "W50": "NEGATIVE",
        "W750": "NEGATIVE"
      },
      "original_discordant_window_pairs": 2,
      "original_signs": {
        "W300": "POSITIVE",
        "W50": "NEGATIVE",
        "W750": "POSITIVE"
      }
    },
    {
      "cell_id": "T539:K3",
      "dedup_discordant_window_pairs": 1,
      "dedup_signs": {
        "W300": "NEGATIVE",
        "W50": "POSITIVE",
        "W750": "ZERO"
      },
      "original_discordant_window_pairs": 2,
      "original_signs": {
        "W300": "NEGATIVE",
        "W50": "POSITIVE",
        "W750": "POSITIVE"
      }
    }
  ]
}
```

### 3. Do P638 K1 results materially change after collapsing the C01-C07 family?

Answer: `DESCRIPTIVE_SIGN_CHANGE`

```json
{
  "c01_c07_family": {
    "authority_qualified_callable_identity": [
      "P638_CURRENT_REPLAY_AND_RANKING",
      "P638",
      1,
      "callable-sha256:910e4d00093b63db80704405c33bac275651218096688218d9b2dd328bd2905f"
    ],
    "callable_identity": "callable-sha256:910e4d00093b63db80704405c33bac275651218096688218d9b2dd328bd2905f",
    "callable_labels": [
      "lottolab.strategies.adapters.cross_dataset_batch02_bridge:_PowerLottoWave2BridgeAdapter._predict"
    ],
    "member_count": 7,
    "member_identities": [
      [
        "P638_CURRENT_REPLAY_AND_RANKING",
        "P638",
        "power_c01_recency_decay_1bet",
        "v0.1-p638-p173"
      ],
      [
        "P638_CURRENT_REPLAY_AND_RANKING",
        "P638",
        "power_c02_gap_overdue_1bet",
        "v0.1-p638-p173"
      ],
      [
        "P638_CURRENT_REPLAY_AND_RANKING",
        "P638",
        "power_c03_pair_centrality_1bet",
        "v0.1-p638-p176"
      ],
      [
        "P638_CURRENT_REPLAY_AND_RANKING",
        "P638",
        "power_c04_zone_balanced_1bet",
        "v0.1-p638-p173"
      ],
      [
        "P638_CURRENT_REPLAY_AND_RANKING",
        "P638",
        "power_c05_dispersion_match_1bet",
        "v0.1-p638-p176"
      ],
      [
        "P638_CURRENT_REPLAY_AND_RANKING",
        "P638",
        "power_c06_regime_cusum_1bet",
        "v0.1-p638-p176"
      ],
      [
        "P638_CURRENT_REPLAY_AND_RANKING",
        "P638",
        "power_c07_borda_ensemble_1bet",
        "v0.1-p638-p176"
      ]
    ],
    "removed_sibling_count": 6,
    "removed_sibling_identities": [
      [
        "P638_CURRENT_REPLAY_AND_RANKING",
        "P638",
        "power_c02_gap_overdue_1bet",
        "v0.1-p638-p173"
      ],
      [
        "P638_CURRENT_REPLAY_AND_RANKING",
        "P638",
        "power_c03_pair_centrality_1bet",
        "v0.1-p638-p176"
      ],
      [
        "P638_CURRENT_REPLAY_AND_RANKING",
        "P638",
        "power_c04_zone_balanced_1bet",
        "v0.1-p638-p173"
      ],
      [
        "P638_CURRENT_REPLAY_AND_RANKING",
        "P638",
        "power_c05_dispersion_match_1bet",
        "v0.1-p638-p176"
      ],
      [
        "P638_CURRENT_REPLAY_AND_RANKING",
        "P638",
        "power_c06_regime_cusum_1bet",
        "v0.1-p638-p176"
      ],
      [
        "P638_CURRENT_REPLAY_AND_RANKING",
        "P638",
        "power_c07_borda_ensemble_1bet",
        "v0.1-p638-p176"
      ]
    ],
    "representative_identity": [
      "P638_CURRENT_REPLAY_AND_RANKING",
      "P638",
      "power_c01_recency_decay_1bet",
      "v0.1-p638-p173"
    ],
    "representative_rule": "LEXICOGRAPHIC_MINIMUM_COMPLETE_AUTHORITY_QUALIFIED_IDENTITY",
    "resolution_authorities": [
      "BASE_PRODUCTION_LINEAGE",
      "R2_AUTHORITY_QUALIFIED_ATTRIBUTION"
    ]
  },
  "materiality_threshold": "NOT_DEFINED_OR_TESTED",
  "per_window": [
    {
      "cell_id": "P638:K1",
      "dedup_frozen_metric": {
        "metric_id": "OFFICIAL_ANY_PRIZE_TARGET_RATE",
        "rate": {
          "decimal_12": "0.107438016529",
          "denominator": 121,
          "exact": "13/121",
          "numerator": 13
        },
        "success_count": 91,
        "target_count": 847
      },
      "dedup_frozen_strategy_id": "power_biglotto_optimized_ensemble_1bet",
      "dedup_rolling_metric": {
        "metric_id": "OFFICIAL_ANY_PRIZE_TARGET_RATE",
        "rate": {
          "decimal_12": "0.115702479339",
          "denominator": 121,
          "exact": "14/121",
          "numerator": 14
        },
        "success_count": 98,
        "target_count": 847
      },
      "dedup_rolling_vs_dedup_frozen_exact_delta": {
        "decimal_12": "0.008264462810",
        "denominator": 121,
        "exact": "1/121",
        "numerator": 1
      },
      "dedup_rolling_vs_dedup_frozen_sign": "POSITIVE",
      "dedup_vs_original_exact_delta": {
        "decimal_12": "0.002361275089",
        "denominator": 847,
        "exact": "2/847",
        "numerator": 2
      },
      "dedup_vs_original_sign": "POSITIVE",
      "deduplicated_callable_count": 10,
      "eligible_target_count": 847,
      "exclusions": {
        "dedup_exclusion_reason": null,
        "dedup_status": "COMPLETE",
        "original_exclusion_reason": null,
        "original_status": "COMPLETE"
      },
      "first_target": "102000067",
      "k": 1,
      "last_target": "115000061",
      "lottery_id": "P638",
      "original_candidate_count": 22,
      "original_frozen_metric": {
        "metric_id": "OFFICIAL_ANY_PRIZE_TARGET_RATE",
        "rate": {
          "decimal_12": "0.119244391972",
          "denominator": 847,
          "exact": "101/847",
          "numerator": 101
        },
        "success_count": 101,
        "target_count": 847
      },
      "original_frozen_strategy_id": "power_c07_borda_ensemble_1bet",
      "original_rolling_metric": {
        "metric_id": "OFFICIAL_ANY_PRIZE_TARGET_RATE",
        "rate": {
          "decimal_12": "0.113341204250",
          "denominator": 847,
          "exact": "96/847",
          "numerator": 96
        },
        "success_count": 96,
        "target_count": 847
      },
      "original_rolling_vs_original_frozen_exact_delta": {
        "decimal_12": "-0.005903187721",
        "denominator": 847,
        "exact": "-5/847",
        "numerator": -5
      },
      "original_rolling_vs_original_frozen_sign": "NEGATIVE",
      "removed_sibling_count": 12,
      "selection_frequencies": {
        "dedup_rolling_by_callable": {
          "callable-sha256:910e4d00093b63db80704405c33bac275651218096688218d9b2dd328bd2905f": 140,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_attention_replay_tickets": 162,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_dynamic_frequency_tickets": 65,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_graph_predictor_tickets": 48,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_hot_cooccurrence_tickets": 80,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_optimized_ensemble": 94,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_dms_predict": 156,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_single_predictor": 102
        },
        "dedup_rolling_by_strategy": {
          "power_biglotto_attention_replay_1bet": 162,
          "power_biglotto_cold_hunter_1bet": 102,
          "power_biglotto_dms_1bet": 156,
          "power_biglotto_dynamic_frequency_1bet": 65,
          "power_biglotto_graph_predictor_1bet": 48,
          "power_biglotto_hot_cooccurrence_1bet": 80,
          "power_biglotto_optimized_ensemble_1bet": 94,
          "power_c01_recency_decay_1bet": 140
        },
        "original_rolling_by_callable": {
          "callable-sha256:910e4d00093b63db80704405c33bac275651218096688218d9b2dd328bd2905f": 246,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_attention_replay_tickets": 37,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_dynamic_frequency_tickets": 22,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_graph_predictor_tickets": 14,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_optimized_ensemble": 54,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_dms_predict": 70,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_single_predictor": 404
        },
        "original_rolling_by_strategy": {
          "power_biglotto_attention_replay_1bet": 37,
          "power_biglotto_cold_hunter_1bet": 62,
          "power_biglotto_dms_1bet": 70,
          "power_biglotto_dynamic_frequency_1bet": 22,
          "power_biglotto_gap_pressure_1bet": 12,
          "power_biglotto_graph_predictor_1bet": 14,
          "power_biglotto_moderate_rank_1bet": 178,
          "power_biglotto_optimized_ensemble_1bet": 54,
          "power_biglotto_pure_cold_1bet": 19,
          "power_biglotto_rebound_aware_1bet": 22,
          "power_biglotto_short_window_deviation_1bet": 55,
          "power_biglotto_zone_momentum_1bet": 56,
          "power_c01_recency_decay_1bet": 17,
          "power_c03_pair_centrality_1bet": 34,
          "power_c04_zone_balanced_1bet": 11,
          "power_c05_dispersion_match_1bet": 22,
          "power_c06_regime_cusum_1bet": 65,
          "power_c07_borda_ensemble_1bet": 97
        }
      },
      "source_authority_id": "P638_CURRENT_REPLAY_AND_RANKING",
      "switch_counts": {
        "dedup_minus_original": -37,
        "dedup_rolling": 78,
        "original_rolling": 115
      },
      "target_set_parity": {
        "dedup_rolling_equals_dedup_frozen": true,
        "original_equals_dedup": true
      },
      "window": 50,
      "window_label": "W50"
    },
    {
      "cell_id": "P638:K1",
      "dedup_frozen_metric": {
        "metric_id": "OFFICIAL_ANY_PRIZE_TARGET_RATE",
        "rate": {
          "decimal_12": "0.112227805695",
          "denominator": 597,
          "exact": "67/597",
          "numerator": 67
        },
        "success_count": 67,
        "target_count": 597
      },
      "dedup_frozen_strategy_id": "power_biglotto_attention_replay_1bet",
      "dedup_rolling_metric": {
        "metric_id": "OFFICIAL_ANY_PRIZE_TARGET_RATE",
        "rate": {
          "decimal_12": "0.100502512563",
          "denominator": 199,
          "exact": "20/199",
          "numerator": 20
        },
        "success_count": 60,
        "target_count": 597
      },
      "dedup_rolling_vs_dedup_frozen_exact_delta": {
        "decimal_12": "-0.011725293132",
        "denominator": 597,
        "exact": "-7/597",
        "numerator": -7
      },
      "dedup_rolling_vs_dedup_frozen_sign": "NEGATIVE",
      "dedup_vs_original_exact_delta": {
        "decimal_12": "-0.008375209380",
        "denominator": 597,
        "exact": "-5/597",
        "numerator": -5
      },
      "dedup_vs_original_sign": "NEGATIVE",
      "deduplicated_callable_count": 10,
      "eligible_target_count": 597,
      "exclusions": {
        "dedup_exclusion_reason": null,
        "dedup_status": "COMPLETE",
        "original_exclusion_reason": null,
        "original_status": "COMPLETE"
      },
      "first_target": "106000081",
      "k": 1,
      "last_target": "115000061",
      "lottery_id": "P638",
      "original_candidate_count": 22,
      "original_frozen_metric": {
        "metric_id": "OFFICIAL_ANY_PRIZE_TARGET_RATE",
        "rate": {
          "decimal_12": "0.108877721943",
          "denominator": 597,
          "exact": "65/597",
          "numerator": 65
        },
        "success_count": 65,
        "target_count": 597
      },
      "original_frozen_strategy_id": "power_c07_borda_ensemble_1bet",
      "original_rolling_metric": {
        "metric_id": "OFFICIAL_ANY_PRIZE_TARGET_RATE",
        "rate": {
          "decimal_12": "0.108877721943",
          "denominator": 597,
          "exact": "65/597",
          "numerator": 65
        },
        "success_count": 65,
        "target_count": 597
      },
      "original_rolling_vs_original_frozen_exact_delta": {
        "decimal_12": "0.000000000000",
        "denominator": 1,
        "exact": "0/1",
        "numerator": 0
      },
      "original_rolling_vs_original_frozen_sign": "ZERO",
      "removed_sibling_count": 12,
      "selection_frequencies": {
        "dedup_rolling_by_callable": {
          "callable-sha256:910e4d00093b63db80704405c33bac275651218096688218d9b2dd328bd2905f": 86,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_attention_replay_tickets": 214,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_dynamic_frequency_tickets": 20,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_hot_cooccurrence_tickets": 11,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_optimized_ensemble": 69,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_dms_predict": 130,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_single_predictor": 67
        },
        "dedup_rolling_by_strategy": {
          "power_biglotto_attention_replay_1bet": 214,
          "power_biglotto_cold_hunter_1bet": 67,
          "power_biglotto_dms_1bet": 130,
          "power_biglotto_dynamic_frequency_1bet": 20,
          "power_biglotto_hot_cooccurrence_1bet": 11,
          "power_biglotto_optimized_ensemble_1bet": 69,
          "power_c01_recency_decay_1bet": 86
        },
        "original_rolling_by_callable": {
          "callable-sha256:910e4d00093b63db80704405c33bac275651218096688218d9b2dd328bd2905f": 494,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_attention_replay_tickets": 17,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_dms_predict": 28,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_single_predictor": 58
        },
        "original_rolling_by_strategy": {
          "power_biglotto_attention_replay_1bet": 17,
          "power_biglotto_dms_1bet": 28,
          "power_biglotto_moderate_rank_1bet": 52,
          "power_biglotto_pure_cold_1bet": 6,
          "power_c03_pair_centrality_1bet": 18,
          "power_c04_zone_balanced_1bet": 144,
          "power_c06_regime_cusum_1bet": 68,
          "power_c07_borda_ensemble_1bet": 264
        }
      },
      "source_authority_id": "P638_CURRENT_REPLAY_AND_RANKING",
      "switch_counts": {
        "dedup_minus_original": 14,
        "dedup_rolling": 35,
        "original_rolling": 21
      },
      "target_set_parity": {
        "dedup_rolling_equals_dedup_frozen": true,
        "original_equals_dedup": true
      },
      "window": 300,
      "window_label": "W300"
    },
    {
      "cell_id": "P638:K1",
      "dedup_frozen_metric": {
        "metric_id": "OFFICIAL_ANY_PRIZE_TARGET_RATE",
        "rate": {
          "decimal_12": "0.074829931973",
          "denominator": 147,
          "exact": "11/147",
          "numerator": 11
        },
        "success_count": 11,
        "target_count": 147
      },
      "dedup_frozen_strategy_id": "power_biglotto_attention_replay_1bet",
      "dedup_rolling_metric": {
        "metric_id": "OFFICIAL_ANY_PRIZE_TARGET_RATE",
        "rate": {
          "decimal_12": "0.074829931973",
          "denominator": 147,
          "exact": "11/147",
          "numerator": 11
        },
        "success_count": 11,
        "target_count": 147
      },
      "dedup_rolling_vs_dedup_frozen_exact_delta": {
        "decimal_12": "0.000000000000",
        "denominator": 1,
        "exact": "0/1",
        "numerator": 0
      },
      "dedup_rolling_vs_dedup_frozen_sign": "ZERO",
      "dedup_vs_original_exact_delta": {
        "decimal_12": "-0.006802721088",
        "denominator": 147,
        "exact": "-1/147",
        "numerator": -1
      },
      "dedup_vs_original_sign": "NEGATIVE",
      "deduplicated_callable_count": 10,
      "eligible_target_count": 147,
      "exclusions": {
        "dedup_exclusion_reason": null,
        "dedup_status": "COMPLETE",
        "original_exclusion_reason": null,
        "original_status": "COMPLETE"
      },
      "first_target": "113000079",
      "k": 1,
      "last_target": "115000061",
      "lottery_id": "P638",
      "original_candidate_count": 22,
      "original_frozen_metric": {
        "metric_id": "OFFICIAL_ANY_PRIZE_TARGET_RATE",
        "rate": {
          "decimal_12": "0.047619047619",
          "denominator": 21,
          "exact": "1/21",
          "numerator": 1
        },
        "success_count": 7,
        "target_count": 147
      },
      "original_frozen_strategy_id": "power_c07_borda_ensemble_1bet",
      "original_rolling_metric": {
        "metric_id": "OFFICIAL_ANY_PRIZE_TARGET_RATE",
        "rate": {
          "decimal_12": "0.081632653061",
          "denominator": 49,
          "exact": "4/49",
          "numerator": 4
        },
        "success_count": 12,
        "target_count": 147
      },
      "original_rolling_vs_original_frozen_exact_delta": {
        "decimal_12": "0.034013605442",
        "denominator": 147,
        "exact": "5/147",
        "numerator": 5
      },
      "original_rolling_vs_original_frozen_sign": "POSITIVE",
      "removed_sibling_count": 12,
      "selection_frequencies": {
        "dedup_rolling_by_callable": {
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_attention_replay_tickets": 147
        },
        "dedup_rolling_by_strategy": {
          "power_biglotto_attention_replay_1bet": 147
        },
        "original_rolling_by_callable": {
          "callable-sha256:910e4d00093b63db80704405c33bac275651218096688218d9b2dd328bd2905f": 75,
          "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_single_predictor": 72
        },
        "original_rolling_by_strategy": {
          "power_biglotto_moderate_rank_1bet": 72,
          "power_c03_pair_centrality_1bet": 33,
          "power_c07_borda_ensemble_1bet": 42
        }
      },
      "source_authority_id": "P638_CURRENT_REPLAY_AND_RANKING",
      "switch_counts": {
        "dedup_minus_original": -4,
        "dedup_rolling": 0,
        "original_rolling": 4
      },
      "target_set_parity": {
        "dedup_rolling_equals_dedup_frozen": true,
        "original_equals_dedup": true
      },
      "window": 750,
      "window_label": "W750"
    }
  ],
  "sign_changed_windows": [
    "W50",
    "W300",
    "W750"
  ]
}
```

### 4. Are W50 sign reversals reduced?

Answer: `NO_CHANGE`

```json
{
  "dedup_reversal_cell_count": 10,
  "dedup_reversal_cells": [
    "B649:K3",
    "P638:K1",
    "P638:K2",
    "P638:K3",
    "P638:K4",
    "P638:K7",
    "T539:K1",
    "T539:K2",
    "T539:K3",
    "T539:K5"
  ],
  "original_reversal_cell_count": 10,
  "original_reversal_cells": [
    "B649:K3",
    "P638:K1",
    "P638:K2",
    "P638:K3",
    "P638:K4",
    "P638:K7",
    "T539:K1",
    "T539:K2",
    "T539:K3",
    "T539:K5"
  ]
}
```

### 5. Does switching frequency decrease?

Answer: `YES`

```json
{
  "dedup_switch_frequency": {
    "decimal_12": "0.017995425623",
    "denominator": 208553,
    "exact": "3753/208553",
    "numerator": 3753
  },
  "dedup_switches": 3753,
  "experiment_directions": {
    "DECREASED": 12,
    "INCREASED": 2,
    "UNCHANGED": 48
  },
  "original_switch_frequency": {
    "decimal_12": "0.026875662302",
    "denominator": 208553,
    "exact": "5605/208553",
    "numerator": 5605
  },
  "original_switches": 5605,
  "shared_transition_count": 208553
}
```

### 6. Are gains concentrated in any lottery/K/window?

Answer: `DESCRIPTIVE_COUNTS_ONLY`

```json
{
  "improvements_by_cell": {
    "P638:K1": 1,
    "T539:K1": 2,
    "T539:K2": 2,
    "T539:K3": 3
  },
  "improvements_by_lottery": {
    "P638": 1,
    "T539": 7
  },
  "improvements_by_window": {
    "W300": 2,
    "W50": 4,
    "W750": 2
  },
  "positive_experiments": [
    {
      "cell_id": "P638:K1",
      "delta": {
        "decimal_12": "0.002361275089",
        "denominator": 847,
        "exact": "2/847",
        "numerator": 2
      },
      "window_label": "W50"
    },
    {
      "cell_id": "T539:K1",
      "delta": {
        "decimal_12": "0.000880281690",
        "denominator": 1136,
        "exact": "1/1136",
        "numerator": 1
      },
      "window_label": "W50"
    },
    {
      "cell_id": "T539:K1",
      "delta": {
        "decimal_12": "0.007028112450",
        "denominator": 996,
        "exact": "7/996",
        "numerator": 7
      },
      "window_label": "W750"
    },
    {
      "cell_id": "T539:K2",
      "delta": {
        "decimal_12": "0.011764705882",
        "denominator": 85,
        "exact": "1/85",
        "numerator": 1
      },
      "window_label": "W50"
    },
    {
      "cell_id": "T539:K2",
      "delta": {
        "decimal_12": "0.005967450271",
        "denominator": 5530,
        "exact": "33/5530",
        "numerator": 33
      },
      "window_label": "W300"
    },
    {
      "cell_id": "T539:K3",
      "delta": {
        "decimal_12": "0.013321799308",
        "denominator": 5780,
        "exact": "77/5780",
        "numerator": 77
      },
      "window_label": "W50"
    },
    {
      "cell_id": "T539:K3",
      "delta": {
        "decimal_12": "0.009584086799",
        "denominator": 5530,
        "exact": "53/5530",
        "numerator": 53
      },
      "window_label": "W300"
    },
    {
      "cell_id": "T539:K3",
      "delta": {
        "decimal_12": "0.001968503937",
        "denominator": 508,
        "exact": "1/508",
        "numerator": 1
      },
      "window_label": "W750"
    }
  ]
}
```

### 7. Does the dedup challenger still show mixed outcomes?

Answer: `YES`

```json
{
  "negative": 7,
  "positive": 8,
  "zero": 47
}
```

## Selection-frequency and family detail

### B649:K2

Original candidates: 19; dedup callables: 19; removed siblings: 0.

- W50 original strategies: `{}`
- W50 original callables: `{}`
- W50 dedup strategies: `{}`
- W50 dedup callables: `{}`
- W300 original strategies: `{}`
- W300 original callables: `{}`
- W300 dedup strategies: `{}`
- W300 dedup callables: `{}`
- W750 original strategies: `{}`
- W750 original callables: `{}`
- W750 dedup strategies: `{}`
- W750 dedup callables: `{}`
- Reduced callable families: `[]`

### B649:K3

Original candidates: 19; dedup callables: 19; removed siblings: 0.

- W50 original strategies: `{"legacy_biglotto__backtest_sum_constraint__acb3b118300d": 91, "legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2": 118, "legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5": 29, "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d": 1, "legacy_biglotto__core_satellite__611284461323": 20, "legacy_biglotto__predict_biglotto_triple_strike__dad1c50d1504": 41, "legacy_biglotto__test_asm__d39a233a4c75": 18, "legacy_biglotto__test_cag__7ca5343dfedd": 23, "legacy_biglotto__test_ces__78d17c530ab8": 42, "legacy_biglotto__test_cluster_cover__5b43959e7c55": 66, "legacy_biglotto__test_dcb__c3299c25ca59": 66, "legacy_biglotto__test_dms__b63442289bd5": 14, "legacy_biglotto__test_mwsc__ba37643d6a3b": 71, "legacy_biglotto__test_tme__f3bb5106dfe3": 21, "legacy_biglotto__test_zdp__e80cc7e95453": 33}`
- W50 original callables: `{"callable-sha256:06e44ebcc74bec4ac714a818f4e89f77b021406f33cb256359f730e95aba4678": 21, "callable-sha256:07cc35e567f0830a30de8a4eee55d31cfccfd4973ea82e11288eb7d2459b7e49": 118, "callable-sha256:1eb01f06b983b9a8a9cc63883c25940668a0880f993aa09fd395164fef40680d": 20, "callable-sha256:2bef88048bd72f34b975864b6b9c00f2faaca74bbc4094a20c8ac22869350fe8": 33, "callable-sha256:3449814a1275cf9ae0212ed893f81baf3e3dd5a5874c8450666166a189a3fd32": 41, "callable-sha256:3e20a5b378e8a1b2507a51b3eb6acaa67f5d06f99440bbd3f5338e372fa58828": 91, "callable-sha256:8b231722df07afed7ef291e2b6b567e709435128f847a58adbef807846dc1168": 66, "callable-sha256:a62152b48f0a02ec557cc2204abfb9d915e738ffb5568746e8a85f0e7ac31663": 29, "callable-sha256:c2d7c644b4937350a72a62b187598ae5fa6afaad72be841eb9acc541165d1f70": 18, "callable-sha256:d16f928e78144cbd775b626f2eee2e082c3cbac756b466eff1fc36e6eeeeb05b": 66, "callable-sha256:e529fed4b203aba417f04b80d7773e10e0c953935a9c302b0e175d7a44de16fa": 1, "callable-sha256:f48aadb4c4e891a71b41ace05ed669731926fd642dc6e2d851d1ddbd76d68b34": 23, "wave26-structural-sha256:1e28a4b57f88a0109fbca62fc40c1e9f35967ef6effae6b6de211c08178beeb6": 42, "wave26-structural-sha256:51d3b444f45840125e3668b6d6a0b9eeb51db7b0391e506612b829f5d4842f3e": 71, "wave26-structural-sha256:e208ad41afb8cba2efd6d285928c173ab6b209a9db461e80dafa274a3e1c32f1": 14}`
- W50 dedup strategies: `{"legacy_biglotto__backtest_sum_constraint__acb3b118300d": 91, "legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2": 118, "legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5": 29, "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d": 1, "legacy_biglotto__core_satellite__611284461323": 20, "legacy_biglotto__predict_biglotto_triple_strike__dad1c50d1504": 41, "legacy_biglotto__test_asm__d39a233a4c75": 18, "legacy_biglotto__test_cag__7ca5343dfedd": 23, "legacy_biglotto__test_ces__78d17c530ab8": 42, "legacy_biglotto__test_cluster_cover__5b43959e7c55": 66, "legacy_biglotto__test_dcb__c3299c25ca59": 66, "legacy_biglotto__test_dms__b63442289bd5": 14, "legacy_biglotto__test_mwsc__ba37643d6a3b": 71, "legacy_biglotto__test_tme__f3bb5106dfe3": 21, "legacy_biglotto__test_zdp__e80cc7e95453": 33}`
- W50 dedup callables: `{"callable-sha256:06e44ebcc74bec4ac714a818f4e89f77b021406f33cb256359f730e95aba4678": 21, "callable-sha256:07cc35e567f0830a30de8a4eee55d31cfccfd4973ea82e11288eb7d2459b7e49": 118, "callable-sha256:1eb01f06b983b9a8a9cc63883c25940668a0880f993aa09fd395164fef40680d": 20, "callable-sha256:2bef88048bd72f34b975864b6b9c00f2faaca74bbc4094a20c8ac22869350fe8": 33, "callable-sha256:3449814a1275cf9ae0212ed893f81baf3e3dd5a5874c8450666166a189a3fd32": 41, "callable-sha256:3e20a5b378e8a1b2507a51b3eb6acaa67f5d06f99440bbd3f5338e372fa58828": 91, "callable-sha256:8b231722df07afed7ef291e2b6b567e709435128f847a58adbef807846dc1168": 66, "callable-sha256:a62152b48f0a02ec557cc2204abfb9d915e738ffb5568746e8a85f0e7ac31663": 29, "callable-sha256:c2d7c644b4937350a72a62b187598ae5fa6afaad72be841eb9acc541165d1f70": 18, "callable-sha256:d16f928e78144cbd775b626f2eee2e082c3cbac756b466eff1fc36e6eeeeb05b": 66, "callable-sha256:e529fed4b203aba417f04b80d7773e10e0c953935a9c302b0e175d7a44de16fa": 1, "callable-sha256:f48aadb4c4e891a71b41ace05ed669731926fd642dc6e2d851d1ddbd76d68b34": 23, "wave26-structural-sha256:1e28a4b57f88a0109fbca62fc40c1e9f35967ef6effae6b6de211c08178beeb6": 42, "wave26-structural-sha256:51d3b444f45840125e3668b6d6a0b9eeb51db7b0391e506612b829f5d4842f3e": 71, "wave26-structural-sha256:e208ad41afb8cba2efd6d285928c173ab6b209a9db461e80dafa274a3e1c32f1": 14}`
- W300 original strategies: `{"legacy_biglotto__backtest_sum_constraint__acb3b118300d": 18, "legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2": 175, "legacy_biglotto__core_satellite__611284461323": 78, "legacy_biglotto__test_cluster_cover__5b43959e7c55": 33, "legacy_biglotto__test_dcb__c3299c25ca59": 100}`
- W300 original callables: `{"callable-sha256:07cc35e567f0830a30de8a4eee55d31cfccfd4973ea82e11288eb7d2459b7e49": 175, "callable-sha256:1eb01f06b983b9a8a9cc63883c25940668a0880f993aa09fd395164fef40680d": 78, "callable-sha256:3e20a5b378e8a1b2507a51b3eb6acaa67f5d06f99440bbd3f5338e372fa58828": 18, "callable-sha256:8b231722df07afed7ef291e2b6b567e709435128f847a58adbef807846dc1168": 100, "callable-sha256:d16f928e78144cbd775b626f2eee2e082c3cbac756b466eff1fc36e6eeeeb05b": 33}`
- W300 dedup strategies: `{"legacy_biglotto__backtest_sum_constraint__acb3b118300d": 18, "legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2": 175, "legacy_biglotto__core_satellite__611284461323": 78, "legacy_biglotto__test_cluster_cover__5b43959e7c55": 33, "legacy_biglotto__test_dcb__c3299c25ca59": 100}`
- W300 dedup callables: `{"callable-sha256:07cc35e567f0830a30de8a4eee55d31cfccfd4973ea82e11288eb7d2459b7e49": 175, "callable-sha256:1eb01f06b983b9a8a9cc63883c25940668a0880f993aa09fd395164fef40680d": 78, "callable-sha256:3e20a5b378e8a1b2507a51b3eb6acaa67f5d06f99440bbd3f5338e372fa58828": 18, "callable-sha256:8b231722df07afed7ef291e2b6b567e709435128f847a58adbef807846dc1168": 100, "callable-sha256:d16f928e78144cbd775b626f2eee2e082c3cbac756b466eff1fc36e6eeeeb05b": 33}`
- W750 original strategies: `{}`
- W750 original callables: `{}`
- W750 dedup strategies: `{}`
- W750 dedup callables: `{}`
- Reduced callable families: `[]`

### P638:K1

Original candidates: 22; dedup callables: 10; removed siblings: 12.

- W50 original strategies: `{"power_biglotto_attention_replay_1bet": 37, "power_biglotto_cold_hunter_1bet": 62, "power_biglotto_dms_1bet": 70, "power_biglotto_dynamic_frequency_1bet": 22, "power_biglotto_gap_pressure_1bet": 12, "power_biglotto_graph_predictor_1bet": 14, "power_biglotto_moderate_rank_1bet": 178, "power_biglotto_optimized_ensemble_1bet": 54, "power_biglotto_pure_cold_1bet": 19, "power_biglotto_rebound_aware_1bet": 22, "power_biglotto_short_window_deviation_1bet": 55, "power_biglotto_zone_momentum_1bet": 56, "power_c01_recency_decay_1bet": 17, "power_c03_pair_centrality_1bet": 34, "power_c04_zone_balanced_1bet": 11, "power_c05_dispersion_match_1bet": 22, "power_c06_regime_cusum_1bet": 65, "power_c07_borda_ensemble_1bet": 97}`
- W50 original callables: `{"callable-sha256:910e4d00093b63db80704405c33bac275651218096688218d9b2dd328bd2905f": 246, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_attention_replay_tickets": 37, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_dynamic_frequency_tickets": 22, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_graph_predictor_tickets": 14, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_optimized_ensemble": 54, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_dms_predict": 70, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_single_predictor": 404}`
- W50 dedup strategies: `{"power_biglotto_attention_replay_1bet": 162, "power_biglotto_cold_hunter_1bet": 102, "power_biglotto_dms_1bet": 156, "power_biglotto_dynamic_frequency_1bet": 65, "power_biglotto_graph_predictor_1bet": 48, "power_biglotto_hot_cooccurrence_1bet": 80, "power_biglotto_optimized_ensemble_1bet": 94, "power_c01_recency_decay_1bet": 140}`
- W50 dedup callables: `{"callable-sha256:910e4d00093b63db80704405c33bac275651218096688218d9b2dd328bd2905f": 140, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_attention_replay_tickets": 162, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_dynamic_frequency_tickets": 65, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_graph_predictor_tickets": 48, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_hot_cooccurrence_tickets": 80, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_optimized_ensemble": 94, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_dms_predict": 156, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_single_predictor": 102}`
- W300 original strategies: `{"power_biglotto_attention_replay_1bet": 17, "power_biglotto_dms_1bet": 28, "power_biglotto_moderate_rank_1bet": 52, "power_biglotto_pure_cold_1bet": 6, "power_c03_pair_centrality_1bet": 18, "power_c04_zone_balanced_1bet": 144, "power_c06_regime_cusum_1bet": 68, "power_c07_borda_ensemble_1bet": 264}`
- W300 original callables: `{"callable-sha256:910e4d00093b63db80704405c33bac275651218096688218d9b2dd328bd2905f": 494, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_attention_replay_tickets": 17, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_dms_predict": 28, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_single_predictor": 58}`
- W300 dedup strategies: `{"power_biglotto_attention_replay_1bet": 214, "power_biglotto_cold_hunter_1bet": 67, "power_biglotto_dms_1bet": 130, "power_biglotto_dynamic_frequency_1bet": 20, "power_biglotto_hot_cooccurrence_1bet": 11, "power_biglotto_optimized_ensemble_1bet": 69, "power_c01_recency_decay_1bet": 86}`
- W300 dedup callables: `{"callable-sha256:910e4d00093b63db80704405c33bac275651218096688218d9b2dd328bd2905f": 86, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_attention_replay_tickets": 214, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_dynamic_frequency_tickets": 20, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_hot_cooccurrence_tickets": 11, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_optimized_ensemble": 69, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_dms_predict": 130, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_single_predictor": 67}`
- W750 original strategies: `{"power_biglotto_moderate_rank_1bet": 72, "power_c03_pair_centrality_1bet": 33, "power_c07_borda_ensemble_1bet": 42}`
- W750 original callables: `{"callable-sha256:910e4d00093b63db80704405c33bac275651218096688218d9b2dd328bd2905f": 75, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_single_predictor": 72}`
- W750 dedup strategies: `{"power_biglotto_attention_replay_1bet": 147}`
- W750 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_attention_replay_tickets": 147}`
- Reduced callable families: `[{"authority_qualified_callable_identity": ["P638_CURRENT_REPLAY_AND_RANKING", "P638", 1, "callable-sha256:910e4d00093b63db80704405c33bac275651218096688218d9b2dd328bd2905f"], "callable_identity": "callable-sha256:910e4d00093b63db80704405c33bac275651218096688218d9b2dd328bd2905f", "callable_labels": ["lottolab.strategies.adapters.cross_dataset_batch02_bridge:_PowerLottoWave2BridgeAdapter._predict"], "member_count": 7, "member_identities": [["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_c01_recency_decay_1bet", "v0.1-p638-p173"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_c02_gap_overdue_1bet", "v0.1-p638-p173"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_c03_pair_centrality_1bet", "v0.1-p638-p176"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_c04_zone_balanced_1bet", "v0.1-p638-p173"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_c05_dispersion_match_1bet", "v0.1-p638-p176"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_c06_regime_cusum_1bet", "v0.1-p638-p176"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_c07_borda_ensemble_1bet", "v0.1-p638-p176"]], "removed_sibling_count": 6, "removed_sibling_identities": [["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_c02_gap_overdue_1bet", "v0.1-p638-p173"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_c03_pair_centrality_1bet", "v0.1-p638-p176"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_c04_zone_balanced_1bet", "v0.1-p638-p173"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_c05_dispersion_match_1bet", "v0.1-p638-p176"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_c06_regime_cusum_1bet", "v0.1-p638-p176"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_c07_borda_ensemble_1bet", "v0.1-p638-p176"]], "representative_identity": ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_c01_recency_decay_1bet", "v0.1-p638-p173"], "representative_rule": "LEXICOGRAPHIC_MINIMUM_COMPLETE_AUTHORITY_QUALIFIED_IDENTITY", "resolution_authorities": ["BASE_PRODUCTION_LINEAGE", "R2_AUTHORITY_QUALIFIED_ATTRIBUTION"]}, {"authority_qualified_callable_identity": ["P638_CURRENT_REPLAY_AND_RANKING", "P638", 1, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_single_predictor"], "callable_identity": "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_single_predictor", "callable_labels": ["lottolab.strategies.adapters.powerlotto_wave6:_single_predictor"], "member_count": 7, "member_identities": [["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_biglotto_cold_hunter_1bet", "v0.1-p638-wave6"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_biglotto_gap_pressure_1bet", "v0.1-p638-wave6"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_biglotto_moderate_rank_1bet", "v0.1-p638-wave6"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_biglotto_pure_cold_1bet", "v0.1-p638-wave6"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_biglotto_rebound_aware_1bet", "v0.1-p638-wave6"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_biglotto_short_window_deviation_1bet", "v0.1-p638-wave6"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_biglotto_zone_momentum_1bet", "v0.1-p638-wave6"]], "removed_sibling_count": 6, "removed_sibling_identities": [["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_biglotto_gap_pressure_1bet", "v0.1-p638-wave6"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_biglotto_moderate_rank_1bet", "v0.1-p638-wave6"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_biglotto_pure_cold_1bet", "v0.1-p638-wave6"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_biglotto_rebound_aware_1bet", "v0.1-p638-wave6"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_biglotto_short_window_deviation_1bet", "v0.1-p638-wave6"], ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_biglotto_zone_momentum_1bet", "v0.1-p638-wave6"]], "representative_identity": ["P638_CURRENT_REPLAY_AND_RANKING", "P638", "power_biglotto_cold_hunter_1bet", "v0.1-p638-wave6"], "representative_rule": "LEXICOGRAPHIC_MINIMUM_COMPLETE_AUTHORITY_QUALIFIED_IDENTITY", "resolution_authorities": ["R2_AUTHORITY_QUALIFIED_ATTRIBUTION"]}]`

### P638:K2

Original candidates: 21; dedup callables: 21; removed siblings: 0.

- W50 original strategies: `{"cold_complement_2bet": 69, "fourier30_markov30_2bet": 33, "lag_reversion_2bet": 112, "midfreq_fourier_2bet": 58, "power_apriori_2bet": 143, "power_biglotto_deviation_2bet": 61, "power_biglotto_dm_dms_2bet": 6, "power_biglotto_echo_2bet": 81, "power_biglotto_enhanced_dual_2bet": 77, "power_biglotto_gemini_v1_2bet": 53, "power_biglotto_p0_echo_2bet": 110, "power_biglotto_smart_2bet": 8, "power_biglotto_two_bet_elite_2bet": 78, "power_biglotto_two_bet_final_2bet": 4, "power_biglotto_two_bet_optimizer_2bet": 52, "power_biglotto_two_bet_optimizer_v2_2bet": 143, "power_fourier_gap_rebound_2bet": 146, "power_fourier_rhythm_2bet": 135, "power_lead_lag_2bet": 132, "power_momentum_2bet": 153, "zonal_entropy_2bet": 129}`
- W50 original callables: `{"callable-sha256:6e762e738e59d3da01eb6f42aa4b01daacda15ebf83a1d957462666260266007": 132, "callable-sha256:870fda8fb0705b055a9999354e15c65487f0300ed906b21ab20188e52ba41f95": 143, "callable-sha256:89d2cb7f42ba0e6e52c91fdd41f9384198551cc4721c1e0b2161bc168f3ceb66": 129, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_cold_complement_tickets": 69, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_fourier30_markov30_tickets": 33, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_midfreq_fourier_tickets": 58, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_power_fourier_rhythm_tickets": 135, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_fourier_gap_rebound_tickets": 146, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_lag_reversion_tickets": 112, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_momentum_tickets": 153, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_deviation_tickets": 61, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_p0_echo_tickets": 110, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_echo_2bet": 81, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_gemini_v1_2bet": 53, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_smart_2bet": 8, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_two_bet_elite": 78, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_two_bet_final": 4, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_two_bet_optimizer": 52, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_two_bet_optimizer_v2": 143, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_enhanced_dual_2bet": 77, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_dm_dms_predict": 6}`
- W50 dedup strategies: `{"cold_complement_2bet": 69, "fourier30_markov30_2bet": 33, "lag_reversion_2bet": 112, "midfreq_fourier_2bet": 58, "power_apriori_2bet": 143, "power_biglotto_deviation_2bet": 61, "power_biglotto_dm_dms_2bet": 6, "power_biglotto_echo_2bet": 81, "power_biglotto_enhanced_dual_2bet": 77, "power_biglotto_gemini_v1_2bet": 53, "power_biglotto_p0_echo_2bet": 110, "power_biglotto_smart_2bet": 8, "power_biglotto_two_bet_elite_2bet": 78, "power_biglotto_two_bet_final_2bet": 4, "power_biglotto_two_bet_optimizer_2bet": 52, "power_biglotto_two_bet_optimizer_v2_2bet": 143, "power_fourier_gap_rebound_2bet": 146, "power_fourier_rhythm_2bet": 135, "power_lead_lag_2bet": 132, "power_momentum_2bet": 153, "zonal_entropy_2bet": 129}`
- W50 dedup callables: `{"callable-sha256:6e762e738e59d3da01eb6f42aa4b01daacda15ebf83a1d957462666260266007": 132, "callable-sha256:870fda8fb0705b055a9999354e15c65487f0300ed906b21ab20188e52ba41f95": 143, "callable-sha256:89d2cb7f42ba0e6e52c91fdd41f9384198551cc4721c1e0b2161bc168f3ceb66": 129, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_cold_complement_tickets": 69, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_fourier30_markov30_tickets": 33, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_midfreq_fourier_tickets": 58, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_power_fourier_rhythm_tickets": 135, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_fourier_gap_rebound_tickets": 146, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_lag_reversion_tickets": 112, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_momentum_tickets": 153, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_deviation_tickets": 61, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_p0_echo_tickets": 110, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_echo_2bet": 81, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_gemini_v1_2bet": 53, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_smart_2bet": 8, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_two_bet_elite": 78, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_two_bet_final": 4, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_two_bet_optimizer": 52, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_two_bet_optimizer_v2": 143, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_enhanced_dual_2bet": 77, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave6:_dm_dms_predict": 6}`
- W300 original strategies: `{"cold_complement_2bet": 21, "lag_reversion_2bet": 87, "power_apriori_2bet": 104, "power_biglotto_echo_2bet": 152, "power_biglotto_p0_echo_2bet": 45, "power_biglotto_two_bet_elite_2bet": 91, "power_biglotto_two_bet_optimizer_v2_2bet": 26, "power_fourier_gap_rebound_2bet": 435, "power_fourier_rhythm_2bet": 290, "power_lead_lag_2bet": 56, "power_momentum_2bet": 70, "zonal_entropy_2bet": 156}`
- W300 original callables: `{"callable-sha256:6e762e738e59d3da01eb6f42aa4b01daacda15ebf83a1d957462666260266007": 56, "callable-sha256:870fda8fb0705b055a9999354e15c65487f0300ed906b21ab20188e52ba41f95": 104, "callable-sha256:89d2cb7f42ba0e6e52c91fdd41f9384198551cc4721c1e0b2161bc168f3ceb66": 156, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_cold_complement_tickets": 21, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_power_fourier_rhythm_tickets": 290, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_fourier_gap_rebound_tickets": 435, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_lag_reversion_tickets": 87, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_momentum_tickets": 70, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_p0_echo_tickets": 45, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_echo_2bet": 152, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_two_bet_elite": 91, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_two_bet_optimizer_v2": 26}`
- W300 dedup strategies: `{"cold_complement_2bet": 21, "lag_reversion_2bet": 87, "power_apriori_2bet": 104, "power_biglotto_echo_2bet": 152, "power_biglotto_p0_echo_2bet": 45, "power_biglotto_two_bet_elite_2bet": 91, "power_biglotto_two_bet_optimizer_v2_2bet": 26, "power_fourier_gap_rebound_2bet": 435, "power_fourier_rhythm_2bet": 290, "power_lead_lag_2bet": 56, "power_momentum_2bet": 70, "zonal_entropy_2bet": 156}`
- W300 dedup callables: `{"callable-sha256:6e762e738e59d3da01eb6f42aa4b01daacda15ebf83a1d957462666260266007": 56, "callable-sha256:870fda8fb0705b055a9999354e15c65487f0300ed906b21ab20188e52ba41f95": 104, "callable-sha256:89d2cb7f42ba0e6e52c91fdd41f9384198551cc4721c1e0b2161bc168f3ceb66": 156, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_cold_complement_tickets": 21, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_power_fourier_rhythm_tickets": 290, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_fourier_gap_rebound_tickets": 435, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_lag_reversion_tickets": 87, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_momentum_tickets": 70, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_p0_echo_tickets": 45, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_echo_2bet": 152, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_two_bet_elite": 91, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_two_bet_optimizer_v2": 26}`
- W750 original strategies: `{"power_biglotto_two_bet_optimizer_v2_2bet": 18, "power_fourier_gap_rebound_2bet": 662, "power_fourier_rhythm_2bet": 193, "power_momentum_2bet": 110, "zonal_entropy_2bet": 100}`
- W750 original callables: `{"callable-sha256:89d2cb7f42ba0e6e52c91fdd41f9384198551cc4721c1e0b2161bc168f3ceb66": 100, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_power_fourier_rhythm_tickets": 193, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_fourier_gap_rebound_tickets": 662, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_momentum_tickets": 110, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_two_bet_optimizer_v2": 18}`
- W750 dedup strategies: `{"power_biglotto_two_bet_optimizer_v2_2bet": 18, "power_fourier_gap_rebound_2bet": 662, "power_fourier_rhythm_2bet": 193, "power_momentum_2bet": 110, "zonal_entropy_2bet": 100}`
- W750 dedup callables: `{"callable-sha256:89d2cb7f42ba0e6e52c91fdd41f9384198551cc4721c1e0b2161bc168f3ceb66": 100, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_power_fourier_rhythm_tickets": 193, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_fourier_gap_rebound_tickets": 662, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_momentum_tickets": 110, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_two_bet_optimizer_v2": 18}`
- Reduced callable families: `[]`

### P638:K3

Original candidates: 14; dedup callables: 14; removed siblings: 0.

- W50 original strategies: `{"fourier_rhythm_3bet": 112, "midfreq_fourier_mk_3bet": 293, "power_biglotto_asm_3bet": 100, "power_biglotto_cag_3bet": 15, "power_biglotto_diversified_ensemble_v6_3bet": 199, "power_biglotto_dms_3bet": 7, "power_biglotto_exhaustive_audit_3bet": 258, "power_biglotto_mwsc_3bet": 43, "power_biglotto_random_core_satellite_3bet": 82, "power_biglotto_random_zone_split_3bet": 179, "power_biglotto_tme_3bet": 177, "power_biglotto_zdp_3bet": 68, "power_biglotto_zone_split_3bet": 201, "power_precision_3bet": 99}`
- W50 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_fourier_rhythm_tickets": 112, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_midfreq_fourier_mk_tickets": 293, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_power_precision_tickets": 99, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_tme_3bet": 177, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_zone_split_3bet": 201, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_asm_3bet": 100, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_cag_3bet": 15, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_diversified_ensemble_v6": 199, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_dms_3bet": 7, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_exhaustive_audit_3bet": 258, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_mwsc_3bet": 43, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_random_core_satellite": 82, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_random_zone_split": 179, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_zdp_3bet": 68}`
- W50 dedup strategies: `{"fourier_rhythm_3bet": 112, "midfreq_fourier_mk_3bet": 293, "power_biglotto_asm_3bet": 100, "power_biglotto_cag_3bet": 15, "power_biglotto_diversified_ensemble_v6_3bet": 199, "power_biglotto_dms_3bet": 7, "power_biglotto_exhaustive_audit_3bet": 258, "power_biglotto_mwsc_3bet": 43, "power_biglotto_random_core_satellite_3bet": 82, "power_biglotto_random_zone_split_3bet": 179, "power_biglotto_tme_3bet": 177, "power_biglotto_zdp_3bet": 68, "power_biglotto_zone_split_3bet": 201, "power_precision_3bet": 99}`
- W50 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_fourier_rhythm_tickets": 112, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_midfreq_fourier_mk_tickets": 293, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_power_precision_tickets": 99, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_tme_3bet": 177, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_zone_split_3bet": 201, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_asm_3bet": 100, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_cag_3bet": 15, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_diversified_ensemble_v6": 199, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_dms_3bet": 7, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_exhaustive_audit_3bet": 258, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_mwsc_3bet": 43, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_random_core_satellite": 82, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_random_zone_split": 179, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_zdp_3bet": 68}`
- W300 original strategies: `{"fourier_rhythm_3bet": 17, "midfreq_fourier_mk_3bet": 597, "power_biglotto_diversified_ensemble_v6_3bet": 87, "power_biglotto_exhaustive_audit_3bet": 120, "power_biglotto_random_zone_split_3bet": 248, "power_biglotto_tme_3bet": 14, "power_biglotto_zone_split_3bet": 279, "power_precision_3bet": 221}`
- W300 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_fourier_rhythm_tickets": 17, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_midfreq_fourier_mk_tickets": 597, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_power_precision_tickets": 221, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_tme_3bet": 14, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_zone_split_3bet": 279, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_diversified_ensemble_v6": 87, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_exhaustive_audit_3bet": 120, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_random_zone_split": 248}`
- W300 dedup strategies: `{"fourier_rhythm_3bet": 17, "midfreq_fourier_mk_3bet": 597, "power_biglotto_diversified_ensemble_v6_3bet": 87, "power_biglotto_exhaustive_audit_3bet": 120, "power_biglotto_random_zone_split_3bet": 248, "power_biglotto_tme_3bet": 14, "power_biglotto_zone_split_3bet": 279, "power_precision_3bet": 221}`
- W300 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_fourier_rhythm_tickets": 17, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_midfreq_fourier_mk_tickets": 597, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_power_precision_tickets": 221, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_tme_3bet": 14, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_zone_split_3bet": 279, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_diversified_ensemble_v6": 87, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_exhaustive_audit_3bet": 120, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_random_zone_split": 248}`
- W750 original strategies: `{"midfreq_fourier_mk_3bet": 503, "power_biglotto_exhaustive_audit_3bet": 55, "power_biglotto_random_zone_split_3bet": 184, "power_biglotto_zone_split_3bet": 385, "power_precision_3bet": 6}`
- W750 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_midfreq_fourier_mk_tickets": 503, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_power_precision_tickets": 6, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_zone_split_3bet": 385, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_exhaustive_audit_3bet": 55, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_random_zone_split": 184}`
- W750 dedup strategies: `{"midfreq_fourier_mk_3bet": 503, "power_biglotto_exhaustive_audit_3bet": 55, "power_biglotto_random_zone_split_3bet": 184, "power_biglotto_zone_split_3bet": 385, "power_precision_3bet": 6}`
- W750 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_midfreq_fourier_mk_tickets": 503, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_power_precision_tickets": 6, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_zone_split_3bet": 385, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_exhaustive_audit_3bet": 55, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave5:_random_zone_split": 184}`
- Reduced callable families: `[]`

### P638:K4

Original candidates: 3; dedup callables: 3; removed siblings: 0.

- W50 original strategies: `{"power_apriori_ext_4bet": 521, "power_biglotto_tme_optimizer_4bet": 391, "pp3_freqort_4bet": 920}`
- W50 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_pp3_freqort_tickets": 920, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_apriori_ext_4bet_tickets": 521, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_tme_optimizer": 391}`
- W50 dedup strategies: `{"power_apriori_ext_4bet": 521, "power_biglotto_tme_optimizer_4bet": 391, "pp3_freqort_4bet": 920}`
- W50 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_pp3_freqort_tickets": 920, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_apriori_ext_4bet_tickets": 521, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_tme_optimizer": 391}`
- W300 original strategies: `{"power_apriori_ext_4bet": 255, "power_biglotto_tme_optimizer_4bet": 65, "pp3_freqort_4bet": 1262}`
- W300 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_pp3_freqort_tickets": 1262, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_apriori_ext_4bet_tickets": 255, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_tme_optimizer": 65}`
- W300 dedup strategies: `{"power_apriori_ext_4bet": 255, "power_biglotto_tme_optimizer_4bet": 65, "pp3_freqort_4bet": 1262}`
- W300 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_pp3_freqort_tickets": 1262, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_apriori_ext_4bet_tickets": 255, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_tme_optimizer": 65}`
- W750 original strategies: `{"power_apriori_ext_4bet": 76, "pp3_freqort_4bet": 1056}`
- W750 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_pp3_freqort_tickets": 1056, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_apriori_ext_4bet_tickets": 76}`
- W750 dedup strategies: `{"power_apriori_ext_4bet": 76, "pp3_freqort_4bet": 1056}`
- W750 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_pp3_freqort_tickets": 1056, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave2:_apriori_ext_4bet_tickets": 76}`
- Reduced callable families: `[]`

### P638:K5

Original candidates: 3; dedup callables: 3; removed siblings: 0.

- W50 original strategies: `{"power_biglotto_five_me_5bet": 844, "power_biglotto_zone_balance_5bet": 48, "power_orthogonal_5bet": 961}`
- W50 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_power_orthogonal_tickets": 961, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_zone_balance_tickets": 48, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_five_me_5bet": 844}`
- W50 dedup strategies: `{"power_biglotto_five_me_5bet": 844, "power_biglotto_zone_balance_5bet": 48, "power_orthogonal_5bet": 961}`
- W50 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_power_orthogonal_tickets": 961, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_zone_balance_tickets": 48, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_five_me_5bet": 844}`
- W300 original strategies: `{"power_biglotto_five_me_5bet": 688, "power_orthogonal_5bet": 915}`
- W300 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_power_orthogonal_tickets": 915, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_five_me_5bet": 688}`
- W300 dedup strategies: `{"power_biglotto_five_me_5bet": 688, "power_orthogonal_5bet": 915}`
- W300 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_power_orthogonal_tickets": 915, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_five_me_5bet": 688}`
- W750 original strategies: `{"power_biglotto_five_me_5bet": 286, "power_orthogonal_5bet": 867}`
- W750 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_power_orthogonal_tickets": 867, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_five_me_5bet": 286}`
- W750 dedup strategies: `{"power_biglotto_five_me_5bet": 286, "power_orthogonal_5bet": 867}`
- W750 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave1:_power_orthogonal_tickets": 867, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_five_me_5bet": 286}`
- Reduced callable families: `[]`

### P638:K7

Original candidates: 3; dedup callables: 3; removed siblings: 0.

- W50 original strategies: `{"power_biglotto_elite_7bet": 1170, "power_biglotto_gemini_phase2_7bet": 613}`
- W50 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_gemini_phase2_tickets": 613, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_elite_7bet": 1170}`
- W50 dedup strategies: `{"power_biglotto_elite_7bet": 1170, "power_biglotto_gemini_phase2_7bet": 613}`
- W50 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_gemini_phase2_tickets": 613, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_elite_7bet": 1170}`
- W300 original strategies: `{"power_biglotto_elite_7bet": 1389, "power_biglotto_gemini_phase2_7bet": 144}`
- W300 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_gemini_phase2_tickets": 144, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_elite_7bet": 1389}`
- W300 dedup strategies: `{"power_biglotto_elite_7bet": 1389, "power_biglotto_gemini_phase2_7bet": 144}`
- W300 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave3:_gemini_phase2_tickets": 144, "selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_elite_7bet": 1389}`
- W750 original strategies: `{"power_biglotto_elite_7bet": 1083}`
- W750 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_elite_7bet": 1083}`
- W750 dedup strategies: `{"power_biglotto_elite_7bet": 1083}`
- W750 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_elite_7bet": 1083}`
- Reduced callable families: `[]`

### P638:K10

Original candidates: 1; dedup callables: 1; removed siblings: 0.

- W50 original strategies: `{"power_biglotto_backtest_10bet": 1853}`
- W50 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_backtest_10bet": 1853}`
- W50 dedup strategies: `{"power_biglotto_backtest_10bet": 1853}`
- W50 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_backtest_10bet": 1853}`
- W300 original strategies: `{"power_biglotto_backtest_10bet": 1603}`
- W300 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_backtest_10bet": 1603}`
- W300 dedup strategies: `{"power_biglotto_backtest_10bet": 1603}`
- W300 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_backtest_10bet": 1603}`
- W750 original strategies: `{"power_biglotto_backtest_10bet": 1153}`
- W750 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_backtest_10bet": 1153}`
- W750 dedup strategies: `{"power_biglotto_backtest_10bet": 1153}`
- W750 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_backtest_10bet": 1153}`
- Reduced callable families: `[]`

### P638:K11

Original candidates: 1; dedup callables: 1; removed siblings: 0.

- W50 original strategies: `{"power_biglotto_variant_history_11bet": 1853}`
- W50 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_variant_history_11bet": 1853}`
- W50 dedup strategies: `{"power_biglotto_variant_history_11bet": 1853}`
- W50 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_variant_history_11bet": 1853}`
- W300 original strategies: `{"power_biglotto_variant_history_11bet": 1603}`
- W300 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_variant_history_11bet": 1603}`
- W300 dedup strategies: `{"power_biglotto_variant_history_11bet": 1603}`
- W300 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_variant_history_11bet": 1603}`
- W750 original strategies: `{"power_biglotto_variant_history_11bet": 1153}`
- W750 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_variant_history_11bet": 1153}`
- W750 dedup strategies: `{"power_biglotto_variant_history_11bet": 1153}`
- W750 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_variant_history_11bet": 1153}`
- Reduced callable families: `[]`

### P638:K12

Original candidates: 1; dedup callables: 1; removed siblings: 0.

- W50 original strategies: `{"power_biglotto_core_satellite_12bet": 1853}`
- W50 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_core_satellite_12bet": 1853}`
- W50 dedup strategies: `{"power_biglotto_core_satellite_12bet": 1853}`
- W50 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_core_satellite_12bet": 1853}`
- W300 original strategies: `{"power_biglotto_core_satellite_12bet": 1603}`
- W300 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_core_satellite_12bet": 1603}`
- W300 dedup strategies: `{"power_biglotto_core_satellite_12bet": 1603}`
- W300 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_core_satellite_12bet": 1603}`
- W750 original strategies: `{"power_biglotto_core_satellite_12bet": 1153}`
- W750 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_core_satellite_12bet": 1153}`
- W750 dedup strategies: `{"power_biglotto_core_satellite_12bet": 1153}`
- W750 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_core_satellite_12bet": 1153}`
- Reduced callable families: `[]`

### P638:K25

Original candidates: 1; dedup callables: 1; removed siblings: 0.

- W50 original strategies: `{"power_biglotto_auto_optimizer_alpha_25bet": 1853}`
- W50 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_auto_optimizer_25bet": 1853}`
- W50 dedup strategies: `{"power_biglotto_auto_optimizer_alpha_25bet": 1853}`
- W50 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_auto_optimizer_25bet": 1853}`
- W300 original strategies: `{"power_biglotto_auto_optimizer_alpha_25bet": 1603}`
- W300 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_auto_optimizer_25bet": 1603}`
- W300 dedup strategies: `{"power_biglotto_auto_optimizer_alpha_25bet": 1603}`
- W300 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_auto_optimizer_25bet": 1603}`
- W750 original strategies: `{"power_biglotto_auto_optimizer_alpha_25bet": 1153}`
- W750 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_auto_optimizer_25bet": 1153}`
- W750 dedup strategies: `{"power_biglotto_auto_optimizer_alpha_25bet": 1153}`
- W750 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.powerlotto_wave4:_auto_optimizer_25bet": 1153}`
- Reduced callable families: `[]`

### T539:K1

Original candidates: 25; dedup callables: 12; removed siblings: 13.

- W50 original strategies: `{"539_3bet_orthogonal": 354, "acb_markov_midfreq": 494, "daily539_f4cold": 482, "daily539_markov_cold": 358, "p0b_539_3bet_f_cold_fmid": 54, "t539_biglotto_attention_replay_1bet": 339, "t539_biglotto_cold_hunter_1bet": 333, "t539_biglotto_dms_1bet": 443, "t539_biglotto_dynamic_frequency_1bet": 292, "t539_biglotto_gap_pressure_1bet": 234, "t539_biglotto_graph_predictor_1bet": 270, "t539_biglotto_hot_cooccurrence_1bet": 281, "t539_biglotto_moderate_rank_1bet": 344, "t539_biglotto_optimized_ensemble_1bet": 354, "t539_biglotto_pure_cold_1bet": 193, "t539_biglotto_rebound_aware_1bet": 209, "t539_biglotto_short_window_deviation_1bet": 295, "t539_biglotto_zone_momentum_1bet": 218, "zone_gap_3bet_539": 133}`
- W50 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_acb_markov_midfreq:Daily539AcbMarkovMidfreqAdapter.get_one_bet": 494, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_batch15:_Daily539Batch15SingleAdapter.get_one_bet": 2269, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 1536, "selector-supplement-callable:lottolab.strategies.adapters.daily539_fourier4:Daily539P0bFourierColdFmidAdapter.get_one_bet": 54, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4ColdAdapter.get_bets": 482, "selector-supplement-callable:lottolab.strategies.adapters.daily539_single_legacy:Daily539Orthogonal3BetAdapter.get_one_bet": 354, "selector-supplement-callable:lottolab.strategies.adapters.daily539_wave1:Daily539MarkovColdAdapter.get_one_bet": 358, "selector-supplement-callable:lottolab.strategies.adapters.daily539_zone_gap:Daily539ZoneGap3BetAdapter.get_one_bet": 133}`
- W50 dedup strategies: `{"539_3bet_orthogonal": 872, "acb_markov_midfreq": 893, "daily539_f4cold": 936, "daily539_markov_cold": 681, "p0b_539_3bet_f_cold_fmid": 87, "t539_biglotto_attention_replay_1bet": 854, "t539_biglotto_cold_hunter_1bet": 848, "zone_gap_3bet_539": 509}`
- W50 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_acb_markov_midfreq:Daily539AcbMarkovMidfreqAdapter.get_one_bet": 893, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_batch15:_Daily539Batch15SingleAdapter.get_one_bet": 848, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 854, "selector-supplement-callable:lottolab.strategies.adapters.daily539_fourier4:Daily539P0bFourierColdFmidAdapter.get_one_bet": 87, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4ColdAdapter.get_bets": 936, "selector-supplement-callable:lottolab.strategies.adapters.daily539_single_legacy:Daily539Orthogonal3BetAdapter.get_one_bet": 872, "selector-supplement-callable:lottolab.strategies.adapters.daily539_wave1:Daily539MarkovColdAdapter.get_one_bet": 681, "selector-supplement-callable:lottolab.strategies.adapters.daily539_zone_gap:Daily539ZoneGap3BetAdapter.get_one_bet": 509}`
- W300 original strategies: `{"539_3bet_orthogonal": 341, "acb_markov_midfreq": 253, "daily539_f4cold": 203, "daily539_markov_cold": 73, "p0b_539_3bet_f_cold_fmid": 450, "t539_biglotto_attention_replay_1bet": 179, "t539_biglotto_cold_hunter_1bet": 562, "t539_biglotto_dms_1bet": 691, "t539_biglotto_dynamic_frequency_1bet": 146, "t539_biglotto_graph_predictor_1bet": 185, "t539_biglotto_hot_cooccurrence_1bet": 298, "t539_biglotto_moderate_rank_1bet": 123, "t539_biglotto_optimized_ensemble_1bet": 618, "t539_biglotto_pure_cold_1bet": 289, "t539_biglotto_rebound_aware_1bet": 110, "t539_biglotto_short_window_deviation_1bet": 468, "t539_biglotto_zone_momentum_1bet": 368, "zone_gap_3bet_539": 73}`
- W300 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_acb_markov_midfreq:Daily539AcbMarkovMidfreqAdapter.get_one_bet": 253, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_batch15:_Daily539Batch15SingleAdapter.get_one_bet": 2611, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 1426, "selector-supplement-callable:lottolab.strategies.adapters.daily539_fourier4:Daily539P0bFourierColdFmidAdapter.get_one_bet": 450, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4ColdAdapter.get_bets": 203, "selector-supplement-callable:lottolab.strategies.adapters.daily539_single_legacy:Daily539Orthogonal3BetAdapter.get_one_bet": 341, "selector-supplement-callable:lottolab.strategies.adapters.daily539_wave1:Daily539MarkovColdAdapter.get_one_bet": 73, "selector-supplement-callable:lottolab.strategies.adapters.daily539_zone_gap:Daily539ZoneGap3BetAdapter.get_one_bet": 73}`
- W300 dedup strategies: `{"539_3bet_orthogonal": 601, "acb_markov_midfreq": 549, "daily539_f4cold": 427, "daily539_markov_cold": 607, "p0b_539_3bet_f_cold_fmid": 597, "t539_biglotto_attention_replay_1bet": 755, "t539_biglotto_cold_hunter_1bet": 979, "zone_gap_3bet_539": 915}`
- W300 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_acb_markov_midfreq:Daily539AcbMarkovMidfreqAdapter.get_one_bet": 549, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_batch15:_Daily539Batch15SingleAdapter.get_one_bet": 979, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 755, "selector-supplement-callable:lottolab.strategies.adapters.daily539_fourier4:Daily539P0bFourierColdFmidAdapter.get_one_bet": 597, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4ColdAdapter.get_bets": 427, "selector-supplement-callable:lottolab.strategies.adapters.daily539_single_legacy:Daily539Orthogonal3BetAdapter.get_one_bet": 601, "selector-supplement-callable:lottolab.strategies.adapters.daily539_wave1:Daily539MarkovColdAdapter.get_one_bet": 607, "selector-supplement-callable:lottolab.strategies.adapters.daily539_zone_gap:Daily539ZoneGap3BetAdapter.get_one_bet": 915}`
- W750 original strategies: `{"539_3bet_orthogonal": 245, "acb_markov_midfreq": 539, "daily539_f4cold": 184, "daily539_markov_cold": 40, "p0b_539_3bet_f_cold_fmid": 520, "t539_biglotto_attention_replay_1bet": 144, "t539_biglotto_cold_hunter_1bet": 585, "t539_biglotto_dms_1bet": 870, "t539_biglotto_dynamic_frequency_1bet": 89, "t539_biglotto_gap_pressure_1bet": 35, "t539_biglotto_graph_predictor_1bet": 5, "t539_biglotto_hot_cooccurrence_1bet": 296, "t539_biglotto_moderate_rank_1bet": 51, "t539_biglotto_optimized_ensemble_1bet": 479, "t539_biglotto_pure_cold_1bet": 576, "t539_biglotto_rebound_aware_1bet": 78, "t539_biglotto_short_window_deviation_1bet": 84, "t539_biglotto_zone_momentum_1bet": 109, "zone_gap_3bet_539": 51}`
- W750 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_acb_markov_midfreq:Daily539AcbMarkovMidfreqAdapter.get_one_bet": 539, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_batch15:_Daily539Batch15SingleAdapter.get_one_bet": 2388, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 1013, "selector-supplement-callable:lottolab.strategies.adapters.daily539_fourier4:Daily539P0bFourierColdFmidAdapter.get_one_bet": 520, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4ColdAdapter.get_bets": 184, "selector-supplement-callable:lottolab.strategies.adapters.daily539_single_legacy:Daily539Orthogonal3BetAdapter.get_one_bet": 245, "selector-supplement-callable:lottolab.strategies.adapters.daily539_wave1:Daily539MarkovColdAdapter.get_one_bet": 40, "selector-supplement-callable:lottolab.strategies.adapters.daily539_zone_gap:Daily539ZoneGap3BetAdapter.get_one_bet": 51}`
- W750 dedup strategies: `{"539_3bet_orthogonal": 600, "acb_markov_midfreq": 754, "daily539_f4cold": 195, "daily539_markov_cold": 548, "p0b_539_3bet_f_cold_fmid": 533, "t539_biglotto_attention_replay_1bet": 827, "t539_biglotto_cold_hunter_1bet": 1056, "zone_gap_3bet_539": 467}`
- W750 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_acb_markov_midfreq:Daily539AcbMarkovMidfreqAdapter.get_one_bet": 754, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_batch15:_Daily539Batch15SingleAdapter.get_one_bet": 1056, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 827, "selector-supplement-callable:lottolab.strategies.adapters.daily539_fourier4:Daily539P0bFourierColdFmidAdapter.get_one_bet": 533, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4ColdAdapter.get_bets": 195, "selector-supplement-callable:lottolab.strategies.adapters.daily539_single_legacy:Daily539Orthogonal3BetAdapter.get_one_bet": 600, "selector-supplement-callable:lottolab.strategies.adapters.daily539_wave1:Daily539MarkovColdAdapter.get_one_bet": 548, "selector-supplement-callable:lottolab.strategies.adapters.daily539_zone_gap:Daily539ZoneGap3BetAdapter.get_one_bet": 467}`
- Reduced callable families: `[{"authority_qualified_callable_identity": ["T539_HISTORICAL_SQLITE", "T539", 1, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_batch15:_Daily539Batch15SingleAdapter.get_one_bet"], "callable_identity": "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_batch15:_Daily539Batch15SingleAdapter.get_one_bet", "callable_labels": ["lottolab.strategies.adapters.daily539_biglotto_batch15:_Daily539Batch15SingleAdapter.get_one_bet"], "member_count": 8, "member_identities": [["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_cold_hunter_1bet", "v0.1-t539-batch15"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_dms_1bet", "v0.1-t539-batch15"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_gap_pressure_1bet", "v0.1-t539-batch15"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_moderate_rank_1bet", "v0.1-t539-batch15"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_pure_cold_1bet", "v0.1-t539-batch15"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_rebound_aware_1bet", "v0.1-t539-batch15"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_short_window_deviation_1bet", "v0.1-t539-batch15"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_zone_momentum_1bet", "v0.1-t539-batch15"]], "removed_sibling_count": 7, "removed_sibling_identities": [["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_dms_1bet", "v0.1-t539-batch15"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_gap_pressure_1bet", "v0.1-t539-batch15"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_moderate_rank_1bet", "v0.1-t539-batch15"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_pure_cold_1bet", "v0.1-t539-batch15"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_rebound_aware_1bet", "v0.1-t539-batch15"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_short_window_deviation_1bet", "v0.1-t539-batch15"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_zone_momentum_1bet", "v0.1-t539-batch15"]], "representative_identity": ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_cold_hunter_1bet", "v0.1-t539-batch15"], "representative_rule": "LEXICOGRAPHIC_MINIMUM_COMPLETE_AUTHORITY_QUALIFIED_IDENTITY", "resolution_authorities": ["R2_AUTHORITY_QUALIFIED_ATTRIBUTION"]}, {"authority_qualified_callable_identity": ["T539_HISTORICAL_SQLITE", "T539", 1, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets"], "callable_identity": "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets", "callable_labels": ["lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets"], "member_count": 7, "member_identities": [["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_attention_replay_1bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_dynamic_frequency_1bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_graph_predictor_1bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_hot_cooccurrence_1bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_hpsb_1bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_must_hit_top6_1bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_optimized_ensemble_1bet", "v0.1-t539-cross-lottery-r2"]], "removed_sibling_count": 6, "removed_sibling_identities": [["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_dynamic_frequency_1bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_graph_predictor_1bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_hot_cooccurrence_1bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_hpsb_1bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_must_hit_top6_1bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_optimized_ensemble_1bet", "v0.1-t539-cross-lottery-r2"]], "representative_identity": ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_attention_replay_1bet", "v0.1-t539-cross-lottery-r2"], "representative_rule": "LEXICOGRAPHIC_MINIMUM_COMPLETE_AUTHORITY_QUALIFIED_IDENTITY", "resolution_authorities": ["R2_AUTHORITY_QUALIFIED_ATTRIBUTION", "SEALED_SELECTOR_SOURCE_STATIC_RESOLUTION"]}]`

### T539:K2

Original candidates: 13; dedup callables: 3; removed siblings: 10.

- W50 original strategies: `{"midfreq_acb_2bet": 1049, "midfreq_fourier_2bet": 342, "t539_biglotto_deviation_2bet": 519, "t539_biglotto_dm_dms_2bet": 495, "t539_biglotto_echo_2bet": 660, "t539_biglotto_enhanced_dual_2bet": 521, "t539_biglotto_gemini_v1_2bet": 295, "t539_biglotto_p0_echo_2bet": 341, "t539_biglotto_smart_2bet": 415, "t539_biglotto_two_bet_elite_2bet": 623, "t539_biglotto_two_bet_final_2bet": 152, "t539_biglotto_two_bet_optimizer_2bet": 45, "t539_biglotto_two_bet_optimizer_v2_2bet": 323}`
- W50 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_batch15:Daily539BigLottoDmDmsAdapter.get_bets": 495, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 3894, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_frequency:_Daily539PortfolioAdapter.get_bets": 1391}`
- W50 dedup strategies: `{"midfreq_acb_2bet": 2248, "t539_biglotto_deviation_2bet": 1882, "t539_biglotto_dm_dms_2bet": 1650}`
- W50 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_batch15:Daily539BigLottoDmDmsAdapter.get_bets": 1650, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 1882, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_frequency:_Daily539PortfolioAdapter.get_bets": 2248}`
- W300 original strategies: `{"midfreq_acb_2bet": 1304, "midfreq_fourier_2bet": 151, "t539_biglotto_deviation_2bet": 826, "t539_biglotto_dm_dms_2bet": 218, "t539_biglotto_echo_2bet": 768, "t539_biglotto_enhanced_dual_2bet": 193, "t539_biglotto_p0_echo_2bet": 203, "t539_biglotto_smart_2bet": 504, "t539_biglotto_two_bet_elite_2bet": 1128, "t539_biglotto_two_bet_optimizer_2bet": 11, "t539_biglotto_two_bet_optimizer_v2_2bet": 224}`
- W300 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_batch15:Daily539BigLottoDmDmsAdapter.get_bets": 218, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 3857, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_frequency:_Daily539PortfolioAdapter.get_bets": 1455}`
- W300 dedup strategies: `{"midfreq_acb_2bet": 2431, "t539_biglotto_deviation_2bet": 2084, "t539_biglotto_dm_dms_2bet": 1015}`
- W300 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_batch15:Daily539BigLottoDmDmsAdapter.get_bets": 1015, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 2084, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_frequency:_Daily539PortfolioAdapter.get_bets": 2431}`
- W750 original strategies: `{"midfreq_acb_2bet": 1509, "midfreq_fourier_2bet": 4, "t539_biglotto_deviation_2bet": 869, "t539_biglotto_echo_2bet": 899, "t539_biglotto_enhanced_dual_2bet": 86, "t539_biglotto_p0_echo_2bet": 114, "t539_biglotto_smart_2bet": 191, "t539_biglotto_two_bet_elite_2bet": 1408}`
- W750 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 3567, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_frequency:_Daily539PortfolioAdapter.get_bets": 1513}`
- W750 dedup strategies: `{"midfreq_acb_2bet": 2845, "t539_biglotto_deviation_2bet": 1772, "t539_biglotto_dm_dms_2bet": 463}`
- W750 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_batch15:Daily539BigLottoDmDmsAdapter.get_bets": 463, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 1772, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_frequency:_Daily539PortfolioAdapter.get_bets": 2845}`
- Reduced callable families: `[{"authority_qualified_callable_identity": ["T539_HISTORICAL_SQLITE", "T539", 2, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets"], "callable_identity": "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets", "callable_labels": ["lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets"], "member_count": 10, "member_identities": [["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_deviation_2bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_echo_2bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_enhanced_dual_2bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_gemini_v1_2bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_p0_echo_2bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_smart_2bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_two_bet_elite_2bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_two_bet_final_2bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_two_bet_optimizer_2bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_two_bet_optimizer_v2_2bet", "v0.1-t539-cross-lottery-r2"]], "removed_sibling_count": 9, "removed_sibling_identities": [["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_echo_2bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_enhanced_dual_2bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_gemini_v1_2bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_p0_echo_2bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_smart_2bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_two_bet_elite_2bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_two_bet_final_2bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_two_bet_optimizer_2bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_two_bet_optimizer_v2_2bet", "v0.1-t539-cross-lottery-r2"]], "representative_identity": ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_deviation_2bet", "v0.1-t539-cross-lottery-r2"], "representative_rule": "LEXICOGRAPHIC_MINIMUM_COMPLETE_AUTHORITY_QUALIFIED_IDENTITY", "resolution_authorities": ["R2_AUTHORITY_QUALIFIED_ATTRIBUTION"]}, {"authority_qualified_callable_identity": ["T539_HISTORICAL_SQLITE", "T539", 2, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_frequency:_Daily539PortfolioAdapter.get_bets"], "callable_identity": "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_frequency:_Daily539PortfolioAdapter.get_bets", "callable_labels": ["lottolab.strategies.adapters.daily539_portfolio_frequency:_Daily539PortfolioAdapter.get_bets"], "member_count": 2, "member_identities": [["T539_HISTORICAL_SQLITE", "T539", "midfreq_acb_2bet", "v0.1"], ["T539_HISTORICAL_SQLITE", "T539", "midfreq_fourier_2bet", "v0.1"]], "removed_sibling_count": 1, "removed_sibling_identities": [["T539_HISTORICAL_SQLITE", "T539", "midfreq_fourier_2bet", "v0.1"]], "representative_identity": ["T539_HISTORICAL_SQLITE", "T539", "midfreq_acb_2bet", "v0.1"], "representative_rule": "LEXICOGRAPHIC_MINIMUM_COMPLETE_AUTHORITY_QUALIFIED_IDENTITY", "resolution_authorities": ["R2_AUTHORITY_QUALIFIED_ATTRIBUTION"]}]`

### T539:K3

Original candidates: 13; dedup callables: 3; removed siblings: 10.

- W50 original strategies: `{"acb_markov_midfreq_3bet": 906, "daily539_f4cold_3bet": 1155, "t539_biglotto_asm_3bet": 123, "t539_biglotto_cag_3bet": 121, "t539_biglotto_diversified_ensemble_v6_3bet": 488, "t539_biglotto_dms_3bet": 272, "t539_biglotto_exhaustive_audit_3bet": 717, "t539_biglotto_mwsc_3bet": 345, "t539_biglotto_random_core_satellite_3bet": 54, "t539_biglotto_random_zone_split_3bet": 647, "t539_biglotto_tme_3bet": 314, "t539_biglotto_zdp_3bet": 167, "t539_biglotto_zone_split_3bet": 471}`
- W50 original callables: `{"callable-sha256:8d315f03ca35764733727ebad1d644ab144ed27061722c5b97d33038895351ad": 906, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 3719, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4Cold3BetAdapter.get_bets": 1155}`
- W50 dedup strategies: `{"acb_markov_midfreq_3bet": 2340, "daily539_f4cold_3bet": 2706, "t539_biglotto_asm_3bet": 734}`
- W50 dedup callables: `{"callable-sha256:8d315f03ca35764733727ebad1d644ab144ed27061722c5b97d33038895351ad": 2340, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 734, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4Cold3BetAdapter.get_bets": 2706}`
- W300 original strategies: `{"acb_markov_midfreq_3bet": 1126, "daily539_f4cold_3bet": 1344, "t539_biglotto_diversified_ensemble_v6_3bet": 382, "t539_biglotto_dms_3bet": 16, "t539_biglotto_exhaustive_audit_3bet": 891, "t539_biglotto_mwsc_3bet": 149, "t539_biglotto_random_zone_split_3bet": 601, "t539_biglotto_tme_3bet": 87, "t539_biglotto_zdp_3bet": 8, "t539_biglotto_zone_split_3bet": 926}`
- W300 original callables: `{"callable-sha256:8d315f03ca35764733727ebad1d644ab144ed27061722c5b97d33038895351ad": 1126, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 3060, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4Cold3BetAdapter.get_bets": 1344}`
- W300 dedup strategies: `{"acb_markov_midfreq_3bet": 2423, "daily539_f4cold_3bet": 3082, "t539_biglotto_asm_3bet": 25}`
- W300 dedup callables: `{"callable-sha256:8d315f03ca35764733727ebad1d644ab144ed27061722c5b97d33038895351ad": 2423, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 25, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4Cold3BetAdapter.get_bets": 3082}`
- W750 original strategies: `{"acb_markov_midfreq_3bet": 709, "daily539_f4cold_3bet": 1991, "t539_biglotto_diversified_ensemble_v6_3bet": 142, "t539_biglotto_exhaustive_audit_3bet": 664, "t539_biglotto_random_zone_split_3bet": 441, "t539_biglotto_tme_3bet": 5, "t539_biglotto_zone_split_3bet": 1128}`
- W750 original callables: `{"callable-sha256:8d315f03ca35764733727ebad1d644ab144ed27061722c5b97d33038895351ad": 709, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 2380, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4Cold3BetAdapter.get_bets": 1991}`
- W750 dedup strategies: `{"acb_markov_midfreq_3bet": 1801, "daily539_f4cold_3bet": 3279}`
- W750 dedup callables: `{"callable-sha256:8d315f03ca35764733727ebad1d644ab144ed27061722c5b97d33038895351ad": 1801, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4Cold3BetAdapter.get_bets": 3279}`
- Reduced callable families: `[{"authority_qualified_callable_identity": ["T539_HISTORICAL_SQLITE", "T539", 3, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets"], "callable_identity": "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets", "callable_labels": ["lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets"], "member_count": 11, "member_identities": [["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_asm_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_cag_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_diversified_ensemble_v6_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_dms_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_exhaustive_audit_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_mwsc_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_random_core_satellite_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_random_zone_split_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_tme_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_zdp_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_zone_split_3bet", "v0.1-t539-cross-lottery-r2"]], "removed_sibling_count": 10, "removed_sibling_identities": [["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_cag_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_diversified_ensemble_v6_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_dms_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_exhaustive_audit_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_mwsc_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_random_core_satellite_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_random_zone_split_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_tme_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_zdp_3bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_zone_split_3bet", "v0.1-t539-cross-lottery-r2"]], "representative_identity": ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_asm_3bet", "v0.1-t539-cross-lottery-r2"], "representative_rule": "LEXICOGRAPHIC_MINIMUM_COMPLETE_AUTHORITY_QUALIFIED_IDENTITY", "resolution_authorities": ["R2_AUTHORITY_QUALIFIED_ATTRIBUTION"]}]`

### T539:K4

Original candidates: 1; dedup callables: 1; removed siblings: 0.

- W50 original strategies: `{"t539_biglotto_tme_optimizer_4bet": 5879}`
- W50 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5879}`
- W50 dedup strategies: `{"t539_biglotto_tme_optimizer_4bet": 5879}`
- W50 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5879}`
- W300 original strategies: `{"t539_biglotto_tme_optimizer_4bet": 5629}`
- W300 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5629}`
- W300 dedup strategies: `{"t539_biglotto_tme_optimizer_4bet": 5629}`
- W300 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5629}`
- W750 original strategies: `{"t539_biglotto_tme_optimizer_4bet": 5179}`
- W750 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5179}`
- W750 dedup strategies: `{"t539_biglotto_tme_optimizer_4bet": 5179}`
- W750 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5179}`
- Reduced callable families: `[]`

### T539:K5

Original candidates: 3; dedup callables: 2; removed siblings: 1.

- W50 original strategies: `{"daily539_f4cold_5bet": 4656, "t539_biglotto_five_me_5bet": 1124}`
- W50 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 1124, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4Cold5BetAdapter.get_bets": 4656}`
- W50 dedup strategies: `{"daily539_f4cold_5bet": 4656, "t539_biglotto_five_me_5bet": 1124}`
- W50 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 1124, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4Cold5BetAdapter.get_bets": 4656}`
- W300 original strategies: `{"daily539_f4cold_5bet": 5486, "t539_biglotto_five_me_5bet": 44}`
- W300 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 44, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4Cold5BetAdapter.get_bets": 5486}`
- W300 dedup strategies: `{"daily539_f4cold_5bet": 5486, "t539_biglotto_five_me_5bet": 44}`
- W300 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 44, "selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4Cold5BetAdapter.get_bets": 5486}`
- W750 original strategies: `{"daily539_f4cold_5bet": 5080}`
- W750 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4Cold5BetAdapter.get_bets": 5080}`
- W750 dedup strategies: `{"daily539_f4cold_5bet": 5080}`
- W750 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_portfolio_f4cold:Daily539F4Cold5BetAdapter.get_bets": 5080}`
- Reduced callable families: `[{"authority_qualified_callable_identity": ["T539_HISTORICAL_SQLITE", "T539", 5, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets"], "callable_identity": "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets", "callable_labels": ["lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets"], "member_count": 2, "member_identities": [["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_five_me_5bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_zone_balance_5bet", "v0.1-t539-cross-lottery-r2"]], "removed_sibling_count": 1, "removed_sibling_identities": [["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_zone_balance_5bet", "v0.1-t539-cross-lottery-r2"]], "representative_identity": ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_five_me_5bet", "v0.1-t539-cross-lottery-r2"], "representative_rule": "LEXICOGRAPHIC_MINIMUM_COMPLETE_AUTHORITY_QUALIFIED_IDENTITY", "resolution_authorities": ["R2_AUTHORITY_QUALIFIED_ATTRIBUTION", "SEALED_SELECTOR_SOURCE_STATIC_RESOLUTION"]}]`

### T539:K7

Original candidates: 3; dedup callables: 1; removed siblings: 2.

- W50 original strategies: `{"t539_biglotto_elite_7bet": 1152, "t539_biglotto_gemini_phase2_7bet": 4620, "t539_biglotto_high_prize_trend_7bet": 8}`
- W50 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5780}`
- W50 dedup strategies: `{"t539_biglotto_elite_7bet": 5780}`
- W50 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5780}`
- W300 original strategies: `{"t539_biglotto_elite_7bet": 73, "t539_biglotto_gemini_phase2_7bet": 5457}`
- W300 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5530}`
- W300 dedup strategies: `{"t539_biglotto_elite_7bet": 5530}`
- W300 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5530}`
- W750 original strategies: `{"t539_biglotto_gemini_phase2_7bet": 5080}`
- W750 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5080}`
- W750 dedup strategies: `{"t539_biglotto_elite_7bet": 5080}`
- W750 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5080}`
- Reduced callable families: `[{"authority_qualified_callable_identity": ["T539_HISTORICAL_SQLITE", "T539", 7, "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets"], "callable_identity": "selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets", "callable_labels": ["lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets"], "member_count": 3, "member_identities": [["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_elite_7bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_gemini_phase2_7bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_high_prize_trend_7bet", "v0.1-t539-cross-lottery-r2"]], "removed_sibling_count": 2, "removed_sibling_identities": [["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_gemini_phase2_7bet", "v0.1-t539-cross-lottery-r2"], ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_high_prize_trend_7bet", "v0.1-t539-cross-lottery-r2"]], "representative_identity": ["T539_HISTORICAL_SQLITE", "T539", "t539_biglotto_elite_7bet", "v0.1-t539-cross-lottery-r2"], "representative_rule": "LEXICOGRAPHIC_MINIMUM_COMPLETE_AUTHORITY_QUALIFIED_IDENTITY", "resolution_authorities": ["R2_AUTHORITY_QUALIFIED_ATTRIBUTION"]}]`

### T539:K10

Original candidates: 1; dedup callables: 1; removed siblings: 0.

- W50 original strategies: `{"t539_biglotto_backtest_10bet": 5879}`
- W50 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5879}`
- W50 dedup strategies: `{"t539_biglotto_backtest_10bet": 5879}`
- W50 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5879}`
- W300 original strategies: `{"t539_biglotto_backtest_10bet": 5629}`
- W300 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5629}`
- W300 dedup strategies: `{"t539_biglotto_backtest_10bet": 5629}`
- W300 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5629}`
- W750 original strategies: `{"t539_biglotto_backtest_10bet": 5179}`
- W750 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5179}`
- W750 dedup strategies: `{"t539_biglotto_backtest_10bet": 5179}`
- W750 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5179}`
- Reduced callable families: `[]`

### T539:K11

Original candidates: 1; dedup callables: 1; removed siblings: 0.

- W50 original strategies: `{"t539_biglotto_variant_history_11bet": 5860}`
- W50 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5860}`
- W50 dedup strategies: `{"t539_biglotto_variant_history_11bet": 5860}`
- W50 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5860}`
- W300 original strategies: `{"t539_biglotto_variant_history_11bet": 5610}`
- W300 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5610}`
- W300 dedup strategies: `{"t539_biglotto_variant_history_11bet": 5610}`
- W300 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5610}`
- W750 original strategies: `{"t539_biglotto_variant_history_11bet": 5160}`
- W750 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5160}`
- W750 dedup strategies: `{"t539_biglotto_variant_history_11bet": 5160}`
- W750 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5160}`
- Reduced callable families: `[]`

### T539:K12

Original candidates: 1; dedup callables: 1; removed siblings: 0.

- W50 original strategies: `{"t539_biglotto_core_satellite_12bet": 5879}`
- W50 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5879}`
- W50 dedup strategies: `{"t539_biglotto_core_satellite_12bet": 5879}`
- W50 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5879}`
- W300 original strategies: `{"t539_biglotto_core_satellite_12bet": 5629}`
- W300 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5629}`
- W300 dedup strategies: `{"t539_biglotto_core_satellite_12bet": 5629}`
- W300 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5629}`
- W750 original strategies: `{"t539_biglotto_core_satellite_12bet": 5179}`
- W750 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5179}`
- W750 dedup strategies: `{"t539_biglotto_core_satellite_12bet": 5179}`
- W750 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5179}`
- Reduced callable families: `[]`

### T539:K25

Original candidates: 1; dedup callables: 1; removed siblings: 0.

- W50 original strategies: `{"t539_biglotto_auto_optimizer_alpha_25bet": 5879}`
- W50 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5879}`
- W50 dedup strategies: `{"t539_biglotto_auto_optimizer_alpha_25bet": 5879}`
- W50 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5879}`
- W300 original strategies: `{"t539_biglotto_auto_optimizer_alpha_25bet": 5629}`
- W300 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5629}`
- W300 dedup strategies: `{"t539_biglotto_auto_optimizer_alpha_25bet": 5629}`
- W300 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5629}`
- W750 original strategies: `{"t539_biglotto_auto_optimizer_alpha_25bet": 5179}`
- W750 original callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5179}`
- W750 dedup strategies: `{"t539_biglotto_auto_optimizer_alpha_25bet": 5179}`
- W750 dedup callables: `{"selector-supplement-callable:lottolab.strategies.adapters.daily539_biglotto_portable:Daily539BigLottoPortableAdapter.get_bets": 5179}`
- Reduced callable families: `[]`

## Scientific and runtime boundaries

The comparisons are exact historical descriptions of the frozen authorities. No future-performance, profitability, significance, or promotion conclusion is authorized.

```text
PREDICTIVE_ADVANTAGE = NOT ESTABLISHED
PROFITABILITY = NOT ESTABLISHED
REFERENCE_PROMOTION = NOT AUTHORIZED
RUNTIME_PROMOTION = NOT AUTHORIZED
K2_R2 = NOT RUN
P638_ZONE2 = NOT RUN
SECOND_EXCHANGE = NOT RUN
STRATEGY_RERUN = NOT RUN
DB_WRITE = NO
```
