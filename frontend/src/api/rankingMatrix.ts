import type { components } from './generated/openapi'
import {
  fetchB649MultiTicketRecords,
  fetchB649MultiTicketSummary,
  type B649HistoryWindow,
  type B649MultiTicketRecord,
  type B649PrefixCount,
} from './b649MultiTicketRecords'
import {
  listP638Runs,
  getP638Rankings,
  type P638Ranking,
} from './p638Historical'
import {
  listT539Runs,
  getT539Rankings,
  type T539Ranking,
} from './t539Historical'
import {
  listStrategies,
  type StrategyView,
} from './strategies'

export type LotteryType = 'BIG_LOTTO' | 'POWER_LOTTO' | 'DAILY_539'
export type TicketCount = 2 | 3 | 5 | 10 | 20
export type RankingWindow = 'FULL' | 'RECENT_750' | 'RECENT_300' | 'RECENT_50'

export const CANONICAL_TICKET_COUNTS = [2, 3, 5, 10, 20] as const satisfies readonly TicketCount[]
export const CANONICAL_WINDOWS = [
  'FULL',
  'RECENT_750',
  'RECENT_300',
  'RECENT_50',
] as const satisfies readonly RankingWindow[]

export const LOTTERY_OPTIONS: readonly { key: LotteryType; label: string; name: string }[] = [
  { key: 'BIG_LOTTO', label: '大樂透 (6/49)', name: 'Big Lotto' },
  { key: 'POWER_LOTTO', label: '威力彩 (6/38)', name: 'Power Lotto' },
  { key: 'DAILY_539', label: '今彩539 (5/39)', name: 'Daily 539' },
] as const

export const WINDOW_OPTIONS: readonly { key: RankingWindow; label: string; subLabel: string }[] = [
  { key: 'FULL', label: 'FULL', subLabel: '全歷史窗口 (Full History)' },
  { key: 'RECENT_750', label: '750', subLabel: '近 750 期 (Recent 750)' },
  { key: 'RECENT_300', label: '300', subLabel: '近 300 期 (Recent 300)' },
  { key: 'RECENT_50', label: '50', subLabel: '近 50 期 (Recent 50)' },
] as const

export type ComparabilityStatus =
  | 'COMPARABLE'
  | 'NOT_HISTORICALLY_COMPARABLE'
  | 'INSUFFICIENT_WINDOW'
  | 'LOW_SAMPLE_SIZE'
  | 'UNAVAILABLE'

export interface RankingRow {
  lotteryType: LotteryType
  ticketCount: TicketCount
  window: RankingWindow
  officialRank: number | null
  strategyId: string
  displayName: string
  strategyVersion: string
  methodFamily: string
  lifecycleStatus: string
  successes: number | null
  observations: number | null
  officialAnyPrizeRate: number | null
  officialAnyPrizeRateFormatted: string
  coverage: number | null
  coverageFormatted: string
  baselineRate: number | null
  baselineRateFormatted: string
  baselineDelta: number | null
  baselineDeltaFormatted: string
  bestOfficialPrize: string
  comparabilityStatus: ComparabilityStatus
  comparabilityLabel: string
  warningCodes: string[]
  isAvailable: boolean
  unrankedReason: string | null
}

export interface MatrixCell {
  ticketCount: TicketCount
  officialRank: number | null
  officialAnyPrizeRate: number | null
  officialAnyPrizeRateFormatted: string
  baselineDelta: number | null
  baselineDeltaFormatted: string
  isAvailable: boolean
  comparabilityStatus: ComparabilityStatus
  comparabilityLabel: string
  warningCodes: string[]
  reason?: string
}

export interface MatrixRow {
  strategyId: string
  displayName: string
  methodFamily: string
  lifecycleStatus: string
  cells: Record<TicketCount, MatrixCell>
}

export interface CrossWindowPoint {
  window: RankingWindow
  windowLabel: string
  officialRank: number | null
  officialAnyPrizeRate: number | null
  officialAnyPrizeRateFormatted: string
  baselineRate: number | null
  baselineRateFormatted: string
  baselineDelta: number | null
  baselineDeltaFormatted: string
  observations: number | null
  coverage: number | null
  coverageFormatted: string
  isAvailable: boolean
}

export interface CrossWindowData {
  strategyId: string
  displayName: string
  ticketCount: TicketCount
  lotteryType: LotteryType
  points: CrossWindowPoint[]
}

export function formatRatePercentage(rate: number | null | undefined): string {
  if (rate === null || rate === undefined || Number.isNaN(rate)) return 'Unavailable'
  return `${(rate * 100).toFixed(2)}%`
}

export function formatDeltaPercentage(delta: number | null | undefined): string {
  if (delta === null || delta === undefined || Number.isNaN(delta)) return 'Unavailable'
  const sign = delta > 0 ? '+' : ''
  return `${sign}${(delta * 100).toFixed(2)}%`
}

export function formatCoveragePercentage(coverage: number | null | undefined): string {
  if (coverage === null || coverage === undefined || Number.isNaN(coverage)) return 'Unavailable'
  return `${(coverage * 100).toFixed(2)}%`
}

export function parseNumberString(value: string | null | undefined): number | null {
  if (!value || typeof value !== 'string') return null
  const parsed = Number.parseFloat(value)
  return Number.isNaN(parsed) ? null : parsed
}

export function extractBestPrizeFromCounts(
  prizeCounts: components['schemas']['B649OfficialPrizeCountsView'] | null | undefined,
): string {
  if (!prizeCounts) return 'Unavailable'
  if (prizeCounts.first > 0) return `頭獎 (${prizeCounts.first})`
  if (prizeCounts.second > 0) return `貳獎 (${prizeCounts.second})`
  if (prizeCounts.third > 0) return `參獎 (${prizeCounts.third})`
  if (prizeCounts.fourth > 0) return `肆獎 (${prizeCounts.fourth})`
  if (prizeCounts.fifth > 0) return `伍獎 (${prizeCounts.fifth})`
  if (prizeCounts.sixth > 0) return `陸獎 (${prizeCounts.sixth})`
  if (prizeCounts.seventh > 0) return `柒獎 (${prizeCounts.seventh})`
  if (prizeCounts.general > 0) return `普獎 (${prizeCounts.general})`
  return '無中獎'
}

export function deriveComparabilityStatus(
  isAvailable: boolean,
  reproductionStatus: string | undefined,
  unrankedReason: string | null | undefined,
  observations: number | null | undefined,
  window: RankingWindow,
): { status: ComparabilityStatus; label: string } {
  if (!isAvailable) {
    return { status: 'UNAVAILABLE', label: '不可用 (Unavailable)' }
  }
  if (reproductionStatus === 'CLOSED_UNEXECUTABLE' || reproductionStatus === 'DUPLICATE_ALIAS') {
    return { status: 'NOT_HISTORICALLY_COMPARABLE', label: '歷史不可直接比較 (Not Comparable)' }
  }
  if (unrankedReason) {
    return { status: 'NOT_HISTORICALLY_COMPARABLE', label: '未正式納入排名 (Unranked)' }
  }
  if (observations !== null && observations !== undefined && observations > 0 && observations < 50) {
    return { status: 'LOW_SAMPLE_SIZE', label: '低樣本數 (Low Sample Size)' }
  }
  if (window === 'RECENT_50' && (observations === null || observations === undefined || observations < 50)) {
    return { status: 'INSUFFICIENT_WINDOW', label: '窗口樣本不足 (Insufficient Window)' }
  }
  return { status: 'COMPARABLE', label: '可正常比較 (Comparable)' }
}

export function deriveWarningCodes(
  rank: number | null,
  coverage: number | null,
  observations: number | null,
  successes: number | null,
  window: RankingWindow,
  reproductionStatus?: string,
  unrankedReason?: string | null,
  metricsUnavailableReason?: string | null,
): string[] {
  const warnings: string[] = []

  if (metricsUnavailableReason) {
    warnings.push(metricsUnavailableReason)
  }
  if (reproductionStatus === 'CLOSED_UNEXECUTABLE') {
    warnings.push('CLOSED_UNEXECUTABLE')
  }
  if (reproductionStatus === 'DUPLICATE_ALIAS') {
    warnings.push('DUPLICATE_ALIAS')
  }
  if (unrankedReason) {
    warnings.push('NOT_HISTORICALLY_COMPARABLE')
  }
  if (rank !== null && rank <= 3 && coverage !== null && coverage < 0.10) {
    warnings.push('HIGH_RANK_LOW_COVERAGE')
  }
  if ((window === 'RECENT_50' || window === 'RECENT_300') && observations !== null && observations > 0 && (successes === 0 || successes === null)) {
    warnings.push('NO_RECENT_OBSERVATIONS')
  }
  if (observations !== null && observations > 0 && observations < 50) {
    warnings.push('LOW_SAMPLE_SIZE')
  }
  if (observations !== null && observations < 50 && window === 'RECENT_50') {
    warnings.push('INSUFFICIENT_WINDOW')
  }

  return Array.from(new Set(warnings))
}

export const WARNING_CODE_METADATA: Record<string, { label: string; description: string; severity: 'warning' | 'info' | 'danger' }> = {
  HIGH_RANK_LOW_COVERAGE: {
    label: '高排名低覆蓋率',
    description: '官方排名前列但有效觀察覆蓋率低於 10%，可能存在抽樣稀疏性。',
    severity: 'warning',
  },
  NO_RECENT_OBSERVATIONS: {
    label: '近期無成功樣本',
    description: '在近 50 或 300 期窗口中無命中成功記錄。',
    severity: 'warning',
  },
  NOT_HISTORICALLY_COMPARABLE: {
    label: '歷史不可直接比較',
    description: '此策略因未提供統一回測口徑或為別名映射，不可直接作為排名對象。',
    severity: 'info',
  },
  INSUFFICIENT_WINDOW: {
    label: '窗口樣本不足',
    description: '該時間窗口內可用開獎期數不足 50 期。',
    severity: 'warning',
  },
  LOW_SAMPLE_SIZE: {
    label: '低樣本數限制',
    description: '回測觀察樣本總數過低，統計檢定能力有限。',
    severity: 'info',
  },
  CLOSED_UNEXECUTABLE: {
    label: '已封存無法重算',
    description: '該策略在歷史中已封存，不可作為線上執行候選。',
    severity: 'info',
  },
  DUPLICATE_ALIAS: {
    label: '重複別名策略',
    description: '該策略為另一策略之等價別名。',
    severity: 'info',
  },
  FROZEN_PREDICTION_OUTPUT_AND_PRODUCER_UNAVAILABLE: {
    label: '預測產出已封存',
    description: '策略產出已固化，無動態產生器。',
    severity: 'info',
  },
}

export function getWarningMeta(code: string): { label: string; description: string; severity: 'warning' | 'info' | 'danger' } {
  return WARNING_CODE_METADATA[code] ?? {
    label: code,
    description: `未預設之檢驗代碼：${code}`,
    severity: 'warning',
  }
}

/**
 * Loads ranking rows for a specific lottery, ticket count, and window.
 * Strictly respects upstream ranking authority; does NOT recompute ranks.
 */
export async function fetchRankingData(
  lotteryType: LotteryType,
  ticketCount: TicketCount,
  window: RankingWindow,
  signal?: AbortSignal,
): Promise<RankingRow[]> {
  if (lotteryType === 'BIG_LOTTO') {
    return loadB649RankingRows(ticketCount, window, signal)
  }
  if (lotteryType === 'POWER_LOTTO') {
    return loadP638RankingRows(ticketCount, window, signal)
  }
  if (lotteryType === 'DAILY_539') {
    return loadT539RankingRows(ticketCount, window, signal)
  }
  return []
}

async function loadB649RankingRows(
  ticketCount: TicketCount,
  window: RankingWindow,
  signal?: AbortSignal,
): Promise<RankingRow[]> {
  const summary = await fetchB649MultiTicketSummary(signal)
  if (!summary.records_available) {
    return []
  }

  // Canonical B649 multi-ticket dataset supports prefix counts 5, 10, 15, 20.
  // When ticket count is 2 or 3, it is not present in canonical multi-ticket dataset.
  const isAvailablePrefix = (ticketCount === 5 || ticketCount === 10 || ticketCount === 20)
  if (!isAvailablePrefix) {
    // Return empty array (the UI will show clean unavailable state for this ticket count)
    return []
  }

  const prefix = ticketCount as B649PrefixCount
  const windowKey = window as B649HistoryWindow
  let offset = 0
  const limit = 100
  let hasMore = true
  const records: B649MultiTicketRecord[] = []

  while (hasMore) {
    const page = await fetchB649MultiTicketRecords(
      {
        prefixCount: prefix,
        window: windowKey,
        criterion: 'M3_PLUS',
        limit,
        offset,
      },
      signal,
    )
    records.push(...page.items)
    offset += limit
    hasMore = records.length < page.total
  }

  // Fetch strategy metadata catalog to enrich display names if possible
  let catalogMap = new Map<string, StrategyView>()
  try {
    const catalog = await listStrategies(signal)
    catalogMap = new Map((catalog as StrategyView[]).map((s: StrategyView) => [s.strategy_id, s]))
  } catch {
    // Ignore catalog lookup error, fallback to record names
  }

  return records.map((rec) => transformB649ToRankingRow(rec, ticketCount, window, catalogMap))
}

function transformB649ToRankingRow(
  record: B649MultiTicketRecord,
  ticketCount: TicketCount,
  window: RankingWindow,
  catalogMap: Map<string, StrategyView>,
): RankingRow {
  const rateNum = parseNumberString(record.official_any_prize_rate)
  const baselineRateNum = parseNumberString(record.official_random_baseline_probability)
  const deltaNum = parseNumberString(record.official_random_baseline_delta)
  const coverageNum = parseNumberString(record.coverage)
  const observations = record.window_available_draws ?? record.effective_backtest_draw_count ?? null
  const successes = record.official_any_prize_count ?? null

  const catalogMeta = catalogMap.get(record.strategy_id)
  const displayName = catalogMeta?.display_name || record.legacy_method_id || record.strategy_id
  const lifecycleStatus = catalogMeta?.lifecycle_status || record.reproduction_status

  const isAvailable = rateNum !== null && record.reproduction_status === 'BACKTESTED'
  const comp = deriveComparabilityStatus(
    isAvailable,
    record.reproduction_status,
    record.unranked_reason,
    observations,
    window,
  )

  const warnings = deriveWarningCodes(
    record.official_rank,
    coverageNum,
    observations,
    successes,
    window,
    record.reproduction_status,
    record.unranked_reason,
    record.metrics_unavailable_reason,
  )

  const bestPrize = extractBestPrizeFromCounts(record.official_prize_counts)

  return {
    lotteryType: 'BIG_LOTTO',
    ticketCount,
    window,
    officialRank: record.official_rank,
    strategyId: record.strategy_id,
    displayName,
    strategyVersion: record.strategy_version,
    methodFamily: record.method_family,
    lifecycleStatus,
    successes,
    observations,
    officialAnyPrizeRate: rateNum,
    officialAnyPrizeRateFormatted: formatRatePercentage(rateNum),
    coverage: coverageNum,
    coverageFormatted: formatCoveragePercentage(coverageNum),
    baselineRate: baselineRateNum,
    baselineRateFormatted: formatRatePercentage(baselineRateNum),
    baselineDelta: deltaNum,
    baselineDeltaFormatted: formatDeltaPercentage(deltaNum),
    bestOfficialPrize: bestPrize,
    comparabilityStatus: comp.status,
    comparabilityLabel: comp.label,
    warningCodes: warnings,
    isAvailable,
    unrankedReason: record.unranked_reason,
  }
}

async function loadP638RankingRows(
  ticketCount: TicketCount,
  window: RankingWindow,
  signal?: AbortSignal,
): Promise<RankingRow[]> {
  try {
    const runsPage = await listP638Runs({ limit: 5, offset: 0 }, signal)
    if (!runsPage.items.length) return []
    const latestRun = runsPage.items[0]
    if (!latestRun) return []

    const rankingPage = await getP638Rankings(latestRun.run_id, signal)
    return rankingPage.items.map((r: P638Ranking): RankingRow => {
      const isAvailable = (ticketCount as number) === r.native_ticket_count
      const rateNum = isAvailable ? r.winning_target_rate : null
      const successes = isAvailable ? r.winning_target_count : null
      const observations = isAvailable ? r.eligible_target_count : null

      const comp = deriveComparabilityStatus(
        isAvailable,
        'BACKTESTED',
        null,
        observations,
        window,
      )

      return {
        lotteryType: 'POWER_LOTTO',
        ticketCount,
        window,
        officialRank: isAvailable ? r.rank : null,
        strategyId: r.strategy_id,
        displayName: r.strategy_id,
        strategyVersion: r.strategy_version,
        methodFamily: 'p638_native',
        lifecycleStatus: 'ONLINE',
        successes,
        observations,
        officialAnyPrizeRate: rateNum,
        officialAnyPrizeRateFormatted: formatRatePercentage(rateNum),
        coverage: isAvailable ? 1.0 : null,
        coverageFormatted: isAvailable ? '100.00%' : 'Unavailable',
        baselineRate: null,
        baselineRateFormatted: 'Unavailable',
        baselineDelta: null,
        baselineDeltaFormatted: 'Unavailable',
        bestOfficialPrize: r.highest_prize_tier_achieved || '無中獎',
        comparabilityStatus: comp.status,
        comparabilityLabel: comp.label,
        warningCodes: isAvailable ? [] : ['UNAVAILABLE_TICKET_COUNT'],
        isAvailable,
        unrankedReason: null,
      }
    })
  } catch {
    return []
  }
}

async function loadT539RankingRows(
  ticketCount: TicketCount,
  window: RankingWindow,
  signal?: AbortSignal,
): Promise<RankingRow[]> {
  try {
    const runsPage = await listT539Runs({ limit: 5, offset: 0 }, signal)
    if (!runsPage.items.length) return []
    const latestRun = runsPage.items[0]
    if (!latestRun) return []

    const rankingPage = await getT539Rankings(latestRun.run_id, signal)
    return rankingPage.items.map((r: T539Ranking): RankingRow => {
      const isAvailable = (ticketCount as number) === r.native_ticket_count
      const rateNum = isAvailable ? r.winning_target_rate : null
      const successes = isAvailable ? r.winning_target_count : null
      const observations = isAvailable ? r.eligible_target_count : null

      const comp = deriveComparabilityStatus(
        isAvailable,
        'BACKTESTED',
        null,
        observations,
        window,
      )

      return {
        lotteryType: 'DAILY_539',
        ticketCount,
        window,
        officialRank: isAvailable ? r.rank : null,
        strategyId: r.strategy_id,
        displayName: r.strategy_id,
        strategyVersion: r.strategy_version,
        methodFamily: 't539_native',
        lifecycleStatus: 'ONLINE',
        successes,
        observations,
        officialAnyPrizeRate: rateNum,
        officialAnyPrizeRateFormatted: formatRatePercentage(rateNum),
        coverage: isAvailable ? 1.0 : null,
        coverageFormatted: isAvailable ? '100.00%' : 'Unavailable',
        baselineRate: null,
        baselineRateFormatted: 'Unavailable',
        baselineDelta: null,
        baselineDeltaFormatted: 'Unavailable',
        bestOfficialPrize: r.highest_prize_tier_achieved || '無中獎',
        comparabilityStatus: comp.status,
        comparabilityLabel: comp.label,
        warningCodes: isAvailable ? [] : ['UNAVAILABLE_TICKET_COUNT'],
        isAvailable,
        unrankedReason: null,
      }
    })
  } catch {
    return []
  }
}

/**
 * Builds the Multi-Ticket Matrix for all strategies across 2, 3, 5, 10, 20 tickets for a given window.
 */
export async function fetchMultiTicketMatrix(
  lotteryType: LotteryType,
  window: RankingWindow,
  signal?: AbortSignal,
): Promise<MatrixRow[]> {
  // Load data for all canonical ticket counts (2, 3, 5, 10, 20)
  const ticketCountsToFetch: TicketCount[] = [2, 3, 5, 10, 20]
  const rowsPerCount = await Promise.all(
    ticketCountsToFetch.map(async (tc) => ({
      ticketCount: tc,
      rows: await fetchRankingData(lotteryType, tc, window, signal),
    })),
  )

  // Collect all unique strategies
  const strategyMap = new Map<string, {
    strategyId: string
    displayName: string
    methodFamily: string
    lifecycleStatus: string
    cells: Partial<Record<TicketCount, MatrixCell>>
  }>()

  for (const { ticketCount, rows } of rowsPerCount) {
    for (const row of rows) {
      if (!strategyMap.has(row.strategyId)) {
        strategyMap.set(row.strategyId, {
          strategyId: row.strategyId,
          displayName: row.displayName,
          methodFamily: row.methodFamily,
          lifecycleStatus: row.lifecycleStatus,
          cells: {},
        })
      }
      const entry = strategyMap.get(row.strategyId)!
      entry.cells[ticketCount] = {
        ticketCount,
        officialRank: row.officialRank,
        officialAnyPrizeRate: row.officialAnyPrizeRate,
        officialAnyPrizeRateFormatted: row.officialAnyPrizeRateFormatted,
        baselineDelta: row.baselineDelta,
        baselineDeltaFormatted: row.baselineDeltaFormatted,
        isAvailable: row.isAvailable,
        comparabilityStatus: row.comparabilityStatus,
        comparabilityLabel: row.comparabilityLabel,
        warningCodes: row.warningCodes,
        reason: row.unrankedReason || undefined,
      }
    }
  }

  // Ensure all ticket counts have a cell for every strategy
  const matrixRows: MatrixRow[] = []
  for (const entry of strategyMap.values()) {
    const completeCells: Record<TicketCount, MatrixCell> = {
      2: entry.cells[2] ?? createUnavailableCell(2),
      3: entry.cells[3] ?? createUnavailableCell(3),
      5: entry.cells[5] ?? createUnavailableCell(5),
      10: entry.cells[10] ?? createUnavailableCell(10),
      20: entry.cells[20] ?? createUnavailableCell(20),
    }

    matrixRows.push({
      strategyId: entry.strategyId,
      displayName: entry.displayName,
      methodFamily: entry.methodFamily,
      lifecycleStatus: entry.lifecycleStatus,
      cells: completeCells,
    })
  }

  // Sort rows primarily by 5-ticket rank (or first available rank)
  matrixRows.sort((a, b) => {
    const rankA = a.cells[5]?.officialRank ?? 9999
    const rankB = b.cells[5]?.officialRank ?? 9999
    return rankA - rankB
  })

  return matrixRows
}

function createUnavailableCell(ticketCount: TicketCount): MatrixCell {
  return {
    ticketCount,
    officialRank: null,
    officialAnyPrizeRate: null,
    officialAnyPrizeRateFormatted: 'Unavailable',
    baselineDelta: null,
    baselineDeltaFormatted: 'Unavailable',
    isAvailable: false,
    comparabilityStatus: 'UNAVAILABLE',
    comparabilityLabel: '未提供回測',
    warningCodes: [],
    reason: `${ticketCount} 注未包含在此回測數據集中`,
  }
}

/**
 * Loads cross-window comparison points (FULL / 750 / 300 / 50) for a selected strategy.
 */
export async function fetchCrossWindowData(
  lotteryType: LotteryType,
  ticketCount: TicketCount,
  strategyId: string,
  displayName: string,
  signal?: AbortSignal,
): Promise<CrossWindowData> {
  const windows: RankingWindow[] = ['FULL', 'RECENT_750', 'RECENT_300', 'RECENT_50']
  const windowResults = await Promise.all(
    windows.map(async (w) => {
      const rows = await fetchRankingData(lotteryType, ticketCount, w, signal)
      const match = rows.find((r) => r.strategyId === strategyId)
      return { window: w, row: match }
    }),
  )

  const points: CrossWindowPoint[] = windowResults.map(({ window, row }) => {
    const winOption = WINDOW_OPTIONS.find((wo) => wo.key === window)
    const windowLabel = winOption?.label ?? window
    if (!row || !row.isAvailable) {
      return {
        window,
        windowLabel,
        officialRank: row?.officialRank ?? null,
        officialAnyPrizeRate: null,
        officialAnyPrizeRateFormatted: 'Unavailable',
        baselineRate: null,
        baselineRateFormatted: 'Unavailable',
        baselineDelta: null,
        baselineDeltaFormatted: 'Unavailable',
        observations: row?.observations ?? null,
        coverage: row?.coverage ?? null,
        coverageFormatted: row?.coverageFormatted ?? 'Unavailable',
        isAvailable: false,
      }
    }
    return {
      window,
      windowLabel,
      officialRank: row.officialRank,
      officialAnyPrizeRate: row.officialAnyPrizeRate,
      officialAnyPrizeRateFormatted: row.officialAnyPrizeRateFormatted,
      baselineRate: row.baselineRate,
      baselineRateFormatted: row.baselineRateFormatted,
      baselineDelta: row.baselineDelta,
      baselineDeltaFormatted: row.baselineDeltaFormatted,
      observations: row.observations,
      coverage: row.coverage,
      coverageFormatted: row.coverageFormatted,
      isAvailable: true,
    }
  })

  return {
    strategyId,
    displayName,
    ticketCount,
    lotteryType,
    points,
  }
}
