import {
  P638_AVAILABLE_TICKET_COUNTS,
  type EvidenceStatusLabel,
  type PeriodOption,
  type ReplayExplorerAdapter,
  type ReplayExplorerItem,
  type ReplayPrizeCounts,
  type ReplayQueryParams,
  type StrategyOption,
  type TargetDetailRecord,
  type TicketCount,
  type TrendPoint,
  type TrendSeries,
} from '../types'

import {
  getP638Rankings,
  listP638Replay,
  listP638Runs,
  listP638Strategies,
  type P638Ranking,
  type P638Replay,
  type P638Run,
  type P638Strategy,
} from '../../../api/p638Historical'

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

function transformP638Strategy(
  strat: P638Strategy,
  ranking: P638Ranking | undefined,
  _run: P638Run | undefined,
  runId: string,
  ticketCount: TicketCount,
): ReplayExplorerItem {
  const isAvailable = strat.replay_status === 'COMPLETE' && strat.complete_target_count > 0
  const evaluatedTargets = isAvailable ? strat.complete_target_count : null
  const rank = ranking?.rank ?? null
  const hitRate = ranking ? ranking.winning_target_rate : null

  const winningTargets = hitRate !== null && evaluatedTargets !== null
    ? Math.round(hitRate * evaluatedTargets)
    : null

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
    id: `P638-${strat.strategy_id}-${ticketCount}-${runId}`,
    game: 'P638',
    strategyId: strat.strategy_id,
    strategyVersion: strat.strategy_version,
    displayLabel: strat.display_label || strat.strategy_id,
    methodFamily: 'p638_native',
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
    status: strat.replay_status,
    lifecycleStatus: strat.lifecycle_status,
    evidenceStatus,
    notes,
    isAvailable,
    unrankedReason: isAvailable ? null : 'INSUFFICIENT_HISTORY_OR_UNEXECUTABLE',
    rawPayload: strat as unknown as Record<string, unknown>,
  }
}

function createUnavailableItem(
  strategyId: string,
  displayLabel: string,
  version: string,
  ticketCount: TicketCount,
  runId: string,
): ReplayExplorerItem {
  return {
    id: `P638-${strategyId}-${ticketCount}-${runId}`,
    game: 'P638',
    strategyId,
    strategyVersion: version,
    displayLabel,
    methodFamily: 'p638_native',
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

export const p638Adapter: ReplayExplorerAdapter = {
  game: 'P638',
  gameTitle: 'P638 Replay',
  gameSubtitle: 'Canonical Historical Replay Explorer',
  gameDescription: 'Multi-strategy replay evaluation and historical draw replay evidence for Power Lotto (6/38 + 1/8).',
  availableTicketCounts: P638_AVAILABLE_TICKET_COUNTS,
  supportsTimeWindowHorizons: false,
  supportsTargetInspection: true,
  supportsCoverageLedger: false,
  supportsTrend: true,

  async loadInitialState(signal?: AbortSignal) {
    const runsPage = await listP638Runs({ limit: 25, offset: 0 }, signal)
    const periods: PeriodOption[] = runsPage.items.map((r) => ({
      key: r.run_id,
      label: `Run: ${r.run_id}`,
      subLabel: r.status,
      drawCount: r.complete_target_count || r.draw_count,
      dateRange: r.first_draw_date && r.last_draw_date ? `${r.first_draw_date} — ${r.last_draw_date}` : undefined,
    }))

    const defaultRunId = periods[0]?.key || 'default'

    let strategies: StrategyOption[] = []
    if (defaultRunId && defaultRunId !== 'default') {
      try {
        const stratPage = await listP638Strategies(defaultRunId, { limit: 200, offset: 0 }, signal)
        strategies = stratPage.items.map((s) => ({
          id: s.strategy_id,
          label: s.display_label || s.strategy_id,
          version: s.strategy_version,
          family: 'p638_native',
          status: s.replay_status,
          executable: s.executable,
        }))
      } catch {
        strategies = []
      }
    }

    return {
      strategies,
      periods,
      families: ['p638_native'],
      defaultPeriodKey: defaultRunId,
      defaultTicketCount: 1,
    }
  },

  async loadItems(params: ReplayQueryParams, signal?: AbortSignal): Promise<ReplayExplorerItem[]> {
    const runId = params.selectedPeriodKey
    if (!runId) return []

    const runsPage = await listP638Runs({ limit: 25, offset: 0 }, signal)
    const currentRun = runsPage.items.find((r) => r.run_id === runId)

    const [stratPage, rankingPage] = await Promise.all([
      listP638Strategies(runId, { limit: 200, offset: 0 }, signal),
      getP638Rankings(runId, signal).catch(() => ({ run_id: runId, items: [] as P638Ranking[] })),
    ])

    const rankingMap = new Map<string, P638Ranking>()
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
          const matches = strat.strategy_id.toLowerCase().includes(q) ||
            strat.display_label.toLowerCase().includes(q)
          if (!matches) continue
        }
        const item = transformP638Strategy(
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
          const q = params.searchQuery.toLowerCase()
          return strat.strategy_id.toLowerCase().includes(q) || strat.display_label.toLowerCase().includes(q)
        }
        return true
      })

      for (const strat of activeStrategies) {
        for (const count of unavailableCounts) {
          items.push(
            createUnavailableItem(
              strat.strategy_id,
              strat.display_label || strat.strategy_id,
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
    signal?: AbortSignal,
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

      try {
        const replayPage = await listP638Replay(
          runId,
          { strategyId: stratId, limit: 100, offset: 0 },
          signal,
        )

        if (!replayPage.items.length) {
          seriesList.push({
            strategyId: stratId,
            strategyLabel: label,
            points: [],
          })
          continue
        }

        let cumulativeWins = 0
        const points: TrendPoint[] = []

        const sortedItems = [...replayPage.items].sort((a, b) =>
          Number.parseInt(a.target_id.replace(/\D/g, '') || '0', 10) -
          Number.parseInt(b.target_id.replace(/\D/g, '') || '0', 10),
        )

        const step = Math.max(1, Math.floor(sortedItems.length / 15))
        for (let i = 0; i < sortedItems.length; i++) {
          const item = sortedItems[i]!
          const hasWin = item.tickets.some((t) => t.is_winner || (t.prize_tier && t.prize_tier !== 'none'))
          if (hasWin) cumulativeWins++

          if (i % step === 0 || i === sortedItems.length - 1) {
            const drawIndex = i + 1
            const rollingRate = cumulativeWins / drawIndex
            const drawLabel = `Draw ${item.target_id}`
            points.push({
              xLabel: drawLabel,
              xValue: item.target_id,
              yValue: rollingRate,
              yFormatted: formatRate(rollingRate),
              isAvailable: true,
              tooltipText: `${label} @ ${drawLabel}: ${formatRate(rollingRate)} (${cumulativeWins}/${drawIndex} hits)`,
            })
          }
        }

        seriesList.push({
          strategyId: stratId,
          strategyLabel: label,
          points,
        })
      } catch {
        seriesList.push({
          strategyId: stratId,
          strategyLabel: label,
          points: [],
        })
      }
    }

    return seriesList
  },

  async loadTargetList(
    strategyId: string,
    periodKey: string,
    ticketCount: TicketCount,
    signal?: AbortSignal,
  ): Promise<TargetDetailRecord[]> {
    if (ticketCount !== 1) return []
    try {
      const page = await listP638Replay(
        periodKey,
        { strategyId, limit: 100, offset: 0 },
        signal,
      )
      return page.items.map((it: P638Replay): TargetDetailRecord => {
        const firstTicket = it.tickets[0]
        return {
          targetId: it.target_id,
          drawNumberOrId: it.target_id,
          drawDate: null,
          status: it.status,
          predictedNumbers: firstTicket
            ? { zone1: firstTicket.predicted_zone1_numbers, zone2: firstTicket.predicted_zone2_number }
            : { zone1: [] },
          actualNumbers: firstTicket
            ? { zone1: firstTicket.actual_zone1_numbers, zone2: firstTicket.actual_zone2_number }
            : { zone1: [] },
          hitsCount: firstTicket?.zone1_hit_count ?? 0,
          specialOrZone2Hit: firstTicket?.zone2_hit,
          prizeTier: firstTicket?.prize_tier ?? null,
          prizeAmount: firstTicket?.prize_amount ?? null,
          tickets: it.tickets.map((t) => ({
            ticketPosition: t.ticket_position,
            predicted: { zone1: t.predicted_zone1_numbers, zone2: t.predicted_zone2_number },
            hitsCount: t.zone1_hit_count,
            prizeTier: t.prize_tier,
            isWinner: t.is_winner,
          })),
        }
      })
    } catch {
      return []
    }
  },
}
