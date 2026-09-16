export type ReplayOverviewGame = 'B649' | 'P638' | 'T539'

export type ReplayOverviewTicketCount = 10 | 15 | 20

export const REPLAY_OVERVIEW_TICKET_COUNTS: readonly ReplayOverviewTicketCount[] = [10, 15, 20]

export type ReplayOverviewWindow = 'FULL' | 'RECENT_750' | 'RECENT_300' | 'RECENT_50'

export interface ReplayOverviewWindowOption {
  key: ReplayOverviewWindow
  label: string
  shortLabel: string
  draws: number | null
  description: string
}

export const REPLAY_OVERVIEW_WINDOWS: readonly ReplayOverviewWindowOption[] = [
  {
    key: 'FULL',
    label: 'Full Horizon · 全部歷史',
    shortLabel: 'FULL',
    draws: null,
    description: 'Full available historical observation window',
  },
  {
    key: 'RECENT_750',
    label: 'Long · 750 期',
    shortLabel: '750',
    draws: 750,
    description: 'Recent 750 historical evaluation draws (primary out-of-sample window)',
  },
  {
    key: 'RECENT_300',
    label: 'Medium · 300 期',
    shortLabel: '300',
    draws: 300,
    description: 'Recent 300 historical evaluation draws (intermediate stability window)',
  },
  {
    key: 'RECENT_50',
    label: 'Short · 50 期',
    shortLabel: '50',
    draws: 50,
    description: 'Recent 50 historical evaluation draws (exploratory / low statistical power)',
  },
] as const

export interface ReplayOverviewPrizeCounts {
  first: number
  second: number
  third: number
  fourth: number
  fifth: number
  sixth?: number
  seventh?: number
  general?: number
}

export type ReplayOverviewReproductionStatus =
  | 'BACKTESTED'
  | 'CLOSED_UNEXECUTABLE'
  | 'DUPLICATE_ALIAS'
  | 'UNAVAILABLE'

export interface ReplayOverviewStrategyItem {
  id: string
  game: ReplayOverviewGame
  ticketCount: ReplayOverviewTicketCount
  window: ReplayOverviewWindow
  strategyId: string
  strategyVersion: string
  legacyMethodId: string
  methodFamily: string
  reproductionStatus: ReplayOverviewReproductionStatus
  duplicateAliasTarget: string | null
  officialRank: number | null
  rank: number | null
  officialAnyPrizeCount: number | null
  officialAnyPrizeRate: number | null
  officialAnyPrizeRateFormatted: string
  officialRandomBaselineProbability: number | null
  officialRandomBaselineProbabilityFormatted: string
  officialRandomBaselineDelta: number | null
  officialRandomBaselineDeltaFormatted: string
  unrankedReason: string | null
  successCount: number | null
  effectiveBacktestDrawCount: number | null
  successfulExecutionCount: number | null
  coverage: number | null
  coverageFormatted: string
  bestHit: string
  prizeCounts: ReplayOverviewPrizeCounts | null
  isAvailable: boolean
  evidenceStatus: string
  notes: string
}

export interface ReplayOverviewSummary {
  game: ReplayOverviewGame
  ticketCount: ReplayOverviewTicketCount
  window: ReplayOverviewWindow
  totalStrategies: number
  rankedStrategies: number
  backtestedStrategies: number
  unrankedStrategies: number
  observationCoverageRate: number | null
  topStrategy: {
    strategyId: string
    officialRank: number
    hitRateFormatted: string
  } | null
  isDimensionAvailable: boolean
  unavailableReason: string | null
  canonicalSource: string
  fullUniverseStatus: 'COMPLETE' | 'TOP_N_ONLY' | 'UNRESOLVED'
}

export interface ReplayOverviewMatrixRow {
  strategyId: string
  strategyLabel: string
  methodFamily: string
  reproductionStatus: ReplayOverviewReproductionStatus
  cells: Record<ReplayOverviewTicketCount, ReplayOverviewStrategyItem | null>
}

export type SortField =
  | 'officialRank'
  | 'hitRate'
  | 'successes'
  | 'observations'
  | 'coverage'
  | 'baselineDelta'
  | 'strategyId'

export type SortDirection = 'asc' | 'desc'
