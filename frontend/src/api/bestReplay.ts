import {
  fetchB649MultiTicketRecords,
  fetchB649MultiTicketSummary,
  type B649HistoryWindow,
  type B649MultiTicketRecord,
  type B649PrefixCount,
} from './b649MultiTicketRecords'
import {
  getP638Rankings,
  listP638Runs,
  type P638Ranking,
} from './p638Historical'
import {
  getT539Rankings,
  listT539Runs,
  type T539Ranking,
} from './t539Historical'
import {
  B649_AVAILABLE_TICKET_COUNTS,
  CANONICAL_HORIZONS,
  P638_AVAILABLE_TICKET_COUNTS,
  T539_AVAILABLE_TICKET_COUNTS,
  type BestReplayItem,
  type BestReplayPrizeCounts,
  type EvidenceStatusLabel,
  type GameCode,
  type HorizonKey,
  type TicketCount,
} from '../features/best-replay/types'

export function isTicketCountAvailable(game: GameCode, ticketCount: TicketCount): boolean {
  if (game === 'B649') return B649_AVAILABLE_TICKET_COUNTS.includes(ticketCount)
  if (game === 'P638') return P638_AVAILABLE_TICKET_COUNTS.includes(ticketCount)
  if (game === 'T539') return T539_AVAILABLE_TICKET_COUNTS.includes(ticketCount)
  return false
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

export function extractBestHit(prizeCounts: BestReplayPrizeCounts | null | undefined): string {
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
  rank: number | null,
  hitRate: number | null,
  baselineDelta: number | null,
  horizon: HorizonKey,
  evaluatedTargets: number,
  reproductionStatus?: string,
): EvidenceStatusLabel {
  if (!isAvailable || hitRate === null) return 'EVIDENCE UNAVAILABLE'
  if (reproductionStatus === 'CLOSED_UNEXECUTABLE') return 'EXPLORATORY'
  if (horizon === 'RECENT_50') return 'LOW POWER'
  if (evaluatedTargets > 0 && evaluatedTargets < 300) return 'LIMITED SAMPLE'
  if (rank === 1 && hitRate > 0) return 'DESCRIPTIVE LEADER'
  if (rank !== null && rank <= 3 && baselineDelta !== null && baselineDelta > 0) return 'PARETO FRONTIER'
  if (baselineDelta !== null && baselineDelta <= 0) return 'NO ADJUSTED SUPERIORITY'
  return 'HISTORICAL ONLY'
}

export function deriveEvidenceNotes(
  isAvailable: boolean,
  rank: number | null,
  baselineDelta: number | null,
  horizon: HorizonKey,
  evaluatedTargets: number,
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
  } else if (evaluatedTargets < 300) {
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

export function transformB649Record(
  record: B649MultiTicketRecord,
  horizon: HorizonKey,
  ticketCount: TicketCount,
): BestReplayItem {
  const horizonDef = CANONICAL_HORIZONS.find((h) => h.key === horizon)
  const horizonLabel = horizonDef?.label ?? horizon
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
  const evaluatedTargets =
    record.effective_backtest_draw_count ?? record.window_available_draws ?? (horizon === 'RECENT_50' ? 50 : horizon === 'RECENT_300' ? 300 : horizon === 'RECENT_750' ? 750 : 1949)
  const winningTargets = record.official_any_prize_count ?? record.success_count ?? null
  const coverage = record.coverage ? Number.parseFloat(record.coverage) : null

  const prizeCounts: BestReplayPrizeCounts | null = record.official_prize_counts
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
    rank,
    hitRate,
    baselineDelta,
    horizon,
    evaluatedTargets,
    record.reproduction_status,
  )
  const notes = deriveEvidenceNotes(
    isAvailable,
    rank,
    baselineDelta,
    horizon,
    evaluatedTargets,
    ticketCount,
  )

  return {
    id: `B649-${record.strategy_id}-${ticketCount}-${horizon}`,
    rank,
    strategyId: record.strategy_id,
    strategyVersion: record.strategy_version,
    legacyMethodId: record.legacy_method_id,
    methodFamily: record.method_family,
    game: 'B649',
    ticketCount,
    horizon,
    horizonLabel,
    evaluatedTargets: isAvailable ? evaluatedTargets : 0,
    winningTargets: isAvailable ? winningTargets : null,
    hitRate: isAvailable ? hitRate : null,
    hitRateFormatted: isAvailable ? formatRatePercentage(hitRate) : 'Unavailable',
    baselineProbability: isAvailable ? baselineProbability : null,
    baselineDelta: isAvailable ? baselineDelta : null,
    baselineDeltaFormatted: isAvailable ? formatDeltaPercentage(baselineDelta) : 'Unavailable',
    coverage: isAvailable ? coverage : null,
    bestHit: isAvailable ? bestHit : 'Unavailable',
    prizeCounts: isAvailable ? prizeCounts : null,
    evidenceStatus,
    notes,
    isAvailable,
    reproductionStatus: record.reproduction_status,
    unrankedReason: record.unranked_reason,
  }
}

export function createUnavailableItem(
  game: GameCode,
  strategyId: string,
  strategyVersion: string,
  methodFamily: string,
  ticketCount: TicketCount,
  horizon: HorizonKey,
): BestReplayItem {
  const horizonDef = CANONICAL_HORIZONS.find((h) => h.key === horizon)
  const horizonLabel = horizonDef?.label ?? horizon
  return {
    id: `${game}-${strategyId}-${ticketCount}-${horizon}`,
    rank: null,
    strategyId,
    strategyVersion,
    methodFamily,
    game,
    ticketCount,
    horizon,
    horizonLabel,
    evaluatedTargets: 0,
    winningTargets: null,
    hitRate: null,
    hitRateFormatted: 'Unavailable',
    baselineProbability: null,
    baselineDelta: null,
    baselineDeltaFormatted: 'Unavailable',
    coverage: null,
    bestHit: 'Unavailable',
    prizeCounts: null,
    evidenceStatus: 'EVIDENCE UNAVAILABLE',
    notes: `No canonical multi-ticket backtest evidence is recorded for ticket count ${ticketCount}.`,
    isAvailable: false,
  }
}

export async function loadB649BestReplayData(
  ticketCounts: readonly TicketCount[],
  horizon: HorizonKey,
  signal?: AbortSignal,
): Promise<BestReplayItem[]> {
  const summary = await fetchB649MultiTicketSummary(signal)
  if (!summary.records_available) return []

  const availableCountsToFetch = ticketCounts.filter((c) =>
    B649_AVAILABLE_TICKET_COUNTS.includes(c),
  ) as B649PrefixCount[]

  const results: BestReplayItem[] = []

  const windowKey = horizon as B649HistoryWindow

  const fetchPromises = availableCountsToFetch.map(async (prefixCount) => {
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
        },
        signal,
      )
      records.push(...page.items)
      offset += limit
      hasMore = records.length < page.total
    }

    return records.map((rec) => transformB649Record(rec, horizon, prefixCount))
  })

  const fetchedArrays = await Promise.all(fetchPromises)
  for (const items of fetchedArrays) {
    results.push(...items)
  }

  return results
}

export async function loadP638BestReplayData(
  ticketCounts: readonly TicketCount[],
  horizon: HorizonKey,
  signal?: AbortSignal,
): Promise<BestReplayItem[]> {
  if (!ticketCounts.includes(1)) return []
  try {
    const runsPage = await listP638Runs({ limit: 5, offset: 0 }, signal)
    if (!runsPage.items.length) return []
    const latestRun = runsPage.items[0]
    if (!latestRun) return []

    const rankingPage = await getP638Rankings(latestRun.run_id, signal)
    const horizonDef = CANONICAL_HORIZONS.find((h) => h.key === horizon)
    const horizonLabel = horizonDef?.label ?? horizon

    return rankingPage.items.map((r: P638Ranking): BestReplayItem => {
      const evaluatedTargets = latestRun.complete_target_count || 1000
      const hitRate = r.winning_target_rate
      const winningTargets = Math.round(hitRate * evaluatedTargets)
      const rank = r.rank

      const prizeCounts: BestReplayPrizeCounts = {
        first: r.prize_tier_counts.find((p) => p.prize_tier === 'first' || p.prize_tier === '1')?.count ?? 0,
        second: r.prize_tier_counts.find((p) => p.prize_tier === 'second' || p.prize_tier === '2')?.count ?? 0,
        third: r.prize_tier_counts.find((p) => p.prize_tier === 'third' || p.prize_tier === '3')?.count ?? 0,
        fourth: r.prize_tier_counts.find((p) => p.prize_tier === 'fourth' || p.prize_tier === '4')?.count ?? 0,
        fifth: r.prize_tier_counts.find((p) => p.prize_tier === 'fifth' || p.prize_tier === '5')?.count ?? 0,
      }

      const evidenceStatus = deriveEvidenceStatus(
        true,
        rank,
        hitRate,
        null,
        horizon,
        evaluatedTargets,
      )
      const notes = deriveEvidenceNotes(
        true,
        rank,
        null,
        horizon,
        evaluatedTargets,
        1,
      )

      return {
        id: `P638-${r.strategy_id}-1-${horizon}`,
        rank,
        strategyId: r.strategy_id,
        strategyVersion: 'v1.0',
        methodFamily: 'p638_native',
        game: 'P638',
        ticketCount: 1,
        horizon,
        horizonLabel,
        evaluatedTargets,
        winningTargets,
        hitRate,
        hitRateFormatted: formatRatePercentage(hitRate),
        baselineProbability: null,
        baselineDelta: null,
        baselineDeltaFormatted: 'Unavailable',
        coverage: null,
        bestHit: extractBestHit(prizeCounts),
        prizeCounts,
        evidenceStatus,
        notes,
        isAvailable: true,
      }
    })
  } catch {
    return []
  }
}

export async function loadT539BestReplayData(
  ticketCounts: readonly TicketCount[],
  horizon: HorizonKey,
  signal?: AbortSignal,
): Promise<BestReplayItem[]> {
  if (!ticketCounts.includes(1)) return []
  try {
    const runsPage = await listT539Runs({ limit: 5, offset: 0 }, signal)
    if (!runsPage.items.length) return []
    const latestRun = runsPage.items[0]
    if (!latestRun) return []

    const rankingPage = await getT539Rankings(latestRun.run_id, signal)
    const horizonDef = CANONICAL_HORIZONS.find((h) => h.key === horizon)
    const horizonLabel = horizonDef?.label ?? horizon

    return rankingPage.items.map((r: T539Ranking): BestReplayItem => {
      const evaluatedTargets = 1000
      const hitRate = r.winning_target_rate
      const winningTargets = Math.round(hitRate * evaluatedTargets)
      const rank = r.rank

      const prizeCounts: BestReplayPrizeCounts = {
        first: r.prize_tier_counts.find((p) => p.prize_tier === 'first' || p.prize_tier === '1')?.count ?? 0,
        second: r.prize_tier_counts.find((p) => p.prize_tier === 'second' || p.prize_tier === '2')?.count ?? 0,
        third: r.prize_tier_counts.find((p) => p.prize_tier === 'third' || p.prize_tier === '3')?.count ?? 0,
        fourth: r.prize_tier_counts.find((p) => p.prize_tier === 'fourth' || p.prize_tier === '4')?.count ?? 0,
        fifth: r.prize_tier_counts.find((p) => p.prize_tier === 'fifth' || p.prize_tier === '5')?.count ?? 0,
      }

      const evidenceStatus = deriveEvidenceStatus(
        true,
        rank,
        hitRate,
        null,
        horizon,
        evaluatedTargets,
      )
      const notes = deriveEvidenceNotes(
        true,
        rank,
        null,
        horizon,
        evaluatedTargets,
        1,
      )

      return {
        id: `T539-${r.strategy_id}-1-${horizon}`,
        rank,
        strategyId: r.strategy_id,
        strategyVersion: 'v1.0',
        methodFamily: 't539_native',
        game: 'T539',
        ticketCount: 1,
        horizon,
        horizonLabel,
        evaluatedTargets,
        winningTargets,
        hitRate,
        hitRateFormatted: formatRatePercentage(hitRate),
        baselineProbability: null,
        baselineDelta: null,
        baselineDeltaFormatted: 'Unavailable',
        coverage: null,
        bestHit: extractBestHit(prizeCounts),
        prizeCounts,
        evidenceStatus,
        notes,
        isAvailable: true,
      }
    })
  } catch {
    return []
  }
}
