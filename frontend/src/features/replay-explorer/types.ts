export type GameCode = 'B649' | 'P638' | 'T539'

export type ViewMode = 'table' | 'matrix' | 'trend' | 'compare'
export type LoadingState = 'loading' | 'ready' | 'empty' | 'unavailable' | 'error'

export type TicketCount =
  | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10
  | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20

export const ALL_CANONICAL_TICKET_COUNTS: readonly TicketCount[] = [
  1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
  11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
]

export const B649_AVAILABLE_TICKET_COUNTS: readonly TicketCount[] = [5, 10, 15, 20]
export const P638_AVAILABLE_TICKET_COUNTS: readonly TicketCount[] = [1]
export const T539_AVAILABLE_TICKET_COUNTS: readonly TicketCount[] = [1]

export type B649HorizonKey = 'FULL' | 'RECENT_750' | 'RECENT_300' | 'RECENT_50'

export interface HorizonDefinition {
  key: string
  label: string
  shortLabel: string
  drawCount?: number
  description: string
}

export const B649_CANONICAL_HORIZONS: readonly HorizonDefinition[] = [
  { key: 'FULL', label: 'Full Stored Replay', shortLabel: 'Full', drawCount: 1949, description: 'All stored historical backtest draws (1949 draws)' },
  { key: 'RECENT_750', label: 'Long Horizon · 750 Draws', shortLabel: 'Long · 750', drawCount: 750, description: 'Recent 750 historical draws' },
  { key: 'RECENT_300', label: 'Medium Horizon · 300 Draws', shortLabel: 'Medium · 300', drawCount: 300, description: 'Recent 300 historical draws' },
  { key: 'RECENT_50', label: 'Short Horizon · 50 Draws', shortLabel: 'Short · 50', drawCount: 50, description: 'Recent 50 historical draws (Low Power exploratory window)' },
]

export type EvidenceStatusLabel =
  | 'DESCRIPTIVE LEADER'
  | 'PARETO FRONTIER'
  | 'HISTORICAL ONLY'
  | 'LIMITED SAMPLE'
  | 'LOW POWER'
  | 'EXPLORATORY'
  | 'NO ADJUSTED SUPERIORITY'
  | 'EVIDENCE UNAVAILABLE'

export interface ReplayPrizeCounts {
  first: number
  second: number
  third: number
  fourth: number
  fifth: number
  sixth?: number
  seventh?: number
  general?: number
}

export interface ReplayExplorerItem {
  id: string
  game: GameCode
  strategyId: string
  strategyVersion: string
  displayLabel: string
  methodFamily: string | null
  ticketCount: TicketCount
  periodKey: string
  periodLabel: string
  evaluatedTargets: number | null
  winningTargets: number | null
  hitRate: number | null
  hitRateFormatted: string
  rank: number | null
  baselineProbability: number | null
  baselineDelta: number | null
  baselineDeltaFormatted: string
  coverage: number | null
  bestHit: string | null
  prizeCounts: ReplayPrizeCounts | null
  status: string
  reproductionStatus?: string
  lifecycleStatus?: string
  evidenceStatus: EvidenceStatusLabel
  notes: string
  isAvailable: boolean
  unrankedReason?: string | null
  rawPayload?: Record<string, unknown>
}

export interface StrategyOption {
  id: string
  label: string
  version: string
  family?: string | null
  status?: string
  executable?: boolean
}

export interface PeriodOption {
  key: string
  label: string
  subLabel?: string
  drawCount?: number
  dateRange?: string
}

export interface ReplayQueryParams {
  game: GameCode
  selectedStrategyIds: string[]
  selectedTicketCounts: TicketCount[]
  selectedPeriodKey: string
  searchQuery: string
  statusFilter?: string
  methodFamilyFilter?: string
  criterionFilter?: string
}

export interface TrendPoint {
  xLabel: string
  xValue: number | string
  yValue: number | null
  yFormatted: string
  isAvailable: boolean
  tooltipText?: string
}

export interface TrendSeries {
  strategyId: string
  strategyLabel: string
  points: TrendPoint[]
}

export interface ReplayExplorerSummary {
  totalStrategies: number
  availableCombinations: number
  unavailableCombinations: number
  highestHitRate: number | null
  highestHitRateStrategy: string | null
  periodLabel: string
  ticketCountLabels: string[]
}

export interface TargetDetailRecord {
  targetId: string
  drawNumberOrId: string
  drawDate: string | null
  status: string
  predictedNumbers: number[] | { zone1: number[]; zone2?: number }
  actualNumbers: number[] | { zone1: number[]; zone2?: number }
  hitsCount: number
  specialOrZone2Hit?: boolean
  prizeTier: string | null
  prizeAmount?: number | null
  tickets?: Array<{
    ticketPosition: number
    predicted: number[] | { zone1: number[]; zone2?: number }
    hitsCount: number
    prizeTier: string | null
    isWinner: boolean
  }>
}

export interface ReplayExplorerAdapter {
  game: GameCode
  gameTitle: string
  gameSubtitle: string
  gameDescription: string
  availableTicketCounts: readonly TicketCount[]
  supportsTimeWindowHorizons: boolean
  supportsTargetInspection: boolean
  supportsCoverageLedger: boolean
  supportsTrend: boolean
  trendUnavailableReason?: string
  
  loadInitialState: (signal?: AbortSignal) => Promise<{
    strategies: StrategyOption[]
    periods: PeriodOption[]
    families?: string[]
    defaultPeriodKey: string
    defaultTicketCount: TicketCount
  }>

  loadItems: (
    params: ReplayQueryParams,
    signal?: AbortSignal,
  ) => Promise<ReplayExplorerItem[]>

  loadTrendData?: (
    params: ReplayQueryParams,
    items: ReplayExplorerItem[],
    signal?: AbortSignal,
  ) => Promise<TrendSeries[]>

  loadTargetList?: (
    strategyId: string,
    periodKey: string,
    ticketCount: TicketCount,
    signal?: AbortSignal,
  ) => Promise<TargetDetailRecord[]>

  loadTargetDetail?: (
    strategyId: string,
    periodKey: string,
    targetId: string,
    signal?: AbortSignal,
  ) => Promise<TargetDetailRecord | null>
}
