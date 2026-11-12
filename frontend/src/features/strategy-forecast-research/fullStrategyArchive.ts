import {
  fetchB649MultiTicketRecords,
  fetchB649MultiTicketSummary,
  type B649MultiTicketRecord,
  type B649MultiTicketSummary,
} from '../../api/b649MultiTicketRecords'

export const FULL_STRATEGY_ARCHIVE_SOURCE = {
  prefixCount: 15,
  window: 'FULL',
  criterion: 'M3_PLUS',
  limit: 100,
} as const

export type FullStrategyArchiveStatusFilter =
  | 'ALL'
  | 'BACKTESTED'
  | 'CLOSED_UNEXECUTABLE'
  | 'DUPLICATE_ALIAS'

export type FullStrategyArchivePerformanceFilter =
  | 'ALL'
  | 'ABOVE_RANDOM'
  | 'AT_RANDOM'
  | 'BELOW_RANDOM'
  | 'METRIC_UNAVAILABLE'

export type FullStrategyArchivePerformance = Exclude<
  FullStrategyArchivePerformanceFilter,
  'ALL'
>

export interface FullStrategyArchiveMetrics {
  numerator: number
  denominator: number
  effectiveBacktestDrawCount: number | null
  actualRate: number
  randomBaselineRate: number
  delta: number
}

export interface FullStrategyArchiveSnapshot {
  records: B649MultiTicketRecord[]
  total: number
  summary: B649MultiTicketSummary
}

export interface FullStrategyArchiveStatusCounts {
  BACKTESTED: number
  CLOSED_UNEXECUTABLE: number
  DUPLICATE_ALIAS: number
}

export async function fetchFullStrategyBacktestArchive(
  signal?: AbortSignal,
): Promise<FullStrategyArchiveSnapshot> {
  const summary = await fetchB649MultiTicketSummary(signal)
  if (!summary.records_available) {
    throw new Error('B649 回測紀錄來源目前不可用。')
  }

  const records: B649MultiTicketRecord[] = []
  let expectedTotal: number | null = null
  let offset = 0

  do {
    const page = await fetchB649MultiTicketRecords(
      {
        ...FULL_STRATEGY_ARCHIVE_SOURCE,
        offset,
      },
      signal,
    )

    if (
      page.prefix_count !== FULL_STRATEGY_ARCHIVE_SOURCE.prefixCount ||
      page.window !== FULL_STRATEGY_ARCHIVE_SOURCE.window ||
      page.criterion !== FULL_STRATEGY_ARCHIVE_SOURCE.criterion ||
      page.offset !== offset ||
      page.limit !== FULL_STRATEGY_ARCHIVE_SOURCE.limit
    ) {
      throw new Error('B649 全策略來源範圍或分頁位置與請求不一致。')
    }
    if (expectedTotal !== null && page.total !== expectedTotal) {
      throw new Error('B649 全策略來源總數在分頁查詢期間改變。')
    }
    if (expectedTotal === null) {
      expectedTotal = page.total
      if (expectedTotal !== summary.progress.total_strategy_count) {
        throw new Error('B649 摘要總數與全策略紀錄總數不一致。')
      }
    }
    if (page.items.length > FULL_STRATEGY_ARCHIVE_SOURCE.limit) {
      throw new Error('B649 全策略來源回傳超過要求上限的資料頁。')
    }
    if (offset + page.items.length > page.total) {
      throw new Error('B649 全策略來源回傳超過宣告總數的資料。')
    }
    if (
      page.items.some((record) =>
        record.prefix_count !== FULL_STRATEGY_ARCHIVE_SOURCE.prefixCount ||
        record.window !== FULL_STRATEGY_ARCHIVE_SOURCE.window ||
        record.criterion !== FULL_STRATEGY_ARCHIVE_SOURCE.criterion,
      )
    ) {
      throw new Error('B649 全策略來源包含不同事件或窗口的紀錄。')
    }

    records.push(...page.items)
    offset += page.items.length
    if (offset < page.total && page.items.length === 0) {
      throw new Error('B649 全策略來源在完成分頁前回傳空頁。')
    }
  } while (expectedTotal !== null && offset < expectedTotal)

  const total = expectedTotal ?? 0
  if (records.length !== total) {
    throw new Error(`B649 全策略來源只載入 ${records.length} / ${total} 筆。`)
  }

  const statusCounts = countArchiveStatuses(records)
  if (
    statusCounts.BACKTESTED !== summary.progress.backtested_count ||
    statusCounts.CLOSED_UNEXECUTABLE !== summary.progress.closed_count ||
    statusCounts.DUPLICATE_ALIAS !== summary.progress.duplicate_alias_count ||
    statusCounts.BACKTESTED !== summary.progress.reproduced_count ||
    records.length !== summary.progress.total_strategy_count
  ) {
    throw new Error('B649 摘要狀態數與完整策略紀錄不一致。')
  }

  return { records, total, summary }
}

export function classifyFullStrategyArchivePerformance(
  record: B649MultiTicketRecord,
): FullStrategyArchivePerformance {
  const metrics = getFullStrategyArchiveMetrics(record)
  if (!metrics) return 'METRIC_UNAVAILABLE'
  if (metrics.delta > 0) return 'ABOVE_RANDOM'
  if (metrics.delta < 0) return 'BELOW_RANDOM'
  return 'AT_RANDOM'
}

export function getFullStrategyArchiveMetrics(
  record: B649MultiTicketRecord,
): FullStrategyArchiveMetrics | null {
  if (
    record.reproduction_status !== 'BACKTESTED' ||
    record.prefix_count !== FULL_STRATEGY_ARCHIVE_SOURCE.prefixCount ||
    record.window !== FULL_STRATEGY_ARCHIVE_SOURCE.window ||
    record.criterion !== FULL_STRATEGY_ARCHIVE_SOURCE.criterion ||
    record.metrics_unavailable_reason !== null
  ) {
    return null
  }

  const numerator = record.success_count
  const denominator = record.successful_execution_count
  const actualRate = parseFiniteDecimal(record.historical_success_rate)
  const randomBaselineRate = parseFiniteDecimal(record.random_baseline_success_rate)
  const delta = parseFiniteDecimal(record.random_baseline_rate_difference)
  if (
    !isNonnegativeInteger(numerator) ||
    !isNonnegativeInteger(denominator) ||
    denominator === 0 ||
    numerator > denominator ||
    actualRate === null ||
    actualRate < 0 ||
    actualRate > 1 ||
    randomBaselineRate === null ||
    randomBaselineRate < 0 ||
    randomBaselineRate > 1 ||
    delta === null ||
    delta < -1 ||
    delta > 1
  ) {
    return null
  }

  return {
    numerator,
    denominator,
    effectiveBacktestDrawCount: isNonnegativeInteger(record.effective_backtest_draw_count)
      ? record.effective_backtest_draw_count
      : null,
    actualRate,
    randomBaselineRate,
    delta,
  }
}

export function filterFullStrategyArchiveRecords(
  records: B649MultiTicketRecord[],
  statusFilter: FullStrategyArchiveStatusFilter,
  performanceFilter: FullStrategyArchivePerformanceFilter,
): B649MultiTicketRecord[] {
  return records.filter((record) => {
    if (statusFilter !== 'ALL' && record.reproduction_status !== statusFilter) {
      return false
    }
    return (
      performanceFilter === 'ALL' ||
      classifyFullStrategyArchivePerformance(record) === performanceFilter
    )
  })
}

export function isFullStrategyArchiveLowSample(record: B649MultiTicketRecord): boolean {
  const executions = record.successful_execution_count
  return (
    record.reproduction_status === 'BACKTESTED' &&
    isNonnegativeInteger(executions) &&
    executions < 50
  )
}

export function isFullStrategyArchiveLowCoverage(record: B649MultiTicketRecord): boolean {
  const coverage = parseFiniteDecimal(record.coverage)
  return coverage !== null && coverage >= 0 && coverage < 0.1
}

export function parseFiniteDecimal(value: string | null): number | null {
  if (value === null || value.trim() === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

export function formatFullStrategyArchiveRate(value: string | null): string {
  const parsed = parseFiniteDecimal(value)
  return parsed === null ? '不可用' : `${(parsed * 100).toFixed(2)}%`
}

export function formatFullStrategyArchiveDelta(value: string | null): string {
  const parsed = parseFiniteDecimal(value)
  if (parsed === null) return '不可用'
  return `${parsed > 0 ? '+' : ''}${(parsed * 100).toFixed(2)}%`
}

export function formatFullStrategyArchiveCount(value: number | null): string {
  return isNonnegativeInteger(value) ? String(value) : '不可用'
}

export function countArchiveStatuses(
  records: B649MultiTicketRecord[],
): FullStrategyArchiveStatusCounts {
  return records.reduce(
    (counts, record) => {
      counts[record.reproduction_status] += 1
      return counts
    },
    {
      BACKTESTED: 0,
      CLOSED_UNEXECUTABLE: 0,
      DUPLICATE_ALIAS: 0,
    },
  )
}

function isNonnegativeInteger(value: number | null): value is number {
  return value !== null && Number.isInteger(value) && value >= 0
}
