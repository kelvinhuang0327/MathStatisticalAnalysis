import {
  type B649Sealed084ReplayResult,
  type B649Sealed084ReplayStatus,
  type B649Sealed084Window,
} from '../../api/rankingMatrix'
import {
  SEALED_084_COMMON_COMPARISONS,
  type Sealed084CommonComparison,
} from './sealed084ComparisonEvidence'

export interface Sealed084Strategy {
  strategyId: string
  strategyVersion: string
  ticketCount: number
  sourceTaskId: string
}

export const SEALED_084_STRATEGIES: readonly Sealed084Strategy[] = [
  {
    strategyId: 'research_causal_renewal_hazard_k2',
    strategyVersion: 'v1.0',
    ticketCount: 2,
    sourceTaskId: 'NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1',
  },
  {
    strategyId: 'research_conditional_transfer_entropy_k2',
    strategyVersion: 'v1.0',
    ticketCount: 2,
    sourceTaskId: 'NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1',
  },
  {
    strategyId: 'b649_new_horizon_minimax_disagreement_r1',
    strategyVersion: 'v0.1',
    ticketCount: 2,
    sourceTaskId: 'NUMBER2_A_B649_HORIZON_V01_K2_SEALED084_REPLAY_20261102_R1',
  },
  {
    strategyId: 'research_causal_renewal_hazard_k3',
    strategyVersion: 'v1.0',
    ticketCount: 3,
    sourceTaskId: 'NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1',
  },
  {
    strategyId: 'research_conditional_transfer_entropy_k3',
    strategyVersion: 'v1.0',
    ticketCount: 3,
    sourceTaskId: 'NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1',
  },
  {
    strategyId: 'research_causal_renewal_hazard_k5',
    strategyVersion: 'v1.0',
    ticketCount: 5,
    sourceTaskId: 'NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1',
  },
  {
    strategyId: 'research_conditional_transfer_entropy_k5',
    strategyVersion: 'v1.0',
    ticketCount: 5,
    sourceTaskId: 'NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1',
  },
]

export const SEALED_084_WINDOWS: readonly { key: B649Sealed084Window; label: string }[] = [
  { key: 'FULL', label: 'FULL' },
  { key: 'RECENT_750', label: '近 750 期' },
  { key: 'RECENT_300', label: '近 300 期' },
  { key: 'RECENT_50', label: '近 50 期' },
]

export type Sealed084CellStatus =
  | 'READY'
  | 'SOURCE_UNAVAILABLE'
  | 'NO_DATA'
  | 'VERSION_MISMATCH'
  | 'INVALID_DATA'
  | 'DUPLICATE_DATA'

export type Sealed084NativeCell =
  | { status: 'READY'; result: B649Sealed084ReplayResult }
  | { status: Exclude<Sealed084CellStatus, 'READY'> }

export function getSealed084NativeCell(
  results: readonly B649Sealed084ReplayResult[],
  strategy: Sealed084Strategy,
  window: B649Sealed084Window,
  sourceReady: boolean,
  sourceStatus: B649Sealed084ReplayStatus | null,
): Sealed084NativeCell {
  if (!sourceReady) return { status: 'SOURCE_UNAVAILABLE' }

  const matching = results.filter((result) =>
    result.strategy_id === strategy.strategyId &&
    result.ticket_count === strategy.ticketCount &&
    result.window === window,
  )
  if (!matching.length) return { status: 'NO_DATA' }
  if (matching.length !== 1) return { status: 'DUPLICATE_DATA' }

  const result = matching[0]!
  if (result.strategy_version !== strategy.strategyVersion) return { status: 'VERSION_MISMATCH' }
  const expectedSource = sourceStatus?.sources.find((source) => source.source_task_id === strategy.sourceTaskId)
  if (
    result.game !== 'BIG_LOTTO' ||
    result.source_task_id !== strategy.sourceTaskId ||
    !expectedSource ||
    result.source_artifact_identity !== expectedSource.source_artifact_identity ||
    result.source_validation_status !== expectedSource.source_validation_status ||
    result.draw_source_status !== expectedSource.draw_source_status ||
    result.original_draw_data_v3_status !== expectedSource.original_draw_data_v3_status ||
    result.source_gaps !== expectedSource.source_gaps ||
    result.source_cutoff !== '115000084' ||
    result.source_tier !== 'SEALED_ATTESTED_DRAW_ROWS' ||
    result.historical_replay_status !== 'SEALED_084_RESEARCH_REPLAY' ||
    !Number.isInteger(result.successful_issues) ||
    !Number.isInteger(result.evaluated_issues) ||
    result.successful_issues < 0 ||
    result.evaluated_issues <= 0 ||
    result.successful_issues > result.evaluated_issues ||
    !Number.isFinite(result.success_rate) ||
    result.success_rate < 0 ||
    result.success_rate > 1 ||
    Math.abs(result.success_rate - result.successful_issues / result.evaluated_issues) > 1e-12
  ) {
    return { status: 'INVALID_DATA' }
  }
  return { status: 'READY', result }
}

export function getSealed084CommonComparison(
  strategy: Sealed084Strategy,
  window: B649Sealed084Window,
): Sealed084CommonComparison | undefined {
  return SEALED_084_COMMON_COMPARISONS.find((comparison) =>
    comparison.strategyId === strategy.strategyId &&
    comparison.ticketCount === strategy.ticketCount &&
    comparison.window === window,
  )
}

export function serializeSealed084ManualReviewCsv(
  results: readonly B649Sealed084ReplayResult[],
  sourceStatus: B649Sealed084ReplayStatus | null,
  sourceReady: boolean,
): string {
  const columns = [
    'game',
    'strategy_id',
    'strategy_version',
    'ticket_count',
    'source_status',
    'source_cutoff',
    'source_tier',
    'source_task_id',
    'source_artifact_identity',
    'source_validation_status',
    'draw_source_status',
    'original_draw_data_v3_status',
    'source_gaps',
  ]
  for (const window of SEALED_084_WINDOWS) {
    const suffix = window.key.toLowerCase()
    columns.push(
      `native_${suffix}_status`,
      `native_${suffix}_successful_issues`,
      `native_${suffix}_evaluated_issues`,
      `native_${suffix}_success_rate`,
      `native_${suffix}_comparability_status`,
      `common_${suffix}_comparison_window`,
      `common_${suffix}_successful_issues`,
      `common_${suffix}_comparable_issue_count`,
      `common_${suffix}_success_rate`,
      `common_${suffix}_comparability_status`,
      `common_${suffix}_peer_comparisons`,
    )
  }
  columns.push(
    'owner_long_rank',
    'owner_mid_rank',
    'owner_short_rank',
    'owner_reason',
    'owner_adoption',
  )

  const records = SEALED_084_STRATEGIES.map((strategy) => {
    const source = sourceStatus?.sources.find((item) => item.source_task_id === strategy.sourceTaskId)
    const row: unknown[] = [
      'BIG_LOTTO',
      strategy.strategyId,
      strategy.strategyVersion,
      strategy.ticketCount,
      sourceStatus?.status ?? 'SOURCE_UNAVAILABLE',
      sourceStatus?.source_cutoff ?? '',
      sourceStatus?.source_tier ?? '',
      strategy.sourceTaskId,
      source?.source_artifact_identity ?? '',
      source?.source_validation_status ?? '',
      source?.draw_source_status ?? '',
      source?.original_draw_data_v3_status ?? '',
      source?.source_gaps ?? '',
    ]
    for (const window of SEALED_084_WINDOWS) {
      const native = getSealed084NativeCell(results, strategy, window.key, sourceReady, sourceStatus)
      const common = getSealed084CommonComparison(strategy, window.key)
      row.push(
        native.status,
        native.status === 'READY' ? native.result.successful_issues : '',
        native.status === 'READY' ? native.result.evaluated_issues : '',
        native.status === 'READY' ? native.result.success_rate : '',
        native.status === 'READY' ? native.result.comparability_status : '',
        common?.comparisonWindow ?? '',
        common?.successfulIssues ?? '',
        common?.comparableIssueCount ?? '',
        common?.successRate ?? '',
        common?.comparabilityStatus ?? '',
        common ? JSON.stringify(common.peers) : '',
      )
    }
    row.push('', '', '', '', '')
    return row.map(escapeCsvCell).join(',')
  })
  return [columns.map(escapeCsvCell).join(','), ...records].join('\r\n')
}

function escapeCsvCell(value: unknown): string {
  if (value === null || value === undefined || value === '') return ''
  const text = String(value)
  return `"${text.replaceAll('"', '""')}"`
}
