import {
  T539_AVAILABLE_TICKET_COUNTS,
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
  getT539Rankings,
  listT539Runs,
  listT539Strategies,
  type T539Ranking,
  type T539Run,
  type T539Strategy,
} from '../../../api/t539Historical'

function formatRate(val: number | null | undefined): string {
  if (val === null || val === undefined || Number.isNaN(val)) return 'Unavailable'
  return `${(val * 100).toFixed(2)}%`
}

function extractBestHit(prizeCounts: ReplayPrizeCounts | null | undefined): string {
  if (!prizeCounts) return 'Unavailable'
  if (prizeCounts.first > 0) return `1st Prize (${prizeCounts.first})`
  if (prizeCounts.second > 0) return `2nd Prize (${prizeCounts.second})`
  if (prizeCounts.third > 0) return `3rd Prize (${prizeCounts.third})`
  if (prizeCounts.fourth > 0) return `4th Prize (${prizeCounts.fourth})`
  if (prizeCounts.fifth > 0) return `5th Prize (${prizeCounts.fifth})`
  return 'None'
}

function deriveEvidenceStatus(
  isAvailable: boolean,
  rank: number | null,
  hitRate: number | null,
  evaluatedTargets: number | null,
): EvidenceStatusLabel {
  if (!isAvailable || hitRate === null) return 'EVIDENCE UNAVAILABLE'
  if (evaluatedTargets !== null && evaluatedTargets < 300) return 'LIMITED SAMPLE'
  if (rank === 1 && hitRate > 0) return 'DESCRIPTIVE LEADER'
  if (rank !== null && rank <= 3 && hitRate > 0.05) return 'PARETO FRONTIER'
  return 'HISTORICAL ONLY'
}

function deriveEvidenceNotes(
  isAvailable: boolean,
  rank: number | null,
  _hitRate: number | null,
  evaluatedTargets: number | null,
  ticketCount: TicketCount,
  runId: string,
): string {
  if (!isAvailable) {
    return `No canonical multi-ticket backtest evidence is recorded for ticket count ${ticketCount}.`
  }
  const notes: string[] = []
  if (rank === 1) {
    notes.push('Highest winning target rate in stored replay run')
  }
  if (evaluatedTargets !== null && evaluatedTargets < 300) {
    notes.push('Limited observation sample size')
  }
  notes.push(`Replay run ${runId}`)
  notes.push('Descriptive historical evidence only; does not infer future performance')
  return notes.join('. ') + '.'
}

function transformT539Strategy(
  strat: T539Strategy,
  ranking: T539Ranking | undefined,
  _run: T539Run | undefined,
  runId: string,
  ticketCount: TicketCount,
): ReplayExplorerItem {
  const isAvailable = strat.status === 'COMPLETE' && strat.successful_target_draw_count > 0
  const evaluatedTargets = isAvailable
    ? strat.processed_target_draw_count || strat.expected_target_draw_count
    : null
  const rank = ranking?.rank ?? null
  const hitRate = ranking ? ranking.winning_target_rate : null

  const winningTargets = ranking ? ranking.winning_target_count : null

  const prizeCounts: ReplayPrizeCounts | null = ranking
    ? {
        first: ranking.prize_tier_counts.find((p) => p.prize_tier === 'first' || p.prize_tier === '1')?.count ?? 0,
        second: ranking.prize_tier_counts.find((p) => p.prize_tier === 'second' || p.prize_tier === '2')?.count ?? 0,
        third: ranking.prize_tier_counts.find((p) => p.prize_tier === 'third' || p.prize_tier === '3')?.count ?? 0,
        fourth: ranking.prize_tier_counts.find((p) => p.prize_tier === 'fourth' || p.prize_tier === '4')?.count ?? 0,
        fifth: ranking.prize_tier_counts.find((p) => p.prize_tier === 'fifth' || p.prize_tier === '5')?.count ?? 0,
      }
    : null

  const bestHit = isAvailable ? extractBestHit(prizeCounts) : 'Unavailable'
  const evidenceStatus = deriveEvidenceStatus(isAvailable, rank, hitRate, evaluatedTargets)
  const notes = deriveEvidenceNotes(isAvailable, rank, hitRate, evaluatedTargets, ticketCount, runId)

  return {
    id: `T539-${strat.strategy_id}-${ticketCount}-${runId}`,
    game: 'T539',
    strategyId: strat.strategy_id,
    strategyVersion: strat.strategy_version,
    displayLabel: strat.strategy_id,
    methodFamily: 't539_native',
    ticketCount,
    periodKey: runId,
    periodLabel: `Run: ${runId}`,
    evaluatedTargets,
    winningTargets,
    hitRate: isAvailable ? hitRate : null,
    hitRateFormatted: isAvailable ? formatRate(hitRate) : 'Unavailable',
    rank,
    baselineProbability: null,
    baselineDelta: null,
    baselineDeltaFormatted: 'Unavailable',
    coverage: null,
    bestHit,
    prizeCounts,
    status: strat.status,
    lifecycleStatus: strat.status,
    evidenceStatus,
    notes,
    isAvailable,
    unrankedReason: isAvailable ? null : 'INSUFFICIENT_HISTORY_OR_UNEXECUTABLE',
    rawPayload: strat as unknown as Record<string, unknown>,
  }
}

function createUnavailableItem(
  strategyId: string,
  version: string,
  ticketCount: TicketCount,
  runId: string,
): ReplayExplorerItem {
  return {
    id: `T539-${strategyId}-${ticketCount}-${runId}`,
    game: 'T539',
    strategyId,
    strategyVersion: version,
    displayLabel: strategyId,
    methodFamily: 't539_native',
    ticketCount,
    periodKey: runId,
    periodLabel: `Run: ${runId}`,
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

export const t539Adapter: ReplayExplorerAdapter = {
  game: 'T539',
  gameTitle: 'T539 Replay',
  gameSubtitle: 'Canonical Daily Cash Replay Explorer',
  gameDescription: 'Multi-strategy replay evaluation and historical draw replay evidence for Daily Cash (5/39).',
  availableTicketCounts: T539_AVAILABLE_TICKET_COUNTS,
  supportsTimeWindowHorizons: false,
  supportsTargetInspection: true,
  supportsCoverageLedger: true,
  supportsTrend: true,

  async loadInitialState(signal?: AbortSignal) {
    const runsPage = await listT539Runs({ limit: 25, offset: 0 }, signal)
    const periods: PeriodOption[] = runsPage.items.map((r) => ({
      key: r.run_id,
      label: `Run: ${r.run_id}`,
      subLabel: r.status,
      drawCount: r.draw_count,
      dateRange: r.first_draw_date && r.last_draw_date ? `${r.first_draw_date} — ${r.last_draw_date}` : undefined,
    }))

    const defaultRunId = periods[0]?.key || 'default'

    let strategies: StrategyOption[] = []
    if (defaultRunId && defaultRunId !== 'default') {
      try {
        const stratPage = await listT539Strategies(defaultRunId, { limit: 200, offset: 0 }, signal)
        strategies = stratPage.items.map((s) => ({
          id: s.strategy_id,
          label: s.strategy_id,
          version: s.strategy_version,
          family: 't539_native',
          status: s.status,
          executable: s.status === 'COMPLETE',
        }))
      } catch {
        strategies = []
      }
    }

    return {
      strategies,
      periods,
      families: ['t539_native'],
      defaultPeriodKey: defaultRunId,
      defaultTicketCount: 1,
    }
  },

  async loadItems(params: ReplayQueryParams, signal?: AbortSignal): Promise<ReplayExplorerItem[]> {
    const runId = params.selectedPeriodKey
    if (!runId) return []

    const runsPage = await listT539Runs({ limit: 25, offset: 0 }, signal)
    const currentRun = runsPage.items.find((r) => r.run_id === runId)

    const [stratPage, rankingPage] = await Promise.all([
      listT539Strategies(runId, { limit: 200, offset: 0 }, signal),
      getT539Rankings(runId, signal).catch(() => ({ run_id: runId, items: [] as T539Ranking[] })),
    ])

    const rankingMap = new Map<string, T539Ranking>()
    for (const r of rankingPage.items) {
      rankingMap.set(r.strategy_id, r)
    }

    const items: ReplayExplorerItem[] = []
    const isTicketCount1Selected = params.selectedTicketCounts.includes(1)

    if (isTicketCount1Selected) {
      for (const strat of stratPage.items) {
        if (params.selectedStrategyIds.length > 0 && !params.selectedStrategyIds.includes(strat.strategy_id)) {
          continue
        }
        if (params.searchQuery) {
          const q = params.searchQuery.toLowerCase()
          if (!strat.strategy_id.toLowerCase().includes(q)) continue
        }
        const item = transformT539Strategy(
          strat,
          rankingMap.get(strat.strategy_id),
          currentRun,
          runId,
          1,
        )
        items.push(item)
      }
    }

    // Handle unavailable ticket counts (2..20)
    const unavailableCounts = params.selectedTicketCounts.filter((c) => c !== 1)
    if (unavailableCounts.length > 0) {
      const activeStrategies = stratPage.items.filter((strat) => {
        if (params.selectedStrategyIds.length > 0 && !params.selectedStrategyIds.includes(strat.strategy_id)) {
          return false
        }
        if (params.searchQuery) {
          return strat.strategy_id.toLowerCase().includes(params.searchQuery.toLowerCase())
        }
        return true
      })

      for (const strat of activeStrategies) {
        for (const count of unavailableCounts) {
          items.push(
            createUnavailableItem(
              strat.strategy_id,
              strat.strategy_version,
              count,
              runId,
            ),
          )
        }
      }
    }

    return items
  },

  async loadTrendData(
    params: ReplayQueryParams,
    items: ReplayExplorerItem[],
    _signal?: AbortSignal,
  ): Promise<TrendSeries[]> {
    const runId = params.selectedPeriodKey
    if (!runId) return []

    const targetStrategyIds = params.selectedStrategyIds.length > 0
      ? params.selectedStrategyIds.slice(0, 4)
      : Array.from(new Set(items.map((i) => i.strategyId))).slice(0, 4)

    const seriesList: TrendSeries[] = []

    for (const stratId of targetStrategyIds) {
      const matched = items.find((i) => i.strategyId === stratId)
      const label = matched?.displayLabel || stratId
      const stratItem = matched?.rawPayload as unknown as T539Strategy | undefined

      if (stratItem && Array.isArray(stratItem.hit_distribution) && stratItem.hit_distribution.length > 0) {
        const points: TrendPoint[] = stratItem.hit_distribution.map((h) => ({
          xLabel: `${h.value} Hits`,
          xValue: h.value,
          yValue: h.count,
          yFormatted: `${h.count} targets`,
          isAvailable: true,
          tooltipText: `${label}: ${h.count} targets with ${h.value} hit(s)`,
        }))
        seriesList.push({
          strategyId: stratId,
          strategyLabel: label,
          points,
        })
      } else {
        seriesList.push({
          strategyId: stratId,
          strategyLabel: label,
          points: [],
        })
      }
    }

    return seriesList
  },
}
