import {
  deriveEvidenceNotes,
  deriveEvidenceStatus,
  extractBestHit,
  formatRatePercentage,
} from '../../api/bestReplay'
import {
  getP638Rankings,
  listP638Runs,
  type P638Ranking,
} from '../../api/p638Historical'
import {
  getT539Rankings,
  listT539Runs,
  type T539Ranking,
} from '../../api/t539Historical'
import {
  CANONICAL_HORIZONS,
  type BestReplayItem,
  type BestReplayPrizeCounts,
  type HorizonKey,
} from './types'

function getHorizonLabel(horizon: HorizonKey): string {
  return CANONICAL_HORIZONS.find((definition) => definition.key === horizon)?.label ?? horizon
}

function getPrizeCounts(items: Array<{ prize_tier: string; count: number }>): BestReplayPrizeCounts {
  return {
    first: items.find((item) => item.prize_tier === 'first' || item.prize_tier === '1')?.count ?? 0,
    second: items.find((item) => item.prize_tier === 'second' || item.prize_tier === '2')?.count ?? 0,
    third: items.find((item) => item.prize_tier === 'third' || item.prize_tier === '3')?.count ?? 0,
    fourth: items.find((item) => item.prize_tier === 'fourth' || item.prize_tier === '4')?.count ?? 0,
    fifth: items.find((item) => item.prize_tier === 'fifth' || item.prize_tier === '5')?.count ?? 0,
  }
}

function mapRanking<T extends P638Ranking | T539Ranking>(
  game: 'P638' | 'T539',
  ranking: T,
  horizon: HorizonKey,
  sourceRunId: string,
  sourceCompletedAt: string | null,
  sourceAsOfDate: string | null,
): BestReplayItem {
  const horizonLabel = getHorizonLabel(horizon)
  const strategyVersion = ranking.strategy_version || null
  const common = {
    id: `${game}-${ranking.strategy_id}-1-${horizon}`,
    strategyId: ranking.strategy_id,
    strategyVersion,
    methodFamily: game === 'P638' ? 'p638_native' : 't539_native',
    game,
    ticketCount: 1 as const,
    horizon,
    horizonLabel,
    sourceRunId,
    sourceCompletedAt,
    sourceAsOfDate,
  }

  if (horizon !== 'FULL') {
    return {
      ...common,
      rank: null,
      evaluatedTargets: null,
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
      notes: `${game} canonical evidence does not publish an exact ${horizon} ranking window. Descriptive historical evidence only; does not infer future performance.`,
      isAvailable: false,
      unavailableReasonCode: 'NO_CANONICAL_WINDOW_EVIDENCE',
    }
  }

  // Use the ranking row's own numerator, denominator, and source rate together.
  // The run-level count is not interchangeable with a row's eligible target count.
  const evaluatedTargets = ranking.eligible_target_count ?? null
  const winningTargets = ranking.winning_target_count ?? null
  const sourceRate = ranking.winning_target_rate ?? null
  const hasRate = typeof sourceRate === 'number' && Number.isFinite(sourceRate)
  const isAvailable = hasRate && evaluatedTargets !== 0
  const hitRate = isAvailable ? sourceRate : null
  const prizeCounts = getPrizeCounts(ranking.prize_tier_counts)
  const rank = ranking.rank
  const evidenceStatus = deriveEvidenceStatus(
    isAvailable,
    rank,
    hitRate,
    null,
    evaluatedTargets,
  )

  return {
    ...common,
    rank,
    evaluatedTargets,
    winningTargets,
    hitRate,
    hitRateFormatted: isAvailable ? formatRatePercentage(hitRate) : 'Unavailable',
    baselineProbability: null,
    baselineDelta: null,
    baselineDeltaFormatted: 'Unavailable',
    coverage: null,
    bestHit: isAvailable ? extractBestHit(prizeCounts) : 'Unavailable',
    prizeCounts: isAvailable ? prizeCounts : null,
    evidenceStatus,
    notes: deriveEvidenceNotes(isAvailable, rank, null, evaluatedTargets, 1),
    isAvailable,
  }
}

export async function loadP638SourceEvidence(
  horizon: HorizonKey,
  signal?: AbortSignal,
): Promise<BestReplayItem[]> {
  const runPage = await listP638Runs({ limit: 5, offset: 0 }, signal)
  const latestRun = runPage.items[0]
  if (!latestRun) return []

  const rankingPage = await getP638Rankings(latestRun.run_id, signal)
  if (rankingPage.run_id !== latestRun.run_id
    || rankingPage.items.some((ranking) => ranking.run_id !== latestRun.run_id)) {
    throw new Error('P638 rankings did not match the selected source run.')
  }

  return rankingPage.items.map((ranking) => mapRanking(
    'P638',
    ranking,
    horizon,
    latestRun.run_id,
    latestRun.completed_at || null,
    null,
  ))
}

export async function loadT539SourceEvidence(
  horizon: HorizonKey,
  signal?: AbortSignal,
): Promise<BestReplayItem[]> {
  const runPage = await listT539Runs({ limit: 5, offset: 0 }, signal)
  const latestRun = runPage.items[0]
  if (!latestRun) return []

  const rankingPage = await getT539Rankings(latestRun.run_id, signal)
  if (rankingPage.run_id !== latestRun.run_id
    || rankingPage.items.some((ranking) => ranking.run_id !== latestRun.run_id)) {
    throw new Error('T539 rankings did not match the selected source run.')
  }

  return rankingPage.items.map((ranking) => mapRanking(
    'T539',
    ranking,
    horizon,
    latestRun.run_id,
    null,
    latestRun.as_of_date || null,
  ))
}
