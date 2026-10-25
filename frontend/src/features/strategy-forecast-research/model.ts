import {
  deriveComparabilityStatus,
  deriveWarningCodes,
  fetchRankingData,
  type RankingRow,
  type RankingWindow,
} from '../../api/rankingMatrix'
import {
  fetchB649MultiTicketRecords,
  type B649MultiTicketRecord,
} from '../../api/b649MultiTicketRecords'

export const STRATEGY_RESEARCH_K_VALUES = [2, 3, 5, 10, 15, 20] as const
export const STRATEGY_RESEARCH_WINDOWS = [
  'FULL',
  'RECENT_750',
  'RECENT_300',
  'RECENT_50',
] as const satisfies readonly RankingWindow[]

export type StrategyResearchK = (typeof STRATEGY_RESEARCH_K_VALUES)[number]
export type StrategyResearchWindow = (typeof STRATEGY_RESEARCH_WINDOWS)[number]

export interface StrategyResearchRow {
  strategyId: string
  displayName: string
  strategyVersion: string
  ticketCount: StrategyResearchK
  window: StrategyResearchWindow
  eventCriterion: string
  officialRank: number | null
  numerator: number | null
  denominator: number | null
  actualRate: number | null
  baselineRate: number | null
  baselineDelta: number | null
  coverage: number | null
  isAvailable: boolean
  comparabilityStatus: string
  comparabilityLabel: string
  warningCodes: string[]
  source: 'RANKING_MATRIX' | 'B649_M3_PLUS'
  hasFormalOosEvidence: false
}

function finiteNumber(value: number | null | undefined): number | null {
  return value !== null && value !== undefined && Number.isFinite(value) ? value : null
}

function finiteDecimal(value: string | null | undefined): number | null {
  if (value === null || value === undefined || value.trim() === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function mapRankingRow(row: RankingRow): StrategyResearchRow {
  const denominator = row.k5Record
    ? row.k5Record.official_any_prize_denominator
    : row.observations
  return {
    strategyId: row.strategyId,
    displayName: row.displayName,
    strategyVersion: row.strategyVersion,
    ticketCount: row.ticketCount as StrategyResearchK,
    window: row.window,
    eventCriterion: 'OFFICIAL_ANY_PRIZE',
    officialRank: row.officialRank,
    numerator: finiteNumber(row.successes),
    denominator: finiteNumber(denominator),
    actualRate: finiteNumber(row.officialAnyPrizeRate),
    baselineRate: finiteNumber(row.baselineRate),
    baselineDelta: finiteNumber(row.baselineDelta),
    coverage: finiteNumber(row.coverage),
    isAvailable: row.isAvailable,
    comparabilityStatus: row.comparabilityStatus,
    comparabilityLabel: row.comparabilityLabel,
    warningCodes: [...row.warningCodes],
    source: 'RANKING_MATRIX',
    hasFormalOosEvidence: false,
  }
}

function mapM3PlusRecord(record: B649MultiTicketRecord): StrategyResearchRow {
  const actualRate = finiteDecimal(record.historical_success_rate)
  const baselineRate = finiteDecimal(record.random_baseline_success_rate)
  const baselineDelta = finiteDecimal(record.random_baseline_rate_difference)
  const coverage = finiteDecimal(record.coverage)
  const numerator = finiteNumber(record.success_count)
  const denominator = finiteNumber(record.effective_backtest_draw_count)
  const isAvailable = actualRate !== null && record.reproduction_status === 'BACKTESTED'
  const comparability = deriveComparabilityStatus(
    isAvailable,
    record.reproduction_status,
    record.unranked_reason,
    denominator,
    record.window,
  )
  return {
    strategyId: record.strategy_id,
    displayName: record.legacy_method_id || record.strategy_id,
    strategyVersion: record.strategy_version,
    ticketCount: 15,
    window: record.window,
    eventCriterion: record.criterion,
    officialRank: record.official_rank,
    numerator,
    denominator,
    actualRate,
    baselineRate,
    baselineDelta,
    coverage,
    isAvailable,
    comparabilityStatus: comparability.status,
    comparabilityLabel: comparability.label,
    warningCodes: deriveWarningCodes(
      record.official_rank,
      coverage,
      denominator,
      numerator,
      record.window,
      record.reproduction_status,
      record.unranked_reason,
      record.metrics_unavailable_reason,
    ),
    source: 'B649_M3_PLUS',
    hasFormalOosEvidence: false,
  }
}

export function toStrategyResearchRows(
  rows: RankingRow[],
  ticketCount: Exclude<StrategyResearchK, 15>,
  window: StrategyResearchWindow,
): StrategyResearchRow[] {
  return rows
    .filter((row) => row.ticketCount === ticketCount && row.window === window)
    .map(mapRankingRow)
}

export async function fetchStrategyResearchRows(
  ticketCount: StrategyResearchK,
  window: StrategyResearchWindow,
  signal?: AbortSignal,
): Promise<StrategyResearchRow[]> {
  if (ticketCount !== 15) {
    const rows = await fetchRankingData('BIG_LOTTO', ticketCount, window, signal)
    return toStrategyResearchRows(rows, ticketCount, window)
  }

  const rows: StrategyResearchRow[] = []
  const limit = 100
  let offset = 0
  let total: number | null = null
  do {
    const page = await fetchB649MultiTicketRecords(
      { prefixCount: 15, window, criterion: 'M3_PLUS', limit, offset },
      signal,
    )
    if (page.prefix_count !== 15 || page.window !== window || page.criterion !== 'M3_PLUS') {
      throw new Error('B649 K15 source identity did not match the requested M3_PLUS window.')
    }
    if (total !== null && page.total !== total) {
      throw new Error('B649 K15 source total changed during pagination.')
    }
    total = page.total
    rows.push(...page.items.map(mapM3PlusRecord))
    offset += page.items.length
    if (offset < total && page.items.length === 0) {
      throw new Error('B649 K15 source returned an incomplete page.')
    }
  } while (total !== null && offset < total)

  return rows
}

export function hasValidBaselineComparison(row: StrategyResearchRow): boolean {
  return (
    row.denominator !== 0 &&
    row.actualRate !== null &&
    Number.isFinite(row.actualRate) &&
    row.baselineRate !== null &&
    Number.isFinite(row.baselineRate) &&
    row.baselineDelta !== null &&
    Number.isFinite(row.baselineDelta)
  )
}

export function isAboveRandomBaseline(row: StrategyResearchRow): boolean {
  return hasValidBaselineComparison(row) && (row.baselineDelta as number) > 0
}

export function filterStrategyResearchRows(
  rows: StrategyResearchRow[],
  strategyIdQuery: string,
  aboveRandomOnly: boolean,
): StrategyResearchRow[] {
  const query = strategyIdQuery.trim().toLocaleLowerCase()
  return rows.filter((row) => {
    if (query && !row.strategyId.toLocaleLowerCase().includes(query)) return false
    if (aboveRandomOnly && !isAboveRandomBaseline(row)) return false
    return true
  })
}

export function formatResearchRate(value: number | null): string {
  return value === null || !Number.isFinite(value) ? '不可用' : `${(value * 100).toFixed(2)}%`
}

export function formatResearchDelta(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return '不可用'
  return `${value > 0 ? '+' : ''}${(value * 100).toFixed(2)}%`
}

export function formatResearchCount(value: number | null): string {
  return value === null ? '不可用' : String(value)
}

export function formatActualRateForDisplay(row: StrategyResearchRow): string {
  if (row.denominator === 0) return '不可用（0 / 0）'
  return formatResearchRate(row.actualRate)
}

