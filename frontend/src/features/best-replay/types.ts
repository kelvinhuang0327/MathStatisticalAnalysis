export type GameCode = 'B649' | 'P638' | 'T539'
export type GameFilter = GameCode | 'ALL'

export type HorizonKey = 'RECENT_50' | 'RECENT_300' | 'RECENT_750' | 'FULL'

export interface HorizonDefinition {
  key: HorizonKey
  label: string
  shortLabel: string
  draws: number | null
  description: string
}

export const CANONICAL_HORIZONS: readonly HorizonDefinition[] = [
  {
    key: 'RECENT_50',
    label: 'Short · 50',
    shortLabel: 'Short',
    draws: 50,
    description: 'Recent 50 historical evaluation draws (exploratory / low statistical power)',
  },
  {
    key: 'RECENT_300',
    label: 'Medium · 300',
    shortLabel: 'Medium',
    draws: 300,
    description: 'Recent 300 historical evaluation draws (intermediate stability window)',
  },
  {
    key: 'RECENT_750',
    label: 'Long · 750',
    shortLabel: 'Long',
    draws: 750,
    description: 'Recent 750 historical evaluation draws (primary out-of-sample window)',
  },
  {
    key: 'FULL',
    label: 'Full',
    shortLabel: 'Full',
    draws: null,
    description: 'Full available historical observation window',
  },
] as const

export const PRIMARY_TICKET_COUNTS = [1, 2, 3, 4, 5] as const
export type PrimaryTicketCount = (typeof PRIMARY_TICKET_COUNTS)[number]

export const ALL_TICKET_COUNTS = [
  1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
] as const

export type TicketCount = (typeof ALL_TICKET_COUNTS)[number]

export const B649_AVAILABLE_TICKET_COUNTS: readonly TicketCount[] = [5, 10, 15, 20]
export const P638_AVAILABLE_TICKET_COUNTS: readonly TicketCount[] = [1]
export const T539_AVAILABLE_TICKET_COUNTS: readonly TicketCount[] = [1]

export interface BestReplayPrizeCounts {
  first: number
  second: number
  third: number
  fourth: number
  fifth: number
  sixth?: number
  seventh?: number
  general?: number
}

export type EvidenceStatusLabel =
  | 'DESCRIPTIVE LEADER'
  | 'PARETO FRONTIER'
  | 'NO ADJUSTED SUPERIORITY'
  | 'LOW POWER'
  | 'LIMITED SAMPLE'
  | 'EVIDENCE UNAVAILABLE'
  | 'HISTORICAL ONLY'
  | 'EXPLORATORY'

export interface BestReplayItem {
  id: string
  rank: number | null
  strategyId: string
  strategyVersion: string
  legacyMethodId?: string
  methodFamily: string
  game: GameCode
  ticketCount: TicketCount
  horizon: HorizonKey
  horizonLabel: string
  evaluatedTargets: number
  winningTargets: number | null
  hitRate: number | null
  hitRateFormatted: string
  baselineProbability: number | null
  baselineDelta: number | null
  baselineDeltaFormatted: string
  coverage: number | null
  bestHit: string
  prizeCounts: BestReplayPrizeCounts | null
  evidenceStatus: EvidenceStatusLabel
  notes: string
  isAvailable: boolean
  reproductionStatus?: string
  unrankedReason?: string | null
  unavailableReasonCode?: string
}

export interface BestReplaySummary {
  bestStrategyId: string | null
  bestStrategyLabel: string | null
  ticketCount: number | string
  horizon: string
  historicalHitRate: string
  evaluatedTargets: number
  baselineDelta: string
  evidenceStatus: EvidenceStatusLabel
  totalAvailableRecords: number
  game: GameFilter
}

export interface BestReplayQuery {
  game: GameFilter
  ticketCounts: TicketCount[]
  horizon: HorizonKey
  searchQuery?: string
  methodFamily?: string
  limit?: number
  offset?: number
  sortField?: 'rank' | 'hitRate' | 'baselineDelta' | 'ticketCount' | 'strategyId'
  sortDirection?: 'asc' | 'desc'
}

export interface BestReplayMatrixRow {
  strategyId: string
  strategyLabel: string
  methodFamily: string
  game: GameCode
  cells: Record<TicketCount, BestReplayItem | null>
}
