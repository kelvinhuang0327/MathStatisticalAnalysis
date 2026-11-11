// Static same-issue comparison snapshot from the completed manual comparison receipt.
import type { B649Sealed084Window } from '../../api/rankingMatrix'

export interface Sealed084CommonPeer {
  strategyId: string
  strategyVersion: string
  successfulIssues: number
  successRate: string
  successCountDifference: number
  successRateDifference: string
  sourceTaskId: string
}

export interface Sealed084CommonComparison {
  strategyId: string
  strategyVersion: string
  ticketCount: number
  window: B649Sealed084Window
  comparisonWindow: string
  nativeWindow: string
  comparableIssueCount: number
  successfulIssues: number
  successRate: string
  firstIssue: string
  lastIssue: string
  sourceTaskId: string
  sourceTier: string
  sourceIdentity: string
  dataCutoff: string
  sourceLimitations: string
  comparabilityStatus: string
  commonIssueIdsSha256: string
  peers: Sealed084CommonPeer[]
}

export const SEALED_084_COMMON_COMPARISON_SOURCE = {
  file: 'NUMBER2_A_B649_084_MANUAL_COMPARE_20261102_R1/common_issue_comparison.csv',
  sha256: "1945a9cf6d1274e3e798a33b594434cc13e234e2fed685ec9b6ff033766abb32",
} as const

export const SEALED_084_COMMON_COMPARISONS: readonly Sealed084CommonComparison[] = [
  {
    "strategyId": "research_conditional_transfer_entropy_k2",
    "strategyVersion": "v1.0",
    "ticketCount": 2,
    "window": "FULL",
    "comparisonWindow": "COMMON_FULL",
    "nativeWindow": "FULL",
    "comparableIssueCount": 1416,
    "successfulIssues": 81,
    "successRate": "0.057203389830508475",
    "firstIssue": "103000017",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (NOT_DIRECTLY_VERIFIED; original DRAW_DATA_V3 payload and serialization not located).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;INTERSECTION_SHORTER_THAN_AT_LEAST_ONE_NATIVE_WINDOW;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "844f549d0d71cbf6ad6ff10844e2da8474d56f8546ae4cf2ada191f05487be57",
    "peers": [
      {
        "strategyId": "b649_new_horizon_minimax_disagreement_r1",
        "strategyVersion": "v0.1",
        "successfulIssues": 103,
        "successRate": "0.07274011299435028",
        "successCountDifference": -22,
        "successRateDifference": "-0.015536723163841804",
        "sourceTaskId": "NUMBER2_A_B649_HORIZON_V01_K2_SEALED084_REPLAY_20261102_R1"
      },
      {
        "strategyId": "research_causal_renewal_hazard_k2",
        "strategyVersion": "v1.0",
        "successfulIssues": 79,
        "successRate": "0.0557909604519774",
        "successCountDifference": 2,
        "successRateDifference": "0.0014124293785310743",
        "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "b649_new_horizon_minimax_disagreement_r1",
    "strategyVersion": "v0.1",
    "ticketCount": 2,
    "window": "FULL",
    "comparisonWindow": "COMMON_FULL",
    "nativeWindow": "FULL",
    "comparableIssueCount": 1416,
    "successfulIssues": 103,
    "successRate": "0.07274011299435028",
    "firstIssue": "103000017",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_HORIZON_V01_K2_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "BIG_LOTTO_CUTOFF_115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (NOT_DIRECTLY_VERIFIED: original DRAW_DATA_V3 payload and canonical hash contract unavailable).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;INTERSECTION_SHORTER_THAN_AT_LEAST_ONE_NATIVE_WINDOW;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "844f549d0d71cbf6ad6ff10844e2da8474d56f8546ae4cf2ada191f05487be57",
    "peers": [
      {
        "strategyId": "research_conditional_transfer_entropy_k2",
        "strategyVersion": "v1.0",
        "successfulIssues": 81,
        "successRate": "0.057203389830508475",
        "successCountDifference": 22,
        "successRateDifference": "0.015536723163841804",
        "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1"
      },
      {
        "strategyId": "research_causal_renewal_hazard_k2",
        "strategyVersion": "v1.0",
        "successfulIssues": 79,
        "successRate": "0.0557909604519774",
        "successCountDifference": 24,
        "successRateDifference": "0.016949152542372878",
        "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_causal_renewal_hazard_k2",
    "strategyVersion": "v1.0",
    "ticketCount": 2,
    "window": "FULL",
    "comparisonWindow": "COMMON_FULL",
    "nativeWindow": "FULL",
    "comparableIssueCount": 1416,
    "successfulIssues": 79,
    "successRate": "0.0557909604519774",
    "firstIssue": "103000017",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (UNVERIFIED).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;INTERSECTION_SHORTER_THAN_AT_LEAST_ONE_NATIVE_WINDOW;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "844f549d0d71cbf6ad6ff10844e2da8474d56f8546ae4cf2ada191f05487be57",
    "peers": [
      {
        "strategyId": "research_conditional_transfer_entropy_k2",
        "strategyVersion": "v1.0",
        "successfulIssues": 81,
        "successRate": "0.057203389830508475",
        "successCountDifference": -2,
        "successRateDifference": "-0.0014124293785310743",
        "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1"
      },
      {
        "strategyId": "b649_new_horizon_minimax_disagreement_r1",
        "strategyVersion": "v0.1",
        "successfulIssues": 103,
        "successRate": "0.07274011299435028",
        "successCountDifference": -24,
        "successRateDifference": "-0.016949152542372878",
        "sourceTaskId": "NUMBER2_A_B649_HORIZON_V01_K2_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_conditional_transfer_entropy_k2",
    "strategyVersion": "v1.0",
    "ticketCount": 2,
    "window": "RECENT_750",
    "comparisonWindow": "RECENT_750",
    "nativeWindow": "RECENT_750",
    "comparableIssueCount": 750,
    "successfulIssues": 44,
    "successRate": "0.058666666666666666",
    "firstIssue": "109000027",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (NOT_DIRECTLY_VERIFIED; original DRAW_DATA_V3 payload and serialization not located).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "6a7867345e6bb482ef904fe33424aa3c22b102e8dc7a72989a574b6a7e186d14",
    "peers": [
      {
        "strategyId": "b649_new_horizon_minimax_disagreement_r1",
        "strategyVersion": "v0.1",
        "successfulIssues": 58,
        "successRate": "0.07733333333333334",
        "successCountDifference": -14,
        "successRateDifference": "-0.01866666666666667",
        "sourceTaskId": "NUMBER2_A_B649_HORIZON_V01_K2_SEALED084_REPLAY_20261102_R1"
      },
      {
        "strategyId": "research_causal_renewal_hazard_k2",
        "strategyVersion": "v1.0",
        "successfulIssues": 43,
        "successRate": "0.05733333333333333",
        "successCountDifference": 1,
        "successRateDifference": "0.0013333333333333322",
        "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "b649_new_horizon_minimax_disagreement_r1",
    "strategyVersion": "v0.1",
    "ticketCount": 2,
    "window": "RECENT_750",
    "comparisonWindow": "RECENT_750",
    "nativeWindow": "RECENT_750",
    "comparableIssueCount": 750,
    "successfulIssues": 58,
    "successRate": "0.07733333333333334",
    "firstIssue": "109000027",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_HORIZON_V01_K2_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "BIG_LOTTO_CUTOFF_115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (NOT_DIRECTLY_VERIFIED: original DRAW_DATA_V3 payload and canonical hash contract unavailable).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "6a7867345e6bb482ef904fe33424aa3c22b102e8dc7a72989a574b6a7e186d14",
    "peers": [
      {
        "strategyId": "research_conditional_transfer_entropy_k2",
        "strategyVersion": "v1.0",
        "successfulIssues": 44,
        "successRate": "0.058666666666666666",
        "successCountDifference": 14,
        "successRateDifference": "0.01866666666666667",
        "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1"
      },
      {
        "strategyId": "research_causal_renewal_hazard_k2",
        "strategyVersion": "v1.0",
        "successfulIssues": 43,
        "successRate": "0.05733333333333333",
        "successCountDifference": 15,
        "successRateDifference": "0.020000000000000004",
        "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_causal_renewal_hazard_k2",
    "strategyVersion": "v1.0",
    "ticketCount": 2,
    "window": "RECENT_750",
    "comparisonWindow": "RECENT_750",
    "nativeWindow": "RECENT_750",
    "comparableIssueCount": 750,
    "successfulIssues": 43,
    "successRate": "0.05733333333333333",
    "firstIssue": "109000027",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (UNVERIFIED).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "6a7867345e6bb482ef904fe33424aa3c22b102e8dc7a72989a574b6a7e186d14",
    "peers": [
      {
        "strategyId": "research_conditional_transfer_entropy_k2",
        "strategyVersion": "v1.0",
        "successfulIssues": 44,
        "successRate": "0.058666666666666666",
        "successCountDifference": -1,
        "successRateDifference": "-0.0013333333333333322",
        "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1"
      },
      {
        "strategyId": "b649_new_horizon_minimax_disagreement_r1",
        "strategyVersion": "v0.1",
        "successfulIssues": 58,
        "successRate": "0.07733333333333334",
        "successCountDifference": -15,
        "successRateDifference": "-0.020000000000000004",
        "sourceTaskId": "NUMBER2_A_B649_HORIZON_V01_K2_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_conditional_transfer_entropy_k2",
    "strategyVersion": "v1.0",
    "ticketCount": 2,
    "window": "RECENT_300",
    "comparisonWindow": "RECENT_300",
    "nativeWindow": "RECENT_300",
    "comparableIssueCount": 300,
    "successfulIssues": 14,
    "successRate": "0.04666666666666667",
    "firstIssue": "113000021",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (NOT_DIRECTLY_VERIFIED; original DRAW_DATA_V3 payload and serialization not located).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "2972041052452b19cdf863ccbacf7adf43f49c5ce22e830106969a3b01b6ea27",
    "peers": [
      {
        "strategyId": "b649_new_horizon_minimax_disagreement_r1",
        "strategyVersion": "v0.1",
        "successfulIssues": 20,
        "successRate": "0.06666666666666667",
        "successCountDifference": -6,
        "successRateDifference": "-0.019999999999999997",
        "sourceTaskId": "NUMBER2_A_B649_HORIZON_V01_K2_SEALED084_REPLAY_20261102_R1"
      },
      {
        "strategyId": "research_causal_renewal_hazard_k2",
        "strategyVersion": "v1.0",
        "successfulIssues": 22,
        "successRate": "0.07333333333333333",
        "successCountDifference": -8,
        "successRateDifference": "-0.026666666666666665",
        "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "b649_new_horizon_minimax_disagreement_r1",
    "strategyVersion": "v0.1",
    "ticketCount": 2,
    "window": "RECENT_300",
    "comparisonWindow": "RECENT_300",
    "nativeWindow": "RECENT_300",
    "comparableIssueCount": 300,
    "successfulIssues": 20,
    "successRate": "0.06666666666666667",
    "firstIssue": "113000021",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_HORIZON_V01_K2_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "BIG_LOTTO_CUTOFF_115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (NOT_DIRECTLY_VERIFIED: original DRAW_DATA_V3 payload and canonical hash contract unavailable).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "2972041052452b19cdf863ccbacf7adf43f49c5ce22e830106969a3b01b6ea27",
    "peers": [
      {
        "strategyId": "research_conditional_transfer_entropy_k2",
        "strategyVersion": "v1.0",
        "successfulIssues": 14,
        "successRate": "0.04666666666666667",
        "successCountDifference": 6,
        "successRateDifference": "0.019999999999999997",
        "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1"
      },
      {
        "strategyId": "research_causal_renewal_hazard_k2",
        "strategyVersion": "v1.0",
        "successfulIssues": 22,
        "successRate": "0.07333333333333333",
        "successCountDifference": -2,
        "successRateDifference": "-0.006666666666666668",
        "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_causal_renewal_hazard_k2",
    "strategyVersion": "v1.0",
    "ticketCount": 2,
    "window": "RECENT_300",
    "comparisonWindow": "RECENT_300",
    "nativeWindow": "RECENT_300",
    "comparableIssueCount": 300,
    "successfulIssues": 22,
    "successRate": "0.07333333333333333",
    "firstIssue": "113000021",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (UNVERIFIED).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "2972041052452b19cdf863ccbacf7adf43f49c5ce22e830106969a3b01b6ea27",
    "peers": [
      {
        "strategyId": "research_conditional_transfer_entropy_k2",
        "strategyVersion": "v1.0",
        "successfulIssues": 14,
        "successRate": "0.04666666666666667",
        "successCountDifference": 8,
        "successRateDifference": "0.026666666666666665",
        "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1"
      },
      {
        "strategyId": "b649_new_horizon_minimax_disagreement_r1",
        "strategyVersion": "v0.1",
        "successfulIssues": 20,
        "successRate": "0.06666666666666667",
        "successCountDifference": 2,
        "successRateDifference": "0.006666666666666668",
        "sourceTaskId": "NUMBER2_A_B649_HORIZON_V01_K2_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_conditional_transfer_entropy_k2",
    "strategyVersion": "v1.0",
    "ticketCount": 2,
    "window": "RECENT_50",
    "comparisonWindow": "RECENT_50",
    "nativeWindow": "RECENT_50",
    "comparableIssueCount": 50,
    "successfulIssues": 3,
    "successRate": "0.06",
    "firstIssue": "115000035",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (NOT_DIRECTLY_VERIFIED; original DRAW_DATA_V3 payload and serialization not located).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "913df1821d08c0118b9f2d8814040db8571e324f3670071a140b8c454256f262",
    "peers": [
      {
        "strategyId": "b649_new_horizon_minimax_disagreement_r1",
        "strategyVersion": "v0.1",
        "successfulIssues": 5,
        "successRate": "0.1",
        "successCountDifference": -2,
        "successRateDifference": "-0.04000000000000001",
        "sourceTaskId": "NUMBER2_A_B649_HORIZON_V01_K2_SEALED084_REPLAY_20261102_R1"
      },
      {
        "strategyId": "research_causal_renewal_hazard_k2",
        "strategyVersion": "v1.0",
        "successfulIssues": 4,
        "successRate": "0.08",
        "successCountDifference": -1,
        "successRateDifference": "-0.020000000000000004",
        "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "b649_new_horizon_minimax_disagreement_r1",
    "strategyVersion": "v0.1",
    "ticketCount": 2,
    "window": "RECENT_50",
    "comparisonWindow": "RECENT_50",
    "nativeWindow": "RECENT_50",
    "comparableIssueCount": 50,
    "successfulIssues": 5,
    "successRate": "0.1",
    "firstIssue": "115000035",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_HORIZON_V01_K2_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "BIG_LOTTO_CUTOFF_115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (NOT_DIRECTLY_VERIFIED: original DRAW_DATA_V3 payload and canonical hash contract unavailable).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "913df1821d08c0118b9f2d8814040db8571e324f3670071a140b8c454256f262",
    "peers": [
      {
        "strategyId": "research_conditional_transfer_entropy_k2",
        "strategyVersion": "v1.0",
        "successfulIssues": 3,
        "successRate": "0.06",
        "successCountDifference": 2,
        "successRateDifference": "0.04000000000000001",
        "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1"
      },
      {
        "strategyId": "research_causal_renewal_hazard_k2",
        "strategyVersion": "v1.0",
        "successfulIssues": 4,
        "successRate": "0.08",
        "successCountDifference": 1,
        "successRateDifference": "0.020000000000000004",
        "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_causal_renewal_hazard_k2",
    "strategyVersion": "v1.0",
    "ticketCount": 2,
    "window": "RECENT_50",
    "comparisonWindow": "RECENT_50",
    "nativeWindow": "RECENT_50",
    "comparableIssueCount": 50,
    "successfulIssues": 4,
    "successRate": "0.08",
    "firstIssue": "115000035",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (UNVERIFIED).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "913df1821d08c0118b9f2d8814040db8571e324f3670071a140b8c454256f262",
    "peers": [
      {
        "strategyId": "research_conditional_transfer_entropy_k2",
        "strategyVersion": "v1.0",
        "successfulIssues": 3,
        "successRate": "0.06",
        "successCountDifference": 1,
        "successRateDifference": "0.020000000000000004",
        "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1"
      },
      {
        "strategyId": "b649_new_horizon_minimax_disagreement_r1",
        "strategyVersion": "v0.1",
        "successfulIssues": 5,
        "successRate": "0.1",
        "successCountDifference": -1,
        "successRateDifference": "-0.020000000000000004",
        "sourceTaskId": "NUMBER2_A_B649_HORIZON_V01_K2_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_conditional_transfer_entropy_k3",
    "strategyVersion": "v1.0",
    "ticketCount": 3,
    "window": "FULL",
    "comparisonWindow": "FULL",
    "nativeWindow": "FULL",
    "comparableIssueCount": 1416,
    "successfulIssues": 113,
    "successRate": "0.07980225988700565",
    "firstIssue": "103000017",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (NOT_DIRECTLY_VERIFIED; original DRAW_DATA_V3 payload and serialization not located).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "844f549d0d71cbf6ad6ff10844e2da8474d56f8546ae4cf2ada191f05487be57",
    "peers": [
      {
        "strategyId": "research_causal_renewal_hazard_k3",
        "strategyVersion": "v1.0",
        "successfulIssues": 114,
        "successRate": "0.08050847457627118",
        "successCountDifference": -1,
        "successRateDifference": "-0.0007062146892655302",
        "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_causal_renewal_hazard_k3",
    "strategyVersion": "v1.0",
    "ticketCount": 3,
    "window": "FULL",
    "comparisonWindow": "FULL",
    "nativeWindow": "FULL",
    "comparableIssueCount": 1416,
    "successfulIssues": 114,
    "successRate": "0.08050847457627118",
    "firstIssue": "103000017",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (UNVERIFIED).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "844f549d0d71cbf6ad6ff10844e2da8474d56f8546ae4cf2ada191f05487be57",
    "peers": [
      {
        "strategyId": "research_conditional_transfer_entropy_k3",
        "strategyVersion": "v1.0",
        "successfulIssues": 113,
        "successRate": "0.07980225988700565",
        "successCountDifference": 1,
        "successRateDifference": "0.0007062146892655302",
        "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_conditional_transfer_entropy_k3",
    "strategyVersion": "v1.0",
    "ticketCount": 3,
    "window": "RECENT_750",
    "comparisonWindow": "RECENT_750",
    "nativeWindow": "RECENT_750",
    "comparableIssueCount": 750,
    "successfulIssues": 58,
    "successRate": "0.07733333333333334",
    "firstIssue": "109000027",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (NOT_DIRECTLY_VERIFIED; original DRAW_DATA_V3 payload and serialization not located).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "6a7867345e6bb482ef904fe33424aa3c22b102e8dc7a72989a574b6a7e186d14",
    "peers": [
      {
        "strategyId": "research_causal_renewal_hazard_k3",
        "strategyVersion": "v1.0",
        "successfulIssues": 62,
        "successRate": "0.08266666666666667",
        "successCountDifference": -4,
        "successRateDifference": "-0.005333333333333329",
        "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_causal_renewal_hazard_k3",
    "strategyVersion": "v1.0",
    "ticketCount": 3,
    "window": "RECENT_750",
    "comparisonWindow": "RECENT_750",
    "nativeWindow": "RECENT_750",
    "comparableIssueCount": 750,
    "successfulIssues": 62,
    "successRate": "0.08266666666666667",
    "firstIssue": "109000027",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (UNVERIFIED).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "6a7867345e6bb482ef904fe33424aa3c22b102e8dc7a72989a574b6a7e186d14",
    "peers": [
      {
        "strategyId": "research_conditional_transfer_entropy_k3",
        "strategyVersion": "v1.0",
        "successfulIssues": 58,
        "successRate": "0.07733333333333334",
        "successCountDifference": 4,
        "successRateDifference": "0.005333333333333329",
        "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_conditional_transfer_entropy_k3",
    "strategyVersion": "v1.0",
    "ticketCount": 3,
    "window": "RECENT_300",
    "comparisonWindow": "RECENT_300",
    "nativeWindow": "RECENT_300",
    "comparableIssueCount": 300,
    "successfulIssues": 24,
    "successRate": "0.08",
    "firstIssue": "113000021",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (NOT_DIRECTLY_VERIFIED; original DRAW_DATA_V3 payload and serialization not located).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "2972041052452b19cdf863ccbacf7adf43f49c5ce22e830106969a3b01b6ea27",
    "peers": [
      {
        "strategyId": "research_causal_renewal_hazard_k3",
        "strategyVersion": "v1.0",
        "successfulIssues": 32,
        "successRate": "0.10666666666666667",
        "successCountDifference": -8,
        "successRateDifference": "-0.026666666666666672",
        "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_causal_renewal_hazard_k3",
    "strategyVersion": "v1.0",
    "ticketCount": 3,
    "window": "RECENT_300",
    "comparisonWindow": "RECENT_300",
    "nativeWindow": "RECENT_300",
    "comparableIssueCount": 300,
    "successfulIssues": 32,
    "successRate": "0.10666666666666667",
    "firstIssue": "113000021",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (UNVERIFIED).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "2972041052452b19cdf863ccbacf7adf43f49c5ce22e830106969a3b01b6ea27",
    "peers": [
      {
        "strategyId": "research_conditional_transfer_entropy_k3",
        "strategyVersion": "v1.0",
        "successfulIssues": 24,
        "successRate": "0.08",
        "successCountDifference": 8,
        "successRateDifference": "0.026666666666666672",
        "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_conditional_transfer_entropy_k3",
    "strategyVersion": "v1.0",
    "ticketCount": 3,
    "window": "RECENT_50",
    "comparisonWindow": "RECENT_50",
    "nativeWindow": "RECENT_50",
    "comparableIssueCount": 50,
    "successfulIssues": 6,
    "successRate": "0.12",
    "firstIssue": "115000035",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (NOT_DIRECTLY_VERIFIED; original DRAW_DATA_V3 payload and serialization not located).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "913df1821d08c0118b9f2d8814040db8571e324f3670071a140b8c454256f262",
    "peers": [
      {
        "strategyId": "research_causal_renewal_hazard_k3",
        "strategyVersion": "v1.0",
        "successfulIssues": 6,
        "successRate": "0.12",
        "successCountDifference": 0,
        "successRateDifference": "0.0",
        "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_causal_renewal_hazard_k3",
    "strategyVersion": "v1.0",
    "ticketCount": 3,
    "window": "RECENT_50",
    "comparisonWindow": "RECENT_50",
    "nativeWindow": "RECENT_50",
    "comparableIssueCount": 50,
    "successfulIssues": 6,
    "successRate": "0.12",
    "firstIssue": "115000035",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (UNVERIFIED).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "913df1821d08c0118b9f2d8814040db8571e324f3670071a140b8c454256f262",
    "peers": [
      {
        "strategyId": "research_conditional_transfer_entropy_k3",
        "strategyVersion": "v1.0",
        "successfulIssues": 6,
        "successRate": "0.12",
        "successCountDifference": 0,
        "successRateDifference": "0.0",
        "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_conditional_transfer_entropy_k5",
    "strategyVersion": "v1.0",
    "ticketCount": 5,
    "window": "FULL",
    "comparisonWindow": "FULL",
    "nativeWindow": "FULL",
    "comparableIssueCount": 1416,
    "successfulIssues": 195,
    "successRate": "0.13771186440677965",
    "firstIssue": "103000017",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (NOT_DIRECTLY_VERIFIED; original DRAW_DATA_V3 payload and serialization not located).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "844f549d0d71cbf6ad6ff10844e2da8474d56f8546ae4cf2ada191f05487be57",
    "peers": [
      {
        "strategyId": "research_causal_renewal_hazard_k5",
        "strategyVersion": "v1.0",
        "successfulIssues": 207,
        "successRate": "0.1461864406779661",
        "successCountDifference": -12,
        "successRateDifference": "-0.008474576271186446",
        "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_causal_renewal_hazard_k5",
    "strategyVersion": "v1.0",
    "ticketCount": 5,
    "window": "FULL",
    "comparisonWindow": "FULL",
    "nativeWindow": "FULL",
    "comparableIssueCount": 1416,
    "successfulIssues": 207,
    "successRate": "0.1461864406779661",
    "firstIssue": "103000017",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (UNVERIFIED).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "844f549d0d71cbf6ad6ff10844e2da8474d56f8546ae4cf2ada191f05487be57",
    "peers": [
      {
        "strategyId": "research_conditional_transfer_entropy_k5",
        "strategyVersion": "v1.0",
        "successfulIssues": 195,
        "successRate": "0.13771186440677965",
        "successCountDifference": 12,
        "successRateDifference": "0.008474576271186446",
        "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_conditional_transfer_entropy_k5",
    "strategyVersion": "v1.0",
    "ticketCount": 5,
    "window": "RECENT_750",
    "comparisonWindow": "RECENT_750",
    "nativeWindow": "RECENT_750",
    "comparableIssueCount": 750,
    "successfulIssues": 106,
    "successRate": "0.14133333333333334",
    "firstIssue": "109000027",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (NOT_DIRECTLY_VERIFIED; original DRAW_DATA_V3 payload and serialization not located).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "6a7867345e6bb482ef904fe33424aa3c22b102e8dc7a72989a574b6a7e186d14",
    "peers": [
      {
        "strategyId": "research_causal_renewal_hazard_k5",
        "strategyVersion": "v1.0",
        "successfulIssues": 111,
        "successRate": "0.148",
        "successCountDifference": -5,
        "successRateDifference": "-0.006666666666666654",
        "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_causal_renewal_hazard_k5",
    "strategyVersion": "v1.0",
    "ticketCount": 5,
    "window": "RECENT_750",
    "comparisonWindow": "RECENT_750",
    "nativeWindow": "RECENT_750",
    "comparableIssueCount": 750,
    "successfulIssues": 111,
    "successRate": "0.148",
    "firstIssue": "109000027",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (UNVERIFIED).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "6a7867345e6bb482ef904fe33424aa3c22b102e8dc7a72989a574b6a7e186d14",
    "peers": [
      {
        "strategyId": "research_conditional_transfer_entropy_k5",
        "strategyVersion": "v1.0",
        "successfulIssues": 106,
        "successRate": "0.14133333333333334",
        "successCountDifference": 5,
        "successRateDifference": "0.006666666666666654",
        "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_conditional_transfer_entropy_k5",
    "strategyVersion": "v1.0",
    "ticketCount": 5,
    "window": "RECENT_300",
    "comparisonWindow": "RECENT_300",
    "nativeWindow": "RECENT_300",
    "comparableIssueCount": 300,
    "successfulIssues": 42,
    "successRate": "0.14",
    "firstIssue": "113000021",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (NOT_DIRECTLY_VERIFIED; original DRAW_DATA_V3 payload and serialization not located).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "2972041052452b19cdf863ccbacf7adf43f49c5ce22e830106969a3b01b6ea27",
    "peers": [
      {
        "strategyId": "research_causal_renewal_hazard_k5",
        "strategyVersion": "v1.0",
        "successfulIssues": 46,
        "successRate": "0.15333333333333332",
        "successCountDifference": -4,
        "successRateDifference": "-0.013333333333333308",
        "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_causal_renewal_hazard_k5",
    "strategyVersion": "v1.0",
    "ticketCount": 5,
    "window": "RECENT_300",
    "comparisonWindow": "RECENT_300",
    "nativeWindow": "RECENT_300",
    "comparableIssueCount": 300,
    "successfulIssues": 46,
    "successRate": "0.15333333333333332",
    "firstIssue": "113000021",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (UNVERIFIED).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "2972041052452b19cdf863ccbacf7adf43f49c5ce22e830106969a3b01b6ea27",
    "peers": [
      {
        "strategyId": "research_conditional_transfer_entropy_k5",
        "strategyVersion": "v1.0",
        "successfulIssues": 42,
        "successRate": "0.14",
        "successCountDifference": 4,
        "successRateDifference": "0.013333333333333308",
        "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_conditional_transfer_entropy_k5",
    "strategyVersion": "v1.0",
    "ticketCount": 5,
    "window": "RECENT_50",
    "comparisonWindow": "RECENT_50",
    "nativeWindow": "RECENT_50",
    "comparableIssueCount": 50,
    "successfulIssues": 9,
    "successRate": "0.18",
    "firstIssue": "115000035",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (NOT_DIRECTLY_VERIFIED; original DRAW_DATA_V3 payload and serialization not located).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "913df1821d08c0118b9f2d8814040db8571e324f3670071a140b8c454256f262",
    "peers": [
      {
        "strategyId": "research_causal_renewal_hazard_k5",
        "strategyVersion": "v1.0",
        "successfulIssues": 10,
        "successRate": "0.2",
        "successCountDifference": -1,
        "successRateDifference": "-0.020000000000000018",
        "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  },
  {
    "strategyId": "research_causal_renewal_hazard_k5",
    "strategyVersion": "v1.0",
    "ticketCount": 5,
    "window": "RECENT_50",
    "comparisonWindow": "RECENT_50",
    "nativeWindow": "RECENT_50",
    "comparableIssueCount": 50,
    "successfulIssues": 10,
    "successRate": "0.2",
    "firstIssue": "115000035",
    "lastIssue": "115000084",
    "sourceTaskId": "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1",
    "sourceTier": "SEALED_ATTESTED_DRAW_ROWS",
    "sourceIdentity": "SEALED_ATTESTED_DRAW_ROWS:115000084",
    "dataCutoff": "115000084",
    "sourceLimitations": "SEALED_ATTESTED_DRAW_ROWS only; direct original DRAW_DATA_V3 payload/canonical-hash parity is not established (UNVERIFIED).",
    "comparabilityStatus": "COMMON_ISSUE_ID_INTERSECTION;SAME_K;SAME_TICKET_COUNT;OFFICIAL_ANY_PRIZE;ALL_METHOD_ISSUE_SETS_MATCH;MONETARY_COST_NOT_VERIFIED",
    "commonIssueIdsSha256": "913df1821d08c0118b9f2d8814040db8571e324f3670071a140b8c454256f262",
    "peers": [
      {
        "strategyId": "research_conditional_transfer_entropy_k5",
        "strategyVersion": "v1.0",
        "successfulIssues": 9,
        "successRate": "0.18",
        "successCountDifference": 1,
        "successRateDifference": "0.020000000000000018",
        "sourceTaskId": "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1"
      }
    ]
  }
]
