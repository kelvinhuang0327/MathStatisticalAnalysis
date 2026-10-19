import {
  fetchB649MultiTicketRecords,
  fetchB649MultiTicketSummary,
  type B649HistoryWindow,
  type B649MultiTicketRecord,
  type B649PrefixCount,
} from './b649MultiTicketRecords'

import type {
  ReplayOverviewGame,
  ReplayOverviewMatrixRow,
  ReplayOverviewPrizeCounts,
  ReplayOverviewReproductionStatus,
  ReplayOverviewStrategyItem,
  ReplayOverviewSummary,
  ReplayOverviewTicketCount,
  ReplayOverviewWindow,
} from '../features/replay-overview/types'

export function isDimensionAvailable(
  game: ReplayOverviewGame,
  ticketCount: ReplayOverviewTicketCount,
): boolean {
  if (game === 'B649') {
    return [10, 15, 20].includes(ticketCount)
  }
  // P638 and T539 upstream canonical authorities do not have 10, 15, or 20 ticket replay evidence
  return false
}

export function getCanonicalSource(game: ReplayOverviewGame): string {
  if (game === 'B649') return '/api/v1/b649-multi-ticket-records'
  if (game === 'P638') return '/api/v1/p638-historical/runs'
  if (game === 'T539') return '/api/v1/t539-historical/runs'
  return 'unknown'
}

export function getUnavailableReason(
  game: ReplayOverviewGame,
  ticketCount: ReplayOverviewTicketCount,
): string {
  if (game === 'P638') {
    return `No canonical ${ticketCount}-ticket backtest evidence is recorded in P638 upstream authority. Upstream P638 replay is restricted to single-ticket (1-ticket) runs.`
  }
  if (game === 'T539') {
    return `No canonical ${ticketCount}-ticket backtest evidence is recorded in T539 upstream authority. Upstream T539 replay is restricted to single-ticket (1-ticket) runs.`
  }
  return `No canonical multi-ticket replay evidence exists for ${game} with ${ticketCount} tickets.`
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

export function formatCoverage(coverage: number | null | undefined): string {
  if (coverage === null || coverage === undefined || Number.isNaN(coverage)) return 'Unavailable'
  return `${(coverage * 100).toFixed(1)}%`
}

export function extractBestHit(prizeCounts: ReplayOverviewPrizeCounts | null | undefined): string {
  if (!prizeCounts) return 'Unavailable'
  if (prizeCounts.first > 0) return `1st Prize (${prizeCounts.first})`
  if (prizeCounts.second > 0) return `2nd Prize (${prizeCounts.second})`
  if (prizeCounts.third > 0) return `3rd Prize (${prizeCounts.third})`
  if (prizeCounts.fourth > 0) return `4th Prize (${prizeCounts.fourth})`
  if (prizeCounts.fifth > 0) return `5th Prize (${prizeCounts.fifth})`
  if (prizeCounts.sixth && prizeCounts.sixth > 0) return `6th Prize (${prizeCounts.sixth})`
  if (prizeCounts.seventh && prizeCounts.seventh > 0) return `7th Prize (${prizeCounts.seventh})`
  if (prizeCounts.general && prizeCounts.general > 0) return `General (${prizeCounts.general})`
  return 'None'
}

export function deriveEvidenceStatus(
  isAvailable: boolean,
  reproductionStatus: string,
  officialRank: number | null,
  hitRate: number | null,
  baselineDelta: number | null,
  unrankedReason?: string | null,
): string {
  if (!isAvailable) return 'EVIDENCE UNAVAILABLE'
  if (reproductionStatus === 'CLOSED_UNEXECUTABLE') return 'CLOSED_UNEXECUTABLE'
  if (reproductionStatus === 'DUPLICATE_ALIAS') return 'DUPLICATE_ALIAS'
  if (unrankedReason) return unrankedReason
  if (officialRank === 1 && hitRate !== null && hitRate > 0) return 'DESCRIPTIVE LEADER'
  if (officialRank !== null && officialRank <= 3 && baselineDelta !== null && baselineDelta > 0)
    return 'TOP TIER'
  if (baselineDelta !== null && baselineDelta > 0) return 'ABOVE BASELINE'
  if (baselineDelta !== null && baselineDelta <= 0) return 'NO ADJUSTED SUPERIORITY'
  return 'BACKTESTED'
}

export function transformB649Record(
  record: B649MultiTicketRecord,
  ticketCount: ReplayOverviewTicketCount,
  window: ReplayOverviewWindow,
): ReplayOverviewStrategyItem {
  const isAvailable =
    record.reproduction_status === 'BACKTESTED' &&
    record.official_any_prize_rate !== null &&
    record.official_rank !== null

  const officialRank = record.official_rank ?? null
  const rank = record.official_rank ?? record.rank ?? null
  const officialAnyPrizeRate = record.official_any_prize_rate
    ? Number.parseFloat(record.official_any_prize_rate)
    : record.historical_success_rate
      ? Number.parseFloat(record.historical_success_rate)
      : null
  const officialRandomBaselineProbability = record.official_random_baseline_probability
    ? Number.parseFloat(record.official_random_baseline_probability)
    : record.random_baseline_success_rate
      ? Number.parseFloat(record.random_baseline_success_rate)
      : null
  const officialRandomBaselineDelta = record.official_random_baseline_delta
    ? Number.parseFloat(record.official_random_baseline_delta)
    : record.random_baseline_rate_difference
      ? Number.parseFloat(record.random_baseline_rate_difference)
      : null
  const coverage = record.coverage ? Number.parseFloat(record.coverage) : null

  const prizeCounts: ReplayOverviewPrizeCounts | null = record.official_prize_counts
    ? {
        first: record.official_prize_counts.first,
        second: record.official_prize_counts.second,
        third: record.official_prize_counts.third,
        fourth: record.official_prize_counts.fourth,
        fifth: record.official_prize_counts.fifth,
        sixth: record.official_prize_counts.sixth,
        seventh: record.official_prize_counts.seventh,
        general: record.official_prize_counts.general,
      }
    : null

  const bestHit = extractBestHit(prizeCounts)
  const evidenceStatus = deriveEvidenceStatus(
    isAvailable,
    record.reproduction_status,
    officialRank,
    officialAnyPrizeRate,
    officialRandomBaselineDelta,
    record.unranked_reason,
  )

  const notes =
    record.reproduction_status === 'CLOSED_UNEXECUTABLE'
      ? record.unranked_reason ?? 'Excluded from multi-ticket execution'
      : record.reproduction_status === 'DUPLICATE_ALIAS'
        ? `Duplicate alias of ${record.duplicate_alias_target ?? 'canonical strategy'}`
        : record.unranked_reason ?? 'Descriptive historical replay evidence'

  return {
    id: `B649-${record.strategy_id}-${ticketCount}-${window}`,
    game: 'B649',
    ticketCount,
    window,
    strategyId: record.strategy_id,
    strategyVersion: record.strategy_version,
    legacyMethodId: record.legacy_method_id,
    methodFamily: record.method_family,
    reproductionStatus: record.reproduction_status as ReplayOverviewReproductionStatus,
    duplicateAliasTarget: record.duplicate_alias_target,
    officialRank,
    rank,
    officialAnyPrizeCount: record.official_any_prize_count ?? record.success_count ?? null,
    officialAnyPrizeRate,
    officialAnyPrizeRateFormatted: isAvailable
      ? formatRatePercentage(officialAnyPrizeRate)
      : 'Unavailable',
    officialRandomBaselineProbability,
    officialRandomBaselineProbabilityFormatted: isAvailable
      ? formatRatePercentage(officialRandomBaselineProbability)
      : 'Unavailable',
    officialRandomBaselineDelta,
    officialRandomBaselineDeltaFormatted: isAvailable
      ? formatDeltaPercentage(officialRandomBaselineDelta)
      : 'Unavailable',
    unrankedReason: record.unranked_reason,
    successCount: record.success_count ?? null,
    effectiveBacktestDrawCount:
      record.effective_backtest_draw_count ?? record.window_available_draws ?? null,
    successfulExecutionCount: record.successful_execution_count ?? null,
    coverage,
    coverageFormatted: isAvailable ? formatCoverage(coverage) : 'Unavailable',
    bestHit: isAvailable ? bestHit : 'Unavailable',
    prizeCounts: isAvailable ? prizeCounts : null,
    isAvailable,
    evidenceStatus,
    notes,
  }
}

export async function fetchReplayOverviewData(
  game: ReplayOverviewGame,
  ticketCount: ReplayOverviewTicketCount,
  window: ReplayOverviewWindow,
  signal?: AbortSignal,
): Promise<{ items: ReplayOverviewStrategyItem[]; summary: ReplayOverviewSummary }> {
  if (!isDimensionAvailable(game, ticketCount)) {
    const unavailableReason = getUnavailableReason(game, ticketCount)
    return {
      items: [],
      summary: {
        game,
        ticketCount,
        window,
        totalStrategies: 0,
        rankedStrategies: 0,
        backtestedStrategies: 0,
        unrankedStrategies: 0,
        observationCoverageRate: null,
        topStrategy: null,
        isDimensionAvailable: false,
        unavailableReason,
        canonicalSource: getCanonicalSource(game),
        fullUniverseStatus: 'UNRESOLVED',
      },
    }
  }

  // B649 implementation: fetch all pages to guarantee full strategy universe
  const summaryPayload = await fetchB649MultiTicketSummary(signal)
  if (!summaryPayload.records_available) {
    return {
      items: [],
      summary: {
        game,
        ticketCount,
        window,
        totalStrategies: summaryPayload.progress.total_strategy_count,
        rankedStrategies: 0,
        backtestedStrategies: 0,
        unrankedStrategies: summaryPayload.progress.total_strategy_count,
        observationCoverageRate: null,
        topStrategy: null,
        isDimensionAvailable: false,
        unavailableReason: 'B649 multi-ticket record dataset is currently unavailable on server.',
        canonicalSource: getCanonicalSource(game),
        fullUniverseStatus: 'UNRESOLVED',
      },
    }
  }

  let offset = 0
  const limit = 100
  let hasMore = true
  const rawRecords: B649MultiTicketRecord[] = []

  while (hasMore) {
    const page = await fetchB649MultiTicketRecords(
      {
        prefixCount: ticketCount as B649PrefixCount,
        window: window as B649HistoryWindow,
        criterion: 'M3_PLUS',
        limit,
        offset,
      },
      signal,
    )
    rawRecords.push(...page.items)
    offset += limit
    hasMore = rawRecords.length < page.total
  }

  const items = rawRecords.map((r) => transformB649Record(r, ticketCount, window))

  const rankedItems = items.filter((item) => item.officialRank !== null)
  rankedItems.sort((a, b) => (a.officialRank ?? 999999) - (b.officialRank ?? 999999))

  const topItem = rankedItems[0] ?? null
  const backtestedCount = items.filter((item) => item.reproductionStatus === 'BACKTESTED').length
  const unrankedCount = items.filter((item) => item.officialRank === null).length

  let totalCoverage = 0
  let coverageCount = 0
  for (const item of items) {
    if (item.coverage !== null) {
      totalCoverage += item.coverage
      coverageCount += 1
    }
  }
  const averageCoverage = coverageCount > 0 ? totalCoverage / coverageCount : null

  return {
    items,
    summary: {
      game,
      ticketCount,
      window,
      totalStrategies: items.length,
      rankedStrategies: rankedItems.length,
      backtestedStrategies: backtestedCount,
      unrankedStrategies: unrankedCount,
      observationCoverageRate: averageCoverage,
      topStrategy: topItem
        ? {
            strategyId: topItem.strategyId,
            officialRank: topItem.officialRank ?? 1,
            hitRateFormatted: topItem.officialAnyPrizeRateFormatted,
          }
        : null,
      isDimensionAvailable: true,
      unavailableReason: null,
      canonicalSource: getCanonicalSource(game),
      fullUniverseStatus: 'COMPLETE',
    },
  }
}

export async function fetchReplayOverviewMatrixData(
  game: ReplayOverviewGame,
  window: ReplayOverviewWindow,
  signal?: AbortSignal,
): Promise<{ rows: ReplayOverviewMatrixRow[]; isDimensionAvailable: boolean; unavailableReason: string | null }> {
  if (game !== 'B649') {
    return {
      rows: [],
      isDimensionAvailable: false,
      unavailableReason: getUnavailableReason(game, 10),
    }
  }

  const [res10, res15, res20] = await Promise.all([
    fetchReplayOverviewData('B649', 10, window, signal),
    fetchReplayOverviewData('B649', 15, window, signal),
    fetchReplayOverviewData('B649', 20, window, signal),
  ])

  const map10 = new Map<string, ReplayOverviewStrategyItem>()
  const map15 = new Map<string, ReplayOverviewStrategyItem>()
  const map20 = new Map<string, ReplayOverviewStrategyItem>()

  for (const item of res10.items) map10.set(item.strategyId, item)
  for (const item of res15.items) map15.set(item.strategyId, item)
  for (const item of res20.items) map20.set(item.strategyId, item)

  const allStrategyIds = Array.from(
    new Set([...map10.keys(), ...map15.keys(), ...map20.keys()]),
  )

  const rows: ReplayOverviewMatrixRow[] = allStrategyIds.map((strategyId) => {
    const item10 = map10.get(strategyId) ?? null
    const item15 = map15.get(strategyId) ?? null
    const item20 = map20.get(strategyId) ?? null
    const sample = item10 ?? item15 ?? item20
    return {
      strategyId,
      strategyLabel: sample?.legacyMethodId ?? strategyId,
      methodFamily: sample?.methodFamily ?? 'general',
      reproductionStatus: sample?.reproductionStatus ?? 'UNAVAILABLE',
      cells: {
        10: item10,
        15: item15,
        20: item20,
      },
    }
  })

  // Sort rows by default: best rank in 10 tickets first, then unranked
  rows.sort((a, b) => {
    const rankA = a.cells[10]?.officialRank ?? 999999
    const rankB = b.cells[10]?.officialRank ?? 999999
    return rankA - rankB
  })

  return {
    rows,
    isDimensionAvailable: true,
    unavailableReason: null,
  }
}
