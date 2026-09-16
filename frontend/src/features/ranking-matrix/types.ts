import type {
  ComparabilityStatus,
  CrossWindowData,
  CrossWindowPoint,
  LotteryType,
  MatrixCell,
  MatrixRow,
  RankingRow,
  RankingWindow,
  TicketCount,
} from '../../api/rankingMatrix'

export type {
  ComparabilityStatus,
  CrossWindowData,
  CrossWindowPoint,
  LotteryType,
  MatrixCell,
  MatrixRow,
  RankingRow,
  RankingWindow,
  TicketCount,
}

export type ViewMode = 'table' | 'matrix'

export type SortField =
  | 'officialRank'
  | 'officialAnyPrizeRate'
  | 'successes'
  | 'observations'
  | 'coverage'
  | 'baselineDelta'
  | 'strategyId'

export type SortDirection = 'asc' | 'desc'

export type AboveBaselineFilter = 'ALL' | 'ABOVE' | 'AT_OR_BELOW'
export type WarningFilter = 'ALL' | 'HAS_WARNING' | 'NO_WARNING'

export interface RankingFilterState {
  search: string
  lifecycleStatus: string
  comparabilityStatus: string
  aboveBaseline: AboveBaselineFilter
  warningFilter: WarningFilter
  minCoverage: number // 0 to 100
}

export type PageLoadState = 'loading' | 'ready' | 'empty' | 'error'
