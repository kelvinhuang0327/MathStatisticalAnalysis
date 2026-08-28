import {
  B649_CANONICAL_HORIZONS,
  B649_AVAILABLE_TICKET_COUNTS,
  type EvidenceStatusLabel,
  type PeriodOption,
  type ReplayExplorerAdapter,
  type ReplayExplorerItem,
  type ReplayPrizeCounts,
  type ReplayQueryParams,
  type StrategyOption,
  type TicketCount,
  type TrendPoint,
  type TrendSeries,
} from '../types'

import {
  fetchB649MultiTicketRecords,
  fetchB649MultiTicketSummary,
  type B649HistoryWindow,
  type B649MultiTicketRecord,
  type B649PrefixCount,
} from '../../../api/b649MultiTicketRecords'

function formatRate(val: number | null | undefined): string {
  if (val === null || val === undefined || Number.isNaN(val)) return 'Unavailable'
  return `${(val * 100).toFixed(2)}%`
}

function formatDelta(val: number | null | undefined): string {
  if (val === null || val === undefined || Number.isNaN(val)) return 'Unavailable'
  const sign = val > 0 ? '+' : ''
  return `${sign}${(val * 100).toFixed(2)}%`
}

function extractBestHit(prizeCounts: ReplayPrizeCounts | null | undefined): string {
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

function deriveEvidenceStatus(
  isAvailable: boolean,
  rank: number | null,
  hitRate: number | null,
  baselineDelta: number | null,
  horizon: string,
  evaluatedTargets: number | null,
  reproductionStatus?: string,
): EvidenceStatusLabel {
  if (!isAvailable || hitRate === null) return 'EVIDENCE UNAVAILABLE'
  if (reproductionStatus === 'CLOSED_UNEXECUTABLE') return 'EXPLORATORY'
  if (horizon === 'RECENT_50') return 'LOW POWER'
  if (evaluatedTargets !== null && evaluatedTargets > 0 && evaluatedTargets < 300) return 'LIMITED SAMPLE'
  if (rank === 1 && hitRate > 0) return 'DESCRIPTIVE LEADER'
  if (rank !== null && rank <= 3 && baselineDelta !== null && baselineDelta > 0) return 'PARETO FRONTIER'
  if (baselineDelta !== null && baselineDelta <= 0) return 'NO ADJUSTED SUPERIORITY'
  return 'HISTORICAL ONLY'
}

function deriveEvidenceNotes(
  isAvailable: boolean,
  rank: number | null,
  baselineDelta: number | null,
  horizon: string,
  evaluatedTargets: number | null,
  ticketCount: TicketCount,
): string {
  if (!isAvailable) {
    return `No canonical multi-ticket backtest evidence is recorded for ticket count ${ticketCount}.`
  }
  const notes: string[] = []
  if (rank === 1) {
    notes.push('Historically strongest strategy at this horizon')
  }
  if (horizon === 'RECENT_50') {
    notes.push('Short-window result has low statistical power (50 historical draws)')
  } else if (evaluatedTargets !== null && evaluatedTargets < 300) {
    notes.push('Limited observation sample size')
  }
  if (baselineDelta !== null) {
    if (baselineDelta > 0) {
      notes.push('Positive descriptive lift vs uniform random baseline')
    } else if (baselineDelta < 0) {
      notes.push('No adjusted superiority demonstrated vs uniform random baseline')
    } else {
      notes.push('Equivalent to uniform random baseline')
    }
  }
  notes.push('Descriptive historical evidence only; does not infer future performance')
  return notes.join('. ') + '.'
}

function transformRecord(
  record: B649MultiTicketRecord,
  periodKey: string,
  periodLabel: string,
  ticketCount: TicketCount,
): ReplayExplorerItem {
  const isAvailable =
    record.reproduction_status === 'BACKTESTED' &&
    record.official_any_prize_rate !== null &&
    record.official_rank !== null

  const rank = record.official_rank ?? record.rank ?? null
  const hitRate = record.official_any_prize_rate
    ? Number.parseFloat(record.official_any_prize_rate)
    : record.historical_success_rate
      ? Number.parseFloat(record.historical_success_rate)
      : null
  const baselineDelta = record.official_random_baseline_delta
    ? Number.parseFloat(record.official_random_baseline_delta)
    : record.random_baseline_rate_difference
      ? Number.parseFloat(record.random_baseline_rate_difference)
      : null
  const baselineProbability = record.official_random_baseline_probability
    ? Number.parseFloat(record.official_random_baseline_probability)
    : record.random_baseline_success_rate
      ? Number.parseFloat(record.random_baseline_success_rate)
      : null
  const evaluatedTargets = isAvailable
    ? record.effective_backtest_draw_count ?? record.window_available_draws ?? (periodKey === 'RECENT_50' ? 50 : periodKey === 'RECENT_300' ? 300 : periodKey === 'RECENT_750' ? 750 : 1949)
    : null
  const winningTargets = isAvailable
    ? record.official_any_prize_count ?? record.success_count ?? null
    : null
  const coverage = isAvailable && record.coverage ? Number.parseFloat(record.coverage) : null

  const prizeCounts: ReplayPrizeCounts | null = isAvailable && record.official_prize_counts
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

  const bestHit = isAvailable ? extractBestHit(prizeCounts) : 'Unavailable'
  const evidenceStatus = deriveEvidenceStatus(
    isAvailable,
    rank,
    hitRate,
    baselineDelta,
    periodKey,
    evaluatedTargets,
    record.reproduction_status,
  )
  const notes = deriveEvidenceNotes(
    isAvailable,
    rank,
    baselineDelta,
    periodKey,
    evaluatedTargets,
    ticketCount,
  )

  return {
    id: `B649-${record.strategy_id}-${ticketCount}-${periodKey}`,
    game: 'B649',
    strategyId: record.strategy_id,
    strategyVersion: record.strategy_version,
    displayLabel: record.legacy_method_id || record.strategy_id,
    methodFamily: record.method_family,
    ticketCount,
    periodKey,
    periodLabel,
    evaluatedTargets,
    winningTargets,
    hitRate: isAvailable ? hitRate : null,
    hitRateFormatted: isAvailable ? formatRate(hitRate) : 'Unavailable',
    rank,
    baselineProbability: isAvailable ? baselineProbability : null,
    baselineDelta: isAvailable ? baselineDelta : null,
    baselineDeltaFormatted: isAvailable ? formatDelta(baselineDelta) : 'Unavailable',
    coverage,
    bestHit,
    prizeCounts,
    status: record.reproduction_status,
    reproductionStatus: record.reproduction_status,
    evidenceStatus,
    notes,
    isAvailable,
    unrankedReason: record.unranked_reason,
    rawPayload: record as unknown as Record<string, unknown>,
  }
}

function createUnavailableItem(
  strategyId: string,
  displayLabel: string,
  version: string,
  methodFamily: string | null,
  ticketCount: TicketCount,
  periodKey: string,
  periodLabel: string,
): ReplayExplorerItem {
  return {
    id: `B649-${strategyId}-${ticketCount}-${periodKey}`,
    game: 'B649',
    strategyId,
    strategyVersion: version,
    displayLabel,
    methodFamily,
    ticketCount,
    periodKey,
    periodLabel,
    evaluatedTargets: null,
    winningTargets: null,
    hitRate: null,
    hitRateFormatted: 'Unavailable',
    rank: null,
    baselineProbability: null,
    baselineDelta: null,
    baselineDeltaFormatted: 'Unavailable',
    coverage: null,
    bestHit: 'Unavailable',
    prizeCounts: null,
    status: 'UNAVAILABLE',
    evidenceStatus: 'EVIDENCE UNAVAILABLE',
    notes: `No canonical multi-ticket backtest evidence is recorded for ticket count ${ticketCount}.`,
    isAvailable: false,
    unrankedReason: 'UNAVAILABLE_TICKET_COUNT',
  }
}

export const b649Adapter: ReplayExplorerAdapter = {
  game: 'B649',
  gameTitle: 'B649 Replay',
  gameSubtitle: 'Canonical Multi-Ticket Replay Explorer',
  gameDescription: 'Multi-strategy, multi-ticket-count, and multi-horizon replay evidence for Taiwan Big Lotto (6/49).',
  availableTicketCounts: B649_AVAILABLE_TICKET_COUNTS,
  supportsTimeWindowHorizons: true,
  supportsTargetInspection: false,
  supportsCoverageLedger: false,
  supportsTrend: true,

  async loadInitialState(signal?: AbortSignal) {
    const summary = await fetchB649MultiTicketSummary(signal)
    const periods: PeriodOption[] = B649_CANONICAL_HORIZONS.map((h) => ({
      key: h.key,
      label: h.label,
      subLabel: h.shortLabel,
      drawCount: h.drawCount,
    }))

    // Load first page of records to populate initial strategy list
    let strategies: StrategyOption[] = []
    try {
      const page = await fetchB649MultiTicketRecords(
        {
          prefixCount: 5,
          window: 'FULL',
          criterion: 'M3_PLUS',
          limit: 100,
          offset: 0,
        },
        signal,
      )
      strategies = page.items.map((item) => ({
        id: item.strategy_id,
        label: item.legacy_method_id || item.strategy_id,
        version: item.strategy_version,
        family: item.method_family,
        status: item.reproduction_status,
        executable: item.reproduction_status === 'BACKTESTED',
      }))
    } catch {
      // Fallback strategies if initial fetch fails
      strategies = []
    }

    return {
      strategies,
      periods,
      families: summary.method_families,
      defaultPeriodKey: 'FULL',
      defaultTicketCount: 5,
    }
  },

  async loadItems(params: ReplayQueryParams, signal?: AbortSignal): Promise<ReplayExplorerItem[]> {
    const windowKey = (params.selectedPeriodKey || 'FULL') as B649HistoryWindow
    const horizonDef = B649_CANONICAL_HORIZONS.find((h) => h.key === windowKey)
    const periodLabel = horizonDef?.shortLabel ?? windowKey

    const validCounts = params.selectedTicketCounts.filter((c) =>
      B649_AVAILABLE_TICKET_COUNTS.includes(c),
    ) as B649PrefixCount[]

    const unavailableCounts = params.selectedTicketCounts.filter(
      (c) => !B649_AVAILABLE_TICKET_COUNTS.includes(c),
    )

    const items: ReplayExplorerItem[] = []

    // Fetch available ticket count records
    const fetchPromises = validCounts.map(async (prefixCount) => {
      let offset = 0
      const limit = 100
      let hasMore = true
      const records: B649MultiTicketRecord[] = []

      while (hasMore) {
        const page = await fetchB649MultiTicketRecords(
          {
            prefixCount,
            window: windowKey,
            criterion: 'M3_PLUS',
            limit,
            offset,
            q: params.searchQuery || undefined,
            methodFamily: params.methodFamilyFilter && params.methodFamilyFilter !== 'ALL' ? params.methodFamilyFilter : undefined,
          },
          signal,
        )
        records.push(...page.items)
        offset += limit
        hasMore = records.length < page.total
      }

      return records.map((rec) => transformRecord(rec, windowKey, periodLabel, prefixCount))
    })

    const recordGroups = await Promise.all(fetchPromises)
    for (const group of recordGroups) {
      items.push(...group)
    }

    // If strategy filtering is active, filter available items
    let filteredItems = items
    if (params.selectedStrategyIds.length > 0) {
      const selectedSet = new Set(params.selectedStrategyIds)
      filteredItems = items.filter((item) => selectedSet.has(item.strategyId))
    }

    // For unavailable ticket counts, generate placeholder items for displayed strategies
    if (unavailableCounts.length > 0) {
      // Find distinct strategies in current items
      const knownStrategies = new Map<string, { label: string; version: string; family: string | null }>()
      for (const it of filteredItems) {
        if (!knownStrategies.has(it.strategyId)) {
          knownStrategies.set(it.strategyId, {
            label: it.displayLabel,
            version: it.strategyVersion,
            family: it.methodFamily,
          })
        }
      }

      for (const [strategyId, info] of knownStrategies.entries()) {
        for (const count of unavailableCounts) {
          filteredItems.push(
            createUnavailableItem(
              strategyId,
              info.label,
              info.version,
              info.family,
              count,
              windowKey,
              periodLabel,
            ),
          )
        }
      }
    }

    return filteredItems
  },

  async loadTrendData(
    params: ReplayQueryParams,
    items: ReplayExplorerItem[],
    signal?: AbortSignal,
  ): Promise<TrendSeries[]> {
    // Collect up to 4 strategies to show in trend
    const targetStrategyIds = params.selectedStrategyIds.length > 0
      ? params.selectedStrategyIds.slice(0, 4)
      : Array.from(new Set(items.map((i) => i.strategyId))).slice(0, 4)

    const targetTicketCount = params.selectedTicketCounts.find((c) =>
      B649_AVAILABLE_TICKET_COUNTS.includes(c),
    ) ?? 5

    const windows: B649HistoryWindow[] = ['FULL', 'RECENT_750', 'RECENT_300', 'RECENT_50']
    const windowLabels: Record<B649HistoryWindow, string> = {
      FULL: 'Full (1949 draws)',
      RECENT_750: '750 draws',
      RECENT_300: '300 draws',
      RECENT_50: '50 draws',
    }

    const seriesList: TrendSeries[] = []

    for (const stratId of targetStrategyIds) {
      const matched = items.find((i) => i.strategyId === stratId)
      const label = matched?.displayLabel || stratId
      const points: TrendPoint[] = []

      for (const win of windows) {
        try {
          const page = await fetchB649MultiTicketRecords(
            {
              prefixCount: targetTicketCount as B649PrefixCount,
              window: win,
              criterion: 'M3_PLUS',
              limit: 100,
              offset: 0,
            },
            signal,
          )
          const found = page.items.find((it) => it.strategy_id === stratId)
          if (found && found.official_any_prize_rate !== null) {
            const rate = Number.parseFloat(found.official_any_prize_rate)
            points.push({
              xLabel: windowLabels[win],
              xValue: win,
              yValue: rate,
              yFormatted: formatRate(rate),
              isAvailable: true,
              tooltipText: `${label} @ ${windowLabels[win]}: ${formatRate(rate)} (Rank #${found.official_rank ?? found.rank ?? '—'})`,
            })
          } else {
            points.push({
              xLabel: windowLabels[win],
              xValue: win,
              yValue: null,
              yFormatted: 'Unavailable',
              isAvailable: false,
            })
          }
        } catch {
          points.push({
            xLabel: windowLabels[win],
            xValue: win,
            yValue: null,
            yFormatted: 'Unavailable',
            isAvailable: false,
          })
        }
      }

      seriesList.push({
        strategyId: stratId,
        strategyLabel: label,
        points,
      })
    }

    return seriesList
  },
}
